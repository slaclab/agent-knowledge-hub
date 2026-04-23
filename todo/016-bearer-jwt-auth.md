# 016 — Bearer JWT Auth: CLI Authentication Path for the Backend API

**Status:** 🏁 Implementation Done
**Branch:** —
**PR:** —

---

## Problem & Goal

**Problem:** The backend API only authenticates requests via VouchProxy headers (browser sessions through ingress) or the internal Next.js proxy secret. CLI tools — including the `/agent-knowledge-hub` skill — cannot authenticate write operations (rating, submitting) because they have no browser session and no access to the internal secret.

**Goal:** Add a third auth path to `get_current_user` that validates a SLAC-issued JWT from `Authorization: Bearer <token>`, allowing CLI tools to authenticate any write request using the token written to `~/.s3df-access-token` by `s3df login`.

**Success metrics:**
- `POST /api/skills/<slug>/rate` with a valid SLAC JWT returns 200
- `POST /api/skills/<slug>/rate` with an invalid/expired token returns 401
- Existing Next.js proxy auth path (Path 2) is unaffected; VouchProxy path (Path 1) is intentionally removed (see ADR-016-B)
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

- **FR-1:** `get_current_user` accepts `Authorization: Bearer <token>` as Path 3 (Path 1 Vouch removed per ADR-016-B; Path 2 proxy secret retained).
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
- **AC-5:** Given no `Authorization` header, Path 3 is skipped and the request falls through to 401 (Path 1 removed; Path 2 requires X-Internal-Secret).
- **AC-6:** Given `jwt_public_key=None`, a Bearer token is ignored and falls through to 401.
- **AC-7:** Given `AUTH_MODE=dev`, Bearer token is never checked (dev path short-circuits first).
- **AC-8:** Given a valid JWT for a user in `admin_users`, `get_current_user` returns `User(is_admin=True)`.
- **AC-9:** `POST /api/skills/<slug>/rate` with a valid Bearer JWT returns 200.
- **AC-10:** Existing proxy-secret (Path 2) tests continue to pass unchanged. Path 1 (Vouch) tests are removed/updated to verify 401 instead of 200.
- **AC-11:** Given a JWT with `alg: HS256` signed using the public key as HMAC secret, `get_current_user` raises HTTP 401. _(security review AM-1)_
- **AC-12:** Given a JWT with `alg: none` and empty signature, `get_current_user` raises HTTP 401. _(security review AM-1)_
- **AC-13:** Given a request to `/api` with a spoofed `X-Vouch-Idp-Claims-Name` header (no VouchProxy), `get_current_user` raises HTTP 401 (not 200). _(security review AM-2)_

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

### ADR-016-B: Remove Path 1 (Vouch headers) — two-path auth model

**Status:** Accepted
**Date:** 2026-04-22 (updated from original "Path 3 position" ADR)

#### Context
The original plan added Path 3 (Bearer JWT) after Path 1 (Vouch) and Path 2 (proxy secret).
Board review identified that after the ingress split, Path 1 becomes a Vouch header spoofing
vector — any external client can forge `X-Vouch-Idp-Claims-Name` on the Vouch-free API ingress.

A frontend audit confirmed that all 7 browser write operations already use the Next.js proxy
(Path 2 / X-Internal-Secret). Path 1 is never the active auth path for browser writes.

VouchProxy strips `Authorization: Bearer` headers, making it impossible to keep Path 1 active
on an ingress that also needs to pass Bearer tokens through.

#### Decision
Remove Path 1 from `get_current_user`. The two remaining paths are:
- **Path 2:** `X-Internal-Secret` — Next.js server-side proxy (browser writes)
- **Path 3:** `Authorization: Bearer <JWT>` — CLI tools

#### Consequences
- Vouch header spoofing is impossible (no code trusts Vouch headers)
- No nginx annotation workarounds needed for `ingress-api`
- Browser read operations are unaffected (unauthenticated)
- Browser write operations are unaffected (already using Path 2)

