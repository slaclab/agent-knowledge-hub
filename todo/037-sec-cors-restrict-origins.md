# 037 — Security: Restrict CORS Origins (allow_origins=["*"] + credentials)

**Status:** ✅ Complete
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M1)

---

## Phase 1 — Problem & Goal

### What is broken today

`backend/app/main.py` lines 81–87 configure CORS as:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The combination of `allow_origins=["*"]` and `allow_credentials=True` is a misconfiguration: FastAPI/Starlette will reflect the requesting `Origin` header verbatim and include `Access-Control-Allow-Credentials: true`, meaning any origin on the internet receives a credentialed CORS approval. An attacker-controlled page can make cross-origin `fetch()` calls with cookies/credentials to the API and read the response.

Today's auth primarily uses `X-Vouch-Idp-Claims-Name` (injected by nginx) and `X-Internal-Secret` (Next.js BFF), so the immediate blast radius is limited. However, if browser cookies are ever introduced (or a browser silently sends stored session tokens), the attack vector becomes directly exploitable. The misconfiguration also signals to scanners and auditors that origin validation is absent.

The three known legitimate origins are:
- `https://agent-knowledge-hub.slac.stanford.edu` (prod, from `ingress-frontend.yaml`)
- `https://agent-knowledge-hub-stage.slac.stanford.edu` (stage)
- `https://agent-knowledge-hub-dev.slac.stanford.edu` (dev)
- `http://localhost:3000` (local development)

`backend/app/config.py` has no `allowed_origins` setting today — the fix must add one.

### What success looks like

- `allow_origins=["*"]` is gone; an explicit, per-environment list is used.
- A request from `https://evil.com` does not receive `Access-Control-Allow-Origin` or `Access-Control-Allow-Credentials` in the response.
- The production, stage, dev, and local-dev origins all pass preflight checks without changes to the frontend or auth flow.

### Out of scope

- Changing auth model (Vouch, HMAC, JWT paths are unchanged).
- Restricting `allow_methods` or `allow_headers` beyond what is needed for this ticket.
- CORS hardening on the nginx ingress layer (separate concern).

### Constraints

- Must not break the existing Next.js BFF → backend call path (uses `X-Internal-Secret`).
- Must not break the CLI JWT path (Bearer token, no CORS preflight needed in practice, but must not regress).
- Must be deployable via kustomize `configMapGenerator` literals — no new Secrets required.
- Local dev (`localhost:3000`) must continue to work without manual config overrides by developers.

---

## Phase 1.5 — User Stories

1. As a **developer running locally**, I want `http://localhost:3000` always permitted, so that my Next.js dev server can call the backend without CORS errors.
2. As a **frontend user on prod**, I want only `https://agent-knowledge-hub.slac.stanford.edu` to receive credentialed CORS approval, so that my session cannot be hijacked by a malicious cross-origin page.
3. As a **stage tester**, I want the stage origin permitted in the stage overlay, so that stage E2E tests against the real backend pass without config hacks.
4. As an **admin deploying to a new environment**, I want `ALLOWED_ORIGINS` configurable as a single env var in the kustomize configmap, so that adding an origin does not require a code change.
5. As an **attacker on `https://evil.com`**, I should receive no `Access-Control-Allow-Origin` header from the API, so that I cannot read credentialed API responses from a victim's browser.
6. As a **CLI user making JWT-authenticated requests**, I want the CORS change to not affect my non-browser API calls, so that my tool continues to work without modification.
7. As a **security auditor**, I want the CORS policy to be explicit and environment-specific, so that automated scanners no longer flag `allow_origins=["*"]` as a misconfiguration.
8. As a **developer adding a new environment** (e.g., a PR preview URL), I want to add its origin to the configmap literal without touching Python source, so that the change is low-risk and reviewable in the kustomize overlay alone.

---

## Phase 2 — Requirements

### Functional Requirements

**FR-1:** `backend/app/config.py` must expose an `allowed_origins` field of type `list[str]`, populated from the `ALLOWED_ORIGINS` env var (comma-separated string), with a default of `["http://localhost:3000"]`.

**FR-2:** `backend/app/main.py` must pass `settings.allowed_origins` to `CORSMiddleware` instead of `["*"]`.

**FR-3:** Each kustomize overlay (`dev`, `stage`, `prod`) must set `ALLOWED_ORIGINS` as a `configMapGenerator` literal with the correct origin(s) for that environment plus `http://localhost:3000`.

**FR-4:** A `field_validator` on `allowed_origins` must strip whitespace from each entry and filter empty strings, so that `"https://a.com, https://b.com"` and `"https://a.com,https://b.com"` both parse correctly.

### Non-Functional Requirements

**NFR-1 (Performance):** CORS middleware runs before route handlers; the change from a wildcard check to a list lookup adds negligible latency (<0.1 ms per request).

