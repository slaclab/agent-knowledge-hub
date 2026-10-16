# TODO #045 — Allow-list `repo_url` and `skill_path` characters at create time

> **Priority:** 🟠 P1 — High
> **Severity:** HIGH
> **Status:** 🏁 Implementation Done (not yet deployed)
> **Branch:** `fix/045-allowlist`
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Provenance

**Raised by:** #006 board review 2026-10-14, security-review Round 1 (HIGH finding, deferred to its own task by user decision).

**References:**
- [#006](006-skillsets.md) — blocked by this task: #006 Slice 4 (`install skillset`) must not merge until this task is deployed to production, because Slice 4 clones members chosen by another user and goes live when it merges. #006 FR-7 › Argument rule is the client-side half of the same protection.
- [#040](040-sec-repo-url-validation.md) — this task tightens the `_GITHUB_URL_RE` check that #040 added. #040's plan also specified a 500-character limit and newline rejection for `repo_url`; the shipped validator has neither.
- [#012](012-moderation-flags-and-admin-deactivation.md) — cleanup path: admin deactivation is the existing way to withdraw a stored skill whose values fail the new check.

---

## Problem Statement

The catalog stores `repo_url` and `skill_path` values that can carry shell syntax, and the `/agent-knowledge-hub` skill passes both values to `git clone` and `cp` on the installing user's machine.

- `SkillCreate.validate_repo_url` in `backend/app/schemas/skill.py` checks `repo_url` against `_GITHUB_URL_RE` (`^https://github\.com/[^/]+/[^/]+$`). The class `[^/]` matches every character except `/`, including `$`, `(`, `)`, `;`, `'`, a space, and a newline.
- `Skill.validate_skill_path` in `backend/app/models/skill.py` rejects only `..` components and values longer than 500 characters.
- `create()` in `backend/app/services/skill.py` stores a skill even when the GitHub fetch or the repository scan fails, so an unreachable or malformed repository still becomes a catalog entry.
- `skill/SKILL.md` › Install tells the agent to clone `repo_url` and copy from `skill_path`. The agent builds those commands from the stored text.
- The `[CREATE]` log line in `create()` formats `repo_url` and `skill_path` with `%s`. A newline inside either value writes a forged line into the backend log, and #006 NFR-5 makes that log the audit record for skillset writes.

Any signed-in user can submit a skill. With #006, any signed-in user can also put that skill into a skillset that other users install with one command.

### What fails today

Measured with the probe in Measured facts › current-validation.

| Input | Field | Current behaviour | Desired behaviour |
|---|---|---|---|
| `https://github.com/a/$(touch x)` | `repo_url` | Accepted | 422 |
| `https://github.com/a;id/b` | `repo_url` | Accepted | 422 |
| `https://github.com/a\nINFO fake/b` (inner newline) | `repo_url` | Accepted | 422 |
| `https://github.com/a/b'c` | `repo_url` | Accepted | 422 |
| `https://github.com/a/` followed by a 5000-character name | `repo_url` | Accepted | 422 |
| `/a/$(id)`, `/a;b`, `/a\nb`, `/a b` | `skill_path` | Accepted | 422 |
| `https://github.com/slaclab/lcls-tools`, `/skills/x` | both | Accepted | Accepted |

---

## Goals

1. `POST /api/skills` with `source_type="github"` returns 422 for a `repo_url` that #006 FR-7 › Argument rule would refuse, so every entry the catalog stores can be installed by `install skillset`.
2. Every create path returns 422 for a `skill_path` outside the character set that FR-7 › Argument rule accepts.
3. The `[CREATE]` log line cannot be split by a submitted value.
4. The number of already-stored skills that fail the new checks is known on dev and prod before this task deploys.
5. The task is deployed to production before #006 Slice 4 merges.

## Non-Goals

- Rewriting or deleting stored records. The read-only query reports failing entries; withdrawing one is an admin decision through #012 deactivation.
- Requiring a successful GitHub fetch at create time. See Open Questions.
- `source_type="local"` submissions, whose `repo_url` is a `local://` string. `install skillset` already treats that value as a path-guard abort.
- The `repo_url` query parameter on `GET /api/github-preview`, which #040 also left out of scope. The endpoint never stores the value.
- The identity-header question in `backendHeaders()` (`frontend/app/api/_internal.ts`), which #006 Follow-ups records separately.

---

## User Stories

**As a** user running `install skillset` **I want** every member's `repo_url` and `skill_path` to be safe to quote into a shell command **so that** a skillset curated by someone else cannot run code on my machine.

- **AC:** `POST /api/skills` with `repo_url="https://github.com/a/$(touch x)"` returns 422 and stores nothing.
- **AC:** `POST /api/skills` with `skill_path="/a;b"` returns 422 and stores nothing.

**As a** skill submitter **I want** a valid GitHub URL and path to keep working **so that** the stricter check does not break normal submissions.

- **AC:** `POST /api/skills` with `repo_url="https://github.com/slaclab/lcls-tools"` and `skill_path="/skills/x"` returns 201, as it does today.

**As an** admin reading backend logs **I want** each `[CREATE]` entry to stay on one line **so that** a submitted value cannot forge an audit record.

- **AC:** a `[CREATE]` record for a value containing `\n` renders the newline as the two characters `\n`.

---

## Requirements

### Functional

| ID | Requirement | Verified by |
|---|---|---|
| FR-1 | For `source_type="github"`, `SkillCreate` rejects a `repo_url` that, after the existing `strip()`, does not match `^https://github\.com/[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$`. The owner segment follows GitHub's username rules; the length bounds come from GitHub's limits. | `backend/tests/test_skill_create_validation.py` (new file) |
| FR-2 | `Skill.validate_skill_path` keeps its `..` and length checks and also rejects a value that does not match `^/[A-Za-z0-9._/-]*$` after its existing leading-slash normalisation. | `backend/tests/test_skill_create_validation.py` (new file) |
| FR-3 | The `[CREATE] submitter=... repo_url=... skill_path=...` line in `create()` formats `repo_url` and `skill_path` with `%r`. | `caplog` test on a value containing `\n` |
| FR-4 | One read-only query lists every stored skill with `source_type` other than `local` whose `repo_url` or `skill_path` fails FR-1 or FR-2, run on dev and prod before deploy. The result is recorded in Measured facts. | Measured facts › stored-failing |

### Non-functional

| ID | Requirement | Budget | Verified by |
|---|---|---|---|
| NFR-1 | Every pattern FR-1 and FR-2 accept is accepted by #006 FR-7 › Argument rule, so a stored entry never fails the install loop's own check. | — | Comparison test of the two patterns over the FR-1 and FR-2 fixtures |
| NFR-2 | The existing backend suite passes unchanged except for tests that submit values the new checks reject. | Baseline in #006 Measured facts › test-baseline | `python -m pytest -q` in `backend/` |

---

## Design

### Architecture

```
POST /api/skills
  └─ SkillCreate (Pydantic)
       ├─ validate_repo_url        ← FR-1: tighten _GITHUB_URL_RE
       └─ skill_path: str
  └─ skill_repository.create()
       ├─ logger.info("[CREATE] ...")   ← FR-3: %r for repo_url, skill_path
       └─ Skill(...)
            └─ validate_skill_path      ← FR-2: add character allow-list
```

### Key Decisions

- **The server pattern matches #006 FR-7's client pattern, plus length bounds.** A stricter server check would refuse nothing extra that matters; a looser one would let the catalog store entries the install loop refuses.
- **`_GITHUB_URL_RE` is tightened in place.** `SkillUpdate.validate_forked_from_url` also uses it, so `forked_from_url` gets the same check. Whether that is wanted is an open question.

### Trade-offs

| Decision | Gains | Costs | Accepted because |
|---|---|---|---|
| ASCII-only allow-list | One rule shared with the install loop; trivially quotable | A repository or path with other characters cannot be submitted | GitHub owner and repository names are already limited to this set |
| Report stored failures instead of migrating | No write to stored data; trivial rollback | Failing entries stay listed until an admin acts | #012 deactivation exists for this |

---

## Implementation Plan

### Step 1 — `backend/app/schemas/skill.py`
Tighten `_GITHUB_URL_RE` to the FR-1 pattern.

### Step 2 — `backend/app/models/skill.py`
Add the FR-2 allow-list to `validate_skill_path`.

### Step 3 — `backend/app/services/skill.py`
Change the two `%s` placeholders for `repo_url` and `skill_path` in the first `[CREATE]` line to `%r`.

### Step 4 — tests
Create `backend/tests/test_skill_create_validation.py` with a case for every input in Problem Statement › What fails today, plus a `caplog` test for FR-3 and the NFR-1 comparison test.

### Step 5 — read-only query
Run the FR-4 query on dev and prod with `kubectl exec` into the backend pod and record the counts.

---

## Implementation Checklist

- [x] Step 1 — `_GITHUB_URL_RE` tightened
- [x] Step 2 — `skill_path` allow-list added
- [x] Step 3 — `[CREATE]` line uses `%r`
- [x] Step 4 — tests written and passing
- [x] Step 5 — stored-failing counts recorded for dev and prod
- [ ] Deployed to production before #006 Slice 4 merges

---

## Problems & Solutions

### Problem: #040 shipped narrower than its plan
**Encountered:** 2026-10-14
**Root cause:** #040's Design specified a 500-character limit and newline rejection for `repo_url`. The shipped `SkillCreate.validate_repo_url` is a `model_validator` that only matches `_GITHUB_URL_RE`, #040's planned test file, `backend/tests/test_skill_create_validation.py`, does not exist, and #040's Definition of Done boxes are unticked although its status is ✅ Complete.
**Solution:** FR-1's anchored character class and length bounds cover both missing checks.

---

### Deviation: `skill_path` is also checked in the request body
**Encountered:** 2026-10-16
**Root cause:** FR-2 places the allow-list in `Skill.validate_skill_path`, which runs only when `create()` builds the `Skill` document. That happens after the GitHub fetch and scan, and a `ValueError` there reaches the generic exception handler instead of becoming a 422.
**Solution:** `normalize_skill_path()` in `backend/app/models/skill.py` holds the check, and both `Skill.validate_skill_path` and a new `SkillCreate.validate_skill_path` call it. A bad `skill_path` is now a 422 before any GitHub call, for GitHub and local submissions alike.

### Detail: full-string matches
**Encountered:** 2026-10-16
**Root cause:** Python's `$` also matches before a final newline, so `re.match(r"^/[A-Za-z0-9._/-]*$", "/a/b\n")` succeeds.
**Solution:** both patterns are applied with `fullmatch`. `forked_from_url` goes through `_normalize_github_url`, which returns an unmatched value unstripped, so it uses `fullmatch` too.

## Open Questions

1. **Should `forked_from_url` get the tightened pattern too?** — Recommendation: yes. It shares `_GITHUB_URL_RE` today, and a fork URL is also served to clients. *Decided 2026-10-16: yes, by the shared pattern.*
2. **Should create reject a repository that GitHub cannot fetch?** — Recommendation: no. *Decided 2026-10-16: no.* FR-1 and FR-2 close the injection path, and rejecting on fetch failure would block submissions during a GitHub outage or rate limit.
3. **What happens to stored entries that fail the new checks?** — Recommendation: report them under FR-4 and let an admin deactivate each one through #012. Decide after the counts are known. *Moot 2026-10-16: none fail (Measured facts › stored-failing).*

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| A legitimate submission uses a character outside the allow-list | Low | Low | The allow-list matches GitHub's own name rules; the 422 message names the allowed set | — |
| Stored entries fail the new checks and cannot be installed by `install skillset` | Unknown until FR-4 runs | Low | The install loop reports them as path-guard aborts; #012 deactivation withdraws them | — |
| The client and server patterns drift apart | Medium | Medium | NFR-1 comparison test | — |

---

## Definition of Done

- [x] Every FR and NFR row has a passing verifier
- [x] Every input in What fails today returns its desired behaviour
- [x] Measured facts › stored-failing has dev and prod counts
- [ ] Deployed to production before #006 Slice 4 merges
- [x] CHANGELOG entry added under `## Unreleased`
- [ ] Shipped release written into the Status line

---

## Measured facts — measured 2026-10-14, re-derive before implementing

| Fact | Value | Command | Measured |
|---|---|---|---|
| current-validation | `SkillCreate` accepted every `repo_url` input in What fails today, including the 5000-character name. `Skill.validate_skill_path` accepted every `skill_path` input listed there. | `SkillCreate(repo_url=...)` and `Skill.validate_skill_path(...)` called with `PYTHONPATH=backend` in a venv built from `backend/requirements.txt` | 2026-10-14 |
| stored-sample | All 13 active dev skills without an MCP server have a `repo_url` and `skill_path` that pass FR-1 and FR-2. Deactivated skills and skills with an MCP server were not checked. | Read-only `find` on `skills` in the dev backend pod, from the #006 install-loop spike | 2026-10-14 |
| stored-failing | No stored skill fails FR-1, FR-2 or the tightened `forked_from_url` check: dev checked 13 skills with `source_type` other than `local`, active and deactivated, and prod checked 39. | Read-only `find` with a projection of `slug`, `repo_url`, `skill_path`, `forked_from_url` and `status`, run with `kubectl exec` in each backend pod; it prints only slugs and the failing field | 2026-10-16 |

---

## Board Review

> *Populated by `/board-review` after the board completes. Do not fill manually.*

---

## Relationship to Other Tasks

- **#006 (Skillsets):** This task must be deployed to production before #006 Slice 4 merges. It does not block #006 Slice 1 or Slice 2+3.
- **#040 (repo_url validation):** Complete. This task tightens the regex #040 added.
- **#012 (Moderation):** Complete. Its admin deactivation is the cleanup path for stored entries that fail the new checks.
