# TODO #017 — Skill Version / Commit Pinning

> **Priority:** 🟡 P2 — Medium
> **Status:** ✅ Complete
> **Branch:** main
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** 2026-06-02 (`31e1d38`)

---

## Problem Statement

Skills are installed by fetching files from the GitHub repo at the time of install. If an author pushes a breaking change to `main` after registering the skill, users who install it later get a different (possibly broken) version than the one that was reviewed and registered. There is also no way to know if a registered skill is out of date relative to its upstream repo.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Author pushes breaking change to `main` | Next install silently gets broken files | Install is pinned to commit at registration time |
| "Has this skill been updated upstream?" | No signal | Badge: "Update available" on skill card/detail |
| "What exact version am I installing?" | Unknown — always HEAD | Pinned SHA (and tag if present) shown in UI |
| Admin wants to refresh skill to latest | Clicks Refetch (updates metadata only) | Explicit "Update to latest" pins new commit |

---

## Goals

1. **Reproducible installs** — installer always passes `?ref=<pinned_commit_sha>` so users get the exact files that were registered/last updated
2. **Version display** — catalog shows pinned SHA (short form) and tag name (if one exists at that commit)
3. **Update available badge** — when upstream HEAD has moved past the pinned commit, show a badge on the skill card and detail page
4. **Explicit update action** — submitter or admin can pin to the latest upstream commit via a button in the UI

## Non-Goals

- README cache changes (separate concern, explicitly out of scope)
- Automatic/scheduled background polling for upstream changes
- Semver constraint resolution between skills
- Support for non-GitHub repos

---

## Design

### Data Model

Three new optional fields on `Skill`:

```
pinned_commit_sha: Optional[str]   # SHA pinned for installs; set at create + pin
pinned_ref:        Optional[str]   # Tag name at pinned_commit_sha, if any (e.g. "v1.2.0")
upstream_sha:      Optional[str]   # Latest HEAD on default branch; updated on refetch
```

`update_available` is a computed property (not stored):
```
update_available = upstream_sha is not None and upstream_sha != pinned_commit_sha
```

Existing skills with no `pinned_commit_sha` fall back to HEAD on install (current behaviour) — graceful degradation until backfilled.

### GitHub API calls

`GET /repos/:owner/:repo/git/ref/heads/<default_branch>` → `object.sha` — lightweight, single call for HEAD SHA.

`GET /repos/:owner/:repo/tags?per_page=10` → filter for `commit.sha == head_sha` → tag name (if any). Run in parallel with SHA fetch; skip gracefully on error.

Both calls added to the existing `github_fetcher.fetch()` flow, populating a new `head_sha: Optional[str]` field on `GitHubSnapshot`.

### API changes

**`GET /api/skills/<slug>` response** — add fields:
```json
{
  "pinned_commit_sha": "a1b2c3d4e5f6...",
  "pinned_ref": "v1.2.0",
  "update_available": true
}
```

**`POST /api/skills/<slug>/refetch`** (existing) — extended to also update `upstream_sha`. Does **not** change `pinned_commit_sha`. Auth: submitter or admin (unchanged).

**`POST /api/skills/<slug>/pin`** (new) — fetches latest HEAD SHA, sets `pinned_commit_sha = upstream_sha`, `pinned_ref` from tag lookup, records a `RevisionAction.pin` entry. Auth: submitter or admin.

### Installer change

`/agent-knowledge-hub install <slug>` skill:
1. `GET /api/skills/<slug>` — read `pinned_commit_sha`
2. If present: append `?ref=<pinned_commit_sha>` to all GitHub Contents API calls (`plugin.json` + component files)
3. If absent (legacy / backfill pending): fetch HEAD as today, show advisory: `"No pinned commit — fetching latest HEAD"`

### Backfill

