# 044 — Security: Low-Severity Hardening (L1–L7)

**Status:** ✅ Complete (L6 deferred — see note)
**Severity:** LOW (batch)
**Source:** Security review 2026-06-09 (L1–L7, I1–I3)

---

## Problem & Goal

### What is broken today (specific)

Seven low-severity findings from the 2026-06-09 security review create minor, concrete attack surface:

- **L1** `backend/app/routers/health.py:12` — every `GET /health` call instantiates a new `AsyncIOMotorClient`, bypassing the Beanie connection pool entirely. An unauthenticated flood exhausts MongoDB connections with no rate limit on this endpoint.
- **L2** `backend/app/auth.py:105` — `forwarded_user = request.headers.get("X-Forwarded-User", "")` is used directly as `user_id` (line 116) without format validation. A header value containing null bytes (`\x00`), newlines, or >128 chars reaches the DB query and downstream logs without sanitisation.
- **L3** `backend/app/main.py:26` — `os.environ.get("LOG_LEVEL", "DEBUG")` defaults to DEBUG. `auth.py:91–95` logs all incoming headers at DEBUG level on every request, producing verbose output in production containers.
- **L4** `backend/Dockerfile:12` — `CMD` hardcodes `--log-level debug` for uvicorn, overriding any `LOG_LEVEL` env var set in the Kubernetes deployment manifest.
- **L5** `frontend/app/api/admin/labels/[...path]/route.ts:19` — `params.path.join("/")` is used bare in the URL string. Path segments with `#`, `?`, `%`, or spaces are not encoded, enabling URL injection into the backend proxy request.
- **L6** `frontend/app/api/_internal.ts:4` — `process.env.INTERNAL_API_SECRET ?? ""` silently falls back to empty string. The backend (`auth.py:104`) uses `hmac.compare_digest`, so an empty secret still matches an empty incoming header — misconfiguration is invisible until something breaks.
- **L7** `backend/app/routers/skills.py:534` — provenance cache key is `str(skill.id)` only. Line 536 always builds the tree with `viewer_authenticated=True` and caches it. If an unauthenticated request is the first caller, it gets the unauthenticated tree cached; if an authenticated request arrives first, a subsequent unauthenticated caller briefly receives the authenticated view from cache.

I1 (`source_type` Literal) is handled in #040. I3 (prod image tag) is handled in #034.

### Success after the fix

- `/health` reuses the Beanie connection pool; no new motor clients created per-request.
- Malformed `X-Forwarded-User` values are rejected with HTTP 401 before reaching any downstream code.
- Production containers log at INFO by default; DEBUG only when explicitly configured.
- Frontend labels proxy correctly percent-encodes path segments.
- Missing `INTERNAL_API_SECRET` in production causes a hard startup failure, not silent degradation.
- Provenance cache is keyed by `(skill_id, viewer_authenticated)` — no cross-visibility cache leaks.

### Out of scope

- Rate-limiting `/health` (separate concern; NetworkPolicy already restricts access).
- Moving `INTERNAL_API_SECRET` to a new secret store — it is already sourced from Vault via Kubernetes secret.
- Any changes to auth paths 1 or 3.

### Constraints

- Must not break existing auth flow (paths 2 and 3 in `auth.py`).
- All changes deploy via kustomize; no new Kubernetes resources required.
- `package-lock.json` commit (I2) is a separate git operation; no test changes needed.

---

## Findings

### L1 — Health endpoint creates new MongoDB connection per request
**File:** `backend/app/routers/health.py:9–16`
Unauthenticated, no rate limit, creates a new `AsyncIOMotorClient` each call. Flood this endpoint to exhaust MongoDB connections.
**Fix:** Reuse the Beanie connection — replace with `await Skill.find_one()` or `await asyncio.wait_for(Motor.ping(), timeout=2)` using the existing client.

### L2 — X-Forwarded-User header value not validated for format
**File:** `backend/app/auth.py:102–119`
Header value is used as `user_id` without format validation — could contain null bytes, newlines, very long strings.
**Fix:** `if not re.match(r"^[a-z0-9._\-@]{1,128}$", forwarded_user): raise HTTPException(401)`

