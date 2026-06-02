---
name: agent-knowledge-hub
description: Discover, install, rate, and submit SLAC S3DF catalog skills from within your agent session.
---

# /agent-knowledge-hub

Interact with the SLAC S3DF skills catalog without leaving your agent session.

**Catalog base URL:** `https://agent-knowledge-hub.slac.stanford.edu/cli`
**Skills directory:** `~/.claude/skills/`
**Commands directory:** `~/.claude/commands/`
**Agents directory:** `~/.claude/agents/`
**Token file:** `~/.s3df-access-token` (written by `s3df login`)

---

## Shared procedure: fetch-and-write

All install paths call this primitive. Apply it for every file written during install.

```
fetch-and-write(github_url, local_path, allowed_prefix):
  1. Security check: resolve the full absolute path of local_path.
     Assert it starts with allowed_prefix. If not → abort the entire install,
     warn the user, and do NOT write any file.
  2. Fetch github_url from GitHub Contents API.
     Include Authorization header if GITHUB_TOKEN env var is set.
  3. If response is 403 with X-RateLimit-Remaining: 0 → abort install,
     tell the user to set GITHUB_TOKEN and retry.
  4. If response is any non-200 other than 404 → abort install with the error.
  5. Decode base64 content from the response JSON ("content" field).
  6. Create parent directories of local_path as needed, then write the file.
```

Allowed prefixes by component type:
- `skills` → `~/.claude/skills/<slug>/`
- `commands` → `~/.claude/commands/`
- `agents` → `~/.claude/agents/`

---

## Sub-commands

### Natural-language search (default)
`/agent-knowledge-hub <query>`
`/agent-knowledge-hub search <query>`

1. Fetch `GET /api/skills/summary` — returns slug, name, description, labels, version, avg_rating,
   compatible_platforms for all active skills.
2. Pass the full catalog list and the user's query to Claude.
3. Match the query against name, description, **and labels**.
4. Rank the results by relevance, return the top matches with a one-sentence explanation each.
5. Ask the user if they want to install any of them.

If the user says yes, run the install flow for that slug.

---

### Install by slug
`/agent-knowledge-hub install <slug>`

1. Fetch `GET /api/skills/<slug>` — get `repo_url`, `skill_path`, and `compatible_platforms`.
2. Parse `repo_url` to extract `<owner>/<repo>`. It must be a `https://github.com/` URL.

3. **Locate plugin.json** (try in order; stop at first success):
   a. `GET https://api.github.com/repos/<owner>/<repo>/contents/<skill_path>/plugin.json`
   b. If 404 → `GET https://api.github.com/repos/<owner>/<repo>/contents/<skill_path>/.claude-plugin/plugin.json`
   c. If 404 → **legacy install** (step 9).
   If any step returns a non-404 error → abort install with the error message.

4. **Platform check** — before writing any files:
   - Read `compatible_platforms` from plugin.json (falls back to catalog value if absent).
   - If absent from both → treat as `["claude-code"]` (backward compatibility).
   - If `compatible_platforms` does not include `"claude-code"`:
     ```
     ⚠  This skill declares it does not support claude-code.
        Supported platforms: <list>.
        Install anyway? (y/n)
     ```
     If user says n → abort. If user says y → proceed.
   - If `compatible_platforms` includes other platforms alongside `claude-code`:
     ```
     ℹ  This skill also supports: <others>. Those components are not installed here.
     ```

5. **Install skills component:**
   - If `plugin.json["skills"]` is a **string** (directory path, e.g. `"./skill/"`):
     - Resolve the path relative to `skill_path` in the repo.
     - Fetch directory listing: `GET /repos/<owner>/<repo>/contents/<resolved_path>`
     - Recursively fetch all files (recurse into any subdirectory entries).
     - Cap at 200 files total; if exceeded → warn and abort install.
     - If directory has 0 files → warn: `⚠ skills directory <path> is empty — nothing installed.`
     - For each file: call `fetch-and-write(file_url, ~/.claude/skills/<slug>/<relative_path>, ~/.claude/skills/<slug>/)`.
   - If `plugin.json["skills"]` is an **array** of file paths:
     - For each path: call `fetch-and-write(file_url, ~/.claude/skills/<slug>/<filename>, ~/.claude/skills/<slug>/)`.
   - If `plugin.json["skills"]` is absent → skip skills component.

6. **Install commands component** (same string/array logic as skills):
   - String (directory) → recursively fetch and write to `~/.claude/commands/`, preserving subdirs.
   - Array → fetch each file, write to `~/.claude/commands/`.
   - Allowed prefix: `~/.claude/commands/`.

