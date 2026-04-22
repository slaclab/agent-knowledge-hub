# 016 — Bearer JWT Auth: CLI Authentication Path for the Backend API

**Status:** ⬜ Open
**Branch:** —
**PR:** —

---

## Problem & Goal

**Problem:** The backend API only authenticates requests via VouchProxy headers (browser sessions through ingress) or the internal Next.js proxy secret. CLI tools — including the `/agent-knowledge-hub` skill — cannot authenticate write operations (rating, submitting) because they have no browser session and no access to the internal secret.

**Goal:** Add a third auth path to `get_current_user` that validates a SLAC-issued JWT from `Authorization: Bearer <token>`, allowing CLI tools to authenticate any write request using the token written to `~/.s3df-access-token` by `s3df login`.

**Success metrics:**
- `POST /api/skills/<slug>/rate` with a valid SLAC JWT returns 200
- `POST /api/skills/<slug>/rate` with an invalid/expired token returns 401
- Existing VouchProxy and Next.js proxy auth paths are unaffected
- All other write endpoints (submit, edit, admin actions) also accept Bearer JWT

**Out of scope:**
- Token issuance or `s3df login` changes — that's the S3DF platform team's responsibility
- Full mTLS or service mesh auth
- Token-exchange endpoint — not needed; `s3df login` already issues a standard RS256 JWT
- OpenCode or other non-Claude-Code CLI clients (but the path is generic enough to support them)

---

## Confirmed JWT Details

| Property | Value |
|---|---|
| Token location | `~/.s3df-access-token` (raw JWT string) |
| Identity token | `~/.s3df-token.json` → `idToken` field (not used here) |
| Algorithm | RS256 |
| User identity claim | `name` |
| Issuer | `https://dex.slac.stanford.edu` |
| Public key location | JWKS endpoint at issuer (to be confirmed: `<issuer>/.well-known/openid-configuration`) |

---

## User Stories

1. As a CLI user, I want to run `/agent-knowledge-hub rate <slug> 5` and have my rating saved, so that I can rate skills without opening a browser.
2. As a CLI user, I want my `s3df login` session to be sufficient for all write operations, so that I don't need a separate auth step.
3. As a CLI user with an expired token, I want a clear 401 error message, so that I know to re-run `s3df login`.
4. As a CLI user with a missing token file, I want a clear error telling me to run `s3df login`, so that I understand what action to take.
5. As a browser user, I want my VouchProxy session to continue working unchanged, so that this change doesn't affect my browser workflow.
6. As the Next.js frontend, I want the proxy secret path to continue working, so that internal API calls are unaffected.
7. As an admin, I want CLI-authenticated users to have the same admin rights as browser-authenticated ones (based on `admin_users` config), so that admin CLI workflows work.
8. As a security engineer, I want the `iss` claim validated against `https://dex.slac.stanford.edu`, so that tokens from other issuers are rejected.
9. As a security engineer, I want expired tokens rejected with 401, so that stale credentials cannot be used.
10. As a security engineer, I want the Bearer path only active when `jwt_public_key` is configured, so that a misconfigured deployment cannot accidentally accept unsigned tokens.
11. As an operator, I want to configure the JWT public key via an env var / k8s secret, so that key rotation doesn't require a code change.
12. As a developer, I want `AUTH_MODE=dev` to bypass JWT validation as it does for other paths, so that local development is unaffected.

---

## Requirements

### Functional

- **FR-1:** `get_current_user` accepts `Authorization: Bearer <token>` as Path 3 (after Path 1 VouchProxy, Path 2 proxy secret).
- **FR-2:** Path 3 validates the JWT signature using RS256 and the configured public key.
- **FR-3:** Path 3 validates the `iss` claim equals `https://dex.slac.stanford.edu`.
- **FR-4:** Path 3 validates token expiry (`exp` claim).
- **FR-5:** Path 3 extracts `user_id` from the `name` claim.
- **FR-6:** Path 3 is disabled (falls through to 401) when `jwt_public_key` is not configured.
- **FR-7:** All existing write endpoints accept Bearer JWT without per-endpoint changes.
- **FR-8:** Admin rights are determined by `admin_users` config, same as other paths.

