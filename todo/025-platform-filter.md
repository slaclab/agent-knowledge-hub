# 025 — Platform Filter: Searchable, Filterable Platform Dimension in the Catalog

**Status:** ⬜ Open
**Branch:** —

---

## Problem & Goal

**Problem:** `compatible_platforms` is fully modelled on every Skill document (`List[str]`, already returned in `SkillOut` and `SkillListOut`) and rendered as coloured chips on skill cards via `PlatformBadges`. However, neither the backend nor the frontend exposes platforms as a filterable dimension: there is no `platforms=` query param on `GET /api/skills`, no platform toggles in the filter bar, and clicking a platform badge on a card does nothing. Users who want to browse "skills that work in OpenCode" or "skills compatible with Codex" have no path to do so.

**Goal:** Ship end-to-end platform filtering — a `platforms=` query param on the list endpoint, platform facet counts in the paginated response, platform toggle chips in the filter bar, URL-driven filter state, and click-to-filter on platform badges in skill cards.

**Success metric:**
- A user can click a platform badge on any skill card and see only skills that list that platform.
- Platform filter state is reflected in the URL and survives page refresh.
- The filter bar shows a live count of how many skills match each platform.

**Out of scope:**
- Adding or removing platforms from a skill (write path is handled by `PlatformSection` and `POST/DELETE /api/skills/:slug/platforms`, which already exist).
- Normalisation or validation of new platform values (handled by `platform-section.tsx`).
- A dedicated `/platforms` browse page (not needed — the catalog filter is sufficient).

**Constraints:**
- Platform values are an open-ended enum stored directly on `Skill.compatible_platforms` (not a separate collection). No join is needed — the filter is a simple `$in` on the embedded array.
- Filter semantics are OR (any skill listing at least one of the requested platforms), not AND. A user browsing "OpenCode" skills should see all skills that mention OpenCode, not only skills that list every requested platform simultaneously.
- Known platform values: `claude-code`, `codex`, `opencode`, `openai`, `langchain`, `crewai`, `autogen`, `mcp`, `other`. These are the values the `PlatformBadges` component already has colour mappings for.

---

## User Stories

1. As a consumer, I want to click a platform badge on a skill card and be taken to the catalog filtered to that platform, so I can discover all skills for my stack.
2. As a consumer, I want to click a platform badge on a skill detail page and be taken to the catalog filtered to that platform.
3. As a consumer, I want to select one or more platform toggles in the filter bar, so I can narrow results to skills compatible with my tools.
4. As a consumer, I want the platform filter to be reflected in the URL, so I can bookmark or share a filtered view.
5. As a consumer, I want to see how many skills are available per platform in the filter UI, so I know which platforms have good coverage before I click.
6. As a consumer, I want to clear individual platform filters by clicking the active chip, so I can progressively widen my search.
7. As a consumer, I want to see a platform-specific empty state when no skills match my platform filter, so I understand why results are empty.
8. As an unauthenticated visitor, I want platform filtering to work fully without logging in.

---

## Requirements

### Functional

**Backend**
- FR-P1: `GET /api/skills` accepts an optional `platforms` query param: a comma-separated list of platform values. When present, returns only skills where `compatible_platforms` contains at least one of the requested values (`$in` filter on the `Skill.compatible_platforms` array field).
- FR-P2: The `platforms` filter is applied in `SkillRepository.list()` alongside existing filters (`q`, `labels`, `visibility`, `forked_from`). All filters are combined with AND logic at the query level — a skill must satisfy every active filter (labels AND, platforms OR-within-the-param).
- FR-P3: `PaginatedSkills` response schema gains `platform_counts: dict[str, int]` — a map of platform name to the count of skills that list that platform among the current filtered result set (after applying all filters _except_ the `platforms` param itself, so users can see the impact of toggling each platform). An empty dict is returned if `platform_counts` cannot be computed cheaply.
- FR-P4: `platform_counts` is computed via a MongoDB aggregation (`$unwind` on `compatible_platforms`, then `$group` by platform value, `$match`ing the same base query as the main list, but _without_ the `compatible_platforms.$in` clause). This runs as a parallel async task alongside the main query.
- FR-P5: An unknown or empty `platforms` value is ignored silently (not a 400 error). Values are lowercased and stripped before use.

