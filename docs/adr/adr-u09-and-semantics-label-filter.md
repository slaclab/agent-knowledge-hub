# ADR-U09: AND semantics for multi-label filter

**Status:** Accepted
**Date:** 2026-04-22
**Feature:** #003 Label UX

## Context

Two options for multi-label filter semantics:
- **OR** — return skills that carry any of the selected labels (widens results)
- **AND** — return skills that carry all selected labels (narrows results)

## Decision

AND semantics. More useful for discovery: "show me skills tagged both `python` AND `data-viz`" is a more precise and actionable query than "show me anything tagged either one."

## Consequences

With many labels selected, the result set may become empty. Mitigated by showing a label-specific empty state: "No skills match all selected labels. Try removing some to widen your search." The URL reflects selected labels so filtered views remain shareable.
