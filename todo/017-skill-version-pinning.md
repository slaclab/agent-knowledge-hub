# TODO #017 — Skill Version / Commit Pinning

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** —

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

- [ ] `Skill` model: add `pinned_commit_sha`, `pinned_ref`, `upstream_sha`
- [ ] `GitHubSnapshot`: add `head_sha`
- [ ] `github_fetcher.fetch()`: fetch HEAD SHA via `git/ref/heads/<branch>`; tag lookup in parallel
- [ ] `skill_repository.create()`: set `pinned_commit_sha`
- [ ] `skill_repository.refetch()`: update `upstream_sha`
- [ ] `skill_repository.pin()`: new method; sets `pinned_commit_sha`, `pinned_ref`; records revision
- [ ] `POST /{slug}/pin` endpoint (submitter/admin auth)
- [ ] `SkillOut` / `SkillListOut`: add new fields + `update_available`
- [ ] Frontend: "Update available" badge on skill card
- [ ] Frontend: pinned SHA + tag display on detail page
- [ ] Frontend: "Update to latest" button (submitter/admin only)
- [ ] Install skill: pass `?ref=<pinned_commit_sha>` in GitHub Contents API calls
- [ ] Backfill script for existing skills
- [ ] Tests: pin endpoint auth, `update_available` logic, installer ref passthrough

---

## Definition of Done

- [ ] New skills capture `pinned_commit_sha` at registration
- [ ] `install <slug>` fetches files at pinned SHA, not HEAD
- [ ] "Update available" badge appears when upstream has moved ahead
- [ ] Submitter/admin can pin to latest via UI button
- [ ] Existing (unpinned) skills install from HEAD with an advisory — no regression
- [ ] All checklist items complete

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

> *Populated by `/codebase-board-review` after the board completes. Do not fill manually.*

**Verdict:** —
**Date:** —
**Rounds:** —

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — | — | — |
| codebase-arch-review | — | — | — |
| codebase-eng-review | — | — | — |
| codebase-doc-review | — | — | — |
| security-review | — | — | — |

---

## Relationship to Other Tasks

- **#014 (Provenance tree):** Pinned SHA feeds into the provenance tree — nodes can show exact version installed vs upstream
- **#013 (Revision history):** `pin` action records a `RevisionAction.pin` entry, visible in revision history
- **#001 (Private/internal repos):** Pin endpoint needs same App token handling as refetch for internal skills
