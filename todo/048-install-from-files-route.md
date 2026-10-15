# TODO #048 — Install Internal Skills Through the Files Route, Confined to the Skill Folder

> **Priority:** 🟢 P3 — Low
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Problem Statement

The `/agent-knowledge-hub` client installs a skill by cloning its repository as the user (#022). A skill the catalog records as `internal` (`VisibilityEnum.internal`, commented "fetched via GitHub App (slaclab private)") lives in a repository private to slaclab on GitHub, so a user without their own GitHub access to that repository cannot install it. Error handling in `skill/SKILL.md` has no case for that clone failure.

The catalog already serves those files. `GET /api/skills/{slug}/files/{path}` (`get_skill_file` in `backend/app/routers/skills.py`) answers any signed-in user for an `internal` skill and refuses only a request without a user, with 401. It serves only the paths in the skill's `file_manifest`, which `GET /api/skills/{slug}` returns.

Installing from that route moves file names from git to the catalog. A clone takes its file names from git, which refuses `..` entries. The route takes them from `file_manifest`, as plain strings, and the catalog does not check the names a submitter sends for a `local` skill: `SkillCreate.snapshotted_files` in `backend/app/schemas/skill.py` is a bare `Dict[str, str]`, `_create_local` in `backend/app/services/skill.py` stores it as sent, `_build_local_manifest` in `backend/app/services/local.py` copies its keys into the manifest unchanged, and `get_skill_file` serves any manifest path. A listed name such as `../../settings.json`, written beneath `~/.claude/skills/<slug>/`, lands in `~/.claude/settings.json`, whose hooks Claude Code runs in later sessions. #049 refuses such names at submission; this task makes the client safe whatever the catalog holds.

The manifest's shape also limits what the route can install (Measured facts). It lists the top level of `skill_path` only (ADR-U17), shows a subdirectory as a directory entry without its contents, stops at 200 entries and sets `manifest_truncated`, and the route answers 400 `binary_file` for any file whose extension is not in `_TEXT_EXTENSIONS`. A skill with a `scripts/` folder, a `LICENSE` file, or an image cannot be installed whole through the route as it stands.

The Cogito deployment (`slaclab/cogito`, TODO #200) files this task as hub request H-5. Cogito loads only skills from anonymously readable repositories into its sessions, and its deployment owner decided on 2026-10-14 that a private skill reaches a Cogito session only as a personal install, through this route once this task ships. Cogito counted 15 of 39 catalog skills (38%) as `internal` on 2026-10-05.

### What fails today

As of 2026-10-14:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A user without slaclab GitHub access installs an `internal` skill | The clone fails, and the client has no case for it | The client installs the skill from the files route |
| The same, before this task ships | No case in Error handling names the cause | The client says the repository is private to slaclab on GitHub and that installing it needs the user's own GitHub access (FR-3) |
| A manifest lists `../../settings.json` | No client installs from the route yet; the name is stored and served as sent | The client abandons the install and writes nothing |
| An `internal` skill has a `scripts/` folder | Not applicable; the route is not used for installs | The client abandons the install and says why (FR-4), until Open Design Question 1 is answered |

---

## Goals

1. A signed-in user can install an `internal` skill without their own GitHub access to its repository.
2. No install through the route writes outside `~/.claude/skills/<slug>/`.
3. No install through the route leaves a partial skill.

## Non-Goals

- Changing who may read `internal` skill files. Open Design Question 4 states the rule this task relies on.
- Validating names at submission. That is #049.
- Commands, agents, and MCP servers that a plugin declares. The route installs the skill folder's files only.

---

## Requirements

### Functional

- **FR-1:** The client installs a skill whose repository the user cannot clone, which the catalog records as `internal` ("fetched via GitHub App (slaclab private)"), from the catalog's own `GET /api/skills/<slug>/files/<path>`, which already serves those files to any signed-in user.
- **FR-2:** The client writes each file the skill's `file_manifest` lists only beneath `~/.claude/skills/<slug>/`, and abandons the install, writing nothing, on a listed path that is absolute or has a `..` segment. Unlike a clone, no git check stands between the catalog's file names and the real `~/.claude`, and the catalog does not check the names a submitter sends for a `local` skill. The rule applies to every install through the route, whatever the skill's `source_type`.
- **FR-3:** Until the client installs through that route, a failed clone of such a repository says that the repository is private to slaclab on GitHub and that installing it needs the user's own GitHub access, rather than reporting the skill as not found.
- **FR-4:** The client never installs part of a skill. It fetches every listed file before writing any, and abandons the install, writing nothing and naming the reason, when `manifest_truncated` is true, when the manifest holds a directory entry, or when the route answers 400 `binary_file` for a listed file. This requirement is not in Cogito's request; it follows from the manifest's shape (Measured facts).

### Acceptance Criteria

- **AC-1:** Given an `internal` skill whose manifest lists only top-level text files, and a user whose clone of its repository fails, when the user runs `/agent-knowledge-hub install <slug>`, then each listed file lands in `~/.claude/skills/<slug>/` with the content the route serves.
- **AC-2:** Given a manifest that lists `/etc/x`, `../x`, or `a/../../x`, when the client installs the skill, then it writes nothing, anywhere, and tells the user which name it refused.
- **AC-3:** Given a manifest with `manifest_truncated` true, a directory entry, or a file the route answers 400 `binary_file` for, when the client installs the skill, then it writes nothing and names the reason.
- **AC-4:** Given the clone path still in use and an `internal` repository the user cannot read, when the clone fails, then the client gives FR-3's message.
- **AC-5:** Given a manifest name such as `a..b.md`, which contains `..` but has no `..` segment, when the client installs the skill, then the file is written.

### Definition of Done

- [ ] FR-1 to FR-4 built; AC-1 to AC-5 pass
- [ ] `skill/SKILL.md` › Install and › Error handling describe the route install, FR-2's refusal, FR-4's reasons, and FR-3's message
- [ ] `version` in `.claude-plugin/plugin.json` raised (#006 › References › Claude Code plugin updates)
- [ ] `frontend/app/guides/slac-github-access/page.tsx` says that the client can install `internal` skills without GitHub access, within FR-4's limits
- [ ] CHANGELOG entry

---

## Open Design Questions

1. **Subdirectories.** FR-4 abandons any skill with a subfolder, which excludes many skills. ADR-U17 leaves recursive traversal to "a future iteration"; making the manifest recursive for `internal` skills, at the GitHub API cost ADR-U17 names, would let the route install them whole.
2. **Rate limit.** `get_skill_file` allows 60 requests a minute per client address, and a manifest can list 200 entries, so an install that makes one request per file can meet a 429. The client can pace its requests, or the catalog can serve a skill's files in one response.
3. **Prose or script.** The install could run inside #050's helper or a second shipped script rather than as prose the model follows, for the reason #050 gives for the token: an instruction cannot guarantee where files land. Cogito's security review raised this as a non-blocking follow-up. It is not a requirement, because the clone path already relies on the client's prose path-prefix rule, and FR-2 states the containment the route needs.
4. **The access rule this task relies on.** This task makes the route the endorsed install path for `internal` files. It does not widen who can read them: any signed-in user can already read them through the web UI and this route, and an install copies them into that user's own home. If the catalog narrows the rule, for example to members of slaclab on GitHub, installs through the route narrow with it. Cogito's deployment owner accepted the rule as it stands on 2026-10-05.
5. **When to use the route.** The client can try the clone first and fall back to the route on failure, or go to the route for every `internal` skill. The route serves a GitHub skill's files at `pinned_commit_sha` when one is set, otherwise at the branch, as a clone does.

---

## Measured facts — read 2026-10-14, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| Who can read an `internal` skill's files | Any request with a user; 401 only when there is none | `get_skill_file` in `backend/app/routers/skills.py`, `get_optional_user` dependency |
| Which paths the route serves | Only paths in `file_manifest`; 404 for others; 400 for a directory entry | Same function |
| Binary files | 400 with `{"error": "binary_file", ...}` for an entry whose `is_text` is false; `is_text` comes from the extension being in `_TEXT_EXTENSIONS` | Same function; `build_file_manifest` in `backend/app/services/github.py`; `_TEXT_EXTENSIONS` in `backend/app/services/scanner.py` |
| Manifest depth and size | Top level of `skill_path` only, with subdirectories as `is_dir` entries; at most `_MAX_MANIFEST` (200) entries, then `manifest_truncated` | `docs/adr/adr-u17-manifest-depth-flat.md`; `build_file_manifest`; `_MAX_MANIFEST` in `backend/app/services/scanner.py` |
| Where the client reads the manifest | `file_manifest` and `manifest_truncated` are fields of `SkillOut`, returned by `GET /api/skills/{slug}` | `backend/app/schemas/skill.py` |
| The route's rate limit | `@limiter.limit("60/minute")`, keyed by `get_remote_address` | `backend/app/routers/skills.py` |
| Commit the route reads for a GitHub skill | `pinned_commit_sha`, else the branch from `repo_url` | `get_skill_file` |
| Names of a `local` skill's files | `snapshotted_files` keys, unvalidated, copied into `file_manifest` | `SkillCreate` in `backend/app/schemas/skill.py`; `_create_local` in `backend/app/services/skill.py`; `_build_local_manifest` in `backend/app/services/local.py` |
| The client's install and errors | `git clone`, falling back to the GitHub Contents API without git; no case for a failed clone | `skill/SKILL.md` on `main` |
| `internal` skills in the catalog | 15 of 39 (38%) | Cogito TODO #200 › Measured facts, `GET /api/skills/<slug>` for each slug, 2026-10-05 |

---

## Relationship to Other Tasks

- **Cogito TODO #200 (`slaclab/cogito`), hub request H-5:** no Cogito slice waits for it. Cogito's user documentation says that a skill from a repository private to slaclab needs the user's own GitHub access until this task ships; that sentence changes when it does.
- **#028 (Skill file manifest):** built the route and the manifest this task installs from (ADR-U16, ADR-U17).
- **#022 (Installer git clone):** the clone path FR-3 covers until the route is used.
- **#006 (Skillsets):** FR-7 › Failure rule plans an access hint for a clone failure on an `internal` repository, pointing to `gh auth login` and the `/guides/slac-github-access` page, and applies it to plain `install` too. If #006's Slice 4 ships first and its hint states both facts FR-3 names, FR-3 is met there and not built twice.
- **#050 (Client token helper):** the route needs the token, so its requests go through that helper.
- **#049 (Local file name validation):** the server-side check beside FR-2.
- **#001 (Private repos and forks):** introduced `internal` visibility and the GitHub App.
