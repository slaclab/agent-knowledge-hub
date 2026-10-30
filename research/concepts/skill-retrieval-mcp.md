> **Concept:** skill-retrieval-mcp — Local Hybrid Semantic/Keyword Search over a Curated Skill
> Corpus, Served over MCP
> **Source:** GitHub (`JayCheng113/skill-retrieval-mcp`), PyPI `skill-retrieval-mcp`
> **Relevance:** A shipped, open-source reference implementation of the semantic-search pattern
> already recommended for AKH in reports/skillnet-integration.md §2.3 — and a concrete negative
> case for the "tool-level MCP indexing" gap identified in reports/mcp-registry-for-akh.md

*Generated 2026-10-16 / Confidence: High for architecture and claims directly inspectable in source (README + dev.md); Medium for the self-reported retrieval-eval numbers (transparent methodology, not independently reproduced)*

---

## 1. Overview

skill-retrieval-mcp is an MIT-licensed Python MCP server (PyPI: `skill-retrieval-mcp`) that
provides semantic and keyword search over a licence-vetted corpus of 374 agent skills, served to a
coding agent over the Model Context Protocol. It runs entirely locally, answers in single-digit
milliseconds, and makes zero external API calls by default. It is compatible with Claude Code,
Codex CLI, Gemini CLI, Cursor, OpenClaw, NousResearch's Hermes (the subject of
[concepts/hermes-agent-skills.md](hermes-agent-skills.md)), and any MCP-compatible agent.

**Repo:** https://github.com/JayCheng113/skill-retrieval-mcp — created 2026-03-14, last pushed
2026-08-27, 134 stars, Python.

---

## 2. Retrieval Architecture

Hybrid keyword + vector search, both self-hosted:

- **Keyword:** SQLite with FTS5 virtual tables (exact match — tool names, error messages, CLI
  commands).
- **Semantic:** FAISS `IndexFlatIP` over L2-normalised vectors (cosine similarity via inner
  product).
- **Embedding backend:** default `sentence-transformers/all-MiniLM-L6-v2` — local, free, no API
  key; the pre-built downloadable index is built with this model. Optional backends: OpenAI
  (requires `OPENAI_API_KEY`, index must be rebuilt locally) and Ollama (requires a local Ollama
  instance, index must be rebuilt locally). An index is valid only for the embedding model that
  built it — switching backends requires a full re-embed.
- **Data layout** (default `~/.skill-mcp/`): `config.yaml`, `skills.db` (SQLite+FTS5),
  `index/` (FAISS).

This is the same architectural family as the vector-plus-keyword hybrid claimed for SkillNet
(see [concepts/skillnet.md](skillnet.md) §6), and is the specific pattern already recommended for
AKH in [reports/skillnet-integration.md](../reports/skillnet-integration.md) §2.3 ("embed
`name + description + skill_md_raw`... hybrid BM25+vector... local embedding model"). The
difference is evidentiary: SkillNet's search claims are unverified from available extracts (no
published scoring formula, no inspectable source for the search endpoint; confidence Medium in
that entry). skill-retrieval-mcp's equivalent claims are directly inspectable — the full
implementation, including the retrieval-evaluation harness, is open source.

### MCP tool surface (this project is itself an MCP server with four tools)

| Tool | What it does |
|---|---|
| `search_skills` | Semantic search — natural-language query |
| `keyword_search` | Exact match via FTS5 — tool names, error strings, CLI commands |
| `get_skill` | Fetch full instructions for one skill, called after search narrows candidates |
| `list_categories` | Browse available domains and counts |

**Two-stage design, with an explicit token-economics argument in the README:** search returns
summaries only, not full instructions. Five summaries cost "a few hundred tokens"; one full skill
fetched via `get_skill` costs about 2,400 tokens. By contrast, loading all 374 skill
names-and-descriptions into context up front — the naive lazy-loading approach most skill
frameworks use — costs roughly 37,000 tokens before a single skill has been read; the full
instruction corpus is roughly 960,000 tokens. This figure is a reusable justification for any
summary-first search design, including AKH's own.

---

## 3. Relation to This Corpus's Existing MCP-Indexing Gap Analysis

[reports/mcp-registry-for-akh.md](../reports/mcp-registry-for-akh.md) identifies "The Missing
Layer — Tool-Level Indexing": every MCP server registry surveyed in
[concepts/mcp-registry-landscape.md](mcp-registry-landscape.md) operates at the *server* level —
discovery flow is find a server → connect → call `tools/list` to see what tools it exposes. No
registry indexes individual MCP tool descriptions or input schemas across servers.

