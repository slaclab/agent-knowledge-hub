# 005 — Skill Ratings

**Status:** ⬜ Open
**Branch:** —
**PR:** —

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
- **FR-4:** The endpoint returns `{"avg_rating": float, "rating_count": int}`.
- **FR-5:** `StarRating` gains an optional `onRate?: (value: number) => void` prop; when provided, stars are interactive (hover highlight, pointer cursor, click handler).
- **FR-6:** The `readonly` prop bug (inverted `cursor-not-allowed` logic) is fixed as part of this change.
- **FR-7:** A new `RatingWidget` client component wraps `StarRating` and calls `rateSkill()` on click, with optimistic update and error revert.
- **FR-8:** The skill detail page replaces the "coming soon" block with `RatingWidget`, passing `slug` and initial `avg_rating`/`rating_count`. Auth state comes from `useAuth()` inside the widget.
- **FR-9:** Unauthenticated users see the read-only `StarRating` display plus "Sign in to rate." text, matching the `LabelSection` pattern.
- **FR-10:** `rateSkill(slug, value)` helper is added to `lib/api.ts`, calling `CLIENT_BASE` (Next.js proxy).
- **FR-11:** A Next.js proxy route `app/api/skills/[slug]/rate/route.ts` forwards `POST` to the backend with `backendHeaders()`.

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
    - reads auth from useAuth() internally
    - renders StarRating with onRate when user is authenticated
    - renders read-only StarRating + "Sign in to rate." when unauthenticated
  Status: New
  Testable in isolation: Yes — mock useAuth() and rateSkill()

Module: rateSkill (lib/api.ts)
  Responsibility: POST /api/skills/{slug}/rate with value, return updated avg/count
  Interface: rateSkill(slug: string, value: number) → Promise<{ avg_rating, rating_count } | null>
  Status: New (additive to api.ts)
  Testable in isolation: Yes (mock fetch)

Module: Next.js proxy route — /app/api/skills/[slug]/rate/route.ts
  Responsibility: Forward POST to backend with backendHeaders(); pass through response
  Interface: POST handler, delegates to BACKEND /api/skills/{slug}/rate
  Status: New
  Testable in isolation: Yes (integration test via fetch mock)

Module: rate_skill service function (app/services/skill.py)
  Responsibility: Upsert Rating doc; recompute avg_rating + rating_count on Skill
  Interface: rate_skill(skill_id: str, user_id: str, value: int) → tuple[float, int]
  Status: New (added to SkillRepository or as standalone function)
  Testable in isolation: Yes — test with real Beanie + mongomock or test DB

Module: POST /api/skills/{slug}/rate route (app/routers/skills.py)
  Responsibility: Auth guard, slug→skill lookup, call rate_skill, return updated aggregates
  Interface: POST /{slug}/rate, body: { value: int }, returns: { avg_rating, rating_count }
  Status: New (additive to skills router)
  Testable in isolation: Yes — FastAPI TestClient
```

---

## System Design

```
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
             →  on error: revert optimistic state, show toast/inline error
```

**New backend schema** (add to `app/schemas/skill.py`):

```python
class RateSkillIn(BaseModel):
    value: int = Field(..., ge=1, le=5)

class RateSkillOut(BaseModel):
    avg_rating: float
    rating_count: int
```

**API contract:**

```
POST /api/skills/{slug}/rate
  Auth: required (401 if missing)
  Body: { "value": 1–5 }

200 OK:
  { "avg_rating": 4.2, "rating_count": 17 }

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

Choice: Service-layer uniqueness for (skill_id, user_id) (vs. DB unique index)
  + Index already exists as a regular index; no migration needed
  - Theoretical TOCTOU race if two identical requests arrive simultaneously
  Decision: Accept the risk. Duplicate ratings from racing requests is
            cosmetically annoying but not a safety issue. Can add a unique
            index in a follow-up if it becomes a problem.
```

---

## Delivery Slices

```
Slice 1 — Backend (1d)
  - Add RateSkillIn / RateSkillOut schemas to app/schemas/skill.py
  - Add rate_skill() to SkillRepository in app/services/skill.py
      (upsert Rating, aggregation pipeline, write back to Skill)
  - Add POST /{slug}/rate route to app/routers/skills.py
  - Unit test rate_skill: upsert creates, re-rate updates, aggregates correct
  - Integration test: route returns 401 unauth, 404 bad slug, 200 with updated values

Slice 2 — Frontend plumbing (0.5d)
  - Add rateSkill() to lib/api.ts
  - Add app/api/skills/[slug]/rate/route.ts (POST proxy)
  - Manual smoke test: curl through proxy, verify auth forwarding works

Slice 3 — StarRating + RatingWidget (1d)
  - Fix readonly bug in star-rating.tsx
  - Add onRate prop with hover/click behaviour
  - Build RatingWidget client component (optimistic update, error revert, auth gate)
  - Replace "coming soon" block in skill detail page with <RatingWidget>
  - Manual E2E: log in → rate → average updates; log out → read-only shown

Slice 4 — Polish & tests (0.5d)
  - Verify SkillCard read-only stars unaffected
  - Add unit test for StarRating (readonly vs interactive render)
  - Add unit test for RatingWidget (optimistic update, revert on error)
```

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Two simultaneous ratings from same user create duplicate docs | Low | Low | Composite index prevents duplicates at DB level; service-layer find-then-upsert is belt-and-suspenders |
| MongoDB aggregation pipeline is slow for a skill with many ratings | Low | Low | Pipeline uses indexed `skill_id` field; at thousands of ratings it's still < 5ms |
| `useAuth()` returns `null` flicker on load (user appears logged out briefly) | Medium | Low | `RatingWidget` shows read-only view during auth loading — same as LabelSection |
| Optimistic update diverges from server (e.g. server rejects value) | Low | Low | On error: revert state to pre-click values and show inline error message |
| `readonly` bug fix on StarRating breaks SkillCard styling | Low | Low | SkillCard explicitly passes `readonly` prop — fix changes `!readonly` → `readonly` so the explicit `readonly` usage is unaffected |

---

## Definition of Done

- [ ] `POST /api/skills/{slug}/rate` returns correct `avg_rating` and `rating_count` after upsert
- [ ] Re-rating the same skill updates the existing `Rating` doc (no duplicates)
- [ ] Unauthenticated request returns `401`; invalid value returns `422`
- [ ] `StarRating` `readonly` bug fixed; `onRate` prop works with hover + click
- [ ] `RatingWidget` renders interactive picker for authed users, read-only + "Sign in to rate." for unauthed
- [ ] Optimistic update reverts cleanly on API error
- [ ] `SkillCard` read-only usage visually unaffected
- [ ] Unit tests: `rate_skill` service (upsert, re-rate, aggregation)
- [ ] Unit tests: `StarRating` (readonly vs interactive), `RatingWidget` (optimistic/revert)
- [ ] "Rating submission coming soon." placeholder removed from detail page

---

## Problems & Solutions

_None yet._
