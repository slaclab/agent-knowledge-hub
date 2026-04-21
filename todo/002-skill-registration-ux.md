# 002 — Improved Skill Registration UX: Directory-Aware Submission

**Status:** 🏁 Implementation Done

---

## Problem & Goal

**Problem:** The current submit form requires a bare GitHub repo URL and then asks users to fill in name, description, platforms, version, and license manually. This is friction-heavy, especially for skills that live in a subdirectory of a monorepo (e.g. `slac-agent-plugin-marketplace/plugins/coding-orchestrator`). Users also need the submission to carry enough structural metadata for the `/agent-knowledge-hub` CLI skill to know exactly which directory to clone/copy when installing.

**Goal:** A user submits a single GitHub URL — either a bare repo URL or a `tree/branch/path` directory URL — and the system scans the target directory, auto-populates all form fields from discovered files, and the user reviews/edits before final submission. The stored `repo_url` + `skill_path` pair uniquely identifies the skill and is sufficient for local install.

**Success metric:**
- Median time-to-submit drops below 2 minutes (from current ~5 min estimate)
- Skills in monorepos can be registered and installed via `/agent-knowledge-hub install <slug>`
- Duplicate (repo + path) submissions are rejected

**Out of scope:**
- Executing or validating skill code
- Supporting non-GitHub VCS (GitLab, Bitbucket)
- Auto-discovering all skills in a monorepo (user still provides the path)

**Constraints:**
- GitHub API rate limits (unauthenticated: 60/hr; App token: 5000/hr — see todo/001)
- Must remain backward-compatible with existing bare-repo submissions (path = `/`)

---

## User Stories

1. As a skill author, I want to paste a GitHub directory URL and have all fields auto-filled, so I don't have to type metadata I've already written in my repo.
2. As a skill author with a monorepo, I want to register individual skills at specific paths, so each skill gets its own catalog entry.
3. As a skill author, I want to see a live preview of the auto-populated fields before I submit, so I can catch incorrect extractions.
4. As a skill author, I want to edit any auto-populated field before submitting, so I can improve on what was inferred.
5. As a skill author, I want to submit a bare repo URL (no path) and have the system treat the root as the skill directory, so existing workflows still work.
6. As a consumer, I want to install a skill with `/agent-knowledge-hub install <slug>` and have the correct subdirectory cloned to `~/.claude/skills/`, so I don't need to find and copy files manually.
7. As a consumer, I want the install command to work for both root-level and subdirectory skills without any extra configuration.
8. As a skill author, I want the system to scan for `skill.md`, `CLAUDE.md`, `README.md`, `package.json`, and `pyproject.toml` in the skill directory and extract metadata from each, so the preview is as complete as possible.
9. As a skill author, I want repo-level metadata (stars, last commit, license) to be fetched alongside directory-level files, so the card shows accurate GitHub stats.
10. As a skill author, I want a clear error if the supplied path doesn't contain any recognisable skill files, so I know the URL is wrong before submitting.
11. As a skill author, I want to re-submit with a corrected path if the first scan failed, without losing the repo URL I already typed.
12. As a catalog admin, I want uniqueness enforced on (repo_url + skill_path), so two authors can't create duplicate entries for the same skill directory.
13. As an admin, I want to see `skill_path` in the skill detail and audit log, so I can verify the correct directory was registered.
14. As a `/agent-knowledge-hub` CLI user, I want `install <slug>` to check out only the `skill_path` subdirectory (sparse checkout or file copy), so I don't pull an entire monorepo.

---

## Requirements

### Functional

- FR-U1: The submit form accepts a GitHub URL in any of these formats and normalises it:
  - `https://github.com/owner/repo` → repo=owner/repo, branch=default, path=`/`
  - `https://github.com/owner/repo/tree/<branch>/<path>` → repo, branch, path extracted
- FR-U2: An explicit "Scan" button is the primary trigger. On-blur fires scan as a convenience. The Submit button is disabled while a scan is in progress. On activation, backend fetches:
  1. Repo-level metadata via GitHub API (`stars`, `last_commit_at`, `license`, `default_branch`)
  2. Directory listing at `path` via `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`
  3. Contents of each recognised file: `skill.md`, `CLAUDE.md`, `README.md` (directory), `package.json`, `pyproject.toml`
  4. Repo-root `README.md` (if path ≠ `/`)
- FR-U3: Metadata extraction priority (first match wins per field):
  - **name**: frontmatter `name` in `skill.md`/`CLAUDE.md` → `package.json#name` → `pyproject.toml#project.name` → directory basename → repo name
  - **description**: frontmatter `description` → first non-heading paragraph of directory `README.md` → GitHub repo description
  - **compatible_platforms**: frontmatter `platforms` list in `skill.md`/`CLAUDE.md` → inferred from file presence (`CLAUDE.md` → `claude-code`, `package.json` → check for `openai`/`langchain` deps)
  - **version**: frontmatter `version` → `package.json#version` → `pyproject.toml#project.version`
  - **license**: GitHub repo API `license.spdx_id`
  - **readme_html**: directory `README.md` rendered as HTML; fall back to repo-root `README.md`
