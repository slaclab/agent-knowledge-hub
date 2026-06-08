# ADR-U24: Labels in snapshot — embed at write time

**Status:** Accepted
**Date:** 2026-06-03
**Task:** #013 Rich Revision History

## Context

Labels are stored in the `SkillLabel` junction collection, not on the `Skill` document. The current `snapshot = skill.model_dump(mode="json")` therefore excludes labels. Two options: embed label names in the snapshot at write time, or derive label changes post-hoc from `SkillLabel.applied_at` timestamps.

## Options

| Option | Pros | Cons |
|---|---|---|
| Embed `labels: List[str]` in snapshot at write time | Accurate point-in-time state; simple diff; no post-hoc reconstruction | One extra DB query at revision write time (fetch labels for skill) |
| Derive from SkillLabel timestamps post-hoc | No snapshot change | Approximate; requires joining two collections per revision; complex for bulk history |

## Decision

**Embed `labels: List[str]` (names only) in the snapshot at revision write time.**

The revision service fetches labels for the skill and adds them to the snapshot dict before persisting. This is accurate, simple to diff, and consistent with how all other fields are stored. The cost is one extra label query per write — negligible given writes are infrequent.

For the `create` flow, labels are applied **before** `revision_service.record()` is called so the genesis snapshot is accurate.

## Consequences

- `revision_service.record()` gains a `labels: Optional[List[str]]` param
- `skill_service` passes current label names at each of the 4 call sites (create, edit, refetch, pin)
- Old snapshots (pre-this-change) lack the `labels` key — handled gracefully by `computeDiff` (omits labels row if key absent in either snapshot)
- No migration required — missing key = no labels diff shown for legacy revisions
