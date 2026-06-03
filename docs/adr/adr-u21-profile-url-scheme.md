# ADR-U21: Profile URL scheme — `/users/<user_id>` dedicated page

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/011-user-activity-profile.md

## Context

Two approaches to viewing a user's submitted skills: a filter param on the existing skills list
(`/skills?submitted_by=alice`) or a dedicated profile page (`/users/alice`).

## Decision

**Dedicated `/users/[user_id]` page.** The multi-tab requirement (Submitted / Edited / Installed)
makes a filter param insufficient — the list page has no tab mechanism. The dedicated route also
gives a stable, shareable profile URL.

## Consequences

- New Next.js route: `frontend/app/users/[user_id]/page.tsx`
- `/users/me` redirects server-side to `/users/{authenticated_user_id}`; unauthenticated → `/skills`
- New backend endpoints: `/api/users/{user_id}`, `/api/users/{user_id}/skills`, `/api/users/{user_id}/edits`
- `GET /api/skills?submitted_by=` filter still added for programmatic use; frontend uses dedicated endpoints
- Unknown users return 200 with zero counts (prevents enumeration — preferred over 404)