7. **Install agents component** (same string/array logic):
   - String (directory) → recursively fetch and write to `~/.claude/agents/`, preserving subdirs.
   - Array → fetch each file, write to `~/.claude/agents/`.
   - Allowed prefix: `~/.claude/agents/`.

8. **Install mcp-servers component:**
   - For each entry in `plugin.json["mcp-servers"]`:
     - Entry must have `name` and `command` fields (optional: `args: []`, `env: {}`).
     - Run: `claude mcp add <name> <command> [args...]`
     - Confirm each registered MCP server.

9. **Write installed-files manifest** (after all files confirmed written):
   ```json
   {
     "slug": "<slug>",
     "installed_at": "<ISO timestamp>",
     "commands": ["<absolute-path>", ...],
     "agents":   ["<absolute-path>", ...]
   }
   ```
   Write to `~/.claude/skills/<slug>/.installed-manifest.json`.
   List every file installed into `commands` and `agents` (not skills — the slug dir is deleted as a whole).
   If no commands or agents were installed, write an empty manifest anyway (commands: [], agents: []).

10. Print a summary of all installed paths and registered MCP servers.
    If `plugin.json` contains a `version` field: `Installed <slug> v<version>`.

11. **Legacy install** (reached only when no plugin.json found at steps 3a or 3b):
    Fetch the file listing from the GitHub Contents API:
    `GET https://api.github.com/repos/<owner>/<repo>/contents/<skill_path>`
    If `skill_path` is `/` or empty, use the repo root.
    For each file in the listing: call `fetch-and-write(file_url, ~/.claude/skills/<slug>/<filename>, ~/.claude/skills/<slug>/)`.
    Write an empty manifest (`commands: [], agents: []`) after install.

If the GitHub API returns a rate-limit error (403 with X-RateLimit-Remaining: 0), suggest the user set a `GITHUB_TOKEN` environment variable.

---

### List installed skills
`/agent-knowledge-hub list`

Scan `~/.claude/skills/` and print each subdirectory name. For each:
1. If `SKILL.md` is present: show `name`, `description`, and `version` frontmatter.
2. If `plugin.json` is also present: show a second line with platform and component summary.

```
<slug>   v<version>   <name> — <description>
         Platforms: claude-code, codex   Components: 1 skill, 7 agents, 1 MCP server
```

Omit `v<version>` if no version frontmatter. Omit the second line if no `plugin.json`.

---

### Update a skill
`/agent-knowledge-hub update <slug>`

1. Read `~/.claude/skills/<slug>/SKILL.md` version frontmatter → `<old_version>` (if present).
2. **Clean up old install:**
   a. Read `~/.claude/skills/<slug>/.installed-manifest.json` into memory (if present).
   b. If manifest absent: read `~/.claude/skills/<slug>/plugin.json["commands"]` and `["agents"]` as string arrays (fallback for pre-manifest installs).
   c. Delete every path collected in steps a–b from `~/.claude/commands/` and `~/.claude/agents/`.
   d. For each MCP server in the old `plugin.json["mcp-servers"]`: run `claude mcp remove <name>`.
3. Delete `~/.claude/skills/<slug>/` entirely.
4. Re-run the full install flow for that slug.
5. After install, read the new `version` from the freshly installed SKILL.md → `<new_version>`.
6. Print:
   - If both versions available: `Updated <slug> v<old_version> → v<new_version>`
   - If only new version: `Updated <slug> → v<new_version>`
   - Otherwise: `Updated <slug>`

---

### Remove a skill
`/agent-knowledge-hub remove <slug>`

Ask the user to confirm, then — **in this exact order** (manifest is inside slug dir; read before deleting):

1. Read `~/.claude/skills/<slug>/.installed-manifest.json` into memory (if present).
2. If manifest absent: read `~/.claude/skills/<slug>/plugin.json["commands"]` and `["agents"]` as string arrays.
   If those are directory-form strings (not arrays), warn:
   `⚠ Could not determine which commands/agents were installed (pre-manifest directory-form install). Remove them manually from ~/.claude/commands/ and ~/.claude/agents/.`
3. Delete every path collected in steps 1–2 from `~/.claude/commands/` and `~/.claude/agents/`.
   Skip any path that no longer exists (do not abort).
4. For each MCP server in `plugin.json["mcp-servers"]`: run `claude mcp remove <name>`.
5. Delete `~/.claude/skills/<slug>/` entirely.

