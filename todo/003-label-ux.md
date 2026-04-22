# 003 — Label UX: Community Tagging System

**Status:** 🔄 In Progress
**Branch:** feat/label-ux

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
- FR-L1: `GET /api/labels` — list all labels ordered by `usage_count` desc; supports `?q=<prefix>` for typeahead. `q` must be `re.escape()`d before use in `$regex` query to prevent ReDoS.
- FR-L2: `GET /api/labels/:name` — single label detail with `usage_count`.
- FR-L3: `POST /api/skills/:slug/labels` — add a label to a skill (auth required). Body: `{ "name": "<label>" }`. Label name normalised then validated against `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` (max 50 chars) — invalid input returns 400. Creates `Label` document if it doesn't exist; creates `SkillLabel` after successful insert; increments `usage_count` via `$inc` after insert. Returns 409 if caller already applied this label. Returns 429 if caller has applied ≥ 5 labels to this skill. Returns **201** on success.
- FR-L3b: Rate limiting — max 5 labels per user per skill (enforced in `LabelService.add()`); max 50 label-add operations per user per hour (enforced via slowapi).
- FR-L4: `DELETE /api/skills/:slug/labels/:name` — remove a label the caller applied (auth required). Resolves label by normalised name. Decrements `usage_count` via `$inc` after delete. Returns 404 if label not applied by caller.
- FR-L5: `GET /api/skills/:slug/labels` — list all labels on a skill. Uses `get_optional_user` dependency (returns `User | None`) so unauthenticated callers receive `applied_by_me: false` without 401.
- FR-L6: `SkillOut` and `SkillListOut` schemas include `labels: list[LabelOut]` (name + count of appliers). `SkillListOut` populated via batch hydration (2 extra queries per page, not N+1).
- FR-L7: `GET /api/skills` supports `?labels=<comma-separated>` AND filter. Implementation: (1) resolve label names to IDs, (2) aggregate `SkillLabel` to find skill_ids carrying ALL label_ids (`$group` + `$match count == len(ids)`), (3) `$in` on Skill. Requires `(label_id, skill_id)` compound index on `skill_labels` collection.
- FR-L8: Admin — `PATCH /api/admin/labels/:id` — rename label; wrapped in MongoDB multi-document transaction. `:id` must be a valid 24-char hex ObjectId.
- FR-L9: Admin — `POST /api/admin/labels/:id/merge` — merge label B into A; all steps in a MongoDB transaction. Body: `{ "into_id": str }` — `into_id` must be a valid ObjectId. After merge, `usage_count` recounted from actual `SkillLabel` records (not arithmetic).
- FR-L10: Admin — `DELETE /api/admin/labels/:id` — delete label and all its SkillLabel records in a MongoDB transaction.
- FR-L11: Admin — `GET /api/admin/labels` — all labels with usage counts (same as public but includes zero-usage labels).
- FR-L12b: `Label.name` index must have `unique=True`. `SkillLabel` compound index `(skill_id, label_id, applied_by)` must have `unique=True`.
- FR-L12c: New `get_optional_user` dependency added to `auth.py` returning `User | None`. Used by any public endpoint that optionally enriches responses for authenticated callers.
- FR-L12d: Labels router and admin sub-router registered in `backend/app/main.py`.

