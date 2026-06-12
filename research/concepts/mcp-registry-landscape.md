> **Concept:** MCP Registry Landscape — Survey of Five Production Registries
> **Source:** modelcontextprotocol/registry (GitHub), smithery.ai, pulsemcp.com, turbomcp docs, AWS AgentCore docs
> **Relevance:** AKH already installs MCP servers; understanding what the registry ecosystem provides and where it falls short informs AKH's own registry and governance design

*Generated 2026-06-09 / Confidence: Medium (primary sources + user brief — verify AWS AgentCore details)*

---

## Comparison Table

| Dimension | Official Registry | Turbo MCP | Smithery | PulseMCP | AWS AgentCore |
|---|---|---|---|---|---|
| **Deployment** | Self-host (Go + PostgreSQL) | Single K8s container (private registry) | SaaS-only (Cloudflare Workers) | SaaS-only | AWS-managed |
| **Open source** | Yes (Apache-2.0) | No (proprietary) | CLI AGPL-3.0; platform closed | No | No |
| **Auth / namespace ownership** | GitHub OAuth/OIDC, DNS/HTTP challenge | OIDC (any compatible IdP) | OAuth token lifecycle managed | API key + tenant ID (partner only) | IAM |
| **Search** | None — cursor-paginated listing only | Unknown (API undocumented) | Unknown | None (human-facing only) | Hybrid keyword + semantic |
| **Approval workflow** | None | Yes — admin approval required before server is discoverable | None | Editorial curation (human) | Yes — Publisher → Curator → Consumer |
| **Audit trail** | Soft-delete with `deleted` status | Full audit logs (claimed) | Write-only credential storage | None | CloudTrail (all control-plane calls) |
| **Connection proxy** | None | Gateway layer (opaque) | Yes — namespace-scoped multiplexer + OAuth token lifecycle | None | MCP-native endpoint per registry instance |
| **Scale / catalog size** | Canonical source (subregistries ETL from it) | Unknown (pre-GA) | Unknown | 16,000+ servers (curated) | Organisation-scoped |
| **Ecosystem role** | Canonical metaregistry | Enterprise governance layer | Managed connectivity layer | Human-facing directory + analytics | AWS-ecosystem catalog |
| **AKH fit** | ETL source via `updated_since` incremental sync | Governance model reference; not yet integrable | Connection proxy + credential model reference | Best enriched data source (partner API) | Semantic search + approval workflow reference |

---

## 1. Official MCP Registry

**Repo:** https://github.com/modelcontextprotocol/registry
**Latest release:** v1.7.9 (2026-05-12)
**License:** Apache-2.0 (transitioning from MIT)

### Architecture

Metadata-only metaregistry (no binaries or code stored). Subregistries (Smithery, PulseMCP, etc.) ETL from it. The Generic MCP Registry API spec is decoupled from this implementation — any conforming implementation is valid. Two-tier API versioning: `/v0/` is the mutable dev track; `/v0.1/` entered API freeze in October 2025 for stable integrator use.

### Deployment model

Self-hosted via Docker (`ghcr.io/modelcontextprotocol/registry:latest`) with an external PostgreSQL instance. `make dev-compose` builds with `ko` and starts the full stack locally. Pulumi manages production deployment. Published CLI tool `mcp-publisher` with SBOM-signed release binaries.

### Auth / namespace ownership

Namespace ownership enforced per namespace type:
- `io.github.*` — GitHub OAuth (must authenticate as the matching GitHub user/org)
- GitHub Actions publishers — GitHub OIDC (keyless)
- Domain-based namespaces (e.g. `me.adamjones/*`) — DNS challenge or HTTP challenge
- Admin users — Google OIDC

### Search

None. The listing endpoint `GET /v0.1/servers` returns cursor-paginated results. Cursors are opaque strings (`nextCursor`, `null` when exhausted). The `updated_since` RFC3339 filter enables incremental sync for subregistries.

### Unique features

- `updated_since` filter purpose-built for delta ETL by downstream subregistries
- Soft-delete semantics: servers get `deleted` status rather than hard removal; `include_deleted` query param exposes them
- Two-tier API versioning with explicit stability contract on `/v0.1/`
- Spec/implementation separation — ecosystem can have multiple conforming registries

### Limitations

No search capability. No approval workflow. No connection proxying. Depends on downstream subregistries for enrichment (popularity signals, quality filtering, semantic search).

### AKH relevance

AKH can act as a subregistry, ETL-ing from `registry.modelcontextprotocol.io` using cursor pagination plus `updated_since` for efficient delta syncs. Target `/v0.1/` stable endpoints for production ingestion.

---

## 2. Turbo MCP

**URL:** https://turbomcp.com (formerly www.mcp.run)
**Status:** Pre-GA as of June 2026 (the `/run` application path returns 404)
**License:** Proprietary (commercial, pricing gated behind sales contact)

### Architecture

Single-container deployment with a gateway layer sitting between MCP clients and registered servers. Admin approval gates prevent servers from appearing in any client view until an admin approves them. Includes DLP features and a kill-switch that deactivates AI agent access without blocking human access to the same work apps.

