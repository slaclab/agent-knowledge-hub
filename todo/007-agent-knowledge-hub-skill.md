# 007 — `/agent-knowledge-hub` Agent-Native Discovery & Install Skill

**Status:** 📋 Preparing
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

1. **`s3df login` JWT format**: Does the token written to `~/.s3df-access-token` conform to a standard SLAC JWT spec the backend can validate? If yes, Option A is straightforward. If no, Option B (token exchange) is needed.
2. **`submit` — GitHub repo creation**: Does the skill need a GitHub personal access token from the user, or does it rely on the user having `gh` CLI configured?
3. **Skill repo**: Should `slaclab/agent-knowledge-hub` be a new standalone repo (separate from this app repo), or a subdirectory (`skill/`) in this monorepo?

---

## Implementation Plan

_To be filled in after open questions are resolved and `/codebase-draft` runs._

---

## Problems & Solutions

_None yet._

---

## References

- PRD §2 user stories 48–57 (agent-native discovery & install)
- PRD §5 API contract: `GET /api/skills/summary`, `GET /api/marketplace.json`
- PRD §15 `/agent-knowledge-hub` design: invocation examples, sub-commands, submit flow, marketplace.json shape, bootstrap instructions
- [Slice 10 in PRD §8]: delivery slice for this feature
