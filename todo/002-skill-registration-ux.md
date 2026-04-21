# 002 — Improved Skill Registration UX: Directory-Aware Submission

**Status:** ⬜ Open

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
- FR-U2: On URL blur (or explicit "Scan" button), backend fetches:
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
- FR-U4: A new backend endpoint `GET /api/github-scan?url=<github_url>` returns the full extracted metadata snapshot.
- FR-U5: Skill model adds `skill_path: str` (default `/`). Uniqueness index on `(repo_url, skill_path)`.
- FR-U6: `POST /api/skills` accepts `skill_path` in the request body.
- FR-U7: If the scanned directory contains no recognisable skill files (`skill.md`, `CLAUDE.md`, `README.md`, `package.json`, `pyproject.toml`), the endpoint returns a warning (not an error) — user can still submit with manual metadata.
- FR-U8: The stored `skill_path` is included in the `SkillOut` schema and surfaced on the detail page.
- FR-U9: `GET /api/skills/:slug` returns `skill_path` so the CLI install command knows which directory to fetch.
- FR-U10: Duplicate (repo_url + skill_path) submissions return HTTP 409 with a link to the existing entry.
- FR-U11: When a bare repo URL is submitted (path `/`), the backend additionally scans the repo recursively for skill directories — any directory containing `skill.md` or `CLAUDE.md` is treated as a candidate skill.
- FR-U12: `GET /api/github-scan?url=<repo_url>&discover=true` returns a list of `SkillSnapshot[]` — one per discovered skill directory — instead of a single snapshot.
- FR-U13: The submit form has a "Scan entire repo" mode: when a bare repo URL is entered and discovery returns multiple skills, the form renders a checklist of discovered skills with the same auto-populated + editable fields for each. The user selects which ones to submit and can edit each independently before bulk-submitting.
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
  ├── For each candidate directory (parallel, up to 10 concurrent):
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

**`GET /api/github-scan` route handler (new, `frontend/app/api/github-scan/route.ts`)**
- Replaces the existing `/api/github-preview` for the submit form
- Accepts full GitHub URL, returns full SkillSnapshot

**SubmitForm (modify, `frontend/components/submit-form.tsx`)**
- Replace repo_url input with a single URL field accepting both formats
- On blur: call `/api/github-scan`, populate all fields
- Show warning if no skill files found

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
- `GitHubURLParser` + `GitHubScanner` + `MetadataExtractor` backend services
- `GET /api/github-scan` endpoint
- Unit tests for parser + extractor

**Slice 2 — Frontend form (single skill)**
- Replace submit form URL input with directory-aware input
- On blur: call `/api/github-scan`, populate fields with preview
- Warning state for missing skill files
- Handle 409 duplicate with link to existing entry

**Slice 3 — Repo discovery + bulk submit**
- `discover=true` param on `/api/github-scan`; recursive tree walk + parallel per-dir scan
- Submit form discovery mode: checklist UI, per-skill editable fields, bulk submit
- Already-registered skills shown as pre-deselected with "view" link

**Slice 4 — Install support**
- Add `skill_path` to `SkillOut` schema
- Update `/agent-knowledge-hub install` skill to use `skill_path` for sparse directory fetch

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub API rate limit on scan (10 calls per submission) | Medium | Medium | GitHub App token (todo/001); cache scan results 60s |
| Branch names with slashes break URL parsing | Medium | Low | Encode/decode correctly; test with known edge cases |
| Frontmatter not present in most existing skills | High | Low | Graceful fallback chain; warning not error |
| Large directory listing (100+ files) slows scan | Low | Low | Only fetch recognised filenames, not all files |
| Compound index migration fails on existing data | Low | High | All existing entries have path="/"; index is safe to create |

---

## Definition of Done

- [ ] `skill_path` field on Skill model, compound unique index on (repo_url, skill_path)
- [ ] `GitHubURLParser` handles bare repo + tree/branch/path URLs, unit tested
- [ ] `MetadataExtractor` priority rules unit tested for all field extraction paths
- [ ] `GET /api/github-scan` returns full snapshot in < 3s for a 10-file directory
- [ ] Submit form: single URL input, auto-populates all fields on blur, shows warning if no skill files
- [ ] 409 on duplicate (repo_url + skill_path) with link to existing entry
- [ ] `skill_path` returned in `SkillOut` and visible on detail page
- [ ] Existing bare-repo submissions unaffected (path defaults to `/`)
- [ ] `python-frontmatter` added to `requirements.txt`
