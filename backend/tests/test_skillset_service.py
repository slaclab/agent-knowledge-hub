"""Tests for #006 — skillset service: create, membership, order, hydration, permissions, audit log."""
from __future__ import annotations

import pytest

from app.auth import User
from app.models.skill import Skill, SkillStatus
from app.models.skillset import Skillset, SkillsetMember
from app.services.skillset import (
    PermissionDeniedError,
    SkillNotFoundError,
    SkillsetAlreadyExistsError,
    SkillsetMemberAlreadyError,
    SkillsetMemberNotFoundError,
    SkillsetNotFoundError,
    SkillsetVersionConflictError,
    skillset_service,
)
from app.services.skill import skill_repository

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


async def _skillset_with(*skill_slugs: str, owner: User = OWNER) -> Skillset:
    await _make_skillset(owner=owner)
    for skill_slug in skill_slugs:
        await _make_skill(skill_slug)
        await skillset_service.add_skill("set", skill_slug, owner)
    return await skillset_service.get("set")


class TestSkillsetServiceOrder:
    async def test_reorder_stores_permutation_and_keeps_audit_fields(self):  # O1
        before = await _skillset_with("a", "b", "c")
        added = {m.skill_id: (m.added_by, m.added_at) for m in before.members}
        after = await skillset_service.reorder("set", ["c", "a", "b"], before.version, OWNER)
        assert await _member_slugs("set") == ["c", "a", "b"]
        assert after.version == before.version + 1
        stored = await skillset_service.get("set")
        assert {m.skill_id: (m.added_by, m.added_at) for m in stored.members} == added

    async def test_reorder_with_stale_version_conflicts(self):  # O2
        before = await _skillset_with("a", "b")
        with pytest.raises(SkillsetVersionConflictError):
            await skillset_service.reorder("set", ["b", "a"], before.version - 1, OWNER)
        assert await _member_slugs("set") == ["a", "b"]

    async def test_reorder_missing_member_rejected(self):  # O3
        before = await _skillset_with("a", "b")
        with pytest.raises(ValueError):
            await skillset_service.reorder("set", ["a"], before.version, OWNER)

    @pytest.mark.parametrize("slugs", [["a", "b", "x"], ["a", "a"], ["a", "b", "b"]])  # O4
    async def test_reorder_extra_or_repeated_slug_rejected(self, slugs):
        before = await _skillset_with("a", "b")
        await _make_skill("x")
        with pytest.raises(ValueError):
            await skillset_service.reorder("set", slugs, before.version, OWNER)

    async def test_add_after_reorder_appends(self):  # O5
        before = await _skillset_with("a", "b")
        await skillset_service.reorder("set", ["b", "a"], before.version, OWNER)
        await _make_skill("c")
        await skillset_service.add_skill("set", "c", OWNER)
        assert await _member_slugs("set") == ["b", "a", "c"]

    async def test_reorder_by_non_owner_denied(self):  # O6
        before = await _skillset_with("a", "b")
        with pytest.raises(PermissionDeniedError):
            await skillset_service.reorder("set", ["b", "a"], before.version, User(user_id="stranger"))

    async def test_reorder_by_admin_allowed(self):  # O7
        before = await _skillset_with("a", "b")
        await skillset_service.reorder("set", ["b", "a"], before.version, ADMIN)
        assert await _member_slugs("set") == ["b", "a"]

    async def test_stale_page_after_add_gets_conflict_not_mismatch(self):  # O8
        before = await _skillset_with("a", "b")
        await _make_skill("c")
        await skillset_service.add_skill("set", "c", OWNER)
        with pytest.raises(SkillsetVersionConflictError):
            await skillset_service.reorder("set", ["b", "a"], before.version, OWNER)

    async def test_reorder_write_after_concurrent_change_conflicts(self, monkeypatch):  # ADR-U18 reorder write guard
        before = await _skillset_with("a", "b")
        await _make_skill("c")
        await skillset_service.add_skill("set", "c", OWNER)
        monkeypatch.setattr(skillset_service, "get", _returning(before))
        with pytest.raises(SkillsetVersionConflictError):
            await skillset_service.reorder("set", ["b", "a"], before.version, OWNER)
        monkeypatch.undo()
        assert await _member_slugs("set") == ["a", "b", "c"]

    async def test_reorder_keeps_deactivated_member(self):  # O10
        before = await _skillset_with("a", "b")
        await (await Skill.find_one(Skill.slug == "a")).set({Skill.status: SkillStatus.deactivated})
        await skillset_service.reorder("set", ["b", "a"], before.version, OWNER)
        assert await _member_slugs("set") == ["b", "a"]

    async def test_reorder_drops_orphan_member(self):  # O11
        await _skillset_with("a", "b")
        orphan = SkillsetMember(skill_id="0123456789abcdef01234567", added_by="owner")
        await Skillset.find_one(Skillset.slug == "set").update({"$push": {"members": orphan.model_dump()}})
        current = await skillset_service.get("set")
        await skillset_service.reorder("set", ["b", "a"], current.version, OWNER)
        stored = await skillset_service.get("set")
        assert "0123456789abcdef01234567" not in [m.skill_id for m in stored.members]
        assert await _member_slugs("set") == ["b", "a"]


