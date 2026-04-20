from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from beanie import Document
from pydantic import Field


class FlagReason(str, enum.Enum):
    inappropriate = "inappropriate"
    stale = "stale"
    superseded = "superseded"
    broken = "broken"
    other = "other"


class FlagStatus(str, enum.Enum):
    active = "active"
    resolved = "resolved"


class SkillFlag(Document):
    skill_id: str
    reporter_id: str
    reason: FlagReason
    note: Optional[str] = None  # max 500 chars
    superseded_by_slug: Optional[str] = None
    status: FlagStatus = FlagStatus.active
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    class Settings:
        name = "skill_flags"
        indexes = [
            [("skill_id", 1), ("reporter_id", 1)],
        ]
