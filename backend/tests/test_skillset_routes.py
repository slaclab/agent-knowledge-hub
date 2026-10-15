"""Tests for #006 — skillset HTTP endpoints and the skillset fields on skill endpoints."""
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import config as config_module
from app.auth import User
from app.main import create_app
from app.models.skill import Skill, SkillStatus
from app.models.skillset import Skillset, SkillsetMember
from app.services.label import label_service
from app.services.skillset import skillset_service

_TEST_SECRET = "test-secret-for-006"
OWNER = User(user_id="owner")


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(config_module.settings, "internal_api_secret", _TEST_SECRET)
    monkeypatch.setattr(config_module.settings, "admin_users", "admin")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth(user_id: str = "owner") -> dict:
    return {"X-Internal-Secret": _TEST_SECRET, "X-Forwarded-User": user_id}


async def _make_skill(slug: str, submitter: str = "author", status: SkillStatus = SkillStatus.active) -> Skill:
    skill = Skill(
        slug=slug,
        name=slug,
        repo_url=f"https://github.com/test/{slug}",
        skill_path="/",
        submitter_id=submitter,
        status=status,
    )
    await skill.insert()
    return skill


async def _skillset_with(*skill_slugs: str, slug: str = "set", owner: str = "owner") -> Skillset:
    actor = User(user_id=owner)
    await skillset_service.create(name=slug, description="", actor=actor, slug=slug)
    for skill_slug in skill_slugs:
        if await Skill.find_one(Skill.slug == skill_slug) is None:
            await _make_skill(skill_slug)
        await skillset_service.add_skill(slug, skill_slug, actor)
    return await skillset_service.get(slug)


async def _member_slugs(client: AsyncClient, slug: str = "set") -> list[str]:
    resp = await client.get(f"/api/skillsets/{slug}")
    return [s["slug"] for s in resp.json()["skills"]]


class TestSkillsetsRouterCRUD:
    async def test_create(self, client):  # I1
        resp = await client.post("/api/skillsets", json={"name": "LCLS Starter"}, headers=_auth())
        assert resp.status_code == 201
        body = resp.json()
        assert (body["slug"], body["created_by"], body["skills"], body["member_count"]) == (
            "lcls-starter", "owner", [], 0,
        )

    async def test_create_unauthenticated(self, client):  # I2
        resp = await client.post("/api/skillsets", json={"name": "LCLS Starter"})
        assert resp.status_code == 401

    async def test_create_duplicate_slug(self, client):  # I3
        await client.post("/api/skillsets", json={"name": "LCLS Starter"}, headers=_auth())
        resp = await client.post("/api/skillsets", json={"name": "LCLS Starter"}, headers=_auth())
        assert resp.status_code == 409
        assert resp.json()["suggested_slug"] == "lcls-starter-2"

    async def test_create_invalid_slug(self, client):
        resp = await client.post("/api/skillsets", json={"name": "x", "slug": "Bad Slug"}, headers=_auth())
        assert resp.status_code == 422

    async def test_list_pages_newest_first(self, client):  # I4
        for slug in ("one", "two", "three"):
            await _skillset_with(slug=slug)
        page1 = (await client.get("/api/skillsets?page_size=2")).json()
        page2 = (await client.get("/api/skillsets?page=2&page_size=2")).json()
        assert page1["total"] == 3
        assert [s["slug"] for s in page1["items"] + page2["items"]] == ["three", "two", "one"]

    async def test_detail_hydrates_members_in_order(self, client):  # I5
        first = await _make_skill("first")
        await _make_skill("second")
        await _make_skill("third")
        await label_service.add(str(first.id), "lcls", "author")
        await _skillset_with("first", "second", "third")
        await (await Skill.find_one(Skill.slug == "second")).set({Skill.status: SkillStatus.deactivated})
        resp = await client.get("/api/skillsets/set")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == 3
        assert [s["slug"] for s in body["skills"]] == ["first", "second", "third"]
        assert body["skills"][0]["labels"] == ["lcls"]
        assert body["skills"][1]["status"] == "deactivated"
        assert body["member_count"] == 3

    async def test_detail_unknown(self, client):  # I6
        assert (await client.get("/api/skillsets/nope")).status_code == 404

    async def test_update_by_owner(self, client):  # I7
        await _skillset_with()
        resp = await client.patch("/api/skillsets/set", json={"name": "Renamed"}, headers=_auth())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    async def test_update_by_non_owner(self, client):  # I8
        await _skillset_with()
        resp = await client.patch("/api/skillsets/set", json={"name": "Renamed"}, headers=_auth("stranger"))
        assert resp.status_code == 403

    async def test_delete_by_owner(self, client):  # I9
        await _skillset_with("a")
        assert (await client.delete("/api/skillsets/set", headers=_auth())).status_code == 204
        assert (await client.get("/api/skillsets/set")).status_code == 404

    async def test_delete_by_admin(self, client):  # I10
        await _skillset_with("a")
        assert (await client.delete("/api/skillsets/set", headers=_auth("admin"))).status_code == 204
        assert await Skillset.find_one(Skillset.slug == "set") is None

    async def test_delete_by_non_owner(self, client):  # I11
        await _skillset_with()
        assert (await client.delete("/api/skillsets/set", headers=_auth("stranger"))).status_code == 403

    async def test_patch_ignores_slug(self, client):  # I12
        await _skillset_with()
        resp = await client.patch("/api/skillsets/set", json={"slug": "moved", "name": "N"}, headers=_auth())
        assert resp.status_code == 200
        assert resp.json()["slug"] == "set"
        assert await Skillset.find_one(Skillset.slug == "moved") is None

    async def test_detail_omits_orphan(self, client):  # I13
        await _skillset_with("a")
        orphan = SkillsetMember(skill_id="0123456789abcdef01234567", added_by="owner")
        await Skillset.find_one(Skillset.slug == "set").update({"$push": {"members": orphan.model_dump()}})
        body = (await client.get("/api/skillsets/set")).json()
        assert [s["slug"] for s in body["skills"]] == ["a"]
        assert body["member_count"] == 1


