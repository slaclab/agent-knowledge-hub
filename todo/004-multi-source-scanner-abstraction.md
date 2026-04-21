# 004 — Multi-Source Scanner Abstraction: Local Directories, GitLab, and Beyond

**Status:** ⬜ Open
**Depends on:** #002 (GitHubScanner is the first concrete implementation of the source abstraction)

---

## Problem & Goal

**Problem:** The skill scanner (introduced in #002) is tightly coupled to GitHub. The `GitHubScanner`, `GitHubURLParser`, and `GitHubFetcher` all assume a GitHub API as the source of truth. This makes it impossible to register skills from local directories, GitLab repos, or any other VCS without rewriting the scanning layer.

**Goal:** Introduce a `SourceScanner` abstraction so that the scan endpoint, metadata extractor, and install flow are source-agnostic. GitHub becomes one concrete implementation; local directory and GitLab are future concrete implementations. The catalog UI, API contract, and `MetadataExtractor` remain unchanged.

**Success metric:**
- A skill in a local directory can be submitted via CLI with the same metadata auto-population as a GitHub skill
- Adding a new source type (e.g. GitLab) requires implementing one class and registering it — no changes to the API layer or MetadataExtractor
- Existing GitHub submissions are unaffected

**Out of scope:**
- Full GitLab implementation (this todo defines the abstraction; a separate todo implements GitLab)
- Syncing/mirroring skills across sources
- Per-user auth tokens for VCS sources (scoped to a future auth todo)

**Constraints:**
- #002 must ship first — the abstraction refactors what #002 builds
- Local directory source is only submittable via CLI (the web form can't access the user's filesystem)
- Snapshotted file content must be stored for local skills (no URL to re-fetch from)

---

## User Stories

1. As a skill author, I want to submit a skill from a local directory via `agent-knowledge-hub submit /path/to/skill`, so I can register skills I haven't pushed to GitHub yet.
2. As a skill author, I want metadata (name, description, platforms) auto-extracted from local `skill.md`/`CLAUDE.md`/`README.md` files, so submission is as fast as the GitHub flow.
3. As a skill author, I want the catalog to show "Local" as the source on my skill card, so consumers know there is no public repo to clone.
4. As a developer adding GitLab support, I want to implement a single `SourceScanner` subclass and register it, so I don't have to touch the API layer or MetadataExtractor.
5. As a platform engineer, I want the source type to be stored on each skill record, so the install flow knows which fetcher to use.
6. As a consumer, I want `install <slug>` to work for GitHub skills exactly as before, regardless of the abstraction refactor.

---

## Requirements

### Functional

- FR-S1: Introduce a `SourceScanner` abstract base class with a single async method: `scan(ref: SourceRef) → RawScanResult`. `SourceRef` is a discriminated union: `GitHubRef | LocalRef | GitLabRef`.
- FR-S2: `GitHubScanner` becomes a concrete implementation of `SourceScanner`. No behaviour change.
- FR-S3: `LocalScanner` is a new concrete implementation of `SourceScanner`. It reads files directly from the filesystem at `ref.path`. No HTTP calls. Returns the same `RawScanResult` shape.
- FR-S4: A `SourceScannerRegistry` maps source type strings (`"github"`, `"local"`, `"gitlab"`) to scanner implementations. The scan endpoint resolves the correct scanner from the URL/path format.
- FR-S5: Skill model adds `source_type: str` (default `"github"`). Existing skills are `"github"`.
- FR-S6: For `source_type: "local"`, file content is snapshotted into the catalog at submission time (stored in the Skill document or a linked blob). The skill has no re-fetchable URL.
- FR-S7: `GET /api/github-scan` is renamed or aliased to `GET /api/scan` to be source-agnostic. Old endpoint kept as alias for backward compatibility.
- FR-S8: The CLI `agent-knowledge-hub submit <path>` accepts a local filesystem path and calls `POST /api/skills` with `source_type: "local"` and the snapshotted file content.
- FR-S9: `install <slug>` for local skills copies snapshotted files from the catalog to `~/.claude/skills/<slug>/` (no GitHub API call needed).

### Non-Functional

- NFR-S1: Adding a new source type requires zero changes to `MetadataExtractor`, the API router, or the frontend form.
- NFR-S2: The abstraction adds no latency to the existing GitHub scan path.

### Acceptance Criteria

- AC-S1: Given `agent-knowledge-hub submit ~/projects/my-skill`, when run, name/description/platforms are extracted from local files and the skill is registered with `source_type: "local"`.
- AC-S2: Given an existing GitHub skill, `install <slug>` continues to work unchanged.
- AC-S3: Given a `LocalScanner` implementation, all existing `GitHubScanner` unit tests still pass with no changes to `MetadataExtractor` tests.

---

## Architecture

### Abstraction Layers

```
GET /api/scan?url=<url>   (or CLI: submit <path>)
  │
  ▼
SourceRef = SourceRefParser.parse(input)
  │   "https://github.com/..."  → GitHubRef
  │   "/home/user/my-skill"     → LocalRef
  │   "https://gitlab.com/..."  → GitLabRef (future)
  │
  ▼
scanner = SourceScannerRegistry.get(ref.source_type)
  │   "github" → GitHubScanner
  │   "local"  → LocalScanner
  │   "gitlab" → GitLabScanner (future)
  │
  ▼
RawScanResult = await scanner.scan(ref)
  │
  ▼
SkillSnapshot = MetadataExtractor.extract(result)   ← unchanged
```

### Abstract Interface

```python
class SourceRef(BaseModel):
    source_type: str   # "github" | "local" | "gitlab"

class RawScanResult(BaseModel):
    files: dict[str, str]    # filename → decoded content
    repo_meta: dict          # stars, license, last_commit_at, etc. (empty for local)
    skill_path: str          # path within source

class SourceScanner(ABC):
    @abstractmethod
    async def scan(self, ref: SourceRef) → RawScanResult: ...

    @abstractmethod
    async def discover(self, ref: SourceRef) → list[RawScanResult]: ...
```

### Data Model Addition

```python
class Skill(Document):
    source_type: str = "github"   # new — "github" | "local" | "gitlab"
    # repo_url remains; for local skills it is null or a local path
```

### Modules

**SourceRef + SourceRefParser (new, `backend/app/services/scanner.py`)**
- Responsibility: Parse any input (URL or path) into a typed `SourceRef`
- Interface: `parse(input: str) → SourceRef`
- Testable: Yes — pure parsing

**SourceScanner ABC (new, `backend/app/services/scanner.py`)**
- Responsibility: Define the scan/discover interface all sources must implement
- Testable: Via concrete implementations

**SourceScannerRegistry (new, `backend/app/services/scanner.py`)**
- Responsibility: Map source_type string → SourceScanner instance
- Interface: `get(source_type: str) → SourceScanner`

**GitHubScanner (refactor, `backend/app/services/github.py`)**
- Becomes a concrete `SourceScanner` subclass — no behaviour change, just conforms to interface

**LocalScanner (new, `backend/app/services/local.py`)**
- Responsibility: Read skill files from filesystem path, return `RawScanResult`
- No HTTP calls, no auth
- Testable: Yes — tmpdir fixtures

---

## Delivery Slices

**Slice 1 — Abstraction layer (no behaviour change)**
- Define `SourceRef`, `RawScanResult`, `SourceScanner` ABC, `SourceScannerRegistry` in `backend/app/services/scanner.py`
- Refactor `GitHubScanner` to implement `SourceScanner` — zero behaviour change
- All existing #002 tests pass unchanged

**Slice 2 — LocalScanner + CLI submit**
- Implement `LocalScanner`
- `GET /api/scan` endpoint resolves scanner from registry
- `agent-knowledge-hub submit <path>` CLI command
- Skill model gains `source_type` field

**Slice 3 — GitLab (separate todo)**
- Implement `GitLabScanner` as a concrete `SourceScanner`
- Register in `SourceScannerRegistry`
- Zero changes to API layer or MetadataExtractor

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Abstraction leaks GitHub-specific concepts into base interface | Medium | High | Keep `RawScanResult` generic; `repo_meta` is optional/empty for local |
| Local file snapshots bloat the DB | Medium | Medium | Store only recognised skill files (skill.md, CLAUDE.md, README.md, package.json, pyproject.toml) — typically < 50KB |
| CLI submit auth (how does the CLI prove user identity?) | Medium | High | CLI must call the authenticated API endpoint; user must have a session token or API key — scope to a future auth todo |
| #002 implementation bakes in GitHub-specific abstractions | High | Medium | Add abstraction guidance to #002 Definition of Done before implementation starts |

---

## Definition of Done

- [ ] `SourceScanner` ABC, `SourceRef`, `RawScanResult`, `SourceScannerRegistry` defined
- [ ] `GitHubScanner` implements `SourceScanner` — all existing #002 tests pass unchanged
- [ ] `LocalScanner` implemented and unit tested with tmpdir fixtures
- [ ] `source_type` field on Skill model (default `"github"`, additive migration)
- [ ] `GET /api/scan` resolves correct scanner from registry
- [ ] `agent-knowledge-hub submit <path>` CLI command functional
- [ ] `MetadataExtractor` has no imports from `github.py` — fully source-agnostic
- [ ] Adding a new scanner requires only: implement `SourceScanner`, call `registry.register()`
