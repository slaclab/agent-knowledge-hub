# OpenCode and OpenAI Codex: Plugin, Skill, and Extension Systems

**Research date:** 2026-06-02  
**Status:** Complete

---

## What is OpenCode?

OpenCode (github.com/sst/opencode, opencode.ai) is **not** the legacy VS Code open-source fork. It is a fully independent, open-source AI coding agent built by the SST team. It is a terminal CLI + desktop application (beta) for macOS, Windows, Linux — with IDE integrations as separate SDK projects.

- 160K GitHub stars, ~7.5M monthly developers
- Written primarily in TypeScript (66.8%) + MDX documentation, using Bun as package manager, Turborepo monorepo
- Distributed as `opencode-ai` on npm, also via Homebrew, Scoop, curl install script, and desktop app
- MCP (Model Context Protocol) is a first-class integration layer
- Supports multiple LLM providers: Anthropic, OpenAI, Gemini, and others

---

## OpenCode Extension Architecture

OpenCode has **four distinct layers** of customization, from lowest to highest abstraction:

### 1. Plugins (JavaScript/TypeScript event hooks)

**Format:** JavaScript or TypeScript files exporting one or more plugin functions.

Each plugin function signature:
```typescript
export default function(context: PluginContext): PluginHooks {
  return {
    "tool.execute.before": async (input, output) => { ... },
    "session.idle": async (input, output) => { ... },
    "file.edited": async (input, output) => { ... },
    // ...
  }
}
```

Context object contains: `project`, `client`, `$` (shell), `directory`, `worktree`, `serverUrl`.

**Directory conventions:**
- Project-local: `.opencode/plugins/`
- Global: `~/.config/opencode/plugins/`

**Distribution via npm:**  
Plugins can be npm packages (regular or scoped). Specified in `opencode.json`:
```json
{ "plugin": ["my-plugin-pkg", "@org/another-plugin"] }
```
npm plugins are installed automatically using Bun at startup, cached in `~/.cache/opencode/node_modules/`.

**Load order:** global config → project config → global plugins → project plugins (later plugins override earlier).

**Available hooks:** `tool.execute.before`, `session.idle`, `file.edited`, and others. Plugins can also define custom tools inline.

**Internal built-in plugins** (loaded before user plugins): CodexAuthPlugin, CopilotAuthPlugin, and others.

**Use cases documented:** notifications on task completion, protecting `.env` files, injecting environment variables, customizing session compaction prompts, sandboxing via Daytona.

**Community ecosystem:** opencode.cafe, awesome-opencode aggregate community plugins. No centralized marketplace — GitHub repositories and npm are the distribution channels.

---

### 2. Custom Tools (TypeScript/JS functions exposed as LLM tools)

**Format:** TypeScript or JavaScript files using a `tool()` helper:
```typescript
export const myTool = tool({
  description: "...",
  args: z.object({ ... }),   // Zod schema validation
  async execute(args, ctx) { ... }
})
```

Context available: agent name, session ID, directory, git worktree root.

**Directory conventions:**
- Project-local: `.opencode/tools/`
- Global: `~/.config/opencode/tools/`

**Naming:** filename becomes tool name; multiple exports per file named `<filename>_<exportname>`.

**Override behavior:** custom tools take precedence over built-in tools with the same name (allows replacing `read`, `write`, `bash`).

**Multi-language support:** tool definitions must be TS/JS, but can invoke Python, bash, or other language scripts via `Bun.$`.

**No separate npm distribution** — custom tools are project-local or global files only, not packaged as npm modules (unlike plugins).

---

### 3. Agent Skills (SKILL.md instruction files)

**Format:** Markdown files with YAML frontmatter, named `SKILL.md`:
```markdown
---
name: git-release
description: Handles git versioning and release workflows
license: MIT
compatibility: opencode>=0.8.0
---

# Git Release Skill
[Markdown instructions here...]
```

Frontmatter required: `name` (string, 1–64 chars, lowercase alphanumeric + hyphens), `description` (string).  
Optional: `license`, `compatibility`, `metadata`.  
Directory name must match `name` field.

**Directory conventions:**
- Project-local: `.opencode/skills/<name>/SKILL.md`
- Global: `~/.config/opencode/skills/<name>/SKILL.md`
- Also scans `.claude/` and `.agents/` directories for compatibility with Claude Code and other agents

