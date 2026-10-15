from __future__ import annotations

import logging
from typing import Optional

from pymongo.errors import DuplicateKeyError
from slugify import slugify

from app.auth import User
from app.models.skillset import Skillset

logger = logging.getLogger(__name__)


class SkillsetError(Exception):
    pass


class SkillsetAlreadyExistsError(SkillsetError):
    def __init__(self, slug: str, suggested_slug: str):
        super().__init__(f"Skillset slug {slug!r} is already taken")
        self.suggested_slug = suggested_slug


async def _next_free_slug(slug: str) -> str:
    i = 2
    while await Skillset.find_one(Skillset.slug == f"{slug}-{i}"):
        i += 1
    return f"{slug}-{i}"


class SkillsetService:
    async def create(
        self, name: str, description: str, actor: User, slug: Optional[str] = None
    ) -> Skillset:
        skillset = Skillset(
            slug=slug or slugify(name),
            name=name,
            description=description,
            created_by=actor.user_id,
        )
        try:
            await skillset.insert()
        except DuplicateKeyError:
            raise SkillsetAlreadyExistsError(skillset.slug, await _next_free_slug(skillset.slug))
        return skillset


skillset_service = SkillsetService()
