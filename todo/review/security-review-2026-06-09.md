# Security Review — Agent Knowledge Hub
*Reviewed: 2026-06-09 | Reviewers: Claude Opus (2 parallel agents) | Model: claude-opus-4-6*

---

## Status
**FAIL** — 3 HIGH findings are individually blocking. Must be resolved before next production deployment.

---

## Summary

20 findings across backend, frontend BFF, Kubernetes, and supply chain. The core JWT authentication logic is sound (JWKS rotation, RS256-only, proper claims validation). The main risk clusters are:

1. **Missing auth on two backend endpoints** — unauthenticated GitHub probing and ownership bypass on platform mutations
2. **Secret leaked to logs** — internal API secret written in plaintext on every `/api/me` call  
3. **No security headers** — no CSP, HSTS, or X-Frame-Options; clickjacking and XSS amplification risk
4. **Containers run as root** with no securityContext in prod Kubernetes manifests
5. **Supply chain** — mutable image tags in prod, no backend lockfile, package-lock.json untracked

---

## Issues

### HIGH

| # | Severity | Area | File | Description |
|---|----------|------|------|-------------|
| H1 | HIGH | authz | `backend/app/routers/skills.py:344–373` | **Missing ownership check on platform add/remove.** `POST /api/skills/{slug}/platforms` and `DELETE /api/skills/{slug}/platforms/{platform}` require auth but perform no ownership or admin check. Any authenticated user can add/remove platforms on any skill. Fix: add `if skill.submitter_id != user.user_id and not user.is_admin: raise HTTPException(403)` — identical to the check on `PATCH /api/skills/{slug}`. |
| H2 | HIGH | auth | `backend/app/routers/skills.py:544–566` | **Unauthenticated `/api/github-preview` uses server's GitHub credentials.** No `Depends(get_current_user)`. Attacker can probe private repos the GitHub App has access to, enumerate org repos, and exhaust the server's GitHub API rate limit. Fix: add `user: User = Depends(get_current_user)` — same pattern as `/api/scan`. |
| H3 | HIGH | data-protection | `frontend/app/api/me/route.ts:15` | **Internal API secret logged in plaintext on every request.** `JSON.stringify(outHeaders)` includes `"X-Internal-Secret": INTERNAL_SECRET`. Anyone with log access (ELK/Splunk/Loki) can forge requests to the backend as any user. Fix: redact before logging: `{ ...outHeaders, "X-Internal-Secret": "[REDACTED]" }` or remove the debug log entirely. |
| H4 | HIGH | kubernetes | `kubernetes/overlays/prod/backend-deployment.yaml`, `frontend-deployment.yaml` | **Containers run as root — no securityContext in either prod deployment.** Neither Dockerfile sets `USER` and neither manifest sets `runAsNonRoot`. A container escape gives the attacker root. Fix: add `securityContext: { runAsNonRoot: true, runAsUser: 1000, allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: { drop: ["ALL"] } }` to both deployments and `USER 1000` to both Dockerfiles. |
| H5 | HIGH | supply-chain | `kubernetes/overlays/prod/backend-deployment.yaml:17`, `frontend-deployment.yaml:17` | **Production images use mutable semver tags** (`0.2.0`). Tags can be overwritten in the registry; next pod restart pulls the replacement. Fix: pin to digest — `image: slaclab/agent-knowledge-hub-backend@sha256:<digest>`. Update via CI on release. |
| H6 | HIGH | headers | `frontend/next.config.mjs` | **No security headers.** No CSP, X-Frame-Options, X-Content-Type-Options, HSTS, or Referrer-Policy. Enables clickjacking, MIME-sniffing, and amplifies any future XSS. Fix: add `headers()` to `next.config.mjs` with at minimum `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security: max-age=63072000; includeSubDomains`. |
| H7 | HIGH | supply-chain | `backend/requirements.txt` | **No lockfile — non-reproducible Python builds.** Unpinned constraints (`fastapi>=0.111.0` etc.) pull whatever is latest at build time. Fix: generate `requirements.lock` with `pip-compile --generate-hashes` and use `pip install --require-hashes -r requirements.lock` in Dockerfile. |

