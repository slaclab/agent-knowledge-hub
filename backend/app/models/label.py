from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from beanie import Document
from pydantic import Field


class Label(Document):
    name: str  # canonical, lowercase, hyphens only
    aliases: List[str] = Field(default_factory=list)
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    usage_count: int = 0

    class Settings:
        name = "labels"
        indexes = [[("name", 1)]]


class SkillLabel(Document):
    skill_id: str
    label_id: str
    applied_by: str
    applied_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "skill_labels"
        indexes = [
            [("skill_id", 1), ("label_id", 1), ("applied_by", 1)],
        ]