class TestSkillsetsRouterMembership:
    async def test_add(self, client):  # R1
        await _make_skill("a")
        await _skillset_with()
        resp = await client.put("/api/skillsets/set/skills/a", headers=_auth())
        assert resp.status_code == 204
        assert await _member_slugs(client) == ["a"]

    async def test_add_twice(self, client):  # R2
        await _skillset_with("a")
        assert (await client.put("/api/skillsets/set/skills/a", headers=_auth())).status_code == 409

    async def test_add_unknown_skill(self, client):  # R3
        await _skillset_with()
        assert (await client.put("/api/skillsets/set/skills/missing", headers=_auth())).status_code == 404

    async def test_remove(self, client):  # R4
        await _skillset_with("a", "b")
        assert (await client.delete("/api/skillsets/set/skills/a", headers=_auth())).status_code == 204
        assert await _member_slugs(client) == ["b"]

    async def test_remove_non_member(self, client):  # R5
        await _make_skill("a")
        await _skillset_with()
        assert (await client.delete("/api/skillsets/set/skills/a", headers=_auth())).status_code == 404

    async def test_add_by_non_owner(self, client):  # R6
        await _skillset_with("a")
        await _make_skill("b")
        for skill_slug in ("a", "b"):
            resp = await client.put(f"/api/skillsets/set/skills/{skill_slug}", headers=_auth("stranger"))
            assert resp.status_code == 403

    async def test_remove_by_unrelated_user(self, client):  # R7
        await _skillset_with("a")
        resp = await client.delete("/api/skillsets/set/skills/a", headers=_auth("stranger"))
        assert resp.status_code == 403

    async def test_remove_by_skill_submitter(self, client):  # R8
        await _skillset_with("a")
        resp = await client.delete("/api/skillsets/set/skills/a", headers=_auth("author"))
        assert resp.status_code == 204
        assert await _member_slugs(client) == []

    async def test_reorder(self, client):  # R9
        before = await _skillset_with("a", "b")
        resp = await client.put(
            "/api/skillsets/set/order",
            json={"skill_slugs": ["b", "a"], "version": before.version},
            headers=_auth(),
        )
        assert resp.status_code == 200
        assert [s["slug"] for s in resp.json()["skills"]] == ["b", "a"]
        assert resp.json()["version"] == before.version + 1

    async def test_reorder_stale_version(self, client):  # R10
        before = await _skillset_with("a", "b")
        resp = await client.put(
            "/api/skillsets/set/order",
            json={"skill_slugs": ["b", "a"], "version": before.version - 1},
            headers=_auth(),
        )
        assert resp.status_code == 409

    async def test_reorder_wrong_member_set(self, client):  # R11
        before = await _skillset_with("a", "b")
        resp = await client.put(
            "/api/skillsets/set/order",
            json={"skill_slugs": ["a"], "version": before.version},
            headers=_auth(),
        )
        assert resp.status_code == 422

    async def test_list_by_creator(self, client):  # R12
        await _skillset_with(slug="mine")
        await _skillset_with(slug="theirs", owner="other")
        body = (await client.get("/api/skillsets?created_by=owner")).json()
        assert [s["slug"] for s in body["items"]] == ["mine"]

    async def test_reorder_by_non_owner(self, client):  # R13
        before = await _skillset_with("a", "b")
        resp = await client.put(
            "/api/skillsets/set/order",
            json={"skill_slugs": ["b", "a"], "version": before.version},
            headers=_auth("stranger"),
        )
        assert resp.status_code == 403

    async def test_writes_need_identity(self, client):  # R14
        await _skillset_with("a")
        assert (await client.put("/api/skillsets/set/skills/a")).status_code == 401
        assert (await client.delete("/api/skillsets/set/skills/a")).status_code == 401
        resp = await client.put("/api/skillsets/set/order", json={"skill_slugs": ["a"], "version": 1})
        assert resp.status_code == 401

    async def test_remove_deactivated_member(self, client):  # R15
        await _skillset_with("a")
        await (await Skill.find_one(Skill.slug == "a")).set({Skill.status: SkillStatus.deactivated})
        assert (await client.delete("/api/skillsets/set/skills/a", headers=_auth())).status_code == 204

    async def test_submitter_can_only_remove(self, client):  # R16
        before = await _skillset_with("a", "b")
        author = _auth("author")
        reorder = {"skill_slugs": ["b", "a"], "version": before.version}
        assert (await client.put("/api/skillsets/set/order", json=reorder, headers=author)).status_code == 403
        assert (await client.patch("/api/skillsets/set", json={"name": "X"}, headers=author)).status_code == 403
        assert (await client.delete("/api/skillsets/set", headers=author)).status_code == 403
        after = await skillset_service.get("set")
        assert (after.name, after.version) == ("set", before.version)

    async def test_add_limit_counts_per_user_across_paths(self, client):  # R17
        # User ids unique to this test: limiter counts live in process memory for the whole run.
        await skillset_service.create(name="r17", description="", actor=User(user_id="r17-a"), slug="r17-a")
        await skillset_service.create(name="r17", description="", actor=User(user_id="r17-b"), slug="r17-b")
        for i in range(51):
            await _make_skill(f"r17-{i}")
        statuses = [
            (await client.put(f"/api/skillsets/r17-a/skills/r17-{i}", headers=_auth("r17-a"))).status_code
            for i in range(51)
        ]
        assert statuses[:50] == [204] * 50
        assert statuses[50] == 429
        resp = await client.put("/api/skillsets/r17-b/skills/r17-0", headers=_auth("r17-b"))
        assert resp.status_code == 204


