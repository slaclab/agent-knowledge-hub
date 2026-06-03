"""Admin-only routes: flag queue, skill deactivation/reactivation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import User, require_admin
from app.schemas.flag import (
    DeactivateIn,
    DeactivateOut,
    PaginatedFlaggedSkills,
    ReactivateIn,
    ReactivateOut,
)
import app.services.flag as flag_service
from app.services.skill import skill_repository

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/flags", response_model=PaginatedFlaggedSkills)
async def list_flagged_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = await flag_service.list_flagged_skills(page=page, page_size=page_size)
    pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedFlaggedSkills(items=items, total=total, page=page, pages=pages)


@router.post("/skills/{slug}/deactivate", response_model=DeactivateOut)
async def deactivate_skill(
    slug: str,
    body: DeactivateIn,
    admin: User = Depends(require_admin),
):
    try:
        skill, warnings = await skill_repository.deactivate(
            slug=slug,
            reason=body.reason,
            admin_id=admin.user_id,
            superseded_by_slug=body.superseded_by_slug,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
        if msg == "already_deactivated":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill is already deactivated")
        raise
    return DeactivateOut(slug=skill.slug, status=skill.status.value, warnings=warnings)


@router.post("/skills/{slug}/reactivate", response_model=ReactivateOut)
async def reactivate_skill(
    slug: str,
    body: ReactivateIn,
    admin: User = Depends(require_admin),
):
    try:
        skill = await skill_repository.reactivate(
            slug=slug,
            reason=body.reason,
            admin_id=admin.user_id,
        )
    except ValueError as e:
        msg = str(e)
        if msg == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
        if msg == "already_active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill is already active")
        raise
    return ReactivateOut(slug=skill.slug, status=skill.status.value)
