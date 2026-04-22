# 009 — Duplicate & Similar Skill Detection

**Status:** ⬜ Open
**Branch:** —

---

## Problem & Goal

**Problem:** When a user runs discovery (bulk submit from a directory URL), the UI already grays out *exact* duplicates (`existing_slug` set by the backend via `repo_url + skill_path` match). However, there is no handling for:

1. **Near-duplicates** — a skill with the same name or very similar description already exists in the catalog, submitted from a different repo or path (e.g. a fork, a mirror, or a slightly different directory layout).
2. **User intent conflict** — the user explicitly selects an already-registered skill in the discovery UI and tries to submit it anyway; the current UI only disables the checkbox but gives no explanation.
3. **Post-submit collision** — two users submit the same skill concurrently; the second submission gets a `409 Conflict` with no actionable guidance beyond the raw error.

**Goal:** Surface duplicate and similar-skill signals earlier (before submission), give users actionable guidance (link to existing entry, explain why it's flagged), and handle the post-submit 409 gracefully in the bulk submit flow.

---

## User Stories

1. As a submitter, when I run discovery on a directory, I want near-duplicate skills clearly flagged with a link to the existing catalog entry, so I don't submit a redundant copy.
2. As a submitter, when I try to select an already-registered skill in discovery mode, I want to see *why* it's disabled (not just grayed out), so I understand what's happening.
3. As a submitter, if my bulk submission hits a 409, I want the result row to show "Already in catalog → view →" rather than a raw error message.
4. As an admin, I want to be able to mark two skills as duplicates of each other, so the community converges on the best version.

---

## Open Questions

- **Similarity threshold**: What constitutes a "similar" skill? Options:
  - Exact name match (case-insensitive)
  - Name edit distance < N (fuzzy)
  - Embedding cosine similarity > threshold (semantic — requires vector index, deferred to #007 or a later slice)
- **Where does similarity run?** Backend at scan time (add `similar_slugs: list[str]` to `SkillScanSnapshotOut`) vs. frontend-only check against the catalog summary endpoint.
- **Admin dedup tooling**: Should admins be able to set `superseded_by_slug` on a skill from the admin label dashboard, or does this need a separate admin skill management page?

---

## Proposed Approach (sketch)

### Phase 1 — Exact duplicate UX polish (low effort)
- In `DiscoveryCard`: show a tooltip/explainer on the disabled checkbox: "Already in catalog" with a link to `existing_slug`.
- In bulk submit result rows: detect `409` response and render "Already in catalog → view →" instead of raw error text.

### Phase 2 — Name-based near-duplicate detection (medium effort)
- Backend: in `_check_existing` (or a new `_check_similar`), also query for skills with the same normalised name (case-insensitive). Return a `similar_slugs: list[str]` field alongside `existing_slug` in `SkillScanSnapshotOut`.
- Frontend: render a "Similar skill already exists" warning chip on `DiscoveryCard` when `similar_slugs` is non-empty, with links. Keep the checkbox enabled — user can still submit if they believe their version is distinct.

### Phase 3 — Semantic similarity (deferred)
- Requires a vector index on skill embeddings (related to #004 multi-source scanner and future semantic search).
- Out of scope until vector search infrastructure exists.

---

## Definition of Done

- [ ] `DiscoveryCard` shows "Already in catalog → view →" tooltip/link on disabled checkbox
- [ ] Bulk submit 409 result row shows actionable message with link, not raw error
- [ ] Backend `SkillScanSnapshotOut` includes `similar_slugs: list[str]` (name-match)
- [ ] `DiscoveryCard` renders "Similar skill exists" warning when `similar_slugs` non-empty
- [ ] Single-skill submit form shows same near-duplicate warning after scan
- [ ] Admin can set `superseded_by_slug` from skill edit page (or admin dashboard)
