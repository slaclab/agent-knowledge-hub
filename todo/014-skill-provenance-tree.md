# TODO #014 — Skill Provenance Tree: Fork and Evolution Graph

> **Priority:** 🟡 P2 — Medium
> **Status:** 🔍 Reviewed
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

Skills don't exist in isolation — they fork from upstream repos, get superseded by newer versions, and accumulate forks within the catalog. Today the detail page shows one hop in each direction (a "Forked from" link and a "N forks in catalog" count) but there's no way to see the full lineage: where did this skill originate, who forked it, which version superseded which?

A user looking at a skill cannot answer: "Is this the canonical version or a downstream fork?", "Which fork is most actively maintained?", "Has this skill been superseded — and by what chain?".

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| "Where did this skill come from?" | Single "Forked from" link (one hop) | Full upstream chain visualised |
| "Who forked this skill?" | "N forks in catalog" count + filtered list link | Tree showing direct forks and their forks |
| "Has this been superseded?" | Banner if direct `superseded_by_slug` set | Full supersession chain shown |
| "Which fork is most active?" | Not comparable | Tree nodes show stars, last commit, rating |
| New contributor lands on a fork | No signal about canonical upstream | Provenance tree shows canonical root |

---

## Goals

1. A dedicated `GET /api/skills/{slug}/provenance` backend endpoint returning a pre-built tree JSON — upstream chain, downstream forks (2 levels), and supersession chain
2. A collapsible `ProvenanceTree` section on the skill detail page sidebar (collapsed by default)
3. Tree nodes show: name, slug, submitter, github_stars, avg_rating, last_commit_at — enough to compare forks at a glance
4. Non-catalog upstream entries (GitHub repos not in the catalog) shown as external leaf nodes with a GitHub link
5. Supersession chain rendered as a directed path with "superseded by" labels
6. Depth-capped: max 3 hops upstream, max 2 levels of downstream forks — prevents runaway queries on deep lineages

## Non-Goals

