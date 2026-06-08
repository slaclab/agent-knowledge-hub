# TODO #023 — MCP Server Registry: Rich Metadata, Autodiscovery, and GUI Registration Flow

> **Priority:** 🟡 P2 — Medium
> **Status:** 🔍 Reviewed
> **Branch:** —
> **PR:** —
> **Created:** 2026-06-02
> **Shipped:** —
> **Depends on:** #019 (plugin.json scan pipeline — `has_mcp_server` bool already stored)

---

## Problem Statement

When a skill declares MCP servers in `plugin.json`, the catalog stores only a boolean (`has_mcp_server: true`). The actual server list — names, commands, auth requirements, environment variables, access restrictions — is discarded at scan time. Users see an "MCP" badge on the skill card but have no way to know what credentials, network access, or configuration they need before installing.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Skill declares `"mcp-servers": [{...}]` | Only `has_mcp_server: true` stored; rest discarded | Full server list stored: name, command, args, auth type, access level, env vars |
| User views a skill with an MCP badge | No detail — just a badge | Detail page shows each server: auth type, SLAC-internal flag, required env vars, copy-pasteable install snippet |
| Skill uses `uvx mcp-server-epics` | No inference | Auto-detected as SLAC EPICS service; auth + access pre-filled |
| Author submits a skill | Must manually declare every auth field | Autodiscovery pre-fills auth/access metadata from command, args, and well-known probes; author confirms or adjusts |
| Admin knows a server is SLAC-restricted | No override path | Admin can curate/correct auth and access metadata post-registration |

---

## Goals

1. Store the full MCP server list per skill: name, transport, command, args, env var requirements, auth type, access level
2. Autodiscover auth and access metadata with minimal user intervention — pre-fill from command/args inference, SLAC service registry, and well-known URL probes; present as editable defaults on the submission form
3. Surface MCP server details on the skill detail page: one card per server with auth type, access level, required env vars, and a copy-pasteable `claude mcp add` snippet
4. Allow catalog admins to curate/override MCP server metadata after registration
5. Keep the skill card badge as-is; enrich the detail page only

## Non-Goals

- Running `claude mcp add` from the browser (user must run it locally; we generate the command)
- Storing or proxying credentials
- Supporting non-Claude-Code MCP clients in this todo
- Full OAuth2 callback flow (auth type is informational, not interactive)
- Live health-checking or uptime monitoring of MCP servers

---

## Design

### plugin.json extended schema

Authors declare MCP servers in `plugin.json["mcp-servers"]` as an array of objects:

```json
{
  "mcp-servers": [
    {
      "name": "epics-archiver",
      "transport": "stdio",
      "command": "uvx",
      "args": ["mcp-server-epics", "--url", "${ARCHIVER_URL}"],
      "env": {
        "ARCHIVER_URL": {
          "description": "Archiver appliance base URL",
          "required": true,
          "example": "https://archiver.slac.stanford.edu"
        },
        "ARCHIVER_TOKEN": {
          "description": "Bearer token for Archiver API",
          "required": false
        }
      },
      "auth": {
        "type": "bearer",
        "description": "Obtain a token from the SLAC IAM portal"
      },
      "access": {
        "level": "slac-internal",
        "description": "Requires SLAC network or VPN",
        "service": "epics-archiver"
      }
    }
  ]
}
```

**Field glossary:**

| Field | Type | Values | Notes |
|---|---|---|---|
| `name` | string | — | Unique within the plugin; used as the `claude mcp add <name>` identifier |
| `transport` | string | `stdio`, `http`, `sse` | Defaults to `stdio` if absent |
| `command` | string | — | Executable, e.g. `uvx`, `npx`, `python` |
| `args` | string[] | — | CLI args; `${ENV_VAR}` references mark env substitutions |
| `env` | object | — | Map of env var name → `{description, required, example}` |
| `auth.type` | string | `none`, `bearer`, `api-key`, `slac-sso`, `oauth2` | |
| `auth.description` | string | — | Human-readable instructions for obtaining credentials |
| `access.level` | string | `public`, `slac-internal`, `slac-group`, `restricted` | |
| `access.description` | string | — | Where to request access |
| `access.service` | string | — | Canonical SLAC service name (matched against internal registry) |
| `url` | string | — | For `http`/`sse` transport — base URL of the server |

### Autodiscovery pipeline

At scan time, for each entry in `mcp-servers`, run three inference passes in order. Later passes fill gaps left by earlier ones; they never overwrite an explicit author declaration.

**Pass 1 — Command/args inference**

Match `command` + `args[0]` against a built-in pattern table:

| Pattern | Inferred fields |
|---|---|
| `uvx mcp-server-epics` | `access.level=slac-internal`, `access.service=epics-archiver`, `auth.type=bearer` |
| `uvx mcp-server-loki` | `access.level=slac-internal`, `access.service=loki`, `auth.type=bearer` |
| `uvx mcp-server-kafka` | `access.level=slac-internal`, `access.service=kafka`, `auth.type=api-key` |
| `npx @modelcontextprotocol/server-*` | `access.level=public`, `auth.type=none` |
| Any `${*_TOKEN}` or `${*_KEY}` in args | `auth.type=bearer` or `auth.type=api-key` respectively |

