# TODO #023 — MCP Server Registry: Rich Metadata, Autodiscovery, and GUI Registration Flow

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
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

### Storage

**`Skill` model** — replace `has_mcp_server: bool` with `mcp_servers: List[MCPServerInfo]`. `has_mcp_server` becomes a computed property (`len(mcp_servers) > 0`) for backwards compatibility.

New embedded model:

```python
class MCPServerEnvVar(BaseModel):
    description: Optional[str] = None
    required: bool = False
    example: Optional[str] = None

class MCPServerAuth(BaseModel):
    type: str = "none"   # none | bearer | api-key | slac-sso | oauth2
    description: Optional[str] = None

class MCPServerAccess(BaseModel):
    level: str = "public"   # public | slac-internal | slac-group | restricted
    description: Optional[str] = None
    service: Optional[str] = None   # canonical SLAC service name

class MCPServerInfo(BaseModel):
    name: str
    transport: str = "stdio"
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    env: Dict[str, MCPServerEnvVar] = Field(default_factory=dict)
    auth: MCPServerAuth = Field(default_factory=MCPServerAuth)
    access: MCPServerAccess = Field(default_factory=MCPServerAccess)
    admin_notes: Optional[str] = None   # admin-only override field
```

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

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `backend/app/services/mcp_inference.py` | New | Pass 1 command/args inference; pattern table; returns partial `MCPServerInfo` |
| `backend/app/data/slac_mcp_services.json` | New | Curated SLAC service registry; Pass 2 lookup |
| `backend/app/services/mcp_probe.py` | New | Pass 3 well-known URL probe; async fetch with timeout; returns partial fields or None |
| `backend/app/services/github.py` — `_parse_plugin_json()` | Modify | Parse full `mcp-servers` array; run autodiscovery pipeline; return `List[MCPServerInfo]` |
| `backend/app/models/skill.py` | Modify | Replace `has_mcp_server: bool` with `mcp_servers: List[MCPServerInfo]`; computed property |
| `backend/app/schemas/skill.py` — `SkillOut`/`SkillListOut`/`SkillScanSnapshotOut` | Modify | Expose `mcp_servers`; retain `has_mcp_server` as computed |
| `backend/app/routers/skills.py` | Modify | Add `PATCH /skills/{slug}/mcp-servers/{name}` admin endpoint |
| `frontend/components/mcp-server-card.tsx` | New | Single server card: auth, access, env vars, copy-paste snippet |
| `frontend/components/mcp-servers-section.tsx` | New | Section wrapper; maps over `skill.mcp_servers` |
| `frontend/app/skills/[slug]/page.tsx` | Modify | Add `<MCPServersSection>` below component metadata |
| `frontend/components/skill-submit-preview.tsx` (or equivalent) | Modify | Add MCP server pre-fill section to submission form |

---

## ADRs

### ADR-001: Embed MCP server list in `Skill` document rather than a separate collection

**Status:** Accepted

**Context:** MCP server metadata is always read alongside skill metadata — never independently. A separate collection would require joins on every skill fetch.

**Decision:** Embed `mcp_servers: List[MCPServerInfo]` directly in the `Skill` document (MongoDB embedded array). Admin overrides are stored as fields within each `MCPServerInfo` object.

**Consequences:** No separate collection or foreign-key joins. Server-level updates require a targeted `$set` on the array element by `name`. Array size is bounded (< 20 servers per plugin in practice), so document size is not a concern.

---

### ADR-002: Autodiscovery fills gaps; never overwrites explicit author declarations

**Status:** Accepted

**Context:** Author declarations in `plugin.json` are the ground truth for their own server. Autodiscovery should help authors who don't know what to declare, not silently override accurate metadata.

**Decision:** Three-pass merge: author fields first, then Pass 1 (command inference), then Pass 2 (SLAC registry), then Pass 3 (well-known probe). Each pass only fills fields that are still absent.

**Consequences:** Authors who declare auth/access get exactly what they declared. Authors who omit those fields get the best available inference. Admin overrides (stored in `admin_notes` and applied in the API response layer) take highest precedence.

