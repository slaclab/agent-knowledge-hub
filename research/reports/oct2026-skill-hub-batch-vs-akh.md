# October 2026 Skill-Hub Batch vs AKH — Integrate, Adopt, or Landscape — Report

> **Type:** Report
> **Concept References:** [open-agent-hub](../concepts/open-agent-hub.md), [skill-retrieval-mcp](../concepts/skill-retrieval-mcp.md), [Plugin4Shell](../concepts/plugin4shell.md), [agenticskills.io find-skills](../concepts/agenticskills-find-skills.md), [chops](../concepts/chops.md), [asm](../concepts/asm.md), [Hermes Agent skills](../concepts/hermes-agent-skills.md), [SkillClaw](../concepts/skillclaw.md), [MCP registry landscape](../concepts/mcp-registry-landscape.md)
> **Prior analysis:** [mcp-registry-for-akh.md](mcp-registry-for-akh.md), [skillnet-integration.md](skillnet-integration.md), [skillnet-scripts-analysis.md](skillnet-scripts-analysis.md), [akh-skillnet-improvements.md](akh-skillnet-improvements.md)
> **Keywords:** AKH, Agent Knowledge Hub, skill marketplace, skill installer, skill/SKILL.md, hub-request.sh, npx skills, skills.sh, Vercel skills CLI, multi-client install, cross-client install, Codex install path, pre-install security scanning, skills_guard, pinned_commit_sha, commit pinning, Plugin4Shell, CVE-2026-86063, GHSA-pq7j-f95f-qfcv, two-stage search, summarize-then-fetch, hybrid search, FAISS, FTS5, retrieval eval, token budget, attention budget, context cost, MCP security scorecard, RFC 9728, tool-level MCP indexing, tools/list, marketplace.json, git-subdir
> **Status:** evolving

*Generated: 2026-10-16 | Confidence: Medium-High (AKH code, backlog and git history read directly; claims about external projects inherited from the six concept files at their stated confidence; no new fetches)*

---

## Executive Summary

AKH should integrate none of the external tools in this batch. Each is a single-user client or a closed directory with no access-tier model, and each would route installs around properties AKH's own client already enforces: the S3DF-gated catalog (#050), the argument allow-list (#045), the MCP-server and agent policy (#051), and the pinned commit (#017, #053). The one external dependency worth declaring is Claude Code's fix for CVE-2026-86063, which becomes load-bearing once #046 puts a `sha` into `marketplace.json`. Five ideas are worth building as AKH code, led by one the batch implies but no concept file states: AKH's own pin holds only on the clone path, only once #053 lands, and only for the 15% of the catalog that has one, so it has to be made real before any scan result or "reviewed" signal relies on it. Multi-client reach is adopted only if users show they want it. AKH installed into Codex in June 2026 and lost that path in a commit labelled `docs`, and nothing in the backlog shows that anyone noticed.

## Background

The TOPICS row "Oct 2026 skill-hub batch vs AKH" asks, for six sources catalogued on 2026-10-16, whether AKH should run the external tool, build its own version of the idea, or take no action. The concept files compare each source with AKH in the abstract, partly from AKH's README. This report checks each comparison against `skill/SKILL.md`, the backend, the open backlog and the repository history. Three premises in the corpus, and one supporting premise in #053, do not hold against the code (§2).