### MEDIUM

| # | Severity | Area | File | Description |
|---|----------|------|------|-------------|
| M1 | MEDIUM | auth | `backend/app/main.py:81–87` | **CORS: `allow_origins=["*"]` with `allow_credentials=True`.** FastAPI/Starlette reflects the requesting Origin with credentials when both are set, making any origin able to issue credentialed requests. Fix: replace `["*"]` with `["https://agent-knowledge-hub.slac.stanford.edu", "http://localhost:3000"]`. |
| M2 | MEDIUM | secrets | `backend/app/config.py:41–47` | **`internal_api_secret` has no minimum length validation.** A weak secret (e.g. `"test"`) is accepted, making forged `X-Forwarded-User` trivial to produce. Fix: enforce minimum 32 chars in the validator. |
| M3 | MEDIUM | auth | `backend/app/routers/skills.py:158–170` | **No rate limit on `POST /api/skills` (skill creation).** An authenticated attacker can create thousands of skills, exhausting GitHub API quota, MongoDB connections, and cache. Fix: add `@limiter.limit("10/hour")`. |
| M4 | MEDIUM | validation | `backend/app/schemas/skill.py:28–41` | **`SkillCreate.repo_url` accepts arbitrary strings.** No URL format validation; non-GitHub URLs are stored raw and served to API consumers. Fix: add a `field_validator` enforcing `^https://github\.com/[^/]+/[^/]+`. |
| M5 | MEDIUM | xss | `frontend/components/readme-render.tsx:11` | **DOMPurify default config allows `<style>` tags and inline CSS.** An attacker controlling README content can inject CSS that overlays fake UI (phishing) or exfiltrates data via `background-image: url(attacker.com/...)`. Fix: `DOMPurify.sanitize(html, { FORBID_TAGS: ['style'], FORBID_ATTR: ['style'] })`. |
| M6 | MEDIUM | kubernetes | `frontend/` manifests | **Frontend pods have no NetworkPolicy.** Any pod in the cluster can reach the frontend on port 3000 and send forged auth headers. Fix: add namespace-wide default-deny + explicit allow from `ingress-nginx` namespace only. |
| M7 | MEDIUM | kubernetes | `kubernetes/overlays/dev/mongodb/mongo.yaml:8` | **`allowUnsafeConfigurations: true` on dev MongoDB operator.** May disable auth and TLS between replicas. Remove this flag or ensure the dev cluster is fully isolated. |
| M8 | MEDIUM | frontend-bff | `/frontend/app/api/admin/*/route.ts` (all admin routes) | **Admin BFF routes have no BFF-layer auth check** — entirely rely on backend rejection. Defense-in-depth: add a middleware check that validates user presence before proxying admin requests. |
| M9 | MEDIUM | data-protection | `frontend/app/api/me/route.ts:8–19`, `frontend/app/api/_internal.ts:20–28` | **Verbose debug logging leaks user identity and full headers in production.** Gate behind `process.env.NODE_ENV !== 'production'` check. |
| M10 | MEDIUM | frontend-bff | All `frontend/app/api/` routes | **No rate limiting on any frontend API routes.** Backend slowapi limits are bypassed; attacker can flood the Next.js event loop. Fix: add `nginx.ingress.kubernetes.io/limit-rps` annotation or a token-bucket middleware. |
| M11 | MEDIUM | kubernetes | `kubernetes/overlays/prod/ingress-*.yaml` | **No TLS section in ingress manifests.** Add `tls:` block or at minimum `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"` annotation. |

### LOW

