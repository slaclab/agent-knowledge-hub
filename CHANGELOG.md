# Changelog

## Unreleased

### Client: workspace installs and the development catalog (#057)

- **`--workspace`** — `install`, `install skillset`, `list`, `update` and `remove` take `--workspace`, which works on the project's own `.claude/` folder, `<workspace>/.claude/`, instead of `~/.claude/`. A skill installed that way loads only in sessions started in that project. The client makes the folders without group or other write, sets the installed files to `0644`, or `0755` where the skill marks them executable, and adds the skill's folder and the command and agent files it wrote to the repository's `.git/info/exclude`, so they never show as untracked; `remove --workspace` takes the lines out. A workspace whose path holds a character other than letters, digits, `.`, `_`, `-` and `/` is refused, and so is the home folder, a `.claude/` folder that is a link or not yours, and one other accounts can write. An MCP server's printed command adds it for that workspace only (`claude mcp add-json --scope local`), a server that runs a file from `${HOME}/.claude/skills/` gets no command, and the closing message names any installed file that refers to `~/.claude/skills/<slug>/`.
- **Checked component paths** — every install now refuses a command or agent file whose path in `plugin.json` holds a character other than letters, digits, `.`, `_`, `-` and `/`, or a `.` or `..` part, before any command takes it. Such a name could otherwise close a command's quoting and run as you; the agent checks of earlier clients passed agent paths to commands unchecked.
- **`install --exact`** — installs into the workspace exactly the skills and skillsets a list names, for a list the user confirmed elsewhere, such as Cogito's New session dialog. Each item installs only when the catalog's current entry, or the skillset's version and members, equals its line; an item that changed installs nothing and is reported. The command asks nothing.
- **The development catalog** — with `AKH_INSTANCE=dev` in the session's environment, `hub-request.sh` sends to `https://agent-knowledge-hub-dev.slac.stanford.edu` with `.s3df-dev-access-token`, and success lines say so. No other value changes anything, and the production token never goes to the development catalog.
- **Client 2.4.0** — an existing plugin install keeps the earlier client until you run `/plugin marketplace update SLAC-Agent-Knowledge-Hub` in a session, or `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` in a shell.

**New docs:** `docs/adr/adr-u44-client-workspace-install.md`.

## 0.21.0 — 2026-10-16

### Skillsets: pages for browsing and curating (#006, frontend)

- **`/skillsets`** — lists every skillset with its description, skill count and curator, with a **Skillsets** link in the top bar. Signed-in users get **+ Create Skillset**, which suggests a slug from the name and offers a free one when the slug is taken.
- **Skillset page** — shows the skills in their stored order, marks deactivated ones, warns above the list when any member needs SLAC GitHub access, and gives the `/agent-knowledge-hub install skillset <slug>` command with a copy button. The owner and admins can rename, re-describe or delete the skillset.
- **Curating** — the owner adds skills with a search that matches part of a word, so "depl" finds "deploy", removes them, and moves them up or down. A move made from a page that another tab has since changed is not saved; the page reloads the list and says so. **Add new skill →** opens the submit form, which adds the new skill to the skillset and returns to it.
- **Skill pages** — a skill's page lists the skillsets that hold it, and a skill card says how many. A user who owns skillsets gets an **Add to skillset** menu on every skill page. The skill's submitter can remove it from any skillset, after a confirmation, because only the curator can add it back.

### Skillsets: `install skillset` (#006, client)

- **`/agent-knowledge-hub install skillset <slug>`** — installs every skill in a skillset, in the order its curator chose. Before it installs anything it fetches every member, asks whether to replace a skill folder it did not install, then lists the skills it will install, with each repository and `MCP server, not added` or `scripts` where they apply, and asks once. An installed member is skipped and a failed one is reported while the rest install; the run ends with a summary line, one line per failure, and the server blocks of every member, grouped by member.
- **Checked catalog values** — plain `install` and `install skillset` now refuse a catalog entry whose `repo_url`, `skill_path` or pinned commit falls outside the characters the client's commands can take, before any command runs. Clones and pinned fetches fail instead of waiting for a password when a repository cannot be read, and an internal repository's failure points to `gh auth login`.
- **Client 2.3.0** — an existing plugin install keeps the earlier client until you run `/plugin marketplace update SLAC-Agent-Knowledge-Hub` in a session, or `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` in a shell.

**New docs:** `docs/adr/adr-u20-akh-install-skillset.md`.

## 0.20.2 — 2026-10-16

### Security: the backend no longer logs the internal API secret

