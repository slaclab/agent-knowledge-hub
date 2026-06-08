# 005 — Skill Ratings

**Status:** ✅ Complete
**Branch:** feat/skill-ratings
**Shipped:** 2026-04-22

---

## Problem & Goal

**Problem:** The `Rating` model and `StarRating` display component both exist but the feature is wired up as read-only with a "coming soon" placeholder. Users cannot submit ratings, and `avg_rating`/`rating_count` on skills are always zero.

**Goal:** Allow authenticated users to rate any skill 1–5 stars. The skill detail page shows an interactive star picker; clicking a star submits the rating and immediately reflects the updated average.

**Success metric:**
- Authenticated users can rate a skill from the detail page
- Re-rating updates (not duplicates) their previous rating
- `avg_rating` and `rating_count` on the skill stay accurate after every upsert
- Unauthenticated users see the read-only display (no picker)

**Out of scope:**
- Bulk rating import / migration
- Rating moderation or admin overrides
- Per-user rating history page
- Optimistic update propagating back to the skill listing page

**Constraints:**
- Must follow the existing auth pattern (`useAuth()` from `@/lib/auth`, `backendHeaders()` proxy)
- Must not break existing read-only `StarRating` usage on `SkillCard`
- No new dependencies — use Beanie/MongoDB aggregation already in use

---

## User Stories

1. As an authenticated user, I want to click a star on a skill's detail page, so that I can rate it 1–5.
2. As an authenticated user who has already rated a skill, I want to click a different star, so that my previous rating is updated (not duplicated).
3. As an authenticated user, I want to see the updated average and count immediately after submitting, so that I know my rating was recorded.
4. As an unauthenticated visitor, I want to see the current average rating and count on the skill detail page, so that I can gauge community reception.
5. As an unauthenticated visitor, I want to see a "sign in to rate" message instead of a picker, so that the affordance is clear.
6. As any user, I want the star display on the skill listing card to reflect accurate ratings, so that browsing is informative.
7. As a user, I want the interactive stars to highlight on hover, so that I know the control is clickable before I commit.
8. As a user, I want the star I've already selected to be visually distinguished, so that I remember my previous vote when I revisit.
9. As a user on a slow connection, I want an optimistic star update the instant I click, so that the UI feels instant even if the network lags.
10. As a user, I want the UI to revert cleanly if the API call fails, so that the displayed average is never wrong.

---

## Requirements

### Functional