### L3 — Default LOG_LEVEL is DEBUG in production
**File:** `backend/app/main.py:26`, `backend/app/auth.py`
Auth module logs all incoming headers at DEBUG level. In production the default `LOG_LEVEL` should be `INFO`.
**Fix:** Change default to `INFO` in `config.py`. Debug-level header logging in `auth.py` is then silenced.

### L4 — Backend Dockerfile hardcodes `--log-level debug`
**File:** `backend/Dockerfile:12`
CMD hardcodes `--log-level debug` — overrides any env var.
**Fix:** Remove `--log-level` from CMD, let uvicorn inherit from `LOG_LEVEL` env var via the app startup.

### L5 — Path segments in catch-all admin labels route joined without encodeURIComponent
**File:** `frontend/app/api/admin/labels/[...path]/route.ts:19`
`params.path.join("/")` doesn't encode special URL characters in segments.
**Fix:** `params.path.map(encodeURIComponent).join("/")`

### L6 — INTERNAL_API_SECRET defaults to empty string in frontend
**File:** `frontend/app/api/_internal.ts:4`
`process.env.INTERNAL_API_SECRET ?? ""` — silent misconfiguration if env var not set.
**Fix:** Fail fast at startup: `if (!process.env.INTERNAL_API_SECRET && process.env.NODE_ENV === "production") throw new Error("INTERNAL_API_SECRET must be set in production")`

### L7 — Provenance cache keyed only by skill_id, not (skill_id, viewer_authenticated)
**File:** `backend/app/routers/skills.py:531–536`
Rare race: unauthenticated request could briefly get authenticated view from cache.
**Fix:** Key the `@ttl_cache` by `(slug, bool(user is not None))`.

### I1 — source_type accepts arbitrary strings
**File:** `backend/app/schemas/skill.py:40`
Use `Literal["github", "local"]` — covered in #040 (do at same time).

### I2 — package-lock.json not committed
**File:** `frontend/.gitignore`
Remove `package-lock.json` from `.gitignore` and commit it.

### I3 — Prod/dev image tag drift
**File:** `kubernetes/overlays/prod/*-deployment.yaml`
Prod manifests reference `0.2.0`, actual version is `0.17.0`. Covered by #034.

---

## Phase 1.5 — User Stories

**US-1:** As an attacker, I want to flood `/health` with concurrent requests, so that I can exhaust MongoDB connections and cause a denial of service — **prevented by L1 fix.**

**US-2:** As an attacker, I want to inject a header value like `X-Forwarded-User: admin\x00evil` so that it bypasses downstream string comparisons — **prevented by L2 fix.**

**US-3:** As a developer, I want production containers to log at INFO by default, so that auth header contents are not leaked to log aggregators in production.

**US-4:** As a platform engineer, I want the Docker CMD to respect the `LOG_LEVEL` env var, so that I can control logging verbosity from the Kubernetes deployment manifest without rebuilding the image.

**US-5:** As an attacker with admin access to the labels UI, I want to craft a label name containing `?injected=true` so that the BFF proxy appends attacker-controlled query parameters to the backend URL — **prevented by L5 fix.**

**US-6:** As a developer mis-deploying the frontend, I want the app to refuse to start if `INTERNAL_API_SECRET` is unset in production, so that I discover the misconfiguration immediately rather than silently accepting any caller as authenticated.

**US-7:** As an unauthenticated user, I want the provenance tree to only show me public information, so that a cache populated by an authenticated user does not leak private provenance data to me.

**US-8:** As an authenticated API consumer, I want the `/health` endpoint to reflect real DB connectivity without degrading shared connection pool performance.

**US-9:** As an admin, I want label management operations with special characters in label names to route correctly through the BFF proxy, so that labels containing spaces or special chars work end-to-end.

**US-10:** As a security auditor, I want all seven low findings remediated in a single deployable batch, so that the security posture improves without prolonged open findings.

---

## Phase 2 — Requirements

### Functional requirements (FR)

**FR-1 (L1):** `/health` MUST use the Beanie/Motor connection pool — no `AsyncIOMotorClient` instantiation per request.

**FR-2 (L2):** `X-Forwarded-User` header value in `auth.py` path 2 MUST be validated against `^[a-z0-9._\-@]{1,128}$` before use; non-conforming values MUST return HTTP 401.

**FR-3 (L3):** `LOG_LEVEL` default in `main.py` MUST change from `"DEBUG"` to `"INFO"`.

