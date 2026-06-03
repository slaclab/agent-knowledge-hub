from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.skill import EntryType, SkillStatus, VisibilityEnum
from app.services.scanner import FileManifestEntry


_GITHUB_URL_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+$")


class LabelOut(BaseModel):
    name: str
    usage_count: int
    applied_by_me: bool = False


class AdminLabelOut(BaseModel):
    id: str
    name: str
    usage_count: int


class SkillCreate(BaseModel):
    repo_url: str
    skill_path: str = "/"
    name: Optional[str] = None
    description: Optional[str] = None
    compatible_platforms: List[str] = []
    keywords: List[str] = []  # deprecated: converted to labels on create
    license: Optional[str] = None
    version: Optional[str] = None
    uses_agent_gateway: bool = False
    entry_type: EntryType = EntryType.skill
    # local submission fields (source_type='local')
    source_type: str = "github"
    snapshotted_files: Dict[str, str] = Field(default_factory=dict)


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


class RateSkillIn(BaseModel):
    value: int = Field(..., ge=1, le=5)


class RateSkillOut(BaseModel):
    avg_rating: float
    rating_count: int
    my_rating: int


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
    skill_md_raw: Optional[str]
    skill_md_filename: Optional[str]
    readme_raw: Optional[str]
    compatible_platforms: List[str]
    license: Optional[str]
    version: Optional[str]
    github_stars: Optional[int]
    last_commit_at: Optional[datetime]
    readme_fetched_at: Optional[datetime]
    uses_agent_gateway: bool
    visibility: VisibilityEnum
    forked_from_url: Optional[str]
    # plugin.json metadata
    agent_count: int = 0
    agent_names: List[str] = []
    has_mcp_server: bool = False
    has_scripts: bool = False
    plugin_author: Optional[str] = None
    # source tracking
    source_type: str = "github"
    # file manifest
    file_manifest: List[FileManifestEntry] = []
    manifest_truncated: bool = False
    # version pinning (#017)
    pinned_commit_sha: Optional[str] = None
    pinned_ref: Optional[str] = None
    upstream_sha: Optional[str] = None
    update_available: bool = False

    submitter_id: str
    submitted_at: datetime
    updated_at: datetime
    avg_rating: float
    rating_count: int
    flag_count: int
    labels: List[LabelOut] = []
    my_rating: Optional[int] = None
    my_flag: Optional[object] = None  # FlagOut | None — avoid circular import; typed at route layer

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
    # plugin.json metadata
    agent_count: int = 0
    agent_names: List[str] = []
    has_mcp_server: bool = False
    has_scripts: bool = False
    plugin_author: Optional[str] = None
    # source tracking
    source_type: str = "github"
    # version pinning (#017)
    update_available: bool = False

    submitter_id: str
    submitted_at: datetime
    updated_at: datetime
    labels: List[LabelOut] = []

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
    # plugin.json fields
    agent_count: int = 0
    agent_names: List[str] = []
    has_mcp_server: bool = False
    has_scripts: bool = False
    plugin_author: Optional[str] = None
    keywords: List[str] = []
    # file manifest
    file_manifest: List[FileManifestEntry] = []
    manifest_truncated: bool = False


class DiscoverOut(BaseModel):
    skills: List[SkillScanSnapshotOut]
    tree_truncated: bool = False
    capped: bool = False


class SkillSummaryOut(BaseModel):
    """Slim skill record for the /api/skills/summary endpoint (no readme_html)."""
    slug: str
    name: str
    description: Optional[str]
    repo_url: str
    skill_path: str
    entry_type: str
    compatible_platforms: List[str]
    version: Optional[str] = None
    avg_rating: float
    rating_count: int
    labels: List[str] = []

    model_config = {"from_attributes": True}
