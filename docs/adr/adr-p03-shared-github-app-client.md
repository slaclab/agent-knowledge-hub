# ADR-P03: Shared GitHubAppClient between GitHubFetcher and GitHubScanner

**Status:** Accepted
**Date:** 2026-04-21
**Feature:** #001 — Private/Internal GitHub Repos

## Context

Both `GitHubFetcher` (submission/refetch) and `GitHubScanner` (#002 scan endpoint) need to make
authenticated GitHub API calls using the GitHub App installation token. Two options for sharing:

## Decision

Single module-level `GitHubAppClient` singleton in `backend/app/services/github_app.py`, imported
by both `GitHubFetcher` and `GitHubScanner`.

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| **Shared singleton `GitHubAppClient`** ✓ | One token generated, one cache, consistent fallback | Slight coupling between services |
| Independent token per class | Fully decoupled | Double token requests, two caches to invalidate |

## Consequences

- Installation token generated once and cached (TTL from `expires_at` minus 60s safety margin)
- `asyncio.Lock` prevents thundering-herd on concurrent token refresh
- Existing pattern (`github_fetcher = GitHubFetcher()`) is already module-level singleton — consistent
- Tests mock at the HTTP level (respx) so the singleton pattern doesn't block unit testing
