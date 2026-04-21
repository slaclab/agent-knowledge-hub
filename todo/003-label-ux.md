# 003 — Label UX: Community Tagging System

**Status:** ⬜ Open

---

## Problem & Goal

**Problem:** Labels (free-form community tags) are fully modelled in the backend (`Label`, `SkillLabel` documents) but have zero functional surface: no API endpoints, no frontend UX, and `SkillOut` doesn't include label data. The list page filter for labels exists in the UI (`label-filter.tsx`) but returns no data. Users have no way to categorise or discover skills by topic.

**Goal:** Ship end-to-end label UX — add/remove labels on skill detail, label chips on cards, click-to-filter on list page, a `/labels` browse page, and admin tools to rename/merge/delete labels.

**Success metric:**
- Labels present on > 50% of listed skills within 60 days of launch (PRD target)
- Users can filter the skill list by label without a page reload

**Out of scope:**
- Label suggestions / autocomplete from an ML model (free-text typeahead from existing labels only)
- Voting on labels (add/remove is sufficient)
- Label hierarchies or namespaces

**Constraints:**
- Label names normalised to lowercase, hyphens only (existing model constraint)
- One `SkillLabel` record per (skill, label, user) — users can only apply a label once
- Admin operations (rename/merge/delete) must be atomic across all SkillLabel records

---

## User Stories

1. As a consumer, I want to see all labels applied to a skill on its detail page, so I understand how the community categorises it.
2. As a consumer, I want to click a label chip and see all skills sharing that label, so I can explore a topic.
3. As a consumer, I want to filter the skill list by one or more labels, so I can narrow results to my domain.
4. As a consumer, I want to see label chips on skill cards in the list view, so I can quickly scan topics.
5. As a consumer, I want to browse all labels at `/labels` with usage counts, so I can discover topic areas.
6. As an authenticated user, I want to add a free-form label to any skill, so I can help others find it.
7. As an authenticated user, I want the label input to suggest existing labels as I type, so I don't create duplicates accidentally.
8. As an authenticated user, I want to remove a label I personally applied, so I can correct a mistake.
9. As a consumer, I want to know if I've already applied a label to a skill, so I don't try to add it twice.
10. As a consumer, I want to see a count of how many people applied each label, so I know which tags are well-established.
11. As an admin, I want to rename a label globally, so the taxonomy stays clean.
12. As an admin, I want to merge two labels into one, so duplicates are consolidated.
13. As an admin, I want to delete a label and remove it from all skills, so stale tags are cleaned up.
14. As an admin, I want a label management dashboard listing all labels with usage counts, so I can identify noisy or redundant tags.
15. As a consumer, I want the label filter to be reflected in the URL, so I can share a filtered view.
16. As an unauthenticated visitor, I want to see labels on skills and filter by them, so I can browse without logging in.
17. As an unauthenticated visitor, when I try to add a label, I want to see a prompt explaining I need to be logged in, not a broken UI.

---

## Requirements

### Functional

**Backend**
- FR-L1: `GET /api/labels` — list all labels ordered by `usage_count` desc; supports `?q=<prefix>` for typeahead.
- FR-L2: `GET /api/labels/:name` — single label detail with `usage_count`.
- FR-L3: `POST /api/skills/:slug/labels` — add a label to a skill (auth required). Body: `{ "name": "<label>" }`. Label name normalised to lowercase hyphens. Creates `Label` document if it doesn't exist; increments `usage_count`; creates `SkillLabel`. Returns 409 if caller already applied this label.
- FR-L4: `DELETE /api/skills/:slug/labels/:name` — remove a label the caller applied (auth required). Decrements `usage_count`. Returns 404 if label not applied by caller.
- FR-L5: `GET /api/skills/:slug/labels` — list all labels on a skill with `applied_by` list per label.
- FR-L6: `SkillOut` and `SkillListOut` schemas include `labels: list[LabelOut]` (name + count of appliers).
- FR-L7: `GET /api/skills` supports `?labels=<comma-separated>` filter (already partially wired; make it functional).
- FR-L8: Admin — `PATCH /api/admin/labels/:id` — rename label; all `SkillLabel` records updated atomically.
- FR-L9: Admin — `POST /api/admin/labels/:id/merge` — merge label B into label A; all SkillLabel records for B updated to A; B deleted.
- FR-L10: Admin — `DELETE /api/admin/labels/:id` — delete label and all its SkillLabel records.
- FR-L11: Admin — `GET /api/admin/labels` — all labels with usage counts (same as public but includes zero-usage labels).

