# ADR-P04: Determine visibility from GitHub API `private` field, not auth method

**Status:** Proposed
**Date:** 2026-04-21
**Context:** todo/001-private-repos-and-forks.md, Architecture Review AR-2

## Context

The plan's fallback chain (unauth -> PAT -> App token) assigns `visibility` based on which authentication method succeeded:

- Unauth success -> `visibility: public`
- PAT success -> `visibility: public`
- App token success -> `visibility: internal`

This is incorrect. A PAT can access private repos that the token holder has access to. If the unauthenticated call returns 404 but the PAT succeeds, the repo may actually be private -- yet it would be labelled `public`.

Conversely, a PAT might be configured purely for rate-limit headroom on public repos, in which case the repo truly is public and should be labelled as such.

The auth method used tells us nothing reliable about the repo's actual visibility.

## Decision

Determine `visibility` from the GitHub API response's `private` field (`data["private"]`), which is always present in the `GET /repos/{owner}/{repo}` response and accurately reflects the repository's visibility setting.

| `data["private"]` | `visibility` |
|---|---|
| `false` | `public` |
| `true` | `internal` (fetched via App or PAT with access) |

The `private` enum value in `VisibilityEnum` is reserved for manually submitted skills where no GitHub fetch was possible.

## Rationale

1. **Accuracy:** The `private` field is the source of truth from GitHub. It does not depend on which token was used.
2. **Simplicity:** One field check replaces tracking which auth step succeeded through the fallback chain.
3. **Forward-compatible:** If a fourth auth method is added (e.g., per-user OAuth from a future feature), the visibility logic does not change.

## Consequences

- FR-P2 must be reworded: visibility is no longer determined by "which fallback step succeeded" but by `data["private"]`.
- The `GitHubSnapshot` (or `SkillSnapshot`) should carry a `visibility` field populated from the API response, not from the auth context.
- The fallback chain's only job is to *get* the response; visibility is derived *from* the response.
