# 042 — Security: Add NetworkPolicy for Frontend Pods

**Status:** ⬜ Open
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M6)

---

## Phase 1 — Problem & Goal

### What is broken today

The backend pods have a NetworkPolicy (`backend-deny-all-ingress` + `backend-allow-frontend-and-ingress` in `kubernetes/overlays/dev/network-policy-backend.yaml` lines 1–34) that restricts ingress to the frontend pod and ingress-nginx only. The **frontend pods have no corresponding NetworkPolicy** — any pod inside the same namespace (or any namespace in the cluster) can reach port 3000 on the frontend pod directly.

This matters because `frontend/app/api/_internal.ts` (`backendHeaders()`, lines 11–41) reads auth headers injected by ingress-nginx/VouchProxy (`X-Vouch-Idp-Claims-Name`, `X-Auth-Request-User`, `X-Forwarded-User`) and forwards them to the backend with an `X-Internal-Secret`. A rogue pod bypassing ingress can send arbitrary `X-Forwarded-User` values directly to the Next.js BFF, potentially impersonating any user if it also knows the internal secret — or can probe BFF endpoints without authentication.

Additionally, there is no namespace-wide `default-deny` policy. New pods that land in `dev` / `agent-knowledge-hub-stage` / `agent-knowledge-hub` get full lateral movement freedom by default.

### What success looks like

- Direct pod-to-pod HTTP to frontend port 3000 from any non-ingress-nginx pod is blocked at the network level.
- A namespace-wide default-deny policy is in force across all three overlays.
- The existing `backend-allow-frontend-and-ingress` policy (`network-policy-backend.yaml`) continues to work — frontend → backend port 8000 is not broken.
- Browser traffic via ingress-nginx still reaches the frontend normally.

### Out of scope

- Changes to auth logic in `frontend/app/api/_internal.ts` or `backend/app/auth.py`.
- Egress NetworkPolicy (frontend needs to reach the backend and external GitHub API; egress restriction is a separate task).
- MongoDB NetworkPolicy (Percona operator manages its own policies).

### Constraints

- Must deploy via kustomize (`make apply` in each overlay).
- Must not break health probes (kubelet → pod on port 3000 — kubelet runs on the node, not a pod, so pod-selector policies do not block it; node CIDR exception not required for in-cluster health checks).
- All three overlays (dev, stage, prod) must be updated consistently.

---

## Phase 2 — Requirements / Feasibility

### Which overlays need changes

All three: `kubernetes/overlays/dev/`, `kubernetes/overlays/stage/`, `kubernetes/overlays/prod/`.

Each overlay currently lists `network-policy-backend.yaml` in its `kustomization.yaml` resources list (lines 14–15 in all three files). The new file `network-policy-frontend.yaml` must be added to each.

### New Kubernetes resources required

One new YAML file per overlay (`network-policy-frontend.yaml`) containing two `NetworkPolicy` objects: a namespace-wide `default-deny-all` and a `frontend-allow-ingress-nginx` rule. No new CRDs or RBAC required.

### Traffic risk during rollout

- The `default-deny-all` policy uses `policyTypes: [Ingress]` only (no egress block), so existing outbound traffic from frontend → backend is not affected.
- Applying the frontend allow policy before (or together with) the default-deny ensures ingress-nginx → frontend traffic is not briefly severed. Since both objects are in the same file, `kubectl apply` via kustomize applies them atomically.
- No existing NetworkPolicy is modified; only additive resources are created.

### Rollback feasibility

`kubectl delete networkpolicy default-deny-all frontend-allow-ingress-nginx -n <namespace>` instantly restores the previous (open) state. Kustomize `make apply` of the previous commit also suffices.

---

## Phase 3 — ADRs

**ADR-042-1: Namespace-wide default-deny for Ingress only (not Egress)**
Status: Accepted
Context: A full default-deny (Ingress + Egress) would also block the frontend from calling `http://agent-knowledge-hub-backend:8000` and external GitHub APIs, requiring explicit egress allow rules and significantly expanding scope.
Options considered:
- Ingress-only default-deny (chosen)
- Full Ingress + Egress default-deny with explicit egress allow rules
- No default-deny, only frontend-specific allow rule

Decision: Ingress-only default-deny. This closes the lateral-movement attack surface (rogue pods reaching frontend) without touching egress. Egress hardening is deferred to a follow-on task.
Consequences: Egress from any pod remains unrestricted; rogue pods can still initiate outbound calls. Accepted as a lower-risk concern compared to inbound impersonation.

---

**ADR-042-2: One shared NetworkPolicy file per overlay rather than a base + patches**
Status: Accepted
Context: The existing backend NetworkPolicy is duplicated verbatim across all three overlays rather than extracted to a `base/` directory. Introducing a base layer mid-project increases merge complexity.
Options considered:
- Duplicate `network-policy-frontend.yaml` in each overlay (chosen, consistent with existing pattern)
- Create `kubernetes/base/` and patch per overlay

