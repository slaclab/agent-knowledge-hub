# Claude Code: Skill, Command, and Agent Discovery — File Formats and Directory Conventions

**Research date:** 2026-06-02  
**Method:** Local filesystem analysis (web tools unavailable in this environment). Sources are project-internal documents that themselves synthesize official Claude Code behavior.  
**Primary sources consulted:**
- `skill/SKILL.md` — the Agent Knowledge Hub installer skill (canonical reference for how Claude Code reads/installs skills)
- `docs/skill-file-discovery.md` — documented algorithm for scanning GitHub repos for skill files
- `docs/github-api-plugin-installation.md` — comparative research on GitHub API approaches vs. native Claude Code plugin install
- `docs/adr/adr-u02-frontmatter-format.md` — ADR on YAML frontmatter format decision
- `todo/020-installer-skill-extension.md` — design doc for installer extensions, contains canonical plugin.json spec
- `.claude-plugin/plugin.json` — this project's own plugin manifest
- `.claude/skills/k8s-access/SKILL.md`, `.claude/skills/deploy/SKILL.md` — project-local skill files
- `backend/.venv/lib/python3.12/site-packages/fastapi/.agents/skills/fastapi/SKILL.md` — FastAPI package-shipped skill

---

## 1. ~/.claude/ Directory Layout

Claude Code uses the following standard directories under `~/.claude/`:

| Directory | Purpose |
|---|---|
| `~/.claude/skills/<slug>/` | Skill files for a named skill. Each slug gets its own subdirectory. The primary file is `SKILL.md`. Supporting files (scripts, config, references/) are placed alongside it. |
| `~/.claude/commands/` | Slash command definition files (`.md` files). Shared across all installed skills. |
| `~/.claude/agents/` | Agent definition files (`.md` files). Shared across all installed skills. |
| `~/.claude/skills/<slug>/.installed-manifest.json` | Per-skill install manifest tracking which commands/agents files were written during install. Written at install time; read during update/remove. |

Additionally, Claude Code uses:
- `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` — cache directory for cloned plugin repos (used by native `/plugin install` via git clone)
- `~/.claude/settings.json` / `~/.claude/settings.local.json` — permissions configuration

At the project level, Claude Code reads:
- `.claude/skills/<slug>/SKILL.md` — project-scoped skills (override or supplement global skills)
- `.claude/settings.local.json` — project-scoped permissions and configuration
- `CLAUDE.md` (project root or `~/.claude/CLAUDE.md`) — context loaded into every session

---

## 2. SKILL.md Format and Frontmatter

### File format

`SKILL.md` is a Markdown file with optional YAML frontmatter at the top:

```markdown
---
name: <slug-or-display-name>
description: <one-sentence description>
version: 1.2.0          # optional
platforms: [claude-code, openai]  # optional
keywords: [k8s, deploy]  # optional
---

# /<command-name>

Body: instructions Claude follows when the skill is invoked.
```

### Frontmatter fields

| Field | Required | Notes |
|---|---|---|
| `name` | Recommended | Display name; used as fallback identifier |
| `description` | Recommended | One-sentence summary; used in catalog/list display |
| `version` | Optional | Semantic version string |
| `platforms` | Optional | Array of compatible platform identifiers |
| `keywords` | Optional | Array of string tags |

**Frontmatter is purely additive** — files without frontmatter degrade gracefully. The metadata extraction chain falls through to `plugin.json`, `package.json`, `pyproject.toml`, path segment, and repo name in order.

**Parser:** `python-frontmatter` library (ADR-U02). Handles: valid frontmatter, empty frontmatter, missing `---` delimiter, malformed YAML — all non-valid cases fall through.

### Accepted filenames

The scanner recognises any of: `SKILL.md`, `skill.md`, `CLAUDE.md` as equivalent skill definition files. `CLAUDE.md` is accepted as a legacy/compatible filename.

### Reference files

Skills may include reference docs in a `references/` subdirectory (seen in FastAPI skill: `references/dependencies.md`, `references/streaming.md`, `references/other-tools.md`). The SKILL.md body links to them with relative markdown paths.

---

## 3. Agent File Format (`agents/*.md`)

Agent files are Markdown with YAML frontmatter:

```markdown
---
name: <agent-name>
description: <agent role description>
---

<system prompt body — instructions for this agent's behavior>
```

| Field | Required | Notes |
|---|---|---|
| `name` | Required | Identifier for the agent |
| `description` | Required | Role description |

Agent files are installed to `~/.claude/agents/` and tracked in `.installed-manifest.json`.

---

## 4. plugin.json Format

`plugin.json` is the plugin manifest. It can live at two locations (tried in order):
1. `<skill_path>/plugin.json` (root-level, preferred)
2. `<skill_path>/.claude-plugin/plugin.json` (platform-specific subdirectory fallback)

### Schema

