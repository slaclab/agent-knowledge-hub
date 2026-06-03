# TODO #011 — User Activity Profile: Skills by User

> **Priority:** 🟡 P2 — Medium
> **Status:** ✅ Complete
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** 2026-06-03

---

## Problem Statement

There is no way to see what a specific user has done in the catalog. If you want to find skills submitted by a colleague, you have to search by name and hope. There is no profile page or activity view. The revision history already records `actor_id` for every create/edit/refetch action, so the data exists — it's just not surfaced. Install/download events are not tracked at all.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| "Show me skills submitted by alice" | No way to filter/view | `/users/alice` Submitted tab |
| "Show me skills alice has edited" | Not possible | `/users/alice` Edited tab |
| "Show me skills I've installed" | Not tracked | `/users/me` Installed tab (self only) |
| Clicking a contributor name in the detail header | Nothing | Navigates to `/users/<user_id>` |

---

## Goals

1. A dedicated `/users/[user_id]` page with three tabs: **Submitted**, **Edited**, **Installed**
2. Contributor names in skill detail headers become clickable links to that page
3. Install tracking: AKH skill POSTs an install event to the backend on successful install
4. Backend API endpoints to support all three tabs and the profile page

## Non-Goals

- Full user profile (avatar, bio, social links) — activity view only
- Following/subscribing to users
- Email notifications about user activity
- Admin user management UI (separate task)
- Public visibility of another user's installed skills (installed tab is self + admin only)

---

## User Stories