### Non-functional

- **NFR-1:** JWT validation adds < 5ms overhead per request (RS256 verify is CPU-bound but fast for 2048-bit keys).
- **NFR-2:** No external network call per request — public key loaded from config at startup, not fetched from JWKS on each request.
- **NFR-3:** Key rotation supported via config update + pod restart (acceptable for v1).
- **NFR-4:** No new runtime dependencies — `PyJWT[crypto]>=2.8` is already in `requirements.txt`.

### Acceptance Criteria

- **AC-1:** Given a valid RS256 JWT with `name=alice` and `iss=https://dex.slac.stanford.edu`, `GET_current_user` returns `User(user_id="alice")`.
- **AC-2:** Given a JWT signed with the wrong key, `get_current_user` raises HTTP 401.
- **AC-3:** Given an expired JWT (`exp` in the past), `get_current_user` raises HTTP 401.
- **AC-4:** Given a JWT with `iss != https://dex.slac.stanford.edu`, `get_current_user` raises HTTP 401.
- **AC-5:** Given no `Authorization` header, Path 3 is skipped and the request falls through to 401 (or is satisfied by Path 1/2).
- **AC-6:** Given `jwt_public_key=None`, a Bearer token is ignored and falls through to 401.
- **AC-7:** Given `AUTH_MODE=dev`, Bearer token is never checked (dev path short-circuits first).
- **AC-8:** Given a valid JWT for a user in `admin_users`, `get_current_user` returns `User(is_admin=True)`.
- **AC-9:** `POST /api/skills/<slug>/rate` with a valid Bearer JWT returns 200.
- **AC-10:** Existing VouchProxy and proxy-secret tests continue to pass unchanged.

---

## ADRs

### ADR-016-C: Split ingress — remove VouchProxy from `/api`

**Status:** Accepted
**Date:** 2026-04-22

#### Context
VouchProxy is applied globally to all ingress routes, including `/api`. A CLI Bearer JWT request
has no SLAC SSO session so Vouch redirects it to login before it reaches the backend.

Options explored:
1. **VouchProxy pass-through mode** — not supported; `allowAllUsers` controls authorisation not authentication
2. **nginx `error_page 401` fallback** — requires `configuration-snippet` annotations, blocked on SLAC cluster
3. **Split ingress** — separate Ingress objects for frontend (Vouch) and API (no Vouch)
4. **Remove Vouch entirely** — too disruptive; breaks browser SSO

#### Decision
Split into `ingress-frontend.yaml` (Vouch retained) and `ingress-api.yaml` (no Vouch).

#### Consequences
- Unauthenticated requests to `/api` reach the backend and receive a 401 (not an SSO redirect)
- Browser auth is unaffected: Vouch still gates `/` and the Next.js server-side proxy uses `X-Internal-Secret`
- Defence-in-depth is reduced for `/api` (outer gate removed); accepted because backend auth is correct and `/api` is JSON-only

---

### ADR-016-A: RS256 public key from config, not JWKS auto-fetch

**Status:** Accepted
**Date:** 2026-04-22

#### Context
RS256 JWT validation requires the issuer's public key. Two common approaches:
1. Fetch from JWKS endpoint (`<issuer>/.well-known/jwks.json`) on first use and cache
2. Configure the PEM public key as an env var / k8s secret

#### Options

| Option | Pros | Cons |
|---|---|---|
| JWKS auto-fetch + cache | Automatic key rotation; zero-config after issuer URL set | Network call on startup; cache invalidation complexity; failure mode if JWKS endpoint unreachable |
| Static PEM in config (chosen) | No network dependency; simple; predictable | Requires manual key rotation + pod restart |