---

### ADR-003: SLAC service registry as a committed JSON file, not a database table

**Status:** Accepted

**Context:** The registry of known SLAC services and their auth requirements changes infrequently (new services onboarded a few times a year). A DB table would require a migration and admin UI for what is effectively config.

**Decision:** `backend/app/data/slac_mcp_services.json` — a plain JSON file committed to the repo. Changes go through PR review. Loaded at startup (or per-scan; it's small).

**Consequences:** Adding a new SLAC service requires a code PR, not an admin UI action. Acceptable given change frequency. If the registry grows to > 50 entries or needs user-facing editing, migrate to a DB table at that point.

---

### ADR-004: Well-known URL probe is best-effort, never blocks registration

**Status:** Accepted

**Context:** Not all MCP servers expose a well-known endpoint, and probing at scan time adds latency. A probe failure must not prevent skill registration.

**Decision:** Pass 3 runs with a 5s timeout. Any non-200 response or exception is silently ignored; the server entry is registered with whatever Pass 1 and Pass 2 populated. Probe results are not cached or retried outside of a manual refetch.

**Consequences:** HTTP servers that do expose well-known metadata benefit automatically. Stdio servers (the majority) are unaffected. No dependency on external availability for registration success.

---

### ADR-005: `has_mcp_server` retained as computed property, not a stored field

**Status:** Accepted

**Context:** Existing API consumers (frontend skill card, installer skill) read `has_mcp_server`. Removing it would be a breaking change.

**Decision:** `has_mcp_server` becomes a `@property` on `Skill` returning `len(self.mcp_servers) > 0`. Serialised in all `SkillOut` schemas as before. The stored field is removed; value is computed on read.

**Consequences:** Zero breaking changes to existing consumers. Existing skills with `has_mcp_server=true` and no `mcp_servers` list will return `false` until refetched — acceptable, since they'll be refetched during any update cycle.

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

**Slice 1 — Storage + scanner**
- `MCPServerInfo` model and embedded array on `Skill`
- `mcp_inference.py`: Pass 1 command/args patterns
- `slac_mcp_services.json`: initial entries (EPICS, Loki, Kafka)
- `github.py`: parse full `mcp-servers` array; run Pass 1 + Pass 2; store list
- `SkillOut`/`SkillListOut`: expose `mcp_servers`
- `has_mcp_server` computed property

**Slice 2 — Well-known probe**
- `mcp_probe.py`: async well-known URL fetch
- Integrate Pass 3 into scan pipeline
- Unit tests with mocked HTTP responses

**Slice 3 — GUI detail page**
- `mcp-server-card.tsx`: auth, access, env vars, copy-paste snippet
- `mcp-servers-section.tsx`: section wrapper
- Wire into skill detail page

**Slice 4 — Submission form pre-fill**
- Add MCP server pre-fill section to submit preview form
- Editable auth type, access level, env var descriptions

**Slice 5 — Admin override**
- `PATCH /skills/{slug}/mcp-servers/{name}` endpoint
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
- [ ] Autodiscovery runs for every skill with MCP servers: Pass 1 (command inference), Pass 2 (SLAC registry), Pass 3 (URL probe)
- [ ] Submission form pre-fills MCP metadata from autodiscovery; author can edit before confirming
- [ ] Skill detail page shows one card per MCP server: auth type, access level, env vars, copy-paste `claude mcp add` snippet
- [ ] Admin can override auth/access metadata post-registration
- [ ] `has_mcp_server` backwards-compatible computed property works for all existing consumers
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

- **#019 (plugin.json scan pipeline):** #019 introduced `has_mcp_server: bool`; this todo replaces it with a full `mcp_servers` list and autodiscovery pipeline.
- **#020 (installer skill extension):** The installer's `remove` flow runs `claude mcp remove <name>` for each server in `plugin.json["mcp-servers"]`. The richer schema defined here is the same format the installer reads.
- **#016 (bearer JWT auth):** If `auth.type=bearer` servers require SLAC SSO tokens, the token flow from #016 may be referenced in `auth.description`.
