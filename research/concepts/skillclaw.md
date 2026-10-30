> **Concept:** SkillClaw — Collective Skill Evolution via Local API Proxy and Agentic Evolver
> **Source:** GitHub (`AMAP-ML/SkillClaw`), arXiv 2604.08377
> **Relevance:** Companion to Hermes (and Claude Code, Codex, OpenClaw) that intercepts LLM traffic, injects skills into prompts, and evolves shared skill libraries from real user interactions

*Generated 2026-06-08 / Confidence: High (GitHub source code + README + arXiv abstract)*

---

## 1. Overview

SkillClaw (AMAP-ML, Alibaba) is an open-source skill evolution system. It solves the problem of static post-deployment skills: agent skills typically improve only at training time and stagnate once deployed. SkillClaw treats cross-user, cross-session interaction trajectories as the primary signal for continuously improving shared skill libraries.

**Paper:** arXiv:2604.08377 (Ma et al., 2026)
**Repo:** https://github.com/AMAP-ML/SkillClaw
**License:** MIT

Core claim: enable skills to develop progressively through real interactions, propagating improvements across all users without requiring additional user effort.

---

## 2. Architecture

Two optional components:

```
Client Proxy (port 30000, default)
  ├── Intercepts /v1/chat/completions  (OpenAI-compatible)
  ├── Intercepts /v1/messages           (Anthropic-compatible)
  ├── Injects skills into system prompt before forwarding to upstream LLM
  ├── Records session artifacts
  ├── Deduplicates and improves skills locally
  └── Manages local skill library (skill_manager.py)

Evolve Server (optional, same or separate machine)
  ├── Workflow engine: Summarize → Aggregate → Execute (3-stage LLM pipeline)
  └── Agent engine: OpenClaw-driven workspace for direct skill editing
```

**Deployment models:**
- Single-user local: client proxy only
- With evolution: client proxy + evolve server on same machine
- Team sharing: multiple clients → shared storage (OSS/S3/local) → centralised evolve server

---

## 3. Supported Agent Integrations

SkillClaw configures supported agents to route LLM traffic through its local proxy via `claw_adapter.py`:

| Agent | Adapter mechanism |
|-------|------------------|
| Hermes | Patches `~/.hermes/config.yaml` to point at proxy |
| Claude Code | Patches JSON settings to route Anthropic traffic via proxy |
| Codex | Patches TOML to register SkillClaw as opt-in profile |
| OpenClaw | `openclaw config set` + `openclaw gateway restart` |
| Codex, QwenPaw, IronClaw, PicoClaw, ZeroClaw | Similar config patching |

All agents must use OpenAI-compatible or Anthropic-compatible API endpoints — SkillClaw translates between them.

---

## 4. Skill Format

Skills are SKILL.md files with YAML frontmatter — the same format used by OpenClaw and Hermes:

```yaml
---
name: skill-name
description: what this skill does
category: general          # optional; SkillClaw stores in metadata.skillclaw.category for OpenClaw compat
disable-model-invocation: false   # set true to exclude from automatic injection
---
## Instructions
...
```

Category resolution priority: `metadata.skillclaw.category` → top-level `category` → `"general"`.

---

## 5. Core Skill Operations (`skill_manager.py`)

### Scan
`_load_skills()` — globs for SKILL.md files in `skills_dir`. Uses `**/SKILL.md` (recursive) for Hermes skill roots; `*/SKILL.md` (single-level) for others. Parses YAML frontmatter into in-memory flat collection.

### Search / Retrieve
`retrieve(task_description, top_k=6)` — embedding similarity × effectiveness score ranking. Deduplicates candidates. Falls back to sorting all skills by effectiveness if template mode is active.

### Change Detection
`refresh_if_changed()` — computes fingerprint as `(realpath, mtime_ns, size)` tuples for all SKILL.md files. Returns True and increments generation counter if any file changed.

`reload()` — re-scans directory, rebuilds skill bank, recomputes fingerprint, clears embedding cache.

### Prompt Injection
`format_skills_for_prompt()` / `format_skills_compact()` — builds `<available_skills>` XML catalog. Full version includes descriptions; compact omits them for token efficiency. Injected into system prompt before forwarding.

---

## 6. Remote Skill Catalog (`skill_hub.py`)

Bidirectional sync between local `skills_dir` and shared object store (OSS/S3/local filesystem).

| Operation | Function | Mechanism |
|-----------|----------|-----------|
| List remote | `list_remote()` | Load `manifest.jsonl` from object store |
| Pull | `pull_skills()` | SHA256-based incremental download; backup/restore on failure |
| Push | `push_skills()` | Upload new/changed skills; optional filter |
| Sync | `sync_skills()` | Pull then push |

---

## 7. Validation Worker (`validation_worker.py`)

Background quality verification — disabled by default, only activates when sharing is enabled and local proxy is idle.

**Replay-based comparison method:**
1. Take stored replay cases (previous user tasks)
2. Run against candidate skill AND baseline (current) skill in parallel
3. Score both via PRM scorer (`prm_scorer.py`) — OpenAI-compatible judge using majority voting across 3 parallel evaluations
4. Normalise raw scores to 0–1
5. Accept candidate if: `candidate_mean ≥ threshold AND candidate_mean ≥ baseline_mean`

**Validation criteria assessed:**
- `grounded_in_evidence`
- `preserves_existing_value`
- `specificity_and_reusability`
- `safe_to_publish`

**Server-side publish gate** (`EVOLVE_PUBLISH_MODE=validated`):
```
EVOLVE_VALIDATION_REQUIRED_RESULTS=1
EVOLVE_VALIDATION_REQUIRED_APPROVALS=1
EVOLVE_VALIDATION_MIN_MEAN_SCORE=0.75
EVOLVE_VALIDATION_MAX_REJECTIONS=1
```

---

## 8. CLI

```bash
skillclaw setup               # configure provider and model
skillclaw start --daemon      # activate local proxy (port 30000)
skillclaw skills list-remote  # list skills in shared backend
skillclaw skills pull         # download shared skills
skillclaw skills push         # upload local skills
skillclaw skills sync         # bidirectional sync
skillclaw skills publish <name> <version>  # publish to Nacos registry
skillclaw dashboard sync      # sync dashboard data
skillclaw dashboard serve     # open local UI at http://127.0.0.1:3791
skillclaw validation status   # check validation worker state
skillclaw validation run-once --force
skillclaw doctor hermes       # diagnose Hermes integration
skillclaw restore hermes      # revert Hermes config changes
```

---

## 9. Relationship to Other Systems

| System | Relationship |
|--------|-------------|
| **Hermes** | Primary target agent; SkillClaw patches Hermes config and manages `~/.hermes/skills/` |
| **OpenClaw** | Separate agent framework; SkillClaw has dedicated adapter; shares SKILL.md format |
| **SkillNet** | Independent project (zjunlp, not AMAP). SkillNet = tool knowledge graph for tool selection; SkillClaw = skill evolution from user interactions. Different problem spaces. |
| **AKH** | SkillClaw's proxy model (intercept → inject → record → evolve) is a deployable alternative to a centralised catalog; the validation worker's replay-based PRM scoring is a concrete quality verification mechanism AKH could adopt |

---

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — `format_skills_compact` and `retrieve(top_k=6)` cited as precedent for token-cost display and top-k search (A-4, A-5)

## Sources

- https://github.com/AMAP-ML/SkillClaw — fetched 2026-06-08
- https://arxiv.org/abs/2604.08377 — abstract fetched 2026-06-08
