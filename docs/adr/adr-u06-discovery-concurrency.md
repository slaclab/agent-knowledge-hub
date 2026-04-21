# ADR-U06: Discovery concurrency limit and rate-limit budget

**Status:** Accepted
**Date:** 2026-04-21
**Context:** todo/002-skill-registration-ux.md

## Context

The `?discover=true` mode recursively walks a repo tree and scans each candidate directory (any directory containing `skill.md` or `CLAUDE.md`). Each directory scan makes 3-5 GitHub API calls. A monorepo could contain 10-50 skill directories.

With unauthenticated GitHub API access (60 req/hr), a single discovery of a 10-skill repo would consume 30-50 requests -- more than half the hourly budget. With an App token (5000 req/hr), this is manageable but still needs bounds.

## Decision

1. Cap concurrent directory scans at 20 (asyncio.Semaphore) — updated from initial 10 to align with FR-U12a.
2. Cap total discoverable directories at 50 per discovery request.
3. Require a GitHub App token (from todo/001) for the discovery endpoint; return 503 if no token is configured.
4. Include `X-RateLimit-Remaining` from GitHub responses in the scan response headers so the frontend can warn users.

## Rationale

- 20 concurrent scans x 5 API calls each = 100 in-flight requests maximum. This stays well within httpx connection pool defaults and avoids GitHub secondary rate limits (which trigger on burst concurrency, not just hourly totals).
- 50 directories is a reasonable upper bound. Repos with more than 50 skill directories are unlikely; if encountered, the user can scan individual paths.
- Without an App token, discovery is impractical (60 req/hr is consumed by a single discovery). Failing fast with a clear error is better than silently degrading.

## Consequences

- The `GET /api/github-scan?discover=true` endpoint checks for `settings.github_token` and returns 503 with a descriptive message if not configured.
- The response includes `rate_limit_remaining` so the frontend can display a warning when budget is low.
- Individual scans (without `?discover=true`) remain functional without a token, as they use only 3-5 API calls.
