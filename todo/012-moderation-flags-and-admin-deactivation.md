# TODO #012 — Moderation: User Flags and Admin Deactivation

> **Priority:** 🟠 P1 — High
> **Status:** ✅ Complete
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** 2026-06-03

---

## Problem Statement

The catalog has no moderation loop. `SkillFlag` and `SkillStatus.deactivated` already exist in the backend data model, but:

- No API route lets users submit a flag
- No API route lets admins view, resolve, or act on flags
- No API route lets admins deactivate a skill
- The `FlagIndicator` component shows a count on the detail page but it's always zero (no flags are ever written)
- Admins have no UI surface to take action on flagged or bad skills

The result: bad, broken, or superseded skills accumulate in the catalog with no mechanism for the community to signal problems or for admins to clean up.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| User notices a skill is broken | No action possible | User can flag it with a reason |
| User flags the same skill twice | Not prevented | Upsert: updates existing flag record |
| Admin sees skills with high flag counts | No visibility | Admin queue shows flagged skills sorted by flag count |
| Admin wants to disable a harmful skill | No mechanism | Admin can deactivate with a reason; skill shows tombstone |
| Admin wants to mark a skill superseded | Manual edit only | Admin can set `superseded_by_slug` and deactivate atomically |
| Admin resolves a flag | Not possible | Admin marks flag resolved with a note; flag count decrements |

---

## Goals

1. **User flagging** — authenticated users can flag a skill with a reason (broken, stale, superseded, inappropriate, other) and optional note; upsert semantics: one flag doc per user per skill
2. **Flag indicator** — `FlagIndicator` on the detail page reflects real flag counts; logged-in users see whether they've already flagged it
3. **Admin flag queue** — `/admin/flags` page lists flagged skills sorted by count; admin can view individual flags (reason, note, timestamp)
4. **Admin deactivation** — admin can deactivate a skill (with reason) from the detail page or admin queue; skill shows tombstone to all users; all active flags auto-resolved
5. **Admin reactivation** — admin can reactivate a previously deactivated skill
6. **Flag retraction** — user can retract their own active flag; `flag_count` decrements

## Non-Goals