**Frontend**
- FR-P6: New `platform-filter.tsx` component rendered in the controls bar of `skill-list.tsx`, positioned between `LabelFilter` and `SortSelect`. It renders the full list of known platforms as inline toggle chips using `platformPillClass` from `platform-badges.tsx` (`selected` style when active, `unselected` when inactive).
- FR-P7: `PlatformFilter` accepts `activePlatforms: string[]` and reads `platform_counts` from the `PaginatedSkills` response (passed as a prop). Each chip shows the platform name and, if available, the count from `platform_counts`.
- FR-P8: Clicking a platform chip toggles it in `?platforms=` URL param (comma-separated, same pattern as `?labels=`). Toggling resets `?page=` to 1.
- FR-P9: Active platform chips render as removable pills in the controls bar (same pattern as active label pills in `skill-list.tsx`), with a `×` to deactivate individually.
- FR-P10: `skill-list.tsx` gains `platforms: string[]` prop. `removeplatform` callback mirrors `removeLabel`. The empty state distinguishes a platform-only filter: "No skills found for the selected platform(s). Try removing a filter or submitting one." (shown alongside active-platform chips).
- FR-P11: `skill-card.tsx` — platform badges rendered by `PlatformBadges` become `<Link>` elements pointing to `/skills?platforms=<name>` (one platform per badge click). `e.stopPropagation()` prevents the card navigation from firing, same pattern as label chips.
- FR-P12: `page.tsx` reads `searchParams.platforms`, splits on `,`, and passes the array to `listSkills` and down to `SkillList`.
- FR-P13: `SkillListParams` in `types/skill.ts` gains `platforms?: string[]`. `PaginatedSkills` gains `platform_counts?: Record<string, number>`. `listSkills` in `lib/api.ts` serialises `platforms` as `platforms=<comma-joined>` query param.
- FR-P14: Detail page — platform badges in `PlatformSection` (the read-only path for unauthenticated users) become `<Link>` elements pointing to `/skills?platforms=<name>`, same as cards.

### Non-Functional

- NFR-P1: The `platform_counts` aggregation adds no more than 20ms to the list response at catalog scale (≤ 5,000 skills). It runs concurrently with the main paginated query via `asyncio.gather`.
- NFR-P2: Platform filter state is bookmarkable and shareable — fully driven by URL params, no client-only state.
- NFR-P3: No new npm dependencies. `PlatformFilter` uses existing `platformPillClass` from `platform-badges.tsx` and Next.js router primitives.

### Acceptance Criteria

- AC-P1: Given a user clicks the "claude-code" badge on any skill card, the catalog URL becomes `?platforms=claude-code` and only skills listing `claude-code` in `compatible_platforms` are shown.
- AC-P2: Given a user activates two platform chips (e.g. "opencode" and "codex"), the URL reads `?platforms=opencode,codex` and results include skills that list either platform.
- AC-P3: Given the URL is loaded with `?platforms=mcp`, the platform chip for "mcp" renders in the selected style without client-side interaction.
- AC-P4: Given no skills list the requested platform(s), the platform-specific empty state is shown.
- AC-P5: Given an unauthenticated visitor, platform filter chips are fully functional (no auth required).
- AC-P6: Given `platform_counts` is present in the response, each chip in the filter bar displays the count next to the platform name.

---

## Architecture

### Data Flow

```
Catalog page (SSR)
  │  GET /api/skills?platforms=opencode,codex&...
  │     → PaginatedSkills { items, total, page, page_size, platform_counts }
  ▼
SkillRepository.list()
  │  query_parts += { compatible_platforms: { $in: ["opencode", "codex"] } }
  │  asyncio.gather(
  │    main paginated query,
  │    platform_counts aggregation (base query minus platforms filter)
  │  )
  ▼
MongoDB Skill collection
  compatible_platforms is a native array field — $in works without a join.
```

### OR Filter Query Pattern

```python
# SkillRepository.list() — platform filter addition
if platforms:
    platform_list = [p.strip().lower() for p in platforms if p.strip()]
    if platform_list:
        query_parts.append({"compatible_platforms": {"$in": platform_list}})

# platform_counts aggregation (runs concurrently, excludes platforms filter)
async def _platform_counts(base_query_parts_without_platform) -> dict[str, int]:
    pipeline = [
        {"$match": _build_mongo_match(base_query_parts_without_platform)},
        {"$unwind": "$compatible_platforms"},
        {"$group": {"_id": "$compatible_platforms", "count": {"$sum": 1}}},
    ]
    cursor = Skill.get_motor_collection().aggregate(pipeline)
    return {doc["_id"]: doc["count"] async for doc in cursor}
```

No new index is needed — `compatible_platforms` with `$in` performs a collection scan on the embedded array. At ≤ 5,000 skills this is acceptable. A sparse multikey index on `compatible_platforms` can be added in a follow-up if query time grows.

### API Contract

