---
name: agent-knowledge-hub
description: Discover, install, rate, and submit SLAC S3DF catalog skills from within your agent session.
---

# /agent-knowledge-hub

Interact with the SLAC S3DF skills catalog without leaving your agent session.

**Catalog base URL:** `https://agent-knowledge-hub.slac.stanford.edu`
**Skills directory:** `~/.claude/skills/`
**Token file:** `~/.s3df-access-token` (written by `s3df login`)

---

## Sub-commands

### Natural-language search (default)
`/agent-knowledge-hub <query>`
`/agent-knowledge-hub search <query>`

1. Fetch `GET /api/skills/summary` — returns slug, name, description, labels, avg_rating for all active skills.
2. Pass the full catalog list and the user's query to Claude.
3. Rank the results by relevance, return the top matches with a one-sentence explanation each.
4. Ask the user if they want to install any of them.

If the user says yes, run the install flow for that slug.

---

### Install by slug
`/agent-knowledge-hub install <slug>`

1. Fetch `GET /api/skills/<slug>` — get `repo_url` and `skill_path`.
2. Parse `repo_url` to extract `<owner>/<repo>`. It must be a `https://github.com/` URL.
3. Fetch the file listing from the GitHub Contents API:
   `GET https://api.github.com/repos/<owner>/<repo>/contents/<skill_path>`
   If `skill_path` is `/` or empty, use the repo root.
4. For each file in the response, download its `download_url`.
5. **Security check (mandatory):** Before writing each file, resolve the target path and assert it stays inside `~/.claude/skills/<slug>/`. If any file would escape this directory, abort the entire install and warn the user. Never write the file.
6. Write all files to `~/.claude/skills/<slug>/`.
7. Confirm the install path to the user.

If the GitHub API returns a rate-limit error (403 with X-RateLimit-Remaining: 0), suggest the user set a `GITHUB_TOKEN` environment variable.

---

### List installed skills
`/agent-knowledge-hub list`

Scan `~/.claude/skills/` and print each subdirectory name. If a `SKILL.md` is present, show its `description` frontmatter field alongside the slug.

---

### Update a skill
`/agent-knowledge-hub update <slug>`

Delete `~/.claude/skills/<slug>/` then re-run the install flow for that slug.

---

### Remove a skill
`/agent-knowledge-hub remove <slug>`

Ask the user to confirm, then delete `~/.claude/skills/<slug>/`.

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

Ask the user for:
- A directory to create the skill in (default: current directory)
- A slug/name for the skill
- A one-sentence description

Then scaffold a `SKILL.md` file using this template:

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

Confirm the file path to the user and remind them they can submit it via `/agent-knowledge-hub submit` once it's in a GitHub repo.

---

### Submit to the catalog
`/agent-knowledge-hub submit`

Ask for the GitHub URL of the skill's repo. Then print:

```
To submit your skill to the SLAC S3DF catalog, open:
  https://agent-knowledge-hub.slac.stanford.edu

Click "Submit a skill" and paste your GitHub URL.
```

(Direct API submission via Bearer JWT is planned for v2.)

---

## Error handling

- **Skill not found (404):** Tell the user the slug doesn't exist and suggest running a search.
- **Deactivated skill (410):** Tell the user the skill has been deactivated. If `superseded_by_slug` is present, suggest installing that instead.
- **Path traversal attempt:** Abort install, warn the user that the skill's `skill_path` contains unsafe components, and do not write any files.
- **Network error:** Show the error message and suggest retrying.
