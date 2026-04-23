# ADR-P08: /cli path prefix for CLI direct backend access — browser uses /api via frontend

**Status:** Accepted (revised from separate-hostname approach)
**Date:** 2026-04-22
**Supersedes:** Original path-split ADR-P08, separate-hostname revision
**Related:** ADR-P09 (JWKS auto-fetch), ADR-P10 (remove Vouch Path 1)

---

## Context

Two prior approaches failed:

1. **Path-split on same hostname** (`/` → frontend, `/api` → backend): broke browser auth because
   browser `fetch("/api/me")` (from `AuthProvider` client-side) was routed directly to the backend,
   bypassing the Next.js proxy and its `X-Internal-Secret` injection.

2. **Separate hostname** (`agent-knowledge-hub-api-dev.slac.stanford.edu`): requires DNS
   registration and a separate TLS cert — coordination overhead with the SLAC platform team.

---

## Decision

Use a **`/cli` path prefix** on the same hostname for direct backend access (CLI tools):

- **`/` and `/api`** → `ingress-frontend` (Vouch gated) → Next.js frontend (port 3000)  
  All browser requests, including `fetch("/api/me")`, go through the Next.js proxy which injects
  `X-Internal-Secret`. Vouch injects user identity headers for browser sessions.

- **`/cli/...`** → `ingress-api` (no Vouch) → backend (port 8000)  
  nginx strips the `/cli` prefix via `rewrite-target` before forwarding. CLI tools call
  `https://<host>/cli/api/skills/<slug>/rate` etc. with `Authorization: Bearer <jwt>`.

---

## Consequences

- No new DNS entry or TLS cert needed — same hostname throughout
- Browser auth fully restored: `/api` still routes to frontend (Next.js proxy)
- CLI tools must use `/cli/api/...` as their base URL instead of `/api/...`
- `todo/007` skill must be updated to use `/cli` as the base path for write operations
- The `/cli` path is Vouch-free — unauthenticated requests reach the backend and get a 401 JSON
  response (not an SSO redirect), which is the correct behaviour for an API client
