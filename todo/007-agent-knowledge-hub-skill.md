# 007 — `/agent-knowledge-hub` Agent-Native Discovery & Install Skill

**Status:** ⬜ Open
**Branch:** —
**PR:** —

---

## Problem & Goal

**Problem:** Users must leave their agent session and open a browser to discover, evaluate, and install skills from the catalog. There is no way to search the catalog, install a skill, or submit a new one without context-switching to a web UI.

**Goal:** Ship a Claude Code skill (`/agent-knowledge-hub`) that lets users discover, install, update, remove, and rate catalog skills — and submit new ones — entirely from within their agent session. The skill uses the catalog API for data and Claude as the semantic matching layer (no separate vector index needed).

**Success metrics:**
- `SLAC S3DF` marketplace registered once; `/plugin install agent-knowledge-hub` works
- Natural-language queries (e.g. `/agent-knowledge-hub I need something to query EPICS`) return ranked, explained matches
- `install`, `list`, `update`, `remove`, `rate`, and `submit` sub-commands all function end-to-end
- The skill is installable by any S3DF user without manual git operations

**Out of scope (v1):**
- OpenCode custom agent install (`~/.config/opencode/agents/`) — v2
- OOD pre-seeding (auto-registering the marketplace for all S3DF users) — follow-on
- Automated skill testing or CI on install
- Backend Bearer JWT validation — tracked in **[#016](016-bearer-jwt-auth.md)** (dependency)

**Dependencies:**
- **[#016](016-bearer-jwt-auth.md)** — Bearer JWT auth must land before `rate` can authenticate

---

## Design

### Invocation examples (from PRD §15)

```
/agent-knowledge-hub install something that allows me to query EPICS
/agent-knowledge-hub I have a problem trying to work out what's wrong with my Kubernetes deployment
/agent-knowledge-hub find me a skill for analysing NeXus files
/agent-knowledge-hub search --label hdf5
/agent-knowledge-hub list
/agent-knowledge-hub update k8s-troubleshooting
/agent-knowledge-hub remove k8s-troubleshooting
/agent-knowledge-hub rate k8s-troubleshooting 5
/agent-knowledge-hub submit
```

### How it works (from PRD §15)

```
User: /agent-knowledge-hub <natural language query>
  → Skill fetches GET /api/skills/summary (slug, name, description, labels, avg_rating)
  → Passes catalog + user query to Claude
  → Claude returns ranked matches with explanations
  → User picks one → skill clones repo to ~/.claude/skills/<slug>/
```

Search is intentionally LLM-powered (Claude as semantic layer), avoiding a vector index for v1.

### Sub-command table

| Command | Behaviour |
|---|---|
| `/agent-knowledge-hub <query>` | Natural-language search + optional install |
| `/agent-knowledge-hub search <query>` | Search without installing |
| `/agent-knowledge-hub install <slug>` | Direct install by slug (no LLM step) |
| `/agent-knowledge-hub list` | Show installed skills from `~/.claude/skills/` |
| `/agent-knowledge-hub update <slug>` | Re-pull latest from skill's repo |
| `/agent-knowledge-hub remove <slug>` | Delete from skills directory |
| `/agent-knowledge-hub rate <slug> <1-5>` | Submit rating via API |
| `/agent-knowledge-hub submit` | Guided publish flow (repo → scaffold → catalog POST) |

### Install target (v1)

Claude Code: clone `<repo_url>` into `~/.claude/skills/<slug>/`. The skill validates that the repo contains a recognisable plugin structure before installing.

### Guided submit flow (`/agent-knowledge-hub submit`)

```
Step 1 — Existing repo? [yes → enter URL → skip to 4] [no → Step 2]
Step 2 — Create GitHub repo (suggest name, create via API, clone)
Step 3 — Scaffold skill.md from template (SiteSettings.skill_template_repo_url)
Step 4 — POST /api/skills with SLAC identity → confirm live URL
         → optionally add labels
```

### Required API additions

```
GET /api/skills/summary      # slug, name, description, labels, avg_rating only (no README HTML)
GET /api/marketplace.json    # dynamic Claude Code marketplace manifest; cached 5 min, ETag
```

`marketplace.json` shape (from PRD §15):

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "agent-knowledge-hub",
  "description": "SLAC S3DF agent skills catalog",
  "owner": { "name": "SLAC S3DF", "email": "s3df-support@slac.stanford.edu" },
  "metadata": { "version": "1.0.0" },
  "plugins": [
    { "name": "...", "source": { "source": "github", "repo": "slaclab/<slug>" }, ... }
  ]
}
```

Every `entry_type: skill` in the catalog becomes a plugin entry automatically.

### Bootstrap (for users)

```bash
# Register the SLAC marketplace (one-time)
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json

# Install the discovery skill itself
/plugin install agent-knowledge-hub
```

### Skill vs plugin terminology

- **Skill**: a single `SKILL.md` with YAML frontmatter defining a slash command.
- **Plugin**: a directory with `plugin.json` + one or more `SKILL.md` files. Installed via `/plugin install`; skills namespaced as `/plugin-name:skill-name`.

`/agent-knowledge-hub` ships as a **plugin** in a dedicated GitHub repo (`slaclab/agent-knowledge-hub`).

### CLI Authentication (`s3df login`)

**Resolved (OQ-1):** The skill authenticates by reading a token from `~/.s3df-access-token`, populated by the `s3df login` command. The skill reads this file and passes the token as a `Bearer` token in the `Authorization` header on all write requests (`rate`, `submit`, `label`).

**Still to resolve — backend token validation:** The current backend trusts `X-Vouch-*` headers injected by VouchProxy at the ingress layer. A Bearer token arriving directly at the API bypasses VouchProxy entirely. Two options:

| Option | Pros | Cons |
|---|---|---|
| **A — S3DF issues a signed JWT** that the backend validates (shared secret or public key) | Clean; no new infrastructure; VouchProxy already supports JWT issuance | Need to confirm S3DF can issue a compatible JWT; backend adds JWT validation path |
| **B — Lightweight token exchange endpoint** (`POST /api/auth/token-exchange`) where the user presents their `~/.s3df-access-token` and gets back a short-lived session token the backend issues and validates | Self-contained; no VouchProxy dependency for CLI flows | New infrastructure in the backend; token storage/rotation complexity |
| **C — `s3df login` writes a VouchProxy session cookie** that the skill sends as a cookie header | Zero backend changes | Fragile; cookies aren't designed for CLI use; session expiry unpredictable |

**Recommended path:** Option A — confirm with S3DF platform team whether `s3df login` issues a standard SLAC JWT (likely yes). Backend adds a second auth path: if `Authorization: Bearer <token>` present, validate JWT; otherwise fall back to existing `X-Vouch-*` header path.

Read-only endpoints (browse, search) remain unauthenticated and require no token.

### Open Questions

1. **`s3df login` JWT format** _(blocks #016 Slice 2)_: Tracked in `todo/016-bearer-jwt-auth.md`.
2. **`submit` — GitHub repo creation**: Resolved — the skill does **not** create GitHub repos. `create` scaffolds the skill files locally; `submit` redirects to the web form in v1.
3. **Skill repo location**: Resolved — `skill/` subdirectory in this monorepo.

---

## User Stories

1. As an S3DF scientist, I want to search for skills using plain English so that I can find tools without knowing their exact slug.
2. As an S3DF scientist, I want to see a ranked list of matches with explanations so that I can choose the most relevant skill.
3. As an S3DF scientist, I want to install a skill directly from my agent session so that I don't need to open a browser or run git commands.
4. As an S3DF scientist, I want to install a skill by exact slug so that I can quickly get something I already know the name of.
5. As an S3DF scientist, I want to list the skills I have installed locally so that I can see what's available to me.
6. As an S3DF scientist, I want to update an installed skill to the latest version so that I benefit from improvements without manual steps.
7. As an S3DF scientist, I want to remove a skill I no longer need so that my skills directory stays tidy.
8. As an S3DF scientist, I want to rate a skill I've used so that others benefit from my feedback without leaving my agent session.
9. As a skill author, I want to scaffold a new skill from a template so that I can get started without manually copying boilerplate.
10. As a skill author, I want to submit my existing GitHub repo to the catalog so that colleagues can discover and install it.
11. As a skill author, I want the submit flow to walk me through the required fields so that I don't have to read docs first.
12. As a skill author, I want to see the catalog URL for my skill after submitting so that I can share it immediately.
13. As an S3DF scientist, I want a clear error message when a skill's repo is private or removed so that I know what to do next.
14. As an S3DF scientist, I want installation to be safe against malicious skill_path values so that a bad catalog entry can't write files outside my skills directory.
15. As an S3DF scientist, I want to rate a skill using my SLAC identity so that ratings are meaningful and not anonymous.

---

## Requirements

### Functional

- **FR-1**: Natural-language and `search` commands call `GET /api/skills?q=<query>&limit=20`, pass results + query to Claude, and present ranked matches with explanations.
- **FR-2**: `install <slug>` fetches `GET /api/skills/<slug>`, validates `skill_path`, fetches file listing from GitHub Contents API, downloads all files, writes to `~/.claude/skills/<slug>/`.
- **FR-3**: `list` scans `~/.claude/skills/` and prints installed skills (slug + SKILL.md description if present).
- **FR-4**: `update <slug>` deletes `~/.claude/skills/<slug>/` and re-runs install.
- **FR-5**: `remove <slug>` deletes `~/.claude/skills/<slug>/` after user confirmation.
- **FR-6**: `rate <slug> <1–5>` POSTs to `POST /api/skills/<slug>/rate` with a Bearer token from `~/.s3df-access-token`.
- **FR-7**: `create` scaffolds a new `SKILL.md` (and optional `README.md`) from the catalog template (`SiteSettings.skill_template_repo_url`), in a directory the user specifies.
- **FR-8**: `submit` guides the user: enter GitHub URL → redirect to web form (v1); direct API POST in v2 once auth is stable.
- **FR-9**: Path traversal guard: every file write resolves the target path and asserts it stays inside `~/.claude/skills/<slug>/`.
- **FR-10**: If `~/.s3df-access-token` is absent when `rate` is called, the skill explains how to log in via `s3df login`. If #016 is not yet deployed, `rate` warns that server-side auth is not yet active.

### Non-functional

- **NFR-1**: `install` completes in < 10s for a skill with ≤ 20 files on a standard campus connection.
- **NFR-2**: `search` LLM round-trip completes in < 15s.
- **NFR-3**: The skill file (`skill/SKILL.md`) must not exceed 8 KB — keep it within LLM context budget.
- **NFR-4**: No secrets or tokens are logged or echoed; token is read from file, not user input.

### Acceptance Criteria

- **AC-1**: Given `/agent-knowledge-hub I need to debug Kubernetes pods`, Claude returns ≥ 1 ranked result with an explanation.
- **AC-2**: Given `/agent-knowledge-hub install k8s-troubleshooting`, files appear in `~/.claude/skills/k8s-troubleshooting/` and the skill confirms the install path.
- **AC-3**: Given a `skill_path` containing `..`, install aborts with a security warning and writes no files.
- **AC-4**: Given `/agent-knowledge-hub update k8s-troubleshooting`, old files are removed and fresh files are written.
- **AC-5**: Given `/agent-knowledge-hub remove k8s-troubleshooting`, the directory is deleted after confirmation.
- **AC-6**: Given `/agent-knowledge-hub rate k8s-troubleshooting 5` with a valid `~/.s3df-access-token` (and #016 deployed), the API returns 200 and the skill confirms the rating.
- **AC-7**: Given `/agent-knowledge-hub rate k8s-troubleshooting 5` with no token file, the skill explains how to authenticate.
- **AC-8**: Given `/agent-knowledge-hub create`, the skill produces a populated `SKILL.md` in the user's chosen directory.

---

## ADRs

### ADR-007-A: Install method — GitHub Contents API over `git clone`

**Status:** Accepted

| Option | Pros | Cons |
|---|---|---|
| GitHub Contents API | No git required; handles subdirs natively; per-file security checks | Rate-limited (60 req/hr unauth, 5000 auth); extra round-trips for many files |
| `git clone` | Single command; no rate limit | Downloads whole repo; sparse-checkout complexity; git must be available |
| `git sparse-checkout` | Subdir-scoped; no rate limit | Complex; git must be available; harder to do per-file validation |

**Decision:** GitHub Contents API. Skills are small (< 20 files); rate limit is not a concern at this scale. Per-file write validation is essential for the path traversal guard and easier to implement with the API.

---

### ADR-007-B: `submit` scope — web redirect for v1

**Status:** Accepted

Direct `POST /api/skills` from the CLI requires Bearer JWT auth (tracked in #016). Rather than block the skill on auth infra, `submit` redirects to the web form in v1. The `create` sub-command handles the in-agent scaffolding use case.

---

## Module Design

### Skill file — `skill/SKILL.md` (new)
- **Responsibility:** SKILL.md with YAML frontmatter that Claude Code reads as slash-command instructions. Contains all command logic as natural-language instructions to Claude.
- **Interface:** Invoked when user types `/agent-knowledge-hub <args>`
- **Status:** New (monorepo `skill/` subdir)
- **Testable in isolation:** Manual only — Claude Code slash command execution

---

## Architecture

```
User: /agent-knowledge-hub <query>
  │
  ▼
SKILL.md (Claude Code slash command)
  │
  ├─ search/NL query ──► GET /api/skills?q=<query>&limit=20
  │                        └─► Claude ranks + explains results
  │
  ├─ install <slug> ──► GET /api/skills/<slug>           (get repo_url, skill_path)
  │                   ► GET github.com/repos/.../contents/<skill_path>   (file list)
  │                   ► GET each file (download_url)     (download)
  │                   ► path traversal check             (security)
  │                   ► Write to ~/.claude/skills/<slug>/
  │
  ├─ update <slug> ───► rm -rf ~/.claude/skills/<slug>/ + re-run install
  │
  ├─ remove <slug> ───► rm -rf ~/.claude/skills/<slug>/  (after confirm)
  │
  ├─ list ────────────► ls ~/.claude/skills/             (local only)
  │
  ├─ rate <slug> N ───► read ~/.s3df-access-token
  │                   ► POST /api/skills/<slug>/rate     (Bearer token)
  │
  ├─ create ──────────► fetch template from SiteSettings.skill_template_repo_url
  │                   ► scaffold SKILL.md in user-chosen dir
  │
  └─ submit ──────────► print web form URL (v1 redirect)
                       ► (v2: POST /api/skills with Bearer token — needs #016)
```

### No migration required
Additive change — new skill file and packaging only. No schema or backend changes in this todo.

---

## Trade-offs

| Choice | Given up | Decision |
|---|---|---|
| GitHub Contents API for install | Single `git clone` simplicity | Handles subdirs natively; no git dependency; path-traversal guard per file |
| Web redirect for `submit` v1 | Fully in-agent submit | Unblocks skill shipping; direct POST lands once Bearer auth is stable |
| `update` = delete + reinstall | Incremental diff | Correct and simple; skills are small; diff adds complexity with little benefit |
| Bearer JWT via `~/.s3df-access-token` | More auth options | Consistent with `s3df login` ecosystem; no new token infrastructure needed |

---

## Delivery Slices

### Slice 1 — Skill file (read-only commands)
**Scope:** `skill/SKILL.md` with `search`, `install`, `list`, `update`, `remove` commands.
Uses existing `GET /api/skills` and GitHub Contents API. No auth required.
**Done when:** AC-1 through AC-5 pass manually. Skill installable from the monorepo.

### Slice 2 — `rate` command + `create` scaffolding
**Scope:** Add `rate` to `SKILL.md` (reads `~/.s3df-access-token`, POSTs to `/rate`). Add `create` scaffolding flow. Add `submit` redirect.
**Note:** `rate` sends the Bearer token; server-side JWT validation is gated on **#016**.
**Done when:** AC-6, AC-7, AC-8 pass.

### Slice 3 — Packaging + bootstrap docs
**Scope:** `plugin.json` in `skill/`, bootstrap instructions in `docs/` and web guides. Update `TODO.md`.
**Done when:** A fresh S3DF user can install via `/plugin install agent-knowledge-hub` from the monorepo.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub Contents API rate limit (60/hr unauth) | Low | Medium | Surface clear error; document `GITHUB_TOKEN` env var workaround |
| Path traversal via crafted `skill_path` | Low | High | Per-file `resolve().is_relative_to()` guard; abort entire install on failure |
| Skill file exceeds LLM context budget | Low | Medium | Keep `SKILL.md` ≤ 8 KB; split verbose docs to `README.md` |
| `~/.s3df-access-token` world-readable | Low | Medium | Document `chmod 600`; skill warns if permissions are too open |
| #016 (Bearer JWT) delayed | Medium | Low | `rate` still works — token sent, server silently ignores until #016 lands |

---

## Definition of Done

- [ ] `skill/SKILL.md` committed to monorepo `skill/` subdir
- [ ] AC-1 through AC-5: search, install, list, update, remove verified manually
- [ ] AC-3: path traversal guard tested with `../` in `skill_path`
- [ ] AC-6, AC-7: rate command works with and without token file
- [ ] Bootstrap instructions added to web guides page
- [ ] `plugin.json` present and valid for `/plugin install` flow
- [ ] `skill/SKILL.md` size verified ≤ 8 KB
- [ ] **#016** (Bearer JWT) deployed to staging before rate auth is considered complete

---

## Problems & Solutions

_None yet._

---

## References

- PRD §2 user stories 48–57 (agent-native discovery & install)
- PRD §15 `/agent-knowledge-hub` design: invocation examples, sub-commands, submit flow, marketplace.json shape, bootstrap instructions
- PRD §8 Slice 10: delivery slice for this feature
- `~/.claude/skills/agent-knowledge-hub/SKILL.md` — existing install-flow implementation (from #002 Slice 4)
