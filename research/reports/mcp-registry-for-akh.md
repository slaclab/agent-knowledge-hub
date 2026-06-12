> **Report:** MCP Registry Landscape — What AKH and Cogito Should Steal, Defer, and Skip
> **Addressed to:** AKH + Cogito platform team
> **Concept References:** [mcp-registry-landscape.md](../concepts/mcp-registry-landscape.md)

*Generated 2026-06-09 / Confidence: Medium (primary sources + user brief)*

## Executive Summary

Five distinct registries now cover the MCP server discovery space, but they cluster into two archetypes: public community indexes (Official MCP Registry, PulseMCP, Smithery) optimised for breadth and discovery, and enterprise governance layers (Turbo MCP, AWS AgentCore) optimised for controlled onboarding and auditability. AKH currently sits between these — it has a community catalog but lacks governance, and Cogito needs governance first. The most important capability gap is one no existing registry fills: tool-level semantic indexing. Every registry today indexes servers; none indexes the individual tools those servers expose. AKH should steal the admin approval gate from Turbo MCP's pattern immediately, adopt the Official MCP Registry's namespace ownership model to resolve publisher identity, and build the tool-level embedding layer as original work. Managed connection proxying (Smithery) and deep semantic search (AWS AgentCore) are real but deferrable.

## What to Steal Now

### 1. Admin Approval Gate — from Turbo MCP

Turbo MCP's core workflow: a publisher registers a server, tests connectivity, and submits for approval; the server is invisible to consumers until an admin explicitly approves it. This is exactly the governance layer Cogito needs and AKH currently lacks.

**What to implement:**
- Add a `status` field to AKH's MongoDB catalog entries: `pending | approved | rejected | suspended`.
- Servers in `pending` are not returned by the public listing API (`GET /v0.1/servers`).
- Admins receive a notification (initially email; later a review queue in the AKH UI) and call a `PATCH /v0.1/servers/{id}/status` endpoint to approve or reject with a reason string.
- Rejected servers can be resubmitted after the publisher addresses the stated reason.

**Why now:** Cogito's multi-team deployment model cannot tolerate unapproved MCP servers appearing in the tool namespace of production agents. Without this gate, any developer can inject a server that all Cogito agents can discover and call.

**Caveat:** Turbo MCP's API is entirely undocumented and the product is pre-GA as of June 2026. The *pattern* is sound but no implementation can be borrowed directly — this is original build work informed by Turbo MCP's advertised architecture.

### 2. Namespace Ownership Model — from the Official MCP Registry

The Official MCP Registry (github.com/modelcontextprotocol/registry, Apache-2.0, v1.7.9) enforces that a publisher claiming a namespace (e.g., `io.github.slac/*`) must authenticate as the matching GitHub user or organisation. Verification methods: GitHub OAuth, GitHub Actions OIDC (keyless), DNS challenge, or HTTP challenge.

**What to implement:**
- AKH already has GitHub OAuth for publisher identity. Extend it: when a publisher registers a server, validate that the claimed namespace prefix matches their authenticated GitHub identity.
- For SLAC-internal servers (`gov.slac.*`), add a DNS or HTTP challenge path so institutional publishers can claim org-level namespaces without requiring GitHub accounts.
- Reject namespace squatting at registration time, not at approval time — this reduces admin review burden.

**Why now:** AKH currently has no namespace collision prevention. As the catalog grows, two different publishers can register identically-named servers. The Official Registry's ownership model is proven, open-source, and directly implementable.

**Implementation reference:** The mcp-publisher CLI (SBOM-signed binaries in each release) is a usable reference for the client-side registration flow. The Go source at github.com/modelcontextprotocol/registry is Apache-2.0 and forkable.

### 3. Incremental Sync via `updated_since` — from the Official MCP Registry

The Official Registry's `GET /v0.1/servers?updated_since=<RFC3339>` endpoint enables efficient delta syncs for any downstream catalog that ETLs from it. This is the mechanism that makes subregistries (PulseMCP, Smithery) stay current without full re-scrapes.

**What to implement:**
- AKH's catalog ingestion pipeline (if it ETLs from the Official Registry) should use `updated_since` + cursor pagination, not polling full result sets.
- Expose the same parameter on AKH's own listing API so Cogito or any downstream consumer can do the same delta-sync against AKH.
- Store `updated_at` with millisecond precision on every catalog record.

**Why now:** This is a two-hour implementation against an already-specified API pattern and prevents O(n) polling that will become expensive as the catalog scales.

### 4. Curated Quality Filtering — from PulseMCP

PulseMCP deliberately omits low-quality, test, and spam servers. Its sub-registry API (partner/B2B only — requires outreach to api.pulsemcp.com) returns `isOfficial`, `visitorsEstimateMostRecentWeek`, and statically-discovered tool objects as enrichment fields beyond the base MCP Registry spec.

**What to implement:**
- Add an `is_official` boolean and a `quality_tier` enum (`community | verified | official`) to AKH's server schema.
- When ingesting from PulseMCP (if partner access is negotiated), propagate `visitorsEstimateMostRecentWeek` as a popularity signal for default sort ordering.
- A spam/low-quality report flag for community-submitted servers should feed the admin review queue.

