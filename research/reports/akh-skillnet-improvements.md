# AKH Improvements from SkillNet Scripts — Recommendations Report

> **Type:** Report
> **Concept References:** [SkillNet](../concepts/skillnet.md)
> **Prior analysis:** [skillnet-scripts-analysis.md](skillnet-scripts-analysis.md), [skillnet-integration.md](skillnet-integration.md)

*Generated: 2026-06-05 | Confidence: High (first-party codebase read + SkillNet source retrieved)*

---

## Executive Summary

Comparing SkillNet's `skillnet-ai` Python scripts against our own backend surfaces three actionable improvements, ordered by value-to-effort ratio. The highest-leverage steal is the **five-dimension quality scoring rubric** from `evaluator.py`/`prompts.py`: we can lift the exact criteria verbatim, call a fast LLM at scan time, and store structured quality scores on the `Skill` model with roughly 50 lines of new code — no external infrastructure needed. The second item is a **one-line fix to `github.py`** that reads `X-RateLimit-Reset` and sleeps before retrying in background scan jobs, replacing our current hard-fail behaviour. The third is a **`min_stars` filter on `GET /api/skills`**, a one-liner that mirrors SkillNet's search API. Everything else in their toolkit is either already covered by our implementation or requires infrastructure we should defer.

---

## Background

SkillNet ships a Python SDK (`skillnet-ai`) with five modules: `searcher.py`, `downloader.py`, `evaluator.py`, `analyzer.py`, and `creator.py`. The question was whether any of these scripts contain logic, patterns, or rubrics we could apply directly to AKH's backend or install flow. After reading all five against our own `github.py`, `scanner.py`, `services/skill.py`, `services/search.py`, and `routers/skills.py`, three concrete improvements emerged. The others were either inferior to our current implementation or require capabilities (vector DB, sandboxed script execution) that aren't in scope yet.

---

## Item 1: Five-Dimension Quality Scoring

### The gap

AKH has community star ratings (1–5, averaged). Stars measure popularity, not quality. A skill can have five stars and still be vague, unsafe, or unmaintainable. SkillNet addresses this with a structured LLM-assisted scorecard evaluated on five independent dimensions. We have nothing equivalent.

### What to steal

The rubric from `prompts.py` is the entire asset — no infrastructure needs to be copied. The five dimensions and their criteria:

| Dimension | Good | Average | Poor |
|---|---|---|---|
| **Safety** | No destructive defaults; explicit safety checks; medical skills carry disclaimers | Benign domain, safeguards unnecessary | Dangerous operations without protection |
| **Completeness** | Goals, steps, inputs/outputs, and edge cases all stated | Details underspecified | Too vague to act on; formula/algorithm errors present |
| **Executability** | Concrete, actionable steps — instruction-only skills count if guidance is unambiguous | Steps are ambiguous | Lacks operational detail entirely |
| **Maintainability** | Narrow scope, clear I/O boundaries, composable without breaking dependents | Boundaries unclear | Tightly coupled; trivial placeholder content |
| **Cost-Awareness** | Explicit efficiency controls (batching, limits, caching) where workload is heavy | No mention, but behaviour not wasteful | Encourages unbounded/wasteful execution |

Each dimension returns `{"level": "Good"|"Average"|"Poor", "reason": "<evidence from the SKILL.md>"}`.

### Implementation

**Step 1 — Add field to `Skill` model** (`backend/app/models/skill.py`):

```python
quality_scores: Optional[Dict[str, str]] = None   # {"safety": "Good", ...}
quality_scores_reason: Optional[Dict[str, str]] = None  # per-dimension rationale
quality_scored_at: Optional[datetime] = None
```

No migration needed — Beanie/MongoDB adds the field lazily on next write.

**Step 2 — Score at scan time** (`backend/app/services/scanner.py` or a new `services/evaluator.py`):

After `skill_md_raw` is populated by any scanner (GitHub or local), call a fast LLM:

