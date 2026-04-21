# 001 — Private/Internal GitHub Repos, Access Model, and Fork Provenance

**Status:** 🔍 Reviewed
**Depends on:** #002 (Slice 2 requires GitHubScanner from #002 to be in place)

---

## Problem & Goal

**Problem:** The catalog assumes all skills are in public GitHub repos. Many existing SLAC skills live in private/internal repos under the slaclab enterprise org. GitHub API returns 404 for these without auth — indistinguishable from a nonexistent repo. Additionally, there is no model for fork lineage: a fork of a skill is a separate repo with shared origin, but the catalog treats it as an unrelated entry.

**Goal:** Support submission, display, and metadata re-fetch for private/internal GitHub repos via a GitHub App token. Show a "SLAC Internal" badge with access instructions for users who can't clone the repo. Model fork provenance with a `forked_from_url` field auto-populated at submission.

**Success metric:**
- A SLAC skill in a private slaclab repo can be submitted and its metadata fetched without manual entry
- Users see a clear "SLAC Internal" badge + access instructions on private skill cards and detail pages
- A forked skill shows its origin repo on the detail page

**Out of scope:**
- Snapshotting skill.md content for offline use
- Multi-level fork graph / full lineage tree (v2)
- Per-user GitHub OAuth tokens

**Constraints:**
- GitHub App must be installed on the slaclab enterprise org by an org admin
- App private key stored in vault; injected as env var in backend

---

## User Stories

1. As a skill author with a private slaclab repo, I want to submit it by URL and have GitHub metadata fetched automatically, so I don't have to enter name/description/stars manually.
2. As a skill author, I want the catalog to distinguish "repo not found" from "repo is private", so the error message is actionable.
3. As a consumer, I want to see a "SLAC Internal" badge on skills in private repos, so I know upfront I may need to request access before cloning.
4. As a consumer, I want a link to SLAC GitHub access instructions on private skill cards, so I know how to get access without contacting the author.
5. As a skill author, I want to re-fetch metadata for a private repo skill (stars, last commit, README) using the GitHub App, so I don't have to update it manually.
6. As a skill author, I want to submit a fork of an existing skill, and have the catalog auto-detect and populate the `forked_from_url` field from GitHub, so the relationship is recorded without manual input.
7. As a consumer, I want to see "Forked from <repo link>" on a skill's detail page when it is a fork, so I understand its provenance.
8. As a consumer, I want to see all catalog entries that are forks of a given skill, so I can compare variants.
9. As an admin, I want to manually set or override `forked_from_url` on any skill entry, so I can fix incorrectly detected fork relationships.
10. As a skill author with a public fork of a private upstream, I want the catalog to record the upstream URL even though it's inaccessible, so provenance is preserved.

---

## Requirements

### Functional

