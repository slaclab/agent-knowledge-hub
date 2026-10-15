from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter

from app.auth import User, get_current_user, user_id_key_func
from app.models.skillset import Skillset
from app.schemas.skillset import (
    PaginatedSkillsets,
    SkillsetCreate,
    SkillsetListOut,
    SkillsetOrderIn,
    SkillsetOut,
    SkillsetUpdate,
)
from app.services.skillset import (
    PermissionDeniedError,
    SkillNotFoundError,
    SkillsetAlreadyExistsError,
    SkillsetError,
    SkillsetMemberAlreadyError,
    SkillsetMemberNotFoundError,
    SkillsetNotFoundError,
    SkillsetVersionConflictError,
    skillset_service,
)

router = APIRouter(prefix="/api/skillsets", tags=["skillsets"])

# Counted per user across every path of a route. slowapi's default key_style ("url") counts
# each path separately, so each (skillset, skill) pair would get its own allowance.
limiter = Limiter(key_func=user_id_key_func, key_style="endpoint")

_STATUS = {
    SkillsetNotFoundError: status.HTTP_404_NOT_FOUND,
    SkillNotFoundError: status.HTTP_404_NOT_FOUND,
    SkillsetMemberNotFoundError: status.HTTP_404_NOT_FOUND,
    SkillsetMemberAlreadyError: status.HTTP_409_CONFLICT,
    SkillsetVersionConflictError: status.HTTP_409_CONFLICT,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
}


def _http_error(exc: SkillsetError) -> HTTPException:
    return HTTPException(status_code=_STATUS[type(exc)], detail=str(exc))


def _list_out(skillset: Skillset) -> SkillsetListOut:
    # Counts orphan members until a reorder drops them; avoids a Skill query per row.
    return SkillsetListOut(
        slug=skillset.slug,
        name=skillset.name,
        description=skillset.description,
        created_by=skillset.created_by,
        member_count=len(skillset.members),
        created_at=skillset.created_at,
    )


@router.get("", response_model=PaginatedSkillsets)
async def list_skillsets(
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=100),
    created_by: Optional[str] = Query(None, max_length=128),
):
    items, total = await skillset_service.list(page=page, page_size=page_size, created_by=created_by)
    return PaginatedSkillsets(
        items=[_list_out(s) for s in items], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=SkillsetOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def create_skillset(
    request: Request,
    body: SkillsetCreate,
    user: User = Depends(get_current_user),
):
    try:
        skillset = await skillset_service.create(
            name=body.name, description=body.description, actor=user, slug=body.slug
        )
    except SkillsetAlreadyExistsError as e:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(e), "suggested_slug": e.suggested_slug},
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return await skillset_service.detail(skillset)


@router.get("/{slug}", response_model=SkillsetOut)
async def get_skillset(slug: str):
    try:
        skillset = await skillset_service.get(slug)
    except SkillsetError as e:
        raise _http_error(e)
    return await skillset_service.detail(skillset)


@router.patch("/{slug}", response_model=SkillsetOut)
async def update_skillset(
    slug: str,
    body: SkillsetUpdate,
    user: User = Depends(get_current_user),
):
    try:
        skillset = await skillset_service.update(
            slug, user, name=body.name, description=body.description
        )
    except SkillsetError as e:
        raise _http_error(e)
    return await skillset_service.detail(skillset)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skillset(slug: str, user: User = Depends(get_current_user)):
    try:
        await skillset_service.delete(slug, user)
    except SkillsetError as e:
        raise _http_error(e)


@router.put("/{slug}/order", response_model=SkillsetOut)
async def reorder_skillset(
    slug: str,
    body: SkillsetOrderIn,
    user: User = Depends(get_current_user),
):
    try:
        skillset = await skillset_service.reorder(slug, body.skill_slugs, body.version, user)
    except SkillsetError as e:
        raise _http_error(e)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return await skillset_service.detail(skillset)


@router.put("/{slug}/skills/{skill_slug}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("50/hour")
async def add_skillset_member(
    request: Request,
    slug: str,
    skill_slug: str,
    user: User = Depends(get_current_user),
):
    try:
        await skillset_service.add_skill(slug, skill_slug, user)
    except SkillsetError as e:
        raise _http_error(e)


@router.delete("/{slug}/skills/{skill_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_skillset_member(
    slug: str,
    skill_slug: str,
    user: User = Depends(get_current_user),
):
    try:
        await skillset_service.remove_skill(slug, skill_slug, user)
    except SkillsetError as e:
        raise _http_error(e)