A one-off admin script (or admin-triggered endpoint) iterates all skills with `pinned_commit_sha == None`, calls `github_fetcher.fetch()`, and sets `pinned_commit_sha = head_sha`. Low urgency — legacy skills degrade gracefully to HEAD installs.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `Skill` model | Modify | Add `pinned_commit_sha`, `pinned_ref`, `upstream_sha` + `update_available` computed prop |
| `GitHubSnapshot` | Modify | Add `head_sha: Optional[str]` field |
| `github_fetcher.fetch()` | Modify | Fetch HEAD SHA + tag name alongside existing metadata |
| `skill_repository.create()` | Modify | Set `pinned_commit_sha = github_data.head_sha` at registration |
| `skill_repository.refetch()` | Modify | Update `upstream_sha`; leave `pinned_commit_sha` untouched |
| `skill_repository.pin()` | New | Set `pinned_commit_sha = upstream_sha`, `pinned_ref`; record revision |
| `POST /{slug}/pin` router | New | Auth guard (submitter or admin); call `skill_repository.pin()` |
| `SkillOut` / `SkillListOut` schemas | Modify | Add `pinned_commit_sha`, `pinned_ref`, `update_available` |
| Skill card component | Modify | Show "Update available" badge when `update_available` |
| Skill detail page | Modify | Show pinned SHA/tag; "Update to latest" button (submitter/admin only) |
| Install skill | Modify | Pass `?ref=<pinned_commit_sha>` in GitHub Contents API calls |

---

## ADRs

### ADR-001: Separate `refetch` and `pin` endpoints

**Status:** Accepted

**Context:** `refetch` currently updates metadata (stars, readme, last_commit_at). We need a way to also advance the pinned install SHA. Combining them risks silently advancing the pin on every metadata refresh.

**Decision:** Keep `refetch` for metadata-only updates (now also sets `upstream_sha`). New `pin` endpoint explicitly advances `pinned_commit_sha`. Users understand the difference: "refresh info" vs "update what gets installed".

**Consequences:** Two separate actions in the UI. Slightly more surface area. Clearer intent.

---

### ADR-002: Store SHA not tag as the install pin

**Status:** Accepted

**Context:** Tags are mutable (can be force-moved). SHAs are immutable. For reproducible installs the SHA is the authoritative reference.

**Decision:** `pinned_commit_sha` is the 40-char SHA. `pinned_ref` is the tag name stored for display only — it is never passed to GitHub as the install ref.

**Consequences:** Display shows human-readable tag if available; install always uses SHA. Tag drift doesn't break installs.

---

## Trade-offs

```
Choice: Fetch HEAD SHA in existing fetch() call (adds 1 extra API call per submission/refetch)
  + Single code path; SHA always fresh
  - Slightly more GitHub API quota usage
  Decision: Accept. One extra lightweight call per refetch. GitHub rate limits are not a concern at current scale.

Choice: Backfill as script vs on-demand per-skill
  + Script: one-shot, bulk, cheap
  - Script: requires ops intervention; window where old skills have no pin
  Decision: Script (or admin endpoint) run once post-deploy. Old skills fall back to HEAD gracefully.

Choice: update_available as computed vs stored boolean
  + Computed: always accurate, no sync issues
  - Computed: requires upstream_sha to be kept fresh (relies on periodic refetch)
  Decision: Computed. upstream_sha is updated on every refetch; that's sufficient freshness.
```

---

## Delivery Slices

**Slice 1 — Backend data + API (no installer change yet)**
- Add fields to `Skill` model
- Extend `github_fetcher.fetch()` to return `head_sha`
- Set `pinned_commit_sha` in `create()`, `upstream_sha` in `refetch()`
- Add `pin()` service method + `POST /{slug}/pin` endpoint
- Update `SkillOut`/`SkillListOut` schemas

**Slice 2 — Frontend**
- "Update available" badge on skill card and detail page
- "Update to latest" button on detail page (submitter/admin only)
- Show short SHA + tag on detail page

**Slice 3 — Installer**
- Update install skill to pass `?ref=<pinned_commit_sha>`
- Fallback to HEAD with advisory if no SHA present

**Slice 4 — Backfill**
- Admin script / endpoint to populate `pinned_commit_sha` for existing skills

---

## Migration

