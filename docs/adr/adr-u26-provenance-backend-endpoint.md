# ADR-U26: Provenance as backend endpoint, not client-side assembly

**Status:** Accepted
**Date:** 2026-06-03
**Task:** #014 Skill Provenance Tree

## Context

The provenance tree requires multi-hop resolution: follow `forked_from_url` → match `repo_url` in catalog → repeat. This can be done client-side (multiple sequential API calls) or via a single backend endpoint.

## Options

| Option | Pros | Cons |
|---|---|---|
| Client-side sequential fetches | No new endpoint | N round trips from browser; hard to cap depth; complex error handling; can't batch |
| Backend `GET /skills/{slug}/provenance` | Single round trip; depth-capped server-side; batchable queries; cacheable | New endpoint to build |

## Decision

**Backend endpoint.** The multi-hop resolution is fundamentally a graph traversal that must be depth-capped and cycle-detected server-side. Client-side assembly would result in N sequential API calls (one per hop) and can't efficiently batch-resolve downstream forks. A single endpoint returning the full tree is cleaner and cacheable.

## Consequences

- New `GET /api/skills/{slug}/provenance` in `routers/skills.py`
- New `services/provenance.py` for graph traversal logic
- 5-minute TTL cache (provenance trees change rarely)
- External GitHub node metadata fetched best-effort (failure → null fields)