---

## Module Design

### `_validate_slac_jwt(token: str) → str` (new, in `auth.py`)

**Responsibility:** Validate a SLAC RS256 JWT and return the `name` claim as user_id. Raise HTTP 401 on any validation failure.

**Interface:**
```python
def _validate_slac_jwt(token: str) -> str:
    # Returns user_id string on success
    # Raises HTTPException(401) on: bad signature, expired, wrong issuer, missing name claim, jwt_public_key not configured
    # Raises HTTPException(500) on: InvalidKeyError (malformed PEM — server misconfiguration)
```

**Implementation notes (from eng review):**
- `aud` claim is always validated against `settings.jwt_audience` (default `"s3df"` — confirmed with platform team). Do NOT pass `verify_aud=False`.
- Use `"require": ["exp", "iss", "name"]` in options to get automatic `MissingRequiredClaimError` for missing identity claim.
- After decode, validate `name` is a non-empty string: `isinstance(name, str) and name.strip()`.
- Catch `InvalidKeyError` separately and raise HTTP 500 (server config error), not 401 (client error).
- Catch `ExpiredSignatureError` separately and raise HTTP 401 with an actionable message ("Re-run `s3df login`").
- Catch `PyJWTError` (base class) for all other JWT failures -> HTTP 401.

```python
import jwt as pyjwt
from jwt.exceptions import ExpiredSignatureError, InvalidKeyError, PyJWTError

def _validate_slac_jwt(token: str) -> str:
    if settings.jwt_public_key is None:
        raise HTTPException(status_code=401, detail="JWT authentication not configured")
    try:
        decode_options = {"require": ["exp", "iss", "name"]}
        decode_kwargs = {
            "algorithms": [settings.jwt_algorithm],
            "issuer": settings.jwt_issuer,
        }
        # Audience validation: always enabled; default value "s3df" (confirmed with platform team)
        decode_kwargs["audience"] = settings.jwt_audience
        payload = pyjwt.decode(
            token,
            settings.jwt_public_key,
            options=decode_options,
            **decode_kwargs,
        )
    except InvalidKeyError:
        logger.error("JWT public key configuration error — check JWT_PUBLIC_KEY format")
        raise HTTPException(status_code=500, detail="Server authentication configuration error")
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Re-run 's3df login' to refresh your session.")
    except PyJWTError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=401, detail="JWT missing valid 'name' claim")
    return name.strip()
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
jwt_audience: str = "s3df"           # OIDC audience claim; must match `aud` in SLAC Dex tokens
```

**Field validator (from eng review):** Add `_strip_jwt_public_key` following the `_strip_internal_api_secret` pattern:
```python
@field_validator("jwt_public_key", mode="before")
@classmethod
def _strip_jwt_public_key(cls, v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    # Env vars often encode newlines as literal \n
    return s.replace("\\n", "\n")
```

**Algorithm validator (security review AM-1):** Prevent config-injection of `HS256` or other weak algorithms:
```python
@field_validator("jwt_algorithm", mode="before")
@classmethod
def _validate_jwt_algorithm(cls, v: object) -> str:
    allowed = {"RS256"}
    val = str(v).strip().upper()
    if val not in allowed:
        raise ValueError(f"jwt_algorithm must be one of {allowed}, got {val!r}")
    return val
```

**Note:** `jwt_secret` (HS256 fallback) is dropped — RS256 is confirmed, no fallback needed.

**Testable in isolation:** Yes — pydantic-settings, patchable in tests.

---

### `get_current_user` (modify `auth.py`)

**Responsibility:** Remove Path 1 (Vouch headers) and add Path 3 (Bearer JWT). After the ingress
split, all browser writes go through the Next.js proxy (Path 2 / X-Internal-Secret — confirmed by
frontend audit). Path 1 is no longer reached from any browser path and its removal eliminates the
Vouch header spoofing attack surface entirely.