Pattern table lives in `backend/app/services/mcp_inference.py` as a plain dict — easy to extend without a schema migration.

**Pass 2 — SLAC service registry lookup**

If `access.service` was set (by author or Pass 1), look it up in an internal registry (`backend/app/data/slac_mcp_services.json`):

```json
{
  "epics-archiver": {
    "display_name": "EPICS Archiver Appliance",
    "access_level": "slac-internal",
    "auth_type": "bearer",
    "auth_instructions": "Request a token at https://iam.slac.stanford.edu",
    "network_requirement": "SLAC network or VPN",
    "contact": "controls@slac.stanford.edu"
  },
  "loki": { ... },
  "kafka": { ... }
}
```

Admin-curated file, committed to the repo. Fills `auth` and `access` fields if not already set by author.

**Pass 1 fallback description:** For entries where Pass 1 inferred `access.service` but Pass 2 found no matching registry entry, set a fallback `access.description`: *"Contact the skill author or your facility IT team for access."* This ensures the card always has an action path even for unlisted services.

**Pass 3 — Well-known URL probe**

For `http`/`sse` transport servers with a declared `url`, attempt `GET <url>/.well-known/mcp-server.json` at scan time (5s timeout, 1 retry). If it returns a valid JSON object with `auth` or `access` fields, merge them in.

This is best-effort: 404 or timeout is silently ignored; result is never cached beyond the current scan.

### Submission form pre-fill

When a user submits a skill (or refetches), the scan snapshot includes `mcp_servers` — the full array after autodiscovery. The submit preview form (currently shows labels, agent count, etc.) gains a new **MCP Servers** section:

- One collapsible row per server
- Editable fields: auth type (dropdown), access level (dropdown), description text areas
- Env vars shown as a table with required/optional toggle and description field
- User can accept autodiscovered defaults or correct them before confirming submission

This mirrors the existing label pre-fill UX: system proposes, user confirms or adjusts.

**Default expansion rule:** MCP server rows in the submission form start **expanded** when autodiscovery filled any auth or access field (i.e., `auth.type != "none"` or `access.level != "public"`). Rows start collapsed only when the author explicitly declared all fields in `plugin.json` and autodiscovery added nothing. When a row is collapsed but contains MCP metadata, the card header row displays a `"Review MCP settings"` indicator to signal the section requires attention.

### Storage

**`Skill` model** — replace `has_mcp_server: bool` with `mcp_servers: List[MCPServerInfo]`. `has_mcp_server` becomes a computed property (`len(mcp_servers) > 0`) for backwards compatibility.

New embedded model:

```python
class MCPServerEnvVar(BaseModel):
    description: Optional[str] = None
    required: bool = False
    example: Optional[str] = None

class MCPServerAuth(BaseModel):
    # Optional so autodiscovery can distinguish "author declared" from "absent"
    type: Optional[Literal["none", "bearer", "api-key", "slac-sso", "oauth2"]] = None
    description: Optional[str] = Field(None, max_length=500)

class MCPServerAccess(BaseModel):
    # Optional so autodiscovery can distinguish "author declared" from "absent"
    level: Optional[Literal["public", "slac-internal", "slac-group", "restricted"]] = None
    description: Optional[str] = Field(None, max_length=500)
    service: Optional[str] = None   # canonical SLAC service name

class MCPServerInfo(BaseModel):
    # name used as URL path param and MongoDB arrayFilter key — constrain strictly
    name: str = Field(..., pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    transport: Literal["stdio", "http", "sse"] = "stdio"
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    # url must be https:// and validated for SSRF at probe time
    url: Optional[str] = None
    # env var keys validated as [A-Z0-9_]+ to prevent MongoDB key injection
    env: Dict[str, MCPServerEnvVar] = Field(default_factory=dict)
    auth: Optional[MCPServerAuth] = None    # None = not declared; post-merge defaults to MCPServerAuth(type="none")
    access: Optional[MCPServerAccess] = None  # None = not declared; post-merge defaults to MCPServerAccess(level="public")
    admin_notes: Optional[str] = Field(None, max_length=1000)
    admin_override: bool = False  # True = autodiscovery must not overwrite on refetch
```

**Autodiscovery merge rule for `auth` / `access`:** After all passes, if `auth` is still `None`, default to `MCPServerAuth(type="none")`; if `access` is still `None`, default to `MCPServerAccess(level="public")`. This ensures the stored document always has populated auth/access fields while keeping `None` as the sentinel during merge.

**Env var key validation:** In `_parse_plugin_json()`, drop any env key that does not match `^[A-Z][A-Z0-9_]*$` and log a warning. This prevents MongoDB operator injection via keys like `$set`.

**`admin_override` flag:** When `admin_override=True` on a server entry, `refetch()` and `scan()` must not overwrite `auth`, `access`, or `admin_notes` from the autodiscovery pipeline. Checked in the merge step.

Stored as an embedded array in the `Skill` document (MongoDB). No separate collection needed.

**Migration:** Existing skills with `has_mcp_server: true` get `mcp_servers = []` (empty list) — they retain the badge and will be populated on next refetch.

### API

`SkillOut` and `SkillListOut` gain `mcp_servers: List[MCPServerInfo]`. `has_mcp_server` retained as a computed field for list views (no breaking change to existing consumers).