- FR-P1: Backend supports a GitHub App installation token for authenticated GitHub API calls. Falls back to `GITHUB_TOKEN` (PAT), then unauthenticated.
- FR-P2: On submission, if unauthenticated fetch returns 404, backend retries with GitHub App token. If retry succeeds, repo is marked `visibility: internal`. If retry also fails, repo is treated as nonexistent (show AC-2 error).
- FR-P3: Skill model adds `visibility` enum: `public` | `internal` | `private`. Default: `public`. Set to `internal` when GitHub App token was required to fetch.
- FR-P4: Skill cards and detail pages display a "SLAC Members Only" badge when `visibility == internal`, linking to a configurable access instructions URL (default: `/guides/slac-github-access` — a plain-language guide hosted in the catalog that explains how to link a GitHub account via SLAC SSO). The raw SSO URL (`https://github.com/enterprises/slaclab/sso`) is referenced within the guide, not used as the badge link directly.
- FR-P5: Re-fetch endpoint uses GitHub App token for `visibility: internal` skills.
- FR-P6: On submission, backend calls `GET /repos/{owner}/{repo}` and checks `fork: true` in the response. If true, fetches `parent.html_url` and stores it as `forked_from_url`.
- FR-P7: Skill model adds `forked_from_url: str | null`. Indexed for lookup.
- FR-P8: Skill detail page shows "Forked from **owner/repo**" (human-readable, extracted from URL) as a clickable link when `forked_from_url` is set. If the upstream repo is also in the catalog, link to its catalog detail page instead of GitHub.
- FR-P9: `GET /api/skills?forked_from=<url>` returns all catalog entries forked from that repo URL.
- FR-P10: `PATCH /api/skills/:slug` allows owner/admin to set/override `forked_from_url`.
- FR-P11: Submit form shows a live preview for internal repos (same as public) when the GitHub App has access. No special UI needed.
- FR-P12: SiteSettings stores `github_access_instructions_url` (configurable by admin); default value: `/guides/slac-github-access`. Used in the "SLAC Members Only" badge link.
- FR-P13: `GET /api/github-scan` (from #002) uses the same App token fallback chain as `GitHubFetcher`. `GitHubScanner` shares the `GitHubAppClient` helper — same token, same cache. If the App token is required to fetch the repo, the returned `SkillSnapshot` includes `visibility: internal`.
- FR-P14: Discovery mode (`discover=true`) also uses the App token when scanning private repos. The recursive tree walk (`GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1`) and all per-directory scans use the installation token. Discovery on a private repo is only available if the App is installed and configured.
- FR-P15: `GET /api/skills` accepts an optional `visibility` filter parameter (`public`, `internal`, or `all`; default `all`). The skill listing page exposes this as a filter control (e.g., toggle or dropdown: "All / Public only / SLAC Members Only") so scientists can discover or exclude internal skills.
- FR-P16: Skill detail page sidebar shows a "Forks in catalog" section when `GET /api/skills?forked_from={this_skill.repo_url}` returns results. Displays count and a "View all" link to the filtered list. Omitted when fork count is zero.
- FR-P17: When the submit form preview detects `visibility: internal`, an informational banner is shown below the preview: "This repo requires SLAC GitHub access. Users without access will see a 'SLAC Members Only' badge with instructions on how to get access." The `GitHubPreview` response includes a `visibility` field to enable this.

### Non-Functional

- NFR-P1: GitHub App token generation adds < 500ms to submission latency (token is cached per installation for its 1h TTL).
- NFR-P2: App private key never logged or exposed in error messages.
- NFR-P3: Fallback chain (App → PAT → unauth) is transparent to the user.

### Acceptance Criteria

- AC-P1: Given a private slaclab repo URL, when submitted, the GitHub App token is used and metadata is fetched successfully — the skill appears with `visibility: internal` and a "SLAC Members Only" badge.
- AC-P2: Given a genuinely nonexistent repo URL, even after App token retry, the form shows: _"This repo couldn't be found. Check the URL. If this is a private repo outside the slaclab GitHub organization, it can't be auto-fetched — you can still submit with a manual description."_ — not a badge.
- AC-P3: Given a public fork of another repo, when submitted, `forked_from_url` is auto-populated with the parent repo URL and shown on the detail page.
- AC-P4: Given a skill with `forked_from_url` set, `GET /api/skills?forked_from=<url>` returns it.
- AC-P5: Given an admin, they can set `forked_from_url` to any value via PATCH.

---

## Architecture

### GitHub App Token Flow

The same fallback chain applies to both `GitHubFetcher` (submission/refetch) and `GitHubScanner` (scan endpoint from #002). Both share a single `GitHubAppClient` instance with a cached installation token (1h TTL).

```
Any GitHub API call (fetch, scan, or discover)
  │
  ▼
GitHubAppClient.get_token()   ← shared, cached per installation
  │  1. Try unauthenticated
  │     → 200: return result (visibility=public)
  │     → 404: continue
  │  2. Try GITHUB_TOKEN (PAT) if set
  │     → 200: return result (visibility=public, token used for rate limit)
  │     → 404: continue
  │  3. Try GitHub App installation token
  │     → generate JWT → GET /app/installations → POST /installations/{id}/access_tokens
  │     → 200: return result (visibility=internal)
  │     → 404: raise GitHubFetchError("not found")
```

### GitHub App Setup (one-time)
1. Create GitHub App in slaclab org: read-only `Contents` + `Metadata` permissions
2. Install on slaclab org (all repos or selected)
3. Store `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` (PEM) in vault
4. Add to backend k8s secret

### Data Model Changes

```python
class VisibilityEnum(str, Enum):
    public = "public"
    internal = "internal"   # fetched via GitHub App (slaclab private)
    private = "private"     # manually submitted, no fetch possible

class Skill(Document):
    # new fields
    visibility: VisibilityEnum = VisibilityEnum.public
    forked_from_url: Optional[str] = None
```

### API Changes

```
GET /api/skills?forked_from=<repo_url>   # new filter param
PATCH /api/skills/:slug                  # forked_from_url now patchable
```

---

## ADRs

### ADR-P01: GitHub App over per-user OAuth

**Status:** Accepted

| Option | Pros | Cons |
|---|---|---|
| GitHub App (org-level) | One setup, works for all slaclab repos, no per-user friction | Requires org admin, all-or-nothing access |
| Per-user OAuth token | Granular, user controls access | Complex UX, token storage, refresh flow |
| Shared PAT | Simple | Tied to one person's account, rotation risk |

**Decision:** GitHub App — org-level installation, read-only `Contents` + `Metadata`. Single setup by an admin, transparent to submitters.

### ADR-P02: visibility field over is_private bool

**Status:** Accepted

A bool `is_private` doesn't capture the distinction between "slaclab internal" (accessible via App) and "truly private" (manually submitted, no fetch). Three-value enum `public/internal/private` allows correct badge display and fetch strategy selection.

### ADR-P03: Shared GitHubAppClient between GitHubFetcher and GitHubScanner

**Status:** Accepted

**Context:** todo/002 introduces `GitHubScanner` in `backend/app/services/github.py` alongside the existing `GitHubFetcher`. Both need to make authenticated GitHub API calls. If each creates its own token, we get double token generation and potentially double rate-limit consumption.

| Option | Pros | Cons |
|---|---|---|
| Shared singleton `GitHubAppClient` | One token generated, one cache, consistent fallback logic | Slight coupling between two services |
| Independent token per class | Fully decoupled | Double token requests, two caches to invalidate |

**Decision:** Shared singleton. `GitHubAppClient` is instantiated once at module level in `backend/app/services/github.py` and imported by both `GitHubFetcher` and `GitHubScanner`. Installation token cached with 1h TTL; both services benefit from the same warm cache.

**GitHubFetcher (modify `backend/app/services/github.py`)**
- Add fallback chain: unauth → PAT → App token
- Add `GitHubAppClient` helper: generates installation JWT, caches access token (1h TTL)
- Returns `GitHubSnapshot` + `visibility` field
- Testable in isolation: Yes (respx mocks)

**GitHubAppClient (new, `backend/app/services/github.py`)**
- Responsibility: Generate GitHub App installation JWT, exchange for access token, cache with 1h TTL
- Dependency: `PyJWT[crypto]>=2.8` (RS256 signing requires the `cryptography` extra)
- Interface: `async get_token() → str | None` — returns token or None if App not configured
- Cache must use `asyncio.Lock` to prevent thundering-herd on concurrent token refresh
- On 401 during a GitHub API call, invalidate cached token and retry once (handles mid-request expiry)
- Shared singleton used by both `GitHubFetcher` and `GitHubScanner` (#002)
- Testable in isolation: Yes (mock JWT generation + HTTP exchange)

**Skill model (modify `backend/app/models/skill.py`)**
- Add `visibility: VisibilityEnum`
- Add `forked_from_url: Optional[str]`
- Add sparse index on `forked_from_url` (most values are null; sparse index only indexes non-null)
- Add compound index `{visibility: 1, submitted_at: -1}` for visibility filtering

**SkillRepository (modify `backend/app/services/skill.py`)**
- `list()`: add `forked_from` filter param; add `visibility` filter param
- `create()`: store `visibility` and `forked_from_url` from GitHubSnapshot
- `refetch()`: use App token directly for `visibility: internal` skills (skip unauth/PAT steps)
- Add `_normalize_github_url()` helper: strip trailing slash, force https, strip `.git`, lowercase owner/repo. Apply on write (create, update) and on query (forked_from filter)

**GitHubSnapshot (modify `backend/app/services/github.py`)**
- Add `visibility: VisibilityEnum = VisibilityEnum.public`
- Add `forked_from_url: Optional[str] = None`

**Schemas (modify `backend/app/schemas/skill.py`)**
- `SkillOut`: add `visibility` and `forked_from_url`
- `SkillListOut`: add `visibility` and `forked_from_url`
- `SkillUpdate`: add `forked_from_url: Optional[str]`

**Router (modify `backend/app/routers/skills.py`)**
- `_skill_to_out()` and `_skill_to_list_out()`: include `visibility` and `forked_from_url`
- `list_skills()`: add `forked_from` and `visibility` query parameters
- New endpoint: `GET /api/github-preview?repo_url=...` — uses shared `GitHubAppClient` fallback chain; returns `GitHubPreview` including `visibility` field

**Frontend github-preview route (modify `frontend/app/api/github-preview/route.ts`)**
- Replace direct GitHub API call with proxy to new backend `GET /api/github-preview` endpoint
- Remove duplicated GitHub auth logic from frontend

**Frontend types (modify `frontend/types/skill.ts`)**
- `Skill` interface: add `visibility: "public" | "internal" | "private"` and `forked_from_url: string | null`
- `SkillUpdate` interface: add `forked_from_url?: string`
- `GitHubPreview` interface: add `visibility: "public" | "internal" | "private"`

**Migration script (new, `backend/scripts/001_add_visibility_fields.py`)**
- One-shot script: set `visibility: "public"` and `forked_from_url: null` on all existing Skill documents
- Create sparse index on `forked_from_url`
- Create compound index `{visibility: 1, submitted_at: -1}`
- Idempotent (safe to re-run)

**Config (modify `backend/app/config.py`)**
- Add `github_app_id: Optional[str]`
- Add `github_app_private_key: Optional[str]`

**Frontend SkillCard + SkillDetail (modify)**
- Show "SLAC Members Only" badge when `visibility == internal`
- Show "Forked from **owner/repo**" (linked) when `forked_from_url` is set
- Show "Forks in catalog" section on detail sidebar when forks exist
- Show visibility filter on skill listing page
- Show internal repo warning banner on submit form

---

## Delivery Slices

**Slice 1 — Data model + fork detection**
- Add `visibility` + `forked_from_url` to Skill model with defaults
- Add `_normalize_github_url()` helper
- Extend `GitHubSnapshot` with `visibility` and `forked_from_url`
- Auto-populate `forked_from_url` from GitHub API on submission (public repos only first)
- Update `SkillOut`, `SkillListOut`, `SkillUpdate` schemas with new fields
- Update `_skill_to_out()` and `_skill_to_list_out()` router helpers
- Update `frontend/types/skill.ts` with new fields
- Add `forked_from` and `visibility` filter params to list endpoint
- Show "Forked from" on detail page
- Write and run migration script for existing documents + indexes

**Slice 2 — GitHub App integration**
- Add `PyJWT[crypto]>=2.8` dependency
- `GitHubAppClient`: JWT generation, installation token fetch, 1h cache, `asyncio.Lock` for thread-safety
- Fallback chain in both `GitHubFetcher` (submission/refetch) and `GitHubScanner` (scan/discovery from #002) — shared `GitHubAppClient` singleton
- `visibility: internal` set in `SkillSnapshot` when App token was required
- Optimized refetch: skip to App token for known-internal skills
- New backend endpoint: `GET /api/github-preview?repo_url=...` using shared fallback chain
- Replace frontend `github-preview` route with proxy to backend endpoint
- Vault secrets + k8s secret for `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY`
- Note: #002 must ship before or alongside this slice for the scanner integration to be testable

**Slice 3 — Frontend badges + instructions + fork UI**
- "SLAC Members Only" badge on card and detail
- `github_access_instructions_url` in SiteSettings (default: `/guides/slac-github-access`)
- Badge links to configurable URL
- Visibility filter on skill listing page (FR-P15)
- "Forks in catalog" section on detail page sidebar (FR-P16)
- Submit form internal repo warning banner (FR-P17)
- `GitHubPreview` response includes `visibility` field for submit form

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub App install rejected by org admin | Medium | High | Document request process; PAT fallback still works for public repos |
| App private key leaked | Low | Critical | Store only in vault; never log; rotate immediately if exposed |
| Fork detection false positive | Low | Low | Admin can override `forked_from_url` via PATCH |
| App token cache invalidation bug | Low | Medium | Unit test token expiry; fall back to generating new token on 401 |

---

## Definition of Done

- [ ] `visibility` and `forked_from_url` fields on Skill, indexed
- [ ] GitHubFetcher fallback chain tested with mocks (unauth → PAT → App)
- [ ] GitHubScanner (#002) uses shared GitHubAppClient — fallback chain tested for scan + discovery
- [ ] App token generation + caching unit tested (including expiry + refresh)
- [ ] `forked_from` filter on list endpoint tested
- [ ] "SLAC Members Only" badge shown in frontend for `visibility=internal`
- [ ] "Forked from" shown on detail page as human-readable `owner/repo` link
- [ ] Visibility filter exposed on skill listing page (FR-P15)
- [ ] "Forks in catalog" section on detail page sidebar (FR-P16)
- [ ] Submit form shows informational banner for internal repos (FR-P17)
- [ ] `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` added to vault + k8s secrets for dev/stage/prod
- [ ] SiteSettings `github_access_instructions_url` configurable by admin
- [ ] No private key in logs or error responses — error handler middleware redacts tracebacks containing PRIVATE_KEY (NFR-P2 enforcement)
- [ ] `GET /api/github-preview` rate-limited (slowapi or equivalent, 10 req/min per IP)
- [ ] `forked_from_url` validated as `https://github.com/*` URL in `SkillUpdate` Pydantic schema
- [ ] `github_access_instructions_url` validated as http/https URL in SiteSettings schema (Pydantic `HttpUrl`)
- [ ] Private repo scan via `/api/github-scan` returns `visibility: internal` in SkillSnapshot
- [ ] Discovery mode (`discover=true`) works on private repos when App is configured
- [ ] ADRs committed to `docs/adr/`: adr-p01-github-app-over-oauth.md, adr-p02-visibility-enum.md, adr-p03-shared-github-app-client.md
- [ ] GitHub App setup runbook written to `docs/runbooks/github-app-setup.md` (GitHub Enterprise App creation, vault secrets, k8s secret injection, verification)
- [ ] `backend/.env.example` updated with `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY` (with comments noting they are optional)
- [ ] `README.md` updated to mention private/internal repo support and the "SLAC Members Only" badge
- [ ] `SkillOut`, `SkillListOut`, and `SkillUpdate` schemas include `visibility` and `forked_from_url`; router helpers updated

---

## Test Plan

_Added by eng review (round 1). 28 test cases across 7 groups._

### Group 1: GitHubAppClient unit tests (`test_github_app_client.py`)

| # | Test | Technique | Validates |
|---|------|-----------|-----------|
| T01 | `get_token()` returns None when `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` not set | Unit, no mocks | Graceful degradation when App not configured |
| T02 | `get_token()` generates valid JWT, exchanges for installation token, returns token | respx mock `GET /app/installations` + `POST /installations/{id}/access_tokens` | Happy path token generation |
| T03 | `get_token()` returns cached token on second call within TTL | respx mock (assert single call) | Cache hit — no duplicate HTTP requests |
| T04 | `get_token()` refreshes token after TTL expires | Freeze time past 1h, respx mock | Cache expiry + refresh |
| T05 | `get_token()` handles invalid PEM key format gracefully | Bad key string in config | Error handling — raises descriptive error, does not crash |
| T06 | `get_token()` handles 401 from `/app/installations` (bad App ID) | respx mock 401 | Error handling — returns None or raises, does not loop |
| T07 | Concurrent `get_token()` calls result in single HTTP exchange | `asyncio.gather` of 10 calls + respx call count assertion | `asyncio.Lock` prevents thundering herd |
| T08 | Token invalidation on 401 during API call triggers re-fetch | Mock first token returning 401, second succeeding | Mid-request expiry recovery |

### Group 2: GitHubFetcher fallback chain tests (`test_github_fetcher.py`, extend existing)

| # | Test | Technique | Validates |
|---|------|-----------|-----------|
| T09 | Public repo: unauthenticated 200 — returns `visibility=public` | respx mock 200 | No fallback needed for public repos |
| T10 | Private repo, no App configured: unauthenticated 404 — raises GitHubFetchError | respx mock 404 + no App config | Existing behavior preserved |
| T11 | Private repo, App configured: unauthenticated 404 → App token 200 — returns `visibility=internal` | respx mock 404 then 200 on retry with auth header | Full fallback chain, internal detection |
| T12 | Nonexistent repo, App configured: unauthenticated 404 → App token 404 — raises GitHubFetchError("not found") | respx mock 404 on both attempts | Distinguishes nonexistent from private |
| T13 | Public fork: response has `fork: true` + `parent.html_url` — returns `forked_from_url` | respx mock with fork data | Fork detection on public repos |
| T14 | Non-fork repo: response has `fork: false` — returns `forked_from_url=None` | respx mock without fork data | No false positives |
| T15 | Fork with private parent: `parent.html_url` is set but parent fetch would 404 — still stores URL | respx mock | Provenance preserved even when upstream is inaccessible (User Story 10) |
| T16 | Refetch of internal skill: skips unauth/PAT, goes straight to App token | respx mock + assert no unauthenticated call made | Optimized refetch path (FR-P5) |

### Group 3: SkillRepository + forked_from filter (`test_skill_crud.py`, extend existing)

| # | Test | Technique | Validates |
|---|------|-----------|-----------|
| T17 | `create()` stores `visibility` and `forked_from_url` from GitHubSnapshot | Integration test with mongomock | Fields persisted correctly |
| T18 | `list(forked_from=url)` returns only skills with matching `forked_from_url` | Create 3 skills (2 forks, 1 not), filter | forked_from filter works |
| T19 | `list(forked_from=url)` with URL variants (trailing slash, `.git`, HTTP) still matches | Normalized URLs | URL normalization on query |
| T20 | `list(visibility="internal")` returns only internal skills | Create mix of public/internal skills | Visibility filter works |
| T21 | PATCH `forked_from_url` by owner succeeds | Update skill via repository | FR-P10 |
| T22 | PATCH `forked_from_url` normalizes URL on write | PATCH with `http://` URL, assert stored as `https://` | URL normalization on write |

### Group 4: API endpoint tests (`test_api_skills.py`, new or extend)

| # | Test | Technique | Validates |
|---|------|-----------|-----------|
| T23 | `GET /api/skills?forked_from=<url>` returns filtered results | httpx TestClient | API-level forked_from filter |
| T24 | `GET /api/github-preview?repo_url=<private_url>` returns preview with `visibility: internal` | respx mock + httpx TestClient | Backend preview endpoint with fallback chain |
| T25 | `GET /api/github-preview?repo_url=<nonexistent>` returns 404 with descriptive error | respx mock 404 | Error message for nonexistent repos (AC-P2) |

### Group 5: Security tests (`test_security.py`, new)

| # | Test | Technique | Validates |
|---|------|-----------|-----------|
| T26 | Private key is not present in any error response body | Trigger GitHubAppClient errors, inspect response JSON | NFR-P2 |
| T27 | Private key is not present in log output | Capture log output during token generation failure, grep for key substring | NFR-P2 |

### Group 6: Migration script (`test_migration.py`, new)

| # | Test | Technique | Validates |
|---|------|-----------|-----------|
| T28 | Migration script sets `visibility: "public"` on existing documents and is idempotent | Run twice on test DB with existing skills | Data migration correctness |

### Group 7: Frontend (manual verification, Slice 3)

_These are visual/interaction tests verified during Slice 3 development:_

- "SLAC Members Only" badge visible on skill card when `visibility=internal`
- "SLAC Members Only" badge visible on skill detail page with link to instructions
- "Forked from owner/repo" shown on detail page as clickable link
- "Forks in catalog" section shown when forks exist, hidden when zero
- Visibility filter dropdown on skill listing page works
- Submit form shows internal repo warning banner after preview
- Frontend `github-preview` calls backend endpoint (no direct GitHub API call)

---

## Board Review

**Verdict:** CLEAR WITH WARNINGS
**Date:** 2026-04-21
**Rounds:** 1

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | ⚠️ WARN | N | PyJWT dep missing; fallback chain ordering; TTL from expires_at |
| codebase-arch-review | ⚠️ WARN | Y | Visibility from data["private"] not auth method; asyncio.Lock needed; ADR-P04 written |
| codebase-eng-review | ⚠️ WARN | Y | JWT dep + migration + frontend preview route (resolved); 28-case test plan added |
| codebase-doc-review | ⚠️ WARN | Y | 5 DoD gaps: ADRs, runbook, .env.example, README, schemas |
| security-review | ⚠️ WARN | Y | Rate-limit preview endpoint; validate forked_from_url URL; NFR-P2 enforcement |
| codebase-ux-review | ⚠️ WARN | Y | Badge text, SSO link, fork list UI, submit warning, FR-P15/16/17 added |

**Accepted warnings:** singleton DI trade-off (module-level `GitHubAppClient` kept for consistency with existing pattern); `private` enum value kept with no v1 write path (forward-compat); GITHUB_APP_PRIVATE_KEY as env var (acceptable for this threat model)
**ADRs written:** 1 (docs/adr/adr-p04-visibility-from-api-response.md)
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research-handbook — Round 1 (⚠️ WARN)</summary>

## Summary

Research-handbook review of todo/001 (private repos and fork provenance). Verified GitHub API assumptions for App JWT auth, installation tokens, fork detection, and the fallback chain. Found 2 blocking issues (JWT expiry claim in plan is wrong, new `PyJWT`+`cryptography` dependency not listed), 4 warnings (fallback chain ordering suboptimal, singleton pattern fragile for testing, installation token TTL incorrect in plan, `datetime.utcnow()` deprecated), and 1 simplification opportunity.

## Issues

### Blocking

- **blocking | dependencies | `PyJWT` and `cryptography` not in requirements.txt** — The plan specifies JWT generation for GitHub App auth (RS256 signing with a PEM private key). This requires `PyJWT` (or `jwt`) and `cryptography` as new dependencies. Neither appears in `backend/requirements.txt`. Without adding them, the implementation will fail at import time. The plan should explicitly list `PyJWT>=2.8.0` and `cryptography>=42.0.0` as new dependencies in a Dependencies section or in the delivery slice.

- **blocking | auth | Fallback chain makes 3 serial HTTP calls for every private repo — unauthenticated call always hits 404 first** — The plan's fallback chain (unauth -> PAT -> App token) means every private repo submission makes at least 2 wasted GitHub API calls (unauth 404, then PAT 404) before the App token succeeds. For the scan endpoint (potentially listing many repos), this triples latency and rate-limit consumption. The chain should be inverted for repos under the `slaclab` org: try the App token first, then fall back to lower-privilege tokens. At minimum, after a repo is known to be `visibility: internal`, the refetch path should skip straight to the App token. The plan's NFR-P1 (< 500ms added latency) is likely violated by 3 serial round-trips to `api.github.com`.

### Warning

- **warning | auth | Installation access token TTL is 1 hour by default, but can be customized down to 10 minutes** — The plan states "cached per installation for its 1h TTL" as if the 1h duration is fixed. In practice, the `POST /app/installations/{id}/access_tokens` response includes an `expires_at` field. The cache should use `expires_at` from the response rather than a hardcoded 1h TTL. This avoids breakage if the token lifetime changes or if custom permissions reduce it.

- **warning | auth | JWT max lifetime is 10 minutes, not mentioned in plan** — GitHub App JWTs must have `exp` no more than 10 minutes in the future (600 seconds). The `iat` claim should be backdated by 60 seconds to handle clock skew. The plan mentions "generate JWT" but does not specify these constraints. Implementers may use a longer expiry and get rejected. The plan should note: `iat = now - 60s`, `exp = now + 600s`, algorithm = RS256, `iss` = App ID.

- **warning | architecture | Module-level singleton `GitHubAppClient` is fragile for testing** — The plan specifies `GitHubAppClient` as a module-level singleton in `backend/app/services/github.py`, shared between `GitHubFetcher` and `GitHubScanner`. The existing pattern (`github_fetcher = GitHubFetcher()`) already makes testing harder — it requires patching the module-level instance. Adding a second singleton compounds this. Consider dependency injection via FastAPI's `Depends()` or a factory function that can be overridden in tests, rather than a bare module-level global. The existing test file (`test_github_fetcher.py`) works around this by instantiating `GitHubFetcher()` directly in each test, but this won't work for `GitHubAppClient` if it holds cached state.

- **warning | code quality | `datetime.utcnow()` is deprecated in Python 3.12+** — The existing codebase uses `datetime.utcnow()` in multiple places (`github.py:86`, `skill.py:42,43`). Python 3.12 deprecated `datetime.utcnow()` in favor of `datetime.now(timezone.utc)`. Since the project requires Python >= 3.11, this is not yet broken but will emit deprecation warnings on 3.12+ and will be removed in a future version. New code in this plan should use `datetime.now(timezone.utc)` and existing usage should be migrated as part of the same PR.

### Info

- **info | api | GitHub API fork detection is correct but incomplete for nested forks** — The plan correctly identifies that `GET /repos/{owner}/{repo}` returns `fork: true` and `parent.html_url` for immediate forks. However, `parent` refers to the immediate parent, while `source` refers to the ultimate root of the fork tree. For a fork-of-a-fork scenario (A -> B -> C), fetching C gives `parent = B` and `source = A`. The plan stores `forked_from_url` from `parent.html_url`, which is correct for showing "forked from" (immediate parent). The plan explicitly scopes out multi-level fork graphs, so this is fine, but the implementation should document that `parent` (not `source`) is used.

- **info | api | `GET /repos/{owner}/{repo}` includes `visibility` field** — The GitHub API response includes a `visibility` field (`public`, `private`, or `internal` for GitHub Enterprise). The plan could use this directly to set the `VisibilityEnum` rather than inferring it from which token succeeded. However, the plan's inference approach is more reliable for the fallback chain model (you know which token was needed), so the current approach is acceptable.

## Decisions Required

### Decision: Fallback chain ordering for known-org repos
- **Severity:** blocking
- **Question:** Should the fallback chain try the App token first for repos under `slaclab` org, rather than always starting with unauthenticated?
- **Options:** A) Keep the plan's chain (unauth -> PAT -> App) for all repos. B) Detect `slaclab` org from URL and try App token first, fall back to unauth. C) Always try App token first if configured, fall back to unauth for non-404 errors.
- **Assumed:** B — detect org from URL, invert chain for known org. This avoids 2 wasted round-trips per private repo call while keeping the generic path for public repos.
- **Impact if wrong:** If A is chosen, every private repo operation takes 3x the API calls and latency. If C is chosen, all public repo fetches consume App token rate limit unnecessarily.

### Decision: New dependency management for PyJWT + cryptography
- **Severity:** blocking
- **Question:** Should `PyJWT` and `cryptography` be added as direct dependencies, or should an alternative JWT library (e.g., `python-jose`) be used?
- **Options:** A) `PyJWT[crypto]>=2.8.0` (pulls in `cryptography` transitively). B) `python-jose[cryptography]>=3.3.0`. C) `authlib>=1.3.0` (includes JWT utilities).
- **Assumed:** A — `PyJWT[crypto]` is the most widely used, actively maintained, and recommended in GitHub's own documentation for App authentication.
- **Impact if wrong:** `python-jose` is less actively maintained. `authlib` is heavier but could be useful if OAuth flows are added later. Minimal impact either way — all three handle RS256 JWT generation correctly.

### Decision: Token cache key strategy
- **Severity:** judgement-call
- **Question:** Should the installation token be cached by installation ID (supporting multiple orgs) or as a single global token (only slaclab)?
- **Options:** A) Cache by installation ID (dict of tokens). B) Single cached token (only one org supported).
- **Assumed:** B — the plan only targets `slaclab` org. Single token keeps the implementation simpler. If multi-org support is needed later, refactoring to a dict cache is trivial.
- **Impact if wrong:** If the App is installed on multiple orgs, only one org's token would be cached, causing repeated token generation for the other. Low impact since the plan explicitly targets only slaclab.