**Frontend**
- FR-L12: Skill cards show up to 5 label chips in a single row; "+N more" badge if > 5 (no wrapping). The "+N more" badge is non-interactive; clicking the card navigates to the detail page. Label chips on cards show name only (no usage counts). Chips use a distinct interactive style: `cursor-pointer`, hover background, colour differentiated from platform badges.
- FR-L13: Clicking a label chip on a card or detail page navigates to `/skills?labels=<name>`.
- FR-L14: Skill detail page: label section shows all labels with usage counts. Authenticated users see an inline combobox (always visible, compact style) with typeahead from `GET /api/labels?q=`. Authenticated users can remove labels they applied (× button on chip). Label add/remove use optimistic UI updates; on server error (409, 404, network), UI reverts and shows inline error below the combobox.
- FR-L15: `label-filter.tsx` is a **new** component (not an existing file). It renders as a multi-select popover in the controls bar of the skill list page (next to visibility filter and sort select). Fetches suggestions from `GET /api/labels`; selected labels reflected in URL `?labels=`; AND semantics (skill must carry all selected labels).
- FR-L16: `/labels` page — lists all labels sorted by usage count with counts displayed; click navigates to filtered skill list.
- FR-L17: Unauthenticated users see label chips read-only; combobox disabled with tooltip "Authentication required to add labels. Refresh if your session expired."
- FR-L18: Admin label management at `/admin/labels` (new Next.js route group `(admin)` with layout and admin guard). Delete and merge require AlertDialog confirmation: delete shows label name + affected skill count; merge shows source, target, and skill count. Both state the operation is irreversible.
- FR-L19: Empty state when label filters produce zero results: "No skills match all selected labels. Try removing some to widen your search." — shown alongside removable active-label chips.
- FR-L20: A "Labels" link appears in the global nav bar (between "Guides" and "Submit Skill") linking to `/labels`.
- FR-L21: When `user.is_admin` is true, an "Admin" link appears in the global nav bar linking to `/admin/labels`.
- FR-L22: Next.js proxy route handlers created for `/api/labels/[...]`, `/api/skills/[slug]/labels/[...]`, and `/api/admin/labels/[...]` following the existing `_internal.ts` auth-forwarding pattern.
- FR-L23: `cmdk` added to `package.json` dependencies for the combobox typeahead component.
- FR-L24: `LabelOut` TypeScript interface added to `frontend/types/skill.ts`; `labels: LabelOut[]` field added to `Skill` type.

### Non-Functional

- NFR-L1: Label add/remove acknowledges within 500ms (PRD NFR-3).
- NFR-L2: Typeahead responds in < 200ms for prefix search on up to 10k labels.
- NFR-L3: Admin rename/merge/delete operations are atomic — all steps wrapped in MongoDB multi-document transactions (Beanie `session` parameter on all find/update/delete calls within the block).

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

All admin operations wrapped in MongoDB multi-document transactions via `async with await client.start_session() as session: async with session.start_transaction()`. Motor client accessed via `Label.get_motor_collection().database.client`.

```
Rename label A → B:
  (in transaction)
  1. Update Label.name = B, push A to Label.aliases
  2. No SkillLabel changes needed (SkillLabel stores label_id not name)

Merge label B into A:
  (in transaction)
  1. Find all SkillLabel where label_id = B.id
  2. For each: if (skill_id, A.id, applied_by) doesn't exist → update label_id = A.id
              else → delete (dedup)
  3. Delete Label B and all remaining SkillLabel for B
  4. Recount: A.usage_count = await SkillLabel.find(label_id=A.id).count()

Delete label A:
  (in transaction)
  1. Delete all SkillLabel where label_id = A.id
  2. Delete Label A
```

### AND Filter Query Pattern