```
GET /api/skills?platforms=<comma-separated>&...
    → PaginatedSkills {
        items: SkillListOut[],
        total: int,
        page: int,
        page_size: int,
        platform_counts: { "claude-code": 45, "mcp": 23, ... }   # new
      }
```

### Schema Changes

```python
# backend/app/schemas/skill.py

class PaginatedSkills(BaseModel):
    items: List[SkillListOut]
    total: int
    page: int
    page_size: int
    platform_counts: dict[str, int] = {}    # ← new field; default empty for compat
```

```typescript
// frontend/types/skill.ts

export interface PaginatedSkills {
  items: Skill[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  platform_counts?: Record<string, number>;   // ← new optional field
}

// SkillListParams gains:
export interface SkillListParams {
  // ... existing fields ...
  platforms?: string[];    // ← new
}
```

Migration: additive — `platform_counts: {}` default for all existing responses. No data migration needed.

---

## Modules

**`SkillRepository.list()` (modify, `backend/app/services/skill.py`)**
- Accept `platforms: Optional[List[str]] = None` param
- Apply `{"compatible_platforms": {"$in": platform_list}}` to query parts
- Run `_platform_counts_aggregation()` concurrently via `asyncio.gather`
- Return `(items, total, platform_counts)` — adjust return type accordingly

**`list_skills` route (modify, `backend/app/routers/skills.py`)**
- Add `platforms: Optional[str] = Query(None, description="Comma-separated platform names (OR filter)")`
- Split into list, pass to `skill_repository.list()`
- Include `platform_counts` in `PaginatedSkills` response

**`PaginatedSkills` schema (modify, `backend/app/schemas/skill.py`)**
- Add `platform_counts: dict[str, int] = {}`

**`PlatformFilter` (new, `frontend/components/platform-filter.tsx`)**
- Accepts `activePlatforms: string[]`, `platformCounts: Record<string, number>`
- Renders all known platforms as toggle chips using `platformPillClass`
- Inline chip row (no dropdown — platform list is short and enumerable)
- Clicking a chip calls router to update `?platforms=` URL param
- Testable: Yes

**`SkillList` (modify, `frontend/components/skill-list.tsx`)**
- Add `platforms: string[]` and `platformCounts: Record<string, number>` props
- Add `removePlatform` callback mirroring `removeLabel`
- Render `<PlatformFilter>` in controls bar
- Render active-platform removable pills alongside active-label pills
- Update empty-state logic: check `platforms.length > 0` for platform-specific message

**`SkillCard` (modify, `frontend/components/skill-card.tsx`)**
- Replace static `<PlatformBadges>` with per-badge `<Link href={/skills?platforms=<p>}>` elements
- `e.stopPropagation()` on click to prevent card-level navigation

**`PlatformSection` (modify, `frontend/components/platform-section.tsx`)**
- Unauthenticated read-only path: wrap each platform chip in `<Link href={/skills?platforms=<p>}>`
- Authenticated path: platform chips remain non-navigating (they have remove buttons; clicking should not navigate)

**`page.tsx` (modify, `frontend/app/skills/page.tsx`)**
- Read `searchParams.platforms`, split on `,`, pass to `listSkills` and `SkillList`

**`lib/api.ts` (modify, `frontend/lib/api.ts`)**
- Serialise `params.platforms` as `platforms=<comma-joined>` in `listSkills`

**`types/skill.ts` (modify, `frontend/types/skill.ts`)**
- Add `platforms?: string[]` to `SkillListParams`
- Add `platform_counts?: Record<string, number>` to `PaginatedSkills`

---

## Trade-offs

**OR vs AND semantics for multi-platform filter**
- `+` OR: "show me all skills for OpenCode _or_ Codex" is the natural use case; most users want to discover what exists for their stack, not find skills that explicitly support multiple platforms simultaneously
- `-` OR: result set widens with more chips selected, which may feel counterintuitive compared to label AND
- Decision: OR — consistent with how platform tags are used (a skill listing "codex" targets Codex users; selecting both "codex" and "opencode" should show the union, not restrict to only skills that support both)

**Inline chip row vs dropdown (LabelFilter pattern)**
- `+` Inline chips: no click to open; platforms are a short, known enumerable list; coloured badges already convey meaning at a glance
- `-` Inline chips: adds horizontal space to the controls bar; wraps to second row on narrow viewports
- Decision: Inline chips — the known, bounded platform set (≤ 9 values) makes a full dropdown unnecessary; the colour coding is a core affordance of the existing `PlatformBadges` system

