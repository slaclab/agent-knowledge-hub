---
name: agent-knowledge-hub-dev
description: Discover, install, rate, and submit SLAC S3DF catalog skills from within your agent session.
---

# /agent-knowledge-hub-dev

Interact with the SLAC S3DF skills catalog without leaving your agent session.

**Catalog base URL:** `https://agent-knowledge-hub-dev.slac.stanford.edu/cli`
**Skills directory:** `~/.claude/skills/`
**Commands directory:** `~/.claude/commands/`
**Agents directory:** `~/.claude/agents/`
**Token file:** `~/.s3df-access-token` (written by `s3df login`)

---

## Sub-commands

### Natural-language search (default)
`/agent-knowledge-hub-dev <query>`
`/agent-knowledge-hub-dev search <query>`

1. Fetch `GET /api/skills/summary` — returns slug, name, description, keywords, labels, version, avg_rating for all active skills.
2. Pass the full catalog list and the user's query to Claude.
3. Match the query against name, description, labels, **and keywords**.
4. Rank the results by relevance, return the top matches with a one-sentence explanation each.
5. Ask the user if they want to install any of them.

If the user says yes, run the install flow for that slug.

---

### Install by slug
`/agent-knowledge-hub-dev install <slug>`

1. Fetch `GET /api/skills/<slug>` — get `repo_url` and `skill_path`.
2. Parse `repo_url` to extract `<owner>/<repo>`. It must be a `https://github.com/` URL.
3. Attempt to fetch `<skill_path>/plugin.json` from the GitHub Contents API:
   `GET https://api.github.com/repos/<owner>/<repo>/contents/<skill_path>/plugin.json`
   If not found, fall back to **legacy install** (step 8).

4. **plugin.json install:** Parse the `plugin.json`. For each component type present:

   **skills** — for each file path in `plugin.json["skills"]`:
   - Download the file from GitHub.
   - Security check: assert the resolved path stays inside `~/.claude/skills/<slug>/`.
   - Write to `~/.claude/skills/<slug>/`.

   **commands** — for each file path in `plugin.json["commands"]`:
   - Download the file from GitHub.
   - Security check: assert the resolved path stays inside `~/.claude/commands/`.
   - Write to `~/.claude/commands/`.

   **agents** — for each file path in `plugin.json["agents"]`:
   - Download the file from GitHub.
   - Security check: assert the resolved path stays inside `~/.claude/agents/`.
   - Write to `~/.claude/agents/`.

   **mcp-servers** — for each entry in `plugin.json["mcp-servers"]`:
   - Each entry must have a `name` and a `command` field (and optionally `args: []` and `env: {}`).
   - Run: `claude mcp add <name> <command> [args...]`
   - Confirm each registered MCP server.

5. Print a summary of all installed paths and registered MCP servers.
6. If `plugin.json` contains a `version` field, note: `Installed <slug> v<version>`.

7. **Security check (mandatory for all file writes):** Before writing any file, resolve the target
   path and assert it stays within `~/.claude/`. If any file would escape this directory, abort
   the entire install and warn the user. Never write the file.

8. **Legacy install (no plugin.json):** Fetch the file listing from the GitHub Contents API:
   `GET https://api.github.com/repos/<owner>/<repo>/contents/<skill_path>`
   If `skill_path` is `/` or empty, use the repo root.
   Download each file and write to `~/.claude/skills/<slug>/`.

If the GitHub API returns a rate-limit error (403 with X-RateLimit-Remaining: 0), suggest the user set a `GITHUB_TOKEN` environment variable.

---

### List installed skills
`/agent-knowledge-hub-dev list`

Scan `~/.claude/skills/` and print each subdirectory name. If a `SKILL.md` is present, show its
`name` frontmatter, `description` frontmatter, and `version` frontmatter alongside the slug:

```
<slug>   v<version>   <name> — <description>
```

Omit `v<version>` if no version frontmatter is present.

---

### Update a skill
`/agent-knowledge-hub-dev update <slug>`

1. If `~/.claude/skills/<slug>/SKILL.md` exists, read its `version` frontmatter (call it `<old_version>`).
2. Delete `~/.claude/skills/<slug>/`.
3. Re-run the full install flow for that slug.
4. After install, read the new `version` from the freshly installed SKILL.md (call it `<new_version>`).
5. Print:
   - If both versions available: `Updated <slug> v<old_version> → v<new_version>`
   - If only new version: `Updated <slug> → v<new_version>`
   - Otherwise: `Updated <slug>`

---

### Remove a skill
`/agent-knowledge-hub-dev remove <slug>`

Ask the user to confirm, then:

