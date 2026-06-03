# Changelog

## Unreleased

### Skill file manifest: browsable file listing + inline viewer (#028)

Skills and plugins now expose a full file listing, visible in the submission preview and on the skill detail page.

- **File manifest stored at scan time**: `GitHubScanner.scan()` captures every file and directory in the skill path from the GitHub Contents API as a `FileManifestEntry(path, size_bytes, is_text, is_dir)`. Manifest is capped at 200 entries; `manifest_truncated` flag set when the directory has more.
- **Scan preview**: the submit form shows a collapsible "Files (N)" section listing all discovered files with size badges. Collapsed by default; directory entries shown greyed-out.
- **Files tab on skill detail page**: new "Files" tab always shown. Flat file list with size badges; clicking a text file fetches and renders it inline. Binary files show a "View on GitHub" link. Empty state shown for skills that pre-date file indexing.
- **`GET /api/skills/{slug}/files/{path:path}`**: new endpoint serving file content with manifest-based path allowlist (traversal attacks return 404 by design), 60/min rate limit, auth gating for internal skills, 5-min TTL cache for GitHub content.
- **Local skills**: `LocalScanner` populates the manifest from `snapshotted_files`. The file content endpoint serves local files directly without a GitHub round-trip.
- **`refetch()` updates the manifest**: re-scanning a skill via the admin "Rescan" button refreshes `file_manifest` and `manifest_truncated`.

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
