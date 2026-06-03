# TODO #015 — Catalog Scale: Search Quality, Pagination, and Performance

> **Priority:** 🟡 P2 — Medium
> **Status:** 🔍 Reviewed
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

The current implementation was designed for a small catalog. As the number of registered skills grows, several parts of the stack will degrade:

1. **Pagination** uses `skip(n).limit(m)` — MongoDB must scan and discard `n` documents on every page turn. At 1,000+ skills this is slow and gets worse with each page.
2. **Total count** runs a separate `count()` against the full filtered query on every page load. This is redundant work and slows as the corpus grows.
3. **Search** uses MongoDB `$text` (basic stemmed keyword match). It has no relevance ranking beyond score, no fuzzy matching. With hundreds of skills, a query like "kubernetes deploy helm" will miss skills that describe the concept differently.
4. **Label filter** uses an aggregation pipeline (`SkillLabel` → aggregate → `$in` filter) that produces a potentially large `$in` list. At scale this risks becoming slow.
5. **No caching** — every page load hits MongoDB directly. Repeated identical queries (front page, "newest 20 skills") are re-executed every time.
6. **Frontend pagination** is simple prev/next with no page-number input or direct-link deep pages.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| 5,000 skills, page 50 | `skip(980)` scans 980+ docs | Keyset cursor, no scan |
| Search "kubernetes deployment" | Only matches if exact words appear | Improved match quality |
| Front page load | Full count + query on every request | Cached count; indexed query |
| Filter by 3 labels, 2,000 skills | Large `$in` built per request | Index-covered aggregation (fast today; monitor) |
| User wants page 7 of results | Can only click prev/next | Page number input |

---

## Goals

1. **Keyset/cursor pagination** — replace `skip()` with keyset pagination for `sort=newest` (initial delivery); expose optional `cursor` param; frontend page numbers stay in URL for backward compat. `most_stars` keyset deferred due to nullable `github_stars` (see AR-2)
2. **Count caching** — cache or approximate total counts per filter fingerprint; avoid re-counting on every page request
3. **Compound sort indexes** — explicit MongoDB indexes for each sort field to make current skip()-based pages 1–10 fast today
4. **Search quality** — ship one concrete improvement over `$text`: either Atlas Search (if available), regex-assisted fuzzy match, or name/description weighting; defer full semantic/vector search
5. **Frontend UX** — add page-number input / "jump to page N" for catalogs >5 pages

## Non-Goals

- Full semantic / vector search (follow-on once embedding infra is in place)
- Elasticsearch / Solr (overkill for current scale)
- Real-time streaming updates to the catalog list
- Infinite scroll (can be a separate frontend task)
- Label aggregation rewrite (current pipeline is fast enough up to ~10k skills; monitor before changing)

---

## Design

### Current Implementation (baseline)

`skill_service.list()` at `backend/app/services/skill.py:49`:
- Builds a `base_query` from filter parts
- Runs `await base_query.count()` (line 107) — full filtered count every request
- Runs `base_query.sort(sort_expr).skip((page-1)*page_size).limit(page_size)` (lines 109-113)
- Sort options: `newest` (submitted_at desc), `highest_rated` (avg_rating desc), `most_rated` (rating_count desc), `most_stars` (github_stars desc)

Frontend (`frontend/components/skill-list.tsx`): prev/next buttons only; page number displayed as `{page} / {pages}`.

### Design Decisions

**Keyset pagination:** Add an optional `cursor` query param to `GET /api/skills`. When `cursor` is absent, current `skip()` behaviour is preserved (backward compat). When `cursor` is present (opaque base64-encoded `{sort_value, id}` pair), the backend uses a compound `$gt`/`$lt` query instead of `skip()`. The frontend will only send `cursor` when navigating beyond page 10; pages 1–10 stay skip-based (at most 180 docs scanned — negligible at current scale). Keyset pagination is restricted to `newest` sort in initial delivery: `submitted_at` is non-nullable so cursor math is unambiguous. `most_stars` keyset is deferred until null `github_stars` handling is specified (see AR-2 in arch review).

**Count caching:** Cache filtered counts in-process with a 30-second TTL, keyed by a hash of `(q, labels, visibility, forked_from, sort)`. For unfiltered requests, use `estimatedDocumentCount()` which is O(1) and reads from collection metadata. This alone eliminates the most common extra round-trip (the front page reload).

**Search improvement:** Default to improving `$text` weighting + adding a pre-filter name/slug exact-match pass. If a query token exactly matches a skill name or slug, boost that result to the top. This requires no new infrastructure. Atlas Search is the better long-term path but depends on the Atlas tier; include a feature-flagged path that enables Atlas Search if `MONGODB_ATLAS_SEARCH=1` is set.