## Amendments

### Amendment 1: Add dependency note to plan
The plan does not mention the new Python dependencies required for JWT generation. Added a note to the Architecture section.

_No direct edit made to the plan file — this is a documentation gap the author should address when implementing Slice 2. The required addition to `backend/requirements.txt`:_
```
PyJWT[crypto]>=2.8.0
```
_(The `[crypto]` extra pulls in `cryptography` for RS256 support.)_

### Amendment 2: JWT generation constraints should be documented
The plan's "generate JWT" step in the fallback chain should specify:
- Algorithm: RS256
- Claims: `iat = now() - 60` (clock skew buffer), `exp = now() + 600` (max 10 min), `iss = GITHUB_APP_ID`
- The JWT is used only to obtain an installation token; it is not sent to the repos API directly

_No plan edit — this is implementation guidance._

### Amendment 3: Cache should use `expires_at` from token response
The plan says "1h TTL" for the cached installation token. The implementation should parse `expires_at` from the `POST /installations/{id}/access_tokens` response and cache until `expires_at - 60s` (safety margin), not a hardcoded 3600s.

_No plan edit — this is implementation guidance._

## Simplification Opportunities

- **Consider `gidgethub` library** — `gidgethub` is a well-maintained async GitHub API library (used by CPython's bot) that has built-in GitHub App JWT generation and installation token management. Using it would eliminate the need to manually implement JWT signing, token caching, and the installation token exchange. It works with `httpx` via `gidgethub.httpx.GitHubAPI`. This could replace the entire `GitHubAppClient` class with ~10 lines of code. Trade-off: adds a dependency but removes significant custom auth code.

- **`visibility` field from API response** — As noted in Issues/Info, the GitHub API returns a `visibility` field on `GET /repos/{owner}/{repo}`. Rather than inferring visibility from which token succeeded, the code could read `data["visibility"]` directly and map `"private"` or `"internal"` to the enum. This is simpler and handles edge cases where the token has access but the repo's org-level visibility setting differs from what the fallback chain would infer.

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-arch-review — Round 1 (⚠️ WARN)</summary>

# Architecture Review: 001 -- Private Repos, Access Model, and Fork Provenance

**Reviewer:** codebase-arch-review
**Round:** 1
**Plan:** todo/001-private-repos-and-forks.md
**Date:** 2026-04-21

---

## Summary

- **Overall approach is sound:** GitHub App for org-level access, three-value visibility enum, and shared GitHubAppClient singleton are all correct top-level decisions. The three inline ADRs (P01-P03) are well-reasoned.
- **Blocking issue -- visibility labelling (AR-2):** The plan determines visibility by which auth method succeeded, but this is unreliable. A PAT can access private repos. The fix is simple: read `data["private"]` from the GitHub API response. New ADR-P04 written to `docs/adr/adr-p04-visibility-from-api-response.md`.
- **High issue -- singleton race (AR-3):** The module-level `GitHubAppClient` singleton has no concurrency protection on token refresh. An `asyncio.Lock` is needed to prevent redundant token generation under concurrent requests.
- **High issue -- fallback chain order (AR-1):** Fixed unauth -> PAT -> App order wastes ~400ms on known-private orgs. A configurable org list to skip straight to App token is recommended.
- **Missing migration (AR-6):** Existing Skill documents lack `visibility` and `forked_from_url` fields. MongoDB queries with `{visibility: "public"}` will not match field-absent documents. A one-line backfill is needed in the migration plan.

---

## Step 0: Scope Assessment

The architectural approach is sound at the top level. Using a GitHub App for org-level read access is the correct choice over per-user OAuth or shared PATs -- this is well-argued in ADR-P01. The three-value visibility enum is preferable to a boolean (ADR-P02). Sharing a single GitHubAppClient between fetcher and scanner (ADR-P03) avoids double-token generation.

However, several implementation details in the plan have correctness issues that could cause silent data corruption, race conditions, or unnecessary latency in production. These are detailed below.

---

## Issues

| # | Severity | Area | Description |
|---|----------|------|-------------|
| AR-1 | HIGH | fallback-chain | Fallback order is unauth -> PAT -> App. For slaclab org repos (always private), this means 2 serial 404 roundtrips (~400ms wasted) before the App token is tried. The chain should be context-aware: detect `slaclab` org in the URL and skip unauth/PAT steps. |
| AR-2 | HIGH | visibility-labelling | PAT fallback at step 2 sets `visibility=public` even if the PAT was required (i.e., unauthenticated returned 404). A repo that requires a PAT is not public -- it is at minimum `internal`. The plan conflates "PAT succeeded" with "publicly accessible." |
| AR-3 | HIGH | singleton-safety | `GitHubAppClient` as a module-level singleton with a cached token is not safe under concurrent async requests. If two requests hit `get_token()` simultaneously when the cache is expired, both will generate JWTs and call the GitHub API to exchange for installation tokens. There is no lock. This is a classic TOCTOU race on the cache check. |
| AR-4 | MEDIUM | token-ttl | Plan hardcodes 1h TTL for the installation token cache. GitHub App installation tokens have an actual `expires_at` field in the API response. Hardcoding 1h risks serving an expired token (clock skew, GitHub changes) or wasting a valid token early. The cache TTL should be derived from `expires_at` minus a safety margin (e.g., 60 seconds). |
| AR-5 | MEDIUM | fork-detection-private-upstream | Plan does not address what happens when `forked_from_url` parent fetch returns 404 (private upstream). FR-P6 says "fetches `parent.html_url`" but this comes from the same `/repos/{owner}/{repo}` response -- it is the `parent` field in the fork's repo metadata, not a separate fetch. If the fork's metadata includes `parent.html_url` pointing to a private repo, the URL is still available in the response -- but the plan should clarify: submission succeeds, `forked_from_url` is stored even if the parent is inaccessible. User story 10 says this, but the FR does not encode it. |
| AR-6 | MEDIUM | migration-gap | No migration plan for existing Skill documents. The plan adds `visibility: VisibilityEnum = VisibilityEnum.public` with a default, which handles new documents. But existing documents in MongoDB have no `visibility` field. Beanie will use the Python default on read, so queries work. However, MongoDB queries that filter on `visibility` (e.g., `{"visibility": "public"}`) will NOT match documents where the field is absent. A backfill is needed: `db.skills.updateMany({visibility: {$exists: false}}, {$set: {visibility: "public", forked_from_url: null}})`. |
| AR-7 | MEDIUM | singleton-testability | Module-level singleton `github_fetcher = GitHubFetcher()` (line 89 of github.py) and the planned `GitHubAppClient` singleton mean tests must either monkeypatch module globals or use `respx` to mock HTTP. This works today (tests use `respx`), but DI via FastAPI `Depends()` would be cleaner and is standard practice. Not blocking, but the plan should acknowledge this as a deliberate trade-off. |
| AR-8 | LOW | token-boundary-inflight | If a request is in-flight when the cached token expires, the request will use the stale token and get a 401 from GitHub. The plan's risk register mentions "App token cache invalidation bug" but does not specify the mitigation: retry with a fresh token on 401. The fallback chain should include a 401-retry step. |
| AR-9 | LOW | error-message-leakage | NFR-P2 says "App private key never logged or exposed in error messages." The plan does not specify how this is enforced. Python exception tracebacks will include local variables by default. The `GitHubAppClient` should avoid storing the raw PEM in instance attributes; instead, load it from the environment on each JWT generation, or use a `SecretStr` wrapper that redacts on repr. |
| AR-10 | LOW | rate-limit-budget | ADR-U06 requires a GitHub App token for discovery. The plan's fallback chain for `GitHubScanner` starts with unauthenticated, burning 60 req/hr budget on the first attempt even for discovery. The scanner's chain should always use the App token when available, not fall back *to* it. |
| AR-11 | LOW | adrs-not-committed | The plan lists three ADRs (P01, P02, P03) as inline content in the plan file. They need to be committed as separate files in `docs/adr/` to match the existing convention (adr-u01 through adr-u06). The numbering should continue as `adr-p01-*`, `adr-p02-*`, `adr-p03-*` -- or use sequential numbers `adr-007-*`, `adr-008-*`, `adr-009-*` following the existing `u01-u06` series. |

---

## Decisions Required

### Decision: Fallback chain order -- context-aware vs. fixed
- **Severity:** judgement-call
- **Question:** Should the fallback chain skip unauthenticated and PAT steps when the repo URL contains a known private-org domain (e.g., `slaclab`)?
- **Options:** A) Fixed chain (always unauth -> PAT -> App) as planned. Simple, uniform, but 2 wasted 404s for private repos. B) Context-aware chain: if `owner == "slaclab"` (configurable org list), skip directly to App token. Falls back to fixed chain for unknown orgs.
- **Assumed:** B -- a configurable `GITHUB_PRIVATE_ORGS` env var (comma-separated) that causes the chain to start with App token for matching orgs. The fixed chain is still the default for all other orgs. This is ~10 lines of code and saves 400ms+ per private repo submission.
- **Impact if wrong:** If A is chosen, private repo submissions are 400ms slower and consume 2 unnecessary API calls. Acceptable for low volume, but wasteful.