**Frontend**
- FR-L12: Skill cards show up to 5 label chips; "+N more" if > 5.
- FR-L13: Clicking a label chip on a card or detail page navigates to `/skills?labels=<name>`.
- FR-L14: Skill detail page: label section shows all labels. Authenticated users see an "Add label" input with typeahead from `GET /api/labels?q=`. Authenticated users can remove labels they applied (× button).
- FR-L15: Label filter on list page (`label-filter.tsx`) is wired to real data from `GET /api/labels`; selected labels reflected in URL `?labels=`.
- FR-L16: `/labels` page — lists all labels sorted by usage count; click navigates to filtered skill list.
- FR-L17: Unauthenticated users see label chips read-only; "Add label" input shows tooltip "Log in to add labels".

### Non-Functional

- NFR-L1: Label add/remove acknowledges within 500ms (PRD NFR-3).
- NFR-L2: Typeahead responds in < 200ms for prefix search on up to 10k labels.
- NFR-L3: Admin rename/merge operations are atomic (MongoDB transaction or two-phase update with rollback).

### Acceptance Criteria

- AC-L1: Given an authenticated user adds label "data-viz" to a skill, the label chip appears on the card and detail page immediately.
- AC-L2: Given a user clicks label "data-viz" on any card, the list page filters to skills tagged "data-viz".
- AC-L3: Given a user tries to add a label they've already applied, the UI shows the label already highlighted — no duplicate created (PRD AC-10).
- AC-L4: Given admin renames "data-viz" to "data-visualization", all skills formerly tagged "data-viz" now show "data-visualization" (PRD AC-4).
- AC-L5: Given admin merges "llms" into "llm", all skills formerly tagged "llms" are now tagged "llm" and "llms" is gone (PRD AC-5).
- AC-L6: Given an unauthenticated visitor, label chips are visible but "Add label" is disabled with a tooltip.
- AC-L7: Given label filter `?labels=web-scraping`, only skills carrying that label appear (PRD AC-6).

---

## Architecture

### Data Flow

```
Detail page (CSR)
  │  GET /api/skills/:slug/labels    → label list with applied_by
  │  GET /api/labels?q=<prefix>      → typeahead suggestions
  │  POST /api/skills/:slug/labels   → add label (auth)
  │  DELETE /api/skills/:slug/labels/:name → remove (auth)
  ▼
Backend LabelService
  │  normalise(name) → lowercase, hyphens
  │  upsert Label document
  │  create/delete SkillLabel
  │  inc/dec Label.usage_count
  ▼
MongoDB (labels, skill_labels collections)
```

### Atomic Admin Operations

```
Rename label A → B:
  1. Update Label.name = B, push A to Label.aliases
  2. No SkillLabel changes needed (SkillLabel stores label_id not name)

Merge label B into A:
  1. Find all SkillLabel where label_id = B.id
  2. For each: if (skill_id, A.id, applied_by) doesn't exist → update label_id = A.id
              else → delete (dedup)
  3. Add A.usage_count += B.usage_count (minus deduped count)
  4. Delete Label B and all remaining SkillLabel for B

Delete label A:
  1. Delete all SkillLabel where label_id = A.id
  2. Delete Label A
```

### API Contract

```
GET  /api/labels?q=<prefix>&limit=20
     → [{ name, usage_count }]

GET  /api/skills/:slug/labels
     → [{ name, usage_count, applied_by_me: bool }]

POST /api/skills/:slug/labels
     Body: { name: str }
     → 200 { name, usage_count } | 409 already applied

DELETE /api/skills/:slug/labels/:name
     → 204 | 404 not applied by caller

PATCH /api/admin/labels/:id
     Body: { name: str }
     → 200 Label

POST /api/admin/labels/:id/merge
     Body: { into_id: str }
     → 200 Label (the target)

DELETE /api/admin/labels/:id
     → 204
```

