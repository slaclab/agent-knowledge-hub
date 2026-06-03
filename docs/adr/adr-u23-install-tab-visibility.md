# ADR-U23: Installed tab visibility — private to self + admin

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/011-user-activity-profile.md

## Context

Should a user's install history be public (visible to anyone) or private (visible to self and
admins only)?

## Decision

**Private to self + admin.** Submitted and edited activity is public (already visible via skill
metadata). Install history reveals tooling choices which a user may not want to broadcast. The
check is simple: `viewer == profile_user or viewer.is_admin`.

## Consequences

- `GET /api/users/{user_id}` omits `install_count` for non-self, non-admin viewers
- `GET /api/users/{user_id}/installs` returns 403 for non-self, non-admin
- Frontend Installed tab: always visible in the tab bar (consistent UI structure); content gated:
  - Self or admin: full install list
  - Unauthenticated: "Sign in to view your install history"
  - Authenticated third-party: "Install history is private to {user_id}"
- `GET /api/me/installs` is the canonical self-view endpoint (always returns own data)