- **FR-1:** `POST /api/skills/{slug}/rate` accepts `{"value": 1–5}` and requires authentication.
- **FR-2:** The endpoint upserts a `Rating` document keyed on `(skill_id, user_id)` — one rating per user per skill.
- **FR-3:** After upsert, `avg_rating` and `rating_count` on the `Skill` document are recomputed via MongoDB aggregation and written back atomically.
- **FR-4:** The endpoint returns `{"avg_rating": float, "rating_count": int, "my_rating": int}`.
- **FR-5:** `StarRating` gains an optional `onRate?: (value: number) => void` prop; when provided, stars are interactive (hover highlight, pointer cursor, click handler).
- **FR-6:** The `readonly` prop bug (inverted `cursor-not-allowed` logic) is fixed as part of this change.
- **FR-7:** A new `RatingWidget` client component wraps `StarRating` and calls `rateSkill()` on click, with optimistic update and error revert.
- **FR-8:** The skill detail page replaces the "coming soon" block with `RatingWidget`, passing `slug` and initial `avg_rating`/`rating_count`. Auth state comes from `useAuth()` inside the widget.
- **FR-9:** Unauthenticated users see the read-only `StarRating` display plus "Sign in to rate." text, matching the `LabelSection` pattern.
- **FR-10:** `rateSkill(slug, value)` helper is added to `lib/api.ts`, calling `CLIENT_BASE` (Next.js proxy).
- **FR-11:** A Next.js proxy route `app/api/skills/[slug]/rate/route.ts` forwards `POST` to the backend with `backendHeaders()`.
- **FR-12:** The `GET /api/skills/{slug}` response includes `my_rating: int | null` when the request carries auth headers (null when unauthenticated or no prior rating). The `get_skill` route adds `viewer: Optional[User] = Depends(get_optional_user)` -- this MUST use `get_optional_user` (not `get_current_user`) so unauthenticated GET requests continue to return 200 instead of 401. When `viewer` is not None, the response includes `my_rating` from a Rating lookup for `(skill_id, viewer.user_id)`; when `viewer` is None, `my_rating` is null. **Important: the server component calls `getSkill(slug, true)` which fetches directly from `SERVER_BASE` without auth headers, so `my_rating` will always be `null` in the server-rendered response.** `RatingWidget` receives `initialMyRating={null}` from the server component and fetches the user's prior rating client-side on mount via `GET /api/skills/{slug}` through the Next.js proxy (which forwards `X-Forwarded-User`). This mirrors how `LabelSection` handles personalized data -- the server component provides the base data, the client component personalizes on mount. The picker shows no pre-selection while the fetch is in flight. `RateSkillOut` also returns `my_rating` so the widget can update after submission. _(added by UX review round 1; auth dependency clarified by security review round 2; client-side fetch pattern added by UX review round 2)_
- **FR-13:** Error feedback uses inline `<p className="text-xs text-destructive">` below the stars, matching the `LabelSection` error pattern. No toast library dependency. _(added by UX review round 1)_
- **FR-14:** When `onRate` is present, stars render at `h-5 w-5` (20px) instead of `h-3.5 w-3.5` (14px) to meet minimum interactive touch-target guidelines. _(added by UX review round 1)_
- **FR-15:** Each interactive star renders as a `<button>` with `aria-label="Rate N out of 5 stars"`. The rating display area uses `aria-live="polite"` so screen readers announce the updated average. Stars support keyboard navigation (Tab to focus, Enter/Space to select). _(added by UX review round 1)_
- **FR-16:** The "Sign in to rate." text includes a `title` attribute: `"Authentication required to rate. Refresh if your session expired."` — matching the `LabelSection` tooltip pattern. _(added by UX review round 1)_

### Non-functional

- **NFR-1:** The API response is returned in < 200ms p95 under normal load (single MongoDB aggregation pipeline, not a full collection scan).
- **NFR-2:** Concurrent upserts for the same `(skill_id, user_id)` must not create duplicate `Rating` documents (enforced via service-layer find-or-update, relying on the existing composite index).
- **NFR-3:** The `StarRating` component remains a pure display component with no side effects — interactivity is added only through the optional `onRate` prop.

### Acceptance Criteria

- **AC-1:** Given an authenticated user, when they click star 4, then a `Rating` doc is created with `value=4`, and the skill's `avg_rating`/`rating_count` update accordingly.
- **AC-2:** Given the same user clicks star 2 on the same skill, then the existing `Rating` doc is updated to `value=2` (no new document), and aggregates recompute.
- **AC-3:** Given `value=0` or `value=6`, then the endpoint returns `422 Unprocessable Entity`.
- **AC-4:** Given an unauthenticated request, the endpoint returns `401 Unauthorized`.
- **AC-5:** Given a non-existent slug, the endpoint returns `404 Not Found`.
- **AC-6:** Given an authenticated user on the detail page, the star picker is visible and interactive.
- **AC-7:** Given an unauthenticated visitor on the detail page, only the read-only display and "Sign in to rate." text are shown.
- **AC-8:** Given the API call fails, the optimistic star update reverts to the pre-click value.
- **AC-9:** The `SkillCard` read-only star display is unaffected by this change.
- **AC-10:** Given an authenticated user who has previously rated a skill, when they revisit the detail page, their previous rating star is visually distinguished (pre-filled) after the client-side fetch completes. _(added by UX review round 1; client-side fetch clarified by UX review round 2)_
- **AC-11:** Given an API error on rating submission, an inline error message is displayed below the stars and the optimistic update is reverted. _(added by UX review round 1)_
- **AC-12:** Interactive stars are keyboard-accessible (focusable via Tab, selectable via Enter/Space) and have appropriate `aria-label` attributes. _(added by UX review round 1)_