### Decision: PAT-required visibility labelling
- **Severity:** blocking
- **Question:** When the unauthenticated call returns 404 but the PAT succeeds, what should `visibility` be set to?
- **Options:** A) `public` as currently planned -- reasoning: the PAT is just for rate limits. B) `internal` -- the repo required auth to access. C) New heuristic: check the `private` field in the GitHub API response (`data["private"]`) to determine actual visibility.
- **Assumed:** C -- the GitHub API response includes `"private": true/false`. Use this directly: if `private == true`, set `visibility = internal`; if `private == false`, set `visibility = public`. This is accurate regardless of which auth method succeeded.
- **Impact if wrong:** If A is kept, repos that are actually private but accessible via PAT will be marked `public`, and users will not see the "SLAC Internal" badge -- breaking user story 3.

### Decision: Singleton concurrency safety -- asyncio Lock vs. DI
- **Severity:** judgement-call
- **Question:** How should the `GitHubAppClient` singleton handle concurrent token refresh?
- **Options:** A) Add an `asyncio.Lock` around the token refresh in `get_token()` so only one coroutine generates a new token while others await. B) Replace the module-level singleton with FastAPI DI (`Depends(get_github_client)`) and a request-scoped or app-scoped instance.
- **Assumed:** A for now -- `asyncio.Lock` is the minimal change. DI refactor is nice-to-have but not blocking since the existing `github_fetcher` singleton follows the same pattern and tests already mock at the HTTP level. Note: the Lock MUST be created inside the running event loop (not at module level), so use `asyncio.Lock()` as a lazy attribute on first call.
- **Impact if wrong:** If neither is done, concurrent requests during token expiry will redundantly generate tokens. Not a correctness bug (GitHub accepts both tokens) but wasteful and could hit secondary rate limits under load.