**FR-4 (L4):** `backend/Dockerfile` CMD MUST NOT include `--log-level`; uvicorn log level MUST be controlled solely by the `LOG_LEVEL` env var passed in.

**FR-5 (L5):** Every path segment in `frontend/app/api/admin/labels/[...path]/route.ts` MUST be percent-encoded via `encodeURIComponent` before URL construction.

**FR-6 (L6):** `frontend/app/api/_internal.ts` MUST throw at module load time when `INTERNAL_API_SECRET` is absent in a `production` `NODE_ENV`.

**FR-7 (L7):** Provenance cache key MUST include a boolean `viewer_authenticated` component, producing independent cache entries for authenticated and unauthenticated viewers.

**FR-8 (I2):** `package-lock.json` MUST be removed from `frontend/.gitignore` and committed to the repository.

### Non-functional requirements (NFR)

**NFR-1 (performance):** L1 fix adds ≤1 ms latency to `/health` (Beanie ping is a single in-pool command vs. a new TCP handshake — net improvement expected).

**NFR-2 (compatibility):** L2 regex allows all real GitHub usernames and SLAC email-style identifiers; no valid existing user is rejected.

**NFR-3 (compatibility):** L3/L4 changes do not affect dev environments — `LOG_LEVEL=DEBUG` in `.env` or Kubernetes dev overlay restores debug output.

**NFR-4 (compatibility):** L5 does not change the semantic path — `encodeURIComponent` is idempotent on segments that contain only alphanumeric chars (existing label names).

**NFR-5 (startup):** L6 check runs at Next.js module load time (top-level `if` block) — no runtime performance cost.

**NFR-6 (correctness):** L7 cache fix doubles the maximum cache entries for provenance (two entries per skill), still within `maxsize=512`.

### Acceptance criteria (AC)

**AC-1:** Given a running backend, when `GET /health` is called 100 times in 1 second, then `db.admin.command("ping")` is called via the existing motor client, not via new `AsyncIOMotorClient` instances.

**AC-2:** Given path 2 auth is enabled, when `X-Forwarded-User: admin\x00evil` is sent with a valid secret, then the backend returns HTTP 401.

**AC-3:** Given `LOG_LEVEL` is not set, when the backend container starts, then `logging.root.level` is INFO and no DEBUG lines appear in uvicorn output.

**AC-4:** Given `LOG_LEVEL=DEBUG` in the Kubernetes dev overlay, when the backend starts, then DEBUG log lines appear — confirming env var is now the sole control.

**AC-5:** Given a label name of `foo?bar=baz`, when the frontend proxies a GET request, then the backend receives `/api/admin/labels/foo%3Fbar%3Dbaz`, not `/api/admin/labels/foo?bar=baz`.

**AC-6:** Given `NODE_ENV=production` and `INTERNAL_API_SECRET` unset, when the Next.js server starts, then it throws `Error: INTERNAL_API_SECRET must be set in production` before serving any requests.

**AC-7:** Given an unauthenticated request hits `/api/skills/{slug}/provenance` after an authenticated request has populated the cache, then the response contains only the unauthenticated view (no private entries).

**AC-8:** `package-lock.json` is present and tracked in the `frontend/` directory in git.

---

## Phase 3 — ADRs

**ADR-044-1: Use Beanie model ping for /health rather than raw Motor admin command**
Status: Accepted
Context: Health endpoint needs a real DB liveness check without introducing new connections. Two options: `Skill.find_one()` (reads a document) vs. `motor_client.admin.command("ping")` reusing the existing client.
Options considered:
- `Skill.find_one()` — uses the Beanie-managed connection, exercises ODM stack, adds ≤1 ms, returns a real document.
- `motor_client.admin.command("ping")` — lighter, needs importing the module-level client from `main.py`; creates a coupling between health.py and main.py internals.
Decision: Use `await asyncio.wait_for(get_motor_client().admin.command("ping"), timeout=2)` by exposing a `get_motor_client()` accessor in `main.py`, keeping health.py decoupled from Beanie models.
Consequences: Small coupling to `main.py` accessor; timeout behaviour is explicit and testable.

