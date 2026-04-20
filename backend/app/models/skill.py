from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from beanie import Document, Indexed
from pydantic import Field


class EntryType(str, enum.Enum):
    skill = "skill"
    marketplace_ref = "marketplace_ref"


class SkillStatus(str, enum.Enum):
    active = "active"
    deactivated = "deactivated"


class Skill(Document):
    slug: Indexed(str, unique=True)  # type: ignore[valid-type]
    name: str
    repo_url: Indexed(str, unique=True)  # type: ignore[valid-type]
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

    submitter_id: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Denormalized community aggregates
    avg_rating: float = 0.0
    rating_count: int = 0
    flag_count: int = 0

    class Settings:
        name = "skills"
        indexes = [
            [("name", "text"), ("description", "text")],
        ]