_LOCAL_SKILL_MD = "---\nname: {name}\ndescription: A locally submitted skill.\n---\n\n# {name}\n"


def _local_submission(name: str, skillset_slug: str | None) -> dict:
    body = {
        "repo_url": f"local:///home/user/{name}",
        "source_type": "local",
        "snapshotted_files": {"SKILL.md": _LOCAL_SKILL_MD.format(name=name)},
    }
    if skillset_slug is not None:
        body["skillset_slug"] = skillset_slug
    return body


class TestCreateSkillAutoAdd:
    async def test_owner_skillset_gets_new_skill(self, client):  # C1
        await _skillset_with("a")
        resp = await client.post("/api/skills", json=_local_submission("fresh", "set"), headers=_auth())
        assert resp.status_code == 201
        assert await _member_slugs(client) == ["a", resp.json()["slug"]]

    async def test_other_users_skillset_unchanged(self, client):  # C2
        before = await _skillset_with("a", owner="other")
        resp = await client.post("/api/skills", json=_local_submission("fresh", "set"), headers=_auth())
        assert resp.status_code == 201
        after = await skillset_service.get("set")
        assert ([m.skill_id for m in after.members], after.version) == (
            [m.skill_id for m in before.members], before.version,
        )

    async def test_admin_does_not_auto_add_to_others(self, client):  # C3
        before = await _skillset_with("a", owner="other")
        resp = await client.post("/api/skills", json=_local_submission("fresh", "set"), headers=_auth("admin"))
        assert resp.status_code == 201
        assert (await skillset_service.get("set")).version == before.version

    async def test_missing_skillset_ignored(self, client):  # C4
        resp = await client.post("/api/skills", json=_local_submission("fresh", "nope"), headers=_auth())
        assert resp.status_code == 201


class TestSkillDetailIncludesSkillsets:
    async def test_detail_lists_skillsets(self, client):  # S1
        await _skillset_with("a", slug="first")
        await skillset_service.create(name="Second", description="", actor=OWNER, slug="second")
        await skillset_service.add_skill("second", "a", OWNER)
        body = (await client.get("/api/skills/a")).json()
        assert body["skillset_count"] == 2
        assert body["skillsets"] == [{"slug": "first", "name": "first"}, {"slug": "second", "name": "Second"}]

    async def test_detail_without_skillsets(self, client):  # S2
        await _make_skill("a")
        body = (await client.get("/api/skills/a")).json()
        assert (body["skillset_count"], body["skillsets"]) == (0, [])

    async def test_list_counts_skillsets(self, client):  # S3
        await _skillset_with("a", slug="first")
        await skillset_service.create(name="second", description="", actor=OWNER, slug="second")
        await skillset_service.add_skill("second", "a", OWNER)
        await _make_skill("b")
        items = (await client.get("/api/skills")).json()["items"]
        assert {i["slug"]: i["skillset_count"] for i in items} == {"a": 2, "b": 0}

    async def test_summary_matches_part_of_a_word(self, client):  # S4
        await _make_skill("k8s-deploy")
        await _make_skill("unrelated")
        body = (await client.get("/api/skills/summary?q=depl")).json()
        assert [s["slug"] for s in body] == ["k8s-deploy"]