**`platform_counts` in list response vs separate `/api/platforms` endpoint**
- `+` Inline: single request per page load; no waterfall; consistent with how label usage_counts piggyback on skill responses
- `-` Inline: adds a MongoDB aggregation to every list request, even when no platform filter UI is mounted
- Decision: Inline with async `gather` — the aggregation is lightweight at current scale; keep it simple. Can be moved to a separate endpoint or cached if profiling shows impact.

**Multikey index on `compatible_platforms`**
- `+` Index: speeds up `$in` filter at scale; MongoDB creates a multikey index automatically for array fields
- `-` Index overhead: write amplification on every platform add/remove (negligible — platform changes are rare)
- Decision: Add `compatible_platforms` sparse multikey index in this ticket. The field already exists; adding the index is a one-line Beanie/Motor declaration.

---

## ADRs

### ADR-001: OR filter semantics for platforms

**Status:** Accepted

**Context:** Labels use AND semantics (skill must carry all requested labels). Platforms are different: a user browsing by platform wants to find all skills compatible with any of their chosen environments.

**Decision:** Platform filter uses OR semantics — the `$in` operator on `compatible_platforms` returns skills that list at least one of the requested platforms.

**Consequences:** Multi-chip selection widens results rather than narrows. This is the expected and desirable behaviour for platform discovery. A future "strict mode" (AND) can be added as a separate query param if needed.

---

### ADR-002: Inline chip row for PlatformFilter

**Status:** Accepted

**Context:** `LabelFilter` uses a dropdown because labels are open-ended (potentially hundreds); a search input is necessary. Platforms are a closed enum of ≤ 9 known values.

**Decision:** Render all platform chips inline in the controls bar rather than behind a dropdown. `PlatformFilter` is a row of coloured toggle chips using the existing `platformPillClass` colour system.

**Consequences:** The controls bar grows wider. At narrow viewports it wraps. Acceptable — the filter bar already wraps on mobile (flex-wrap is set). The coloured chips are more scannable than a dropdown for a short, meaningful list.

---

### ADR-003: platform_counts in PaginatedSkills (not a separate endpoint)

**Status:** Accepted

**Context:** The frontend needs per-platform counts to display numbers on filter chips. Two approaches: (a) add `platform_counts` to the existing list response, (b) add a `GET /api/platforms` endpoint with counts.

**Decision:** Add `platform_counts: dict[str, int]` to `PaginatedSkills`. Counts are computed in the backend via a parallel aggregation on the same base query (minus the platforms filter) so the numbers reflect "how many skills match your other active filters per platform".

**Consequences:** Every `GET /api/skills` call runs an extra aggregation. At ≤ 5,000 skills this is negligible. If the catalog grows to 50k+ skills, this should be moved to a cached endpoint.

---

### ADR-004: All slices ship in one PR

**Status:** Accepted

**Context:** Backend-only or frontend-only slices are non-functional in staging; the filter needs both halves to be testable end-to-end.

**Decision:** Ship backend schema + query changes, and frontend filter + click-through changes, as one branch/PR.

**Consequences:** Larger PR. Acceptable — the feature is narrow and the slices are separable in commits.

---

## Delivery Slices

All slices ship in one branch (`feat/platform-filter`), one PR. Order of implementation:

**Slice 1 — Backend**
- Add `platforms: Optional[List[str]] = None` to `SkillRepository.list()` signature
- Apply `{"compatible_platforms": {"$in": platform_list}}` to `query_parts` when `platforms` is non-empty
- Add `_platform_counts_aggregation()` helper; run via `asyncio.gather` alongside the main query
- Add `compatible_platforms` multikey index declaration in the Beanie `Skill` model settings
- Add `platform_counts: dict[str, int] = {}` to `PaginatedSkills` schema
- Add `platforms: Optional[str] = Query(None)` param to `list_skills` route; split and pass through
- Unit tests per test plan

**Slice 2 — Frontend**
- Add `platforms?: string[]` to `SkillListParams`; add `platform_counts?: Record<string, number>` to `PaginatedSkills` in `types/skill.ts`
- Update `listSkills` in `lib/api.ts` to serialise `platforms` param
- Update `page.tsx` to read `searchParams.platforms`, pass to `listSkills` and `SkillList`
- New `platform-filter.tsx`: inline chip row using `platformPillClass`; toggles `?platforms=` URL param
- Update `skill-list.tsx`: add `platforms` + `platformCounts` props; render `<PlatformFilter>`; add `removePlatform` callback + active-platform pills; platform-specific empty state
- Update `skill-card.tsx`: wrap each platform badge in `<Link href={/skills?platforms=<p>}>` with `e.stopPropagation()`
- Update `platform-section.tsx`: unauthenticated read path — wrap each chip in `<Link>`

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `platform_counts` aggregation adds latency at scale | Low | Low | Runs via `asyncio.gather`; at ≤ 5k skills adds < 20ms; can cache or remove if needed |
| Inline chip row overflows narrow viewports | Low | Low | Controls bar already uses `flex-wrap`; chips wrap to second row gracefully |
| `compatible_platforms: $in` slow without index | Low | Low | Adding multikey index in Slice 1; at current scale a collection scan is also acceptable |
| Platform badge click conflicts with card navigation | Low | Medium | Use `e.stopPropagation()` on badge `<Link>` click; same pattern as label chips in `skill-card.tsx` |
| `opencode` not in `PLATFORM_COLORS` map | Medium | Low | `platform-badges.tsx` has a `PLATFORM_FALLBACK` colour; add `opencode` entry to the map as part of Slice 2 |