- FR-U4: A new backend FastAPI endpoint `GET /api/github-scan?url=<github_url>` returns the full extracted metadata snapshot. A thin Next.js proxy route at `frontend/app/api/github-scan/route.ts` forwards to it. Scanner logic lives in Python (`backend/app/services/github.py`).
- FR-U4a: The endpoint requires authentication (`Depends(get_current_user)`) — consistent with `POST /api/skills`. Unauthenticated requests return HTTP 401.
- FR-U4b: `GitHubURLParser` validates the URL is a `github.com` URL before parsing. `GitHubScanner` constructs all outbound API URLs from parsed `{owner, repo, branch, path}` components only — the raw user URL is never used for outbound HTTP requests (SSRF prevention by construction).
- FR-U5: Skill model adds `skill_path: str` (default `/`). Uniqueness index on `(repo_url, skill_path)`. `skill_path` is validated at write time: strip leading `/`, reject any path component containing `..`.
- FR-U5a: Migration: explicitly drop the existing `repo_url` unique index before creating the compound `(repo_url, skill_path)` index in the Beanie startup lifespan (Beanie does not auto-drop old indexes).
- FR-U6: `POST /api/skills` accepts `skill_path` in the request body.
- FR-U7: If the scanned directory contains no recognisable skill files (`skill.md`, `CLAUDE.md`, `README.md`, `package.json`, `pyproject.toml`), the endpoint returns a warning (not an error) — user can still submit with manual metadata.
- FR-U8: The stored `skill_path` is included in the `SkillOut` schema and surfaced on the detail page.
- FR-U9: `GET /api/skills/:slug` returns `skill_path` so the CLI install command knows which directory to fetch.
- FR-U10: Duplicate (repo_url + skill_path) submissions return HTTP 409 with a link to the existing entry.
- FR-U11: When a bare repo URL is submitted (path `/`), the backend additionally scans the repo recursively for skill directories — any directory containing `skill.md` or `CLAUDE.md` is treated as a candidate skill.
- FR-U12: `GET /api/github-scan?url=<repo_url>&discover=true` returns a list of `SkillSnapshot[]` — one per discovered skill directory — instead of a single snapshot. If the GitHub Trees API returns `truncated: true`, the response includes `tree_truncated: true` and a warning message: "This repo is very large — not all skill directories may have been found. Paste a specific directory URL to register a skill directly."
- FR-U12a: Discovery is capped at 20 concurrent directory scans. If more than 20 candidates are found, the first 20 are scanned and a `capped: true` flag is returned.
- FR-U13: The submit form has a "Scan entire repo" mode: when a bare repo URL is entered and discovery returns multiple skills, the form renders a checklist of discovered skills. Skills are shown as **collapsed cards by default** (path + inferred name only); users expand individual cards to edit fields. A "Select all new" / "Deselect all" toggle is provided. The submit button shows the count: "Submit N of M skills". The user selects which ones to submit and can edit each independently before bulk-submitting.
- FR-U16: Duplicate check is performed at scan time. If the scanned `(repo_url, skill_path)` already exists, the scan response includes `existing_slug` and the form shows a warning with a link to the existing entry immediately, before the user fills in fields. The check is also enforced at submit time (HTTP 409).
- FR-U14: Bulk submission calls `POST /api/skills` once per selected skill (sequentially or in parallel). Each succeeds or fails independently; partial success is reported per-skill.
- FR-U15: Already-registered skills (duplicate repo_url + skill_path) in the discovery list are shown as "Already in catalog" and pre-deselected.

### Non-Functional

- NFR-U1: Directory scan completes in < 3s for a directory with ≤ 20 files (GitHub API calls are parallelised).
- NFR-U2: File content fetches are done in parallel (asyncio.gather).
- NFR-U3: Scan result is cached for 60s (same URL, same user session) to avoid re-fetching on accidental re-blur.

### Acceptance Criteria

- AC-U1: Given `https://github.com/slaclab/slac-agent-plugin-marketplace/tree/main/plugins/coding-orchestrator`, when scanned, the form populates name, description, and platforms from files in that directory.
- AC-U2: Given `https://github.com/yee379/dotclaude`, when scanned, path defaults to `/` and root files are used.
- AC-U3: Given a directory with no recognised skill files, the form shows a warning but allows manual submission.
- AC-U4: Given two submissions with the same repo_url and skill_path, the second returns HTTP 409 with a link to the existing skill.
- AC-U5: Given a submitted skill with `skill_path=/skills/agentic-standards`, `GET /api/skills/<slug>` returns `skill_path` in the response.

---

## Architecture

### URL Parsing

```
Input URL
  │
  ▼
GitHubURLParser.parse(url) → {owner, repo, branch, path}
  │
  "https://github.com/owner/repo"                    → branch=None, path="/"
  "https://github.com/owner/repo/tree/main/plugins/x" → branch="main", path="plugins/x"
```

### Scan Flow

