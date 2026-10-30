# TODO #055 — Decide whether the silently-removed Codex install path should be restored or formally dropped

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-16
> **Shipped:** —

---

## Provenance

**Raised by:** `research/reports/oct2026-skill-hub-batch-vs-akh.md`, Recommendation 7 (finding A-6)
and § AKH as Built ("Codex install" row), § Corrections to Premises in the Corpus item 1. The report
traced, via `git log -S '.codex' -- skill/SKILL.md` and `git show 0be429a`, that AKH shipped a Codex
install path in #020 Slice 5 (`0ccd319`), which was then silently removed by `0be429a` (2026-06-08,
"docs: overhaul presentation and trim agent-knowledge-hub skill" — a commit labelled `docs` that
shrank `skill/SKILL.md` from roughly 610 to 90 lines and, in the same pass, also dropped the pin
handling #053 restores). `CHANGELOG.md`, #020's Definition of Done, and #051's Follow-ups all still
describe or assume a working Codex install path.

**References:**
- [#020](020-installer-skill-extension.md) — shipped the Codex path this task concerns; its
  Definition of Done still has the Codex item checked.
- [#051](051-client-confirms-mcp-servers-and-agents.md) — its Follow-ups section calls the Codex
  path "#020's planned Codex slice," unaware it shipped and was then removed.
- `CHANGELOG.md` — still lists the Codex install path as shipped.
- [#053](053-sec-skill-install-sha-checkout-verification.md) — if Codex is restored, its install path
  needs the same pin-verification guarantees (FR-1, FR-4, FR-5) #053 defines for the Claude Code path.
- `research/concepts/open-agent-hub.md` §7 and `research/reports/skillnet-integration.md` §1 — both
  credit AKH with "claude-code + codex" reach, a premise this finding corrects.

---

## Problem Statement

AKH's install reach has been Claude Code only since `0be429a` (2026-06-08), but three other
documents — `CHANGELOG.md`, #020's Definition of Done, and #051's Follow-ups — still describe or
assume a working Codex install path. Nobody has recorded whether the removal was a deliberate
decision (for example, because Codex's own skill mechanism had changed and AKH's copy had gone
stale) or an unintended side effect of a commit whose own message framed it as a documentation and
presentation pass, not a functional change.

The corpus itself holds two different, unreconciled claims about what Codex's *current* skill
mechanism even is: a `~/.codex/config.toml` plugin route, read from `codex-rs` in June 2026 (#020
ADR-003), versus a `~/.codex/skills/` directory convention (`research/concepts/agenticskills-find-skills.md`'s
platform table — Low confidence, a partial capture per `_scratch/agenticskills-find-skills-raw.md`).
Restoring the old path without checking which of these is still accurate risks shipping a Codex
install that no longer matches the client.

---

## Goals

1. Determine, as best as can be reconstructed, whether `0be429a`'s removal of the Codex install path
   was intentional. "Could not be determined" is an acceptable outcome of this step.
2. Decide: restore the Codex install path, or formally drop it. Either way, correct `CHANGELOG.md`,
   #020's Definition of Done, and #051's Follow-ups to match reality — the current state, where all
   three assert a capability that does not exist, is the one outcome this task must not leave in place.
3. Before choosing to restore, get at least a rough signal on whether any S3DF or Cogito user
   actually runs Codex — install events carry no client field today (see `research/TOPICS.md` row
   "Which harnesses do S3DF / Cogito users actually run besides Claude Code?"), so this may require a
   quick survey or a one-off instrumentation change rather than existing data.

## Non-Goals

- Does not implement multi-client reach beyond Codex (open-agent-hub's 8-client table — finding A-6
  is explicit that broader reach should wait for demand data, independent of this decision).
- Does not change #053's design — if Codex is restored, giving its install path the same pin
  guarantees #053 defines is this task's implementation detail if the decision is "restore," not a
  reason to expand this task's own scope now.
- Does not resolve, as part of this task's own research, which Codex mechanism (`config.toml` vs.
  `~/.codex/skills/`) is current — that is the separate `research/TOPICS.md` open question "Which
  Codex skill mechanism is current," which gates the "restore" option. This task can still deliver
  "formally drop" without that question being answered first.

## Rationale

Cheap to resolve (a decision plus corrections to three already-incorrect documents), but left
unresolved it means three separate documents keep asserting a capability that silently does not
exist — which will mislead whoever next reads #020, #051, or `CHANGELOG.md` expecting a working
Codex path to be there.

---

## Design

N/A — this is a decision-and-documentation task. If the decision is "restore," implementation is a
separate, re-scoped follow-on task once the Codex-mechanism open question is answered, not built
under this task's own number.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Restoring against the stale June-2026 understanding of Codex's mechanism (#020 ADR-003) re-ships a broken path | Medium | Low | Goal 1/2's "restore" option requires re-verifying against a current `codex-rs` read, not reusing ADR-003's snapshot |
| No one can determine whether the removal was deliberate (no recorded discussion, author unavailable) | Medium | Low | Goal 1 is best-effort; Goal 2's correction of the three stale documents is required regardless of whether intent can be established |

---

## Definition of Done

- [ ] Removal intent documented, or explicitly recorded as "could not be determined"
- [ ] Decision recorded: restore, or formally drop
- [ ] `CHANGELOG.md`, #020's Definition of Done, and #051's Follow-ups corrected to match the decision
- [ ] If restored: Codex's current mechanism re-verified against `codex-rs`, and the install path
      carries the same pin-verification guarantees #053 defines for the clone-based path

---

## Board Review

> *Populated by `/board-review` after the board completes. Do not fill manually.*

---

## Relationship to Other Tasks

- **#020 (Installer skill extension):** Shipped the path this task concerns; its Definition of Done
  needs correcting regardless of which way this task's decision goes.
- **#051 (Client confirms MCP servers and agents):** Its Follow-ups section references the Codex
  slice as still-planned; needs correcting.
- **#053 (Verify post-checkout HEAD):** If Codex is restored, its install path needs the equivalent
  pin-verification guarantees #053 defines for the Claude Code path.
- **`research/TOPICS.md`:** "Which harnesses do S3DF / Cogito users actually run besides Claude Code?"
  and "Which Codex skill mechanism is current?" are open questions this task should consult before
  choosing to restore.
