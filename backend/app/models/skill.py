from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, Indexed
from pymongo import IndexModel, ASCENDING, DESCENDING
from pydantic import Field, field_validator


class EntryType(str, enum.Enum):
    skill = "skill"
    marketplace_ref = "marketplace_ref"


class SkillStatus(str, enum.Enum):
    active = "active"
    deactivated = "deactivated"


class VisibilityEnum(str, enum.Enum):
    public = "public"
    internal = "internal"   # fetched via GitHub App (slaclab private)
    private = "private"     # manually submitted, no fetch possible


class Skill(Document):
    slug: Indexed(str, unique=True)  # type: ignore[valid-type]
    name: str
    repo_url: str
    entry_type: EntryType = EntryType.skill
    status: SkillStatus = SkillStatus.active
    deactivation_reason: Optional[str] = None
    superseded_by_slug: Optional[str] = None

    description: Optional[str] = None
    readme_html: Optional[str] = None
    compatible_platforms: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    version: Optional[str] = None
    github_stars: Optional[int] = None
    last_commit_at: Optional[datetime] = None
    readme_fetched_at: Optional[datetime] = None
    uses_agent_gateway: bool = False

    visibility: VisibilityEnum = VisibilityEnum.public
    forked_from_url: Optional[str] = None
    skill_path: str = "/"

    @field_validator("skill_path")
    @classmethod
    def validate_skill_path(cls, v: str) -> str:
        if not v.startswith("/"):
            v = "/" + v
        parts = v.strip("/").split("/") if v.strip("/") else []
        if any(p == ".." for p in parts):
            raise ValueError("skill_path must not contain '..' components")
        if len(v) > 500:
            raise ValueError("skill_path must be <= 500 characters")
        return v

    submitter_id: str
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Denormalized community aggregates
    avg_rating: float = 0.0
    rating_count: int = 0
    flag_count: int = 0

    class Settings:
        name = "skills"
        indexes = [
            [("name", "text"), ("description", "text")],
            IndexModel([("forked_from_url", ASCENDING)], sparse=True, name="forked_from_url_sparse"),
            IndexModel([("visibility", ASCENDING), ("submitted_at", DESCENDING)], name="visibility_submitted_at"),
            IndexModel([("repo_url", ASCENDING), ("skill_path", ASCENDING)], unique=True, name="repo_url_skill_path_unique"),
        ]
