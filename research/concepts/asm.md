> **Concept:** asm (agent-skill-manager) — Cross-Provider Skill CLI
> **Source:** GitHub (`luongnv89/asm`) — README, repo metadata
> **Relevance:** A close functional comparator to AKH — cross-agent skill discovery, install, and
> pre-install security scanning, built as a client-side CLI rather than a hosted marketplace

*Generated 2026-10-16 / Confidence: Medium-High (README + repo metadata only; scanner and pinning internals not verified against source code, flagged explicitly below)*

---

## 1. Overview

`asm` (package name `agent-skill-manager`, github.com/luongnv89/asm) is a Node.js/TypeScript CLI
for discovering, installing, auditing, and managing AI agent skills across 21 different
agent/tool providers — including Claude Code, Codex, Cursor, GitHub Copilot, Cline, Windsurf,
Gemini CLI, and others. Its README reports a catalog of 6,905+ skills aggregated from 85 source
repositories. Confirmed as the correct project for this research (not a namesake collision with an
unrelated assembler or similar generically-named "asm" tool): the repo's description, topics
(`agents`, `ai`, `aiagents`, `coding`, `skills`), and README content are unambiguously about AI
agent skill management.

Of the three sources in this batch, asm is the closest functional match to AKH's own problem
space — both are systems for discovering, vetting, and installing third-party agent skill
packages across multiple client tools.

## 2. How It Works

asm is explicitly designed to be both human- and agent-operable: every command supports a
`--json` output mode and a `--yes` non-interactive flag, which the README frames as making the
tool directly callable by an AI agent on its own behalf, not only by a human operator at a
terminal.

Core commands: `asm list` (cross-provider inventory of installed skills in one view), `asm search
"query" --json` (catalog search), `asm install github:user/repo --yes` (fetch, place, and register
a skill across the relevant provider's directory convention), `asm audit --yes` (detect duplicate
or orphaned skills across providers), `asm stats --tokens` (token-cost accounting), and `asm init
my-skill -p claude` (skill authoring/scaffolding — functionally analogous to AKH's own
`/agent-knowledge-hub create`).

The README calls out a "pre-install security scanning" step that checks for shell execution,
credential access, and network-call patterns before a skill is installed, and a "registry pinning"
capability aimed at the same manual-install-friction problem AKH's `/agent-knowledge-hub submit`
flow addresses. Neither the scanning categories nor the pinning mechanism are specified in detail
in the README (no pattern list or severity taxonomy comparable to Hermes's documented six-category
regex scanner was found) — treat these as stated capabilities, not verified implementations, since
this pass did not read asm's source.

A notable feature with no direct AKH equivalent: "attention budget" / token accounting (`asm stats
--tokens`), which distinguishes the token cost of a skill sitting resident in context from the cost
only paid when its body actually executes. This addresses a cost dimension AKH's own catalog model
does not currently surface.

## 3. Key Facts

| Fact | Detail |
|------|--------|
| Repo | github.com/luongnv89/asm, npm package `agent-skill-manager` |
| License | MIT |
| Language / runtime | TypeScript / Node.js 22+ |
| Stars | ~957 (at fetch time) |
| Catalog size (self-reported) | 6,905+ skills from 85 repositories |
| Providers supported | 21 (Claude Code, Codex, Cursor, GitHub Copilot, Cline, Windsurf, Gemini CLI, Hermes, OpenClaw, Roo Code, Continue, Aider, Zed, Augment, Amp, and others per README) |
| Install surface | CLI only — no hosted web catalog; explicitly "no accounts, no telemetry" |

## 4. Relevance to AKH

asm is a direct comparator, not a landscape footnote — both systems exist to solve the same
problem (discover, vet, and install third-party agent skills) but at different layers. asm is a
client-side CLI with no server component: its catalog, security scanning, and pinning all run
locally on the installing machine, with no hosted web presence, rating system, or access-tier
model. AKH is the inverse: a centralized, hosted marketplace with a web catalog, community ratings,
label-based discovery, and an institutional access tier (public vs. "SLAC Members Only" private
GitHub repos).

Two points carry over directly:

- **Pre-install security scanning as a stated, marketed feature.** asm's README treats a
  pre-install scan as a core selling point, the same way Hermes's `skills_guard.py` does (see
  `concepts/hermes-agent-skills.md`) — further evidence that a visible, user-facing trust signal
  at install time is now a baseline expectation in this space, not a differentiator AKH could skip.
  Unlike Hermes, asm's README does not document its scanner's categories or verdict logic in
  enough detail to compare rigor directly; that would require reading asm's source, out of scope
  here.
- **Token/attention-budget accounting is a feature AKH does not currently have an analogue for.**
  Worth flagging as a backlog candidate (surfacing a skill's context-token cost on its catalog
  page) rather than something to build immediately — it is an open idea, not a researched
  recommendation in this pass.

One point requires caution rather than reuse: asm's README mentions "registry pinning" without
specifying the mechanism. Given `concepts/plugin4shell.md` in this same corpus documents a
commit-SHA-pinning bypass that recurred independently across four separately-built agents because
each omitted a post-checkout integrity check, any pinning mechanism — asm's included — should be
verified, not assumed safe, before treating it as a reference implementation. This research pass
makes no claim either way about asm's exposure to that specific bypass; it is noted here only as a
reason not to copy asm's pinning approach into AKH without first reading asm's actual install
code.

## 5. Known Gaps / Limitations

No hosted catalog, ratings, or community-visible trust signal beyond what the CLI itself
computes locally at install time — asm's "no accounts, no telemetry" design is a deliberate
trade-off for a different audience (individual developers wanting a local tool) and is not a model
AKH should adopt, since AKH's value proposition includes the community rating/discovery layer that
a telemetry-free local CLI structurally cannot provide. The security-scanning and pinning
mechanisms are both under-documented in the README relative to their stated importance; this
concept file could be strengthened with a follow-up pass that reads asm's actual scanner and
installer source rather than relying on README framing alone.

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — pre-install scanning adopted as an AKH-native server-side scan keyed to `pinned_commit_sha` (A-2); token accounting adopted (A-4); registry pinning landscape-only, not to be copied unread (L-4)

## Sources

- https://github.com/luongnv89/asm — fetched 2026-10-16
- https://raw.githubusercontent.com/luongnv89/asm/main/README.md — fetched 2026-10-16
