# 040 — Security: Validate repo_url Format in SkillCreate Schema

**Status:** ✅ Complete
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M4)
**Follow-up:** [#045](045-sec-repo-url-skill-path-allowlist.md) tightens the `_GITHUB_URL_RE` check added here.

---

## Problem & Goal

### What is broken today

`SkillCreate.repo_url` in `backend/app/schemas/skill.py` (line 29) is a plain `str` with no
validation. `source_type` (line 40) is also `str = "github"` with no type restriction.

In `backend/app/services/skill.py` line 392, the create path is:
```python
repo_url = extract_repo_root_url(data.repo_url) or data.repo_url
```
If `extract_repo_root_url()` returns `None` (input is not a recognisable GitHub URL), the raw
user-supplied string is stored verbatim in MongoDB (line 449: `repo_url=repo_url`) and immediately
returned in every `SkillOut`, `SkillListOut`, and `SkillSummaryOut` response served to all callers.

Attack surface:
- Very long strings (DoS via bandwidth / frontend rendering)
- Non-HTTP URIs (`javascript:`, `data:`, `file://`) — exploitable if any client renders `repo_url`
  as an `<a href>` without its own sanitisation
- Newline injection into log lines (skill.py line 383 logs `repo_url` directly)
- Invalid `source_type` values that bypass the `"github"` branch in `_create_local` at line 389

**Key observation**: `_GITHUB_URL_RE = re.compile(r"^https://github\.com/[^/]+/[^/]+$")` already
exists at `backend/app/schemas/skill.py` line 13 and is already used in `SkillUpdate.validate_forked_from_url`
(lines 55–64). The fix is a direct parallel — apply the same pattern to `SkillCreate`.

### What success looks like

- `POST /api/skills` with a non-GitHub or malformed `repo_url` returns HTTP 422 before any DB write.
- `source_type` values other than `"github"` or `"local"` return HTTP 422.
- Raw user input is never stored as `repo_url` in MongoDB.
- No change to the happy path for legitimate submissions.

### Out of scope

- Validating `repo_url` on already-stored (legacy) records — a migration is not warranted for MEDIUM severity.
- The unvalidated `repo_url` query param on `GET /api/github-preview` (skills.py line 547) — that
  endpoint is rate-limited to 10/min and never stores the value; track separately if desired.
- Frontend URL display/sanitisation — `readme-render.tsx` already uses DOMPurify; frontend link
  rendering is a separate concern.

### Constraints

- Must not break `source_type="local"` submissions, which set `repo_url` to a `local://...` string
  (used in `_create_local`, skill.py line 549).
- Must not break any existing passing tests.
- No schema migration required — validation is at the API layer only.
- Fix must deploy via the existing kustomize/Docker build pipeline (no infra changes).

---

## User Stories

1. As a **developer submitting a GitHub skill**, I want the API to reject obviously malformed URLs
   immediately, so that I get a clear error before wasting time on a bad submission.
2. As an **admin reviewing submissions**, I want every stored `repo_url` to be a canonical
   `https://github.com/<owner>/<repo>` URL, so that filters and deduplication work reliably.
3. As an **API consumer** (CLI, frontend), I want the API to return a structured 422 with a
   human-readable `detail` field when `repo_url` is invalid, so that I can surface a useful error
   message without special-casing.
4. As an **attacker**, I want to store `javascript:alert(1)` as `repo_url`, so that clients that
   render it as an `<a href>` execute arbitrary JavaScript — **this must be prevented**.
5. As an **attacker**, I want to submit a 1 MB string as `repo_url` to inflate response payloads and
   MongoDB document sizes — **this must be prevented**.
6. As an **attacker**, I want to set `source_type="foobar"` to reach an unintended code path — **this
   must be prevented**.
7. As a **developer submitting a local skill** (`source_type="local"`), I want `repo_url` set to
   `local://<path>` to be accepted without GitHub URL validation, so that local submissions continue
   to work.
8. As a **security auditor**, I want to see that input validation is enforced at the Pydantic schema
   layer (not just in service logic), so that it is independently testable and not bypassable by
   future refactors.
9. As a **log analyst**, I want `repo_url` values in log lines to be safe (no newlines or control
   characters), so that log injection attacks do not corrupt audit trails.
10. As an **engineer on call**, I want the fix to be a pure schema change with no DB migration or
    service-layer side effects, so that rollback is trivial (revert + redeploy).

---

## Requirements

### Functional requirements

**FR-1:** `SkillCreate.repo_url` must pass a Pydantic `@field_validator` that, for
`source_type="github"`, enforces the pattern `^https://github\.com/[^/]+/[^/]+$` after running
the value through `extract_repo_root_url()` (to accept subdirectory URLs and normalise them to the
repo root). Raises `ValueError` on mismatch.

**FR-2:** `SkillCreate.source_type` must be changed from `str = "github"` to
`Literal["github", "local"] = "github"`. Values outside this set must produce HTTP 422.

**FR-3:** For `source_type="local"`, the `repo_url` validator must skip the GitHub URL check
(local submissions legitimately use `local://` URIs).

**FR-4:** The validator must cap `repo_url` length at 500 characters and reject values containing
newlines or null bytes, regardless of `source_type`.

**FR-5:** Error responses must include a human-readable `detail` message identifying the invalid
field (Pydantic default behaviour; no custom handler required).

### Non-functional requirements

**NFR-1 (performance):** The validator is a pure regex/string check with no I/O; added latency must
be under 1 ms per request.

**NFR-2 (compatibility):** All existing callers that submit valid `https://github.com/<owner>/<repo>`
URLs (including subdirectory variants normalised by `extract_repo_root_url`) must continue to work
without any client-side changes.

**NFR-3 (testability):** The validator must be testable in isolation via `SkillCreate(...)` without
spinning up FastAPI or MongoDB.

**NFR-4 (consistency):** The new validator must reuse the existing `_GITHUB_URL_RE` constant
(skill.py line 13) and `extract_repo_root_url` function to avoid divergent regex definitions.

### Acceptance criteria

**AC-1:** Given `source_type="github"`, when `repo_url="not-a-url"` is submitted, then `SkillCreate`
raises `ValueError` and `POST /api/skills` returns HTTP 422.

**AC-2:** Given `source_type="github"`, when `repo_url="https://github.com/owner/repo/tree/main/subdir"`
is submitted, then the validator normalises it to `https://github.com/owner/repo` and accepts it.

**AC-3:** Given `source_type="github"`, when `repo_url="javascript:alert(1)"` is submitted, then
`POST /api/skills` returns HTTP 422.

**AC-4:** Given `source_type="github"`, when `repo_url` exceeds 500 characters, then HTTP 422 is
returned.

**AC-5:** Given `source_type="local"`, when `repo_url="local:///tmp/myskill"` is submitted, then
the validator passes without error (the local submission flow continues as before).

**AC-6:** Given `source_type="foobar"`, then `POST /api/skills` returns HTTP 422.

**AC-7:** Given `repo_url="https://github.com/owner/repo\nX-Injected: evil"`, then HTTP 422 is
returned.

**AC-8:** All pre-existing tests in `backend/tests/test_skill_crud.py` continue to pass.

---

## ADRs

**ADR-040-1: Validate at schema layer using the existing `_GITHUB_URL_RE` constant**

Status: Accepted

Context: Validation could be added at the Pydantic schema layer (`SkillCreate`) or in
`SkillRepository.create()`. The schema already has a parallel validator (`validate_forked_from_url`
in `SkillUpdate`) using `_GITHUB_URL_RE` (line 13) and `_normalize_github_url`.

| Option | Pro | Con |
|---|---|---|
| Schema-layer `@field_validator` | Rejects before service logic; independently testable; consistent with `SkillUpdate` pattern | Validator must know about `source_type` (cross-field check) |
| Service-layer guard in `SkillRepository.create()` | No cross-field validator complexity | Not testable without DB; duplicates logic |

Decision: Schema-layer validator on `SkillCreate`, using `info.data` to read `source_type` for
the conditional check. Reuses `_GITHUB_URL_RE` and `extract_repo_root_url` already in scope.

Consequences: The validator depends on field ordering in `SkillCreate` — `source_type` must be
declared before `repo_url` for `info.data` to populate it. (It already is: lines 29/40.)

---

**ADR-040-2: Accept subdirectory GitHub URLs by normalising through `extract_repo_root_url` first**

Status: Accepted

Context: Some callers (e.g., the GitHub scan UI flow) may submit full tree/blob URLs like
`https://github.com/owner/repo/tree/main/skills/foo`. `service/skill.py` already normalises these
via `extract_repo_root_url` (line 392). Rejecting them at the schema layer would break that flow.

Decision: Run `extract_repo_root_url(v)` inside the validator and validate the normalised result
against `_GITHUB_URL_RE`. Store the normalised value, not the raw input.

Consequences: Normalisation happens twice (once in validator, once in service create). This is
harmless and idempotent; avoids changing service-layer logic.

---

## Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/schemas/skill.py` | Modify | Add `@field_validator("repo_url")` to `SkillCreate`; change `source_type: str` to `Literal["github", "local"]`; add `max_length` and newline checks | Yes — unit test `SkillCreate(...)` directly |
| `backend/tests/test_skill_create_validation.py` | New file | Unit tests for all AC-1..AC-8 validator cases | Yes — pure Pydantic, no DB |

No router, service, model, or infrastructure changes are required.

---

## System / Infrastructure Design

### Attack interception: data flow

```
Client
  │
  │  POST /api/skills  {repo_url: "javascript:alert(1)", source_type: "github"}
  ▼
FastAPI route (skills.py:159)
  │
  │  body: SkillCreate = ...   ← Pydantic parses + runs validators
  │
  ├─ [NEW] SkillCreate.validate_repo_url()
  │    • source_type == "github": run extract_repo_root_url(v)
  │    • check len <= 500, no newlines
  │    • match _GITHUB_URL_RE
  │    • raise ValueError → FastAPI returns HTTP 422  ◄── ATTACK STOPPED HERE
  │
  └─ [existing] SkillRepository.create(body, submitter_id)
       │
       └─ extract_repo_root_url(data.repo_url) or data.repo_url
          Skill(..., repo_url=repo_url)
          await skill.insert()
```

### Before / after: `SkillCreate` schema

**Before (line 29–41):**
```python
class SkillCreate(BaseModel):
    repo_url: str                   # no validation
    source_type: str = "github"     # accepts any string
    ...
```

**After:**
```python
from typing import Literal
from app.services.github import extract_repo_root_url

_MAX_REPO_URL_LEN = 500

class SkillCreate(BaseModel):
    repo_url: str
    source_type: Literal["github", "local"] = "github"
    ...

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url(cls, v: str, info) -> str:
        if len(v) > _MAX_REPO_URL_LEN:
            raise ValueError(f"repo_url must be <= {_MAX_REPO_URL_LEN} characters")
        if "\n" in v or "\r" in v or "\x00" in v:
            raise ValueError("repo_url must not contain newlines or null bytes")
        source_type = (info.data or {}).get("source_type", "github")
        if source_type == "github":
            normalized = extract_repo_root_url(v)
            if not normalized or not _GITHUB_URL_RE.match(normalized):
                raise ValueError(
                    "repo_url must be a valid GitHub repository URL "
                    "(e.g. https://github.com/owner/repo)"
                )
            return normalized
        return v
```

Note: `_GITHUB_URL_RE` is already defined at line 13 of `skill.py`; no import needed.
`extract_repo_root_url` must be imported from `app.services.github` (or use a local import to
avoid a circular dependency — check at implementation time; a local import inside the validator
is acceptable).

---

## Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Reject subdirectory GitHub URLs (strict) | Simpler validator | Breaks callers that submit tree/blob URLs |
| Normalise subdirectory URLs (chosen) | Backward compatible; consistent with service layer | Validator slightly more complex; normalisation runs twice |
| `Literal["github", "local"]` for `source_type` | Rejects unknown values at schema layer | Any future `source_type` (e.g. `"gitlab"`) requires a schema change first |
| Schema-layer validation only (no DB migration) | Zero downtime; easy rollback | Legacy records with bad URLs remain in DB (acceptable for MEDIUM) |

---

## Delivery Slices

**Slice 1 (core fix — ship first):** Add `@field_validator("repo_url")` to `SkillCreate` in
`backend/app/schemas/skill.py`. Change `source_type` to `Literal["github", "local"]`. Write new
test file `backend/tests/test_skill_create_validation.py` covering AC-1..AC-7.

**Slice 2 (regression guard — ship with Slice 1 or immediately after):** Verify all existing
`backend/tests/test_skill_crud.py` tests pass unchanged. Add AC-8 check to CI.

These two slices can be merged as a single PR. No Slice 3 is needed.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Circular import: `extract_repo_root_url` from `app.services.github` imported into `app.schemas.skill` | Low — schemas already import from models | Build failure | Use a local import inside the validator method, or inline a minimal regex |
| `source_type` field ordering: `info.data` doesn't contain `source_type` if it fails validation first | Low | Validator falls back to `"github"`, rejects valid `local://` URL | `source_type: Literal[...]` validates before `repo_url` due to Pydantic field order; add a test |
| Existing CLI callers send subdirectory GitHub URLs | Medium | AC-2 must pass; normalisation ensures backward compat | Covered by AC-2 test |
| Legacy DB records with bad URLs cause `SkillOut` serialisation failures | None — `SkillOut.repo_url: str` has no validator | No impact | Out of scope; monitor if needed |

---

## Definition of Done

- [ ] `@field_validator("repo_url")` added to `SkillCreate` in `backend/app/schemas/skill.py`
- [ ] `source_type` changed to `Literal["github", "local"]` in `SkillCreate`
- [ ] `backend/tests/test_skill_create_validation.py` created, covering AC-1 through AC-7
- [ ] All existing tests in `backend/tests/test_skill_crud.py` pass without modification (AC-8)
- [ ] Full test suite passes: `pytest backend/tests/`
- [ ] Manual smoke test: `POST /api/skills` with `repo_url="javascript:alert(1)"` → 422;
      `repo_url="https://github.com/owner/repo"` → 201
- [ ] Deployed to dev overlay via kustomize; no pod crash-loops
- [ ] No regressions in `GET /api/skills` or `GET /api/skills/{slug}`