**NFR-2 (Compatibility):** All existing callers (Next.js BFF via HMAC, CLI via JWT, health probes) must continue to function without modification after the change.

**NFR-3 (Operability):** Adding or removing an allowed origin must require only a configmap literal change and a rolling restart — no image rebuild.

### Acceptance Criteria

**AC-1:** Given a request with `Origin: https://evil.com`, when the preflight OPTIONS or any credentialed request reaches the backend, then the response does NOT contain `Access-Control-Allow-Origin` or contains `Access-Control-Allow-Origin: https://evil.com`.

**AC-2:** Given the prod overlay (`ALLOWED_ORIGINS=https://agent-knowledge-hub.slac.stanford.edu,http://localhost:3000`), when a request with `Origin: https://agent-knowledge-hub.slac.stanford.edu` arrives, then the response contains `Access-Control-Allow-Origin: https://agent-knowledge-hub.slac.stanford.edu` and `Access-Control-Allow-Credentials: true`.

**AC-3:** Given `ALLOWED_ORIGINS` is unset (default), when any request arrives, then only `http://localhost:3000` is an allowed origin.

**AC-4:** Given `ALLOWED_ORIGINS=https://a.com, https://b.com` (with a space after the comma), when settings are loaded, then both `https://a.com` and `https://b.com` appear in `settings.allowed_origins` without whitespace.

**AC-5:** The existing test suite (`pytest backend/tests/`) passes without modification after the change.

---

## Phase 3 — ADRs

**ADR-037-1: Env-var-driven origin list via Pydantic Settings**
Status: Accepted
Context: The origin list differs per environment; it must be changeable without a code or image rebuild.
Options considered:
- Hardcode per-environment list in `config.py` with env detection — tight coupling, requires image rebuild per env.
- Read from `ALLOWED_ORIGINS` env var (comma-separated), parsed in `config.py` — clean, consistent with existing Settings pattern (`admin_users`, `github_private_orgs`).
- Read from a mounted ConfigMap file — heavier operational lift, no benefit at this scale.

Decision: Comma-separated `ALLOWED_ORIGINS` env var parsed in `config.py` with a `field_validator`, matching the established pattern for `admin_users`.
Consequences: Origin list is visible in kustomize configmap literals (not a secret — origins are public by nature). Adding a new env requires a configmap edit + rolling restart.

**ADR-037-2: Keep `allow_credentials=True`**
Status: Accepted
Context: Should we remove `allow_credentials=True` since current auth does not use browser cookies?
Decision: Retain it. The Next.js BFF sends `X-Internal-Secret` and the frontend may send cookies in future; removing it now would break potential future flows and is not the concern of this ticket. Restricting `allow_origins` is sufficient to neutralise the wildcard + credentials attack vector.
Consequences: Credentialed CORS is still enabled, but only for explicitly listed origins.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/config.py` | Add field | Add `allowed_origins: list[str]` with `field_validator` to parse comma-separated env var | Yes — unit test Settings instantiation with env var |
| `backend/app/main.py` | Update | Replace `allow_origins=["*"]` with `allow_origins=settings.allowed_origins` (line 82) | Yes — `TestClient` with `headers={"Origin": ...}` checks response headers |
| `kubernetes/overlays/dev/kustomization.yaml` | Update | Add `ALLOWED_ORIGINS=https://agent-knowledge-hub-dev.slac.stanford.edu,http://localhost:3000` to `configMapGenerator` literals | Deploy smoke test |
| `kubernetes/overlays/stage/kustomization.yaml` | Update | Add `ALLOWED_ORIGINS=https://agent-knowledge-hub-stage.slac.stanford.edu,http://localhost:3000` | Deploy smoke test |
| `kubernetes/overlays/prod/kustomization.yaml` | Update | Add `ALLOWED_ORIGINS=https://agent-knowledge-hub.slac.stanford.edu,http://localhost:3000` | Deploy smoke test |
| `backend/tests/test_cors.py` | New file | Unit tests for AC-1 through AC-5 | Yes — pytest + starlette TestClient, no DB needed |

---

## Phase 4 — System/Infrastructure Design

### Data flow: CORS preflight from malicious origin (before vs. after)

**Before (broken):**
```
Browser (evil.com)
  → OPTIONS /api/skills  Origin: https://evil.com
  → nginx ingress (passes through)
  → FastAPI CORSMiddleware: allow_origins=["*"] → reflects origin
  ← 200  Access-Control-Allow-Origin: https://evil.com
         Access-Control-Allow-Credentials: true
  → Browser: CORS approved, sends credentialed GET
  ← 200  [skill data, user data, etc.]
```

**After (fixed):**
```
Browser (evil.com)
  → OPTIONS /api/skills  Origin: https://evil.com
  → nginx ingress (passes through)
  → FastAPI CORSMiddleware: allow_origins=[known list] → origin not in list
  ← 200  (no Access-Control-Allow-Origin header)
  → Browser: CORS blocked, request aborted
```

