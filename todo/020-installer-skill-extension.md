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

- Backend catalog changes (those are in #019)
- Codex-specific install paths (we don't know Codex's install directories yet; warn + skip is sufficient for now)
- Installing from non-GitHub sources
- Plugin signing or integrity verification

---

## Design

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

### `update` — directory-aware removal

When updating a skill installed from a directory-form plugin, the old files may include subdirectories. Before re-installing, delete `~/.claude/skills/<slug>/` entirely (already the current behaviour). Also clean up any commands/agents from old plugin.json.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `skill/SKILL.md` — install flow | Modify | Handle directory-form components; platform check |
| `skill/SKILL.md` — validate command | Modify | Accept directory-form; validate author, compatible_platforms |
| `skill/SKILL.md` — create command | Modify | Richer question flow; scaffold directory structure + plugin.json |
| `skill/SKILL.md` — list command | Modify | Show platform + component summary from local plugin.json |
| `skill/SKILL.md` — remove command | Modify | Recursively clean directory-installed files |
| `skill/SKILL.md` — error handling | Modify | Add platform mismatch warning, file cap warning |

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

---

## Implementation Checklist

- [ ] Install: detect `"skills"` (and `"agents"`, `"commands"`) as string (directory) vs array
- [ ] Install: recursive GitHub Contents API fetch for directory-form components
- [ ] Install: security check on every file in recursive fetch
- [ ] Install: 200-file cap with warning
- [ ] Install: platform check — warn if `claude-code` absent from `compatible_platforms`
- [ ] Install: note other platforms if present
- [ ] Remove: clean up recursively installed files
- [ ] `validate`: accept directory-form; validate author object; validate compatible_platforms
- [ ] `validate`: show agent count, platform list, scripts presence in summary
- [ ] `create`: extended question flow (agents, scripts, MCP, platforms)
- [ ] `create`: generate directory structure matching answers
- [ ] `create`: generate full plugin.json template
- [ ] `list`: show platform + component summary from local plugin.json
- [ ] Tests: directory install, platform warning, validate directory-form, create scaffold

---

## Definition of Done

- [ ] `"skills": "./skills"` installs all files in that directory preserving subdir structure
- [ ] Install warns when skill does not list `claude-code` in `compatible_platforms`
- [ ] `validate` passes on marketplace-format plugins (directory-form skills)
- [ ] `create` generates a plugin.json with agents/scripts/MCP sections when requested
- [ ] `list` shows agent count and platform info
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