```python
EVAL_PROMPT = """
You are evaluating an AI agent skill. Rate the SKILL.md below on five dimensions.
For each dimension return JSON: {"level": "Good"|"Average"|"Poor", "reason": "<1 sentence>"}

Dimensions and criteria:
- safety: ...        (rubric from above)
- completeness: ...
- executability: ...
- maintainability: ...
- cost_awareness: ...

SKILL.md:
{skill_md_raw}

Return a single JSON object with keys: safety, completeness, executability,
maintainability, cost_awareness. No prose outside the JSON.
"""
```

Model choice: any fast/cheap model (Claude Haiku, Gemma 3, GPT-4o-mini). Cost at current catalog scale: negligible. Parse with `json.loads`; fall back to `json_repair` on malformed output (same pattern SkillNet uses).

**Step 3 — Expose in schemas** (`backend/app/schemas/skill.py`):

Add `quality_scores` and `quality_scored_at` to `SkillOut`. Add a compact summary (count of "Good" dimensions) to `SkillListOut` for the catalog list view.

**Step 4 — Display in frontend**: badge row on skill detail page, sortable/filterable column in catalog (deferred to a subsequent PR).

### Why not author self-scoring?

Author-declared scores are gameable and create a false signal. System-computed scores from a neutral LLM are reproducible and updatable on every refetch. We can add an author-suggested score later as an override signal if needed, but start with the system-computed path.

---

## Item 2: Rate-Limit Resilience in `github.py`

### The gap

When GitHub returns HTTP 403 with `X-RateLimit-Remaining: 0`, our current behaviour in `github.py` is:

```python
if repo_status == 403:
    raise GitHubFetchError("GitHub rate limit reached. Wait a moment and try again.")
```

This is correct for user-facing API endpoints (a 503 is the right UX). But for **background scan jobs** — `POST /api/skills/{slug}/refetch`, the scanner loop, any future batch ingestion — it causes an unnecessary task failure that requires manual retry.

SkillNet's `_request_with_retry` reads `X-RateLimit-Reset` and sleeps until the reset timestamp:

```python
reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
wait_seconds = max(0, reset_time - int(time.time()))
time.sleep(wait_seconds + 1)
continue  # retry once
```

### Implementation

Add a helper in `github.py`:

```python
async def _wait_for_rate_limit_reset(response: httpx.Response, cap_seconds: int = 65) -> None:
    reset_ts = response.headers.get("X-RateLimit-Reset")
    if reset_ts:
        wait = max(0, int(reset_ts) - int(time.time())) + 1
        await asyncio.sleep(min(wait, cap_seconds))
```

Call it in the GitHub fetcher on 403 responses **only when executing in a background context** (refetch, scan). Raise immediately as before on the user-facing create/preview paths. A boolean parameter `background: bool = False` on the fetcher method is the cleanest toggle, or check a context var.

The 65-second cap prevents pathological waits if `X-RateLimit-Reset` is far in the future (e.g. app token exhaustion vs PAT exhaustion).

### Scope constraint

Do **not** apply this to `GET /api/github-preview` or `POST /api/skills` (user-facing). The request timeout on user paths is already 10 seconds; sleeping 60+ seconds would hang the response. Background-only.

---

## Item 3: `min_stars` Filter on `GET /api/skills`

### The gap

SkillNet's search API exposes `min_stars: int = 0` as a query param. We have `sort=most_stars` but no way to exclude low-star skills from results. For a curated domain catalog this is low priority, but it costs almost nothing to add and covers the "show me only well-regarded skills" use case.

### Implementation

**Router** (`backend/app/routers/skills.py`):

```python
min_stars: Optional[int] = Query(None, ge=0, description="Minimum GitHub stars filter"),
```

Pass through to `skill_repository.list_with_cursors(min_stars=min_stars)`.

