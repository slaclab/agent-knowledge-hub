"""LocalScanner — reads skill files from the local filesystem.

Security constraints (per board review):
- API endpoint MUST reject LocalRef (HTTP 422); only the CLI submit path reaches this scanner
- Every file path resolved and checked with is_relative_to() before reading
- Symlinks: files with resolved path outside the skill dir are skipped
- os.walk with followlinks=False prevents directory symlink traversal
- File size capped at _MAX_FILE_SIZE before read_text()
- Directory depth capped at _MAX_DISCOVER_DEPTH
- _SKIP_DIRS exclusion set prevents traversal of common noise directories
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, List

from app.services.scanner import (
    LocalRef,
    RawScanResult,
    SourceRef,
    SourceScanner,
    scanner_registry,
)

logger = logging.getLogger(__name__)

_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md", "README.md", "package.json", "pyproject.toml", "plugin.json"}
_MAX_FILE_SIZE = 100_000        # 100 KB per file
_MAX_DISCOVER_DEPTH = 5         # directory levels below the root
_SKILL_MARKERS = {"SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md"}
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".tox"}


class ScanError(Exception):
    pass


class LocalScanner(SourceScanner):

    async def scan(self, ref: SourceRef, **kwargs: Any) -> RawScanResult:
        assert isinstance(ref, LocalRef), f"LocalScanner requires LocalRef, got {type(ref)}"
        root = Path(ref.path)
        if not root.exists() or not root.is_dir():
            raise ScanError(f"Path not found or not a directory: {ref.path}")

        files: dict[str, str] = {}

        for fname in _SKILL_FILES:
            candidate = root / fname
            content = self._safe_read(candidate, root)
            if content is not None:
                files[fname] = content

        # .claude-plugin/plugin.json fallback
        if "plugin.json" not in files:
            fallback = root / ".claude-plugin" / "plugin.json"
            content = self._safe_read(fallback, root)
            if content is not None:
                files["plugin.json"] = content

        no_skill_files = not any(f in files for f in _SKILL_MARKERS)
        return RawScanResult(
            ref=ref,
            files=files,
            snapshotted_files=files,
            no_skill_files=no_skill_files,
        )

    async def discover(self, ref: SourceRef, **kwargs: Any) -> tuple[List[RawScanResult], bool, bool]:
        assert isinstance(ref, LocalRef), f"LocalScanner requires LocalRef, got {type(ref)}"
        root = Path(ref.path).resolve()
        skill_dirs: list[Path] = []

        for dirpath, dirnames, filenames in os.walk(str(root), followlinks=False):
            current = Path(dirpath)
            # Depth check
            try:
                depth = len(current.relative_to(root).parts)
            except ValueError:
                continue
            if depth > _MAX_DISCOVER_DEPTH:
                dirnames.clear()
                continue

            # Skip noise directories in-place (mutate dirnames to prevent descent)
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

            # Symlink containment: skip if dirpath somehow escapes root
            try:
                current.resolve().relative_to(root)
            except ValueError:
                logger.warning("[LOCAL] discover: path escaped root, skipping: %s", dirpath)
                continue

            if any(f in _SKILL_MARKERS for f in filenames):
                skill_dirs.append(current)

        capped = len(skill_dirs) > 20
        dirs_to_scan = skill_dirs[:20]
        results = []
        for d in dirs_to_scan:
            try:
                result = await self.scan(LocalRef(path=str(d)))
                results.append(result)
            except ScanError as e:
                logger.warning("[LOCAL] discover: scan failed for %s: %s", d, e)

        return results, False, capped

    def _safe_read(self, path: Path, root: Path) -> str | None:
        """Read a file only if it exists, is within root, is not a dir-symlink escape, and is within size limit."""
        if not path.exists():
            return None
        try:
            resolved = path.resolve()
            resolved.relative_to(root.resolve())  # raises ValueError if outside root
        except ValueError:
            logger.warning("[LOCAL] path escapes root, skipping: %s", path)
            return None
        try:
            size = resolved.stat().st_size
        except OSError:
            return None
        if size > _MAX_FILE_SIZE:
            logger.warning("[LOCAL] file too large (%d bytes), skipping: %s", size, path)
            return None
        try:
            return resolved.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("[LOCAL] read failed for %s: %s", path, e)
            return None


local_scanner = LocalScanner()
scanner_registry.register("local", local_scanner)
