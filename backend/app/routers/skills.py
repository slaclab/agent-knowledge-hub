from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.auth import User, get_current_user
from app.models.revision import SkillRevision
from app.models.skill import SkillStatus
from app.schemas.skill import (
    GitHubPreviewOut,
    PaginatedSkills,
    RevisionOut,
    SkillCreate,
    SkillListOut,
    SkillOut,
    SkillUpdate,
)
from app.services.skill import SortField, skill_repository

router = APIRouter(prefix="/api/skills")
github_router = APIRouter(prefix="/api")


def _skill_to_out(skill) -> SkillOut:
    return SkillOut(
        id=str(skill.id),
        slug=skill.slug,
        name=skill.name,
        repo_url=skill.repo_url,
        entry_type=skill.entry_type,
        status=skill.status,
        deactivation_reason=skill.deactivation_reason,
        superseded_by_slug=skill.superseded_by_slug,
        description=skill.description,
        readme_html=skill.readme_html,
        compatible_platforms=skill.compatible_platforms,
        license=skill.license,
        version=skill.version,
        github_stars=skill.github_stars,
        last_commit_at=skill.last_commit_at,
        readme_fetched_at=skill.readme_fetched_at,
        uses_agent_gateway=skill.uses_agent_gateway,
        visibility=skill.visibility,
        forked_from_url=skill.forked_from_url,
        submitter_id=skill.submitter_id,
        submitted_at=skill.submitted_at,
        updated_at=skill.updated_at,
        avg_rating=skill.avg_rating,
        rating_count=skill.rating_count,
        flag_count=skill.flag_count,
    )


def _skill_to_list_out(skill) -> SkillListOut:
    return SkillListOut(
        id=str(skill.id),
        slug=skill.slug,
        name=skill.name,
        entry_type=skill.entry_type,
        status=skill.status,
        description=skill.description,
        compatible_platforms=skill.compatible_platforms,
        github_stars=skill.github_stars,
        avg_rating=skill.avg_rating,
        rating_count=skill.rating_count,
        flag_count=skill.flag_count,
        visibility=skill.visibility,
        forked_from_url=skill.forked_from_url,
        submitter_id=skill.submitter_id,
        submitted_at=skill.submitted_at,
        updated_at=skill.updated_at,
    )


@router.get("", response_model=PaginatedSkills)
async def list_skills(
    q: Optional[str] = Query(None, description="Full-text search query"),
    sort: SortField = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    forked_from: Optional[str] = Query(None, description="Filter by upstream fork URL"),
    visibility: Optional[str] = Query(None, description="Filter by visibility: public, internal, all"),
):
    items, total = await skill_repository.list(
        q=q, sort=sort, page=page, page_size=page_size,
        forked_from=forked_from, visibility=visibility,
    )
    return PaginatedSkills(
        items=[_skill_to_list_out(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    user: User = Depends(get_current_user),
):
    skill = await skill_repository.create(body, submitter_id=user.user_id)
    return _skill_to_out(skill)


@router.get("/{slug}", response_model=SkillOut)
async def get_skill(slug: str):
    skill = await skill_repository.get(slug)
    if not skill:
        # Check if it's deactivated (for tombstone response)
        from app.models.skill import Skill
        deactivated = await Skill.find_one(Skill.slug == slug)
        if deactivated and deactivated.status == SkillStatus.deactivated:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail={
                    "code": "deactivated",
                    "reason": deactivated.deactivation_reason,
                    "superseded_by_slug": deactivated.superseded_by_slug,
                },
            )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return _skill_to_out(skill)


@router.patch("/{slug}", response_model=SkillOut)
async def update_skill(
    slug: str,
    body: SkillUpdate,
    user: User = Depends(get_current_user),
):
    skill = await skill_repository.get(slug, include_deactivated=True)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    if skill.submitter_id != user.user_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your skill")
    skill = await skill_repository.update(skill, body, actor_id=user.user_id)
    return _skill_to_out(skill)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    slug: str,
    user: User = Depends(get_current_user),
):
    skill = await skill_repository.get(slug, include_deactivated=True)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    if skill.submitter_id != user.user_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your skill")
    await skill_repository.delete(skill)


@router.post("/{slug}/refetch", response_model=SkillOut)
async def refetch_skill(slug: str, user: User = Depends(get_current_user)):
    skill = await skill_repository.get(slug, include_deactivated=True)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    if skill.submitter_id != user.user_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your skill")
    skill = await skill_repository.refetch(skill, actor_id=user.user_id)
    return _skill_to_out(skill)


@router.get("/{slug}/revisions", response_model=List[RevisionOut])
async def list_revisions(slug: str):
    from app.models.skill import Skill
    skill = await Skill.find_one(Skill.slug == slug)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    revisions = (
        await SkillRevision.find(SkillRevision.skill_id == str(skill.id))
        .sort([("revision_number", 1)])
        .to_list()
    )
    return [
        RevisionOut(
            revision_number=r.revision_number,
            actor_id=r.actor_id,
            action=r.action,
            changelog_note=r.changelog_note,
            created_at=r.created_at,
            snapshot=r.snapshot,
        )
        for r in revisions
    ]


@router.get("/{slug}/revisions/{n}", response_model=RevisionOut)
async def get_revision(slug: str, n: int):
    from app.models.skill import Skill
    skill = await Skill.find_one(Skill.slug == slug)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    rev = await SkillRevision.find_one(
        SkillRevision.skill_id == str(skill.id),
        SkillRevision.revision_number == n,
    )
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    return RevisionOut(
        revision_number=rev.revision_number,
        actor_id=rev.actor_id,
        action=rev.action,
        changelog_note=rev.changelog_note,
        created_at=rev.created_at,
        snapshot=rev.snapshot,
    )


@github_router.get("/github-preview", response_model=GitHubPreviewOut)
async def github_preview(
    repo_url: str = Query(..., description="GitHub repo URL to preview"),
    request: Request = None,
):
    """Preview GitHub repo metadata using the shared fallback chain (unauth → PAT → App token).

    Rate limited to 10 req/min per IP by the rate-limiter middleware.
    """
    from app.services.github import GitHubFetchError, github_fetcher
    try:
        snapshot = await github_fetcher.fetch(repo_url)
    except GitHubFetchError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return GitHubPreviewOut(
        name=snapshot.name,
        description=snapshot.description,
        stars=snapshot.stars,
        license=snapshot.license,
        last_commit_at=snapshot.last_commit_at,
        visibility=snapshot.visibility,
    )
