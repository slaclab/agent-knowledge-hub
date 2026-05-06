# TODO #020 — Installer Skill Extension: Directory Skills, Multi-Platform, Richer Scaffold

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** —
> **Depends on:** #019 (plugin.json format canonical spec)

---

## Problem Statement

The `/agent-knowledge-hub` installer skill (`skill/SKILL.md`) was designed around a simple model: a skill is a flat set of files listed explicitly in `plugin.json["skills"]`. Real-world plugins (like those in `slac-agent-plugin-marketplace`) are richer:

1. **Directory-form skills** — `"skills": "./skills"` is a directory path, not a file array. The installer currently silently installs nothing for this form.
2. **Scripts, config, tests alongside SKILL.md** — multi-file skill packages need all supporting files installed, preserving directory structure (e.g. `scripts/query_archiver.py`, `config/archiver-config.schema.json`).
3. **Multi-platform support** — plugins can target `claude-code`, `codex`, or both. The installer has no platform awareness; it always writes to `~/.claude/` paths regardless of whether the skill supports Claude Code.
4. **Scaffold gap** — `/agent-knowledge-hub create` generates only a bare SKILL.md + a minimal plugin.json. It doesn't ask about agents, scripts, MCP servers, or target platforms, leaving authors to figure out the full structure manually.
5. **validate schema mismatch** — the `validate` command checks that `skills` is a non-empty array, which rejects valid directory-form plugins.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| `"skills": "./skills"` in plugin.json | Install step silently installs nothing | All files in `./skills/` directory installed, preserving subdirs |
| Skill ships `scripts/query.py` alongside SKILL.md | Script not installed (only SKILL.md fetched) | Full directory tree installed into `~/.claude/skills/<slug>/` |
| Plugin targets only Codex, not Claude Code | Installs to `~/.claude/` regardless | Warn: "this skill does not list claude-code as a supported platform" |
| Plugin targets both Claude Code + Codex | Same — installs to `~/.claude/` only | Installs Claude Code components; notes Codex components require a different agent |
| `validate` on directory-form plugin | `✗ skills is not a non-empty array` | `✓ skills: directory ./skills (N files)` |
| `/agent-knowledge-hub create` | Generates SKILL.md + minimal plugin.json only | Asks about agents, scripts, MCP, platforms; scaffolds full directory structure |

---

## Goals

1. Install directory-form `"skills"` (and `"agents"`, `"commands"`) by fetching and writing the full directory tree from GitHub, preserving subdirectory structure
2. Add platform awareness to the install flow: check `compatible_platforms`, warn if Claude Code is not listed
3. Update `validate` to accept both array-form and directory-form component declarations
4. Extend `create` scaffold to ask about agents, scripts, MCP servers, and target platforms; generate matching directory structure and plugin.json
5. Update `list` and `update` to surface new metadata (agent count, platform support) from plugin.json

## Non-Goals

- Codex-specific install paths (we don't know Codex's install directories yet; warn + skip is sufficient for now)
- Installing from non-GitHub sources
- Plugin signing or integrity verification

---

## Design

### Shared procedure: fetch-and-write

All three install paths (array-form, directory-form, legacy) call the same primitive. Define it once at the top of the install section and reference it by name:

```
fetch-and-write(github_url, local_path):
  1. Security check: resolve local_path. Assert it stays within the allowed prefix
     (~/.claude/skills/<slug>/ for skills, ~/.claude/commands/ for commands,
     ~/.claude/agents/ for agents). If not → abort entire install, warn user.
  2. Fetch github_url from GitHub Contents API (include auth header if GITHUB_TOKEN set).
  3. If 403 with X-RateLimit-Remaining: 0 → abort, suggest GITHUB_TOKEN.
  4. Decode base64 content from response.
  5. Write to local_path, creating parent directories as needed.
```

Array-form, directory-form, and legacy install all say "call fetch-and-write(url, path) for each file" rather than repeating the security check and error handling inline.

### skill_path normalization for `.claude-plugin/` layout (backend fix)

