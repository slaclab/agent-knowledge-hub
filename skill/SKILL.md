---
name: agent-knowledge-hub
description: Discover, install, rate, and submit SLAC S3DF catalog skills from within your agent session.
---

# /agent-knowledge-hub

> **Beta** — the catalog and install tooling are actively evolving. Report issues at agent-knowledge-hub.slac.stanford.edu.

Interact with the SLAC S3DF skills catalog without leaving your agent session.

**Catalog base URL:** `https://agent-knowledge-hub.slac.stanford.edu/cli`
**Skills directory:** `~/.claude/skills/`
**Commands directory:** `~/.claude/commands/`
**Agents directory:** `~/.claude/agents/`
**Token file:** `~/.s3df-access-token` (written by `s3df login`)

---

## Commands

### Search (default)
`/agent-knowledge-hub <query>`

Fetch `GET /api/skills/summary`, match against name/description/labels, rank by relevance, show top results with a one-sentence explanation each, and offer to install.

---

### Install
`/agent-knowledge-hub install <slug>`

1. Fetch `GET /api/skills/<slug>` for `repo_url`, `skill_path`, and `pinned_commit_sha`.
2. Clone the repo (`git clone --depth 1`, or pinned SHA if present). Fall back to GitHub Contents API if git is unavailable.
3. Read `plugin.json` (or `.claude-plugin/plugin.json`). Check `compatible_platforms` — warn if `claude-code` is not listed.
4. Install components to their target directories, enforcing path-prefix security on every write:
   - `skills` → `~/.claude/skills/<slug>/`
   - `commands` → `~/.claude/commands/`
   - `agents` → `~/.claude/agents/`
   - `mcp-servers` → `claude mcp add <name> <command> [args...]`
5. Write `~/.claude/skills/<slug>/.installed-manifest.json` listing all installed commands and agents.
6. Record install event via `POST /api/me/installs/<slug>` (fire-and-forget; never aborts install on failure).

Print installed paths and version on success. If `pinned_commit_sha` was used: `Installed at commit <short_sha>`.

---

### List installed
`/agent-knowledge-hub list`

Scan `~/.claude/skills/` and print each skill's slug, version, name, and description from frontmatter.

---

### Update
`/agent-knowledge-hub update <slug>`

Remove the old install (commands, agents, MCP servers, skill dir), then re-run the full install flow. Print `Updated <slug> v<old> → v<new>`.

---

### Remove
`/agent-knowledge-hub remove <slug>`

Confirm with the user, then delete all installed commands and agents (from manifest), deregister MCP servers, and delete `~/.claude/skills/<slug>/`.

---

### Rate
`/agent-knowledge-hub rate <slug> <1-5>`

POST `Authorization: Bearer <token>` to `/api/skills/<slug>/rate`. Requires `~/.s3df-access-token` (run `s3df login` first).

---

### Validate
`/agent-knowledge-hub validate <path>`

Check `plugin.json` for required fields (`name`, at least one component), verify all declared files exist, and check slug availability against the catalog. Print a pass/fail summary.

---

### Create scaffold
`/agent-knowledge-hub create`

Interactively scaffold a new skill directory with `plugin.json`, `SKILL.md`, and optional agent/MCP stubs.

---

### Submit
`/agent-knowledge-hub submit`
`/agent-knowledge-hub submit <path>`

**No args:** print the catalog URL and ask the user to paste their GitHub URL via the web form.

**With path:** POST the local skill directory directly to the catalog API using `~/.s3df-access-token` (or `AGENT_KNOWLEDGE_HUB_TOKEN` env var). Requires a valid `SKILL.md` with a `name` field.

---

## Error handling

- **404:** Skill not found — suggest searching.
- **410:** Skill deactivated — show `superseded_by_slug` if present.
- **Path traversal:** Abort install, warn user, write nothing.
- **Rate limit (403):** Suggest setting `GITHUB_TOKEN` and retrying.
- **Network error:** Show message and suggest retrying.
