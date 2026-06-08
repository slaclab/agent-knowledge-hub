> **Report:** SkillNet Scripts — Applicability to AKH Components
> **Addressed to:** AKH development team
> **Date:** 2026-06-05

*Confidence: Medium-High (GitHub source + raw file fetches; evaluator prompt template retrieved verbatim)*

---

## Executive Summary

SkillNet's Python toolkit (`skillnet-ai`) has four scripts of interest: `searcher.py`, `downloader.py`, `evaluator.py`, and `models.py`. After comparing against our own backend, the verdict is: **two gaps worth closing now** (rate-limit header handling in our GitHub fetcher, and the min_stars/threshold search params in our API), **one major feature to plan** (the evaluator prompt rubric — steal it directly for our quality scoring todo), and **one thing where we are already strictly better** (downloader — our scanner is more capable; the SkillNet downloader is naïve by comparison). Nothing in their toolkit requires importing their code; these are idea-lifts, not dependency additions.

---

## 1. `searcher.py` — Keyword + Vector Modes

### What they have

```
GET /v1/search?q=...&mode=keyword|vector&category=...&limit=...
                &page=...&min_stars=0&sort_by=stars|recent   (keyword)
                &threshold=0.8                               (vector)
```

- Dual-mode: keyword (paginated, min_stars filter, sort_by stars/recent) vs vector (similarity threshold)
- `category` filter across both modes
- Clean None-stripping before sending params
- 15s timeout

### What we have

Our `GET /api/skills` supports: `q`, `sort` (newest/highest_rated/most_rated/most_stars), `page`, `page_size`, `labels`, `visibility`, `platforms`, `submitted_by`, `cursor`, `forked_from`.

Our `search.py` has `name_boost()` (exact name/slug prepend) and a dead-letter `build_atlas_pipeline()` (Atlas-only, unused on PSMDB).

### Gaps worth closing

**`min_stars` filter** — SkillNet exposes `min_stars` as a first-class search param. We have `sort=most_stars` but no way to *filter out* low-star results. For a curated catalog this is low priority, but it's a one-line addition to `list_skills()` and `skill_repository.list_with_cursors()` if wanted.

**`mode=vector` / `threshold`** — we have no vector search at all. This maps to the ADR-U34 dead-letter `build_atlas_pipeline`. Not worth closing until we're on Atlas or add a vector sidecar (see `research/reports/skillnet-integration.md §2.3`).

**`sort_by=recent`** — we already have `sort=newest`. Covered.

**`category` filter** — we use freeform labels instead. This gap only matters if we add a fixed taxonomy (see integration report §2.5).

**Verdict: steal `min_stars` filter; defer vector mode; rest already covered.**

---

## 2. `downloader.py` — GitHub Install

### What they have

```python
def _parse_github_url(url):
    parts = url.rstrip('/').split('/')
    owner, repo = parts[3], parts[4]
    ref = parts[6]     # branch or commit SHA
    dir_path = "/".join(parts[7:])
    ...

def _request_with_retry(url, timeout=15, max_retries=3, base_delay=1):
    for attempt in range(1, max_retries+1):
        response = session.get(url, timeout=timeout)
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "?")
            if remaining == "0":
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                wait_seconds = max(0, reset_time - int(time.time()))
                time.sleep(wait_seconds + 1)   # ← sleep to reset time
                continue
        return response
    ...

# Mirror support
GITHUB_MIRROR env var → prepended to raw.githubusercontent.com URLs
```

Authentication: `Authorization: token <api_token>` header if token provided.

### What we have

Our `github.py` uses `httpx.AsyncClient` with 10s timeout. On 403 it raises `GitHubFetchError("GitHub rate limit reached")` immediately with no retry or reset-time sleep. We do support `GITHUB_TOKEN` for auth. No mirror support.

### Gaps worth closing

**`X-RateLimit-Reset` header sleep** — SkillNet reads the reset timestamp and sleeps until it. We raise immediately. For the server-side refetch/scan flow (background jobs that hit GitHub repeatedly) this matters: instead of failing and needing a manual retry, we could sleep `max(0, reset_time - now) + 1` seconds and retry once. This is safe in a background task context; not appropriate for a user-facing request (where a 503 response is better).

Concretely: in `github.py`, on a 403 response with `X-RateLimit-Remaining: 0`, read `X-RateLimit-Reset`, sleep up to a reasonable cap (e.g. 65s), then retry once. For user-facing paths, keep the immediate 503.

**Mirror URL support (`GITHUB_MIRROR`)** — not relevant for SLAC S3DF (direct GitHub access is fine). Skip.

**URL parsing** — SkillNet's `_parse_github_url` is naïve (positional split). Ours uses a proper regex parser with branch/path disambiguation. We are strictly better here.

**Clone vs Contents API** — SkillNet uses Contents API only (no git clone). Our `SKILL.md` install flow already uses git clone with Contents API fallback (see `skill/SKILL.md` §git-clone-to-temp). We are strictly better here.

**Verdict: steal the `X-RateLimit-Reset` sleep for background refetch paths only. Skip mirror, URL parser, and clone logic (ours is better).**

---

## 3. `evaluator.py` — Five-Dimension Quality Scoring

### What they have

Full LLM-assisted evaluation pipeline:

1. Load `SKILL.md`, supporting scripts, reference files
2. Optionally execute scripts in sandbox (configurable via `EvaluatorConfig`)
3. Build prompt via `PromptBuilder.build()` — injects skill content + script results into `SKILL_EVALUATION_PROMPT`
4. Call LLM (OpenAI-compatible API, model configurable via `SKILLNET_MODEL` env var)
5. Parse JSON response with multi-stage fallback: strip markdown fences → `json.loads` → `json_repair` library
6. Output: `{"level": "Good"|"Average"|"Poor", "reason": "..."}` per dimension

