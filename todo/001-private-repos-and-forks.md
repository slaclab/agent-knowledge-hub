# 001 — Private/Internal GitHub Repos, Access Model, and Fork Provenance

**Status:** ⬜ Open
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
- FR-P4: Skill cards and detail pages display a "SLAC Internal" badge when `visibility == internal`, linking to `https://github.com/enterprises/slaclab/sso` (or configurable URL in SiteSettings).
- FR-P5: Re-fetch endpoint uses GitHub App token for `visibility: internal` skills.
- FR-P6: On submission, backend calls `GET /repos/{owner}/{repo}` and checks `fork: true` in the response. If true, fetches `parent.html_url` and stores it as `forked_from_url`.
- FR-P7: Skill model adds `forked_from_url: str | null`. Indexed for lookup.
- FR-P8: Skill detail page shows "Forked from <url>" when `forked_from_url` is set.
- FR-P9: `GET /api/skills?forked_from=<url>` returns all catalog entries forked from that repo URL.
- FR-P10: `PATCH /api/skills/:slug` allows owner/admin to set/override `forked_from_url`.
- FR-P11: Submit form shows a live preview for internal repos (same as public) when the GitHub App has access. No special UI needed.
- FR-P12: SiteSettings stores `github_access_instructions_url` (configurable by admin); used in the SLAC Internal badge link.
- FR-P13: `GET /api/github-scan` (from #002) uses the same App token fallback chain as `GitHubFetcher`. `GitHubScanner` shares the `GitHubAppClient` helper — same token, same cache. If the App token is required to fetch the repo, the returned `SkillSnapshot` includes `visibility: internal`.
- FR-P14: Discovery mode (`discover=true`) also uses the App token when scanning private repos. The recursive tree walk (`GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1`) and all per-directory scans use the installation token. Discovery on a private repo is only available if the App is installed and configured.

### Non-Functional

- NFR-P1: GitHub App token generation adds < 500ms to submission latency (token is cached per installation for its 1h TTL).
- NFR-P2: App private key never logged or exposed in error messages.
- NFR-P3: Fallback chain (App → PAT → unauth) is transparent to the user.

### Acceptance Criteria

- AC-P1: Given a private slaclab repo URL, when submitted, the GitHub App token is used and metadata is fetched successfully — the skill appears with `visibility: internal` and a "SLAC Internal" badge.
- AC-P2: Given a genuinely nonexistent repo URL, even after App token retry, the form shows: _"This repo couldn't be found. Check the URL."_ — not a badge.
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
- Interface: `async get_token() → str | None` — returns token or None if App not configured
- Shared singleton used by both `GitHubFetcher` and `GitHubScanner` (#002)
- Testable in isolation: Yes (mock JWT generation + HTTP exchange)

**Skill model (modify `backend/app/models/skill.py`)**
- Add `visibility: VisibilityEnum`
- Add `forked_from_url: Optional[str]`
- Add index on `forked_from_url`

**SkillRepository (modify `backend/app/services/skill.py`)**
- `list()`: add `forked_from` filter param
- `create()`: store `visibility` and `forked_from_url` from GitHubSnapshot
- `refetch()`: use App token for internal skills

**Config (modify `backend/app/config.py`)**
- Add `github_app_id: Optional[str]`
- Add `github_app_private_key: Optional[str]`

**Frontend SkillCard + SkillDetail (modify)**
- Show "SLAC Internal" badge when `visibility == internal`
- Show "Forked from <url>" when `forked_from_url` is set

---

## Delivery Slices

**Slice 1 — Data model + fork detection**
- Add `visibility` + `forked_from_url` to Skill model
- Auto-populate `forked_from_url` from GitHub API on submission (public repos only first)
- Show "Forked from" on detail page
- `forked_from` filter on list endpoint

**Slice 2 — GitHub App integration**
- `GitHubAppClient`: JWT generation, installation token fetch, 1h cache
- Fallback chain in both `GitHubFetcher` (submission/refetch) and `GitHubScanner` (scan/discovery from #002) — shared `GitHubAppClient` singleton
- `visibility: internal` set in `SkillSnapshot` when App token was required
- Vault secrets + k8s secret for `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY`
- Note: #002 must ship before or alongside this slice for the scanner integration to be testable

**Slice 3 — Frontend badges + instructions**
- "SLAC Internal" badge on card and detail
- `github_access_instructions_url` in SiteSettings
- Badge links to configurable URL

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
- [ ] "SLAC Internal" badge shown in frontend for `visibility=internal`
- [ ] "Forked from" shown on detail page
- [ ] `GITHUB_APP_ID` + `GITHUB_APP_PRIVATE_KEY` added to vault + k8s secrets for dev/stage/prod
- [ ] SiteSettings `github_access_instructions_url` configurable by admin
- [ ] No private key in logs or error responses (security check)
- [ ] Private repo scan via `/api/github-scan` returns `visibility: internal` in SkillSnapshot
- [ ] Discovery mode (`discover=true`) works on private repos when App is configured