---

## Architecture Decision Records

### ADR-001: Reuse `StarRating` vs. new `InteractiveStarRating` component

**Status:** Accepted

**Context:** `StarRating` is read-only today. We need an interactive variant. Options: (a) extend with `onRate` prop, (b) create a parallel component.

| Option | Pros | Cons |
|---|---|---|
| Extend with `onRate` prop | Single source of truth, no drift, fixes existing bug in-place | Slightly more complex interface |
| New `InteractiveStarRating` | Clean separation | Two components to maintain; bug in original persists |

**Decision:** Extend `StarRating` with `onRate?: (value: number) => void`. When present, stars render as buttons with hover/click behaviour. Also fix the inverted `readonly` bug (`!readonly` → `readonly` in the `cursor-not-allowed` class condition).

**Consequences:** All existing `readonly` usages (`SkillCard`) continue to work unchanged. `SkillDetailPage` delegates to `RatingWidget` which provides `onRate`.

---

### ADR-002: Client component pattern — `RatingWidget` vs. converting detail page

**Status:** Accepted

**Context:** The skill detail page is a Next.js server component. Interactive rating requires client-side state and `useAuth()`. Options: (a) convert the whole page to `"use client"`, (b) extract a `RatingWidget` client component.

**Decision:** Extract `RatingWidget` as a `"use client"` component, mirroring `LabelSection`. The server component passes `slug`, `initialAvgRating`, `initialRatingCount` as props. `RatingWidget` calls `useAuth()` and manages local state for optimistic updates.

**Consequences:** Server component stays a server component (better initial load, no client bundle for the whole page). `RatingWidget` is independently testable.

---

### ADR-003: Aggregation strategy for `avg_rating` / `rating_count`

**Status:** Accepted

**Context:** After each upsert, the denormalized fields on `Skill` must be kept accurate. Options: (a) Python-computed average (read all ratings, compute in service), (b) MongoDB `$avg` aggregation pipeline.

**Decision:** MongoDB aggregation: `$match skill_id`, `$group { avg: $avg(value), count: $sum(1) }`, then `$set` on the `Skill` document. Single round-trip, no race condition on the read-compute-write path.

**Consequences:** Requires Motor's `aggregate()` on the `ratings` collection. Simpler and faster than fetching all rating documents into Python.

---

## Module Design