Decision: Follow the existing per-overlay duplication pattern. The three files are identical in structure; only the namespace differs (managed by kustomize `namespace:` field). No structural refactor is introduced in this task.
Consequences: Three nearly identical YAML files to maintain. Accepted — the files are small and change rarely.

---

## Phase 3.5 — Migration / Transition Path

### Zero-downtime rollout

Yes. The new NetworkPolicy objects only restrict ingress to the frontend pod. Existing ingress-nginx → frontend traffic matches the allow rule and is unaffected. The frontend → backend path is egress from the frontend pod, which is not touched.

### Rollout order

1. **dev** — apply and manually verify (curl from a test pod is blocked, browser still works).
2. **stage** — apply after dev passes.
3. **prod** — apply after stage passes.

Each overlay is independent; there is no cross-overlay dependency.

### Rollback procedure

```bash
# Delete policies in a specific namespace
kubectl delete networkpolicy default-deny-all frontend-allow-ingress-nginx -n dev

# Or revert via kustomize (remove network-policy-frontend.yaml from kustomization.yaml and reapply)
make -C kubernetes/overlays/dev apply
```

---

## Phase 4 — System / Infrastructure Design

### New file: `kubernetes/overlays/{dev,stage,prod}/network-policy-frontend.yaml`

```yaml
---
# Namespace-wide default deny all ingress
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}
  policyTypes:
    - Ingress
---
# Allow frontend to receive traffic only from ingress-nginx namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: frontend-allow-ingress-nginx
spec:
  podSelector:
    matchLabels:
      app: agent-knowledge-hub-frontend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 3000
```

### Kustomization diff (identical change in all three overlays)

```yaml
# kubernetes/overlays/{dev,stage,prod}/kustomization.yaml — add one line:
 resources:
   ...
   - network-policy-backend.yaml
+  - network-policy-frontend.yaml
```

### NetworkPolicy topology after fix

```
[Internet] → ingress-nginx (ns: ingress-nginx)
                  │  allowed by frontend-allow-ingress-nginx (port 3000)
                  ▼
        [frontend pod :3000]
                  │  egress (unrestricted, no egress policy)
                  ▼
        [backend pod :8000]  ← protected by backend-allow-frontend-and-ingress
```

Rogue pods inside the same namespace hit `default-deny-all` on both frontend and backend ingress.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Ingress-only default-deny | Closes lateral-movement attack without touching egress; zero-risk rollout | Egress from rogue pods still unrestricted |
| Duplicate YAML per overlay | Consistent with existing codebase pattern; no refactor risk | Three files to keep in sync on future changes |
| Apply all objects in one file | Atomic apply — no window where default-deny is live but allow rule is missing | Slightly larger file per overlay |

---

## Phase 8 — Delivery Slices

**Slice 1 — dev overlay** (safe to ship alone)
- Create `kubernetes/overlays/dev/network-policy-frontend.yaml`
- Add it to `kubernetes/overlays/dev/kustomization.yaml`
- Apply to dev, run manual smoke test

**Slice 2 — stage overlay** (safe after Slice 1 passes)
- Same changes in `kubernetes/overlays/stage/`
- Apply and verify

**Slice 3 — prod overlay** (safe after Slice 2 passes)
- Same changes in `kubernetes/overlays/prod/`
- Apply and verify

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Kubelet health probes blocked | Low | High (pod restart loop) | Kubelet runs on node (not a pod); pod-selector NetworkPolicy does not block node-sourced traffic |
| Ingress-nginx namespace label missing | Low | High (frontend becomes unreachable) | Verify `kubectl get ns ingress-nginx --show-labels` before applying; label is standard on SLAC cluster |
| MongoDB operator pods need frontend access | Very low | Low | Percona operator pods do not initiate connections to the frontend |
| `default-deny-all` conflicts with existing backend policy | None | None | Both policies coexist; Kubernetes evaluates policies additively |

---

## Phase 10 — Definition of Done

- [ ] `network-policy-frontend.yaml` created in all three overlays (dev, stage, prod)
- [ ] `kustomization.yaml` updated in all three overlays to include the new file
- [ ] `make apply` succeeds without errors in dev overlay
- [ ] Manual smoke test in dev: browser access via ingress works
- [ ] Manual smoke test in dev: `kubectl exec <test-pod> -n dev -- curl -m 5 http://agent-knowledge-hub-frontend:3000/` times out or is refused
- [ ] Frontend → backend traffic confirmed working (existing backend NetworkPolicy not regressed)
- [ ] Applied to stage and prod after dev verification passes
- [ ] No unrelated regressions in existing kustomize resources

---

## Original Implementation Plan (retained)

- [ ] Create `kubernetes/overlays/dev/network-policy-frontend.yaml`
- [ ] Add to `kubernetes/overlays/dev/kustomization.yaml` resources
- [ ] Apply same to stage and prod overlays
- [ ] Deploy to dev and verify: frontend pod still reachable from browser, pod-to-pod reach from non-ingress pods blocked
- [ ] Verify backend's existing NetworkPolicy (allow from frontend pod) still passes
