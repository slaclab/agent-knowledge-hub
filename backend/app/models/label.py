from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from beanie import Document
from pymongo import ASCENDING, IndexModel
from pydantic import Field, field_validator


_LABEL_NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class Label(Document):
    name: str  # canonical, lowercase, hyphens only
    aliases: List[str] = Field(default_factory=list)
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    usage_count: int = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 50:
            raise ValueError("Label name must be 50 characters or fewer")
        if not _LABEL_NAME_RE.match(v):
            raise ValueError(
                "Label name must contain only lowercase letters, digits, and hyphens, "
                "and must not start or end with a hyphen"
            )
        return v

    class Settings:
        name = "labels"
        indexes = [
            IndexModel([("name", ASCENDING)], unique=True),
        ]


class SkillLabel(Document):
    skill_id: str
    label_id: str
    applied_by: str
    applied_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "skill_labels"
        indexes = [
            IndexModel(
                [("skill_id", ASCENDING), ("label_id", ASCENDING), ("applied_by", ASCENDING)],
                unique=True,
            ),
            IndexModel([("label_id", ASCENDING), ("skill_id", ASCENDING)]),
        ]
