# ADR-P02: Visibility Enum over is_private Bool

**Status:** Accepted
**Date:** 2026-04-21
**Feature:** #001 — Private/Internal GitHub Repos

## Context

Skills need a field indicating whether their GitHub repo is publicly accessible, accessible only via
SLAC GitHub Enterprise (slaclab org), or manually submitted without any GitHub fetch.

## Decision

Use a three-value enum `public | internal | private` instead of a boolean `is_private`.

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| `is_private: bool` | Simple | Can't distinguish "slaclab internal" from "truly private" |
| **`visibility: enum` (public/internal/private)** ✓ | Correct badge display and fetch strategy per state | Slightly more complex |

## Consequences

- `public`: unauthenticated or PAT fetch succeeded; repo is publicly accessible
- `internal`: GitHub App token was required; repo is private but within slaclab org
- `private`: manually submitted; no GitHub fetch possible (forward-compat, no v1 write path)
- Visibility is determined by `data["private"]` from the GitHub API response (see ADR-P04)