### Decision: ADR file naming convention
- **Severity:** defaulted
- **Question:** Should the new ADRs use the `p` prefix (plan-scoped) or continue the global sequential numbering?
- **Options:** A) `adr-p01-*`, `adr-p02-*`, `adr-p03-*` (plan-scoped prefix, matching the plan's naming). B) `adr-007-*`, `adr-008-*`, `adr-009-*` (global sequential after existing u01-u06).
- **Assumed:** A -- the existing ADRs use `u` prefix (presumably for todo/002's "ux" scope), so `p` prefix for todo/001's "private" scope is consistent. This also avoids collisions if multiple plans are in flight.
- **Impact if wrong:** Cosmetic only. Can be renamed later.

### Decision: Token TTL source
- **Severity:** judgement-call
- **Question:** Should the token cache TTL be hardcoded at 1h or derived from the GitHub API `expires_at` response field?
- **Options:** A) Hardcoded 1h as planned. B) Parse `expires_at` from the token response, cache until `expires_at - 60s`.
- **Assumed:** B -- it is 3 extra lines of code and eliminates a class of bugs (GitHub changes token lifetime, clock skew, etc.). The `POST /installations/{id}/access_tokens` response includes `expires_at` as an ISO 8601 timestamp.
- **Impact if wrong:** If A is kept, tokens could be served after actual expiry (if GitHub shortens lifetime) or discarded early (wasting API calls). Low probability but trivially avoidable.

---

## Amendments

1. **ADR-P04 written:** New ADR `docs/adr/adr-p04-visibility-from-api-response.md` -- determines visibility from the GitHub API `private` field rather than which auth method succeeded. Addresses AR-2.
2. **Plan amendment recommended (not applied):** FR-P2 should be reworded. Current: "If retry succeeds, repo is marked `visibility: internal`." Proposed: "Visibility is determined by the `private` field in the GitHub API response: `private: true` -> `visibility: internal`, `private: false` -> `visibility: public`, regardless of which auth method succeeded. If the repo URL could not be fetched by any method, it is treated as nonexistent." This affects FR-P2 and the Architecture section's fallback chain diagram.
3. **Plan amendment recommended (not applied):** Add to Delivery Slice 1: "Run a MongoDB backfill to set `visibility: 'public'` and `forked_from_url: null` on all existing Skill documents where these fields are absent."
4. **Plan amendment recommended (not applied):** Add 401-retry logic to the fallback chain description: "If any authenticated call returns 401, discard the cached token, generate a new one, and retry once."

---

## ADR Written

See `docs/adr/adr-p04-visibility-from-api-response.md` (created as part of this review).

---

## Status
PASS WITH WARNINGS

Three issues are HIGH severity (AR-1, AR-2, AR-3). AR-2 is blocking because it causes incorrect visibility labelling. AR-1 and AR-3 are high but non-blocking (they cause performance waste and redundant API calls, not data corruption). All three have straightforward fixes described in the Decisions Required section. The remaining issues are MEDIUM or LOW and are addressable during implementation without plan changes.

</details>

<details>
<summary>codebase-eng-review — Round 1 (⚠️ WARN)</summary>

## Summary

Engineering review of #001 (Private Repos and Fork Provenance). The plan is well-structured and buildable, but has 3 blocking gaps: (1) no JWT library dependency specified, (2) no data migration strategy for existing Skill documents, (3) the frontend github-preview route duplicates the backend fallback chain without any connection to it. Additionally, 5 non-blocking issues cover URL normalization for forked_from filtering, async-safety of the token cache, the `private` enum value having no write path, the frontend type/schema gap, and missing error differentiation in the current GitHubFetcher for the 404-retry flow. A test plan with 28 test cases is appended to the plan file.

## Issues

### ISSUE-1: No JWT dependency specified (blocking)

**Severity:** blocking

GitHub App authentication requires generating a JWT signed with the App's RSA private key. The plan references JWT generation in `GitHubAppClient` but does not identify the Python library needed. `pyproject.toml` currently has no dependencies listed (only build-system), and there is no `requirements.txt` visible. The implementation will need `PyJWT` (with `cryptography` for RS256) or `python-jose`.

**Recommendation:** Add `PyJWT[crypto]>=2.8` to the project dependencies. Document the choice in the plan. The `cryptography` extra is required for RS256 signing.

---

### ISSUE-2: No migration strategy for existing Skill documents (blocking)

**Severity:** blocking

The plan adds `visibility` and `forked_from_url` to the Skill model (Beanie/MongoDB). Existing documents in the `skills` collection lack these fields. While Beanie/Pydantic will use defaults when reading (visibility=public, forked_from_url=None), there is no plan to:

