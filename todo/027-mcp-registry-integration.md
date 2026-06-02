# TODO #027 — MCP Registry Integration: Pass 0 Autodiscovery from the Official MCP Registry

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-06-02
> **Shipped:** —
> **Depends on:** #023 (MCP server registry — autodiscovery pipeline, `MCPServerInfo` model, storage layer)

---

## Problem Statement

AKH's #023 autodiscovery pipeline (Pass 1 = command/args inference, Pass 2 = SLAC service registry, Pass 3 = well-known URL probe) infers MCP server metadata entirely from local heuristics. It has no awareness of the official MCP Registry (modelcontextprotocol.io/registry) — the Anthropic-backed public index of publicly published MCP servers — even when a plugin.json entry is an exact match for a registered server.

### What fails today (after #023 ships)

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| plugin.json declares `"package": "io.github.user/server-name"` | Package identifier ignored; falls through to Pass 1 heuristics | Pass 0 queries the MCP Registry; canonical install command + transport returned |
| Skill uses a popular public MCP server (e.g. `@modelcontextprotocol/server-github`) | Pass 1 matches on `npx` prefix at best; no description or canonical transport | Registry returns `server.json` with install command, transport, and description verbatim |
| User views a skill detail page | No provenance signal beyond author-declared metadata | "Listed in MCP Registry" badge shows the server is a known, registered package |
| Registry queried on every refetch | — | 24h TTL cache prevents hammering the registry API |
| SLAC team discovers a useful public server and wants to list it | No publish flow within AKH | Optional stretch: guided publish flow to submit `server.json` to the official registry |

---

## Goals

1. Add a **Pass 0** step to #023's autodiscovery pipeline: before running Pass 1–3, check whether the plugin.json MCP server entry declares a `"package"` field in MCP Registry format (`io.github.*/*` or similar reverse-DNS identifier) and, if so, fetch its `server.json` from the registry API
2. Merge registry metadata (install command, args, transport type, description) as the highest-priority source in the pass merge order — filling fields before Pass 1 heuristics apply
3. Cache registry API responses with a 24h TTL (per server identifier) to avoid hammering the registry on every skill refetch
4. Surface a **"Listed in MCP Registry"** provenance badge on the MCP server card in the skill detail GUI, linked to the registry entry
5. (Stretch) Provide an AKH admin flow to publish a SLAC-internal `server.json` entry to the official registry — scoped as a P3 follow-on

## Non-Goals

- Consuming the MCP Registry as a discovery source for AKH itself (AKH still scans GitHub repos; the registry is used only to enrich metadata for servers already declared in plugin.json)
- Health-checking or uptime monitoring of registered MCP servers
- Mirroring or rehosting registry data — AKH fetches on-demand and caches; the registry remains authoritative
- Authenticating users to the MCP Registry (it is a public read API)
- Replacing Pass 1–3 with the registry — the registry only covers publicly listed servers; SLAC-internal servers continue to rely on Pass 1 + Pass 2

---

## Design

### MCP Registry API overview

The official MCP Registry exposes a REST API conforming to its published OpenAPI spec. Servers are indexed by a reverse-DNS identifier:

```
GET https://registry.modelcontextprotocol.io/v0/servers/{id}
```

Where `id` is the server's reverse-DNS name, e.g. `io.github.user/server-name`.

A successful response returns a `server.json` object that includes:

```json
{
  "id": "io.github.user/server-name",
  "name": "Human-readable name",
  "description": "What this server does",
  "transport": ["stdio"],
  "packages": [
    {
      "registry_name": "npm",
      "name": "@user/server-name",
      "install_command": "npx @user/server-name"
    }
  ],
  "repository": { "url": "https://github.com/user/server-name" }
}
```

AKH extracts: `transport[0]`, the preferred `install_command` from `packages`, and `description`. These map directly to `MCPServerInfo.transport`, `MCPServerInfo.command` + `MCPServerInfo.args`, and an optional `registry_description` field.

### plugin.json — `package` field

