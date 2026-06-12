# 039 — Security: Rate Limit Skill Creation Endpoint

**Status:** ✅ Complete
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M3)

---

## Problem & Goal

### What is broken today

`POST /api/skills` (line 158 of `backend/app/routers/skills.py`) has **no `@limiter.limit()` decorator** and no `request: Request` parameter. An authenticated attacker can issue unlimited parallel creation requests.

Each creation call:
1. Writes a MongoDB document with `readme_html`, `skill_md_raw`, `file_manifest`, and a `SkillRevision` — unbounded storage growth.
2. Calls `skill_repository.create()` which internally calls `github_fetcher.fetch()` and `github_scanner.scan()` — two outbound GitHub API calls per request, burning the shared App token quota.
3. Clears `_count_cache` on every insert (see `skill_service.py`), serialising all catalog reads.

Compare: `POST /api/skills/{slug}/flag` (line 228) uses `@_flag_limiter.limit("10/hour")` with `user_id_key_func`; `POST /api/skills/{slug}/rate` (line 212) uses `@limiter.limit("30/minute")` with `get_remote_address`. Creation is more expensive than both yet is unprotected.

**Critical additional issue:** The `limiter` instance in `skills.py` (line 38) uses `get_remote_address`. Behind the Next.js BFF, all browser requests share one source IP (the frontend pod). An IP-based limit would throttle *all users* together. The fix must use `user_id_key_func` (already defined in `auth.py` line 158) so limits are per authenticated user — matching the approach in `_flag_limiter`.

### What success looks like

- Any single authenticated user cannot submit more than 10 skills per hour.
- Admins are subject to the same limit (they can override counts via admin endpoints if needed).
- The 429 response includes a standard `Retry-After` header (slowapi default).
- All existing callers (frontend BFF, CLI) continue to work without change.

### Out of scope

- Rate-limiting `PATCH /api/skills/{slug}` (update) — lower risk, no GitHub I/O on every update.
- A per-skill-creation cost model or quota system.
- Admin bypass / exemption from rate limits.

### Constraints

- Must not change auth flow — `get_current_user` dependency stays in place.
- Deploy path is kustomize overlays; no new config keys needed (slowapi uses in-memory storage by default).
- `request: Request` must be added as the **first** parameter to avoid slowapi decorator ordering bugs.

---

## User Stories

1. As a **developer**, I want to submit a new skill to the catalog, so that my tool is discoverable by the SLAC community.
2. As a **developer**, I want a clear 429 error with a `Retry-After` header when I've hit the limit, so that I know when to retry.
3. As an **API consumer (CLI)**, I want my Bearer JWT requests to be rate-limited by my own identity, not by a shared IP, so that other CLI users' submissions don't consume my quota.
4. As an **attacker with a valid SLAC account**, I want to be prevented from bulk-creating thousands of junk skills, so that the attack surface is minimised.
5. As an **attacker**, I want to exhaust the shared GitHub App token, so that legitimate fetches fail — this fix prevents using the creation endpoint to do so.
6. As an **admin**, I want assurance that a single compromised account cannot flood the catalog, so that moderation workload stays manageable.
7. As the **platform operator**, I want MongoDB and GitHub API usage bounded per user per hour, so that the cluster does not incur runaway costs.
8. As a **frontend user**, I want my skill submissions to succeed under normal use, so that the rate limit does not affect typical day-to-day workflows.

---

## Requirements

### Functional Requirements

**FR-1:** `POST /api/skills` must be decorated with a per-user rate limit of **10 requests per hour**.

**FR-2:** The limiter key function must be `user_id_key_func` (from `app.auth`) so limits are scoped to `user:{user_id}`, not remote IP.

**FR-3:** A `_create_limiter = Limiter(key_func=user_id_key_func)` instance must be added in `skills.py` (analogous to `_flag_limiter` on line 39) — reusing the IP-based `limiter` is incorrect for this endpoint.

**FR-4:** `request: Request` must be added as the first positional parameter in `create_skill` (slowapi requires it; currently absent at line 159).

**FR-5:** The 429 response body produced by slowapi's `_rate_limit_exceeded_handler` must be returned as-is (no custom response needed).

### Non-Functional Requirements

**NFR-1 (Performance):** The decorator adds negligible latency (<1 ms); the in-memory counter lookup is O(1). Total overhead must be <5 ms.

**NFR-2 (Compatibility):** Existing callers (Next.js BFF via `X-Internal-Secret`, CLI via Bearer JWT) pass `request` through ASGI — no changes required in frontend or CLI code.

**NFR-3 (Correctness):** If `request.state.user` is not populated (auth middleware runs after rate-limit check), `user_id_key_func` falls back to `get_remote_address`. This is acceptable for an authenticated endpoint because `get_current_user` will 401 before the body executes anyway.

### Acceptance Criteria

**AC-1:** Given a user makes 10 `POST /api/skills` requests within one hour, all 10 return HTTP 201.

**AC-2:** Given the same user makes an 11th `POST /api/skills` within the same hour, the response is HTTP 429 with a `Retry-After` header.

**AC-3:** Given user-A is rate-limited, user-B's first `POST /api/skills` still returns HTTP 201 (limits are per-user, not global).

**AC-4:** Given the rate limit window resets (1 hour elapses), the user can submit again.

**AC-5:** All existing `test_skill_crud.py` tests continue to pass unchanged.

---

## ADRs

**ADR-039-1: Use `user_id_key_func` instead of `get_remote_address` for creation limiter**

Status: Accepted

Context: The existing `limiter` in `skills.py` uses `get_remote_address`. Behind the Next.js BFF all browser requests arrive from one pod IP, so IP-based limiting would be a single shared bucket for all users.