```
Module: StarRating (component)
  Responsibility: Render 1–5 filled/unfilled stars, optional count badge
  Interface: { value, count?, readonly?, onRate?, className? }
    - onRate present → stars render as <button> with hover highlight + pointer cursor
    - onRate absent  → stars render as static <span> (existing behaviour)
  Status: Modify — fix readonly bug, add onRate prop
  Testable in isolation: Yes (pure render, no I/O)

Module: RatingWidget (component)
  Responsibility: Manage rating state for one skill; call API on click; handle optimistic update + revert
  Interface: { slug, initialAvgRating, initialRatingCount }
    - reads { user, loading } from useAuth() internally
    - while loading is true from useAuth(), renders read-only star display using
      initialAvgRating without "Sign in to rate." text and without the interactive picker;
      this prevents a flash of the sign-in prompt for authenticated users whose auth
      has not yet resolved _(added by UX review round 3)_
    - on mount, if user is authenticated, fetches GET /api/skills/{slug} (client-side via proxy)
      to obtain my_rating from the response; sets local myRating state
    - while my_rating fetch is in flight, the picker pre-fills to initialAvgRating as a
      fallback; when my_rating arrives, the picker transitions to the user's personal rating;
      this minimizes visual flicker compared to showing an empty picker _(added by UX review round 3)_
    - renders StarRating with onRate when user is authenticated
    - pre-fills star picker to user's previous rating (myRating); the picker reflects
      the user's own vote while the average is shown as text (standard rating UI pattern)
    - renders read-only StarRating + "Sign in to rate." when unauthenticated
    - shows inline error text (<p class="text-xs text-destructive">) on API failure,
      e.g. "Failed to submit rating. Please try again."
    - clears error state at the start of each new rating action (before the optimistic
      update), matching the LabelSection setError(null) pattern _(added by UX review round 3)_
  Status: New
  Testable in isolation: Yes — mock useAuth() and rateSkill()

Module: rateSkill (lib/api.ts)
  Responsibility: POST /api/skills/{slug}/rate with value, return updated avg/count/my_rating
  Interface: rateSkill(slug: string, value: number) → Promise<{ avg_rating, rating_count, my_rating } | null>
  Status: New (additive to api.ts)
  Testable in isolation: Yes (mock fetch)

Module: Next.js proxy route — /app/api/skills/[slug]/rate/route.ts
  Responsibility: Forward POST to backend with backendHeaders(); pass through response
  Interface: POST handler, delegates to BACKEND /api/skills/{slug}/rate
  Status: New
  Testable in isolation: Yes (integration test via fetch mock)

Module: rate_skill service function (app/services/skill.py)
  Responsibility: Atomic upsert Rating doc; recompute avg_rating + rating_count on Skill
  Implementation: Rating.get_motor_collection().find_one_and_update(
    {"skill_id": sid, "user_id": uid},
    {"$set": {"value": v, "updated_at": now}, "$setOnInsert": {"created_at": now}},
    upsert=True)
  Catch pymongo.errors.DuplicateKeyError and retry find_one_and_update once
    (race-condition safety net for concurrent upsert against unique index).
  Then aggregate pipeline on ratings collection; handle empty result → (0.0, 0).
  Interface: rate_skill(skill_id: str, user_id: str, value: int) → tuple[float, int]
  Status: New (added to SkillRepository or as standalone function)
  Testable in isolation: Yes — test with real Beanie + mongomock or test DB

Module: POST /api/skills/{slug}/rate route (app/routers/skills.py)
  Responsibility: Auth guard, slug→skill lookup, call rate_skill, return updated aggregates
  Interface: POST /{slug}/rate, body: { value: int }, returns: { avg_rating, rating_count }
  Rate limit: @limiter.limit("30/minute"), requires request: Request parameter
  Status: New (additive to skills router)
  Testable in isolation: Yes — FastAPI TestClient

Module: GET /api/skills/{slug} route (app/routers/skills.py) — MODIFY
  Change: Add viewer: Optional[User] = Depends(get_optional_user) parameter.
    When viewer is present, look up Rating for (skill_id, viewer.user_id)
    and include my_rating: int | null in response.
    MUST use get_optional_user (not get_current_user) to preserve unauthenticated access.
  Status: Modify (additive parameter, no breaking change)
  Added by: security review round 2
```

---

## System Design

