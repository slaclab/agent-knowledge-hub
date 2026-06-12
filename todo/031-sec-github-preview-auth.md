# 031 — Security: Unauthenticated /api/github-preview Endpoint

**Status:** ✅ Complete
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H2)

---

## Phase 1 — Problem & Goal

### What is broken today

`GET /api/github-preview` (registered in `backend/app/routers/skills.py` at line 544) has **no authentication dependency**. The handler signature is:

```python
@github_router.get("/github-preview", response_model=GitHubPreviewOut)
@limiter.limit("10/minute")
async def github_preview(
    repo_url: str = Query(...),
    request: Request = None,   # note: = None is also a bug
):
```

Only IP-based rate limiting (10 req/min via `get_remote_address`) is applied. Every other mutating or sensitive endpoint in `skills.py` uses `Depends(get_current_user)` (e.g. `create_skill` at line 161, `refetch_skill` at line 319, `rate_skill_route` at line 215).

The endpoint calls `github_fetcher.fetch(repo_url)` which uses the server's GitHub PAT or GitHub App installation tokens (configured in `app.config.settings`). An unauthenticated attacker can:

1. **Information disclosure** — probe private/internal repos the GitHub App installation has access to (name, description, star count, visibility returned in `GitHubPreviewOut`).
2. **Rate-limit exhaustion** — burn the server's GitHub API quota (1000 req/hr for App tokens), blocking all legitimate scans and refetches.
3. **Org enumeration** — observe 200 vs 404 to determine which repos exist under `slaclab`.

The frontend BFF at `frontend/app/api/github-preview/route.ts` (line 15) uses a bare `fetch()` **without** `backendHeaders()`, so it omits both `X-Internal-Secret` and `X-Forwarded-User`. This means once the backend starts requiring auth, BFF calls will immediately return 401 unless fixed in the same deployment.

### Success criteria

- `GET /api/github-preview` without valid auth returns 401.
- Authenticated users (browser session via BFF, CLI via Bearer JWT) receive the same response as today — no regression.
- Frontend BFF forwards auth headers consistently with all other BFF routes.

### Out of scope

- Rate limit tuning (current 10/min per IP is retained as a defence-in-depth layer).
- Adding auth to `GET /api/skills` list (public catalog browse is intentionally unauthenticated).
- Changes to the GitHub token chain or `github_fetcher` internals.

### Constraints

- Must deploy via kustomize overlays (dev → stage → prod); no schema migration needed.
- Must not break CLI callers that send `Authorization: Bearer <jwt>` — Path 3 in `auth.py` already handles this.
- Must not break the Next.js BFF → backend trust path (Path 2: `X-Internal-Secret` + `X-Forwarded-User`).
- Two files change; both must be deployed together (backend change without frontend fix = broken UI; frontend fix without backend change = harmless but inconsistent).

---

## Phase 1.5 — User Stories

**US-1:** As a **logged-in SLAC user**, I want the github-preview feature to work after sign-in, so that I can preview a repo before submitting it as a skill.

**US-2:** As a **CLI user**, I want `GET /api/github-preview?repo_url=...` to succeed when I provide a valid Bearer JWT, so that CLI-based submission workflows are not broken.

**US-3:** As an **anonymous attacker**, I should receive a 401 when calling `/api/github-preview` without credentials, so that private repo metadata is not leaked.

**US-4:** As an **attacker attempting rate-limit exhaustion**, I should be blocked by both the 401 (no valid session) and the existing 10/min IP limiter, so that the server's GitHub quota is protected.

**US-5:** As an **org-enumeration attacker**, I should not be able to infer which repos exist under `slaclab` by sending unauthenticated probe requests, so that internal project names are not disclosed.

**US-6:** As a **backend developer**, I want `github_preview` to follow the same `Depends(get_current_user)` convention as every other sensitive endpoint in `skills.py`, so that new engineers do not copy an insecure pattern.

**US-7:** As a **frontend developer**, I want the github-preview BFF route to use `backendHeaders()` consistently with all other BFF routes (e.g. `frontend/app/api/skills/route.ts`), so that auth header injection is not accidentally omitted in future edits.

**US-8:** As a **platform operator**, I want the fix to require no config changes or secrets rotation, so that it can be deployed in a single kustomize rollout.

---

## Phase 2 — Requirements

### Functional Requirements

**FR-1:** `GET /api/github-preview` must reject unauthenticated requests with `HTTP 401 Authentication required`.

**FR-2:** Authenticated requests (Path 2: internal secret + forwarded user; Path 3: Bearer JWT) must continue to return `GitHubPreviewOut` as before.