**ADR-044-2: Fail-fast on missing INTERNAL_API_SECRET at module load, not request time**
Status: Accepted
Context: Silent empty-string fallback means misconfigured deployments serve requests without the intended HMAC secret check. Failing at module load surfaces the error immediately in pod startup logs, causing the pod to crash-loop and alert operators before traffic is served.
Options considered:
- Warn at startup (log only) — does not prevent silent degradation.
- Fail at request time — first request fails but subsequent debugging is harder.
- Fail at module load — pod never becomes Ready; Kubernetes restarts it; operator sees CrashLoopBackOff immediately.
Decision: Throw at module load when `NODE_ENV === "production"`.
Consequences: Local development with `NODE_ENV=production` (rare) must explicitly set the variable; dev/test environments are unaffected because `NODE_ENV` defaults to `development`.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/routers/health.py` | Refactor | Remove `AsyncIOMotorClient` instantiation; import and call a `get_motor_client()` accessor or use Beanie ping | Yes — mock motor client in unit test |
| `backend/app/main.py` | Addition | Export `get_motor_client()` returning the `AsyncIOMotorClient` created in `lifespan` | Yes — unit test accessor returns same client |
| `backend/app/auth.py:105–118` | Bug fix | Add `re.match` format check on `forwarded_user` before use; raise HTTP 401 on mismatch | Yes — unit tests for valid/invalid header values |
| `backend/app/main.py:26` | Config fix | Change default from `"DEBUG"` to `"INFO"` | Yes — test that missing env var yields INFO level |
| `backend/Dockerfile:12` | Config fix | Remove `--log-level debug` from CMD | Yes — build image, inspect CMD |
| `frontend/app/api/admin/labels/[...path]/route.ts:19,24,28,32` | Bug fix | `params.path.map(encodeURIComponent).join("/")` on all four HTTP method handlers | Yes — unit test URL construction with special chars |
| `frontend/app/api/_internal.ts:4` | Hardening | Replace `?? ""` with a startup guard that throws when `NODE_ENV === "production"` | Yes — test with `NODE_ENV=production` and missing var |
| `backend/app/routers/skills.py:534` | Bug fix | Change cache key from `str(skill.id)` to `(str(skill.id), viewer is not None)` | Yes — unit test with authenticated/unauthenticated callers |
| `frontend/.gitignore` | Config fix | Remove `package-lock.json` line | N/A |

---

## Phase 4 — System/Infrastructure Design

### L1: Health endpoint data flow (before / after)

```
BEFORE:
  GET /health
    → health.py:12  AsyncIOMotorClient(settings.mongo_uri)   ← NEW TCP connection each call
    → client.admin.command("ping")
    → client is garbage-collected (connection not returned to pool)

AFTER:
  GET /health
    → health.py     get_motor_client().admin.command("ping")  ← shared pool connection
    → returns {"status": "ok"} or "degraded"
```

### L2: X-Forwarded-User validation intercept

```
Request:  X-Internal-Secret: <valid>  X-Forwarded-User: <value>
                    │
           auth.py:104  hmac.compare_digest  → match
                    │
           [NEW] re.match(r"^[a-z0-9._\-@]{1,128}$", forwarded_user)
                    │
            ┌───────┴────────┐
           FAIL             PASS
            │                │
        HTTP 401         User(user_id=forwarded_user, ...)
```

### L6: Startup guard (frontend)

```
_internal.ts module load:
  if (!INTERNAL_API_SECRET && NODE_ENV === "production")
    throw Error("INTERNAL_API_SECRET must be set in production")
  ↓
  Pod: CrashLoopBackOff  ← operator alerted immediately
```

### L7: Provenance cache key

```
BEFORE:  cache_key = str(skill.id)
         → slot shared across all viewers

AFTER:   cache_key = (str(skill.id), viewer is not None)
         → slot["abc123", True]   authenticated tree
         → slot["abc123", False]  unauthenticated tree