Note: the original mcp.run was a distinct product (Dylibso's WebAssembly/XTP-based servlet registry, discontinued approximately April 2025). Turbo MCP is not an architectural rebrand — it is a separate enterprise product that acquired the mcp.run domain.

### Deployment model

Single K8s container distributed through a private registry (customers pull/mirror). Also supports PaaS and bare-metal VMs per marketing copy. No public Helm chart or Docker Hub image found.

### Auth

OIDC-compatible IdP integration for user management. Dynamic Client Registration (DCR) for OAuth is handled automatically for MCP server connectivity. RBAC governs which users can submit vs approve servers.

### Search

Unknown. The API is fully undocumented; no public API surface exists. The entire web presence is a Framer marketing site with a demo CTA.

### Unique features

- Admin approval workflow: team members register servers and test connectivity; admins approve before servers become discoverable
- AI-only kill-switch: one-click deactivation stops AI agent activity without blocking human access to connected work apps
- OIDC SSO compatible with Dex/Keycloak

### Limitations

API entirely opaque. No public documentation beyond marketing copy. Pre-GA product; direct sales engagement required. Licensing terms unavailable. The "fka mcp.run" framing in the brief is misleading — the original mcp.run architecture is discontinued.

### AKH relevance

The admin approval workflow and OIDC-gated server onboarding map directly onto AKH's multi-team governance requirements. Not integrable in its current pre-GA state. Worth revisiting post-GA; the governance model (not the API) is the reference.

---

## 3. Smithery

**URL:** https://smithery.ai
**CLI:** AGPL-3.0 (v1.2.0, 2026-05-31); platform is proprietary SaaS
**Infrastructure:** Cloudflare Workers

### Architecture

Two-layer product: (1) an MCP server registry and (2) a managed connection proxy. The proxy endpoint `https://mcp.smithery.run/{namespace}` multiplexes all connections in a namespace behind a single MCP endpoint. On `tools/call` the proxy strips a connection-ID prefix and forwards to the correct backend server. Also operates a separate Skills Registry (higher-level reusable agent components, installable via `npx skills add`).

### Deployment model

SaaS-only. No self-hosting docs, Helm charts, or Docker Compose found. No on-premises option.

### Auth / credential management

Smithery manages OAuth apps for major integrations. Tokens auto-refresh before expiry; on refresh failure the connection transitions to `auth_required` state. Credentials are stored encrypted with write-only access — agents cannot read back secrets. Zero OAuth configuration is an explicit platform promise for end users.

### Search

Not documented in available sources.

### Unique features

- **Namespace multiplexer:** single ingress URL per namespace fronts all servers in that namespace — no per-server endpoint management
- **Uplink:** exposes a local stdio MCP server publicly without deployment, via Smithery's edge network. Uses MCPB (MCP Bundle) format for compiled stdio servers executed via Uplink
- **Write-only credential storage:** agents can use OAuth tokens but cannot exfiltrate them
- **Dual catalog:** MCP servers + Skills Registry are separate catalogs under one platform

### Limitations

SaaS-only — no self-hosting. Uplink documentation returned 404 during research; protocol details are not publicly documented. Product reached GA only in May 2026; some features are still underdocumented.

### AKH relevance

The namespace-scoped proxy endpoint maps onto AKH's multi-tenant architecture. The write-only credential storage model is directly applicable to AKH's credential handling design for user-connected external services. Uplink is a potential onramp for letting AKH users expose local dev-time MCP servers without a full deploy cycle.

---

## 4. PulseMCP

**URL:** https://pulsemcp.com
**Sub-Registry API:** https://api.pulsemcp.com (partner/B2B only — requires partner agreement)
**Ecosystem role:** Named alongside Anthropic, GitHub, and Microsoft as a trusted official registry contributor

### Architecture

Human-facing directory wrapping the official MCP Registry spec with proprietary enrichment fields. Implements the Generic MCP Registry API as a sub-registry with additions: `visitorsEstimateMostRecentWeek`, `visitorsEstimateLastFourWeeks`, `visitorsEstimateTotal`, `isOfficial`, corrected server.json metadata, and (premium tier) OAuth/API key auth details and statically-discovered MCP tool objects. Cursor-based pagination, incremental ETL design, soft-delete only.

### Deployment model

SaaS-only.

### Auth

B2B Sub-Registry API uses API key + tenant ID over HTTPS. The human-facing directory has no auth.

### Search

No programmatic search. The human-facing directory provides trending search chips and three classification filters (Anthropic References, Official Providers, Community). The "60+ category tags" claim in the user brief could not be verified — approximately 36 trending chips were found.

### Unique features

- **Popularity analytics:** per-server weekly visitor estimates derived from SEO signals and calibration against known adoption data (not PulseMCP site traffic). Top servers: Playwright 3.1m/week, Chrome DevTools 2.2m/week, Context7 1.3m/week
- **Intentional quality curation:** explicitly omits low-quality, test, and spam entries — catalog is smaller than raw aggregators by editorial decision
- **Enrichment-as-a-subregistry:** the only registry adding popularity signals to the standard spec fields
- **Governance access:** lead author is an active MCP Steering Committee member; PulseMCP is the primary quality layer for the official registry ecosystem

### Limitations

No public API — partner agreement required for Sub-Registry API access. Server count at time of research was 16,249 (late May 2026 snapshot); the 17,413 figure in the user brief is unconfirmed but plausible given daily growth. No programmatic search capability.

### AKH relevance

Strongest candidate data source for AKH's server catalog: curated, enriched metadata with weekly visitor estimates and quality filtering already applied. If AKH negotiates partner access to the Sub-Registry API, it gets de-duplication, popularity ranking, and official-status flags out of the box.

---

## 5. AWS AgentCore Registry

**URL:** https://aws.amazon.com/bedrock/agentcore/
**Docs:** https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html
**Status:** Preview (Registry component); AgentCore broader platform is GA

### Architecture

Organisation-scoped registry running inside AWS. Exposes a per-registry MCP-native endpoint — any MCP-compatible client can connect using the MCP protocol directly without touching the AWS SDK. Hybrid search runs keyword and semantic modalities simultaneously, ranking by weighted combination. Custom "resource" record type accepts any valid JSON structure, enabling organisations to register arbitrary resource types (APIs, Lambda functions, knowledge bases) with their own schema.

### Deployment model

AWS-managed only. Requires an AWS account. Can catalogue resources deployed on-premises or other clouds, but the registry service itself runs exclusively on AWS.

### Auth

IAM. All control-plane API calls logged as management events in CloudTrail by default.

### Search

Hybrid keyword + semantic. Semantic search resolves natural-language queries to relevant records across vocabulary gaps (searching "payment processing" finds records tagged "billing"). Metadata filters (record name, type, version) compose with both search modalities.

### Unique features

- **Hybrid search:** only registry in this survey with confirmed cross-vocabulary semantic matching
- **CloudTrail audit trail:** complete, automatic log of all registry mutations (create, update, approve, reject)
- **EventBridge approval workflow:** governed Publisher → Curator → Consumer lifecycle; `UpdateRegistryRecordStatus` API lets external CI/security tooling participate in the review pipeline without living inside AWS
- **MCP-native endpoint per registry instance:** clients connect via MCP protocol, not SDK, enabling seamless tool discovery from within agentic workflows
- **Record-sync:** auto-pulls tool metadata from live MCP server URLs (AKH does not yet have this)

### Limitations

AWS account required. Pricing not publicly available. Regional availability not documented. Registry component still in preview. Deep AWS-ecosystem coupling (IAM, Bedrock, EventBridge) makes it unsuitable as an AKH dependency.

### AKH relevance

Architecture reference for AKH's target state: semantic search over tool metadata, approval workflow integrated with external CI, and per-organisation scoping. The record-sync capability (auto-pulling tool metadata from live MCP server URLs) is a feature gap in AKH worth addressing. The EventBridge approval hook pattern is transferable to AKH's Kubernetes event bus.

---

## 6. The Missing Layer — Tool-Level Indexing

Every registry surveyed operates at the **server level**. Discovery flow in all five:

1. Search or browse to find a server by name, description, or category
2. Connect to the server
3. Call `tools/list` to enumerate the tools inside it

No registry indexes at the **tool level** — individual tool descriptions, parameter schemas, and usage examples are not searchable across registries. A query like "find me a tool that extracts invoice line items from PDF" cannot be answered without first connecting to each candidate server and calling `tools/list` individually.

PulseMCP's premium tier includes statically-discovered MCP tool objects as an enrichment field, which is the closest any registry comes to tool-level indexing — but it is behind a B2B agreement and is not searchable via semantic query.

The gap this creates for AKH:

- AKH already calls `tools/list` at install time; it could index the resulting tool schemas into a vector store
- A semantic index over tool descriptions would make AKH the only discoverable tool-level catalog in the ecosystem
- This is not a feature any of the five registries plan to provide at the server-registry layer — it is a value-add that belongs in the consuming platform

Recommended approach: at server install time, persist each `ToolDefinition` (name, description, inputSchema) to a vector index keyed by `(registry_id, server_id, tool_name)`. Expose a `/tools/search?q=` endpoint backed by embedding similarity. This fills the gap the report identifies and differentiates AKH from every existing registry.

---

## Applied in
- [reports/mcp-registry-for-akh.md](../reports/mcp-registry-for-akh.md) — what AKH and cogito should steal, defer, and skip

---

## Sources

- https://github.com/modelcontextprotocol/registry — fetched 2026-06-09
- https://modelcontextprotocol.io/docs/concepts/registry — fetched 2026-06-09
- https://turbomcp.com — fetched 2026-06-09
- https://smithery.ai — fetched 2026-06-09
- https://smithery.ai/docs — fetched 2026-06-09
- https://smithery.ai/llms.txt — fetched 2026-06-09
- https://pulsemcp.com — fetched 2026-06-09
- https://api.pulsemcp.com — fetched 2026-06-09
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html — fetched 2026-06-09
- https://aws.amazon.com/bedrock/agentcore/ — fetched 2026-06-09
