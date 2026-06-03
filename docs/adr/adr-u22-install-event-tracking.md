# ADR-U22: Install event tracking — client-side POST, not server-side intercept

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/011-user-activity-profile.md

## Context

Install happens agent-side (AKH skill clones from GitHub locally). The backend has no hook into the
install process. Two approaches: add a server-side download counter on `GET /api/skills/{slug}`
views, or have the AKH skill explicitly POST an install event after a successful install.

## Decision

**AKH skill POSTs `POST /api/me/installs/{slug}` after successful install.** The AKH skill already
handles Bearer JWT auth (`~/.s3df-access-token`) and makes API calls. A fire-and-forget POST is a
natural extension. Old AKH skill versions simply never post — the installed tab starts empty for
legacy installs, which is acceptable.

## Consequences

- New `SkillInstallEvent` MongoDB collection with `(user_id, skill_slug)` unique index
- New endpoints: `POST /api/me/installs/{slug}` (rate-limited 60/hour per user), `GET /api/me/installs`
- AKH `skill/SKILL.md` step 13: fire-and-forget POST after install success; failure logs warning only
- Upsert semantics: re-installing updates `installed_at`, not a second row
- `skill_repository.delete()` nulls out `skill_id` in install events when a skill is removed
- Rate limit keyed on `user_id` (not IP): `request.state.user = user` set in `get_current_user` so slowapi `key_func` can read it