1. Attempt to fetch `~/.claude/skills/<slug>/plugin.json`. If present, parse it and:
   - Delete any files listed in `commands` from `~/.claude/commands/`.
   - Delete any files listed in `agents` from `~/.claude/agents/`.
   - For each entry in `mcp-servers`, run: `claude mcp remove <name>`
2. Delete `~/.claude/skills/<slug>/`.

If `plugin.json` is not present, just delete `~/.claude/skills/<slug>/`.

---

### Validate a local plugin
`/agent-knowledge-hub-dev validate <path>`

Validate a plugin directory before submitting it to the catalog.

1. Look for `<path>/plugin.json` or `<path>/.claude-plugin/plugin.json`. If neither exists, fail with:
   `✗ No plugin.json found at <path>/plugin.json or <path>/.claude-plugin/plugin.json`

2. Parse the file as JSON. If invalid, fail with the parse error.

3. Check required fields:
   - `name` (non-empty string) — fail if missing or empty.
   - `version` (non-empty string) — warn if missing (not a hard failure).
   - At least one of `skills`, `commands`, `agents`, `mcp-servers` must be a non-empty array — fail if none present.

4. For each file path listed in `skills`, `commands`, and `agents`:
   - Check that the file exists at `<path>/<file_path>`.
   - If the file is a `.md` file with a `---` frontmatter block, verify it contains both `name:` and `description:` keys.
   - Report each missing file or missing frontmatter field as a failure.

5. Check slug availability: derive the expected slug from `plugin.json["name"]` (lowercased, spaces to hyphens).
   Call `GET /api/skills/<slug>`:
   - 404 → slug is available ✓
   - 200 → slug is already taken — warn: `⚠ Slug "<slug>" is already registered in the catalog.`
   - Network error → skip this check and note it.

6. Print a summary:
```
Validation results for <path>:
  ✓ plugin.json found and valid JSON
  ✓ name: <name>
  ✓ version: <version>
  ✓ components: skills (2), commands (1)
  ✓ all 3 component files exist
  ✓ frontmatter valid on all .md files
  ✓ slug "<slug>" is available

All checks passed.
```
Or list each failure with `✗` and a description, then print `X check(s) failed.`

---

### Rate a skill
`/agent-knowledge-hub-dev rate <slug> <1-5>`

1. Read `~/.s3df-access-token`. If the file does not exist or is empty:
   Tell the user: `"No SLAC token found. Run 's3df login' to authenticate, then try again."` — stop here.
2. Strip whitespace from the token.
3. `POST /api/skills/<slug>/rate` with body `{"value": <1-5>}` and header `Authorization: Bearer <token>`.
4. On success (200): confirm the rating was saved.
5. On 401: display the `detail` field from the JSON response directly — it is written to be actionable (e.g. `"Token expired. Re-run 's3df login' to refresh your session."`).

---

### Create a new skill scaffold
`/agent-knowledge-hub-dev create`

Ask the user for:
- A directory to create the skill in (default: current directory)
- A slug/name for the skill
- A one-sentence description

Then scaffold two files:

**`SKILL.md`:**
```
---
name: <slug>
description: <description>
---

# /<slug>

TODO: describe what this skill does and how to invoke it.

## Instructions

TODO: write the instructions for Claude to follow when this skill is invoked.
```

**`plugin.json`:**
```json
{
  "name": "<slug>",
  "description": "<description>",
  "version": "0.1.0",
  "skills": [
    {
      "name": "<slug>",
      "path": "SKILL.md"
    }
  ]
}
```

Confirm both file paths to the user and remind them:
- Run `/agent-knowledge-hub-dev validate .` to check the plugin before submitting.
- Submit via `/agent-knowledge-hub-dev submit` once it's in a GitHub repo.

---

### Submit to the catalog
`/agent-knowledge-hub-dev submit`

Ask for the GitHub URL of the skill's repo. Then print:

```
To submit your skill to the SLAC S3DF catalog, open:
  https://agent-knowledge-hub-dev.slac.stanford.edu

Click "Submit a skill" and paste your GitHub URL.
```

(Direct API submission via Bearer JWT is planned for v2.)

---

## Error handling

- **Skill not found (404):** Tell the user the slug doesn't exist and suggest running a search.
- **Deactivated skill (410):** Tell the user the skill has been deactivated. If `superseded_by_slug` is present, suggest installing that instead.
- **Path traversal attempt:** Abort install, warn the user that the skill's `skill_path` contains unsafe components, and do not write any files.
- **Network error:** Show the error message and suggest retrying.
- **MCP registration failure:** Show the error from `claude mcp add` and suggest the user run the command manually.