| # | Severity | Area | File | Description |
|---|----------|------|------|-------------|
| L1 | LOW | auth | `backend/app/routers/health.py:9–16` | Health endpoint creates a new MongoDB connection per request (unauthenticated, no rate limit). Reuse the Beanie connection pool. |
| L2 | LOW | validation | `backend/app/auth.py:102–119` | `X-Forwarded-User` value not validated for format. Add `re.match(r"^[a-z0-9._-]{1,64}$", forwarded_user)`. |
| L3 | LOW | data-protection | `backend/app/auth.py:91–95` | Debug log level is default in production. Change `LOG_LEVEL` default to `INFO`. |
| L4 | LOW | data-protection | `backend/Dockerfile:12` | `--log-level debug` hardcoded in CMD. Use env var instead. |
| L5 | LOW | frontend-bff | `frontend/app/api/admin/labels/[...path]/route.ts:19` | Path segments in catch-all route joined without `encodeURIComponent` — potential URL injection. Fix: `params.path.map(encodeURIComponent).join("/")`. |
| L6 | LOW | frontend-bff | `frontend/app/api/_internal.ts:4` | `INTERNAL_API_SECRET` defaults to empty string — silent misconfiguration. Fail fast at startup if unset in production. |
| L7 | LOW | authz | `backend/app/routers/skills.py:531–536` | Provenance cache keyed only by `skill_id`, not `(skill_id, viewer_authenticated)`. Rare race could expose authenticated view to unauthenticated caller. |

### INFO

| # | Severity | Area | File | Description |
|---|----------|------|------|-------------|
| I1 | INFO | validation | `backend/app/schemas/skill.py:40` | `source_type: str` accepts arbitrary values. Use `Literal["github", "local"]`. |
| I2 | INFO | supply-chain | `frontend/package-lock.json` | Listed in `.gitignore` (untracked). Commit it for reproducible frontend builds. |
| I3 | INFO | kubernetes | prod vs dev manifests | Image tags in prod manifests (`0.2.0`) don't match actual version (`0.17.0`). Signs of gitops drift — verify what's actually deployed. |

---

## Positive findings

The core security model is solid in several areas:
- JWT validation: JWKS rotation, RS256-only (no algorithm confusion), issuer/audience checks, expiry enforced, required claims validated
- `hmac.compare_digest` on internal secret (timing-attack safe)
- `require_admin` as a router-level `Depends` dependency (can't accidentally be bypassed per-route)
- MongoDB injection: Beanie ODM prevents most vectors; label search uses `re.escape()` before `$regex`
- Cursor decoding validates ObjectId format with anchored regex
- `skill_path` validation rejects `..` traversal
- Rate limiting applied to most scan and write-heavy endpoints

---

## Recommended fix order

1. **H3 first** — secret in logs is a live exposure. One-line fix, zero risk.
2. **H1 + H2** — both backend auth gaps, small diffs.
3. **M1** — CORS fix, small diff.
4. **H6** — security headers in `next.config.mjs`, no logic change.
5. **M5** — DOMPurify config, one-line fix.
6. **H4** — securityContext in K8s manifests + USER in Dockerfiles.
7. **H7 + I2** — lockfile generation (build system change, needs testing).
8. **H5** — digest pinning (CI pipeline work).
9. Remaining MEDIUM/LOW in priority order.

---

## Decisions Required

**D1 (M8 — admin BFF auth):** Should the Next.js BFF validate admin status independently, or is relying on the backend as the sole enforcement point acceptable given the internal network is not Zero Trust? If acceptable, document the decision.

**D2 (M11 — TLS in ingress):** Is TLS terminated at a layer above (e.g. cluster-wide cert-manager default, or an upstream load balancer)? If so, add a comment to the ingress manifests stating this. If not, the `tls:` section is blocking.

**D3 (H7 — lockfile):** Switch backend from `requirements.txt` to `uv.lock` (preferred) or `pip-compile` output? This is a build system change — needs team agreement on tooling.

---

## Sources

- `backend/app/auth.py`, `config.py`, `main.py`
- `backend/app/routers/` (all 9 files)
- `backend/app/services/` (all 11 files)
- `backend/app/schemas/`, `models/`
- `frontend/app/api/` (all BFF route files)
- `frontend/lib/auth.tsx`, `api.ts`
- `frontend/components/readme-render.tsx`, `submit-form.tsx`, `edit-form.tsx`
- `frontend/next.config.mjs`
- `kubernetes/overlays/prod/` and `dev/` (all manifests)
- `backend/pyproject.toml`, `requirements.txt`, `Dockerfile`
- `frontend/package.json`, `Dockerfile`
