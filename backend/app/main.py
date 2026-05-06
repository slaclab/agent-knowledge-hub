from contextlib import asynccontextmanager
import asyncio
import logging

import beanie
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import settings
from app.models import ALL_MODELS
from app.routers import health, me, site_settings, skills
from app.routers import github_scan
from app.routers.catalog import router as catalog_router
from app.routers.labels import admin_router as labels_admin_router
from app.routers.labels import router as labels_router
from app.routers.labels import skills_labels_router

import os
_log_level = getattr(logging, os.environ.get("LOG_LEVEL", "DEBUG").upper(), logging.DEBUG)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
# Keep noisy third-party libraries at WARNING
for _noisy in ("httpx", "httpcore", "motor", "pymongo", "beanie", "bson", "cachetools"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client.get_default_database()
    logger.info("Dropping legacy repo_url_1 index (if present)...")
    try:
        await asyncio.wait_for(db["skills"].drop_index("repo_url_1"), timeout=5.0)
        logger.info("Dropped repo_url_1 index")
    except Exception as e:
        logger.info("drop_index repo_url_1 skipped: %s", e)
    logger.info("Initialising Beanie...")
    await beanie.init_beanie(database=db, document_models=ALL_MODELS)
    logger.info("Beanie ready.")
    if settings.auth_mode != "dev" and settings.internal_api_secret is None:
        logger.warning(
            "INTERNAL_API_SECRET is not configured — Next.js proxy auth path is disabled. "
            "Set INTERNAL_API_SECRET in Vault and redeploy to enable."
        )
    yield
    client.close()


def _redact_private_key(text: str) -> str:
    """Replace any PEM private key block in text with a redacted placeholder."""
    import re
    return re.sub(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        "[REDACTED PRIVATE KEY]",
        text,
        flags=re.DOTALL,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Knowledge Hub API", version="0.2.0", lifespan=lifespan)

    # Rate limiter state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # NFR-P2: redact private key from any unhandled exception responses
    @app.exception_handler(Exception)
    async def redact_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        import traceback
        detail = _redact_private_key("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(site_settings.router)
    app.include_router(catalog_router)
    app.include_router(skills.router)
    app.include_router(skills.github_router)
    app.include_router(github_scan.router)
    app.include_router(labels_router)
    app.include_router(skills_labels_router)
    app.include_router(labels_admin_router)

    return app


app = create_app()
