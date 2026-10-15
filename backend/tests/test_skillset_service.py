"""Tests for #006 — skillset service: create, membership, order, hydration, permissions, audit log."""
from __future__ import annotations

import pytest

from app.auth import User
from app.services.skillset import skillset_service

OWNER = User(user_id="owner")


class TestSkillsetServiceCreate:
    async def test_create_starts_empty(self):  # U1
        skillset = await skillset_service.create(name="LCLS Starter", description="", actor=OWNER)
        assert skillset.members == []
        assert skillset.version == 0
        assert skillset.created_by == "owner"