- **Auth warning** — when a request carried the correct `X-Internal-Secret` with an empty `X-Forwarded-User`, the backend logged every `X-` header with its value, the secret included. It now logs the header names only. A deployment whose logs are collected outside the pod should rotate `INTERNAL_API_SECRET` if such a line was ever written.
- **0.20.1** — built and pushed with the old log line, and never deployed. Do not deploy it.

### Security: local submissions refuse unsafe file names (#049)

- **`POST /api/skills`** — a `local` submission returns 422 when a `snapshotted_files` name is absolute, starts with a drive letter, contains a backslash or a control character, or has an empty, `.` or `..` segment. The message names the file and the rule. GitHub submissions are unaffected. No stored skill on dev or prod is `local`.

### Security: a pinned install fetches exactly the pinned commit (#053)

- **`/agent-knowledge-hub install`** — for a pinned skill, the client fetches only the pinned commit, by its ID, checks it out detached, and stops unless `HEAD` is that commit. A branch named like the pinned commit, which a repository owner can create, no longer changes what is installed. A pin behind the default branch's tip, which `git clone --depth 1` could not reach, now installs.
- **No `git`** — a pinned skill is no longer installed through the GitHub Contents API, which dropped the pin; the client says that `git` is needed.
- **Client 2.2.0** — an existing plugin install keeps the earlier client until you run `/plugin marketplace update SLAC-Agent-Knowledge-Hub` in a session, or `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` in a shell.

### Fix: the submit form shows why the catalog refused a skill

- **Validation messages** — a 422 from `POST /api/skills` now shows its messages, such as the allowed characters of `skill_path`, instead of the raw `detail` list.

## 0.20.0 — 2026-10-16

### Security: both containers run as an unprivileged user with a read-only root filesystem (#033)

- **Images** — the backend runs as `appuser` and the frontend as `node`, both UID 1000. The frontend's code stays owned by root, so the server cannot change it.
- **Kubernetes** — the hub's dev and prod deployments set `runAsNonRoot`, UID and GID 1000, `allowPrivilegeEscalation: false` and `readOnlyRootFilesystem: true`, and drop every capability. `/tmp` in both containers and the frontend's `/app/.next/cache` are `emptyDir` volumes.

### Security: production runs images by digest (#034)

- **Pinned image lines** — prod's deployments name each image as `tag@sha256:<digest>`, so a re-pushed tag cannot change what a restarted pod runs. Dev keeps `:latest`.
- **`make pin-digests`** — looks up the registry digests of a release tag and writes them into the prod manifests. `docs/runbooks/image-digest-pinning.md` covers checking a running pod and rolling back.

### Security: the backend image installs only hash-pinned packages (#036)

- **Lockfiles** — `backend/requirements.lock` pins all 44 runtime packages, transitive ones included, with their SHA-256 hashes, and `backend/requirements-dev.lock` pins the test and tooling set on top of the same runtime versions. Both are generated by pip-tools with Python 3.12.
- **Image build** — the backend Dockerfile runs `pip install --require-hashes --only-binary :all: -r requirements.lock`, so a substituted package or an unpinned dependency aborts the build.
- **New make targets** — `make -C backend lock` regenerates both lockfiles, `lock-check` fails when they are stale, and `audit` runs pip-audit on the runtime lock. The root `make backend` runs `lock-check` and `audit` before it pushes an image. `make -C backend dev` installs from `requirements-dev.lock` with hash checking.

### Security: catalog entries carry only shell-safe `repo_url` and `skill_path` values (#045)

The `/agent-knowledge-hub` client passes each skill's `repo_url` and `skill_path` to `git clone` and `cp` on the installing user's machine, so the catalog now refuses values that could carry shell syntax.

- **`repo_url`** — `POST /api/skills` returns 422 unless a GitHub submission's `repo_url` is `https://github.com/<owner>/<repo>`, with an owner of letters, digits and `-` (up to 39 characters) and a repository of letters, digits, `.`, `_` and `-` (up to 100). `forked_from_url` uses the same rule.
- **`skill_path`** — every submission, GitHub or local, returns 422 unless `skill_path` holds only letters, digits, `.`, `_`, `-` and `/`. The `..` and 500-character checks stay.
- **Audit log** — the `[CREATE]` line writes `repo_url` and `skill_path` with `%r`, so a newline in either value cannot start a forged log line.
- **Stored entries** — no stored skill on dev or prod fails the new checks.

## 0.19.1 — 2026-10-16

### Security: dependency upgrades

