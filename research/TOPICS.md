# Research Topics

| priority | status | type | topic | researched | notes |
|----------|--------|------|-------|------------|-------|
| 🔹 P3 | ✅ done | concept | SkillNet | 2026-06-05 | `concepts/skillnet.md` — core architecture, skill schema, 5-dimension eval, relationship ontology |
| 🔹 P3 | ✅ done | report | SkillNet integration with Agent Knowledge Hub | 2026-06-05 | `reports/skillnet-integration.md` — what to steal, what to defer, what to skip |
| 🔹 P3 | ✅ done | report | SkillNet scripts analysis | 2026-06-05 | `reports/skillnet-scripts-analysis.md` — searcher, downloader, evaluator comparison vs AKH; 5 actionable items |
| 🔹 P3 | ✅ done | report | AKH improvements from SkillNet | 2026-06-05 | `reports/akh-skillnet-improvements.md` — 3 recommendations with implementation detail |
| 🔹 P3 | ✅ done | concept | SkillClaw (AMAP-ML) | 2026-06-08 | `concepts/skillclaw.md` — proxy intercept + skill injection + evolution; validation_worker PRM scoring; Hermes/Claude Code/Codex adapters |
| 🔹 P3 | ✅ done | concept | Hermes agent skill search/scan/verify | 2026-06-08 | `concepts/hermes-agent-skills.md` — 8-source search, trust-aware security scan (skills_guard.py, 6 threat categories), quarantine→install flow, HubLockFile provenance |
| 🔺 P1 | 🔲 todo | concept | npm / PyPI registry patterns | — | Dependency graphs, SLSA provenance attestation, security advisories, deprecation/unpublish semantics, private mirror support. Directly applicable to skill relationship graph and artifact preservation gap; referenced by `skillnet`, `skillnet-integration` |
| 🔺 P1 | 🔲 todo | report | Discovery UX patterns beyond search | — | Editorial "featured"/"trending" surfaces, category browse, org/team collections, "users also installed" recommendations. Informed by VS Code Marketplace + Hugging Face Hub; referenced by `skillnet`, `skillnet-integration` |
| 🔹 P3 | 🔲 todo | report | Private / mirrored registry support | — | Enterprise IT pattern: curated subsets, internal mirrors, install policy gates. Relevant to `visibility: internal` already in model; referenced by `akh-skillnet-improvements`, `skillnet-scripts-analysis` |
| 🔹 P3 | 🔲 todo | report | Vector/semantic search for skill discovery | — | SkillNet uses vector + keyword search; AKH uses MongoDB text index only. What embedding approach fits our stack? |
| 🔹 P3 | 🔲 todo | concept | Skill relationship graphs in existing catalogs | — | SkillNet: similar_to / belong_to / compose_with / depend_on. How do npm, PyPI, Homebrew handle dependency/relationship graphs? |
| 🔹 P3 | 🔲 todo | concept | VS Code Extension Marketplace | — | Most mature plugin registry for a developer tool — editorial features, publisher trust, install telemetry UX, review gates, in-editor discovery sidebar. Direct comparator for AKH UI layer |
| 🔹 P3 | ✅ done | concept | MCP registry landscape (Smithery, mcp.so, mcpservers.com) | 2026-06-09 | `concepts/mcp-registry-landscape.md` — survey of 5 registries; tool-level indexing gap identified. Report: `reports/mcp-registry-for-akh.md` |
| 🔸 P2 | 🔲 todo | report | Tool-level MCP indexing design | — | AKH-original recommendation: embed individual tool descriptions across all servers for semantic search. No existing registry does this. Identified in `reports/mcp-registry-for-akh.md` |
| 🔹 P3 | 🔲 todo | concept | Hugging Face Hub | — | Richest metadata model in AI ecosystem — mandatory model card fields, gated access, org/team model, dataset provenance. Study how quality is enforced at metadata schema layer |
| 🔸 P2 | 🔲 todo | report | Skill catalog trust model | — | How mature registries communicate trust at install decision point: publisher verification, install counts, security advisories, content-addressed storage, pre-submission safety gates. Referenced by `skillnet-integration` |
| 🔹 P3 | 🔲 todo | report | Auto-generation of skills from agent execution logs | — | SkillNet creates skills from trajectories/logs. Could AKH auto-generate skill stubs from Claude Code session transcripts? |
| 🔹 P3 | 🔲 todo | concept | Skill quality scoring systems | — | SkillNet 5-dimension scoring vs community stars. Academic literature on software quality dimensions. |

## Backlog

| priority | topic | affects | why it might matter |
|----------|-------|---------|---------------------|
| 🔹 P3 | SkillNet ontology: 10 functional domains | — | Could replace or augment AKH's freeform label system with a taxonomy |
| 🔹 P3 | Cost-awareness metadata for agent skills | — | SkillNet scores API cost overhead; useful for SLAC HPC context |
