# TODO #011 — User Activity Profile: Skills by User

> **Priority:** 🟡 P2 — Medium
> **Status:** 📋 Preparing
> **Branch:** —
> **PR:** —
> **Created:** 2026-04-22
> **Shipped:** —

---

## Problem Statement

There is no way to see what a specific user has done in the catalog. If you want to find skills submitted by a colleague, you have to search by name and hope. There is no profile page or activity view. The revision history already records `actor_id` for every create/edit/refetch action, so the data exists — it's just not surfaced.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|----------|-------------------|-------------------|
| "Show me skills submitted by alice" | No way to filter/view | Skills page filtered to submitter_id=alice |
| "Show me skills alice has edited" | Not possible | Skills page or profile shows skills alice has an edit revision on |
| "Show me skills I've downloaded / installed" | Not tracked | Per-user download/install event log surfaced on profile |
| Clicking a contributor name in the detail header | Nothing | Navigates to user activity view |

---

## Goals

1. A user activity page (e.g. `/users/<user_id>`) showing:
   - Skills submitted by the user
   - Skills the user has edited (has at least one revision with `action=edit` and `actor_id=<user>`)
   - Skills the user has downloaded/installed (if download events are tracked)
2. Contributor names in the skill detail header are clickable links to that user's activity page
3. Backend API endpoint(s) to query skills by contributor role
4. Download/install tracking if not already in place (or scoped as a sub-task)

## Non-Goals

- Full user profile (avatar, bio, social links) — this is an activity view, not a social profile
- Following/subscribing to users
- Email notifications about user activity
- Admin user management UI (separate concern)

---

## Design

> *To be filled in by `/codebase-draft`.*

### Open Questions

1. **Are download/install events tracked today?** — If not, is tracking them in scope for this task or a separate sub-task?
2. **Is there a concept of "install" distinct from "view"?** — The `/agent-knowledge-hub` skill triggers installs; does the backend record them?
3. **URL scheme: `/users/<user_id>` or `/skills?submitted_by=<user_id>`?** — Recommendation: a dedicated `/users/<user_id>` page with tabs (Submitted / Edited / Downloaded) reads more naturally as a profile.
4. **Authentication: should unauthenticated users see other users' activity?** — Recommendation: yes, submitted and edited are public; downloaded may be private to self + admin.

---

## Implementation Plan

> *To be filled in by `/codebase-draft`.*

---

## Implementation Checklist

- [ ] Backend: query skills by `submitter_id`
- [ ] Backend: query skills where user has an `edit` revision
- [ ] Backend: download/install event tracking (or confirm already tracked)
- [ ] Backend: API route(s) for user activity
- [ ] Frontend: `/users/[user_id]` page with Submitted / Edited / Downloaded tabs
- [ ] Frontend: contributor names in detail header are clickable links
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

- **#007 (`/agent-knowledge-hub` skill):** The skill triggers installs — install tracking here would feed that skill's "recently installed" data.
- **#003 (Label UX):** The contributor name link in the detail header was added alongside label work; this task makes those names interactive.
