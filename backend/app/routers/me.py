import re
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter

from app.auth import User, get_current_user, user_id_key_func
from app.models.install_event import SkillInstallEvent
from app.models.skill import Skill, SkillStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
_limiter = Limiter(key_func=user_id_key_func)

_SLUG_RE = re.compile(r"^[a-z0-9-]{1,200}$")


@router.get("/me")
async def me(request: Request, user: User = Depends(get_current_user)):
    # DEBUG: log raw headers received at /api/me
    safe_headers = {
        k: ("[REDACTED]" if k.lower() in ("x-internal-secret", "authorization") else v)
        for k, v in request.headers.items()
    }
    logger.debug("ME /api/me received headers: %s", safe_headers)
    logger.info("ME /api/me resolved user=%s is_admin=%s", user.user_id, user.is_admin)
    return {"user_id": user.user_id, "is_admin": user.is_admin}


@router.post("/me/installs/{slug}", status_code=status.HTTP_204_NO_CONTENT)
@_limiter.limit("60/hour")
async def record_install(
    request: Request,
    slug: str,
    user: User = Depends(get_current_user),
):
    if not _SLUG_RE.match(slug):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid slug")

    skill = await Skill.find_one(Skill.slug == slug, Skill.status == SkillStatus.active)
    if skill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    # Atomic upsert — creates or updates installed_at
    collection = SkillInstallEvent.get_motor_collection()
    now = datetime.now(timezone.utc)
    await collection.update_one(
        {"user_id": user.user_id, "skill_slug": slug},
        {
            "$set": {"installed_at": now, "skill_id": str(skill.id)},
            "$setOnInsert": {"user_id": user.user_id, "skill_slug": slug},
        },
        upsert=True,
    )


@router.get("/me/installs")
async def get_my_installs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    query = SkillInstallEvent.find(SkillInstallEvent.user_id == user.user_id)
    total = await query.count()
    events = (
        await query.sort([("installed_at", -1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )

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
