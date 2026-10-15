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
