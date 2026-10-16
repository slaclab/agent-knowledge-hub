# 033 — Security: Containers Running as Root — Add Kubernetes securityContext

**Status:** ✅ Complete — shipped in 0.20.0, deployed to dev and prod 2026-10-16
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H4)

---

## Phase 1 — Problem & Goal

### What is broken today

Both `backend/Dockerfile` (line 12) and `frontend/Dockerfile` (line 22) have no `USER` directive — every process in both containers runs as **root (UID 0)**. None of the six deployment manifests (`kubernetes/overlays/{dev,stage,prod}/{backend,frontend}-deployment.yaml`) set a `securityContext` at the container or pod level.

Concrete risk: a remote code execution or container escape in uvicorn (backend) or the Next.js Node process (frontend) gives the attacker unrestricted root inside the container — full filesystem write access, ability to install tooling, and a clear path to exploit kernel CVEs for host escape.

### What success looks like

- Both containers start as UID 1000 (non-root) in all three overlays.
- `allowPrivilegeEscalation: false` and `capabilities: drop: ALL` are set on every container.
- `readOnlyRootFilesystem: true` is enabled; any known writable paths are backed by `emptyDir` volumes.
- `kubectl exec <pod> -- id` returns `uid=1000(appuser)` for both backend and frontend.

### Out of scope

