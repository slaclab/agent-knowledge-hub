# /deploy — Agent Knowledge Hub release & deploy

Invoke this skill when the user asks to deploy, release, build images, update manifests, or run
a backfill. Read and apply the full workflow below.

---

## Environment reference

| Env  | KUBECONFIG                                  | Namespace | Overlay path (in ai-playground-deploy)                        |
|------|---------------------------------------------|-----------|---------------------------------------------------------------|
| dev  | `~/.kube/config.sage-dev`                   | `dev`     | `kubernetes/overlays/dev/agent-knowledge-hub/`                |
| prod | `~/.kube/config.sage`                       | `prod`    | `kubernetes/overlays/prod/agent-knowledge-hub/`               |

Repos:
- **App code**: `/sdf/home/y/ytl/k8s/agent-knowledge-hub/` (this repo)
- **Manifests**: `/sdf/home/y/ytl/k8s/ai-playground-deploy/` (separate git repo)

Dev's deployments run `:latest` with `imagePullPolicy: Always`, so a dev release is a restart. Prod's
deployments pin a version tag.

Image names:
- `slaclab/agent-knowledge-hub-backend:<version>`
- `slaclab/agent-knowledge-hub-frontend:<version>`

---

## Full release cycle

### Step 1 — Bump the version

Set `X.Y.Z` in `backend/pyproject.toml` (`version = "X.Y.Z"`), in `frontend/package.json` and the two
root `version` fields of `frontend/package-lock.json`, and in the image tags of this repo's
`kubernetes/overlays/{dev,prod,stage}/*-deployment.yaml`. Rename `## Unreleased` in `CHANGELOG.md`
to `## X.Y.Z — <date>`. Commit in the app repo:
```bash
git commit -m "chore: bump version to X.Y.Z"
```

Never reuse a tag that prod already runs: the build pushes the tag again with different contents.

### Step 2 — Update the prod manifests

Edit the two prod deployment files in the **ai-playground-deploy** repo. Dev's files stay at
`:latest`.

```
kubernetes/overlays/prod/agent-knowledge-hub/backend-deployment.yaml
kubernetes/overlays/prod/agent-knowledge-hub/frontend-deployment.yaml
```

Change `image: slaclab/agent-knowledge-hub-{backend,frontend}:OLD` → `:X.Y.Z` in both, then commit
in that repo:
```bash
git -C /sdf/home/y/ytl/k8s/ai-playground-deploy add kubernetes/overlays/prod/agent-knowledge-hub/backend-deployment.yaml kubernetes/overlays/prod/agent-knowledge-hub/frontend-deployment.yaml
git -C /sdf/home/y/ytl/k8s/ai-playground-deploy commit -m "chore: bump agent-knowledge-hub prod to X.Y.Z"
```

### Step 3 — Build and push images

Build with rootless `podman` on the host `sdfiana008`, over `ssh`, never with `sudo`. Keep podman's
storage, the build context and its temporary files on `/lscratch`, not on the NFS home: export the
release commit with `git archive` and build from the export.

Check first that podman's storage is on `/lscratch` and that it is logged in to Docker Hub. The login
is the user's; never run `podman login` or handle a Docker Hub credential.
```bash
ssh sdfiana008 'podman info --format "{{.Store.GraphRoot}}"; podman login --get-login docker.io'
# expect /lscratch/ytl/containers/storage and slaclab
```

Then build and push both images:
```bash
ssh sdfiana008 'set -e; W=/lscratch/ytl/akh-build-X.Y.Z; rm -rf "$W"; mkdir -p "$W" /lscratch/ytl/tmp
  git -C /sdf/home/y/ytl/k8s/agent-knowledge-hub archive --format=tar <commit> | tar -x -C "$W"
  export TMPDIR=/lscratch/ytl/tmp; make -C "$W" containers'
```

`make containers` pushes `:X.Y.Z` and `:latest` for each image. The `TAG` comes from
`backend/pyproject.toml`, because the export holds no git tag. The frontend image installs from
`package-lock.json` with `npm ci`.

### Step 4 — Deploy to dev

Do not use `make dev-deploy` or `make prod-deploy` for a hub release: they apply every app in the
overlay (LibreChat, LiteLLM, agentgateway, the MCP servers and more) and pull secrets.

Dev runs `:latest`, so restart the two hub deployments:
```bash
KUBECONFIG=~/.kube/config.sage-dev kubectl -n dev rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend
KUBECONFIG=~/.kube/config.sage-dev kubectl -n dev rollout status deployment/agent-knowledge-hub-backend --timeout=300s
KUBECONFIG=~/.kube/config.sage-dev kubectl -n dev rollout status deployment/agent-knowledge-hub-frontend --timeout=300s
```

