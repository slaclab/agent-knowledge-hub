from fastapi import APIRouter, Depends

from app.auth import User, get_current_user

router = APIRouter(prefix="/api")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"user_id": user.user_id, "is_admin": user.is_admin}