class TestSkillsetServicePermissions:
    async def test_update_by_owner(self):  # P1
        await _make_skillset()
        updated = await skillset_service.update("set", OWNER, name="Renamed", description="New")
        assert (updated.name, updated.description) == ("Renamed", "New")

    async def test_update_by_non_owner_denied(self):  # P2
        await _make_skillset()
        with pytest.raises(PermissionDeniedError):
            await skillset_service.update("set", User(user_id="stranger"), name="Renamed")
        assert (await skillset_service.get("set")).name == "set"

    async def test_update_by_admin(self):  # P3
        await _make_skillset()
        updated = await skillset_service.update("set", ADMIN, name="Renamed")
        assert updated.name == "Renamed"

    async def test_update_leaves_unset_fields(self):
        await skillset_service.create(name="n", description="keep", actor=OWNER, slug="set")
        updated = await skillset_service.update("set", OWNER, name="Renamed")
        assert updated.description == "keep"

    async def test_delete_by_owner_removes_document(self):  # P4
        await _skillset_with("a")
        await skillset_service.delete("set", OWNER)
        assert await Skillset.find_one(Skillset.slug == "set") is None

    async def test_delete_by_non_owner_denied(self):  # P5
        await _make_skillset()
        with pytest.raises(PermissionDeniedError):
            await skillset_service.delete("set", User(user_id="stranger"))
        assert await Skillset.find_one(Skillset.slug == "set") is not None

    async def test_update_from_stale_read_keeps_concurrent_add(self, monkeypatch):  # P6
        stale = await _skillset_with("a")
        await _make_skill("b")
        await skillset_service.add_skill("set", "b", OWNER)
        after_add = await skillset_service.get("set")
        monkeypatch.setattr(skillset_service, "get", _returning(stale))
        await skillset_service.update("set", OWNER, name="Renamed")
        monkeypatch.undo()
        stored = await skillset_service.get("set")
        assert stored.name == "Renamed"
        assert [m.skill_id for m in stored.members] == [m.skill_id for m in after_add.members]
        assert stored.version == after_add.version


class TestSkillsetServiceList:
    async def test_list_newest_first_with_total(self):
        for slug in ("one", "two", "three"):
            await _make_skillset(slug)
        items, total = await skillset_service.list(page=1, page_size=2)
        assert total == 3
        assert [s.slug for s in items] == ["three", "two"]
        items, _ = await skillset_service.list(page=2, page_size=2)
        assert [s.slug for s in items] == ["one"]

    async def test_list_filters_by_creator(self):
        await _make_skillset("mine")
        await _make_skillset("theirs", owner=User(user_id="other"))
        items, total = await skillset_service.list(page=1, page_size=20, created_by="owner")
        assert (total, [s.slug for s in items]) == (1, ["mine"])


class TestSkillsetServiceBatchHydration:
    async def test_one_query_for_a_page_of_skills(self, monkeypatch):  # B1
        a = await _make_skill("a")
        b = await _make_skill("b")
        await _make_skillset()
        await skillset_service.add_skill("set", "a", OWNER)
        calls = []
        original = Skillset.find

        def spy(*args, **kwargs):
            calls.append(args)
            return original(*args, **kwargs)

        monkeypatch.setattr(Skillset, "find", spy)
        await skillset_service.batch_skillsets_for_skills([str(a.id), str(b.id)])
        assert len(calls) == 1

    async def test_skill_in_two_skillsets(self):  # B2
        a = await _make_skill("a")
        for slug in ("first", "second"):
            await _make_skillset(slug)
            await skillset_service.add_skill(slug, "a", OWNER)
        result = await skillset_service.batch_skillsets_for_skills([str(a.id)])
        assert [(r.slug, r.name) for r in result[str(a.id)]] == [("first", "first"), ("second", "second")]

    async def test_skill_in_no_skillset(self):  # B3
        a = await _make_skill("a")
        await _make_skillset()
        assert await skillset_service.batch_skillsets_for_skills([str(a.id)]) == {str(a.id): []}

    async def test_empty_input(self):  # B4
        assert await skillset_service.batch_skillsets_for_skills([]) == {}


class TestSkillsetServiceCascade:
    async def test_purge_removes_skill_everywhere(self):  # M9
        a = await _make_skill("a")
        await _make_skill("b")
        for slug in ("first", "second"):
            await _make_skillset(slug)
            await skillset_service.add_skill(slug, "a", OWNER)
        await skillset_service.add_skill("first", "b", OWNER)
        await skillset_service.purge_for_skill(str(a.id), "a", "owner")
        first = await skillset_service.get("first")
        second = await skillset_service.get("second")
        assert await _member_slugs("first") == ["b"]
        assert second.members == []
        assert (first.version, second.version) == (3, 2)

    async def test_skill_delete_cascades(self):  # M13
        a = await _make_skill("a")
        for slug in ("first", "second"):
            await _make_skillset(slug)
            await skillset_service.add_skill(slug, "a", OWNER)
        await skill_repository.delete(a, actor_id="author")
        for slug in ("first", "second"):
            stored = await skillset_service.get(slug)
            assert (stored.members, stored.version) == ([], 2)

    async def test_reorder_after_member_skill_deleted_conflicts(self):  # O9
        before = await _skillset_with("a", "b")
        await skill_repository.delete(await Skill.find_one(Skill.slug == "a"), actor_id="author")
        with pytest.raises(SkillsetVersionConflictError):
            await skillset_service.reorder("set", ["b", "a"], before.version, OWNER)