```

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| L1: Reuse pool via accessor vs. `Skill.find_one()` | Minimal overhead; no document deserialization | Accessor creates slight coupling between health.py and main.py |
| L2: Regex allowlist vs. blocklist | Predictable, tight surface; null bytes and newlines rejected by default | Very long SLAC email-style usernames (>128 chars) would break — adjust limit if needed |
| L3/L4: Default INFO via env var only | Ops can tune without rebuild; consistent with 12-factor | Devs must explicitly set `LOG_LEVEL=DEBUG`; silent to them if forgotten |
| L6: Crash at module load vs. warn | Immediate operator visibility; no silent degraded state | Any environment running `NODE_ENV=production` without the secret breaks — intentional |
| L7: Two cache slots per skill | No cross-visibility leaks | Cache capacity per skill halved; `maxsize=512` still sufficient for expected load |

---

## Phase 8 — Delivery Slices

All fixes are independent one-liners or small patches. They can be grouped into up to 3 PRs:

**Slice A — Backend hardening (L1, L2, L3, L7)**
Files: `health.py`, `main.py`, `auth.py`, `skills.py`
Safe to ship alone: yes — no frontend or k8s changes.

**Slice B — Docker / config fixes (L4)**
Files: `backend/Dockerfile`
Safe to ship alone: yes — requires new image build and deploy; no code changes.
Note: Slice A (L3) should land before or with Slice B so the env var default and uvicorn flag are consistent.

**Slice C — Frontend fixes + package-lock (L5, L6, I2)**
Files: `frontend/app/api/admin/labels/[...path]/route.ts`, `frontend/app/api/_internal.ts`, `frontend/.gitignore`, `frontend/package-lock.json`
Safe to ship alone: yes — pure frontend; backend unchanged.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| L2 regex rejects a valid SLAC username | Low | Medium — locked-out user | Test against known username corpus before shipping; pattern allows dots, hyphens, `@` |
| L4 Dockerfile change ships without matching k8s `LOG_LEVEL` env var in dev overlay | Low | Low — dev gets INFO logs until they add the var | Add `LOG_LEVEL: DEBUG` to dev overlay before or in same PR |
| L6 startup throw fires in a CI environment running `NODE_ENV=production` | Low | Low — CI fails noisily | Set `INTERNAL_API_SECRET=ci-placeholder` in CI env; or check `NODE_ENV !== "test"` as additional guard |
| L7 cache key change doubles cold-start misses during first deploy | Very Low | Negligible | TTL is 300 s; cache warms in seconds under normal load |

---

## Implementation Plan

- [ ] L1: Fix health endpoint to reuse connection pool
- [ ] L2: Add format validation to `X-Forwarded-User` in `auth.py`
- [ ] L3: Change default `LOG_LEVEL` to `INFO` in `main.py`
- [ ] L4: Remove `--log-level debug` from `backend/Dockerfile` CMD
- [ ] L5: Add `encodeURIComponent` to catch-all route path join
- [ ] L6: Add startup check for `INTERNAL_API_SECRET` in production
- [ ] L7: Change provenance cache key to `(skill_id, viewer_is_authenticated)`
- [ ] I2: Remove `package-lock.json` from `frontend/.gitignore`, commit it

---

## Phase 10 — Definition of Done

- [ ] L1: Unit test confirms no new `AsyncIOMotorClient` created on `/health` call; existing health tests pass
- [ ] L2: Unit tests for valid usernames (pass) and null-byte / long-string / newline values (401)
- [ ] L3: Test that `LOG_LEVEL` unset → root logger at INFO level
- [ ] L4: Docker CMD verified (no `--log-level` flag); smoke test: container starts, logs at INFO
- [ ] L5: Unit test that path segment `foo?bar=1` is encoded to `foo%3Fbar%3D1` in the proxied URL
- [ ] L6: Integration/unit test: `NODE_ENV=production`, `INTERNAL_API_SECRET` unset → module throws
- [ ] L7: Unit test: unauthenticated caller after authenticated cache-fill receives unauthenticated tree
- [ ] I2: `git ls-files frontend/package-lock.json` returns the file
- [ ] All existing backend tests pass (`pytest -x`)
- [ ] All existing frontend lint/type checks pass (`npm run lint && tsc --noEmit`)
- [ ] Manual smoke test: `/health` returns `{"status": "ok"}`; admin labels UI works; provenance page loads
- [ ] Deployed to dev overlay; no regressions observed in pod logs

## Acceptance Criteria

- [ ] `/health` no longer creates new connections per request
- [ ] Malformed `X-Forwarded-User` returns 401
- [ ] Production containers log at INFO by default
- [ ] Labels catch-all route encodes path segments
- [ ] Missing `INTERNAL_API_SECRET` fails fast in production
- [ ] `package-lock.json` committed to repo