**Service** (`backend/app/services/skill.py`) — add to the Beanie query filter:

```python
if min_stars is not None:
    filters.append(Skill.github_stars >= min_stars)
```

**Note:** `github_stars` is nullable on local/private skills. Treat `None` as 0 for filter purposes, or exclude null-star skills from `min_stars` results (the latter is more conservative and avoids surfacing unscored private skills).

---

## What to Defer

| SkillNet feature | Why defer |
|---|---|
| `mode=vector` semantic search | Requires Atlas Vector Search or Qdrant sidecar; not warranted until catalog is 50+ skills |
| `category` filter | Only makes sense after a fixed taxonomy is introduced (see integration report §2.5) |
| Sandboxed script execution (evaluator) | Heavy infra (container isolation); the LLM rubric alone provides most of the value |
| Mirror URL support (`GITHUB_MIRROR`) | SLAC has direct GitHub access; adds complexity for no benefit |
| `analyzer.py` (relationship inference) | Covered by the typed relationship graph todo (#006-skillsets path); different approach |
| `creator.py` (skill generation from logs) | High effort, own planning cycle needed |

---

## Recommendations

1. **Implement five-dimension quality scoring** — add `quality_scores` to `Skill`, score from `skill_md_raw` using the SkillNet rubric at every scan/refetch. Expose in `SkillOut`. Single PR; ~50 lines of new production code plus tests. This is the highest-value steal from the entire SkillNet codebase.

2. **Add `X-RateLimit-Reset` retry in `github.py` for background paths** — prevents unnecessary task failures on scan jobs. Isolated change; no user-facing behaviour changes. One-liner addition with a cap.

3. **Add `min_stars` filter to `GET /api/skills`** — one param in router, one condition in service query builder. Low effort; rounds out the search API.

---

## Trade-offs & Risks

| Option | Benefit | Risk |
|---|---|---|
| LLM scoring at scan time (Item 1) | Automated, reproducible, no human bottleneck | LLM cost at scale; possible drift in scoring as model versions change; prompt needs versioning |
| Author self-score (alternative to Item 1) | Zero infra, zero cost | Gameable; no consistency across submitters |
| Sleep-on-reset for all paths (Item 2, wider scope) | Fewer total failures | Would silently hang user-facing requests for up to 60s; unacceptable UX |
| Skip `min_stars` (Item 3) | Simpler | Marginal; catalog is small enough that all results are visible anyway |

---

## Open Questions

1. **Prompt versioning for quality scores:** if the LLM scoring prompt changes, existing scores become inconsistent. Should `quality_scored_at` be enough to track staleness, or do we need a `quality_scores_prompt_version` field?
2. **Score visibility for private/internal skills:** should quality scores be visible to unauthenticated users even when `skill_md_raw` is withheld? Currently `skill_md_raw` is omitted for `internal` visibility without auth — the score itself could be shown without leaking content.
3. **`min_stars` and null handling:** exclude null-star skills from `min_stars > 0` results (conservative, correct for local/private skills), or treat null as 0 (inclusive)? Recommend exclude-null.
4. **Rate-limit cap:** 65 seconds is chosen to cover a full GitHub PAT reset window. Is this acceptable latency for background scan jobs, or should we log and skip instead of sleeping?

---

## Sources

- `backend/app/services/github.py` — read 2026-06-05
- `backend/app/services/scanner.py` — read 2026-06-05
- `backend/app/services/skill.py` — read 2026-06-05
- `backend/app/services/search.py` — read 2026-06-05
- `backend/app/routers/skills.py` — read 2026-06-05
- `backend/app/models/skill.py` — read 2026-06-05
- [skillnet-scripts-analysis.md](skillnet-scripts-analysis.md) — prior analysis 2026-06-05
- [skillnet-integration.md](skillnet-integration.md) — prior analysis 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/evaluator.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/prompts.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/downloader.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/searcher.py — fetched 2026-06-05
