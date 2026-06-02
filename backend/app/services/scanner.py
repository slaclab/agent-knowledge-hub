"""Source-agnostic scanner abstraction.

Defines the SourceScanner ABC, SourceRef discriminated union, RawScanResult,
SourceScannerRegistry, and SourceRefParser. GitHub is the first concrete
implementation; LocalScanner (Slice 2) and future scanners (GitLab, etc.)
register here without touching any other module.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# SourceRef — discriminated union
# ---------------------------------------------------------------------------

class GitHubRef(BaseModel):
    source_type: Literal["github"] = "github"
    owner: str
    repo: str
    branch: Optional[str] = None
    path: str = "/"


class LocalRef(BaseModel):
    source_type: Literal["local"] = "local"
    path: str  # absolute, resolved filesystem path


SourceRef = Annotated[
    Union[GitHubRef, LocalRef],
    Field(discriminator="source_type"),
]


# ---------------------------------------------------------------------------
# RawScanResult — generic scan output, source-agnostic
# ---------------------------------------------------------------------------

class RawScanResult(BaseModel):
    ref: SourceRef
    repo_meta: Dict[str, Any] = {}       # empty for local skills
    files: Dict[str, str] = {}           # filename → decoded text content
    root_readme: Optional[str] = None
    no_skill_files: bool = False
    snapshotted_files: Dict[str, str] = {}  # persisted for local skills (Slice 2)


# ---------------------------------------------------------------------------
# SourceScanner ABC
# ---------------------------------------------------------------------------

class SourceScanner(ABC):
    @abstractmethod
    async def scan(self, ref: SourceRef, **kwargs: Any) -> RawScanResult: ...

    @abstractmethod
    async def discover(
        self, ref: SourceRef, **kwargs: Any
    ) -> tuple[List[RawScanResult], bool, bool]: ...


# ---------------------------------------------------------------------------
# SourceScannerRegistry
# ---------------------------------------------------------------------------

class SourceScannerRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, SourceScanner] = {}

    def register(self, source_type: str, scanner: SourceScanner) -> None:
        self._registry[source_type] = scanner

    def get(self, source_type: str) -> SourceScanner:
        if source_type not in self._registry:
            raise ValueError(
                f"No scanner registered for source_type={source_type!r}. "
                f"Available: {sorted(self._registry)}"
            )
        return self._registry[source_type]


scanner_registry = SourceScannerRegistry()


# ---------------------------------------------------------------------------
# SourceRefParser — route any input string to the right SourceRef subtype
# ---------------------------------------------------------------------------

class SourceRefParser:
    def parse(self, input: str) -> SourceRef:
        s = input.strip()
        if s.startswith("https://github.com/") or s.startswith("http://github.com/"):
            # Defer to the existing GitHubURLParser in github.py
            from app.services.github import github_url_parser  # noqa: PLC0415
            raw = github_url_parser.parse(s)
            # Return a GitHubRef from scanner.py (same fields)
            return GitHubRef(
                owner=raw.owner,
                repo=raw.repo,
                branch=raw.branch,
                path=raw.path,
            )
        if s.startswith("/") or s.startswith("~") or s.startswith("."):
            resolved = str(Path(s).expanduser().resolve())
            return LocalRef(path=resolved)
        raise ValueError(
            f"Cannot determine source type for input: {input!r}. "
            "Expected a GitHub URL (https://github.com/...) or a local path (/... or ~/... or ./...)"
        )


source_ref_parser = SourceRefParser()