**Change:** Remove Path 1 block; add Path 3 after Path 2, before the final 401:
```python
# Path 3: Bearer JWT — CLI tools with SLAC-issued token
auth_header = request.headers.get("Authorization", "")
if auth_header.startswith("Bearer "):
    token = auth_header[7:].strip()  # len("Bearer ") == 7; strip whitespace/newlines
    if token:
        user_id = _validate_slac_jwt(token)
        return User(user_id=user_id, is_admin=user_id in settings.admin_user_set)
```

**Parsing notes (from eng review):**
- `startswith("Bearer ")` (with trailing space) rejects `BearerXYZ` and `Bearer` without token
- Guard `if token:` handles `"Bearer "` with empty token (falls through to 401 silently)
- `_validate_slac_jwt` internally checks `jwt_public_key is not None`

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

**Security rationale for removing Path 1:** A frontend audit confirmed that all browser write
operations (rate, create, update, delete, label — 7 endpoints) route through the Next.js proxy
route handlers at `frontend/app/api/*/route.ts`, which authenticate to the backend via
`X-Internal-Secret` (Path 2). Path 1 (Vouch headers) is never the active auth path for any
browser write request — it is unreachable via the Next.js proxy path, which fires Path 2 first.

Removing Path 1 entirely:
- Eliminates the Vouch header spoofing attack surface on `ingress-api` (no longer any code path
  that trusts `X-Vouch-Idp-Claims-Name`)
- Requires no nginx annotation workarounds (`configuration-snippet` is blocked on SLAC cluster)
- Simplifies `get_current_user` to two paths: Path 2 (proxy secret) and Path 3 (Bearer JWT)

**Browser read operations** (e.g. `GET /api/skills`) are unauthenticated — they work without any
auth header and are unaffected by this change.

**After split — two auth paths remain:**
```
Browser write  → Next.js proxy (X-Internal-Secret)   → Path 2 ✅
CLI write      → ingress-api (Authorization: Bearer)  → Path 3 ✅
Unauthenticated reads → ingress-api                   → no auth required ✅
Spoofed X-Vouch-Idp-Claims-Name → Path 1 removed → 401 ✅
```

The Slice 0 validation gate must include:
- `curl -H "X-Vouch-Idp-Claims-Name: admin" https://<dev-host>/api/skills` returns 401 (not 200)

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
  │    Path 1: REMOVED (ADR-016-B — Vouch headers no longer trusted)
  │    Path 2: X-Internal-Secret match?  → User (Next.js server-side proxy)
  │    Path 3: Authorization: Bearer?
  │      └─ _validate_slac_jwt(token)
  │           ├─ jwt_public_key configured? else → 401
  │           ├─ PyJWT.decode(RS256, iss, aud="s3df", verify_exp=True)
  │           ├─ extract payload["name"] → user_id
  │           └─ return User(user_id, is_admin=...)
  │    None matched → 401
  ▼
  rate endpoint handler (no changes needed)