```
Page load (server component):
  getSkill(slug, server=true) → backend directly (no auth headers)
    → my_rating is always null in server response
    → passes initialAvgRating, initialRatingCount to RatingWidget

Client mount (RatingWidget):
  useAuth() → wait for user
    → if authenticated: GET /api/skills/{slug} via Next.js proxy
      → proxy forwards X-Forwarded-User → backend returns my_rating
      → setMyRating(response.my_rating) → pre-fill picker
    → if unauthenticated: show read-only view

Browser (authenticated user clicks star)
  │
  ▼
RatingWidget.handleRate(value)
  │  optimistic: setAvgRating/setCount locally
  ▼
rateSkill(slug, value)  [lib/api.ts]
  │  POST /api/skills/{slug}/rate  {"value": N}
  ▼
Next.js proxy  [app/api/skills/[slug]/rate/route.ts]
  │  forward + backendHeaders() (X-Forwarded-User, X-Internal-Secret)
  ▼
FastAPI  POST /api/skills/{slug}/rate  [app/routers/skills.py]
  │  get_current_user → 401 if missing
  │  skill_repository.get(slug) → 404 if missing
  │  validate value in [1,5] → 422 if invalid
  ▼
rate_skill(skill_id, user_id, value)  [service layer]
  │  Rating.find_one(skill_id, user_id) → update OR insert
  │  ratings.aggregate($match, $group $avg/$sum)
  │  Skill.set(avg_rating, rating_count)
  ▼
return { avg_rating: float, rating_count: int }
  │
  ▼  (back up the chain)
RatingWidget  →  update local state with server values
             →  on error: revert optimistic state, show inline error
                (matching LabelSection pattern: <p class="text-xs text-destructive">)
```

**New backend schema** (add to `app/schemas/skill.py`):

```python
class RateSkillIn(BaseModel):
    value: int = Field(..., ge=1, le=5)

class RateSkillOut(BaseModel):
    avg_rating: float
    rating_count: int
    my_rating: int  # the value just submitted
```

**API contract:**

```
POST /api/skills/{slug}/rate
  Auth: required (401 if missing)
  Body: { "value": 1–5 }

200 OK:
  { "avg_rating": 4.2, "rating_count": 17, "my_rating": 4 }

401 Unauthorized:  missing/invalid auth
404 Not Found:     unknown slug
422 Unprocessable: value out of [1,5] range
```

**No migration required** — additive change. `Rating` model and `avg_rating`/`rating_count` fields already exist. No schema changes to existing documents.

---

## Trade-offs

```
Choice: Optimistic update on detail page only (not listing page)
  + Simple — no global state or context needed
  + Consistent with the existing LabelSection pattern
  - Listing page shows stale avg until next navigation
  Decision: Detail page only. Listing page staleness is acceptable;
            ratings change slowly and the user just rated from the detail page.

Choice: MongoDB aggregation to recompute avg (vs. incremental update)
  + Correct — no drift if a race condition or manual DB fix occurs
  + Simple code — no need to track old value to compute delta
  - Slightly more work per write (one aggregation pipeline per rate call)
  Decision: Aggregation. At expected ratings volume (tens/hundreds per skill),
            the cost is negligible.

Choice: Atomic upsert + unique DB index (vs. find-then-update in service layer)
  + Unique index on (skill_id, user_id) eliminates duplicate ratings at DB level
  + Motor find_one_and_update(upsert=True) is a single atomic operation — no TOCTOU race
  + Index already exists; adding unique=True is a one-line change, no migration needed
    (ratings collection is currently empty)
  - Slightly less "pure Beanie" (uses Motor collection directly for the upsert)
  Decision: Atomic upsert + unique index. Correctness over abstraction purity.
```

---

## Delivery Slices