New admin endpoint: `PATCH /skills/{slug}/mcp-servers/{server_name}` — allows curators to update `auth`, `access`, and `admin_notes` on a specific server entry post-registration.

### GUI — skill detail page

New **MCP Servers** section on the detail page, rendered below the existing platform/component metadata row. One card per server:

```
┌─────────────────────────────────────────────────────────┐
│  epics-archiver                         slac-internal   │
│  EPICS Archiver Appliance                               │
│                                                         │
│  Auth: Bearer token                                     │
│  Obtain at https://iam.slac.stanford.edu                │
│                                                         │
│  Network: SLAC network or VPN required                  │
│                                                         │
│  Environment variables:                                 │
│    ARCHIVER_URL  (required)  Archiver appliance URL     │
│    ARCHIVER_TOKEN            Bearer token               │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ claude mcp add epics-archiver uvx mcp-server-... │   │
│  │                                              📋  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

The `claude mcp add` snippet is generated from `name`, `transport`, `command`, `args`, substituting `${ENV_VAR}` placeholders literally (user fills them in). Copy button copies to clipboard.

**Skill card** — no change. The existing MCP badge remains; the detail page carries the detail.

**Empty-state (migration period):** When `has_mcp_server=true` AND `mcp_servers=[]`, render the MCP Servers section with an informational notice: *"MCP server metadata will populate on next sync. Check the skill's [plugin.json in the repository](#) for configuration details."* (Link to `repo_url`.) This covers the window between schema migration and the first rescan.

**Snippet copy box:** Render a note below every snippet: *"Run in terminal. Replace `${…}` placeholders with your actual values before running."* Plain text, always visible — not a tooltip.

**Same-page anchor:** Assign `id="mcp-servers"` to the MCP Servers section container. Change the "MCP server" badge in the Components row of `page.tsx` from a `<span>` to an `<a href="#mcp-servers">` so users can jump directly from the badge to the section.

**Display strings for auth/access:** Map raw enum values to human-readable text in `mcp-server-card.tsx`:

| `auth.type` | Display |
|---|---|
| `none` | No authentication required |
| `bearer` | Bearer token (a password-like API credential) |
| `api-key` | API key |
| `slac-sso` | SLAC SSO (your SLAC login) |
| `oauth2` | OAuth 2.0 |

| `access.level` | Badge text |
|---|---|
| `public` | (omit badge — no restriction to announce) |
| `slac-internal` | SLAC network required |
| `slac-group` | SLAC group access required |
| `restricted` | Restricted access |

**Null fields:** If `auth.description` is null, omit the "Obtain at" line. If `access.description` is null, render only the access badge without a detail line. Never render empty `<p>` or `<dd>` elements.

**Section placement:** Place `<MCPServersSection>` in the **main content column** (`lg:col-span-2`) below `<SkillContentTabs>`, not in the sidebar. Env var tables and snippet boxes require full-column width; the 1/3-width sidebar will cause overflow on normal screens for skills with 2+ servers.

**Micro-copy above snippet:** Add one line above the copy box: *"Run this command in your terminal to register the server with Claude Code."*

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `backend/app/services/mcp_inference.py` | New | Pass 1 command/args inference; pattern table; merge logic (fills only `None` fields); returns updated `List[MCPServerInfo]` |
| `backend/app/data/slac_mcp_services.json` | New | Curated SLAC service registry; Pass 2 lookup |
| `backend/app/services/mcp_probe.py` | New | Pass 3 well-known URL probe; async fetch with SSRF guard (https-only, RFC-1918 block); 5s timeout; returns partial fields or `None` |
| `backend/app/services/github.py` — `_parse_plugin_json()` | Modify | Parse full `mcp-servers` array; run Pass 1 + Pass 2 (sync); **does not run Pass 3** — returns `List[MCPServerInfo]` with auth/access still `None` where absent |
| `backend/app/services/github.py` — `github_scanner.scan()` | Modify | Add `async` call to `mcp_probe.enrich(servers)` after `_parse_plugin_json()` returns (Pass 3 runs here in async context) |
| `backend/app/services/skill.py` — `create()` / `refetch()` | Modify | Update `auto_labels` check from `plugin_meta.get("has_mcp_server")` to `len(plugin_meta.get("mcp_servers", [])) > 0`; pass `mcp_servers` to `Skill` constructor |
| `backend/app/models/skill.py` | Modify | Replace `has_mcp_server: bool` field with `mcp_servers: List[MCPServerInfo]`; add bare `@property has_mcp_server` returning `len > 0`; update `getattr` call sites |
| `backend/app/schemas/skill.py` — `SkillOut`/`SkillListOut`/`SkillScanSnapshotOut` | Modify | Expose `mcp_servers: List[MCPServerInfo]`; retain `has_mcp_server: bool` as explicitly-passed field (same pattern as `update_available`) |
| `backend/app/routers/admin.py` | Modify | Add `PATCH /skills/{slug}/mcp-servers/{name}` endpoint here (not `skills.py`) — guarded by router-level `require_admin` dependency; uses raw Motor `arrayFilters` to update a single embedded server |
| `backend/app/services/github.py` — `SkillScanSnapshot` dataclass | Modify | Add `mcp_servers: list[MCPServerInfo]` field alongside `has_mcp_server` |
| `frontend/components/mcp-server-card.tsx` | New | Single server card: auth, access, env vars, copy-paste snippet; display-string maps; ${ENV_VAR} note |
| `frontend/components/mcp-servers-section.tsx` | New | Section wrapper; maps over `skill.mcp_servers`; empty-state for migration period; `id="mcp-servers"` anchor |
| `frontend/app/skills/[slug]/page.tsx` | Modify | Add `<MCPServersSection>` in **main content column** (not sidebar); change Components MCP badge to `<a href="#mcp-servers">` |
| `frontend/components/skill-submit-preview.tsx` (or equivalent) | Modify | Add MCP server pre-fill section to submission form; rows default expanded when autodiscovery filled auth/access |

---

## ADRs

### ADR-U32: Embed MCP server list in `Skill` document rather than a separate collection

**Status:** Accepted

**Context:** MCP server metadata is always read alongside skill metadata — never independently. A separate collection would require joins on every skill fetch.

**Decision:** Embed `mcp_servers: List[MCPServerInfo]` directly in the `Skill` document (MongoDB embedded array). Admin overrides are stored as fields within each `MCPServerInfo` object.

**Consequences:** No separate collection or foreign-key joins. Server-level updates require a targeted `$set` on the array element by `name`. Array size is bounded (< 20 servers per plugin in practice), so document size is not a concern.

---

### ADR-U33: Autodiscovery fills gaps; never overwrites explicit author declarations

**Status:** Accepted

**Context:** Author declarations in `plugin.json` are the ground truth for their own server. Autodiscovery should help authors who don't know what to declare, not silently override accurate metadata.

**Decision:** Three-pass merge: author fields first, then Pass 1 (command inference), then Pass 2 (SLAC registry), then Pass 3 (well-known probe). Each pass only fills fields that are still absent.

**Consequences:** Authors who declare auth/access get exactly what they declared. Authors who omit those fields get the best available inference. Admin overrides (stored in `admin_notes` and applied in the API response layer) take highest precedence.

---

### ADR-U35: SLAC service registry as a committed JSON file, not a database table

**Status:** Accepted

**Context:** The registry of known SLAC services and their auth requirements changes infrequently (new services onboarded a few times a year). A DB table would require a migration and admin UI for what is effectively config.

**Decision:** `backend/app/data/slac_mcp_services.json` — a plain JSON file committed to the repo. Changes go through PR review. Loaded at startup (or per-scan; it's small).

**Consequences:** Adding a new SLAC service requires a code PR, not an admin UI action. Acceptable given change frequency. If the registry grows to > 50 entries or needs user-facing editing, migrate to a DB table at that point.

---

### ADR-U36: Well-known URL probe is best-effort, never blocks registration

**Status:** Accepted

**Context:** Not all MCP servers expose a well-known endpoint, and probing at scan time adds latency. A probe failure must not prevent skill registration. The `/.well-known/mcp-server.json` path is a **local convention for this project**, not a ratified MCP specification (the MCP spec uses `/.well-known/oauth-protected-resource` per RFC9728 for OAuth metadata only). The probe is therefore inherently best-effort.

**Decision:** Pass 3 runs with a 5s timeout. Any non-200 response or exception is silently ignored; the server entry is registered with whatever Pass 1 and Pass 2 populated. Probe results are not cached or retried outside of a manual refetch.

**SSRF mitigation (required):** `mcp_probe.py` must validate the `url` field before connecting: (1) scheme must be `https://`; (2) resolve the hostname to an IP and reject RFC 1918 ranges (10.x, 172.16–31.x, 192.168.x), loopback (127.x), and link-local (169.254.x). This is distinct from `github_fetcher`'s URL validation, which only validates `github.com` URLs. The ADR-004 claim "mitigated by github_fetcher URL validation" was incorrect and is removed.