```

### Skill-side contract (interface for todo/007)

This section defines the contract that the `/agent-knowledge-hub` skill (todo/007) must implement
to use Bearer JWT auth. It is out of scope for #016 to implement the skill side, but the interface
must be locked in so #007 has a stable target.

**Token discovery:**
- Read `~/.s3df-access-token` (raw JWT string, single line, may have trailing newline)
- If the file does not exist or is empty, do NOT send a Bearer header; instead display:
  `"No SLAC token found. Run 's3df login' to authenticate, then try again."`
- Strip whitespace from the token before sending

**Request format:**
- Header: `Authorization: Bearer <token>` (no quotes around token)
- Sent on all write requests: `rate`, `submit`, `label`
- NOT sent on read requests (`search`, `install`, `list`) — those are unauthenticated

**Error handling — interpreting 401 responses:**
The backend returns JSON `{"detail": "<message>"}` on 401. The skill should display the `detail`
value directly to the user — it is written to be human-readable and actionable:

| Backend `detail` | Skill should display |
|---|---|
| `"Token expired. Re-run 's3df login' to refresh your session."` | Show as-is |
| `"Invalid or expired token"` | Show as-is (covers bad signature, malformed token) |
| `"JWT missing valid 'name' claim"` | Show as-is + suggest contacting S3DF support |
| `"JWT authentication not configured"` | `"Server-side auth not yet configured. Bearer JWT auth may not be deployed yet."` |
| `"Authentication required"` | Generic fallback — show as-is |

**Token refresh flow (user-facing):**
1. User runs `/agent-knowledge-hub rate <slug> 5`
2. Skill reads `~/.s3df-access-token`, sends Bearer header
3. Backend returns 401 with `"Token expired..."` detail
4. Skill displays: `"Token expired. Re-run 's3df login' to refresh your session."`
5. User runs `s3df login` in their terminal
6. User retries the rate command -- succeeds

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
- [ ] `curl -H "X-Vouch-Idp-Claims-Name: admin" https://<dev-host>/api/skills` returns `401` (Vouch header spoofing blocked) _(security review AM-2)_

_Do not proceed until all five checks pass._

---

### Slice 1 — JWT validation logic (local only, no deployment)

**Assumption being tested:** The `_validate_slac_jwt` helper correctly accepts and rejects tokens
using a synthetic RS256 key pair — before we need a real SLAC public key.

- Add `jwt_public_key`, `jwt_algorithm`, `jwt_issuer` to `Settings` in `config.py`
- Add `_strip_jwt_public_key` field validator (A-1 from eng review)
- Add `_validate_slac_jwt(token) -> str` to `auth.py`
  - Returns `user_id` on success
  - Raises `HTTPException(401)` on: not configured, bad signature, expired, wrong issuer, missing `name` claim
  - Raises `HTTPException(500)` on: `InvalidKeyError` (malformed PEM — server misconfiguration)
  - Expired tokens get a distinct detail message: `"Token expired. Re-run 's3df login' to refresh your session."`
- Add Path 3 block to `get_current_user`
  - Strip whitespace from Bearer token before validation (`token.strip()`) to handle trailing newlines from file reads
- Generate a throwaway RSA key pair in the test suite (no secrets needed)
- Unit tests in `test_auth.py` covering AC-1 through AC-10 plus expanded test matrix

**Test fixture pattern:**
```python
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

@pytest.fixture(scope="module")
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem

def _make_jwt(private_pem, claims=None, **overrides):
    import time
    payload = {"name": "alice", "iss": "https://dex.slac.stanford.edu",
               "exp": int(time.time()) + 3600, "iat": int(time.time())}
    if claims: payload.update(claims)
    payload.update(overrides)
    return jwt.encode(payload, private_pem, algorithm="RS256")
```

**Expanded test matrix (from eng review):**

