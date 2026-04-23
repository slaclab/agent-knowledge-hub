# ADR-P10: Remove Path 1 (VouchProxy headers) — two-path auth model

**Status:** Accepted
**Date:** 2026-04-22
**Supersedes:** Original `get_current_user` Path 1 (VouchProxy headers)
**Related:** ADR-P07 (remove bare X-Forwarded-User), ADR-P08 (split ingress)

---

## Context

The original `get_current_user` had three auth paths:

- **Path 1:** `X-Vouch-Idp-Claims-Name` / `X-Vouch-User` headers injected by VouchProxy
- **Path 2:** `X-Internal-Secret` — Next.js server-side proxy
- **Path 3:** `Authorization: Bearer <JWT>` — CLI tools (being added in todo/016)

After the ingress split (ADR-P08), the API ingress has no Vouch gate. This means any external
client can forge `X-Vouch-Idp-Claims-Name` on the Vouch-free API ingress — a header spoofing
attack.

A frontend audit confirmed that all 7 browser write operations
(`rate`, `create`, `update`, `delete`, `label` × 2, `refetch`) route through the Next.js proxy
route handlers at `frontend/app/api/*/route.ts`, which authenticate to the backend via
`X-Internal-Secret` (Path 2). **Path 1 is never the active auth path for any browser write.**

VouchProxy also strips `Authorization: Bearer` headers, making it impossible to keep Path 1
active on an ingress that also needs to pass Bearer tokens through (Path 3).

---

## Decision

Remove Path 1 from `get_current_user`. The two remaining paths are:

- **Path 2:** `X-Internal-Secret` — Next.js server-side proxy (browser writes)
- **Path 3:** `Authorization: Bearer <JWT>` — CLI tools (new in todo/016)

---

## Consequences

- Vouch header spoofing is impossible — no code trusts `X-Vouch-Idp-Claims-Name`.
- No nginx `configuration-snippet` annotation workarounds needed for `ingress-api`.
- Browser read operations are unaffected (unauthenticated reads still work).
- Browser write operations are unaffected (already using Path 2 exclusively).
- Tests for Path 1 updated to verify 401 (not 200) to prevent regression.
- `auth_mode` in ConfigMap can remain `vouchproxy` — it only controls the dev bypass; Path 1
  code no longer exists.
