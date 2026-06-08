---
charge: 1
question: What is SkillNet and what can we learn from it?
status: Answered
primary_sources:
  - concepts/skillnet.md
  - reports/skillnet-integration.md
updated: 2026-06-05
---

# Charge 1: What is SkillNet and what can we learn from it?

**Status:** Answered

---

## Direct Answer

SkillNet is a published academic system (arXiv 2603.04448, ZJUNLP group) that is structurally the same thing as Agent Knowledge Hub — a catalog and install manager for AI agent skills in SKILL.md format — but with three ideas we don't yet have: **structured quality scoring**, **a typed relationship graph between skills**, and **vector/semantic search**. The quality scoring and relationship graph are the highest-leverage things to steal; both are additive with low risk and directly unblock open todos (#006 skillsets, #014 provenance tree).

---

## Key Findings

**1. SkillNet and AKH use the same base format.** Both use SKILL.md files with frontmatter (`name`, `description`) as the unit of capability. SkillNet formalised this independently; it validates our design direction.
[→ concepts/skillnet.md §2. Skill Representation]

**2. SkillNet's 5-dimension quality scoring fills the gap community stars don't.** Stars measure popularity; the five dimensions (Safety, Completeness, Executability, Maintainability, Cost-awareness) measure intrinsic quality. Their benchmarks show ~40% better agent outcomes from quality-scored skills.
[→ concepts/skillnet.md §4. Five-Dimension Evaluation Scoring]
[→ reports/skillnet-integration.md §2.1]

**3. The typed relationship graph is the most architecturally novel idea.** Four edge types (`similar_to`, `belong_to`, `compose_with`, `depend_on`) let agents discover pipelines, prerequisites, and alternatives automatically. This is not just a nice-to-have: it directly enables skillsets (#006) and the provenance tree (#014) without building a separate top-level concept.
[→ concepts/skillnet.md §5. Skill Relationship Ontology]
[→ reports/skillnet-integration.md §2.2]

**4. Semantic search is the obvious infrastructure gap.** AKH uses MongoDB text index (token matching); SkillNet uses hybrid keyword + vector search. At current scale this is fine; at 50+ skills the gap becomes user-visible.
[→ reports/skillnet-integration.md §2.3]

**5. Auto-generation from agent logs is interesting but expensive.** SkillNet can ingest session trajectories and produce skill stubs. For AKH this would lower the contribution barrier significantly but requires a dedicated planning cycle.
[→ reports/skillnet-integration.md §2.4]

**6. AKH is ahead where it matters for a trusted domain catalog.** SkillNet has no auth, no moderation, no version pinning, no flags. AKH's trust model (auth, flags, admin deactivation, pinned commits) is a feature, not a gap.
[→ reports/skillnet-integration.md §1. Where We Are Now vs SkillNet]

---

## Recommended Action

Implement in this order:

1. **Five-dimension quality score** — `quality_scores` field on `Skill` model, manual checklist on submit, badge on detail page
2. **Typed skill relations** — `SkillRelation` collection + `plugin.json["relations"]` parser + `/api/skills/<slug>/relations` endpoint; unblocks skillsets
3. **Functional category taxonomy** — single `category` field + LLM classification at scan time; powers browse UX
4. **Semantic search** — defer to ~50+ skills
5. **Log-based skill extraction** — backlog

---

## Residual Open Questions

1. Should quality scores be author-declared or system-computed? (Gameable vs expensive)
2. Should `similar_to` edges be inferred by the system from embedding similarity rather than author-declared?
3. What taxonomy categories fit SLAC S3DF workloads specifically?
4. Which vector search backend fits our MongoDB deployment (Atlas vs self-hosted)?