Currently, `backend/app/services/github.py` `discover()` strips `.claude-plugin` from the path — a skill at `repo-root/.claude-plugin/plugin.json` gets `skill_path = "/"`. This means the installer fetches `//plugin.json` (404) and falls to legacy.

Fix: store `skill_path = ".claude-plugin"` (or `<parent>/.claude-plugin`) instead of stripping it:

```python
# Before:
if fname == "plugin.json" and (dirpath == ".claude-plugin" or ...):
    dirpath = dirpath[:-len("/.claude-plugin")] if "/" in dirpath else "/"

# After: keep .claude-plugin as the skill_path
# dirpath stays as ".claude-plugin" — no stripping
```

Existing skills with `skill_path = "/"` that use `.claude-plugin/` layout will pick up the correct path on next refetch. The AKH skill itself should be refetched after this ships.

### plugin.json lookup — install fallback order

The install flow looks for `plugin.json` in this order:
1. `GET repos/<owner>/<repo>/contents/<skill_path>/plugin.json`
2. If 404 → `GET repos/<owner>/<repo>/contents/<skill_path>/.claude-plugin/plugin.json`
   (safety net for: locally-validated plugins, skills not yet refetched after the skill_path fix)
3. If 404 → **legacy install** (step 8 — flat file dump of `skill_path` directory)

This matches the fallback order already implemented in `validate`.

### Directory-form install

When `plugin.json` component field is a string (e.g. `"skills": "./skills"`):

1. Treat it as a directory path relative to `skill_path` in the repo.
2. Fetch directory listing: `GET https://api.github.com/repos/<owner>/<repo>/contents/<resolved_path>?ref=<pinned_sha>`
3. Recursively fetch all files (respecting the existing security check — all paths must stay within `~/.claude/skills/<slug>/`).
4. Write files preserving subdirectory structure: `./skills/epics-archiver/scripts/query.py` → `~/.claude/skills/<slug>/scripts/query.py`.
5. Cap at 200 files per component type; warn and abort if exceeded.

Same logic applies when `"agents"` or `"commands"` is a directory string.

**Security check:** For each file in the recursive fetch, resolve the full target path and assert it stays within the allowed prefix (`~/.claude/skills/<slug>/` for skills, `~/.claude/commands/` for commands, `~/.claude/agents/` for agents). Any path traversal attempt aborts the entire install.

### Platform check

After fetching plugin.json, before writing any files:

