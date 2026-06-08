# TODO #029 — Skillset Cross-Ownership: Add Skills to Other Users' Skillsets

> **Priority:** 🔵 P3 — Low
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-06-03
> **Shipped:** —

---

## Problem Statement

In #006, adding a skill to a skillset is restricted to the skillset owner (or admin). This covers the primary use case — a curator managing their own set — but leaves a gap: a user who submits a new skill via `/skills/submit?skillset=<slug>` targeting *someone else's* skillset will have their `skillset_slug` param silently ignored.

This is the right default (you can't inject your skills into someone's curated list without their consent), but there's no approval path yet.

### What fails today (post #006)

| Scenario | Behaviour |
|---|---|
| Submit new skill with `?skillset=<other-owner-slug>` | Skill created, skillset param silently ignored |
| Want my skill included in a colleague's LCLS starter set | No mechanism — must ask the curator manually out-of-band |
| Curator wants to invite contributions to their skillset | No invite/request flow exists |

---

## Goals

1. A skill submitter can *request* that their skill be added to a skillset they don't own
2. The skillset owner receives a notification (or sees a queue) and can approve or reject the request
3. Approval auto-adds the skill to the skillset; rejection discards the request

## Non-Goals

- Automatic approval (always requires owner consent)
- Request expiry or notifications via email/Slack (in-app queue only for v1)
- Bulk request workflows

---

## Open Design Questions

The following need to be answered before a full PRD can be written:

1. **Request mechanism** — should the request be created at skill-submit time (via `skillset_slug` param on a non-owned skillset), as a separate action from the skill detail page ("Request to add to skillset"), or both?
2. **Notification** — how does the skillset owner find out about pending requests? A badge on their skillset detail page? A dedicated `/skillsets/[slug]/requests` sub-page? A count in the top nav?
3. **Request visibility** — can the requester see the status of their request (pending/approved/rejected)?
4. **Data model** — new `SkillsetMemberRequest` collection, or extend `SkillsetMember` with a `status` field?

---

## Relationship to Other Tasks

- **#006 (Skillsets):** Cross-ownership is explicitly deferred there. `SkillCreate.skillset_slug` silently ignores non-owned targets — this task adds the request flow as the resolution path.