**Compound indexes:** Add explicit compound indexes for all four sort fields combined with `status=active`:
- `(status, submitted_at DESC, _id DESC)` — supports `newest` sort (includes `_id` tiebreaker to match sort expression)
- `(status, github_stars DESC, submitted_at DESC)` — supports `most_stars`
- `(status, avg_rating DESC, submitted_at DESC)` — supports `highest_rated`
- `(status, rating_count DESC, submitted_at DESC)` — supports `most_rated`

These make `skip()` for pages 1–10 fast today (index-only scan) while we build out keyset support.

> **Note (AR-5):** These compound indexes only accelerate non-search queries (where `q` is absent). When `q` is present, MongoDB must use the `$text` index pipeline and applies the sort in-memory on the result set — the compound indexes are bypassed. The search path is not helped by these indexes. This is an argument for prioritising Atlas Search, which handles both search and sort natively in a single pipeline.

---

## User Stories

1. As a user browsing the catalog, I want page loads to feel fast even when there are 5,000 skills registered
2. As a user on page 7, I want to be able to type "3" and jump to page 3 without clicking prev/next 4 times
3. As a user searching for "kubernetes deployment", I want results that include skills about deploying to k8s even if the exact phrase isn't in the name
4. As a user filtering by 3 labels, I want filter results to load quickly at any catalog size
5. As an admin, I want the front page to load fast without running expensive count queries on every request
6. As an agent using the catalog API, I want cursor-based pagination so I can page through all skills without skip-scan degradation
7. As a developer, I want the keyset cursor to be opaque (base64) so the frontend doesn't need to know the sort field type
8. As a developer, I want the existing `?page=N` interface to keep working so no frontend changes are required for the basic case
9. As a user, I want search results to show the most relevant skill first, not just any skill that contains the search tokens
10. As a user, I want slug and name exact matches to rank above description partial matches

---

## Requirements

### Functional Requirements

**FR-1:** `GET /api/skills` gains optional `cursor` query param (opaque base64 string). When provided for `sort=newest` (the only keyset-eligible sort in initial delivery), the backend uses a keyset `$gt`/`$lt` compound query on `(submitted_at, _id)` instead of `skip()`. When absent, or when sort is not `newest`, existing `skip()` behaviour is unchanged. `most_stars` keyset is deferred (see AR-2).

  **Cursor decode security requirements (SR-1/SR-2):** (1) base64-decode and JSON-parse the input, returning HTTP 400 on any parse error; (2) validate that `sv` is a scalar type (str or numeric — not dict, list, or null) matching the sort field's expected type; (3) validate that `id` is an exact full-match against `^[0-9a-f]{24}$` (anchored regex); additionally wrap `ObjectId(id)` in `try/except bson.errors.InvalidId` and treat any `InvalidId` exception as a validation failure; (4) return HTTP 422 with message "Invalid or expired cursor" for any validation failure. Never surface raw exception detail in the 4xx response body.

**FR-2:** `GET /api/skills` response gains optional `next_cursor` and `prev_cursor` fields alongside existing `page`, `pages`, `total`. Cursors are present only when `sort` is keyset-eligible.

**FR-3:** Count caching — unfiltered requests use `estimatedDocumentCount()` (O(1)). Filtered requests cache count per filter fingerprint for 30 seconds in-process. Cache invalidation clears the entire cache on any skill write (create, deactivate, reactivate); individual fingerprint eviction is not used because it is not feasible to determine which fingerprints a changed skill affects. The cache must be bounded to at most 1,000 entries (evict LRU when full) to prevent unbounded memory growth from high-cardinality `q` values. Use `cachetools.TTLCache(maxsize=1000, ttl=30)` or equivalent.

  **Note (UX):** `estimatedDocumentCount()` counts all documents regardless of `status`, including deactivated skills. It must only be used when no filters are active and the fraction of deactivated skills is negligible. If deactivated skills become a meaningful share of the collection, replace the unfiltered path with a fast indexed count against `{status: 'active'}` (O(log N) with the compound index). The implementer must verify this before shipping Slice 1.

**FR-4:** Compound MongoDB indexes added for all four sort fields (see Design section). No schema migration needed — additive index creation only.

**FR-5:** Search pre-pass — before returning `$text` results, run a name/slug exact-match query and prepend matching skills to the result list (deduplicating with `$text` results). This is the "name boost" heuristic.

**FR-6:** Feature flag `MONGODB_ATLAS_SEARCH` (env var, default false). When true, the `list()` service uses an Atlas Search aggregation pipeline instead of `$text`. Disabled by default until Atlas tier is confirmed.

  **Atlas Search error handling (SR-5):** The Atlas Search pipeline must be wrapped with a try/except on `pymongo.errors.OperationFailure`. On failure (e.g., index not found), log at WARNING and fall back to the `$text` path for that request. A startup check should validate index existence and log WARNING if absent.

