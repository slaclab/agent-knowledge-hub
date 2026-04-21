from contextlib import asynccontextmanager

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

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client.get_default_database()
    # Drop old repo_url single-column unique index before Beanie creates the new compound one
    try:
        await db["skills"].drop_index("repo_url_1")
    except Exception:
        pass
    await beanie.init_beanie(database=db, document_models=ALL_MODELS)
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
    app = FastAPI(title="Agent Knowledge Hub API", version="0.1.0", lifespan=lifespan)

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
    app.include_router(skills.router)
    app.include_router(skills.github_router)
    app.include_router(github_scan.router)

    return app


app = create_app()