**Discovery:** OpenCode walks up from current working directory to the git worktree boundary, loading all matching `skills/**/SKILL.md` and `{skill,skills}/**/SKILL.md` patterns. Also supports remote URLs in `opencode.json` `instructions` field.

**Injection mechanism:** Skills are **loaded on-demand** via the native `skill` tool. The LLM agent sees available skill names/descriptions and requests full content when needed — they are not pre-loaded into context. This preserves context window budget.

**A built-in `customize-opencode` skill** is registered by default; user-defined skills override it.

**Compatibility with Claude Code:** The scanner also reads from `.claude/` directories, meaning Claude Code CLAUDE.md-style files are recognized. OpenCode explicitly falls back to `~/.claude/CLAUDE.md` for rules if not disabled.

**Distribution:** No dedicated marketplace. Skills are typically committed to project repos or global config. The same file format is designed to be compatible with Claude Code's skill/command conventions.

---

### 4. Agents (Custom agent configurations)

**Format:** Either JSON in `opencode.json` or standalone `.md` files:
```
~/.config/opencode/agents/<name>.md
.opencode/agents/<name>.md
```

Agent config fields:
- `mode`: `"primary"` | `"subagent"` | `"all"`
- `model`: LLM model identifier (e.g., `"anthropic/claude-sonnet-4-20250514"`)
- `prompt`: path to system instructions file
- `description`: required for subagents
- `permission`: granular tool permission map (`read`, `edit`, `bash`, `glob`, `grep`, `lsp`, `task`, `webfetch`, `websearch`)
- `temperature`, `top_p`, `steps`, `color`

Built-in agents: `build` (full access, default), `plan` (read-only, confirms before bash), `general` (subagent for complex searches).

**Interactive creation:** `opencode agent create` wizard generates the markdown config file.

**Permission system for skills/tools:** `opencode.json` `permissions` key with `allow`/`deny`/`ask` patterns:
```json
{
  "permissions": {
    "skill": "ask",
    "skill/git-release": "allow",
    "bash": "allow",
    "bash/git push *": "deny"
  }
}
```

---

### 5. MCP Servers (Model Context Protocol)

**Format:** Configured in `opencode.json` under `mcp` key:
```json
{
  "mcp": {
    "my-server": {
      "type": "local",
      "command": ["npx", "-y", "my-mcp-package"],
      "env": { "KEY": "value" }
    },
    "remote-server": {
      "type": "remote",
      "url": "https://api.example.com/mcp",
      "headers": { "Authorization": "Bearer ..." }
    }
  }
}
```

**Auto-discovery:** MCP tools become immediately available to the LLM alongside built-in tools once configured.

**OAuth support:** Remote MCPs with 401 responses trigger automatic OAuth flow with Dynamic Client Registration.

**Context warning:** Each MCP server adds to the agent's context window, so token budget management is important.

---

### opencode.json Configuration Schema

- Format: JSON or JSONC (with comments), schema validated against `https://opencode.ai/config.json`
- **Merge behavior:** configs from multiple locations are *merged*, not replaced; later configs override conflicting keys only
- Precedence: remote org defaults → global config → project config → CLI flags

Key top-level fields:
- `plugin`: `string[]` — npm plugin names
- `mcp`: `Record<string, MCPServerConfig>` — MCP servers
- `agent`: `Record<string, AgentConfig>` — custom agent definitions
- `instructions`: `string[]` — additional instruction file paths or URLs
- `permissions`: permission map

---

### Rules / Instruction Injection (AGENTS.md)

OpenCode uses `AGENTS.md` files (same name convention as OpenAI Codex) as the primary rules/instruction format:

**Search order:**
1. Project `AGENTS.md` or `CLAUDE.md` (walks up to git root)
2. Global `~/.config/opencode/AGENTS.md`
3. Fallback: `~/.claude/CLAUDE.md` (if not disabled)

Additional instruction files can be specified in `opencode.json`:
```json
{
  "instructions": ["docs/guidelines.md", "https://example.com/rules.md"]
}
```
Supports glob patterns and remote URLs (5-second timeout on remote fetch).

**`/init` command** generates initial project rules file.

---

## OpenAI Codex CLI

