> **Report:** SkillNet — What to Steal for Agent Knowledge Hub
> **Addressed to:** AKH development team
> **Date:** 2026-06-05

*Confidence: Medium (GitHub README + arXiv HTML; full paper PDF not retrieved — scoring formula details remain approximate)*

---

## Executive Summary

SkillNet is the closest published comparator to Agent Knowledge Hub: same SKILL.md format, same install-from-GitHub model, same multi-platform ambition (Claude Code, Codex, MCP). Where AKH is ahead in auth, moderation, and version pinning, SkillNet is ahead in three areas worth stealing: **structured quality scoring**, **a typed relationship graph between skills**, and **auto-generation of skills from agent execution logs**. A fourth idea — semantic/vector search — is low-hanging fruit that replaces our current MongoDB text-only index with meaningfully better discovery. None of these require architectural overhaul; they are additive.

---

## 1. Where We Are Now vs SkillNet

| Feature | AKH (current) | SkillNet |
|---|---|---|
| Skill format | SKILL.md + plugin.json | SKILL.md (same) |
| Install from GitHub | ✅ + version pinning | ✅ no pinning |
| Multi-platform | ✅ claude-code + codex | ✅ claude-code + codex + MCP |
| Community ratings | ✅ 1–5 stars, avg_rating | ❌ |
| Moderation / flags | ✅ | ❌ |
| Auth / user accounts | ✅ | ❌ |
| Quality scoring | ❌ freeform | ✅ 5-dimension rubric |
| Skill relationships | ❌ | ✅ similar_to / depend_on / compose_with / belong_to |
| Semantic search | ❌ MongoDB text index | ✅ vector + keyword |
| Auto-generation from logs | ❌ | ✅ trajectory → skill |
| Scale | ~dozens of skills | 200k–500k skills |
| Functional taxonomy | ❌ freeform labels | ✅ 10 domain categories |

---

## 2. Recommendations

### 2.1 Steal: Five-Dimension Quality Score (High value, low effort)

**What:** Add a structured quality scorecard to each skill: Safety, Completeness, Executability, Maintainability, Cost-awareness — each rated Poor / Average / Good.

**Why it matters for AKH:** Community stars tell you *popularity*, not *quality*. A skill with 5 stars might be incomplete or unsafe. SkillNet's benchmarks show that quality-scored skills produce 40% better agent outcomes. Even a manual initial scoring (checklist on submit) captures most of the value before investing in LLM-assisted auto-scoring.

**How to integrate:**
- Add `quality_scores: dict[str, str]` to the `Skill` model (5 keys → "good" | "average" | "poor" | null)
- Display as a badge row on the skill detail page — not buried in metadata
- Gate the score on submission (checklist in the submit flow) or compute it server-side from SKILL.md content analysis
- The `Executability` dimension is the most valuable: "does this skill actually work in a sandbox?" — even a boolean tested field adds signal

**Effort:** Low for model + schema. Medium for UI. High for auto-scoring (defer that).

---

### 2.2 Steal: Typed Skill Relationship Graph (High value, medium effort)

**What:** Let skills declare relationships to other skills: `depend_on`, `compose_with`, `similar_to`, `belong_to`.

**Why it matters for AKH:** Discovery today is search → install. The relationship graph enables:
- "Skills that work well with this one" (compose_with → pipeline suggestions)
- "Skills this one needs first" (depend_on → auto-dependency install)
- "Alternative/duplicate skills" (similar_to → deduplication UX, deactivation suggestions)
- "Sub-skills of a workflow" (belong_to → skill bundles / skillsets)

This directly unblocks todo/006-skillsets.md — skillsets become a named set of `compose_with` edges rather than a new top-level concept.

**How to integrate:**
- Add a `SkillRelation` collection: `{ from_slug, to_slug, relation_type: similar_to | depend_on | compose_with | belong_to, created_by: "author" | "system" }`
- Author-declared: in `plugin.json["relations"]` array, parsed at scan time
- System-inferred: LLM-assisted from SKILL.md content similarity (defer to after manual declaration works)
- Expose as `/api/skills/<slug>/relations` endpoint
- Frontend: "Related skills" section on the detail page

**Effort:** Medium — new collection, scan-time parser, one API endpoint, one UI section.

---

### 2.3 Steal: Semantic / Vector Search (Medium value, low-medium effort)

**What:** Supplement or replace MongoDB text index with embedding-based vector search.

**Why it matters for AKH:** "Find me a skill for X" natural-language queries are the primary discovery path. MongoDB `$text` does exact token matching — it misses synonyms, related concepts, and intent. SkillNet uses vector search as a first-class path alongside keyword matching. The `/agent-knowledge-hub search` flow already passes the full catalog to Claude for re-ranking, which compensates somewhat — but at scale (100s of skills) that approach becomes expensive and slow.

