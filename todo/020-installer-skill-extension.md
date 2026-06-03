# TODO #020 — Installer Skill Extension: Directory Skills, Multi-Platform, Richer Scaffold

> **Scope:** Changes are confined to `skill/SKILL.md` — the Claude-side installer skill that users invoke locally. No backend (`github.py`, database, API) changes are required or included.

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Note:** Slices 1–4 shipped in feat(#020) v0.8.0. Slice 5 (Codex install path) is the remaining scope.
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

- **Backend changes** — `github.py`, the database schema, or any API endpoint. The backend scanner already handles plugin.json correctly (#019 covers that side).
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

### skill_path for `.claude-plugin/` layout — backend is correct as-is

`discover()` in `github.py` correctly strips `.claude-plugin` — storing `skill_path = "/"` (repo root) is right because plugin.json paths like `"skills": "./skill/"` are relative to the repo root, not relative to `.claude-plugin/`. The backend scanner also has its own `.claude-plugin/` fallback in `scan()` (lines 410-418).

The gap is only in the **installer** (SKILL.md step 3). No backend change needed.

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

---

## ADRs

### ADR-001: Directory-form components use recursive GitHub Contents API fetch

**Status:** Accepted (for #020 scope; superseded by [#022](022-installer-git-clone.md) long-term)

**Context:** `"skills": "./skills"` declares a directory. We need to install all files within it, potentially nested several levels deep (skills/epics-archiver/scripts/query.py).

Three options were evaluated (see [`docs/github-api-plugin-installation.md`](../docs/github-api-plugin-installation.md)):
- **Contents API (recursive):** current path; O(depth × breadth) round trips; rate-limit sensitive; no git required
- **Git Trees API:** single call enumerates all paths; still needs per-file downloads; better than Contents API for enumeration
- **Git clone:** single operation; no API rate limits; arbitrary depth; what Claude Code native `/plugin install` uses

**Decision:** Recursive Contents API fetch for #020 (simpler, no new system dependency). Cap at 200 files. Switch to git clone tracked in [#022](022-installer-git-clone.md).

**Consequences:** More API calls per install (bounded by directory depth × breadth). At current skill sizes (< 50 files), fine. Rate limit advisory already shown for 403 responses. Git Trees API is a better interim option than recursive Contents API for enumeration and should be considered if rate limits become a problem before #022 ships.

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

### ADR-003: Codex install paths — now documented

**Status:** Superseded by research (2026-06-02). See `source/research/agent-skill-mcp-integration/agent-5-codex-install-paths.md`.

**Context:** Codex install conventions were unknown at the time of writing. Research against `openai/codex` main branch (codex-rs, the actively maintained Rust CLI) has now established them.

**What was found:**
- `CODEX_HOME` defaults to `~/.codex/` (overridable via env var)
- Codex recognises **both** `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json` — a plugin with `.claude-plugin/plugin.json` works in Codex without modification
- Skills live under `skills/<skill-name>/SKILL.md` within a plugin directory
- Plugins are registered via `~/.codex/config.toml` using a local marketplace entry:
  ```toml
  [marketplaces."agent-knowledge-hub"]
  source_type = "local"
  source = "~/.akh/plugins"

  [plugins."<plugin-name>@agent-knowledge-hub"]
  enabled = true
  ```
- Global instruction file is `~/.codex/AGENTS.md` (also reads `~/.codex/AGENTS.override.md`)

**Decision:** When `compatible_platforms` includes `"codex"`, the installer should:
1. Install plugin files to `~/.akh/plugins/<slug>/` (AKH-controlled directory, not Codex's `.tmp/marketplaces/`)
2. Append a local marketplace + plugin entry to `~/.codex/config.toml`
3. Optionally append to `~/.codex/AGENTS.md` for global skill instructions

This is a new delivery slice for #020 — tracked as Slice 5 below.

**Gaps resolved (2026-06-03):**
- `marketplace.json` schema verified from `codex-rs/core-plugins/src/marketplace.rs` — required at `.agents/plugins/marketplace.json` within marketplace root; schema: `{ name, plugins: [{ name, source }] }`
- Explicit `[plugins]` config.toml entry IS required — no auto-discovery without it (confirmed)
- Project-level `.codex/config.toml` layer exists but not needed for AKH install (confirmed)

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

**Slice 5 — Codex install path** *(unblocked by research + schema verification 2026-06-03)*

When `compatible_platforms` includes `"codex"`, after the Claude Code install completes:

**5a. Install plugin files to AKH-managed directory:**
```
~/.akh/plugins/
  .agents/plugins/marketplace.json   ← created/updated by AKH
  <slug>/
    .claude-plugin/plugin.json       ← plugin manifest (recognised by Codex cross-compat)
    skills/<skill-name>/
      SKILL.md
    agents/                          ← if agents declared
    commands/                        ← if commands declared
```

**5b. Write/update `~/.akh/plugins/.agents/plugins/marketplace.json`:**

`marketplace.json` is required by Codex for `source_type = "local"` marketplaces. It must live at `.agents/plugins/marketplace.json` inside the marketplace root. Schema (verified from codex-rs/core-plugins/src/marketplace.rs):

```json
{
  "name": "agent-knowledge-hub",
  "plugins": [
    { "name": "<slug>", "source": "./<slug>" },
    ...existing entries...
  ]
}
```

On first install: create the file with the AKH marketplace entry and this skill as the first plugin.
On subsequent installs: read the file, append the new plugin entry if not present, write back.
On remove: read the file, remove the plugin entry, write back. If `plugins` becomes empty, delete the file.

**5c. Register the AKH marketplace in `~/.codex/config.toml`** (once, idempotent):
```toml
[marketplaces."agent-knowledge-hub"]
source_type = "local"
source = "~/.akh/plugins"
```
Check if the `[marketplaces."agent-knowledge-hub"]` key already exists before appending.

**5d. Enable plugin in `~/.codex/config.toml`:**
```toml
[plugins."<slug>@agent-knowledge-hub"]
enabled = true
```
Append this block. On remove: delete this block.

**5e. (Optional) inject global instructions into `~/.codex/AGENTS.md`:**
- If the plugin has a `SKILL.md` or `AGENTS.md` in its skills directory, ask:
  ```
  Add skill instructions to ~/.codex/AGENTS.md for global Codex access? (y/n)
  ```
- If yes: append a clearly-delimited section:
  ```markdown
  <!-- BEGIN agent-knowledge-hub:<slug> -->
  <SKILL.md content>
  <!-- END agent-knowledge-hub:<slug> -->
  ```
- On remove: delete the delimited section from `~/.codex/AGENTS.md`.

**5f. Print Codex install summary:**
```
✓ Codex: installed to ~/.akh/plugins/<slug>/
         Marketplace: agent-knowledge-hub registered in ~/.codex/config.toml
         Plugin: <slug>@agent-knowledge-hub enabled
```

**5g. Remove flow** — reverse in order: delete `~/.codex/AGENTS.md` section, remove `[plugins."<slug>@agent-knowledge-hub"]` from config.toml, update marketplace.json, delete `~/.akh/plugins/<slug>/`. Leave `[marketplaces."agent-knowledge-hub"]` in config.toml if other AKH plugins remain.

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
| `~/.codex/config.toml` parse fails (malformed TOML by user) | Low | Medium | Read-modify-write with error; if parse fails, append blocks as plaintext with comment warning user to merge manually |
| Codex not installed — `~/.codex/` absent | Medium | Low | Check for directory existence before writing; skip Codex install path with: `ℹ Codex home (~/.codex/) not found — skipping Codex install.` |
| `marketplace.json` written mid-update corrupts registry if interrupted | Very Low | Low | Write to temp file, rename atomically |
| Delimited section in AGENTS.md accidentally deleted by user, remove leaves orphan plugin | Low | Low | Remove only deletes what it finds; warn if section absent |

---

## Implementation Checklist

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
- [ ] **Slice 5 — Codex install path:**
- [ ] Install (Codex): create `~/.akh/plugins/<slug>/` with plugin manifest + skill files when `"codex"` in `compatible_platforms`
- [ ] Install (Codex): create/update `~/.akh/plugins/.agents/plugins/marketplace.json` (append plugin entry, idempotent)
- [ ] Install (Codex): register `[marketplaces."agent-knowledge-hub"]` in `~/.codex/config.toml` (once, idempotent)
- [ ] Install (Codex): add `[plugins."<slug>@agent-knowledge-hub"] enabled = true` to `~/.codex/config.toml`
- [ ] Install (Codex): offer to inject SKILL.md content into `~/.codex/AGENTS.md` with delimited section
- [ ] Install (Codex): skip gracefully if `~/.codex/` directory does not exist
- [ ] Remove (Codex): delete delimited AGENTS.md section, remove plugin config.toml block, update marketplace.json, delete `~/.akh/plugins/<slug>/`
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
| S12 | Codex install — happy path | `install` a skill with `"compatible_platforms": ["claude-code", "codex"]` | Files in `~/.akh/plugins/<slug>/`, entries in `config.toml`, marketplace.json updated |
| S13 | Codex install — Codex absent | Same, but `~/.codex/` does not exist | Prints skip message; Claude Code install still succeeds |
| S14 | Codex remove | `remove` a skill with Codex install | `~/.akh/plugins/<slug>/` deleted, config.toml entries removed, marketplace.json updated |
| S15 | Codex AGENTS.md inject | Install with Codex + say y to AGENTS.md prompt | Delimited section present in `~/.codex/AGENTS.md`; remove deletes it |

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
- [ ] Codex install: plugin files in `~/.akh/plugins/<slug>/`, marketplace.json updated, config.toml entries added
- [ ] Codex remove: all Codex-side state cleaned up cleanly (no orphan entries in config.toml or marketplace.json)
- [ ] Codex absent: installer degrades gracefully without error
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