Authors (or AKH's scan pipeline in the future) add a `"package"` field to an MCP server entry to declare its registry identity:

```json
{
  "mcp-servers": [
    {
      "name": "github",
      "package": "io.github.modelcontextprotocol/server-github",
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": {
          "description": "GitHub PAT with repo scope",
          "required": true
        }
      }
    }
  ]
}
```

The `package` field is optional. If absent, the server skips Pass 0 and proceeds directly to Pass 1.

**Identifier format:** `io.github.<owner>/<repo>` for GitHub-hosted servers; `io.pypi.<package>` or `io.npmjs.<package>` for registry-native packages. The MCP Registry itself normalises these. AKH accepts any string matching `[a-z0-9.-]+/[a-z0-9._-]+` and forwards it verbatim to the registry API.

### Autodiscovery pipeline — revised pass order

```
Pass 0 — MCP Registry lookup (this todo)
  If package identifier declared → fetch registry API → fill transport, install command, description
  Cache response 24h per identifier
  Never overwrites explicit author-declared fields
  ↓ (fills remaining gaps)
Pass 1 — Command/args inference (from #023)
  ↓
Pass 2 — SLAC service registry lookup (from #023)
  ↓
Pass 3 — Well-known URL probe (from #023)
```

Pass 0 output is fed into the same `MCPServerInfo` partial-merge logic introduced by #023. Each pass fills only absent fields.

### Caching

A simple key-value cache keyed by package identifier, backed by the existing MongoDB instance. Collection: `mcp_registry_cache`.

Document shape:

```python
class MCPRegistryCache(BaseModel):
    package_id: str          # e.g. "io.github.modelcontextprotocol/server-github"
    fetched_at: datetime
    ttl_seconds: int = 86400  # 24h
    server_json: dict         # raw registry response
    not_found: bool = False   # True if registry returned 404 (avoids repeated 404 fetches)
```

On miss: fetch from registry, write to cache, return result.
On hit within TTL: return cached result.
On hit past TTL: re-fetch, update cache.
On 404: store `not_found=True` with same 24h TTL (negative caching — avoids hammering for unknown IDs).
On non-404 error (5xx, timeout): log warning, skip Pass 0 silently, proceed to Pass 1. Do not cache error state.

### Trust / provenance badge

`MCPServerInfo` gains an optional `registry_badge` field:

```python
class MCPRegistryBadge(BaseModel):
    listed: bool = True
    registry_url: str        # e.g. "https://registry.modelcontextprotocol.io/v0/servers/io.github..."
    package_id: str
    fetched_at: datetime

class MCPServerInfo(BaseModel):
    ...
    registry_badge: Optional[MCPRegistryBadge] = None
```

Set only if Pass 0 returned a successful registry hit. If the server is not found in the registry (404) or has no `package` field, `registry_badge` is `None`.

The GUI renders this as a small "MCP Registry" chip on the server card, linking to the registry entry.

### Admin stretch goal: publish flow (P3, not in this todo)

Out of scope for this todo. A future task (#028 or similar) would design a guided form allowing AKH admins to fill a `server.json` template for a SLAC-internal server and submit a PR to the official registry's GitHub-backed index. This todo delivers only the read/consumer side.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `backend/app/services/mcp_registry.py` | New | Async Pass 0 client: fetch `server.json` from MCP Registry API; parse transport + install command + description; return partial `MCPServerInfo` or `None` |
| `backend/app/services/mcp_registry_cache.py` | New | TTL cache layer over `mcp_registry_cache` MongoDB collection; get/set/invalidate; negative caching on 404 |
| `backend/app/models/mcp_registry_cache.py` | New | `MCPRegistryCache` Beanie document model |
| `backend/app/models/skill.py` | Modify | Add `MCPRegistryBadge` model; add `registry_badge: Optional[MCPRegistryBadge]` to `MCPServerInfo` |
| `backend/app/services/github.py` — `_parse_plugin_json()` | Modify | Read `package` field from each `mcp-servers` entry; call `mcp_registry.py` before Pass 1–3 |
| `backend/app/schemas/skill.py` — `MCPServerInfoOut` | Modify | Expose `registry_badge` in API response |
| `frontend/components/mcp-server-card.tsx` | Modify | Render "MCP Registry" badge chip if `registry_badge` is present; link to registry URL |

No new router endpoints. No changes to existing API contracts beyond the additive `registry_badge` field.

---

## ADRs

### ADR-001: Pass 0 as a pre-pass, not a replacement for Pass 1–3

**Status:** Accepted

**Context:** The official MCP Registry covers publicly listed servers. SLAC-internal servers will never appear there. If Pass 0 replaced the pipeline, all internal servers would lose autodiscovery.

**Decision:** Pass 0 runs first and fills gaps; Pass 1–3 fill remaining gaps. Pass 0 never removes entries that Pass 1–3 would populate. SLAC-internal servers with no `package` field skip Pass 0 entirely.

**Consequences:** The pipeline gains one async I/O step (mitigated by caching). All existing Pass 1–3 behaviour is preserved for servers that skip Pass 0 or where Pass 0 returns `None`.

---

### ADR-002: Cache in MongoDB, not in-process

**Status:** Accepted

**Context:** The backend may run multiple replicas. An in-process dict cache would not be shared across replicas and would be invalidated on every restart, causing thundering-herd fetches on deploy.

**Decision:** Cache in a dedicated `mcp_registry_cache` MongoDB collection. TTL index on `fetched_at` field for automatic expiry. All replicas share the same cache.

**Consequences:** One extra MongoDB collection. Cache reads add a small round-trip (< 5ms on the same cluster), negligible relative to the registry HTTP fetch it avoids.

---

### ADR-003: 24h TTL for positive hits; 24h TTL for negative (404) hits

**Status:** Accepted

**Context:** Registry metadata changes infrequently (server publish events). A short TTL (minutes) would hammer the registry unnecessarily. A long TTL (weeks) would mean stale metadata persists after a registry update.

**Decision:** 24h TTL for both positive and negative cache entries. Negative TTL prevents repeated 404 fetches for unknown package IDs. A manual refetch (via the AKH admin refetch action) bypasses the cache.

**Consequences:** Registry updates (e.g. a server changes its install command) take up to 24h to propagate. Acceptable given how rarely this changes and that Pass 1–3 still provide fallback metadata.

---

### ADR-004: Non-404 registry errors are silent no-ops, not fatal

**Status:** Accepted

**Context:** The MCP Registry is an external service in preview. 5xx responses, timeouts, or DNS failures must not break skill registration or refetch.

**Decision:** Any registry error that is not a 404 causes Pass 0 to return `None` silently. A warning is logged. The scan continues to Pass 1–3 as normal. Error state is not cached (unlike 404).

**Consequences:** A registry outage is invisible to end users — skills register without a `registry_badge`. On the next successful refetch, the badge appears. No retries within a single scan to keep scan latency predictable.

---

### ADR-005: `package` field is additive to plugin.json schema; author opt-in

**Status:** Accepted

**Context:** Requiring all plugin.json authors to add a `package` field would be a breaking change and impose unnecessary work on SLAC-internal skill authors (whose servers will never be in the public registry).

**Decision:** The `package` field is optional. Authors of public MCP servers may add it to unlock Pass 0 enrichment and the registry badge. Authors may omit it; behaviour is identical to pre-#027.

**Consequences:** Pass 0 enrichment adoption is gradual and author-driven. A future task could auto-detect the package ID from `command`/`args` for well-known packages (e.g. `npx @modelcontextprotocol/server-github` → `io.github.modelcontextprotocol/server-github`), but that is out of scope here.

---

## Trade-offs

```
Choice: Cache in MongoDB vs Redis vs in-process
  + MongoDB: shared across replicas; no additional infra; TTL index handles expiry natively
  - MongoDB: slightly higher read latency than Redis
  Decision: MongoDB. No Redis in the stack; adding it for a 24h cache is over-engineering.

Choice: Pass 0 before vs after Pass 1
  + Before: registry is canonical source; heuristics fill remaining gaps (correct precedence)
  - Before: adds one async step even when registry returns nothing (mitigated by cache)
  Decision: Before. Registry metadata is higher quality than heuristic inference when available.

Choice: Expose registry_badge as a separate model vs a bool flag
  + Separate model: carries registry URL + package ID; GUI can link directly to the registry entry
  - Separate model: slightly larger API response
  Decision: Separate model. The link to the registry entry is the value; a bool flag would
  require a second lookup to build the link.

Choice: Negative-cache 404s vs skip negative caching
  + Negative cache: prevents repeated 404 fetches for SLAC-internal servers that will never
    be in the registry (e.g. every uvx mcp-server-epics entry if it has a package field)
  - Negative cache: a newly listed server takes up to 24h to get its badge after registration
  Decision: Negative cache. SLAC-internal servers dominate AKH's catalog; absorbing 404s
  on every refetch is unacceptable.

Choice: Auto-detect package ID from command/args vs require explicit author declaration
  + Auto-detect: zero author friction for known npx/@modelcontextprotocol/* packages
  - Auto-detect: heuristic mapping may be wrong; introduces false registry lookups
  Decision: Explicit declaration only in this todo. Auto-detect is a future enhancement once
  the registry's identifier→package mapping is stable.
```

---

## Delivery Slices

**Slice 1 — Cache layer + registry client**
- `MCPRegistryCache` Beanie model + `mcp_registry_cache` collection
- `mcp_registry_cache.py`: get/set/invalidate with 24h TTL; negative caching on 404
- `mcp_registry.py`: async HTTP client against the registry API; parses `transport`, `install_command`, `description`; returns partial `MCPServerInfo` or `None`
- Unit tests with mocked HTTP and mocked MongoDB

**Slice 2 — Pass 0 integration**
- Read `package` field from `mcp-servers` entries in `_parse_plugin_json()`
- Call `mcp_registry.py` as Pass 0; merge result before Pass 1–3
- `MCPRegistryBadge` model; set on `MCPServerInfo` when Pass 0 hits
- Integration test: scan plugin.json with `package` field → `registry_badge` populated

**Slice 3 — GUI badge**
- `MCPRegistryBadge` exposed in `MCPServerInfoOut` schema
- Render "MCP Registry" chip in `mcp-server-card.tsx` if `registry_badge` present; chip links to `registry_badge.registry_url`

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| MCP Registry API changes its URL or response schema (preview status) | Medium | Medium | Pin to versioned endpoint (`/v0/`); parse defensively — wrap field access in try/except; log schema mismatches |
| Registry outage causes scan latency spike (waiting for timeout) | Low | Medium | 5s connect timeout + 10s read timeout; errors are silent no-ops; scan continues to Pass 1–3 |
| Cache collection grows unboundedly | Low | Low | TTL index on `fetched_at` expires documents automatically; collection size bounded by number of distinct package IDs ever seen |
| Author adds `package` field pointing to wrong registry ID; wrong metadata merged | Low | Medium | Pass 0 only fills absent fields — author's explicit plugin.json fields always win; admin override endpoint from #023 remains available |
| Negative-cache TTL hides a newly-registered server for up to 24h | Very Low | Very Low | Admin manual refetch bypasses cache; acceptable given the badge is purely cosmetic |
| Registry covers only public servers; SLAC authors confuse it with the SLAC registry | Low | Low | Badge copy ("Listed in MCP Registry") and tooltip make clear this is the public registry, not a SLAC-internal listing |

---

## Implementation Checklist

- [ ] Add `package: Optional[str]` to `MCPServerInfo` (from #023) — schema-level only, no logic
- [ ] Define `MCPRegistryBadge` model; add `registry_badge: Optional[MCPRegistryBadge]` to `MCPServerInfo`
- [ ] Create `mcp_registry_cache` MongoDB collection with TTL index on `fetched_at`
- [ ] `models/mcp_registry_cache.py`: `MCPRegistryCache` Beanie document
- [ ] `services/mcp_registry_cache.py`: get/set; 24h TTL; negative caching on 404; cache bypass flag for manual refetch
- [ ] `services/mcp_registry.py`: async client for `GET /v0/servers/{id}`; parse `transport`, preferred `install_command`, `description`; return partial `MCPServerInfo` + `MCPRegistryBadge` or `None`
- [ ] `services/github.py._parse_plugin_json()`: read `package` field; call Pass 0 before Pass 1–3
- [ ] Pass 0 merge logic: registry fields fill absent `MCPServerInfo` fields; never overwrite author-declared values
- [ ] `schemas/skill.py`: expose `registry_badge` in `MCPServerInfoOut`
- [ ] `frontend/components/mcp-server-card.tsx`: render "MCP Registry" badge chip; link to `registry_badge.registry_url`
- [ ] Tests: cache miss/hit/expiry; 404 negative cache; 5xx silent no-op; merge precedence (author > registry > Pass 1); GUI badge renders/hides correctly
- [ ] Confirm #023 has shipped and `MCPServerInfo` model is in place before merging Slice 2

---

## Test Plan

### Unit tests
- `mcp_registry.py`: valid `server.json` response → correct `MCPServerInfo` partial; missing `transport` field → defaults to `stdio`; missing `packages` → `command` not set; non-200 response → returns `None`; timeout → returns `None`
- `mcp_registry_cache.py`: cache miss → fetches and stores; cache hit within TTL → returns cached; cache hit past TTL → re-fetches; 404 response → stores negative entry; negative entry within TTL → skips fetch; cache bypass flag → always fetches
- Pass 0 merge: author-declared `transport` not overwritten by registry; absent `transport` filled from registry; `registry_badge` set on hit; `registry_badge` absent on miss

### Integration tests
- Scan plugin.json with `"package": "io.github.modelcontextprotocol/server-github"` (mocked registry) → `Skill.mcp_servers[0].registry_badge.listed == true`
- Scan with no `package` field → `registry_badge` is `None`; Pass 1–3 run as before
- Scan with unknown `package` ID (404) → `registry_badge` is `None`; negative cache entry written
- Second scan within TTL → cache hit; registry HTTP call not made

### Smoke tests (manual before DoD)

| # | Scenario | Expected |
|---|---|---|
| S1 | Skill with `package: "io.github.modelcontextprotocol/server-github"` | Detail page shows "MCP Registry" badge on the server card |
| S2 | Badge chip clicked | Browser navigates to `registry.modelcontextprotocol.io` entry for that server |
| S3 | Skill with SLAC-internal server, no `package` field | No "MCP Registry" badge; Pass 1–2 metadata still shown |
| S4 | Registry API down (simulate with mock) | Skill registers normally; no badge; no error surfaced to user |
| S5 | Refetch skill after registry returns new `install_command` (past 24h TTL) | Updated install command appears in the `claude mcp add` snippet |
| S6 | Refetch within 24h TTL | Cached response used; no outbound registry call |
| S7 | Author declares `transport: "http"` and registry says `transport: "stdio"` | Author's declaration wins; `http` shown on card |

---

## Definition of Done

- [ ] `package` field accepted in plugin.json `mcp-servers` entries; stored on `MCPServerInfo`
- [ ] Pass 0 runs before Pass 1–3 for any server with a `package` field; registry metadata merged
- [ ] 24h TTL cache in MongoDB; negative caching on 404; cache bypass on manual refetch
- [ ] Registry errors (non-404) are silent no-ops; scan never fails due to registry unavailability
- [ ] `registry_badge` field populated in API response for registry-listed servers
- [ ] "MCP Registry" badge chip rendered on skill detail MCP server card; links to registry entry
- [ ] All checklist items complete
- [ ] #023 is shipped and `MCPServerInfo` model is stable

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

- **#023 (MCP server registry):** This todo is a pure extension of #023. #023 must ship first (or in parallel). The `MCPServerInfo` model, `_parse_plugin_json()` pipeline, and `MCPServerInfo` merge logic are all defined by #023; this todo adds `package`, `registry_badge`, and Pass 0 on top.
- **#019 (plugin.json scan pipeline):** #019 introduced the plugin.json scan; #023 extended it with full MCP server metadata; this todo adds one more optional field (`package`) to the scan.
- **#020 (installer skill extension):** The installer reads `mcp-servers` entries; the `registry_badge` field is informational and does not affect install behaviour. No installer changes required.
- **#022 (installer git clone):** No interaction — this todo is backend scan-time only.
