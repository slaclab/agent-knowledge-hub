# 038 — Security: Enforce Minimum Length on internal_api_secret

**Status:** ✅ Complete
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M2)

---

## Phase 1 — Problem & Goal

### What is broken today

`backend/app/config.py` lines 41–47 define `_strip_internal_api_secret`, a `@field_validator` that only strips whitespace and normalises empty values to `None`. There is no minimum-length check. A deployment that sets `INTERNAL_API_SECRET=test` or `INTERNAL_API_SECRET=secret` will start silently.

`backend/app/auth.py` lines 102–113 trust Path 2 fully once `hmac.compare_digest(incoming_secret, settings.internal_api_secret)` passes. A weak secret is trivially guessable by an attacker with network access to port 8000 (even from within the cluster), letting them forge `X-Forwarded-User` and authenticate as any SLAC user, including admins.

Current test fixtures confirm short secrets are in use:
- `test_moderation.py` line 21: `_TEST_SECRET = "test-secret-for-012"` (19 chars)
- `test_labels.py` line 286: `_TEST_SECRET = "test-internal-secret"` (21 chars)
- `test_ratings.py` line 31: `_TEST_SECRET = "test-internal-secret"` (21 chars)
- `test_user_activity.py` line 25: `_TEST_SECRET = "test-secret-for-011"` (19 chars)
- `test_auth.py` lines 392, 404, 418, 455, 466, 515: `"mysecret"` (8 chars) passed via `patch.object`

All of these bypass the validator via `monkeypatch.setattr` / `patch.object` (set directly on the instantiated `settings` object), so they are safe to leave as-is. However, they document a pattern of weak test secrets that should be flagged.

### What success looks like

- The app refuses to start at all if `INTERNAL_API_SECRET` is set to a value shorter than 32 characters.
- The error message tells the operator exactly how to generate a valid secret.
- `openssl rand -hex 32` (64-char hex) passes validation.
- No existing authenticated code paths change behaviour; the check is startup-only.

### Out of scope

- Rotating secrets currently deployed in Vault (operational task, not code)
- Adding HMAC-SHA256 request signing (defence-in-depth; separate ticket)
- Changing how test fixtures inject short secrets via `monkeypatch` (they bypass the validator legitimately)

### Constraints

- Must not break the existing auth flow in `auth.py` — zero runtime changes to `get_current_user`
- Must deploy via kustomize (no manifest changes required; this is purely Python)
- Must not require changes to Kubernetes secrets — existing 64-char hex secrets already satisfy ≥32 chars

---

## Phase 1.5 — User Stories

1. As a **developer** setting up a local dev environment, I want the app to fail fast with a clear message if my `.env` has `INTERNAL_API_SECRET=dev`, so that I fix it before deploying.
2. As an **operator** deploying to prod, I want the startup check to fail immediately on a misconfigured secret, so that a bad deploy fails at pod startup (CrashLoopBackOff) rather than running insecurely.
3. As an **attacker** who has network access to backend:8000 inside the cluster, I want to be prevented from brute-forcing a 4–8 character secret by timing requests, so that I cannot forge `X-Forwarded-User` headers.
4. As an **attacker** attempting to impersonate the Next.js frontend, I want the secret to be long enough to be infeasible to guess even with O(10^6) attempts, so that escalation to admin credentials is blocked.
5. As an **admin**, I want to trust that any deployment with Path 2 enabled has a cryptographically adequate secret, so that I do not need to audit individual deployments manually.
6. As a **CI pipeline**, I want the test suite to exercise both the rejection path (short secret) and the acceptance path (32+ char secret) in the validator, so that regressions are caught automatically.
7. As an **API consumer (CLI tool)** using Bearer JWT (Path 3), I want the internal secret validation to be startup-only, so that my JWT auth path is not affected.
8. As a **developer writing tests**, I want a well-named constant `_TEST_SECRET_32` of exactly 32+ chars available in conftest, so that new tests start with a compliant value.

---

## Phase 2 — Requirements

### Functional requirements