```
GET /api/github-scan?url=<url>
  │
  ▼
GitHubScanner.scan(owner, repo, branch, path)
  │
  ├── parallel:
  │   ├── GET /repos/{owner}/{repo}                         → repo metadata
  │   ├── GET /repos/{owner}/{repo}/contents/{path}?ref=    → directory listing
  │   └── GET /repos/{owner}/{repo}/contents/README.md      → repo-root README
  │
  ├── for each recognised file in directory listing (parallel):
  │   └── GET /repos/{owner}/{repo}/contents/{path}/{file}?ref=  → decode base64 content
  │
  ▼
MetadataExtractor.extract(files, repo_meta) → SkillSnapshot
  (name, description, compatible_platforms, version, license, readme_html, skill_path)
```

### Data Model Changes

```python
class Skill(Document):
    skill_path: str = "/"          # new — path within repo, default root
    # repo_url uniqueness index replaced by compound (repo_url, skill_path)
```

### API Changes

```
# New endpoint
GET /api/github-scan?url=<github_url>
  Response 200: SkillSnapshot (same shape as existing GitHubPreview + extracted fields)
  Response 422: invalid URL format
  Response 404: repo/path not found

# Modified
POST /api/skills
  Body: adds optional skill_path: str (default "/")

GET /api/skills/:slug
  Response: adds skill_path field
```

### Repo Discovery Flow

```
GET /api/github-scan?url=https://github.com/owner/repo&discover=true
  │
  ▼
GitHubScanner.discover(owner, repo, branch)
  │
  ├── GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1  → full file tree
  │
  ├── Find all directories containing skill.md or CLAUDE.md
  │   e.g. ["plugins/coding-orchestrator", "plugins/data-analysis", ...]
  │
  ├── For each candidate directory (parallel, up to 20 concurrent):
  │   └── GitHubScanner.scan(ref with path=dir) → SkillSnapshot
  │
  ▼
Response: { discovered: SkillSnapshot[], already_registered: str[] }
```

### Submit Form — Discovery Mode

```
User pastes bare repo URL
  │
  ▼
"Scan for skills" button (or auto on blur if path="/")
  │
  ▼
Checklist of discovered skills:
  ┌─────────────────────────────────────────┐
  │ ☑ plugins/coding-orchestrator           │
  │   Name: Coding Orchestrator             │
  │   Description: [editable]               │
  │   Platforms: [claude-code] [editable]   │
  ├─────────────────────────────────────────┤
  │ ☑ plugins/data-analysis                 │
  │   ...                                   │
  ├─────────────────────────────────────────┤
  │ ☐ plugins/legacy-tool  (already in      │
  │   catalog — view →)                     │
  └─────────────────────────────────────────┘
  [ Submit selected (2) ]
```



### Migration

Expand-contract: additive only. `skill_path` defaults to `/` for all existing entries. Existing `repo_url` unique index replaced with compound `(repo_url, skill_path)` unique index — existing data is valid (all have path `/`). No data migration required; index creation is safe on an empty or small collection.

**Index migration order (required):** Beanie does not auto-drop old indexes. The startup lifespan must explicitly call `drop_index("repo_url_1")` before `init_beanie()` to remove the old unique index, then allow Beanie to create the new compound index. Without this, monorepo skills sharing the same `repo_url` will be silently rejected.

---

## ADRs

### ADR-U01: New `/api/github-scan` endpoint vs. extending existing `/api/github-preview`

**Status:** Accepted

| Option | Pros | Cons |
|---|---|---|
| Extend `/api/github-preview` | One fewer endpoint | Preview is lightweight (stars/name only); scan is heavyweight (multiple fetches, parsing) |
| New `/api/github-scan` | Clean separation of concerns; scan can be slow without affecting preview | One more endpoint |

**Decision:** New `/api/github-scan`. The scan fetches 5–10 files in parallel and parses frontmatter — a different contract from the quick preview.

### ADR-U02: Frontmatter format for skill.md / CLAUDE.md

**Status:** Accepted (pending validation of existing repos)

YAML frontmatter at top of file (standard Jekyll/Hugo convention):
```yaml
---
name: Coding Orchestrator
description: Orchestrates multi-agent coding workflows
platforms: [claude-code, openai]
version: 1.2.0
---
```
If no frontmatter present, fall back to content heuristics. Parser: `python-frontmatter` library.

### ADR-U03: sparse checkout vs. full clone for install

**Status:** Accepted

GitHub supports `sparse-checkout` but it requires a local git operation. Simpler: use the GitHub API `GET /repos/{owner}/{repo}/contents/{path}` recursively to download only the skill directory files. No git required on the user's machine beyond what Claude Code already has. The `/agent-knowledge-hub install` skill fetches files via API and writes them to `~/.claude/skills/<slug>/`.

---

## Modules

**GitHubURLParser (new, `backend/app/services/github.py`)**
- Responsibility: Parse any GitHub URL into `{owner, repo, branch, path}`
- Interface: `parse(url: str) → GitHubRef`
- Testable: Yes — pure string parsing, no I/O

