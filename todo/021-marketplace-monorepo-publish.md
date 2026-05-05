# TODO #021 — Marketplace Monorepo Publish: `/agent-knowledge-hub create` → PR to slac-agent-plugin-marketplace

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** —
> **Depends on:** #020 (richer scaffold — directory structure, plugin.json format)

---

## Problem Statement

Today `/agent-knowledge-hub create` scaffolds a SKILL.md + plugin.json locally and tells the user "push to your own GitHub repo, then submit the URL." This works for authors who have a suitable public repo, but creates friction for:

1. **Authors without a public repo** — they have to create one, configure it, push, then submit.
2. **Discoverability of SLAC-internal skills** — skills scattered across many individual repos are harder to audit, maintain, and discover than skills in a single well-known location.
3. **No curated community home** — there is no canonical place where SLAC-authored skills live and can be found together.

`slac-agent-plugin-marketplace` (`github.com/slaclab/slac-agent-plugin-marketplace`) is already set up as a monorepo with a `plugins/` directory and an established layout. If it's opened for write to all `slaclab` org members, it can serve as the community publishing target.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Author creates a skill and has no public repo | Must create + configure a GitHub repo manually | `/agent-knowledge-hub create` offers to open a PR to the marketplace monorepo |
| SLAC skill catalogue: where do contributed skills live? | Scattered across individual repos | All contributed SLAC skills under `plugins/` in one auditable repo |
| Author wants to iterate on a skill | Pushes to their own repo, re-submits URL | Pushes a new commit / updates PR in the marketplace repo |

---

## Goals

1. Extend `/agent-knowledge-hub create` with a **publish step** that opens a PR against `slac-agent-plugin-marketplace` for the newly scaffolded plugin
2. Keep the existing flow intact — "I have my own repo" remains a valid choice; the monorepo path is opt-in
3. After a successful PR merge, the skill can be submitted to the AKH catalog using the monorepo URL + `plugins/<slug>` as `skill_path`

## Non-Goals

- Automatic catalog registration on PR merge (webhook/CI integration) — manual submit after merge is fine for now
- Hosting skills in the AKH backend itself (supply chain risk — install always goes to GitHub)
- Editing or deleting skills in the monorepo via the AKH CLI
- Supporting non-GitHub monorepos

---

## Design

### Publish flow

After `/agent-knowledge-hub create` scaffolds files locally, add a final prompt:

```
Scaffold created at ./my-skill/.

Where would you like to publish this skill?
  [1] I'll push to my own GitHub repo (existing behaviour)
  [2] Open a PR to slac-agent-plugin-marketplace (SLAC community repo)
```

If the user chooses option 2:

1. **Auth check** — read `~/.s3df-access-token`. If absent or expired, prompt: "Run `s3df login` first, then re-run `/agent-knowledge-hub create`." (The token is a SLAC SSO JWT, not a GitHub PAT — see step 2.)

2. **GitHub auth check** — the PR requires a GitHub PAT or `gh` CLI auth. Check whether `gh auth status` succeeds. If not, prompt the user to run `gh auth login` with a PAT authorized for `slaclab` SSO (link to the guides page).

3. **Clone/fork check** — use the `gh` CLI to check if the user already has a fork of `slac-agent-plugin-marketplace`. If not, fork it:
   ```
   gh repo fork slaclab/slac-agent-plugin-marketplace --clone=false
   ```

4. **Create branch** — derive a branch name: `add-<slug>-skill`

5. **Copy scaffold** — copy the locally generated files into `plugins/<slug>/` within a temporary worktree of the fork.

6. **Commit + push** — commit with message `feat(plugins): add <slug> skill` and push the branch to the user's fork.

7. **Open PR** — use `gh pr create` against `slaclab/slac-agent-plugin-marketplace`:
   ```
   gh pr create \
     --repo slaclab/slac-agent-plugin-marketplace \
     --title "Add <slug> skill" \
     --body "..."
   ```