- Auto-deactivation based on flag threshold (future follow-on)
- Email/Slack notifications to admins on new flags (future)
- User appeals process
- Flag activity shown on user profile (see #011 as a future extension)
- Bulk deactivation from the admin queue (single-skill inline action only for this iteration)

---

## Design

### Key Decision: Labels vs First-Class Fields

Labels are community taxonomy (searchable, filterable, multi-value). Deactivation and flag status are boolean/enum system state that affects visibility and routing. Mixing them would let users manipulate moderation state via the label API and would pollute label search results with system values. The existing `SkillStatus` and `SkillFlag` models are the right home.

### Existing Backend Assets

- `SkillFlag` document: `skill_id`, `reporter_id`, `reason` (FlagReason enum), `note` (max 500 chars), `superseded_by_slug`, `status` (FlagStatus), `resolved_by`, `resolution_note`, `created_at`, `resolved_at`
- Unique index already on `(skill_id, reporter_id)` — enforces one record per user per skill
- `SkillStatus.deactivated` + `deactivation_reason` on `Skill` — model exists; no admin route
- `RevisionAction.deactivate` and `RevisionAction.reactivate` exist — no service methods wire them up yet
- `flag_count: int = 0` denormalized on `Skill` — must be kept in sync
- `Tombstone` frontend component: fully implemented, just never rendered
- `FlagIndicator` frontend component: renders `count > 0` badge; never receives non-zero count today
- `require_admin` dependency: used in `routers/labels.py`; reuse for admin routes

### Flag Deduplication

The unique index on `(skill_id, reporter_id)` means we upsert on flag: if a resolved flag already exists for this user+skill, we reset `status=active`, update `reason`/`note`, update `created_at`. This avoids both duplicate inserts and the complexity of multi-record histories per user. The flag_count is only incremented when the existing record was `resolved` (not on update of an already-active flag).

### Admin Routes Location

New `routers/admin.py` router with prefix `/api/admin` — keeps admin concerns separate, applies `require_admin` at the router level rather than per-endpoint. This matches the existing admin page at `/admin/labels` in the frontend.

---

## User Stories

1. As an authenticated user, I want to flag a skill as broken so that admins know it needs attention
2. As an authenticated user, I want to pick a flag reason (broken/stale/superseded/inappropriate/other) so my flag gives admins actionable context
3. As an authenticated user, I want to add an optional note when flagging so I can describe the specific problem
4. As an authenticated user flagging a superseded skill, I want to specify the replacement slug so the admin can set `superseded_by_slug` atomically
5. As an authenticated user, I want to retract a flag I submitted so I can undo a mistaken report
6. As an authenticated user, I want to see whether I have already flagged a skill so I don't submit duplicates
7. As an authenticated user, I want to see the total flag count on a skill's detail page so I know if others share my concern
8. As a skill submitter, I want to be able to flag my own skill (e.g. to mark it stale) so I don't need admin access to signal deprecation
9. As an admin, I want to see a queue of all flagged skills sorted by flag count so I can triage the most problematic first
10. As an admin, I want to see each flag's reason and note so I have full context before acting
11. As an admin, I want to deactivate a skill with a reason so the tombstone explains to users why it's gone
12. As an admin, I want to optionally set `superseded_by_slug` when deactivating so the tombstone links to the replacement
13. As an admin, I want deactivation to auto-resolve all active flags for the skill so the queue stays clean
14. As an admin, I want to reactivate a previously deactivated skill so I can undo erroneous deactivations
15. As an admin, I want a deactivate/reactivate button directly on the skill detail page so I don't have to navigate to the admin queue
16. As a user viewing a deactivated skill, I want to see a tombstone with the reason and a link to the replacement so I understand what happened
17. As an unauthenticated visitor, I want the flag button to prompt login so the call-to-action is clear
18. As an admin, I want deactivation and reactivation to be recorded as revisions so there is an audit trail

---

## Requirements

### Functional Requirements

**FR-1:** `POST /api/skills/{slug}/flag` — authenticated; body `{reason: FlagReason, note?: str (max 500), superseded_by_slug?: str}`; upsert semantics on `(skill_id, reporter_id)`; increments `flag_count` only when transitioning from resolved→active; 429 rate limit (10/hour per user). **[ENG-AMD-1]** Rate limit must be enforced per `user_id` (not per IP) — `get_remote_address` is not acceptable because all web requests proxy through a single Next.js backend IP; use an in-service per-user counter or a custom slowapi `key_func` reading the authenticated `user_id`. **[ENG-AMD-3]** If the target skill is `status=deactivated`, return 410 with `{code: "deactivated"}` — flagging a deactivated skill is not permitted.

**FR-2:** `DELETE /api/skills/{slug}/flag` — authenticated; sets user's flag to `status=resolved`; decrements `flag_count` using a conditional update `{$inc: {flag_count: -1}, $max: {flag_count: 0}}` or equivalent to guarantee floor-at-0 atomically (concurrent retracts must not drive count negative); 404 if no active flag exists

**FR-3:** `GET /api/admin/flags` — admin only; returns skills where `flag_count >= 1` **AND `skill.status = active`**, sorted by `flag_count` desc; includes per-skill flag list (reason, note, created_at — reporter_id omitted from public; reporter_id included for admins). **[ENG-AMD-4]** Deactivated skills must be excluded from the queue regardless of their `flag_count` value to prevent concurrent flag+deactivate races from polluting the queue.

**FR-4:** `POST /api/admin/skills/{slug}/deactivate` — admin only; body `{reason: str (required, max_length=1000), superseded_by_slug?: str (max_length=100)}`; returns 409 if skill is already deactivated; sets `SkillStatus.deactivated` + `deactivation_reason`; optionally sets `superseded_by_slug`; writes `RevisionAction.deactivate` revision; bulk-sets all active `SkillFlag` records for the skill to `status=resolved` with `resolved_by=admin_id`. If `superseded_by_slug` resolves to a skill that is itself deactivated, the 200 response includes `"warnings": ["superseded_by_slug 'X' is itself deactivated"]`; the admin UI surfaces this warning adjacent to the confirmation dialog.

**FR-5:** `POST /api/admin/skills/{slug}/reactivate` — admin only; body `{reason?: str}`; sets `SkillStatus.active`; clears `deactivation_reason`; writes `RevisionAction.reactivate` revision. **[ENG-AMD-7]** Calling reactivate on an already-active skill returns 409 Conflict. Calling deactivate on an already-deactivated skill also returns 409 Conflict. These guard rails prevent stale revision entries and double-overwrite of `deactivation_reason`.

**FR-6:** `GET /api/skills/{slug}` response gains `my_flag: {reason, note, status} | null` when the requesting user has a flag record for the skill (null for unauthenticated)

**FR-7:** `FlagIndicator` on skill detail page reflects live `flag_count`; shows "Flagged by you" variant when `my_flag` is non-null and active. On successful POST flag or DELETE flag, `FlagButton` updates the displayed count and "Flagged by you" state from the API response body — no page reload required; count is taken from the response payload `{flag_count, my_flag}`, not a separate refetch.

**FR-8:** Flag button on skill detail page — visible to all authenticated users (including own submitters); opens modal with reason select + optional note field + optional superseded_by_slug field (shown only when reason=superseded); unauthenticated users see a "Sign in to flag" prompt. Submit button is disabled until a reason is selected (reason select renders with a non-valid placeholder "Select a reason…"). When `myFlag` is active the button renders as "Flagged — click to retract"; clicking shows a confirmation popover ("Remove your flag for this skill?") before calling DELETE; the flag modal does not re-open on the retract path.

**FR-9:** `/admin/flags` frontend page — table showing skill name, slug, flag count, list of flags per skill; deactivate action available inline per skill. After successful inline deactivation: replace the "Deactivate" button with a "Deactivated" badge and disable further action on that row; row persists until the next page load (no automatic removal). Bulk deactivation is out of scope.

**FR-10:** Deactivate / Reactivate button visible to admins on the skill detail page; confirmation dialog shows reason input (required text area, max 1000 chars); the confirm/submit button is disabled until the reason field is non-empty; on 422 from the server, the dialog shows an inline validation error without closing

### Non-functional Requirements

**NFR-1:** Flag creation p95 latency < 200ms

**NFR-2:** `GET /admin/flags` p95 latency < 500ms at 1,000 skills with flags

**NFR-3:** Flag count is eventually consistent (denormalized counter on Skill); can differ by ±1 during concurrent flag/unflag — acceptable

**NFR-4:** Rate limit flag creation at 10/hour per user to discourage abuse

**NFR-5:** Admin routes require `require_admin` dependency (existing pattern); return 403 for non-admins

### Acceptance Criteria

**AC-1:** Given an authenticated user, when they POST `/skills/my-skill/flag` with `{reason: "broken"}`, then a `SkillFlag` doc is created and `skill.flag_count` increments by 1

**AC-2:** Given a user who already has an active flag, when they POST again with a different reason, then the existing flag is updated (not duplicated) and `flag_count` does not change

**AC-3:** Given a user with an active flag, when they DELETE `/skills/my-skill/flag`, then the flag status becomes `resolved` and `flag_count` decrements by 1

**AC-4:** Given an admin, when they POST `/admin/skills/my-skill/deactivate` with a reason, then the skill `status` becomes `deactivated`, a revision is written, and all active flags for the skill are resolved

**AC-5:** Given a deactivated skill, when any user GETs `/skills/my-skill`, then the API returns 410 with `{code: "deactivated", reason: "...", superseded_by_slug: ...}`

**AC-6:** Given a deactivated skill's detail page, when a user visits, then the `Tombstone` component is rendered (already implemented — just needs real data). If `superseded_by_slug` itself resolves to a deactivated skill, the Tombstone renders the slug as plain text with a note "(also deactivated)" rather than a live link.

**AC-7:** Given an unauthenticated user on the skill detail page, when they view the flag button, then it reads "Sign in to flag" and redirects to login on click

**AC-8:** Given a non-admin user, when they call `GET /admin/flags`, then the response is 403

---

## Module Design

**`routers/admin.py`** (new)
- Responsibility: all admin-only routes; applies `require_admin` at the router level
- Interface: `GET /api/admin/flags`, `POST /api/admin/skills/{slug}/deactivate`, `POST /api/admin/skills/{slug}/reactivate`
- Testable in isolation: yes — mock `flag_service` and `skill_service`

**`services/flag.py`** (new)
- Responsibility: flag lifecycle — create/upsert, retract, resolve_all_for_skill, list_flagged_skills
- Interface:
  - `create_or_update(skill_id, reporter_id, reason, note, superseded_by_slug) → SkillFlag`
  - `retract(skill_id, reporter_id) → None`
  - `resolve_all_for_skill(skill_id, resolved_by) → int` (returns count resolved; **[ENG-AMD-2] must also reset `Skill.flag_count = 0` via `$set` after bulk-resolving** — not via repeated `$inc` — this is an idempotent hard reset that avoids TOCTOU drift under concurrent flags+deactivate)
  - `list_flagged_skills(page, page_size) → (List[FlaggedSkillOut], int)`
- Testable in isolation: yes — all DB operations, no HTTP layer

**`services/skill.py`** (modify)
- Add `deactivate(slug, reason, superseded_by_slug, admin_id) → Skill`
- Add `reactivate(slug, reason, admin_id) → Skill`
- Both call `revision_service.record()` with the appropriate action and call `flag_service.resolve_all_for_skill()` on deactivate

**`routers/skills.py`** (modify)
- Add `POST /api/skills/{slug}/flag` — calls `flag_service.create_or_update()`
- Add `DELETE /api/skills/{slug}/flag` — calls `flag_service.retract()`
- `GET /api/skills/{slug}` gains optional `my_flag` field in response (uses `get_optional_user`)

**`schemas/flag.py`** (new)
- `FlagCreate`: `reason: FlagReason, note: Optional[str] = Field(None, max_length=500), superseded_by_slug: Optional[str] = Field(None, max_length=100)`. `superseded_by_slug` is validated at the service layer: if provided, the slug must resolve to an existing active skill (404 if not found; the flag is still accepted but a warning is returned if it resolves to a deactivated skill — same semantics as FR-4).
- `FlagOut`: `reason, note, status, created_at`
- `FlaggedSkillSummary`: `skill_slug, skill_name, flag_count, flags: List[AdminFlagOut]`
- `AdminFlagOut`: extends `FlagOut` with `reporter_id, resolved_by, resolution_note`

**`frontend/components/flag-button.tsx`** (new)
- Responsibility: flag/unflag toggle button with modal; manages `my_flag` state
- Props: `skillSlug, initialFlagCount, myFlag`
- Flag path: modal opens; submit disabled until reason selected; on success updates local state from response `{flag_count, my_flag}` (no page reload)
- Retract path: when `myFlag` is active, button shows filled "Flagged — click to retract" state; click triggers confirmation popover ("Remove your flag for this skill?"); on confirm calls DELETE and clears local state from response `{flag_count}`; modal does not re-open
- Error states: POST flag 429 → show toast "You've flagged too many skills recently. Try again later." (do not close modal); POST flag other error → show inline error in modal, keep modal open; DELETE flag error → show toast, do NOT clear local `myFlag` state (leave button in "Flagged" state so user can retry)

**`frontend/components/flag-indicator.tsx`** (modify)
- Add `isMine?: boolean` prop; renders "Flagged by you" variant when true

**`frontend/app/admin/flags/page.tsx`** (new)
- Admin-only page; calls `GET /api/admin/flags`; table with deactivate action inline

---

## System Design

```
User (authenticated)
  │  POST /api/skills/{slug}/flag  {reason, note?}
  ▼
routers/skills.py
  │  get_current_user → verify auth
  │  flag_service.create_or_update(skill_id, reporter_id, ...)
  ▼
services/flag.py
  │  upsert SkillFlag (skill_flags collection)
  │  if resolvedActive → Skill.inc(flag_count, +1)
  └──► SkillFlag (MongoDB)  +  Skill.flag_count update

Admin
  │  POST /api/admin/skills/{slug}/deactivate  {reason, superseded_by_slug?}
  ▼
routers/admin.py
  │  require_admin → verify is_admin
  │  skill_service.deactivate(slug, reason, ...)
  ▼
services/skill.py
  │  Skill.status = deactivated  +  deactivation_reason
  │  revision_service.record(RevisionAction.deactivate, ...)
  │  flag_service.resolve_all_for_skill(skill_id, admin_id)
  └──► Skill (skills) + SkillRevision (revisions) + SkillFlag bulk update
```

**API contract:**

```
POST /api/skills/{slug}/flag
  Auth: Bearer (required)
  Body: { "reason": "broken"|"stale"|"superseded"|"inappropriate"|"other",
          "note": "string (max 500, optional)",
          "superseded_by_slug": "string (optional, used when reason=superseded)" }
  200: { "flag_count": 3, "my_flag": { "reason": "broken", "status": "active" } }
  401: not authenticated
  404: skill not found
  429: rate limit exceeded

DELETE /api/skills/{slug}/flag
  Auth: Bearer (required)
  200: { "flag_count": 2 }
  401: not authenticated
  404: no active flag to retract

GET /api/admin/flags?page=1&page_size=20
  Auth: Bearer (admin required)
  200: { "items": [
    { "skill_slug": "...", "skill_name": "...", "flag_count": 5,
      "flags": [{ "reporter_id": "...", "reason": "broken", "note": "...", "created_at": "..." }] }
  ], "total": 12, "page": 1, "pages": 1 }
  403: not admin

POST /api/admin/skills/{slug}/deactivate
  Auth: Bearer (admin required)
  Body: { "reason": "string (required, max 1000)", "superseded_by_slug": "string (optional, max 100)" }
  200: { "slug": "...", "status": "deactivated", "warnings": [] }
  403: not admin
  404: skill not found
  409: skill already deactivated

POST /api/admin/skills/{slug}/reactivate
  Auth: Bearer (admin required)
  Body: { "reason": "string (optional)" }
  200: { "slug": "...", "status": "active" }
  403: not admin
  404: skill not found
  409: skill already active
```

**Data model changes:** No new collections needed. `SkillFlag` already exists. **[ENG-AMD-5]** The existing compound index declaration in `SkillFlag.Settings.indexes` uses a plain list-of-tuples (`[("skill_id", 1), ("reporter_id", 1)]`) which creates a regular index without `unique=True` — the uniqueness constraint is **not** currently enforced at the DB level. Before implementing the service layer, fix this to: `IndexModel([("skill_id", 1), ("reporter_id", 1)], unique=True, name="skill_reporter_unique")`. Without this, the `find_one_and_update(upsert=True)` retry loop has nothing to catch on concurrent inserts. `flag_count` is already on `Skill`. No migrations required — additive change.

---

## ADRs

### ADR-U29: Flag upsert vs. append semantics

**Status:** Accepted

**Context:** `SkillFlag` has a unique index on `(skill_id, reporter_id)`. A user who previously flagged a skill (even if resolved) cannot insert a new record. Options: (A) upsert — reset status/reason/note on the existing record; (B) lift the unique index and allow multiple records per user per skill.

**Decision:** Upsert (A). One flag record per user per skill ever. Reset `status=active`, update `reason`/`note`/`created_at` on re-flag. Increment `flag_count` only if the record was previously `resolved`.

**Consequences:** Simple flag count arithmetic. No multi-record history per user. Acceptable: the audit value of tracking re-flag history is low.

---

### ADR-U30: Admin router location

**Status:** Accepted

**Context:** Admin routes could go in existing `routers/skills.py` (adds noise, `require_admin` must be repeated per endpoint) or a new `routers/admin.py` with `require_admin` applied at the router level.

**Decision:** New `routers/admin.py` with prefix `/api/admin`. Matches the existing frontend `/admin/*` convention.

**Implementation constraint — require_admin dependency chain:**  
The current `require_admin` signature is `def require_admin(user: User) -> User:` with no `Depends()` on `user`. FastAPI will NOT automatically inject `get_current_user` into a plain `User` parameter at router level. Two correct options:

- **Option A (recommended):** Redefine `require_admin` in `app/auth.py` to embed `get_current_user`:  
  `def require_admin(user: User = Depends(get_current_user)) -> User:`  
  Then `router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])` works correctly. Backward-compatible with existing per-endpoint usage in `labels.py`.

- **Option B (no auth.py change):** Keep current `require_admin` signature; use per-endpoint pattern from `labels.py`:  
  `user: User = Depends(get_current_user), _admin: User = Depends(require_admin)` on each admin endpoint.

**Decision:** Option A — cleaner router-level enforcement, auth.py change is minimal and safe.

**Consequences:** Clean separation. Admin routes are easy to audit. Small code addition (`main.py` gains one `include_router` call). `app/auth.py` has a one-line signature change.

---

### ADR-U31: Flag count sync strategy

**Status:** Accepted

**Context:** `flag_count` is denormalized on `Skill`. Options: (A) keep denormalized, sync via `$inc` on flag create/resolve; (B) remove denormalized count and compute live from `SkillFlag.count()` on every skill fetch; (C) scheduled reconciliation job.

**Decision:** Keep denormalized `$inc` approach (A). Live count (B) adds a query per skill fetch on list pages. Reconciliation (C) adds operational complexity. The `±1` eventual consistency window is acceptable — flags are not financial data.

**All `flag_count` mutation points:**
1. `create_or_update()` — `$inc +1` only when transitioning from resolved → active
2. `retract()` — `$inc -1` with `$max: {flag_count: 0}` floor guarantee (concurrent retracts must not produce negative count)
3. `resolve_all_for_skill()` — `$set {flag_count: 0}` on the Skill document after bulk-resolving all active flags; **not** `$inc -(count_resolved)` because `$inc` is not idempotent (could go negative under a race) and computing `count_resolved` between query and update introduces a TOCTOU window; `$set 0` is the correct hard-reset when all flags for a skill have been cleared

**Consequences:** Occasional stale count if a request crashes between the flag insert and the `$inc`. A periodic reconciliation script can be added later if drift becomes noticeable. The deactivation flush (point 3) is a bulk decrement that must be included to keep `flag_count` consistent after admin actions.

---

## Trade-offs

**Choice: Flag modal vs. inline flag button**
- Modal: captures reason + note cleanly; avoids accidental flags
- Inline: faster; lower friction
- Decision: modal. Reason is required for admin triage value; accidental flags with no context waste admin time.

**Choice: Auto-resolve flags on deactivation vs. keep them for audit**
- Auto-resolve: cleaner admin queue; deactivation is the outcome flags were requesting
- Keep: preserves the pre-deactivation flag count for historical analysis
- Decision: auto-resolve. The audit trail is preserved in the revision log. The admin queue should reflect actionable items only.

**Choice: Admin routes in `skills.py` vs. new `admin.py`**
- `skills.py`: fewer files
- `admin.py`: clear auth boundary, easier to audit, matches frontend convention
- Decision: `admin.py` (see ADR-U30)

---

## Delivery Slices

**Slice 1 — Backend flag routes (2–3 days)**
- `services/flag.py`: `create_or_update`, `retract`, `resolve_all_for_skill`
- `routers/skills.py`: `POST /flag`, `DELETE /flag`
- `schemas/flag.py`: `FlagCreate`, `FlagOut`
- `GET /api/skills/{slug}` gains `my_flag` field
- Unit tests for flag service (upsert, retract, flag_count sync)

**Slice 2 — Backend admin routes (1–2 days)**
- `routers/admin.py`: `GET /admin/flags`, `POST /admin/skills/{slug}/deactivate`, `POST /admin/skills/{slug}/reactivate`
- `services/skill.py`: `deactivate()`, `reactivate()`
- Integration tests: deactivation writes revision + resolves flags + tombstone visible

**Slice 3 — Frontend flag UX (2 days)**
- `FlagButton` component: modal with reason/note/superseded_by_slug
- `FlagIndicator` update: "flagged by you" variant
- Skill detail page: wire up `FlagButton` + updated `FlagIndicator`

**Slice 4 — Frontend admin UI (2 days)**
- `/admin/flags` page: table sorted by count with inline deactivate action
- Skill detail page: admin deactivate/reactivate button + confirmation dialog

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| flag_count drift under concurrent flag/unflag | Low | Low | `$inc` is atomic; add reconciliation script if needed |
| Admin deactivates wrong skill | Low | High | Confirmation dialog; reactivate is one click; revision log |
| Flag button used for spam/harassment | Low | Medium | Rate limit (10/hour); `reporter_id` visible to admin; block user if abused |
| `SkillFlag` unique index conflict on re-flag | None | — | Upsert via `find_one_and_update` avoids this entirely |
| `SkillFlag` compound index missing `unique=True` — concurrent inserts bypass upsert guard | High (pre-fix) | Medium | **[ENG-AMD-5]** Fix `models/flag.py` to use `IndexModel(..., unique=True)` before writing service code |
| Revision insert fails after skill.status saved as deactivated | Very Low | Medium | Skill appears deactivated with no audit trail. Reactivate → re-deactivate creates the missing revision. No user data loss. |
| Flag resolution fails after skill deactivated | Very Low | Low | Admin queue may briefly show a deactivated skill with active flags. Flags auto-removed when skill is hard-deleted. Admin can tolerate short inconsistency. |

---

## Definition of Done

- [x] `POST /api/skills/{slug}/flag` creates / upserts flag and updates flag_count
- [x] `DELETE /api/skills/{slug}/flag` retracts flag and updates flag_count
- [x] `GET /api/admin/flags` returns flagged skills sorted by count (admin only, 403 for non-admin)
- [x] `POST /api/admin/skills/{slug}/deactivate` deactivates skill, writes revision, resolves active flags
- [x] `POST /api/admin/skills/{slug}/reactivate` reactivates skill, writes revision
- [x] `GET /api/skills/{slug}` response includes `my_flag` when user is authenticated
- [x] `FlagButton` component renders on skill detail for authenticated users; unauthenticated users see sign-in prompt
- [x] `FlagIndicator` shows real count and "flagged by you" state
- [x] `/admin/flags` page renders flagged skill queue with inline deactivate action
- [x] Admin deactivate/reactivate button visible on skill detail for admins
- [x] Deactivated skill shows `Tombstone` on detail page (existing component, now wired up)
- [x] `SkillFlag` compound index `(skill_id, reporter_id)` uses `IndexModel(..., unique=True)` — enforced at DB layer, not just application layer
- [x] Unit tests (see `test_flag_service.py`): **[ENG-AMD-6]** U-01 through U-32 as specified in round-1-er.md — flag upsert (new, re-flag same reason, re-flag different reason, re-flag after retract), retract (floor guard, not-found, already-resolved), resolve_all_for_skill (3-flag bulk reset flag_count=0, no-op for 0 active flags, mixed active/resolved, resolved_by set), list_flagged_skills (active-skills-only filter, sort order, field presence)
- [x] Integration tests (see `test_flag_routes.py`): **[ENG-AMD-6]** I-01 through E-01 as specified in round-1-er.md — POST flag (auth, upsert, 401, 404, 410 for deactivated, 422 on bad note/reason), DELETE flag (retract, 404 no flag, 401), GET skill my_flag field (null unauthed, null no-flag, set after flag, resolved after retract), GET admin/flags (200 admin, 403 non-admin, 401 unauthed, deactivated-skill excluded), POST deactivate (200 + revision + flags resolved + flag_count=0 + 410 on subsequent GET, 403, 409 on already-deactivated, superseded_by_slug stored), POST reactivate (200 + revision + 200 on subsequent GET, 403, 409 on already-active), end-to-end flow E-01
- [x] Test: per-user rate limit fires on 11th flag from same user within 1 hour → 429; different user can still flag the same skill
- [x] Test: POST flag with `superseded_by_slug` pointing to a deactivated skill → 200 with `warnings` field in response (flag still accepted)
- [x] Test: POST admin/deactivate with `superseded_by_slug` pointing to a deactivated skill → 200 with `warnings` field; admin UI must surface warning
- [x] ADRs written: `docs/adr/adr-u29-flag-upsert.md`, `docs/adr/adr-u30-admin-router.md`, `docs/adr/adr-u31-flag-count-sync.md`
- [x] `CHANGELOG.md` Unreleased section updated with #012 entry (flag routes, admin routes, FlagButton, FlagIndicator, /admin/flags page, tombstone wiring)
- [x] `PRD.md` API table updated to match implemented endpoint shapes (`POST /api/skills/{slug}/flag`, `DELETE /api/skills/{slug}/flag`, `GET /api/admin/flags`, `POST /api/admin/skills/{slug}/deactivate`, `POST /api/admin/skills/{slug}/reactivate`)

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-03
**Rounds:** 2

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | ✅ PASS | Y | SkillFlag unique index missing `unique=True` (blocking); rate limit is per-IP not per-user; `resolve_all_for_skill` should use `$set 0` not `$inc -(N)` |
| codebase-arch-review | ✅ PASS | Y | flag_count stale on deactivation (fixed: `$set 0`); `require_admin` router-level dependency chain broken (fixed: Option A — embed `get_current_user`); deactivation non-atomicity documented in Risk Register |
| codebase-eng-review | ✅ PASS | Y | Rate limit per user_id; flagging deactivated skill returns 410; admin queue filters active skills only; 409 on idempotent deactivate/reactivate; 40-case test plan added |
| doc-review | ✅ PASS | Y | CHANGELOG missing from DoD; PRD.md API paths misaligned with implemented endpoints |
| security-review | ✅ PASS | Y | note max_length in FlagCreate schema; superseded_by_slug max_length + existence validation; deactivation reason max_length=1000; flag_count floor via conditional update |
| codebase-ux-review | ✅ PASS | Y | Flag modal submit disabled until reason selected; retract toggle + confirmation popover; tombstone chained deactivation guard; admin queue row badge after deactivate; optimistic update from response; FR-10 confirm disabled until reason non-empty; FlagButton error states |

**Accepted warnings:**
- Motor 3.7.1 deprecated May 2025 (same as #015 — non-blocking under current Beanie 1.26 dependency)
- Deactivation is three non-atomic DB operations (skill save → revision insert → flag bulk-resolve); partial failure modes documented in Risk Register; no transaction primitive available in this stack

**Unresolved decisions:** none

---

## Relationship to Other Tasks

- **#003 (Label UX):** Labels and flags are explicitly kept separate — see Key Decision above.
- **#008 (Auth hardening):** Admin-only routes depend on reliable identity from the hardened auth header.
- **#011 (User activity):** Flag activity (skills a user has flagged) could appear on the user profile as a future extension.
- **#013 (Revision history):** Deactivation and reactivation are recorded as revisions — visible in the revision timeline once #013 ships.

---

### Reviewer output

<details>
<summary>research — Round 1 (PASS WITH AMENDMENTS)</summary>

**Key findings:**

- BLOCKING: SkillFlag unique index is `[("skill_id", 1), ("reporter_id", 1)]` without `unique=True` — compound index created, uniqueness constraint NOT enforced. Entire upsert strategy depends on this constraint. Fix: `IndexModel([...], unique=True)` in models/flag.py. DoD item added.
- Non-blocking: Limiter uses `get_remote_address` — per-IP, not per-user. Corrected in FR-1.
- Non-blocking: Router-level `require_admin` requires `get_current_user` in endpoint signatures when user context needed. ADR-U30 Option A resolves this.
- Non-blocking: `resolve_all_for_skill` should use `$set {flag_count: 0}` not `$inc -(N)`. Fixed in ADR-U31.
- Confirmed: `find_one_and_update` upsert pattern is correct (same as ratings.py). Denormalized `$inc` is safe (MongoDB atomic). Motor deprecation non-blocking.

**Status: PASS WITH AMENDMENTS**

</details>

<details>
<summary>codebase-arch-review — Round 2 (PASS)</summary>

**Key findings (Round 1 + Round 2):**

- CRITICAL: `flag_count` not zeroed on deactivation — `resolve_all_for_skill()` bulk-resolved flags but never updated `Skill.flag_count`. Fixed: service spec now requires `$set {flag_count: 0}`.
- CRITICAL: `require_admin` without embedded `get_current_user` silently passes non-admins as router-level dependency. Fixed: ADR-U30 Option A (change signature to embed `Depends(get_current_user)`).
- MATERIAL: Deactivation is three non-atomic DB operations. Partial failure modes documented in Risk Register.
- MINOR: SkillFlag index list syntax creates non-unique compound index. Fixed in DoD.
- Round 2: ADR-U31 still said `$inc -(count_resolved)` while ENG-AMD-2 said `$set 0` — contradiction fixed.

**Status: PASS**

</details>

<details>
<summary>codebase-eng-review — Round 2 (PASS)</summary>

**Key findings (Round 1 + Round 2):**

- BLOCKING: Rate limit `get_remote_address` bypassed via Next.js proxy. Fixed: per-user_id key function required in FR-1.
- BLOCKING: `resolve_all_for_skill` left `flag_count` non-zero after deactivation. Fixed: `$set {flag_count: 0}`.
- BLOCKING: Flagging a deactivated skill — undefined behavior. Fixed: FR-1 returns 410.
- HIGH: Admin flag queue must filter `status=active` to exclude deactivated skills. Fixed in FR-3.
- HIGH: Deactivate/reactivate idempotency — 409 if already in target state. Fixed in FR-4/FR-5.
- SkillFlag unique index missing `unique=True`. Fixed in DoD.
- 40-case test plan added to DoD covering all service methods and routes.
- Round 2: ADR-U31 `$inc` vs `$set` contradiction fixed; 409 added to API contract; 3 test cases added for rate-limit, superseded_by_slug warning paths.

**Status: PASS**

</details>

<details>
<summary>doc-review — Round 1 (PASS WITH AMENDMENTS)</summary>

**Key findings:**

- DC-1 (BLOCKING): CHANGELOG missing `## Unreleased` entry for #012. Added to DoD.
- DC-2 (NON-BLOCKING): PRD.md API table has wrong paths (`/flags` plural, PATCH method) — plan uses singular `/flag`, DELETE. Updated DoD to require PRD.md fix.
- DC-3: ADR files (adr-u29, adr-u30, adr-u31) not yet on disk — correctly tracked in DoD already.
- DC-4/5: No separate API reference needed — this project uses CHANGELOG + PRD.md. Consistent with pattern.

**Status: PASS WITH AMENDMENTS**

</details>

<details>
<summary>security-review — Round 2 (PASS)</summary>

**Key findings (Round 1 + Round 2):**

- BLOCKER: `note` max 500 chars not enforced in Pydantic schema — only in model. Fixed: `Field(None, max_length=500)` in FlagCreate.
- BLOCKER: `superseded_by_slug` — arbitrary string, no length or existence check. Fixed: `max_length=100` + service-layer existence validation (404 if not found, warning if deactivated).
- BLOCKER: Rate limit per-IP bypassed via proxy. Fixed: per-user_id.
- MEDIUM: `deactivation_reason` no max_length — tombstone renders verbatim. Fixed: `max_length=1000` in FR-4.
- MEDIUM: `flag_count` floor via bare `$inc` — race-prone. Fixed: conditional update with `$max: {flag_count: 0}` in FR-2; `resolve_all_for_skill` uses `$set 0`.
- LOW: Admin `superseded_by_slug` no max_length. Fixed: `max_length=100` in FR-4.
- Verified: `require_admin` Option A, router-level dependency chain correct.

**Status: PASS**

</details>

<details>
<summary>codebase-ux-review — Round 2 (PASS)</summary>

**Key findings (Round 1 + Round 2):**

- BLOCKER: Flag modal submit enabled without reason — submit should be disabled until reason selected. Fixed: FR-8 + FlagButton spec.
- HIGH: Retract path not specified — FlagButton had no toggle or confirmation flow. Fixed: "Flagged — click to retract" toggle + confirmation popover.
- MEDIUM: Tombstone with chained deactivated `superseded_by_slug` — infinite redirect loop risk. Fixed: AC-6 + FR-4 warning; Tombstone renders plain text with "(also deactivated)".
- MEDIUM: Admin queue row state after inline deactivate unspecified. Fixed: FR-9 shows "Deactivated" badge, row persists until reload.
- LOW: Optimistic update model unspecified. Fixed: FR-7/FlagButton update from response payload.
- Round 2: FR-10 confirm button disabled until reason non-empty; FlagButton error states specified (429 toast, POST error inline, DELETE error preserves state).

**Status: PASS**

</details>