**Consequences:** HTTP servers that do expose well-known metadata benefit automatically. Stdio servers (the majority) are unaffected. No dependency on external availability for registration success. SSRF to internal SLAC network services is prevented.

---

### ADR-U37: `has_mcp_server` retained as bare `@property`, not stored field, not `@computed_field`

**Status:** Accepted

**Context:** Existing API consumers (frontend skill card, installer skill) read `has_mcp_server`. Removing it would be a breaking change. Pydantic v2 bare `@property` is **not** included in `model_dump()`, so revision snapshots would silently omit it. The existing `update_available` property has the same exposure and is handled by explicit mapping at the router layer.

**Decision:** `has_mcp_server` becomes a bare `@property` on `Skill` returning `len(self.mcp_servers) > 0`. It is **not** a `@computed_field`. It is explicitly passed at the router layer in `_skill_to_out()` as `has_mcp_server=skill.has_mcp_server`, exactly as `update_available` is handled. It is not relied upon from `model_dump()`.

**Consequences:** Zero breaking changes to existing consumers. All `_skill_to_out()` call sites must pass `has_mcp_server` explicitly (4 sites in `routers/skills.py`, same pattern as `update_available`). Existing skills with `has_mcp_server=true` stored will continue to surface the badge from the stored field until the schema migration removes it, at which point skills with `mcp_servers=[]` will return `false` until refetched.

