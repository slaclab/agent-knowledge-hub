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

---

## Design

### Backend

`POST /api/skills/{slug}/rate` — requires auth, body `{"value": 1–5}`.

1. Look up skill by slug → 404 if missing
2. Upsert `Rating` (find by `skill_id` + `user_id`, create or update `value`/`updated_at`)
3. Recompute `avg_rating` and `rating_count` via MongoDB aggregation on the `ratings` collection, write back to the `Skill` document
4. Return updated `{"avg_rating": float, "rating_count": int}`

No separate GET endpoint needed — aggregate values are already on the skill response.

### Frontend

- `StarRating` gains an `onRate?: (value: number) => void` prop; when provided, stars become clickable (hover highlight, pointer cursor)
- Skill detail page passes `onRate` only when user is authenticated
- On click: call `POST /api/skills/{slug}/rate`, optimistically update local state, revert on error
- Unauthenticated state: existing read-only display unchanged

---

## Implementation Plan

- [ ] Backend: add `rate_skill` service function in `app/services/skill.py` (upsert + recompute)
- [ ] Backend: add `POST /api/skills/{slug}/rate` route in `app/routers/skills.py`
- [ ] Backend: register `Rating` model in `app/main.py` Beanie init
- [ ] Frontend: extend `StarRating` with optional `onRate` prop + hover/click behaviour
- [ ] Frontend: wire `onRate` in skill detail page, call API, handle optimistic update
- [ ] Frontend: add `rateSkill` helper to `lib/api.ts`
- [ ] Tests: unit test `rate_skill` service (upsert + avg recomputation)

---

## Problems & Solutions

_None yet._
