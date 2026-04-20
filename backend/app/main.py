from contextlib import asynccontextmanager

import beanie
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.models import ALL_MODELS
from app.routers import health, me, skills


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongo_uri)
    await beanie.init_beanie(database=client.get_default_database(), document_models=ALL_MODELS)
    yield
    client.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Knowledge Hub API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(skills.router)

    return app


app = create_app()
