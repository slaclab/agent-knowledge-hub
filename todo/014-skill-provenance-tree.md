# TODO #014 — Skill Provenance Tree: Fork and Evolution Graph

> **Priority:** 🟡 P2 — Medium
> **Status:** 📋 Preparing
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

Skills don't exist in isolation — they fork from upstream repos, get superseded by newer versions, and accumulate forks within the catalog. Today the detail page shows one hop in each direction (a "Forked from" link and a "N forks in catalog" count) but there's no way to see the full lineage: where did this skill originate, who forked it, which version superseded which?

A user looking at a skill cannot answer: "Is this the canonical version or a downstream fork?", "Which fork is most actively maintained?", "Has this skill been superseded — and by what chain?".

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| "Where did this skill come from?" | Single "Forked from" link | Full upstream chain visualised |
| "Who forked this skill?" | "N forks in catalog" count with a link to filtered list | Tree showing forks and their forks |
| "Has this been superseded?" | Banner on detail page if direct `superseded_by_slug` set | Full supersession chain shown |
| "Which fork is most active?" | Not comparable | Tree nodes show stars, last commit, rating |
| New contributor lands on a fork | No signal about canonical upstream | Provenance tree shows canonical root |

---

## Goals

1. A provenance tree view on the skill detail page (or a dedicated `/skills/<slug>/provenance` page) showing:
   - Upstream chain: the skill's `forked_from_url` → resolved to catalog entries where possible, with GitHub links for entries not in the catalog
   - Downstream forks: catalog skills that declare `forked_from_url` pointing to this skill's repo
   - Supersession chain: skills linked via `superseded_by_slug` rendered as a directed path
2. Tree nodes show: name, submitter, stars, last commit, avg rating — enough to compare forks at a glance
3. Non-catalog upstream entries (GitHub repos not in the catalog) shown as external nodes with a link
4. Collapsed by default on the detail page sidebar; full tree accessible on a dedicated page or modal

## Non-Goals

- Automatic fork detection from GitHub (relies on `forked_from_url` being set at submission time — improving that detection is a separate concern)
- Diff between fork and upstream (relates to #013 but is a distinct problem)
- Visualising label or revision history on the tree nodes

---

## Design

> *To be filled in by `/codebase-draft`.*

### Data Model

The graph is implicit in three existing fields:
- `forked_from_url` — points to upstream repo URL (may or may not be in catalog)
- `superseded_by_slug` — catalog slug of the replacement skill
- `repo_url` — used to match downstream forks (`listSkills({ forked_from: repo_url })`)

Building the full tree requires multi-hop resolution: fetch forks of forks, follow supersession chains. This could be:
- **Client-side recursive fetch** — simple but multiple round trips
- **Backend `GET /skills/<slug>/provenance`** — returns the full tree in one call; better for deep chains

### Open Questions

1. **How deep should the tree go?** — Recommendation: cap at 3 hops upstream and 2 levels of forks downstream to avoid runaway queries on deep lineages.
2. **Backend endpoint or client-side assembly?** — Recommendation: a dedicated `GET /skills/<slug>/provenance` endpoint that returns a pre-built tree JSON; avoids N+1 fetches from the browser.
3. **Visualisation library?** — A simple indented tree (CSS only) may be sufficient for v1. A graph library (e.g. react-flow, d3-hierarchy) would be needed for complex DAGs. Recommendation: start with indented tree, upgrade if needed.
4. **What if the upstream repo is not in the catalog?** — Show as an external leaf node with a GitHub link and repo metadata (stars, last commit) fetched via the existing scan endpoint.

---

## Implementation Plan

> *To be filled in by `/codebase-draft`.*

---

## Implementation Checklist

- [ ] Backend: `GET /skills/{slug}/provenance` — return tree of upstream, forks, and supersession chain (depth-limited)
- [ ] Backend: resolve `forked_from_url` to catalog slugs where possible
- [ ] Frontend: `ProvenanceTree` component — indented tree or graph
- [ ] Frontend: tree nodes show name, submitter, stars, rating, last commit
- [ ] Frontend: external (non-catalog) nodes shown with GitHub link
- [ ] Frontend: supersession chain shown as directed path with "superseded by" labels
- [ ] Frontend: collapsed summary on detail page sidebar; full view on expand or dedicated page
- [ ] Tests for tree construction (cycles, orphan nodes, external-only upstreams)

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

- **#001 (Fork provenance):** This task is the richer visualisation of the fork links introduced in #001.
- **#013 (Revision history):** Tree nodes could eventually link to revision diffs for a given fork.
- **#009 (Duplicate detection):** Provenance data helps distinguish intentional forks from accidental duplicates.