**Legitimate origin (unchanged):**
```
Browser (agent-knowledge-hub.slac.stanford.edu)
  → OPTIONS /api/skills  Origin: https://agent-knowledge-hub.slac.stanford.edu
  → FastAPI CORSMiddleware: origin in settings.allowed_origins
  ← 200  Access-Control-Allow-Origin: https://agent-knowledge-hub.slac.stanford.edu
         Access-Control-Allow-Credentials: true
  → Browser: CORS approved, proceeds normally
```

### Config change (before/after)

**Before — `backend/app/main.py` line 82:**
```python
allow_origins=["*"],
```

**After:**
```python
allow_origins=settings.allowed_origins,
```

**After — `backend/app/config.py` new field:**
```python
allowed_origins: list[str] = ["http://localhost:3000"]

@field_validator("allowed_origins", mode="before")
@classmethod
def _parse_allowed_origins(cls, v: object) -> list[str]:
    if isinstance(v, list):
        return [o.strip() for o in v if str(o).strip()]
    return [o.strip() for o in str(v).split(",") if o.strip()]
```

**After — `kubernetes/overlays/prod/kustomization.yaml` configMapGenerator addition:**
```yaml
- ALLOWED_ORIGINS=https://agent-knowledge-hub.slac.stanford.edu,http://localhost:3000
```

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Env-var comma-separated list | Consistent with `admin_users` pattern; no new infra | Slightly awkward to read long lists in kustomize literals |
| Keep `allow_credentials=True` | No frontend regressions; future cookie support preserved | Credentialed CORS still enabled (mitigated by explicit origin list) |
| Default includes `localhost:3000` | Zero-friction local dev | Anyone running the backend locally with default config accepts localhost as an origin (acceptable for dev) |
| No `allow_methods`/`allow_headers` tightening in this ticket | Minimal diff, single-purpose change | `allow_methods=["*"]` and `allow_headers=["*"]` remain permissive (tracked separately) |

---

## Phase 8 — Delivery Slices

### Slice 1 — Config + backend code (safe to ship alone, tightens security immediately)
- Add `allowed_origins` field to `config.py` with validator.
- Update `main.py` line 82 to use `settings.allowed_origins`.
- Add `backend/tests/test_cors.py` covering AC-1 through AC-5.
- Default value `["http://localhost:3000"]` means the change is non-breaking in isolation (prod pods will only allow localhost until Slice 2 lands, but the API backend is not directly browser-accessible without the ingress anyway).

### Slice 2 — Kustomize overlays (must follow Slice 1; deploy env by env)
- Add `ALLOWED_ORIGINS` literals to dev, stage, prod `kustomization.yaml` configMapGenerator.
- Rolling restart picks up the new configmap.
- Smoke-test each environment after restart.

### Slice 3 — (Optional) Tighten `allow_methods` and `allow_headers`
- Out of scope for this ticket; create a follow-up if desired.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A legitimate origin is missing from the list and users get CORS errors | Low | Medium — users see blocked requests | Test AC-2 before prod deploy; list all three env origins in respective overlays |
| Dev overlay missing `localhost:3000` breaks local development | Low | Low — dev env only | Default in `config.py` always includes `localhost:3000`; overlay value appends to it after parsing |
| Slice 1 deployed without Slice 2 in prod — backend rejects prod frontend temporarily | Low | Low — backend is not directly accessed by browsers; Next.js BFF is server-side and does not send CORS headers | Coordinate deploy order; ship Slice 2 immediately after Slice 1 in prod |
| Future developer adds `"*"` back thinking it's needed | Low | Medium | Comment in `config.py` and `main.py` explaining the restriction |

---

## Phase 10 — Definition of Done

- [ ] `allow_origins=["*"]` removed from `backend/app/main.py`
- [ ] `allowed_origins` field added to `backend/app/config.py` with `field_validator`
- [ ] `backend/tests/test_cors.py` written and all assertions pass
- [ ] `pytest backend/tests/` passes with no regressions
- [ ] `ALLOWED_ORIGINS` literal added to dev, stage, and prod kustomize overlays
- [ ] Manual smoke test: `curl -H "Origin: https://evil.com"` against dev returns no `Access-Control-Allow-Origin` header
- [ ] Manual smoke test: preflight from actual frontend host on dev succeeds
- [ ] Deployed to dev overlay and rolling restart confirmed healthy
- [ ] No regressions in Next.js BFF → backend calls (check browser network tab or k8s logs)

---

## Original Implementation Plan (retained)

- [ ] Add `allowed_origins: list[str]` to `backend/app/config.py` with sensible defaults
- [ ] Update `backend/app/main.py` to use `settings.allowed_origins`
- [ ] Set correct values in each overlay's environment (dev, stage, prod)
- [ ] Verify local dev (`localhost:3000`) still works
- [ ] Verify cross-origin preflight from the actual frontend host succeeds