### Schema Changes

```python
# New response schema
class LabelOut(BaseModel):
    name: str
    usage_count: int
    applied_by_me: bool = False  # only meaningful when authed

# Add to SkillOut and SkillListOut
labels: List[LabelOut] = []
```

Migration: additive — `labels: []` default for all existing skills. No data migration needed.

---

## Modules

**LabelService (new, `backend/app/services/label.py`)**
- `add(skill_id, name, actor_id)` → LabelOut | raises Duplicate
- `remove(skill_id, name, actor_id)` → None | raises NotFound
- `list_for_skill(skill_id, viewer_id)` → List[LabelOut]
- `search(q, limit)` → List[LabelOut]
- `rename(label_id, new_name, actor_id)` — admin
- `merge(source_id, target_id, actor_id)` — admin
- `delete(label_id, actor_id)` — admin
- Testable: Yes — mongomock

**Labels router (new, `backend/app/routers/labels.py`)**
- `GET /api/labels`, `GET /api/skills/:slug/labels`
- `POST/DELETE /api/skills/:slug/labels/:name`
- Admin sub-router at `/api/admin/labels`

**LabelSection component (new, `frontend/components/label-section.tsx`)**
- Shows label chips + counts, "Add label" typeahead input, remove button
- Calls `/api/skills/:slug/labels` on mount, `/api/labels?q=` for typeahead
- Auth-aware via `useAuth()`

**LabelFilter (modify, `frontend/components/label-filter.tsx`)**
- Wire to real `GET /api/labels` data (currently renders nothing)
- Multi-select chips → updates `?labels=` URL param

**SkillCard (modify, `frontend/components/skill-card.tsx`)**
- Add label chips (up to 5 + overflow count)

**`/labels` page (new, `frontend/app/labels/page.tsx`)**
- SSR: fetches all labels sorted by usage_count
- Grid of label chips with counts; each links to `/skills?labels=<name>`

---

## Trade-offs

**`usage_count` denormalised on Label vs. count query**
- `+` Fast reads; no aggregation on list page
- `-` Must keep in sync on every add/remove/merge/delete
- Decision: Denormalise — label writes are infrequent; correctness enforced in LabelService

**Label typeahead in backend vs. frontend filtering**
- `+` Backend: scales to 10k+ labels; no full dump to client
- Decision: Backend `?q=prefix` search with limit=20

---

## Delivery Slices

**Slice 1 — Backend endpoints**
- `LabelService` with add/remove/list/search
- `GET /api/labels`, `GET/POST/DELETE /api/skills/:slug/labels`
- `labels` field in `SkillOut` / `SkillListOut`
- Unit tests

**Slice 2 — Frontend: cards + detail**
- Label chips on `SkillCard`
- `LabelSection` component on skill detail (add/remove, typeahead)
- Wire `label-filter.tsx` to real API data
- `/labels` browse page

**Slice 3 — Admin**
- Admin label management endpoints (rename/merge/delete)
- Admin UI: `/admin/labels` page with table + actions

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| usage_count drift from concurrent add/remove | Low | Low | Use MongoDB `$inc` atomic operator |
| Merge creates duplicate SkillLabel records | Medium | Medium | Dedup check in merge logic; unit tested |
| Label spam (many meaningless tags) | Medium | Medium | Admin can delete; rate-limit label adds per user per skill (max 5) |
| Rename breaks existing `?labels=` URL filters | Low | Low | Aliases stored on Label; resolve by name OR alias in filter query |

---

## Definition of Done

- [ ] `GET /api/labels`, `GET/POST/DELETE /api/skills/:slug/labels` implemented and tested
- [ ] Admin rename/merge/delete endpoints implemented with atomicity tests
- [ ] `SkillOut` + `SkillListOut` include `labels` field
- [ ] Label chips on skill cards (up to 5 + overflow)
- [ ] `LabelSection` on detail page: view, add (typeahead), remove own
- [ ] `label-filter.tsx` wired to real API; `?labels=` URL param functional
- [ ] `/labels` browse page live
- [ ] Unauthenticated users see labels read-only with tooltip on add
- [ ] AC-L1 through AC-L7 pass in staging
