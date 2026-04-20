from __future__ import annotations

from datetime import datetime

from beanie import Document
from pydantic import Field


class Rating(Document):
    skill_id: str
    user_id: str
    value: int  # 1–5
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "ratings"
        indexes = [
            [("skill_id", 1), ("user_id", 1)],  # unique enforced in service layer
        ]
