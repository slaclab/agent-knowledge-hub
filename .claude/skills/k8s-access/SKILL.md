# k8s-access — Agent Knowledge Hub cluster access

This skill must be read and applied before any kubectl, make, or cluster command in this project.

---

## KUBECONFIG

Always prefix kubectl and make commands with the correct KUBECONFIG for the target environment.
Never rely on the ambient `~/.kube/config`.

| Environment | KUBECONFIG |
|-------------|-----------|
| dev         | `/sdf/home/y/ytl/.kube/config.sage-dev` |
| stage       | (TBD — ask user) |
| prod        | (TBD — ask user) |

Example:
```bash
KUBECONFIG=/sdf/home/y/ytl/.kube/config.sage-dev kubectl get pods -n dev
```

---

## Overlay directories

```
kubernetes/overlays/dev/
kubernetes/overlays/stage/
kubernetes/overlays/prod/
```

Each overlay has its own `Makefile` with the `KUBECONFIG` default baked in, but it must still
be set explicitly from the shell so `ensure-context` passes.

---

## Make targets

### Applying to the cluster

The deployed overlays live in `ai-playground-deploy`, not in this repository; this repository's
`kubernetes/overlays/` are reference copies that nothing applies. A hub release applies only the
hub's own kustomization, `overlays/<env>/agent-knowledge-hub/`, with `kubectl diff -k` and
`kubectl apply -k` (deploy skill, Steps 4 and 5). The overlay-wide `make apply` below applies every
app in the environment.

**For an overlay-wide apply, use `make apply`, never `kubectl apply -k .` directly.**

`make apply` runs `secrets` first (pulls from Vault into `etc/.secrets/`), then applies, then
deletes the secrets files. Running `kubectl apply -k .` directly will fail because the
`secretGenerator` files won't exist.

```bash
KUBECONFIG=<path> make -C kubernetes/overlays/dev apply
```

### Other targets

```bash
# Diff what would change (safe, no write)
KUBECONFIG=<path> make -C kubernetes/overlays/dev diff

# Restart pods without re-applying manifests
KUBECONFIG=<path> make -C kubernetes/overlays/dev rollout-restart

# Run backend unit tests (from backend/ directory)
make test
# or equivalently:
(cd backend && make test)

# Build and push images: see the deploy skill, Step 2 (rootless podman on sdfiana008)
```

---

## Image build, push and release

Follow `.claude/skills/deploy/SKILL.md`. Images are built with rootless `podman` on `sdfiana008`,
from a `git archive` export on `/lscratch`, and prod is pinned to image digests with
`make pin-digests`. Claude may run the build; the Docker Hub login and `sudo` are never Claude's.

---

## Vault secrets

The hub's credentials are delivered by External Secrets Operator from Vault keys
`scs/sage/agent-knowledge-hub/{app,mongo}` (prod) and `scs/sage-dev/agent-knowledge-hub/{app,mongo}`
(dev), on the KV v2 mount `secret`; `ai-playground-deploy`'s ExternalSecret manifests are the record.
Rotating `INTERNAL_API_SECRET` is `docs/runbooks/internal-api-secret.md`.

**Critical:** use `vault kv patch -method=rw` to change one field. `vault kv put` replaces the
whole key, and the other fields (the GitHub App credentials) are lost. Never put a secret value in a
command's arguments: pass it on stdin with `FIELD=-`.

---

## Cluster topology

This is a **vcluster** running on SLAC S3DF. Key implications:

- **No CNI pods visible** — only CoreDNS is in `kube-system`. The host Cilium CNI handles
  networking but does not sync vcluster `NetworkPolicy` objects. Standard `NetworkPolicy`
  resources applied inside the vcluster are **not enforced** at the network level (verified
  2026-04-22 — `busybox` pod bypassed `deny-all-ingress` policy). Raise with SLAC to enable
  NetworkPolicy sync.
- **No `kube-system` access for CNI** — `cilium status`, `hubble observe`, etc. won't work.
- **Nodes** show as `sdfk8sc0XX`, role `c` (worker-only view).
- **Ingress** is `nginx` class, served by the host cluster's `ingress-nginx` namespace.

---

## Auth architecture

| Path | Headers | When |
|------|---------|------|
| Path 1 | `X-Vouch-Idp-Claims-Name` / `X-Vouch-User` | Browser → ingress → backend (VouchProxy-injected) |
| Path 2 | `X-Internal-Secret` + `X-Forwarded-User` | Next.js server → backend (internal proxy) |
| Dev   | `DEV_USER` env var | `AUTH_MODE=dev` only |

- VouchProxy rewrites `X-Vouch-Idp-Claims-Name` via `auth-response-headers` (proxy_set_header) — client-supplied values are overwritten for authenticated sessions.
- `INTERNAL_API_SECRET` uses `hmac.compare_digest` (constant-time). Identity check (`is not None`), not truthiness — empty string does not bypass.
- If `INTERNAL_API_SECRET` is not configured, Path 2 is disabled entirely and a warning is logged at startup.
- Fix 1 (ingress header stripping via `proxy-set-headers`) is **deferred** — `configuration-snippet` is blocked on the SLAC host cluster. See `docs/adr/adr-p05-ingress-header-stripping-deferred.md`.

---

## Ingress

- Host: `agent-knowledge-hub-dev.slac.stanford.edu`
- `/api/*` and `/health` route directly to backend (port 8000) — bypasses Next.js
- `/` routes to frontend (port 3000)
- VouchProxy: `https://vouch-dev.slac.stanford.edu/validate`

Unauthenticated requests to `/api/*` get a 302 redirect to the Vouch login page.

---

## Useful read-only kubectl commands

```bash
# Pod status
KUBECONFIG=<path> kubectl get pods -n dev -o wide

# Rollout status
KUBECONFIG=<path> kubectl rollout status deployment/agent-knowledge-hub-backend -n dev
KUBECONFIG=<path> kubectl rollout status deployment/agent-knowledge-hub-frontend -n dev

# Logs
KUBECONFIG=<path> kubectl logs -n dev deployment/agent-knowledge-hub-backend --tail=50
KUBECONFIG=<path> kubectl logs -n dev deployment/agent-knowledge-hub-frontend --tail=50

# Events (sorted by time)
KUBECONFIG=<path> kubectl get events -n dev --sort-by='.lastTimestamp' | tail -20

# NetworkPolicies
KUBECONFIG=<path> kubectl get networkpolicy -n dev

# Ingress
KUBECONFIG=<path> kubectl describe ingress agent-knowledge-hub -n dev

# Secrets (check keys present, not values)
KUBECONFIG=<path> kubectl get secret agent-knowledge-hub-secrets -n dev -o jsonpath='{.data}' | python3 -c "import json,sys; [print(k) for k in json.load(sys.stdin)]"
```

---

## What Claude must never do

- `kubectl apply -k .` on a whole overlay — use `make apply`; a hub release applies only `overlays/<env>/agent-knowledge-hub/`
- `sudo podman`, `podman login`, or any handling of the Docker Hub credential
- `vault kv put` with partial fields — use `vault kv patch`
- Run destructive kubectl commands (`delete`, `drain`, `cordon`) without explicit user confirmation
