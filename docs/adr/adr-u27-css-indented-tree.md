# ADR-U27: Indented tree UI (not a graph library)

**Status:** Accepted
**Date:** 2026-06-03
**Task:** #014 Skill Provenance Tree

## Context

The provenance data is a shallow tree (max 3 + 2 levels). Visualisation options: a full graph library (react-flow, d3-hierarchy) or a simple CSS-based indented tree.

## Options

| Option | Pros | Cons |
|---|---|---|
| react-flow / d3-hierarchy | Handles complex DAGs; draggable/zoomable | Heavy dependency; overkill for 3-level trees; layout complexity |
| CSS indented tree (native) | Zero new dependencies; fast to build; fits sidebar well | Can't render true DAGs (node appearing in multiple places) |

## Decision

**CSS indented tree, no new library dependency.** The provenance tree is depth-capped at 3+2 levels — a graph library is overkill. If a node appears in both upstream and forks (true DAG), it's rendered twice.

## Consequences

- `ProvenanceTree` component uses `border-left` + `padding-left` CSS for indentation — no ASCII tree characters (`├`, `└`). This ensures mobile resilience when text wraps.
- No new npm dependencies
- DAG dedup (same node appearing multiple times) accepted for v1