---

## Trade-offs

```
Choice: Embed MCPServerInfo in Skill document vs separate MCPServer collection
  + Embed: single fetch, simpler queries, no join
  - Embed: targeted array-element updates are more verbose ($set with arrayFilters)
  Decision: Embed. Server list is small and always fetched with the skill.

Choice: Autodiscovery at scan time vs on-demand at install time
  + Scan time: metadata in catalog before user even visits the page
  - Scan time: well-known probe adds latency to every refetch
  Decision: Scan time for Pass 1 + Pass 2 (fast, no I/O); Pass 3 (URL probe) also at scan
  time but with 5s timeout and best-effort semantics.

Choice: Pre-fill MCP metadata on submission form vs require author to fill manually
  + Pre-fill: minimal user friction; autodiscovered data is better than nothing
  - Pre-fill: user may not notice wrong defaults and submit incorrect metadata
  Decision: Pre-fill with clear "review and confirm" framing — same pattern as label pre-fill.

Choice: claude mcp add snippet in GUI vs leave to installer skill
  + GUI snippet: immediately useful; user can copy and run without installing AKH skill
  - GUI snippet: duplicates logic with installer skill; may drift
  Decision: Include snippet in GUI. It's a read-only rendering of name/command/args —
  no logic to maintain.
```

---

## Delivery Slices

**Slice 1 — Storage + scanner (Pass 1 + Pass 2)**
- `MCPServerInfo` model with `Optional[MCPServerAuth]`/`Optional[MCPServerAccess]` (merge sentinels); `name` regex validator; `transport`/`auth.type`/`access.level` as `Literal` enums; env key sanitisation
- `mcp_inference.py`: Pass 1 command/args patterns; merge logic (fills only `None` fields); `admin_override` flag respected
- `slac_mcp_services.json`: initial entries (EPICS, Loki, Kafka)
- `github.py._parse_plugin_json()`: parse full `mcp-servers` array; run Pass 1 + Pass 2 (sync only); return `List[MCPServerInfo]` with final auth/access defaults applied
- `github_scanner.scan()`: wire mcp_servers from metadata_extractor result; Pass 3 integrated here in Slice 2
- `skill.py`: update `auto_labels` MCP check; pass `mcp_servers` to `Skill` constructor
- `SkillOut`/`SkillListOut`/`SkillScanSnapshotOut`: expose `mcp_servers`; `has_mcp_server` explicitly mapped at router layer
- `SkillScanSnapshot` dataclass: add `mcp_servers` field

**Slice 2 — Well-known probe (Pass 3)**
- `mcp_probe.py`: async `enrich(servers)` function; SSRF guard (https-only + RFC-1918 IP block); 5s timeout; best-effort
- Integrate: call `await mcp_probe.enrich(servers)` inside `github_scanner.scan()` after `_parse_plugin_json()` (async context)
- Unit tests with mocked HTTP responses (respx)

**Slice 3 — GUI detail page**
- `mcp-server-card.tsx`: auth, access, env vars, copy-paste snippet
- `mcp-servers-section.tsx`: section wrapper
- Wire into skill detail page

**Slice 4 — Submission form pre-fill**
- Add MCP server pre-fill section to submit preview form
- Editable auth type, access level, env var descriptions

**Slice 5 — Admin override**
- `PATCH /skills/{slug}/mcp-servers/{name}` endpoint in `routers/admin.py` (not `skills.py`) — router-level `require_admin` guard; uses raw Motor `arrayFilters` to update a single embedded server element; sets `admin_override=True`
- Admin UI hook (minimal — can reuse existing edit form patterns)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Well-known URL probe hits internal SLAC services from scanner infra | Medium | Medium | Probe only for `http`/`sse` transport with explicit `url`; scanner runs inside SLAC network, so this is expected behaviour |
| SLAC service registry goes stale (service retired, auth changed) | Medium | Low | PR review gates changes; `admin_notes` override for urgent corrections without a full rescan |
| Author declares wrong auth type; users get confused | Medium | Medium | Admin override endpoint + submission form review step |
| Embedding large MCP server lists bloats `Skill` documents | Very Low | Low | Cap at 20 servers per plugin; warn at scan time if exceeded |
| `has_mcp_server` computed property returns false for old skills until refetch | Low | Low | Badge disappears temporarily; harmless until next scheduled refetch |
| `claude mcp add` snippet in GUI drifts from installer skill behaviour | Low | Low | Snippet is a static rendering of `name command args` — no logic to drift |

---

## Implementation Checklist

