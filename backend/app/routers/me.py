from fastapi import APIRouter, Depends, Request
import logging

from app.auth import User, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


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
