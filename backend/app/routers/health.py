from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    try:
        from beanie import Document
        from app.models.skill import Skill
        await Skill.find_one()
        return {"status": "ok"}
    except Exception:
        return {"status": "degraded", "detail": "MongoDB unreachable"}
