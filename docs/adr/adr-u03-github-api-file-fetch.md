# ADR-U03: GitHub API file fetch vs. sparse checkout or full clone

**Status:** Accepted
**Date:** 2026-04-21
**Context:** todo/002-skill-registration-ux.md

## Context

The scan and install features need to read files from a specific subdirectory of a GitHub repo. Three approaches were considered.

## Options

| Option | Pros | Cons |
|---|---|---|
| A) GitHub Contents API (`GET /repos/{o}/{r}/contents/{path}`) | No git required on server; works with any GitHub repo; parallelizable | Rate-limited (1 API call per file); base64-encoded content adds overhead |
| B) Sparse checkout (`git sparse-checkout`) | Efficient for large repos; local files available immediately | Requires git on the server; stateful (local clone directory); cleanup needed |
| C) Full clone + filter | Simple implementation | Wasteful for large monorepos; slow; disk-heavy |

## Decision

Option A: GitHub Contents API. Fetch directory listings and file contents via the REST API with parallel `asyncio.gather`.

## Rationale

1. **Stateless:** No local filesystem state needed on the backend. The backend remains a 12-factor stateless service.
2. **Parallelizable:** Individual file fetches can be done concurrently. A 10-file directory completes in ~500ms with parallel requests vs. ~3s sequential.
3. **Rate limits are manageable:** A single scan uses ~5-15 API calls. With a GitHub App token (5000/hr from todo/001), this supports ~300-1000 scans/hr -- more than sufficient.
4. **No git dependency:** The backend container does not need git installed.

## Consequences

- Each file fetch is a separate API call. Very large directories (100+ files) should only fetch recognized filenames, not all files.
- The discovery flow (`?discover=true`) uses `GET /repos/{o}/{r}/git/trees/{branch}?recursive=1` which returns the entire tree in one call (efficient), then scans each candidate directory (up to 10 concurrent).
- Base64 decoding is needed for file contents (the Contents API returns base64-encoded content).
