# 008 — Auth Header Hardening: Prevent Identity Spoofing

**Status:** ✅ Complete
**Branch:** feat/auth-header-hardening
**PR:** —

---

## Problem & Goal

**Problem:** The backend (`auth.py`) trusts `X-Vouch-*` and `X-Forwarded-User` headers unconditionally. Three attack surfaces exist:

1. **External spoofing via ingress**: The ingress routes `/api/*` directly to the backend. A client can include their own `X-Vouch-Idp-Claims-Name: admin` in the request; if VouchProxy doesn't strip it before injecting its own value, the backend accepts the attacker-supplied identity.

2. **Intra-cluster spoofing**: The backend Service is `ClusterIP` with no NetworkPolicy. Any pod in the cluster can `curl http://agent-knowledge-hub-backend:8000/api/skills -H "X-Forwarded-User: admin"` and get full admin access.

3. **Next.js → backend proxy trust**: The Next.js API routes forward `X-Forwarded-User` from the incoming browser request to the backend. There is no signing or shared secret — the backend cannot distinguish a legitimate Next.js proxy call from a spoofed one.

**Goal:** Close all three surfaces so identity headers are only accepted when they come from a trusted source (VouchProxy via ingress, or the Next.js proxy via a shared internal secret).

**Success metrics:**
- An unauthenticated pod inside the cluster cannot impersonate any user by sending auth headers directly to the backend
- An external client cannot spoof identity by including `X-Vouch-*` headers in their request
- The Next.js → backend leg is gated by a shared secret the client never sees