- **Next.js 15.5.28 and React 19** — the frontend moves from Next.js 14.2.35 to 15.5.28, which fixes the 23 Next.js advisories that apply to 14.2.35, among them two critical ones for unauthenticated remote code execution (GHSA-2xp9-vwfh-vxw4, GHSA-p293-qw3h-jr36). Pages and route handlers now await `params`, `searchParams`, `cookies()` and `headers()`, as Next.js 15 requires.
- **PostCSS 8.5.30** — an npm override also replaces the copy that Next.js bundles.
- **Other frontend packages** — `vitest`, `undici`, `dompurify`, `js-yaml`, `nanoid`, `browserslist` and the other transitive packages with a patched release are updated in `package-lock.json`.
- **Backend minimum versions** — `PyJWT[crypto]>=2.15.0` and `python-multipart>=0.0.31`, and for tests `anyio>=4.14.2` and `pytest>=9.0.3`, so that no install can pick a version with a known advisory. The 0.19.0 backend image already had patched versions.
- **Still open** — 9 advisories in build-time packages: Tailwind CSS 3's `braces`, `micromatch`, `chokidar`, `postcss-selector-parser` and `postcss-nested`, and `eslint-config-next`'s `fast-glob`, which pins `micromatch` and `braces`. `braces` has no patched release. None of these packages is in the runtime image.

## 0.19.0 — 2026-10-16

### Behaviour change: install no longer adds MCP servers, and refuses agents it cannot vet (#051)

`/agent-knowledge-hub install` now leaves a skill's MCP servers to you and writes only agents whose settings it can check.

- **MCP servers** — the install adds no server. It prints each server's configuration, with warnings, and the command that adds it. Run that command yourself, or ask Claude to add the server by name; Claude then runs the printed command exactly as printed. A server the client cannot show safely, for example one whose command starts with `~`, is listed with its reason and gets no command. The client writes and shows each configuration with `python3`; without it, no server gets a command.
- **Agents** — the install writes an agent only when its frontmatter declares no key outside `name`, `description`, `tools`, `disallowedTools`, `model` and `color`, and its name is not a built-in agent's or another agent's in `~/.claude/agents/`. A refused agent is linked in the closing message instead.
- **Your own files** — an agent or command file you already have is left unchanged. `install` of a skill already installed writes nothing and says to run `update`. `install` writes nothing when `~/.claude/skills/<slug>/` exists without the client's install manifest.
- **Skill folder** — the install never copies a skill's `.claude-plugin/`, `.installed-manifest.json` or `.akh-mcp/`, and leaves out every symbolic link.
- **Servers an earlier client added** — the earlier client added servers at local scope, for the directory the install ran in or the git repository that holds it, so `claude mcp list` run from that directory shows them. `remove` leaves such a server and prints `claude mcp remove --scope local <name>` to run from there. The first `update` does the same, even for a server the new version still lists.
- **Updating an existing install** — a plugin install keeps the earlier client, which still adds servers without asking, until you run `/plugin marketplace update SLAC-Agent-Knowledge-Hub` in a session, or `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` in a shell.

**New docs:** `docs/adr/adr-u43-client-prints-mcp-servers.md`.

### Client sign-in: one script sends the S3DF token (#050)

Every catalog command in `/agent-knowledge-hub`, Search and Install included, now sends your S3DF sign-in. The client makes each catalog request through `skill/hub-request.sh`, a script that ships with it, reads the token, and sends it only to `https://agent-knowledge-hub.slac.stanford.edu`.

- **Token location** — the client reads `.s3df-access-token` from your account's real home directory, the one `getent passwd` reports, and falls back to `~/.s3df-access-token`. It now finds the token in a Cogito session, where `$HOME` is a different directory. A user whose token is already in their own home directory needs to do nothing.
- **Sign-in messages** — when the token file is missing, holds something that is not a token, or holds a token the catalog refuses, the client says which case applies and shows the steps to sign in again, in Cogito and on an S3DF node.
- **Permission prompts** — a session that asks before each Bash command now asks before each catalog request. The client tells you, on its first catalog request in a conversation, which rule stops the prompts.
- **Fixed destination** — the script accepts only the requests the client sends, follows no redirect, and ignores the CA-bundle and key-log variables, so text in a catalog entry cannot steer the token elsewhere through the script.
- **Updating an existing install** — run `/plugin marketplace update SLAC-Agent-Knowledge-Hub` in a session, or `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` in a shell.

**Breaking change:** the client no longer reads `AGENT_KNOWLEDGE_HUB_TOKEN`. A job that set it now gets the "No S3DF sign-in found" message. Write the token to `.s3df-access-token` in the job's home directory instead; that file also works with the previous client, which reads it when the variable is unset.

**New docs:** `docs/adr/adr-u42-client-token-helper.md`.

### Skillsets: curated skill collections (#006, backend)