OpenAI Codex CLI (github.com/openai/codex) is a separate product from the original OpenAI Codex model. It is "a lightweight coding agent that runs in your terminal," released under Apache-2.0.

There are **two implementations**:
1. **codex-cli** (TypeScript/Node) — the original CLI
2. **codex-rs** (Rust) — a newer, faster Rust rewrite

**Installation:** curl install script, npm, Homebrew, platform binaries from GitHub Releases.  
**Authentication:** ChatGPT account (Plus/Pro/Business/Enterprise/Edu) or API key.  
**IDE integrations:** VS Code, Cursor, Windsurf (as separate extensions, not plugins within Codex itself).

### AGENTS.md in OpenAI Codex

The `AGENTS.md` file found at the root of the openai/codex repository is the **developer contribution guide** for the project itself (coding standards, testing conventions, Rust style, etc.) — not a user-facing customization mechanism.

However, based on the Rust version (`codex-rs`) documentation, Codex does support `AGENTS.md` files as an instruction injection mechanism for the agent:
- Project-level `AGENTS.md` files provide custom context/instructions to the agent
- Same convention used by OpenCode and other tools — a converging standard

### Codex Rust CLI Configuration

- Configuration file: `~/.codex/config.toml` (TOML format, unlike OpenCode's JSON)
- **MCP support:** Can connect to MCP servers on startup; can also run *as* an MCP server via `codex mcp-server`
- **Sandbox policies:** `--sandbox` flag with `read-only` (default), `workspace-write`, `danger-full-access`
- **Memory:** `~/.codex/memories` path for agent memory across sessions
- **Notifications:** Scripts executed when agent completes a task
- **Non-interactive mode:** `codex exec` for programmatic/scripted usage
- **Execution mode:** `RUST_LOG` env var for debug logging

### Codex MCP Interface

The `codex-rs` Rust implementation exposes a JSON-RPC 2.0 API over MCP stdio transport (`codex mcp-server`):
- Thread management: start, resume, fork, read, list
- Turn control: start, steer, interrupt
- Configuration endpoints (write, batch)
- Model listing with reasoning effort levels
- `collaborationMode/list` — pre-built profiles that modify reasoning effort and developer instructions
- Event streaming via `codex/event/*` notifications
- Approval gates: `applyPatchApproval`, `execCommandApproval`
- Status: experimental, method names subject to change

### Plugin/Extension System (Codex CLI)

Unlike OpenCode, the OpenAI Codex CLI does **not** have a formal plugin or skill system analogous to OpenCode's. Customization is limited to:
- `AGENTS.md` instruction files (project/global rules)
- `config.toml` model and behavior settings
- MCP server integration (connect external tools)
- Sandbox policy selection

There is no npm plugin ecosystem, no SKILL.md format, no custom tool API, and no agent marketplace for Codex CLI. Extension happens primarily through MCP servers and IDE integrations.

---

## Comparison: OpenCode vs. Codex vs. Claude Code

| Dimension | OpenCode | OpenAI Codex CLI | Claude Code |
|---|---|---|---|
| Plugin format | JS/TS npm packages, event hooks | None (MCP only) | CLAUDE.md skills (markdown) |
| Skill format | SKILL.md with YAML frontmatter | AGENTS.md (instructions only) | Skills in `~/.claude/skills/` |
| Distribution | npm packages, GitHub | None (MCP servers externally) | npm (planned), GitHub |
| Config file | `opencode.json` (JSON/JSONC) | `~/.codex/config.toml` (TOML) | `.claude/settings.json` |
| Rules/instructions | AGENTS.md, CLAUDE.md compat | AGENTS.md | CLAUDE.md |
| Custom tools | TS/JS files in `.opencode/tools/` | None | Bash tool + hooks |
| MCP | First-class, local + remote + OAuth | Supported (connect + serve) | Supported |
| Agent customization | Full (model, prompt, perms, mode) | Limited (sandbox policy) | Via system prompt / settings |
| Installation | npm, brew, curl, desktop app | npm, brew, curl, binaries | npm |
| Discovery | Walk git tree + config dirs | Walk git tree (AGENTS.md) | Walk git tree (CLAUDE.md) |
| Community | opencode.cafe, awesome-opencode | None | None (yet) |

---

## Key Sources

1. OpenCode official docs — skills: https://opencode.ai/docs/skills/
2. OpenCode official docs — plugins: https://opencode.ai/docs/plugins/
3. OpenCode official docs — custom tools: https://opencode.ai/docs/custom-tools/
4. OpenCode official docs — agents: https://opencode.ai/docs/agents
5. OpenCode official docs — MCP servers: https://opencode.ai/docs/mcp-servers
6. OpenCode official docs — config: https://opencode.ai/docs/config
7. OpenCode official docs — rules: https://opencode.ai/docs/rules
8. OpenCode official docs — permissions: https://opencode.ai/docs/permissions
9. OpenCode official docs — ecosystem: https://opencode.ai/docs/ecosystem
10. OpenCode GitHub repo: https://github.com/sst/opencode
11. OpenCode SDK docs: https://opencode.ai/docs/sdk
12. OpenCode plugin source (internal): https://github.com/sst/opencode/blob/dev/packages/opencode/src/plugin/index.ts
13. OpenCode skill source: https://github.com/sst/opencode/blob/dev/packages/opencode/src/skill/index.ts
14. OpenAI Codex GitHub repo: https://github.com/openai/codex
15. OpenAI Codex MCP interface docs: https://github.com/openai/codex/blob/main/codex-rs/docs/codex_mcp_interface.md
16. OpenAI Codex Rust README: https://github.com/openai/codex/blob/main/codex-rs/README.md
17. OpenAI Codex AGENTS.md: https://github.com/openai/codex/blob/main/AGENTS.md

---

## Conflicts and Gaps

- **AGENTS.md dual meaning in Codex:** The `AGENTS.md` at the root of openai/codex is a dev contribution guide, not a user-facing instruction file. Whether Codex CLI actually uses project-level `AGENTS.md` as instruction injection (like OpenCode does) could not be fully confirmed from publicly accessible source files — the codex-cli TypeScript source returned 404s.
- **Codex CLI plugin system:** No evidence of any plugin or extension API beyond MCP. This may be intentional (Codex positions as a minimal agent, extending via MCP rather than native plugins).
- **OpenCode SKILL.md distribution:** No centralized skill registry exists. Skills must be manually shared via GitHub or included in project repos. No equivalent of an npm registry for SKILL.md files.
- **OpenCode version compatibility:** The `compatibility` frontmatter field in SKILL.md is documented but enforcement mechanism was not confirmed in source code review.
- **Codex Web vs CLI:** The cloud version at chatgpt.com/codex may have different customization capabilities not covered here (focused on CLI).

---

## Analysis: Implications, Tensions, Patterns

1. **AGENTS.md is converging as an industry standard.** Both OpenCode and OpenAI Codex use `AGENTS.md` as the project-level instruction file convention. Claude Code uses `CLAUDE.md` but OpenCode explicitly reads both. This suggests a cross-tool portability standard is emerging — projects may eventually maintain a single instruction file that works across all agents.

2. **OpenCode's layered extensibility is significantly more sophisticated than Codex CLI.** OpenCode has four distinct extension layers (plugins, custom tools, skills, agents) with clear separation of concerns, while Codex CLI essentially has one (MCP integration). This reflects different philosophies: OpenCode optimizes for power-user customization, Codex optimizes for simplicity and IDE integration.

3. **npm as the plugin distribution channel for AI agents creates security risks.** OpenCode's automatic Bun install of npm plugins at startup means any package in `opencode.json` runs arbitrary code. This mirrors historical npm supply chain attack patterns. No signature verification or sandboxing for plugins was documented.

4. **Skills/SKILL.md are intentionally context-efficient.** The on-demand loading model (agent requests skill content only when needed) is a deliberate design choice to avoid pre-loading all skills into context. This contrasts with Claude Code's approach where skills/CLAUDE.md content may be included more eagerly. This has significant implications for skill discovery UX — users need to ensure descriptions are accurate enough for the agent to know when to load them.

5. **The absence of a centralized skill registry is a gap for both tools.** OpenCode's skills are distributed via GitHub and project repos; Codex CLI has no skill concept at all. Claude Code's planned npm distribution (if it follows similar patterns) would be the first attempt at a formal skill registry/marketplace in this space — a potential competitive advantage if executed well.
