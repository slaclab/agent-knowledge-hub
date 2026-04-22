# ADR-P06: Shared HMAC secret over mTLS for Next.js → backend trust

**Status:** Accepted
**Date:** 2026-04-22
**Context:** todo/008-auth-header-hardening.md

## Context

The Next.js frontend acts as a proxy: it receives authenticated browser requests via VouchProxy,
then forwards them to the backend with auth headers. The backend currently cannot distinguish
a legitimate Next.js call from a spoofed pod-to-pod call with fabricated headers.

A trust mechanism is needed for the Next.js → backend leg.

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| Shared secret (`X-Internal-Secret` header) | Simple; no cert management; works with existing HTTP; secret stored in Vault | Requires manual rotation; compromised frontend pod = compromised secret |
| mTLS between frontend and backend | Cryptographically strong; no shared state; no manual rotation | Requires cert-manager or service mesh; significant operational overhead |
| Network isolation only (Fix 2, NetworkPolicy) | No app changes | Only guards against external callers; a compromised frontend pod still has full backend access |

## Decision

Shared secret (`X-Internal-Secret`) + NetworkPolicy (Fix 2).

- The secret is generated with `openssl rand -hex 32` at deploy time, stored in Vault, and
  never committed to git.
- The backend verifies it using `hmac.compare_digest` (constant-time comparison to prevent
  timing attacks).
- The backend uses `if settings.internal_api_secret is not None:` (identity check, not
  truthiness) to prevent empty-string bypass.
- A pydantic `@field_validator` strips trailing whitespace/newlines from Vault-injected values
  and normalises empty strings to `None`.
- If `INTERNAL_API_SECRET` is not configured, the Next.js proxy auth path is disabled entirely
  (safe default).

mTLS is deferred to a future cluster-wide hardening effort.

## Consequences

- `INTERNAL_API_SECRET` must be added to Vault for dev, stage, and prod.
- Rotation requires a coordinated redeploy of backend then frontend (see rotation runbook).
- If the frontend pod is compromised, the attacker holds the secret — accepted risk at current
  threat model.
- Cost: secret rotation adds ~5 minutes of operational work per environment.