**GitHubScanner (new, `backend/app/services/github.py`)**
- Responsibility: Fetch repo metadata + directory listing + file contents in parallel; return raw file map
- Interface: `scan(ref: GitHubRef) → RawScanResult`
- Testable: Yes — respx mocks

**MetadataExtractor (new, `backend/app/services/github.py`)**
- Responsibility: Extract name/description/platforms/version/license/readme from raw files using priority rules
- Interface: `extract(result: RawScanResult) → SkillSnapshot`
- Testable: Yes — pure transformation, no I/O

**`GET /api/github-scan` route handler (new, `backend/app/routers/github_scan.py` + thin proxy at `frontend/app/api/github-scan/route.ts`)**
- FastAPI endpoint on backend; Next.js proxy forwards to it (consistent with existing skills pattern)
- Requires `Depends(get_current_user)`
- Accepts full GitHub URL, returns full SkillSnapshot

**SubmitForm (modify, `frontend/components/submit-form.tsx`)**
- Replace repo_url input with a single URL field accepting both bare-repo and `tree/branch/path` formats
- Placeholder shows both formats: `https://github.com/org/repo  or  .../tree/branch/path/to/skill`
- Helper text below input: "Paste any GitHub URL — bare repo or a specific directory."
- Explicit "Scan" button is the primary trigger; on-blur fires scan as a convenience
- Submit button disabled while scan is in progress
- Warning state for missing skill files (with "fill in manually" CTA)
- Duplicate shown at scan time with link to existing entry (also enforced at submit as 409)
- Client-side timeout: 10s for single scan, 30s for discovery; on timeout show "Taking longer than expected — retry?" with cancel

**Skill model (modify, `backend/app/models/skill.py`)**
- Add `skill_path: str = "/"`
- Replace `repo_url` unique index with compound `(repo_url, skill_path)` unique index

---

## Trade-offs

**Single URL input vs. separate repo + path fields**
- `+` Simpler UX: paste one URL from browser address bar
- `+` Handles both formats transparently
- `-` URL parsing edge cases (branch names with slashes, encoded characters)
- Decision: Single URL input with robust parser; error clearly if parsing fails

**Parallel file fetches vs. sequential**
- `+` Parallel: 5-10 files fetched in ~500ms instead of ~3s
- `-` More concurrent GitHub API calls; hits rate limits faster on unauthenticated path
- Decision: Parallel with `asyncio.gather`; App token (todo/001) solves rate limits

---

## Delivery Slices

**Slice 1 — Data model + API**
- Add `skill_path` to Skill model, compound unique index
- Migration: drop old `repo_url_1` index before creating compound index in startup lifespan
- Validate `skill_path` at write time: strip leading `/`, reject `..` path components
- `GitHubURLParser` + `GitHubScanner` + `MetadataExtractor` backend services (Python, `backend/app/services/github.py`)
- `GitHubURLParser` validates URL is github.com; scanner constructs outbound URLs from parsed components only (SSRF prevention)
- `GET /api/github-scan` FastAPI endpoint (auth-gated) + Next.js proxy route
- Unit tests for parser + extractor
- Scan cache: `cachetools.TTLCache` (60s, keyed by `(url, user_id, discover)` — the `discover` flag must be in the key to avoid returning wrong-shape cached results)

**Slice 2 — Frontend form (single skill)**
- Replace submit form URL input with directory-aware input (both URL formats)
- Update placeholder text and helper text to show both URL formats
- Explicit "Scan" button as primary trigger; on-blur as convenience; Submit disabled during scan
- Duplicate check at scan time (show warning + link); enforced at submit as 409
- Warning state for missing skill files with "fill in manually" CTA
- Distinct visual treatment for 4 error states: no-files (yellow), 404 (red), 409 (amber+link), rate-limit (amber+retry)
- Client-side timeout: 10s with retry prompt
- Update guides page and README with new URL submission instructions

**Slice 3 — Repo discovery + bulk submit**
- `discover=true` param on `/api/github-scan`; recursive tree walk + parallel per-dir scan (cap: 20 concurrent)
- Detect `truncated: true` from Trees API; surface warning to user with fallback guidance
- Submit form discovery mode: collapsed cards by default (expand to edit), "Select all new" / "Deselect all" toggle, submit button shows count "Submit N of M skills"
- Already-registered skills shown as pre-deselected with submitter info and "view" link
- Partial failure reporting per-skill in bulk submit result
- 30s client-side timeout for discovery