Options considered:

| Option | Pro | Con |
|---|---|---|
| Reuse existing `limiter` (IP-based) | Zero new code | Shared bucket for all BFF users — effectively a global limit |
| New `_create_limiter` with `user_id_key_func` | Per-user isolation, consistent with `_flag_limiter` | One extra `Limiter` instance |

Decision: Add `_create_limiter = Limiter(key_func=user_id_key_func)` and decorate with `@_create_limiter.limit("10/hour")`. This mirrors the pattern already in use for `_flag_limiter` (line 39).

Consequences: A second in-memory limiter instance is allocated. No Redis or external state is needed. Each instance tracks its own counters independently, which is correct since they guard different endpoints.

---

**ADR-039-2: Rate limit value of 10/hour**

Status: Accepted

Context: The limit must be tight enough to prevent abuse (thousands of submissions) but permissive enough for legitimate use (a developer onboarding a batch of tools).

Options considered: 5/hour (too tight for bulk imports), 10/hour (matches the initial design note), 20/hour (explicitly mentioned as a fallback in the original task), 60/hour (too permissive).

Decision: Start at `10/hour`. The value is a string constant in the decorator and can be changed in a one-line PR without an ADR revision.

Consequences: A developer importing >10 skills in one sitting will be throttled. The workaround is to wait 1 hour or batch-submit via admin tooling (no rate limit on admin endpoints that create skills directly).

---

## Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/routers/skills.py` | Modify | Add `_create_limiter = Limiter(key_func=user_id_key_func)` (line ~39); add `@_create_limiter.limit("10/hour")` to `create_skill`; add `request: Request` as first param | Yes — httpx AsyncClient test against ASGI app |
| `backend/tests/test_skill_crud.py` (or new file) | Add tests | 3 new async test cases: 10 OK, 11th is 429, second user unaffected | Yes — existing conftest + mongomock |

No other files change.

---

## System / Infrastructure Design

### Attack vs. fix data flow

```
Attacker (authenticated)
        │
        │  POST /api/skills  (repeated rapidly)
        ▼
[SlowAPIMiddleware]  ← already registered in main.py (line 79)
        │
        │  key = user_id_key_func(request)
        │        → "user:attacker-id"
        │
        ▼
[_create_limiter counter]
        │
        ├─ count ≤ 10/hour ──► create_skill() → MongoDB write + GitHub fetch
        │
        └─ count > 10/hour ──► 429 Too Many Requests  (stops here, no DB/GitHub I/O)
```

### Before vs. after: endpoint signature

**Before (line 158-162):**
```python
@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    user: User = Depends(get_current_user),
):
```

**After:**
```python
@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
@_create_limiter.limit("10/hour")
async def create_skill(
    request: Request,
    body: SkillCreate,
    user: User = Depends(get_current_user),
):
```

No API contract change — callers do not send `request`, FastAPI injects it.

---

## Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Per-user key (`user_id_key_func`) | Each user has an independent 10/hour bucket | Slightly more memory (one counter per active user) |
| In-memory counter (default slowapi) | Zero infra dependency | Counter resets on pod restart; burst possible across rolling restarts |
| 10/hour hard limit | Stops bulk abuse immediately | Legitimate bulk importers need to wait or use admin tooling |
| No admin exemption | Simplicity | Admins creating >10 skills/hour must use the admin router or a direct DB operation |

---

## Delivery Slices

**Slice 1 (the fix — ship alone):**
- Add `_create_limiter` and `@_create_limiter.limit("10/hour")` decorator.
- Add `request: Request` to `create_skill` signature.
- No config change, no migration.

**Slice 2 (tests — can be in same PR as Slice 1):**
- Add `test_create_skill_rate_limited` to `tests/test_skill_crud.py` (or a new `test_rate_limits.py`).
- Verify AC-1, AC-2, AC-3.

**Slice 3 (optional, future):**
- Expose `SKILL_CREATE_RATE_LIMIT` as a config value in `app/config.py` so ops can tune without a code deploy.

Slices 1+2 are a single PR. Slice 3 is a follow-on.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pod restart resets in-memory counters; attacker bursts 10 creations per rolling restart | Low | Low | Acceptable for MEDIUM severity; Redis-backed limits are Slice 3+ |
| `request: Request` positional change breaks existing tests that call the endpoint without `request` | Medium | Low | Tests that use httpx AsyncClient pass through ASGI; `request` is injected by FastAPI, not by test callers |
| `_create_limiter` and `_flag_limiter` both call `user_id_key_func`; auth sets `request.state.user` in `get_current_user`, which runs *after* slowapi middleware | Low | Low | `user_id_key_func` falls back to IP on unauthenticated calls; `get_current_user` will 401 before any write happens anyway |
| Rate limit value too restrictive for CI/CD pipelines that bulk-seed skills | Low | Medium | CI pipelines use admin tooling or direct DB seeding, not `POST /api/skills` |

---

## Definition of Done

- [ ] `_create_limiter = Limiter(key_func=user_id_key_func)` added to `backend/app/routers/skills.py`
- [ ] `@_create_limiter.limit("10/hour")` decorator applied to `create_skill`
- [ ] `request: Request` added as first parameter to `create_skill`
- [ ] Test: 10 consecutive `POST /api/skills` calls return 201
- [ ] Test: 11th `POST /api/skills` call within the hour returns 429
- [ ] Test: A second user's first call succeeds after first user is rate-limited
- [ ] All existing `tests/test_skill_crud.py` tests pass unchanged
- [ ] `pytest backend/` passes with no regressions
- [ ] Manual smoke test: submit a skill via the frontend on dev overlay — succeeds
- [ ] Deployed to dev overlay via kustomize; no errors in pod logs
