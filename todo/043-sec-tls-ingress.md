# 043 — Security: Confirm TLS Termination on Ingress (HSTS / Force SSL Redirect)

**Status:** ✅ Complete
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M11)

---

## Problem & Goal

### What is broken / at risk today

All six ingress manifests across three overlays (`dev`, `stage`, `prod`) define only `spec.rules` with `http:` blocks and carry zero TLS configuration. Specifically:

- `kubernetes/overlays/prod/ingress-frontend.yaml` — no `tls:` section, no `force-ssl-redirect` annotation (lines 1-25)
- `kubernetes/overlays/prod/ingress-api.yaml` — same gap (lines 1-30); exposes the `/cli` path where CLI clients send `Authorization: Bearer <jwt>` tokens
- `kubernetes/overlays/dev/ingress-frontend.yaml`, `kubernetes/overlays/dev/ingress-api.yaml`, `kubernetes/overlays/stage/ingress-frontend.yaml`, `kubernetes/overlays/stage/ingress-api.yaml` — identical gap

If ingress-nginx's cluster-wide default does not enforce HTTPS, an HTTP request will be served plaintext. Auth cookies (set by VouchProxy after OIDC login), the `X-Internal-Secret` HMAC header (used for Next.js BFF → backend calls), and Bearer JWTs on the `/cli` path are all in-flight cleartext. None of the existing NetworkPolicy or auth-hardening work (task #008) protects transport-layer exposure.

Additionally there is a legacy `kubernetes/overlays/dev/ingress.yaml` (lines 1-40) — a single-Ingress leftover that still exists in the dev overlay alongside the split ingress-frontend/ingress-api files — that also lacks TLS and should be removed or reconciled.

**It is possible TLS is terminated at the upstream SLAC load balancer before traffic reaches ingress-nginx.** If that is the case, HTTP inside the cluster is acceptable, but HTTP from the public internet is not — and without `force-ssl-redirect`, there is nothing to prevent a client from connecting over HTTP.

### What success looks like

