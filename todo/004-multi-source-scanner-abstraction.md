# TODO #004 — Multi-Source Scanner Abstraction: Local Directories, GitLab, and Beyond

> **Priority:** 🟡 P2 — Medium
> **Status:** 🔍 Reviewed
> **Branch:** —
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** —
> **Depends on:** #002 (GitHubScanner is the first concrete implementation — already shipped)

---

## Problem Statement

The skill scanner (`backend/app/services/github.py`) is tightly coupled to the GitHub API. `GitHubScanner`, `GitHubRef`, and the entire scan/discover pipeline assume GitHub as the only source. The router is named `/api/github-scan`, the ref model carries GitHub-specific fields (`owner`, `repo`, `branch`), and `skill.py` imports `github_scanner` directly by name.

This makes it impossible to register skills from local directories, GitLab repos, or any other source without rewriting the scanning layer. It also prevents the installer skill from submitting a locally-developed skill before it has been pushed to GitHub.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Author runs `/agent-knowledge-hub submit ~/projects/my-skill` | No local submit path exists | Skill files read from disk, metadata auto-extracted, registered with `source_type: "local"` |
| Developer wants to add GitLab support | Must rewrite router, scanner, MetadataExtractor | Implement one `SourceScanner` subclass, register it — nothing else changes |
| Scan endpoint URL | `/api/github-scan` (GitHub-specific name) | `/api/scan` (source-agnostic); old URL aliased |
| `MetadataExtractor` | Accepts only `RawScanResult` with GitHub ref | Accepts `RawScanResult` regardless of source |

---

## Goals