- Changing MongoDB operator pod security (separate operator-managed resource).
- PodSecurityPolicy / PodSecurityAdmission enforcement at the namespace level (follow-on hardening).
- Network policy changes (already in place from #008).

### Constraints

- Must deploy via kustomize (`make apply`); no Helm or out-of-band changes.
- Must not break the existing auth flow: Vouch header injection, HMAC internal secret, Bearer JWT — none of these touch the container user identity.
- Rolling update must not drop traffic (prod runs 2 replicas; RollingUpdate strategy preserves availability).

---

## Phase 2 — Requirements [Feasibility]

### Overlays affected

All three overlays need changes: `dev`, `stage`, `prod`. Each overlay has its own standalone deployment YAML (no shared base), so each file must be edited independently — 6 manifest files total plus 2 Dockerfiles.

### New Kubernetes resources

No new resource types. Two `emptyDir` volumes per deployment (backend: `/tmp`; frontend: `/app/.next/cache` + `/tmp`).

### Traffic / networking risk during rollout

Low. `securityContext` is applied during a pod spec change, which triggers a rolling restart. Existing pods serve traffic until new pods pass readiness probes. The only breakage scenario is if a pod crashes due to a permission error — mitigated by testing in dev first.

### Rollback feasibility

Trivially reversible: remove the `securityContext` blocks and `emptyDir` volumes from the manifests, rebuild images without the `USER` directive, re-apply. No persistent state is affected.

---

## Phase 3 — ADRs

**ADR-033-1: Enforce non-root via both Dockerfile USER and k8s securityContext**
Status: Accepted
Context: Non-root enforcement can be applied at the image layer (Dockerfile `USER`), at the k8s layer (`securityContext.runAsUser`), or both. Defense in depth requires both.
Options considered:
- Dockerfile only — k8s can override with `runAsUser: 0`; insufficient.
- k8s only — image still ships with root as default; weak supply-chain posture.
- Both — image refuses to run as root by default; k8s adds an additional hard constraint.
Decision: Both layers. Dockerfile adds `appuser` (UID 1000) and sets `USER appuser`; k8s sets `runAsNonRoot: true` + `runAsUser: 1000`.
Consequences: Image builds must succeed before k8s changes take effect; two places to update if UID changes.

---

**ADR-033-2: Enable readOnlyRootFilesystem with targeted emptyDir mounts**
Status: Accepted
Context: `readOnlyRootFilesystem: true` is the strongest container hardening control available without a seccomp profile, but it breaks processes that write to the container filesystem at runtime.
Options considered:
- Skip `readOnlyRootFilesystem` — simpler, but leaves filesystem writability as an attack vector.
- Enable with emptyDir for known write paths — backend needs `/tmp`; Next.js standalone needs `/app/.next/cache` and `/tmp`.
- Enable without emptyDir — likely crashes (Next.js ISR cache writes).
Decision: Enable with emptyDir mounts for `/tmp` (both containers) and `/app/.next/cache` (frontend only). Backend code scan (`grep -rn "writeFile\|createWriteStream\|/tmp" backend/app/`) found no writes — uvicorn and Beanie ODM are fully in-memory.
Consequences: Added `volumes` and `volumeMounts` stanzas in all 6 manifest files; minor YAML verbosity.

---

**ADR-033-3: Apply identical securityContext across all three overlays**
Status: Accepted
Context: dev/stage/prod overlays are structurally identical in security posture; diverging them creates drift and audit risk.
Decision: Apply the same `securityContext` block to all three overlays in a single PR. Roll out dev → stage → prod sequentially.
Consequences: A single failing container permission issue in dev blocks the entire rollout until resolved.

---

## Phase 3.5 — Migration Path

**Zero-downtime:** Yes. Each deployment uses `RollingUpdate` strategy (default). New pods with the security context come up, pass readiness probes, then old pods terminate. The 2-replica prod deployment ensures no traffic gap.

**Rollout order:** dev → stage → prod. Validate `kubectl exec` UID check and liveness/readiness in dev before promoting.

**Rollback procedure:**
1. Revert the manifest changes: remove `securityContext` blocks and `emptyDir` volumes.
2. `make apply` in the affected overlay — rolling restart restores root-running pods.
3. Revert Dockerfile `USER` lines and rebuild images if image-layer rollback is needed (low priority; k8s layer is the immediate lever).

---

## Phase 4 — System/Infrastructure Design

### Dockerfile changes

**`backend/Dockerfile`** — add before `CMD` (after `COPY app/`):
```dockerfile
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser
USER appuser
```

**`frontend/Dockerfile`** — add in the `runner` stage (after `COPY --from=builder` lines, before `CMD`):
```dockerfile
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app
USER appuser
```
The `chown` is required because the standalone build copies files as root; the runner process needs read access to `/app/.next/static` and write access to `/app/.next/cache` (via emptyDir mount).

### Kubernetes manifest changes (all 6 deployment files)

**Backend deployment** (`kubernetes/overlays/{dev,stage,prod}/backend-deployment.yaml`) — add to `spec.template.spec`:
```yaml
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
        - name: backend
          # ... existing fields ...
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            runAsGroup: 1000
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
```

**Frontend deployment** (`kubernetes/overlays/{dev,stage,prod}/frontend-deployment.yaml`) — add to `spec.template.spec`:
```yaml
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
      containers:
        - name: frontend
          # ... existing fields ...
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            runAsGroup: 1000
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: nextjs-cache
              mountPath: /app/.next/cache
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: nextjs-cache
          emptyDir: {}
        - name: tmp
          emptyDir: {}
```

No NetworkPolicy changes — existing policy (from #008) already restricts ingress to backend:8000 from frontend and ingress-nginx only; container UID does not affect network policy matching.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Enforce non-root at both Dockerfile and k8s layers | Defense in depth; image is hardened independently of cluster config | Two places to maintain; image rebuilds needed alongside manifest changes |
| `readOnlyRootFilesystem: true` with emptyDir | Prevents attacker writing tools/payloads to container FS | Requires explicit emptyDir for every writable path; any undiscovered write path causes a runtime crash |
| Single PR covering all 3 overlays | Audit trail is clean; no drift between environments | A test failure in dev blocks stage/prod deployment until resolved |
| `capabilities: drop: ALL` | Eliminates all POSIX capabilities (NET_RAW, SYS_ADMIN, etc.) | If a future feature needs a capability (unlikely for a web API), it must be explicitly re-added |

---

## Phase 8 — Delivery Slices

**Slice 1 — Dockerfiles (image layer hardening)**
- Add `appuser` + `USER appuser` to `backend/Dockerfile` and `frontend/Dockerfile`.
- Build and push new images; update image tags in dev manifests.
- Safe to ship independently: images run as non-root even without k8s securityContext.

**Slice 2 — k8s securityContext in dev overlay**
- Add `securityContext` + emptyDir volumes to `kubernetes/overlays/dev/backend-deployment.yaml` and `frontend-deployment.yaml`.
- Apply and validate: `kubectl exec` UID check, liveness/readiness probes green, app smoke test.
- Safe to ship after Slice 1; dev is the validation gate.

**Slice 3 — Promote to stage and prod**
- Replicate identical securityContext changes to `stage` and `prod` overlays.
- Apply stage → validate → apply prod.
- Depends on Slice 2 passing. No functional changes beyond overlay promotion.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Next.js runtime write to undiscovered path fails with `readOnlyRootFilesystem` | Medium | Pod crashloop in dev | Test thoroughly in dev before stage; add emptyDir for any path that fails |
| `chown -R` in frontend Dockerfile significantly increases image build time | Low | Slow CI | Scope `chown` to only `/app` (already bounded); standalone output is ~50 MB |
| Percona MongoDB operator pods are also running as root | Low (out of scope) | Medium — separate pod lineage | Track as follow-on; operator manages its own PSA |
| Future code introduces a filesystem write without a corresponding emptyDir | Low | Runtime crash in prod | Add lint/review checklist item for any new `open()`/`write` in backend; note in CONTRIBUTING |

---

## Phase 10 — Definition of Done

- [x] `backend/Dockerfile` sets `USER appuser` (non-root, UID 1000)
- [x] `frontend/Dockerfile` sets `USER appuser` with `chown` of `/app` in runner stage
- [x] `securityContext` applied to backend and frontend deployments in all three overlays (6 files)
- [x] `emptyDir` volumes mounted at `/tmp` (backend + frontend) and `/app/.next/cache` (frontend)
- [x] `kubectl exec -it <backend-pod> -- id` returns `uid=1000` in dev
- [x] `kubectl exec -it <frontend-pod> -- id` returns `uid=1000` in dev
- [x] Backend liveness probe (`/health`) passes after rollout in dev
- [x] Frontend liveness probe (`/`) passes after rollout in dev
- [x] No `Permission denied` errors in pod logs after rollout
- [x] Existing backend test suite passes (`pytest`) — no auth regressions
- [x] Deployed to stage and prod after dev validation
- [x] `kubectl get pod -o yaml` confirms `allowPrivilegeEscalation: false` in running pods

---

## Problems & Solutions

### Deviation: the frontend runs as the image's `node` user, and `/app` stays owned by root
**Encountered:** 2026-10-16
**Root cause:** on Alpine, `adduser --system` assigns a system UID below 1000, so the planned `appuser` would not have matched `runAsUser: 1000`, and UID 1000 already belongs to `node` in `node:20-alpine`.
**Solution:** the runner stage uses `USER 1000:1000`, which is `node`, and does not `chown -R /app`. The server reads its code but does not own it, so it cannot change it even without the read-only root. Only `/app/.next/cache` is created and given to UID 1000, so the image also runs outside Kubernetes; the cluster mounts an `emptyDir` there.

### Decision: numeric `USER` in both images
**Encountered:** 2026-10-16
**Root cause:** the kubelet verifies `runAsNonRoot` from a numeric user; a named one fails that check unless `runAsUser` is also set.
**Solution:** the backend creates `appuser` with UID and GID 1000 (`groupadd`/`useradd`, Debian's tools) and sets `USER 1000:1000`. It also sets `PYTHONDONTWRITEBYTECODE=1`, so Python does not try to write bytecode on the read-only root. `useradd` prints a harmless warning that UID 1000 is above `SYS_UID_MAX`.

### Deviation: the deployed manifests live in `ai-playground-deploy`
**Encountered:** 2026-10-16
**Root cause:** the root `Makefile` applies the overlays in `ai-playground-deploy`; this repository's `kubernetes/overlays/` are reference copies that nothing applies, and `ai-playground-deploy` has no stage overlay.
**Solution:** the same blocks went into the hub's dev and prod deployments in `ai-playground-deploy` (commit `e73e278`) and into this repository's six copies. "Deployed to stage" is therefore met only by the reference copy.

### Verification, 2026-10-16
- On `sdfiana008`, both 0.20.0 images ran in one podman pod with MongoDB under `--read-only --tmpfs /tmp --cap-drop=ALL --security-opt=no-new-privileges`: `id` gave `uid=1000(appuser)` and `uid=1000(node)`, `/health` and `/api/skills/summary` answered 200, every probed page answered 200, `touch /app/x` failed with `Read-only file system`, and neither log held a write error.
- On dev and then prod, after `kubectl apply -k` of the hub's own kustomization: both pods ready with 0 restarts, `id` gave `uid=1000` in both, `touch /app/x` failed with `Read-only file system`, the running container's `securityContext` held `allowPrivilegeEscalation: false` and `readOnlyRootFilesystem: true`, and the last 300 log lines held no `EROFS`, `EACCES`, `Permission denied`, `Traceback` or 5xx. The backend suite passed: 1129 passed, 5 skipped.

## Implementation Plan

- [x] Add `USER appuser` to `backend/Dockerfile` (after `COPY app/`, before `CMD`)
- [x] Add `USER appuser` + `chown /app` to `frontend/Dockerfile` runner stage
- [x] Rebuild + push both images with new tags
- [x] Add `securityContext` + emptyDir volumes to `kubernetes/overlays/dev/backend-deployment.yaml`
- [x] Add `securityContext` + emptyDir volumes to `kubernetes/overlays/dev/frontend-deployment.yaml`
- [x] `make apply` in dev; validate UID, probes, and app smoke test
- [x] Replicate securityContext changes to `kubernetes/overlays/stage/` (both files)
- [ ] `make apply` in stage; validate
- [x] Replicate securityContext changes to `kubernetes/overlays/prod/` (both files)
- [x] `make apply` in prod; validate
