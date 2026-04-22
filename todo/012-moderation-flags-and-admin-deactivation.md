# TODO #012 — Moderation: User Flags and Admin Deactivation

> **Priority:** 🟠 P1 — High
> **Status:** 📋 Preparing
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

The catalog has no moderation loop. `SkillFlag` and `SkillStatus.deactivated` already exist in the backend data model, but:

- No API route lets users submit a flag
- No API route lets admins view, resolve, or act on flags
- No API route lets admins deactivate a skill
- The `FlagIndicator` component shows a count on the detail page but it's always zero (no flags are ever written)
- Admins have no UI surface to take action on flagged or bad skills

The result: bad, broken, or superseded skills accumulate in the catalog with no mechanism for the community to signal problems or for admins to clean up.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| User notices a skill is broken | No action possible | User can flag it with a reason |
| User flags the same skill twice | Not prevented | Deduplicated per reporter |
| Admin sees skills with high flag counts | No visibility | Admin queue shows flagged skills sorted by flag count |
| Admin wants to disable a harmful skill | No mechanism | Admin can deactivate with a reason; skill shows tombstone |
| Admin wants to mark a skill superseded | Manual edit only | Admin can set `superseded_by_slug` and deactivate atomically |
| Admin resolves a flag | Not possible | Admin marks flag resolved with a note; flag count decrements |

---

## Goals

1. **User flagging** — authenticated users can flag a skill with a reason (broken, stale, superseded, inappropriate, other) and optional note; one active flag per user per skill
2. **Flag indicator** — `FlagIndicator` on the detail page reflects real flag counts; logged-in users see whether they've already flagged it
3. **Admin flag queue** — `/admin/flags` page lists active flags sorted by count; admin can view reason/notes per flag
4. **Admin deactivation** — admin can deactivate a skill (with reason) from the detail page or admin queue; skill shows tombstone to all users
5. **Admin reactivation** — admin can reactivate a previously deactivated skill
6. **Flag resolution** — when admin deactivates or dismisses, active flags for that skill are marked resolved

## Non-Goals

- Auto-deactivation based on flag threshold (can be a future follow-on)
- Special-label approach for flags (labels are community taxonomy; moderation state is a first-class field — keep them separate)
- Email/Slack notifications to admins on new flags (future)
- User appeals process

---

## Design

> *To be filled in by `/codebase-draft`.*

### Key Decision: Labels vs First-Class Fields

The user suggested "special labels" as an implementation approach. Recommendation: **don't use labels for moderation state**. Labels are community taxonomy (searchable, filterable, multi-value). Deactivation and flag status are boolean/enum system state that affects visibility and routing. Mixing them would let users manipulate moderation state via the label API and would pollute label search results with system values. The existing `SkillStatus` and `SkillFlag` models are the right home.

### Existing Backend Assets

- `SkillFlag` model with `FlagReason`, `FlagStatus`, `reporter_id`, `resolved_by`, `resolution_note` — fully defined, no router exists yet
- `SkillStatus.deactivated` + `deactivation_reason` on `Skill` — model and schema exist; `deactivate`/`reactivate` revision actions exist; no admin route exposes them
- `FlagIndicator` frontend component reads `flag_count` from skill — count is always 0 today

### Open Questions

1. **Should flagging require a reason or is a one-click flag sufficient?** — Recommendation: require a reason (drives better admin triage) with an optional free-text note, same as the existing `FlagReason` enum.
2. **Should users see who flagged a skill?** — Recommendation: no — `reporter_id` is admin-only; public UI shows only the count.
3. **Should the flag button be visible to the skill's own submitter?** — Recommendation: yes (they might want to flag their own as stale); admins can always see and resolve.
4. **Admin route prefix: `/admin/flags` or extend existing `/admin/labels`?** — Recommendation: separate `/admin/flags` page; the admin layout already handles auth gating.

---

## Implementation Plan

> *To be filled in by `/codebase-draft`.*

---

## Implementation Checklist

- [ ] Backend: `POST /skills/{slug}/flag` — create flag (auth required, deduplicated)
- [ ] Backend: `DELETE /skills/{slug}/flag` — retract own flag
- [ ] Backend: `GET /admin/flags` — list active flags with skill info, sorted by count
- [ ] Backend: `POST /admin/skills/{slug}/deactivate` — deactivate with reason (admin only)
- [ ] Backend: `POST /admin/skills/{slug}/reactivate` — reactivate (admin only)
- [ ] Backend: resolve all active flags when skill is deactivated
- [ ] Frontend: flag button on skill detail page (authenticated users)
- [ ] Frontend: `FlagIndicator` reflects real counts; shows "flagged by you" state
- [ ] Frontend: `/admin/flags` queue page
- [ ] Frontend: deactivate/reactivate action on detail page for admins
- [ ] Tests written and passing

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

> *Populated by `/codebase-board-review` after the board completes. Do not fill manually.*

**Verdict:** —
**Date:** —
**Rounds:** —

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — | — | — |
| codebase-arch-review | — | — | — |
| codebase-eng-review | — | — | — |
| codebase-doc-review | — | — | — |
| security-review | — | — | — |

---

## Relationship to Other Tasks

- **#003 (Label UX):** Labels and flags are explicitly kept separate — see Key Decision above.
- **#008 (Auth hardening):** Admin-only routes depend on reliable identity from the hardened auth header.
- **#011 (User activity):** Flag activity (skills a user has flagged) could appear on the user profile as a future extension.
