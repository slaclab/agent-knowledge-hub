# TODO #046 — marketplace.json Plugin Sources: `git-subdir` with the Skill's Path and Pinned Commit

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Problem Statement

`marketplace_json` in `backend/app/routers/catalog.py` emits each active catalog skill as a plugin whose source is `{"source": "github", "repo": "<owner>/<repo>"}`. It adds `"path"` from `skill_path` when the skill is not at the repository root, and it emits no `ref` and no `sha`. The client's own entry is `{"source": "github", "repo": "slaclab/agent-knowledge-hub", "path": "skill"}`.

A `github` plugin source has no `path` field and fetches the default branch when `ref` is omitted (#006 › References › Claude Code plugin updates; Measured facts). Claude Code therefore installs every entry's repository root at the default branch's tip:

- A skill that lives in a subdirectory installs as its whole repository, and the plugin Claude Code builds from that root is not the skill folder.
- The client installs correctly only because the root `.claude-plugin/plugin.json` points `skills` at `./skill/`; the `path` key in its entry does nothing (#006 › Follow-ups › Docs).
- A skill pinned under #017 installs at whatever the default branch holds, not at its `pinned_commit_sha`.

The Cogito deployment (`slaclab/cogito`, TODO #200) files this task as hub request H-2. Cogito users who install through the plugin route get the wrong content for every skill in a subdirectory, and Cogito's Open Question 3 recommends documenting a marketplace route for its sessions once this task ships, together with #047.

### What fails today

As of 2026-10-14, read from the code:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| `/plugin install <slug>@SLAC-Agent-Knowledge-Hub` for a skill at `skills/<name>` | The repository root is installed | Only `skills/<name>` is installed |
| The same for a skill with a `pinned_commit_sha` | The default branch's tip is installed | The pinned commit is installed |
| The client's own entry | Installs the repository root, which works through the root `plugin.json` | Installs the client folder by an explicit rule (Open Design Question 3) |
| A `local` skill, whose `repo_url` is `local://<path>` | The owner and repository split in `marketplace_json` passes it, so the entry carries `"repo": "local:/"` (derived from the code; not observed in a served manifest) | The skill is left out (FR-3) |

---

## Goals

1. Every plugin entry installs exactly its skill folder.
2. Every pinned skill installs at its `pinned_commit_sha`.
3. The minimum Claude Code version this route depends on is stated, not left implicit. **Added
   2026-10-16**, per `research/reports/oct2026-skill-hub-batch-vs-akh.md` finding I-1: until FR-1
   emits a `sha`, this route has no pin for CVE-2026-86063 (`research/concepts/plugin4shell.md`) to
   bypass, since Claude Code installs the default branch's tip either way. Once FR-1 ships, the pin's
   integrity rests entirely on Claude Code's own fixed `git checkout` (patched in 2.1.179) — a
   marketplace cannot enforce this client-side guarantee itself. State ≥2.1.179 as the minimum
   version this route requires, in the Definition of Done and in `README.md` once this task and #047
   ship. **Unconfirmed, flagged as this report's Open Question 6:** whether the 2.1.179 fix covers a
   `git-subdir` source specifically, or only the `github` source type Air Security's disclosure
   describes — verify before relying on the stated minimum for this task's `git-subdir` design.

## Non-Goals

- Making `marketplace.json` reachable from Claude Code. That is #047.
- Changing how `pinned_commit_sha` is set or advanced. That is #017.
- Publishing skills into `slaclab/slac-agent-plugin-marketplace`. That is #021.

---

## Requirements

### Functional

- **FR-1:** `marketplace.json` emits each plugin as a `git-subdir` source with `url`, `path`, and a `sha` taken from `pinned_commit_sha`. `url` is the repository's clone URL, derived from `repo_url`; `path` is `skill_path` without its leading `/`.
- **FR-2:** The client's own entry follows FR-1 or the rule chosen under Open Design Question 3, so that it no longer depends on a `path` key that a `github` source ignores.
- **FR-3:** A skill whose `source_type` is `local` has no repository and is left out. This requirement is not in Cogito's request; it follows from FR-1, which needs a clone URL.

### Acceptance Criteria

- **AC-1:** Given an active skill with `repo_url` `https://github.com/<owner>/<repo>`, `skill_path` `/skills/<name>`, and a `pinned_commit_sha`, when `marketplace.json` is built, then its entry's source is `{"source": "git-subdir", "url": <the clone URL>, "path": "skills/<name>", "sha": <pinned_commit_sha>}`.
- **AC-2:** Given that entry, when a user runs `/plugin install <slug>@SLAC-Agent-Knowledge-Hub` in Claude Code, then the installed plugin holds only the files under `skills/<name>` at the pinned commit. This is a manual check, because it needs Claude Code and GitHub.
- **AC-3:** Given an active `local` skill, when `marketplace.json` is built, then no entry names it.
- **AC-4:** Given the client's own entry, when a user installs it, then `/agent-knowledge-hub` is available and runs.

### Definition of Done

- [ ] FR-1 to FR-3 built; AC-1, AC-3, and AC-4 pass, and AC-2 is recorded once with the Claude Code version used
- [ ] `PRD.md` › `marketplace.json` manifest shows the new source shape
- [ ] Minimum Claude Code version (≥2.1.179, pending confirmation it covers `git-subdir` — Goal 3) stated in this file and in `README.md`
- [ ] CHANGELOG entry

---

## Open Design Questions

1. **Skills at the repository root.** Whether Claude Code accepts a `git-subdir` source with an empty `path`, or such entries keep a `github` source with `sha`, which a `github` source takes (#006 › References).
2. **Skills without a pin.** Cogito TODO #200 counted 6 of 39 catalog skills with a `pinned_commit_sha` (15%) on 2026-10-05, reading `GET /api/skills/<slug>` for each slug. An unpinned entry can omit `sha`, installing the default branch's tip as it does now, or be left out.
3. **The client's own entry.** A `git-subdir` with `path` `skill` makes the plugin root the `skill/` folder, which holds `SKILL.md` (and #050's helper) but no `.claude-plugin/plugin.json`. Keeping the repository root keeps that `plugin.json` and its `version`, on which the update rule depends: an existing install receives a new copy only when the plugin's computed version changes, and that version comes from `plugin.json` first (#006 › References › Claude Code plugin updates). How a `sha` enters the computed version was not checked.

---

## Measured facts — read 2026-10-14, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| Source shape `marketplace_json` emits | `github` with `repo`, plus `path` when `skill_path` is not `/` or empty; `version` on the plugin when set; no `ref`, no `sha` | Read `marketplace_json` in `backend/app/routers/catalog.py` |
| The client's entry | `{"source": "github", "repo": "slaclab/agent-knowledge-hub", "path": "skill"}`, emitted first | Same function |
| Root plugin manifest | `.claude-plugin/plugin.json` sets `"skills": "./skill/"` and `"version": "1.0.0"` | Read the file on `main` |
| Fields of a `github` plugin source | `repo`, `ref`, `sha`; no `path`; the default branch when `ref` is omitted | #006 › References, checked 2026-10-14 against the Claude Code `plugins/marketplace-reference` documentation; Cogito TODO #200 records the same |
| Fields of a `git-subdir` plugin source | `url`, `path`, `sha` | Recorded in Cogito TODO #200 from the same documentation; not re-checked here. `docs/github-api-plugin-installation.md` describes `git-subdir` as a sparse clone of a subdirectory |
| A local skill's `repo_url` | Stored as the submitter sent it; `_create_local` reads the path after `local://` | `_create_local` in `backend/app/services/skill.py` |

---

## Relationship to Other Tasks

- **Cogito TODO #200 (`slaclab/cogito`), hub request H-2:** needed by Cogito users of the plugin route and by Cogito's Open Question 3. No Cogito slice waits for it. Cogito's own image does not load skills through the marketplace or at `pinned_commit_sha`; it pins each skill by commit in a lock file of its own, because a submitter can re-pin their own skill (#017).
- **#017 (Skill version pinning):** supplies `pinned_commit_sha`.
- **#006 (Skillsets):** its References record the `github` source fields this task relies on, and its Slice 4 relies on the `version` rule in Open Design Question 3.
- **#047 (marketplace.json reachable from Claude Code):** the two together give Claude Code users a marketplace route that installs the right content. Its option B meets Goal 3's minimum version automatically; option A needs it written into `README.md` explicitly (`oct2026-skill-hub-batch-vs-akh.md` § Effect on #046, #047 and #048).
- **#053 (verify post-checkout HEAD in skill install) and `research/reports/oct2026-skill-hub-batch-vs-akh.md`:** #053 and this task cover the two places AKH's pin can be bypassed — #053 on the per-skill clone-based installer, this task's Goal 3 on the native marketplace route. The report also notes that on the native route, Claude Code loads the installed folder as a full plugin, which can carry bundled hooks and MCP server configuration that AKH's own client strips (#051) — worth stating explicitly which plugin components an entry may carry on this route when FR-1 is implemented.