---

### Validate a local plugin
`/agent-knowledge-hub validate <path>`

Validate a plugin directory before submitting it to the catalog.

1. Look for `<path>/plugin.json` or `<path>/.claude-plugin/plugin.json`. If neither exists, fail:
   `✗ No plugin.json found at <path>/plugin.json or <path>/.claude-plugin/plugin.json`

2. Parse the file as JSON. If invalid, fail with the parse error.

3. Check required fields:
   - `name` (non-empty string) — fail if missing or empty.
   - `version` (non-empty string) — warn if missing (not a hard failure).
   - At least one of `skills`, `commands`, `agents`, `mcp-servers` must be present — fail if none.

4. For each of `skills`, `commands`, `agents`:
   - If the value is a **string** (directory path):
     - Check the directory exists at `<path>/<value>`.
     - Count `.md` files inside; note subdirectories.
     - Report: `✓ skills: directory <value> (N files)`
   - If the value is an **array** of file paths:
     - Check each listed file exists at `<path>/<file_path>`.
     - If the file is a `.md` file with a `---` frontmatter block, verify it contains both `name:` and `description:` keys.
     - Report each missing file or missing frontmatter field as a failure.

5. If `compatible_platforms` is present:
   - Must be a non-empty array of strings — fail if not.
   - Report: `✓ compatible_platforms: <list>`

6. If `author` is present:
   - Must have a `name` field (non-empty string) — fail if missing.
   - Report: `✓ author: <name> <<email>>` (email optional)

7. Check slug availability: derive the expected slug from `plugin.json["name"]` (lowercased, spaces to hyphens).
   Call `GET /api/skills/<slug>`:
   - 404 → slug is available ✓
   - 200 → slug is already taken — warn: `⚠ Slug "<slug>" is already registered in the catalog.`
   - Network error → skip this check and note it.

8. Print a summary:
```
Validation results for <path>:
  ✓ plugin.json found and valid JSON
  ✓ name: <name>
  ✓ version: <version>
  ✓ skills: directory ./skills (3 files)
  ✓ agents: 2 agent files declared and present
  ✓ compatible_platforms: claude-code, codex
  ✓ author: Claudio Bisegni <bisegni@slac.stanford.edu>
  ✓ slug "<slug>" is available

All checks passed.
```
Or list each failure with `✗` and print `X check(s) failed.`

---

### Rate a skill
`/agent-knowledge-hub rate <slug> <1-5>`

1. Read `~/.s3df-access-token`. If the file does not exist or is empty:
   Tell the user: `"No SLAC token found. Run 's3df login' to authenticate, then try again."` — stop here.
2. Strip whitespace from the token.
3. `POST /api/skills/<slug>/rate` with body `{"value": <1-5>}` and header `Authorization: Bearer <token>`.
4. On success (200): confirm the rating was saved.
5. On 401: display the `detail` field from the JSON response directly — it is written to be actionable (e.g. `"Token expired. Re-run 's3df login' to refresh your session."`).

---

### Create a new skill scaffold
`/agent-knowledge-hub create`

Ask the user:
1. A directory to create the skill in (default: current directory)
2. A slug/name for the skill
3. A one-sentence description
4. Does this skill include sub-agents? (y/n) — if yes: enter agent names one per line
5. Does this skill need an MCP server? (y/n) — if yes: server name and command
6. Does this skill include Python scripts or other supporting files? (y/n)
7. Target platforms: `[1] claude-code only  [2] claude-code + codex  [3] all`

Scaffold based on answers. For a skill with agents and scripts selected:

**Directory structure:**
```
<dir>/
  plugin.json
  README.md
  skills/<slug>/
    SKILL.md
    scripts/        ← only if scripts=yes
      .gitkeep
  agents/           ← only if agents=yes
    <agent1>.md
    <agent2>.md
```

**`skills/<slug>/SKILL.md`:**
```markdown
---
name: <slug>
description: <description>
---

# /<slug>

TODO: describe what this skill does and how to invoke it.

## Instructions

TODO: write the instructions for Claude to follow when this skill is invoked.
```

**`agents/<agentN>.md`** (one per agent name entered):
```markdown
---
name: <agent-name>
description: TODO: describe this agent's role
---

TODO: write the system prompt for this agent.
```

