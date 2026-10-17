# TODO #056 — The client's skill description says when to use it

> **Priority:** 🔵 P3 — Low
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-16
> **Shipped:** —

---

## Provenance

**Raised by:** Cogito (`slaclab/cogito`) TODO #223, an audit of Cogito's Claude Code skills against
Anthropic's documentation, 2026-10-16. Cogito asks for it as hub request H-8.

**References:**

- Cogito TODO #200 — Cogito's host image carries this client as a managed skill, pinned by commit,
  so it is listed in every Claude Code session on that image.

---

## Problem Statement

`skill/SKILL.md`'s frontmatter description, 92 characters, says what the client does and not when
to use it:

> Discover, install, rate, and submit SLAC S3DF catalog skills from within your agent session.

Claude Code decides whether to load a skill from its description. Anthropic's documentation asks
the description to say "what the skill does and when to use it", and to put the key use case first
(`code.claude.com/docs/en/skills`). Every other skill that Cogito's image carries names the requests
it answers, with a "Use when" clause. Without one, a session is less likely to reach for the client
when a user asks, in their own words, for a SLAC skill for a task, such as one for EPICS archiver
data or for Slurm jobs.

## Goals

1. The description keeps its first sentence and adds a "Use when" clause that names the user's
   requests: finding a SLAC or S3DF skill for a task or a facility, installing, updating or
   removing one, installing a skill set, rating one, and submitting one's own. It stays well under
   Claude Code's limit of 1,536 characters for the description and `when_to_use` together.
2. The client's version moves, so that installs and Cogito's lock can name the change.

## Non-Goals

- No change to the client's commands or its helper.