**FR-3:** The Next.js BFF route `frontend/app/api/github-preview/route.ts` must attach `backendHeaders(request)` to the upstream fetch call, matching the pattern used by all other BFF routes.

**FR-4:** The `request: Request = None` default must be corrected to `request: Request` (required parameter) to prevent FastAPI from silently skipping rate-limit middleware.

### Non-Functional Requirements

**NFR-1 (Performance):** The auth check adds one synchronous HMAC `compare_digest` call (Path 2) or one in-memory JWT validation (Path 3). Both are sub-millisecond. Added latency must be < 2 ms p99.

**NFR-2 (Compatibility):** No change to the `GitHubPreviewOut` response schema. All existing callers that provide auth headers today are unaffected.

**NFR-3 (Observability):** `auth.py`'s existing `logger.warning` on auth failure already fires for the 401 path — no additional instrumentation needed.

### Acceptance Criteria

**AC-1:** Given an unauthenticated `GET /api/github-preview?repo_url=https://github.com/slaclab/foo`, when the request carries no `Authorization` header and no `X-Internal-Secret`, then the response status is 401 and the body contains `"Authentication required"`.

**AC-2:** Given a request with a valid `X-Internal-Secret` and a non-empty `X-Forwarded-User`, when `GET /api/github-preview` is called, then the response status matches the underlying GitHub fetch result (200 or 404) — same as pre-fix.

**AC-3:** Given a request with a valid `Authorization: Bearer <jwt>`, when `GET /api/github-preview` is called, then the response is identical to the pre-fix authenticated response.

**AC-4:** Given the Next.js BFF route `frontend/app/api/github-preview/route.ts`, when a browser session request arrives, then the upstream `fetch()` to the backend includes both `X-Internal-Secret` and `X-Forwarded-User` headers.

**AC-5:** The existing test suite passes without modification (no regressions in `test_auth.py`, `test_skill_crud.py`, etc.).

---

## Phase 3 — ADRs

**ADR-031-1: Require full auth (get_current_user) rather than optional auth (get_optional_user)**

Status: Accepted

Context: Two patterns exist in `skills.py` — `Depends(get_current_user)` (hard 401 on missing auth) and `Depends(get_optional_user)` (returns None, endpoint decides). The `github_preview` endpoint exposes server-held GitHub credentials so unauthenticated access is always wrong.

Options considered:
- `get_optional_user` + manual 401 if `user is None` — equivalent but adds dead code
- `get_current_user` — idiomatic, one line, consistent with `create_skill`, `refetch_skill`, etc.
- IP allowlist via NetworkPolicy only — insufficient; auth is required at the application layer too

Decision: Use `Depends(get_current_user)`. Simpler, consistent with existing pattern, no extra branch.

Consequences: CLI callers must send a Bearer JWT (they already do per `backend/app/auth.py` Path 3). Anonymous probes are rejected.

---

**ADR-031-2: Fix frontend and backend in the same deployment**

Status: Accepted

Context: The backend fix (add `Depends(get_current_user)`) and the frontend fix (add `backendHeaders()`) are in separate repos/containers. If only the backend is deployed, the UI breaks. If only the frontend is deployed, the fix is incomplete.

Options considered:
- Deploy backend first with a feature flag — over-engineered for a 2-file fix
- Deploy both in the same kustomize rollout — correct and minimal

Decision: Both changes ship as a single commit/deployment. The backend PR gates on the frontend BFF fix being included.

Consequences: One combined rollout. Rollback undoes both. No partial state window.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/routers/skills.py` | Modify | Add `user: User = Depends(get_current_user)` param to `github_preview` (line 547); fix `request: Request = None` → `request: Request` | Yes — pytest with mocked `get_current_user` dep |
| `frontend/app/api/github-preview/route.ts` | Modify | Import `backendHeaders` from `../_internal`; pass `headers: backendHeaders(request)` in the `fetch()` call | Yes — unit test with mocked `_internal` |
| `backend/tests/test_github_preview_auth.py` | New file | Two tests: unauthenticated → 401; authenticated (mocked secret) → 200 with mocked `github_fetcher` | Yes |

No schema changes. No config changes. No kustomize manifest changes.

---

## Phase 4 — System/Infrastructure Design

### Data flow — attack path (before fix)

```
Attacker
  |
  | GET /api/github-preview?repo_url=https://github.com/slaclab/secret-repo
  v
nginx ingress ──────────────────────────────────────────────────────────────>
  |   (NetworkPolicy allows ingress-nginx → backend:8000)
  v
backend:8000  /api/github-preview
  |  [only: @limiter.limit("10/minute") by remote IP]
  |  NO auth check
  v