Additive-only MongoDB model changes — no schema migration required. Existing documents simply lack the new fields (treated as `None`). Installer falls back to HEAD for unpinned skills.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HEAD SHA fetch adds GitHub rate limit pressure | Low | Low | One extra call per create/refetch; well within limits |
| Tag lookup returns stale/wrong tag | Low | Low | Tag is display-only; SHA is the install ref |
| Backfill fetches fail for deleted/private repos | Medium | Low | Log failures, leave `pinned_commit_sha` null; installer degrades gracefully |
| Author deletes a commit (force-push) | Very low | High | SHA becomes invalid; installer errors with "ref not found" — surface clearly, prompt user to re-pin |

---

## Implementation Checklist

- [x] `Skill` model: add `pinned_commit_sha`, `pinned_ref`, `upstream_sha`
- [x] `GitHubSnapshot`: add `head_sha`
- [x] `github_fetcher.fetch()`: fetch HEAD SHA via `git/ref/heads/<branch>`; tag lookup in parallel
- [x] `skill_repository.create()`: set `pinned_commit_sha`
- [x] `skill_repository.refetch()`: update `upstream_sha`
- [x] `skill_repository.pin()`: new method; sets `pinned_commit_sha`, `pinned_ref`; records revision
- [x] `POST /{slug}/pin` endpoint (submitter/admin auth)
- [x] `SkillOut` / `SkillListOut`: add new fields + `update_available`
- [x] Frontend: "Update available" badge on skill card
- [x] Frontend: pinned SHA + tag display on detail page
- [x] Frontend: "Update to latest" button (submitter/admin only)
- [x] Install skill: pass `?ref=<pinned_commit_sha>` in GitHub Contents API calls
- [x] Backfill script for existing skills
- [x] Tests: pin endpoint auth, `update_available` logic, installer ref passthrough
- [x] CHANGELOG.md: add "Skill version pinning (#017)" section under Unreleased
- [x] skill/SKILL.md: update "Install by slug" to document `?ref=<pinned_commit_sha>` and fallback advisory
- [x] docs/adr/: persist ADR-001 (separate refetch/pin) and ADR-002 (SHA over tag) as files (adr-u11, adr-u12)
- [x] docs/github-api-plugin-installation.md: update "Current approach" to note ref pinning (post-ship)

---

## Definition of Done

- [x] New skills capture `pinned_commit_sha` at registration
- [x] `install <slug>` fetches files at pinned SHA, not HEAD
- [x] "Update available" badge appears when upstream has moved ahead
- [x] Submitter/admin can pin to latest via UI button
- [x] Existing (unpinned) skills install from HEAD with an advisory — no regression
- [x] CHANGELOG entry written
- [x] skill/SKILL.md install docs match new behavior
- [x] All checklist items complete

---

## Test Plan

> *Generated by engineering review (round 1, 2026-06-02)*

### Unit Tests (backend/tests/test_version_pinning.py)

**Model / Validation**
- `test_sha_validation_accepts_valid_40char_hex` — `Skill(pinned_commit_sha="a"*40)` passes
- `test_sha_validation_rejects_short_sha` — `"abc123"` raises ValidationError
- `test_sha_validation_rejects_uppercase` — `"A"*40` raises ValidationError
- `test_sha_validation_accepts_none` — None is valid (unpinned skill)

**Computed Property: update_available**
- `test_update_available_true_when_shas_differ` — upstream != pinned -> True
- `test_update_available_false_when_shas_match` — upstream == pinned -> False
- `test_update_available_false_when_upstream_is_none` — never checked -> False
- `test_update_available_false_when_both_none` — legacy skill -> False

**GitHubSnapshot / Fetcher**
- `test_fetch_populates_head_sha` — git/ref/heads/main returns SHA correctly
- `test_fetch_head_sha_graceful_on_api_error` — git/ref fails -> head_sha=None, no crash
- `test_fetch_tag_lookup_finds_matching_tag` — tag with matching SHA -> pinned_ref set
- `test_fetch_tag_lookup_no_match` — no matching tag -> pinned_ref=None
- `test_fetch_tag_lookup_graceful_on_error` — tags endpoint 404 -> no exception
- `test_fetch_tag_multiple_matches_takes_first` — first tag wins

**Repository: create()**
- `test_create_sets_pinned_commit_sha_from_head` — SHA captured at creation time
- `test_create_pinned_sha_none_when_github_unavailable` — graceful degradation