**skill-retrieval-mcp does not fill this gap, and the distinction matters.** It indexes `SKILL.md`
documents — markdown instruction packages — not MCP `ToolDefinition` records pulled from other
servers' `tools/list` responses. It is itself an MCP server, but its own tool surface is the fixed
four-tool table above; it never aggregates or searches across *other* MCP servers' tool schemas.
It solves "search across skill instructions," a problem one layer away from "search across MCP
tool schemas," which is what the gap report's proposed `/v0.1/tools/search` endpoint targets.

What *is* directly transferable to that report's design: the two-stage "summaries first, fetch
detail on demand" pattern and the concrete token-cost figures above. The existing report's
`ToolDefinition` embedding proposal does not quantify the token savings it would produce — this
project's numbers are a ready-made justification for the same design choice.

---

## 4. Corpus & Curation Model

374 skills drawn from 8 upstream repositories, each licence read before import:

| Repository | Skills | Licence |
|---|---|---|
| K-Dense-AI/scientific-agent-skills | 163 | MIT |
| google/skills | 112 | Apache-2.0 |
| mattpocock/skills | 35 | MIT |
| addyosmani/agent-skills | 24 | MIT |
| anthropics/skills | 20 | Apache-2.0 |
| obra/superpowers | 14 | MIT |
| kepano/obsidian-skills | 5 | MIT |
| Agents365-ai/drawio-skill | 1 | MIT |

Every skill record carries its source repository, upstream URL, and SPDX licence for traceability.
Median skill length is approximately 9,600 characters — full step-by-step guides, not one-liners.
The documented bar for adding a new source repository is "a licence that permits redistribution,
and evidence the skills actually win queries" — an empirical, retrieval-eval-gated admission
criterion, distinct from editorial/reviewer judgement. This is stricter and more mechanical than
either AKH's own submission model or the editorial triage used by agenticskills.io (see
[concepts/agenticskills-find-skills.md](agenticskills-find-skills.md)).

No per-skill rating or install-count leaderboard exists — unlike the Vercel `skills`/skills.sh
ecosystem referenced in Sources 1 and 3 of this batch, which surfaces install counts prominently.
Trust here comes from licence provenance plus a measured retrieval win-rate, not social proof.

---

## 5. Retrieval Evaluation

*Medium confidence — self-reported, transparent methodology, not independently reproduced.*

43 held-out, in-domain queries, each phrased the way an agent would phrase a task rather than
echoing a skill's own name, evaluated against a set of acceptable answers (not a single gold
label). On the shipped 374-skill corpus: **Recall@1 81.4%, Recall@3 90.7%, Recall@5 90.7%,
MRR 0.853**. The `@3 → @5` step is zero-gain in this eval set — ranks 4 and 5 never supplied a
correct answer, which the project's own `dev.md` flags as what the default `k=5` is "actually
buying." All four misses are attributed to vocabulary gaps (e.g., product-branding terms like
"Agent Platform" versus task phrasing like "fine tune a foundation model") rather than corpus
gaps. The evaluation harness ships in the repository (`dev.md`), which raises confidence above an
unverifiable marketing claim, but no independent or third-party reproduction of these numbers was
found.

---

## 6. Installation & Operational Notes

```bash
pip install "skill-retrieval-mcp[local,hf]"
skill-mcp pull --include-index      # corpus + pre-built vector index from HuggingFace
skill-mcp init                      # detect installed agents, register MCP config
```

`init` writes `.mcp.json`, `~/.gemini/settings.json`, `.cursor/mcp.json`, and
`~/.codex/config.toml` directly; for OpenClaw and Hermes it calls their own `mcp add` command
rather than re-serialising their hand-edited configs (which would drop comments). Two documented
footguns: the registered `command` must be an absolute path, since the agent's `PATH` typically
has not seen the install venv or pipx directory; and `--data-dir` must be spelled out explicitly
and placed before the `serve` subcommand, or the server opens silently on the wrong directory and
answers every search with nothing. 240 tests ship in the repo (`pytest tests/`, ~6s).

---

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — eval-first search and server-side top-k on a trigger (A-5); two-stage design carried into the MCP tool-indexing gap (A-8); token figures reused (A-4); the server and corpus landscape-only (L-3)

Candidate noted at cataloguing: an amendment to
[reports/mcp-registry-for-akh.md](../reports/mcp-registry-for-akh.md)'s "Missing Layer" section,
citing this project's token-cost figures and two-stage search design as a concrete precedent —
without overstating it as a solution to the MCP tool-indexing gap, which it does not address.

---

## Sources

- https://github.com/JayCheng113/skill-retrieval-mcp (README.md) — fetched 2026-10-16
- https://github.com/JayCheng113/skill-retrieval-mcp (dev.md) — fetched 2026-10-16
- https://api.github.com/repos/JayCheng113/skill-retrieval-mcp — fetched 2026-10-16
- WebSearch "github JayCheng113 skill-retrieval-mcp" — fetched 2026-10-16 (independent
  corroboration of architecture and corpus claims)