**Slice 4 — Install support**
- Add `skill_path` to `SkillOut` schema
- Update `/agent-knowledge-hub install` skill to use `skill_path` for sparse directory fetch
- CLI validates `skill_path` from API before file write: reject `..` components, ensure resolved path stays within `~/.claude/skills/<slug>/`

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub API rate limit on scan (10 calls per submission) | Medium | Medium | GitHub App token (todo/001); cache scan results 60s |
| Branch names with slashes break URL parsing | Medium | Low | Known limitation: only simple branch names supported; documented; users with slashed branches paste directory URL directly |
| Frontmatter not present in most existing skills | High | Low | Graceful fallback chain; warning not error |
| Large directory listing (100+ files) slows scan | Low | Low | Only fetch recognised filenames, not all files |
| Compound index migration fails on existing data | Low | High | All existing entries have path="/"; drop old index explicitly before creating compound index |
| Refetch not path-aware for monorepo skills | Medium | Low | Existing refetch method uses repo-root README for skills with skill_path != "/"; acceptable for v1, track as follow-up |
| Trees API truncation on large repos | Medium | Low | Detect `truncated: true`; surface warning with fallback guidance |
| SSRF via user-supplied URL | Low | High | URL parser validates github.com; scanner constructs API URLs from parsed components only |
| Path traversal via skill_path in install | Low | High | Validate at API write time + CLI before file write |

---

## Definition of Done

