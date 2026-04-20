from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from app.config import settings


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
    else:
        user_id = request.headers.get("X-Forwarded-User")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

    return User(user_id=user_id, is_admin=user_id in settings.admin_user_set)


def require_admin(user: User) -> User:
    """FastAPI dependency — requires the caller to have admin rights."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