| ID | Description | Category |
|----|-------------|----------|
| T-JWT-01 | Valid RS256 JWT -> `User(user_id="alice")` | AC-1 |
| T-JWT-02 | JWT signed with wrong RSA key -> 401 | AC-2 |
| T-JWT-03 | Expired JWT -> 401 | AC-3 |
| T-JWT-04 | Wrong `iss` -> 401 | AC-4 |
| T-JWT-05 | No Authorization header -> 401 | AC-5 |
| T-JWT-06 | `jwt_public_key=None` -> falls through to 401 | AC-6 |
| T-JWT-07 | `auth_mode=dev` -> dev_user wins, Bearer ignored | AC-7 |
| T-JWT-08 | Valid JWT, user in admin_users -> is_admin=True | AC-8 |
| T-JWT-09 | POST /api/skills/slug/rate with Bearer -> 200 | AC-9 |
| T-JWT-10 | Path 1 (Vouch header) → 401; Path 2 (proxy secret) tests unchanged | AC-10 |
| T-JWT-11 | `Bearer ` (empty token) -> 401 | Edge |
| T-JWT-12 | `Bearer abc.def` (malformed) -> 401 | Edge |
| T-JWT-13 | `Basic ...` (non-Bearer) -> skipped, 401 | Edge |
| T-JWT-14 | Missing `name` claim -> 401 | Edge |
| T-JWT-15 | `name=""` -> 401 | Edge |
| T-JWT-16 | `name=123` (non-string) -> 401 | Edge |
| T-JWT-17 | No `aud` claim in token -> 401 (aud always validated) | PyJWT |
| T-JWT-18 | PEM with literal `\n` -> validator normalises | Config |
| T-JWT-19 | Whitespace-only PEM -> None, disabled | Config |
| T-JWT-20 | Spoofed `X-Vouch-Idp-Claims-Name` header on API ingress -> 401 (Path 1 removed) | Security |
| T-JWT-21 | Internal secret + Bearer -> secret wins | Priority |
| T-JWT-22 | get_optional_user + bad Bearer -> None | Dep |
| T-JWT-23 | Malformed PEM -> 500 | Config err |
| T-JWT-24 | `nbf` in future -> 401 | Edge |
| T-JWT-25 | Wrong `aud` claim (e.g. `"other-app"`) -> 401 | Security |

**Validation gate:**
- [ ] All unit tests pass in CI with synthetic key pair
- [ ] Existing Path 2 (proxy-secret) tests pass unchanged; Path 1 (Vouch) tests updated to verify 401
- [ ] `jwt_public_key=None` → Path 3 disabled, falls through to 401 (AC-6)

_Do not proceed until CI is green._

---

### Slice 2 — Real key + dev cluster integration

**Assumption being tested:** The real SLAC RS256 public key and a real `~/.s3df-access-token`
actually work against the deployed backend.

- Obtain the SLAC Dex RS256 public key (PEM) — fetch from `https://dex.slac.stanford.edu/.well-known/openid-configuration` → `jwks_uri`, extract the active signing key
- Add `JWT_PUBLIC_KEY` to the dev k8s secret
- Add `JWT_PUBLIC_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER` to `backend/.env.example` with comments explaining defaults and AUTH_MODE=dev bypass
- Deploy Slice 1 code + updated secret to dev cluster
- Write `docs/runbooks/jwt-public-key-rotation.md` — follows the `internal-api-secret.md` pattern: fetch key from JWKS, store in Vault, deploy backend, verify, rollback

**Validation gate:**
- [ ] `curl -H "Authorization: Bearer $(cat ~/.s3df-access-token)" https://<dev-host>/api/skills/me` returns 200 with correct `user_id`
- [ ] `curl -H "Authorization: Bearer badtoken"` returns 401
- [ ] Expired token (manually crafted or waited out) returns 401
- [ ] Browser auth (Next.js proxy / Path 2) still works alongside Path 3

_Do not proceed until all four checks pass against the live dev cluster._

---

### Slice 3 — Promote to prod + unblock todo/007

**Assumption being tested:** Everything works the same in prod as in dev.

- Apply ingress split to prod and stage overlays
- Add `JWT_PUBLIC_KEY` to prod k8s secret
- Deploy to prod
- Smoke test: `curl -H "Authorization: Bearer $(cat ~/.s3df-access-token)" https://<prod-host>/api/skills/me`
- Update `todo/007` dependency note: "Bearer JWT auth — ✅ complete"
- **Docs:**
  - Add CHANGELOG entry for Bearer JWT auth (new auth path, ingress split, config requirements)
  - Update `docs/runbooks/internal-api-secret.md` Section 5 verification table to include a Path 3 Bearer JWT check
  - Extract ADR-016-A, ADR-016-B, ADR-016-C from this file into `docs/adr/adr-p08-*.md` (or next available number) as standalone files
  - Update `PRD.md` Section 12 Secrets Management: replace `JWT_SECRET` reference with `JWT_PUBLIC_KEY`

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
| Vouch header spoofing on ungated API ingress _(security review SR-3)_ | N/A | N/A | Eliminated by Path 1 removal (ADR-016-B) — no code trusts Vouch headers; verified by AC-13 |
| Token replay from other Dex clients _(security review SR-2)_ | Low | Medium | `aud` claim validated against `"s3df"` — tokens for other Dex clients are rejected |
| Algorithm confusion via `alg: HS256` or `alg: none` _(security review SR-1)_ | Low (PyJWT 2.8 mitigates) | Critical | Pin `algorithms=["RS256"]`; validate `jwt_algorithm` config; test AC-11/AC-12 |

