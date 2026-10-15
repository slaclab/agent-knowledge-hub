from __future__ import annotations

import logging
from typing import Optional

from pymongo.errors import DuplicateKeyError
from slugify import slugify

from app.auth import User
from app.models.skill import Skill, SkillStatus
from app.models.skillset import Skillset, SkillsetMember

logger = logging.getLogger(__name__)


class SkillsetError(Exception):
    pass


class SkillsetNotFoundError(SkillsetError):
    pass


class SkillsetAlreadyExistsError(SkillsetError):
    def __init__(self, slug: str, suggested_slug: str):
        super().__init__(f"Skillset slug {slug!r} is already taken")
        self.suggested_slug = suggested_slug


class SkillNotFoundError(SkillsetError):
    pass


class SkillsetMemberAlreadyError(SkillsetError):
    pass


class SkillsetMemberNotFoundError(SkillsetError):
    pass


class PermissionDeniedError(SkillsetError):
    pass


async def _next_free_slug(slug: str) -> str:
    i = 2
    while await Skillset.find_one(Skillset.slug == f"{slug}-{i}"):
        i += 1
    return f"{slug}-{i}"


def _is_owner_or_admin(skillset: Skillset, actor: User) -> bool:
    return actor.is_admin or skillset.created_by == actor.user_id


async def _missing_or(skillset: Skillset, error: SkillsetError) -> SkillsetError:
    """Name the reason a guarded write matched nothing: the skillset is gone, or the guard held."""
    if await Skillset.find_one(Skillset.id == skillset.id) is None:
        return SkillsetNotFoundError("Skillset not found")
    return error


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

    async def get(self, slug: str) -> Skillset:
        skillset = await Skillset.find_one(Skillset.slug == slug)
        if skillset is None:
            raise SkillsetNotFoundError("Skillset not found")
        return skillset

    async def add_skill(self, slug: str, skill_slug: str, actor: User) -> None:
        skillset = await self.get(slug)
        if not _is_owner_or_admin(skillset, actor):
            raise PermissionDeniedError("Only the skillset's owner or an admin can add skills")
        skill = await Skill.find_one(Skill.slug == skill_slug)
        if skill is None or skill.status != SkillStatus.active:
            raise SkillNotFoundError("Skill not found")
        skill_id = str(skill.id)
        member = SkillsetMember(skill_id=skill_id, added_by=actor.user_id)
        result = await Skillset.find_one(
            {"_id": skillset.id, "members.skill_id": {"$ne": skill_id}}
        ).update({"$push": {"members": member.model_dump()}, "$inc": {"version": 1}})
        if result.matched_count == 0:
            raise await _missing_or(skillset, SkillsetMemberAlreadyError("Skill is already in this skillset"))

    async def remove_skill(self, slug: str, skill_slug: str, actor: User) -> None:
        skillset = await self.get(slug)
        skill = await Skill.find_one(Skill.slug == skill_slug)
        is_submitter = skill is not None and skill.submitter_id == actor.user_id
        if not (_is_owner_or_admin(skillset, actor) or is_submitter):
            raise PermissionDeniedError(
                "Only the skillset's owner, an admin, or the skill's submitter can remove it"
            )
        if skill is None:
            raise SkillNotFoundError("Skill not found")
        skill_id = str(skill.id)
        result = await Skillset.find_one(
            {"_id": skillset.id, "members.skill_id": skill_id}
        ).update({"$pull": {"members": {"skill_id": skill_id}}, "$inc": {"version": 1}})
        if result.matched_count == 0:
            raise await _missing_or(skillset, SkillsetMemberNotFoundError("Skill is not in this skillset"))


skillset_service = SkillsetService()
