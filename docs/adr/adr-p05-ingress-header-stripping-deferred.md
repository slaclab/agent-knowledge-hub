# ADR-P05: Ingress-level auth header stripping — deferred

**Status:** Accepted (deferral)
**Date:** 2026-04-22
**Context:** todo/008-auth-header-hardening.md, Board Review Round 1 (arch-review finding)

## Context

The original plan proposed stripping client-supplied `X-Vouch-*` headers at the nginx
ingress before they reach the backend, preventing external identity spoofing via Surface 1.
Two mechanisms were evaluated:

1. `nginx.ingress.kubernetes.io/proxy-set-headers` — referenced in the nginx-ingress docs as
   a way to set upstream proxy headers. However, this is a **global controller ConfigMap
   setting only**, not a per-ingress annotation. Applied per-ingress, it is silently ignored.
   Even if applied globally, the nginx template renders the strip directives **after**
   `auth-response-headers` injection, which would overwrite VouchProxy-validated values.

2. `nginx.ingress.kubernetes.io/configuration-snippet` — provides direct nginx config
   injection (e.g. `more_clear_input_headers`) and is the correct mechanism. **Blocked on
   the SLAC host cluster** (`allow-snippet-annotations: false`).

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| `proxy-set-headers` per-ingress annotation | Per-spec, no snippets needed | Does not exist as a per-ingress annotation — silently ignored |
| Global `proxy-set-headers` ConfigMap | Technically possible | Strip runs after VouchProxy inject in nginx template — defeats the purpose |
| `configuration-snippet` with `more_clear_input_headers` | Correct mechanism | Disabled on SLAC host cluster |
| `server-snippet` / `http-snippet` with `more_set_input_headers` | Correct mechanism | Also requires snippet annotations, which are blocked |
| Accept and defer | No cluster changes; Fix 2+3 provide defence-in-depth | Attack surface 1 partially unmitigated — residual risk accepted |

## Decision

Defer Fix 1. Ingress-level header stripping is not achievable with the current nginx-ingress
configuration on the SLAC host cluster.

Residual risk: An external client with a valid SLAC VouchProxy session sending
`X-Vouch-Idp-Claims-Name: <other-user>` to the `/api` ingress path may successfully
impersonate another authenticated user if VouchProxy does not overwrite the client-supplied
header before injecting its own value. This is:
- **Not** an unauthenticated bypass — the attacker must hold a valid SLAC SSO session
- **User-impersonates-user**, not external attacker
- **Likelihood: Low-Medium** — requires an attacker to be authenticated to SLAC SSO
- **Impact: Medium** — full backend API access as the impersonated user

## Future Mitigation Path

If any of the following become available on the cluster, Fix 1 can be revisited:

1. **Enable snippet annotations** (`allow-snippet-annotations: true` in the ingress controller
   ConfigMap) — allows `configuration-snippet` with `more_clear_input_headers`.
2. **Service mesh** (Istio/Linkerd) — header manipulation at the sidecar proxy level,
   independent of nginx-ingress constraints.
3. **VouchProxy configuration** — if VouchProxy can be configured to explicitly overwrite
   (not supplement) client-supplied headers, Surface 1 is mitigated at the auth layer.

## Consequences

- AC-1 acceptance criterion (external header spoofing via ingress) cannot be fully verified.
- The threat model documents this as an accepted risk.
- Fix 2 (NetworkPolicy) and Fix 3 (shared internal secret) close attack surfaces 2 and 3.
- This decision must be revisited if the cluster security posture changes.