#### Decision
Static PEM via `JWT_PUBLIC_KEY` env var. At v1 scale (small team, infrequent key rotations), the simplicity wins. JWKS auto-fetch can replace this in a future iteration if key rotation becomes painful.

#### Consequences
- Key rotation requires updating the k8s secret + rolling restart (acceptable for v1)
- PEM must be stored securely in k8s secret, not in a ConfigMap

---

### ADR-016-B: Path 3 position — after Path 1 and Path 2

**Status:** Accepted
**Date:** 2026-04-22

#### Context
`get_current_user` checks paths in order. Bearer JWT needs a position.

#### Decision
Path 3 comes last (after VouchProxy and proxy secret). Rationale:
- VouchProxy is the highest-trust path (ingress-injected, cannot be spoofed from outside)
- Proxy secret is internal-only
- Bearer JWT is the lowest-trust path (self-presented credential requiring cryptographic verification)
- Ordering by trust level is the correct security posture

#### Consequences
- If a browser request somehow carries both a Vouch header and a Bearer token, Vouch wins (correct)
- No change to existing path ordering

---

## Module Design

### `_validate_slac_jwt(token: str) → str` (new, in `auth.py`)

**Responsibility:** Validate a SLAC RS256 JWT and return the `name` claim as user_id. Raise HTTP 401 on any validation failure.

**Interface:**
```python
def _validate_slac_jwt(token: str) -> str:
    # Returns user_id string on success
    # Raises HTTPException(401) on: bad signature, expired, wrong issuer, missing name claim, jwt_public_key not configured
```

**Testable in isolation:** Yes — pure function over a token string and settings; no I/O.

---

### `Settings` additions (modify `config.py`)

**Responsibility:** Surface `JWT_PUBLIC_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER` as typed config fields.

**Interface:**
```python
jwt_public_key: str | None = None    # RS256 PEM public key; None disables Path 3
jwt_algorithm: str = "RS256"
jwt_issuer: str = "https://dex.slac.stanford.edu"
```

**Note:** `jwt_secret` (HS256 fallback) is dropped — RS256 is confirmed, no fallback needed.

**Testable in isolation:** Yes — pydantic-settings, patchable in tests.

---

### `get_current_user` (modify `auth.py`)

**Responsibility:** Add Path 3 call after Path 2.

**Change:** Three-line addition — check for `Authorization: Bearer`, call `_validate_slac_jwt`, return `User`.

**No migration required** — additive change, no schema change, no data migration.

---

## Architecture

### Ingress split (prerequisite)

The current ingress applies VouchProxy auth globally to all routes including `/api`. VouchProxy
redirects unauthenticated requests to SLAC SSO login — meaning a CLI Bearer JWT request never
reaches the backend. The ingress must be split before Path 3 can work.

**Current (single Ingress, Vouch on everything):**
```
Internet → ingress (Vouch gated)
               ├── /        → frontend:3000
               ├── /api     → backend:8000   ← Vouch blocks CLI requests here
               └── /health  → backend:8000
```

**After split (two Ingress objects):**
```
Internet → ingress-frontend (Vouch gated)
               └── /        → frontend:3000

Internet → ingress-api (no Vouch — backend owns auth)
               ├── /api     → backend:8000
               └── /health  → backend:8000
```

**Security trade-off (accepted):** Removing Vouch from `/api` eliminates the outer SSO gate as
defence-in-depth. Unauthenticated requests now reach the backend and receive a 401 rather than
being redirected at the ingress. This is acceptable because:
- The backend already correctly returns 401 for all unauthenticated requests
- `/api` serves JSON only — no sessions, no HTML, no cookies
- Browser users are unaffected: client-side JS fetches `/api` → nginx → backend (Path 1 still
  works because VouchProxy headers are injected by the frontend Ingress for `/` requests, and the
  Next.js server-side proxy path uses `X-Internal-Secret` via `BACKEND_URL` internally)
