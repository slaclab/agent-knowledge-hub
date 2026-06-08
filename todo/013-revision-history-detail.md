# TODO #013 — Rich Revision History: Diffs, Labels, and Upstream Links

> **Priority:** 🟡 P2 — Medium
> **Status:** ✅ Done
> **Branch:** main
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** 2026-06-03

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
| Refetch with no meaningful change | Shows "Re-fetched from GitHub" with no context | Shows "no changes detected" or lists what updated (stars, last_commit_at) |

---

## Goals

1. For `edit` and `refetch` revisions, compute a field-level diff between consecutive snapshots and display changed fields inline in the timeline
2. Show label adds/removes per revision (labels added to snapshot at write time)
3. Collapsible diff view — collapsed by default, expandable per revision
4. Highlight semantically meaningful changes: `name`, `description`, `compatible_platforms`, `version`, `license`, `repo_url`, `forked_from_url`, `visibility`, `labels`
5. Refetch revisions with no metadata changes show a "no changes detected" note
6. `create` revisions show genesis values (name, description, platforms, labels)

## Non-Goals

- Full side-by-side word-level text diff for long description fields — "changed" indicator is sufficient for v1
- Revision rollback / undo
- Diff for `deactivate` / `reactivate` (action is self-describing)
- README content diff (too noisy — "README updated" indicator only)

---

## User Stories

1. As a user, I want to see which fields changed in an edit revision, so that I can understand what was actually updated without reading changelog notes.
2. As a user, I want to see label adds/removes per revision, so that I can track community tagging changes over time.
3. As a user, I want the diff collapsed by default, so that the revision timeline sidebar isn't overwhelming.
4. As a user, I want to click "3 fields changed" to expand and see the actual changes, so that I can dig in when I care.
5. As a user, I want a "no changes detected" note on empty refetches, so that I know it ran but found nothing new.
6. As a user, I want the initial `create` revision to show the genesis values, so that I can see what the skill looked like when first submitted.
7. As a user, I want repo URL and fork URL changes surfaced prominently, so that I can detect if a skill quietly changed its upstream source.
8. As a contributor, I want platforms added/removed to show clearly in the diff, so that my platform changes are visible to users.

---

## Requirements

### Functional

- **FR-1:** `SkillRevision.snapshot` includes `labels: List[str]` (label names at snapshot time). The snapshot is written at revision record time, so labels are fetched from the label service and embedded.
- **FR-2:** `computeDiff(prev, next)` client-side utility returns a structured `FieldDiff[]` for display. Handles scalar, array, and null→value / value→null transitions.
- **FR-3:** Diffable semantic fields: `name`, `description`, `version`, `license`, `repo_url`, `forked_from_url`, `visibility`, `compatible_platforms`, `labels`.
- **FR-4:** Diffable metadata fields (shown for refetch only): `github_stars`, `last_commit_at`.
- **FR-5:** `edit`/`refetch` revision entries show a collapsed "N fields changed" badge; the badge has an explicit disclosure chevron and button styling to communicate clickability; click expands inline diff.
- **FR-6:** If `computeDiff` returns zero changes for a `refetch`, show "Re-fetched — no changes detected".
- **FR-7:** `create` revision shows genesis state (no prev snapshot; display initial values as "added").
- **FR-8:** Array fields (`compatible_platforms`, `labels`) show added items in green and removed items in red with strikethrough. Text labels ("added"/"removed") accompany colour for accessibility/colour-blindness — colour alone is not used.
- **FR-9:** `readme_html` / `readme_raw` / `skill_md_raw` are excluded from diff; a "README updated" indicator is shown if `readme_html` changed.
- **FR-10:** Long scalar fields (`description`) are truncated to 120 chars with "…" in the collapsed preview; full value shown on expand. Note: truncation is display-only — full value is available in the API response.
- **FR-11:** The revisions endpoints (`GET /{slug}/revisions`, `GET /{slug}/revisions/{n}`) gain `viewer: Optional[User] = Depends(get_optional_user)`. Internal skills without an authenticated viewer return 401. Snapshot fields `snapshotted_files`, `readme_html`, `readme_raw`, and `skill_md_raw` are stripped from `RevisionOut.snapshot` in the API response (these are irrelevant to diff and add 50–200KB of redundant transfer per revision).
- **FR-12:** When revision count exceeds 10, show only the 10 most recent revisions with a "Show all N revisions" toggle at the bottom of the timeline.