1. Define a `SourceScanner` ABC and `SourceRef` discriminated union so the scan/discover pipeline is source-agnostic
2. Refactor `GitHubScanner` to implement `SourceScanner` with zero behaviour change
3. Implement `LocalScanner` — reads skill files from the local filesystem, no HTTP calls
4. Add `source_type` field to the `Skill` model; store snapshotted file content for local skills
5. Enable `agent-knowledge-hub submit <path>` CLI command using bearer token auth (#016)

## Non-Goals

- Full GitLab implementation (this todo defines the abstraction and `LocalScanner`; GitLab is a future todo)
- Syncing or mirroring skills across sources
- File storage for assets >100KB (only recognised skill files snapshotted; typically <50KB)
- New authentication mechanism — local submit uses the existing bearer JWT auth from #016

---

## Design

### Codebase reality check

From reading the current code:

- `RawScanResult` (line 280 of `github.py`) already has the right generic shape: `files: Dict[str, str]`, `repo_meta: Dict[str, Any]`, `no_skill_files: bool`. The only GitHub-specific field is `ref: GitHubRef` — this needs to become `ref: SourceRef`.
- `MetadataExtractor.extract()` (line 724) is already pure — no I/O, only reads `result.files` and `result.repo_meta`. It will work unchanged once `RawScanResult.ref` is widened.
- `github_scanner` is a module-level singleton imported directly in `skill.py` (line 20) and `github_scan.py` (line 14). These become `scanner_registry.get(ref.source_type)` calls.
- The router `github_scan.py` imports `GitHubRef`, `github_url_parser`, and `github_scanner` by name. It becomes source-agnostic by routing through the registry.

### Abstract interface

New file: `backend/app/services/scanner.py`

```python
from abc import ABC, abstractmethod
from typing import Union
from pydantic import BaseModel

# SourceRef — discriminated union
class GitHubRef(BaseModel):          # moved here from github.py (re-exported for compat)
    source_type: Literal["github"] = "github"
    owner: str
    repo: str
    branch: Optional[str] = None
    path: str = "/"

class LocalRef(BaseModel):
    source_type: Literal["local"] = "local"
    path: str                        # absolute filesystem path

SourceRef = Union[GitHubRef, LocalRef]

# RawScanResult — widened ref field
class RawScanResult(BaseModel):
    ref: SourceRef                   # was GitHubRef
    repo_meta: Dict[str, Any] = {}   # empty for local skills
    files: Dict[str, str] = {}       # filename → decoded text content
    root_readme: Optional[str] = None
    no_skill_files: bool = False
    snapshotted_files: Dict[str, str] = {}  # for local skills: same as files, persisted to DB

# Abstract scanner
class SourceScanner(ABC):
    @abstractmethod
    async def scan(self, ref: SourceRef) -> RawScanResult: ...

    @abstractmethod
    async def discover(self, ref: SourceRef) -> tuple[list[RawScanResult], bool, bool]: ...

# Registry
class SourceScannerRegistry:
    def __init__(self):
        self._registry: dict[str, SourceScanner] = {}

    def register(self, source_type: str, scanner: SourceScanner) -> None:
        self._registry[source_type] = scanner

    def get(self, source_type: str) -> SourceScanner:
        if source_type not in self._registry:
            raise ValueError(f"No scanner registered for source_type={source_type!r}")
        return self._registry[source_type]

scanner_registry = SourceScannerRegistry()
```

### GitHubScanner refactor (Slice 1 — zero behaviour change)

- Add `source_type: Literal["github"] = "github"` to `GitHubRef`
- `GitHubScanner` implements `SourceScanner` (add `ABC` parent, ensure method signatures match)
- `RawScanResult` in `github.py` is replaced by the one from `scanner.py` (re-export for backward compat)
- `github_scanner` registered: `scanner_registry.register("github", github_scanner)`
- All existing tests pass unchanged

### LocalScanner (Slice 2)

New file: `backend/app/services/local.py`

```python
_MAX_FILE_SIZE = 100_000  # 100KB — reject files larger than this
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
_MAX_DISCOVER_DEPTH = 5

class LocalScanner(SourceScanner):
    async def scan(self, ref: LocalRef) -> RawScanResult:
        path = Path(ref.path).resolve()
        if not path.exists() or not path.is_dir():
            raise ScanError(f"Path not found or not a directory: {ref.path}")
        files = {}
        for fname in _SKILL_FILES:
            candidate = path / fname
            resolved = candidate.resolve()
            # SECURITY: containment check — reject symlinks escaping skill root
            if not resolved.is_relative_to(path):
                logger.warning("[LOCAL] path escape blocked: %s -> %s", candidate, resolved)
                continue
            if not resolved.exists() or not resolved.is_file():
                continue
            # SECURITY: size check before read
            if resolved.stat().st_size > _MAX_FILE_SIZE:
                logger.warning("[LOCAL] file too large, skipping: %s (%d bytes)", fname, resolved.stat().st_size)
                continue
            files[fname] = resolved.read_text(encoding="utf-8")
        # Also check .claude-plugin/plugin.json fallback
        if "plugin.json" not in files:
            fallback = (path / ".claude-plugin" / "plugin.json").resolve()
            if fallback.is_relative_to(path) and fallback.exists() and fallback.stat().st_size <= _MAX_FILE_SIZE:
                files["plugin.json"] = fallback.read_text(encoding="utf-8")
        return RawScanResult(
            ref=ref,
            files=files,
            snapshotted_files=files,  # persisted to DB
            no_skill_files=not any(
                f in files for f in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md")
            ),
        )

    async def discover(self, ref: LocalRef) -> tuple[list[RawScanResult], bool, bool]:
        root = Path(ref.path).resolve()
        skill_dirs = []
        # SECURITY: bounded walk with depth limit and directory exclusions (no symlink following)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth > _MAX_DISCOVER_DEPTH:
                dirnames.clear()
                continue
            # Skip non-skill directories
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            if "SKILL.md" in filenames or "skill.md" in filenames:
                resolved = Path(dirpath).resolve()
                if resolved.is_relative_to(root):
                    skill_dirs.append(resolved)
        results = [await self.scan(LocalRef(path=str(d))) for d in skill_dirs[:20]]
        capped = len(skill_dirs) > 20
        return results, False, capped
```

`LocalScanner` registered: `scanner_registry.register("local", local_scanner)`

### SourceRefParser — input routing

```python
class SourceRefParser:
    def parse(self, input: str) -> SourceRef:
        if input.startswith("https://github.com/") or input.startswith("http://github.com/"):
            return github_url_parser.parse(input)   # existing GitHubURLParser
        if input.startswith("/") or input.startswith("~") or input.startswith("."):
            return LocalRef(path=str(Path(input).expanduser().resolve()))
        raise ValueError(f"Cannot determine source type for input: {input!r}")

source_ref_parser = SourceRefParser()
```

### Security constraints

1. **API endpoint MUST reject `LocalRef`:** The `GET /api/scan` endpoint runs on the server — it MUST NOT invoke `LocalScanner` to read from the server's filesystem based on client input. Local skill submission happens exclusively via `POST /api/skills` where the CLI sends pre-read `snapshotted_files` content. The server never reads local disk on behalf of a remote client.

2. **Path containment:** `LocalScanner.scan()` and `discover()` MUST `resolve()` all paths and verify they remain within the original `ref.path` root after symlink resolution. Reject any file whose resolved path escapes the skill directory.

3. **Symlink safety:** `discover()` MUST NOT follow symlinks that resolve outside the root path. Use `candidate.resolve()` and check `resolved.is_relative_to(root_resolved)` before processing.

4. **Per-file size limit:** `_MAX_FILE_SIZE = 100_000` (100KB). Check `candidate.stat().st_size` before `read_text()`. Skip files exceeding the limit with a warning log.

5. **Discover depth and exclusion:** `discover()` MUST skip common non-skill directories (`.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, `build`). Max traversal depth of 5 levels. Use `os.walk()` with depth tracking rather than unbounded `rglob()`.

6. **Content sanitization:** `snapshotted_files` content MUST pass through the same markdown-to-HTML sanitization pipeline as GitHub-sourced content before frontend rendering.

### Router changes

`github_scan.py` → renamed/aliased to `scan.py`:
- `GET /api/scan?url=<input>` — parses input via `source_ref_parser`, resolves scanner from `scanner_registry`
- **SECURITY:** If `source_ref_parser` returns a `LocalRef`, the endpoint MUST return HTTP 422 with detail "Local paths cannot be scanned via the API. Use POST /api/skills with snapshotted_files."
- `GET /api/github-scan` kept as an alias (same handler) for backward compatibility
- No change to `SkillScanSnapshotOut` schema

`skills.py` scan call sites (lines 142–147 and 295–300):
- Replace `github_url_parser.parse(url)` + `github_scanner.scan(ref)` with `source_ref_parser.parse(url)` + `scanner_registry.get(ref.source_type).scan(ref)`

### Skill model change

```python
class Skill(Document):
    source_type: str = "github"              # new — "github" | "local"
    snapshotted_files: Dict[str, str] = {}   # new — populated for local skills; empty for GitHub
```

Both fields are additive/nullable — no migration needed. Existing GitHub skills get `source_type="github"` and `snapshotted_files={}`.

For local skills, `snapshotted_files` holds the recognised skill files at submission time (<50KB total). `refetch()` re-reads from disk (if path still exists) or marks stale.

### Auth for CLI submit

Uses #016 bearer JWT. Token resolution order (first found wins):
1. `AGENT_KNOWLEDGE_HUB_TOKEN` env var (CI/automation use case)
2. `~/.s3df-access-token` file (same as existing `rate` command — written by `s3df login`)
3. `~/.claude/settings.local.json` `agent_knowledge_hub_token` field (legacy fallback)

If none found, print: `No auth token found. Run 's3df login' to authenticate, then try again.`

This unifies the auth UX with the existing `rate` command — scientists who have already run `s3df login` need zero new setup.

### Error handling for `submit <path>`

| Condition | Message |
|---|---|
| Path does not exist | `Path not found: <path>. Check that the directory exists.` |
| Path is a file, not directory | `<path> is a file — expected a directory containing skill files.` |
| No SKILL.md found | `No SKILL.md found in <path>. Run '/agent-knowledge-hub create' to scaffold a skill, or add a SKILL.md file.` |
| SKILL.md missing name | `SKILL.md is missing required frontmatter field: name` |
| Slug already exists | `Skill "<slug>" already exists in the catalog. Use '/agent-knowledge-hub update <slug>' to update it, or choose a different name.` |
| Token missing | `No auth token found. Run 's3df login' to authenticate, then try again.` |
| Token expired/401 | Display `detail` field from API response directly (matches `rate` command pattern) |

### Success confirmation for `submit <path>`

After successful submission, print:
```
Submitted "<name>" to the catalog.
  Slug:    <slug>
  Source:  local (<N> files snapshotted)
  View:    https://agent-knowledge-hub.slac.stanford.edu/skills/<slug>
```

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `backend/app/services/scanner.py` | New | `SourceRef`, `RawScanResult`, `SourceScanner` ABC, `SourceScannerRegistry`, `SourceRefParser` |
| `backend/app/services/github.py` | Modify | `GitHubScanner` implements `SourceScanner`; `GitHubRef` gains `source_type` literal; re-exports `RawScanResult` from `scanner.py` |
| `backend/app/services/local.py` | New | `LocalScanner` — filesystem reads, no HTTP; `snapshotted_files` population |
| `backend/app/routers/scan.py` | New (replaces `github_scan.py`) | Source-agnostic scan/discover endpoint; `/api/github-scan` alias |
| `backend/app/routers/skills.py` | Modify | Two scan call sites use `source_ref_parser` + `scanner_registry` |
| `backend/app/models/skill.py` | Modify | Add `source_type: str`, `snapshotted_files: Dict[str, str]` |
| `backend/app/schemas/skill.py` | Modify | Expose `source_type` in `SkillOut`/`SkillListOut` |
| `skill/SKILL.md` — install flow | Modify | Add `submit <path>` command; read bearer token; call `POST /api/skills` |

---

## ADRs

### ADR-001: `RawScanResult.ref` widened to `SourceRef` union; `GitHubRef` re-exported for backward compat

**Status:** Accepted

**Context:** `RawScanResult` currently carries `ref: GitHubRef`. Widening to `SourceRef = Union[GitHubRef, LocalRef]` is a breaking change for any code that accesses `result.ref.owner` etc.

**Decision:** Move `RawScanResult` and `SourceRef` to `scanner.py`. `github.py` re-exports them for backward compat (`from app.services.scanner import RawScanResult, GitHubRef`). Code that accesses `result.ref.owner` must narrow the type first (`if isinstance(result.ref, GitHubRef)`). Only two such sites exist in the codebase (`github_scan.py` and the `SkillScanSnapshotOut` builder) — both are in the router that is being rewritten anyway.

**Consequences:** Zero breaking changes for external API consumers. Internal type narrowing required at two sites.

---

### ADR-002: `snapshotted_files` embedded in `Skill` document; no separate collection

**Status:** Accepted (user decision 2026-06-02)

**Context:** Local skills have no URL to re-fetch from. File content must be stored somewhere. Three options: embed in `Skill` document, separate blobs collection, GridFS.

**Decision:** Embed `snapshotted_files: Dict[str, str]` directly in the `Skill` document. Only recognised skill files are stored (SKILL.md, CLAUDE.md, AGENTS.md, README.md, plugin.json, package.json, pyproject.toml — capped at 7 files, ~50KB total). MongoDB document limit is 16MB; 50KB is negligible.

**Consequences:** No extra collection or join. `refetch()` for local skills reads from disk rather than the DB snapshot. If the local path moves, refetch fails gracefully and marks the skill stale.

---

### ADR-003: `GitHubScanner` implements `SourceScanner` via duck-typing + ABC, not a forced rewrite

**Status:** Accepted

**Context:** `GitHubScanner` already has the right `scan()` and `discover()` method signatures. Making it formally subclass `SourceScanner` risks breaking the singleton import pattern (`github_scanner = GitHubScanner()`).

**Decision:** Add `SourceScanner` as ABC parent to `GitHubScanner`. Method signatures are already compatible — no body changes needed. The singleton `github_scanner` is registered with `scanner_registry` at module import time. Existing direct imports of `github_scanner` continue to work.

**Consequences:** Slice 1 is a pure refactor with no behaviour change. All existing tests pass unchanged.

---

### ADR-004: `/api/github-scan` kept as a permanent alias, not deprecated

**Status:** Accepted

**Context:** External clients (the installer skill, tests, any direct API users) call `/api/github-scan`. Removing it would break them.

**Decision:** The new `scan.py` router registers both `/api/scan` and `/api/github-scan` pointing at the same handler. The old name is kept permanently — not deprecated. Both accept the same query params.

**Consequences:** No breaking changes. Future sources (local, GitLab) are submitted to `/api/scan`; GitHub clients can use either URL.

---

## Trade-offs

```
Choice: SourceRef as discriminated union (Pydantic) vs plain string + dict
  + Union: type-safe, IDE autocompletion, self-documenting
  - Union: two call sites must narrow the type with isinstance()
  Decision: Discriminated union. Two sites is manageable; type safety is worth it.

Choice: LocalScanner in its own file vs adding to github.py
  + Own file: cleaner separation, github.py stays GitHub-only
  - Own file: one more import to manage
  Decision: Own file (local.py). Matches the pattern: one file per source type.

Choice: Re-read disk on refetch vs store snapshots
  + Re-read disk: always current, no storage cost
  - Re-read disk: fails if user moves or deletes the directory
  Decision: Re-read on refetch; fall back to snapshotted_files if path missing.
  This gives the catalog a "last known good" state even if the local path moves.

Choice: `submit` command in SKILL.md vs a separate CLI binary
  + SKILL.md: already installed, no new dependency
  - SKILL.md: Claude executes it; not suitable for programmatic/CI use
  Decision: SKILL.md for now. Separate binary is a future todo once usage patterns are known.
```

---

## Delivery Slices

**Slice 1 — Abstraction refactor (no behaviour change)**
- Create `backend/app/services/scanner.py`: `SourceRef`, `RawScanResult`, `SourceScanner` ABC, `SourceScannerRegistry`, `SourceRefParser`
- `GitHubRef` gains `source_type: Literal["github"]`; `RawScanResult` ref widens to `SourceRef`
- `GitHubScanner` subclasses `SourceScanner`; registered with `scanner_registry`
- Router `scan.py` replaces `github_scan.py`; `/api/github-scan` aliased
- `skills.py` scan call sites use `source_ref_parser` + `scanner_registry`
- **All existing tests pass unchanged. Zero behaviour change.**

**Slice 2 — LocalScanner + CLI submit**
- `backend/app/services/local.py`: `LocalRef`, `LocalScanner`; registered with `scanner_registry`
- `Skill` model: `source_type`, `snapshotted_files` fields
- `SkillOut`/`SkillListOut`: expose `source_type`
- `POST /api/skills` accepts `source_type: "local"` + snapshotted content
- Installer skill: `submit <path>` command, reads `AGENT_KNOWLEDGE_HUB_TOKEN`, calls API
- Unit tests: `LocalScanner` with tmpdir fixtures; refetch-from-disk path; missing-path fallback

**Slice 3 — GitLab (separate future todo)**
- Implement `GitLabScanner(SourceScanner)` in `gitlab.py`
- Register in `scanner_registry`
- Zero changes to router, MetadataExtractor, or model

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Abstraction leaks GitHub-specific concepts into `RawScanResult` | Low | High | `repo_meta` is already typed as `Dict[str, Any]` (empty for local) — no GitHub-specific fields in the contract |
| Local file snapshots grow large for repos with big READMEs | Low | Low | Cap at recognised `_SKILL_FILES` only; skip files >100KB with a warning |
| `isinstance(ref, GitHubRef)` type narrowing missed at a call site | Medium | Low | mypy/pyright will flag it; review at Slice 1 PR |
| Auth token not available when user runs `submit` | Medium | Low | Token fallback chain reads `AGENT_KNOWLEDGE_HUB_TOKEN` → `~/.s3df-access-token` → settings.local.json; most users already have `~/.s3df-access-token` from `s3df login`; clear setup message if all sources absent |
| Local path moves between submit and refetch | Medium | Low | Refetch falls back to `snapshotted_files`; marks skill `stale` in catalog |
| Slice 1 "no behaviour change" claim is wrong | Low | High | Run full test suite before merging Slice 1; gate on green CI |
| **Arbitrary file read via API** — `GET /api/scan` with local path reads server filesystem | High | Critical | API endpoint rejects `LocalRef`; local submissions only via `POST /api/skills` with pre-read content |
| **Symlink traversal** — `rglob()` follows symlinks outside skill directory | Medium | High | Resolve + containment check on every path; reject symlinks escaping root |
| **Size bomb** — large file at valid skill path causes OOM | Medium | High | `_MAX_FILE_SIZE = 100_000` enforced before `read_text()` |

---

## Implementation Checklist

- [ ] `scanner.py`: `SourceRef`, `LocalRef`, `GitHubRef` (with `source_type` literal), `RawScanResult`, `SourceScanner` ABC, `SourceScannerRegistry`, `SourceRefParser`
- [ ] `github.py`: `GitHubScanner` subclasses `SourceScanner`; re-exports `RawScanResult`, `SourceRef`, `GitHubRef` from `scanner.py`; registers with `scanner_registry`
- [ ] `scan.py`: replaces `github_scan.py`; both `/api/scan` and `/api/github-scan` registered
- [ ] `skills.py`: two scan call sites updated to use `source_ref_parser` + `scanner_registry`
- [ ] All existing tests pass (CI gate for Slice 1)
- [ ] `local.py`: `LocalScanner.scan()`, `LocalScanner.discover()`, `snapshotted_files` population
- [ ] `local_scanner` registered with `scanner_registry`
- [ ] `Skill` model: `source_type: str = "github"`, `snapshotted_files: Dict[str, str] = {}`
- [ ] `SkillOut`/`SkillListOut`: `source_type` exposed
- [ ] `POST /api/skills` handles `source_type: "local"` + snapshot content
- [ ] `LocalScanner` unit tests: happy path, missing path, no skill files, `.claude-plugin/` fallback
- [ ] Installer skill: `submit <path>` command with token fallback chain (`AGENT_KNOWLEDGE_HUB_TOKEN` > `~/.s3df-access-token` > settings.local.json)
- [ ] Installer skill: `submit <path>` error messages for all failure modes (path missing, no SKILL.md, missing name, slug taken, token missing/expired)
- [ ] Installer skill: `submit <path>` success confirmation (name, slug, file count, catalog URL)
- [ ] Frontend: skill detail page conditionally renders Repository section only for `source_type === "github"`; shows "Local submission" badge for local skills
- [ ] Frontend: skill-card handles missing `repo_url` gracefully for local skills
- [ ] `skill/SKILL.md`: update `create` sub-command closing guidance to mention `/agent-knowledge-hub submit .` as the primary local path
- [ ] Smoke test: `submit ~/projects/test-skill` end-to-end
- [ ] **SECURITY:** `/api/scan` endpoint rejects `LocalRef` with HTTP 422 — server never reads local disk for remote clients
- [ ] **SECURITY:** `LocalScanner.scan()` resolves all paths and validates containment within `ref.path` root
- [ ] **SECURITY:** `LocalScanner.discover()` skips symlinks resolving outside root; skips `.git`, `node_modules`, `.venv`; max depth 5
- [ ] **SECURITY:** Per-file size cap (`_MAX_FILE_SIZE = 100_000`) enforced before `read_text()` in `LocalScanner`
- [ ] **SECURITY:** `snapshotted_files` content sanitized through same pipeline as GitHub content before frontend rendering
- [ ] **SECURITY:** Installer skill warns if `~/.claude/settings.local.json` is world-readable (file permissions check)
- [ ] **SECURITY:** Unit tests for path traversal attempts (`../../../etc/passwd`), symlink escape, oversized file rejection

---

## Test Plan

### Unit tests
- `SourceRefParser.parse()`: GitHub URL → `GitHubRef`; local absolute path → `LocalRef`; relative path → `LocalRef` (resolved); unknown input → `ValueError`
- `LocalScanner.scan()`: dir with SKILL.md; dir with only README.md; dir with `.claude-plugin/plugin.json`; non-existent path; path is a file not a dir
- `LocalScanner.discover()`: flat single-skill repo; nested multi-skill repo; >20 skill dirs (capped)
- `SourceScannerRegistry`: register + get; unknown source_type raises ValueError

### Integration tests
- Slice 1: existing `/api/github-scan` tests pass unchanged
- Slice 2: `POST /api/skills` with `source_type="local"` and snapshotted files → skill created with correct `source_type`
- Slice 2: refetch of local skill re-reads from disk; missing path falls back to snapshot

### Smoke tests (manual before DoD)

| # | Scenario | Expected |
|---|---|---|
| S1 | `GET /api/github-scan?url=<github-url>` | Identical response to pre-refactor |
| S2 | `GET /api/scan?url=<github-url>` | Same as S1 |
| S3 | `/agent-knowledge-hub submit ~/projects/my-skill` | Skill registered with `source_type: "local"`, metadata extracted from local files |
| S4 | Submit skill, move directory, trigger refetch | Refetch falls back to `snapshotted_files`, marks skill stale |
| S5 | Add GitLabScanner stub, register it | No changes to router or MetadataExtractor needed |

### Amendment — eng-review (round 1)

**Added regression tests (Slice 1 baseline):**
- `GitHubScanner.scan()`: mock GitHub Contents + Repo API; verify `RawScanResult` contains expected `files`, `ref`, `repo_meta`; baseline for proving Slice 1 refactor preserves behavior
- `GitHubScanner.discover()`: mock tree API with multiple skill dirs; verify discovered `RawScanResult` list and `capped` flag

**Added safety tests (Slice 2):**
- `LocalScanner.scan()`: file >100KB is skipped with warning (not read into memory)
- `LocalScanner.discover()`: symlink pointing outside root dir is not followed
- `LocalScanner.discover()`: traversal halts after 1000 candidates (guards against flat repos with massive SKILL.md sprawl)
- Refetch path: `source_type="local"` skill with deleted path falls back to `snapshotted_files` and records `last_refetch_error`

**Added API schema tests:**
- `POST /api/skills` with `source_type="local"` stores `repo_url` as `local:///absolute/path`; unique index rejects duplicate local path submissions with 409
- `GET /api/scan?url=/path/to/skill` returns `SkillScanSnapshotOut` with `ref.source_type="local"`

---

## Definition of Done

- [ ] `SourceScanner` ABC, `SourceRef`, `RawScanResult`, `SourceScannerRegistry`, `SourceRefParser` defined in `scanner.py`
- [ ] `GitHubScanner` implements `SourceScanner` — all existing tests pass unchanged
- [ ] `LocalScanner` implemented and unit tested
- [ ] `source_type` and `snapshotted_files` fields on `Skill` model
- [ ] `/api/scan` endpoint resolves correct scanner from registry; `/api/github-scan` aliased
- [ ] `agent-knowledge-hub submit <path>` CLI command functional with bearer token auth
- [ ] `MetadataExtractor` has no imports from `github.py` — import chain goes `github.py` → `scanner.py`, not the reverse
- [ ] Adding a new scanner requires only: implement `SourceScanner`, call `scanner_registry.register()`
- [ ] All checklist items complete

---

## Amendment — doc-review (round 1)

> Added by board doc-review, 2026-06-02. Six documentation gaps identified.

Add to **Implementation Checklist**:

- [ ] Update `docs/skill-file-discovery.md`: add `SourceRefParser` routing step, `LocalScanner` section, document `snapshotted_files` field, scope GitHub-specific sections as "GitHubScanner" behaviour
- [ ] Update `skill/SKILL.md`: full `submit <path>` sub-command section — procedure steps, `AGENT_KNOWLEDGE_HUB_TOKEN` env var setup, error handling, coexistence with existing web-based `submit` (no args)
- [ ] Add `CHANGELOG.md` "Unreleased" entry for multi-source scanner abstraction (new endpoint, new API field, new CLI command, model change)
- [ ] File inline ADRs to `docs/adr/` per project convention: `adr-u11-source-ref-discriminated-union.md`, `adr-u12-snapshotted-files-embedded.md`, `adr-u13-github-scanner-abc-subclass.md`, `adr-u14-github-scan-permanent-alias.md`
- [ ] Update `docs/runbooks/internal-api-secret.md` endpoint validation table: add `/api/scan` alongside `/api/github-scan`
- [ ] Update `README.md` "Share what you've built" section: document both submission paths (GitHub web flow via `submit` and local directory submission via `submit <path>`)

**Sequencing recommendation:** ADRs and `docs/skill-file-discovery.md` should ship with Slice 1 (they document the abstraction). `SKILL.md` command docs, `README.md`, `CHANGELOG.md`, and runbook update ship with Slice 2 (they document user-facing features).

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-02
**Rounds:** 2

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | ✅ PASS | Yes | Pydantic discriminator syntax sound; MetadataExtractor coupling gated by DoD; path traversal multi-layer defense confirmed adequate |
| codebase-arch-review | ✅ PASS | Yes | 5+ call sites (not 2) now acknowledged; MetadataExtractor widening gated by DoD; per-file size check before read_text() confirmed |
| codebase-eng-review | ✅ PASS | No | File size cap, symlink traversal, stale-marking, and SkillScanSnapshotOut gaps addressed by other reviewers' amendments |
| doc-review | ✅ PASS | Yes | 6 doc gaps added to checklist: skill-file-discovery.md, SKILL.md submit command, CHANGELOG, 4 ADRs, runbook, README |
| security-review | ✅ PASS | Yes | API rejects LocalRef (422) eliminating arbitrary file read; os.walk(followlinks=False) + depth cap; content sanitization pipeline |
| codebase-ux-review | ✅ PASS | Yes | Token fallback chain (AGENT_KNOWLEDGE_HUB_TOKEN → ~/.s3df-access-token → settings.local.json); error message table; conditional GitHub UI |

**Accepted warnings:** ADR-001 inaccurately says "two sites" (actual 5+) — minor precision issue, does not affect implementation
**Unresolved decisions:** none

<details>
<summary>research-handbook — Round 2 (PASS)</summary>

All five Round 1 issues resolved. Pydantic v2 auto-detects Literal discriminators. MetadataExtractor reads files/repo_meta only; name enforced via frontmatter. Path traversal mitigated with multi-layer defense. Size worst-case 700KB (0.04% of MongoDB 16MB limit).

</details>

<details>
<summary>codebase-arch-review — Round 2 (PASS)</summary>

All blocking issues resolved or gated by DoD. Remaining minor gaps (ADR-001 site count, no explicit MetadataExtractor checklist entry) are implementation-detail precision issues, not architectural problems. Architecture is sound: discriminated union, registry pattern, ABC hierarchy, security constraints, delivery sequencing all correct.

</details>

<details>
<summary>codebase-eng-review — Round 1 (PASS WITH AMENDMENTS)</summary>

Six issues found: file size cap (resolved by security review), symlink traversal (resolved), stale-marking checklist item (resolved), SkillScanSnapshotOut source_type (resolved), existing tests don't cover GitHubScanner.scan()/discover() — "all tests pass" claim vacuously true but unhelpful, concurrent local submit is covered by existing DuplicateSkillError handling. Test plan amendments added.

</details>

<details>
<summary>doc-review — Round 2 (PASS)</summary>

All six documentation gaps addressed with explicit, actionable checklist items. Sequencing correct: ADRs and skill-file-discovery.md with Slice 1; user-facing docs with Slice 2.

</details>

<details>
<summary>security-review — Round 2 (PASS)</summary>

All six security issues resolved with technically sound mitigations. Critical arbitrary-file-read eliminated architecturally (API rejects LocalRef). Path containment uses resolve() + is_relative_to(). Size caps enforced before I/O. rglob() replaced with bounded os.walk(followlinks=False, depth=5). Content sanitization reuses existing pipeline.

</details>

<details>
<summary>codebase-ux-review — Round 2 (PASS)</summary>

All six UX issues resolved. Token fallback chain unified with s3df login — zero new setup for existing users. Full error message table (7 conditions). Frontend conditionally renders Repository section for source_type=github only. Both submit paths documented (web vs local). Success confirmation specifies name, slug, file count, catalog URL.

</details>

---

## Relationship to Other Tasks

- **#002 (Skill registration UX):** #002 built `GitHubScanner` as the first concrete scanner. This todo extracts the abstraction that makes it extensible.
- **#016 (Bearer JWT auth):** The `submit <path>` CLI command uses #016's bearer token mechanism for API authentication.
- **#022 (git clone installer):** Both touch `github.py` and the installer skill. Coordinate to avoid merge conflicts; #004 Slice 1 should land first as it's a pure refactor.
- **#024 (AGENTS.md scanner):** Adds `AGENTS.md` to `_SKILL_FILES`. Should be applied to `scanner.py`'s constant after Slice 1 lands.
- **#026 (Package-embedded skills):** Extends `discover()` to detect `.agents/skills/`. The abstraction from #004 makes this a `GitHubScanner`-only concern — no leakage into the base interface.
- **#004 → GitLab (future):** Once Slice 1 and 2 are shipped, adding `GitLabScanner` requires only a new file + `registry.register()` call.
