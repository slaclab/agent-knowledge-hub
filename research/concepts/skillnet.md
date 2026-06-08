> **Concept:** SkillNet — Open Infrastructure for Creating, Evaluating, and Connecting AI Agent Skills
> **Source:** GitHub (`zjunlp/SkillNet`), arXiv 2603.04448, official website `skillnet.openkg.cn`
> **Relevance:** Direct comparator and inspiration source for Agent Knowledge Hub

*Generated 2026-06-05 / Confidence: Medium (GitHub README + arXiv HTML — full PDF not retrieved)*

---

## 1. Overview

SkillNet is an open-source platform that packages AI agent capabilities as reusable, shareable, versioned units ("skills") — described by its authors as "npm for AI functionalities." It combines a community repository (200,000–500,000 skills), a Python toolkit for skill lifecycle management, and a web platform for browse/search/install workflows.

**Paper:** arXiv:2603.04448 (Zhuang et al., ZJUNLP group)
**Repo:** https://github.com/zjunlp/SkillNet
**Website:** http://skillnet.openkg.cn/

---

## 2. Skill Representation

A skill is a structured directory with:

- `SKILL.md` — frontmatter (`name`, `description`) + instruction body; the executable unit read by the agent at runtime
- Optional supporting files: scripts, templates, configs

This is structurally identical to the Agent Knowledge Hub's own SKILL.md convention. SkillNet formalises it further with a unified schema but the ground-level format is the same.

---

## 3. Skill Creation Pipeline

Four ingestion sources feed the creation pipeline:

| Source | Description |
|--------|-------------|
| Execution trajectories / logs | Agent session recordings → skill extraction |
| GitHub repositories | Scan repo for skill-like patterns |
| Semi-structured documents | PDF, PowerPoint, Word → parse into skill format |
| Natural language prompts | LLM-assisted generation from a description |

Multi-stage curation: deduplication → rule-based filter → model-based filter → categorisation (10 functional domains) → evaluation scoring → consolidation.

---

## 4. Five-Dimension Evaluation Scoring

Each skill is rated Good / Average / Poor on five dimensions:

| Dimension | What it measures |
|-----------|-----------------|
| **Safety** | Hazardous operations, adversarial robustness |
| **Completeness** | Procedural steps, prerequisites, execution constraints present |
| **Executability** | Successful agent implementation in sandboxed environments |
| **Maintainability** | Modularity, composability without breaking dependencies |
| **Cost-awareness** | Time latency, computational resource consumption, API usage costs |

No numerical formula published in available extracts; scoring appears LLM-assisted with structured rubrics. Results reported as pass/fail per dimension.

---

## 5. Skill Relationship Ontology

SkillNet defines four typed edges between skills:

| Relationship | Semantics |
|---|---|
| `similar_to` | Functionally equivalent tasks (candidate deduplication, alternatives) |
| `belong_to` | Sub-component within a larger workflow (part-of / hierarchy) |
| `compose_with` | Frequently co-invoked skills with data dependency (pipeline composition) |
| `depend_on` | Prerequisite skill required for execution (hard dependency) |

These form a graph that agents traverse at install-time and at query-time to discover related capabilities.

---

## 6. Search & Discovery

- **Keyword search:** traditional token matching
- **Vector/semantic search:** embedding-based similarity retrieval
- **API endpoint:** `http://api-skillnet.openkg.cn/v1/search`
- **Auto-discovery:** the relationship graph surfaces related skills automatically (compose candidates, prerequisites, alternatives)

---

## 7. Platform Integrations

Stated integrations: OpenClaw, Claude Code, Codex CLI, MCP (Model Context Protocol) servers. This makes it a direct comparator to AKH's multi-platform install flow.

---

## 8. Benchmark Results

Evaluated on ALFWorld, WebShop, ScienceWorld environments:

- ~40% improvement in average rewards vs ReAct baseline
- ~30% reduction in interaction steps
- Tested across DeepSeek V3.2, Gemini 2.5 Pro, o4 Mini

Significance: skill reuse measurably accelerates agents — not just a convenience feature.

---

## Applied in

- [reports/skillnet-integration.md](../reports/skillnet-integration.md) — what to steal for AKH

## Sources

- https://github.com/zjunlp/SkillNet — fetched 2026-06-05
- https://arxiv.org/html/2603.04448 — fetched 2026-06-05
- https://arxiv.org/abs/2603.04448 — abstract only, fetched 2026-06-05
