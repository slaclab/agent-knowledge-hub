# TODO #059 — The workspace install links `.agents/skills` to `.claude/skills`

> **Priority:** 🟡 P2 — Medium
> **Status:** 🏁 Implementation Done
> **Branch:** `feat/059-agents-skills-link`
> **PR:** —
> **Created:** 2026-10-29
> **Shipped:** —

---

## Provenance

**Raised by:** the deployment owner of Cogito (`slaclab/cogito`), 2026-10-29, as slice 1 of Cogito TODO #285, "One skills folder that every harness reads".

**References:**

- Cogito TODO #285 — dependency: its slice 2 re-pins the client commit in `cogito-host/skillsets.lock` after this change is merged and pushed. Its PRD chose `.agents/skills` as the real folder and made this layout the fallback; § Design below records why this task builds the fallback.
- [#057](057-client-workspace-install.md) — dependency: introduced `--workspace`, `akh-workspace-base` and `akh-workspace-exclude`, which this task extends.

---

## Problem Statement

A workspace install writes to `<workspace>/.claude/skills`, which Claude Code reads. Codex, OpenCode and Omnigent also read `<workspace>/.agents/skills`. Cogito links `.claude/skills` into each harness's home to bridge the gap, and each new harness needs another link. A skill the client installs is not visible to a tool that reads only `.agents/skills`.

## Goals

- After a workspace install, `<workspace>/.agents/skills` is a link to `.claude/skills` when nothing was at that path.
- A path that already exists at `.agents/skills`, or a `.agents` the client must not write, is left untouched.
- Git does not list the link as untracked in a repository, as it does not list the installed skill.

## Non-Goals

- Making `.agents/skills` the real folder. See § Design.
- Changing `~/.claude/skills`, the home install, or any `--workspace` command's use of `<base>/skills`.
- Reloading a skill added after a session starts.

---

## Design

`akh-agents-link`, a new fixed command beside `akh-workspace-modes`, runs after the manifest is written and before `akh-workspace-exclude`. It runs only for a workspace install, takes `<base>`, and does nothing unless `<base>` ends in `.claude` and `<base>/skills` is a folder that is the account's own and that others cannot write. It makes `.agents` with mode `0755` when missing, uses an existing `.agents` only when it is a folder that is the account's own and that others cannot write, and makes `skills` there as the relative link `../.claude/skills`. It prints `akh-workspace: linked .agents/skills` when it made the link, and nothing otherwise. The closing message reports the link in one line.

`akh-workspace-exclude` with `add` also writes `/.agents/skills` to the repository's `info/exclude` when that path is a link to `../.claude/skills`. `remove` leaves the line, because the link stays for other skills.

**Why the real folder stays `.claude/skills`.** Every command that reads or writes an installed skill opens `<base>/skills/<slug>` one folder at a time without following a link (`akh-copy`, `akh-remove`, `akh-workspace-modes`, `akh-workspace-exclude`, `akh-list` and the manifest readers), and `akh-workspace-base` refuses a linked `.claude/skills`. A real `.agents/skills` would put a link on that path and need each of those walks, and the tests behind them, to take a second base. Cogito measured the two layouts on 2026-10-29 and found Claude Code, OpenCode and Codex read either one when the skill exists at session start, so the link direction changes nothing the user sees. The One-real-folder rule in Cogito's #285 still lets a later task flip the direction.

## Requirements

| ID | Requirement | Where | Verified by |
|---|---|---|---|
| FR-1 | A workspace install links `.agents/skills` to `.claude/skills` when nothing is at the path | `akh-agents-link` in `skill/SKILL.md`, under Modes and git | `TestAgentsLink` in `backend/tests/test_client_install_rules.py` |
| FR-2 | An existing `.agents/skills`, whether real, a link or dangling, is left untouched | The same command | `test_a_real_agents_skills_folder_is_left_as_it_is`, `test_an_agents_skills_link_elsewhere_is_left_as_it_is`, `test_a_dangling_agents_skills_link_is_left_as_it_is` |
| FR-3 | A `.agents` that is a link, a file or writable by others is not written | The same command | `test_an_agents_path_the_client_must_not_write_is_left_alone` |
| FR-4 | The link is excluded from git on `add` and the exclusion survives `remove` | `akh-workspace-exclude` | `test_the_link_is_excluded_from_git_and_stays_excluded_after_a_remove` and two negative cases |
| FR-5 | The closing message reports the link | Install › Closing message, the linked line | `WORKSPACE_LINES` in the test file |

## Results

`backend/tests/test_client_install_rules.py` on this branch: 352 passed, 1 failed. The failure, `TestWorkspaceSection::test_words[line10]`, fails on `main` at `474d8db` as well: the home-folder stop message in `skill/SKILL.md` was reworded in client 2.4.2 and the expected line in `WORKSPACE_LINES` still carries the old wording. It is not fixed here.

Run with `PYTHONPATH=<a folder holding pytest> python3 -m pytest --noconftest -p no:cacheprovider backend/tests/test_client_install_rules.py`; the file imports only the standard library and pytest, so `--noconftest` skips the database fixtures.

## Checklist

- [x] `akh-agents-link` and its tests
- [x] `akh-workspace-exclude` covers the link
- [x] Closing-message line, Workspace installs prose and CHANGELOG entry
- [ ] Merged to `main`, pushed to `slaclab/agent-knowledge-hub`
- [ ] Cogito re-pins the commit (Cogito TODO #285 slice 2)
