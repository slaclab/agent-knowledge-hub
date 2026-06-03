from __future__ import annotations

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from pydantic import BaseModel

from app.auth import User, get_current_user, get_optional_user
from app.models.rating import Rating
from app.models.revision import SkillRevision
from app.models.skill import SkillStatus
from app.schemas.skill import (
    GitHubPreviewOut,
    LabelOut,
    PaginatedSkills,
    RateSkillIn,
    RateSkillOut,
    RevisionOut,
    SkillCreate,
    SkillListOut,
    SkillOut,
    SkillUpdate,
)
from app.services.label import label_service
from app.services.rating import rate_skill
from app.services.skill import DuplicateSkillError, PinNotSupportedError, SortField, skill_repository

router = APIRouter(prefix="/api/skills")
github_router = APIRouter(prefix="/api")

limiter = Limiter(key_func=get_remote_address)


def _skill_to_out(skill, labels: Optional[List[LabelOut]] = None, my_rating: Optional[int] = None, omit_content: bool = False) -> SkillOut:
    return SkillOut(
        id=str(skill.id),
        slug=skill.slug,
        name=skill.name,
        repo_url=skill.repo_url,
        skill_path=skill.skill_path,
        entry_type=skill.entry_type,
        status=skill.status,
        deactivation_reason=skill.deactivation_reason,
        superseded_by_slug=skill.superseded_by_slug,
        description=skill.description,
        readme_html=None if omit_content else skill.readme_html,
        skill_md_raw=None if omit_content else skill.skill_md_raw,
        skill_md_filename=None if omit_content else skill.skill_md_filename,
        readme_raw=None if omit_content else skill.readme_raw,
        compatible_platforms=skill.compatible_platforms,
        license=skill.license,
        version=skill.version,
        github_stars=skill.github_stars,
        last_commit_at=skill.last_commit_at,
        readme_fetched_at=skill.readme_fetched_at,
        uses_agent_gateway=skill.uses_agent_gateway,
        visibility=skill.visibility,
        forked_from_url=skill.forked_from_url,
        agent_count=getattr(skill, "agent_count", 0),
        agent_names=getattr(skill, "agent_names", []),
        has_mcp_server=getattr(skill, "has_mcp_server", False),
        has_scripts=getattr(skill, "has_scripts", False),
        plugin_author=getattr(skill, "plugin_author", None),
        file_manifest=getattr(skill, "file_manifest", []),
        manifest_truncated=getattr(skill, "manifest_truncated", False),
        pinned_commit_sha=getattr(skill, "pinned_commit_sha", None),
        pinned_ref=getattr(skill, "pinned_ref", None),
        upstream_sha=getattr(skill, "upstream_sha", None),
        update_available=getattr(skill, "update_available", False),
        submitter_id=skill.submitter_id,
        submitted_at=skill.submitted_at,
        updated_at=skill.updated_at,
        avg_rating=skill.avg_rating,
        rating_count=skill.rating_count,
        flag_count=skill.flag_count,
        labels=labels or [],
        my_rating=my_rating,
    )


def _skill_to_list_out(skill, labels: Optional[List[LabelOut]] = None) -> SkillListOut:
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
        agent_count=getattr(skill, "agent_count", 0),
        agent_names=getattr(skill, "agent_names", []),
        has_mcp_server=getattr(skill, "has_mcp_server", False),
        has_scripts=getattr(skill, "has_scripts", False),
        plugin_author=getattr(skill, "plugin_author", None),
        update_available=getattr(skill, "update_available", False),
        submitter_id=skill.submitter_id,
        submitted_at=skill.submitted_at,
        updated_at=skill.updated_at,
        labels=labels or [],
    )


