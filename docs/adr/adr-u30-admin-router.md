# ADR-U30: Admin router location — new `routers/admin.py`

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/012-moderation-flags-and-admin-deactivation.md

## Context

Admin routes could go in existing `routers/skills.py` (adds noise, `require_admin` must be repeated per endpoint) or a new `routers/admin.py` with `require_admin` applied at the router level.

## Decision

**New `routers/admin.py`** with prefix `/api/admin`. `require_admin` applied via `dependencies=[Depends(require_admin)]` on the `APIRouter` constructor — no per-endpoint repetition.

**Implementation constraint:** The original `require_admin` signature was `def require_admin(user: User) -> User:` with no embedded `Depends()`. FastAPI does NOT inject `get_current_user` into a plain `User` parameter at router level. Fixed by embedding it:

```python
def require_admin(user: User = Depends(get_current_user)) -> User:
```

This is backward-compatible with existing per-endpoint usage in `labels.py` (FastAPI deduplicates the dependency).

## Consequences

- Clear auth boundary — all admin routes in one auditable file
- Matches the existing frontend `/admin/*` route convention
- `app/auth.py` has a one-line signature change; `main.py` gains one `include_router` call