1. **Backfill existing documents** so the fields are explicitly present (important for index creation on `forked_from_url` -- MongoDB won't index documents missing the field unless a sparse/partial index is used).
2. **Create the index** -- the plan says "indexed" but doesn't specify whether this is a standard or sparse index. A standard index on `forked_from_url` where most values are `null` wastes space. A sparse index skips nulls but means `GET /api/skills?forked_from=null` won't work (unlikely need, but should be explicit).
3. **Handle the `visibility` index** -- no index is specified for `visibility`, but filtering by it will likely be needed (e.g., "show only internal skills"). Should it be indexed?

**Recommendation:** Add a Slice 1 sub-task: "Write a one-shot migration script that sets `visibility: 'public'` and `forked_from_url: null` on all existing documents. Create a sparse index on `forked_from_url`." Add a compound index `{visibility: 1, submitted_at: -1}` if filtering by visibility is anticipated.

---

### ISSUE-3: Frontend github-preview route not integrated with backend fallback (blocking)

**Severity:** blocking

The frontend `app/api/github-preview/route.ts` (lines 1-49) makes its own direct GitHub API call with only `GITHUB_TOKEN` (PAT). It has no connection to the backend's planned fallback chain. This means:

- **FR-P11** (submit form shows live preview for internal repos) is unimplementable with the current architecture -- the preview route will return 404 for private repos because it has no App token.
- The preview route duplicates auth logic (PAT only) and will need its own App token integration or, preferably, should be replaced by a backend endpoint.

**Recommendation:** Add to the plan: "Replace frontend `github-preview` route with a call to a new backend `GET /api/github-preview?repo_url=...` endpoint that uses the shared `GitHubAppClient` fallback chain. This ensures the preview for internal repos works (FR-P11) and eliminates duplicated GitHub auth logic in the frontend."

---

### ISSUE-4: `forked_from` URL filter needs normalization strategy (non-blocking)

**Severity:** non-blocking, needs spec

`GET /api/skills?forked_from=<url>` (FR-P9) uses URL matching. The plan doesn't specify how URLs are matched. Consider:

- `https://github.com/slaclab/foo` vs `https://github.com/slaclab/foo/` (trailing slash)
- `http://` vs `https://`
- `.git` suffix: `https://github.com/slaclab/foo.git`
- Case sensitivity: `SLACLAB` vs `slaclab` (GitHub is case-insensitive for owner/repo)

If `forked_from_url` is stored as-is from GitHub's `parent.html_url`, it will be consistent (GitHub always returns canonical `https://github.com/{owner}/{repo}` without trailing slash). But user-submitted overrides via PATCH (FR-P10) could introduce variants.

**Recommendation:** Normalize `forked_from_url` on write (strip trailing slash, force https, strip `.git`, lowercase owner/repo) and normalize the query parameter the same way. Add a `_normalize_github_url()` helper.

---

### ISSUE-5: Token cache async-safety in FastAPI (non-blocking)

**Severity:** non-blocking, needs spec

The plan says `GitHubAppClient` is a "shared singleton" with a "1h TTL cache." FastAPI runs on a single event loop (uvicorn), so multiple concurrent requests could trigger simultaneous token refresh if the token expires. This creates a thundering-herd problem:

- 10 concurrent submissions all see expired token
- All 10 trigger JWT generation + HTTP token exchange
- GitHub rate-limits the `/app/installations` endpoint

**Recommendation:** Use an `asyncio.Lock` to serialize token refresh. Only one coroutine fetches the new token; others await the lock and use the freshly cached result. Document this in the plan.

---

### ISSUE-6: `private` visibility enum value has no write path (non-blocking)

**Severity:** non-blocking, design clarification

The `VisibilityEnum` has three values: `public`, `internal`, `private`. The plan defines when `public` (unauthenticated fetch succeeds) and `internal` (App token required) are set. But `private` (described as "manually submitted, no fetch possible") has no defined write path:

- Submission always tries the fallback chain. If all steps fail, the skill is treated as nonexistent (FR-P2), not as `private`.
- There's no UI or API path documented for setting `visibility: private`.

**Recommendation:** Either (a) remove `private` from the enum for now (YAGNI -- add it when per-user OAuth is implemented), or (b) define the write path: "If a user submits a repo URL and the fallback chain fails, offer to submit with `visibility: private` and manual metadata entry."

---

### ISSUE-7: Frontend types and schemas not updated in plan (non-blocking)

**Severity:** non-blocking

The plan modifies the backend Skill model and API responses but does not mention updating:

- `frontend/types/skill.ts` -- `Skill` interface needs `visibility` and `forked_from_url` fields
- `frontend/types/skill.ts` -- `SkillUpdate` interface needs `forked_from_url`
- `backend/app/schemas/skill.py` -- `SkillOut`, `SkillListOut`, `SkillUpdate` schemas need the new fields
- `backend/app/routers/skills.py` -- `_skill_to_out()` and `_skill_to_list_out()` need the new fields
- `backend/app/routers/skills.py` -- `list_skills()` needs the `forked_from` query parameter

These are straightforward but should be listed as implementation tasks in the delivery slices to avoid them being forgotten.

**Recommendation:** Add explicit sub-tasks to Slice 1: "Update SkillOut/SkillListOut/SkillUpdate schemas, router serialization helpers, and frontend Skill type with visibility and forked_from_url."

---

### ISSUE-8: GitHubFetcher error message change is a breaking change for tests (non-blocking)

**Severity:** non-blocking

Current `GitHubFetcher.fetch()` raises `GitHubFetchError("Repo not found or is private")` on 404. The plan changes the 404 behavior to retry with App token. The existing test `test_fetch_not_found` (line 38-46 of `test_github_fetcher.py`) asserts on the string "not found or is private". The new behavior should differentiate:

- 404 without App token configured: same as today
- 404 with App token configured: retry, then "not found" (not "or is private")
- 404 on unauth, success on App token: no error, return snapshot with `visibility: internal`

**Recommendation:** Document the new error messages in the plan. Test cases for the fallback chain should cover all three scenarios above.

---

### ISSUE-9: Performance concern -- fallback chain latency budget (non-blocking)

**Severity:** non-blocking

NFR-P1 says "< 500ms for token generation." But the full fallback chain for a private repo submission is:

1. Unauthenticated `GET /repos/{o}/{r}` -- 404 (~200ms)
2. PAT `GET /repos/{o}/{r}` -- 404 (~200ms, if PAT configured)
3. JWT generation (~5ms)
4. `GET /app/installations` (~200ms, if not cached)
5. `POST /installations/{id}/access_tokens` (~200ms, if not cached)
6. App-token `GET /repos/{o}/{r}` -- 200 (~200ms)
7. App-token `GET /repos/{o}/{r}/readme` -- 200 (~200ms)

Total worst case: ~1200ms. The NFR covers only step 3-5 but the user experiences the full chain.

**Recommendation:** (a) Skip the PAT step if App token is configured (PAT is for rate-limit relief on public repos, not private repo access). (b) Consider parallelizing step 1 (unauth) and step 3-5 (token generation) so the token is warm by the time the 404 arrives. (c) Add an NFR for total submission latency, not just token generation. (d) For re-fetch of known `internal` skills (FR-P5), skip straight to App token (don't re-run the full chain).

---

### ISSUE-10: `GitHubSnapshot` needs `visibility` and `fork` fields (non-blocking)

**Severity:** non-blocking

The plan says `GitHubFetcher` returns `GitHubSnapshot + visibility field` but the current `GitHubSnapshot` model (lines 14-22 of `github.py`) doesn't have `visibility` or `forked_from_url`. These need to be added to the snapshot so `SkillRepository.create()` can store them.

**Recommendation:** Add to Slice 1 implementation tasks: "Extend `GitHubSnapshot` with `visibility: VisibilityEnum = VisibilityEnum.public` and `forked_from_url: Optional[str] = None`."

## Decisions Required

### Decision: Remove `private` enum value from v1
- **Severity:** judgement-call
- **Question:** Should `VisibilityEnum` include `private` in the initial implementation, given there is no defined write path for it?
- **Options:** A) Keep all three values (public/internal/private) for forward-compatibility. B) Ship with only public/internal; add private later when per-user OAuth lands.
- **Assumed:** A -- keep all three. The enum is in the data model and changing it later requires a migration. Adding an unused value now is cheap.
- **Impact if wrong:** If we ship `private`, someone might set it via the DB directly and the UI has no handling for it. Minor -- just shows no badge.

### Decision: Frontend preview route replacement
- **Severity:** blocking
- **Question:** Should the frontend `github-preview` Next.js route be replaced with a backend endpoint, or should it be extended with its own App token logic?
- **Options:** A) Replace with backend `GET /api/github-preview?repo_url=...` that uses the shared fallback chain. B) Keep in frontend and add App token logic to the Next.js route.
- **Assumed:** A -- backend endpoint. Single source of truth for GitHub auth. The frontend route already exists only as a proxy; moving it to the backend is cleaner.
- **Impact if wrong:** If kept in frontend, the App private key must be injected into the frontend container, which is a security concern (NFR-P2). This makes option B unacceptable.

### Decision: Sparse vs standard index on forked_from_url
- **Severity:** judgement-call
- **Question:** Should the MongoDB index on `forked_from_url` be sparse (only indexes documents where the field is not null) or standard?
- **Options:** A) Sparse index -- smaller, only indexes forks. B) Standard index -- indexes all documents including nulls.
- **Assumed:** A -- sparse index. The vast majority of skills will not be forks. The only query that uses this index is `forked_from=<url>` which always provides a non-null value.
- **Impact if wrong:** If someone needs to query "all skills that are NOT forks" using the index, a sparse index won't help. That query can use a collection scan (small collection) so this is acceptable.

### Decision: URL normalization for forked_from_url
- **Severity:** judgement-call
- **Question:** Should `forked_from_url` values be normalized on write, or stored as-is from GitHub?
- **Options:** A) Normalize on write and on query (strip trailing slash, force https, strip .git, lowercase owner/repo). B) Store as-is from GitHub; normalize only the query parameter.
- **Assumed:** A -- normalize on both write and query. This handles PATCH overrides with variant URLs.
- **Impact if wrong:** If stored as-is, PATCH overrides with `http://` or trailing slashes won't match queries. Fixable with a migration later, but better to get right from the start.

### Decision: Optimized fallback chain for known-internal skills
- **Severity:** judgement-call
- **Question:** Should `refetch()` for skills with `visibility: internal` skip the unauthenticated and PAT steps and go straight to the App token?
- **Options:** A) Always run full fallback chain (consistent, handles visibility changes). B) Skip to App token for known-internal skills (faster, avoids unnecessary 404s).
- **Assumed:** B -- skip to App token for known-internal. The visibility was determined at submission time. If the repo becomes public, a manual visibility override or a full re-scan can update it.
- **Impact if wrong:** If a repo is made public and the skill is still marked `internal`, refetch will use the App token unnecessarily (still works, just uses a token slot). Acceptable.

## Amendments

### Amendment 1: Added dependency requirement to plan

Added `PyJWT[crypto]>=2.8` to the implementation component list for `GitHubAppClient` to make the JWT signing dependency explicit.

### Amendment 2: Added migration sub-task to Slice 1

Added a migration sub-task to Slice 1 for backfilling existing documents and creating appropriate indexes.

### Amendment 3: Added github-preview backend endpoint to plan

Added a new implementation component: backend `GET /api/github-preview` endpoint using the shared fallback chain, and noted the frontend route replacement in Slice 2.

### Amendment 4: Added schema/type update tasks to Slice 1

Added explicit tasks for updating `GitHubSnapshot`, `SkillOut`, `SkillListOut`, `SkillUpdate`, frontend `Skill` type, and router serialization helpers.

### Amendment 5: Added URL normalization requirement

Added `_normalize_github_url()` helper requirement to the `SkillRepository` component and the `forked_from` filter implementation.

### Amendment 6: Added asyncio.Lock note to GitHubAppClient spec

Added async-safety requirement for the token cache.

## Test Plan

See test plan appended to `todo/001-private-repos-and-forks.md` under `## Test Plan`.

## Status
COMPLETE

**Decision resolved by user:** Frontend preview route → Option A (backend endpoint). Plan already reflects this.

</details>

<details>
<summary>codebase-doc-review — Round 1 (⚠️ WARN)</summary>

## Summary

Documentation review of todo/001 (Private Repos and Forks). Found **8 issues** across 6 documentation surfaces. The plan introduces new API endpoints, new env vars, a new GitHub App integration requiring admin setup, new frontend badges, and 3 ADRs -- none of which are tracked as documentation deliverables in the Definition of Done. The README, `.env.example`, API schema outputs, runbooks, ADR files, and CLAUDE.md all need updates or creation. Five DoD items added to the plan.

## Issues

### DC-01: No ADR files planned for docs/adr/
**Severity:** medium
**Location:** Plan section "ADRs" + `docs/adr/` directory

The plan defines three ADRs (ADR-P01, ADR-P02, ADR-P03) inline in the task file, but the Definition of Done does not include writing them to `docs/adr/`. The existing codebase has 6 ADRs (adr-u01 through adr-u06) already committed as standalone markdown files in `docs/adr/`. These three new ADRs should follow the same convention: `docs/adr/adr-p01-github-app-over-oauth.md`, `docs/adr/adr-p02-visibility-enum.md`, `docs/adr/adr-p03-shared-github-app-client.md`.

### DC-02: README.md needs updating for private repo support
**Severity:** medium
**Location:** `README.md`

The README is user-facing and currently describes a purely public-repo workflow ("submit a new skill by providing a GitHub repo URL"). After this feature ships:
- Users submitting private/internal repos need to know the catalog supports them
- The "SLAC Internal" badge concept should be mentioned
- The access instructions link should be referenced