**Repository: refetch()**
- `test_refetch_updates_upstream_sha` — upstream_sha populated
- `test_refetch_does_not_change_pinned_sha` — pinned stays stable

**Repository: pin()**
- `test_pin_sets_pinned_sha_to_latest` — advances to current HEAD
- `test_pin_records_revision_with_pin_action` — RevisionAction.pin recorded
- `test_pin_updates_pinned_ref_from_tag` — tag name captured
- `test_pin_clears_pinned_ref_when_no_tag` — old tag cleared if new SHA has none
- `test_pin_fetches_head_when_upstream_sha_is_none` — self-contained (no prior refetch needed)
- `test_pin_local_skill_raises_error` — source_type="local" -> error

### API / Endpoint Tests (backend/tests/test_pin_endpoint.py)

**Auth**
- `test_pin_endpoint_requires_auth` — no token -> 401
- `test_pin_endpoint_submitter_allowed` — submitter -> 200
- `test_pin_endpoint_admin_allowed` — admin (not submitter) -> 200
- `test_pin_endpoint_other_user_forbidden` — other user -> 403

**Endpoint behavior**
- `test_pin_endpoint_returns_updated_skill` — response has new SHA + update_available=False
- `test_pin_endpoint_skill_not_found` — 404
- `test_pin_endpoint_local_skill_rejected` — 400

**Refetch endpoint extended**
- `test_refetch_now_returns_upstream_sha` — response includes upstream_sha
- `test_refetch_does_not_change_pinned_commit_sha` — pinned unchanged

### Schema / Serialization Tests

- `test_skill_out_includes_version_pinning_fields` — all three fields present in JSON
- `test_skill_list_out_includes_update_available` — badge field in list response

### Integration Tests (installer)

- `test_install_passes_ref_query_param` — ?ref=<sha> appended to GitHub Contents API calls
- `test_install_falls_back_to_head_when_no_sha` — no ?ref= when sha is None
- `test_install_clear_error_on_expired_sha` — GitHub 404 -> user-friendly message

### Backfill Script Tests

- `test_backfill_sets_pinned_sha_for_unpinned_skills` — sha populated post-backfill
- `test_backfill_skips_local_skills` — source_type="local" untouched
- `test_backfill_handles_deleted_repo_gracefully` — 404 -> logs warning, skill unchanged

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
| research | ✅ PASS | R1 | GitHub API design correct; tag pagination (per_page=10) is best-effort only — confirmed acceptable per ADR-002 |
| codebase-arch-review | ⚠️ WARN | R1 | pin() self-containment resolved; backend file-preview endpoint should also respect pinned SHA (non-blocking) |
| codebase-eng-review | ✅ PASS | R1 | SHA validation and pin() self-sufficiency resolved; comprehensive 30+ case test plan appended |
| doc-review | ✅ PASS | R1 | CHANGELOG, skill/SKILL.md, ADR files, github-api-plugin-installation.md all added to checklist |
| security-review | ✅ PASS | R1 | SHA format validation (^[0-9a-f]{40}$) and App token for pin() on internal skills both addressed |
| codebase-ux-review | ⚠️ WARN | R1 | 5 UX items for Slice 2: staleness timestamp, regular-user recourse, plain-language advisory, tag-first display, dual-version labelling |

**Accepted warnings:**
- arch: backend `/files/{path}` endpoint should pass `pinned_commit_sha` as ref (implement in Slice 1 alongside main backend work)
- ux: 5 UX polish items (staleness "last checked" display, regular-user tooltip for "Update available", plain-language install advisory, tag-first SHA display, "Pinned git tag" label disambiguation) — handle in Slice 2 frontend

**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research — Round 1 (PASS)</summary>

## Claim Verdicts