Three facts constrain every answer. The catalog holds about 39 skills, 15 of them (38%) `internal`, in repositories private to slaclab (Cogito TODO #200 counts, 2026-10-05, cited in #048). Submissions are GitHub-only (`_GITHUB_URL_RE`, #040, tightened by #045). The per-skill installer is prose in `skill/SKILL.md` that the user's agent executes, and every catalog request goes through `hub-request.sh` (#050).

## 1. AKH as Built

| Surface | What the code does | Evidence |
|---|---|---|
| Search | `/agent-knowledge-hub <query>` fetches every active skill from `GET /cli/api/skills/summary`, unpaginated, 11 fields per record, and the model ranks them in context. The endpoint's `q` parameter is a substring filter that Search does not send. `GET /api/skills?q=` uses a `$text` index on `name` and `description`. No vector search exists. | `skills_summary` in `backend/app/routers/catalog.py`; `skill/SKILL.md` › Search; text index in `backend/app/models/skill.py` |
| Request channel | `hub-request.sh` refuses any path holding a character outside `A-Za-z0-9._~/-`, so no query string, and allows five routes: GET summary, GET `skills/<slug>`, POST `me/installs/<slug>`, POST `skills/<slug>/rate`, POST `skills`. | `skill/hub-request.sh`, argument checks and route table |
| Install reach | Writes only to `~/.claude/skills/`, `~/.claude/commands/` and `~/.claude/agents/`. `compatible_platforms` is catalog metadata, inferred from `SKILL.md` and `AGENTS.md` and filterable under #025. It does not change where the installer writes. | `skill/SKILL.md` header; `_extract_platforms` in `backend/app/services/github.py` |
| Codex install | Shipped as #020 Slice 5 in `0ccd319`. Removed by `0be429a` (2026-06-08, "docs: overhaul presentation and trim agent-knowledge-hub skill"; the commit body says SKILL.md was "condensed from ~610 to ~90 lines"). `CHANGELOG.md` still lists the Codex install path, #020's Definition of Done still ticks it, and #051 › Follow-ups calls it "#020's planned Codex slice". | `git log -S '.codex' -- skill/SKILL.md`; `git show 0be429a` |
| Pin on the clone path | Install step 2 reads `git clone --depth 1 <repo_url> "$d/repo"`, "or check out the pinned SHA if present", and no step checks `HEAD` afterwards (#053). Until `0be429a`, the text specified a full clone without `--depth` for a pinned SHA. | `skill/SKILL.md` › Install step 2; `git show 0be429a` |
| Pin on the fallback path | "Fall back to the GitHub Contents API if git is unavailable", with no ref. `0be429a` removed the line "Use `?ref=<pinned_commit_sha>` on all calls if pinned SHA is set." | Same |
| Pinned share | 6 of 39 catalog skills had a `pinned_commit_sha` (15%) on 2026-10-05, although #017 sets the pin at create and ticks a backfill script. | #046 › Open Design Question 2, from Cogito TODO #200 |
| Pin on the files route | `get_skill_file` reads at `pinned_commit_sha`, else the branch, server-side through the GitHub App. Not yet an install path (#048). | `backend/app/routers/skills.py` |
| Marketplace route | `marketplace_json` emits `github` sources with no `ref` and no `sha`, and the documented URL answers 401. | `backend/app/routers/catalog.py`; #046 and #047 › Measured facts |
| MCP servers | The backend records `has_mcp_server` from `plugin.json`. The client prints an add command and never adds a server (#051). Nothing under `backend/`, `skill/`, `scripts/`, `frontend/app/` or `frontend/lib/` calls `tools/list`. #023 (Reviewed, not built) plans a well-known URL probe for `http` and `sse` servers and calls stdio servers "the majority". | `grep -rn tools/list` with no match; `_parse_plugin_json` in `github.py`; #023 ADR-U36 |
| Install record | One `SkillInstallEvent` per user and slug, upserted, with no commit SHA and no client name. `.installed-manifest.json` records commands, agents and server names, and no SHA. | `record_install` in `backend/app/routers/me.py`; `skill/SKILL.md` › Install step 5 |
| Earlier recommendations | None of the three items in `akh-skillnet-improvements.md` shipped: `quality_scores`, `min_stars` and `X-RateLimit-Reset` appear nowhere under `backend/app`. | `grep` with no match |

*High — read from code and git history on 2026-10-16.*

## 2. Corrections to Premises in the Corpus

1. **AKH installs into one client, not two.** `open-agent-hub.md` §7 and `skillnet-integration.md` §1 credit AKH with "claude-code + codex". That is `compatible_platforms` metadata. Install reach has been Claude Code only since `0be429a`, so the open-agent-hub comparison is 8 clients to 1. *High.*
2. **AKH never calls `tools/list`.** `mcp-registry-landscape.md` §6 says "AKH already calls `tools/list` at install time; it could index the resulting tool schemas". No code does, and #051 made it a rule that the client never adds or starts a server. The tool-level indexing design in `mcp-registry-for-akh.md` therefore has no source for its tool records (A-8). *High.*
3. **The marketplace route had no pin for CVE-2026-86063 to bypass.** `plugin4shell.md` §6 calls the marketplace route a direct exposure. `marketplace_json` emits no `sha`, so on that route Claude Code installs the default branch's tip, and the URL answers 401 anyway (#047). The exposure begins when #046 adds `sha` (I-1). §6's conclusion about client versions stands, and the Amendment, which concerns `skill/SKILL.md`, is unaffected. *High.*
4. **#053's risk register assumes a full clone that the install text no longer asks for.** Its second risk row says #022 uses a full clone for SHA-pinned installs, but `0be429a` replaced that with `--depth 1`. #053's FR-1 check still catches the result, since a checkout that fails or is skipped leaves `HEAD` different from the pin. The finding and the fix stand; what is missing is the instruction for obtaining the commit (A-1). *High.*

## 3. Ideas by Bucket

Each idea appears in exactly one bucket. The IDs (I-, A-, L-) are used again in Recommendations and Open Questions.

### 3.1 Integrate the external tool directly

**I-1 — Depend on Claude Code ≥ 2.1.179 for the `marketplace.json` route** (source: Plugin4Shell).
On that route the checkout belongs to Claude Code, and Air Security's point holds: "the pin is resolved on the client, so no marketplace can enforce the guarantee" (`plugin4shell.md` §5). AKH cannot reimplement that step, so it has to depend on the vendor's fix and state the minimum version.

The dependency is dormant today, because no `sha` is emitted and the route answers 401. It becomes load-bearing with #046 FR-1. Under #047 option B the minimum is met automatically, because a URL marketplace's `headersHelper` needs Claude Code 2.1.238 or later (recorded in Cogito TODO #200, not re-checked). Under option A nothing enforces it, so `README.md` has to state it. Cogito hosts already exceed it (2.1.281 on `sdfiana008`, #051 › Measured facts), so the minimum matters for S3DF users outside Cogito.

*Medium — the advisory refers to "a marketplace's pinned commit SHA"; whether the 2.1.179 fix covers `git-subdir` sources was not checked (Open Question 6).*

Nothing else in the batch qualifies. `npx skills`, the skill-retrieval-mcp server, asm, the `oah` linker and the agenticskills.io scorecard each fail on at least one count: no access-tier model, single-user local state, closed source, or an install path that skips #045, #051 and #053. Their ideas are placed below, and the tools themselves are L-1 to L-5.

### 3.2 Adopt the idea, build AKH's own

**A-1 — Make AKH's own pin real before anything trusts it** (sources: Plugin4Shell; asm, through its caution).
The asm concept file warns against copying a pinning mechanism nobody has verified. Applied to AKH's own pin, the warning finds five gaps. #053 (filed, P1) closes the first:

- (a) No `HEAD` check after checkout. This is #053, as filed.
- (b) The fallback path drops the pin. Without git, the client uses the Contents API with no ref, so a pinned skill installs from the default branch and nothing says so. #053's Non-Goals exclude the fallback. Restore `?ref=<pinned_commit_sha>`, which `0be429a` removed, or refuse the fallback for a pinned skill.
- (c) The clone instruction cannot reach a pin behind the tip, because a `--depth 1` clone holds only the tip commit. Say how to obtain the pinned commit: a full clone, as #022 specified, or a fetch by SHA. A fetch by SHA must then check out the SHA, never `FETCH_HEAD`, because a default branch named `FETCH_HEAD` is Plugin4Shell's Method 2 (`plugin4shell.md` §2). #053's check covers both.
- (d) 85% of the catalog has no pin. On 2026-10-05, 33 of 39 skills installed from the default branch with nothing to verify. Run #017's backfill on production, re-measure, and find out why `create()` left most skills unpinned (Open Question 2).
- (e) No install records a commit. Hermes's `HubLockFile` stores a hash per install (`hermes-agent-skills.md` §4). AKH stores none, so if a problem is found in commit X, AKH cannot tell the users who installed X. Record the verified SHA in `.installed-manifest.json` and in the install event.

This belongs in the adopt bucket because the clone path is AKH's own prose, and no external fix reaches it (`plugin4shell.md` › Amendment). (b) and (c) sit in the same install step as #053 and fit as an amendment to its scope. (d) is an operations run of an existing script. (e) is small and fits A-2.

**A-2 — Deterministic server-side scan, keyed to `pinned_commit_sha`** (source: asm's pre-install scanning; rule set from Hermes).
asm and Hermes both treat a pre-install scan as standard. asm's README does not document its rules (`asm.md` §2). Hermes's `skills_guard.py` does: six categories, and finding records with pattern, severity, file and line (`hermes-agent-skills.md` §3). So Hermes supplies the specification and asm confirms the expectation. The scan belongs in the backend, not in `skill/SKILL.md`:

- One implementation serves every client, including any future Codex path (A-6).
- It is code, not prose. #051 records what prose gates cost: the model, writing a file itself, lost a U+2028 in 2 of 4 hand-run installs, which is why `akh-mcp-file` became a fixed command.
- Each result belongs to one immutable commit. Run the scan at create, refetch and pin, and store findings per SHA. Return them in `GET /api/skills/<slug>`, and have the client print them before the clone, escaped the way #051 FR-4 escapes values.
- It needs the full file tree at that SHA. The manifest lists the top level only (ADR-U17), and `scripts/`, the content most worth scanning, sits below it. The Trees API (`docs/github-api-plugin-installation.md`) returns the whole tree in one call, and #048's Open Design Question 1 needs the same list.

Two constraints apply. First, show findings, never a "safe" badge. Regex rules miss obfuscated code, so a clean result means only "no match from N rules at commit X". Second, keep the scan separate from the LLM rubric in `akh-skillnet-improvements.md` Item 1. The scanned text is written by the submitter, and it can address the model that judges it.

The scan depends on A-1, because without it the scanned commit and the installed commit can differ. Someone also has to triage the findings, and the admin approval gate from `mcp-registry-for-akh.md`, which would provide that review, is unbuilt. This deserves its own todo.

**A-3 — Repository-hygiene facts and an RFC 9728 probe** (source: agenticskills.io's MCP scorecard).
The scorecard's repository checks are licence, `SECURITY.md`, a commit in the last 90 days, active contributors, CI, lockfile and SBOM (`agenticskills-find-skills.md` §5). They apply to every AKH entry, because every entry is a GitHub repository, and `github_fetcher.fetch()` already reads repository metadata on each refetch. Show each check as a dated fact, not as one combined grade. In agenticskills.io's own run, 45% of servers had no source to check and SBOM passed 0 of 25, so a combined grade would mostly measure what is missing.

The scorecard's endpoint check tests OAuth 2.1 metadata discovery per RFC 9728. #023 Pass 3 instead probes `/.well-known/mcp-server.json`. #023 ADR-U36 calls that path "a local convention for this project, not a ratified MCP specification" and notes that the MCP specification uses `/.well-known/oauth-protected-resource` per RFC 9728. Probe the RFC 9728 path, under the SSRF guard #023 already specifies.

The scorecard itself cannot be integrated: it is a closed site's one-off run (2026-08-07), with no API, covering MCP servers only. This fits as an amendment to #023 plus a fetcher change, with no new todo.

**A-4 — Resident and on-invoke token cost on each entry** (source: asm `stats --tokens`; figures from skill-retrieval-mcp).
asm separates what a skill costs while it sits in context from what it costs when it runs (`asm.md` §2). skill-retrieval-mcp puts numbers on both: about 99 tokens per skill for name and description (37,000 tokens for 374 skills), and about 2,400 tokens for one full skill (`skill-retrieval-mcp.md` §2). AKH stores `skill_md_raw` (#018), so the scan can compute two estimates and label them as such: frontmatter length, which is loaded every session, and body length, which is loaded on invocation. For a bundled MCP server the resident cost is its tool schemas, which AKH cannot see (A-8), so show "unknown", not zero. This is small and fits in A-2's scan.

**A-5 — Search: measure first, then server-side top-k** (source: skill-retrieval-mcp).
AKH's Search uses the approach skill-retrieval-mcp measures as its baseline: every name and description goes into context before any skill is read. By their per-skill figure, AKH's ~39 records, which carry nine fields besides name and description, cost at least 4,000 tokens per search. *Low — an estimate, not a measurement (Open Question 8).*

At this size, a frontier model ranking 39 descriptions in context is plausibly better than MiniLM retrieval. The case for change is therefore cost that grows with the catalog, and AKH has no evaluation that would show ranking quality either way. The order of work:

1. Build a held-out set of 30–50 queries, phrased the way S3DF users describe tasks, each with a set of acceptable answers. Score the current Search on Recall@k and MRR, the method skill-retrieval-mcp used (43 queries, `dev.md`).
2. Measure the summary payload in tokens.
3. Set a trigger: a token budget or a recall floor. When it fires, add a ranked route that returns the top 3 summaries, since their recall gained nothing between rank 3 and rank 5. Keep `GET /cli/api/skills/<slug>` as the second stage.

The new route has to fit the helper, which refuses `?q=`. That means a `POST /cli/api/skills/search` with a JSON body on standard input, the way `rate` takes its body, plus one route-table line in `hub-request.sh`, reviewed against #050.

No vector database is needed. skill-retrieval-mcp uses FAISS `IndexFlatIP`, which is exhaustive exact search, over 374 skills. AKH can likewise store one embedding per `Skill` document and score in process. For any catalog under a few thousand skills, this settles the backend question in `skillnet-integration.md` Open Question 4 and `mcp-registry-for-akh.md` Open Question 2. The cost is a local embedding model, a heavy addition to the backend image (#034, #036), to be weighed when the trigger fires.

**A-6 — Multi-client reach, conditional on demand** (source: open-agent-hub; corroborated by asm's 21 providers and agenticskills.io's 9 platforms).
The idea worth taking from open-agent-hub is its table of install paths per client. For AKH, "reach" means two different things:

- (i) From a Claude Code session, install a skill folder into another client's skill directory. This is cheap, because `SKILL.md` folders are portable.
- (ii) Run the client itself in another harness. This is expensive, because `skill/SKILL.md` depends on `${CLAUDE_SKILL_DIR}`, Claude Code's permission-rule syntax, `claude mcp add-json`, and Claude Code's subagent keys and built-in agent names.

Adopt (i) only, for the `skills` component. Report commands, agents and MCP servers as Claude Code only, the same way #051 prints a server's command rather than adding it. Copy, never link: `oah` links by symlink, while #051 FR-3 refuses links and manifest-based removal depends on copies.

Three things come first:

- Decide whether `0be429a`'s removal of the Codex path stands, and correct `CHANGELOG.md`, #020 and #051 › Follow-ups whichever way the decision goes.
- Find out which harnesses S3DF users actually run.
- Re-verify each target client's convention against its own source. For Codex the corpus holds two mechanisms it has not reconciled. #020 ADR-003, read from `codex-rs` in June 2026, describes a plugin route through `~/.codex/config.toml`. agenticskills.io's platform table lists `~/.codex/skills/` (*Low — partial capture, recorded in `_scratch/agenticskills-find-skills-raw.md`*).

This deserves its own todo, starting with the removal decision.

**A-7 — Install count as a trust signal** (source: agenticskills.io's copy of the `find-skills` skill, which follows skills.sh).
`find-skills` tells agents to prefer skills with more than 1,000 installs. AKH keeps one install event per user and skill but shows no count, and the aggregate is cheap to compute. It will undercount, because the install event is fire-and-forget and the user can decline it, and a threshold of 1,000 means nothing at SLAC's scale. Show it as "N S3DF users", not as a gate. Fold it into the existing P2 TOPICS row "Skill catalog trust model".

**A-8 — Tool-level MCP indexing: two-stage design, acquisition first** (source: skill-retrieval-mcp).
skill-retrieval-mcp does not fill this gap: it indexes `SKILL.md` files, not `ToolDefinition` records (`skill-retrieval-mcp.md` §3). Its two-stage design and token figures do carry over to the proposed `/tools/search`. The real obstacle comes before search design, though: AKH never obtains a tool list (§2.2). Each way of obtaining one costs something AKH has so far deferred:

- A stdio server, the majority per #023, lists its tools only when its command runs. That means running the submitter's code in AKH's cluster, the sandboxed execution both SkillNet reports deferred.
- An `http` or `sse` server needs an MCP handshake. Entries marked `auth.type: slac-sso` also need a credential AKH cannot pass (#051 FR-1 (e)).
- Tools declared by the author in `plugin.json` cost nothing to collect, but nothing verifies them.

Re-scope the open TOPICS row "Tool-level MCP indexing design" so that it starts with how AKH obtains the tool records.

### 3.3 Landscape only

| ID | Idea | Source | Why no action |
|---|---|---|---|
| L-1 | `npx skills` and skills.sh as an install or publishing route | open-agent-hub, agenticskills.io | A public AKH skill can already be installed with `npx skills add <owner>/<repo>@<skill>`, because it lives in a public GitHub repository; AKH need not enable this and cannot block it. Endorsing that route would drop the install event, #045's argument checks and #051's policy, and its pin behaviour is unknown because the corpus has not read `vercel-labs/skills`' install code. It reaches the 38% `internal` skills no better than a clone does; only #048's files route reaches them. Publishing to skills.sh would expose internal catalog metadata to the internet: #047 option A's disclosure concern, on a larger scale. |
| L-2 | The `oah` symlink linker, bundle-as-unit distribution, and `skills_sources.json` upstream sync | open-agent-hub | Bundles already exist as skillsets (#006). Links conflict with #051 FR-3. Pulling third-party skills into a curated set conflicts with the curation stance in `skillnet-integration.md` §3. |
| L-3 | Running skill-retrieval-mcp, or importing its 374-skill corpus | skill-retrieval-mcp | A single-user stdio server with local SQLite and FAISS under `~/.skill-mcp/` and no notion of visibility. Pointed at AKH, it would copy internal metadata onto every user's disk. Its corpus is public skills outside SLAC curation. A user can install it alongside AKH without any AKH change. |
| L-4 | asm's registry pinning, `audit`, `--json`/`--yes` CLI design, `init` scaffold | asm | The pinning mechanism is undocumented (`asm.md` §4). The corpus now records five independent pin implementations that omitted the same check, AKH's among them, so do not copy one nobody has read. AKH's client is already operated by an agent, and `create` already does what `init` does. |
| L-5 | Weekly editorial triage, paid featured placement, outbound link rerouting, and the `find-skills` heuristics other than A-7 | agenticskills.io | Covered by the admin approval gate in `mcp-registry-for-akh.md` and the open "Discovery UX patterns beyond search" row. Paid placement has no place in an institutional catalog. |
| L-6 | chops, entirely | chops | A local macOS editor for files already on disk. Its deduplication by resolved symlink path solves a problem AKH's copy-only installer does not create. It is evidence of demand for managing skills across tools, and gives AKH nothing to build. |

### 3.4 Verdict per source

| Source | Primary bucket | One line |
|---|---|---|
| open-agent-hub | Adopt (A-6, conditional) | Build the per-client install table as AKH code once users show demand and the removed Codex path is decided; the `oah` linker and `npx skills` are landscape. |
| skill-retrieval-mcp | Adopt (A-5, A-8; figures in A-4) | Measure Search first, move to server-side top-k when a trigger fires, and carry the two-stage design into the MCP indexing gap; the server and its corpus are landscape. |
| Plugin4Shell | Integrate (I-1) | Depend on Claude Code ≥ 2.1.179 for the marketplace route once #046 pins it; AKH's own install route is #053 plus A-1. |
| agenticskills.io find-skills | Adopt (A-3; A-7) | Repository-hygiene checks shown as dated facts, and RFC 9728 in place of #023's local probe path; the directory and its `npx skills` dependency are landscape. |
| chops | Landscape (L-6) | No action. |
| asm | Adopt (A-2; A-4) | A deterministic server-side scan tied to the pinned commit, and a token cost on each entry; asm's pinning is landscape and should not be copied unread. |

## 4. Effect on #046, #047 and #048

- **#046 changes meaning.**
  - FR-1's `sha` turns the marketplace route from unpinned into pinned by Claude Code's own checkout, which makes I-1 a requirement. FR-1 or the Definition of Done should name 2.1.179 as the minimum version, and AC-2 should be recorded with at least that version.
  - Open Design Question 2 carries more weight than its wording suggests. With 15% of the catalog pinned, most entries would install unpinned, with no check of any kind.
  - A further point, not from the batch, came up while checking I-1. On the native route, Claude Code loads the installed folder as a plugin, and Claude Code plugins can bundle hooks and MCP server configuration (Claude Code plugin documentation, not re-checked here). AKH's own client never loads that content: it strips `.claude-plugin/` and adds no server (#051 FR-1, FR-3). The native route therefore trades #051's content policy for vendor-maintained pin integrity. #046 should state which plugin components an entry may carry on that route. *Medium.*
- **#047, small change.** Option B meets the I-1 minimum automatically; option A needs it written in `README.md`. Option A's disclosure cost is the same reason L-1 rules out publishing to skills.sh. The batch gives no other reason to choose between A and B.
- **#048 is strengthened.**
  - The files route is the only AKH install path where AKH's own backend resolves the pin (`get_skill_file`). It is therefore the one place where Air Security's "no marketplace can enforce the guarantee" does not hold, because AKH serves the bytes itself. That is the batch's strongest argument for the script option in Open Design Question 3.
  - It is also where A-2's scan meets the install, with the same backend, the same commit and the same file list. Build the recursive tree that Open Design Question 1 needs and A-2's tree once.
  - The route falls back to the branch for an unpinned skill, which brings back A-1 (d).
- **`npx skills` changes none of the three** (L-1). #046 and #047 target Claude Code's marketplace schema, Codex has a schema of its own (#020 ADR-003), and skills.sh uses neither.

## 5. Relation to Prior Recommendations

- `akh-skillnet-improvements.md`: none of its three items has shipped. Item 1's LLM rubric remains a quality signal, but its Safety dimension cannot serve as a security gate (A-2).
- `skillnet-integration.md` §2.3 and Open Question 4, and `mcp-registry-for-akh.md` Open Question 2: exact in-process search at this scale settles the vector-backend question (A-5). The trigger changes from "defer until 50+ skills" to a token budget plus a recall floor.
- `mcp-registry-for-akh.md` › The Missing Layer: its premise is corrected (§2.2), and the row is re-scoped to start with acquisition (A-8). Its Recommendation 1, the admin approval gate, becomes the place where A-2's findings are triaged.
- `hermes-agent-skills.md` supplies the rule set for A-2 and the install record with a hash for A-1 (e). AKH already has a quarantine step, the `mktemp -d` clone (#051 FR-3), and structural refusals Hermes lacks. What it lacks is content rules and an install record that names a commit.
- `skillclaw.md`: `format_skills_compact`, which drops descriptions to save tokens, and `retrieve(top_k=6)` are a second precedent for A-4 and A-5. Nothing else carries over.

## 6. Adversarial Challenge

| # | Premise | Strongest counter-argument | Verdict |
|---|---|---|---|
| P1 | The access tier, the pin and #051's policy are AKH's core value, so tools that bypass them cannot be integrated. | AKH's 450-line prose installer reproduced a vendor CVE on its own. A maintained third-party installer might be safer than AKH's text. | Survives, narrowed. The maintained installer that fits is Claude Code's own, which is why I-1 exists. For `npx skills` the corpus has no evidence on pinning or private repositories (Open Question 3), and even a good answer would leave the `internal` skills, the install event and #051's policy uncovered. *Medium.* |
| P2 | The pinned commit can anchor scan results and "reviewed" signals. | 85% of the catalog is unpinned, the fallback path drops the pin, and the clone text cannot reach a pin behind the tip. | Fails as stated. A-2 is therefore sequenced after A-1 and gated on a fresh measurement of the pinned share. |
| P3 | At ~39 skills, the reason to change Search is cost, not quality. | No evaluation exists, so ranking quality is assumed, not known. | Survives only as "measure first": A-5 starts with the eval set, not the new route. |
| P4 | S3DF users want installs into clients other than Claude Code. | There is no data. Cogito hosts run Claude Code, and the Codex path disappeared in June with no recorded complaint. | Fails as an unconditional claim. A-6 is therefore conditional on demand data and starts with a decision on the removal. |
| P5 | The external claims in the concept files are accurate enough to design from. | Several come from READMEs only: asm's scanner and pinning, agenticskills.io's partial platform table, the internals of `npx skills`. | Survives, because only ideas are adopted, and each AKH design takes its specification from a primary source (Hermes's source code, RFC 9728, `codex-rs`), not from these READMEs. |

Different scale or rules would change the order. At thousands of skills, or with open public submission, A-5's trigger fires early and A-2 rises to P1. If AKH serves only Cogito sessions, A-6 drops out.

## Recommendations

1. **[A-1] Make the pin real first.** Ship #053 as filed. Amend its scope to cover two more gaps. For the Contents API fallback, restore `?ref=<pinned_commit_sha>` or refuse the fallback for a pinned skill. For the clone instruction, obtain the pinned commit with a full clone or a fetch by SHA, and check out the SHA, never `FETCH_HEAD`. Run #017's backfill on production and re-measure the pinned share. — *No new todo: amend #053 and run #017's script.*
2. **[I-1] Declare Claude Code ≥ 2.1.179 as the minimum version for the marketplace route.** Add it to #046 FR-1 or its Definition of Done, and to `README.md` when #046 and #047 ship. First confirm that the fix covers `git-subdir` sources. — *Fold into #046.*
3. **[A-2] Build a deterministic server-side scan tied to `pinned_commit_sha`.** Use Hermes's six categories as the rule set, run it over the full tree from the Trees API, and show findings only, never a pass badge. Record the installed SHA in the manifest and the install event. Start after item 1. — *Deserves its own todo (proposed P2).*
4. **[A-3] Add dated repository-hygiene facts to the fetcher, and switch #023 Pass 3 to RFC 9728's `/.well-known/oauth-protected-resource`.** — *Amend #023; no new todo.*
5. **[A-4] Compute resident and on-invoke token estimates in A-2's scan,** showing "unknown" for MCP tool schemas. — *Part of item 3's todo.*
6. **[A-5] Build the Search eval set and measure the summary payload now.** Add the ranked `POST /cli/api/skills/search` route, with exact in-process vector scoring, only when the trigger fires. — *A research row now; a todo when the trigger fires.*
7. **[A-6] Decide whether `0be429a`'s removal of the Codex path stands, and correct `CHANGELOG.md`, #020 and #051 to match.** Gather data on which harnesses users run before any cross-client install work. — *Deserves its own todo (proposed P2); its first deliverable is the decision.*
8. **[A-8] Re-scope the "Tool-level MCP indexing design" row to start with how AKH obtains tool records.** — *A TOPICS row edit, which the user owns.*
9. **[A-7] Fold unique-user install counts into the existing "Skill catalog trust model" row.** — *No new row.*
10. **[L-1 to L-6] No action.** Do not document `npx skills` as an AKH install route, and do not publish catalog metadata to skills.sh.

## Trade-offs & Risks

| Option | Benefit | Risk |
|---|---|---|
| Refuse the Contents API fallback for pinned skills (A-1 b) | The pin is never dropped silently | Users without git cannot install pinned skills; few such users on S3DF and Cogito |
| Restore `?ref=` on the fallback instead | Keeps the fallback | A second path to verify; #053's `rev-parse` check does not apply to it, so the fallback needs its own check |
| Server-side scan (A-2) | One implementation for every client, tied to the commit | False assurance if shown as a pass; regex rules can be evaded; Trees API calls on every refetch count against the GitHub App's rate limit |
| Scan written into the client prose | No backend work | Prose gates fail (#051's record); one copy per harness |
| Native marketplace route (#046 + I-1) | The vendor maintains pin integrity | Loads plugin components (hooks, MCP configuration) that AKH's client strips; Claude Code only |
| Hygiene facts without a grade (A-3) | No false precision | Users read several facts instead of one number |
| Exact in-process vector search (A-5) | No new datastore | An embedding model in the backend image, and an index rebuilt whenever the model changes (`skill-retrieval-mcp.md` §2) |
| Restore the Codex install (A-6) | The code exists in `0ccd319` | Edits `~/.codex/config.toml`, a second configuration format to keep correct; the mechanism may have changed since June |

## Open Questions

1. Was it deliberate that `0be429a` removed the Codex install path, the full clone for pinned SHAs and the Contents API `?ref=`? Settling this means restoring or formally dropping each one, then correcting `CHANGELOG.md` and the Definitions of Done in #017, #020 and #022.
2. What share of catalog skills carries a `pinned_commit_sha` today? Why did `create()` and #017's backfill leave 33 of 39 skills unpinned on 2026-10-05? A read-only count on production and the backfill's log would answer it.
3. Does `vercel-labs/skills` pin by commit, check `HEAD` after checkout, and handle private repositories? Reading its install code would answer it. Only an unexpected yes on all three would reopen L-1.
4. Which harnesses other than Claude Code do S3DF and Cogito users run? Install events carry no client field. A survey, or an optional client field in the install event's body, would answer it.
5. Which Codex mechanism is current: `~/.codex/skills/` (agenticskills.io's table), or the plugin route through `~/.codex/config.toml` (#020 ADR-003, June 2026)? Reading `codex-rs` at a pinned release would answer it.
6. Does the fix in Claude Code 2.1.179 cover `git-subdir` sources, and which plugin components does the native route activate from a folder that AKH's client would strip? The Claude Code plugin reference, plus a throwaway-`HOME` install like #051's tests, would answer it.
7. How should AKH obtain MCP `ToolDefinition` records: declared by the author in `plugin.json`, probed from `http` and `sse` servers, or run in a sandbox for stdio servers? The answer becomes the first step of the "Tool-level MCP indexing design" row.
8. How many tokens does the summary payload cost today, and how does the current Search score on a 30–50-query SLAC eval set? Both measurements set A-5's trigger.
9. What scan policy applies: which findings refuse an install, which are only printed, and who triages them while the admin approval gate is unbuilt?
10. Does asm check `HEAD` after it checks out a pin? This matters only if someone proposes reusing asm's code.

## Sources

First-party, read 2026-10-16:

- `README.md`, `CHANGELOG.md` (Codex install path entry), `TODO.md`, `.claude-plugin/plugin.json`
- `skill/SKILL.md`, `skill/hub-request.sh`
- `backend/app/routers/catalog.py` (`skills_summary`, `marketplace_json`), `backend/app/routers/skills.py` (`get_skill_file`), `backend/app/routers/me.py` (`record_install`), `backend/app/services/github.py` (`_parse_plugin_json`, `_extract_platforms`), `backend/app/services/search.py`, `backend/app/models/skill.py`, `backend/app/schemas/skill.py` (`SkillSummaryOut`)
- `docs/github-api-plugin-installation.md`
- [#017](../../todo/017-skill-version-pinning.md), [#020](../../todo/020-installer-skill-extension.md), [#022](../../todo/022-installer-git-clone.md), [#023](../../todo/023-mcp-server-registry.md), [#045](../../todo/045-sec-repo-url-skill-path-allowlist.md), [#046](../../todo/046-marketplace-git-subdir-sources.md), [#047](../../todo/047-marketplace-route-reachable.md), [#048](../../todo/048-install-from-files-route.md), [#051](../../todo/051-client-confirms-mcp-servers-and-agents.md), [#053](../../todo/053-sec-skill-install-sha-checkout-verification.md)
- git history: `0ccd319` (#020 Slice 5), `0be429a` (2026-06-08 condensation of `skill/SKILL.md`), `31e1d38` (#017), `8a57425` (#022); `git log -S '.codex'` and `git log -S '?ref='` over `skill/SKILL.md`

Corpus, read 2026-10-16:

- Concepts: [open-agent-hub](../concepts/open-agent-hub.md), [skill-retrieval-mcp](../concepts/skill-retrieval-mcp.md), [plugin4shell](../concepts/plugin4shell.md) (including its 2026-10-16 Amendment), [agenticskills-find-skills](../concepts/agenticskills-find-skills.md), [chops](../concepts/chops.md), [asm](../concepts/asm.md), [hermes-agent-skills](../concepts/hermes-agent-skills.md), [skillclaw](../concepts/skillclaw.md), [mcp-registry-landscape](../concepts/mcp-registry-landscape.md)
- Reports: [mcp-registry-for-akh](mcp-registry-for-akh.md), [skillnet-integration](skillnet-integration.md), [skillnet-scripts-analysis](skillnet-scripts-analysis.md), [akh-skillnet-improvements](akh-skillnet-improvements.md)
- `_scratch/agenticskills-find-skills-raw.md` (agenticskills.io platform table, partial capture)

No external URL was fetched for this report. Claims about external projects carry the fetch dates and confidence levels of the concept files listed above.
