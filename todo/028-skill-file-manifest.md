# 028 — Skill File Manifest: browsable file listing for skill/plugin repos

**Status:** 🔍 Reviewed
**Branch:** —
**Priority:** 🟡 P2 — Medium
**Created:** 2026-06-02

---

## Problem Statement

When a user views a skill detail page, they see `SKILL.md` and `README.md` (via #018 tabs) and a handful of extracted plugin.json fields (`has_scripts`, `agent_names`, etc.). But there's no way to see what else ships with the plugin — helper scripts, config templates, example files, Dockerfiles, etc.

There are two distinct gaps:
1. **Registration time**: a submitter has no visibility into which files will be captured before they confirm the submission. They trust the scanner blindly.
2. **Browse time**: a catalog user can't see the full file manifest of an installed skill without leaving AKH to visit GitHub.

---

## Goal

- **Registration flow**: show the full file list in the scan preview card so submitters see exactly what they're registering before confirming.
- **Skill detail page**: add a browsable Files tab so catalog users can read any file in a plugin without leaving AKH.

---

## User Stories

**Registration flow**
1. As a submitter, when I scan a GitHub URL, I want to see a list of all files in the skill directory in the scan preview card, so I can confirm the right files are included before I click Submit.
2. As a submitter, I want each file to show its size so I can spot unusually large files.
3. As a submitter using `submit <path>` (#004), I want the CLI to print the file list and count before the confirmation prompt.

**Skill detail — Files tab**
4. As a catalog browser, I want a Files tab on the skill detail page showing every file bundled with the plugin.
5. As a browser, I want to click on a text file to see its content inline with syntax highlighting, without leaving AKH.
6. As a browser, I want binary files (images, ZIPs) to show a "View on GitHub" link rather than attempting to render them.
7. As an admin, I want the manifest stored in the DB at scan time so the Files tab loads instantly on every page view.
8. As a submitter using a local directory skill (#004), I want the manifest populated from `snapshotted_files` so local skills get the same Files tab.

---

## Requirements

### Functional

- **FR-1**: `FileManifestEntry` captures: `path` (relative to skill dir), `size_bytes`, `is_text` (by extension allowlist), `is_dir: bool` (True when GitHub API returns `type: "dir"`). `is_dir=True` entries have `size_bytes=0` and `is_text=False`.
- **FR-2**: `RawScanResult` carries the full file listing from the GitHub Contents API dir listing (not just the recognised skill files already decoded).
- **FR-3**: Manifest is capped at 200 entries; excess files are omitted and a `manifest_truncated: bool` flag is set.
- **FR-4**: `SkillScanSnapshot` (scan preview) includes `file_manifest`.
- **FR-5**: `Skill` model stores `file_manifest` in MongoDB.
- **FR-6**: `SkillOut` serialises `file_manifest`.
- **FR-7**: `GET /api/skills/{slug}/files/{path:path}` returns the decoded text content of a single file. Binary files return HTTP 400 with a `github_url` field the client can redirect to.
- **FR-7a**: Path validation uses manifest-based lookup — only paths present in `skill.file_manifest` are served. Any unrecognised path returns HTTP 404 (not traversal logic). No pathlib resolution needed.
- **FR-7b**: Auth/visibility: `get_optional_user` dependency. Public skills: anonymous access allowed. Internal skills: require authenticated user (HTTP 401 for anon). Matches the existing `GET /api/skills/{slug}` auth pattern.
- **FR-7c**: Rate limiting: `@limiter.limit("60/minute")` per IP. Consistent with existing slowapi usage.
- **FR-8**: Local skills (`source_type="local"`) build `file_manifest` from `snapshotted_files` keys and their decoded lengths. Note: in v1, `snapshotted_files` only contains recognised skill files (SKILL.md, README.md, plugin.json, etc.) — the manifest will be partial for local skills. This is an acceptable v1 limitation; document in the Files tab empty-state copy.
- **FR-9**: Frontend submit form renders the file list (with size badges) inside the scan preview card.
- **FR-10**: Frontend skill detail adds a Files tab to `SkillContentTabs` with a flat file list and inline viewer.

### Non-functional

- **NFR-1**: File manifest stored in DB — the Files tab must render without an extra GitHub API call.
- **NFR-2**: `GET /api/skills/{slug}/files/{path:path}` uses a short-lived cache (TTL = 5 min) to avoid hammering GitHub on repeated views of the same file.
- **NFR-3**: Path security — only paths present in `skill.file_manifest` are served; all others return 404. No pathlib resolution required.

### Acceptance Criteria

- **AC-1**: Given a GitHub scan of a repo with 5 files, the scan preview card lists all 5 files with sizes.
- **AC-2**: Given a submitted skill, `GET /api/skills/{slug}` returns `file_manifest` with correct `path`, `size_bytes`, `is_text`.
- **AC-3**: Given a text file, `GET /api/skills/{slug}/files/SKILL.md` returns its decoded content.
- **AC-4**: Given a binary file, `GET /api/skills/{slug}/files/logo.png` returns HTTP 400 with `github_url`.
- **AC-5**: Given an unrecognised path (including traversal attempts like `../../etc/passwd`), the endpoint returns HTTP 404 (manifest-based lookup — unknown paths are not found, not explicitly rejected as traversal).
- **AC-6**: Given a local skill, the Files tab shows the files from `snapshotted_files`.
- **AC-7**: Given a repo with 250 files, only 200 are stored and `manifest_truncated=true`.

---

## Architecture Decision Records

### ADR-u15: FileManifestEntry placement

**Status:** Accepted

**Context:** `FileManifestEntry` is used in `RawScanResult` (scanner layer), `Skill` (model layer), and API schemas. Where should it be defined to avoid circular imports?

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Define in `scanner.py` | Close to first use, already imports Pydantic | Leaks scanner internals into models |
| Define in `models/skill.py` | Lives with the persistent model | scanner.py would import from models — layering violation |
| New `app/types.py` | Clean shared types module, no circular deps | One more file |

**Decision:** Define `FileManifestEntry` in `scanner.py` (alongside `RawScanResult`). Models/skill.py imports it from there — scanner is a low-level utility with no upward dependencies, so this direction is safe.

**Consequences:** `models/skill.py` imports from `app.services.scanner` — this is acceptable since scanner has no model imports.

---

### ADR-u16: File content serving strategy

**Status:** Accepted

**Context:** The Files tab inline viewer needs to fetch file content. Two options: serve live from GitHub, or store all file content in the DB alongside the manifest.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Live GitHub fetch per request | Always fresh; no extra DB storage | Rate limit exposure; latency; fails for private repos if token expired |
| Store all text content in `snapshotted_files` for all skills | Zero-latency; works offline; consistent with local skills | Potentially large DB documents; ~100KB/skill worst case |

**Decision:** Live fetch via `GET /api/skills/{slug}/files/{path:path}` with a 5-minute TTL cache on the backend. This is consistent with how `readme_raw` is refreshed. Storing all file content for GitHub skills would bloat MongoDB documents unnecessarily. Local skills already have content in `snapshotted_files` — the endpoint reads from there directly.

**Consequences:** File viewer requires an extra network round-trip on first view. TTL cache mitigates repeated fetches. Must handle expired/missing GitHub token gracefully (return 503 with message).

---

### ADR-u17: Manifest depth (flat vs recursive)

**Status:** Accepted

**Context:** The GitHub Contents API returns one directory level at a time. Recursive listing requires multiple API calls. The manifest is for the declared `skill_path` only.

**Options:**

| Option | Pros | Cons |
|---|---|---|
| Flat — top-level of `skill_path` only | One API call already made; zero extra cost | Misses files in `scripts/`, `config/`, etc. |
| Recursive — walk all subdirs | Complete picture | N extra API calls; rate limit pressure; complexity |

**Decision:** **Flat first** — use the single Contents API call already made during `scan()`. Files in subdirectories are omitted in v1. A future iteration can add recursive traversal. Most well-structured plugins keep their primary files flat; `plugin.json` already describes subdirs semantically.

**Consequences:** Subdirectory contents not visible in manifest. Acceptable for v1; add `manifest_depth: "flat"` flag to the API response so the frontend can indicate this to the user.

---

## Module Design

### `FileManifestEntry` — new (in `scanner.py`)
```python
class FileManifestEntry(BaseModel):
    path: str         # relative to skill_path, e.g. "scripts/install.sh"
    size_bytes: int
    is_text: bool     # extension-based; False for dirs
    is_dir: bool = False  # True when GitHub API returns type:"dir"
```
Simple value object. No I/O. Fully testable. Directory entries: `is_dir=True`, `size_bytes=0`, `is_text=False`.

### `RawScanResult` — modify (`scanner.py`)
Add `all_files: List[FileManifestEntry] = []`.

`GitHubScanner.scan()` populates this from `contents_data` (already available at line 420; currently only `recognised` subset is used). `LocalScanner` populates from `snapshotted_files` keys/values.

### `_TEXT_EXTENSIONS` — new constant (in `scanner.py`)
```python
_TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".sh", ".bash", ".zsh", ".py", ".js", ".ts",
    ".jsx", ".tsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".env", ".dockerfile", ".gitignore", ".gitattributes", ".editorconfig",
    ".sql", ".html", ".css", ".go", ".rb", ".rs", ".java", ".kt", ".swift",
}
```
No extension → `is_text=False`.

### `SkillScanSnapshot` — modify (`github.py`)
Add `file_manifest: List[FileManifestEntry] = []` and `manifest_truncated: bool = False`.

`MetadataExtractor.extract()` passes `result.all_files` through.

### `Skill` model — modify (`models/skill.py`)
Add `file_manifest: List[FileManifestEntry] = Field(default_factory=list)` and `manifest_truncated: bool = False`.

### `skill_repository.create()` — modify (`services/skill.py`)
Populate `file_manifest` and `manifest_truncated` from the scan snapshot (GitHub path) or from `snapshotted_files` (local path).

### `SkillOut` / `SkillScanSnapshotOut` — modify (`schemas/skill.py`)
Add `file_manifest` and `manifest_truncated`.

### `GET /api/skills/{slug}/files/{path:path}` — new endpoint (`routers/skills.py`)
- Path validation: look up `path` in `skill.file_manifest` paths. If not found → 404. No pathlib traversal logic needed.
- Auth: `get_optional_user`; if `skill.visibility == internal` and user is None → 401.
- Rate limit: `@limiter.limit("60/minute")`.
- For GitHub skills: fetches content via a new public method `github_scanner.fetch_file_content(skill, path)` (not the private `_fetch_text` directly). TTL cache keyed by `(slug, path)` with 5-min TTL.
- For local skills: reads from `skill.snapshotted_files[path]`; 404 if not present (v1 limitation).
- Returns `{"content": str, "path": str}` or `{"error": "binary_file", "github_url": str}` (400).

### `SkillContentTabs` — modify (`frontend/components/skill-content-tabs.tsx`)
Add a `files` tab. Renders a flat file list with size badges. Directory entries shown greyed-out with tooltip. Clicking a text file calls the new endpoint and shows an inline code block with loading/error states. Always show the Files tab (even when manifest empty) with an empty-state message. Tab label: "Files".

### `submit-form.tsx` — modify (`frontend/components/submit-form.tsx`)
Add file list as a **collapsible section below all form fields** in the scan preview card. Collapsed by default with "Files (N)" as the toggle header. Only shown when `snapshot.file_manifest.length > 0`. Directory entries (greyed out) are shown with a tooltip "Subdirectory — contents not indexed in this version".

---

## System Design

```
GitHub Contents API  ──► GitHubScanner.scan()
                          │
                          ├── contents_data (all files, existing)
                          │   └── all_files: List[FileManifestEntry]  ← NEW
                          │       (capped at 200, is_text by extension)
                          │
                          └── files (recognised skill files, existing)

RawScanResult { all_files, files, ... }
      │
      ▼
MetadataExtractor.extract()
      │
      ▼
SkillScanSnapshot { file_manifest, manifest_truncated, ... }  ← NEW fields
      │
      ├── Registration flow
      │   ├── SkillScanSnapshotOut  (API: /api/scan)
      │   └── submit-form.tsx  → renders file list in scan preview card
      │
      └── skill_repository.create()
            │
            ▼
          Skill (MongoDB) { file_manifest, manifest_truncated }  ← NEW fields
                │
                ▼
              SkillOut  (API: /api/skills/{slug})

GET /api/skills/{slug}/files/{path}  ← NEW endpoint
  auth: get_optional_user; 401 if internal + anon
  rate: 60/minute per IP
  validation: path must be in file_manifest (else 404)
      │
      ├── GitHub skills: github_scanner.fetch_file_content() + 5-min TTL cache
      └── Local skills:  skill.snapshotted_files[path] (404 if absent — v1 limitation)
            │
            ▼
      SkillContentTabs (Files tab)  ← NEW tab
```

**API contracts (new/modified):**

```
GET /api/skills/{slug}
  + file_manifest: [{ path, size_bytes, is_text }, ...]
  + manifest_truncated: bool

GET /api/skills/{slug}/files/{path:path}
  Auth:     get_optional_user; 401 if skill.visibility==internal and user is None
  Rate:     60/minute per IP (@limiter.limit)
  Validate: path must exist in skill.file_manifest paths; else 404
  Response 200 (text):   { "content": str, "path": str }
  Response 400 (binary): { "error": "binary_file", "github_url": str }
  Response 401:          { "detail": "Authentication required" }
  Response 404:          { "detail": "File not found in manifest" }
  Response 503:          { "detail": "GitHub fetch failed" }

GET /api/scan?url=...   (SkillScanSnapshotOut)
  + file_manifest: [{ path, size_bytes, is_text }, ...]
  + manifest_truncated: bool
```

---

## Trade-offs

**Flat manifest only (ADR-u17):**
- `+` zero extra GitHub API calls; no rate limit pressure
- `-` scripts in subdirs invisible; some plugins will show an incomplete picture
- Decision: ship flat, add depth toggle in a follow-up

**Live file fetch (ADR-u16):**
- `+` no DB bloat; always fresh
- `-` extra round-trip on first view; rate limit exposure
- Decision: 5-min TTL cache makes this a one-time cost per viewer per file

**`is_text` by extension (not content sniffing):**
- `+` zero I/O; deterministic; safe
- `-` `.env` files, files without extensions misclassified
- Decision: extension allowlist is sufficient; `.env` without extension returns binary → GitHub link (acceptable)

---

## Delivery Slices

### Slice 1 — Data + scan pipeline (backend only)
- Add `FileManifestEntry` + `_TEXT_EXTENSIONS` to `scanner.py`
- Add `all_files: List[FileManifestEntry]` to `RawScanResult`
- `GitHubScanner.scan()`: populate `all_files` from `contents_data` (with 200-cap and `manifest_truncated`)
- `LocalScanner`: populate `all_files` from `snapshotted_files` keys
- `SkillScanSnapshot` gains `file_manifest` + `manifest_truncated`
- `MetadataExtractor.extract()` passes `all_files` through
- `Skill` model gains `file_manifest` + `manifest_truncated`
- `skill_repository.create()` stores manifest
- `SkillOut` + `SkillScanSnapshotOut` serialise the new fields
- Tests: unit tests for `FileManifestEntry`, `_TEXT_EXTENSIONS`, scanner population, and `MetadataExtractor` passthrough

### Slice 2 — Registration flow: scan preview file list (frontend)
- `SkillScanSnapshot` TypeScript type gets `file_manifest` + `manifest_truncated`
- `submit-form.tsx`: render file list section in scan preview card (flat list, size badges, truncation notice)
- SKILL.md CLI `submit <path>`: print file list + count before confirm prompt

### Slice 3 — File content endpoint (backend)
- `GET /api/skills/{slug}/files/{path:path}` in `routers/skills.py`
- Path validation: manifest-based lookup (path in file_manifest paths set); 404 if not found
- Auth: `get_optional_user`; 401 if internal and anon
- Rate limit: `@limiter.limit("60/minute")`
- Add public `github_scanner.fetch_file_content(skill, path)` method (not `_fetch_text` directly)
- 5-min TTL cache keyed by `(slug, path)`
- Local skills: read from `snapshotted_files`; 404 if absent
- Tests: manifest-path-not-found 404, auth gating for internal skill, rate-limit header present, text response, binary 400, local skill read

### Slice 4 — Files tab (frontend)
- `SkillContentTabs` gains `fileManifest` prop + Files tab
- Always render Files tab; show empty state when manifest is empty ("File listing not available for this skill. Re-submit the URL to refresh.")
- Flat list with size badges; truncation notice when `manifest_truncated=true`
- Directory entries rendered greyed out with tooltip "Subdirectory — contents not indexed in this version"
- Text files: click → loading state → calls `/api/skills/{slug}/files/{path}` → renders in `<pre>` / code block with syntax highlighting
- Binary files: "View on GitHub ↗" link
- Error state: if fetch fails, show "Could not load file. View on GitHub ↗"
- Skill detail page passes `fileManifest` to the component

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `contents_data` not a list (single-file path submitted) | Medium | Low | Already guarded in scanner (line 420); `all_files` stays empty |
| GitHub rate limit on file content fetches | Low | Medium | 5-min TTL cache; one fetch per file per 5 min per instance |
| Path traversal via `..` in `{path}` | Low | High | Manifest-based lookup — only paths in `file_manifest` are served; all others 404 |
| MongoDB document bloat if manifest is large | Low | Low | 200-file cap; `FileManifestEntry` is ~60 bytes each → max ~12KB per skill |
| Private repo file content exposed | Low | High | File endpoint inherits same auth token logic as existing skill fetch; internal skills already gated |

---

## Definition of Done

**Slice 1 — Data + scan pipeline**
- [ ] `FileManifestEntry` defined in `scanner.py` with `path`, `size_bytes`, `is_text`
- [ ] `_TEXT_EXTENSIONS` constant defined
- [ ] `RawScanResult.all_files` populated by `GitHubScanner.scan()` from `contents_data`
- [ ] `RawScanResult.all_files` populated by `LocalScanner` from `snapshotted_files`
- [ ] 200-file cap enforced; `manifest_truncated` flag set correctly
- [ ] `SkillScanSnapshot.file_manifest` + `manifest_truncated` populated by `MetadataExtractor`
- [ ] `Skill` model has `file_manifest` + `manifest_truncated`
- [ ] `skill_repository.create()` stores manifest for both GitHub and local skills
- [ ] `skill_repository.refetch()` updated to refresh `file_manifest` + `manifest_truncated` (prevent stale manifests on re-fetch)
- [ ] `SkillOut` + `SkillScanSnapshotOut` include `file_manifest` + `manifest_truncated`
- [ ] `_skill_to_out()` / manual serialisation mappings updated to include `file_manifest`
- [ ] Unit tests passing for all above; test fixtures include `size` field in mock dir listing items

**Slice 2 — Registration flow**
- [ ] `SkillScanSnapshot` TypeScript type updated
- [ ] Scan preview card renders file list with sizes
- [ ] Truncation notice shown when `manifest_truncated=true`
- [ ] CLI `submit <path>` prints file list before confirm

**Slice 3 — File content endpoint**
- [ ] `GET /api/skills/{slug}/files/{path:path}` returns content for text files
- [ ] Path validation: manifest-based lookup; 404 for unknown paths
- [ ] Auth: 401 for anonymous access to internal skills
- [ ] Rate limit: `@limiter.limit("60/minute")` applied
- [ ] Public `fetch_file_content()` method added to `GitHubScanner` (not private `_fetch_text`)
- [ ] 5-min TTL cache keyed by `(slug, path)`
- [ ] Binary files return 400 + `github_url`
- [ ] Local skills served from `snapshotted_files`; 404 if absent
- [ ] Tests for all response paths

**Slice 4 — Files tab**
- [ ] Files tab always rendered; empty state for skills with no manifest
- [ ] Files tab renders file list with size badges
- [ ] Directory entries shown greyed-out with tooltip
- [ ] Truncation notice shown when `manifest_truncated=true`
- [ ] Inline viewer with syntax highlighting for text files
- [ ] Binary files show "View on GitHub ↗" link
- [ ] Loading state while fetching file content
- [ ] Error state when file fetch fails

**Documentation (post-ship)**
- [ ] `docs/skill-file-discovery.md` updated to document `all_files` in scan pipeline
- [ ] `CHANGELOG.md` entry added under [Unreleased]
- [ ] ADR-u15, ADR-u16, ADR-u17 written as standalone files in `docs/adr/`
- [ ] `skill/SKILL.md` updated — mention file list in CLI `submit <path>` flow
- [ ] `docs/github-api-plugin-installation.md` updated — note rate-limit implications of file content endpoint

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-02
**Rounds:** 3

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ✅ PASS | Y | Core technical claims verified; TTL ref corrected; local manifest gap documented |
| codebase-arch-review | ✅ PASS | N | Router must expose public `fetch_file_content()` not `_fetch_text`; `refetch()` must update manifest; `SkillListOut` excludes manifest |
| codebase-eng-review | ⚠️ PASS WITH WARNINGS | N | `is_dir` field required (fixed R2); `_skill_to_out()` gap; 35-case test plan produced |
| doc-review | ✅ PASS | Y | 5 doc gaps added to DoD; ADRs must become standalone files in `docs/adr/` |
| security-review | ✅ PASS | N | All 3 blocking issues resolved: auth=get_optional_user+401, rate=60/min, path=manifest-lookup |
| codebase-ux-review | ✅ PASS | N | Collapsible file list placement resolved; greyed-out dirs with tooltip resolved |

**Accepted warnings:** eng-review: `_skill_to_out()` gap and cache invalidation on refetch (v2 item) — both addressed in DoD
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research — Round 1 (PASS)</summary>

## Summary

Plan is factually sound on its core technical claims — the GitHub Contents API data IS available in scan() and includes size_bytes, the path traversal pattern IS safe, and the MongoDB size impact is reasonable (~13-15KB worst case vs. 16MB limit). Three issues need attention: (1) the TTL consistency reference is wrong (should cite _MARKETPLACE_TTL, not readme_fetched_at), (2) use PurePosixPath for GitHub path validation instead of filesystem resolve(), and (3) local skill manifests face a design gap because snapshotted_files only stores recognized files, not a full directory listing. One judgement-call decision required on local skill manifest scope.

## Issues

### 1. TTL claim is misleading — existing scan cache is 60s, not 5 min
low: The plan stated "consistent with readme_fetched_at" but readme_fetched_at is a MongoDB timestamp, not a cache TTL. Existing _scan_cache is TTLCache(ttl=60). The 5-min choice is valid; correct consistency anchor is _MARKETPLACE_TTL (300s). Plan amended.

### 2. Path traversal uses filesystem resolve() for GitHub paths
low: Semantically awkward (GitHub paths aren't filesystem paths) but functionally safe. Superseded by manifest-based lookup decision.

### 3. Local skill manifest from snapshotted_files — size_bytes only derivable from len(content.encode())
medium: snapshotted_files is Dict[str, str] — only recognised skill files, not full directory. size_bytes = len(content.encode('utf-8')). Documented in plan as v1 limitation.

## Verified Claims
- GitHub Contents API dir listing fetched at line 392/420: CONFIRMED
- size field present in Contents API response: CONFIRMED
- contents_data currently discarded after _SKILL_FILES filter: CONFIRMED
- MongoDB size impact ~12KB: APPROXIMATELY CORRECT (~13-15KB)
- Path traversal safe: CONFIRMED (superseded by manifest-lookup)

## Status
PASS (amended)

</details>

<details>
<summary>codebase-arch-review — Round 1 (PASS)</summary>

## Summary
Solid v1 scope. Design reuses existing contents_data avoiding extra API calls. Three items: (1) router must not call _fetch_text() directly — add public fetch_file_content(); (2) refetch() must update file_manifest; (3) models/skill.py import from scanner.py is acceptable (leaf-to-leaf). No blocking issues. Two judgement calls.

## Issues
1. medium | layering | Router calling private _fetch_text() — add public fetch_file_content(ref, file_path) method
2. medium | staleness | refetch() doesn't update file_manifest — skills will show stale manifests forever
3. low | performance | SkillListOut must NOT include file_manifest (keep paginated responses lightweight)
4. low | ops | In-memory cache not shared across replicas — accepted v1 trade-off
5. low | routing | FastAPI {path:path} empty path edge case — needs test
6. low | layering | models/skill.py import from services/scanner — acceptable, scanner is leaf module

## Amendments
- Added public fetch_file_content() method to module design
- Added refetch() update requirement to DoD Slice 1
- Confirmed SkillListOut excludes file_manifest

## Status
PASS

</details>

<details>
<summary>codebase-eng-review — Round 2 (PASS WITH WARNINGS)</summary>

## Summary
Well-structured plan with sound ADRs. Six issues: one blocking (missing is_dir field — fixed), three warnings (refetch underspecified, _skill_to_out gap, AC-5 status code — all fixed), two notes. 35-case test plan produced.

## Key Issues Fixed
- I-1 BLOCKING: FileManifestEntry missing is_dir field — FIXED in Round 2 (is_dir: bool = False added)
- I-2 WARNING: refetch() in wrong DoD section — FIXED (moved to Slice 1 code tasks)
- I-3 WARNING: _skill_to_out() mapping gap — FIXED (added to Slice 1 DoD)
- I-4 WARNING: AC-5 says 400 but FR-7a says 404 — FIXED (AC-5 updated to 404)

## Notes
- Use item["name"] not item["path"] for FileManifestEntry.path (flat basename, not full repo-relative path)
- Test fixtures (FAKE_DIR_LISTING) must add size field
- Cache invalidation on refetch is v2 item

## Status
PASS WITH WARNINGS (warnings accepted)

</details>

<details>
<summary>doc-review — Round 1 (PASS)</summary>

## Summary
Plan has zero documentation deliverables but 5 existing docs are directly affected. All 5 gaps added as DoD items.

## Gaps Found
1. docs/skill-file-discovery.md — pipeline doc directly affected by all_files addition
2. CHANGELOG.md — new endpoint, new fields, new tab warrant an entry
3. ADR-u15/u16/u17 inline only — must become standalone files in docs/adr/ (convention of existing u01-u10)
4. skill/SKILL.md — submit <path> section needs update for file list display
5. docs/github-api-plugin-installation.md — rate-limit implications of new endpoint

## Status
PASS (amended)

</details>

<details>
<summary>security-review — Round 2 (PASS)</summary>

## Summary
All 3 Round 1 blocking issues correctly and completely resolved.

1. Auth (ISSUE-1): get_optional_user + 401 for internal skills — matches codebase patterns, specified in FR-7b, covered in tests
2. Rate limit (ISSUE-2): 60/minute per IP — uses established slowapi pattern, contextually appropriate for cached read-only endpoint
3. Path traversal (ISSUE-4): Manifest-based allowlist eliminates entire traversal attack class by design — no pathlib, no edge cases, fail-safe to 404

XSS concern neutralized by JSON response envelope (FastAPI default application/json).

## Status
PASS

</details>

<details>
<summary>codebase-ux-review — Round 2 (PASS)</summary>

## Summary
Both Round 1 blocking decisions correctly incorporated. Loading/error/empty states all addressed. One non-blocking warning (sort order unspecified — default API order acceptable for v1).

1. File list placement: collapsible "Files (N)" section below form fields, collapsed by default — correctly specified in Module Design for submit-form.tsx
2. Directory entries: greyed-out with tooltip "Subdirectory — contents not indexed in this version" — specified for both registration and detail page

## Status
PASS

</details>
