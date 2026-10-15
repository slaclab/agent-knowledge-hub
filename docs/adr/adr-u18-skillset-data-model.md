# ADR-U18: Skillset data model — embedded ordered member list

**Status:** Accepted
**Date:** 2026-10-14
**Context:** todo/006-skillsets.md

## Context

A skillset is an ordered list of catalog skills that its curator can add to, remove from, and reorder. Each skill must also report which skillsets hold it, and deleting a skill must remove it from every skillset. None of these writes may need a multi-document transaction, because the test database (`mongomock`) cannot run one.

## Decision

Each `Skillset` document stores its members as an ordered list of `SkillsetMember` subdocuments (`skill_id`, `added_by`, `added_at`) plus a `version` counter. There is no separate member collection. The list order is the display order and the install order.

Every membership change is one single-document update on `Skillset`, written in `app/services/skillset.py`:

| Change | Filter | Update | No match means |
|---|---|---|---|
| Add | `_id`, `members.skill_id` not equal to the skill | `$push` the member, `$inc` `version` | Already a member (409), or the skillset is gone (404) |
| Remove | `_id`, `members.skill_id` equal to the skill | `$pull` the member, `$inc` `version` | Not a member (404), or the skillset is gone (404) |
| Reorder | `_id`, `version` equal to the request's `version` | `$set` the reordered list, `$inc` `version` | Another write landed after the read (409) |
| Edit name or description | `_id` | `$set` only the requested fields and `updated_at` | — |
| Skill deleted | `members.skill_id` equal to the skill (`update_many`) | `$pull` the member, `$inc` `version` | — |

A reorder compares the request's `version` with the stored one before it checks the member list, so a page made stale by a concurrent add gets 409 rather than 422. The reordered list is built from the stored subdocuments, so `added_by` and `added_at` survive.

No `Skillset` write uses Beanie `save()` or `replace()`. `save()` writes back every field of the copy it holds, so an edit that read the document before a concurrent add would drop that member and roll `version` back.

A multikey index on `members.skill_id` answers "which skillsets hold these skills" for a page of skills in one query.

A member whose skill document no longer exists is an orphan. The detail response leaves orphans out, and the next reorder drops them. The list response counts members with `len(members)` and so still counts an orphan until then.

## Alternatives rejected

| Alternative | Fact that rules it out |
|---|---|
| Separate member collection, one document per membership | Order needs a position on every member document, so a reorder writes many documents, which is atomic only inside a transaction. |
| Integer `position` on member documents | Renumbering in one pass violates a unique `(skillset_id, position)` index, and two concurrent adds read the same maximum position. |
| Float `position` on member documents | Repeated moves into one slot exhaust float precision after about 50 moves, so a renumber job is needed. |
| Ordered id list on `Skillset` plus member documents | Membership is stored twice; a crash between the two writes of an add leaves a member missing from the order. |

## Consequences

- The member count is derived when a response is built, so no stored count can drift.
- `app/services/skillset.py` queries `app.models.skill.Skill` directly and never imports `app.services.skill`, which imports it for the delete cascade.
- The cascade's `update_many` is atomic for each skillset it changes, not across them.
- A pending-request feature cannot store requests as a status on `SkillsetMember`, because every reader treats `members` as the member set.
- The 16 MB document limit is far above any expected skillset, so there is no member cap.
