from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class User:
    user_id: str
    is_admin: bool = False


def get_current_user(request: Request) -> User:
    """FastAPI dependency — extracts identity from VouchProxy header or DEV_USER."""
    if settings.auth_mode == "dev":
        user_id = settings.dev_user
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AUTH_MODE=dev but DEV_USER is not set",
            )
        return User(user_id=user_id, is_admin=user_id in settings.admin_user_set)

    # Path 1: Direct ingress — VouchProxy-injected headers (no internal secret needed)
    vouch_user = request.headers.get("X-Vouch-Idp-Claims-Name") or request.headers.get(
        "X-Vouch-User"
    )
    if vouch_user:
        return User(user_id=vouch_user, is_admin=vouch_user in settings.admin_user_set)

    # Path 2: Next.js proxy — requires matching internal secret
    # X-Forwarded-User is only trusted after the secret check passes.
    # If internal_api_secret is not configured (None), this path is disabled entirely.
    if settings.internal_api_secret is not None:
        incoming_secret = request.headers.get("X-Internal-Secret", "")
        if hmac.compare_digest(incoming_secret, settings.internal_api_secret):
            forwarded_user = request.headers.get("X-Forwarded-User", "")
            if forwarded_user:
                return User(
                    user_id=forwarded_user,
                    is_admin=forwarded_user in settings.admin_user_set,
                )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def get_optional_user(request: Request) -> User | None:
    """FastAPI dependency — returns User if authenticated, None otherwise."""
    try:
        return get_current_user(request)
    except HTTPException:
        return None


def require_admin(user: User) -> User:
    """FastAPI dependency — requires the caller to have admin rights."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