```json
{
  "name": "<slug>",
  "description": "<description>",
  "version": "0.1.0",
  "author": { "name": "", "email": "" },
  "license": "MIT",
  "keywords": [],
  "compatible_platforms": ["claude-code"],
  "skills": "./skills",           // string (directory path) OR array of file paths
  "agents": [
    "./agents/agent1.md",
    "./agents/agent2.md"
  ],
  "commands": "./commands",       // string OR array
  "mcp-servers": [
    {
      "name": "<server-name>",
      "command": "<command>",
      "args": [],
      "env": {}
    }
  ]
}
```

### Component value forms

Each of `skills`, `agents`, `commands` can be:
- **String (directory path):** e.g. `"./skills"` — installer recursively fetches all files in that directory
- **Array of file paths:** e.g. `["./agents/foo.md", "./agents/bar.md"]` — installer fetches each listed file

### compatible_platforms

- Array of strings: known values include `"claude-code"`, `"codex"`
- If absent: treated as `["claude-code"]` for backward compatibility
- If present and does not include `"claude-code"`: installer warns before proceeding

### .claude-plugin/ subdirectory convention

The `.claude-plugin/` subdirectory pattern allows a repo to place `plugin.json` in a platform-specific hidden directory without cluttering the repo root. The regex `r"(^|\/)\.[\w-]+-plugin$"` matches any `.<name>-plugin` directory. Similarly, `.codex-plugin/plugin.json` is supported for the Codex platform.

This project's own manifest lives at `.claude-plugin/plugin.json` and reads:
```json
{
  "name": "agent-knowledge-hub",
  "description": "Discover, install, rate, and submit skills from the SLAC S3DF catalog...",
  "version": "1.0.0",
  "skills": "./skill/"
}
```

---

## 5. Claude Code's Native Plugin Install (Git Clone)

Per `docs/github-api-plugin-installation.md`, Claude Code's **native `/plugin install`** mechanism uses git clone (not the Contents API):

```
source types:
  github    → full git clone of the repo at a pinned ref/sha
  git-subdir → sparse clone of a subdirectory (for monorepos)
  url       → direct git URL clone
  npm       → npm install
```

- Cache location: `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`
- Plugin manifest location: `.claude-plugin/plugin.json`
- Version pinning: SHA-pinned via `ref` + `sha` fields in a marketplace.json
- No GitHub API rate limits (uses git protocol)
- Auth: existing git credential helpers (gh auth, SSH keys)

The AKH installer skill uses the GitHub Contents API instead (no git binary dependency), which is a deliberate trade-off documented in TODO #020 ADR-001.

---

## 6. CLAUDE.md Context Loading

`CLAUDE.md` serves dual purpose:
1. As a **context file**: automatically loaded into every Claude Code session to provide project-specific instructions, conventions, routing tables, etc.
2. As a **skill filename alias**: `CLAUDE.md` is accepted as equivalent to `SKILL.md` for skill discovery in GitHub repos.

The project's global `~/.claude/CLAUDE.md` contains session-level instructions (skill routing table, file access boundaries, terminal command conventions). The project `.claude/` directory contains project-scoped skills but no CLAUDE.md at the project root.

---

## 7. How Skills Are Invoked

Skills are invoked as slash commands using the `name` frontmatter field or the filename:

```
/agent-knowledge-hub search <query>
/deploy
/k8s-access
```

The Skill tool in Claude Code's tool set is used to invoke skills programmatically. When invoked, the SKILL.md body is read by Claude as operational instructions for that command.

The global CLAUDE.md can contain a skill routing table mapping user intent patterns to specific skills, which Claude uses to decide when to automatically invoke a skill.

---

## 8. Package-Embedded Skills (`.agents/` in Python packages)

The FastAPI Python package ships with a `.agents/` directory inside the package:

```
site-packages/fastapi/.agents/skills/fastapi/SKILL.md
site-packages/fastapi/.agents/skills/fastapi/references/other-tools.md
site-packages/fastapi/.agents/skills/fastapi/references/dependencies.md
site-packages/fastapi/.agents/skills/fastapi/references/streaming.md
```

This indicates Claude Code has a mechanism to discover skills embedded in Python packages (and presumably other package managers) via a `.agents/` directory at the package root. This is distinct from the `~/.claude/skills/` installation path — it appears to be a package-level skill distribution mechanism.

---

## 9. Installed-Files Manifest

After any successful install, the installer writes:

```json
// ~/.claude/skills/<slug>/.installed-manifest.json
{
  "slug": "<slug>",
  "installed_at": "<ISO timestamp>",
  "commands": ["<absolute-path-to-command-file>", ...],
  "agents":   ["<absolute-path-to-agent-file>", ...]
}
```

Skills-dir files are NOT listed (the whole `~/.claude/skills/<slug>/` dir is deleted on remove). Only files installed to the shared `commands/` and `agents/` directories are tracked.

---

## 10. Security Model

The installer enforces path traversal prevention:

```
Allowed prefixes by component type:
  skills  → ~/.claude/skills/<slug>/
  commands → ~/.claude/commands/
  agents  → ~/.claude/agents/
```

Every file path written during install is resolved to an absolute path and asserted to start with the allowed prefix. Any path traversal attempt aborts the entire install.

---

## Key Facts Summary

