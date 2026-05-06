# /deploy — Agent Knowledge Hub release & deploy

Invoke this skill when the user asks to deploy, release, build images, update manifests, or run
a backfill. Read and apply the full workflow below.

---

## Environment reference

| Env  | KUBECONFIG                                  | Namespace | Overlay path (in ai-playground-deploy)                        |
|------|---------------------------------------------|-----------|---------------------------------------------------------------|
| dev  | `~/.kube/config.sage-dev`                   | `dev`     | `kubernetes/overlays/dev/agent-knowledge-hub/`                |
| prod | `~/.kube/config.sage`                       | `prod`    | `kubernetes/overlays/prod2/agent-knowledge-hub/`              |

Repos:
- **App code**: `/sdf/home/y/ytl/k8s/agent-knowledge-hub/` (this repo)
- **Manifests**: `/sdf/home/y/ytl/k8s/ai-playground-deploy/` (separate git repo)

Image names:
- `slaclab/agent-knowledge-hub-backend:<version>`
- `slaclab/agent-knowledge-hub-frontend:<version>`

---

## Full release cycle

### Step 1 — Bump the version

Edit `backend/pyproject.toml`:
```
version = "X.Y.Z"
```

Commit in the app repo:
```bash
git add backend/pyproject.toml
git commit -m "chore: bump version to X.Y.Z"
```

### Step 2 — Update manifests

Edit the four deployment files in the **ai-playground-deploy** repo:

```
kubernetes/overlays/dev/agent-knowledge-hub/backend-deployment.yaml
kubernetes/overlays/dev/agent-knowledge-hub/frontend-deployment.yaml
kubernetes/overlays/prod2/agent-knowledge-hub/backend-deployment.yaml
kubernetes/overlays/prod2/agent-knowledge-hub/frontend-deployment.yaml
```

Change `image: slaclab/agent-knowledge-hub-{backend,frontend}:OLD` → `:X.Y.Z` in all four.

Commit in the **ai-playground-deploy** repo (Claude edits the files; user commits or Claude
commits if in that repo's working directory):
```bash
git -C /sdf/home/y/ytl/k8s/ai-playground-deploy add kubernetes/overlays/dev/agent-knowledge-hub/ kubernetes/overlays/prod2/agent-knowledge-hub/
git -C /sdf/home/y/ytl/k8s/ai-playground-deploy commit -m "chore: bump agent-knowledge-hub to X.Y.Z"
```

### Step 3 — Build and push images (USER ONLY)

**Claude must not run these.** They require `sudo podman` and Docker Hub credentials.

Ask the user to run from the app repo root:
```bash
make containers   # builds + pushes both backend and frontend
# or separately:
make backend
make frontend
```

The `TAG` is auto-derived from `backend/pyproject.toml` version when no git tag exists.

### Step 4 — Deploy to dev

Claude can run this once images are pushed:
```bash
make dev-deploy
```

This is equivalent to:
```bash
KUBECONFIG=~/.kube/config.sage-dev make -C /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/dev/ apply
KUBECONFIG=~/.kube/config.sage-dev kubectl -n dev rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend
```

Then verify:
```bash
KUBECONFIG=~/.kube/config.sage-dev kubectl rollout status deployment/agent-knowledge-hub-backend -n dev
KUBECONFIG=~/.kube/config.sage-dev kubectl rollout status deployment/agent-knowledge-hub-frontend -n dev
```

### Step 5 — Deploy to prod

Only after dev is verified:
```bash
make prod-deploy
```

Equivalent to:
```bash
KUBECONFIG=~/.kube/config.sage make -C /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/prod2/ apply
KUBECONFIG=~/.kube/config.sage kubectl -n prod rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend
```

Verify:
```bash
KUBECONFIG=~/.kube/config.sage kubectl rollout status deployment/agent-knowledge-hub-backend -n prod
KUBECONFIG=~/.kube/config.sage kubectl rollout status deployment/agent-knowledge-hub-frontend -n prod
```

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

- Run `make backend`, `make frontend`, or `make containers` — user only (requires sudo podman + Docker Hub auth)
- Run `kubectl delete` / `drain` / `cordon` without explicit user confirmation
- Use `vault kv put` with partial fields — use `vault kv patch` to avoid wiping other secrets
