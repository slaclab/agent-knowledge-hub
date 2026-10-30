# Agent Knowledge Hub — Research

**"I need a management-level summary of what the research concluded"**
→ `CHARGE.md` — browse the questions; each links to its synthesis answer

---

## Concepts

Reference entries — what things are.

| File | Subject | Status | Date |
|------|---------|--------|------|
| [concepts/skillnet.md](concepts/skillnet.md) | SkillNet — architecture, skill schema, 5-dimension eval, relationship ontology | New | 2026-06-05 |
| [concepts/skillclaw.md](concepts/skillclaw.md) | SkillClaw (AMAP-ML) — local API proxy, skill injection, collective evolution, PRM validation | New | 2026-06-08 |
| [concepts/hermes-agent-skills.md](concepts/hermes-agent-skills.md) | Hermes Agent skills subsystem — 8-source search, trust-aware security scan, quarantine install flow, HubLockFile provenance | New | 2026-06-08 |
| [concepts/mcp-registry-landscape.md](concepts/mcp-registry-landscape.md) | MCP Registry Landscape — survey of 5 production registries (Official, Turbo, Smithery, PulseMCP, AWS AgentCore) | New | 2026-06-09 |
| [concepts/open-agent-hub.md](concepts/open-agent-hub.md) | Open Agent Hub — TypeScript CLI linking a curated skill monorepo into 8 assistants' config dirs; no search backend, no ratings | New | 2026-10-16 |
| [concepts/skill-retrieval-mcp.md](concepts/skill-retrieval-mcp.md) | skill-retrieval-mcp — hybrid FTS5+FAISS MCP server for skill search over a 374-skill corpus | New | 2026-10-16 |
| [concepts/plugin4shell.md](concepts/plugin4shell.md) | Plugin4Shell / CVE-2026-86063 — Git SHA-pinning bypass in Claude Code / Codex / Copilot / Gemini CLI plugin installers | New | 2026-10-16 |
| [concepts/agenticskills-find-skills.md](concepts/agenticskills-find-skills.md) | agenticskills.io find-skills — curated third-party skill directory, no rating system | New | 2026-10-16 |
| [concepts/chops.md](concepts/chops.md) | chops — native macOS local file manager for skills already on disk; landscape / low relevance | New | 2026-10-16 |
| [concepts/asm.md](concepts/asm.md) | asm (agent-skill-manager) — cross-provider CLI with pre-install security scanning and registry pinning | New | 2026-10-16 |

---

## Reports

Opinionated analysis and recommendations.

| File | Topic | Status | Date |
|------|-------|--------|------|
| [reports/skillnet-integration.md](reports/skillnet-integration.md) | What to steal from SkillNet for AKH | New | 2026-06-05 |
| [reports/skillnet-scripts-analysis.md](reports/skillnet-scripts-analysis.md) | SkillNet scripts vs AKH components — gaps, steals, defers | New | 2026-06-05 |
| [reports/akh-skillnet-improvements.md](reports/akh-skillnet-improvements.md) | Actionable improvements from SkillNet — quality scoring, rate-limit retry, min_stars filter | New | 2026-06-05 |
| [reports/mcp-registry-for-akh.md](reports/mcp-registry-for-akh.md) | MCP Registry for AKH — what to steal, defer, skip; tool-level indexing gap | New | 2026-06-09 |
| [reports/oct2026-skill-hub-batch-vs-akh.md](reports/oct2026-skill-hub-batch-vs-akh.md) | Oct 2026 skill-hub batch vs AKH — integrate nothing, adopt 8 ideas as AKH code, depend on Claude Code ≥2.1.179 for the marketplace route | New | 2026-10-16 |
