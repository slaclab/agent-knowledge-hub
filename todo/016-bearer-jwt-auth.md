# 016 — Bearer JWT Auth: CLI Authentication Path for the Backend API

**Status:** ⬜ Open
**Branch:** —
**PR:** —

---

## Problem & Goal

**Problem:** The backend API only authenticates requests via VouchProxy headers (browser sessions through ingress) or the internal Next.js proxy secret. CLI tools — including the `/agent-knowledge-hub` skill — cannot authenticate write operations (rating, submitting) because they have no browser session and no access to the internal secret.

**Goal:** Add a third auth path to `get_current_user` that validates a SLAC-issued JWT from `Authorization: Bearer <token>`, allowing CLI tools to authenticate write requests using the token written to `~/.s3df-access-token` by `s3df login`.

**Success metrics:**
- `POST /api/skills/<slug>/rate` with a valid SLAC JWT returns 200
- `POST /api/skills/<slug>/rate` with an invalid/expired token returns 401
- Existing VouchProxy and Next.js proxy auth paths are unaffected

**Out of scope:**
- Token issuance or `s3df login` changes — that's the S3DF platform team's responsibility
- Full mTLS or service mesh auth
- OpenCode or other non-Claude-Code CLI clients

---

## Design

### Pre-condition

Verify with the S3DF platform team that `s3df login` writes a standard SLAC JWT to `~/.s3df-access-token` and confirm:
- JWT signing algorithm (RS256 / HS256)
- Public key or shared secret location / distribution
- Token expiry and refresh behaviour

If `s3df login` does **not** issue a standard JWT, a lightweight token-exchange endpoint (`POST /api/auth/token-exchange`) is needed instead — scope to be determined before implementation.

### Auth path addition (`backend/app/auth.py`)

```python
# Path 3: CLI Bearer JWT (added after existing Path 1 and Path 2)
auth_header = request.headers.get("Authorization", "")
if auth_header.startswith("Bearer "):
    token = auth_header[7:]
    user_id = _validate_slac_jwt(token)  # raises HTTP 401 on bad/expired token
    if user_id:
        return User(user_id=user_id, is_admin=user_id in settings.admin_user_set)
```

### Config additions (`backend/app/config.py`)

```python
jwt_public_key: str | None = None   # RS256: PEM public key
jwt_secret: str | None = None       # HS256: shared secret (fallback)
jwt_algorithm: str = "RS256"
jwt_issuer: str | None = None       # optional: validate iss claim
```

### No migration required
Additive change — new path in existing dependency function, no schema change, no data migration.

---

## Implementation Plan

### Slice 1 — Verify JWT format
- Contact S3DF platform team; document algorithm, key/secret, issuer, expiry
- Record outcome in this file's Problems & Solutions section

### Slice 2 — Backend JWT validation
- Add `_validate_slac_jwt(token) -> str` helper to `auth.py`
- Add `jwt_public_key` / `jwt_secret` / `jwt_algorithm` / `jwt_issuer` to `Settings`
- Add `JWT_PUBLIC_KEY` (or `JWT_SECRET`) to k8s secret and dev `.env`
- Unit tests: valid token → 200, invalid token → 401, expired token → 401, missing token → falls through to 401

### Slice 3 — Integration test
- Test against staging with a real `~/.s3df-access-token`
- Verify existing VouchProxy path still works

---

## Problems & Solutions

_None yet._

---

## References

- `backend/app/auth.py` — existing `get_current_user` with Path 1 (VouchProxy) and Path 2 (Next.js proxy)
- `todo/007-agent-knowledge-hub-skill.md` — depends on this todo for `rate` command auth
- `todo/008-auth-header-hardening.md` — explicitly deferred "CLI auth / Bearer token path (covered by #007)" → now #016
