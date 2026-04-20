from __future__ import annotations

import re
from datetime import datetime
from typing import List, Literal, Optional, Tuple

from beanie.operators import In, Text
from slugify import slugify

from app.models.skill import Skill, SkillStatus
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services.github import GitHubFetchError, github_fetcher
from app.services.revision import revision_service
from app.models.revision import RevisionAction


SortField = Literal["newest", "highest_rated", "most_rated", "most_stars"]


async def _unique_slug(base: str) -> str:
    slug = slugify(base)
    if not await Skill.find_one(Skill.slug == slug):
        return slug
    i = 2
    while await Skill.find_one(Skill.slug == f"{slug}-{i}"):
        i += 1
    return f"{slug}-{i}"


class SkillRepository:
    async def list(
        self,
        q: Optional[str] = None,
        labels: Optional[List[str]] = None,
        sort: SortField = "newest",
        page: int = 1,
        page_size: int = 20,
        include_deactivated: bool = False,
    ) -> Tuple[List[Skill], int]:
        query_parts = []
        if not include_deactivated:
            query_parts.append(Skill.status == SkillStatus.active)

        if q:
            query_parts.append({"$text": {"$search": q}})

        base_query = Skill.find(*query_parts) if query_parts else Skill.find()

        sort_expr = {
            "newest": [("submitted_at", -1)],
            "highest_rated": [("avg_rating", -1)],
            "most_rated": [("rating_count", -1)],
            "most_stars": [("github_stars", -1)],
        }[sort]

        total = await base_query.count()
        items = (
            await base_query.sort(sort_expr)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list()
        )
        return items, total

    async def get(self, slug: str, include_deactivated: bool = False) -> Optional[Skill]:
        skill = await Skill.find_one(Skill.slug == slug)
        if skill and not include_deactivated and skill.status == SkillStatus.deactivated:
            return None
        return skill

    async def create(self, data: SkillCreate, submitter_id: str) -> Skill:
        github_data = None
        try:
            github_data = await github_fetcher.fetch(data.repo_url)
        except GitHubFetchError:
            pass

        name = data.name or (github_data.name if github_data else data.repo_url.split("/")[-1])
        slug = await _unique_slug(name)

        skill = Skill(
            slug=slug,
            name=name,
            repo_url=data.repo_url,
            entry_type=data.entry_type,
            description=data.description or (github_data.description if github_data else None),
            readme_html=github_data.readme_html if github_data else None,
            readme_fetched_at=github_data.fetched_at if github_data else None,
            compatible_platforms=data.compatible_platforms,
            license=data.license or (github_data.license if github_data else None),
            version=data.version,
            github_stars=github_data.stars if github_data else None,
            last_commit_at=github_data.last_commit_at if github_data else None,
            uses_agent_gateway=data.uses_agent_gateway,
            submitter_id=submitter_id,
        )
        await skill.insert()
        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=submitter_id,
            action=RevisionAction.create,
            snapshot=skill.model_dump(mode="json"),
        )
        return skill

    async def update(
        self,
        skill: Skill,
        data: SkillUpdate,
        actor_id: str,
    ) -> Skill:
        update_fields = data.model_dump(exclude_none=True, exclude={"changelog_note"})
        for k, v in update_fields.items():
            setattr(skill, k, v)
        skill.updated_at = datetime.utcnow()
        await skill.save()
        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=actor_id,
            action=RevisionAction.edit,
            snapshot=skill.model_dump(mode="json"),
            changelog_note=data.changelog_note,
        )
        return skill

    async def refetch(self, skill: Skill, actor_id: str) -> Skill:
        try:
            gh = await github_fetcher.fetch(skill.repo_url)
            skill.github_stars = gh.stars
            skill.last_commit_at = gh.last_commit_at
            skill.readme_html = gh.readme_html
            skill.readme_fetched_at = gh.fetched_at
            if not skill.description:
                skill.description = gh.description
            skill.updated_at = datetime.utcnow()
            await skill.save()
            await revision_service.record(
                skill_id=str(skill.id),
                actor_id=actor_id,
                action=RevisionAction.refetch,
                snapshot=skill.model_dump(mode="json"),
            )
        except GitHubFetchError:
            pass
        return skill

    async def delete(self, skill: Skill) -> None:
        await skill.delete()


skill_repository = SkillRepository()
