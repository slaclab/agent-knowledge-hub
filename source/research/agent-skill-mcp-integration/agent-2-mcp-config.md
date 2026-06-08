# Agent MCP Server Configuration Research

**Sub-question:** How do Claude Code, OpenCode, and OpenAI Codex/Agents register and configure MCP servers?

**Research date:** 2026-06-02
**Researcher:** agent-2 (sub-agent)

---

## Sources

1. **MCP Official Spec — Transports** (https://modelcontextprotocol.io/specification/2025-11-25/basic/transports.md)
   - Fetched 2026-06-02. Primary source for transport protocol definitions.

2. **MCP Official Docs — Connect to Local Servers** (https://modelcontextprotocol.io/docs/develop/connect-local-servers.md)
   - Fetched 2026-06-02. Covers Claude Desktop `claude_desktop_config.json` format.

3. **MCP Official Docs — Connect to Remote Servers** (https://modelcontextprotocol.io/docs/develop/connect-remote-servers.md)
   - Fetched 2026-06-02. Covers remote MCP Custom Connectors in Claude.ai.

4. **MCP Official Docs — Authorization Tutorial** (https://modelcontextprotocol.io/docs/tutorials/security/authorization.md)
   - Fetched 2026-06-02. Detailed OAuth 2.1 flow for HTTP-transport MCP servers.

5. **OpenCode Docs — MCP Servers** (https://opencode.ai/docs/mcp-servers/)
   - Fetched 2026-06-02. OpenCode's `opencode.jsonc` MCP configuration.

6. **OpenAI Agents Python SDK — MCP** (https://github.com/openai/openai-agents-python/blob/main/docs/mcp.md)
   - Fetched 2026-06-02. Python SDK's programmatic MCP configuration.

7. **MCP Registry — About** (https://modelcontextprotocol.io/registry/about.md)
   - Fetched 2026-06-02. Central registry for MCP server discovery.

8. **MCP Docs — Understanding MCP Clients** (https://modelcontextprotocol.io/docs/learn/client-concepts.md)
   - Fetched 2026-06-02. Client features: elicitation, roots, sampling.

---

## Key Findings

### 1. MCP Transport Types (Spec-Level)

The MCP specification (as of 2025-11-25) defines two standard transports:

**stdio**
- Client launches server as a subprocess.
- Communication via `stdin`/`stdout` using newline-delimited JSON-RPC.
- Server logs go to `stderr`; client may capture or ignore.
- Used exclusively for local/process-level servers.
- Clients SHOULD support stdio whenever possible.

**Streamable HTTP** (replaces deprecated HTTP+SSE from 2024-11-05)
- Server is an independent process, handles multiple clients.
- Transport uses HTTP POST (client-to-server) and HTTP GET (server-to-client via SSE).
- Single MCP endpoint (e.g., `https://example.com/mcp`) handles both POST and GET.
- Client MUST include `Accept: application/json, text/event-stream` on POST.
- Client MUST include `MCP-Protocol-Version: <version>` header on all requests.
- Session management via `Mcp-Session-Id` header.
- Resumability via SSE `id` fields and `Last-Event-ID` header.
- Security: servers MUST validate `Origin` header; SHOULD bind localhost only for local servers.

**Legacy HTTP+SSE** (deprecated, protocol version 2024-11-05)
- Separate SSE and POST endpoints.
- Clients wanting backward compat should try POST first, fall back to GET for SSE.

**Custom transports** are allowed; must preserve JSON-RPC format.

WebSocket is NOT a standard MCP transport per the spec.

---

### 2. Claude Code — MCP Configuration

**Config file locations and scope hierarchy:**

Claude Code uses a layered config system with three scopes:

| Scope | File path | Purpose |
|---|---|---|
| User (global) | `~/.claude/settings.json` | Personal MCP servers across all projects |
| Project (shared) | `.mcp.json` at project root | Team-shared servers committed to repo |
| Local (override) | `.claude/settings.local.json` | Machine-local overrides, gitignored |

Claude Desktop (separate from Claude Code) uses:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

**Config format (stdio server example from official docs):**

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/Users/username/Desktop",
        "/Users/username/Downloads"
      ]
    }
  }
}
```

With environment variable injection (documented in troubleshooting):

```json
{
  "brave-search": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "env": {
      "BRAVE_API_KEY": "your-api-key-here"
    }
  }
}
```

**Transport types:**
- `command` + `args` → stdio transport (subprocess invocation)
- URL-based → HTTP/Streamable HTTP (for remote MCP Custom Connectors on claude.ai)

**Runtime invocation:**
- On startup, Claude Desktop/Code reads config and launches each stdio server as a subprocess.
- Subprocess lifetime is tied to the client session.
- Logs: `~/Library/Logs/Claude/mcp.log` (general), `mcp-server-SERVERNAME.log` (per-server stderr).

**Auth mechanisms:**
- stdio: Environment variables injected via `"env"` object in config. Credentials stay local.
- HTTP/remote (Claude.ai Custom Connectors): OAuth flow — user completes browser-based auth when adding connector. Claude.ai triggers OAuth redirect for consent.

**Permission/approval model:**
- Claude Desktop shows an approval prompt before executing any tool/file operation.
- User must explicitly approve each action.
- Tool calls listed in UI before execution.
- Remote (claude.ai): tool permissions configurable per connector — can enable/disable individual tools.

---

### 3. OpenCode — MCP Configuration

**Config file:** `opencode.json` or `opencode.jsonc` (JSONC allows comments) at project root or user config directory. Config key is `"mcp"`.

**Config format:**

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "my-local-server": {
      "type": "local",
      "command": ["npx", "-y", "my-mcp-package"],
      "environment": {
        "MY_API_KEY": "secret-value"
      },
      "enabled": true,
      "timeout": 10000
    },
    "my-remote-server": {
      "type": "remote",
      "url": "https://my-mcp-server.com",
      "headers": {
        "Authorization": "Bearer {env:MY_TOKEN}"
      },
      "oauth": false,
      "enabled": true,
      "timeout": 5000
    },
    "my-oauth-server": {
      "type": "remote",
      "url": "https://oauth-mcp-server.com",
      "oauth": {
        "clientId": "my-client-id",
        "clientSecret": "{env:CLIENT_SECRET}",
        "scope": "read write"
      }
    }
  }
}
```

**Key config fields:**

| Field | Type | Description |
|---|---|---|
| `type` | `"local"` or `"remote"` | Determines transport |
| `command` | Array | For local: command + args to launch server subprocess (stdio) |
| `environment` | Object | Env vars injected into local subprocess |
| `url` | String | For remote: HTTP endpoint URL |
| `headers` | Object | HTTP headers for remote requests |
| `oauth` | Object or `false` | OAuth config; `false` disables auto-OAuth |
| `oauth.clientId` | String | Pre-registered client ID |
| `oauth.clientSecret` | String | Client secret (supports `{env:VAR}` interpolation) |
| `oauth.scope` | String | OAuth scopes |
| `enabled` | Boolean | Enable/disable on startup |
| `timeout` | Number | Tool fetch timeout in ms (default: 5000) |

**Transport types:**
- `type: "local"` → stdio (subprocess)
- `type: "remote"` → Streamable HTTP

**Auth mechanisms:**
- Local servers: env var injection via `environment` object.
- Remote with API key: `oauth: false` + `headers` with `Authorization: Bearer {env:TOKEN}`.
- Remote with OAuth: Auto-detected via 401 response; uses Dynamic Client Registration (RFC 7591). Client prompts user via browser.
- Pre-registered OAuth: Supply `clientId`, `clientSecret`, `scope` in `oauth` object.
- Token storage: `~/.local/share/opencode/mcp-auth.json`.

**CLI commands:**
- `opencode mcp auth <server-name>` — initiate authentication
- `opencode mcp logout <server-name>` — clear stored credentials

**Permission model:**
- Global disable via `tools` config with exact names or glob patterns (e.g., `"my-mcp*"`).
- Per-agent re-enable in agent-specific tool configurations.

**Env var interpolation syntax:** `"{env:VARIABLE_NAME}"` in any string field (headers, OAuth settings, URLs).

---

### 4. OpenAI Agents Python SDK — MCP Configuration

This covers the `openai-agents-python` SDK, which is the closest equivalent to "OpenAI Codex" for MCP (the original Codex CLI does not natively support MCP).

**No static config file** — configuration is programmatic (Python code):

```python
from agents import Agent
from agents.mcp import MCPServerStdio, MCPServerHTTP, MCPServerStreamableHTTP

# Stdio server
stdio_server = MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path"],
    env={"MY_API_KEY": "value"},
)

# HTTP server (deprecated SSE transport)
http_server = MCPServerHTTP(
    url="https://my-mcp-server.com/sse",
    headers={"Authorization": f"Bearer {token}"},
)

# Streamable HTTP server
streamable_server = MCPServerStreamableHTTP(
    url="https://my-mcp-server.com/mcp",
    headers={"Authorization": f"Bearer {token}"},
)

# Register with agent
agent = Agent(
    name="Assistant",
    mcp_servers=[stdio_server, http_server, streamable_server],
    mcp_config={
        "convert_schemas_to_strict": True,
        "failure_error_function": None,
        "include_server_in_tool_names": True,
    }
)
```

**Hosted MCP Tools (Responses API):**
```python
from openai import OpenAI

client = OpenAI()
response = client.responses.create(
    model="gpt-4o",
    tools=[{
        "type": "mcp",
        "server_label": "my-server",
        "server_url": "https://my-mcp-server.com/mcp",
        "headers": {"Authorization": f"Bearer {token}"},
    }],
    input="Use the tools to complete this task",
)
```

**Transport types:**
1. Hosted MCP Tools — invoked by OpenAI's infrastructure via Responses API (no local subprocess)
2. Streamable HTTP — developer-managed; local or remote
3. HTTP+SSE — deprecated; legacy server support only
4. stdio — local subprocess via stdin/stdout

**Auth mechanisms:**
- stdio: environment variables via `env` parameter.
- HTTP: Bearer token in `headers` dict: `{"Authorization": f"Bearer {token}"}`.
- Connectors: OpenAI connector integration via `connector_id` + access tokens (for services like Google Calendar).
- Custom metadata: Per-call `_meta` payloads via `tool_meta_resolver` (for tenant IDs, trace context).

**Runtime invocation:**
- Local (stdio/HTTP): SDK calls `list_tools()` at each agent run, then `call_tool()` with results returned to model.
- Hosted: Model invokes tools directly; SDK forwards server labels to Responses API.

**Approval/permission model:**
- Global policy: `"always"` (always prompt) or `"never"` (never prompt).
- Per-tool policies: dict mapping tool names to `"always"` or `"never"`.
- Custom callbacks: sync/async functions receiving `MCPToolApprovalRequest`, returning approval decision.

```python
agent = Agent(
    name="Assistant",
    mcp_servers=[server],
    # Tool-level approval
    mcp_tool_approval={
        "delete_file": "always",   # always prompt
        "read_file": "never",      # auto-approve
    }
)
```

---

### 5. MCP Authorization — OAuth 2.1 Standard Flow (HTTP transport)

Applies to all HTTP-based MCP servers (remote); stdio uses env-var credentials instead.

**Flow:**
1. Client connects to server; server responds `401 Unauthorized` with `WWW-Authenticate: Bearer realm="mcp", resource_metadata=<URL>`.
2. Client fetches Protected Resource Metadata (PRM) document from `/.well-known/oauth-protected-resource`.
3. Client discovers Authorization Server metadata from OIDC Discovery or RFC 8414 endpoint.
4. Client registers (pre-registered or Dynamic Client Registration per RFC 7591).
5. User authorizes via browser (OAuth 2.1 authorization code + PKCE).
6. Client exchanges code for access + refresh tokens.
7. Client sends requests with `Authorization: Bearer <token>` header.
8. Server validates token (introspection or JWT verification); checks `aud` claim matches server URL.

**Standards relied on:**
- OAuth 2.1 (draft-ietf-oauth-v2-1-13)
- RFC 8414 — Authorization Server Metadata
- RFC 7591 — Dynamic Client Registration
- RFC 9728 — Protected Resource Metadata
- RFC 8707 — Resource Indicators
- PKCE (RFC 7636)

**For stdio:** OAuth flows are NOT used. Env-var credentials or embedded library credentials are the pattern. OAuth is designed for HTTP-transport remote servers.

---

### 6. MCP Registry — Server Discovery

- Official central registry at https://modelcontextprotocol.io/registry (preview as of 2026).
- Backed by Anthropic, GitHub, PulseMCP, Microsoft.
- Servers published as `server.json` metadata pointing to npm/PyPI/Docker packages.
- Server names use reverse-DNS format: `io.github.user/server-name`.
- Namespace authentication via GitHub account or DNS verification.
- NOT consumed directly by host apps; consumed by downstream aggregators/marketplaces.
- Aggregators expose a REST API conforming to the MCP Registry OpenAPI spec.
- Private servers are NOT supported by the public registry.

---

## Conflicts and Gaps

**Conflicts:**
- The MCP spec defines "Streamable HTTP" as the current standard, replacing "HTTP+SSE". OpenAI Agents Python SDK still exposes `MCPServerHTTP` for the deprecated SSE transport alongside `MCPServerStreamableHTTP`. This indicates patchy migration in client implementations.
- Claude Code's `.mcp.json` format uses `"mcpServers"` as the top-level key; OpenCode uses `"mcp"`. No single standard config file name or key.

**Gaps:**
- Claude Code's `settings.json` MCP config format was not directly accessible from Anthropic docs (WebFetch permission denied). The `"mcpServers"` + `"command"/"args"/"env"` structure is inferred from Claude Desktop docs.
- OpenAI Codex CLI (the CLI tool, not the Agents SDK) MCP support status is unclear — the README does not mention MCP at all as of 2026-06-02.
- No information found on Claude Code's `.mcp.json` project-scope format vs. `settings.json` user-scope format structural differences.
- OpenCode's permission/approval model for individual tool calls within an MCP server is not clearly documented (vs. server-level enable/disable).
- The MCP Registry is in preview; production availability and client adoption are uncertain.

**Recency:**
- MCP spec version 2025-11-25 is the current latest; Streamable HTTP transport replaces 2024-11-05 HTTP+SSE.
- MCP spec version 2025-06-18 was also referenced in some pages, indicating rapid versioning.
- OpenCode documentation accessed 2026-06-02 is current.
- OpenAI Agents Python SDK MCP docs accessed 2026-06-02 are current.

---

## Analysis

1. **Config file fragmentation is a real problem.** Three tools use three different config file names and top-level keys: Claude Desktop/Code uses `claude_desktop_config.json` or `settings.json` / `.mcp.json` with `"mcpServers"`, OpenCode uses `opencode.jsonc` with `"mcp"`, and OpenAI Agents uses pure Python code. No universal standard config schema exists, though the MCP Registry's `server.json` format is an attempt to standardize server *metadata* (not client config).

2. **Stdio dominates for local servers; HTTP is the future for remote.** All three implementations treat stdio as the default local transport and HTTP (Streamable HTTP) as the remote transport. The old HTTP+SSE is officially deprecated. WebSocket is absent from the spec and all client implementations.

3. **Auth is transport-tied, not protocol-tied.** Stdio servers authenticate via environment variables injected at subprocess launch — simple, secure for local use. HTTP servers use OAuth 2.1 or static Bearer tokens in headers. The spec explicitly recommends env-var credentials for stdio and OAuth for HTTP-transport servers, cleanly separating the two patterns.

4. **Permission/approval models vary significantly by tool.** Claude Desktop shows per-action approval prompts (user sees each filesystem operation before it runs). OpenAI Agents Python SDK offers programmatic per-tool approval policies (`"always"/"never"` + callbacks). OpenCode operates at the server-level enable/disable granularity. This signals no cross-client consistency on human-in-the-loop design.

5. **The MCP Registry ecosystem is still nascent.** The registry is in preview, is not meant to be consumed directly by host apps, and lacks private server support. This means most MCP server registration today is manual config-file editing by developers, not automated discovery and installation — a significant UX gap that limits adoption for less technical users.
