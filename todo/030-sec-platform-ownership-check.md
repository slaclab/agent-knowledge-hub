# 030 — Security: Missing Ownership Check on Platform Mutations

**Status:** ✅ Complete
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H1)

---

## Phase 1 — Problem & Goal

### What is broken today

`POST /api/skills/{slug}/platforms` (lines 350–363) and
`DELETE /api/skills/{slug}/platforms/{platform}` (lines 366–373) in
`backend/app/routers/skills.py` require authentication but apply **no ownership or
admin check** after the skill is fetched.

Any authenticated user — via Next.js BFF (X-Internal-Secret path) or CLI Bearer JWT
path — can call these endpoints against any slug they do not own.

Attack scenarios:
- **Sabotage:** attacker calls `DELETE /api/skills/important-skill/platforms/claude-code`
  to remove a platform tag from a competitor's skill, making it invisible in the
  `platforms=claude-code` filter without triggering any visible change to the skill record.
- **Pollution:** attacker calls `POST /api/skills/important-skill/platforms` with
  `{"platform": "bogus-platform"}` to inflate a skill's platform coverage or
  invalidate the platform_counts facet cache.

Compare with every other mutating endpoint in the same file:
- `PATCH /{slug}` — line 298: ownership check present
- `DELETE /{slug}` — line 313: ownership check present
- `POST /{slug}/refetch` — line 323: ownership check present
- `POST /{slug}/pin` — line 335: ownership check present

