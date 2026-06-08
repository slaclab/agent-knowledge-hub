# Agent Skill, MCP Server, and Plugin Integration: Research Report

*Generated: 2026-06-02 | Sources: 27 | Confidence: High (MCP spec + official agent docs) / Medium (Codex CLI internals)*

---

## Executive Summary

Claude Code, OpenCode (sst/opencode), and OpenAI Codex approach skill/plugin/MCP integration from fundamentally different philosophies, but a clear convergence is underway at the instruction-file level (`AGENTS.md` / `CLAUDE.md`). At the wire level, MCP servers are portable across all agents — any compliant server binary runs on all three. Deployment portability does not exist: config file formats, auth syntax, and permission models are agent-specific and not standardized. Agent Knowledge Hub is uniquely positioned as the missing registry layer the entire ecosystem lacks; no agent has a formal centralized skill or plugin marketplace today. AKH's existing `plugin.json` + `SKILL.md` format is already partially cross-compatible with OpenCode, and the `compatible_platforms` field is the right architectural direction. The primary gaps for AKH are: richer MCP metadata per `#023`, AGENTS.md scanner support, per-agent installer config generation, and surfacing the package-embedded `.agents/` discovery tier.

---

## 1. Skill / Plugin Discovery and File Formats

### Claude Code: Three-Tier Discovery

Claude Code discovers skills and instructions at three distinct tiers:

| Tier | Location | Notes |
|---|---|---|
| Global | `~/.claude/skills/<slug>/SKILL.md` | Installed by AKH installer |
| Project | `.claude/skills/<slug>/SKILL.md` | Project-scoped, committed to repo |
| Package-embedded | `<site-packages>/<pkg>/.agents/skills/<name>/SKILL.md` | Auto-loaded from installed Python packages |

The package-embedded tier is the least-documented: FastAPI ships `.agents/skills/fastapi/SKILL.md` inside its Python package, and Claude Code apparently loads it automatically when working in a project with FastAPI installed. This third tier has no equivalent in AKH's scanner today.

**Supporting files** (`~/.claude/`):
- `commands/` — slash command `.md` files (shared flat directory across all skills)
- `agents/` — agent definition `.md` files (shared flat directory)
- `plugins/cache/<marketplace>/<plugin>/<version>/` — native git-clone plugin cache

**SKILL.md format** (Claude Code canonical):
```markdown
---
name: my-skill
description: One-sentence summary
version: 1.2.0
platforms: [claude-code, openai]
keywords: [k8s, deploy]
---

# /my-skill

Body: instructions Claude follows when invoked.
```

Frontmatter is purely additive — files without it degrade gracefully. Accepted filenames: `SKILL.md`, `skill.md`, `CLAUDE.md`.

**Agent files** (`~/.claude/agents/<name>.md`): Markdown with `name` + `description` frontmatter and a system prompt body.

**Commands**: `.md` files installed to `~/.claude/commands/`. Format not yet fully documented (frontmatter schema unconfirmed).

**`plugin.json`** discovery order: `<skill_path>/plugin.json` → `<skill_path>/.claude-plugin/plugin.json` → legacy flat install. The `.claude-plugin/` convention allows platform-specific manifests to coexist in one repo without conflict.

**Native install (git clone)**: Claude Code's native `/plugin install` uses git clone with SHA pinning to `~/.claude/plugins/cache/`. The AKH installer uses the GitHub Contents API instead — more portable (no `git` dependency) but slower and rate-limited for large repos.

### OpenCode: Four-Layer Extensibility

OpenCode (sst/opencode, ~160K GitHub stars) has a significantly richer extension architecture:

| Layer | Format | Directory | Distribution |
|---|---|---|---|
| Plugins | JS/TS npm packages with event hooks | `.opencode/plugins/` or `~/.config/opencode/plugins/` | npm auto-installed at startup |
| Custom Tools | TS/JS `tool()` helper with Zod schema | `.opencode/tools/` or `~/.config/opencode/tools/` | Project-local only |
| Agent Skills | `SKILL.md` with YAML frontmatter | `.opencode/skills/<name>/SKILL.md` | GitHub/project repos |
| Agents | JSON in `opencode.json` or `.md` files | `.opencode/agents/` or `~/.config/opencode/agents/` | Config file |