- [ ] Define `MCPServerInfo`, `MCPServerAuth`, `MCPServerAccess`, `MCPServerEnvVar` models
- [ ] Migrate `Skill.has_mcp_server: bool` → `Skill.mcp_servers: List[MCPServerInfo]` + computed property
- [ ] `mcp_inference.py`: Pass 1 pattern table + merge logic
- [ ] `slac_mcp_services.json`: seed with EPICS, Loki, Kafka entries
- [ ] `github.py._parse_plugin_json()`: parse full `mcp-servers` array; run Pass 1 + Pass 2
- [ ] `mcp_probe.py`: async well-known URL fetch, 5s timeout, best-effort
- [ ] `github.py`: integrate Pass 3 for http/sse transport entries
- [ ] `SkillOut`, `SkillListOut`, `SkillScanSnapshotOut`: expose `mcp_servers`; retain `has_mcp_server`
- [ ] `PATCH /skills/{slug}/mcp-servers/{name}` admin endpoint
- [ ] `mcp-server-card.tsx`: auth badge, access badge, env var table, copy-paste snippet
- [ ] `mcp-servers-section.tsx`: collapsible section wrapper
- [ ] Wire `MCPServersSection` into skill detail page
- [ ] Submission form: MCP server pre-fill section (auth, access, env vars editable)
- [ ] Submission form: MCP rows default expanded when autodiscovery filled auth/access; show "Review MCP settings" indicator on collapsed header rows
- [ ] `mcp-server-card.tsx`: use auth/access display-string maps; omit public access badge; never render empty description elements
- [ ] `mcp-server-card.tsx`: micro-copy above snippet ("Run in terminal…") and note below snippet ("Replace ${...} placeholders…")
- [ ] `mcp-servers-section.tsx`: empty state when `has_mcp_server=true` and `mcp_servers=[]`; assign `id="mcp-servers"` to wrapper
- [ ] Place `<MCPServersSection>` in main content column (`lg:col-span-2`), not sidebar
- [ ] `page.tsx`: change Components row "MCP server" badge from `<span>` to `<a href="#mcp-servers">`
- [ ] Inference pipeline: set fallback `access.description` for Pass-1-inferred entries with no Pass-2 registry match
- [ ] Tests: Pass 1 inference, Pass 2 registry lookup, Pass 3 probe (mocked), model migration, API schema
- [ ] Seed `slac_mcp_services.json` with all known SLAC MCP services before Slice 1 ships

---

## Test Plan

### Unit tests
- `mcp_inference.py`: each pattern row; missing command; env var key inference
- `mcp_probe.py`: 200 with valid JSON; 404; timeout; malformed JSON; non-http transport skipped
- `MCPServerInfo` model: serialisation round-trip; computed `has_mcp_server`

### Integration tests
- Scan a plugin.json with full `mcp-servers` array → `Skill` stores correct `mcp_servers` list
- Scan with no `mcp-servers` → `mcp_servers = []`, `has_mcp_server = false`
- Admin `PATCH` endpoint updates `auth.type` and `admin_notes`; subsequent `GET` reflects override

### Smoke tests (manual before DoD)

| # | Scenario | Expected |
|---|---|---|
| S1 | Install skill with `uvx mcp-server-epics` | Detail page shows SLAC-internal badge, bearer auth, ARCHIVER_URL env var |
| S2 | Skill with no auth fields in plugin.json, uvx command matched | Autodiscovered fields pre-filled; no author action needed |
| S3 | HTTP MCP server with `/.well-known/mcp-server.json` | Probe result merged into card display |
| S4 | HTTP MCP server, probe returns 404 | Card shows whatever Pass 1/2 provided; no error |
| S5 | Copy `claude mcp add` snippet | Clipboard contains correct command; `${ENV_VAR}` placeholders intact |
| S6 | Admin overrides `auth.type` via PATCH | Detail page shows updated auth type |
| S7 | Skill with 0 MCP servers | No MCP section rendered on detail page |

---

## Definition of Done

