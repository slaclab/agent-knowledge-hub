# ADR-U10: All label UX slices ship in one PR

**Status:** Accepted
**Date:** 2026-04-22
**Feature:** #003 Label UX

## Context

The label feature was planned in three delivery slices (backend, frontend read path, frontend write path + admin). Options:
- (a) Ship each slice as a separate PR
- (b) Ship all slices in one branch/PR

## Decision

One branch (`feat/label-ux`), one PR. Backend-only or frontend-only slices are non-functional in staging; reviewers cannot verify the feature end-to-end without both.

## Consequences

Larger PR (~3000 lines). Acceptable — the feature is cohesive, the slices are clearly separable in commit history, and end-to-end staging verification is more valuable than incremental merges of non-functional partial work.
