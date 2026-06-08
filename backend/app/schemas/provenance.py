from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ProvenanceNode(BaseModel):
    slug: Optional[str] = None          # None for external (non-catalog) nodes
    name: str
    repo_url: str
    in_catalog: bool
    visibility: Optional[str] = None    # "public" | "internal" — None for external nodes
    submitter_id: Optional[str] = None
    github_stars: Optional[int] = None
    avg_rating: Optional[float] = None
    last_commit_at: Optional[datetime] = None
    status: Optional[str] = None        # "active" | "deactivated" — None for external nodes
    forks: List["ProvenanceNode"] = []
    forks_truncated: bool = False
    total_fork_count: int = 0


class ProvenanceTree(BaseModel):
    empty: bool = False
    subject: Optional[ProvenanceNode] = None
    upstream: List[ProvenanceNode] = []
    supersession: List[ProvenanceNode] = []
