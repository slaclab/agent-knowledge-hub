from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import User, get_current_user
from app.models.skill import Skill
from app.schemas.skill import DiscoverOut, GitHubRefOut, SkillScanSnapshotOut
from app.services.github import (
    GitHubFetchError,
    GitHubRef,
    SkillScanSnapshot,
    github_scanner,
    github_url_parser,
    metadata_extractor,
)

router = APIRouter(prefix="/api")
limiter = Limiter(key_func=get_remote_address)


def _snapshot_to_out(snap: SkillScanSnapshot) -> SkillScanSnapshotOut:
    return SkillScanSnapshotOut(
        ref=GitHubRefOut(
            owner=snap.ref.owner,
            repo=snap.ref.repo,
            branch=snap.ref.branch,
            path=snap.ref.path,
        ),
        name=snap.name,
        description=snap.description,
        compatible_platforms=snap.compatible_platforms,
        version=snap.version,
        license=snap.license,
        readme_html=snap.readme_html,
        stars=snap.stars,
        last_commit_at=snap.last_commit_at,
        visibility=snap.visibility,
        forked_from_url=snap.forked_from_url,
        fetched_at=snap.fetched_at,
        no_skill_files=snap.no_skill_files,
        existing_slug=snap.existing_slug,
        agent_count=snap.agent_count,
        agent_names=snap.agent_names,
        has_mcp_server=snap.has_mcp_server,
        has_scripts=snap.has_scripts,
        plugin_author=snap.plugin_author,
        keywords=snap.keywords,
    )


async def _check_existing(repo_url: str, skill_path: str) -> str | None:
    existing = await Skill.find_one(Skill.repo_url == repo_url, Skill.skill_path == skill_path)
    return existing.slug if existing else None


@router.get("/scan", response_model=SkillScanSnapshotOut | DiscoverOut)
@router.get("/github-scan", response_model=SkillScanSnapshotOut | DiscoverOut)  # permanent alias
@limiter.limit("10/minute")
async def github_scan(
    url: str = Query(..., description="GitHub repo or tree URL to scan"),
    discover: bool = Query(False, description="Discover all skill directories in the repo"),
    request: Request = None,
    user: User = Depends(get_current_user),
):
    try:
        ref = github_url_parser.parse(url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    repo_url = f"https://github.com/{ref.owner}/{ref.repo}"
    cache_key = f"{url}:{user.user_id}:{discover}"

    if discover:
        try:
            results, truncated, capped = await github_scanner.discover(ref, cache_key=cache_key)
        except GitHubFetchError as e:
            detail = str(e)
            code = status.HTTP_429_TOO_MANY_REQUESTS if "rate limit" in detail.lower() else status.HTTP_404_NOT_FOUND
            raise HTTPException(status_code=code, detail=detail)

        snapshots = []
        for raw in results:
            snap = metadata_extractor.extract(raw)
            snap.existing_slug = await _check_existing(repo_url, raw.ref.path)
            snapshots.append(_snapshot_to_out(snap))

        return DiscoverOut(skills=snapshots, tree_truncated=truncated, capped=capped)

    try:
        raw = await github_scanner.scan(ref, cache_key=cache_key)
    except GitHubFetchError as e:
        detail = str(e)
        if "rate limit" in detail.lower():
            code = status.HTTP_429_TOO_MANY_REQUESTS
        elif "not found" in detail.lower():
            code = status.HTTP_404_NOT_FOUND
        else:
            code = status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(status_code=code, detail=detail)

    snap = metadata_extractor.extract(raw)
    snap.existing_slug = await _check_existing(repo_url, ref.path)
    return _snapshot_to_out(snap)
