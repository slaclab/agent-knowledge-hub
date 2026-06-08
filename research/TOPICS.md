# Research Topics

| priority | status | type | topic | researched | notes |
|----------|--------|------|-------|------------|-------|
| 🔺 P1 | ✅ done | concept | SkillNet | 2026-06-05 | `concepts/skillnet.md` — core architecture, skill schema, 5-dimension eval, relationship ontology |
| 🔺 P1 | ✅ done | report | SkillNet integration with Agent Knowledge Hub | 2026-06-05 | `reports/skillnet-integration.md` — what to steal, what to defer, what to skip |
| 🔺 P1 | ✅ done | report | SkillNet scripts analysis | 2026-06-05 | `reports/skillnet-scripts-analysis.md` — searcher, downloader, evaluator comparison vs AKH; 5 actionable items |
| 🔺 P1 | ✅ done | report | AKH improvements from SkillNet | 2026-06-05 | `reports/akh-skillnet-improvements.md` — 3 recommendations with implementation detail |
| 🔸 P2 | 🔲 todo | concept | npm / PyPI registry patterns | — | Dependency graphs, SLSA provenance attestation, security advisories, deprecation/unpublish semantics, private mirror support. Directly applicable to skill relationship graph and artifact preservation gap; referenced by `skillnet`, `skillnet-integration` |
| 🔸 P2 | 🔲 todo | report | Discovery UX patterns beyond search | — | Editorial "featured"/"trending" surfaces, category browse, org/team collections, "users also installed" recommendations. Informed by VS Code Marketplace + Hugging Face Hub; referenced by `skillnet`, `skillnet-integration` |
| 🔸 P2 | 🔲 todo | report | Private / mirrored registry support | — | Enterprise IT pattern: curated subsets, internal mirrors, install policy gates. Relevant to `visibility: internal` already in model; referenced by `akh-skillnet-improvements`, `skillnet-scripts-analysis` |
| 🔸 P2 | 🔲 todo | report | Vector/semantic search for skill discovery | — | SkillNet uses vector + keyword search; AKH uses MongoDB text index only. What embedding approach fits our stack? |
| 🔸 P2 | 🔲 todo | concept | Skill relationship graphs in existing catalogs | — | SkillNet: similar_to / belong_to / compose_with / depend_on. How do npm, PyPI, Homebrew handle dependency/relationship graphs? |
| 🔹 P3 | 🔲 todo | concept | VS Code Extension Marketplace | — | Most mature plugin registry for a developer tool — editorial features, publisher trust, install telemetry UX, review gates, in-editor discovery sidebar. Direct comparator for AKH UI layer |
| 🔹 P3 | 🔲 todo | concept | MCP registry landscape (Smithery, mcp.so, mcpservers.com) | — | Emerging MCP server catalog space — schemas, features, trust models. AKH already installs MCP servers; understanding how competition catalogs them is overdue |
| 🔹 P3 | 🔲 todo | concept | Hugging Face Hub | — | Richest metadata model in AI ecosystem — mandatory model card fields, gated access, org/team model, dataset provenance. Study how quality is enforced at metadata schema layer |
| 🔹 P3 | 🔲 todo | report | Skill catalog trust model | — | How mature registries communicate trust at install decision point: publisher verification, install counts, security advisories, content-addressed storage, pre-submission safety gates. Referenced by `skillnet-integration` |
| 🔹 P3 | 🔲 todo | report | Auto-generation of skills from agent execution logs | — | SkillNet creates skills from trajectories/logs. Could AKH auto-generate skill stubs from Claude Code session transcripts? |
| 🔹 P3 | 🔲 todo | concept | Skill quality scoring systems | — | SkillNet 5-dimension scoring vs community stars. Academic literature on software quality dimensions. |

## Backlog

| priority | topic | affects | why it might matter |
|----------|-------|---------|---------------------|
| 🔹 P3 | SkillNet ontology: 10 functional domains | — | Could replace or augment AKH's freeform label system with a taxonomy |
| 🔹 P3 | Cost-awareness metadata for agent skills | — | SkillNet scores API cost overhead; useful for SLAC HPC context |