1. Read `compatible_platforms` array (may be absent — treat absence as `["claude-code"]` for backwards compatibility with pre-#019 plugins).
2. If `compatible_platforms` is present and does not include `"claude-code"`, print:
   ```
   ⚠  This skill declares it does not support claude-code.
      Supported platforms: <list>.
      Install anyway? (y/n)
   ```
3. If user says yes, proceed. If no, abort.
4. If `compatible_platforms` includes other platforms alongside `claude-code`, note them:
   ```
   ℹ  This skill also supports: codex. Those components are not installed here.
   ```

Claude Code component install paths remain unchanged (`~/.claude/`). No attempt is made to install to other platform paths.

### `validate` update

Current check that fails on directory form:
```
At least one of `skills`, `commands`, `agents`, `mcp-servers` must be a non-empty array
```

New logic:
- `skills` may be a non-empty **string** (directory path) — check the directory exists at `<path>/<skills_value>`
- `skills` may be a non-empty **array** — check each listed file exists (current behaviour)
- `agents` and `commands` follow the same pattern
- Add `compatible_platforms` check: if present, must be a non-empty array of strings
- Add `author` check: if present, must have a `name` field

Updated summary output:
```
  ✓ skills: directory ./skills (found, contains 3 .md files and scripts/)
  ✓ agents: 7 agent files declared and present
  ✓ compatible_platforms: claude-code, codex
  ✓ author: Claudio Bisegni <bisegni@slac.stanford.edu>
```

### `create` scaffold — richer prompts

New question flow:

```
Skill name: 
Description: 
Does this skill include sub-agents? (y/n)
  → If yes: how many? (enter names, one per line, blank to finish)
Does this skill need an MCP server? (y/n)
  → If yes: server name and command?
Does this skill include Python scripts or other supporting files? (y/n)
Target platforms: [1] claude-code only  [2] claude-code + codex  [3] all
```

Generated structure for a skill with scripts + 2 agents:

```
<dir>/
  plugin.json
  README.md
  skills/<slug>/
    SKILL.md
    scripts/              ← generated if scripts=yes
      .gitkeep
  agents/
    <agent1>.md           ← generated if agents=yes
    <agent2>.md
```

Generated plugin.json:
```json
{
  "name": "<slug>",
  "description": "<description>",
  "version": "0.1.0",
  "author": { "name": "", "email": "" },
  "license": "MIT",
  "keywords": [],
  "compatible_platforms": ["claude-code"],
  "skills": "./skills",
  "agents": [
    "./agents/<agent1>.md",
    "./agents/<agent2>.md"
  ]
}
```

### `list` update

If `~/.claude/skills/<slug>/plugin.json` exists, read and show additional metadata:

```
<slug>   v<version>   <name> — <description>
         Platforms: claude-code, codex
         Components: 1 skill, 7 agents, 1 MCP server
```

### Installed-files manifest

Files installed into `~/.claude/skills/<slug>/` are cleaned up trivially by deleting the directory. But files installed into `~/.claude/commands/` and `~/.claude/agents/` are intermixed across all skills — there is no way to identify which files belong to `<slug>` without a record.

**Resolution:** At the end of every install, write `~/.claude/skills/<slug>/.installed-manifest.json`:

```json
{
  "slug": "<slug>",
  "installed_at": "<ISO timestamp>",
  "commands": ["~/.claude/commands/my-cmd.md"],
  "agents":   ["~/.claude/agents/my-agent.md"]
}
```

`remove` and `update` read this manifest to clean up `commands` and `agents` entries. If the manifest is absent (old install before this change), fall back to reading `plugin.json["commands"]` / `plugin.json["agents"]` as arrays (current behaviour). If that is also absent, skip — do not fail.

The manifest is written regardless of whether components are array-form or directory-form. Skills-dir files are not listed in the manifest (the whole dir is deleted).

### `remove` — explicit operation order

**Warning:** The manifest lives inside the slug dir. Read it BEFORE deleting the slug dir:

1. Read `~/.claude/skills/<slug>/.installed-manifest.json` into memory.
2. If manifest absent, read `~/.claude/skills/<slug>/plugin.json["commands"]` / `["agents"]` into memory (fallback for pre-manifest installs).
3. Delete each path collected in steps 1–2 from `~/.claude/commands/` and `~/.claude/agents/`.
4. For each MCP server in `plugin.json["mcp-servers"]`, run `claude mcp remove <name>`.
5. Delete `~/.claude/skills/<slug>/` entirely (this also deletes the manifest).

### `update` — directory-aware removal

Before re-installing:
1. Read `~/.claude/skills/<slug>/.installed-manifest.json`. Delete every path listed in `commands` and `agents`.
2. If manifest absent, read old `plugin.json["commands"]` / `plugin.json["agents"]` as string arrays and delete those paths.
3. Delete `~/.claude/skills/<slug>/` entirely.
4. Run the full install flow (which writes a fresh manifest).

### `create` — plugin.json format

Current `create` generates `"skills": [{"name": "...", "path": "SKILL.md"}]` (object format). The install flow treats array items as string file paths; objects are silently ignored. This is a pre-existing inconsistency.

New `create` always generates directory-form for the skills component:

```json
{
  "skills": "./skills",
  "agents": ["./agents/<agent>.md"]   ← string array when agents selected
}
```

This matches the canonical format the repo itself uses (`"skills": "./skill/"` in `.claude-plugin/plugin.json`) and is unambiguous for the installer.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `skill/SKILL.md` — install flow | Modify | `.claude-plugin/` fallback; directory-form components; platform check; shared fetch-and-write; manifest write |
| `skill/SKILL.md` — validate command | Modify | Accept directory-form; validate author, compatible_platforms |
| `skill/SKILL.md` — create command | Modify | Richer question flow; scaffold directory structure + plugin.json |
| `skill/SKILL.md` — list command | Modify | Show platform + component summary from local plugin.json |
| `skill/SKILL.md` — remove command | Modify | Manifest-based cleanup of commands/agents; explicit operation order |
| `skill/SKILL.md` — update command | Modify | Manifest cleanup before reinstall |
| `skill/SKILL.md` — error handling | Modify | Add platform mismatch warning, file cap warning, empty-dir warning |
| `backend/app/services/github.py` — `discover()` | Modify | Store `skill_path = ".claude-plugin"` instead of stripping to parent |

---

## ADRs

### ADR-001: Directory-form components use recursive GitHub Contents API fetch

**Status:** Accepted

**Context:** `"skills": "./skills"` declares a directory. We need to install all files within it, potentially nested several levels deep (skills/epics-archiver/scripts/query.py).

**Decision:** Recursively fetch via GitHub Contents API. First call gets top-level listing; recurse into subdirectories. Cap at 200 files total to prevent runaway installs.

**Consequences:** More API calls per install (bounded by directory depth × breadth). At current skill sizes (< 50 files), fine. Rate limit advisory already shown for 403 responses.

---

### ADR-002: Absent `compatible_platforms` treated as `["claude-code"]`

**Status:** Accepted

**Context:** Pre-#019 plugins (most existing catalog entries) have no `compatible_platforms` field. Requiring it would break all existing installs.

**Decision:** Absence of `compatible_platforms` means "claude-code only" for backwards compatibility. Only warn when the field is explicitly present and does not include `claude-code`.

**Consequences:** Existing skills continue to install without prompts. New Codex-only plugins correctly warn. Ambiguous for old skills — acceptable given the migration path.

---

### ADR-004: Installed-files manifest for cross-directory component tracking

**Status:** Accepted

**Context:** Commands and agents are installed into shared directories (`~/.claude/commands/`, `~/.claude/agents/`) alongside files from other skills. Without a per-skill record, remove and update cannot clean these up cleanly — especially when components are directory-form strings rather than explicit file lists.

**Options considered:**

| Option | Pros | Cons |
|---|---|---|
| Manifest file per slug | Self-contained, survives GitHub rate limits, no re-fetch needed | Extra file to write/maintain |
| Re-fetch from GitHub on remove | No extra state | Requires network + auth; fragile if repo moves |
| Skip cleanup for directory-form | Simple | Leaves orphan files on every update/remove |

**Decision:** Write `~/.claude/skills/<slug>/.installed-manifest.json` at the end of every install. Remove and update read it first; fall back to array-form `plugin.json` parsing for old installs; skip if both absent.

**Consequences:**
- Old installs (before this change) will not have a manifest; fallback covers array-form only — directory-form commands/agents from old installs cannot be cleaned up automatically (acceptable; warn the user).
- Manifest must be written atomically at the end of install, after all files are confirmed written.

---

### ADR-003: Claude Code paths only; Codex paths TBD

**Status:** Accepted

**Context:** We don't know Codex's install directory conventions. Installing to wrong paths is worse than not installing.

**Decision:** When `compatible_platforms` includes non-claude-code entries, note them but do not attempt to install those components. Revisit when Codex install conventions are documented.

**Consequences:** Codex users get an informational message; they must install Codex components manually for now.

---

## Trade-offs

```
Choice: Recursive Contents API vs Git tree API for directory installs
  + Contents API: simpler; no tree SHA needed; consistent with existing file fetch code
  - Contents API: O(depth) round trips; rate limit sensitive for deep trees
  Decision: Contents API for now, capped at 200 files. Revisit if deep trees become common.

Choice: Always confirm before installing non-claude-code skills vs silent install
  + Confirm: explicit user consent; avoids surprise
  - Confirm: friction for experienced users who know what they're doing
  Decision: Confirm (y/n prompt). Matches existing pattern for rate-limit retries.

Choice: Scaffold with actual agent templates vs empty .md stubs
  + Templates: useful starting point
  - Templates: may confuse if agent role doesn't match template
  Decision: Empty stubs with frontmatter only (name, description, tools). User fills in content.
```

---

## Delivery Slices

**Slice 1 — Directory-form install**
- Install: detect string vs array in `skills`, `agents`, `commands`
- Recursively fetch and write directory trees, preserving subdir structure
- Security check extended to all files in recursive fetch
- File cap (200) with warning

**Slice 2 — Platform awareness**
- Read `compatible_platforms` from plugin.json at install time
- Warn if `claude-code` not listed; note other platforms
- Update `list` to show platform summary

**Slice 3 — validate update**
- Accept directory-form for skills/agents/commands
- Validate author, compatible_platforms
- Update summary output

**Slice 4 — create scaffold**
- Richer question flow
- Directory structure generation
- Full plugin.json template with all supported fields

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Recursive fetch hits GitHub rate limit | Medium | Medium | Show existing rate limit advisory; stop after 403 with clear message |
| Directory traversal via nested symlinks or `..` in filenames | Low | High | Resolve full target path before every write; assert within allowed prefix |
| File cap (200) exceeded for large skill packages | Low | Low | Warn clearly; list capped files; suggest manual install |
| `create` scaffold confuses users with too many questions | Medium | Low | All agent/script/MCP questions are y/n defaults-no; extra prompts only appear if y |
| Existing plugins with implicit claude-code support get wrong warning after #019 adds explicit platforms | Low | Low | ADR-002: absent field = claude-code assumed; no warning triggered |
| Old installs (pre-manifest) leave orphan commands/agents on update/remove | Low | Low | Warn user; fall back to array-form plugin.json parsing; document limitation |
| Manifest write fails mid-install (e.g. disk full) | Very Low | Low | Write manifest last, after all files confirmed; treat missing manifest as old install |

---

## Implementation Checklist

- [ ] Backend: fix `discover()` in `github.py` — store `skill_path = ".claude-plugin"` instead of stripping it to parent dir
- [ ] Backend: refetch AKH skill after fix to update its `skill_path` in the catalog
- [ ] Install: check `<skill_path>/.claude-plugin/plugin.json` as fallback before falling to legacy install (only fall to legacy on 404 — treat 5xx/timeout as a real error)
- [ ] Install: warn when directory-form component resolves to an empty directory (0 files)
- [ ] Install: detect `"skills"` (and `"agents"`, `"commands"`) as string (directory) vs array
- [ ] Install: recursive GitHub Contents API fetch for directory-form components
- [ ] Install: security check on every file in recursive fetch
- [ ] Install: 200-file cap with warning
- [ ] Install: platform check — warn if `claude-code` absent from `compatible_platforms`
- [ ] Install: note other platforms if present
- [ ] Install: write `.installed-manifest.json` after all files confirmed written
- [ ] Remove: read manifest to clean up commands/agents; fall back to array-form plugin.json; warn if old directory-form install
- [ ] Update: read + apply manifest cleanup before deleting slug dir and reinstalling
- [ ] `validate`: accept directory-form; validate author object; validate compatible_platforms
- [ ] `validate`: show agent count, platform list, scripts presence in summary
- [ ] `create`: extended question flow (agents, scripts, MCP, platforms)
- [ ] `create`: generate directory structure matching answers
- [ ] `create`: generate full plugin.json with directory-form `"skills": "./skills"` (not legacy object format)
- [ ] `list`: show platform + component summary from local plugin.json
- [ ] Smoke tests: run manual checklist below before marking done

---

## Test Plan
Generated by /codebase-eng-review on 2026-05-06

### Affected commands
- `/agent-knowledge-hub install <slug>` — directory-form, `.claude-plugin/` fallback, platform check, manifest write
- `/agent-knowledge-hub remove <slug>` — manifest-based cleanup of commands/agents
- `/agent-knowledge-hub update <slug>` — manifest cleanup before reinstall
- `/agent-knowledge-hub validate <path>` — directory-form components, author, compatible_platforms
- `/agent-knowledge-hub create` — extended scaffold, directory structure, plugin.json format
- `/agent-knowledge-hub list` — local plugin.json metadata display

### Smoke tests (manual — run before marking DoD complete)

| # | Scenario | Command | Expected |
|---|---|---|---|
| S1 | Directory-form install | `install` a skill whose `plugin.json` has `"skills": "./skills/"` | All files in `./skills/` written to `~/.claude/skills/<slug>/`, subdirs preserved |
| S2 | `.claude-plugin/` fallback | `install agent-knowledge-hub` (uses `.claude-plugin/plugin.json`) | Structured install runs; NOT legacy flat-file dump |
| S3 | Platform warn — missing claude-code | Install skill with `"compatible_platforms": ["codex"]` | Prints `⚠ This skill declares it does not support claude-code.` + y/n prompt |
| S4 | Platform note — multi-platform | Install skill with `"compatible_platforms": ["claude-code", "codex"]` | Installs silently; prints `ℹ This skill also supports: codex.` |
| S5 | File cap exceeded | Install a directory with >200 files | Warns clearly, aborts install, prints capped count |
| S6 | Manifest written | Any successful install with commands or agents | `~/.claude/skills/<slug>/.installed-manifest.json` exists and lists installed paths |
| S7 | Remove (manifest present) | `remove` a skill installed after #020 | Commands/agents from manifest deleted; slug dir deleted |
| S8 | Remove (pre-manifest fallback) | `remove` a skill installed before #020 (no manifest) | Falls back to plugin.json array-form; prints warning if directory-form can't be cleaned |
| S9 | Validate directory-form | `validate .` on repo with `"skills": "./skills"` | `✓ skills: directory ./skills` instead of `✗ skills is not a non-empty array` |
| S10 | Create with agents | `create` → answer y to agents question | Generates `agents/` dir, agent stub files, plugin.json with `"agents": [...]` |
| S11 | List with metadata | `list` after installing a plugin.json skill | Shows platform and component summary line below slug |

### Edge cases
- Install with `"skills": []` (empty array) — should warn "no skills declared" not silently do nothing
- Install where `.claude-plugin/plugin.json` exists but is invalid JSON — should fail with parse error, not fall to legacy
- Remove with manifest that references a commands file that was already deleted manually — should skip gracefully, not abort
- Path traversal in directory-form filename (e.g. `"../../etc/passwd"`) — security check must catch it

### Critical paths
- Install → remove round-trip: all installed files gone, no orphans in `~/.claude/commands/` or `~/.claude/agents/`
- Install → update: commands/agents from old version removed, new version's files present

---

## Definition of Done

- [ ] `"skills": "./skills"` installs all files in that directory preserving subdir structure
- [ ] Install warns when skill does not list `claude-code` in `compatible_platforms`
- [ ] `validate` passes on marketplace-format plugins (directory-form skills)
- [ ] `create` generates a plugin.json with agents/scripts/MCP sections when requested
- [ ] `list` shows agent count and platform info
- [ ] Remove correctly cleans up commands and agents (manifest-based)
- [ ] Update correctly cleans old commands/agents before reinstalling
- [ ] All checklist items complete

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

> *Populated by `/codebase-board-review` after the board completes. Do not fill manually.*

**Verdict:** —
**Date:** —
**Rounds:** —

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — | — | — |
| codebase-arch-review | — | — | — |
| codebase-eng-review | — | — | — |
| codebase-doc-review | — | — | — |
| security-review | — | — | — |

---

## Relationship to Other Tasks

- **#019 (plugin.json scan pipeline):** #019 defines and documents the canonical plugin.json format; this todo implements the installer side of that same format. `compatible_platforms` behavior here mirrors what #019 stores in the catalog.
- **#017 (Commit pinning):** When #017 ships, install should pass `?ref=<pinned_commit_sha>` to all GitHub Contents API calls including recursive directory fetches.
- **#007 (AKH skill):** This todo modifies the SKILL.md that was first created in #007.
