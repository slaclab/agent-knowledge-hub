# TODO #015 — Catalog Scale: Search Quality, Pagination, and Performance

> **Priority:** 🟡 P2 — Medium
> **Status:** 📋 Preparing
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

The current implementation was designed for a small catalog. As the number of registered skills grows, several parts of the stack will degrade:

1. **Search** uses MongoDB `$text` (basic stemmed keyword match). It has no relevance ranking beyond score, no fuzzy matching, and no semantic/embedding search. With hundreds of skills, a query like "kubernetes deploy helm" will miss skills that describe the concept differently.
2. **Pagination** uses `skip(n).limit(m)` — MongoDB must scan and discard `n` documents on every page turn. At 1,000+ skills this is slow and gets worse with each page.
3. **Total count** runs a separate `count()` against the full filtered query on every page load. This is redundant work and slows as the corpus grows.
4. **Label filter** uses an aggregation pipeline (`SkillLabel` → aggregate → `In` filter) that produces a potentially large `$in` list. At scale this risks exceeding MongoDB's 16 MB document limit or becoming slow.
5. **No caching** — every page load hits MongoDB directly. Repeated identical queries (front page, "newest 20 skills") are re-executed every time.
6. **Frontend pagination** is simple prev/next with no quick-jump, no infinite scroll option, and no URL-preserving deep links for specific pages.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| 5,000 skills, page 50 | `skip(980)` scans 980+ docs | Cursor/keyset pagination, no scan |
| Search "kubernetes deployment" | Only matches if those exact words appear | Fuzzy + semantic match |
| Front page load | Full count + query on every request | Cached or incrementally updated count |
| Filter by 3 labels, 2,000 skills | Large `$in` list built per request | Index-covered join or denormalized tags |
| User wants page 7 of results | Can only click prev/next | Page number input or infinite scroll |

---

## Goals

1. **Keyset/cursor pagination** — replace `skip()` with keyset pagination for `sort=newest` and `sort=most_stars`; retain offset for random-access sorts where keyset is impractical
2. **Search quality** — evaluate options: Atlas Search (if available), a lightweight embedding index, or a dedicated search service (Meilisearch/Typesense); define minimum viable improvement over `$text`
3. **Count caching** — cache or approximate total counts; avoid re-counting on every page request
4. **Label join performance** — benchmark current aggregation at 1k/5k/10k skills; denormalize labels onto the Skill document if aggregation becomes a bottleneck
5. **Frontend UX** — add page-number input, "jump to page N", and optionally infinite scroll as an alternative to prev/next buttons

## Non-Goals

- Full semantic / vector search (may be a follow-on once embedding infra is in place)
- Elasticsearch / Solr (overkill for current scale projection)
- Real-time streaming updates to the catalog list

---

## Design

> *To be filled in by `/codebase-draft`.*

### Current Bottlenecks (in priority order)

1. `skip()` pagination — worst at high page numbers; fix first
2. `count()` on every request — cheap fix: cache with a short TTL or use `estimatedDocumentCount`
3. `$text` search quality — medium-term; Atlas Search or Meilisearch are the main options
4. Label aggregation — only a problem at very high scale; monitor before fixing

### Open Questions

1. **Is MongoDB Atlas Search available on the cluster's Atlas tier?** — Determines whether we can use Atlas Search (best path) or need a sidecar search service.
2. **What is the realistic scale target?** — 500 skills? 5,000? This determines urgency of each fix.
3. **Cursor pagination tradeoff:** keyset works well for time-sorted feeds but breaks "jump to page N". Should we support both modes, or accept that deep pagination is rare?
4. **Infinite scroll vs. traditional pagination?** — Recommendation: keep prev/next as default; add optional infinite scroll behind a feature flag for the list page.

---

## Implementation Plan

> *To be filled in by `/codebase-draft`.*

---

## Implementation Checklist

- [ ] Benchmark current query performance at 100 / 1k / 10k skills
- [ ] Backend: replace `skip()` with keyset pagination for time-sorted queries
- [ ] Backend: cache or approximate total count
- [ ] Backend: evaluate and implement improved search (Atlas Search vs. Meilisearch vs. embedding)
- [ ] Backend: benchmark label aggregation; denormalize if needed
- [ ] Frontend: page number input / jump-to-page
- [ ] Frontend: loading states and skeleton cards during pagination transitions
- [ ] Load tests written and passing at target scale

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

- **#009 (Duplicate detection):** Improved search (especially semantic) directly enables better duplicate detection.
- **#003 (Label UX):** Label filter performance is part of this task's scope.
- **#011 (User activity):** User activity queries (skills by submitter, skills by editor) will have similar pagination needs.
