# TODO #022 — Installer: Switch to Git Clone for Plugin Installation

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-05-28
> **Shipped:** —
> **Depends on:** #020 (installer skill extension)

---

## Problem Statement

The AKH installer skill (`skill/SKILL.md`) uses the GitHub Contents API to download plugin files. This creates two limitations:

1. **No native recursion** — the Contents API returns only direct children of a directory. Traversing nested structures (e.g. `skills/myplugin/scripts/helpers/`) requires O(depth × breadth) round trips, bounded by GitHub's 5,000 req/hr rate limit with a token (60 req/hr unauthenticated).

2. **Inconsistency with Claude Code native** — Claude Code's built-in `/plugin install` system uses **git clone / sparse clone** at a pinned ref+sha. AKH's Contents API approach diverges from the platform's own mechanism, meaning plugin authors face different constraints when targeting AKH vs native Claude Code.

Researched and documented in: [`docs/github-api-plugin-installation.md`](../docs/github-api-plugin-installation.md)

---

## Goals

1. Replace the GitHub Contents API file enumeration + download loop with `git clone` (or sparse clone for `skill_path` subdirectories)
2. Preserve SHA-pinning for reproducible installs (aligns with [#017 commit pinning](017-skill-version-pinning.md))
3. Eliminate the 200-file cap and multi-round-trip enumeration from the install flow
4. Keep auth working for private repos (use existing `gh` credential helpers or `GITHUB_TOKEN`)
5. Maintain backwards compatibility — the install interface and output are unchanged for users

## Non-Goals

- Adopting the full Claude Code native `.claude-plugin/marketplace.json` marketplace format
- Implementing sparse clone (full clone is acceptable; repos are small)
- Supporting non-GitHub sources (GitLab, Bitbucket) — out of scope

---

## Design

### Mechanism

Replace the per-file GitHub Contents API calls with a single `git clone`:

```
git clone --depth 1 [--branch <ref>] <repo_url> <tmp_dir>
```

Then copy the relevant files from `<tmp_dir>/<skill_path>/` to `~/.claude/skills/<slug>/` (and commands/agents as declared in plugin.json).

For SHA-pinned installs (when #017 lands):
```
git clone <repo_url> <tmp_dir>
git -C <tmp_dir> checkout <pinned_sha>
```
(shallow clone can't checkout arbitrary SHAs; full clone required for pinning)

### Auth

- Public repos: no credentials needed
- Private repos: git uses the user's existing credential helpers (e.g. `gh auth login` configures git credentials automatically; SSH keys work too)
- Fallback: if clone fails with auth error, show message: `"Clone failed. For private repos, run 'gh auth login' or set GITHUB_TOKEN."`

### Dependency

Requires `git` on the user's PATH. This is a safe assumption for Claude Code users — `git` is a prerequisite for Claude Code itself (the CLI uses it for context). Add a preflight check: if `git` not found, fall back to Contents API with a warning.

### Cleanup

Delete the temp clone directory after all files are copied. Use a predictable path: `/tmp/akh-install-<slug>-<timestamp>/` so it's identifiable and safe to clean up.

### Security

The existing path traversal security check applies unchanged — every target path must resolve within `~/.claude/`. The check runs at copy time (after clone), not at enumeration time.

### Integration with #020

The #020 installer (when complete) implements recursive Contents API fetching for directory-form plugins. This TODO (#022) would replace that recursion with git clone — so #022 depends on #020 being done first (to establish the correct install shape), then replaces the internals.

Alternatively, #022 could be implemented in parallel as a cleaner rewrite of the install mechanism, with #020's directory-form support built on top of clone from the start. The decision should be made when #020 scope is confirmed.

---

## ADRs

### ADR-001: Git clone vs Trees API vs Contents API

**Status:** Proposed

**Context:** Three options for fetching plugin files (see [`docs/github-api-plugin-installation.md`](../docs/github-api-plugin-installation.md)):
- Contents API: current approach; flat, rate-limited, O(n) calls for directory trees
- Trees API: single call to enumerate paths; still needs per-file downloads; better than Contents API for enumeration
- Git clone: single operation; no API rate limits; native recursive; matches Claude Code's own approach

**Decision:** Git clone is the right long-term approach. Trees API is an interim improvement if git is unavailable.

**Consequences:**
- Requires `git` on PATH (safe assumption for Claude Code users; add preflight check)
- Temp directory needed for clone; must clean up on success and failure
- Slightly more complex error handling (network, auth, disk space) than HTTP calls

---

## Trade-offs

```
Choice: Full clone vs sparse clone
  + Full clone: simpler; works with SHA pinning
  - Full clone: downloads entire repo history (mitigated by --depth 1 for non-pinned)
  Decision: --depth 1 for branch installs; full clone only when SHA pinning required.

Choice: Clone to /tmp vs ~/.claude/skills/<slug>-tmp
  + /tmp: standard; clearly temporary
  + ~/.claude/: avoids /tmp cleanup issues on some systems
  Decision: /tmp — conventional, avoids polluting ~/.claude/ with partial installs.

Choice: Fallback to Contents API if git unavailable vs hard fail
  + Fallback: graceful degradation
  - Fallback: two code paths to maintain
  Decision: Fallback with warning. Contents API path already exists; no extra maintenance cost.
```

---

## Delivery Slices

**Slice 1 — Clone-based install**
- Preflight: check `git` available; warn + fall back if not
- `git clone --depth 1 <repo_url> /tmp/akh-install-<slug>/`
- Copy files from `skill_path` to `~/.claude/skills/<slug>/` (respecting security check)
- Delete temp dir on success and failure (trap)
- Update manifest write to reflect cloned files

**Slice 2 — Auth handling**
- Detect clone auth failure; print actionable error message
- Document `GITHUB_TOKEN` and `gh auth login` as the two supported auth paths

**Slice 3 — SHA pinning integration (when #017 ships)**
- Accept pinned SHA from catalog API response
- Use full clone + `git checkout <sha>` instead of `--depth 1`

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `git` not on PATH | Low | Medium | Preflight check; fall back to Contents API with warning |
| Clone of large repo is slow | Low | Low | `--depth 1` limits history; most skill repos are small |
| Temp dir not cleaned up on error | Low | Low | Use shell trap to delete `/tmp/akh-install-*/` on exit |
| Private repo auth fails | Medium | Medium | Clear error message pointing to `gh auth login` |
| SHA pinning requires full clone (slow for big repos) | Low | Low | Only triggered when #017 ships; revisit then |

---

## Definition of Done

- [ ] `git` preflight check with graceful Contents API fallback
- [ ] `git clone --depth 1` replaces Contents API enumeration + download loop
- [ ] Temp directory cleaned up on success and failure
- [ ] Auth failure produces actionable error message
- [ ] No regression in install output or manifest writing
- [ ] Smoke test: install a skill with nested subdirectories (verify all files present)
- [ ] Smoke test: install from a private repo via `gh auth login`

---

## Relationship to Other Tasks

- **#020 (Installer skill extension):** #020 adds directory-form support via recursive Contents API. #022 replaces that with git clone. Coordinate sequencing.
- **#017 (Commit pinning):** SHA pinning requires full clone (not shallow). #022 should leave a hook for this.
- **[docs/github-api-plugin-installation.md](../docs/github-api-plugin-installation.md):** Research background and comparison table for this decision.