The README does not need to be exhaustive, but should at minimum mention that internal/private SLAC repos are supported and link to the access instructions page.

### DC-03: No runbook for GitHub App setup
**Severity:** high
**Location:** Missing -- no runbooks exist in the repo

The plan describes a one-time GitHub App setup (Architecture section, lines 103-107) that requires an org admin to:
1. Create a GitHub App in the slaclab org with read-only `Contents` + `Metadata` permissions
2. Install on the slaclab org
3. Store `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` in vault
4. Add to backend k8s secret

This is a multi-step admin procedure touching GitHub Enterprise, HashiCorp Vault, and Kubernetes secrets. Without a runbook, an admin who did not write the code cannot perform this setup. The repo has zero runbooks today -- this feature should establish the pattern with at minimum `docs/runbooks/github-app-setup.md`.

Additionally, the k8s secret (`agent-knowledge-hub-secrets`) currently only contains `MONGO_URI` (see `kubernetes/overlays/dev/kustomization.yaml` lines 27-31). The two new secret keys (`GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`) need to be added to the kustomization secretGenerator across dev/stage/prod overlays. This is documented in the plan but not in a runbook.

### DC-04: backend/.env.example missing new env vars
**Severity:** medium
**Location:** `backend/.env.example`

The current `.env.example` has:
```
MONGO_URI=mongodb://localhost:27017/agent-skills
GITHUB_API_URL=https://api.github.com
GITHUB_TOKEN=
AUTH_MODE=dev
DEV_USER=your-slac-username
ADMIN_USERS=your-slac-username
```

The plan adds two new config fields (`github_app_id`, `github_app_private_key`) to `backend/app/config.py`. These must be added to `.env.example` with comments explaining they are optional (the fallback chain works without them -- you just lose private repo support). Without this, developers setting up local environments will not know these vars exist.

### DC-05: API response schemas not updated in plan
**Severity:** medium
**Location:** `backend/app/schemas/skill.py`, plan section "API Changes"

The plan's "API Changes" section only mentions two endpoints:
```
GET /api/skills?forked_from=<repo_url>
PATCH /api/skills/:slug  # forked_from_url now patchable
```

But the actual schema changes are broader. Both `SkillOut` and `SkillListOut` (in `backend/app/schemas/skill.py`) need new fields: `visibility` and `forked_from_url`. The `SkillUpdate` schema needs `forked_from_url` added as a patchable field. The `_skill_to_out()` and `_skill_to_list_out()` helper functions in `backend/app/routers/skills.py` must be updated to include the new fields.

This is an implementation detail rather than a doc gap per se, but the plan should explicitly list the schema file changes so that the `SkillListOut` change (which affects the card view -- the badge needs `visibility` on the list endpoint) is not missed. The `SkillListOut` omission could cause the "SLAC Internal" badge to not render on the browse page if the field is only added to `SkillOut`.

### DC-06: No CHANGELOG exists -- establish one or document the decision not to
**Severity:** low
**Location:** Missing -- no CHANGELOG file in the repo

The project has no CHANGELOG.md. This is acceptable for a pre-launch project, but once this feature ships it introduces a meaningful behavioral change (private repos, new badges, new query params). If the project intends to maintain a changelog, this is the right time to start. If not, no action needed.

### DC-07: No CONTRIBUTING.md exists -- new env vars increase onboarding friction
**Severity:** low
**Location:** Missing -- no CONTRIBUTING.md in the repo

There is no CONTRIBUTING.md. The backend Makefile does copy `.env.example` to `.env` on `make dev`, which partially mitigates onboarding friction. However, as the project adds GitHub App credentials and vault integration, the local development setup becomes non-trivial. A CONTRIBUTING.md would help, but this is not blocking for #001 specifically.

### DC-08: No CLAUDE.md exists for the project
**Severity:** low
**Location:** Missing -- `.claude/CLAUDE.md` not found in the repo

The project has a `.claude/` directory but no `CLAUDE.md` file. After this feature ships, future AI-assisted development sessions would benefit from a project CLAUDE.md documenting: the stack (FastAPI + Next.js + MongoDB/Beanie), the backend config pattern (pydantic-settings), the ADR convention (docs/adr/), and the new GitHub App integration. This is not blocking for #001.


## Decisions Required

### Decision: Should ADRs be written to docs/adr/ as part of this feature?
- **Severity:** judgement-call
- **Question:** The plan has 3 ADRs (P01, P02, P03) written inline in the task file. Should they also be committed as standalone files in `docs/adr/` following the existing convention (adr-u01 through adr-u06)?
- **Options:** A) Yes, write them to `docs/adr/` as part of the DoD B) No, keep them only in the task file -- they can be extracted during closeout
- **Assumed:** A -- write to `docs/adr/` as part of Slice 1. The existing convention is clear and established. Inline-only ADRs will be forgotten.
- **Impact if wrong:** Three ADRs live only in the task file and are not discoverable by future developers browsing `docs/adr/`.

### Decision: Should a runbook directory be established with this feature?
- **Severity:** judgement-call
- **Question:** The GitHub App setup is a multi-step admin procedure. No runbooks exist today. Should this feature establish the `docs/runbooks/` convention?
- **Options:** A) Yes, create `docs/runbooks/github-app-setup.md` as part of Slice 2 B) No, the inline documentation in the plan is sufficient C) Document it in the README instead
- **Assumed:** A -- the procedure involves vault, GitHub Enterprise admin, and k8s secrets. This needs a standalone runbook that an ops person can follow without reading the plan file.
- **Impact if wrong:** The plan file contains the steps, but an admin performing the setup 6 months from now would need to find and read the closed task file.

### Decision: Start CHANGELOG now or defer?
- **Severity:** defaulted
- **Question:** Should a CHANGELOG.md be created as part of this feature?
- **Options:** A) Yes, start CHANGELOG.md with the first entry for this feature B) No, defer to post-launch when versioning is established
- **Assumed:** B -- the project is pre-launch. Starting a changelog now adds process overhead without much benefit. Can be established during the first release.
- **Impact if wrong:** Minor -- missing one changelog entry that can be backfilled.


## Amendments

The following items were added to the Definition of Done in `todo/001-private-repos-and-forks.md`:

1. **ADR files committed:** `docs/adr/adr-p01-github-app-over-oauth.md`, `adr-p02-visibility-enum.md`, `adr-p03-shared-github-app-client.md`
2. **GitHub App setup runbook:** `docs/runbooks/github-app-setup.md` covering GitHub Enterprise App creation, vault secret storage, k8s secret injection, and verification steps
3. **`.env.example` updated:** `GITHUB_APP_ID` and `GITHUB_APP_PRIVATE_KEY` added with comments
4. **README updated:** mention private/internal repo support and SLAC Internal badge
5. **Schema files updated:** `SkillOut`, `SkillListOut`, and `SkillUpdate` schemas include `visibility` and `forked_from_url`; `_skill_to_out()` and `_skill_to_list_out()` helpers updated

See the plan file diff for the exact changes.

## Status
COMPLETE

</details>

<details>
<summary>security-review — Round 1 (⚠️ WARN)</summary>

## Summary

- PATCH /api/skills/:slug auth is correctly enforced (owner OR admin check at line 124) — no gap
- New `GET /api/github-preview` backend endpoint is unauthenticated by design (submit form uses it pre-login); needs rate limiting and URL allowlist to prevent open-proxy abuse
- `forked_from_url` and `github_access_instructions_url` must be validated as `https://github.com/*` URLs before storage/render — no current validation in schemas
- `GITHUB_APP_PRIVATE_KEY` as env var is acceptable but plan must require file-mount option for production; key logging protection needs explicit code guard, not just convention
- No blocking security issues; 3 warnings require DoD additions

## Issues

warning | auth | GET /api/github-preview is unauthenticated — can be called by anyone to proxy GitHub API requests; needs per-IP rate limiting (e.g. slowapi) and URL must match github.com pattern (already validated via regex in frontend route — must be replicated in backend endpoint)
warning | injection | forked_from_url stored from GitHub API parent.html_url — no validation that value is an https://github.com URL; a javascript: or data: URL would render as an XSS vector in frontend badge link
warning | injection | github_access_instructions_url in SiteSettings — stored by admin, rendered as badge href; must be validated as http/https only (no javascript:) before storage; Pydantic HttpUrl validator would cover this
warning | secrets | GITHUB_APP_PRIVATE_KEY as env var: multiline PEM is safe in k8s secrets (base64-encoded) but env vars are visible in /proc and kubectl describe; plan should recommend file-mount (/run/secrets/) as preferred option for production
warning | secrets | NFR-P2 (key never logged) relies on convention; plan should add explicit DoD item: error handler middleware strips/redacts any traceback containing PRIVATE_KEY string
info | auth | GET /api/skills?forked_from=<url> is unauthenticated (list endpoint is public) — this is fine; does not reveal private repo existence since the query only returns skills already in the catalog
info | auth | PATCH /api/skills/:slug auth already enforced correctly (line 124: submitter_id == user_id OR is_admin); forked_from_url patchable via SkillUpdate once that field is added — no new auth gap
info | supply-chain | PyJWT[crypto] (>=2.8) is actively maintained, GitHub-recommended for App JWT; cryptography package is well-audited — no supply chain concerns

## Decisions Required

### Decision: GET /api/github-preview authentication
- **Severity:** judgement-call
- **Question:** Should the new backend `GET /api/github-preview` endpoint require authentication, or remain unauthenticated like the current frontend route?
- **Options:** A) Unauthenticated with per-IP rate limiting (e.g. slowapi 10 req/min) B) Require auth token (breaks submit-form UX for logged-out users)
- **Assumed:** A — unauthenticated with rate limiting. The submit form is used before login in many flows. Rate limiting prevents open-proxy abuse.
- **Impact if wrong:** If left fully open without rate limiting, it becomes a free GitHub API proxy consuming the App's rate limit quota.

### Decision: forked_from_url URL validation
- **Severity:** judgement-call
- **Question:** Should `forked_from_url` be validated as an `https://github.com/*` URL at the Pydantic schema level, or only sanitized at render time in the frontend?
- **Options:** A) Pydantic validator on SkillUpdate and SkillCreate — reject non-github URLs at write time B) Frontend sanitization only
- **Assumed:** A — backend validation is the correct trust boundary. GitHub's API only returns github.com URLs for parent.html_url, but admin PATCH overrides need validation.
- **Impact if wrong:** Admin could accidentally (or maliciously) set a javascript: URL that renders as XSS in the badge link.

