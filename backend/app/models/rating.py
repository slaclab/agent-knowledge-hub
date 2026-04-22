from __future__ import annotations

from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class Rating(Document):
    skill_id: str
    user_id: str
    value: int  # 1–5
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "ratings"
        indexes = [
            IndexModel([("skill_id", ASCENDING), ("user_id", ASCENDING)], unique=True),
        ]