---

## Definition of Done

- [ ] Ingress split deployed to dev; browser login verified; unauthenticated `/api` returns 401
- [ ] AC-1 through AC-13 pass in CI (includes algorithm confusion and Vouch spoofing tests from security review)
- [ ] Unit tests: valid token → 200, bad signature → 401, expired → 401, wrong issuer → 401, no key configured → 401
- [ ] Existing proxy-secret (Path 2) tests pass unchanged; Path 1 (Vouch) tests updated to verify 401
- [ ] Integration test against dev cluster with real `~/.s3df-access-token`
- [ ] `todo/007` dependency unblocked
- [ ] `backend/.env.example` updated with `JWT_PUBLIC_KEY`, `JWT_ALGORITHM`, `JWT_ISSUER`
- [ ] `docs/runbooks/jwt-public-key-rotation.md` written and reviewed
- [ ] `docs/runbooks/internal-api-secret.md` updated with Path 3 verification step
- [ ] CHANGELOG entry added for Bearer JWT auth
- [ ] ADR-016-A/B/C extracted into `docs/adr/` as standalone files
- [ ] `PRD.md` Section 12 `JWT_SECRET` reference corrected to `JWT_PUBLIC_KEY`

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

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-04-22
**Rounds:** 2

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — SKIP | N | Technology well-understood; no speculative unknowns |
| codebase-arch-review | ✅ PASS | Y | BLOCKING: browser auth breaks + Vouch spoofing after split → resolved by removing Path 1 entirely (ADR-016-B); two-path model coherent |
| codebase-eng-review | ⚠️ WARN | Y | PyJWT verify_aud default, name claim type validation, InvalidKeyError→500, expanded test matrix T-JWT-01–25 |
| codebase-doc-review | ⚠️ WARN | Y | 6 doc gaps added: rotation runbook, .env.example, CHANGELOG, PRD stale ref, runbook update, ADR extraction |
| security-review | ⚠️ WARN | Y | Algorithm confusion (AC-11/12), Vouch spoofing resolved via Path 1 removal (AC-13), aud="s3df" always validated |
| codebase-ux-review | ⚠️ WARN | Y | Skill-side contract locked in, distinct 401 detail messages specified, token-strip added |

**Accepted warnings:**
- `name` claim assumed to be immutable UNIX username (not display name) — tech debt tracked
- Key rotation requires pod restart (acceptable for v1; JWKS upgrade path documented)
- CORS `allow_origins=["*"]` pre-existing issue, amplified slightly; deferred to follow-up

**ADRs written:** 3 inline (ADR-016-A, ADR-016-B, ADR-016-C) — to be extracted to `docs/adr/` in Slice 3
**Unresolved decisions:** none

---

### Reviewer output

<details>
<summary>codebase-arch-review — Round 2 (✅ PASS)</summary>

## Summary

BLOCKING-1 and BLOCKING-3 are substantively resolved — Path 1 removal is the correct fix and the two-path model (Path 2 + Path 3) is coherent. BLOCKING-2 wording is improved. However, the plan had several stale references to Path 1 that were cleaned up before implementation.

## Issues

### VERIFIED: BLOCKING-1 resolved — Path 1 removal is correct