**`plugin.json`:**
```json
{
  "name": "<slug>",
  "description": "<description>",
  "version": "0.1.0",
  "author": { "name": "", "email": "" },
  "license": "MIT",
  "keywords": [],
  "compatible_platforms": ["claude-code"],
  "skills": "./skills",
  "agents": [
    "./agents/<agent1>.md",
    "./agents/<agent2>.md"
  ]
}
```

Adjust `plugin.json`:
- Omit `"agents"` if none selected.
- Add `"mcp-servers": [{"name": "<name>", "command": "<command>", "args": []}]` if MCP selected.
- Set `"compatible_platforms": ["claude-code", "codex"]` or `["claude-code", "codex", "other"]` per platform choice.

Confirm all created file paths to the user and remind them:
- Run `/agent-knowledge-hub validate .` to check the plugin before submitting.
- Submit immediately from this directory: `/agent-knowledge-hub submit .`
- Or push to GitHub first and use the web flow: `/agent-knowledge-hub submit`

---

### Submit to the catalog (web)
`/agent-knowledge-hub submit`

Ask for the GitHub URL of the skill's repo. Then print:

```
To submit your skill to the SLAC S3DF catalog, open:
  https://agent-knowledge-hub.slac.stanford.edu

Click "Submit a skill" and paste your GitHub URL.
```

---

### Submit a local skill directory
`/agent-knowledge-hub submit <path>`

Submit a skill from a local directory — no GitHub push required.

**Token resolution (in order — stop at first found):**
1. `AGENT_KNOWLEDGE_HUB_TOKEN` environment variable (CI/automation)
2. `~/.s3df-access-token` file (written by `s3df login` — same token used by `rate`)
3. `~/.claude/settings.local.json` field `agent_knowledge_hub_token`

**If no token is found**, print:
```
✗ No auth token found.
  Run 's3df login' to authenticate, then try again.
  Or set AGENT_KNOWLEDGE_HUB_TOKEN in your environment for CI use.
```

**Steps:**

1. Resolve `<path>` to an absolute path (`Path(<path>).expanduser().resolve()`).

2. **Validate the directory:**
   - Path does not exist → `✗ Path not found: <path>`
   - Path is a file, not a directory → `✗ Expected a directory, got a file: <path>`
   - Directory has no SKILL.md / skill.md / CLAUDE.md / AGENTS.md → `✗ No skill instruction file found in <path>. Create a SKILL.md first (try /agent-knowledge-hub create).`
   - SKILL.md has no name in frontmatter and no --name flag given → `✗ SKILL.md has no 'name' field in frontmatter. Add one or pass --name <slug>.`

3. **Read recognised skill files** from the directory (SKILL.md, skill.md, CLAUDE.md, AGENTS.md, README.md, plugin.json, package.json, pyproject.toml). Skip files larger than 100 KB.

4. **POST** to `https://agent-knowledge-hub.slac.stanford.edu/api/skills` with:
   ```json
   {
     "repo_url": "local://<absolute-path>",
     "source_type": "local",
     "snapshotted_files": { "<filename>": "<content>", ... }
   }
   ```
   Include header: `Authorization: Bearer <token>`

5. **Handle errors:**
   - `401` → `✗ Auth token rejected. Run 's3df login' to refresh your token.`
   - `409` (duplicate) → `✗ A skill from this path is already registered. Use '/agent-knowledge-hub update <slug>' to update it.`
   - Other error → show HTTP status and API error detail

6. **On success**, print:
   ```
   ✓ Submitted "<name>" to the catalog.
     Slug:    <slug>
     Source:  local (<N> files snapshotted)
     View:    https://agent-knowledge-hub.slac.stanford.edu/skills/<slug>
   ```

**Note:** After submitting a local skill, if you later push it to GitHub you can link it by editing the skill entry and updating the repo URL.

**Coexistence with web submit:** `submit` (no args) → web flow as above. `submit <path>` → local directory flow. The two are distinct sub-commands.

---

## Error handling

- **Skill not found (404):** Tell the user the slug doesn't exist and suggest running a search.
- **Deactivated skill (410):** Tell the user the skill has been deactivated. If `superseded_by_slug` is present, suggest installing that instead.
- **Path traversal attempt:** Abort install, warn the user that the skill contains unsafe file paths, and do not write any file.
- **Rate limit (403):** Suggest the user set `GITHUB_TOKEN` and retry.
- **Non-404 error fetching plugin.json:** Abort install with the HTTP status and message — do not fall through to legacy install.
- **Network error:** Show the error message and suggest retrying.
- **MCP registration failure:** Show the error from `claude mcp add` and suggest the user run the command manually.