- Modifying VouchProxy or nginx ingress controller globally is out of scope

### Request flow after this change

```
CLI tool (agent-knowledge-hub skill)
  │  reads ~/.s3df-access-token (raw JWT string)
  │  POST /api/skills/<slug>/rate
  │  Authorization: Bearer <jwt>
  ▼
ingress-api (nginx, no Vouch)
  │  passes Authorization header through untouched
  ▼
Backend FastAPI
  │  get_current_user dependency
  │    Path 1: X-Vouch-Idp-Claims-Name?  → User (vouch user, browser via frontend)
  │    Path 2: X-Internal-Secret match?  → User (Next.js server-side proxy)
  │    Path 3: Authorization: Bearer?
  │      └─ _validate_slac_jwt(token)
  │           ├─ jwt_public_key configured? else → 401
  │           ├─ PyJWT.decode(RS256, issuer, options={verify_exp: True})
  │           ├─ extract payload["name"] → user_id
  │           └─ return User(user_id, is_admin=...)
  │    None matched → 401
  ▼
  rate endpoint handler (no changes needed)
```

---

## Trade-offs

**Static PEM vs JWKS auto-fetch**
- `+` No network dependency at request time; simpler failure mode
- `+` No cache invalidation complexity
- `-` Key rotation requires pod restart
- Decision: Static PEM for v1. Switch to JWKS if rotation cadence increases.