Curators can group catalog skills into named, ordered skillsets, and every skill reports which skillsets hold it. This release adds the API; the web pages and the `install skillset` command follow.

- **Skillset endpoints** — `GET`/`POST /api/skillsets` (the list takes `page`, `page_size`, and a `created_by` filter and returns the newest first), `GET`/`PATCH`/`DELETE /api/skillsets/{slug}`, `PUT /api/skillsets/{slug}/skills/{skill_slug}` and `DELETE` on the same path to add and remove members, and `PUT /api/skillsets/{slug}/order` to reorder them. A reorder sends the page's `version` and is refused with 409 if the skillset changed since it was loaded.
- **Skill responses** — `GET /api/skills/{slug}` now returns `skillset_count` and a `skillsets` list of slugs and names; each item in `GET /api/skills` carries `skillset_count`.
- **Submit into a skillset** — `POST /api/skills` accepts an optional `skillset_slug` and adds the new skill to that skillset when the submitter owns it. Otherwise the skill is created and the field is ignored.
- **Removal on delete** — deleting a skill removes it from every skillset that holds it.
- **Author removal** — a skill's submitter can remove that skill from any skillset, including one another user curates. Only the skillset's owner or an admin can add it back.
- **Rate limits** — each user can create 20 skillsets and add 50 members per hour, counted across all skillsets.
- **Audit log** — every skillset write logs one `[SKILLSET]` line naming the action, the user, the skillset, and the skill.

## 0.17.0 — 2026-06-03

### Rich revision history: field diffs and label tracking (#013)

Revision history on the skill detail page now shows what actually changed in each edit or refetch, not just a changelog note.

- **Field-level diffs** — `edit`, `refetch`, and `pin` revisions show a collapsible "N fields changed" badge. Clicking expands to show old → new values for each changed field (name, description, version, license, repo_url, forked_from_url, visibility, compatible_platforms, labels, github_stars, last_commit_at).
- **Label tracking** — label adds and removes appear per revision with color-coded chips (green added / red strikethrough removed) and text accessibility labels. Labels are now embedded in the revision snapshot at write time.
- **Create genesis display** — the initial `create` revision shows the starting state (name, description, platforms, labels) as added fields.
- **Empty refetch note** — a refetch that changed nothing now shows "Re-fetched — no changes detected" instead of a silent entry.
- **README updated indicator** — when `readme_html` changed but no semantic fields did, the entry shows "README updated" without noisy HTML content.
- **Repo URL warning** — changes to `repo_url` or `forked_from_url` are visually distinguished with a warning icon.
- **10-revision cap** — the timeline shows the 10 most recent revisions by default with a "Show all N revisions" toggle.
- **Auth gating** — `GET /api/skills/{slug}/revisions` and `/revisions/{n}` now require authentication for internal-visibility skills (returns 401 for unauthenticated viewers).
- **Snapshot sanitization** — `readme_html`, `readme_raw`, `skill_md_raw`, `snapshotted_files` are stripped from revision snapshots both at write time and at response time, reducing snapshot payload by 50–200 KB per revision.
- **Vitest test runner** — added Vitest to the frontend for pure-function unit tests. `npm test` runs all tests. 18 `computeDiff` unit tests cover scalar change, array add/remove, reorder (no diff), null transitions, legacy snapshots, excluded fields.

### Skill provenance tree: fork and supersession lineage (#014)

Skills on the detail page now show their full lineage — where they came from, what forked them, and what superseded them.

- **Provenance tree** — a collapsible sidebar section replaces the old "Fork Provenance" and "Forks in Catalog" cards. Collapsed summary shows "Forked from X · N forks in catalog". Expanding shows upstream chain, this skill, forks in catalog (up to 5), and supersession chain.
- **Upstream chain** — follows `forked_from_url` links up to 3 hops. Catalog matches show slug, name, stars, rating, last commit, and submitter. Non-catalog upstream shows a GitHub icon + repo path with best-effort metadata (stars, last commit) fetched via the existing GitHub fetcher.
- **Fork tree (2 levels)** — level-1 forks sorted by stars, up to 5 shown with "and N more →" overflow link. Level-2 forks fetched in a single batched query. `forks_truncated` flag and `total_fork_count` surfaced in response.
- **Supersession chain** — follows `superseded_by_slug` links as a directed path (lineage context only; the existing superseded banner handles the "go update" CTA at the top of the page).
- **Security** — internal-visibility skills in the tree are redacted to `{name: "[internal skill]"}` for unauthenticated viewers. Rate-limited to 30 requests/minute.
- **Cycle detection** — slug-based visited sets for upstream and supersession traversal prevent infinite loops on circular references.
- **5-minute TTL cache** — provenance trees are cached; unfiltered tree is cached and per-viewer visibility filtering is applied at response time.
- **CSS indented tree** — `border-left` + `padding-left` indentation with no ASCII characters; node metadata stacks on mobile.