- [x] `skill_path` field on Skill model, compound unique index on (repo_url, skill_path)
- [x] Old `repo_url_1` unique index explicitly dropped in startup lifespan before compound index created
- [x] `skill_path` validated at write time: leading `/` stripped, `..` components rejected
- [x] `GitHubURLParser` handles bare repo + tree/branch/path URLs, validates github.com, unit tested
- [x] `GitHubURLParser` documents limitation: branch names with slashes not supported
- [x] `MetadataExtractor` priority rules unit tested for all field extraction paths
- [x] `GitHubScanner` constructs all outbound URLs from parsed components (never raw user URL)
- [x] `GET /api/github-scan` FastAPI endpoint (auth-gated) + Next.js proxy route
- [x] `GET /api/github-scan` returns full snapshot in < 3s for a 10-file directory
- [x] Discovery detects `truncated: true` and returns warning + fallback guidance
- [x] Discovery capped at 20 concurrent scans; returns `capped: true` if exceeded
- [x] Submit form: explicit "Scan" button as primary trigger; Submit disabled during scan
- [x] Submit form: placeholder and helper text show both URL formats
- [x] Duplicate check surfaced at scan time (warning + link); enforced at submit (409)
- [x] Distinct error UX for: no-files (yellow), 404 (red), 409 (amber), rate-limit (amber)
- [x] Client-side timeout: 10s single scan, 30s discovery, with retry prompt
- [x] Discovery mode: collapsed cards by default, select-all toggle, count on submit button
- [x] 409 on duplicate (repo_url + skill_path) with link to existing entry
- [x] `skill_path` returned in `SkillOut` and visible on detail page
- [x] CLI install validates `skill_path` before file write (no `..` escape)
- [x] Existing bare-repo submissions unaffected (path defaults to `/`)
- [x] `MetadataExtractor` has no imports from GitHub-specific modules — it receives a generic `RawScanResult` (files dict + repo_meta dict) so it works with any future source type
- [x] `GitHubScanner` and `GitHubURLParser` are not referenced directly from the API router — the router calls them via an interface that a `LocalScanner` or `GitLabScanner` could satisfy (see #004)
- [x] `python-frontmatter` added to `requirements.txt`
- [x] Guides page and README updated with new submission instructions

---

## Test Plan

### Unit Tests (backend, pytest + respx + mongomock-motor)

**File: `backend/tests/test_github_url_parser.py`**

| ID | Test | Input | Expected |
|---|---|---|---|
| TP-01 | Bare repo URL | `https://github.com/slaclab/my-skill` | `GitHubRef(owner="slaclab", repo="my-skill", branch=None, path="/")` |
| TP-02 | Bare repo URL with trailing slash | `https://github.com/slaclab/my-skill/` | Same as TP-01 |
| TP-03 | Bare repo URL with .git suffix | `https://github.com/slaclab/my-skill.git` | Same as TP-01 |
| TP-04 | Tree URL with branch + path | `https://github.com/owner/repo/tree/main/plugins/x` | `branch="main", path="plugins/x"` |
| TP-05 | Tree URL with nested path | `https://github.com/o/r/tree/main/a/b/c` | `path="a/b/c"` |
| TP-06 | Tree URL, branch only, no path | `https://github.com/o/r/tree/develop` | `branch="develop", path="/"` |
| TP-07 | HTTP (not HTTPS) URL | `http://github.com/o/r` | Parses successfully (normalise to https) |
| TP-08 | Non-GitHub URL | `https://gitlab.com/o/r` | Raises `ValueError` / returns error |
| TP-09 | Malformed URL (no repo) | `https://github.com/owner` | Raises `ValueError` |
| TP-10 | URL with query params | `https://github.com/o/r?tab=readme` | Strips params, parses correctly |
| TP-11 | URL with fragment | `https://github.com/o/r#readme` | Strips fragment, parses correctly |
| TP-12 | URL-encoded path | `https://github.com/o/r/tree/main/my%20skill` | `path="my skill"` (decoded) |
| TP-13 | Branch name with slash (ambiguous) | `https://github.com/o/r/tree/feature/v2/src` | Document expected behavior per decision; greedy parse or fallback |

**File: `backend/tests/test_metadata_extractor.py`**

| ID | Test | Input (raw files) | Expected |
|---|---|---|---|
| TP-20 | skill.md frontmatter with all fields | `skill.md` with YAML name, description, platforms, version | All fields populated from frontmatter |
| TP-21 | CLAUDE.md frontmatter fallback | No `skill.md`; `CLAUDE.md` with frontmatter | Fields from CLAUDE.md |
| TP-22 | package.json name/version | No markdown frontmatter; `package.json` with name and version | `name` from package.json, `version` from package.json |
| TP-23 | pyproject.toml name/version | No other files; `pyproject.toml` with `[project]` table | name and version from pyproject.toml |
| TP-24 | Priority: skill.md beats package.json | Both present with different names | skill.md name wins |
| TP-25 | Description from README first paragraph | No frontmatter description; `README.md` with heading then paragraph | First non-heading paragraph extracted |
| TP-26 | Platform inference from CLAUDE.md presence | `CLAUDE.md` exists but has no `platforms` frontmatter | `compatible_platforms` includes `"claude-code"` |
| TP-27 | Platform inference from package.json deps | `package.json` with `openai` in dependencies | `compatible_platforms` includes `"openai"` |
| TP-28 | No recognised files | Empty directory listing | Returns warning flag, all fields None except defaults |
| TP-29 | Frontmatter with no YAML block | `skill.md` with no `---` markers | Falls through to next priority source |
| TP-30 | Malformed YAML frontmatter | `skill.md` with invalid YAML | Graceful fallback, no crash |
| TP-31 | Malformed package.json | Invalid JSON | Graceful fallback |
| TP-32 | Malformed pyproject.toml | Invalid TOML | Graceful fallback |
| TP-33 | readme_html from directory README | Directory has `README.md` | `readme_html` populated |
| TP-34 | readme_html fallback to repo root | Directory has no README; repo root has one | Repo root README used |
| TP-35 | License from repo API | Repo metadata has `license.spdx_id = "MIT"` | `license = "MIT"` |

**File: `backend/tests/test_github_scanner.py`** (respx mocked)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| TP-40 | Successful scan with all files | Mock repo + contents + file fetches | `RawScanResult` with all file contents |
| TP-41 | Repo not found (404) | Mock 404 on repo endpoint | `GitHubFetchError("not found")` |
| TP-42 | Path not found (404) | Repo exists, path 404 | `GitHubFetchError("path not found")` |
| TP-43 | Partial file failures | 2 of 5 files return 404 | `RawScanResult` with available files only |
| TP-44 | GitHub timeout | Mock httpx timeout | `GitHubFetchError` with timeout message |
| TP-45 | Rate limit (403) | Mock 403 with `X-RateLimit-Remaining: 0` | Specific rate-limit error with retry-after |
| TP-46 | Empty directory | Contents endpoint returns empty array | `RawScanResult` with no files |
| TP-47 | Large directory (100+ files) | Contents returns 100 entries | Only recognised filenames fetched (not all 100) |
| TP-48 | Base64 file content decoding | Contents endpoint returns base64-encoded file | Content correctly decoded to UTF-8 |
| TP-49 | Parallel fetch performance | Mock 5 files with 200ms delay each | Total time < 1.5s (parallel, not 5 x 200ms = 1s sequential) |

**File: `backend/tests/test_github_scanner_discover.py`** (respx mocked)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| TP-50 | Discovery finds 3 skill dirs | Tree has 3 dirs with CLAUDE.md | Returns 3 SkillSnapshots |
| TP-51 | Discovery with no skill dirs | Tree has no skill.md or CLAUDE.md | Returns empty list with warning |
| TP-52 | Discovery capped at 20 | Tree has 30 dirs with CLAUDE.md | Returns 20 + `capped: true` |
| TP-53 | Discovery with already-registered | 2 of 3 dirs already in DB | `already_registered` contains 2 slugs |
| TP-54 | Discovery on empty repo | Tree returns no entries | Returns empty list |

**File: `backend/tests/test_skill_crud.py`** (extend existing)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| TP-60 | Create skill with skill_path | `SkillCreate(repo_url=..., skill_path="/plugins/x")` | Skill created with `skill_path="/plugins/x"` |
| TP-61 | Create skill default path | `SkillCreate(repo_url=...)` (no skill_path) | `skill_path="/"` |
| TP-62 | Duplicate repo_url + skill_path | Two creates with same repo_url and path | Second raises/returns 409 with existing slug |
| TP-63 | Same repo_url, different skill_path | Two creates with same repo but different paths | Both succeed |
| TP-64 | skill_path validation: traversal | `skill_path="/../../../etc/passwd"` | Rejected (validation error) |
| TP-65 | skill_path validation: max length | 501-char path | Rejected |
| TP-66 | skill_path validation: valid chars | `skill_path="/plugins/my-skill_v2.0"` | Accepted |

**File: `backend/tests/test_scan_endpoint.py`** (integration, httpx.AsyncClient + respx)

| ID | Test | Scenario | Expected |
|---|---|---|---|
| TP-70 | GET /api/github-scan bare URL | Valid repo URL | 200 with SkillSnapshot |
| TP-71 | GET /api/github-scan tree URL | Valid tree/branch/path URL | 200 with SkillSnapshot for that path |
| TP-72 | GET /api/github-scan invalid URL | Non-GitHub URL | 422 |
| TP-73 | GET /api/github-scan repo 404 | Valid format, repo doesn't exist | 404 |
| TP-74 | GET /api/github-scan discover=true | Bare repo URL with discover | 200 with SkillSnapshot[] |
| TP-75 | GET /api/github-scan no url param | Missing url query param | 422 |

### Frontend Tests (vitest/jest + React Testing Library)

**File: `frontend/__tests__/submit-form.test.tsx`**

| ID | Test | Scenario | Expected |
|---|---|---|---|
| TP-80 | URL blur triggers scan | Type URL, blur | Fetch to `/api/github-scan` called |
| TP-81 | Fields populated from scan response | Mock scan returns full snapshot | Name, description, platforms, version, license fields populated |
| TP-82 | Warning shown when no skill files | Mock scan returns `warning: true` | Warning banner visible |
| TP-83 | 409 duplicate shows link | Mock submit returns 409 with slug | Error message contains link to existing skill |
| TP-84 | Bare URL shows discovery checklist | Mock scan with discover returns 3 skills | Checklist rendered with 3 items |
| TP-85 | Already-registered skills pre-deselected | Discovery response includes `already_registered` | Those items shown as disabled/deselected |
| TP-86 | Bulk submit sends per-skill | Select 2 of 3 discovered skills, submit | Two POST calls made |
| TP-87 | Partial bulk failure shown | 1 of 2 POSTs fails | Success and failure shown per-skill |
| TP-88 | Edit auto-populated field | Populate from scan, edit name | Edited name submitted (not scan value) |
| TP-89 | skill_path included in submit payload | Submit from tree URL scan | POST body includes `skill_path` |

### Manual / Integration Tests

| ID | Test | Steps |
|---|---|---|
| TP-90 | End-to-end bare repo submission | Submit `https://github.com/yee379/dotclaude` via UI, verify skill created with `path="/"`, verify detail page shows path |
| TP-91 | End-to-end subdirectory submission | Submit `https://github.com/slaclab/slac-agent-plugin-marketplace/tree/main/plugins/coding-orchestrator`, verify fields auto-populated, submit, verify `skill_path` stored |
| TP-92 | Duplicate rejection E2E | Submit same URL twice, verify 409 with link on second attempt |
| TP-93 | Discovery mode E2E | Submit bare repo URL with known multi-skill repo, verify checklist, select subset, bulk submit |
| TP-94 | Backward compatibility | Verify all existing skills (path="/") still accessible via API and UI after migration |
| TP-95 | Rate limit behavior | With no GitHub token, trigger multiple rapid scans, verify graceful degradation |

### Test Coverage Targets

| Module | Target | Rationale |
|---|---|---|
| `GitHubURLParser` | 100% line + branch | Pure function, all edge cases enumerable |
| `MetadataExtractor` | 95%+ line | Pure transformation, critical business logic |
| `GitHubScanner` | 90%+ line (with respx mocks) | I/O-heavy but must cover error paths |
| `Skill model (compound index)` | Covered by TP-60..66 | Data integrity critical path |
| `GET /api/github-scan` endpoint | Covered by TP-70..75 | Integration layer |
| `SubmitForm` component | Covered by TP-80..89 | User-facing critical path |

---

## Board Review

**Verdict:** CLEAR WITH WARNINGS
**Date:** 2026-04-21
**Rounds:** 2

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | ⚠️ WARN | Y | GitHub API endpoints verified correct; python-frontmatter healthy; tree truncation risk confirmed and addressed; branch-slash limitation documented |
| codebase-arch-review | ⚠️ WARN | Y (ADRs) | 6 ADRs written; index drop ordering and auth gate resolved; refetch path-awareness deferred as v1 known gap |
| codebase-eng-review | ⚠️ WARN | Y (test plan) | All 6 blocking issues resolved; test plan added (95 cases); minor test gaps for auth 401 and scan-time duplicate |
| codebase-doc-review | ⚠️ WARN | Y | 9 doc gaps found; README + guides page addressed in plan; 5 gaps deferred to closeout |
| security-review | ✅ PASS | Y | SSRF, path traversal, auth all resolved; XSS already mitigated by DOMPurify |
| codebase-ux-review | ⚠️ WARN | Y | Scan trigger, duplicate at scan-time, collapsed cards, timeout UX all addressed; discovery complexity managed with progressive disclosure |

**Accepted warnings:**
- Refetch method not path-aware for monorepo skills (v1 known gap — repo-root README used on refetch for skill_path != "/")
- Per-user throttle not specified on scan endpoint (mitigated by auth gate + App token 5000 req/hr)
- github-preview Next.js route uses GITHUB_TOKEN directly (pre-existing, not changed by this feature)
- 5 doc gaps deferred to /codebase-closeout: troubleshooting entries, PRD sections 4+5, CHANGELOG.md, CLAUDE.md

**ADRs written:** 6 (in docs/adr/)
**Unresolved decisions:** none

---

### Reviewer output

<details>
<summary>research-handbook — Round 1 (⚠️ WARN)</summary>

## Summary

GitHub API endpoints and rate limit figures are verified correct as of April 2026. The `python-frontmatter` library is healthy (v1.1.0, active repo, not archived). The biggest assumption risk is the recursive tree API truncation on large repos (confirmed: `truncated: true` on repos like linux/linux). The plan handles most cases well but has gaps around tree truncation, the Contents API 1000-file directory limit, and branch-name-with-slashes ambiguity. Two decisions required (one blocking, one judgement-call).

## Issues

- warning | GitHub API | Trees API uses branch name as tree_sha (convenience behavior, not formally documented — low risk)
- warning | GitHub API | Contents API returns error for directories with >1000 files; skill.md etc. are small but edge case exists
- warning | GitHub API | Files >1MB cannot be fetched via Contents API (Blobs API needed) — low risk for skill files
- blocking (resolved) | discovery | `truncated: true` not handled — addressed in FR-U12
- judgement-call (resolved) | url-parsing | Branch names with slashes — documented as known limitation
- warning | rate-limits | Discovery mode effectively requires App token (todo/001); unauthenticated discovery exhausts 60 req/hr budget instantly

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-arch-review — Round 2 (⚠️ WARN)</summary>

## Summary

Architecture review of todo/002 (directory-aware skill registration UX). The plan is well-structured with clean service boundaries (GitHubURLParser / GitHubScanner / MetadataExtractor), an appropriate data model evolution, and sound migration strategy. Six ADRs written to `docs/adr/`. All Round 1 blocking issues resolved. Three minor non-blocking issues remain: ADR-U04 migration sequence (now fixed), ADR-U06 concurrency cap (now fixed), refetch path-awareness (v1 known gap).

**Verdict: PASS WITH WARNINGS**

## Issues

- blocking (resolved) | migration | Beanie does not auto-drop old index; explicit drop_index("repo_url_1") now specified in FR-U5a
- blocking (resolved) | auth | Scan endpoint now requires Depends(get_current_user) per FR-U4a
- medium (resolved) | url-parsing | Branch ambiguity documented as known limitation
- low (resolved) | cache | cachetools.TTLCache specified in Slice 1
- low (open) | refetch | Existing refetch method not updated for skill_path != "/" — v1 known gap, tracked in Risk Register

## ADRs written
- docs/adr/adr-u01-github-scan-endpoint.md
- docs/adr/adr-u02-frontmatter-format.md
- docs/adr/adr-u03-github-api-file-fetch.md
- docs/adr/adr-u04-compound-unique-index.md
- docs/adr/adr-u05-scan-on-backend.md
- docs/adr/adr-u06-discovery-concurrency.md

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 2 (⚠️ WARN)</summary>

## Summary

All six Round 1 blocking issues resolved. Test plan added (95 cases across 8 test files). Five low-severity gaps: missing test for auth 401 (FR-U4a), missing test for scan-time duplicate (FR-U16), diagram/FR concurrency inconsistency (fixed), cache key missing discover flag (fixed), TP-52 flag name mismatch (fixed).

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-doc-review — Round 2 (⚠️ WARN)</summary>

## Summary

9 doc gaps identified in Round 1. DC-2 (README), DC-3 (guides page), DC-8 (ADRs) resolved. 5 gaps deferred to /codebase-closeout: DC-4 (troubleshooting), DC-5/DC-6 (PRD updates), DC-7 (CHANGELOG), DC-9 (CLAUDE.md).

**Closeout backlog:**
1. Add troubleshooting entries for 409 Conflict and wrong-directory-scanned
2. Update PRD Sections 4 and 5 with skill_path and GET /api/github-scan
3. Create CHANGELOG.md
4. Create project-level CLAUDE.md

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 2 (✅ PASS)</summary>

## Summary

All three Round 1 blocking issues resolved: SSRF (FR-U4b: parser validates + scanner constructs), path traversal (FR-U5 + Slice 4 CLI), auth (FR-U4a: Depends(get_current_user)). XSS already mitigated by DOMPurify in ReadmeRender. No new blocking issues.

**Accepted warnings:** per-user rate throttle not specified; github-preview frontend route still holds GITHUB_TOKEN directly (pre-existing).

## Status
PASS

</details>

<details>
<summary>codebase-ux-review — Round 1 (⚠️ WARN)</summary>

## Summary

Core flow (paste URL → scan → auto-populate → submit) is well-designed for technical users. One blocking issue resolved: explicit Scan button as primary trigger with Submit disabled during scan. Key UX improvements added: placeholder shows both URL formats, duplicate check at scan time, collapsed cards in discovery mode, client-side timeouts with retry, distinct error states for 4 failure modes.

## Status
PASS WITH WARNINGS

</details>