| Topic | Fact |
|---|---|
| Skills directory | `~/.claude/skills/<slug>/SKILL.md` (global); `.claude/skills/<slug>/SKILL.md` (project-scoped) |
| Commands directory | `~/.claude/commands/` (shared, flat) |
| Agents directory | `~/.claude/agents/` (shared, flat) |
| Skill file format | Markdown with optional YAML frontmatter (`name`, `description`, `version`, `platforms`, `keywords`) |
| Accepted skill filenames | `SKILL.md`, `skill.md`, `CLAUDE.md` |
| Agent file format | Markdown with YAML frontmatter (`name`, `description`) + system prompt body |
| Plugin manifest | `plugin.json` at skill root OR `.claude-plugin/plugin.json` (tried in order) |
| Plugin manifest schema | `name`, `version`, `skills`/`agents`/`commands`/`mcp-servers`, `compatible_platforms`, `author`, `keywords` |
| Component declaration | String (directory path) OR array of file paths |
| Native install mechanism | Git clone; cache at `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` |
| AKH install mechanism | GitHub Contents API recursive fetch (no git dependency) |
| Context loading | CLAUDE.md loaded automatically each session; both global and project-level |
| Package-embedded skills | `.agents/skills/<name>/SKILL.md` inside Python package directories |
| Platform identifiers | `"claude-code"`, `"codex"` (at minimum) |

---

## Source Files

All primary sources are project-local documents:

- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/skill/SKILL.md` — installer skill (canonical behavior reference)
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/docs/skill-file-discovery.md` — GitHub scan algorithm
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/docs/github-api-plugin-installation.md` — API comparison, native install behavior
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/docs/adr/adr-u02-frontmatter-format.md` — frontmatter format decision
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/todo/020-installer-skill-extension.md` — plugin.json canonical spec
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/.claude-plugin/plugin.json` — live plugin manifest example
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/.claude/skills/k8s-access/SKILL.md` — project-scoped skill example
- `/sdf/home/y/ytl/k8s/agent-knowledge-hub/backend/.venv/lib/python3.12/site-packages/fastapi/.agents/skills/fastapi/SKILL.md` — package-embedded skill example

External references cited in local docs (not fetched — web tools unavailable):
- https://code.claude.com/docs/en/plugins
- https://code.claude.com/docs/en/plugin-marketplaces
- https://code.claude.com/docs/en/discover-plugins

---

## Conflicts and Gaps

### Conflicts
- None identified between local sources. The installer SKILL.md and the design docs are internally consistent.

### Gaps / Uncertainties
1. **Exact Claude Code version** when `.agents/` package discovery was introduced — the FastAPI package embeds skills this way, but there is no local documentation on when/how Claude Code activates package-level `.agents/` directories.
2. **Commands file format** — the sources describe commands as `.md` files installed to `~/.claude/commands/`, but no example command file was found locally to confirm frontmatter schema.
3. **Marketplace.json schema** — the `docs/github-api-plugin-installation.md` references a `marketplace.json` that stores `ref` + `sha` for version pinning, but no example or schema was found locally.
4. **Global vs. project CLAUDE.md merge semantics** — it is unclear whether both are concatenated, or whether the project-level CLAUDE.md overrides the global one.
5. **Codex install paths** — `compatible_platforms` accepts `"codex"` but Codex's equivalent of `~/.claude/` is not documented locally (ADR-003 in TODO #020 explicitly defers this).

---

## Analysis

- **The `plugin.json` + `.claude-plugin/` convention is a multi-platform compatibility pattern.** Placing `plugin.json` inside `.claude-plugin/` allows a repo to hold platform-specific manifests for Claude Code, Codex, and others side by side without collisions. The `_plugin_subdir_re` regex on the AKH backend normalizes all these to the same root directory, which prevents duplicate scan entries.

- **SKILL.md is both a human-readable doc and a machine-parsed instruction file.** The YAML frontmatter provides structured metadata for catalog display, while the Markdown body is the actual prompt/instruction text Claude executes. This dual-purpose design means a well-written SKILL.md needs to serve two audiences: humans browsing the catalog and Claude following the instructions.

- **Package-embedded skills (`.agents/` in site-packages) suggest Claude Code has a broader discovery mechanism than just `~/.claude/`.** The FastAPI package ships with a `.agents/` directory, which Claude Code apparently loads automatically when working in a Python project that has FastAPI installed. This represents a third tier of skill discovery beyond global (`~/.claude/`) and project-local (`.claude/`).

- **The AKH installer design deliberately trades accuracy for simplicity.** The native Claude Code plugin system uses git clone (no rate limits, arbitrary depth, handles monorepos naturally). AKH uses the GitHub Contents API to avoid the `git` system dependency inside a skill, which introduces O(depth) round trip costs and rate limit exposure. This is an explicit, documented trade-off.

- **The shared `~/.claude/commands/` and `~/.claude/agents/` directories are a coordination problem.** Multiple installed skills write to the same flat directories. The installed-files manifest was introduced specifically to solve the "which files belong to which skill?" question on remove/update, but pre-manifest installs cannot be cleaned up automatically if they used directory-form declarations. This is a known limitation.