**How to integrate:**
- Embed `name + description + skill_md_raw` at scan/create time using a fast embedding model (text-embedding-3-small or nomic-embed-text locally)
- Store vectors in MongoDB Atlas Vector Search (already available if on Atlas) or add pgvector/Qdrant as a sidecar
- Hybrid search: BM25 keyword + vector cosine similarity, score fusion
- The `/api/skills/summary` endpoint response could include an embedding-friendly compact representation

**Effort:** Low-medium if on Atlas (Atlas Vector Search is turnkey). Medium if self-hosted (Qdrant sidecar).

**Caveat:** Given the current skill count is small, defer until the catalog has 50+ skills where MongoDB text search noticeably degrades. Medium priority.

---

### 2.4 Consider: Auto-generate skill stubs from Claude Code session logs (Low-medium value, high effort)

**What:** SkillNet can ingest agent execution trajectories (session recordings/logs) and generate skill stubs from them.

**Why it matters for AKH:** A user who repeatedly does the same multi-step workflow in Claude Code could click "save as skill" and get a SKILL.md stub pre-filled from their session transcript. This lowers the contribution barrier dramatically — the hardest part of contributing is writing the initial SKILL.md from scratch.

**How to integrate:**
- Add a `/agent-knowledge-hub extract` command that reads recent Claude Code session transcript (`.claude/sessions/`) and sends it to an LLM endpoint to extract a SKILL.md stub
- The stub goes through the normal validate → submit flow
- Server-side: `/api/skills/extract` endpoint that takes a transcript blob and returns a `SkillCreate` pre-filled

**Effort:** High — requires transcript parsing, prompt engineering, quality filtering, and UX. Worth a dedicated todo.

**Defer:** Add to backlog, not next sprint.

---

### 2.5 Consider: Functional Taxonomy (10 domain categories) to complement freeform labels

**What:** SkillNet categorises all skills into 10 functional domains during curation.

**Why it matters for AKH:** Freeform labels (todo/003-label-ux.md) give flexibility but no browse-by-category UX. A fixed top-level taxonomy (e.g. Data Processing, DevOps, Research, Communication, Code Generation, etc.) could sit above labels and power a "Browse by category" homepage section.

**How to integrate:** Add an optional `category` field to the skill model; populate via LLM classification at scan time. Expose as a filter in the catalog list.

**Effort:** Low for model field + LLM classification. Medium for UI. Can be done alongside label improvements.

---

## 3. What NOT to steal

| SkillNet feature | Why skip / defer for AKH |
|---|---|
| 200k+ skill scale | AKH is a curated domain catalog, not a public npm-scale repo. Curation is a feature. |
| Full LLM-assisted auto-scoring pipeline | Requires sandboxed execution infrastructure. High cost for marginal gain over a manual checklist at current scale. |
| PDF/PowerPoint/Word ingestion | Not a relevant source type for SLAC S3DF skills. |
| Community-contributed mass creation | AKH intentionally gates submissions; open mass creation contradicts the trust model. |

---

## 4. Sequencing

Recommended order based on value/effort ratio:

1. **Five-dimension quality score** — add to model + submit flow (manual checklist first, LLM-assisted later). Closes a gap that community ratings don't cover.
2. **Typed skill relations** — `plugin.json["relations"]` + `/api/skills/<slug>/relations` endpoint. Directly unblocks skillsets (#006) and provenance tree (#014).
3. **Functional taxonomy** — single `category` field, LLM-classified at scan time. Powers browse UX.
4. **Semantic search** — defer until catalog reaches ~50+ skills and discovery quality degrades.
5. **Log-based skill extraction** — backlog; high effort, novel UX, requires dedicated planning cycle.

---

## Open Questions

1. **Scoring subjectivity:** SkillNet's dimension scores are LLM-assigned — inter-rater reliability is unknown. Should AKH scores be author-declared (cheap, gameable) or system-computed (expensive, more trustworthy)?
2. **Relation authorship:** author-declared relations in `plugin.json` are biased (authors won't list better alternatives). Should the system infer `similar_to` edges from embedding similarity and surface them without author input?
3. **Taxonomy fit:** SkillNet's 10 domains are not published in available extracts. What categories actually fit SLAC S3DF workloads? Needs a domain expert pass.
4. **Vector search backend:** Atlas Vector Search vs Qdrant vs local embedding + brute-force cosine at small scale — the right answer depends on whether we're on Atlas or self-hosted MongoDB.

---

## Concept References

- [concepts/skillnet.md](../concepts/skillnet.md) — SkillNet architecture reference

## Sources

- https://github.com/zjunlp/SkillNet — fetched 2026-06-05
- https://arxiv.org/html/2603.04448 — fetched 2026-06-05