**`name` claim vs `sub` claim for user_id**
- `name` matches what VouchProxy already surfaces (confirmed by platform team)
- `sub` would be more stable (opaque identifier, won't change on rename)
- Decision: `name` for now — consistency with existing identity. Track as tech debt.

**`jwt_secret` / HS256 fallback**
- Original design included HS256 fallback
- RS256 is confirmed; HS256 fallback adds complexity with no benefit
- Decision: RS256 only. Remove HS256 option entirely.

---

## Implementation Plan

Each slice has an explicit validation gate before proceeding. Do not advance to the next slice
until the gate passes.

### Slice 0 — Ingress split (dev cluster only)

**Assumption being tested:** Splitting the ingress doesn't break browser auth or the Next.js proxy path.

- Split `kubernetes/overlays/dev/ingress.yaml` into:
  - `ingress-frontend.yaml` — `/` → frontend:3000, Vouch annotations retained
  - `ingress-api.yaml` — `/api`, `/health` → backend:8000, no Vouch annotations
- Deploy to dev cluster only (prod/stage unchanged at this stage)

**Validation gate:**
- [ ] Browser login still works end-to-end (Vouch on frontend path)
- [ ] `curl https://<dev-host>/api/skills` without any auth returns `401` JSON (not a 302 redirect)
- [ ] `curl https://<dev-host>/api/skills` with a valid browser session cookie still returns 200
- [ ] Next.js server-side rendering still works (skills page loads, ratings display)

_Do not proceed until all four checks pass._

---

### Slice 1 — JWT validation logic (local only, no deployment)

**Assumption being tested:** The `_validate_slac_jwt` helper correctly accepts and rejects tokens
using a synthetic RS256 key pair — before we need a real SLAC public key.

- Add `jwt_public_key`, `jwt_algorithm`, `jwt_issuer` to `Settings` in `config.py`
- Add `_validate_slac_jwt(token) -> str` to `auth.py`
  - Returns `user_id` on success
  - Raises `HTTPException(401)` on: not configured, bad signature, expired, wrong issuer, missing `name` claim
- Add Path 3 block to `get_current_user`
- Generate a throwaway RSA key pair in the test suite (no secrets needed)
- Unit tests in `test_auth.py` covering AC-1 through AC-10

**Validation gate:**
- [ ] All unit tests pass in CI with synthetic key pair
- [ ] Existing Path 1 and Path 2 tests pass unchanged (AC-10)
- [ ] `jwt_public_key=None` → Path 3 disabled, falls through to 401 (AC-6)

_Do not proceed until CI is green._

---

### Slice 2 — Real key + dev cluster integration

**Assumption being tested:** The real SLAC RS256 public key and a real `~/.s3df-access-token`
actually work against the deployed backend.

- Obtain the SLAC Dex RS256 public key (PEM) — fetch from `https://dex.slac.stanford.edu/.well-known/openid-configuration` → `jwks_uri`, extract the active signing key
- Add `JWT_PUBLIC_KEY` to the dev k8s secret
- Add `JWT_PUBLIC_KEY` to `.env.example` (placeholder/instructions)
- Deploy Slice 1 code + updated secret to dev cluster

**Validation gate:**
- [ ] `curl -H "Authorization: Bearer $(cat ~/.s3df-access-token)" https://<dev-host>/api/skills/me` returns 200 with correct `user_id`
- [ ] `curl -H "Authorization: Bearer badtoken"` returns 401
- [ ] Expired token (manually crafted or waited out) returns 401
- [ ] Browser auth (Path 1) and Next.js proxy (Path 2) still work alongside Path 3

_Do not proceed until all four checks pass against the live dev cluster._

---

### Slice 3 — Promote to prod + unblock todo/007

**Assumption being tested:** Everything works the same in prod as in dev.

- Apply ingress split to prod and stage overlays
- Add `JWT_PUBLIC_KEY` to prod k8s secret
- Deploy to prod
- Smoke test: `curl -H "Authorization: Bearer $(cat ~/.s3df-access-token)" https://<prod-host>/api/skills/me`
- Update `todo/007` dependency note: "Bearer JWT auth — ✅ complete"

**Validation gate:**
- [ ] Prod smoke test returns 200 with correct `user_id`
- [ ] Browser login on prod unaffected
- [ ] `/agent-knowledge-hub rate <slug> <1-5>` in a Claude Code session returns success

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ingress split breaks browser auth | Low | High | Test browser login in dev before promoting to prod |
| Unauthenticated bots scanning `/api` hit backend pod | Medium | Low | Backend 401s are cheap; acceptable without outer gate |
| `name` claim absent in some token variants | Low | Medium | Log warning + 401 with clear message; fall back gracefully |
| PEM key misconfigured (wrong format, trailing newline) | Medium | Medium | Add `_strip` validator (same pattern as `internal_api_secret`) |
| PyJWT version incompatibility with `options` dict | Low | Low | `PyJWT>=2.8` already pinned; API is stable |
| Key rotation causes outage if pod not restarted | Low | High | Document rotation runbook; consider JWKS upgrade in future |

---

## Definition of Done

- [ ] Ingress split deployed to dev; browser login verified; unauthenticated `/api` returns 401
- [ ] AC-1 through AC-10 pass in CI
- [ ] Unit tests: valid token → 200, bad signature → 401, expired → 401, wrong issuer → 401, no key configured → 401
- [ ] Existing Path 1 and Path 2 tests pass unchanged
- [ ] `JWT_PUBLIC_KEY` added to k8s secret (dev + prod overlays)
- [ ] Integration test against dev cluster with real `~/.s3df-access-token`
- [ ] `todo/007` dependency unblocked

---

## Problems & Solutions

_None yet._

---

## References

- `backend/app/auth.py` — existing `get_current_user` with Path 1 (VouchProxy) and Path 2 (Next.js proxy)
- `backend/app/config.py` — `Settings` (pydantic-settings)
- `backend/tests/test_auth.py` — existing Path 1/2 test coverage
- `backend/requirements.txt` — `PyJWT[crypto]>=2.8` already present
- `todo/007-agent-knowledge-hub-skill.md` — depends on this todo for `rate` command auth
- `todo/008-auth-header-hardening.md` — explicitly deferred "CLI auth / Bearer token path" → now this file
- Token location: `~/.s3df-access-token` (raw RS256 JWT string issued by `s3df login`)
- Issuer: `https://dex.slac.stanford.edu`