- Automatic fork detection from GitHub (relies on `forked_from_url` being set at submission — improving detection is a separate concern)
- Diff between fork and upstream (related to #013 but distinct)
- Visualising revision history on tree nodes
- Full graph/DAG visualisation library — indented tree in CSS is sufficient for v1

---

## User Stories

1. As a user on a fork's detail page, I want to see the full upstream chain, so that I can find the canonical original.
2. As a user on a canonical skill's page, I want to see which catalog skills have forked it, so that I can compare alternatives.
3. As a user, I want each tree node to show stars, rating, and last commit, so that I can judge which version is most active without clicking through.
4. As a user, I want supersession chains shown as a path, so that I can follow "replaced by" links without dead ends.
5. As a user, I want external (non-catalog) upstream repos shown with a GitHub link, so that I can reach the original source even if it's not in AKH.
6. As a user, I want the provenance tree collapsed by default, so that the detail sidebar isn't overwhelming.
7. As a user with a skill that has no forks and no upstream, I want the provenance section hidden, so that it doesn't appear as an empty box.
8. As a user on a deep fork chain, I want the tree capped at reasonable depth, so that pathological lineages don't cause slow page loads.

---

## Requirements

### Functional

- **FR-1:** `GET /api/skills/{slug}/provenance` accepts `viewer: Optional[User] = Depends(get_optional_user)` and returns a `ProvenanceTree` JSON with `upstream` chain (capped at 3 hops), `forks` list (each with their own `forks`, capped at 2 levels), and `supersession` chain. Rate limit: `@limiter.limit("30/minute")`.
- **FR-2:** Each tree node for a catalog skill includes: `slug`, `name`, `repo_url`, `submitter_id`, `github_stars`, `avg_rating`, `last_commit_at`, `status` (active/deactivated). Internal-visibility catalog skills are **redacted** to `{ slug: null, in_catalog: true, visibility: "internal", name: "[internal skill]" }` for unauthenticated viewers; only `in_catalog` and `visibility` are exposed. Deactivated public skills appear with `status: "deactivated"` visible. `source_type="local"` skills are excluded from upstream/fork matching (their `repo_url` is `local://...` and cannot match a `forked_from_url`).
- **FR-3:** External (non-catalog) upstream nodes: `repo_url`, `github_stars`, `last_commit_at` fetched via `github_fetcher.fetch()` wrapped in try/except (raises `GitHubFetchError` on failure — catch and return `null` metadata). `in_catalog: false`. **Cap: max 1 external GitHub metadata fetch per request** (only the immediate upstream if external; deeper external ancestors show URL-only nodes with `null` metadata).
- **FR-4:** Upstream chain: resolve `skill.forked_from_url` → find catalog skill with matching `repo_url` AND prefer `skill_path="/"` (root path); if no root-path match, pick oldest by `submitted_at`. Repeat up to 3 hops. Cycle detection uses a visited `slug` set for catalog nodes. URLs normalized via `_normalize_github_url()` before matching.
- **FR-5:** Fork list: `Skill.find(forked_from_url == skill.repo_url)` for level-1 forks, capped at `MAX_FORKS_PER_LEVEL = 20`. Level-2: batch query `Skill.find(forked_from_url IN [level-1 repo_urls])` (single query, not N queries). Response includes `forks_truncated: bool` and `total_fork_count: int` so frontend can show "and N more" link.
- **FR-6:** Supersession chain: follow `superseded_by_slug` links until none or 10-hop cap. Separate visited `slug` set for cycle detection. Internal-visibility nodes in the chain are redacted for unauthenticated viewers (same rule as FR-2).
- **FR-7:** If no upstream, no forks, no supersession, endpoint returns `{ empty: true, subject: <subject node> }`.
- **FR-8:** Frontend `ProvenanceTree` section is hidden when endpoint returns `empty: true`.
- **FR-9:** Frontend collapsed summary shows only the segments that exist, joined by `·`. Format: "Forked from [name]" / "[N] forks in catalog" / "Superseded by [name]". If only one segment exists, show it without separators. "Superseded by" is excluded from the collapsed summary (the existing `SupersededNotice` banner already handles the "go update" CTA at the top of the page — the tree's supersession section is lineage context only, visible on expand).
- **FR-10:** Frontend expanded tree replaces the existing "Fork Provenance" card and "Forks in Catalog" card — those two sidebar sections are removed when `ProvenanceTree` is added. No net increase in sidebar section count.
- **FR-11:** Frontend tree indentation uses CSS `border-left` + `padding-left` (not ASCII `├` `└` characters) for mobile resilience. On viewports below `sm`, node metadata (stars, rating, last-commit) stacks below the skill name instead of inline.
- **FR-12:** Frontend fork display cap: max 5 level-1 forks shown in the tree, sorted by `github_stars` descending. If `forks_truncated` is true or `total_fork_count > 5`, show "and N more forks →" link to `/skills?forked_from=<repo_url>`.
- **FR-13:** Non-catalog upstream nodes are labelled with a GitHub icon and linked repo path (e.g., `github.com/org/repo`) — no "external GitHub" text label.

### Non-functional

- **NFR-1:** Endpoint responds in < 800ms (p95) for trees up to depth 3 + 20 forks; queries are bounded by depth caps.
- **NFR-2:** No N+1 per-node fetches — upstream resolution and fork listing done in batched queries.
- **NFR-3:** External node GitHub metadata fetch is best-effort: failure returns `github_stars: null` without failing the whole endpoint.
- **NFR-4:** Result is cached 5 minutes (same TTL as file content cache) — provenance trees are stable.
- **NFR-5:** Cycle detection: upstream traversal uses a visited `slug` set (catalog nodes) and visited `repo_url` set (external nodes). Supersession traversal uses a separate visited `slug` set. These are independent guards.
- **NFR-6:** Upstream resolution prefers `skill_path="/"` when multiple catalog skills share the same `repo_url`. Cache stores the full unfiltered tree; per-viewer visibility filtering is applied at response time (O(n), n ≤ ~30 nodes). This avoids cache fragmentation without per-user cache keys.

### Acceptance Criteria

- **AC-1:** Given a skill with `forked_from_url` pointing to a catalog skill, `GET /provenance` returns `upstream` array with that skill as a node.
- **AC-2:** Given a skill with `forked_from_url` pointing to a non-catalog GitHub repo, the upstream node has `in_catalog: false` and a `repo_url` link.
- **AC-3:** Given a skill with 3 catalog forks, the response `forks` array contains 3 nodes each with their own metadata.
- **AC-4:** Given a 4-hop upstream chain, the response upstream array contains at most 3 nodes (depth cap enforced).
- **AC-5:** Given a supersession chain A→B→C, the `supersession` array contains B then C in order.
- **AC-6:** Given a skill with no forks, no upstream, no supersession, the endpoint returns `{ empty: true }` and the frontend hides the section.
- **AC-7:** Given a circular fork reference (A forks B, B forks A), cycle detection prevents infinite traversal.
- **AC-8:** Given an endpoint response, the frontend renders a collapsible tree with node metadata (stars, rating, last commit) visible on expand.
- **AC-9:** Given an internal-visibility skill in a fork chain, an unauthenticated viewer receives a redacted node `{ in_catalog: true, visibility: "internal", name: "[internal skill]" }` rather than the skill's actual name, slug, or submitter.
- **AC-10:** Given a skill with 25 catalog forks, the tree shows at most 5 in the expanded view with "and 20 more forks →" overflow link.
- **AC-11:** Given a skill where `SupersededNotice` banner is already shown at the top of the page, the collapsed provenance summary does NOT include "superseded by" — it only appears in the expanded tree as lineage context.
- **AC-12:** Given a supersession cycle (A.superseded_by=B, B.superseded_by=A), the supersession chain returns at most [B] and stops (separate cycle guard from fork/upstream).

---

## Architecture Decision Records

### ADR-U26: Provenance as backend endpoint, not client-side assembly

**Status:** Proposed
**Date:** 2026-06-03

#### Context
The provenance tree requires multi-hop resolution: follow `forked_from_url` → match `repo_url` in catalog → repeat. This can be done client-side (multiple sequential API calls) or via a single backend endpoint.

#### Options

| Option | Pros | Cons |
|---|---|---|
| Client-side sequential fetches | No new endpoint | N round trips from browser; hard to cap depth; complex error handling; can't batch |
| Backend `GET /skills/{slug}/provenance` | Single round trip; depth-capped server-side; batchable queries; cacheable | New endpoint to build |

#### Decision
**Backend endpoint.** The multi-hop resolution is fundamentally a graph traversal that must be depth-capped and cycle-detected server-side. Client-side assembly would result in N sequential API calls (one per hop) and can't efficiently batch-resolve downstream forks. A single endpoint returning the full tree is cleaner and cacheable.

#### Consequences
- New `GET /api/skills/{slug}/provenance` in `routers/skills.py`
- New `services/provenance.py` for graph traversal logic
- 5-minute TTL cache (provenance trees change rarely)
- External GitHub node metadata fetched best-effort (failure → null fields)

---

### ADR-U27: Indented tree UI (not a graph library)

**Status:** Proposed
**Date:** 2026-06-03

#### Context
The provenance data is a shallow tree (max 3 + 2 levels). Visualisation options: a full graph library (react-flow, d3-hierarchy) or a simple CSS-based indented tree.

#### Options

| Option | Pros | Cons |
|---|---|---|
| react-flow / d3-hierarchy | Handles complex DAGs; draggable/zoomable | Heavy dependency; overkill for 3-level trees; layout complexity |
| CSS indented tree (native) | Zero new dependencies; fast to build; fits sidebar well | Can't render true DAGs (node appearing in multiple places) |

#### Decision
**CSS indented tree, no new library dependency.** The provenance tree is depth-capped at 3+2 levels — a graph library is overkill. If a node appears in both upstream and forks (true DAG), it's rendered twice. This is acceptable for v1; upgrade to a library if user feedback shows the need.

#### Consequences
- `ProvenanceTree` component uses `border-left` + `padding-left` CSS for indentation — no ASCII tree characters (`├`, `└`). This ensures mobile resilience when text wraps.
- No new npm dependencies
- DAG dedup (same node appearing multiple times) handled by displaying duplicate nodes with a "(same as above)" label

---

### ADR-U28: External upstream nodes — best-effort GitHub metadata

**Status:** Proposed
**Date:** 2026-06-03

#### Context
`forked_from_url` may point to a GitHub repo not in the AKH catalog. To show meaningful node metadata (stars, last commit) for these external nodes, we'd need to fetch from GitHub.

#### Options

| Option | Pros | Cons |
|---|---|---|
| Skip metadata for external nodes | Zero extra API calls; simple | External nodes show only URL, no comparison data |
| Fetch via existing `github_fetcher` | Shows stars/last_commit for external nodes; enables comparison | Extra GitHub API call per external node; rate limit pressure |

#### Decision
**Fetch via existing `github_fetcher`, best-effort.** The fetcher is already used during scan and handles auth. External nodes are typically just one (the direct upstream), so the API cost is low. If the fetch fails (rate limit, private repo), the node renders with `null` metadata — no error.

#### Consequences
- `provenance_service.py` calls `github_fetcher.fetch(repo_url)` wrapped in `try/except GitHubFetchError` — failures return `null` metadata, never propagate to caller
- Capped at 1 external fetch per request (immediate upstream only; deeper external ancestors render URL-only)
- These fetches count toward GitHub API rate limits — mitigated by 5-min endpoint cache
- SSRF risk is mitigated by `github_fetcher`'s existing URL validation against `github.com` regex and hardcoded `api.github.com` base URL

---

## Module Design

### Backend

| Module | Responsibility | Interface | Status | Testable |
|---|---|---|---|---|
| `services/provenance.py` | Graph traversal: upstream (slug-based cycle guard, root-path preference, URL normalization), fork tree (MAX_FORKS=20 cap, batched level-2 query), supersession (separate slug cycle guard). Visibility filtering applied at response time from cached unfiltered tree. | `build_tree(skill, viewer) -> ProvenanceTree` | New | Yes |
| `schemas/provenance.py` | Pydantic models: `ProvenanceNode` (with `visibility`, `forks_truncated`, `total_fork_count`), `ProvenanceTree` | Data classes | New | Yes |
| `routers/skills.py` | Add `GET /{slug}/provenance` with `get_optional_user`, `@limiter.limit("30/minute")`, 5-min TTL cache (stores unfiltered tree; filter applied per request) | Route handler | Modify | Integration |
| `frontend/app/skills/[slug]/page.tsx` | Remove existing "Fork Provenance" card and "Forks in Catalog" card; add `ProvenanceTree` section instead | Modify | — |

### Frontend

| Module | Responsibility | Status |
|---|---|---|
| `frontend/components/provenance-tree.tsx` | Collapsible indented tree; node cards with metadata | New |
| `frontend/app/skills/[slug]/page.tsx` | Fetch provenance + render `ProvenanceTree` in sidebar (hidden if `empty: true`) | Modify |
| `frontend/types/provenance.ts` | `ProvenanceNode`, `ProvenanceTree` TypeScript interfaces | New |
| `frontend/lib/api.ts` | Add `getProvenance(slug)` fetch function | Modify |

---

## System Design

```
Browser
  └─ GET /api/skills/{slug}/provenance
       │
       ▼
  provenance_service.build_tree(skill)
       │
       ├─ upstream chain (max 3 hops):
       │    resolve forked_from_url → find Skill where repo_url matches
       │    repeat on found skill; stop at 3 hops or no match
       │    if no catalog match → fetch external node via github_fetcher (best-effort)
       │
       ├─ fork tree (max 2 levels):
       │    Skill.find(forked_from_url == skill.repo_url)  [level 1 forks]
       │    for each level-1 fork: Skill.find(forked_from_url == fork.repo_url) [level 2]
       │
       └─ supersession chain (max 10 hops):
            follow superseded_by_slug links until None
```

**Response schema:**

```python
class ProvenanceNode(BaseModel):
    slug: Optional[str]          # None for external nodes
    name: str
    repo_url: str
    in_catalog: bool
    submitter_id: Optional[str]
    github_stars: Optional[int]
    avg_rating: Optional[float]
    last_commit_at: Optional[datetime]
    status: Optional[str]        # "active" | "deactivated"
    forks: List["ProvenanceNode"] = []   # populated for level-1 nodes only

class ProvenanceTree(BaseModel):
    empty: bool = False
    subject: ProvenanceNode           # the skill being viewed
    upstream: List[ProvenanceNode]    # ancestor chain, root-first
    supersession: List[ProvenanceNode] # superseded_by chain
```

**Frontend layout (collapsed):**
```
▶ Provenance  ·  forked from sklearn-recipes  ·  3 forks  ·  superseded by ml-toolkit-v2
```

**Expanded:**
```
▼ Provenance
  Upstream
    ● sklearn-recipes (external GitHub)  ★ 142  last commit 3w ago  →
  This skill
    ● ml-data-tools  ★ 12  ⭐ 4.2  last commit 2d ago
  Forks in catalog (3)
    ├ ● ml-data-tools-lcls  ★ 4  ⭐ 3.8  by bob
    │    └ ● ml-data-tools-lcls-dev  ★ 1  by carol
    └ ● ml-data-tools-usdf  ★ 7  ⭐ 4.5  by dave
  Superseded by
    → ml-toolkit-v2  →  ml-toolkit-v3
```

---

## Trade-offs

```
Choice: Backend endpoint (vs client-side assembly)
  + Single round trip; server-side depth cap; cacheable; batchable
  - New endpoint to maintain
  Decision: Backend. Multi-hop traversal cannot be done efficiently client-side.

Choice: CSS indented tree (vs graph library)
  + Zero new dependencies; fast; fits sidebar
  - Can't render true DAGs elegantly
  Decision: Indented tree. Trees are shallow (≤5 levels); upgrade if needed.

Choice: Fetch external GitHub metadata (vs omit)
  + Enables comparison of catalog vs non-catalog upstream
  - Extra GitHub API call; rate limit pressure
  Decision: Best-effort fetch. Single external node is common case; failures degrade gracefully.

Choice: 5-min TTL cache on endpoint
  + Provenance trees change rarely; reduces DB queries
  - Stale for 5 min after a new fork is submitted
  Decision: 5-min TTL is acceptable; fork submission is a rare event.
```

---

## Delivery Slices

**Slice 1 — Backend: provenance service + endpoint**
- `schemas/provenance.py`: `ProvenanceNode` (with `visibility`, `forks_truncated`, `total_fork_count`), `ProvenanceTree`
- `services/provenance.py`: `build_tree(skill, viewer)` — upstream (slug cycle guard, root-path preference, URL normalization), fork tree (MAX_FORKS_PER_LEVEL=20, batched level-2 via single `$in` query), supersession (separate slug cycle guard). `github_fetcher.fetch()` wrapped in try/except, capped at 1 external call. Visibility filtering at response time.
- `routers/skills.py`: `GET /{slug}/provenance` with `get_optional_user`, `@limiter.limit("30/minute")`, 5-min TTL cache (unfiltered tree cached, filtered per request)
- Unit tests (see DoD for full list)
- Integration tests: endpoint shape, 404, empty, auth redaction of internal nodes

**Slice 2 — Frontend: ProvenanceTree component + wire-up**
- `frontend/types/provenance.ts`: `ProvenanceNode`, `ProvenanceTree` (with `forks_truncated`, `total_fork_count`)
- `frontend/lib/api.ts`: `getProvenance(slug)`
- `frontend/components/provenance-tree.tsx`: collapsible tree using CSS `border-left`/`padding-left` indentation; FR-9 adaptive collapsed summary; FR-11 mobile-stack layout; FR-12 5-fork display cap with overflow link; FR-13 GitHub icon for non-catalog nodes
- `frontend/app/skills/[slug]/page.tsx`: remove existing "Fork Provenance" and "Forks in Catalog" cards; add `ProvenanceTree` section (hidden if `empty: true`)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Circular fork references (A forks B, B forks A) cause infinite traversal | Low | High | Cycle detection: track visited `repo_url` set; stop if already seen |
| External GitHub fetch hits rate limit | Low | Low | Best-effort: failure returns null metadata; 5-min cache reduces frequency |
| Deep supersession chains (10+ hops) are pathological | Very low | Medium | Hard cap at 10 hops; log warning if cap triggered |
| `forked_from_url` not set on many older skills → sparse tree | High | Low | Empty-tree check hides section gracefully; no UX impact |
| Fork of a fork of a fork fills the sidebar | Low | Low | 2-level fork cap; "N more forks" link to filtered list for deeper chains |

---

## Definition of Done

- [ ] All acceptance criteria pass
- [ ] Unit tests (services/provenance.py):
  - upstream chain catalog-only (3 hops)
  - upstream chain with external node (best-effort fetch, 1-call cap)
  - upstream chain depth cap (5-hop chain → 3 returned)
  - upstream multi-skill same repo_url (prefers root-path skill)
  - upstream cycle detection via slug set (A forks B, B forks A)
  - fork tree basic (2 levels)
  - fork tree level cap (3-level deep → 2 returned)
  - fork tree count cap (30 level-1 → 20 returned + forks_truncated=true)
  - fork tree batched level-2 query (single $in, not N queries)
  - supersession chain basic (A→B→C)
  - supersession chain cap (12-hop → 10 returned)
  - supersession cycle detection via separate slug set (A→B→A → [B])
  - empty tree (no upstream, forks, supersession → empty=true)
  - external node fetch failure (GitHubFetchError caught → null metadata)
  - local source_type skill excluded from upstream matching
  - internal skill redacted for unauthenticated viewer
- [ ] Integration tests: GET /provenance returns correct shape; 404 for nonexistent slug; empty:true for orphan skill; internal node redacted when unauthenticated; rate limit enforced
- [ ] 5-min TTL cache verified (second call, no DB queries)
- [ ] Frontend: `ProvenanceTree` renders adaptive collapsed summary (partial segments)
- [ ] Frontend: supersession NOT in collapsed summary (banner handles it)
- [ ] Frontend: existing "Fork Provenance" + "Forks in Catalog" sidebar cards removed
- [ ] Frontend: CSS border-left tree indentation (no ASCII characters)
- [ ] Frontend: mobile-stack layout verified at sm breakpoint
- [ ] Frontend: fork display cap (max 5 shown, overflow link)
- [ ] Frontend: non-catalog nodes use GitHub icon + repo path label
- [ ] Frontend: section hidden when `empty: true`
- [ ] CHANGELOG entry added (`### Skill provenance tree: fork and supersession lineage (#014)` under `## Unreleased`)
- [ ] ADR-U26 → `docs/adr/adr-u26-provenance-backend-endpoint.md`
- [ ] ADR-U27 → `docs/adr/adr-u27-css-indented-tree.md`
- [ ] ADR-U28 → `docs/adr/adr-u28-external-node-metadata.md`

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-03
**Rounds:** 2

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ✅ PASS | NO | All 4 claims confirmed: model fields, sparse index, github_fetcher.fetch(), TTLCache pattern. URL normalization note. |
| codebase-arch-review | ✅ PASS | YES | Architecture sound; batch level-2 fork query added; visibility filtering specified |
| codebase-eng-review | ✅ PASS | YES | CRITICAL cycle detection bug fixed (slug-based sets); unbounded fork fan-out resolved; 21-test plan added |
| doc-review | ✅ PASS | NO | ADR numbering correct (U26-U28); CHANGELOG format derivable; two LOW post-ship prose updates noted |
| security-review | ✅ PASS | YES | HIGH (internal skill disclosure) resolved: get_optional_user + per-node redaction + rate limit |
| codebase-ux-review | ✅ PASS | YES | 6 amendments: sidebar replacement, supersession dedup, mobile CSS tree, partial summary, fork cap, icon labels |

**Accepted warnings:** Cache staleness for 5 min after fork submission (accepted — 5-min TTL adequate at current scale)
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>research — Round 1 (PASS)</summary>

All 4 claims confirmed against codebase:
- `repo_url`, `superseded_by_slug`, `forked_from_url` exist in Skill model
- `forked_from_url_sparse` index present (line 120 of models/skill.py)
- `GitHubFetcher.fetch()` returns all needed ProvenanceNode fields
- `cachetools.TTLCache(maxsize=1024, ttl=300)` pattern established in github.py

Implementation note: normalize URLs via `_normalize_github_url()` before matching.

Status: PASS

</details>

<details>
<summary>codebase-arch-review — Round 1 (PASS with amendments)</summary>

Architecture sound. Indexes adequate, caching pattern reusable, ADRs well-reasoned.

Key findings (all LOW/MEDIUM — resolved in plan):
- MEDIUM: NFR-2 needed explicit batch query guidance for fork-tree level 2 → added to FR-5
- LOW: Visibility behavior for internal skills not specified → resolved by FR-1/FR-2/NFR-6
- LOW: Schema tension (empty:true with required subject) → noted
- LOW: Cache invalidation on fork submission → documented as known limitation
- LOW: Defensive URL normalization in service → noted in FR-4

Status: PASS

</details>

<details>
<summary>codebase-eng-review — Round 1 (REVISE → Round 2 PASS)</summary>

Round 1 findings (all resolved):
- CRITICAL: Cycle detection tracked repo_url but two skills can share repo_url with different skill_paths — fixed by slug-based visited sets + separate set for supersession (NFR-5, FR-4, FR-6)
- HIGH: Unbounded fork fan-out (50 level-1 forks = 51 queries) — resolved by MAX_FORKS_PER_LEVEL=20 + batched level-2 $in query (FR-5)
- HIGH: Upstream resolution ignores skill_path ambiguity — resolved by root-path preference heuristic (FR-4)
- HIGH: Supersession cycle detection used wrong key — fixed with separate slug visited set (FR-6)
- MEDIUM/LOW: Test plan incomplete — 16 unit + 5 integration tests added to DoD

Status: PASS (Round 2)

</details>

<details>
<summary>doc-review — Round 1 (PASS)</summary>

- ADR numbering U26-U28 consistent (last physical ADR is U17; U18-U25 reserved by pending tasks)
- CHANGELOG format derivable from existing entries
- FastAPI auto-docs cover new ProvenanceNode/ProvenanceTree schemas
- LOW: docs/why-agent-knowledge-hub.md (lines 67-69) and guide pages describe fork lineage in pre-tree terms — refresh at closeout

Status: PASS

</details>

<details>
<summary>security-review — Round 1 (REVISE → Round 2 PASS)</summary>

Round 1 findings (all resolved):
- HIGH: Unauthenticated provenance tree exposed internal skill metadata (slug, name, submitter, repo_url) — resolved: FR-1 adds get_optional_user; FR-2 redacts internal nodes to `{in_catalog:true, visibility:"internal", name:"[internal skill]"}` for anonymous viewers; AC-9 tests this; NFR-6 documents cache-then-filter approach
- MEDIUM: Supersession chain leaked deactivated-internal skill slugs — resolved by FR-6 visibility filtering
- MEDIUM: No rate limit → resolved by @limiter.limit("30/minute") in FR-1
- LOW: SSRF mitigated by existing github_fetcher URL validation — no action needed
- LOW: Unbounded external fetches → resolved by 1-fetch cap in FR-3

Status: PASS (Round 2)

</details>

<details>
<summary>codebase-ux-review — Round 1 (REVISE → Round 2 PASS)</summary>

Round 1 findings (all resolved):
- HIGH: Supersession shown twice (banner + tree) — resolved: FR-9 excludes "superseded by" from collapsed summary; tree shows it on expand as lineage context only (AC-11)
- HIGH: Sidebar density — plan did not state ProvenanceTree replaces existing cards — resolved: FR-10 explicitly removes "Fork Provenance" + "Forks in Catalog" cards
- MEDIUM: ASCII tree characters break on mobile — resolved: FR-11 mandates CSS border-left/padding-left indentation; mobile-stack layout at sm breakpoint
- MEDIUM: Partial collapsed summary undefined — resolved: FR-9 defines adaptive single-segment format
- MEDIUM: No fork display cap — resolved: FR-12 adds max 5 level-1 forks shown, sorted by stars, with overflow link
- LOW: "External GitHub" label unclear — resolved: FR-13 uses GitHub icon + repo path

Status: PASS (Round 2)

</details>

---

## Relationship to Other Tasks

- **#001 (Fork provenance):** This task is the richer visualisation of the fork links introduced in #001.
- **#013 (Revision history):** Both live on the detail page sidebar. #013 is time-axis; #014 is space-axis. Tree nodes could eventually link to revision diffs.
- **#009 (Duplicate detection):** Provenance data helps distinguish intentional forks from accidental duplicates.
