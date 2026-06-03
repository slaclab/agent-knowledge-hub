# ADR-U16: File content serving strategy

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/028-skill-file-manifest.md

## Context

The Files tab inline viewer needs to fetch file content on demand. Two strategies were considered: serve live from GitHub, or pre-store all file content in the database alongside the manifest.

## Options

| Option | Pros | Cons |
|---|---|---|
| Live GitHub fetch per request | Always fresh; no extra DB storage | Rate limit exposure; latency; fails if token expired |
| Store all text content in `snapshotted_files` for GitHub skills | Zero-latency; works offline | Potentially large DB documents; ~100 KB/skill worst case |

## Decision

Live fetch via `GET /api/skills/{slug}/files/{path:path}` with a 5-minute TTL server-side cache keyed by `(slug, path, ref)`. Local skills already have content in `snapshotted_files` — the endpoint reads from there directly.

The 5-minute TTL (`_MARKETPLACE_TTL = 300 s`) is consistent with the existing marketplace manifest cache. Storing all file content for GitHub skills would add ~50–100 KB per skill document unnecessarily, while the live path with caching keeps first-view latency acceptable and subsequent views instant.

## Consequences

- File viewer adds one network round-trip on first view per file per 5-minute window.
- The in-memory cache is not shared across replicas (acceptable v1 trade-off).
- Must handle expired/missing GitHub token gracefully (HTTP 503 with message).
- Local skills are served from `snapshotted_files`; content is always available at zero latency.