1. As a user, I want to visit `/users/alice` and see all skills alice has submitted, so that I can discover her contributions.
2. As a user, I want to see skills alice has edited (revised), so that I can find her expertise in the catalog.
3. As a user, I want to visit `/users/me` or my own profile and see which skills I've installed, so that I can track what's on my system.
4. As a user, I want my install history to persist across sessions, so that I don't lose track of what I've installed.
5. As a user, I want contributor names on skill detail pages to be clickable links, so that I can explore other work by the same person.
6. As an admin, I want to see any user's installed skills, so that I can help debug installation issues.
7. As a user, I want my installed tab to be private to me (and admins), so that my install history isn't public.
8. As a user, I want to see the install date for each installed skill, so that I know how recent my install is.
9. As a user, I want the profile page to load quickly even for prolific contributors, so that I'm not waiting on large revision queries.
10. As an AKH skill user, I want a successful `install <slug>` to automatically record the install event, so that my profile stays up to date without extra steps.
11. As a user, I want my submitted and edited tabs to be public (no login required), so that others can explore my contributions.
12. As an admin, I want to see any user's full activity (submitted + edited + installed), so that I can audit or assist any user.
13. As a user with no activity in a tab, I want to see a clear empty state, so that I understand the tab is working but empty.
14. As a user, I want a "Re-install" action on my installed tab, so that I can quickly reinstall a skill after clearing my local cache.
15. As a user, I want skill cards on my Installed tab to show an "update available" badge when the upstream has changed, so I can decide whether to reinstall. (Note: the installed version is not stored — this badge reflects the Skill document's `update_available` flag.)

---

## Requirements

### Functional

- **FR-1:** `GET /api/users/{user_id}` returns a summary of the user's activity (submitted count, edited count, installed count — installed count only if viewer is the user or admin).
- **FR-2:** `GET /api/users/{user_id}/skills` returns skills submitted by `user_id` (paginated, same `SkillListOut` shape).
- **FR-3:** `GET /api/users/{user_id}/edits` returns skills where `user_id` has at least one `SkillRevision` with `action` in `{edit, refetch}` (paginated, `SkillListOut` shape).
- **FR-4:** `GET /api/me/installs` returns the authenticated user's install history (paginated, includes `installed_at` and `skill_slug`).
- **FR-5:** `POST /api/me/installs/{slug}` records an install event for the authenticated user; idempotent (upsert on `user_id + skill_slug`, updating `installed_at`).
- **FR-6:** `GET /api/skills` gains a `submitted_by` query param to filter skills by `submitter_id`.
- **FR-7:** Frontend `/users/[user_id]` page with Submitted / Edited / Installed tabs. Tab state is URL-encoded (`?tab=submitted|edited|installed`; default `submitted`). A `/users/me` server-side redirect resolves to `/users/{authenticated_user_id}`.
- **FR-8:** Installed tab renders for all viewers but shows content conditionally. Authenticated self/admin: full install list. Unauthenticated visitors: placeholder "Sign in to view your install history." Authenticated third-party viewers: placeholder "Install history is private to {user_id}." The tab itself is always visible in the tab bar (so the UI structure is consistent); only the content is gated.
- **FR-8b:** Empty state for self-view with zero installs: "No skills installed yet. Run `install <slug>` in your AKH session to track installs here." Empty state for Submitted tab: "No skills submitted yet." Empty state for Edited tab: "No skills edited yet."
- **FR-9:** Contributor names in `frontend/app/skills/[slug]/page.tsx` detail header and `actor_id` in `RevisionTimeline` are both rendered as `<Link href="/users/{user_id}">`. The current user's name in `nav.tsx` becomes a `<Link href="/users/{user_id}">` (Slice 3).
- **FR-10:** AKH `skill/SKILL.md` updated to `POST /api/me/installs/{slug}` (with Bearer JWT) after each successful skill install.

### Non-functional

- **NFR-1:** `GET /api/users/{user_id}/edits` uses a compound index on `SkillRevision.(actor_id, action, skill_id)` — no collection scans.
- **NFR-2:** All three profile tabs load in < 500ms (p95) for users with up to 500 activity items.
- **NFR-3:** Install event POST is fire-and-forget from the AKH skill — a failure does not abort or roll back the install itself.
- **NFR-4:** `POST /api/me/installs/{slug}` is rate-limited (60/hour) to prevent event spam.

### Acceptance Criteria

- **AC-1:** Given `GET /api/users/alice/skills`, the response contains only skills where `submitter_id == "alice"`.
- **AC-2:** Given `GET /api/users/alice/edits`, the response contains only skills where at least one `SkillRevision` has `actor_id == "alice"` and `action in {edit, refetch}`.
- **AC-3:** Given an authenticated user `alice` POSTing `POST /api/me/installs/my-skill`, an install event is created. A second POST updates `installed_at` (upsert), not a duplicate row.
- **AC-4:** Given an unauthenticated visitor on `/users/alice`, the Installed tab shows a "Private" placeholder. Submitted and Edited tabs render normally.
- **AC-5:** Given an authenticated `alice` visiting `/users/alice`, all three tabs (Submitted, Edited, Installed) are visible.
- **AC-6:** Given a contributor name on a skill detail page, clicking it navigates to `/users/{submitter_id}`.
- **AC-7:** Given the AKH skill runs `install my-skill` successfully, a `POST /api/me/installs/my-skill` is fired; if it fails (network error), the install itself succeeds and the error is logged as a warning only.
- **AC-8:** Given `GET /api/skills?submitted_by=alice`, only alice's submitted skills are returned.

---

## Architecture Decision Records

### ADR-U21: Profile URL scheme — `/users/<user_id>` dedicated page

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Two approaches to viewing a user's submitted skills: a filter param on the existing skills list (`/skills?submitted_by=alice`) or a dedicated profile page (`/users/alice`).

#### Options

| Option | Pros | Cons |
|---|---|---|
| Filter on `/skills?submitted_by=alice` | No new routes; reuses list UI | Can't show edited/installed tabs; no natural place for user summary; URL not shareable as a "profile" |
| Dedicated `/users/[user_id]` page | Natural multi-tab profile; shareable URL; room to extend | New route and page component |

#### Decision
**Dedicated `/users/[user_id]` page.** The multi-tab requirement (Submitted / Edited / Installed) makes a filter param insufficient — the list page has no tab mechanism. The dedicated route also gives a stable, shareable profile URL.

#### Consequences
- New Next.js route: `frontend/app/users/[user_id]/page.tsx`
- New backend endpoints: `/api/users/{user_id}`, `/api/users/{user_id}/skills`, `/api/users/{user_id}/edits`
- The `GET /api/skills?submitted_by=` filter is still added (for programmatic use), but the frontend uses the dedicated endpoints.

---

### ADR-U22: Install event tracking — client-side POST, not server-side intercept

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Install happens agent-side (AKH skill clones from GitHub locally). The backend has no hook into the install process. Two approaches: add a server-side download counter on `GET /api/skills/{slug}` views, or have the AKH skill explicitly POST an install event after a successful install.

#### Options

| Option | Pros | Cons |
|---|---|---|
| Increment counter on `GET /api/skills/{slug}` | No AKH skill change needed; counts views, not installs | Counts page views, not actual installs; inflated by bots/browsers; can't distinguish per-user |
| AKH skill POSTs `POST /api/me/installs/{slug}` after install | True install signal; per-user; idempotent upsert; requires auth (JWT already in AKH skill) | AKH skill must be updated; old skill versions won't post events |
| No backend tracking; local manifest only | Zero backend work | Not queryable; lost on reinstall; not on profile |

#### Decision
**AKH skill POSTs an install event after successful install.** The AKH skill already handles Bearer JWT auth (`~/.s3df-access-token`) and makes API calls. A fire-and-forget `POST /api/me/installs/{slug}` is a natural extension. Old AKH skill versions simply never post — the installed tab starts empty for legacy installs, which is acceptable.

#### Consequences
- New `SkillInstallEvent` MongoDB collection
- New endpoints: `POST /api/me/installs/{slug}`, `GET /api/me/installs`
- AKH `skill/SKILL.md` updated: step added after install success
- Upsert semantics: re-installing updates `installed_at`, not a second row
- Rate limit: 60 installs/hour to prevent spam

---

### ADR-U23: Installed tab visibility — private to self + admin

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Should a user's install history be public (visible to anyone) or private (visible to self and admins only)?

#### Options

| Option | Pros | Cons |
|---|---|---|
| Public | Simpler auth; no viewer checks | Exposes what tools a user is using; potential privacy concern |
| Private to self + admin | Respects privacy; consistent with how download history works in most platforms | Slightly more auth logic; UI needs "Private" placeholder for third parties |

#### Decision
**Private to self + admin.** Submitted and edited activity is public (it's already visible via skill metadata). Install history reveals tooling choices which a user may not want to broadcast. The check is simple: `viewer == profile_user or viewer.is_admin`.

#### Consequences
- `GET /api/users/{user_id}` omits `install_count` for non-self viewers
- `GET /api/users/{user_id}/installs` returns 403 for non-self, non-admin
- Frontend Installed tab: rendered only if `viewer_is_self or viewer_is_admin`, otherwise shows "Private" placeholder
- `GET /api/me/installs` is the canonical self-view endpoint (always returns own data)

---

## Module Design

### Backend

| Module | Responsibility | Interface | Status | Testable |
|---|---|---|---|---|
| `models/install_event.py` | `SkillInstallEvent` Beanie document | Document class + indexes | New | Yes |
| `services/user_activity.py` | Aggregate user activity: submitted skills, edited skills, install events | `get_submitted()`, `get_edited()`, `get_installs()`, `get_summary()` | New | Yes |
| `routers/users.py` | `GET /api/users/{user_id}`, `/skills`, `/edits` (public) | REST routes | New | Integration |
| `routers/me.py` | Extend with `GET /api/me/installs`, `POST /api/me/installs/{slug}` | REST routes | Modify | Integration |
| `routers/skills.py` | Add `submitted_by` query param to `GET /api/skills` | Filter param | Modify | Yes |

### Frontend

| Module | Responsibility | Status |
|---|---|---|
| `frontend/app/users/[user_id]/page.tsx` | Profile page: summary header + Submitted/Edited/Installed tabs; URL-encoded tab state (`?tab=`) | New |
| `frontend/app/users/me/page.tsx` | Server-side redirect to `/users/{authenticated_user_id}`; unauthenticated → redirect to sign-in | New |
| `frontend/components/user-activity-tabs.tsx` | Tab switcher with lazy-loaded content per tab | New |
| `frontend/app/skills/[slug]/page.tsx` | Wrap `submitter_id` in `<Link href="/users/{submitter_id}">` | Modify |
| `frontend/components/revision-timeline.tsx` | Wrap `actor_id` in `<Link href="/users/{actor_id}">` | Modify |
| `frontend/components/nav.tsx` | Make auth username `<span>` a `<Link href="/users/{user_id}">` | Modify |
| `frontend/types/user.ts` | `UserSummary`, `InstallEvent` TypeScript interfaces | New |

### AKH Skill

| Module | Responsibility | Status |
|---|---|---|
| `skill/SKILL.md` | Add fire-and-forget `POST /api/me/installs/{slug}` step after install success | Modify |

---

## System Design

```
Browser
  │
  ├─ GET /api/users/{user_id}              → { submitted_count, edited_count,
  │                                            install_count (self/admin only) }
  ├─ GET /api/users/{user_id}/skills       → PaginatedSkills (SkillListOut[])
  ├─ GET /api/users/{user_id}/edits        → PaginatedSkills (SkillListOut[])
  │
  ├─ GET /api/me/installs                  → Paginated install events (auth required)
  └─ POST /api/me/installs/{slug}          → 204 (auth required, upsert)

AKH Skill (after install success)
  └─ POST /api/me/installs/{slug}          → fire-and-forget (Bearer JWT)
```

**Data model:**

```python
# models/install_event.py
class SkillInstallEvent(Document):
    user_id: str
    skill_id: Optional[str]   # stringified ObjectId; None if skill deleted
    skill_slug: str
    installed_at: datetime

    class Settings:
        name = "skill_install_events"
        indexes = [
            IndexModel([("user_id", ASCENDING), ("skill_slug", ASCENDING)], unique=True),
            IndexModel([("user_id", ASCENDING), ("installed_at", DESCENDING)]),
        ]
```

**Existing indexes leveraged:**
- `SkillRevision`: needs index on `(actor_id, action, skill_id)` — add if not present
- `Skill`: `submitter_id` field exists; needs regular (non-sparse) index on `submitter_id` — add if not present (`submitter_id` is required/non-nullable, sparse is incorrect)

**API contract (new endpoints):**

```
GET /api/users/{user_id}
  Auth: optional
  → { user_id: str, submitted_count: int, edited_count: int,
      install_count?: int }   ← omitted if viewer != user and not admin

GET /api/users/{user_id}/skills?page=1&page_size=20
  Auth: optional
  → PaginatedSkills (same SkillListOut shape as /api/skills)

GET /api/users/{user_id}/edits?page=1&page_size=20
  Auth: optional
  → PaginatedSkills

GET /api/me/installs?page=1&page_size=20
  Auth: required
  → { items: [{ skill_slug, skill_name?, installed_at }], total, page, page_size }

POST /api/me/installs/{slug}
  Auth: required (Bearer JWT)
  Body: empty
  → 204 No Content  (upsert: creates or updates installed_at)
  Rate limit: 60/hour

GET /api/users/{user_id}/installs?page=1&page_size=20
  Auth: required (viewer must be user_id or admin)
  → 403 if viewer != user_id and not admin
  → { items: [{ skill_slug, skill_name?, installed_at }], total, page, page_size }

GET /api/skills?submitted_by={user_id}&...
  Auth: optional
  → PaginatedSkills (existing endpoint, new filter param)
```

---

## Trade-offs

```
Choice: Dedicated /users/[user_id] page (vs filter on /skills)
  + Multi-tab profile; shareable URL; extensible
  - New route + page component
  Decision: Dedicated page. Filter param still added for programmatic use.

Choice: Client-side POST for install events (vs server-side view counter)
  + True install signal; per-user; requires auth
  - Old AKH skill versions never post; legacy installs show empty
  Decision: Client-side POST. Empty is honest — better than inflated view counts.

Choice: Upsert semantics on install event (vs append log)
  + Simple; no duplicate rows; always shows most recent install
  - Lose history of "installed 3 times"
  Decision: Upsert. Install count per-skill is not a goal; most-recent install date is enough.

Choice: Index on SkillRevision.actor_id (vs query-time scan)
  + Fast edits tab; no collection scan on large revision history
  - Slightly larger index
  Decision: Add index. Revision collection will grow large; scan is not viable.
```

---

## Delivery Slices

**Slice 1 — Backend: profile + submitted/edited endpoints**
- Add `IndexModel([("actor_id", ASCENDING), ("action", ASCENDING), ("skill_id", ASCENDING)])` to `SkillRevision.Settings.indexes`
- Add `IndexModel([("submitter_id", ASCENDING)])` to `Skill.Settings.indexes` (non-sparse — field is required)
- Create `backend/scripts/005_add_actor_id_index.py` migration script
- `get_edited()` must use two parallel aggregation pipelines: (1) count pipeline `$match → $group by skill_id → $count` for total; (2) items pipeline `$match → $group by skill_id → $sort by max(added_at) DESC → $skip → $limit → batch Skill.find()`. Using `$count` and `$skip/$limit` in the same pipeline is not valid (the `$count` stage collapses the stream). Rate limit key for `POST /api/me/installs/{slug}`: use a custom `key_func` that returns `request.state.user.user_id` (set after `Depends(get_current_user)` resolves) — not `get_remote_address`.
- `services/user_activity.py`: `get_submitted()`, `get_edited()`, `get_summary()`
- `routers/users.py`: `GET /api/users/{user_id}`, `/skills`, `/edits`
- `GET /api/skills?submitted_by=` filter
- `GET /api/users/{user_id}` returns 200 with zero counts for unknown users (not 404, prevents enumeration)
- Unit + integration tests
- Write ADR-U21, ADR-U22, ADR-U23 to `docs/adr/` (content already drafted in this file)

**Slice 2 — Backend: install event tracking**
- `models/install_event.py`: `SkillInstallEvent` with upsert index; `skill_id: Optional[str]` (not PydanticObjectId)
- Register `SkillInstallEvent` in `backend/app/models/__init__.py` `ALL_MODELS`
- `routers/me.py`: `POST /api/me/installs/{slug}` (rate-limited 60/hour, **keyed on `user_id` not IP**); `GET /api/me/installs`; add `GET /api/users/{user_id}/installs` to `routers/users.py` (auth required; 403 for non-self/non-admin) — must be in Slice 2, not Slice 1, as it depends on `SkillInstallEvent`
- Per-user rate limit: add `request.state.user = user` inside `get_current_user` dependency; the slowapi `key_func` then reads `request.state.user.user_id`
- `POST /api/me/installs/{slug}`: validate slug resolves to an active Skill before upserting; return 404 if not found or deactivated; enforce `max_length=200, pattern=r'^[a-z0-9-]+$'` on path param
- Use atomic `update_one(filter, $set/$setOnInsert, upsert=True)` via Motor collection — not read-modify-write
- Update `skill_repository.delete()` to null out `skill_id` in `SkillInstallEvent` docs when a skill is removed
- Unit + integration tests

**Slice 3 — Frontend: profile page (Submitted + Edited tabs)**
- `frontend/app/users/[user_id]/page.tsx` with URL-encoded tab state (`?tab=` param)
- `frontend/app/users/me/page.tsx` — server-side redirect to `/users/{authenticated_user_id}`
- `frontend/components/user-activity-tabs.tsx`
- Submitted and Edited tabs (no Installed tab yet)
- Contributor name → clickable link in skill detail header (`FR-9`)
- `actor_id` in `RevisionTimeline` → clickable link
- Nav username `<span>` → `<Link href="/users/{user_id}">` (primary self-profile entry point)

**Slice 4 — Frontend: Installed tab + AKH skill update**
- Add Installed tab to profile page (self/admin only)
- Unauthenticated placeholder: "Sign in to view your install history"
- Authenticated-other placeholder: "Install history is private to {user_id}"
- Installed tab card: shows `installed_at` + `update_available` badge from Skill doc; "Re-install" links to skill detail page; deleted skills show slug in monospace + "Skill no longer in catalog" in muted text
- Update `skill/SKILL.md`: after step 12 (write installed-files manifest), insert new step as step 13 (fire-and-forget `POST /api/me/installs/{slug}`; log HTTP status code only, never echo token; does not abort install); renumber current steps 13–15 to 14–16; update cross-reference in step 4 (`jump to step 14 (fallback)` → `jump to step 15`)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `SkillRevision.actor_id` index missing → slow edits query | Medium | High | Add index in Slice 1 migration; test query plan before shipping |
| AKH skill version skew — old versions never post install events | High | Low | Acceptable; installed tab starts empty for legacy installs; document in CHANGELOG |
| Install event POST fails silently → missing history | Medium | Low | Fire-and-forget is intentional; warn in AKH output but never abort install |
| User ID is raw SLAC username (no display name) → ugly profile URLs | Medium | Low | URLs like `/users/alice` are fine; no display-name mapping needed in v1 |
| Rate limit abuse — posting 60 fake install events/hour | Low | Low | Rate limit + auth required; fake events only inflate user's own history |

---

## Definition of Done

- [x] All acceptance criteria pass
- [x] Index on `SkillRevision.(actor_id, action)` verified in MongoDB
- [x] Regular index on `Skill.submitter_id` verified (non-sparse; field is required)
- [x] Unit tests: `get_submitted()`, `get_edited()`, `get_summary()`, upsert install event
- [x] Integration tests: all new endpoints including `GET /api/users/{user_id}/installs`, 403 on cross-user install tab, `submitted_by` filter
- [x] `POST /api/me/installs/{slug}` rate limit is per-user (not per-IP); returns 429 at 61st request same user
- [x] AKH skill: token not echoed in warning output on POST failure
- [x] Frontend: `/users/[user_id]` renders Submitted + Edited tabs; Installed tab private
- [x] Frontend: contributor name in skill detail header is a clickable link
- [x] AKH skill: install flow posts event; failure does not abort install
- [x] No N+1 queries on profile page (batch skill lookups verified)
- [x] CHANGELOG entry added under `## Unreleased` using format `### User activity profile: skills by user (#011)`
- [x] README.md: add one-sentence mention of contributor profile pages (optional — low priority)
- [x] ADR-U21, ADR-U22, ADR-U23 written to `docs/adr/` as `adr-u21-profile-url-scheme.md`, `adr-u22-install-event-tracking.md`, `adr-u23-install-tab-visibility.md`

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-03
**Rounds:** 3

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | YES | `skill_id: Optional[str]` fix, aggregation pipeline correction, `GET /api/users/{user_id}/installs` slice ordering bug, `request.state.user` pattern for rate limit key |
| codebase-arch-review | ⚠️ WARN | YES | `get_edited()` aggregation must use two parallel pipelines; per-user rate-limit key recipe; admin installs endpoint moved to Slice 2 |
| codebase-eng-review | ✅ PASS | YES | Full test plan produced; atomic upsert, rate-limit per-user, skill delete cascade, `/users/me` redirect all verified |
| doc-review | ✅ PASS | YES | CHANGELOG format, ADR filenames, SKILL.md step anchor and renumbering, README note all added |
| security-review | ✅ PASS | YES | Per-user rate limit, `GET /api/users/{user_id}/installs` auth guard, slug validation, token safety note, zero-activity 200 response all verified |
| codebase-ux-review | ✅ PASS | YES | FR-7/FR-8/FR-8b/FR-9 UX spec complete; `/users/me` redirect, nav link, RevisionTimeline links, `update_available` badge, deleted-skill card design all added |

**Accepted warnings:** Unauthenticated `/users/me` redirects to sign-in (not 404). SLAC username enumeration risk accepted (returns 200 with zero counts for all valid-format user IDs — preferred over 404 per ADR). `internal`-visibility skills are not excluded from install events (acceptable; fire-and-forget install POST uses slug only). `GET /api/me/installs` response does not include `pages` field (inconsistency with `PaginatedSkills` noted but deferred).
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research — Round 1+2 (PASS WITH WARNINGS)</summary>

Key findings: `skill_id` type inconsistency (fixed to `Optional[str]`), aggregation pipeline for N+1 prevention, rate-limit key function gap, admin installs endpoint slice ordering, NFR-1 compound index correction.

</details>

<details>
<summary>codebase-arch-review — Round 1+2+3 (PASS)</summary>

Key findings: `get_edited()` aggregation pipeline corrected to two parallel pipelines (count + items). Per-user rate limit key: `request.state.user = user` in `get_current_user`, key_func reads `request.state.user.user_id`. Admin installs endpoint must be in Slice 2 (depends on `SkillInstallEvent`). `RevisionTimeline` and `/users/me` added to frontend module table.

</details>

<details>
<summary>codebase-eng-review — Round 1+2 (PASS)</summary>

Full test plan appended under `## Test Plan`. Key additions: atomic upsert via Motor `update_one`, per-user rate limit tests M7/M8, admin cross-user installs tests M9/M10/M11, skill delete cascade tests D1/D2, frontend tests F1–F8.

</details>

<details>
<summary>doc-review — Round 1+2 (PASS)</summary>

CHANGELOG format specified: `### User activity profile: skills by user (#011)`. ADR filenames: `adr-u21-profile-url-scheme.md`, `adr-u22-install-event-tracking.md`, `adr-u23-install-tab-visibility.md`. SKILL.md insert as step 13, renumber 13–15 → 14–16, update cross-reference in step 4.

</details>

<details>
<summary>security-review — Round 1+2 (PASS)</summary>

Blocking issues resolved: per-user rate limit keyed on `user_id`, `GET /api/users/{user_id}/installs` with auth guard in API contract, slug validation (`max_length=200, pattern=^[a-z0-9-]+$`) on install POST, token safety note for AKH warning output. Zero-activity 200 response documented (prevents enumeration).

</details>

<details>
<summary>codebase-ux-review — Round 1+2 (PASS)</summary>

Key findings resolved: FR-8 persistent create CTA, unauthenticated empty-state copy, FR-8b per-tab empty states, FR-9 amber notice above skill list, FR-9 copyable install block, `/users/me` server redirect, RevisionTimeline actor_id links, nav username link, deleted-skill card design, `update_available` badge.

</details>

---

## Test Plan

> Generated by `codebase-eng-review` — Round 1 (2026-06-03)

### Unit tests — `services/user_activity.py`

| ID | Test | Fixture | Assert |
|----|------|---------|--------|
| U1 | `get_submitted()` returns skills where `submitter_id == user_id`, active only | 2 alice skills, 1 bob | Returns 2 items, all alice's |
| U2 | `get_submitted()` pagination page 1 of 2 | 5 alice skills, page_size=3 | 3 items, total=5 |
| U3 | `get_submitted()` empty for unknown user | empty DB | Returns [], total=0 |
| U4 | `get_edited()` returns skills with `actor_id==user, action in {edit, refetch}` | 1 edit revision, 1 create revision | Returns 1 item |
| U5 | `get_edited()` deduplicates: skill with 3 edit revisions appears once | 3 revisions same skill_id | Returns 1 item |
| U6 | `get_edited()` excludes `action=create/deactivate/reactivate/pin` | Only those actions | Returns [] |
| U7 | `get_edited()` pagination | 6 edited skills, page_size=4 | Page 1 returns 4, page 2 returns 2 |
| U8 | `get_summary()` returns correct counts (self viewer) | alice: 2 submitted, 1 edited, 3 installs | `{submitted_count:2, edited_count:1, install_count:3}` |
| U9 | `get_summary()` omits install_count for non-self viewer | viewer=bob, profile=alice | No `install_count` key |
| U10 | `upsert_install()` creates new event | No prior event | 1 event, `installed_at` set |
| U11 | `upsert_install()` idempotent second call | Existing event | 1 row, `installed_at` updated |
| U12 | `upsert_install()` for deleted skill stores `skill_id=None` | Skill deleted after install | `skill_id` is None |
| U13 | `get_installs()` returns events sorted by `installed_at` desc | 3 events at different times | Newest first |
| U14 | `get_installs()` enriches with `skill_name` where skill still exists | 1 active + 1 deleted skill event | Active has name, deleted has None or slug fallback |

### Integration tests — `routers/users.py`

| ID | Test | Setup | Assert |
|----|------|-------|--------|
| I1 | `GET /api/users/alice` unauthenticated | alice has 2 skills | 200, `submitted_count=2`, no `install_count` |
| I2 | `GET /api/users/alice` as alice | alice session | 200, all three counts present |
| I3 | `GET /api/users/alice` as admin | admin session | 200, all three counts present |
| I4 | `GET /api/users/ghost` with no activity | empty DB | 200, all counts=0 |
| I5 | `GET /api/users/alice/skills` | 3 alice, 1 bob | 200, 3 items all `submitter_id=alice` |
| I6 | `GET /api/users/alice/skills` pagination | 5 alice skills | page=1&page_size=2 → 2 items, total=5 |
| I7 | `GET /api/users/alice/edits` | alice edited 2 skills | 200, 2 items |
| I8 | `GET /api/users/alice/edits` unauthenticated | public | 200 |
| I9 | `GET /api/skills?submitted_by=alice` | 3 alice skills | Only alice's skills |
| I10 | `GET /api/skills?submitted_by=ghost` | no matching | 200, items=[] |

### Integration tests — `routers/me.py` (install events)

| ID | Test | Setup | Assert |
|----|------|-------|--------|
| M1 | `POST /api/me/installs/my-skill` authenticated | skill exists | 204 |
| M2 | `POST /api/me/installs/my-skill` unauthenticated | — | 401 |
| M3 | `POST /api/me/installs/nonexistent` | slug not in DB | 404 |
| M4 | Second `POST /api/me/installs/my-skill` same user | prior event | 204, DB has 1 row |
| M5 | `GET /api/me/installs` authenticated | 3 install events | 200, total=3 |
| M6 | `GET /api/me/installs` unauthenticated | — | 401 |
| M7 | Rate limit: 61st POST same user within 1 hour | 61 requests | 429 |
| M8 | Rate limit is per-user not per-IP | user A at 60, user B first request | user B gets 204 |
| M9 | `GET /api/users/alice/installs` as alice | 2 events | 200 |
| M10 | `GET /api/users/alice/installs` as bob | — | 403 |
| M11 | `GET /api/users/alice/installs` as admin | 2 events | 200 |

### Skill delete cascade tests

| ID | Test | Assert |
|----|------|--------|
| D1 | Deleting a skill nulls `skill_id` in related install events | `SkillInstallEvent.skill_id == None` after delete |
| D2 | Install list still returns event after skill deleted | Event in `GET /api/me/installs`, skill_name absent or slug fallback |

### Frontend component tests

| ID | Test | Assert |
|----|------|--------|
| F1 | `/users/me` redirects to `/users/{session.user_id}` | Navigation occurs |
| F2 | Submitted tab renders with data | Skills list visible |
| F3 | Edited tab renders with data | Skills list visible |
| F4 | Installed tab renders for self | Install list visible |
| F5 | Installed tab shows "Private" for third-party viewer | Placeholder shown, no install API call made |
| F6 | Installed tab renders for admin viewing another user | Install list visible |
| F7 | Empty Submitted tab shows empty state | "No skills submitted yet" message |
| F8 | Contributor name in skill detail is `<Link href="/users/{submitter_id}">` | Link renders and navigates |

### Performance / index verification

| ID | Test |
|----|------|
| P1 | `explain()` on `SkillRevision.find(actor_id=X, action in {...})` — IXSCAN, no COLLSCAN |
| P2 | `explain()` on `Skill.find(submitter_id=X)` — IXSCAN |
| P3 | Load test: 500 install events per user, profile page p95 < 500ms |

---

## Relationship to Other Tasks

- **#007 (`/agent-knowledge-hub` skill):** The skill triggers installs — install tracking here feeds profile data; AKH skill updated in Slice 4.
- **#003 (Label UX):** Contributor name in detail header was already present as text; this task makes it a clickable link.
- **#006 (Skillsets):** Profile page could later show "Skillsets created" tab — natural extension.