@router.get("", response_model=PaginatedSkills)
async def list_skills(
    q: Optional[str] = Query(None, description="Full-text search query"),
    sort: SortField = Query("newest"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    forked_from: Optional[str] = Query(None, description="Filter by upstream fork URL"),
    visibility: Optional[str] = Query(None, description="Filter by visibility: public, internal, all"),
    labels: Optional[str] = Query(None, description="Comma-separated label names (AND filter)"),
):
    label_list = [l.strip() for l in labels.split(",") if l.strip()] if labels else None
    items, total = await skill_repository.list(
        q=q, sort=sort, page=page, page_size=page_size,
        forked_from=forked_from, visibility=visibility, labels=label_list,
    )
    skill_ids = [str(s.id) for s in items]
    labels_by_skill = await label_service.batch_labels_for_skills(skill_ids)
    return PaginatedSkills(
        items=[_skill_to_list_out(s, labels=labels_by_skill.get(str(s.id), [])) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    user: User = Depends(get_current_user),
):
    try:
        skill = await skill_repository.create(body, submitter_id=user.user_id)
    except DuplicateSkillError as e:
        detail = "A skill with this repo URL and path already exists."
        if e.existing_slug:
            detail += f" See /skills/{e.existing_slug}"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    return _skill_to_out(skill)


@router.get("/{slug}", response_model=SkillOut)
async def get_skill(slug: str, viewer: Optional[User] = Depends(get_optional_user)):
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
    skill_labels = await label_service.list_for_skill(str(skill.id))
    my_rating = None
    if viewer:
        rating = await Rating.find_one(
            Rating.skill_id == str(skill.id),
            Rating.user_id == viewer.user_id,
        )
        my_rating = rating.value if rating else None
    from app.models.skill import VisibilityEnum
    omit_content = skill.visibility == VisibilityEnum.internal and not viewer
    return _skill_to_out(skill, labels=skill_labels, my_rating=my_rating, omit_content=omit_content)


@router.post("/{slug}/rate", response_model=RateSkillOut)
@limiter.limit("30/minute")
async def rate_skill_route(
    slug: str,
    body: RateSkillIn,
    request: Request,
    user: User = Depends(get_current_user),
):
    skill = await skill_repository.get(slug)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    avg, count = await rate_skill(str(skill.id), user.user_id, body.value)
    return RateSkillOut(avg_rating=avg, rating_count=count, my_rating=body.value)


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
    skill_labels = await label_service.list_for_skill(str(skill.id))
    return _skill_to_out(skill, labels=skill_labels)


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
    skill_labels = await label_service.list_for_skill(str(skill.id))
    return _skill_to_out(skill, labels=skill_labels)


@router.post("/{slug}/pin", response_model=SkillOut)
@limiter.limit("10/minute")
async def pin_skill(slug: str, request: Request, user: User = Depends(get_current_user)):
    skill = await skill_repository.get(slug, include_deactivated=True)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    if skill.submitter_id != user.user_id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your skill")
    try:
        skill = await skill_repository.pin(skill, actor_id=user.user_id)
    except PinNotSupportedError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    skill_labels = await label_service.list_for_skill(str(skill.id))
    return _skill_to_out(skill, labels=skill_labels)


class AddPlatformIn(BaseModel):
    platform: str


@router.post("/{slug}/platforms", response_model=SkillOut)
async def add_platform(slug: str, body: AddPlatformIn, user: User = Depends(get_current_user)):
    from app.models.skill import Skill
    skill = await Skill.find_one(Skill.slug == slug)
    if not skill or skill.status == SkillStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    platform = body.platform.strip().lower()
    if not platform:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Platform name required")
    if platform not in skill.compatible_platforms:
        skill.compatible_platforms = skill.compatible_platforms + [platform]
        await skill.save()
    skill_labels = await label_service.list_for_skill(str(skill.id))
    return _skill_to_out(skill, labels=skill_labels)


@router.delete("/{slug}/platforms/{platform}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_platform(slug: str, platform: str, user: User = Depends(get_current_user)):
    from app.models.skill import Skill
    skill = await Skill.find_one(Skill.slug == slug)
    if not skill or skill.status == SkillStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    skill.compatible_platforms = [p for p in skill.compatible_platforms if p != platform]
    await skill.save()


class FileContentOut(BaseModel):
    content: str
    path: str


class FileBinaryOut(BaseModel):
    error: Literal["binary_file"]
    github_url: str


@router.get("/{slug}/files/{path:path}")
@limiter.limit("60/minute")
async def get_skill_file(
    slug: str,
    path: str,
    request: Request,
    viewer: Optional[User] = Depends(get_optional_user),
):
    from app.models.skill import Skill, VisibilityEnum
    from app.services.github import github_scanner, GitHubRef
    from app.services.github import github_url_parser

    skill = await Skill.find_one(Skill.slug == slug)
    if not skill or skill.status == SkillStatus.deactivated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    # Auth: internal skills require a logged-in user
    if skill.visibility == VisibilityEnum.internal and not viewer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Path validation: only serve paths present in the manifest (FR-7a)
    manifest_paths = {e.path for e in getattr(skill, "file_manifest", [])}
    if path not in manifest_paths:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in manifest")

    # Find the manifest entry to check is_text / is_dir
    entry = next((e for e in skill.file_manifest if e.path == path), None)
    if entry and entry.is_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot fetch directory content")

    # Local skills: read from snapshotted_files
    if skill.source_type == "local":
        content = skill.snapshotted_files.get(path)
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in manifest")
        if entry and not entry.is_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=FileBinaryOut(error="binary_file", github_url=skill.repo_url).model_dump(),
            )
        return FileContentOut(content=content, path=path)

    # GitHub skills: fetch live via public method
    try:
        ref = github_url_parser.parse(skill.repo_url)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Cannot parse repo URL")

    if entry and not entry.is_text:
        # Build a GitHub HTML URL for the binary file
        branch_part = f"/blob/{ref.branch or 'main'}" if True else ""
        dir_part = skill.skill_path.strip("/")
        github_url = f"https://github.com/{ref.owner}/{ref.repo}{branch_part}/{(dir_part + '/' if dir_part else '')}{path}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "binary_file", "github_url": github_url},
        )

    # Use pinned SHA as the ref for deterministic content; fall back to branch
    file_ref = getattr(skill, "pinned_commit_sha", None) or ref.branch
    cache_key = f"{slug}:{path}:{file_ref or 'head'}"
    content = await github_scanner.fetch_file_content(
        owner=ref.owner,
        repo=ref.repo,
        branch=file_ref,
        skill_path=skill.skill_path,
        filename=path,
        cache_key=cache_key,
    )
    if content is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GitHub fetch failed")

    return FileContentOut(content=content, path=path)


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
@limiter.limit("10/minute")
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