8. **Print PR URL** and remind the user:
   ```
   PR opened: https://github.com/slaclab/slac-agent-plugin-marketplace/pull/NNN

   Once merged, submit to the AKH catalog with:
     /agent-knowledge-hub submit
   → URL: https://github.com/slaclab/slac-agent-plugin-marketplace
   → skill_path: plugins/<slug>
   ```

### `submit` — pre-fill from monorepo

When the user runs `/agent-knowledge-hub submit` after a monorepo PR, offer to pre-fill the URL:
```
Detected recent monorepo publish for <slug>.
Submit https://github.com/slaclab/slac-agent-plugin-marketplace at plugins/<slug>? (y/n)
```

### Monorepo URL constant

```
MARKETPLACE_REPO = "https://github.com/slaclab/slac-agent-plugin-marketplace"
MARKETPLACE_PLUGINS_PATH = "plugins"
```

Hardcoded in SKILL.md — this is a well-known SLAC constant, not user-configurable.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `skill/SKILL.md` — create command | Modify | Add publish step: prompt, auth check, fork, branch, copy, commit, PR |
| `skill/SKILL.md` — submit command | Modify | Pre-fill monorepo URL + skill_path when recent monorepo publish detected |
| `skill/SKILL.md` — error handling | Modify | GitHub auth errors, fork failures, PR creation failures |

---

## ADRs

### ADR-001: Use `gh` CLI for all GitHub operations in the publish flow

**Status:** Accepted

**Context:** The installer skill already uses `gh` for MCP server registration. GitHub API calls via `curl` require token management. `gh` handles auth, fork, branch, PR creation cleanly.

**Decision:** All Git/GitHub operations in the publish flow use `gh` CLI commands. Prerequisite: `gh auth status` must succeed (user must have run `gh auth login`).

**Consequences:** Requires `gh` CLI installed (already assumed by the existing MCP install flow). SAML SSO must be authorized on the user's PAT for the `slaclab` org — same requirement as installing internal skills.

---

### ADR-002: Fork-based PR, not direct push

**Status:** Accepted

**Context:** Even if `slac-agent-plugin-marketplace` is opened for write to all `slaclab` members, PRs from forks are better practice — they allow maintainer review before merge, keep `main` clean, and provide a review record.

**Decision:** Always create a fork + branch + PR, never push directly to `slaclab/slac-agent-plugin-marketplace/main`.

**Consequences:** Users need a GitHub account with `slaclab` org membership. The fork step is a one-time cost; subsequent PRs reuse the existing fork.

---

### ADR-003: Manual catalog submit after PR merge, not auto-registration

**Status:** Accepted

**Context:** Auto-registration on merge would require a webhook or GitHub Actions workflow on the marketplace repo talking back to the AKH API. That's additional infra and a more complex trust model.

**Decision:** After PR merge, user manually submits via `/agent-knowledge-hub submit` (or the web UI). The `submit` command pre-fills the URL to reduce friction.

**Consequences:** Two-step process: PR merge + catalog submit. Acceptable for now. Auto-registration can be added later via a GitHub Actions workflow on the marketplace repo.

---

## Trade-offs

```
Choice: Fork-based PR vs direct branch push (assuming write access)
  + Fork: clean history, review gate, aligns with open-source norms
  - Fork: one extra step (fork creation); slightly more complex gh commands
  Decision: Fork. Write access doesn't mean "commit directly to main without review."

Choice: gh CLI vs direct GitHub API calls
  + gh CLI: handles auth, SSO, token refresh; much less code in SKILL.md
  - gh CLI: must be installed; another tool dependency
  Decision: gh CLI. Already required for MCP install. Installing gh is documented in the guides.

Choice: Hardcode marketplace repo URL vs make it configurable
  + Hardcode: simpler UX; "the SLAC community repo" is a known constant
  - Hardcode: won't work for future non-SLAC deployments of AKH
  Decision: Hardcode for now. If AKH is deployed elsewhere, this can be made configurable via a catalog API endpoint that returns the community repo URL.
```

