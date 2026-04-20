from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, field_validator

from app.models.skill import EntryType, SkillStatus


class SkillCreate(BaseModel):
    repo_url: str
    name: Optional[str] = None
    description: Optional[str] = None
    compatible_platforms: List[str] = []
    license: Optional[str] = None
    version: Optional[str] = None
    uses_agent_gateway: bool = False
    entry_type: EntryType = EntryType.skill


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    compatible_platforms: Optional[List[str]] = None
    license: Optional[str] = None
    version: Optional[str] = None
    uses_agent_gateway: Optional[bool] = None
    superseded_by_slug: Optional[str] = None
    changelog_note: Optional[str] = None


class SkillOut(BaseModel):
    id: str
    slug: str
    name: str
    repo_url: str
    entry_type: EntryType
    status: SkillStatus
    deactivation_reason: Optional[str]
    superseded_by_slug: Optional[str]
    description: Optional[str]
    readme_html: Optional[str]
    compatible_platforms: List[str]
    license: Optional[str]
    version: Optional[str]
    github_stars: Optional[int]
    last_commit_at: Optional[datetime]
    readme_fetched_at: Optional[datetime]
    uses_agent_gateway: bool
    submitter_id: str
    submitted_at: datetime
    updated_at: datetime
    avg_rating: float
    rating_count: int
    flag_count: int

    model_config = {"from_attributes": True}


class SkillListOut(BaseModel):
    id: str
    slug: str
    name: str
    entry_type: EntryType
    status: SkillStatus
    description: Optional[str]
    compatible_platforms: List[str]
    github_stars: Optional[int]
    avg_rating: float
    rating_count: int
    flag_count: int
    submitter_id: str
    submitted_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedSkills(BaseModel):
    items: List[SkillListOut]
    total: int
    page: int
    page_size: int


class RevisionOut(BaseModel):
    revision_number: int
    actor_id: str
    action: str
    changelog_note: Optional[str]
    created_at: datetime
    snapshot: dict

    model_config = {"from_attributes": True}
