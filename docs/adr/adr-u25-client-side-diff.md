# ADR-U25: Diff computation — client-side, no new endpoint

**Status:** Accepted
**Date:** 2026-06-03
**Task:** #013 Rich Revision History

## Context

Field diffs could be computed server-side (new `GET /skills/{slug}/revisions/{n}/diff` endpoint) or client-side from the already-fetched `RevisionOut.snapshot` data.

## Options

| Option | Pros | Cons |
|---|---|---|
| Server-side diff endpoint | Diff logic centralised; one source of truth | New endpoint + service logic; snapshot data already sent to client anyway |
| Client-side from existing snapshots | No new endpoint; snapshots already in frontend state; diff logic is trivial for flat dicts | Diff logic lives in frontend (acceptable — it's UI logic) |

## Decision

**Client-side.** Snapshots are already included in `RevisionOut.snapshot` and sent to the browser. The diff is a flat dict comparison — no complex algorithm needed. Adding a server endpoint would duplicate data flow without benefit.

## Consequences

- New `frontend/lib/revision-diff.ts` utility: `computeDiff(prev, next) => FieldDiff[]`
- `RevisionTimeline` component consumes diffs directly from snapshot pairs
- No new diff endpoint needed beyond adding labels to snapshot (ADR-U24)
- The API response strips `snapshotted_files`, `readme_html`, `readme_raw`, `skill_md_raw` from `RevisionOut.snapshot` before serialization (both at write time and at response time for defense-in-depth)