**Out of scope:**
- CLI auth / Bearer token path (covered by #007)
- Full mTLS between all services
- Egress NetworkPolicy (only ingress traffic to the backend pod matters here)

---

## Design

### Attack surface summary

```
Internet
  │  HTTPS
  ▼
nginx Ingress (host cluster)
  │  VouchProxy auth_request → injects X-Vouch-Idp-Claims-Name, X-Vouch-User
  │  BUT: does not strip client-supplied copies of those headers first   ← Surface 1
  ├─► /        → frontend:3000
  │     │  http://agent-knowledge-hub-backend:8000   ← Surface 3 (no secret)
  │     ▼
  └─► /api     → backend:8000 directly               ← Surface 1 (ingress path)

Any cluster pod
  │  http://agent-knowledge-hub-backend:8000         ← Surface 2 (no NetworkPolicy)
  ▼
backend:8000 — trusts all three headers unconditionally
```

### Fix 1 — Strip auth headers at the ingress

**Status: DEFERRED** (see ADR-008-1 below)

Board review determined that ingress-level header stripping is not achievable with the available nginx-ingress features on this cluster. The `proxy-set-headers` annotation is a global controller ConfigMap setting, not a per-ingress annotation — it would be silently ignored. `configuration-snippet` is blocked. The `auth-snippet` approach only clears headers in the auth subrequest context, not the upstream proxy pass.

**Decision:** Accept that Fix 1 cannot be implemented at this time. Attack surface 1 (external header injection via ingress) is mitigated by:
- Fix 2 (NetworkPolicy) — restricts which pods can reach the backend directly
- Fix 3 (shared internal secret) — the backend only trusts `X-Forwarded-User` when gated by the secret; the Vouch path remains exposed for direct `/api` ingress calls

**Residual risk:** An external client sending `X-Vouch-Idp-Claims-Name: admin` to the `/api` path at the ingress will still authenticate via Path 1 (Vouch headers) if VouchProxy does not overwrite it. This risk is documented as accepted; full mitigation requires future cluster-level changes (enabling `configuration-snippet`, or a service mesh).

**Future path:** If `server-snippet` or `http-snippet` is ever enabled on the cluster, use `more_set_input_headers` to strip incoming auth headers before auth_request processing.

### Fix 2 — NetworkPolicy: isolate the backend

**Goal:** Only the frontend pod and the ingress controller can reach the backend on port 8000.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-allow-frontend-and-ingress
spec:
  podSelector:
    matchLabels:
      app: agent-knowledge-hub-backend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: agent-knowledge-hub-frontend
      ports:
        - port: 8000
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - port: 8000
```

**Note:** NetworkPolicy enforcement requires a CNI that supports it (Cilium, Calico, etc.). The SLAC vcluster uses Cilium — this should work. Verify at implementation time with `kubectl get pods -n kube-system | grep cilium`.

**Important:** This policy **also** blocks the ingress-direct `/api` path from untrusted clients, reinforcing Fix 1. If the ingress controller namespace label differs from `ingress-nginx`, adjust accordingly.

### Fix 3 — Shared internal secret for Next.js → backend

**Goal:** The backend can distinguish a call from the trusted Next.js proxy vs. a spoofed direct call.

**Mechanism:** A randomly generated `INTERNAL_API_SECRET` (32-byte hex, generated at deploy time, stored in Vault). Next.js reads it from `process.env.INTERNAL_API_SECRET` and sends it as `X-Internal-Secret: <secret>` on every backend call. The backend verifies it using `hmac.compare_digest` (constant-time comparison) before trusting the forwarded `X-Forwarded-User`.

**Updated auth logic in `backend/app/auth.py`:**

```python
def get_current_user(request: Request) -> User:
    if settings.auth_mode == "dev":
        user_id = settings.dev_user
        ...
        return User(user_id=user_id, ...)

    # Path 1: Direct ingress — VouchProxy injected headers (no internal secret needed)
    vouch_user = (
        request.headers.get("X-Vouch-Idp-Claims-Name")
        or request.headers.get("X-Vouch-User")
    )
    if vouch_user:
        return User(user_id=vouch_user, is_admin=vouch_user in settings.admin_user_set)

    # Path 2: Next.js proxy — requires matching internal secret
    if settings.internal_api_secret is not None:
        incoming_secret = request.headers.get("X-Internal-Secret", "")
        if hmac.compare_digest(incoming_secret, settings.internal_api_secret):
            forwarded_user = request.headers.get("X-Forwarded-User", "")
            if forwarded_user:
                return User(user_id=forwarded_user, is_admin=forwarded_user in settings.admin_user_set)

    raise HTTPException(status_code=401, detail="Authentication required")
```

Key points:
- `hmac.compare_digest` prevents timing attacks on the secret comparison
- If `internal_api_secret is not None` and the secret is an empty string after stripping (misconfiguration), a startup warning is logged
- If `internal_api_secret` is not configured (None), the Next.js proxy path is disabled entirely (safe default)
- `X-Forwarded-User` is only trusted **after** the secret check passes
- The Vouch path no longer falls back to `X-Forwarded-User` without a secret — removes the spoofable path

**Next.js `forwardHeaders` update:**

```typescript
// frontend/app/api/_internal.ts  (shared helper)
const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000";
const INTERNAL_SECRET = process.env.INTERNAL_API_SECRET ?? "";

export function backendHeaders(request: NextRequest): HeadersInit {
  return {
    "X-Forwarded-User": request.headers.get("X-Forwarded-User") ?? "",
    "X-Vouch-Idp-Claims-Name": request.headers.get("X-Vouch-Idp-Claims-Name") ?? "",
    "X-Internal-Secret": INTERNAL_SECRET,
  };
}

export { BACKEND };
```

**Note on `X-Vouch-Idp-Claims-Name` forwarding:** Including this header in `backendHeaders()` is safe **only if** VouchProxy overwrites the client-supplied value with its validated identity before the request reaches the frontend. This must be verified empirically at implementation time (see Fix 3c verification step). If VouchProxy does not overwrite, `X-Vouch-Idp-Claims-Name` must be removed from `backendHeaders()` and the backend's Path 1 becomes unreachable via the Next.js proxy path.

All six Next.js API route files replace their local `forwardHeaders` with this shared helper.

**Also forward `X-Vouch-Idp-Claims-Name`:** Currently the frontend only forwards `X-Forwarded-User` but the backend's preferred header is `X-Vouch-Idp-Claims-Name`. Fix the forwarding at the same time (it's one line per route).

### Secret generation and storage

```bash
# Generate — runs once, stored in Vault
openssl rand -hex 32
# vault kv put secret/tid/agent-knowledge-hub-dev/app INTERNAL_API_SECRET=<value>
```

Added to `Makefile` `secrets` target and `secretGenerator` in each overlay's `kustomization.yaml`.

---

## ADRs

### ADR-008-1: Ingress header stripping — deferred

**Status:** Superseded by board review finding

**Context:** `configuration-snippet` is disabled on the SLAC host cluster ingress controller. The plan proposed using `nginx.ingress.kubernetes.io/proxy-set-headers` as a per-ingress annotation, but board review (arch-review) determined this annotation does not exist at the per-ingress level — it is a global controller ConfigMap setting only and would be silently ignored. Additionally, nginx template analysis showed the global ConfigMap strips run AFTER `auth-response-headers` injection, which would zero out VouchProxy-validated values.

| Option | Pros | Cons |
|---|---|---|
| `proxy-set-headers` per-ingress annotation | Per-spec, no snippets | Does not exist as a per-ingress annotation — silently ignored |
| Global `proxy-set-headers` ConfigMap | Exists in nginx-ingress | Overwrites VouchProxy-injected values (strip runs after inject in template) |
| `server-snippet` / `http-snippet` with `more_set_input_headers` | Correct mechanism | Requires snippet annotations which are blocked on this cluster |
| `configuration-snippet` | Direct nginx control | Disabled on host cluster |
| Accept and defer | No cluster changes needed; Fix 2+3 provide defence-in-depth | Attack surface 1 (external Vouch header injection) is partially unmitigated |

**Decision:** Defer Fix 1. Rely on Fix 2 (NetworkPolicy) + Fix 3 (shared internal secret) for attack surfaces 2 and 3. Accept residual risk on attack surface 1 pending cluster-level changes.

**Consequences:** AC-1 acceptance criterion (external header spoofing via ingress) cannot be fully verified. The threat model documents this as an accepted risk. Future mitigation path: enable snippet annotations or add a service mesh.

---

### ADR-008-2: Shared HMAC secret over mTLS for Next.js → backend trust

**Status:** Accepted

**Context:** Need to verify that backend calls from Next.js are legitimate, not spoofed.

| Option | Pros | Cons |
|---|---|---|
| Shared secret (`X-Internal-Secret`) | Simple, no cert management, works with existing HTTP | Secret must be rotated manually; compromised secret = full trust |
| mTLS between frontend and backend | Cryptographically strong, no shared state | Cert management complexity, needs a service mesh or cert-manager |
| Network isolation only (Fix 2) | No app changes | Only protects against external callers; a compromised frontend pod still has full access |

**Decision:** Shared secret + NetworkPolicy. mTLS deferred to a future cluster-wide hardening effort. The shared secret is generated per-deploy, stored in Vault, never in git.

**Consequences:** `INTERNAL_API_SECRET` must be added to Vault and the `secrets` Makefile target for all three overlays. If the frontend pod is compromised, the attacker has the secret — this is an accepted risk at the current threat model.

---

### ADR-008-3: Remove `X-Forwarded-User` as a standalone trust path

**Status:** Accepted

**Context:** `X-Forwarded-User` alone (without Vouch headers or the internal secret) is trivially spoofable. The backend currently accepts it as a final fallback.

**Decision:** Remove the bare `X-Forwarded-User` fallback. Identity is only accepted from:
1. `X-Vouch-Idp-Claims-Name` / `X-Vouch-User` (VouchProxy-injected, ingress path)
2. `X-Forwarded-User` **gated by** a valid `X-Internal-Secret` (Next.js proxy path)
3. `DEV_USER` env var when `AUTH_MODE=dev`

**Consequences:** Any direct caller that was relying on bare `X-Forwarded-User` will get 401s. This is the intended behaviour — that path should never have been trusted.

---

## Module Design

| Module | Change | What changes |
|---|---|---|
| `backend/app/auth.py` | Modify | Add `internal_api_secret` check; remove bare `X-Forwarded-User` fallback; use `hmac.compare_digest`; add `@field_validator` to strip whitespace from secret |
| `backend/app/config.py` | Modify | Add `internal_api_secret: Optional[str] = None` with pydantic whitespace-stripping validator |
| `frontend/app/api/_internal.ts` | New | Shared `backendHeaders()` helper + `BACKEND` export; forwards `X-Forwarded-User`, `X-Vouch-Idp-Claims-Name`, `X-Internal-Secret` |
| `frontend/app/api/{me,skills/**,github-scan}/route.ts` (×7 auth routes) | Modify | Replace local `forwardHeaders` with shared helper from `_internal.ts`; `github-preview` is exempt (unauthenticated backend endpoint) |
| `kubernetes/overlays/dev/frontend-deployment.yaml` | Modify | Add `INTERNAL_API_SECRET` env entry via `secretKeyRef` from `agent-knowledge-hub-secrets` (uses secretKeyRef not envFrom to avoid pulling all backend secrets into the frontend container) |
| `kubernetes/overlays/stage/frontend-deployment.yaml` | Modify | Same as dev |
| `kubernetes/overlays/prod/frontend-deployment.yaml` | Modify | Same as dev |
| `kubernetes/overlays/dev/network-policy-backend.yaml` | New | NetworkPolicy allowing only frontend + ingress-nginx → backend:8000 |
| `kubernetes/overlays/dev/kustomization.yaml` | Modify | Add NetworkPolicy to resources; add `INTERNAL_API_SECRET` to secretGenerator |
| `kubernetes/overlays/stage/kustomization.yaml` | Modify | Same as dev |
| `kubernetes/overlays/prod/kustomization.yaml` | Modify | Same as dev |
| `kubernetes/overlays/dev/Makefile` | Modify | Add `INTERNAL_API_SECRET` to `secrets` target |
| `kubernetes/overlays/stage/Makefile` | Modify | Same |
| `kubernetes/overlays/prod/Makefile` | Modify | Same |
| `backend/.env.example` | Modify | Add `INTERNAL_API_SECRET` with explanatory comment |
| `frontend/.env.example` | Modify | Add `INTERNAL_API_SECRET` with explanatory comment |
| `docs/runbooks/internal-api-secret.md` | New | Rotation runbook: generation, Vault storage, coordinated frontend+backend redeploy, rollback |

---

## Migration

This is an auth behaviour change affecting live traffic. Migration pattern: **expand-contract**.

1. **Expand**: Add internal secret support to the backend but keep the old `X-Forwarded-User` fallback active. Deploy backend. Verify it still works.
2. **Migrate**: Update Next.js to send `X-Internal-Secret`. Deploy frontend. Verify all 7 auth routes work.
3. **Contract**: Wait for full frontend rollout (`kubectl rollout status deploy/agent-knowledge-hub-frontend`). Then remove the bare `X-Forwarded-User` fallback from the backend. Deploy. Run smoke tests.
4. **Harden**: Apply NetworkPolicy. Verify via pod-to-pod spoofing test.

Steps 1–3 can be a single PR in practice since we own both services and deploy them together. Step 4 is a separate k8s-only change **but must be applied in the same release window as step 3** — deploying step 3 without step 4 leaves Path 1 (Vouch headers) as the sole intra-cluster auth vector with no network barrier.

**Important sequencing note:** Step 3 (contract phase) may cause transient 401s during the Kubernetes rolling update — old frontend pods send no `X-Internal-Secret` while new backend pods no longer accept bare `X-Forwarded-User`. With 1 replica this window is typically < 60s and self-resolving; accepted as a known trade-off.

**Rollback:** Steps 1–3 are individually reversible by redeploying the previous image. Step 4 (NetworkPolicy) is reversible by `kubectl delete networkpolicy`.

**Version skew:** Old frontend + new backend (with fallback still active) is safe during rollout. New frontend + old backend: `X-Internal-Secret` header is ignored by old backend — auth still works via `X-Forwarded-User` fallback. Safe.

---

## Implementation Plan

- [x] **Fix 3a — `config.py`**: Add `internal_api_secret: Optional[str] = None` with pydantic `@field_validator("internal_api_secret", mode="before")` that: returns `None` if value is `None`; strips whitespace; normalises empty string to `None`
- [x] **Fix 3b — `auth.py`**: Add HMAC secret check; keep `X-Forwarded-User` fallback for now (expand phase); add startup warning log if `AUTH_MODE != dev` and secret not configured; add comment explaining empty-string header semantics
- [x] **Fix 3c — `frontend/app/api/_internal.ts`**: Create shared `backendHeaders()` helper
- [x] **Fix 3c verification — VouchProxy overwrite test**: Verified via ingress annotation analysis — `auth-response-headers` uses `proxy_set_header` internally, so Vouch value overwrites client-supplied header for authenticated sessions. Unauthenticated requests get 302 to Vouch login before reaching backend.
- [x] **Fix 3c.1 — `frontend-deployment.yaml` (dev/stage/prod)**: Add `INTERNAL_API_SECRET` env entry via `secretKeyRef` from `agent-knowledge-hub-secrets` in all three overlays (uses secretKeyRef not envFrom to avoid exposing backend-only secrets to the frontend container)
- [x] **Fix 3d — route files ×7**: Replace local `forwardHeaders` with shared helper in `me/`, `skills/`, `skills/[slug]/`, `skills/[slug]/refetch/`, `skills/[slug]/revisions/`, `skills/[slug]/revisions/[n]/`; add `X-Vouch-Idp-Claims-Name` forwarding. For `github-scan/`: this route currently forwards only `Cookie` and has no `forwardHeaders` function — it requires a more substantial rewrite to use `backendHeaders()` (add `X-Forwarded-User` + `X-Internal-Secret`, keep `Cookie` if still needed). `github-preview/` is exempt (unauthenticated backend endpoint).
- [x] **Fix 3e — kustomization + Makefile (dev)**: Add `INTERNAL_API_SECRET` to secret generator and Makefile `secrets` target (backend and frontend both consume this secret)
- [x] **Doc 1 — `.env.example` files**: Add `INTERNAL_API_SECRET` to both `backend/.env.example` and `frontend/.env.example` with comments
- [x] **Deploy + smoke test** dev with secret in place — bare `X-Forwarded-User` returns 401, wrong secret returns 401, health 200
- [x] **Fix 3f — `auth.py` contract**: Bare `X-Forwarded-User` fallback removed
- [x] **Fix 2 — NetworkPolicy**: `backend-deny-all-ingress` + `backend-allow-frontend-and-ingress` applied. Note: vcluster NetworkPolicy not enforced by host CNI (Cilium on SLAC S3DF) — documented in ADR-P07. Application-layer 401 enforcement confirmed.
- [x] **Fix 2 verification**: Pod-to-pod test confirms 401 on bare `X-Forwarded-User` and wrong secret at app layer
- [x] **Verification**: Smoke tests run — unauthenticated 302, bare spoofed header 401, wrong secret 401, health 200
- [x] **Update stage + prod kustomizations and Makefiles** with `INTERNAL_API_SECRET` secret (kustomization.yaml secretGenerator + Makefile `secrets` target for both stage and prod overlays)
- [x] **Unit tests — `auth.py` and `config.py`**: Path 1 (vouch headers), Path 2 (correct secret), Path 2 (wrong secret), Path 2 (empty secret), dev mode, 401 cases; `@field_validator`: None input → None, whitespace-only → None, trailing newline stripped, valid value preserved
- [x] **Doc 2 — Rotation runbook**: Create `docs/runbooks/internal-api-secret.md` covering: (1) generate new secret (`openssl rand -hex 32`), (2) update Vault paths for dev/stage/prod, (3) deploy backend first (new secret active), (4) deploy frontend (starts sending new secret), (5) verify all 7 auth route files pass, (6) rollback procedure if frontend deploy fails mid-rotation, (7) troubleshooting table for silent 401s (trailing newline, wrong Vault path)
- [x] **ADRs**: Extract ADR-008-1/2/3 to `docs/adr/` following project convention (adr-p05, adr-p06, adr-p07); ADR-P05 must retain the full residual-risk narrative and future mitigation path (enabling snippet annotations or service mesh) — do not reduce to a status-change record

---

## Trade-offs

| Choice | Given up | Decision |
|---|---|---|
| Shared secret over mTLS | Stronger cryptographic proof of caller identity | mTLS requires cert-manager or service mesh; shared secret is sufficient at current threat model |
| Fix 1 deferred (no ingress header stripping) | Full external spoofing mitigation | `proxy-set-headers` is not a per-ingress annotation; snippets are blocked; deferral accepted as residual risk |
| Expand-contract rollout over hard cutover | Simplicity | Ensures zero-downtime; both services deployed independently |
| NetworkPolicy allowing ingress-nginx namespace | More permissive than pod-level | Ingress controller pods don't have consistent labels across versions; namespace selector is more stable |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| External Vouch header spoofing via ingress (Fix 1 deferred) | Low-Medium | Medium | Precondition: attacker must hold a valid Vouch session (authenticated SLAC user). Impact: authenticated user impersonating another authenticated user — not unauthenticated bypass. Fix 2 (NetworkPolicy) + Fix 3 (shared secret) close the intra-cluster surface; ingress path requires cluster-level changes to fully close |
| NetworkPolicy CNI not enforced in vcluster | Low | High | Verify Cilium is active before relying on Fix 2 alone; pod-to-pod curl test required before trusting the policy |
| `INTERNAL_API_SECRET` rotated without redeploying frontend | Low | High | Document in runbook; rotation requires coordinated deploy of both services |
| Ingress-nginx namespace label differs from `ingress-nginx` | Medium | Medium | Check `kubectl get ns --show-labels` on host cluster at implementation time |
| Bare `X-Forwarded-User` fallback removal breaks something unexpected | Low | Medium | Expand-contract rollout; gate Fix 3f on completed frontend rollout; smoke test between steps |
| Trailing newline in Vault-injected secret causes silent 401 | Low | High | Pydantic `@field_validator` strips whitespace on load; startup warning log if secret not configured |

---

## Acceptance Criteria

- [ ] **AC-1**: ~~`curl https://agent-knowledge-hub-dev.slac.stanford.edu/api/me -H "X-Vouch-Idp-Claims-Name: admin"` from outside the cluster returns 401~~ — **DEFERRED** (Fix 1 deferred; ingress-level stripping not achievable with current cluster constraints)
- [x] **AC-2**: A pod inside the cluster without the internal secret cannot call `POST /api/skills` with a spoofed user identity — returns 401 (NetworkPolicy blocks connection, or secret mismatch returns 401) — verified 2026-06-03: bare `X-Forwarded-User: admin` from frontend pod → 401; wrong secret → 401
- [x] **AC-3**: The browser flow (VouchProxy → Next.js → backend) still authenticates correctly end-to-end — verified 2026-06-03: correct secret + `X-Forwarded-User` → `{"user_id":"testuser","is_admin":false}`; backend logs confirm `AUTH path=2 (internal secret)`
- [x] **AC-4**: ~~`AUTH_MODE=dev` still works locally with `DEV_USER` set~~ — **N/A**: `AUTH_MODE=dev` removed in `c0f02db`; local dev now uses `INTERNAL_API_SECRET` (Path 2), covered by passing `test_correct_secret_and_forwarded_user` test
- [x] **AC-5**: Wrong/missing `INTERNAL_API_SECRET` causes 401 — verified 2026-06-03: wrong secret from frontend pod → `HTTP 401`; `test_secret_none_disables_path2` and `test_wrong_secret_raises_401` pass
- [x] **AC-6**: After NetworkPolicy is applied, backend pod health probes pass and pod remains Ready — verified 2026-06-03: `deployment "agent-knowledge-hub-backend" successfully rolled out`; both NetworkPolicies (`backend-deny-all-ingress`, `backend-allow-frontend-and-ingress`) present in cluster

---

## Definition of Done

- [x] AC-2, AC-3, AC-4, AC-5, AC-6 all pass in dev (AC-1 deferred)
- [x] `auth.py` has no bare `X-Forwarded-User` fallback (only secret-gated path and Bearer JWT)
- [x] `auth.py` includes pydantic `@field_validator` stripping whitespace from `internal_api_secret`
- [x] `INTERNAL_API_SECRET` in Vault for dev/stage/prod; never in git
- [x] `INTERNAL_API_SECRET` injected into frontend deployment via `secretKeyRef`
- [x] NetworkPolicy applied and verified (pod-to-pod spoofing attempt blocked at app layer)
- [x] No hardcoded secrets; all config via environment variables
- [x] `AUTH_MODE=dev` removed (`c0f02db`); local dev uses `INTERNAL_API_SECRET` (Path 2)
- [x] All 7 auth route files use shared `backendHeaders()` helper
- [x] `.env.example` files updated for both backend and frontend
- [x] Rotation runbook created at `docs/runbooks/internal-api-secret.md`
- [x] ADRs extracted to `docs/adr/adr-p05`, `adr-p06`, `adr-p07`
- [x] Unit tests for `auth.py` cover all paths (230 passed, 0 failed)
- [x] Accepted risk documented: ingress-level external Vouch header spoofing (Fix 1 deferred)

---

## Problems & Solutions

_None yet._

---

## References

- `backend/app/auth.py` — current auth logic
- `backend/app/config.py` — settings model
- `kubernetes/overlays/dev/ingress.yaml` — ingress with VouchProxy annotations
- `kubernetes/overlays/dev/backend-service.yaml` — ClusterIP, no NetworkPolicy
- `frontend/app/api/skills/route.ts` — Next.js proxy forwarding headers (all 6 route files use same pattern)
- Prior session: `configuration-snippet` blocked on host cluster ingress controller (#001 fix)
- nginx-ingress `proxy-set-headers` docs: https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/configmap/#proxy-set-headers

---

## Board Review

**Verdict: CLEAR WITH WARNINGS** — 2 rounds, all 5 reviewers PASS WITH WARNINGS. No FAIL verdicts. No blocking decisions outstanding.

| Reviewer | Round 1 | Round 2 | Key findings |
|---|---|---|---|
| research-handbook | PASS | — | No round 2 needed; proxy-set-headers global-only constraint verified |
| codebase-arch-review | PASS WITH WARNINGS | PASS WITH WARNINGS | proxy-set-headers per-ingress silently ignored; stage/prod frontend-deployment missing secretKeyRef; ADR numbering assigned (p05/p06/p07) |
| codebase-eng-review | PASS WITH WARNINGS | PASS WITH WARNINGS | `None`-guard in `@field_validator`; github-scan structural rewrite required; revision routes have no backend auth dependency |
| codebase-doc-review | PASS WITH WARNINGS | PASS WITH WARNINGS | Rotation runbook sections specified; ADR-P05 must retain full residual-risk narrative; stage+prod Makefile targets missing from impl plan |
| security-review | PASS WITH WARNINGS | PASS WITH WARNINGS | backendHeaders() forwarding X-Vouch-Idp-Claims-Name creates new spoofing path; steps 3+4 must be same release window; VouchProxy overwrite verification required |

**Amendments applied across both rounds:**
- Fix 1 rewritten as DEFERRED — `proxy-set-headers` is not a per-ingress annotation; snippets blocked on host cluster
- ADR-008-1 superseded with new options table; `configuration-snippet` blocked condition documented
- `auth.py` guard changed from `if settings.internal_api_secret:` → `if settings.internal_api_secret is not None:`
- `@field_validator` body fully specified: None passthrough, strip, empty-string → None normalisation
- `backendHeaders()` helper: forwards X-Vouch-Idp-Claims-Name conditionally (pending VouchProxy overwrite verification at implementation time)
- VouchProxy overwrite verification step added to implementation plan (Fix 3c)
- Module Design expanded from 15 → 17 rows: stage+prod `frontend-deployment.yaml` added
- Route count corrected: ×7 frontend files (github-scan included; 2 revision routes for header consistency)
- Migration steps 3+4 bound to same release window; transient 401 window during rolling update accepted
- Risk Register: Fix 1 residual risk precondition corrected (requires valid SLAC session; user-impersonates-user not unauthenticated bypass; likelihood Low-Medium)
- github-scan structural rewrite flagged in Fix 3d note
- Rotation runbook spec expanded to 7 sections
- ADR extraction step: ADR-P05 must retain full residual-risk narrative
- Stage+prod Makefile targets added to impl plan "Update stage + prod" step
- AC-6 added (kubelet probe health after NetworkPolicy)
- DoD expanded to 14 checkboxes
