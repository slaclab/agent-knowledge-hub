from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import User, get_current_user, get_optional_user
from app.models.install_event import SkillInstallEvent
from app.schemas.skill import PaginatedSkills, SkillListOut
from app.services.user_activity import user_activity_service

router = APIRouter(prefix="/api/users")


def _to_list_out(skills, labels_map=None):
    from app.routers.skills import _skill_to_list_out
    return [_skill_to_list_out(s) for s in skills]


@router.get("/{user_id}")
async def get_user_profile(
    user_id: str,
    viewer: User | None = Depends(get_optional_user),
):
    viewer_id = viewer.user_id if viewer else None
    viewer_is_admin = viewer.is_admin if viewer else False
    return await user_activity_service.get_summary(
        user_id=user_id,
        viewer_id=viewer_id,
        viewer_is_admin=viewer_is_admin,
    )


@router.get("/{user_id}/skills", response_model=PaginatedSkills)
async def get_user_skills(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _viewer: User | None = Depends(get_optional_user),
):
    skills, total = await user_activity_service.get_submitted(
        user_id=user_id, page=page, page_size=page_size
    )
    from app.routers.skills import _skill_to_list_out
    return PaginatedSkills(
        items=[_skill_to_list_out(s) for s in skills],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, -(-total // page_size)),
    )


@router.get("/{user_id}/edits", response_model=PaginatedSkills)
async def get_user_edits(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _viewer: User | None = Depends(get_optional_user),
):
    skills, total = await user_activity_service.get_edited(
        user_id=user_id, page=page, page_size=page_size
    )
    from app.routers.skills import _skill_to_list_out
    return PaginatedSkills(
        items=[_skill_to_list_out(s) for s in skills],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, -(-total // page_size)),
    )


@router.get("/{user_id}/installs")
async def get_user_installs(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    viewer: User = Depends(get_current_user),
):
    if viewer.user_id != user_id and not viewer.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Install history is private")

    query = SkillInstallEvent.find(SkillInstallEvent.user_id == user_id)
    total = await query.count()
    events = (
        await query.sort([("installed_at", -1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

    # Enrich with skill metadata where skill still exists
    from app.models.skill import Skill
    slugs = [e.skill_slug for e in events]
    skills = await Skill.find({"slug": {"$in": slugs}}).to_list()
    skill_map = {s.slug: s for s in skills}

    items = [
        {
            "skill_slug": e.skill_slug,
            "skill_name": skill_map[e.skill_slug].name if e.skill_slug in skill_map else None,
            "installed_at": e.installed_at.isoformat(),
            "update_available": skill_map[e.skill_slug].update_available if e.skill_slug in skill_map else False,
            "is_deleted": e.skill_slug not in skill_map,
        }
        for e in events
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
