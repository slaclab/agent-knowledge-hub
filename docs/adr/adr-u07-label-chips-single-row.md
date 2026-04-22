# ADR-U07: Label chips — single row, no wrap

**Status:** Accepted
**Date:** 2026-04-22
**Feature:** #003 Label UX

## Context

Cards have limited vertical space. Unlimited tag wrapping makes the list page visually inconsistent — cards with many labels push content down and break the grid rhythm.

## Decision

Render up to 5 label chips in a single row on skill cards. Show a non-interactive "+N more" badge for overflow. The detail page shows all chips with no cap.

## Consequences

Users won't see all labels at a glance on cards. Acceptable — the detail page is one click away and shows the full set.