- [ ] Full `mcp-servers` array stored per skill (not just boolean)
- [ ] `MCPServerInfo.name` validated as `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$`; `transport`/`auth.type`/`access.level` as `Literal` enums; env var keys validated as `^[A-Z][A-Z0-9_]*$`
- [ ] `MCPServerAuth` / `MCPServerAccess` use `Optional` fields as merge sentinels; post-merge defaults applied correctly
- [ ] `admin_override: bool` flag prevents autodiscovery from overwriting curated fields on refetch
- [ ] Autodiscovery runs for every skill with MCP servers: Pass 1 (command inference, sync), Pass 2 (SLAC registry, sync), Pass 3 (URL probe, async in scanner)
- [ ] Pass 3 `mcp_probe.py` has SSRF guard: https-only scheme, RFC-1918 IP block
- [ ] `_parse_plugin_json()` is sync (Pass 1+2 only); Pass 3 called from async `github_scanner.scan()`
- [ ] `PATCH /skills/{slug}/mcp-servers/{name}` in `routers/admin.py`; uses raw Motor `arrayFilters`; sets `admin_override=True`
- [ ] `skill.py` auto_labels MCP check updated from `has_mcp_server` bool to `len(mcp_servers) > 0`
- [ ] `SkillScanSnapshot` dataclass gains `mcp_servers` field
- [ ] `has_mcp_server` is a bare `@property`; explicitly mapped at router layer in all `_skill_to_out()` call sites
- [ ] Submission form pre-fills MCP metadata from autodiscovery; rows default expanded when autodiscovery filled auth/access
- [ ] Skill detail page shows one card per MCP server in main content column (not sidebar): auth display string, access badge, env vars, copy-paste snippet with micro-copy, empty state for migration period
- [ ] MCP badge in Components row links to `#mcp-servers` anchor
- [ ] Admin can override auth/access metadata via PATCH endpoint; `admin_override=True` prevents overwrite on next refetch
- [ ] `has_mcp_server` backwards-compatible for all existing consumers (router layer explicit mapping)
- [ ] CHANGELOG entry added under `## Unreleased`
- [ ] ADR files written: `docs/adr/adr-u32-mcp-embed.md`, `docs/adr/adr-u33-autodiscovery-fills-gaps.md`, `docs/adr/adr-u35-slac-registry-json.md`, `docs/adr/adr-u36-well-known-probe.md`, `docs/adr/adr-u37-has-mcp-server-property.md`
- [ ] `docs/skill-file-discovery.md` storage table updated: `has_mcp_server` → computed property; autodiscovery pipeline modules listed
- [ ] `slac_mcp_services.json` schema documented in a comment block at the top of the file or in a companion `README` section
- [ ] All checklist items complete

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-04
**Rounds:** 1

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | YES | All factual claims confirmed; well-known probe not an MCP standard — noted in ADR-U36; has_mcp_server call-site map added to checklist |
| codebase-arch-review | ⚠️ WARN | YES | Admin PATCH moved to admin.py; Pass 3 scope clarified to scanner async context; name validator added; admin_override flag added; github_scan.py + SkillScanSnapshot added to module design |
| codebase-eng-review | ✅ PASS | NO | Three critical issues resolved in plan: async/sync split, arrayFilters/raw Motor, Optional auth/access sentinel; full test plan appended |
| doc-review | ⚠️ WARN | YES | ADR numbers corrected (U32/U33/U35/U36/U37); DoD updated with ADR files, skill-file-discovery.md update, CHANGELOG; slac_mcp_services.json schema note added |
| security-review | ✅ PASS | NO | CRITICAL SSRF resolved: ADR-U36 now mandates https-only + RFC-1918 IP block in mcp_probe.py; name/transport/auth/access as Literal types; env key validation; admin.py router-level guard |
| codebase-ux-review | ✅ PASS | NO | ${ENV_VAR} placeholder note added; migration empty-state added; form expansion rules added; display-string maps added; sidebar → main column; badge anchor link added |

**Accepted warnings:** Well-known probe path is a local convention, not an MCP standard (forward-looking; acknowledged in ADR-U36). Existing skills with has_mcp_server=true will lose badge until refetch (noted in risk register; migration via scheduled refetch).
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research — Round 1 (PASS WITH WARNINGS)</summary>

## Summary

Plan #023 adds rich MCP server metadata to the skill catalog. Core factual claims are correct — the boolean `has_mcp_server` field exists in all the right places, `_parse_plugin_json()` discards the mcp-servers array, and there are no pre-existing `mcp_servers` list fields anywhere. The well-known probe concept (Pass 3) is a **custom invention by this plan**, not a ratified MCP specification — the actual MCP spec defines `/.well-known/oauth-protected-resource` for OAuth2 authorization metadata (RFC9728), not a generic `/.well-known/mcp-server.json` endpoint for capability/auth/access discovery. This is the plan's key unverified claim and needs clarification. Everything else — storage, computed property migration, autodiscovery pipeline, API extension, cachetools availability — is well-founded against the codebase. The plan is approvable with two amendments; no blockers.

## Issues

- medium | well-known probe | `/.well-known/mcp-server.json` is not an MCP specification — it is a local convention invented by this plan
- medium | migration | has_mcp_server=true skills lose badge on computed property switchover until refetch
- medium | SkillOut construction | has_mcp_server @property must be explicitly unpacked at all router call sites (like update_available)
- low | PATCH endpoint | MongoDB array-element update approach not specified
- low | slac_mcp_services.json | backend/app/data/ directory does not exist yet
- low | SkillScanSnapshot dataclass | not listed in module design table

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-arch-review — Round 1 (PASS WITH WARNINGS)</summary>

## Summary

The plan is architecturally sound. Core decisions (embed in Skill document, three-pass pipeline, computed property, SLAC registry as JSON) are all approved. Four implementation issues required plan amendments; all resolved.

## Issues

- CRIT | model/serialization | has_mcp_server @property invisible to model_dump — resolved: bare @property explicitly mapped at router layer per update_available pattern
- HIGH | router/auth | Admin PATCH must be in admin.py (router-level require_admin guard) not skills.py
- HIGH | api/routing | server_name path param needs character-class constraint — resolved: name validator ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$ added
- HIGH | pipeline/async | Pass 3 cannot run inside sync _parse_plugin_json() — resolved: Pass 3 runs in async github_scanner.scan() after sync parse returns
- MED | migration | has_mcp_server=true skills silently return false until refetch — accepted, documented
- MED | api/schema | github_scan.py + SkillScanSnapshot missing from module design — added
- MED | data/admin | admin_notes reset on refetch without admin_override flag — resolved: admin_override: bool added
- LOW | storage | env var dict unbounded — cap at 50 keys recommended
- LOW | wiring | auto_labels MCP check reads has_mcp_server bool, must be updated to check mcp_servers

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 1 (PASS)</summary>

## Summary

Three critical issues resolved in plan amendments. Test plan appended covering all identified gaps.

## Issues

