# TODO #054 — Deterministic server-side security scan, keyed to the pinned commit

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-16
> **Shipped:** —

---

## Provenance

**Raised by:** `research/reports/oct2026-skill-hub-batch-vs-akh.md`, Recommendation 3 (finding A-2)
and Recommendation 5 (finding A-4), written while assessing whether to integrate asm's pre-install
scanning or AKH's own version of the idea. asm and Hermes both treat a pre-install security scan as
a baseline expected feature in this space; AKH has none today, since #019's scan pipeline discards
everything except structural metadata (`has_mcp_server`, labels, component lists).

**References:**
- [#053](053-sec-skill-install-sha-checkout-verification.md) — this task's findings are only
  trustworthy once #053 makes the pin real; the scanned commit and the installed commit can
  otherwise differ. Sequenced after #053.
- [#018](018-skill-file-cache.md) — already stores `skill_md_raw`, reused here for the resident/body
  token-length split (A-4).
- [#048](048-install-from-files-route.md) — shares the backend, the pinned commit, and the recursive
  file-tree need; its Open Design Question 1 needs the same file list this scan needs.
- `docs/github-api-plugin-installation.md` — the Trees API, the only way to get the full recursive
  file tree in one call (the stored manifest lists the top level only, per ADR-U17; `scripts/`, the
  content most worth scanning, sits below it).
- `research/concepts/hermes-agent-skills.md` §3 — the rule set this task borrows: six documented
  threat categories, with finding records carrying pattern, severity, file, and line. asm's own
  README does not document its scanner's rules (`research/concepts/asm.md` §2), so Hermes supplies
  the specification and asm only confirms the expectation exists.
- `research/reports/mcp-registry-for-akh.md` Recommendation 1 — the (unbuilt) admin approval gate
  that would triage this task's findings. Not built by this task.
- `research/TOPICS.md` row "What scan policy applies to a pre-install security scan, and who
  triages findings?" — the open question this task's Definition of Done does not resolve.

---

## Problem Statement

AKH has no server-side inspection of a submitted skill's actual file contents. `backend/app/services/github.py`'s
`_parse_plugin_json()` reads structure (components, MCP server declarations, platform tags) but never
looks at what a script, hook, or skill body actually does. The only other signal in the corpus is the
unbuilt LLM-based quality rubric proposed in `reports/akh-skillnet-improvements.md` Item 1, which
judges quality, not security, and which a submitter's own text can address, since it is a model
reading prose.

---

## Goals

1. A deterministic (rule-based, not LLM-judged) scan runs server-side at `create()`, `refetch()`, and
   `pin()`, over the full file tree resolved at the commit being stored — using the Trees API, since
   the stored manifest only lists the top level.
2. The rule set is Hermes's six documented threat categories (`research/concepts/hermes-agent-skills.md`
   §3), since it is the only one of the sources in this batch with its categories actually published.
3. Findings are stored keyed to the commit SHA they were run against — re-pinning to a new commit
   invalidates stale findings rather than silently keeping them.
4. Findings are returned in `GET /api/skills/<slug>` and the client (`skill/SKILL.md`) prints them
   before the clone step, escaped per #051 FR-4's escaping convention.
5. A clean scan result is shown as "no match from N rules at commit X," never as a "safe" or "pass"
   badge — regex-based rules miss obfuscated or encoded payloads, and the UI must not claim more
   confidence than the method supports.
6. Resident and on-invoke token-cost estimates are computed and shown per entry alongside the scan
   (finding A-4): frontmatter length (loaded every session) versus body length (loaded on invocation),
   using the already-stored `skill_md_raw` (#018). For a bundled MCP server, show "unknown" for
   resident cost, not zero — AKH cannot currently see a server's tool schemas (see the TOPICS.md
   "Tool-level MCP indexing design" row).

## Non-Goals

- Does not replace or change the separate, unbuilt LLM quality rubric in
  `akh-skillnet-improvements.md` Item 1 — that judges quality; this judges fixed security patterns.
  Keeping them separate matters because submitter-written text can address a model-based judge in
  ways a fixed-rule scan resists.
- Does not add an admin triage or approval workflow — that is the admin approval gate in
  `mcp-registry-for-akh.md` Recommendation 1, currently unbuilt. This task produces findings; what
  policy applies to them (refuse vs. display-only, who reviews) is the separate open question
  tracked in `research/TOPICS.md`.
- Does not default to blocking an install on any finding — the same open scan-policy question
  applies; absent a decision, findings are shown, never enforced.
- Does not attempt sandboxed dynamic execution of submitted code — static, rule-based scanning only,
  matching Hermes's approach rather than SkillNet's "executability" dimension, which both existing
  SkillNet reports in this corpus already deferred as out of scope for AKH.

---

## Design (sketch — not yet through `/draft-prd`)

A new scan step, alongside the existing `github_fetcher.fetch()` call in `create()`/`refetch()`/
`pin()`:

1. Resolve the commit being stored (the new, or re-pinned, `pinned_commit_sha`).
2. Fetch the full recursive file tree at that commit via the Trees API (`GET
   /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`).
3. For each file, fetch content and run Hermes's six categories as pattern/regex rules.
4. Store findings as a list of `{pattern, severity, file, line}` records, associated with the commit
   SHA they were produced against — not with the skill record in general, so a later re-pin cannot
   silently keep a stale result attached to a different commit.
5. Alongside the scan, compute `resident_tokens` (frontmatter) and `invoke_tokens` (body) from
   `skill_md_raw`, or `null`/"unknown" when a bundled MCP server's tool schemas are involved.
6. Surface both in `GET /api/skills/<slug>`; `skill/SKILL.md` prints findings (escaped per #051 FR-4)
   before the clone step in the install flow.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A "no findings" result is read by a user as "verified safe" | Medium | Medium | Goal 5 — UI and API never render an absence of findings as a pass/safe signal |
| Regex rules miss obfuscated or encoded payloads | High (inherent to the method) | Medium | Same limitation Hermes's own `skills_guard.py` has; documented, not solved by this task |
| Trees API calls on every refetch add to the GitHub App's rate-limit pressure | Unknown until measured | Low–Medium | Measure against current refetch frequency before shipping; the files route (#048) needs the same tree, so the cost can be shared |
| Scope creeps into the quality-rubric or admin-approval-gate territory | Low, if Non-Goals are respected | Low | Non-Goals above draw the line explicitly |

---

## Definition of Done

- [ ] Deterministic scan runs at `create()`/`refetch()`/`pin()`, keyed to the resolved commit SHA
- [ ] Findings stored and returned in `GET /api/skills/<slug>`
- [ ] Client prints findings before the clone step, escaped per #051 FR-4
- [ ] Resident/on-invoke token estimates computed and shown per entry (A-4), "unknown" for MCP tool schemas
- [ ] No UI or API surface presents an absence of findings as "safe" or "verified" — audited explicitly
- [ ] CHANGELOG entry added under `## Unreleased`

---

## Board Review

> *Populated by `/board-review` after the board completes. Do not fill manually.*

---

## Relationship to Other Tasks

- **#053:** This task's findings are meaningful only once #053 makes the pin real — sequenced after it.
- **#018 (Skill file cache):** Supplies `skill_md_raw`, reused for the token-cost estimate.
- **#048 (Install-from-files route):** Shares the backend, the pinned commit, and the recursive
  file-tree requirement.
- **`research/reports/mcp-registry-for-akh.md`:** Its unbuilt admin approval gate is the natural
  home for triaging this task's findings — a separate, not-yet-decided piece of work.