**OpenCode's SKILL.md format** is nearly identical to Claude Code's:
```markdown
---
name: git-release          # required, 1-64 chars, lowercase alphanumeric + hyphens
description: Handles git versioning and release workflows  # required
license: MIT
compatibility: opencode>=0.8.0
---
```

**Critical compatibility fact**: OpenCode explicitly scans `.claude/` directories, reads `CLAUDE.md` files, and falls back to `~/.claude/CLAUDE.md` for global rules. AKH skills installed to `~/.claude/skills/` are therefore usable in OpenCode sessions with no modification.

**Skill injection**: OpenCode loads skills **on-demand** — the agent sees skill names/descriptions and requests full content via a `skill` tool call only when needed. This contrasts with Claude Code's eager context loading. Skill descriptions must be precise enough for the agent to know when to invoke them.

**Config file** (`opencode.json` or `opencode.jsonc`): JSON/JSONC with `$schema` validation. Multiple config files are merged (not replaced) in order: remote org defaults → global → project → CLI flags.

**Instructions**: OpenCode reads `AGENTS.md` first, then `CLAUDE.md` (walking up the git tree), then global `~/.config/opencode/AGENTS.md`, then `~/.claude/CLAUDE.md`. Additional instruction files via `"instructions"` array in config (supports glob patterns and remote URLs).

### OpenAI Codex CLI: Minimal, MCP-Centric

OpenAI Codex CLI (github.com/openai/codex) has **no formal plugin or skill system**. Two implementations exist: TypeScript `codex-cli` and Rust `codex-rs`.

Customization is limited to:
- `AGENTS.md` instruction files (project-level rules injection — same convention as OpenCode)
- `~/.codex/config.toml` (TOML format; model, sandbox policy, memory path, notification scripts)
- MCP server integration (the primary extension mechanism)
- Sandbox policy: `read-only` (default), `workspace-write`, `danger-full-access`

The `codex-rs` Rust implementation can also **expose itself as an MCP server** (`codex mcp-server`), providing a JSON-RPC 2.0 API over stdio for thread/turn management, config changes, model listing, and approval gates.

---

## 2. MCP Server Configuration Across Agents

### Transport Types (Spec-Level, MCP 2025-11-25)

| Transport | Description | Status |
|---|---|---|
| `stdio` | Subprocess stdin/stdout, newline-delimited JSON-RPC | ✅ Standard, universally supported |
| Streamable HTTP | HTTP POST + optional SSE, single endpoint | ✅ Current standard (replaces HTTP+SSE) |
| HTTP+SSE | Separate SSE + POST endpoints | ⚠️ Deprecated (protocol version 2024-11-05) |
| WebSocket | — | ❌ Not a standard MCP transport |

For Streamable HTTP: client MUST include `Accept: application/json, text/event-stream` and `MCP-Protocol-Version: <version>` headers. Session management via `Mcp-Session-Id` header.

### Config Format Comparison

**Claude Code** (inferred from Claude Desktop docs; same `mcpServers` schema):
```json
// ~/.claude/settings.json  (user-global)
// .mcp.json                (project, shared, committed)
// .claude/settings.local.json  (machine-local, gitignored)
{
  "mcpServers": {
    "epics-archiver": {
      "command": "uvx",
      "args": ["mcp-server-epics", "--url", "https://archiver.slac.stanford.edu"],
      "env": {
        "ARCHIVER_TOKEN": "your-token-here"
      }
    }
  }
}
```

**OpenCode**:
```jsonc
// opencode.json
{
  "mcp": {
    "epics-archiver": {
      "type": "local",          // explicit transport field
      "command": ["uvx", "mcp-server-epics"],
      "environment": {
        "ARCHIVER_TOKEN": "{env:ARCHIVER_TOKEN}"  // env interpolation syntax
      },
      "enabled": true,
      "timeout": 10000
    },
    "remote-server": {
      "type": "remote",
      "url": "https://api.example.com/mcp",
      "headers": { "Authorization": "Bearer {env:MY_TOKEN}" },
      "oauth": { "clientId": "...", "clientSecret": "{env:CLIENT_SECRET}", "scope": "read write" }
    }
  }
}
```