```
SkillService.list() with ?labels=python,data-viz:
  1. label_ids = [Label.find_one(name=n).id for n in requested_names]
  2. matching_skill_ids = db.skill_labels.aggregate([
       {$match: {label_id: {$in: label_ids}}},
       {$group: {_id: "$skill_id", count: {$sum: 1}}},
       {$match: {count: len(label_ids)}}
     ])
  3. Skill.find(In(Skill.id, matching_skill_ids))

Requires index: (label_id, skill_id) on skill_labels collection.
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

## ADRs

### ADR-001: Label chips — single row, no wrap

**Status:** Accepted

**Context:** Cards have limited vertical space; unlimited tag wrapping makes the list page inconsistent and visually noisy.

**Decision:** Render up to 5 chips in a single row; show "+N more" badge for overflow. Detail page shows all chips (no cap).

**Consequences:** Users won't see all labels at a glance on cards. Acceptable — detail page is one click away.

---

### ADR-002: Inline combobox for label input (always visible when authed)

**Status:** Accepted

**Context:** Two options: (a) hidden behind "+ Add label" click, (b) always-visible combobox at bottom of label section.

**Decision:** Always-visible inline combobox (Radix `Command` or similar). Reduces clicks for power users who label frequently.

**Consequences:** Adds ~40px height to detail page for all authenticated users even when they don't want to label. Acceptable tradeoff.

---

### ADR-003: AND semantics for multi-label filter

**Status:** Accepted

**Context:** OR semantics would widen results (any skill with any selected label). AND semantics narrow results (skill must have all selected labels).

**Decision:** AND — more useful for discovery ("show me skills tagged both `python` AND `data-viz`").

**Consequences:** With many labels selected, result set may be empty. Mitigated by showing result count live as labels are added.

---

### ADR-004: All slices ship in one PR

**Status:** Accepted

**Context:** Backend-only or frontend-only slices would be non-functional in staging; reviewers can't verify the feature end-to-end.

**Decision:** Ship backend + frontend + admin as one branch/PR. Delivery slices are development ordering, not separate PRs.

**Consequences:** Larger PR. Acceptable — the feature is cohesive and the slices are clearly separable in commits.

---

## Delivery Slices

All slices ship in one branch (`feat/label-ux`), one PR. Order of implementation:

**Slice 1 — Backend**
- Add `unique=True` to `Label.name` index and `SkillLabel` compound index
- Add `@field_validator('name')` to `Label` model enforcing `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` (max 50 chars)
- Add `get_optional_user` dependency to `auth.py`
- `LabelOut` schema; `labels` field in `SkillOut` / `SkillListOut`; update `_skill_to_out()` and `_skill_to_list_out()`
- `LabelService`: add (with rate limit) / remove / list_for_skill / search (re.escape) / rename / merge (recount) / delete — all wrapped in transactions where needed
- Labels router: `GET /api/labels`, `GET/POST/DELETE /api/skills/:slug/labels` — register in `main.py`
- Admin router: `GET/PATCH/DELETE /api/admin/labels`, `POST /api/admin/labels/:id/merge` — register in `main.py`
- Fix `SkillService.list()` to apply AND label filter via aggregation + `(label_id, skill_id)` index
- Unit tests (mongomock) per test plan

**Slice 2 — Frontend: read path**
- Add `cmdk` to `package.json`
- Add `LabelOut` TypeScript interface; add `labels: LabelOut[]` to `Skill` type
- Next.js proxy route handlers for `/api/labels/[...]`, `/api/skills/[slug]/labels/[...]`, `/api/admin/labels/[...]`
- Label chips on `SkillCard` (single row, 5 max + non-interactive overflow badge, interactive style)
- `/labels` browse page (SSR, sorted by usage_count, with counts)
- Wire `label-filter.tsx` (new component) in list page controls bar; AND filter; `?labels=` URL param; label-specific empty state
- "Labels" link in global nav

**Slice 3 — Frontend: write path + admin**
- `LabelSection` on detail page: inline combobox (cmdk, always visible when authed), usage counts, remove own, optimistic UI, auth tooltip
- `(admin)` route group with layout + admin guard; "Admin" nav link when `user.is_admin`
- `/admin/labels` page: table + rename/merge/delete with AlertDialog confirmations
- File ADRs 001–004 in `docs/adr/` as `adr-u07` through `adr-u10`
- CHANGELOG.md created; entry added for label UX feature

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

- [ ] `Label.name` unique index; `SkillLabel` compound unique index
- [ ] `Label` model `@field_validator` enforcing name regex + max 50 chars
- [ ] `get_optional_user` dependency in `auth.py`
- [ ] `LabelOut` schema; `labels` in `SkillOut` + `SkillListOut` (batch hydration)
- [ ] `LabelService` — add (rate-limit)/remove/list_for_skill/search(re.escape)/rename/merge(recount)/delete, unit tested
- [ ] `GET /api/labels`, `GET/POST/DELETE /api/skills/:slug/labels` implemented and tested
- [ ] Admin rename/merge/delete endpoints with MongoDB transaction tests
- [ ] `SkillService.list()` AND label filter via aggregation; `(label_id, skill_id)` index added
- [ ] Labels and admin routers registered in `main.py`
- [ ] Frontend `Skill` type and `LabelOut` interface updated
- [ ] Next.js proxy route handlers for all new endpoints
- [ ] `cmdk` added to `package.json`
- [ ] Label chips on skill cards (single row, up to 5 + non-interactive "+N more" badge, interactive style)
- [ ] `/labels` browse page live (SSR, sorted by usage_count, with counts); "Labels" nav link
- [ ] `label-filter.tsx` (new): multi-select popover in list page controls bar; AND filter; `?labels=` URL param; label-specific empty state
- [ ] `LabelSection` on detail page: inline combobox (cmdk), usage counts, remove own, optimistic UI, auth tooltip
- [ ] `(admin)` route group + guard; "Admin" nav link when `user.is_admin`
- [ ] `/admin/labels` page: table + rename/merge/delete with AlertDialog confirmations
- [ ] ADRs 001–004 filed in `docs/adr/` as `adr-u07` through `adr-u10`
- [ ] CHANGELOG.md created with label UX entry
- [ ] README updated to mention `/labels`, label combobox, `/admin/labels`
- [ ] AC-L1 through AC-L7 pass in staging

---

## Test Plan

### Unit Tests — `backend/tests/test_label_service.py` (mongomock)

**Happy paths:**
- `test_add_label_creates_label_and_skill_label` — new label created, SkillLabel created, usage_count=1
- `test_add_label_existing_label` — label reused across two skills; usage_count=2
- `test_add_label_same_user_second_label` — user adds two different labels to same skill; both exist
- `test_remove_label` — add then remove; SkillLabel deleted, usage_count decremented
- `test_list_for_skill` — 3 labels added by different users; all returned with correct counts
- `test_list_for_skill_applied_by_me` — `applied_by_me` True for caller's labels, False for others
- `test_list_for_skill_anonymous` — viewer_id=None; all `applied_by_me` = False
- `test_search_prefix` — search "py" returns "python" and "pytorch", not "react"
- `test_search_empty_query` — returns all labels ordered by usage_count desc
- `test_search_limit` — limit parameter caps results

**Error paths:**
- `test_add_label_duplicate_409` — same user adds same label twice; second raises Duplicate
- `test_add_label_invalid_name_uppercase` — "Python" rejected
- `test_add_label_invalid_name_special_chars` — "data_viz" rejected
- `test_add_label_invalid_name_spaces` — "data viz" rejected
- `test_add_label_invalid_name_leading_hyphen` — "-python" rejected
- `test_add_label_invalid_name_trailing_hyphen` — "python-" rejected
- `test_add_label_invalid_name_empty` — "" rejected
- `test_add_label_invalid_name_too_long` — 51-char label rejected
- `test_add_label_skill_not_found` — nonexistent skill_id raises NotFound
- `test_remove_label_not_applied` — label not applied by caller raises NotFound
- `test_add_label_rate_limit` — 6th label by same user on same skill rejected

**Admin operations:**
- `test_rename_label` — Label.name updated, old name pushed to aliases
- `test_rename_label_conflict` — rename to existing name raises Duplicate
- `test_merge_labels_simple` — all SkillLabel for B updated to A; B deleted; usage_count recounted
- `test_merge_labels_with_dedup` — duplicate (skill_id, A.id, user) deduped; usage_count correct
- `test_merge_into_self` — rejected with error
- `test_delete_label` — Label and all SkillLabel removed
- `test_delete_label_cascades` — 3 skills lose label; all 3 SkillLabel records gone

**AND filter:**
- `test_list_skills_filter_single_label` — filter by "python" returns only skills with that label
- `test_list_skills_filter_and_semantics` — filter by ["python","data-viz"] returns only skills with both
- `test_list_skills_filter_no_match` — filter by unseen label combo returns empty list
- `test_list_skills_filter_nonexistent_label` — filter by unknown name returns empty list (not 404)

**Note:** Admin transaction tests (merge, delete) require real MongoDB or testcontainers; mongomock does not support multi-document transactions. Service methods may need transaction bypass in unit test mode.

### Integration Tests — `backend/tests/test_label_routes.py` (FastAPI TestClient)

- `test_get_labels_returns_list`
- `test_get_labels_with_prefix`
- `test_get_skill_labels`
- `test_post_skill_label_authed` — returns 201
- `test_post_skill_label_unauthed` — returns 401
- `test_post_skill_label_duplicate` — returns 409
- `test_delete_skill_label_authed` — returns 204
- `test_delete_skill_label_not_applied` — returns 404
- `test_admin_rename_label` — admin auth returns 200
- `test_admin_rename_label_nonadmin` — returns 403
- `test_admin_merge_label` — admin auth returns 200
- `test_admin_delete_label` — returns 204
- `test_list_skills_with_label_filter` — filtered results correct
- `test_skill_out_includes_labels` — response includes `labels` field

### Frontend Tests (vitest/jest if configured)

- `test_label_chips_render_max_5` — 7 labels → 5 chips + "+2 more"
- `test_label_chips_render_under_5` — 3 labels → 3 chips, no overflow
- `test_label_chip_click_navigates` — chip click → `/skills?labels=name`
- `test_label_section_shows_combobox_when_authed`
- `test_label_section_disabled_when_anon` — tooltip visible, input disabled
- `test_label_filter_multi_select` — selecting labels updates URL params
- `test_label_filter_empty_state` — 0 results → label-specific message

---

## Board Review

**Verdict:** CLEAR WITH WARNINGS
**Date:** 2026-04-22
**Rounds:** 1

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | ⚠️ WARN | Y | Radix Command doesn't exist (→ cmdk); use MongoDB transactions for admin ops; unique index on Label.name |
| codebase-arch-review | ⚠️ WARN | Y | Merge/delete atomicity requires transactions; AND filter needs aggregation strategy + (label_id, skill_id) index; batch hydration for list endpoint |
| codebase-eng-review | ⚠️ WARN | Y | Label.name non-unique (race condition); AND filter silently ignored; Next.js proxy routes missing; name validation unspecified |
| codebase-doc-review | ⚠️ WARN | Y | Inline ADRs need filing in docs/adr/; no CHANGELOG; README update needed; router registration not in plan |
| security-review | ⚠️ WARN | Y | Label name regex must be specified; re.escape() on ?q= param; get_optional_user needed; rate limit must be a formal FR |
| codebase-ux-review | ⚠️ WARN | Y | cmdk dependency missing; +N more badge behaviour undefined; /labels has no nav entry; admin destructive ops need AlertDialog |

**Accepted warnings:**
- mongomock doesn't support transactions; admin service tests need testcontainers or mocked sessions
- always-visible combobox adds ~48px visual weight for non-labeling authenticated users (accepted per ADR-002)
- CORS wildcard pre-existing issue, not introduced by this feature

**ADRs written:** 0 new in docs/adr/ (pending filing as adr-u07–u10 during Slice 3)
**Unresolved decisions:** none

<details>
<summary>research-handbook — Round 1 (⚠️ WARN)</summary>

See round-1-dr.md (merged into plan amendments above)

</details>

<details>
<summary>codebase-arch-review — Round 1 (⚠️ WARN)</summary>

See round-1-ar.md (merged into plan amendments above)

</details>

<details>
<summary>codebase-eng-review — Round 1 (⚠️ WARN)</summary>

See round-1-er.md (merged into plan amendments above; full test plan in ## Test Plan section)

</details>

<details>
<summary>codebase-doc-review — Round 1 (⚠️ WARN)</summary>

See round-1-dc.md (merged into Definition of Done)

</details>

<details>
<summary>security-review — Round 1 (⚠️ WARN)</summary>

See round-1-sr.md (merged into FR-L3/FR-L3b/FR-L12c amendments)

</details>

<details>
<summary>codebase-ux-review — Round 1 (⚠️ WARN)</summary>

See round-1-ux.md (merged into FR-L12 through FR-L24 amendments)

</details>