github_fetcher.fetch(repo_url)  ← uses server PAT / App token
  v
GitHub API  →  returns private repo metadata
  v
Attacker receives: name, description, stars, visibility  ← INFORMATION LEAK
```

### Data flow — after fix

```
Attacker (no session)
  |
  | GET /api/github-preview?repo_url=...
  v
nginx ingress
  v
backend:8000  /api/github-preview
  |  [1] @limiter.limit("10/minute") by remote IP
  |  [2] Depends(get_current_user) ← NEW
  |      Path 2: X-Internal-Secret HMAC check  → no secret present → skip
  |      Path 3: Authorization Bearer            → no header present → skip
  |      → raise HTTP 401 "Authentication required"
  v
Attacker receives: 401  ← BLOCKED

Legitimate browser user (session via Next.js BFF)
  |
  | Browser → Next.js BFF /api/github-preview
  v
BFF route.ts
  |  backendHeaders(request)  ← NEW: injects X-Internal-Secret + X-Forwarded-User
  v
backend:8000  /api/github-preview
  |  Path 2: HMAC match + X-Forwarded-User present → User(user_id=...) returned
  |  → endpoint proceeds
  v
github_fetcher.fetch(repo_url) → GitHub API → 200 with metadata
```

### API contract: no change

The `GitHubPreviewOut` response schema is unchanged. The only visible change is that unauthenticated callers now receive 401 instead of 200/404.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Hard `get_current_user` (not optional) | Consistent with all other write endpoints; no accidental anonymous usage | Cannot later serve public previews without explicit code change |
| Ship backend + frontend together | No window where UI is broken | Requires coordinated deployment (mitigated: same repo, one PR) |
| Keep IP rate-limit alongside auth | Defence-in-depth; limits credential-stuffing attempts | Slightly higher complexity (two decorators on one endpoint) |
| No feature flag / gradual rollout | Minimal code change; reduces surface for mistakes | Cannot test in prod with subset of users (not needed for a 401 fix) |

---

## Phase 8 — Delivery Slices

**Slice 1 (required, ships first): Backend auth gate + frontend BFF fix**
- Add `user: User = Depends(get_current_user)` to `github_preview` in `backend/app/routers/skills.py`
- Fix `request: Request = None` → `request: Request`
- Add `backendHeaders(request)` to `frontend/app/api/github-preview/route.ts`
- Add `backend/tests/test_github_preview_auth.py` with 2 tests
- Deploy to dev overlay, smoke-test manually

**Slice 2 (optional, can follow): Rate-limit upgrade**
- Optionally tighten rate limit from 10/min (IP) to a per-user limiter using `user_id_key_func` (same pattern as `_flag_limiter` in `skills.py` line 39)
- This is defence-in-depth only; the 401 already stops unauthenticated abuse
- Safe to skip if timeline is tight

**Slice 3 (optional): Promote to stage/prod**
- Follows normal kustomize promotion after dev smoke-test passes

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Frontend BFF deployed without backend fix | Low | Low — auth remains absent, no regression | Single PR gates both changes |
| Backend deployed without frontend fix | Low | High — UI github-preview breaks for all users | Combined deployment in one PR; slice cannot be split |
| CLI callers break (no Bearer JWT sent) | Low | Medium — CLI submission workflows fail | CLI already sends `Authorization: Bearer` per `auth.py` Path 3; confirmed in `_validate_slac_jwt` |
| BFF `backendHeaders()` injects empty user (auth header not set by Vouch/oauth2-proxy) | Low | Medium — 401 for valid sessions | `backendHeaders()` already handles this edge case with multi-header fallback chain (lines 14-18 of `_internal.ts`); no code change needed |
| Test coverage gap — no existing test for the endpoint | Medium | Low — caught by AC-1/AC-2 in new test file | New test file required in Slice 1 |

---

## Phase 10 — Definition of Done

- [ ] `user: User = Depends(get_current_user)` added to `github_preview` in `backend/app/routers/skills.py`
- [ ] `request: Request = None` corrected to `request: Request` in same endpoint
- [ ] `frontend/app/api/github-preview/route.ts` imports `backendHeaders` and passes it to `fetch()`
- [ ] `backend/tests/test_github_preview_auth.py` created with:
  - [ ] Test: unauthenticated GET → 401
  - [ ] Test: authenticated GET (mocked internal secret path) → 200
- [ ] All existing backend tests pass (`pytest backend/tests/`)
- [ ] Manual smoke test on dev: unauthenticated curl returns 401; browser submit flow resolves github preview correctly
- [ ] Deployed to dev overlay via kustomize
- [ ] No regressions observed in stage promotion