**OpenAI Agents Python SDK** (programmatic only — no static config file):
```python
from agents.mcp import MCPServerStdio, MCPServerStreamableHTTP
server = MCPServerStdio(command="uvx", args=["mcp-server-epics"], env={"ARCHIVER_TOKEN": "..."})
agent = Agent(name="Assistant", mcp_servers=[server])
```

**Config format incompatibility table**:

| | Claude Code | OpenCode | OpenAI Agents SDK |
|---|---|---|---|
| Config file | `settings.json` / `.mcp.json` | `opencode.json` | Python code |
| Top-level key | `"mcpServers"` | `"mcp"` | N/A |
| Transport declaration | Implicit (command = stdio, url = http) | Explicit `"type": "local"/"remote"` |  Class-based |
| Env var syntax | Inline JSON object | `"{env:VAR}"` string interpolation | `env=` param |
| OAuth | Not well-documented | Auto-handled, tokens at `~/.local/share/opencode/mcp-auth.json` | Manual in headers |

### MCP Authorization (OAuth 2.1, HTTP transport only)

Full OAuth 2.1 flow (with PKCE, RFC 7591 Dynamic Client Registration, RFC 8414 Auth Server Metadata) is specified for HTTP transport. Stdio servers use env-var credentials only — OAuth does not apply.

Flow: server returns `401` with `WWW-Authenticate: Bearer resource_metadata=<URL>` → client fetches PRM document from `/.well-known/oauth-protected-resource` → discovers auth server → registers (dynamic or pre-registered) → user authorizes via browser → token exchange → requests carry `Authorization: Bearer <token>`.

### Official MCP Registry

An official central registry exists at `modelcontextprotocol.io/registry` (in preview as of 2026, backed by Anthropic, GitHub, PulseMCP, Microsoft). Server names use reverse-DNS format: `io.github.user/server-name`. **It is not consumed directly by host applications** — it feeds downstream aggregators/marketplaces. Private servers are not supported. This is the infrastructure AKH could position itself above (as a domain-specific curated layer on top of the public registry).

---

## 3. Cross-Agent Compatibility

### What Is and Isn't Portable

| Layer | Portable? | Notes |
|---|---|---|
| MCP server binary | ✅ Yes | JSON-RPC 2.0 over stdio works on all agents |
| MCP config entry | ❌ No | Agent-specific file format and key names |
| SKILL.md content | ✅ Yes (Claude Code + OpenCode) | OpenCode explicitly reads `.claude/` dirs |
| AGENTS.md / CLAUDE.md | ✅ Converging | Both OpenCode and Codex use AGENTS.md; OpenCode also reads CLAUDE.md |
| plugin.json | ⚠️ Partial | Defined by AKH; `compatible_platforms` field is the right direction; not a cross-agent spec |
| OAuth token storage | ❌ No | Agent-specific paths and formats |
| Permission model | ❌ No | Per-agent, no standard |

### AGENTS.md Convergence

`AGENTS.md` is emerging as a cross-agent instruction file standard. OpenCode reads it first; Codex CLI (codex-rs) uses it for project-level instruction injection; Claude Code uses `CLAUDE.md` (a closely analogous filename). OpenCode explicitly bridges both by reading whichever is present.

**AKH implication**: The GitHub scanner (`github.py`) should be extended to recognize `AGENTS.md` as a fourth valid skill discovery filename alongside `SKILL.md`, `skill.md`, and `CLAUDE.md`. Skills authored for Codex-first workflows will use `AGENTS.md`.

### Cross-Platform plugin.json Design

The `.claude-plugin/` subdirectory convention already supports per-platform manifests coexisting in one repo. A parallel `.codex-plugin/plugin.json` convention is logically implied. The `compatible_platforms` array in AKH's plugin.json is the right design — it communicates to the installer which agents a plugin supports and warns on mismatch.

### MCP Extension Support Matrix Gap

Claude Code (CLI) is **absent from the official MCP extension support matrix** at `modelcontextprotocol.io/extensions/client-matrix.md`. The matrix lists Claude Desktop and Claude (web) but not Claude Code CLI. This likely means Claude Code's OAuth MCP support is incomplete or unverified.

---

## 4. Security Models and Attack Vectors