### Non-functional

- **NFR-1:** Diff computation is synchronous and < 5ms client-side for snapshots up to 50 fields.
- **NFR-2:** No new API endpoint or backend query required — snapshots already returned in `RevisionOut.snapshot`.
- **NFR-3:** Labels added to snapshot do not increase snapshot size by more than ~200 bytes (list of names only, not full LabelOut objects).

### Acceptance Criteria

- **AC-1:** Given an `edit` revision where `description` changed, the timeline shows "1 field changed" collapsed, expanding to show old → new description (truncated to 120 chars).
- **AC-2:** Given an `edit` revision where two labels were added and one removed, the label row shows labelA and labelB in green ("added") and labelC in red with strikethrough ("removed"), with text labels for accessibility.
- **AC-3:** Given a `refetch` with no changes to any diffable field, the timeline shows "Re-fetched — no changes detected".
- **AC-4:** Given a `create` revision, the timeline shows "Submitted" with genesis values for name, description, platforms, and labels.
- **AC-5:** Given an `edit` where `repo_url` changed, the diff row is visually distinct (e.g. warning icon or highlighted row) to signal a significant change.
- **AC-6:** Given a revision with `readme_html` changed but no other semantic fields changed, the timeline shows "README updated" with no expanded diff for the README content.
- **AC-7:** Existing snapshots (without `labels` field) are handled gracefully — labels row omitted, no crash.

---

## Architecture Decision Records

### ADR-U24: Labels in snapshot — embed at write time

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Labels are stored in the `SkillLabel` junction collection, not on the `Skill` document. The current `snapshot = skill.model_dump(mode="json")` therefore excludes labels. Two options: embed label names in the snapshot at write time, or derive label changes post-hoc from `SkillLabel.applied_at` timestamps.

#### Options

| Option | Pros | Cons |
|---|---|---|
| Embed `labels: List[str]` in snapshot at write time | Accurate point-in-time state; simple diff; no post-hoc reconstruction | One extra DB query at revision write time (fetch labels for skill) |
| Derive from SkillLabel timestamps post-hoc | No snapshot change | Approximate; requires joining two collections per revision; complex for bulk history |

#### Decision
**Embed `labels: List[str]` (names only) in the snapshot at revision write time.** The revision service fetches labels for the skill and adds them to the snapshot dict before persisting. This is accurate, simple to diff, and consistent with how all other fields are stored. The cost is one extra label query per write — negligible given writes are infrequent.

#### Consequences
- `revision_service.record()` gains a `labels: Optional[List[str]]` param (passed by `skill_service`)
- Old snapshots (pre-this-change) lack the `labels` key — handled gracefully by `computeDiff` (omit labels row if key absent in either snapshot)
- No migration required — missing key = no labels diff shown for legacy revisions

---

### ADR-U25: Diff computation — client-side, no new endpoint

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Field diffs could be computed server-side (new `GET /skills/{slug}/revisions/{n}/diff` endpoint) or client-side from the already-fetched `RevisionOut.snapshot` data.

#### Options