## 0.16.0 — 2026-06-03

### Catalog scale: search quality, pagination, and performance (#015)

The catalog list endpoint now scales to thousands of skills with keyset pagination, in-process count caching, compound sort indexes, and a name-boost search heuristic.

- **Keyset pagination** — `GET /api/skills` accepts an optional opaque `cursor` param for `sort=newest`. When provided, the backend uses a compound `$gt` keyset query on `(submitted_at, _id)` instead of `skip()`, eliminating O(N) scans at high page numbers. The `?page=N` URL contract is fully preserved; cursors are only used when the frontend explicitly sends one (pages 11+ on `newest` sort).
- **Count caching** — unfiltered catalog requests now use `estimatedDocumentCount()` (O(1)). Filtered requests cache counts per filter fingerprint for 30 seconds in-process (TTLCache, 1,000-entry LRU bound). Any skill write (create, deactivate, reactivate) flushes the cache immediately.
- **Compound sort indexes** — explicit compound MongoDB indexes for all four sort fields (`newest`, `most_stars`, `highest_rated`, `most_rated`) make offset-based pages 1–10 fast via index-only scans.
- **Name boost search** — when a query exactly matches a skill's name or slug, that skill is surfaced first regardless of page position. The search input now shows a hint: "exact name matches rank first."
- **Atlas Search feature flag** — `MONGODB_ATLAS_SEARCH=1` enables a MongoDB Atlas Search pipeline (permanently inactive on the current self-hosted Percona PSMDB cluster; reserved for a future Atlas migration). Falls back to `$text` on `OperationFailure`.
- **Page-number input** — the pagination bar gains a direct page-number input (`<input type="number">`) alongside Prev/Next buttons. Entering an out-of-range value shows a validation error and resets to the current page. The input is hidden on viewports narrower than `sm` (640px); Prev/Next remain visible at all breakpoints. Navigating to an empty page (stale bookmark) redirects to page 1 automatically.
- **API response additions** — `GET /api/skills` now returns `pages`, `next_cursor`, and `prev_cursor` fields alongside existing `total`/`page`/`page_size`.

### Moderation: user flags and admin deactivation (#012)

The community can now flag broken or stale skills, and admins have a full moderation loop to act on those reports.

- **Flag a skill** — authenticated users can flag any active skill with a reason (broken, stale, superseded, inappropriate, other) and an optional note. Flagging is one flag per user per skill; re-flagging updates your existing flag rather than creating a duplicate. The flag count on the skill card and detail page now reflects real data.
- **"Flagged by you" indicator** — the flag button shows a filled orange state when you have an active flag on a skill, so you can see your own reports at a glance.
- **Retract a flag** — changed your mind? Click the "Flagged — click to retract" button and confirm to remove your flag.
- **Admin flag queue** — `/admin/flags` shows all active flagged skills sorted by flag count, with each flag's reason, note, reporter, and timestamp. Inline deactivate action on every row.
- **Admin deactivate/reactivate** — admins now have a Deactivate button directly on every skill detail page. Deactivating requires a reason (free text); the button is disabled until a reason is entered. Deactivation auto-resolves all active flags for the skill and resets the flag count to zero. Reactivation is one click.
- **Tombstone page** — deactivated skills now show the reason and a link to the replacement skill (when `superseded_by_slug` is set) instead of returning 404.
- **Rate limit** — flag creation is rate-limited to 10 per user per hour, keyed on user ID (not IP) so the Next.js proxy hop doesn't pool everyone into the same bucket.
- **`GET /api/skills/{slug}`** — response now includes `my_flag` for authenticated users showing their current flag reason and status.
- **New endpoints:** `POST /api/skills/{slug}/flag`, `DELETE /api/skills/{slug}/flag`, `GET /api/admin/flags`, `POST /api/admin/skills/{slug}/deactivate`, `POST /api/admin/skills/{slug}/reactivate`.

### Skill file manifest: browsable file listing + inline viewer (#028)

Skills and plugins now expose a full file listing, visible in the submission preview and on the skill detail page.