### No OS-Level Sandboxing Anywhere

All three agents rely on **soft permission controls** for MCP servers — none implement OS-level sandboxing (no seccomp, no container isolation, no privilege dropping). Stdio MCP servers run as subprocesses with the full user's OS privileges.

| Agent | Default stance | Granularity |
|---|---|---|
| Claude Code | Ask (human approval required outside allowlist) | Per-tool-category |
| OpenCode | Mostly allow (13 permission types, most default allow) | Per-server enable/disable; wildcard glob patterns |
| OpenAI Agents SDK | Configurable: `"always"/"never"` global or per-tool | Per-tool name or callback |

### Documented Attack Vectors (from MCP Security Best Practices)

1. **Confused Deputy Attack** — MCP proxy with static OAuth client ID + third-party auth server consent cookies allows attackers to steal auth codes via crafted links. Mitigation: per-client server-side consent records, `__Host-` cookie prefix.

2. **Token Passthrough** — MCP servers accepting tokens not issued to them bypass audit trails. Spec forbids this explicitly.

3. **SSRF via OAuth Metadata Discovery** — Malicious servers populate auth discovery URLs with internal IPs (cloud metadata at `169.254.169.254`, RFC 1918 ranges). Mitigation: HTTPS enforcement, IP blocklist, egress proxies (Smokescreen).

4. **Session Hijacking** — Guessable session IDs allow event injection across shared queues. Mitigation: cryptographically random session IDs bound to `<user_id>:<session_id>`.

5. **Local Server Compromise** — Malicious commands embedded in MCP config (supply chain via `npx malicious-pkg`), or DNS rebinding against local HTTP servers. Mitigation: pre-configuration consent dialog, sandbox subprocesses.

6. **Sampling Abuse** — `sampling/createMessage` lets MCP servers request LLM completions without API keys, enabling context exfiltration or prompt injection. Spec requires human-in-the-loop review.

### Credential Management: The Biggest Unresolved Gap

For stdio servers, the only portable pattern is **environment variables in plaintext config files**. No agent has a cross-platform secret management story. OpenCode stores OAuth tokens at `~/.local/share/opencode/mcp-auth.json` (agent-specific). No keychain integration or encrypted credential store is documented for any agent.

### npm Plugin Supply Chain Risk

OpenCode's automatic Bun install of npm plugins at startup (any package listed in `opencode.json`) means a compromised npm package runs arbitrary code silently. No signature verification or sandboxing is documented. This is a live supply chain attack surface.

---

## 5. AKH Integration Plans

### What Already Works

- **AKH SKILL.md format is cross-compatible with OpenCode** — no changes needed. OpenCode explicitly reads `.claude/skills/` directories.
- **`plugin.json` + `compatible_platforms`** — the right architecture; no other agent has an equivalent manifest standard.
- **MCP server detection** (`has_mcp_server`) — correct direction; `#023` extends this to rich metadata.

### Recommended Changes

**Immediate:**

1. **Add `AGENTS.md` to scanner's `_SKILL_FILES` set** — extend `github.py` discovery to recognize `AGENTS.md` as a valid skill instruction file (same weight as `CLAUDE.md`). Skills targeting Codex will use this filename.

2. **Surface `compatible_platforms` prominently in GUI** — not just platform badges but filter/search by platform. Users should be able to browse "skills that work in OpenCode" or "skills that work in Codex".

3. **Per-agent install snippet generation** — when a user views a skill, the installer command should be tailored to their agent. A Claude Code user gets `claude skill install <slug>`; an OpenCode user gets the `opencode.json` snippet to add. This is the UX equivalent of `#023`'s MCP config snippet generator.

**Short-term (new todo candidates):**

4. **Codex config path resolution** — `compatible_platforms` accepts `"codex"` but no one has documented Codex's install directories. Research `~/.codex/` conventions and implement the install path for Codex (currently deferred in #020 ADR-003).

5. **`AGENTS.md` as a first-class skill format** — update the scanner to parse `AGENTS.md` frontmatter (if present) and body. Expose in catalog with a Codex/OpenCode compatibility badge.

6. **Package-embedded skills scanner** — extend GitHub scanner to detect `.agents/skills/` directories inside Python packages (or npm packages). FastAPI already ships a skill this way; this is an emerging distribution pattern.