### Decision: GITHUB_APP_PRIVATE_KEY mount strategy
- **Severity:** defaulted
- **Question:** Env var or file mount for the private key in k8s?
- **Options:** A) File mount at /run/secrets/github-app-private-key B) Env var (current plan)
- **Assumed:** B — env var, consistent with other secrets in this deployment. Document file-mount as recommended alternative in runbook.
- **Impact if wrong:** Env vars are slightly less secure (visible in /proc, kubectl describe) but acceptable for this threat model.

## Amendments

- Added DoD item: `GET /api/github-preview` rate-limited (slowapi or equivalent, 10 req/min per IP)
- Added DoD item: `forked_from_url` validated as https://github.com/* URL in SkillUpdate Pydantic schema
- Added DoD item: `github_access_instructions_url` validated as http/https URL in SiteSettings schema (Pydantic HttpUrl)
- Added DoD item: error handler middleware redacts tracebacks containing PRIVATE_KEY (NFR-P2 enforcement)

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-ux-review — Round 1 (⚠️ WARN)</summary>

## Summary

The plan covers the core technical requirements for private repo support and fork provenance but has significant UX gaps when viewed from the perspective of an S3DF scientist who is not a developer. Seven issues are identified: the badge label "SLAC Internal" is jargon-laden and the SSO link destination will confuse non-developer scientists; there is no way to filter or discover internal skills in the catalog listing; the submit form lacks a warning that other users may not be able to access a private repo; the "Forked from" display uses a raw URL instead of a human-readable repo name; there is no UI specified for discovering forks of a skill (US-8); the error message for not-found repos should hint at the possibility of private repos outside the App's reach; and the three-value visibility enum (public/internal/private) leaks implementation details that will confuse users. Three decisions are required from the plan author. Two amendments were made directly to the plan file.

## Issues

### UX-1: "SLAC Internal" badge label is unclear to scientists
- **Severity:** high
- **Location:** FR-P4, Slice 3
- **Finding:** The term "SLAC Internal" is GitHub/enterprise jargon. A physicist looking at a skill card will not immediately understand what it means. "Internal" could mean "experimental," "under development," or "for staff only." The badge needs to communicate a clear action: you need SLAC credentials to access this repo.
- **Recommendation:** Use "SLAC Members Only" as the badge text. It is unambiguous: you must be a SLAC member (i.e., have SLAC credentials) to clone this repo. The tooltip or linked page can explain the details.

### UX-2: SSO link destination is unhelpful for scientists
- **Severity:** high
- **Location:** FR-P4, FR-P12
- **Finding:** The default link target `https://github.com/enterprises/slaclab/sso` is the GitHub Enterprise SAML SSO page. A scientist who has never configured GitHub Enterprise SSO will land on a page with no context about what to do. They need step-by-step instructions: "1. Go to this URL, 2. Sign in with your SLAC credentials, 3. After linking your GitHub account, you can clone this repo."
- **Recommendation:** The badge should link to a dedicated "How to access SLAC GitHub repos" page on the catalog itself (e.g., `/guides/slac-github-access`), which explains the process in plain language and then links to the SSO page as one step. FR-P12's `github_access_instructions_url` in SiteSettings should default to this internal guide page, not the raw SSO URL. This guide page can be a static page in the Next.js app or a section of the existing `/guides` page.

### UX-3: No visibility filter on the skill listing page
- **Severity:** medium
- **Location:** Skills list page, SkillListParams type, API
- **Finding:** The plan adds a `visibility` field but never mentions a way for users to filter by it. A scientist browsing the catalog cannot find "all SLAC-only skills" or exclude them. The current `SkillListParams` type supports `q`, `labels`, and `sort` but not `visibility`. Without a filter, internal skills are mixed in with public ones and the badge is the only signal -- easily missed in a grid of cards.
- **Recommendation:** Add a `visibility` filter parameter to the list endpoint and expose it as a filter chip or toggle in the skill list UI (e.g., "Show: All / Public only / SLAC Members Only"). This is a small addition that significantly improves discoverability.

### UX-4: Submit form lacks a warning about private repo accessibility
- **Severity:** high
- **Location:** FR-P11, submit-form.tsx
- **Finding:** FR-P11 says the submit form shows a "live preview for internal repos (same as public)" -- but there is no indication to the submitter that other users will not be able to clone this repo without SLAC GitHub access. The current submit form (`submit-form.tsx`) shows preview data and proceeds to submission with no friction. A submitter who has access to a private repo may not realize they are publishing a skill that most catalog users cannot actually use without additional setup.
- **Recommendation:** When the preview response indicates `visibility: internal`, show an informational banner below the preview box: "This repo requires SLAC GitHub access. Users without access will see a 'SLAC Members Only' badge with instructions on how to get access. [Learn more]." This is not a blocker to submission -- just an awareness prompt. The `GitHubPreview` response type should include a `visibility` field so the frontend can render this banner.

### UX-5: "Forked from" displays a raw URL instead of a repo name
- **Severity:** medium
- **Location:** FR-P8
- **Finding:** FR-P8 specifies "Forked from <url>" on the detail page. A raw URL like `https://github.com/slaclab/base-skill` is not user-friendly. Scientists scan page content quickly; a raw URL is visual noise compared to a clean repo name link.
- **Recommendation:** Display as "Forked from **slaclab/base-skill**" where the text is the `owner/repo` segment extracted from the URL, rendered as a clickable link. The URL parsing is trivial (split on `github.com/`). If the upstream is also in the catalog, link to its catalog detail page instead.

### UX-6: No UI for discovering forks of a skill (US-8)
- **Severity:** medium
- **Location:** US-8, FR-P9
- **Finding:** US-8 says "As a consumer, I want to see all catalog entries that are forks of a given skill." FR-P9 defines the API endpoint `GET /api/skills?forked_from=<url>`, but the plan never specifies how this is surfaced in the UI. There is no mention of a "N forks in catalog" link on the detail page, no fork count on the skill card, and no filter in the list page. The API exists but users have no way to reach it.
- **Recommendation:** On the skill detail page sidebar, add a "Forks in catalog" section that queries `GET /api/skills?forked_from={this_skill.repo_url}` and shows a count with a link to the filtered list. Example: "3 forks in catalog -- [View all]". If zero forks, omit the section. This closes the loop between the API and the user.

### UX-7: Error message for not-found repos should hint at private repo possibility
- **Severity:** low
- **Location:** AC-P2
- **Finding:** AC-P2 specifies the error "This repo couldn't be found. Check the URL." for repos that are genuinely not found even after the App token retry. However, there is a third case: a private repo outside the slaclab org (e.g., a personal private repo). The current plan does not distinguish this. The user sees "couldn't be found" and has no idea whether they mistyped the URL or whether the repo is private but outside the App's scope.
- **Recommendation:** Extend the error message to: "This repo couldn't be found. Check the URL. If this is a private repo outside the slaclab GitHub organization, private repos can only be auto-fetched for slaclab org repos." This gives the user an actionable next step: they know they can still submit with manual metadata (as the existing PRD AC-2 flow allows).

## Decisions Required

### Decision: Badge label text
- **Severity:** judgement-call
- **Question:** Should the badge read "SLAC Internal" (current plan), "SLAC Members Only", or something else?
- **Options:** A) "SLAC Internal" -- matches GitHub's own terminology B) "SLAC Members Only" -- clearer to non-developer scientists C) "Requires SLAC Access" -- action-oriented
- **Assumed:** B) "SLAC Members Only" -- proceeded with this in the plan amendment because it is the clearest to the target audience (scientists, not developers)
- **Impact if wrong:** Badge text is trivial to change later. If "SLAC Members Only" is too broad (e.g., some SLAC members don't have GitHub Enterprise access), the wording can be refined post-launch.

### Decision: Should the fork list UI be in scope for this plan or deferred?
- **Severity:** judgement-call
- **Question:** US-8 defines the user story and FR-P9 defines the API, but there is no UI spec. Should the fork list UI (detail page sidebar section + filtered list link) be added to this plan or deferred?
- **Options:** A) Add to Slice 3 (same as badge work -- it is a frontend display concern) B) Defer to a follow-up task
- **Assumed:** A) Add to Slice 3. The API is already being built. A sidebar section with a count and link is minimal frontend work and closes the user story.
- **Impact if wrong:** If deferred, US-8 is technically incomplete -- the API works but no user can access it without constructing a URL manually. Low risk either way since it is a small feature.

### Decision: Should visibility filter be exposed in the list UI?
- **Severity:** judgement-call
- **Question:** Should the skill listing page expose a visibility filter (All / Public / SLAC Members Only)?
- **Options:** A) Add visibility filter to the list page in this plan B) Defer -- let users rely on badge visual scanning C) Add as a label/facet in the labels feature (#003)
- **Assumed:** A) Add to this plan. It is a simple query parameter addition to the existing filter bar and directly supports discoverability.
- **Impact if wrong:** Minor scope addition. If the number of internal skills is small at launch, the filter may be unnecessary and can be removed.

## Amendments

### Amendment 1: Add FR-P15 -- visibility filter on list endpoint and UI

Added requirement FR-P15 to expose a visibility filter on the skill listing page so scientists can discover internal-only skills. Added corresponding frontend work to Slice 3 and a DoD item.

### Amendment 2: Add FR-P16 -- fork list UI on detail page

Added requirement FR-P16 to show a "Forks in catalog" section on the skill detail page sidebar with a count and link to the filtered list. Added to Slice 3 and DoD.

### Amendment 3: Add FR-P17 -- submit form internal repo warning banner

Added requirement FR-P17 for the submit form to show an informational banner when the preview detects an internal repo. Added to Slice 3.

### Amendment 4: Updated FR-P8 -- human-readable fork provenance display

Updated FR-P8 to specify that the "Forked from" display should show `owner/repo` as a linked name, not a raw URL.

### Amendment 5: Updated AC-P2 -- improved error message for not-found repos

Updated AC-P2 to include a hint about private repos outside the slaclab org.

## Status
COMPLETE

</details>