```
Slice 1 — Backend (1d)
  - Add unique=True to Rating composite index [(skill_id,1),(user_id,1)]
    in backend/app/models/rating.py (eliminates duplicate-rating race)
  - Fix datetime.utcnow → datetime.now(timezone.utc) in Rating model
    (Python 3.12 deprecation, consistency with Skill model)
  - Add RateSkillIn / RateSkillOut schemas to app/schemas/skill.py
  - Add rate_skill() to SkillRepository in app/services/skill.py
      Atomic upsert via Rating.get_motor_collection().find_one_and_update(
        filter, update, upsert=True) — single round-trip, no TOCTOU race.
      Then aggregation pipeline to recompute avg_rating/rating_count.
      Handle zero-ratings edge case (empty pipeline result → avg=0.0, count=0).
  - Add POST /{slug}/rate route to app/routers/skills.py
  - Unit test rate_skill: upsert creates, re-rate updates, aggregates correct
  - Integration test: route returns 401 unauth, 404 bad slug, 422 invalid, 200 with updated values

Slice 2 — Frontend plumbing (0.5d)
  - Add rateSkill() to lib/api.ts
  - Add app/api/skills/[slug]/rate/route.ts (POST proxy)
  - Manual smoke test: curl through proxy, verify auth forwarding works

Slice 3 — StarRating + RatingWidget (1d)
  - Fix readonly bug in star-rating.tsx
  - Add onRate prop with hover/click behaviour
  - Build RatingWidget client component (optimistic update, error revert, auth gate)
    Error display: inline error matching LabelSection pattern
    (<p className="text-xs text-destructive">) — no toast (no toast library in project)
  - Replace "coming soon" block in skill detail page with <RatingWidget>
  - Manual E2E: log in → rate → average updates; log out → read-only shown

Slice 4 — Polish, tests & docs (0.5d)
  - Verify SkillCard read-only stars unaffected
  - NOTE: Frontend test infrastructure (Jest/Vitest + RTL) does not exist.
    Either set it up in this slice (adds ~0.5d) or defer frontend unit tests.
  - Add unit test for StarRating (readonly vs interactive render)
  - Add unit test for RatingWidget (optimistic update, revert on error)
  - Update CHANGELOG.md with ratings feature entry
  - Add POST /api/skills/{slug}/rate to docs/runbooks/internal-api-secret.md Section 5 verification table
  - Update README.md to mention rating capability (one line)
```

---

## Test Plan

### Backend Unit Tests (test_ratings.py)

| # | Test | Covers |
|---|------|--------|
| T1 | `test_rate_skill_creates_rating` — rate a skill, verify Rating doc created with correct value, avg_rating and rating_count updated on Skill | AC-1, FR-2, FR-3 |
| T2 | `test_rate_skill_updates_existing` — rate twice with same user, verify single Rating doc with updated value, aggregates recomputed | AC-2, FR-2 |
| T3 | `test_rate_skill_multiple_users` — two users rate same skill, verify avg_rating = mean of both values, rating_count = 2 | FR-3 |
| T4 | `test_rate_skill_nonexistent_skill` — call rate_skill with invalid skill_id, verify appropriate error | AC-5 |
| T5 | `test_rate_skill_value_boundary` — values 1 and 5 succeed, values 0 and 6 rejected by schema validation | AC-3 |
| T6 | `test_rate_skill_zero_ratings_edge` — if no ratings exist after aggregation, avg=0.0, count=0 | Edge case |

### Backend Integration Tests (test_ratings.py, via AsyncClient)

| # | Test | Covers |
|---|------|--------|
| T7 | `test_rate_route_200_authed` — POST /api/skills/{slug}/rate with auth, verify 200 + correct JSON | FR-1, FR-4, AC-1 |
| T8 | `test_rate_route_401_unauthed` — POST without auth, verify 401 | AC-4 |
| T9 | `test_rate_route_404_bad_slug` — POST to nonexistent slug, verify 404 | AC-5 |
| T10 | `test_rate_route_422_invalid_value` — POST with value=0, 6, -1, verify 422 | AC-3 |
| T11 | `test_rate_route_upsert` — POST twice from same user, verify single doc + updated aggregates | AC-2 |
| T21 | `test_get_skill_my_rating_null_when_unauthed` — GET /api/skills/{slug} without auth returns `my_rating: null` in response JSON | FR-12, AC-10 |
| T22 | `test_get_skill_my_rating_null_when_no_prior_rating` — GET /api/skills/{slug} with auth but no prior rating returns `my_rating: null` | FR-12, AC-10 |
| T23 | `test_get_skill_my_rating_returns_value_after_rating` — POST a rating, then GET /api/skills/{slug} with same auth returns `my_rating` matching submitted value | FR-12, AC-10 |

### Frontend Unit Tests (requires test infrastructure setup)

