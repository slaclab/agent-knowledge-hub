# TODO #013 — Rich Revision History: Diffs, Labels, and Upstream Links

> **Priority:** 🟡 P2 — Medium
> **Status:** 📋 Preparing
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

The revision timeline on the skill detail page shows action type, actor, date, and changelog note — but nothing about *what changed*. Every `edit` and `refetch` revision stores a full `snapshot: Dict[str, Any]` of the skill at that point, so the data for a rich diff is already there. It's just not surfaced.

A user looking at revision history today cannot answer: "What fields changed in rev 4?", "Did the description change?", "Were labels added or removed?", "When did the upstream repo URL change?".

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| "What changed in this edit?" | Only changelog note (if author wrote one) | Inline diff of changed fields |
| "Were labels changed?" | Not shown — labels not in revision snapshot | Label adds/removes shown per revision |
| "Did the description change?" | Not shown | Old → new description shown as diff |
| "When did the upstream repo link change?" | Not shown | `repo_url` / `forked_from_url` changes surfaced |
| "What platforms were added?" | Not shown | `compatible_platforms` diff shown |
| Refetch with no meaningful change | Shows "Re-fetched from GitHub" with no context | Shows "no metadata changes" or lists what updated (stars, last_commit_at) |

---

## Goals

1. For `edit` and `refetch` revisions, compute a field-level diff between consecutive snapshots and display changed fields inline in the timeline
2. Show label adds/removes per revision (labels are not in the snapshot today — may need to be added, or tracked separately via a label audit log)
3. Collapsible diff view — collapsed by default, expandable per revision to avoid overwhelming the sidebar
4. Highlight semantically meaningful changes: description, name, platforms, repo_url, forked_from_url, version, license
5. Refetch revisions with no metadata changes show a "no changes detected" note
6. `create` revisions show the initial values (name, description, platforms, labels) as the "genesis" state

## Non-Goals

- Full side-by-side text diff (word-level) for long description fields — a one-line "changed" indicator is sufficient for v1
- Revision rollback / undo
- Diff for `deactivate` / `reactivate` (action is self-describing)

---

## Design

> *To be filled in by `/codebase-draft`.*

### Key Assets

- `SkillRevision.snapshot: Dict[str, Any]` — full skill state at each revision, stored in MongoDB. Fields include: `name`, `description`, `compatible_platforms`, `version`, `license`, `repo_url`, `forked_from_url`, `readme_html`, `github_stars`, `last_commit_at`, `visibility`.
- Revisions are already fetched in `getRevisions()` and passed to `RevisionTimeline` — no new API call needed for field diffs.
- Labels are **not** currently in the snapshot. Two options: (a) add `labels` to the snapshot at write time, or (b) derive label changes from `SkillLabel` timestamps (approximate). Option (a) is cleaner.

### Open Questions

1. **Are labels included in `snapshot` today?** — Check backend `skill_service.py` snapshot construction. If not, adding them is a small backend change alongside this task.
2. **Should `readme_html` diffs be shown?** — Recommendation: no — too noisy in a sidebar. Show a "README updated" indicator at most.
3. **Frontend only or backend diff endpoint?** — Recommendation: compute diff client-side from the already-fetched revision list. No new endpoint needed for field diffs; only the snapshot needs to include labels.
4. **Collapsed by default?** — Recommendation: yes — show a summary badge ("3 fields changed") that expands on click, keeping the sidebar compact.

---

## Implementation Plan

> *To be filled in by `/codebase-draft`.*

---

## Implementation Checklist

- [ ] Backend: confirm whether `labels` are included in revision snapshot; add if not
- [ ] Backend (if needed): include label names in snapshot at revision write time
- [ ] Frontend: `computeDiff(prev: snapshot, next: snapshot)` utility — returns list of changed fields with old/new values
- [ ] Frontend: special handling for array fields (`compatible_platforms`, `labels`) — show added/removed items
- [ ] Frontend: `RevisionTimeline` — show collapsible diff per `edit`/`refetch` revision
- [ ] Frontend: `create` revision shows genesis values
- [ ] Frontend: refetch with no changes shows "no metadata changes"
- [ ] Frontend: upstream/repo URL changes surfaced prominently
- [ ] Tests for diff utility (edge cases: empty arrays, null → value, value → null)

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

- **#012 (Moderation):** Deactivate/reactivate revisions are already action-labelled — this task adds richer context to edit/refetch only.
- **#011 (User activity):** Per-user revision history could link back to this richer diff view.
