# ADR-U29: Flag upsert vs. append semantics

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/012-moderation-flags-and-admin-deactivation.md

## Context

`SkillFlag` has a unique index on `(skill_id, reporter_id)`. A user who previously flagged a skill (even if resolved) cannot insert a new record. Two options: (A) upsert — reset status/reason/note on the existing record; (B) lift the unique index and allow multiple records per user per skill.

## Decision

**Upsert (A).** One flag record per user per skill, ever. On re-flag: reset `status=active`, update `reason`/`note`/`created_at`. Increment `flag_count` only if the record was previously `resolved`.

The `find_one_and_update(upsert=True, return_document=False)` pattern returns the before-state, making it cheap to detect the resolved→active transition that warrants a count increment.

## Consequences

- Simple flag count arithmetic — no multi-record scan needed to compute active flags per user
- No multi-record history per user (acceptable — audit value of re-flag history is low)
- `SkillFlag` compound index **must** use `IndexModel(..., unique=True)` for the upsert guard to hold under concurrent inserts; plain list-of-tuples creates a non-unique index
