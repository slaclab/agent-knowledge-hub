# TODO #049 — Security: Refuse Absolute and `..` File Names in Local Skill Submissions

> **Priority:** 🟢 P3 — Low
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Problem Statement

`POST /api/skills` (`create_skill` in `backend/app/routers/skills.py`) accepts a `SkillCreate` body from any signed-in user. When `source_type` is `local`, `snapshotted_files` carries file names and contents of the submitter's choosing. `SkillCreate.snapshotted_files` in `backend/app/schemas/skill.py` is a bare `Dict[str, str]` with no validator, `_create_local` in `backend/app/services/skill.py` stores it as sent, `_build_local_manifest` in `backend/app/services/local.py` copies its keys into `file_manifest` unchanged, and `get_skill_file` serves any manifest path. Nothing refuses a name that is an absolute path or has a `..` segment.

The catalog already applies this rule elsewhere. `create()` in `backend/app/services/skill.py` refuses a `skill_path` with a `..` component, and `LocalScanner._safe_read` in `backend/app/services/local.py` resolves each file it reads from disk and refuses one outside the skill directory. Neither check covers names that arrive in the request body.

This repository's client does not write these names to disk as of 2026-10-14, because it installs by `git clone` (#022). #048 adds an install path that writes the manifest's names beneath `~/.claude/skills/<slug>/` and checks them itself. A name such as `../../settings.json` that slipped past a client check would land in `~/.claude/settings.json`, whose hooks Claude Code runs in later sessions. This task refuses such names at the source, as defence in depth beside #048's FR-2. Severity is LOW, the rating Cogito's security review gave the finding: no shipped client writes the names, and #048 requires its own check.

The Cogito deployment (`slaclab/cogito`, TODO #200) files this task as hub request H-6. No Cogito slice waits for it.

### What fails today

As of 2026-10-14, read from the code:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A signed-in user submits a `local` skill with a file named `../../settings.json` | Stored, listed in `file_manifest`, and served by `get_skill_file` | 422, and nothing is stored |
| The same with `/etc/profile` | Stored and listed | 422 |
| A `local` skill stored before this task with such a name | Served as stored | Listed by FR-2's query for an admin to deactivate |

---

## Goals

1. No `local` skill submitted after this task carries a file name that is absolute or has a `..` segment.
2. Stored skills that carry one are found.

## Non-Goals

- Validating `repo_url` and `skill_path`. That is #045, which leaves `local` submissions out; the two can be built together.
- File names of GitHub skills. Their manifest names are basenames from the GitHub Contents API (`build_file_manifest` in `backend/app/services/github.py` uses `item["name"]`).
- The client's own containment check. That is #048's FR-2.

---

## Requirements

### Functional

- **FR-1:** The hub refuses, at submission, a `local` skill whose file names (`SkillCreate.snapshotted_files` in `backend/app/schemas/skill.py`) include an absolute path or a `..` segment. The refusal is a 422 that says which rule the name breaks, and nothing is stored. A segment is a part of the name between `/` separators.
- **FR-2:** A one-off read-only query lists stored `local` skills whose `snapshotted_files` names break FR-1, because a create-time check does not change stored entries and `SkillUpdate` cannot edit `snapshotted_files`. An admin deactivates each one found (#012). This requirement is not in Cogito's request; it mirrors #045's FR-4, which runs the same kind of query for `repo_url` and `skill_path`.

### Acceptance Criteria

- **AC-1:** Given a `local` submission whose `snapshotted_files` has the key `/etc/profile`, `../x`, `a/../../x`, or `..`, when it is posted, then the response is 422 and no skill is stored.
- **AC-2:** Given a `local` submission with keys `SKILL.md`, `scripts/run.sh`, and `a..b.md`, when it is posted, then the skill is created.
- **AC-3:** Given a `github` submission, when it is posted, then FR-1 does not change the outcome.
- **AC-4:** Given FR-2's query run against production, then its result is recorded in this file with the date, including when it finds nothing.

### Definition of Done

- [ ] FR-1 and FR-2 built; AC-1 to AC-4 pass
- [ ] Tests for AC-1 to AC-3 in `backend/tests/test_skill_create_validation.py`, the file #045 creates
- [ ] CHANGELOG entry

---

## Open Design Questions

1. **Which other names to refuse.** Candidates: a backslash or a drive letter, which a client on Windows reads as a path; NUL; empty and `.` segments; and a name that `get_skill_file`'s `{path:path}` route cannot address.
2. **Where the check lives.** A `field_validator` on `snapshotted_files` in `SkillCreate`, beside the existing `validate_repo_url` model validator, refuses the body before any service code runs. A check in `_create_local` would also cover a future caller that builds `SkillCreate` without validation, which no code does as of 2026-10-14.

---

## Measured facts — read 2026-10-14, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| `snapshotted_files` validation | None: `Dict[str, str] = Field(default_factory=dict)`; the only validator, `validate_repo_url`, skips `local` submissions | `SkillCreate` in `backend/app/schemas/skill.py` |
| How the names reach the manifest | `_create_local` passes `data.snapshotted_files` to `_build_local_manifest`, which sets each entry's `path` to the key | `backend/app/services/skill.py`; `backend/app/services/local.py` |
| Who can submit | Any signed-in user: `create_skill` depends on `get_current_user` | `backend/app/routers/skills.py` |
| Existing `..` check | `create()` raises `ValueError` when `..` is a component of `skill_path` | `backend/app/services/skill.py` |
| Disk-side containment | `_safe_read` resolves the path and calls `relative_to` on the resolved skill root; the module docstring calls this `is_relative_to()` | `backend/app/services/local.py` |
| Severity | LOW | Cogito TODO #200 › Board Review, security reviewer, round 2 |

---

## Relationship to Other Tasks

- **Cogito TODO #200 (`slaclab/cogito`), hub request H-6:** defence in depth beside H-5, which is #048 here. No Cogito slice waits for it.
- **#048 (Install internal skills through the files route):** its FR-2 is the client-side check this task backs up.
- **#040 (Validate `repo_url` in `SkillCreate`):** added the validator this task sits beside.
- **#045 (Allow-list `repo_url` and `skill_path`):** the same kind of create-time check for the other two submitted fields, with the same kind of stored-entries query as FR-2. It leaves `local` submissions out, which this task covers.
- **#012 (Moderation):** the admin deactivation FR-2 relies on.
- **#004 (Multi-source scanner):** introduced the `local` source type.