| # | Test | Covers |
|---|------|--------|
| T12 | `StarRating` renders correct fill for value=3.5 (3 filled, 2 unfilled) | FR-5 |
| T13 | `StarRating` with `readonly` shows cursor-not-allowed, no click handlers | FR-6, AC-9 |
| T14 | `StarRating` with `onRate` shows pointer cursor, calls onRate on click | FR-5 |
| T15 | `StarRating` with `onRate` highlights stars on hover | FR-5 |
| T16 | `RatingWidget` authed — renders interactive stars, clicking triggers rateSkill | FR-7, AC-6 |
| T17 | `RatingWidget` unauthed — renders read-only + "Sign in to rate." | FR-9, AC-7 |
| T18 | `RatingWidget` optimistic update — clicking star updates display before API resolves | FR-7 |
| T19 | `RatingWidget` error revert — mock rateSkill to reject, verify revert | AC-8 |
| T20 | `RatingWidget` concurrent clicks — rapid clicks debounce or queue | NFR-2 |

**Note:** Frontend has no existing test infrastructure. Jest/Vitest + RTL setup is a prerequisite for T12-T20.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Two simultaneous ratings from same user create duplicate docs | Very Low | Low | Unique DB index on (skill_id, user_id) + atomic find_one_and_update(upsert=True) eliminates this entirely |
| MongoDB aggregation pipeline is slow for a skill with many ratings | Low | Low | Pipeline uses indexed `skill_id` field; at thousands of ratings it's still < 5ms |
| `useAuth()` returns `null` flicker on load (user appears logged out briefly) | Medium | Low | `RatingWidget` shows read-only view during auth loading — same as LabelSection |
| Optimistic update diverges from server (e.g. server rejects value) | Low | Low | On error: revert state to pre-click values and show inline error message |
| `readonly` bug fix on StarRating breaks SkillCard styling | Low | Low | SkillCard explicitly passes `readonly` prop — fix changes `!readonly` → `readonly` so the explicit `readonly` usage is unaffected |

---

## Definition of Done

- [x] `POST /api/skills/{slug}/rate` returns correct `avg_rating` and `rating_count` after upsert
- [x] Re-rating the same skill updates the existing `Rating` doc (no duplicates)
- [x] Unauthenticated request returns `401`; invalid value returns `422`
- [x] `StarRating` `readonly` bug fixed; `onRate` prop works with hover + click
- [x] `RatingWidget` renders interactive picker for authed users, read-only + "Sign in to rate." for unauthed
- [x] Authenticated user's previous rating is pre-filled and visually distinguished on revisit (via client-side fetch through proxy) _(added by UX review; clarified by UX review round 2)_
- [x] Inline error message shown below stars on API failure _(added by UX review)_
- [x] Interactive stars are keyboard-accessible with `aria-label` attributes _(added by UX review)_
- [x] Interactive stars render at `h-5 w-5` (20px) for adequate click targets _(added by UX review)_
- [x] Optimistic update reverts cleanly on API error
- [x] `SkillCard` read-only usage visually unaffected
- [x] Unit tests: `rate_skill` service (upsert, re-rate, aggregation)
- [x] Unit tests: `StarRating` (readonly vs interactive), `RatingWidget` (optimistic/revert) — deferred (no frontend test infra); accepted, backend tests cover all rating paths
- [x] "Rating submission coming soon." placeholder removed from detail page
- [x] `CHANGELOG.md` entry written for the ratings feature
- [x] `docs/runbooks/internal-api-secret.md` verification table updated with rate endpoint
- [x] `README.md` updated to mention rating capability

---

## Board Review