| # | Claim | Verdict | Evidence | Source |
|---|---|---|---|---|
| 1 | `GET /repos/:owner/:repo/git/ref/heads/<branch>` returns `object.sha` (40-char) | CONFIRMED | Docs confirm singular `git/ref/{ref}` endpoint returns `object.sha` (minLength: 40, maxLength: 40). Path format `heads/<branch name>` is correct. | GitHub REST API docs — Git References |
| 2 | `GET /repos/:owner/:repo/tags?per_page=10` returns `commit.sha` usable for matching HEAD SHA | CONFIRMED WITH CAVEAT | Endpoint returns array with `commit.sha` per tag. However, for annotated tags, the git/tags API documentation notes that the tag object references "the SHA of the git object this is tagging" which is "normally a commit but can also be a tree or blob." The higher-level repos/tags endpoint appears to dereference to commits, but this is not explicitly documented. | GitHub REST API docs — List repository tags; Git Tags |
| 3 | `?ref=<full_commit_sha>` works in GitHub Contents API | CONFIRMED (practice) | Docs describe `ref` as accepting "the name of the commit/branch/tag" — wording is slightly ambiguous but passing full 40-char SHAs is standard practice and well-established across the ecosystem. No known failures for public or private repos. | GitHub REST API docs — Get repository content |
| 4 | Tag lookup by filtering `commit.sha == head_sha` on repos/tags is reliable | WARN — partial | Only checks first 10 tags (`per_page=10`). If a repo has more than 10 tags and the matching tag is not in the most recent 10, the lookup will miss it. Also: tags are returned in no guaranteed order. | GitHub REST API docs — pagination behavior |

## Summary
- The core GitHub API design (git/ref for HEAD SHA, Contents API ?ref=sha) is correct and will work as specified.
- Tag matching has a reliability gap: `per_page=10` with no sort guarantee may miss the matching tag. Plan already states "skip gracefully on error" which adequately covers this.
- No issues found with private repos or GitHub App tokens for these endpoints.

## Amendments
No amendments required.

## Status
PASS

</details>

<details>
<summary>research — Round 2 (PASS)</summary>

## Summary
1. SHA format validation (`^[0-9a-f]{40}$`) — Correct. Git SHA-1 commit hashes are exactly 40 lowercase hexadecimal characters.
2. GitHub matching-refs API does NOT support filtering by commit SHA — plan's current approach (fetch tags, filter client-side) is correct and simplest.

## Status: PASS

</details>

<details>
<summary>codebase-arch-review — Round 1 (PASS WITH WARNINGS)</summary>

## Issues

**MEDIUM | data-flow | pin() operation has contradictory specification** — API description says "fetches latest HEAD SHA" but module table says "Set pinned_commit_sha = upstream_sha". If pin() merely copies upstream_sha and upstream_sha is None (never refetched), the pin is set to None. Resolved: pin() must be self-contained (fetch HEAD independently).

**MEDIUM | completeness | Backend file endpoint does not respect pinned SHA** — `GET /api/skills/{slug}/files/{path}` fetches from branch HEAD, not pinned SHA. Creates inconsistency between the installer (pinned) and the UI file viewer (HEAD). Recommendation: pass `pinned_commit_sha` as ref when serving file content.

**LOW | scope | Local skills not explicitly excluded from pinning** — pin() should return 400 for non-GitHub skills.

**LOW | failure-domain | HEAD SHA fetch failure behavior unspecified in create()** — Should degrade gracefully (head_sha=None, skill still created).

## Status: PASS WITH WARNINGS

</details>

<details>
<summary>codebase-arch-review — Round 2 (PASS WITH WARNINGS)</summary>

pin() contradiction and create() failure semantics resolved. Minor residual: backend file-preview endpoint should also pass pinned ref (non-blocking — CLI installer path is primary concern).

## Status: PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 1 (PASS WITH WARNINGS)</summary>

## Issues
**HIGH | Data Validation | No SHA format validation specified** — Add `field_validator` on `Skill.pinned_commit_sha` and `upstream_sha`: reject non-None values not matching `^[0-9a-f]{40}$`.

**HIGH | Logic Gap | pin() behavior when upstream_sha is None** — pin() must fetch HEAD SHA internally (self-contained); calling pin() on a fresh skill must work without a prior refetch.

**MEDIUM | Missing Enum Value | RevisionAction.pin not in current enum** — Add `pin = "pin"` to RevisionAction.

**MEDIUM | Sequencing | Default branch needed before HEAD SHA fetch** — fetch() must get default_branch from repo metadata first, then call git/ref/heads/<default_branch>.