---

## Delivery Slices

**Slice 1 — Publish flow (core)**
- Auth check (`gh auth status`, SLAC token)
- Fork + branch + copy scaffold + commit + push + PR
- Print PR URL + submit reminder

**Slice 2 — `submit` pre-fill**
- Detect recent monorepo publish from local state
- Pre-fill URL + skill_path in submit prompt

**Slice 3 — Update existing monorepo skill**
- `/agent-knowledge-hub update-pr <slug>` — open a new PR to the monorepo to update an existing plugin
- Out of scope for initial delivery; note as future work

---

## Prerequisites (operational, not code)

- `slac-agent-plugin-marketplace` opened for write (fork + PR) to all `slaclab` org members by the repo owner
- `gh` CLI available on S3DF compute nodes (or documented install path)
- Users have completed `gh auth login` with a `slaclab`-SSO-authorized PAT (same requirement as installing internal skills — covered by the guides page)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `gh` CLI not installed on S3DF nodes | Medium | Medium | Check and print install instructions; guide page link |
| User's PAT not SSO-authorized for slaclab | Medium | Medium | Detect `gh` auth error; link to guides/slac-github-access |
| Slug already exists in `plugins/` dir of monorepo | Low | Low | Check before creating PR; prompt user to choose a different name |
| Monorepo maintainer doesn't merge PR promptly | Medium | Low | User can still submit manually to AKH using any other repo; monorepo PR is optional |
| fork creation fails (user already has a fork with conflicts) | Low | Low | Detect and prompt user to resolve manually; print fork URL |

---

## Implementation Checklist

- [ ] `create` command: add publish prompt after scaffold generation
- [ ] `create` publish flow: `gh auth status` check with actionable error
- [ ] `create` publish flow: fork `slaclab/slac-agent-plugin-marketplace` if not already forked
- [ ] `create` publish flow: create branch `add-<slug>-skill`
- [ ] `create` publish flow: copy scaffold to `plugins/<slug>/` in a local clone of the fork
- [ ] `create` publish flow: commit + push branch
- [ ] `create` publish flow: open PR via `gh pr create`; print PR URL
- [ ] `create` publish flow: print submit reminder with pre-filled URL + skill_path
- [ ] `create` publish flow: check `plugins/<slug>` doesn't already exist in monorepo
- [ ] `submit` command: detect + pre-fill monorepo URL when recent publish detected
- [ ] Error handling: gh not installed, auth failure, fork conflict, slug collision
- [ ] Tests / manual verification: end-to-end publish flow on test fork

---

## Definition of Done

- [ ] Running `/agent-knowledge-hub create` offers monorepo publish as an option
- [ ] Choosing publish opens a PR to `slaclab/slac-agent-plugin-marketplace` with the scaffolded plugin under `plugins/<slug>/`
- [ ] PR URL printed; submit reminder pre-fills the correct monorepo URL + skill_path
- [ ] Flow fails gracefully with actionable messages when `gh` not configured or auth missing
- [ ] Existing "push to your own repo" path unchanged
- [ ] All checklist items complete

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

> *Populated by `/codebase-board-review` after the board completes. Do not fill manually.*

**Verdict:** —
**Date:** —
**Rounds:** —

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — | — | — |
| codebase-arch-review | — | — | — |
| codebase-eng-review | — | — | — |
| codebase-doc-review | — | — | — |
| security-review | — | — | — |

---

## Relationship to Other Tasks

- **#020 (Installer skill extension):** #021 builds on the richer scaffold from #020 — the PR to the monorepo submits a directory-structured plugin, not just a bare SKILL.md.
- **#019 (plugin.json scan pipeline):** Skills published to the monorepo will be scanned using the pipeline from #019 when submitted to the catalog.
- **#007 (AKH skill):** This todo extends the skill first created in #007.