- Every HTTP request to any hostname across all three overlays is redirected to HTTPS (301/302).
- The TLS handling model (upstream LB vs. cert-manager) is documented inline in the manifests so future engineers do not have to guess.
- `Strict-Transport-Security` header is present (handled by task #035, but redirect must work first).

### Out of scope

- Provisioning or rotating TLS certificates (cert-manager ClusterIssuer, DNS challenges) — this is an infrastructure decision for SLAC ops, not in-repo.
- HSTS header itself — covered by task #035.
- Any backend auth logic changes.

### Constraints

- Must deploy via `kustomize build` — no Helm, no manual `kubectl apply`.
- Must not break the VouchProxy auth flow (the `auth-url` / `auth-signin` annotations use HTTPS already — a redirect to HTTPS will not break them).
- Must not break CLI Bearer JWT path on `/cli` in `ingress-api.yaml`.
- All three overlays must be updated; they cannot diverge on this security property.

---

## Design

**Recommended path — force-ssl-redirect annotation (no cert-manager):**

Because SLAC's infrastructure likely terminates TLS upstream, the minimal safe fix is to add `force-ssl-redirect: "true"` to every Ingress. This tells ingress-nginx to issue a 301 to HTTPS for any HTTP request regardless of whether a `tls:` block exists. Add a comment documenting the upstream-LB model so the intent is explicit.

```yaml
# Example diff for kubernetes/overlays/prod/ingress-frontend.yaml
metadata:
  annotations:
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    # TLS is terminated at the upstream SLAC load balancer.
    # This annotation ensures HTTP clients are redirected to HTTPS even
    # when no tls: section is defined here. Do not remove without confirming
    # the upstream LB still enforces TLS.
    nginx.ingress.kubernetes.io/auth-url: ...
```

**Fallback path — add tls: section (if upstream LB does not handle TLS):**

If SLAC infra confirms TLS is NOT terminated upstream, add a `tls:` block pointing to a pre-provisioned certificate Secret:

```yaml
spec:
  tls:
    - hosts:
        - agent-knowledge-hub.slac.stanford.edu
      secretName: agent-knowledge-hub-tls
  rules:
    ...
```

The Secret must be provisioned out-of-band (cert-manager or manual); the manifest change alone is sufficient for in-repo purposes.

**Legacy ingress cleanup:**

`kubernetes/overlays/dev/ingress.yaml` is a superseded single-ingress manifest. It is not listed in `kubernetes/overlays/dev/kustomization.yaml` (which lists `ingress-frontend.yaml` and `ingress-api.yaml`). Confirm it is not referenced, then either delete it or leave it orphaned with a comment — it does not need TLS annotation since it is not applied.

---

## Requirements — Feasibility

**Which overlays need changes?**
All three: `dev`, `stage`, `prod`. Each has two Ingress objects (`ingress-frontend.yaml` + `ingress-api.yaml`) = 6 files total.

**New Kubernetes resources required?**
No — annotation-only change for the recommended path. The `force-ssl-redirect` annotation is supported by ingress-nginx ≥0.22.

**Risk of breaking existing traffic during rollout?**
Low. Adding `force-ssl-redirect` to an already-HTTPS site is a no-op for compliant clients. The only breakage scenario: if some legitimate client or health-check hits HTTP and cannot follow a redirect. The `/health` endpoint on `ingress-api.yaml` (prod + stage) is the most likely candidate — confirm health check probes use HTTPS or can follow 301.

**Rollback feasibility:**
Remove the annotation and `kubectl apply` (or `make apply`). Instant rollback, no state to unwind.

---

## ADRs

**ADR-043-1: force-ssl-redirect annotation vs. tls: block**
Status: Proposed
Context: The ingress manifests lack TLS configuration. Two mechanisms can enforce HTTPS: an ingress-level `tls:` block (terminates TLS at ingress-nginx) or the `force-ssl-redirect` annotation (redirects HTTP clients to HTTPS, relies on upstream termination). SLAC's infrastructure model likely terminates TLS at a load balancer before the cluster.
Options considered:

| Option | Requires cert-manager? | Works with upstream LB? | Manifest complexity |
|---|---|---|---|
| `tls:` + cert-manager | Yes | Redundant double-TLS | High |
| `tls:` + pre-provisioned Secret | No (manual cert) | Possible but unusual | Medium |
| `force-ssl-redirect: "true"` annotation | No | Yes (designed for this) | Minimal |

Decision: Use `force-ssl-redirect: "true"` annotation on all six Ingress objects. This is the correct pattern when TLS terminates upstream of ingress-nginx. Document the upstream-LB assumption with an inline comment.
Consequences: If the upstream LB is ever bypassed (e.g., direct cluster access), HTTP would be redirected to HTTPS but the TLS cert would not be at the ingress. This is acceptable for the SLAC cluster topology. If the assumption is wrong, the fallback `tls:` path can be applied as a follow-up without reverting this change.

**ADR-043-2: apply to all overlays uniformly**
Status: Accepted
Context: Dev and stage overlays serve real OIDC credentials and Bearer tokens during testing. Applying the fix only to prod would leave credential exposure open in non-prod environments and create divergent infrastructure.
Decision: Apply `force-ssl-redirect` to all three overlays in the same PR. Each overlay uses its own hostname (`-dev`, `-stage`, no suffix for prod) so there is no cross-overlay risk.
Consequences: Slightly larger diff, but eliminates environment-specific security drift.

---

## Migration / Transition Path

**Zero downtime?** Yes. Adding an annotation to an Ingress causes ingress-nginx to reload its configuration (graceful reload, ~1s). Existing HTTPS connections are not interrupted.

**Rollout order:**
1. `dev` — validate redirect with `curl -I http://agent-knowledge-hub-dev.slac.stanford.edu/`
2. `stage` — repeat validation
3. `prod` — final, after stage passes

Each overlay can be applied and verified independently. No coordinated cutover needed.

**Rollback procedure:**
Remove the `force-ssl-redirect: "true"` annotation from the relevant Ingress files and run `make apply` (or `kubectl apply -k kubernetes/overlays/<env>/`). The ingress-nginx controller will reload within seconds.

---

## System / Infrastructure Design

### Manifest changes (annotation addition)

Apply to all six files. Representative diff for `kubernetes/overlays/prod/ingress-frontend.yaml`:

```diff
 metadata:
   name: agent-knowledge-hub-frontend
   annotations:
+    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
+    # TLS is terminated at the upstream SLAC load balancer.
+    # This annotation ensures all HTTP clients are redirected 301 → HTTPS.
+    # If upstream LB changes, add a tls: section and cert-manager annotation.
     nginx.ingress.kubernetes.io/auth-url: https://vouch.slac.stanford.edu/validate
```

Same diff pattern applies to `ingress-api.yaml` in all three overlays (minus the auth annotations, which differ per overlay).

### Files to edit

| File | Change |
|---|---|
| `kubernetes/overlays/dev/ingress-frontend.yaml` | Add 3-line annotation block |
| `kubernetes/overlays/dev/ingress-api.yaml` | Add 3-line annotation block |
| `kubernetes/overlays/stage/ingress-frontend.yaml` | Add 3-line annotation block |
| `kubernetes/overlays/stage/ingress-api.yaml` | Add 3-line annotation block |
| `kubernetes/overlays/prod/ingress-frontend.yaml` | Add 3-line annotation block |
| `kubernetes/overlays/prod/ingress-api.yaml` | Add 3-line annotation block |

### NetworkPolicy

No changes. Existing `network-policy-backend.yaml` restricts pod-to-pod traffic; this fix operates at the ingress-nginx layer and does not touch pod networking.

### Health check probe

`ingress-api.yaml` in `prod` and `stage` exposes `/health` (line 24-30 in prod, line 24-30 in stage). Verify that whatever external monitor or liveness probe hits this endpoint uses HTTPS, or can follow a 301. If a probe uses HTTP and cannot follow redirects, add a separate internal Service-level health path instead of routing through the Ingress.

---

## Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| `force-ssl-redirect` annotation only (no `tls:` block) | Zero new resources, works with upstream LB, instant rollback | Does not terminate TLS at the ingress — if upstream LB is bypassed, traffic is cleartext to ingress |
| Uniform application across dev/stage/prod | Consistent security posture, no environment drift | Slightly larger PR; dev redirect might surface issues in local port-forward workflows |
| Inline annotation comment documenting upstream LB | Future engineers understand intent without external docs | Adds ~3 lines per file (acceptable) |

---

## Delivery Slices

**Slice 1 — Dev overlay** (safe to ship independently)
Add `force-ssl-redirect: "true"` + comment to `kubernetes/overlays/dev/ingress-frontend.yaml` and `kubernetes/overlays/dev/ingress-api.yaml`. Apply and verify redirect.

**Slice 2 — Stage overlay**
Same change for `stage`. Verify `/health` endpoint probe still works after redirect.

**Slice 3 — Prod overlay**
Same change for `prod`. Final smoke test. Close this task.

Each slice is a 3-line annotation addition per file and can be PRed and deployed independently.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| External health-check/monitor hits HTTP and breaks on 301 | Medium | Low (monitoring noise, not user-facing) | Check all registered health-check URLs before applying to prod; switch to HTTPS endpoint |
| SLAC LB does NOT terminate TLS — HTTP served plaintext despite redirect | Low | High | Validate with `curl -v https://agent-knowledge-hub.slac.stanford.edu/` before closing; if TLS absent, escalate to add `tls:` block |
| Port-forward dev workflows break (local HTTP) | Low | Low (dev only) | `kubectl port-forward` bypasses ingress; unaffected |
| ingress-nginx version too old to support `force-ssl-redirect` | Very low | Medium | Annotation supported since ingress-nginx 0.22 (2019); verify controller version |

---

## Definition of Done

- [ ] Confirm with SLAC infra (or verify via `curl -v`) whether TLS is terminated upstream or at ingress
- [ ] `force-ssl-redirect: "true"` annotation added to all 6 Ingress files (dev + stage + prod, frontend + api)
- [ ] Inline comment added to each file documenting the TLS model
- [ ] `curl -I http://agent-knowledge-hub-dev.slac.stanford.edu/` returns `301` or `302` to `https://`
- [ ] `curl -I http://agent-knowledge-hub-stage.slac.stanford.edu/` returns `301` or `302`
- [ ] `curl -I http://agent-knowledge-hub.slac.stanford.edu/` returns `301` or `302`
- [ ] `/health` endpoint still reachable over HTTPS in prod and stage
- [ ] `kustomize build kubernetes/overlays/prod/` renders valid YAML with no errors
- [ ] No regression in VouchProxy OIDC auth flow (login → redirect → authenticated session)
- [ ] No regression in CLI Bearer JWT path (`/cli/api/...`)
- [ ] Task #035 (HSTS header) tracked as follow-on; `Strict-Transport-Security` header not required here