The platform endpoints were added later (feature #025) and the guard was never
ported across.

### What success looks like

After the fix:
- Non-owner calling `POST /{slug}/platforms` or `DELETE /{slug}/platforms/{platform}`
  receives HTTP 403 with `{"detail": "Not your skill"}`.
- Owner and admin retain full mutation rights, unchanged.
- All existing tests continue to pass.

### Out of scope

- Changing what platforms are considered valid (no allowlist here).
- Rate-limiting platform mutations (separate concern).
- Frontend UI changes — the UI already checks ownership client-side; this is a
  backend guard only.

### Constraints

- Must not touch the auth dependency chain or middleware — only add inline checks.
- Must deploy through the existing kustomize overlay pipeline with no manifest changes.
- Fix must be backward-compatible: no API schema change, same response shapes.

---

## Phase 1.5 — User Stories

1. As a **skill owner**, I want only I (and admins) to be able to modify my skill's
   platform tags, so that my skill is discoverable by the platforms I chose.

2. As an **admin**, I want to add or remove platform tags on any skill, so that I can
   curate catalog quality without needing to impersonate owners.

3. As an **authenticated attacker**, I should be denied when I try to remove a platform
   tag from a skill I do not own, so that I cannot sabotage competitors' discoverability.

4. As an **authenticated attacker**, I should be denied when I try to add a spurious
   platform tag to a skill I do not own, so that I cannot pollute catalog facets.

5. As a **CLI user** (Bearer JWT path), I want the same ownership rules to apply as
   for the web UI path, so that the platform tags I set on my skills are stable.

6. As an **API consumer** (CI pipeline), I want a clear 403 response when my token
   lacks ownership of the target skill, so that my pipeline fails loudly rather than
   silently succeeding.

7. As a **developer reading the code**, I want platform mutation endpoints to follow
   the same guard pattern as all other skill mutations, so that the security invariant
   is easy to audit.

8. As a **QA engineer**, I want automated tests confirming non-owners get 403 on both
   endpoints, so that this regression can never silently re-appear.

---

## Phase 2 — Requirements

### Functional requirements

FR-1: `POST /api/skills/{slug}/platforms` MUST return HTTP 403 when the authenticated
user is not the skill's `submitter_id` and `user.is_admin` is false.

FR-2: `DELETE /api/skills/{slug}/platforms/{platform}` MUST return HTTP 403 under the
same condition.

FR-3: The 403 response body MUST be `{"detail": "Not your skill"}` — consistent with
all other ownership-guarded endpoints.

FR-4: The guard MUST be applied after the skill fetch (so 404 still beats 403 for
non-existent slugs — avoids slug-enumeration via timing).

FR-5: Admins (`user.is_admin == True`) MUST be able to mutate platforms on any skill.

FR-6: Owners (`skill.submitter_id == user.user_id`) MUST retain full mutation rights.

### Non-functional requirements

NFR-1: **Performance** — the fix adds zero additional I/O; the skill document is
already fetched before the guard runs. Latency impact < 0.1 ms.

NFR-2: **Compatibility** — no change to request/response schema, HTTP method, or URL
structure. Existing callers with correct ownership see identical responses.

NFR-3: **Consistency** — guard pattern must be textually identical to the pattern used
at lines 298–299, 313, 323, and 335 of `backend/app/routers/skills.py`.

### Acceptance criteria

AC-1: Given a skill owned by user `alice`, when user `bob` (non-admin) calls
`POST /api/skills/{slug}/platforms` with a valid payload, then the response is
HTTP 403 with body `{"detail": "Not your skill"}`.

AC-2: Given a skill owned by user `alice`, when user `bob` (non-admin) calls
`DELETE /api/skills/{slug}/platforms/claude-code`, then the response is HTTP 403
with body `{"detail": "Not your skill"}`.

AC-3: Given a skill owned by user `alice`, when `alice` calls either endpoint, then
the response is HTTP 200/204 and the platform list is updated.

AC-4: Given a skill owned by user `alice`, when an admin user calls either endpoint,
then the response is HTTP 200/204 and the platform list is updated.

AC-5: Given a non-existent slug, when any authenticated user calls either endpoint,
then the response is HTTP 404 (404 takes precedence over 403).

---

## Phase 3 — ADRs

**ADR-030-1: Inline guard vs. shared Depends() helper**

Status: Accepted

Context: The same two-line ownership check appears in four endpoints already. A shared
`require_skill_owner(skill, user)` helper function would DRY this up, but introduces
more refactoring surface for a security fix.

Options considered:

| Option | Pro | Con |
|---|---|---|
| Inline check (matching existing pattern) | Zero refactor risk; easy to audit by grep | Minor duplication |
| New `assert_owner_or_admin(skill, user)` helper | DRY; single point of change for future policy | Larger diff; risks breaking four existing endpoints |

Decision: Use the inline pattern (`if skill.submitter_id != user.user_id and not
user.is_admin: raise HTTPException(403, "Not your skill")`) — identical to lines
298–299. A clean-up to a shared helper can follow as a separate non-security task.

Consequences: Duplication increases slightly. The pattern is now in six places and
easy to grep. Future policy changes (e.g. org-level ownership) must be applied in all
six spots until the refactor happens.

---

## Phase 3.5 — Module Design

| Module / file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `backend/app/routers/skills.py` | Bug fix | Add 2-line ownership guard in `add_platform` (after line 355) and `remove_platform` (after line 370) | Yes — unit-testable via FastAPI `TestClient` with mocked auth |
| `backend/tests/test_platform_ownership.py` | New file | Four test cases: non-owner POST → 403, non-owner DELETE → 403, owner POST → 200, admin DELETE → 204 | Yes — standalone pytest module |

No schema changes, no migration, no manifest changes, no frontend changes.

---

## Phase 4 — System / Infrastructure Design

### Attack path (before fix)

```
Attacker (authenticated)
  │
  ▼
POST /api/skills/victim-skill/platforms   {"platform": "bogus"}
  │
  ▼
add_platform()
  │
  ├── Skill.find_one(slug == "victim-skill")   ← skill fetched
  │                                              ← NO OWNERSHIP CHECK
  ├── skill.compatible_platforms += ["bogus"]
  └── skill.save()                              ← mutation succeeds ✓ (WRONG)
```

### Fixed path (after fix)

```
Attacker (authenticated)
  │
  ▼
POST /api/skills/victim-skill/platforms   {"platform": "bogus"}
  │
  ▼
add_platform()
  │
  ├── Skill.find_one(slug == "victim-skill")   ← skill fetched
  │
  ├── if skill.submitter_id != user.user_id    ← OWNERSHIP CHECK ✓
  │      and not user.is_admin:
  │       raise HTTP 403 "Not your skill"      ← request rejected
  │
  └── (mutation never reached)
```

### Same fix applies to `remove_platform` — identical flow.

### No API contract change — request/response shapes are unchanged.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Inline guard (no helper) | Minimal diff; no regression risk on existing endpoints | Minor code duplication (6 call sites) |
| 403 before mutation, after 404 | Correct HTTP semantics; no slug enumeration via 403 timing | Slightly more code than a single early-return |
| No allowlist for platform values | No breaking change; platform vocabulary stays flexible | Admins/owners can still set arbitrary strings |

---

## Phase 8 — Delivery Slices

This is a two-file, four-line fix. A single slice is appropriate.

**Slice 1 (the only slice) — add guard + tests, ship to dev:**
1. Add ownership check to `add_platform` in `skills.py` (2 lines, after line 355).
2. Add ownership check to `remove_platform` in `skills.py` (2 lines, after line 370).
3. Add `backend/tests/test_platform_ownership.py` with four test cases.
4. Run full test suite locally; deploy to dev overlay.

Each step is safe to review independently. No feature flags required.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Regression: owner path broken | Low — pattern is already proven in 4 other endpoints | High — owners can no longer manage their skills | AC-3 test covers owner happy path |
| Regression: admin path broken | Low | High — admins lose curation ability | AC-4 test covers admin happy path |
| Guard placed after mutation (wrong order) | Low — code review catches this | High — fix is ineffective | PR review checklist; AC-1/AC-2 tests would fail |
| Test isolation issue (shared DB state in test suite) | Medium — existing tests use mongomock | Low — test will be flaky, not wrong | Follow fixture pattern from `test_skill_crud.py` |

---

## Phase 10 — Definition of Done

- [ ] Ownership guard added to `add_platform` in `backend/app/routers/skills.py`
- [ ] Ownership guard added to `remove_platform` in `backend/app/routers/skills.py`
- [ ] `backend/tests/test_platform_ownership.py` written with 4 test cases (non-owner POST → 403, non-owner DELETE → 403, owner POST → 200, admin DELETE → 204)
- [ ] All existing tests pass (`pytest backend/tests/`)
- [ ] Manual smoke test: authenticated non-owner call to both endpoints returns 403
- [ ] Manual smoke test: owner call to both endpoints succeeds
- [ ] Deployed to dev overlay via kustomize; no pod restarts required
- [ ] No regressions observed in platform filter behaviour (`test_platform_filter.py` all green)

---

## Implementation Plan

- [ ] Add ownership guard to `POST /api/skills/{slug}/platforms` in `backend/app/routers/skills.py` (after the 404 check at line 355, before the platform mutation)
- [ ] Add ownership guard to `DELETE /api/skills/{slug}/platforms/{platform}` in `backend/app/routers/skills.py` (after the 404 check at line 370, before the mutation)
- [ ] Add `backend/tests/test_platform_ownership.py`: non-owner calling both endpoints returns 403
- [ ] Add tests: owner and admin can still mutate platforms (regression guards)
