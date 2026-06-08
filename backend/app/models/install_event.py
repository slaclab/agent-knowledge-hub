from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


class SkillInstallEvent(Document):
    user_id: str
    skill_id: Optional[str] = None  # stringified ObjectId; None if skill deleted
    skill_slug: str
    installed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "skill_install_events"
        indexes = [
            IndexModel(
                [("user_id", ASCENDING), ("skill_slug", ASCENDING)],
                unique=True,
                name="user_skill_slug_unique",
            ),
            IndexModel(
                [("user_id", ASCENDING), ("installed_at", DESCENDING)],
                name="user_installed_at",
            ),
        ]