- CRIT-1 | async | Pass 3 probe cannot run inside sync method — resolved: separate async enrich step after sync parse
- CRIT-2 | arrayFilters | PATCH must use raw Motor, not Beanie save() — specified in plan
- HIGH-1 | merge logic | Default values mask explicit vs absent — resolved: Optional[MCPServerAuth]/Optional[MCPServerAccess] sentinels
- HIGH-2 | admin_notes | Override application point undefined — resolved: write override values directly to auth/access fields + admin_override flag
- HIGH-3 | has_mcp_server | Computed property breaks stored-field filter queries (no current uses; flagged for awareness)
- HIGH-4 | badge regression | Existing has_mcp_server=true skills lose badge until refetch — documented
- MED-1 | snippet generation | stdio vs http/sse format not specified; args with spaces need quoting
- MED-2 | command=None | Pass 1 behavior for missing command not defined
- MED-3 | slac_mcp_services.json | Load timing (startup vs per-scan) unspecified
- MED-5 | name uniqueness | Duplicate names in one plugin.json make arrayFilters ambiguous
- MED-6 | SkillScanSnapshotOut | needs mcp_servers for Slice 4 submission form

## Status
PASS

</details>

<details>
<summary>doc-review — Round 1 (PASS WITH WARNINGS)</summary>

## Summary

Six documentation gaps addressed; ADR numbering corrected (U34 taken by Atlas Search in catalog-api.md).

## Issues

- WARN | ADR numbering | Plan used ADR-001–005; correct project convention is adr-u32, u33, u35, u36, u37 (u34 taken)
- WARN | ADR files not in DoD | Five ADR files not listed as DoD requirements — added
- WARN | docs/skill-file-discovery.md | Storage table documents has_mcp_server as stored bool — will be stale
- WARN | docs/skill-file-discovery.md | Autodiscovery pipeline (mcp_inference, slac_mcp_services, mcp_probe) not documented
- WARN | PATCH endpoint undocumented | New admin override endpoint has no API doc coverage
- WARN | CHANGELOG entry missing from DoD | Every shipped feature has CHANGELOG — added to DoD
- INFO | slac_mcp_services.json | No schema or contributing guide — recommended

## Status
PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 1 (PASS)</summary>

## Summary

One critical (SSRF) and three high-severity issues; all addressed by plan amendments. No architectural changes needed — validators, Literal types, SSRF guard.

## Issues

- CRITICAL | ssrf | No SSRF protection on well-known URL probe — resolved: ADR-U36 mandates https-only + RFC-1918 IP block + port 443 only
- HIGH | MCPServerInfo.url | Stored with no scheme validation — resolved: url validated at probe time and optionally at storage
- HIGH | MCPServerInfo.name | No format constraint; used as URL path param + MongoDB arrayFilter key — resolved: ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$ validator
- HIGH | free-text fields | auth.description/access.description/admin_notes stored and displayed; XSS risk — resolved: max_length limits; frontend uses existing markdown renderer with DOMPurify
- MED | transport/auth.type/access.level | Open str types — resolved: Literal enums
- MED | env var keys | User-controlled MongoDB document keys — resolved: ^[A-Z][A-Z0-9_]*$ validation
- MED | admin PATCH | Inconsistent auth pattern — resolved: moved to admin.py with router-level require_admin
- MED | command field | User-controlled CLI snippet — soft concern; no execution risk from display
- LOW | SSRF via redirect | Redirect following can bypass IP check — recommend disabling redirect following in httpx for probe

## Status
PASS

</details>

<details>
<summary>codebase-ux-review — Round 1 (PASS)</summary>

## Summary

Design direction sound. Seven UX gaps identified and addressed in plan amendments. Slices 1–2 clear; Slice 3 should implement the amendments.

## Issues

- HIGH | F-01 | ${ENV_VAR} placeholders in snippet look like a complete command — resolved: note below snippet box
- HIGH | F-02 | Migration gap: badge shows but no MCP section renders — resolved: empty-state message added
- HIGH | F-03 | Submission form collapsed by default hides autodiscovered wrong metadata — resolved: expand when autodiscovery filled auth/access
- MED | F-04 | Jargon ("bearer token", "stdio transport") opaque to LCLS scientists — resolved: display-string maps added
- MED | F-05 | Sidebar too narrow for env var tables + snippet boxes — resolved: moved to main content column
- MED | F-06 | Null auth/access description rendering not specified — resolved: explicit null rules added
- MED | F-07 | MCP badge on Components row is a dead-end span — resolved: changed to anchor link #mcp-servers
- LOW | F-08 | No context that claude mcp add requires a terminal — resolved: micro-copy added
- LOW | F-09 | Raw enum values render as badge labels — resolved: display-string maps + public badge omitted
- LOW | F-10 | No fallback when Pass-2 registry has no entry — resolved: fallback access.description added

## Status
PASS

</details>

---

## Relationship to Other Tasks

- **#019 (plugin.json scan pipeline):** #019 introduced `has_mcp_server: bool`; this todo replaces it with a full `mcp_servers` list and autodiscovery pipeline.
- **#020 (installer skill extension):** The installer's `remove` flow runs `claude mcp remove <name>` for each server in `plugin.json["mcp-servers"]`. The richer schema defined here is the same format the installer reads.
- **#016 (bearer JWT auth):** If `auth.type=bearer` servers require SLAC SSO tokens, the token flow from #016 may be referenced in `auth.description`.
