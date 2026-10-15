"""Tests for #006 — skillset service: create, membership, order, hydration, permissions, audit log."""
from __future__ import annotations

import pytest

from app.auth import User
from app.models.skill import Skill, SkillStatus
from app.models.skillset import Skillset
from app.services.skillset import (
    PermissionDeniedError,
    SkillNotFoundError,
    SkillsetAlreadyExistsError,
    SkillsetMemberAlreadyError,
    SkillsetMemberNotFoundError,
    SkillsetNotFoundError,
    skillset_service,
)

OWNER = User(user_id="owner")
ADMIN = User(user_id="admin", is_admin=True)


class TestSkillsetServiceCreate:
    async def test_create_starts_empty(self):  # U1
        skillset = await skillset_service.create(name="LCLS Starter", description="", actor=OWNER)
        assert skillset.members == []
        assert skillset.version == 0
        assert skillset.created_by == "owner"

    async def test_slug_derived_from_name(self):  # U2
        skillset = await skillset_service.create(name="My Skillset", description="", actor=OWNER)
        assert skillset.slug == "my-skillset"

    async def test_duplicate_slug_suggests_next_free(self):  # U3
        await skillset_service.create(name="My Skillset", description="", actor=OWNER)
        await skillset_service.create(name="Other", description="", actor=OWNER, slug="my-skillset-2")
        with pytest.raises(SkillsetAlreadyExistsError) as exc:
            await skillset_service.create(name="My Skillset", description="", actor=OWNER)
        assert exc.value.suggested_slug == "my-skillset-3"

    @pytest.mark.parametrize("slug", ["a b", "../etc", "", "-lead", "UPPER", "x" * 101])  # U4-U6
    def test_invalid_slug_rejected(self, slug):
        with pytest.raises(ValueError):
            Skillset(slug=slug, name="n", created_by="owner")

    def test_name_over_200_chars_rejected(self):  # U7
        with pytest.raises(ValueError):
            Skillset(slug="ok", name="n" * 201, created_by="owner")

    async def test_name_without_slug_characters_rejected(self):
        with pytest.raises(ValueError):
            await skillset_service.create(name="!!!", description="", actor=OWNER)


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


async def _make_skillset(slug: str = "set", owner: User = OWNER) -> Skillset:
    return await skillset_service.create(name=slug, description="", actor=owner, slug=slug)


async def _member_slugs(slug: str) -> list[str]:
    skillset = await skillset_service.get(slug)
    skills = {str(s.id): s.slug for s in await Skill.find_all().to_list()}
    return [skills.get(m.skill_id, m.skill_id) for m in skillset.members]


class TestSkillsetServiceMembership:
    async def test_add_appends_and_bumps_version(self):  # M1
        await _make_skill("a")
        await _make_skill("b")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        await skillset_service.add_skill("set", "b", OWNER)
        assert await _member_slugs("set") == ["a", "b"]
        stored = await skillset_service.get("set")
        assert stored.version == 2
        assert stored.members[1].added_by == "owner"

    async def test_add_twice_is_conflict(self):  # M2
        await _make_skill("a")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        with pytest.raises(SkillsetMemberAlreadyError):
            await skillset_service.add_skill("set", "a", OWNER)
        assert (await skillset_service.get("set")).version == 1

    async def test_add_unknown_skill_not_found(self):  # M3
        await _make_skillset()
        with pytest.raises(SkillNotFoundError):
            await skillset_service.add_skill("set", "missing", OWNER)

    async def test_remove_drops_member_and_bumps_version(self):  # M4
        await _make_skill("a")
        await _make_skill("b")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        await skillset_service.add_skill("set", "b", OWNER)
        await skillset_service.remove_skill("set", "a", OWNER)
        assert await _member_slugs("set") == ["b"]
        assert (await skillset_service.get("set")).version == 3

    async def test_remove_non_member_not_found(self):  # M5
        await _make_skill("a")
        await _make_skillset()
        with pytest.raises(SkillsetMemberNotFoundError):
            await skillset_service.remove_skill("set", "a", OWNER)

    async def test_add_to_missing_skillset_not_found(self):  # M6
        await _make_skill("a")
        with pytest.raises(SkillsetNotFoundError):
            await skillset_service.add_skill("nope", "a", OWNER)

    async def test_add_to_skillset_deleted_mid_add_not_found(self, monkeypatch):  # M6, write matches nothing
        await _make_skill("a")
        stale = await _make_skillset()
        await stale.delete()
        monkeypatch.setattr(skillset_service, "get", _returning(stale))
        with pytest.raises(SkillsetNotFoundError):
            await skillset_service.add_skill("set", "a", OWNER)

    async def test_add_by_non_owner_denied(self):  # M7
        await _make_skill("a")
        await _make_skillset()
        with pytest.raises(PermissionDeniedError):
            await skillset_service.add_skill("set", "a", User(user_id="stranger"))
        assert (await skillset_service.get("set")).members == []

    async def test_add_by_admin_allowed(self):  # M8
        await _make_skill("a")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", ADMIN)
        assert await _member_slugs("set") == ["a"]

    async def test_remove_by_skill_submitter_allowed(self):  # M10
        await _make_skill("a", submitter="author")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        await skillset_service.remove_skill("set", "a", User(user_id="author"))
        assert await _member_slugs("set") == []

    async def test_remove_by_unrelated_user_denied(self):  # M11
        await _make_skill("a", submitter="author")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        with pytest.raises(PermissionDeniedError):
            await skillset_service.remove_skill("set", "a", User(user_id="stranger"))
        assert await _member_slugs("set") == ["a"]

    async def test_add_by_skill_submitter_denied(self):  # M12
        await _make_skill("a", submitter="author")
        await _make_skillset()
        with pytest.raises(PermissionDeniedError):
            await skillset_service.add_skill("set", "a", User(user_id="author"))

    async def test_remove_by_admin_allowed(self):  # M14
        await _make_skill("a")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        await skillset_service.remove_skill("set", "a", ADMIN)
        assert await _member_slugs("set") == []

    async def test_remove_deactivated_member_allowed(self):  # M15
        skill = await _make_skill("a")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        await skill.set({Skill.status: SkillStatus.deactivated})
        await skillset_service.remove_skill("set", "a", OWNER)
        assert await _member_slugs("set") == []

    async def test_add_deactivated_skill_not_found(self):  # M16
        await _make_skill("a", status=SkillStatus.deactivated)
        await _make_skillset()
        with pytest.raises(SkillNotFoundError):
            await skillset_service.add_skill("set", "a", OWNER)

    async def test_remove_by_stranger_of_unknown_skill_denied(self):
        await _make_skillset()
        with pytest.raises(PermissionDeniedError):
            await skillset_service.remove_skill("set", "missing", User(user_id="stranger"))

    async def test_remove_unknown_skill_by_owner_not_found(self):
        await _make_skillset()
        with pytest.raises(SkillNotFoundError):
            await skillset_service.remove_skill("set", "missing", OWNER)

    async def test_get_missing_skillset_not_found(self):
        with pytest.raises(SkillsetNotFoundError):
            await skillset_service.get("nope")


def _returning(value):
    async def _fake(*_args, **_kwargs):
        return value
    return _fake
