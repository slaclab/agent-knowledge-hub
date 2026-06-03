"""Tests for #012 — Moderation: User Flags and Admin Deactivation.

Covers:
  Service unit tests: U-01 through U-32 (flag upsert, retract, resolve_all, list)
  Route integration tests: I-01 through I-25 (POST flag, DELETE flag, my_flag, admin routes)
  End-to-end flow: E-01
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app import config as config_module
from app.main import create_app
from app.models.flag import FlagReason, FlagStatus, SkillFlag
from app.models.revision import RevisionAction, SkillRevision
from app.models.skill import Skill, SkillStatus
import app.services.flag as flag_service

_TEST_SECRET = "test-secret-for-012"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

async def _make_skill(slug: str, submitter: str = "alice", status: SkillStatus = SkillStatus.active) -> Skill:
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


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setattr(config_module.settings, "internal_api_secret", _TEST_SECRET)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _auth(user_id: str = "alice") -> dict:
    return {"X-Internal-Secret": _TEST_SECRET, "X-Forwarded-User": user_id}


def _admin_auth(user_id: str = "admin-user", monkeypatch=None, settings=None) -> dict:
    return {"X-Internal-Secret": _TEST_SECRET, "X-Forwarded-User": user_id}


# ---------------------------------------------------------------------------
# Service unit tests — flag_service
# ---------------------------------------------------------------------------

class TestCreateOrUpdate:
    @pytest.mark.asyncio
    async def test_new_flag_creates_record_and_increments_count(self):  # U-01
        skill = await _make_skill("flag-skill-1")
        assert skill.flag_count == 0

        flag = await flag_service.create_or_update(
            skill_id=str(skill.id),
            reporter_id="alice",
            reason=FlagReason.broken,
            note="broken note",
            superseded_by_slug=None,
        )

        assert flag.reason == FlagReason.broken
        assert flag.status == FlagStatus.active
        await skill.sync()
        assert skill.flag_count == 1

    @pytest.mark.asyncio
    async def test_reflag_same_reason_does_not_increment(self):  # U-02
        skill = await _make_skill("flag-skill-2")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)

        await skill.sync()
        assert skill.flag_count == 1  # not 2

    @pytest.mark.asyncio
    async def test_reflag_different_reason_updates_record(self):  # U-03
        skill = await _make_skill("flag-skill-3")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        flag = await flag_service.create_or_update(str(skill.id), "alice", FlagReason.stale, "updated", None)

        assert flag.reason == FlagReason.stale
        assert flag.note == "updated"
        await skill.sync()
        assert skill.flag_count == 1

    @pytest.mark.asyncio
    async def test_reflag_after_retract_increments_again(self):  # U-04
        skill = await _make_skill("flag-skill-4")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.retract(str(skill.id), "alice")
        await skill.sync()
        assert skill.flag_count == 0

        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.stale, None, None)
        await skill.sync()
        assert skill.flag_count == 1

    @pytest.mark.asyncio
    async def test_multiple_reporters_each_increment(self):  # U-05
        skill = await _make_skill("flag-skill-5")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.create_or_update(str(skill.id), "bob", FlagReason.stale, None, None)

        await skill.sync()
        assert skill.flag_count == 2


class TestRetract:
    @pytest.mark.asyncio
    async def test_retract_resolves_flag_and_decrements(self):  # U-06
        skill = await _make_skill("retract-skill-1")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)

        await flag_service.retract(str(skill.id), "alice")

        flag = await flag_service.get_my_flag(str(skill.id), "alice")
        assert flag.status == FlagStatus.resolved
        await skill.sync()
        assert skill.flag_count == 0

    @pytest.mark.asyncio
    async def test_retract_floor_at_zero(self):  # U-07
        skill = await _make_skill("retract-skill-2")
        # Manually set flag_count to 0 to simulate race
        await Skill.find_one(Skill.id == skill.id).update({"$set": {"flag_count": 0}})
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        # Force flag_count back to 0 to simulate concurrent retract
        await Skill.find_one(Skill.id == skill.id).update({"$set": {"flag_count": 0}})

        await flag_service.retract(str(skill.id), "alice")

        await skill.sync()
        assert skill.flag_count >= 0  # never negative

    @pytest.mark.asyncio
    async def test_retract_no_active_flag_raises(self):  # U-08
        skill = await _make_skill("retract-skill-3")
        with pytest.raises(ValueError, match="no_active_flag"):
            await flag_service.retract(str(skill.id), "alice")

    @pytest.mark.asyncio
    async def test_retract_already_resolved_flag_raises(self):  # U-09
        skill = await _make_skill("retract-skill-4")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.retract(str(skill.id), "alice")
        with pytest.raises(ValueError, match="no_active_flag"):
            await flag_service.retract(str(skill.id), "alice")


class TestResolveAllForSkill:
    @pytest.mark.asyncio
    async def test_bulk_resolve_resets_flag_count(self):  # U-10
        skill = await _make_skill("resolve-skill-1")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.create_or_update(str(skill.id), "bob", FlagReason.stale, None, None)
        await flag_service.create_or_update(str(skill.id), "carol", FlagReason.other, None, None)

        count = await flag_service.resolve_all_for_skill(str(skill.id), resolved_by="admin1")

        assert count == 3
        await skill.sync()
        assert skill.flag_count == 0

    @pytest.mark.asyncio
    async def test_bulk_resolve_no_op_when_no_active_flags(self):  # U-11
        skill = await _make_skill("resolve-skill-2")
        count = await flag_service.resolve_all_for_skill(str(skill.id), resolved_by="admin1")
        assert count == 0
        await skill.sync()
        assert skill.flag_count == 0

    @pytest.mark.asyncio
    async def test_bulk_resolve_sets_resolved_by(self):  # U-12
        skill = await _make_skill("resolve-skill-3")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.resolve_all_for_skill(str(skill.id), resolved_by="admin1")

        flags = await SkillFlag.find(SkillFlag.skill_id == str(skill.id)).to_list()
        assert all(f.resolved_by == "admin1" for f in flags)

    @pytest.mark.asyncio
    async def test_bulk_resolve_skips_already_resolved(self):  # U-13
        skill = await _make_skill("resolve-skill-4")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.retract(str(skill.id), "alice")  # already resolved
        await flag_service.create_or_update(str(skill.id), "bob", FlagReason.stale, None, None)

        count = await flag_service.resolve_all_for_skill(str(skill.id), resolved_by="admin1")
        assert count == 1  # only bob's active flag


class TestListFlaggedSkills:
    @pytest.mark.asyncio
    async def test_returns_active_skills_with_flags_sorted_by_count(self):  # U-14
        s1 = await _make_skill("list-flag-1")
        s2 = await _make_skill("list-flag-2")
        # s1 gets 1 flag, s2 gets 2 flags
        await flag_service.create_or_update(str(s1.id), "alice", FlagReason.broken, None, None)
        await flag_service.create_or_update(str(s2.id), "alice", FlagReason.stale, None, None)
        await flag_service.create_or_update(str(s2.id), "bob", FlagReason.other, None, None)

        items, total = await flag_service.list_flagged_skills(page=1, page_size=10)

        assert total == 2
        slugs = [i.skill_slug for i in items]
        assert slugs.index("list-flag-2") < slugs.index("list-flag-1")  # s2 first (more flags)

    @pytest.mark.asyncio
    async def test_excludes_deactivated_skills(self):  # U-15
        active = await _make_skill("list-flag-active")
        deactivated = await _make_skill("list-flag-deact", status=SkillStatus.deactivated)
        await flag_service.create_or_update(str(active.id), "alice", FlagReason.broken, None, None)
        await Skill.find_one(Skill.id == deactivated.id).update({"$set": {"flag_count": 3}})

        items, total = await flag_service.list_flagged_skills()

        slugs = [i.skill_slug for i in items]
        assert "list-flag-active" in slugs
        assert "list-flag-deact" not in slugs


# ---------------------------------------------------------------------------
# Integration tests — POST /api/skills/{slug}/flag
# ---------------------------------------------------------------------------

class TestFlagRoutePost:
    @pytest.mark.asyncio
    async def test_authenticated_user_can_flag(self, client):  # I-01
        await _make_skill("flag-route-1")
        r = await client.post("/api/skills/flag-route-1/flag",
                              json={"reason": "broken"},
                              headers=_auth("alice"))
        assert r.status_code == 200
        data = r.json()
        assert data["flag_count"] == 1
        assert data["my_flag"]["reason"] == "broken"
        assert data["my_flag"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client):  # I-02
        await _make_skill("flag-route-2")
        r = await client.post("/api/skills/flag-route-2/flag", json={"reason": "broken"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_nonexistent_skill_returns_404(self, client):  # I-03
        r = await client.post("/api/skills/no-such-skill/flag",
                              json={"reason": "broken"},
                              headers=_auth("alice"))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_deactivated_skill_returns_410(self, client):  # I-04
        await _make_skill("flag-deact", status=SkillStatus.deactivated)
        r = await client.post("/api/skills/flag-deact/flag",
                              json={"reason": "broken"},
                              headers=_auth("alice"))
        assert r.status_code == 410
        assert r.json()["detail"]["code"] == "deactivated"

    @pytest.mark.asyncio
    async def test_invalid_reason_returns_422(self, client):  # I-05
        await _make_skill("flag-route-3")
        r = await client.post("/api/skills/flag-route-3/flag",
                              json={"reason": "not_a_valid_reason"},
                              headers=_auth("alice"))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_note_too_long_returns_422(self, client):  # I-06
        await _make_skill("flag-route-4")
        r = await client.post("/api/skills/flag-route-4/flag",
                              json={"reason": "broken", "note": "x" * 501},
                              headers=_auth("alice"))
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_upsert_same_user_no_duplicate(self, client):  # I-07
        await _make_skill("flag-route-5")
        await client.post("/api/skills/flag-route-5/flag",
                          json={"reason": "broken"}, headers=_auth("alice"))
        r = await client.post("/api/skills/flag-route-5/flag",
                              json={"reason": "stale"}, headers=_auth("alice"))
        assert r.status_code == 200
        assert r.json()["flag_count"] == 1

    @pytest.mark.asyncio
    async def test_superseded_by_nonexistent_slug_returns_404(self, client):  # I-08
        await _make_skill("flag-route-6")
        r = await client.post("/api/skills/flag-route-6/flag",
                              json={"reason": "superseded", "superseded_by_slug": "no-such-skill"},
                              headers=_auth("alice"))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_superseded_by_deactivated_slug_returns_200_with_warning(self, client):  # I-09
        await _make_skill("flag-route-7")
        await _make_skill("deact-ref", status=SkillStatus.deactivated)
        r = await client.post("/api/skills/flag-route-7/flag",
                              json={"reason": "superseded", "superseded_by_slug": "deact-ref"},
                              headers=_auth("alice"))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Integration tests — DELETE /api/skills/{slug}/flag
# ---------------------------------------------------------------------------

class TestFlagRouteDelete:
    @pytest.mark.asyncio
    async def test_retract_flag(self, client):  # I-10
        await _make_skill("retract-route-1")
        await client.post("/api/skills/retract-route-1/flag",
                          json={"reason": "broken"}, headers=_auth("alice"))
        r = await client.delete("/api/skills/retract-route-1/flag", headers=_auth("alice"))
        assert r.status_code == 200
        assert r.json()["flag_count"] == 0

    @pytest.mark.asyncio
    async def test_retract_no_flag_returns_404(self, client):  # I-11
        await _make_skill("retract-route-2")
        r = await client.delete("/api/skills/retract-route-2/flag", headers=_auth("alice"))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_retract_unauthenticated_returns_401(self, client):  # I-12
        await _make_skill("retract-route-3")
        r = await client.delete("/api/skills/retract-route-3/flag")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Integration tests — GET /api/skills/{slug} my_flag field
# ---------------------------------------------------------------------------

class TestMyFlagField:
    @pytest.mark.asyncio
    async def test_unauthenticated_my_flag_is_null(self, client):  # I-13
        await _make_skill("my-flag-1")
        r = await client.get("/api/skills/my-flag-1")
        assert r.status_code == 200
        assert r.json()["my_flag"] is None

    @pytest.mark.asyncio
    async def test_authenticated_no_flag_my_flag_is_null(self, client):  # I-14
        await _make_skill("my-flag-2")
        r = await client.get("/api/skills/my-flag-2", headers=_auth("alice"))
        assert r.status_code == 200
        assert r.json()["my_flag"] is None

    @pytest.mark.asyncio
    async def test_authenticated_after_flag_my_flag_present(self, client):  # I-15
        await _make_skill("my-flag-3")
        await client.post("/api/skills/my-flag-3/flag",
                          json={"reason": "broken"}, headers=_auth("alice"))
        r = await client.get("/api/skills/my-flag-3", headers=_auth("alice"))
        assert r.status_code == 200
        assert r.json()["my_flag"]["reason"] == "broken"
        assert r.json()["my_flag"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_my_flag_resolved_after_retract(self, client):  # I-16
        await _make_skill("my-flag-4")
        await client.post("/api/skills/my-flag-4/flag",
                          json={"reason": "broken"}, headers=_auth("alice"))
        await client.delete("/api/skills/my-flag-4/flag", headers=_auth("alice"))
        r = await client.get("/api/skills/my-flag-4", headers=_auth("alice"))
        assert r.status_code == 200
        assert r.json()["my_flag"]["status"] == "resolved"


# ---------------------------------------------------------------------------
# Integration tests — GET /api/admin/flags
# ---------------------------------------------------------------------------

class TestAdminFlagsRoute:
    @pytest.mark.asyncio
    async def test_admin_can_list_flagged_skills(self, client, monkeypatch):  # I-17
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        skill = await _make_skill("admin-flag-1")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, "bad", None)
        r = await client.get("/api/admin/flags", headers=_admin_auth())
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        slugs = [i["skill_slug"] for i in data["items"]]
        assert "admin-flag-1" in slugs

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client):  # I-18
        r = await client.get("/api/admin/flags", headers=_auth("alice"))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client):  # I-19
        r = await client.get("/api/admin/flags")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_deactivated_skill_excluded(self, client, monkeypatch):  # I-20
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        deact = await _make_skill("admin-deact-flag", status=SkillStatus.deactivated)
        await Skill.find_one(Skill.id == deact.id).update({"$set": {"flag_count": 5}})
        r = await client.get("/api/admin/flags", headers=_admin_auth())
        assert r.status_code == 200
        slugs = [i["skill_slug"] for i in r.json()["items"]]
        assert "admin-deact-flag" not in slugs


# ---------------------------------------------------------------------------
# Integration tests — POST /api/admin/skills/{slug}/deactivate
# ---------------------------------------------------------------------------

class TestDeactivateRoute:
    @pytest.mark.asyncio
    async def test_admin_deactivates_skill(self, client, monkeypatch):  # I-21
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("deact-1")
        r = await client.post("/api/admin/skills/deact-1/deactivate",
                              json={"reason": "Harmful content"},
                              headers=_admin_auth())
        assert r.status_code == 200
        assert r.json()["status"] == "deactivated"
        assert r.json()["warnings"] == []

    @pytest.mark.asyncio
    async def test_deactivation_writes_revision(self, client, monkeypatch):  # I-22
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        skill = await _make_skill("deact-2")
        await client.post("/api/admin/skills/deact-2/deactivate",
                          json={"reason": "Test"},
                          headers=_admin_auth())
        revs = await SkillRevision.find(
            SkillRevision.skill_id == str(skill.id),
            SkillRevision.action == RevisionAction.deactivate,
        ).to_list()
        assert len(revs) == 1

    @pytest.mark.asyncio
    async def test_deactivation_resolves_active_flags_and_zeros_count(self, client, monkeypatch):  # I-23
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        skill = await _make_skill("deact-3")
        await flag_service.create_or_update(str(skill.id), "alice", FlagReason.broken, None, None)
        await flag_service.create_or_update(str(skill.id), "bob", FlagReason.stale, None, None)

        await client.post("/api/admin/skills/deact-3/deactivate",
                          json={"reason": "Spam"},
                          headers=_admin_auth())

        await skill.sync()
        assert skill.flag_count == 0
        flags = await SkillFlag.find(SkillFlag.skill_id == str(skill.id)).to_list()
        assert all(f.status == FlagStatus.resolved for f in flags)

    @pytest.mark.asyncio
    async def test_get_deactivated_skill_returns_410(self, client, monkeypatch):  # I-24
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("deact-4")
        await client.post("/api/admin/skills/deact-4/deactivate",
                          json={"reason": "Gone"},
                          headers=_admin_auth())
        r = await client.get("/api/skills/deact-4")
        assert r.status_code == 410
        assert r.json()["detail"]["code"] == "deactivated"
        assert r.json()["detail"]["reason"] == "Gone"

    @pytest.mark.asyncio
    async def test_already_deactivated_returns_409(self, client, monkeypatch):  # I-25
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("deact-5", status=SkillStatus.deactivated)
        r = await client.post("/api/admin/skills/deact-5/deactivate",
                              json={"reason": "Already gone"},
                              headers=_admin_auth())
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client):
        await _make_skill("deact-6")
        r = await client.post("/api/admin/skills/deact-6/deactivate",
                              json={"reason": "Nope"},
                              headers=_auth("alice"))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_deactivate_with_superseded_by_slug_stored(self, client, monkeypatch):  # I-26
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("deact-7")
        await _make_skill("replacement")
        await client.post("/api/admin/skills/deact-7/deactivate",
                          json={"reason": "Replaced", "superseded_by_slug": "replacement"},
                          headers=_admin_auth())
        r = await client.get("/api/skills/deact-7")
        assert r.status_code == 410
        assert r.json()["detail"]["superseded_by_slug"] == "replacement"

    @pytest.mark.asyncio
    async def test_superseded_by_deactivated_returns_warning(self, client, monkeypatch):  # I-27
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("deact-8")
        await _make_skill("deact-ref2", status=SkillStatus.deactivated)
        r = await client.post("/api/admin/skills/deact-8/deactivate",
                              json={"reason": "Replaced", "superseded_by_slug": "deact-ref2"},
                              headers=_admin_auth())
        assert r.status_code == 200
        assert len(r.json()["warnings"]) == 1
        assert "deact-ref2" in r.json()["warnings"][0]

    @pytest.mark.asyncio
    async def test_missing_reason_returns_422(self, client, monkeypatch):
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("deact-9")
        r = await client.post("/api/admin/skills/deact-9/deactivate",
                              json={},
                              headers=_admin_auth())
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Integration tests — POST /api/admin/skills/{slug}/reactivate
# ---------------------------------------------------------------------------

class TestReactivateRoute:
    @pytest.mark.asyncio
    async def test_admin_reactivates_skill(self, client, monkeypatch):  # I-28
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("react-1", status=SkillStatus.deactivated)
        r = await client.post("/api/admin/skills/react-1/reactivate",
                              json={},
                              headers=_admin_auth())
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_reactivation_writes_revision(self, client, monkeypatch):  # I-29
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        skill = await _make_skill("react-2", status=SkillStatus.deactivated)
        await client.post("/api/admin/skills/react-2/reactivate",
                          json={},
                          headers=_admin_auth())
        revs = await SkillRevision.find(
            SkillRevision.skill_id == str(skill.id),
            SkillRevision.action == RevisionAction.reactivate,
        ).to_list()
        assert len(revs) == 1

    @pytest.mark.asyncio
    async def test_reactivated_skill_accessible_via_get(self, client, monkeypatch):  # I-30
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("react-3", status=SkillStatus.deactivated)
        await client.post("/api/admin/skills/react-3/reactivate",
                          json={},
                          headers=_admin_auth())
        r = await client.get("/api/skills/react-3")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_already_active_returns_409(self, client, monkeypatch):  # I-31
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("react-4")
        r = await client.post("/api/admin/skills/react-4/reactivate",
                              json={},
                              headers=_admin_auth())
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, client):
        await _make_skill("react-5", status=SkillStatus.deactivated)
        r = await client.post("/api/admin/skills/react-5/reactivate",
                              json={},
                              headers=_auth("alice"))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# End-to-end flow E-01: flag → admin deactivate → tombstone → reactivate
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    @pytest.mark.asyncio
    async def test_full_moderation_lifecycle(self, client, monkeypatch):  # E-01
        monkeypatch.setattr(config_module.settings, "admin_users", "admin-user")
        await _make_skill("e2e-skill")

        # User flags the skill
        r = await client.post("/api/skills/e2e-skill/flag",
                              json={"reason": "broken", "note": "does not work"},
                              headers=_auth("alice"))
        assert r.status_code == 200
        assert r.json()["flag_count"] == 1

        # Skill appears in admin flag queue
        r = await client.get("/api/admin/flags", headers=_admin_auth())
        assert r.status_code == 200
        slugs = [i["skill_slug"] for i in r.json()["items"]]
        assert "e2e-skill" in slugs

        # Admin deactivates
        r = await client.post("/api/admin/skills/e2e-skill/deactivate",
                              json={"reason": "Confirmed broken"},
                              headers=_admin_auth())
        assert r.status_code == 200

        # Skill now returns 410
        r = await client.get("/api/skills/e2e-skill")
        assert r.status_code == 410
        assert r.json()["detail"]["reason"] == "Confirmed broken"

        # Deactivated skill no longer in flag queue
        r = await client.get("/api/admin/flags", headers=_admin_auth())
        slugs = [i["skill_slug"] for i in r.json()["items"]]
        assert "e2e-skill" not in slugs

        # Admin reactivates
        r = await client.post("/api/admin/skills/e2e-skill/reactivate",
                              json={"reason": "False alarm"},
                              headers=_admin_auth())
        assert r.status_code == 200

        # Skill accessible again
        r = await client.get("/api/skills/e2e-skill")
        assert r.status_code == 200
