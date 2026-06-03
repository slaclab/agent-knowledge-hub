# ADR-U17: Manifest depth — flat (top level only) in v1

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/028-skill-file-manifest.md

## Context

The GitHub Contents API returns one directory level at a time. A full recursive listing requires N extra API calls. The manifest covers the declared `skill_path` only.

## Options

| Option | Pros | Cons |
|---|---|---|
| Flat — top-level of `skill_path` only | Zero extra API calls; uses data already fetched during `scan()` | Files in `scripts/`, `config/`, etc. are invisible |
| Recursive — walk all subdirs | Complete picture | N extra API calls; rate limit pressure; added complexity |

## Decision

**Flat first** — populate `all_files` from the single Contents API call already made during `scan()`. No extra API calls are required. Files in subdirectories are omitted in v1; directory entries are shown as greyed-out rows with a tooltip.

Most well-structured plugins keep their primary files at the top level. `plugin.json` already describes subdirectories semantically (agent paths, scripts paths). A future iteration can add opt-in recursive traversal.

## Consequences

- Subdirectory contents are not visible in the manifest.
- Zero additional GitHub API calls at scan time.
- `manifest_depth: "flat"` is implicit (no flag needed in v1; add if recursive mode is added).
- Directory entries (`is_dir=True`) are stored in the manifest so the UI can indicate the subdirectory exists even though its contents are not indexed.
