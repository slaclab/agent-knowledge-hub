# ADR-U04: Compound unique index strategy for (repo_url, skill_path)

**Status:** Accepted
**Date:** 2026-04-21
**Context:** todo/002-skill-registration-ux.md

## Context

The current `Skill` model has a unique index on `repo_url` alone (`Indexed(str, unique=True)`). The new feature allows multiple skills from the same repo at different paths, so uniqueness must be on the pair `(repo_url, skill_path)`.

## Decision

Replace the `repo_url` unique index with a compound unique index on `(repo_url, skill_path)`. Use an expand-contract migration pattern: add `skill_path` with a default of `"/"`, create the compound index, then drop the old single-field unique index.

## Rationale

1. **Expand-contract is safe:** All existing documents have `skill_path="/"` (the default), so the compound index will not violate uniqueness on existing data.
2. **No data migration required:** The default value covers all existing rows. No backfill script is needed.
3. **MongoDB handles this atomically:** `createIndex` on a small collection (< 10k docs expected) is non-blocking.

## Consequences

- The Beanie `Indexed(str, unique=True)` annotation on `repo_url` must be removed and replaced with a compound index in `Settings.indexes`.
- The `slug` field retains its own independent unique index (slugs are globally unique regardless of path).
- Application code must check for duplicate `(repo_url, skill_path)` pairs before insert, returning HTTP 409 with a link to the existing entry. Relying solely on the database unique index for user-facing error messages would produce a raw MongoDB `DuplicateKeyError` -- the application should catch this and translate it.

## Migration Sequence

1. Deploy code that writes `skill_path="/"` on all new/existing documents.
2. **Drop old `repo_url_1` single-field unique index first** (via explicit `drop_index("repo_url_1")` in startup lifespan before `init_beanie()` — Beanie does not auto-drop old indexes).
3. Create compound index `(repo_url, skill_path)` with `unique=True` (Beanie manages this declaratively on startup via `Settings.indexes`).

Steps 2-3 must happen in this order in a single deployment.