ADR-016-B correctly identifies that (a) all 7 browser write operations use the Next.js proxy (Path 2), (b) Path 1 is unreachable for browser writes, and (c) VouchProxy strips Bearer headers making Path 1 and Path 3 incompatible on the same ingress. The two-path model (Path 2 + Path 3) is coherent. ✅

### VERIFIED: BLOCKING-3 resolved — spoofing mitigated by Path 1 removal

With Path 1 removed, no code path trusts `X-Vouch-Idp-Claims-Name`. AC-13 is present and trivially achievable. No nginx annotation workarounds needed. ✅

### VERIFIED: BLOCKING-2 resolved — wording updated ✅

### NOTED: WARNING-1 — prod/stage ingress may not exist yet

Slice 3 says "Apply ingress split to prod and stage overlays" but prod/stage may not have ingress files yet. Non-blocking — implementer should clarify before Slice 3.

## Status
PASS

</details>

<details>
<summary>codebase-eng-review — Round 1 (⚠️ WARN)</summary>

## Summary

The plan is well-structured and nearly complete. `_validate_slac_jwt` is synchronous/pure (appropriate), exception hierarchy is right, path ordering defensible. 2 issues, 1 decision, 8 amendments. None are blockers.

## Issues

- warning | impl | PyJWT `verify_aud` defaults True — SLAC tokens may lack `aud`; resolved by always enabling aud validation with `jwt_audience="s3df"`
- low | impl | `name` claim type not validated — fixed with isinstance + strip check

## Amendments made
- Added `_strip_jwt_public_key` validator
- Added `verify_aud` / `require` options to pseudocode
- Added `name` claim type validation
- Added `InvalidKeyError` → 500 distinction
- Added Bearer header parsing edge cases
- Added `get_optional_user` test note
- Added logging notes
- Expanded test matrix T-JWT-01–24

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-doc-review — Round 1 (⚠️ WARN)</summary>

## Summary

No documentation deliverables were tracked in the Definition of Done. Six gaps identified and added to the plan.

## Issues

- high | docs | No JWT public key rotation runbook (added to Slice 2)
- medium | docs | `.env.example` incomplete — JWT_ALGORITHM and JWT_ISSUER missing (fixed)
- medium | docs | No CHANGELOG entry (added to Slice 3)
- low | docs | PRD Section 12 references stale `JWT_SECRET` (added to Slice 3)
- medium | docs | `internal-api-secret.md` needs Path 3 verification step (added to Slice 3)
- low | docs | Three ADRs inline need extraction to `docs/adr/` (added to Slice 3)

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 2 (✅ PASS)</summary>

## Summary

AM-1 (algorithm confusion) and AM-3 (audience validation) fully verified. AM-2 (Path 1 removal / Vouch spoofing) structurally correct; stale references cleaned up. No new security issues from amendments. Path 1 removal verified safe: all 7 browser write endpoints confirmed to use Next.js proxy (Path 2).

## Amendments verified

- AM-1: `algorithms=["RS256"]` pinned; `jwt_algorithm` field validator rejects non-RS256; AC-11, AC-12 present ✅
- AM-2: Path 1 removed from `get_current_user`; ADR-016-B documents rationale; AC-13 present; Slice 0 gate includes spoofing check ✅
- AM-3: `jwt_audience: str = "s3df"` hardcoded; aud always validated; risk register updated ✅

## Status
PASS

</details>

<details>
<summary>codebase-ux-review — Round 1 (⚠️ WARN)</summary>

## Summary

Core backend plumbing clean. Three UX gaps addressed: skill-side contract locked in, distinct 401 detail messages specified per failure mode, first-use onboarding flow documented, token-strip added.

## Issues

- high | ux | No skill-side token-handling specification — added "Skill-side contract" section
- high | ux | 401 responses generic — added distinct detail strings per failure mode
- medium | ux | No first-use flow documented — added to skill-side contract section
- low | ux | Token trailing-newline handling — added `token.strip()` to Path 3 code

## Status
PASS WITH WARNINGS

</details>
