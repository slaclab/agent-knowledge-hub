from __future__ import annotations

import pytest
import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from app.models import ALL_MODELS


@pytest_asyncio.fixture(autouse=True)
async def mongo():
    client = AsyncMongoMockClient()
    await init_beanie(database=client["test-db"], document_models=ALL_MODELS)
    yield
    client.close()
