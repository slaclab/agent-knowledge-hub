# 006 — Skillsets: Curated Skill Collections

**Status:** 📋 Preparing
**Branch:** —
**PR:** —

---

## Problem & Goal

**Problem:** Users from different facilities and groups (USDF, LCLS, SCS, etc.) need a way to discover and install a curated bundle of skills relevant to their context. Today, every skill is standalone — there is no concept of a collection, no way for a facility lead to say "these 12 skills are what LCLS users should start with", and no signal on a skill's detail page that it belongs to a well-known set.

**Goal:** Introduce **Skillsets** — named, curated collections of skills maintained by a submitter. A skillset can be discovered, browsed, and installed as a unit. Each skill surfaces a reverse link showing which skillsets it belongs to, giving a secondary popularity signal beyond star ratings.

**Success metrics:**
- A user can browse skillsets, see which skills they contain, and install the full set in one action
- A curator can create, name, describe, and manage a skillset (add/remove skills)
- Every skill detail page shows "Part of N skillset(s)" with links to those skillsets
- Skillset membership count is visible on the skills browse/list page as a lightweight popularity indicator

**Out of scope:**
- Automated skillset generation (ML-based recommendations)
- Versioned skillsets (pinning specific skill versions)
- Skillset ratings or reviews (separate feature)
- Private/org-restricted skillsets (initial version is public only)

---

## Design

_To be filled in by `/codebase-draft`._

### Key questions to resolve before design

1. **Data model**: Skillset as a first-class MongoDB document referencing skill slugs/IDs, or embedded in a skills collection?
2. **Curator permissions**: Any authenticated user, or admin-only for initial release?
3. **Install UX**: What does "install all" mean in practice — download a manifest, open each skill, or something else?
4. **Reverse link display**: Show on skill card (list view) or only on skill detail page?
5. **Skillset slug/URL**: `/skillsets/<slug>` as a new top-level route?

---

## Implementation Plan

_To be filled in by `/codebase-draft`._

---

## Problems & Solutions

_None yet._

---

## References

_None yet._