**Why now (partially):** The schema fields are free to add today. The PulseMCP API integration is conditional on negotiating partner access — worth pursuing now, not blocking on.

## What to Defer

### Managed Connection Proxy — Smithery pattern

Smithery's `mcp.smithery.run/{namespace}` endpoint multiplexes all servers in a namespace behind a single MCP URL, handling OAuth token refresh transparently and storing credentials with write-only access so agents cannot exfiltrate secrets. The Uplink feature lets local MCP servers be reachable through Smithery's Cloudflare Workers edge without a deploy.

**Why it matters:** This pattern cleanly maps onto AKH's multi-tenant architecture — one ingress URL per SLAC team rather than N per-server endpoints.

**Why to defer:** Smithery is SaaS-only (no self-host path; CLI is AGPL-3.0 but the platform runs on Cloudflare Workers with no documented on-premises option). AKH/Cogito must run on-cluster in the SLAC environment. Building a Smithery-equivalent proxy from scratch is a significant undertaking that should follow catalog governance, not precede it. Revisit after the approval gate and namespace model land.

**Reference architecture when ready:** Smithery's namespace multiplexer is the correct target design. MCPB bundle execution via Uplink is worth studying for AKH's eventual "local dev onramp" feature.

### Hybrid Semantic + Keyword Search — AWS AgentCore pattern

AWS AgentCore Registry runs keyword and semantic search simultaneously on every query, ranking results by a weighted combination of relevance scores. Cross-vocabulary resolution ("payment processing" matches "billing") is a documented feature. Custom organisational schemas let teams register arbitrary resource types. CloudTrail provides full control-plane audit logs.

**Why it matters:** This is the right long-term search architecture for a registry with hundreds of SLAC-specific servers, and the EventBridge approval workflow integration is a useful pattern for AKH's governance pipeline.

**Why to defer:** AgentCore is AWS-only (requires an AWS account; the registry service itself runs on AWS even if registered resources are elsewhere). The preview tag is still present on registry components as of June 2026. AKH does not require AWS and must not take an AWS-only dependency for core catalog search. The semantic search capability is valuable to build, but build it independently using embeddings (see "The Missing Layer" below) rather than adopting AgentCore's implementation.

### PulseMCP API Integration

The PulseMCP sub-registry API (api.pulsemcp.com) delivers enriched metadata — weekly visitor estimates, official-status flags, quality-filtered server lists — that would significantly improve AKH's catalog quality. Access requires a partner agreement and is not self-service.

**Why to defer:** The negotiation timeline is unknown and AKH cannot build a dependency on a B2B API access that requires ongoing relationship management. Schema fields should be reserved for this data; the integration should be attempted in parallel with other work but not gate releases.

## What to Skip

### Turbo MCP as a Direct Dependency

Turbo MCP is the closest product match to what Cogito needs (K8s-native, OIDC-integrated, admin approval workflow), but it is proprietary, pre-GA, undocumented, and distributed through a private registry behind a sales contact. As of June 2026, the application path at mcp.run returns 404. There is no public API, no open-source license, and no Helm chart. AKH cannot adopt it as a dependency or fork it. Steal the pattern, not the software.

### SaaS-Only Patterns

Smithery's managed OAuth, Uplink tunneling, and edge proxy are all built on Cloudflare Workers and have no on-premises path. SLAC's data environment and Cogito's on-cluster mandate make any SaaS-only component non-viable for core infrastructure. Smithery patterns are useful as a design reference only.

### AWS-Specific Infrastructure

AWS AgentCore's EventBridge integration, CloudTrail audit trail, and IAM-native authorization are useful within the AWS ecosystem but introduce a vendor lock-in that conflicts with AKH's cloud-agnostic Kubernetes-first architecture. The audit trail requirement is real — but it should be satisfied with a Kubernetes-native solution (e.g., audit logging via OpenTelemetry or a self-hosted event store) rather than CloudTrail.

### Full Server Count Maximalism

PulseMCP's 16,000+ server count (trending toward 17,000+) is achieved by indexing everything including low-quality test entries before PulseMCP's own editorial filtering. AKH should not optimise for catalog breadth — it should optimise for signal quality. The SLAC research community benefits more from 200 well-governed, tool-level-indexed servers than from 17,000 unvetted entries.

## The Missing Layer — Tool-Level Indexing

Every registry in this landscape operates at the server level. Discovery workflow: find a server → call `tools/list` → discover what tools it exposes. No registry today lets you search across individual tool descriptions, input schemas, or output contracts.

This is the single most impactful capability AKH can build that no existing registry provides.

### What it is

A secondary index where the unit of discovery is a tool, not a server. Each tool record contains:

