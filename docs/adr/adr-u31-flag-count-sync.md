# ADR-U31: Flag count sync strategy — denormalized `$inc` with hard-reset on deactivation

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/012-moderation-flags-and-admin-deactivation.md

## Context

`flag_count` is denormalized on `Skill`. Options: (A) keep denormalized, sync via `$inc` on flag create/resolve; (B) remove denormalized count and compute live from `SkillFlag.count()` on every skill fetch; (C) scheduled reconciliation job.

## Decision

**Keep denormalized `$inc` approach (A).** Live count (B) adds a query per skill fetch on list pages. Reconciliation (C) adds operational complexity. The `±1` eventual consistency window is acceptable.

### All `flag_count` mutation points

| Event | Operation |
|---|---|
| `create_or_update()` — resolved→active or new insert | `$inc {flag_count: +1}` |
| `retract()` | `$inc {flag_count: -1}` gated on `{flag_count: {$gt: 0}}` — floor at 0, no negative count under races |
| `resolve_all_for_skill()` (called on deactivation) | `$set {flag_count: 0}` — hard reset, not `$inc -(N)`. `$inc` is not idempotent here; computing `count_resolved` between query and update is a TOCTOU window; `$set 0` is correct when all active flags have been cleared |

## Consequences

- Occasional `±1` stale count if a request crashes between flag insert and `$inc` — acceptable
- `flag_count` is guaranteed 0 after admin deactivation (hard reset, not drift)
- A periodic reconciliation script can be added later if drift becomes noticeable
