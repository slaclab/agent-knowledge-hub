# ADR-P01: GitHub App over per-user OAuth

**Status:** Accepted
**Date:** 2026-04-21
**Feature:** #001 — Private/Internal GitHub Repos

## Context

The catalog needs to fetch metadata for private repos in the slaclab GitHub Enterprise organization.
Three approaches were considered for authentication.

## Decision

Use a GitHub App with org-level installation (read-only `Contents` + `Metadata` permissions).

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| **GitHub App (org-level)** ✓ | One setup, works for all slaclab repos, no per-user friction | Requires org admin, all-or-nothing access |
| Per-user OAuth token | Granular, user controls access | Complex UX, token storage, refresh flow |
| Shared PAT | Simple | Tied to one person's account, rotation risk |

## Consequences

- Org admin must create the App once and install it on the slaclab org
- Private key stored in vault; injected as env var in backend
- No per-user overhead; submitters don't need to authenticate to GitHub
- Scope is read-only; the App cannot modify repos
