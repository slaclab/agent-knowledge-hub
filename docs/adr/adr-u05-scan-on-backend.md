# ADR-U05: Scan endpoint on backend (FastAPI) vs. frontend (Next.js route handler)

**Status:** Accepted
**Date:** 2026-04-21
**Context:** todo/002-skill-registration-ux.md

## Context

The existing `/api/github-preview` endpoint is implemented as a Next.js API route handler (`frontend/app/api/github-preview/route.ts`) that calls the GitHub API directly. The new `/api/github-scan` endpoint requires:

- Python-specific parsing (python-frontmatter for YAML, tomllib for pyproject.toml)
- Multiple parallel HTTP calls to the GitHub API
- Complex metadata extraction logic with priority chains
- 60-second caching

The plan places the `GitHubScanner` and `MetadataExtractor` on the backend, but the route handler in the Modules section says `frontend/app/api/github-scan/route.ts`.

## Decision

The scan logic (GitHubScanner, MetadataExtractor) lives on the **FastAPI backend**. The frontend has a thin proxy route handler at `frontend/app/api/github-scan/route.ts` that forwards to the backend -- following the same pattern as `frontend/app/api/skills/route.ts`.

## Rationale

1. **Language fit:** Frontmatter parsing (`python-frontmatter`) and TOML parsing (`tomllib`) are Python libraries. Reimplementing in TypeScript would duplicate effort and diverge.
2. **Consistency:** All business logic and GitHub interaction for skill CRUD is already on the backend. Adding scan logic there keeps a single source of truth.
3. **Auth forwarding:** The proxy pattern is already established. The scan endpoint will need auth for rate-limit tracking (per-user cache).

## Consequences

- The frontend `route.ts` for github-scan is a ~15-line proxy (same as `frontend/app/api/skills/route.ts`).
- The backend gets a new router or extends the existing skills router with `GET /api/github-scan`.
- Both the old `github-preview` (frontend-direct) and new `github-scan` (backend-proxied) patterns coexist. Consider deprecating `github-preview` once the scan endpoint is stable.