**FR-1:** The `@field_validator` for `internal_api_secret` in `backend/app/config.py` must raise `ValueError` when the stripped value is non-None and shorter than 32 characters.

**FR-2:** The error message must include the generation command `openssl rand -hex 32`.

**FR-3:** A value of exactly 32 characters must pass. `openssl rand -hex 32` output (64 chars) must pass.

**FR-4:** `None` (secret disabled) must continue to pass — Path 2 is optional.

**FR-5:** The validator method must be renamed from `_strip_internal_api_secret` to `validate_internal_secret` to match the design in the task file (the new name is used in `test_auth.py`'s `TestInternalApiSecretValidator` test class).

**FR-6:** `docs/runbooks/internal-api-secret.md` must document the minimum length requirement.

### Non-functional requirements

**NFR-1 (performance):** The length check runs only at process startup inside `Settings.__init__` — zero added latency to request handling.

**NFR-2 (compatibility):** All existing callers (`get_current_user`, HMAC compare, all routers) are unaffected — validator output type (`Optional[str]`) is unchanged.

**NFR-3 (observability):** The startup error message must be surfaced as a `pydantic.ValidationError` with the text `"internal_api_secret must be at least 32 characters"` so that it appears clearly in pod logs.

### Acceptance criteria

**AC-1:** Given `INTERNAL_API_SECRET=short`, when the backend process starts, then it raises `pydantic.ValidationError` containing `"internal_api_secret must be at least 32 characters"` and exits non-zero.

**AC-2:** Given `INTERNAL_API_SECRET` unset or empty, when the backend starts, then it starts successfully (Path 2 disabled, no error).

**AC-3:** Given `INTERNAL_API_SECRET` is a 32-character string, when the backend starts, then it starts successfully.

**AC-4:** Given `INTERNAL_API_SECRET` is the output of `openssl rand -hex 32` (64 chars), when the backend starts, then it starts successfully.

**AC-5:** Given a value with leading/trailing whitespace that is ≥32 chars after stripping, when validated, then it passes and the stripped value is stored.

**AC-6:** Given a value with leading/trailing whitespace that is <32 chars after stripping, when validated, then it raises `ValueError`.

**AC-7:** All pre-existing `TestInternalApiSecretValidator` tests in `test_auth.py` pass with the renamed validator.

---

## Phase 3 — ADRs

**ADR-038-1: Minimum secret length of 32 characters**
Status: Accepted
Context: `hmac.compare_digest` provides constant-time comparison but cannot compensate for a secret that is guessable by brute force. A minimum is needed; the question is what threshold.
Options considered:

| Option | Entropy | Notes |
|---|---|---|
| 16 chars | ~128 bits (hex) | Common minimum; acceptable |
| 32 chars | ~256 bits (hex) | Matches `openssl rand -hex 32` default; industry standard |
| 64 chars | ~512 bits (hex) | Diminishing returns; harder to remember in local .env |

Decision: 32 characters. Matches the existing runbook's `openssl rand -hex 32` example (which produces 64 hex chars, comfortably above the minimum). Secrets already deployed in prod/stage/dev use this generator and are compliant.
Consequences: Any deployment with a short secret fails at startup. Local dev setups with `INTERNAL_API_SECRET=dev` will fail — acceptable; the error message is actionable.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/config.py` | Modify | Rename `_strip_internal_api_secret` → `validate_internal_secret`; add `len(stripped) < 32` guard before return | Yes — call `Settings.validate_internal_secret(v)` directly as a classmethod |
| `backend/tests/test_auth.py` | Modify | Update `TestInternalApiSecretValidator` to use new method name; add two tests: short secret raises `ValueError`, exactly-32-char secret passes | Yes — unit tests |
| `docs/runbooks/internal-api-secret.md` | Modify | Add "Minimum length" section noting ≥32 chars required, generated by `openssl rand -hex 32` | n/a (docs) |

No changes required to: `auth.py`, any router, frontend, or Kubernetes manifests.

---

## Phase 4 — System/Infrastructure Design

### Attack flow intercepted

```
Attacker (inside cluster)
        |
        | POST /api/skills  X-Internal-Secret: test  X-Forwarded-User: admin
        v
[backend:8000]
        |
        v
  get_current_user()
        |
        v
  hmac.compare_digest("test", settings.internal_api_secret)
        |
        | [TODAY]  "test" == "test" → MATCH → admin access granted   ← VULNERABILITY
        | [AFTER]  startup already failed; pod never ran              ← FIXED
```

### Validator before / after

**Before (lines 41–47, config.py):**
```python
@field_validator("internal_api_secret", mode="before")
@classmethod
def _strip_internal_api_secret(cls, v: object) -> Optional[str]:
    if v is None:
        return None
    stripped = str(v).strip()
    return stripped if stripped else None
```

**After:**
```python
@field_validator("internal_api_secret", mode="before")
@classmethod
def validate_internal_secret(cls, v: object) -> Optional[str]:
    if v is None:
        return None
    stripped = str(v).strip()
    if not stripped:
        return None
    if len(stripped) < 32:
        raise ValueError(
            "internal_api_secret must be at least 32 characters. "
            "Generate with: openssl rand -hex 32"
        )
    return stripped
```

No API contract change. No data-flow change. The only effect is a `pydantic.ValidationError` at process boot when the value is too short.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Fail-fast at startup | Misconfiguration surfaces immediately as CrashLoopBackOff; never runs insecurely | A dev with `INTERNAL_API_SECRET=dev` in `.env` has a broken local start until they regenerate |
| 32-char minimum (not 16) | Matches `openssl rand -hex 32` default and leaves headroom | Slightly more friction for manually-set secrets |
| Rename to `validate_internal_secret` | Clearer name; matches design doc | Tests that call `_strip_internal_api_secret` by name need updating (only `test_auth.py` line 130, 135, 140, 145, 150, 155) |

---

## Phase 8 — Delivery Slices

**Slice 1 (only slice):** Add length check + rename validator + update test class method references + update runbook. All changes are in one Python file, one test file, and one markdown file. Safe to ship as a single PR; no feature flag or staged rollout needed. Existing prod/stage/dev secrets are already ≥32 chars (generated by `openssl rand -hex 32`).

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A deployed env has a short `INTERNAL_API_SECRET` | Low (prod/stage use `openssl rand -hex 32`) | High (CrashLoopBackOff on backend) | Check Vault secret lengths for all overlays before merging; `vault kv get` and confirm length |
| Test suite breaks because `test_auth.py` calls old method name | High (certain) | Low (CI catches it) | Update all 6 `_strip_internal_api_secret` call sites in `TestInternalApiSecretValidator` to `validate_internal_secret` |
| Local dev setups with short secrets break | Medium | Low (developer inconvenience only) | Error message includes `openssl rand -hex 32` command |

---

## Phase 10 — Definition of Done

- [ ] `backend/app/config.py`: `validate_internal_secret` validator raises `ValueError` for inputs shorter than 32 chars (after stripping)
- [ ] `backend/app/config.py`: method renamed from `_strip_internal_api_secret` to `validate_internal_secret`
- [ ] `backend/tests/test_auth.py`: all 6 call sites in `TestInternalApiSecretValidator` updated to `validate_internal_secret`
- [ ] `backend/tests/test_auth.py`: test added — short secret (e.g. `"tooshort"`) raises `ValueError` containing `"32 characters"`
- [ ] `backend/tests/test_auth.py`: test added — exactly 32-char secret passes and returns the value
- [ ] `docs/runbooks/internal-api-secret.md`: minimum-length requirement documented
- [ ] `pytest backend/tests/test_auth.py` passes with zero failures
- [ ] Full test suite (`pytest backend/`) passes with zero failures
- [ ] Manual smoke test: start backend locally with `INTERNAL_API_SECRET=short` and confirm startup fails with the expected message
- [ ] Manual smoke test: start backend with `INTERNAL_API_SECRET=$(openssl rand -hex 32)` and confirm startup succeeds
- [ ] Verified that prod/stage/dev Vault secrets are ≥32 chars before deploying
