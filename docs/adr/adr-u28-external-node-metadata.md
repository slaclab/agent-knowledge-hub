# ADR-U28: External upstream nodes — best-effort GitHub metadata

**Status:** Accepted
**Date:** 2026-06-03
**Task:** #014 Skill Provenance Tree

## Context

`forked_from_url` may point to a GitHub repo not in the AKH catalog. To show meaningful node metadata (stars, last commit) for these external nodes, we'd need to fetch from GitHub.

## Options

| Option | Pros | Cons |
|---|---|---|
| Skip metadata for external nodes | Zero extra API calls; simple | External nodes show only URL, no comparison data |
| Fetch via existing `github_fetcher` | Shows stars/last_commit for external nodes; enables comparison | Extra GitHub API call per external node; rate limit pressure |

## Decision

**Fetch via existing `github_fetcher`, best-effort.** The fetcher is already used during scan and handles auth. External nodes are typically just one (the direct upstream), so the API cost is low. If the fetch fails (rate limit, private repo), the node renders with `null` metadata — no error.

## Consequences

- `provenance_service.py` calls `github_fetcher.fetch(repo_url)` wrapped in `try/except GitHubFetchError` — failures return `null` metadata, never propagate to caller
- Capped at 1 external fetch per request (immediate upstream only; deeper external ancestors render URL-only)
- These fetches count toward GitHub API rate limits — mitigated by 5-min endpoint cache
- SSRF risk is mitigated by `github_fetcher`'s existing URL validation against `github.com` regex and hardcoded `api.github.com` base URL
