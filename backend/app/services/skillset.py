from __future__ import annotations

import logging
from typing import Optional

from slugify import slugify

from app.auth import User
from app.models.skillset import Skillset

logger = logging.getLogger(__name__)


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
        await skillset.insert()
        return skillset


skillset_service = SkillsetService()