```json
{
  "tool_id": "slac.github/arxiv-mcp/search_papers",
  "server_id": "slac.github/arxiv-mcp",
  "server_version": "1.2.0",
  "tool_name": "search_papers",
  "description": "Search arXiv for papers matching a query, filtered by date and subject area",
  "input_schema": { "$ref": "..." },
  "output_schema": { "$ref": "..." },
  "embedding": [0.023, -0.114, ...],
  "indexed_at": "2026-06-09T00:00:00Z"
}
```

### Embedding approach

1. **Text to embed:** Concatenate `tool_name`, `description`, and a flattened summary of `input_schema` property names and descriptions. Do not embed the full JSON schema — it adds noise.
2. **Model:** `text-embedding-3-small` (OpenAI) or a self-hosted `nomic-embed-text` for air-gapped operation. Vector dimension: 1536 (OpenAI) or 768 (Nomic). Store in MongoDB Atlas Vector Search or a sidecar `pgvector` instance — AKH already uses MongoDB so Atlas Vector Search is the path of least resistance.
3. **Index trigger:** Re-embed a server's tools whenever its `updated_at` timestamp changes or a new version is registered. Use the same `updated_since` delta-sync pattern from the Official Registry to know which servers to re-poll.
4. **Query API:** `POST /v0.1/tools/search` with `{ "q": "find papers on a topic", "limit": 10, "filters": { "server_id": "...", "server_status": "approved" } }` returning ranked tool records with parent server metadata.

### How it complements server-level listing

Server-level listing answers "what servers are available?" Tool-level search answers "what can I ask an agent to do right now?" These are different UX entry points:

- A Cogito agent building a dynamic tool manifest queries the tool index first, then loads only the servers that expose the tools it needs.
- An AKH user searching "summarise a PDF" gets tool results, not server results — the UI can then offer one-click server installation for the server that owns the matching tool.
- Quality filtering at the tool level catches servers that list `do_thing_1` through `do_thing_47` as separate tools (spam signal) versus servers with a small number of precisely described tools.

### Schema additions required

- `tools` collection in MongoDB with the schema above.
- `tool_count` denormalised onto the server record for UI display.
- `last_tools_sync_at` on the server record to track when `tools/list` was last called.
- A background worker (cron or queue-triggered) that calls `tools/list` for each approved server on a schedule and updates the tool index.

## Open Questions

1. **PulseMCP partner access:** Can the SLAC/AKH team negotiate a partner agreement with api.pulsemcp.com? If yes, the enriched metadata (visitor estimates, quality filtering, static tool objects) significantly accelerates catalog quality without building from scratch.

2. **MongoDB Atlas Vector Search vs pgvector:** AKH uses MongoDB. Atlas Vector Search is the natural embedding store, but requires Atlas M10+ tier. If AKH is self-hosted on-cluster (not Atlas), a sidecar pgvector or Qdrant instance may be more practical. This affects the tool-level indexing architecture.

3. **Turbo MCP GA timeline:** Turbo MCP's application path returning 404 in June 2026 suggests pre-launch status. If it reaches GA with documented APIs in Q3/Q4 2026, a reassessment of direct integration is warranted — it may become the right off-the-shelf governance layer rather than a pattern-only reference.

4. **Official Registry ETL scope:** Should AKH ETL from the Official MCP Registry (`registry.modelcontextprotocol.io/v0.1/servers`) as a seed corpus, or only ingest SLAC-originated servers? The former provides immediate catalog breadth; the latter keeps governance manageable at SLAC scale. The `is_official` / `quality_tier` schema supports either strategy but the policy decision should be explicit.

5. **Cogito's OIDC provider:** Turbo MCP explicitly supports "Dex/Keycloak compatible" OIDC. Which IdP does Cogito use? The namespace ownership validation (for `gov.slac.*` namespaces) should integrate with the same IdP rather than requiring a separate GitHub OAuth flow.

6. **Tool-level indexing and live server availability:** The tool index is only as fresh as the last `tools/list` call. Servers can go offline between sync cycles, making stale tool records mislead agents. How frequently should the background worker run, and what staleness TTL is acceptable for Cogito's production agents?

## Sources

- Official MCP Registry — github.com/modelcontextprotocol/registry — fetched 2026-06-09
- Official MCP Registry releases — github.com/modelcontextprotocol/registry/releases — fetched 2026-06-09
- Official MCP Registry API spec — registry.modelcontextprotocol.io — fetched 2026-06-09
- Turbo MCP product site — www.mcp.run — fetched 2026-06-09
- Smithery documentation — smithery.ai/docs — fetched 2026-06-09
- Smithery CLI changelog — github.com/smithery-ai/cli/blob/main/CHANGELOG.md — fetched 2026-06-09
- Smithery llms.txt index — smithery.ai/llms.txt — fetched 2026-06-09
- PulseMCP directory (Wayback snapshot 2026-05-29) — web.archive.org/web/20260529*/pulsemcp.com — fetched 2026-06-09
- PulseMCP sub-registry API spec — api.pulsemcp.com — fetched 2026-06-09
- AWS AgentCore Registry documentation — docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html — fetched 2026-06-09
- AWS AgentCore GA announcement — aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore — fetched 2026-06-09