7. **MCP Registry integration** — AKH could act as a SLAC-domain aggregator above the official MCP Registry (`modelcontextprotocol.io/registry`). When a skill declares MCP servers with `package` identifiers, AKH could resolve them against the registry to pull install commands, transport type, and auth metadata automatically.

8. **Per-agent MCP config generator** — for skills with MCP servers, generate the correct config snippet per agent: `mcpServers` JSON for Claude Code, `mcp` JSON for OpenCode. This is a natural extension of `#023`'s copy-paste snippet.

**Architectural:**

9. **Namespace isolation for commands/agents** — the shared `~/.claude/commands/` and `~/.claude/agents/` directories are a collision hazard. AKH should push upstream for namespaced command paths (e.g., `~/.claude/commands/<slug>/`) or document the collision risk prominently.

10. **Security disclosure section on skill detail pages** — given the documented MCP attack vectors (SSRF, session hijacking, confused deputy), AKH should surface a security section for skills with MCP servers: transport type, whether OAuth is used, and whether the server is a known SLAC service (linking to `#023`'s access level metadata).

---

## Patterns & Implications

- **The agent ecosystem is converging on instruction files, not plugin formats.** `AGENTS.md` and `CLAUDE.md` are the cross-agent portability layer that's actually working. Formal plugin systems (OpenCode's JS hooks, Claude Code's git-clone plugins) are agent-specific. The winning portability bet is: one `SKILL.md` or `AGENTS.md` that all agents can read. AKH should optimize for this.

- **MCP is wire-portable but deployment-fragmented.** The spec guarantees that a compliant server binary runs anywhere. The last-mile deployment problem (getting the right config entry into the right config file for the right agent) is entirely unsolved by the spec and only partially solved by any agent. This deployment gap is exactly what AKH's installer skill can fill — and no other tool is trying to fill it with cross-agent awareness.

- **The absence of a centralized skill registry is a structural gap that AKH fills.** No agent has a formal marketplace: OpenCode's skills live in GitHub repos; Codex has no skill concept; Claude Code's planned npm distribution is unverified. AKH is the most developed registry attempt in this space. The MCP Registry (`modelcontextprotocol.io/registry`) is in preview and intentionally not a host-facing product — AKH operates at the right layer above it.

- **Security is host-enforced with no protocol backstop, and no agent gets it fully right.** No OS-level sandboxing exists anywhere. Credential storage is agent-specific and insecure (plaintext env vars or local JSON files). The attack vectors documented by the MCP spec (SSRF, confused deputy, session hijacking) are architectural — not bugs that will be patched. AKH surfacing auth/access metadata per #023 adds useful pre-install security signal that no other tool currently provides.

- **OpenCode's sophistication creates both a compatibility opportunity and a packaging risk.** OpenCode's four-layer extensibility (plugins, custom tools, skills, agents) means AKH skills work there without modification — but OpenCode's npm auto-install plugin pattern is a live supply chain risk. AKH could differentiate by being the vetted, curated channel for OpenCode plugins (with manual review) vs. unreviewed npm packages.

---

## Key Takeaways

1. **SKILL.md is already cross-compatible with OpenCode.** No format changes needed. Add `AGENTS.md` scanner support and AKH covers Claude Code + OpenCode + Codex for instruction files.

2. **AKH is the missing marketplace layer the entire ecosystem lacks.** Build it as cross-agent-aware from the start: `compatible_platforms`, per-agent install snippets, and per-agent MCP config generation.

3. **MCP server deployment config needs per-agent generation.** The wire protocol is portable; the config file is not. A skill detail page should show the correct `mcpServers` JSON for Claude Code and the correct `mcp` JSON for OpenCode — not just a generic command.

4. **#023's MCP metadata work directly addresses the ecosystem's biggest user friction point.** No tool today tells users what credentials and network access they need before installing a skill with an MCP server. AKH can be the first.

5. **Security should be a first-class signal in AKH.** Given documented SSRF, session hijacking, and supply chain risks, surfacing auth type, access level, and transport on the skill detail page isn't just nice-to-have — it's a meaningful differentiator against unreviewed npm/GitHub distributions.

---

## Sources

1. [MCP Specification 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26) — Core protocol spec, transports, capability negotiation
2. [MCP Transports](https://modelcontextprotocol.io/docs/concepts/transports) — stdio and Streamable HTTP definitions
3. [MCP Authorization](https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization) — OAuth 2.1 flow for HTTP transport
4. [MCP Security Best Practices](https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices.md) — Confused deputy, SSRF, session hijacking, scope inflation
5. [MCP Sampling](https://modelcontextprotocol.io/docs/concepts/sampling) — Server-initiated LLM calls security model
6. [MCP Client Best Practices](https://modelcontextprotocol.io/docs/develop/clients/client-best-practices.md) — Progressive discovery, code-mode sandboxing
7. [MCP Extension Support Matrix](https://modelcontextprotocol.io/extensions/client-matrix.md) — Client capability matrix (Claude Code CLI absent)
8. [MCP Registry](https://modelcontextprotocol.io/registry/about.md) — Official server registry (preview)
9. [MCP Connect Local Servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers.md) — Claude Desktop stdio config format
10. [MCP Connect Remote Servers](https://modelcontextprotocol.io/docs/develop/connect-remote-servers.md) — OAuth remote connector flow
11. [OpenCode MCP Servers](https://opencode.ai/docs/mcp-servers/) — OpenCode MCP config reference
12. [OpenCode Skills](https://opencode.ai/docs/skills/) — SKILL.md format and discovery
13. [OpenCode Plugins](https://opencode.ai/docs/plugins/) — JS/TS plugin hooks, npm distribution
14. [OpenCode Custom Tools](https://opencode.ai/docs/custom-tools/) — TS tool() helper API
15. [OpenCode Agents](https://opencode.ai/docs/agents) — Custom agent configuration
16. [OpenCode Config](https://opencode.ai/docs/config) — opencode.json schema reference
17. [OpenCode Rules](https://opencode.ai/docs/rules) — AGENTS.md / CLAUDE.md instruction loading
18. [OpenCode Permissions](https://opencode.ai/docs/permissions) — Three-state permission model
19. [OpenCode GitHub repo](https://github.com/sst/opencode) — Source, plugin internals
20. [OpenAI Agents Python SDK — MCP](https://github.com/openai/openai-agents-python/blob/main/docs/mcp.md) — Programmatic MCP config
21. [OpenAI Codex GitHub](https://github.com/openai/codex) — CLI source, AGENTS.md
22. [OpenAI Codex MCP Interface](https://github.com/openai/codex/blob/main/codex-rs/docs/codex_mcp_interface.md) — codex-rs as MCP server
23. [OpenAI Codex Rust README](https://github.com/openai/codex/blob/main/codex-rs/README.md) — Config, sandbox policies
24. AKH `skill/SKILL.md` — installer skill (canonical Claude Code behavior reference)
25. AKH `docs/github-api-plugin-installation.md` — native git-clone vs Contents API comparison
26. AKH `todo/020-installer-skill-extension.md` — canonical plugin.json spec
27. AKH `backend/.venv/.../fastapi/.agents/skills/fastapi/SKILL.md` — package-embedded skill example

---

## Methodology

Searched across 4 parallel subagents. Analyzed 27 sources. One subagent (agent-1) had no web tool access and used local project sources instead — findings are therefore grounded in AKH's own implementation, which itself synthesizes official Claude Code behavior.

**Sub-questions investigated:**
1. Claude Code file formats, directory conventions, SKILL.md, plugin.json, agent files
2. MCP server registration and config across Claude Code, OpenCode, and OpenAI Agents SDK
3. OpenCode and Codex plugin/skill/extension packaging and distribution
4. Cross-agent MCP compatibility and security models

**Fetch failures / gaps:**
- Claude Code's `settings.json` MCP config schema not directly accessible from Anthropic docs (permission denied); structure inferred from Claude Desktop docs (same schema)
- OpenAI Codex CLI (TypeScript) source files returned 404s on GitHub; codex-rs Rust implementation was accessible
- Claude Code (CLI) is absent from the official MCP extension support matrix — OAuth support status unverified
- OpenCode SKILL.md `compatibility` field enforcement not confirmed in source code
