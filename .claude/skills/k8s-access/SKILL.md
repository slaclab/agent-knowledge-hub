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

**Always use `make apply`, never `kubectl apply -k .` directly.**

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

# Build images (requires sudo podman, run by user not Claude)
make -C kubernetes/overlays/dev docker-build

# Push images (requires registry auth, run by user not Claude)
make -C kubernetes/overlays/dev docker-push
```

---

## Image build and push — HUMAN ONLY

**Claude must never run `docker-build` or `docker-push`.** These require:
- `sudo podman` (privileged, interactive)
- Registry credentials for `docker.io/slaclab`

When a new image is needed, ask the user to run:
```bash
make -C kubernetes/overlays/dev docker-build
make -C kubernetes/overlays/dev docker-push
```

The `TAG` is derived from `git describe --tags --exact-match` — so the git tag must exist on
the HEAD commit before building. Claude's role: create and move the tag, bump image tags in
deployment YAMLs, commit — then hand off to the user to build and push.

### Release workflow
1. Claude: `git tag vX.Y.Z` on the right commit
2. Claude: `sed -i 's|:old|:new|g'` all six deployment YAMLs (dev/stage/prod × backend/frontend)
3. Claude: commit the YAML changes, move the tag to the new commit with `git tag -f vX.Y.Z`
4. User: `make -C kubernetes/overlays/dev docker-build && make -C kubernetes/overlays/dev docker-push`
5. Claude: `KUBECONFIG=<path> make -C kubernetes/overlays/dev apply` + watch rollout

---

## Vault secrets

Vault path for app secrets (dev): `secret/tid/agent-knowledge-hub-dev/app`

Fields: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `INTERNAL_API_SECRET`

**Critical:** use `vault kv patch` to add or update a single field without wiping others.
`vault kv put` replaces the entire secret — all other fields are lost.

```bash
# CORRECT — add/update one field
vault kv patch secret/tid/agent-knowledge-hub-dev/app INTERNAL_API_SECRET=$(openssl rand -hex 32)

# WRONG — deletes GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY
vault kv put secret/tid/agent-knowledge-hub-dev/app INTERNAL_API_SECRET=...
```

To recover from an accidental `vault kv put`:
```bash
vault kv metadata get secret/tid/agent-knowledge-hub-dev/app   # list versions
vault kv get -version=N secret/tid/agent-knowledge-hub-dev/app # read old version
vault kv put secret/tid/agent-knowledge-hub-dev/app FIELD1=... FIELD2=... FIELD3=...
```

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

- `kubectl apply -k .` — always use `make apply`
- `docker-build` / `docker-push` — user only
- `vault kv put` with partial fields — use `vault kv patch`
- Run destructive kubectl commands (`delete`, `drain`, `cordon`) without explicit user confirmation