**FR-7:** Frontend gains a page-number input field alongside the existing prev/next buttons. The input accepts numbers 1–pages (clamped server-side via `Query(1, ge=1, le=1000)`). UX behaviour:
  - If the entered value is outside [1, pages], the input shows a validation error style (red border or inline message) and does not navigate. On blur or dismiss with an invalid value, the input resets to the current page number.
  - Non-integer input is rejected at the character level (`<input type="number">`).
  - The page input is hidden on viewports narrower than `sm` (640px); Prev/Next remain visible at all breakpoints.
  - If the API returns 0 items and `page > 1` (stale bookmark), the component redirects to `?page=1` rather than showing an empty result set.
  - Frontend clamping is not a substitute for backend validation (SR-4).

**FR-8:** When `sort=newest` and page > 10, the frontend sends `cursor` instead of `page` to the API (uses `next_cursor` from the prior page's response). The URL still reflects `?page=N` for bookmarkability; the cursor is held in component state.

### Non-functional Requirements

**NFR-1:** `GET /api/skills` p95 latency < 300ms at 5,000 skills, any page, any sort, cold cache

**NFR-2:** `GET /api/skills` with cursor (keyset) p95 latency < 150ms at 5,000 skills (no scan)

**NFR-3:** Count cache hit rate > 90% for the unfiltered front page within a 30-second window

**NFR-4:** Compound indexes add < 50ms to write latency for skill create/update (acceptable tradeoff)

**NFR-5:** Existing `?page=N` API contract remains fully backward-compatible — no client changes required for basic pagination

### Acceptance Criteria

**AC-1:** Given 5,000 skills in the DB, when `GET /api/skills?sort=newest&cursor=<opaque>` is called, then the query uses a keyset `$gt` compound on `(submitted_at, _id)` — no `skip()` in the explain plan

**AC-2:** Given two consecutive page requests with identical filters, when the second request is within 30 seconds, then the count is served from cache (not a new `count()` query)

**AC-3:** Given a search query that exactly matches a skill name, when results are returned, then that skill appears first

**AC-4:** Given a `?page=7` request, when `pages=10` and `sort=newest`, then the response includes a non-null `next_cursor`; `prev_cursor` is present in the response schema but is `null` in Slice 2 (backward navigation uses skip fallback until `prev_cursor` is explicitly scoped)

**AC-5:** Given the frontend is on page 7, when the user types "3" in the page input and hits Enter, then the URL becomes `?page=3` and the correct skills are shown

**AC-6:** Given `MONGODB_ATLAS_SEARCH=0` (default), when `GET /api/skills?q=foo`, then the query uses `$text` (existing behaviour unchanged)

---

## Module Design

**`services/skill.py`** (modify — `list()` method)
- Add `cursor: Optional[str]` param (base64-decoded to `{sort_value, id}`)
- Add cursor-based query branch for keyset-eligible sorts
- Add in-process count cache (`_count_cache: dict`, TTL 30s)
- Return `next_cursor` and `prev_cursor` in `SkillListResult`
- Testable in isolation: yes — mock Beanie find

**`models/skill.py`** (modify)
- Add `Settings.indexes` entries for the four compound sort indexes
- No field changes; no migration needed

**`schemas/skill.py`** (modify)
- `PaginatedSkills` gains `next_cursor: Optional[str]`, `prev_cursor: Optional[str]` (not `SkillListOut`, which is the per-item schema)
- `frontend/types/skill.ts` `PaginatedSkills` interface must also add `next_cursor: string | null`, `prev_cursor: string | null`

**`services/search.py`** (new)
- Responsibility: search enhancement logic — name boost pre-pass, Atlas Search pipeline builder
- Interface:
  - `async name_boost(q: str, base_results: List[Skill]) → List[Skill]` — issues a separate `Skill.find(name==q OR slug==q)` DB query, prepends matching skills to `base_results`, deduplicates by id. A DB call is required so that exact-match skills not present in the current `$text` result page are still surfaced.
  - `build_atlas_pipeline(q: str, filters: dict) → List[dict]` — Atlas Search aggregation (pure, no DB calls)
- **Security (SR-6/A3):** `name_boost` uses `$eq` comparison only (`Skill.name == q` and `Skill.slug == q`). No `$regex`. If slug normalization is applied to `q`, the output is used in equality comparison only.
- Testable in isolation: yes — mock Beanie find for `name_boost`; `build_atlas_pipeline` is pure

**`frontend/components/skill-list.tsx`** (modify)
- Add page-number input field (`<input type="number">`) next to prev/next
- Track `nextCursor`/`prevCursor` from API response in component state
- When `page > 10` and cursor is available, pass `cursor` param to API instead of `page`

---

## System Design

```
Client
  │  GET /api/skills?sort=newest&cursor=<opaque>
  ▼
routers/skills.py
  │  parse cursor param → decode to {sort_value, id}
  ▼
services/skill.py  list()
  ├─ count: in-process cache → estimatedDocumentCount (unfiltered)
  │                          → cached count (filtered, 30s TTL)
  ├─ query: cursor present → $gt compound keyset query (no skip)
  │          cursor absent → existing skip() (backward compat)
  ├─ name boost: services/search.py.name_boost(q, results)
  └─ return: items + total + next_cursor + prev_cursor

MongoDB
  ├─ (status, submitted_at DESC, _id DESC) compound index
  ├─ (status, github_stars DESC, submitted_at DESC) compound index
  ├─ (status, avg_rating DESC, submitted_at DESC) compound index
  └─ (status, rating_count DESC, submitted_at DESC) compound index
```

**Cursor encoding:**
```
cursor = base64( json({ "sv": <sort_value>, "id": "<ObjectId string>" }) )
```
Where `sv` is the value of the primary sort field:
- For `newest`: `submitted_at` serialized as UTC ISO8601 (`datetime.isoformat()` with `+00:00` suffix). On decode, parse with `datetime.fromisoformat()` and assert `tzinfo is not None`. Pass the resulting `datetime` object — not a string — to the MongoDB query.
- **NULL sort values (forward-looking — `most_stars` keyset, deferred):** When `sv` is `None` (e.g., `github_stars` not set for a skill), encode `"sv": null`. On decode, skip the `$lt` branch; use `{"github_stars": None, "_id": {"$lt": ObjectId(id)}}` only. Never issue `{"github_stars": {"$lt": None}}` — this matches no documents in MongoDB. **Delivery scope note:** For the current delivery (only `newest` sort is keyset-eligible), `submitted_at` is non-nullable, so a null `sv` in a decoded cursor is invalid. Implementations for Slice 2 must reject null `sv` with HTTP 422 per FR-1. The null `sv` decode path above activates only when `most_stars` keyset is explicitly scoped and enabled (see AR-2).

**Sort stability requirement:** The sort expression for keyset-eligible sorts must include `_id` as the final sort key to guarantee stable document ordering:
```python
"newest": [("submitted_at", -1), ("_id", -1)],
```
Without `_id` as a secondary sort, two documents with identical `submitted_at` may be returned in different orders on consecutive requests, breaking cursor correctness.

The backend decodes and builds (for `newest` sort, forward direction):
```python
# sv must be a datetime object (not a string) to get correct $lt semantics
{"$or": [
  {"submitted_at": {"$lt": sv}},
  {"submitted_at": sv, "_id": {"$lt": ObjectId(id)}}
]}
```

**prev_cursor implementation note:** Backward navigation uses a fetch-and-flip pattern: sort `ASC`, apply `$gt` keyset bounds on the first item of the current page, limit to `page_size`, then reverse the result list. For Slice 2, `prev_cursor` may be set to `null` (with backward navigation falling back to skip-based requests) until this is explicitly scoped.

**API contract additions:**
```
GET /api/skills
  Existing params: q, sort, page, page_size, labels, visibility, forked_from
  New params:      cursor (optional, opaque string)

Response (additions):
  {
    "items": [...],
    "total": 1234,        # existing (now cached)
    "page": 7,            # existing
    "pages": 62,          # existing
    "next_cursor": "...", # new (null if on last page or sort not keyset-eligible)
    "prev_cursor": "..."  # new (null if on first page)
  }
```

---

## ADRs

### ADR-U32: Keyset vs. offset pagination strategy

**Status:** Accepted

**Context:** Pure keyset breaks "jump to page N". Pure offset degrades O(N) at high page numbers. Hybrid options: (A) keep offset for pages 1–10, use keyset beyond; (B) add optional `cursor` param, let frontend choose; (C) replace offset entirely.

**Decision:** Option B — optional `cursor` param, backward-compatible. Pages 1–10 use existing skip() (at most 180 docs scanned — negligible). Pages 11+ use cursor when the frontend sends it. The API never breaks existing clients. Frontend adopts cursor incrementally.

**Consequences:** Two code paths in `list()`. Cursor must be stable during a browsing session (stale-cursor edge case: skill deleted between cursor generation and use — handle gracefully by returning partial page, not 500). Initial delivery restricts keyset to `sort=newest` only. `most_stars` keyset is deferred because `github_stars` is `Optional[int]`; `$lt: null` comparisons in MongoDB do not behave intuitively for descending sort tails.

---

### ADR-U33: Count caching strategy

**Status:** Accepted

**Context:** Options: (A) `estimatedDocumentCount()` — O(1), ignores filters; (B) in-process TTL cache per filter fingerprint; (C) Redis cache; (D) remove total count from API response.

**Decision:** Hybrid A+B. Unfiltered requests (front page) use `estimatedDocumentCount()`. Filtered requests use in-process 30s TTL cache keyed by filter fingerprint. No Redis dependency. Cache is invalidated on skill write operations (create, deactivate, reactivate) — those are rare and write to the same process.

**Consequences:** In multi-process deployments (multiple uvicorn workers), caches are per-process. Counts may differ by up to 30s between workers — acceptable. If the deployment ever moves to multi-node, replace with Redis. Cache invalidation on write must flush the entire cache dict (not just affected fingerprints) — it is not feasible to know which cached fingerprints a newly created/deactivated skill would match. Cache must be size-bounded (maxsize=1000, LRU eviction) to prevent unbounded memory growth from adversarial high-cardinality query inputs.

**Security note (SR-3/A5):** The cache stores counts only, not items. The cache key intentionally excludes caller identity because counts are low-sensitivity. If item-level caching is added in a future slice, caller auth context must be included in the cache key. The `visibility=internal` list-endpoint auth gap is pre-existing and tracked as a separate task; this ADR does not introduce a new disclosure vector — it only caches counts that are already served to unauthenticated callers today.

---

### ADR-U34: Search quality improvement approach

**Status:** Accepted

**Context:** Atlas Search is the ideal path but is Atlas-cloud-only — the cluster runs self-hosted Percona Server for MongoDB 8.0 via the Percona Kubernetes Operator, making Atlas Search architecturally unavailable on the current infrastructure (not just unconfirmed). Options: (A) remove Atlas Search entirely; (B) keep feature-flagged path as dead-letter code reserved for future Atlas migration; (C) add Meilisearch sidecar as an alternative.

**Decision:** Option B. Keep the `MONGODB_ATLAS_SEARCH` feature flag and `build_atlas_pipeline()` in the codebase — they are dead-letter on the current cluster but provide a ready migration path if the stack ever moves to MongoDB Atlas. Ship name/slug boost immediately as the concrete improvement. Meilisearch/Typesense deferred — adds operational complexity that isn't justified at current scale.

**Consequences:** Atlas Search code path is permanently inactive on the current cluster. The Risk Register entry for Atlas Search is updated to reflect this is a certainty, not a risk. Users searching with conceptual or fuzzy terms (e.g. 'k8s deploy helm', 'config drift detection') will not see improvement from this change. The frontend should include a search hint — tooltip on the input or an inline note — indicating that exact name matches rank highest, to set expectations. This is required as part of Slice 3.

---

## Trade-offs

**Choice: Cursor encoding (opaque base64 vs. explicit page+anchor params)**
- Opaque: frontend cannot inspect or forge cursor; easier to change encoding
- Explicit: easier to debug in network tab
- Decision: opaque base64. The cursor format may change (adding sort fields); clients should not depend on its structure.

**Choice: In-process count cache vs. Redis**
- In-process: zero infrastructure cost; works today
- Redis: shared across workers; more accurate in multi-process
- Decision: in-process for now. Flag in code with a TODO for Redis when multi-node.

**Choice: Name boost pre-pass vs. proper search scoring**
- Pre-pass: easy to implement; no infrastructure; handles the most common case (exact name match)
- Proper scoring: requires Atlas Search or external engine; handles all cases
- Decision: pre-pass as a stepping stone. Atlas Search is the target state.

---

## Delivery Slices

**Slice 1 — Compound indexes + count cache (1 day)**
- Add compound indexes to `Skill.Settings.indexes`
- Replace `count()` with `estimatedDocumentCount()` for unfiltered; add in-process cache for filtered
- `PaginatedSkills` gains `next_cursor`/`prev_cursor` fields (null for now; `SkillListOut` is the per-item schema and is unchanged)
- No visible change to users; measurable latency improvement on repeated loads

**Slice 2 — Keyset pagination backend (2 days)**
- Add `cursor` param to `GET /api/skills`
- Implement cursor encode/decode + keyset query branch in `list()`
- Integration test: verify no `skip()` in explain plan when cursor is provided
- `next_cursor` and `prev_cursor` are now populated in responses

**Slice 3 — Search: name boost (1 day)**
- `services/search.py`: `name_boost()` pre-pass
- Wire into `list()` when `q` is present
- Unit test: exact name match appears first
- Frontend search input gains a hint (tooltip or inline note) indicating exact name/slug matches rank highest (per ADR-U34)

**Slice 4 — Frontend: page-number input + cursor adoption (1–2 days)**
- Add page-number input to `skill-list.tsx`
- Track cursors in component state; send cursor for pages >10 (sort=newest only)

**Slice 5 — Atlas Search path (deferred — unavailable on current cluster)**
- `MONGODB_ATLAS_SEARCH` env var and `build_atlas_pipeline()` are present in the codebase but inactive
- This slice only ships if the cluster migrates to MongoDB Atlas
- No integration test possible against current infrastructure

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Atlas Search unavailable on current cluster (self-hosted Percona MongoDB, not Atlas) | Certainty | Low | Feature flag kept for future Atlas migration; name boost is the only active search improvement |
| Stale cursor (skill deleted between pages) | Low | Low | Return partial page, not error; frontend handles gracefully |
| In-process cache diverges across workers | Medium | Low | 30s TTL; note in code for Redis upgrade |
| Compound index creation blocks writes during migration | Low | Medium | Create indexes with `background=True` (MongoDB); run in off-peak window |
| Cursor encoding changes break bookmarked URLs | Low | Medium | Cursors are never in the URL (page number is); cursors are in component state only |

---

## Definition of Done

- [ ] Compound sort indexes defined in `Skill.Settings.indexes` and verified in DB
- [ ] `estimatedDocumentCount()` used for unfiltered count; in-process 30s TTL cache for filtered count
- [ ] `GET /api/skills?cursor=<opaque>` uses keyset query (no skip) for `sort=newest`; `most_stars` keyset deferred
- [ ] `PaginatedSkills` schema gains `next_cursor: Optional[str] = None` and `prev_cursor: Optional[str] = None` (not `SkillListOut` — that is the per-item schema)
- [ ] Name boost pre-pass: `name_boost()` issues a separate DB call so exact matches not in the current `$text` result page are surfaced; deduplication by `_id` applied before returning
- [ ] `MONGODB_ATLAS_SEARCH` feature flag wired up (disabled by default)
- [ ] Frontend: page-number input field renders and navigates correctly
- [ ] Frontend: cursor is used (not page) when navigating beyond page 10 (sort=newest)
- [ ] Unit test: cursor encode/decode round-trip; datetime decoded as UTC `datetime` object (not string); malformed cursor returns HTTP 400; null `sv` generates null-only query branch (no `{"$lt": None}`)
- [ ] Unit test: cursor security validation — `sv` typed as dict or list (structurally valid JSON, semantically invalid scalar check) returns HTTP 422 "Invalid or expired cursor"; `id` field failing `[0-9a-f]{24}` regex returns HTTP 422 "Invalid or expired cursor"; raw exception detail absent from 422 response body
- [ ] Unit test: keyset sort expression includes `_id` as secondary sort key; `{"github_stars": {"$lt": None}}` never generated
- [ ] Unit test: count cache hit within 30s; miss after TTL; entire cache dict cleared on any write; unfiltered path uses `estimatedDocumentCount` not `count()`
- [ ] Unit test: `name_boost` — exact name/slug match prepended and deduplicated; partial match not boosted; off-page exact match appears at position 0
- [ ] Frontend: search input includes a hint (tooltip or inline note) stating that exact name matches rank highest (per ADR-U34)
- [ ] Unit test: Atlas Search flag toggle — `MONGODB_ATLAS_SEARCH=0` produces `$text` query; `MONGODB_ATLAS_SEARCH=1` delegates to aggregation pipeline with `$search` stage; when `MONGODB_ATLAS_SEARCH=1` and `pymongo.errors.OperationFailure` is raised, service logs at WARNING and falls back to `$text` path returning a valid result (no 500)
- [ ] Unit test: stale cursor (skill deleted between pages) returns partial page (no 500)
- [ ] Integration test: explain plan confirms no `skip()` when cursor is provided
- [ ] Integration test: count cache hit on repeated identical requests within 30s
- [ ] Integration test: exact name match ranks first in search results
- [ ] Load test: p95 < 300ms at 5,000 skills, any sort, page 50 (keyset path)
- [ ] ADRs written: `docs/adr/adr-u32-keyset-pagination.md`, `docs/adr/adr-u33-count-cache.md`, `docs/adr/adr-u34-search-quality.md`
- [ ] `CHANGELOG.md` entry written under `## Unreleased` covering cursor pagination, count caching, name-boost search, and page-number input
- [ ] `backend/.env.example` updated: add `MONGODB_ATLAS_SEARCH=` with inline comment explaining the feature flag and the Atlas tier prerequisite
- [ ] `PRD.md` FR-20 updated to reflect the hybrid cursor/skip strategy (currently reads "cursor-based" but the shipped design is opt-in cursor with skip fallback)
- [ ] `docs/skill-file-discovery.md` (or a new `docs/catalog-api.md`) updated to document the full `GET /api/skills` contract: new `cursor` param, new `next_cursor`/`prev_cursor` response fields, count-caching behaviour, and the `MONGODB_ATLAS_SEARCH` flag

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

> *Populated by `/board-review` after the board completes. Do not fill manually.*

**Verdict:** —
**Date:** —
**Rounds:** —

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | ✅ PASS | N | Atlas Search permanently unavailable (self-hosted Percona PSMDB, not Atlas); Motor deprecated May 2025 (Beanie 1.26 still uses it); `_id` needed in compound index |
| codebase-arch-review | ✅ PASS | Y | Page threshold inconsistency (5 vs 10); null `github_stars` breaks `most_stars` keyset; `name_boost` pure-function contradiction; missing `submitted_at` tiebreaker in diagram; cache flush underspecified |
| codebase-eng-review | ✅ PASS | Y | `PaginatedSkills` schema corrected; cursor `_id` sort stability; `prev_cursor` deferred to null; datetime UTC serialization spec; cache invalidation tightened; 6 new unit test cases |
| doc-review | ✅ PASS | Y | CHANGELOG missing from DoD; `MONGODB_ATLAS_SEARCH` undocumented in `.env.example`; PRD FR-20 misaligned with hybrid design; no `GET /api/skills` API contract doc |
| security-review | ✅ PASS | Y | CRITICAL: cursor `sv` NoSQL injection via dict value; HIGH: `ObjectId` raises 500 on invalid input; server-side page cap `le=1000`; Atlas Search fallback on OperationFailure; `name_boost` must use `$eq` only; cache bounded with TTLCache maxsize=1000 |
| codebase-ux-review | ✅ PASS | Y | `PaginatedSkills` schema corrected; stale `estimatedDocumentCount` scope note; FR-7 full UX spec (validation, reset, mobile hide, stale-bookmark redirect); search hint required in Slice 3 |

**Accepted warnings:**
- Motor 3.7.1 deprecated (May 2025); Beanie 1.26 still depends on it. Beanie 2.x upgrade filed as a separate follow-on task.
- `estimatedDocumentCount()` may over-count by orphaned documents on sharded cluster; acceptable for UI display.
- `visibility=internal` on list endpoint has no auth guard (pre-existing, tracked separately).
- In-process count cache diverges across uvicorn workers; Redis upgrade deferred.

**Unresolved decisions:** none

---

## Relationship to Other Tasks

- **#009 (Duplicate detection):** Improved search (especially semantic/Atlas Search) directly enables better duplicate detection.
- **#003 (Label UX):** Label filter performance is in this task's scope — but the current aggregation is already indexed and fast enough to defer.
- **#011 (User activity):** User activity queries (skills by submitter) will benefit from the same compound index approach.

---

### Reviewer output

<details>
<summary>research — Round 1 (PASS)</summary>

# Round 1 — Deep Research Review
**Plan:** 015-catalog-scale-search-pagination
**Reviewer:** research-handbook (DR subagent)
**Date:** 2026-06-03

## Summary

The plan's core pagination and caching strategy is technically sound and well-established. However, **the Atlas Search feature-flag path is permanently dead-letter**: the cluster runs self-hosted Percona Server for MongoDB 8.0, not MongoDB Atlas, so Atlas Search is architecturally unavailable — not just "unconfirmed". The plan's Risk Register already partially acknowledges this but frames it as "medium likelihood"; it is in fact a certainty. Additionally, Motor 3.7.1 (used in this project) was deprecated in May 2025 in favour of PyMongo Async, though Beanie 1.26 still depends on it and critical bug fixes continue until May 2026. The cursor encoding approach is correct but requires a note about `$or`-based multi-field keyset queries being significantly more complex than the plan implies.

## Issues

**ISSUE-1 (HIGH):** Atlas Search is unavailable on the actual cluster — cluster runs self-hosted Percona PSMDB 8.0, not Atlas. Slice 5 and FR-6 are permanently dead-letter as written. Plan amended: Risk Register updated from "Medium" to "Certainty"; ADR-U34 updated to frame as "reserved for future Atlas migration."

**ISSUE-2 (MEDIUM):** Motor 3.7.1 deprecated May 2025; Beanie 1.26 still depends on it. Beanie 2.x (March 2026) dropped Motor. Keyset implementation should use Beanie `find()` API (not raw Motor) to ease future migration.

**ISSUE-3 (MEDIUM):** Multi-field keyset `$or` requires `_id` as third field in compound index for full index coverage. `(status, submitted_at DESC)` is insufficient — needs `(status, submitted_at DESC, _id DESC)`.

**ISSUE-4 (LOW):** `estimatedDocumentCount()` may over-count by orphaned documents on sharded cluster. Acceptable for display; documented in ADR-U33.

**ISSUE-5 (LOW):** No existing Python library for Motor/Beanie keyset pagination — must hand-roll. Confirmed. Use `Skill.find()` API with raw dict query parts.

## Status
PASS

</details>

<details>
<summary>codebase-arch-review — Round 2 (PASS)</summary>

# Architecture Review — Round 2
## #015 Catalog Scale: Search Quality, Pagination, and Performance

## Summary

All Round 1 amendments verified as correctly applied except one: the compound index bullet in Design section and System Design diagram still listed `(status, submitted_at DESC)` without `_id DESC` tiebreaker — amended in Round 2. All other Round 1 amendments confirmed correct.

## Issues

**AR2-1 (MINOR):** Compound index definition for `newest` sort did not include `_id DESC` tiebreaker in Design section bullet and System Design diagram, despite the sort expression section correctly specifying `("_id", -1)`. Without explicit `_id` in the index, MongoDB must fetch `_id` from documents rather than the index for tiebreaker comparison. Both locations corrected.

## Status
PASS WITH AMENDMENTS

</details>

<details>
<summary>codebase-eng-review — Round 2 (PASS)</summary>

# Engineering Review — Round 2
## #015 Catalog Scale: Search, Pagination, Performance

## Summary

All six Round 1 engineering amendments correctly applied. Five residual issues found and all amended: Slice 1 `SkillListOut` reference (fixed by ar), FR-3 cache invalidation aligned with ADR-U33, AC-4 corrected to reflect `prev_cursor` is null in Slice 2, SR-1/SR-2 unit test cases added, Atlas Search OperationFailure fallback test added.

## Key Round 1 issues resolved:
- NULL github_stars cursor bug → keyset restricted to `newest` only
- prev_cursor unspecified → deferred to null (skip fallback)
- Wrong schema `SkillListOut` → corrected to `PaginatedSkills`
- `_id` missing from sort expression → added
- name_boost pure-function contradiction → confirmed as async DB call
- Cache invalidation underspecified → full dict flush on any write

## Status
PASS WITH AMENDMENTS

</details>

<details>
<summary>doc-review — Round 1 (PASS)</summary>

# Doc Review — Round 1
## #015 Catalog Scale

## Summary

Four documentation gaps identified and added to DoD: CHANGELOG missing, `MONGODB_ATLAS_SEARCH` undocumented in `.env.example`, PRD FR-20 misaligned with hybrid design, no `GET /api/skills` API contract doc.

## Issues

**DC-1 (LOW):** CHANGELOG absent from DoD — added.
**DC-2 (MEDIUM):** `MONGODB_ATLAS_SEARCH` not documented in `backend/.env.example` or any runbook — DoD item added.
**DC-3 (LOW):** PRD.md FR-20 says "cursor-based" but design is hybrid skip/cursor — DoD item to update PRD added.
**DC-4 (MEDIUM):** No standalone `GET /api/skills` API contract doc exists; new cursor param, response fields, count semantics, and feature flag need documentation — DoD item added.

## Status
PASS

</details>

<details>
<summary>security-review — Round 2 (PASS)</summary>

# Security Review — Round 2
## #015 Catalog Scale

## Summary

All six Round 1 security amendments confirmed present. Three minor gaps patched: null `sv` scope clarification added to cursor encoding section; `id` regex anchored to `^[0-9a-f]{24}$` and explicit `try/except bson.errors.InvalidId` added to FR-1; in-process count cache bounded with `TTLCache(maxsize=1000, ttl=30)` to prevent unbounded growth from adversarial unique `q` values.

## Key Round 1 issues resolved:
- CRITICAL: cursor `sv` NoSQL injection → scalar type validation required
- HIGH: `ObjectId()` unhandled exception → try/except + HTTP 422
- MEDIUM: no server-side page cap → `le=1000` added to FR-7
- MEDIUM: Atlas Search no fallback → `OperationFailure` catch + `$text` fallback
- LOW: `name_boost` regex risk → `$eq`-only spec added
- `visibility=internal` auth gap acknowledged in ADR-U33

## Status
PASS WITH AMENDMENTS

</details>

<details>
<summary>codebase-ux-review — Round 2 (PASS)</summary>

# UX Review — Round 2
## #015 Catalog Scale

## Summary

Round 1 amendments largely applied correctly. Two residual gaps found and amended: Slice 1 description still referenced `SkillListOut` (fixed); ADR-U34 mandated search hint in Slice 3 but neither Slice 3 bullets nor DoD checklist carried the item (fixed).

## Key Round 1 issues resolved:
- BLOCKER: `PaginatedSkills` schema corrected (cursors on envelope, not per-item)
- BLOCKER: stale/inflated `estimatedDocumentCount` scope note added to FR-3
- HIGH: search quality gap → search hint required in Slice 3
- HIGH: page input clamping UX fully specified in FR-7
- MEDIUM: cursor bookmark regression → documented in FR-8
- LOW: mobile layout spec → FR-7 hide at `sm`

## Status
PASS WITH AMENDMENTS

</details>
