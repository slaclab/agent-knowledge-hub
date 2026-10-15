"""Tests for #006 — skillset service: create, membership, order, hydration, permissions, audit log."""
from __future__ import annotations

import pytest

from app.auth import User
from app.models.skillset import Skillset
from app.services.skillset import SkillsetAlreadyExistsError, skillset_service

OWNER = User(user_id="owner")


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
