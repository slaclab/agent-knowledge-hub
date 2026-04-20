from fastapi import APIRouter
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    try:
        client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
        return {"status": "ok"}
    except Exception:
        return {"status": "degraded", "detail": "MongoDB unreachable"}