---

## Definition of Done

- [ ] `SkillRepository.list()` accepts `platforms` param; applies `$in` filter
- [ ] `_platform_counts_aggregation()` runs concurrently; returns `dict[str, int]`
- [ ] `compatible_platforms` multikey index declared in `Skill` model
- [ ] `PaginatedSkills.platform_counts` added; `list_skills` route wires it through
- [ ] `types/skill.ts` updated: `SkillListParams.platforms`, `PaginatedSkills.platform_counts`
- [ ] `lib/api.ts` `listSkills` serialises `platforms`
- [ ] `page.tsx` reads and passes `platforms` from searchParams
- [ ] `platform-filter.tsx` new component: inline chips, `platformPillClass`, toggles `?platforms=` URL param, shows counts
- [ ] `skill-list.tsx` passes `platforms` + `platformCounts` to `PlatformFilter`; active-platform removable pills; platform empty state
- [ ] `skill-card.tsx` platform badges are `<Link>` elements navigating to `?platforms=<name>`
- [ ] `platform-section.tsx` unauthenticated read path wraps chips in `<Link>`
- [ ] `opencode` added to `PLATFORM_COLORS` in `platform-badges.tsx`
- [ ] AC-P1 through AC-P6 pass in staging

---

## Test Plan

### Unit Tests — `backend/tests/test_skill_repository_platform_filter.py`

**Happy paths:**
- `test_platform_filter_single` — `platforms=["claude-code"]` returns only skills with "claude-code" in `compatible_platforms`
- `test_platform_filter_or_semantics` — `platforms=["opencode","codex"]` returns skills listing either value; skills listing neither are excluded
- `test_platform_filter_all_known` — passing all 9 known platforms returns all active skills (every skill lists at least one)
- `test_platform_filter_with_label_filter` — labels AND platforms filters applied together; only skills satisfying both are returned
- `test_platform_counts_excludes_platform_filter` — `platform_counts` reflects counts for the base query without the `platforms` filter (so active filter chips still show counts)
- `test_platform_counts_with_visibility_filter` — `platform_counts` respects `visibility` filter

**Error/edge paths:**
- `test_platform_filter_unknown_value` — `platforms=["unknown-platform"]` returns empty list (no error)
- `test_platform_filter_empty_string` — `platforms=[""]` after strip is ignored; no filter applied
- `test_platform_filter_none` — `platforms=None` returns all skills (no filter)
- `test_platform_counts_empty_catalog` — `platform_counts` returns `{}` when no skills exist

### Integration Tests — `backend/tests/test_skill_routes_platform_filter.py` (FastAPI TestClient)

- `test_list_skills_platform_filter` — `GET /api/skills?platforms=claude-code` returns only matching skills
- `test_list_skills_platform_filter_multi` — `?platforms=opencode,codex` returns OR-union
- `test_list_skills_platform_counts_present` — response includes `platform_counts` field
- `test_list_skills_no_platform_filter` — `platform_counts` still present; `items` not filtered
- `test_list_skills_platform_and_label_combined` — both filters active; only skills satisfying both returned

### Frontend Tests (vitest/jest if configured)

- `test_platform_filter_chip_toggle` — clicking inactive chip appends `?platforms=<name>` to URL
- `test_platform_filter_chip_deactivate` — clicking active chip removes it from `?platforms=`
- `test_platform_filter_shows_counts` — counts from `platform_counts` rendered on chips
- `test_skill_card_platform_badge_is_link` — platform badge renders as `<a>` with correct href
- `test_skill_card_badge_click_stops_propagation` — badge click does not trigger card navigation
- `test_skill_list_platform_empty_state` — zero results with `platforms.length > 0` shows platform-specific message
- `test_skill_list_active_platform_pill_removes_on_click` — removable pill click updates URL