**MEDIUM | Scope Gap | Local skills not addressed** — pin() returns 400 for local skills.

**LOW | update_available=False means two things** — upstream_sha=None (never checked) vs upstream_sha==pinned (up-to-date). Frontend should distinguish.

## Status: PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 2 (PASS)</summary>

All HIGH and MEDIUM issues resolved. Two cosmetic checklist gaps (enum addition, validator not explicitly listed) but test plan makes requirements unambiguous.

## Status: PASS

</details>

<details>
<summary>doc-review — Round 1 (PASS WITH WARNINGS)</summary>

## Issues
**HIGH | skill/SKILL.md** — install docs will be wrong after Slice 3; must update `Install by slug` section to document `?ref=<pinned_commit_sha>` and fallback advisory.

**HIGH | CHANGELOG.md** — no CHANGELOG entry planned; breaks established project pattern.

**MEDIUM | docs/adr/** — inline ADRs (ADR-001, ADR-002) should be persisted as files (adr-u11-*, adr-u12-*).

**LOW | docs/github-api-plugin-installation.md** — "Current approach" section should be updated post-ship.

**LOW | skill/SKILL.md update command** — note that re-install uses pinned SHA, not HEAD.

## Amendments
Added 4 items to Implementation Checklist; 2 items to Definition of Done.

## Status: PASS WITH WARNINGS

</details>

<details>
<summary>doc-review — Round 2 (PASS)</summary>

All 6 Round 1 doc amendments confirmed present in plan.

## Status: PASS

</details>

<details>
<summary>security-review — Round 1 (PASS WITH WARNINGS)</summary>

## Issues
**HIGH | Input validation** — `pinned_commit_sha` has no format constraint. A branch name stored as pinned_commit_sha is mutable and defeats reproducible installs. Add `field_validator` with `^[0-9a-f]{40}$`.

**MEDIUM | Auth / internal skills** — pin() design doesn't specify `force_app_token=True` for internal-visibility skills. Must match refetch() pattern.

**LOW | Auth / backfill** — if backfill is exposed as an endpoint, requires admin auth.

**LOW | Rate limiting** — pin endpoint triggers outbound GitHub calls; add rate limit (10/min per IP) consistent with existing `github-preview` endpoint.

**INFO | Supply chain** — force-push risk acknowledged in Risk Register; error message should not leak GitHub API error response details.

## Status: PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 2 (PASS)</summary>

Both issues resolved: SHA format validation in test plan, App token handling for pin() explicitly noted.

## Status: PASS

</details>

<details>
<summary>codebase-ux-review — Round 1 (PASS WITH WARNINGS)</summary>

## Issues
**HIGH | Information Staleness** — No "last checked" timestamp for `update_available`; badge may be stale for months with no signal.

**HIGH | Dead-End Workflow** — "Update available" badge visible to all, but only submitter/admin can act. Regular users have no recourse; add tooltip: "Contact {submitter_id} to request an update."

**MEDIUM | Jargon** — "No pinned commit — fetching latest HEAD" is incomprehensible to beamline scientists. Suggested: "This skill has no pinned version — you will receive whatever is currently in the repository."

**MEDIUM | Dual version display** — plugin.json `version` field and `pinned_ref` (git tag) will both appear; labelling them the same way creates confusion. Use "Pinned git tag" as the label for pinned_ref.

**MEDIUM | Card density** — badge position and colour not specified; recommend header row, teal/blue, tooltip.

## Status: PASS WITH WARNINGS

</details>

<details>
<summary>codebase-ux-review — Round 2 (PASS WITH WARNINGS)</summary>

All 5 Round 1 UX items remain unresolved in plan text (low severity — copy/layout items, no structural changes needed). Addressable in Slice 2 acceptance criteria.

## Status: PASS WITH WARNINGS

</details>

---

## Relationship to Other Tasks

- **#014 (Provenance tree):** Pinned SHA feeds into the provenance tree — nodes can show exact version installed vs upstream
- **#013 (Revision history):** `pin` action records a `RevisionAction.pin` entry, visible in revision history
- **#001 (Private/internal repos):** Pin endpoint needs same App token handling as refetch for internal skills
