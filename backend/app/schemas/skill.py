from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, field_validator

from app.models.skill import EntryType, SkillStatus, VisibilityEnum


_GITHUB_URL_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+$")


class SkillCreate(BaseModel):
    repo_url: str
    skill_path: str = "/"
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
    forked_from_url: Optional[str] = None

    @field_validator("forked_from_url")
    @classmethod
    def validate_forked_from_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        from app.services.github import _normalize_github_url
        normalized = _normalize_github_url(v)
        if normalized and not _GITHUB_URL_RE.match(normalized):
            raise ValueError("forked_from_url must be a https://github.com/<owner>/<repo> URL")
        return normalized


class SkillOut(BaseModel):
    id: str
    slug: str
    name: str
    repo_url: str
    skill_path: str
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
    visibility: VisibilityEnum
    forked_from_url: Optional[str]
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
    visibility: VisibilityEnum
    forked_from_url: Optional[str]
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


class GitHubPreviewOut(BaseModel):
    name: str
    description: Optional[str]
    stars: int
    license: Optional[str]
    last_commit_at: Optional[datetime]
    visibility: VisibilityEnum


class GitHubRefOut(BaseModel):
    owner: str
    repo: str
    branch: Optional[str]
    path: str


class SkillScanSnapshotOut(BaseModel):
    ref: GitHubRefOut
    name: Optional[str]
    description: Optional[str]
    compatible_platforms: List[str]
    version: Optional[str]
    license: Optional[str]
    readme_html: Optional[str]
    stars: int
    last_commit_at: Optional[datetime]
    visibility: VisibilityEnum
    forked_from_url: Optional[str]
    fetched_at: datetime
    no_skill_files: bool
    existing_slug: Optional[str]


class DiscoverOut(BaseModel):
    skills: List[SkillScanSnapshotOut]
    tree_truncated: bool = False
    capped: bool = False
