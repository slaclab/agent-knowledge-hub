# ADR-U01: New `/api/github-scan` endpoint vs. extending `/api/github-preview`

**Status:** Accepted
**Date:** 2026-04-21
**Context:** todo/002-skill-registration-ux.md

## Context

The existing `/api/github-preview` endpoint (implemented as a Next.js route handler at `frontend/app/api/github-preview/route.ts`) fetches lightweight repo metadata (name, description, stars, license, last_commit_at) from the GitHub API. It accepts only bare repo URLs (`https://github.com/owner/repo`).

The new directory-aware skill registration feature requires a heavier scan operation: parsing `tree/branch/path` URLs, fetching directory listings, downloading and parsing multiple files (skill.md, CLAUDE.md, README.md, package.json, pyproject.toml), extracting frontmatter, and returning a full `SkillSnapshot`. This is a fundamentally different contract.

## Decision

Create a new `GET /api/github-scan` endpoint on the **backend** (FastAPI) rather than extending the existing frontend-only `/api/github-preview`.

## Rationale

1. **Different contract:** Preview returns 5 scalar fields in ~200ms. Scan returns a full SkillSnapshot after 5-10 parallel GitHub API calls and file parsing, taking 1-3 seconds.
2. **Different failure modes:** Preview fails on one API call. Scan has partial failure (some files missing but others found), which requires richer error/warning semantics.
3. **Backend vs. frontend:** The scan includes Python-specific parsing (python-frontmatter, pyproject.toml TOML parsing) that belongs on the FastAPI backend, not in a Next.js route handler.
4. **The existing preview still has value:** The lightweight preview can remain for a quick "is this repo valid?" check before committing to a full scan.

## Consequences

- Two GitHub-facing endpoints exist: `/api/github-preview` (frontend, lightweight) and `/api/github-scan` (backend, heavyweight).
- The submit form should switch from `github-preview` to `github-scan` on blur. The old preview endpoint can be deprecated or kept as a fast validation check.
- The frontend needs a new Next.js proxy route at `frontend/app/api/github-scan/route.ts` to forward to the backend (following the existing proxy pattern).
