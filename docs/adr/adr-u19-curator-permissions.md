# ADR-U19: Skillset permissions — any signed-in curator, plus author removal

**Status:** Accepted
**Date:** 2026-10-14
**Context:** todo/006-skillsets.md

## Context

Facility leads need to build and maintain skillsets without waiting for an admin. Skill authors need a way to take their skill out of a skillset they object to, without a moderation queue.

## Decision

Any signed-in user can create a skillset and manages the skillsets they created. Admins can edit and delete any skillset. A skill's submitter can remove that skill from any skillset.

| Action | Allowed for |
|---|---|
| Create a skillset | Any signed-in user |
| Edit name or description, delete a skillset | Skillset owner, admin |
| Add a member, reorder members | Skillset owner, admin |
| Remove a member | Skillset owner, admin, or the member skill's submitter |
| Add a new skill on submit (`skillset_slug`) | Skillset owner only |

"Skillset owner" means `Skillset.created_by == User.user_id`. "The member skill's submitter" means `Skill.submitter_id == User.user_id`. Both fields hold `User.user_id` from `app/auth.py`. "Admin" means `User.is_admin`.

The checks live in `app/services/skillset.py`, which raises `PermissionDeniedError` (403) before any write. The add-on-submit check lives in `create_skill` in `app/routers/skills.py`, because the service's add also admits admins. A refused add-on-submit is logged and ignored, and the skill is still created.

A skillset's slug cannot change after creation; `SkillsetUpdate` has no slug field.

## Alternatives rejected

| Alternative | Fact that rules it out |
|---|---|
| Admin-only skillset creation | Every facility lead would wait on an admin for each change. |
| Per-skill "allow inclusion" flag | It does nothing about a membership the author objects to after it exists. |
| Author approval for every add | Membership could not ship until a request queue exists. |

## Consequences

- A submitter's removal is not recorded on the skillset, so the owner or an admin can add the skill again.
- The only record of who removed a member is the `[SKILLSET] action=remove` log line, because `$pull` removes the member's `added_by` with it.
- The add endpoint is rate-limited to 50 per user per hour and creation to 20, both counted per user across every path (`key_style="endpoint"`).