### The evaluation rubric (from `prompts.py`) — verbatim

| Dimension | Good | Average | Poor |
|---|---|---|---|
| **Safety** | Avoids destructive actions by default; explicit safety checks; medical skills have disclaimers | Benign domain, no safeguards needed | Dangerous operations without protection |
| **Completeness** | Clear goals, steps, inputs/outputs, edge cases | Underspecified details | Too vague to act on; formula/algorithm errors |
| **Executability** | Concrete actionable steps (even instruction-only) | Ambiguous steps | Lacks operational detail |
| **Maintainability** | Narrow scope, clear inputs/outputs, composable | Unclear boundaries | Tightly coupled; trivial placeholder |
| **Cost-Awareness** | Explicit efficiency controls (batching, limits, caching) for heavy domains | No mention but no waste | Encourages wasteful/unbounded behavior |

### What we have

Nothing. No quality scoring at all — only community star ratings.

### What to steal

The rubric above is the most directly stealable asset in the entire SkillNet codebase. It requires no infrastructure — just an LLM call or a human checklist. Three integration paths:

**Option A — Manual checklist on submit (low effort, immediate)**
Render the 5-dimension rubric as a guided form in the submit/edit UI. Author self-scores each dimension. No server-side LLM needed. Fast, but gameable.

**Option B — Server-side LLM scoring at scan time (medium effort)**
On `POST /api/skills` and `POST /api/skills/{slug}/refetch`, call an LLM with the SkillNet rubric prompt against the scanned `skill_md_raw`. Store result in `quality_scores: dict[str, str]`. Model: anything fast (Haiku / Gemma). Cost: negligible per scan.

**Option C — Both (best)**
Author self-score on submit → system rescores at refetch → show both with a "system-verified" badge when they agree. Disagreements flag for review.

**Schema change needed:**
```python
# backend/app/models/skill.py — add to Skill:
quality_scores: Optional[Dict[str, str]] = None  # {"safety": "Good", ...}
quality_scores_at: Optional[datetime] = None
```

**Verdict: steal the rubric verbatim; implement Option B first (auto-score at scan); add Option A UI later.**

---

## 4. `models.py` — Search Response Schema

### What they have

```python
class SkillModel(BaseModel):
    skill_name, skill_description, author, stars, skill_url, category, evaluation
    # evaluation: Optional[Dict[str, Any]] — the 5-dimension scores, embedded inline

class SearchResponse(BaseModel):
    data: List[SkillModel]
    meta: MetaModel   # total, page, mode, threshold, sort_by, ...
    success: bool
```

Notable: `evaluation` is embedded in the search result model — scores are visible in search results, not just on the detail page. This means clients can filter/sort by quality in search.

### What we have

`SkillListOut` has no quality scores. `SkillOut` (detail) has no quality scores. Both would need `quality_scores` added.

### What to steal

Include `quality_scores` in both `SkillListOut` and `SkillOut` once the model field exists. In `SkillListOut` a summary (e.g. count of "Good" dimensions) is enough; full scores belong on the detail view.

---

## 5. Summary Table

| SkillNet script | Gap vs AKH | Action | Effort |
|---|---|---|---|
| `searcher.py` — `min_stars` filter | We have no `min_stars` param | Add `min_stars: Optional[int]` to `GET /api/skills` | Low |
| `searcher.py` — `mode=vector` | No vector search | Defer (Atlas/Qdrant dependency) | High |
| `searcher.py` — `category` filter | Freeform labels instead | Add after taxonomy todo | Low |
| `downloader.py` — `X-RateLimit-Reset` sleep | We 503 immediately on rate-limit | Add sleep+retry in background scan paths only | Low |
| `downloader.py` — mirror support | Not needed for SLAC | Skip | — |
| `downloader.py` — URL parser / clone | We are strictly better | Nothing to steal | — |
| `evaluator.py` — 5-dimension rubric | We have none | Steal rubric; auto-score at scan time | Medium |
| `evaluator.py` — sandbox execution | Heavy infrastructure | Defer | High |
| `models.py` — `evaluation` in search results | No quality_scores field | Add after evaluator is implemented | Low |

---

## Recommended Next Steps

1. **Add `quality_scores` to `Skill` model** — `Dict[str, str]` optional field. Zero risk, no migration needed (Beanie/MongoDB adds it lazily).
2. **Add LLM scoring call in `scanner.py`** — after `skill_md_raw` is populated, call LLM with the SkillNet rubric prompt (above) against the SKILL.md content. Store result. ~20 lines.
3. **Expose `quality_scores` in `SkillOut` / `SkillListOut`** — trivial schema change.
4. **Add `X-RateLimit-Reset` retry in `github.py`** — background scan paths only, capped at 65s sleep.
5. **Add `min_stars` filter to `GET /api/skills`** — one line in router + one line in `list_with_cursors`.

Items 4 and 5 are isolated one-liners. Items 1–3 are the evaluator feature and belong in a single PR.

---

## Concept References

- [concepts/skillnet.md](../concepts/skillnet.md) — SkillNet architecture

## Sources

- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/searcher.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/downloader.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/evaluator.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/models.py — fetched 2026-06-05
- https://github.com/zjunlp/SkillNet/blob/main/skillnet-ai/src/skillnet_ai/prompts.py — fetched 2026-06-05
