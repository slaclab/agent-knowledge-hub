from __future__ import annotations

import enum
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

from beanie import Document, Indexed
from pymongo import IndexModel, ASCENDING, DESCENDING
from pydantic import Field, field_validator

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

from app.services.scanner import FileManifestEntry  # noqa: E402 — scanner is a leaf module


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

    skill_md_raw: Optional[str] = None
    skill_md_filename: Optional[str] = None
    readme_raw: Optional[str] = None

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

    # plugin.json metadata
    agent_count: int = 0
    agent_names: List[str] = Field(default_factory=list)
    has_mcp_server: bool = False
    has_scripts: bool = False
    plugin_author: Optional[str] = None

    # source tracking
    source_type: str = "github"                           # "github" | "local"
    snapshotted_files: Dict[str, str] = Field(default_factory=dict)  # populated for local skills

    # file manifest
    file_manifest: List[FileManifestEntry] = Field(default_factory=list)
    manifest_truncated: bool = False

    # version pinning (#017)
    pinned_commit_sha: Optional[str] = None   # SHA pinned for installs; set at create + pin
    pinned_ref: Optional[str] = None           # tag name at pinned_commit_sha, display only
    upstream_sha: Optional[str] = None         # latest HEAD; updated on refetch

    @property
    def update_available(self) -> bool:
        return (
            self.upstream_sha is not None
            and self.pinned_commit_sha is not None
            and self.upstream_sha != self.pinned_commit_sha
        )

    @field_validator("pinned_commit_sha", "upstream_sha", mode="before")
    @classmethod
    def validate_sha(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _SHA_RE.match(v):
            raise ValueError("Must be a 40-character lowercase hex SHA-1")
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
            IndexModel([("submitter_id", ASCENDING)], name="submitter_id"),
            IndexModel([("compatible_platforms", ASCENDING)], sparse=True, name="compatible_platforms_multikey"),
            # Compound sort indexes for catalog list — cover skip() for pages 1–10 and keyset cursor queries
            IndexModel([("status", ASCENDING), ("submitted_at", DESCENDING), ("_id", DESCENDING)], name="sort_newest"),
            IndexModel([("status", ASCENDING), ("github_stars", DESCENDING), ("submitted_at", DESCENDING)], name="sort_most_stars"),
            IndexModel([("status", ASCENDING), ("avg_rating", DESCENDING), ("submitted_at", DESCENDING)], name="sort_highest_rated"),
            IndexModel([("status", ASCENDING), ("rating_count", DESCENDING), ("submitted_at", DESCENDING)], name="sort_most_rated"),
        ]
