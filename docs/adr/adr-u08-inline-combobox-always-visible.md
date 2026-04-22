# ADR-U08: Inline combobox for label input (always visible when authenticated)

**Status:** Accepted
**Date:** 2026-04-22
**Feature:** #003 Label UX

## Context

Two options for label input placement on the skill detail page:
- (a) Hidden behind a "+ Add label" click — minimal visual weight, requires an extra click
- (b) Always-visible inline combobox at the bottom of the label section

## Decision

Always-visible inline combobox using `cmdk`. Reduces clicks for users who label frequently. The combobox is compact (single input row) to minimise visual impact.

## Consequences

Adds approximately 40–48px height to the detail page for all authenticated users, even those who never add labels. Accepted tradeoff — the labeling workflow is a core community feature and reducing friction encourages adoption.
