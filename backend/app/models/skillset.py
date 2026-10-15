from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List

from beanie import Document
from pydantic import BaseModel, Field, field_validator
from pymongo import ASCENDING, IndexModel


_SKILLSET_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SkillsetMember(BaseModel):
    skill_id: str  # stringified ObjectId, same convention as SkillLabel.skill_id
    added_by: str
    added_at: datetime = Field(default_factory=_now)


class Skillset(Document):
    slug: str
    name: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)
    created_by: str
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    # Stored order is the display order and the install order.
    members: List[SkillsetMember] = Field(default_factory=list)
    # Incremented by every membership write; reorder refuses a stale value.
    version: int = 0

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not v or len(v) > 100 or not _SKILLSET_SLUG_RE.match(v):
            raise ValueError(
                "Skillset slug must be 1-100 lowercase letters, digits, and hyphens, "
                "and must not start or end with a hyphen"
            )
        return v

    class Settings:
        name = "skillsets"
        indexes = [
            IndexModel([("slug", ASCENDING)], unique=True),
            IndexModel([("created_by", ASCENDING)]),
            IndexModel([("members.skill_id", ASCENDING)]),
        ]