- **File manifest stored at scan time**: `GitHubScanner.scan()` captures every file and directory in the skill path from the GitHub Contents API as a `FileManifestEntry(path, size_bytes, is_text, is_dir)`. Manifest is capped at 200 entries; `manifest_truncated` flag set when the directory has more.
- **Scan preview**: the submit form shows a collapsible "Files (N)" section listing all discovered files with size badges. Collapsed by default; directory entries shown greyed-out.
- **Files tab on skill detail page**: new "Files" tab always shown. Flat file list with size badges; clicking a text file fetches and renders it inline. Binary files show a "View on GitHub" link. Empty state shown for skills that pre-date file indexing.
- **`GET /api/skills/{slug}/files/{path:path}`**: new endpoint serving file content with manifest-based path allowlist (traversal attacks return 404 by design), 60/min rate limit, auth gating for internal skills, 5-min TTL cache for GitHub content.
- **Local skills**: `LocalScanner` populates the manifest from `snapshotted_files`. The file content endpoint serves local files directly without a GitHub round-trip.
- **`refetch()` updates the manifest**: re-scanning a skill via the admin "Rescan" button refreshes `file_manifest` and `manifest_truncated`.

### User activity profile: skills by user (#011)

Each user now has a public profile page at `/users/<user_id>` showing their catalog contributions.

- **Submitted tab** — skills the user has submitted to the catalog, paginated.
- **Edited tab** — skills the user has edited or re-fetched at least once, deduped by skill.
- **Installed tab** — private to the profile owner and admins; shows skills installed via the AKH skill with `installed_at` date, an "update available" badge when upstream has changed, and a Re-install link. Deleted skills shown with slug in monospace.
- **Contributor links** — contributor names on skill detail pages and actor IDs in revision timelines are now clickable links to the relevant profile page. The username in the nav header links to your own profile.
- **`/users/me`** — server-side redirect to `/users/<your_user_id>` for authenticated users.
- **Install event tracking** — the AKH skill fires a fire-and-forget `POST /api/me/installs/<slug>` after each successful install. Failures log a warning only; they never abort the install.
- **New backend endpoints:** `GET /api/users/{user_id}`, `/skills`, `/edits`, `/installs`; `GET /api/me/installs`; `POST /api/me/installs/{slug}` (rate-limited 60/hour per user, per-user key not per-IP). Install events are upserted — re-installing a skill updates `installed_at` rather than adding a duplicate row.
- **`GET /api/skills?submitted_by=`** — new filter param for programmatic use.
- **ADRs:** `adr-u21-profile-url-scheme.md`, `adr-u22-install-event-tracking.md`, `adr-u23-install-tab-visibility.md`.

### Installer: git clone replaces GitHub Contents API (#022)

Plugin installation now uses `git clone` instead of per-file GitHub Contents API calls.

