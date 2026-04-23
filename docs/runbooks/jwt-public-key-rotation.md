# Runbook: JWT Key Rotation

> **This runbook is superseded.** The backend now uses `PyJWKClient` (JWKS auto-fetch) rather
> than a static PEM key. Key rotation is handled automatically — when SLAC Dex rotates its
> signing key, the backend detects the new `kid` on the next Bearer JWT request and re-fetches
> the JWKS endpoint automatically. No manual intervention is required.
>
> See ADR-P09 for the decision record.

---

## What happens during a Dex key rotation

1. Dex begins signing new tokens with a new key (new `kid` in the JWT header).
2. On the first Bearer request with a new-`kid` token, `PyJWKClient` encounters an unknown `kid`
   and automatically re-fetches `JWT_JWKS_URI` (e.g. `https://dex-dev.slac.stanford.edu/keys`).
3. The new key is cached in memory. All subsequent requests use the cached key.
4. Tokens signed with the old key continue to work until they expire (if Dex keeps the old key in
   its JWKS during the rotation window — standard practice).

**No pod restart or Vault update is required.**

---

## If Bearer JWT auth stops working after a Dex change

1. Check the backend logs for JWKS fetch errors:
   ```bash
   kubectl logs deployment/agent-knowledge-hub-backend -n <namespace> | grep -i jwks
   ```
2. Verify the JWKS endpoint is reachable from the pod:
   ```bash
   kubectl exec deployment/agent-knowledge-hub-backend -n <namespace> -- \
     curl -s https://dex-dev.slac.stanford.edu/keys | python3 -m json.tool | head -20
   ```
3. If the endpoint changed, update `JWT_JWKS_URI` in the kustomization ConfigMap and redeploy.

---

## Configuring JWT_JWKS_URI per environment

The JWKS URI is set in each overlay's `kustomization.yaml` `configMapGenerator`:

| Overlay | `JWT_JWKS_URI` |
|---------|----------------|
| dev | `https://dex-dev.slac.stanford.edu/keys` |
| stage | `https://dex.slac.stanford.edu/keys` |
| prod | `https://dex.slac.stanford.edu/keys` |

If the Dex endpoint URL changes, update the relevant overlay and redeploy.
