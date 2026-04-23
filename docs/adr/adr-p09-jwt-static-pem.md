# ADR-P09: JWKS auto-fetch for JWT public key

**Status:** Accepted (supersedes original static-PEM decision)
**Date:** 2026-04-22
**Supersedes:** Original ADR-P09 (static PEM in config)
**Related:** ADR-P08 (split ingress)

---

## Context

RS256 JWT validation requires the issuer's public key. Two common approaches exist:

1. Configure the PEM public key as an env var / k8s secret (static).
2. Fetch from JWKS endpoint (`<issuer>/.well-known/jwks.json` / `<issuer>/keys`) on first use and cache.

The original decision (static PEM) was made for simplicity, but was reversed for two reasons:

1. **SLAC Dex rotates its signing key.** A static PEM goes stale silently — every CLI auth returns 401 until someone notices and manually updates the k8s secret. That's worse than a network call.
2. **`PyJWT.PyJWKClient` is one line.** It fetches keys on first use, caches them in memory, and automatically re-fetches when it encounters a `kid` it doesn't recognise (i.e. after a Dex key rotation). Zero manual intervention.

---

## Decision

Use `PyJWKClient` with `cache_keys=True` pointed at `settings.jwt_jwks_uri`. The client is a
module-level singleton in `auth.py`, lazy-initialised on the first Bearer request.

```python
_jwks_client: PyJWKClient | None = None

def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.jwt_jwks_uri, cache_keys=True)
    return _jwks_client
```

`JWT_JWKS_URI` is configured per environment in the kustomization ConfigMap:
- dev: `https://dex-dev.slac.stanford.edu/keys`
- prod/stage: `https://dex.slac.stanford.edu/keys`

---

## Consequences

- **No secret to manage** — `JWT_PUBLIC_KEY` is removed entirely; no Vault entry, no rotation runbook needed.
- **Automatic key rotation** — when Dex rotates its signing key, the new `kid` triggers a re-fetch on the next Bearer request. No pod restart required.
- **Network dependency at first request** — if Dex is unreachable, Bearer auth returns 401. Acceptable: Dex outage also blocks `s3df login`, so users would have no valid tokens to present anyway.
- **In-process cache** — keys survive for the pod's lifetime unless a new `kid` triggers re-fetch. Pod restart resets the cache (re-fetches on next request).
- `jwt_public_key` config field and `_strip_jwt_public_key` validator removed from `config.py`.
- `docs/runbooks/jwt-public-key-rotation.md` is superseded — no manual rotation needed.
