# ADR-P07: Remove bare `X-Forwarded-User` as a standalone trust path

**Status:** Accepted
**Date:** 2026-04-22
**Context:** todo/008-auth-header-hardening.md

## Context

The backend's `auth.py` originally accepted `X-Forwarded-User` as a standalone fallback
identity header — if neither `X-Vouch-Idp-Claims-Name` nor `X-Vouch-User` were present,
the backend would trust whatever value `X-Forwarded-User` contained.

`X-Forwarded-User` is a standard reverse-proxy header that any pod in the cluster (or any
external client who can reach the ingress) can set to an arbitrary value. Accepting it
unconditionally is equivalent to having no authentication.

## Decision

Remove the bare `X-Forwarded-User` fallback. Identity is accepted only from:

1. `X-Vouch-Idp-Claims-Name` / `X-Vouch-User` — VouchProxy-injected, ingress path (Path 1)
2. `X-Forwarded-User` **gated by a valid `X-Internal-Secret`** — Next.js proxy path (Path 2)
3. `DEV_USER` env var when `AUTH_MODE=dev` — local development only

The removal is applied in the **contract phase** of the expand-contract rollout:
- Expand: add Path 2 with secret, keep bare fallback active
- Migrate: deploy frontend with `X-Internal-Secret`
- Contract: remove bare fallback after frontend rollout confirms all routes send the secret

## Consequences

- Any direct caller relying on bare `X-Forwarded-User` will receive 401. This is the
  intended behaviour — that path should never have been trusted.
- The expand phase ensures zero downtime during the rollout.
- Steps 3 (contract) and 4 (NetworkPolicy) must be deployed in the same release window —
  deploying contract without NetworkPolicy leaves Path 1 (Vouch headers) as the sole
  intra-cluster vector with no network barrier.

## Known limitation — vcluster NetworkPolicy enforcement

Verified 2026-04-22: the dev environment runs inside a vcluster. A `busybox` pod with no
matching labels was able to reach the backend on port 8000 after both `backend-deny-all-ingress`
and `backend-allow-frontend-and-ingress` NetworkPolicies were applied. This indicates the
host cluster CNI (Cilium on SLAC S3DF) is not syncing vcluster NetworkPolicy objects to the
host network layer.

The NetworkPolicy manifests are correct and are retained — if SLAC enables vcluster NetworkPolicy
sync, enforcement will take effect without any further changes. Until then, intra-cluster
isolation relies solely on the `X-Internal-Secret` application-layer check (Path 2).

Action required: raise with SLAC whether `networkPolicy` syncing can be enabled for this vcluster.