| Option | Pros | Cons |
|---|---|---|
| Server-side diff endpoint | Diff logic centralised; one source of truth | New endpoint + service logic; snapshot data already sent to client anyway |
| Client-side from existing snapshots | No new endpoint; snapshots already in frontend state; diff logic is trivial for flat dicts | Diff logic lives in frontend (acceptable — it's UI logic) |

#### Decision
**Client-side.** Snapshots are already included in `RevisionOut.snapshot` and sent to the browser. The diff is a flat dict comparison — no complex algorithm needed. Adding a server endpoint would duplicate data flow without benefit.

#### Consequences
- New `frontend/lib/revision-diff.ts` utility: `computeDiff(prev: Record<string, any>, next: Record<string, any>) => FieldDiff[]`
- `RevisionTimeline` component consumes diffs directly from snapshot pairs
- No new diff endpoint needed beyond adding labels to snapshot (ADR-U24)
- The API response strips `snapshotted_files`, `readme_html`, `readme_raw`, `skill_md_raw` from `RevisionOut.snapshot` before serialization. These are excluded from diff computation and add 50–200KB of redundant transfer per revision.

---

## Module Design

### Backend

| Module | Responsibility | Interface | Status | Testable |
|---|---|---|---|---|
| `services/revision.py` | Add `labels` param to `record()`; embed in snapshot dict; strip large fields (`snapshotted_files`, `readme_html`, `readme_raw`, `skill_md_raw`) from snapshot before persistence | `record(..., labels: list[str] \| None = None)` | Modify | Yes |
| `services/skill.py` | Pass current label names when calling `revision_service.record()` on create (after label application), edit, refetch, pin. Note: deactivate/reactivate do NOT call record() — 4 call sites only. For `create`: labels are applied AFTER the skill is first saved; re-fetch labels and pass to a second record() call or restructure so labels are applied before snapshot. | Call sites updated | Modify | Yes |
| `routers/skills.py` | Add `get_optional_user` to `list_revisions` and `get_revision`; return 401 for internal skills without viewer; strip large fields from `RevisionOut.snapshot` response | Modify | Integration |

### Frontend

| Module | Responsibility | Status | Testable |
|---|---|---|---|
| `frontend/lib/revision-diff.ts` | `computeDiff(prev, next) => FieldDiff[]` — handles scalar, array, null transitions | New | Yes (pure function) |
| `frontend/components/revision-timeline.tsx` | Extend to show collapsible `RevisionDiffBlock` per edit/refetch entry | Modify | — |
| `frontend/components/revision-diff-block.tsx` | Renders `FieldDiff[]` — collapsed badge + expanded field rows | New | — |
| `frontend/types/skill.ts` | Add `FieldDiff` type; ensure `SkillRevision.snapshot` typed as `Record<string, any>` | Modify | — |

---

## System Design

```
No new API calls. Data flow is unchanged:

  page.tsx
    └─ getRevisions(slug)  →  GET /api/skills/{slug}/revisions
         └─ RevisionOut[]  (each includes snapshot: dict with labels now embedded)

  RevisionTimeline
    └─ for each pair (revisions[n-1], revisions[n]):
         computeDiff(prev.snapshot, next.snapshot)
           └─ returns FieldDiff[]
         RevisionDiffBlock(diffs)
           └─ collapsed: "N fields changed"
           └─ expanded: field-by-field rows
```

**`FieldDiff` type:**
```typescript
type FieldDiff =
  | { field: string; type: "scalar"; old: string | number | null; new: string | number | null }
  | { field: string; type: "array"; added: string[]; removed: string[] }
  | { field: string; type: "readme_updated" }
```

**Array diff normalization:** `computeDiff` uses Set semantics for array fields — order is irrelevant (reorder alone produces no diff). `null` and `undefined` are normalised to `[]` before comparison. `null` vs `""` for scalar fields is treated as a change.

**Expanded diff layout:** Diff rows use a stacked layout (field name on one line, old/new values on the line below) to fit the ~300px sidebar column. Inline `old → new` is not used for scalar fields.

**Diffable fields config:**
```typescript
const SEMANTIC_FIELDS = [
  "name", "description", "version", "license",
  "repo_url", "forked_from_url", "visibility", "labels"
] as const;

const ARRAY_FIELDS = ["compatible_platforms", "labels"] as const;

const METADATA_FIELDS = ["github_stars", "last_commit_at"] as const; // refetch only

const SIGNIFICANT_FIELDS = ["repo_url", "forked_from_url"]; // shown with warning icon

// Excluded from diff entirely (stripped server-side and client-side):
const EXCLUDED_FIELDS = [
  "snapshotted_files", "readme_html", "readme_raw", "skill_md_raw", "file_manifest"
];
```

**Backend snapshot augmentation (revision service):**
```python
# services/revision.py
async def record(self, skill_id, revision_number, actor_id, action,
                 snapshot: dict, changelog_note=None, labels: list[str] | None = None):
    if labels is not None:
        snapshot = {**snapshot, "labels": labels}
    await SkillRevision(..., snapshot=snapshot).insert()
```

---

## Trade-offs

```
Choice: Labels in snapshot (vs post-hoc from SkillLabel timestamps)
  + Accurate point-in-time; simple diff; consistent with all other fields
  - One extra query at write time; old snapshots lack the key
  Decision: Embed at write time. Graceful fallback for legacy snapshots.

Choice: Client-side diff (vs server-side endpoint)
  + No new endpoint; snapshots already in browser; diff is trivial
  - Diff logic lives in frontend
  Decision: Client-side. This is UI logic, not business logic.

Choice: Truncate long scalars (vs full text diff)
  + Sidebar stays compact; full value available on expand
  - Loses word-level change visibility (e.g. one sentence changed in a long description)
  Decision: Truncate in v1. Word-level diff is a future enhancement if users ask for it.

Choice: Exclude readme_html from diff (vs show indicator)
  + Avoids noisy HTML blobs in the sidebar; README tab already shows current content
  - Users can't see what changed in the README
  Decision: "README updated" indicator only. README diffs belong on the README tab (future).
```

---

## Delivery Slices

**Slice 1 — Backend: labels in snapshot + auth gating + snapshot sanitization**
- `revision_service.record()` gains `labels` param; strips `snapshotted_files`, `readme_html`, `readme_raw`, `skill_md_raw` from snapshot before persistence
- `skill_service` passes current label names at each `record()` call — 4 call sites: create (after label application), edit, refetch, pin. Deactivate/reactivate do not call record().
- Create flow: label application must occur BEFORE `revision_service.record()` so labels are captured in the snapshot. Restructure `create()` and `_create_local()` accordingly.
- `routers/skills.py` list_revisions + get_revision: add `get_optional_user`; gate internal skills (return 401 if viewer is None); strip large fields from `RevisionOut.snapshot` response.
- Unit test: snapshot includes `labels` key and excludes large fields; graceful if labels `None`
- Integration test: GET revisions for internal skill without auth → 401

**Slice 2 — Frontend: diff utility + types**
- Prerequisite: verify Vitest (or Jest) is configured for the frontend (`package.json` test script, `vitest.config.ts`, TypeScript path resolution). Set up if missing.
- `frontend/lib/revision-diff.ts`: `computeDiff()` + `DIFFABLE_FIELDS` config + `EXCLUDED_FIELDS` list
- `frontend/types/skill.ts`: `FieldDiff` type (scalar `old`/`new` typed as `string | number | null`)
- Unit tests for `computeDiff`: scalar change, array add/remove, array reorder (no diff), null→value, value→null, null vs `[]` for array (no diff), no-change returns empty, missing labels key (legacy snapshot), excluded fields never appear in output

**Slice 3 — Frontend: enhanced RevisionTimeline**
- `frontend/components/revision-diff-block.tsx`: collapsed badge with chevron affordance + stacked expanded field rows; color-coded array diffs (green added / red strikethrough removed with text labels)
- `frontend/components/revision-timeline.tsx`: wire in diff blocks for `edit`/`refetch`; genesis display for `create`; "Re-fetched — no changes detected" for empty refetch; "README updated" indicator; 10-revision cap with "Show all N revisions" toggle

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Large snapshots contain `readme_html` (50KB+) — slow diff | Low | Medium | Exclude `readme_html`/`readme_raw`/`skill_md_raw` from `computeDiff` explicitly |
| Old snapshots missing `labels` key crash diff | Medium | Low | `computeDiff` checks key existence; omits labels row if absent |
| Label fetch at revision write time fails → revision not recorded | Low | High | Wrap label fetch in try/except; fall back to `labels=[]` rather than aborting the revision write |
| Snapshot `compatible_platforms` type inconsistency (list vs null) | Low | Low | Normalise to `[]` if null before diffing |

---

## Definition of Done

- [x] All acceptance criteria pass
- [x] `revision_service.record()` accepts and embeds `labels` param; strips large fields from snapshot
- [x] All 4 `skill_service` call sites pass current labels to `record()` (create after label application, edit, refetch, pin)
- [x] Create flow restructured: labels applied BEFORE `revision_service.record()`
- [x] Revisions endpoints auth-gated: internal skills return 401 for unauthenticated viewers
- [x] `RevisionOut.snapshot` strips `snapshotted_files`, `readme_html`, `readme_raw`, `skill_md_raw` from response
- [x] Unit tests: `computeDiff` covers scalar, array add/remove, array reorder (no diff), null→value, value→null, null vs [] (no diff), legacy snapshot (no labels key), excluded fields absent
- [x] Integration test: revision snapshot includes `labels`, excludes large fields
- [x] Integration test: GET revisions for internal skill without auth → 401
- [x] Frontend: `edit`/`refetch` revisions show collapsible diff with chevron affordance
- [x] Frontend: array diffs use color-coded items with text accessibility labels
- [x] Frontend: stacked diff layout (field name above values) for narrow sidebar
- [x] Frontend: empty refetch shows "Re-fetched — no changes detected"
- [x] Frontend: `create` revision shows genesis state
- [x] Frontend: `repo_url`/`forked_from_url` changes visually distinguished
- [x] Frontend: no crash on legacy snapshots (missing `labels` key)
- [x] Frontend: 10-revision cap with "Show all N revisions" toggle
- [x] CHANGELOG entry added (`### Rich revision history: field diffs and label tracking (#013)` under `## Unreleased`)
- [x] ADR-U24 written to `docs/adr/adr-u24-labels-in-snapshot.md`
- [x] ADR-U25 written to `docs/adr/adr-u25-client-side-diff.md`

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-03
**Rounds:** 3

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | YES | All 4 claims confirmed; flagged snapshot payload bloat (readme_html/snapshotted_files in revisions response) |
| codebase-arch-review | ✅ PASS | NO | Architecture sound; surfaced HIGH security issue (unauthenticated revisions endpoint leaks internal skill content) — resolved in plan |
| codebase-eng-review | ✅ PASS | YES | Critical label-timing bug in create flow fixed; array normalization added; 34-test test plan written |
| doc-review | ✅ PASS | YES | CHANGELOG + ADR filenames clarified; no other doc gaps |
| security-review | ✅ PASS | NO | Both HIGH issues resolved: auth gating (FR-11) + defense-in-depth snapshot sanitization at write + response layer |
| codebase-ux-review | ✅ PASS | NO | All 5 UX amendments verified: chevron affordance, color-coded diffs, stacked layout, 10-revision cap, corrected copy |

**Accepted warnings:** Snapshot payload size for pre-existing historical revisions (mitigated by response-time stripping in FR-11)
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research — Round 1 (PASS WITH WARNINGS)</summary>

## Claim Verdicts

| # | Claim | Verdict | Evidence | Source |
|---|-------|---------|----------|--------|
| 1 | snapshot = skill.model_dump(mode="json") and labels are NOT currently in snapshot | **CONFIRMED** | `revision_service.record(snapshot=skill.model_dump(mode="json"))` at create (L233), update (L359), refetch (L432), pin (L459). Labels live in separate `SkillLabel` junction collection. | `backend/app/services/skill.py`, `backend/app/models/label.py` |
| 2 | RevisionOut.snapshot is already returned to the frontend | **CONFIRMED** | `RevisionOut` schema at L170-178 includes `snapshot: dict`. Router at L380-390 passes `snapshot=r.snapshot`. Frontend type declares `snapshot: Record<string, unknown>`. | `backend/app/schemas/skill.py:170`, `backend/app/routers/skills.py:387` |
| 3 | No new API endpoint is needed | **CONFIRMED WITH WARNING** | Snapshots are sent but include `readme_html`, `readme_raw`, `skill_md_raw`, `snapshotted_files` — megabytes of redundant content for skills with many revisions. | `backend/app/routers/skills.py:369-390` |
| 4 | Label fetch at write time is the only extra DB query | **CONFIRMED** | `label_service.list_for_skill()` performs 2 queries internally (SkillLabel find + Label find). Negligible impact. | `backend/app/services/label.py:99-117` |

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-arch-review — Round 1 (PASS)</summary>

## Issues

- **HIGH | security** — `GET /api/skills/{slug}/revisions` has no auth dependency. Returns full snapshots including `snapshotted_files` (source code), `readme_html`, `readme_raw` to unauthenticated users. Bypasses visibility gating on main skill endpoint. → Resolved by FR-11.
- **MEDIUM | data-efficiency** — Snapshots contain 50–200KB of content irrelevant to diffing. → Resolved by snapshot sanitization in FR-11/ADR-U25.
- **MEDIUM | coupling** — Plan cited deactivate/reactivate as call sites but those actions don't exist in codebase. 4 call sites only. → Corrected in Slice 1.
- **LOW | type-safety** — FieldDiff scalar type too narrow for numeric fields (github_stars). → Widened to `string | number | null`.
- **LOW | edge-case** — Array diff doesn't define reorder semantics. → Set semantics added to spec.

## Status
PASS

</details>

<details>
<summary>codebase-eng-review — Round 2 (PASS)</summary>

## Issues

None blocking. All Round 1 critical/high issues resolved:
- Create-flow label timing fixed (labels passed after application, test B4)
- Array normalization: Set semantics, null→[] normalisation (FR-8, tests F7/F8)
- 34-test test plan written (B1-B8 backend, F1-F16 frontend unit, C1-C7 component, I1-I3 integration)

Observations (non-blocking): pin revision display undecided (acceptable — self-describing action label); frontend test infra prerequisite implicit (discoverable at dev time).

## Status
PASS

</details>

<details>
<summary>doc-review — Round 2 (PASS)</summary>

## Issues

None blocking. DoD correctly identifies CHANGELOG + ADR-U24/ADR-U25 as only needed doc updates. Conventions derivable from existing artifacts (CHANGELOG.md heading pattern, docs/adr/ naming). FastAPI auto-docs cover schema changes.

## Status
PASS

</details>

<details>
<summary>security-review — Round 3 (PASS)</summary>

## Issues

| # | Severity | Area | Status |
|---|----------|------|--------|
| 1 | HIGH | auth | RESOLVED — FR-11 adds `get_optional_user`, 401 for internal skills without viewer. In Module Design, Slice 1, DoD with integration test. |
| 2 | HIGH | data-exposure | RESOLVED — Defense-in-depth: write-time stripping in `revision_service.record()` + response-time stripping in `routers/skills.py`. All four fields named in FR-11, ADR-U25, System Design, Slice 1, DoD. |

Non-blocking: Risk Register not updated with new auth row (cosmetic); NFR-2 wording slightly misleading but technically accurate.

## Status
PASS

</details>

<details>
<summary>codebase-ux-review — Round 3 (PASS)</summary>

## Verification: All 5 Round 1 amendments present

| # | Amendment | Location | Status |
|---|-----------|----------|--------|
| 1 | Chevron affordance on collapsed badge | FR-5 | ✅ |
| 2 | Color-coded array diffs with text labels | FR-8 | ✅ |
| 3 | 10-revision cap with toggle | FR-12 | ✅ |
| 4 | "Re-fetched — no changes detected" copy | FR-6 | ✅ |
| 5 | Stacked diff layout | System Design | ✅ |

Consistently threaded through AC, Slices, DoD.

## Status
PASS

</details>

---

## Relationship to Other Tasks

- **#014 (Skill provenance tree):** Related but distinct. #013 is time-axis (what changed); #014 is space-axis (how skills relate). Tree nodes in #014 could eventually link to revision diffs from #013.
- **#012 (Moderation):** Deactivate/reactivate revisions are action-labelled — this task adds richer context to `edit`/`refetch` only.
- **#011 (User activity):** Per-user revision history on the profile page could link to these richer diff views.