- **Single clone per install** — `git clone --depth 1 <repo_url> /tmp/akh-install-<slug>/` replaces the loop of individual file-fetch API calls. No API rate limit exposure; arbitrary directory depth; matches how Claude Code's native `/plugin install` works.
- **SHA-pinned installs** — when a skill has a pinned commit SHA (from #017), a full clone + `git checkout <sha>` is used instead of `--depth 1`.
- **Auth** — public repos work with no credentials; private repos use the user's existing git credential helpers (`gh auth login` or SSH keys). Clone auth failures print an actionable error pointing to `gh auth login`.
- **Fallback** — if `git` is not found on PATH, the installer falls back to the Contents API with a warning.
- **Cleanup** — temp clone directory is deleted on both success and failure via a shell trap.

### Installer skill extension: directory skills, multi-platform, Codex (#020)

The `/agent-knowledge-hub` installer now handles the full range of real-world plugin layouts.

- **Directory-form install** — `"skills": "./skills"` in `plugin.json` is now handled correctly: all files in the directory are fetched and written preserving subdirectory structure. Applies equally to `"agents"` and `"commands"` directory declarations.
- **Installed-files manifest** — `~/.claude/skills/<slug>/.installed-manifest.json` written after every install, listing paths of all commands and agents installed into shared directories. `remove` and `update` use it to clean up correctly; falls back to array-form `plugin.json` for old installs.
- **Platform check** — `compatible_platforms` in `plugin.json` is read at install time. Skills that don't list `claude-code` get a warning + y/n prompt; skills that also support other platforms show an informational note.
- **Codex install path** — when `compatible_platforms` includes `"codex"`, the installer also copies files to `~/.akh/plugins/<slug>/`, registers an AKH marketplace entry in `~/.codex/config.toml`, and optionally injects skill instructions into `~/.codex/AGENTS.md`. Degrades gracefully if `~/.codex/` is absent.
- **`validate` update** — accepts both array-form and directory-form component declarations; validates `author` and `compatible_platforms` fields; shows agent count and platform list in summary.
- **`create` scaffold** — extended question flow for agents, scripts, MCP servers, and target platforms; generates matching directory structure and full `plugin.json` with directory-form `"skills": "./skills"`.
- **`list`** — shows platform and component summary from locally-cached `plugin.json`.

### AGENTS.md scanner support (#024)

Skills authored for [OpenAI Codex CLI](https://github.com/openai/codex) using `AGENTS.md` as their instruction file are now recognised and indexed by the AKH scanner.

- **Discovery**: `AGENTS.md` added as a fourth skill directory marker — repos with only `AGENTS.md` (no `SKILL.md` or `CLAUDE.md`) now appear in discovery results.
- **Metadata extraction**: `name`, `description`, `keywords`, and `version` are extracted from `AGENTS.md` YAML frontmatter, identical to how `CLAUDE.md` is handled. Priority order: `SKILL.md` > `skill.md` > `CLAUDE.md` > `AGENTS.md`.
- **Platform inference**: When `AGENTS.md` is present and no explicit `platforms:` field is declared, `"codex"` is inferred. This fires independently alongside `"claude-code"` inference from `CLAUDE.md`/`SKILL.md`.
- **`skill_md_filename`**: Set to `"AGENTS.md"` when it is the only instruction file found; shown on the skill detail page.
- **Frontend**: `"opencode"` added to platform badge colours, platform picker, and platform suggestions (for skills that declare it explicitly via frontmatter).
- **Submit form**: "No skills found" hint now mentions `AGENTS.md` alongside `SKILL.md` and `CLAUDE.md`.

### /agent-knowledge-hub skill (#007)

Discover, install, rate, and submit catalog skills entirely from within your Claude Code session.

- **`/agent-knowledge-hub <query>`** — describe what you need in plain English; Claude fetches
  the catalog and returns ranked matches with explanations. Pick one to install immediately.
- **`install <slug>`** — downloads skill files from GitHub into `~/.claude/skills/<slug>/`
  using the GitHub Contents API. A mandatory path traversal guard rejects any skill whose
  `skill_path` would write files outside the skills directory.
- **`list` / `update` / `remove`** — manage installed skills without leaving your session.
- **`rate <slug> <1-5>`** — submit a rating using your SLAC token from `~/.s3df-access-token`.
  Requires `s3df login` (one-time). Clear error messages if the token is missing or expired.
- **`create`** — scaffold a new `SKILL.md` template locally; ready to push to GitHub and submit.
- **`submit`** — prints the web submission URL (direct API POST planned for v2).

**Bootstrap (one-time):**
```
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json
/plugin install agent-knowledge-hub
```

**New backend endpoints:** `GET /api/skills/summary` (slim catalog listing for LLM context,
no `readme_html`), `GET /api/marketplace.json` (dynamic Claude Code marketplace manifest,
5-minute cache + ETag).

**New guides:** `/guides/agent-knowledge-hub`, `/guides/create-a-skill`, `/guides/troubleshooting`.

### Bearer JWT auth for CLI tools (#016)

CLI tools (including the `/agent-knowledge-hub` skill) can now authenticate write operations
using a SLAC-issued JWT from `~/.s3df-access-token`.

- **New auth path (Path 3):** `Authorization: Bearer <token>` — the backend validates RS256 JWTs
  issued by `https://dex.slac.stanford.edu`. All write endpoints (`rate`, `submit`, `edit`,
  admin actions) accept Bearer JWT with no per-endpoint changes.
- **Path 1 removed:** VouchProxy header trust (`X-Vouch-Idp-Claims-Name`) has been removed from
  `get_current_user`. All browser writes already use the Next.js proxy (Path 2). Removal
  eliminates the Vouch header spoofing attack surface on the now-ungated API ingress.
  See ADR-P10.
- **Ingress split:** The single Ingress object is replaced by two: `ingress-frontend.yaml`
  (Vouch-gated, routes `/` to Next.js) and `ingress-api.yaml` (no Vouch, routes `/api` and
  `/health` to the backend). Browser SSO is unaffected. See ADR-P08.
- **Static PEM config:** Public key configured via `JWT_PUBLIC_KEY` env var / k8s secret.
  No per-request network call. See ADR-P09 and `docs/runbooks/jwt-public-key-rotation.md`.
- **Actionable 401 messages:** Expired tokens return `"Token expired. Re-run 's3df login' to
  refresh your session."` Misconfigured PEM returns HTTP 500 (server error, not client error).
- **Security:** `algorithms=["RS256"]` pinned; `alg: HS256` and `alg: none` rejected;
  `aud="s3df"` always validated; algorithm injection via config rejected at startup.

**New config keys:** `JWT_JWKS_URI` (default `https://dex-dev.slac.stanford.edu/keys`),
`JWT_ALGORITHM` (default `RS256`), `JWT_ISSUER` (default `https://dex.slac.stanford.edu`),
`JWT_AUDIENCE` (default `s3df`).

**New docs:** `docs/runbooks/jwt-public-key-rotation.md`, `docs/adr/adr-p08-split-ingress.md`,
`docs/adr/adr-p09-jwt-static-pem.md`, `docs/adr/adr-p10-remove-vouch-path1.md`.

### Skill file cache: SKILL.md + README storage and tabbed UI (#018)

Skill files are now stored in the database at scan time and surfaced in a tabbed view on the detail page.

- **SKILL.md stored at submission** — `skill_md_raw` and `skill_md_filename` saved to the `Skill` document on first fetch; re-fetched on every manual refetch.
- **Tabbed detail view** — skill detail page gains a "SKILL.md" tab (shown first when content is present) and a "README" tab. Tabs only appear when content exists; the view falls back gracefully to a single tab.
- **Auth gate** — skill file content is only visible to signed-in users; guests see a prompt to sign in.
- **Backfill script** — `backend/scripts/002_backfill_skill_file_content.py` populates `skill_md_raw` for all existing catalog entries. Idempotent; safe to re-run.

### plugin.json scan pipeline: rich component metadata and structural auto-labels (#019)

The scanner now parses `plugin.json` (with `.claude-plugin/plugin.json` fallback) to extract rich component metadata and automatically apply structural labels.

- **Component metadata extracted** — agent count, agent names, MCP server presence, scripts presence, author, and keywords parsed from `plugin.json` and stored on the `Skill` document.
- **`.claude-plugin/plugin.json` fallback** — if `plugin.json` is not found in the skill directory, the scanner checks `.claude-plugin/plugin.json` automatically.
- **Structural auto-labels** — `mcp`, `multi-agent`, and `has-scripts` labels applied automatically at submission based on parsed content; no manual tagging required.
- **Plugin Info sidebar** — skill detail page shows a "Plugin Info" section when any component metadata is present: MCP server badge, agent count badge, scripts badge, and plugin author.
- **Skill card badges** — MCP and agent count badges appear in the right-side badge row on skill list cards.

## v0.3.0 — 2026-04-22

### Skill ratings (#005)

Authenticated users can now rate any skill 1–5 stars from the detail page.

- **Interactive star picker** — authenticated users see a clickable 5-star picker on the skill detail page. Stars highlight on hover; keyboard navigation (Tab, Enter/Space) and `aria-label` attributes are included for accessibility.
- **Optimistic update** — the picker and average update instantly on click; reverts cleanly if the API call fails with an inline error message.
- **Upsert semantics** — re-rating a skill updates your previous vote rather than creating a duplicate. One rating per user per skill, enforced via a unique MongoDB index.
- **Your prior rating pre-filled** — when you revisit a skill you've already rated, your previous star choice is shown in the picker after a client-side fetch.
- **Read-only view for guests** — unauthenticated visitors see the current average and count with a "Sign in to rate." prompt.

## v0.2.0 — 2026-04-22

### Label UX: community tagging, filter, and admin tools (#003)

You can now tag any skill with free-form labels — and use those labels to find skills by topic.

- **Add labels to skills** — authenticated users can apply community labels (e.g. `python`, `data-viz`) to any skill from the detail page. A compact typeahead combobox suggests existing labels as you type to avoid duplicates.
- **Remove your own labels** — made a mistake? Remove any label you personally applied with one click.
- **Label chips on cards** — up to 5 label chips appear on each skill card in the list view; click any chip to filter to skills sharing that label.
- **Filter by label** — multi-select label filter in the skill list controls bar; AND semantics (skill must carry all selected labels); reflected in the URL so filtered views are shareable.
- **Browse all labels** — new `/labels` page lists every label with usage counts; click through to the filtered skill list.
- **Admin label management** — admins can rename, merge, and delete labels globally at `/admin/labels`. Rename updates all skills atomically; merge consolidates duplicates; delete removes the label from every skill. All operations wrapped in MongoDB transactions.

### Auth header hardening (#008)

- Internal API secret (`INTERNAL_API_SECRET`) required for Next.js → backend trust; `X-Forwarded-User` is only accepted after the secret check passes.
- Three new ADRs documenting the ingress header stripping decision, shared-secret choice over mTLS, and removal of bare forwarded-user fallback.
- k8s network policy added to all overlays restricting backend ingress to frontend pods only.

## v0.1.0 — initial release

- Skill catalog: browse, search, submit, edit, delete
- GitHub metadata auto-fetch at submission with manual re-fetch
- Revision history timeline on skill detail pages
- Private/internal GitHub repo support via GitHub App
- SLAC VouchProxy authentication