Then run the smoke tests below against dev.

### Step 5 — Deploy to prod

Only after dev passes the smoke tests. Diff the hub's own kustomization first; it should show only
the two image lines:
```bash
KUBECONFIG=~/.kube/config.sage kubectl diff -k /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/prod/agent-knowledge-hub/
KUBECONFIG=~/.kube/config.sage kubectl apply -k /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/prod/agent-knowledge-hub/
KUBECONFIG=~/.kube/config.sage kubectl rollout status deployment/agent-knowledge-hub-backend -n prod --timeout=300s
KUBECONFIG=~/.kube/config.sage kubectl rollout status deployment/agent-knowledge-hub-frontend -n prod --timeout=300s
```

Rollback: `KUBECONFIG=~/.kube/config.sage kubectl -n prod rollout undo deployment/agent-knowledge-hub-backend`
(and `-frontend`).

### Smoke tests

Run against dev, then prod, with the matching `KUBECONFIG` and namespace.

- Pods: `Running`, 0 restarts. Prod's image digests (`.status.containerStatuses[0].imageID`) equal
  dev's, so prod runs what dev tested.
- Backend log: `Beanie ready` and `Application startup complete`, no `ERROR` or `Traceback`.
- Backend, from inside its pod: `/health` answers 200, and `/openapi.json` lists the routes the
  release adds.
  ```bash
  kubectl -n <ns> exec deploy/agent-knowledge-hub-backend -- python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health").read())'
  ```
- Frontend, from inside its pod: Next listens on the pod's hostname, not on `127.0.0.1`.
  ```bash
  kubectl -n <ns> exec deploy/agent-knowledge-hub-frontend -- sh -c 'wget -S -q -O /dev/null "http://$(hostname):3000/guides/agent-knowledge-hub" 2>&1 | grep -m1 HTTP/'
  ```
  Check that pages the release changes hold their new text.
- Prod only, the `/agent-knowledge-hub` client end to end, from this repo:
  `sh skill/hub-request.sh GET /cli/api/skills/summary` exits 0 and prints JSON.

---

## Deploying without a version bump (hotfix / config change)

If only manifests or config changed (no new image), skip steps 1–3 and go straight to step 4/5.
To force pods to pick up a new image that was pushed under the same tag, use `imagePullPolicy: Always`
(already set) and restart:

```bash
KUBECONFIG=~/.kube/config.sage-dev kubectl -n dev rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend
```

---

## Running backfill / migration scripts

Scripts live at `backend/scripts/`. Run them by exec-ing into the backend pod.

### Get the pod name
```bash
KUBECONFIG=~/.kube/config.sage-dev kubectl get pods -n dev -l app=agent-knowledge-hub-backend
```

### Execute a script
```bash
KUBECONFIG=~/.kube/config.sage-dev kubectl exec -n dev deployment/agent-knowledge-hub-backend \
  -- python -m scripts.002_backfill_skill_file_content
```

For prod, swap in `KUBECONFIG=~/.kube/config.sage` and `-n prod`.

**Dry-run first** (where supported):
```bash
KUBECONFIG=<path> kubectl exec -n <ns> deployment/agent-knowledge-hub-backend \
  -- sh -c 'DRY_RUN=1 python -m scripts.002_backfill_skill_file_content'
```

Scripts are idempotent — safe to re-run if they fail partway through.

---

## Useful diagnostics

```bash
# Pod status
KUBECONFIG=~/.kube/config.sage-dev kubectl get pods -n dev

# Recent logs
KUBECONFIG=~/.kube/config.sage-dev kubectl logs -n dev deployment/agent-knowledge-hub-backend --tail=50
KUBECONFIG=~/.kube/config.sage-dev kubectl logs -n dev deployment/agent-knowledge-hub-frontend --tail=50

# Events (sorted)
KUBECONFIG=~/.kube/config.sage-dev kubectl get events -n dev --sort-by='.lastTimestamp' | tail -20

# Check which image version is running
KUBECONFIG=~/.kube/config.sage-dev kubectl get pods -n dev -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.containers[*]}{.image}{"\n"}{end}{end}'
```

---

## What Claude must never do

- Run `podman` with `sudo`, run `podman login`, or handle a Docker Hub credential
- Build images against the NFS home: podman's storage, the build context and `TMPDIR` stay on `/lscratch`
- Run `kubectl delete` / `drain` / `cordon` without explicit user confirmation
- Use `vault kv put` with partial fields — use `vault kv patch` to avoid wiping other secrets