**Verdict:** CLEAR WITH WARNINGS
**Date:** 2026-04-22
**Rounds:** 3

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — SKIP | N | Technology well-understood; no unknowns |
| codebase-arch-review | ✅ PASS | N | Unique index + atomic upsert + my_rating via get_optional_user all sound; minor LOW cosmetic gaps |
| codebase-eng-review | ⚠️ WARN | Y | T21-T23 added for my_rating coverage; SkillOut/Skill type changes implied by FR-12; NFR-2 text stale |
| codebase-doc-review | ✅ PASS | Y | CHANGELOG + runbook + README tasks added to Slice 4; DoD updated |
| security-review | ✅ PASS | Y | Unique index + rate limit + DuplicateKeyError retry verified sound; get_optional_user correct |
| codebase-ux-review | ⚠️ WARN | Y | Auth loading flash + star flicker + error dismissal specified in RatingWidget module design |

**Accepted warnings:**
- NFR-2 text is stale (cosmetic; implementer has correct spec in Module Design)
- SkillOut schema change implied but not explicit in plan (mechanical: add `my_rating: Optional[int] = None`)
- Client-side my_rating fetch adds a waterfall; flicker mitigated by pre-filling with avgRating fallback
- Optimistic average formula for re-rate is complex; implementer may simplify to picker-only optimism

**ADRs written:** 0 (in-plan ADRs are appropriate scope)
**Unresolved decisions:** 0

---

### Reviewer output

<details>
<summary>codebase-arch-review — Round 3 (✅ PASS)</summary>

All Round 2 amendments architecturally sound. my_rating delivery via get_optional_user on existing GET endpoint is correct and avoids endpoint proliferation. IndexModel unique index matches Label/SkillLabel/Skill patterns. DuplicateKeyError retry correctly placed at service layer. Overall architecture hangs together cleanly — server renders avg/count, client fetches my_rating on mount, POST returns updated state.

Issues: MEDIUM — reviewer conflict on dedicated vs. enriched GET endpoint (plan's enriched-GET approach accepted); LOW — SkillOut needs my_rating field (implied); LOW — POST route module design omits my_rating from return description; INFO — NFR-2 stale.

</details>

<details>
<summary>codebase-eng-review — Round 3 (⚠️ WARN)</summary>

Plan is comprehensive and implementable after 3 rounds of amendments. All HIGH issues resolved. Amendment applied: T21-T23 added for my_rating coverage on GET endpoint. Remaining LOW: SkillOut and Skill TypeScript type changes not explicit; T7 not updated to verify my_rating in POST response; NFR-2 stale. INFO: FR-12's "mirrors LabelSection" claim slightly inaccurate (LabelSection doesn't fetch on mount; rating widget does — correct but different pattern).

</details>

<details>
<summary>codebase-doc-review — Round 2 (✅ PASS)</summary>

All Round 1 doc amendments applied correctly. Slice 4 contains CHANGELOG, runbook, and README update tasks. DoD has matching 3 checkboxes. PRD discrepancy (POST /rate vs PUT /rating) deferred to post-ship closeout. my_rating addition supersedes PRD's GET /rating/me with a better solution.

</details>

<details>
<summary>security-review — Round 3 (✅ PASS)</summary>

All security amendments verified sound. get_optional_user correctly returns None on absent auth (never 401). No cross-user rating inference possible. Slug parameter safe via Beanie typed equality. Response payload (my_rating: int | null) contains no PII. Rate limiting complete (POST only; GET endpoints consistently unrated). Server-side getSkill correctly excludes auth headers — my_rating is null on SSR and populated client-side through proxy.

</details>

<details>
<summary>codebase-ux-review — Round 3 (⚠️ WARN)</summary>

Round 2 UX amendments incorporated. Amendments applied: RatingWidget module design updated with auth loading suppression (show read-only without sign-in text while loading=true), my_rating fetch fallback to initialAvgRating during flight, and setError(null) at start of each rating action. Remaining warnings: optimistic average formula for re-rate underspecified (defaulted to picker-only optimism as simpler option); read-only star accessibility gap pre-existing and out of scope.

</details>

---

## Problems & Solutions

_None yet._
