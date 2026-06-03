# Skill File Discovery Algorithm

**Module:** `backend/app/services/github.py`  
**Classes:** `GitHubScanner`, `MetadataExtractor`  
**Updated:** 2026-05-06 (auth gate section + server-side content auth fix)

---

## Overview

When a user submits a GitHub URL, the backend runs a two-phase pipeline to locate
and retrieve the skill's documentation files (`SKILL.md`, `README.md`) and metadata
(`plugin.json`).

```
User submits URL
      │
      ▼
  Phase 1: discover()          — identifies candidate skill directories in the repo
      │                          using the Git Tree API (recursive blob scan)
      │  yields List[GitHubRef]
      ▼
  Phase 2: scan()              — fetches recognised files from each directory
      │                          using the GitHub Contents API (API-based, no raw.githubusercontent.com)
      │  yields RawScanResult
      ▼
  MetadataExtractor.extract()  — pure transformation: files → SkillScanSnapshot
      │
      ▼
  skill_repository.create()    — stores readme_raw, skill_md_raw, plugin_meta in MongoDB
```

The same pipeline runs twice: once during the **submit form preview** (via
`POST /api/github-scan`) and once during **skill creation** (`skill_repository.create()`),
which issues a fresh scan to ensure the stored content reflects what is saved.

---

## Phase 1 — Directory Discovery (`GitHubScanner.discover`)

**Code:** `github.py:527–601`  
**API used:** `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1`

### What the Git Tree API returns

The recursive tree API returns every object in the repo as a flat list:

```json
[
  { "path": "plugins/my-skill/plugin.json",           "type": "blob", "mode": "100644" },
  { "path": "plugins/my-skill/.claude-plugin/plugin.json", "type": "blob", "mode": "120000" },
  { "path": "plugins/my-skill/skills/my-skill/SKILL.md",   "type": "blob", "mode": "100644" },
  { "path": "plugins/my-skill/README.md",             "type": "blob", "mode": "100644" },
  { "path": "src/util.py",                             "type": "blob", "mode": "100644" },
  { "path": "plugins/my-skill/skills",                 "type": "tree" }
]
```

**Important:** Symlinks are `type: "blob"` with `mode: "120000"`. They are indistinguishable
from regular files at this level — the tree API does not separate them.

### Candidate-detection pass

The scanner iterates every `type == "blob"` item and checks if its basename matches
`("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md", "plugin.json")`.

```python
# github.py discover()
for item in tree_items:
    if item.get("type") == "blob":
        ipath  = item.get("path", "")
        fname  = ipath.rsplit("/", 1)[-1] if "/" in ipath else ipath
        if fname in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md", "plugin.json"):
            dirpath = ipath.rsplit("/", 1)[0] if "/" in ipath else "/"
            if fname == "plugin.json" and _plugin_subdir_re.search(dirpath):
                dirpath = dirpath.rsplit("/", 1)[0] if "/" in dirpath else "/"
            ...
```

Each hit is classified into one of two sets:

| Set | Populated when |
|-----|---------------|
| `plugin_json_dirs` | `fname == "plugin.json"` |
| `skill_md_dirs`    | `fname` in `("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md")` |

### Plugin subdirectory stripping

Some plugins place `plugin.json` inside a hidden subdirectory to support multiple
plugin managers (e.g., `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`).
The regex `_plugin_subdir_re = re.compile(r"(^|\/)\.[\w-]+-plugin$")` matches any
directory whose last segment looks like `.<name>-plugin`.

When a `plugin.json` is found inside such a directory, `dirpath` is promoted one
level up to the actual plugin root:

```
plugins/my-skill/.claude-plugin/plugin.json
  → dirpath before strip: "plugins/my-skill/.claude-plugin"
  → matches _plugin_subdir_re
  → dirpath after strip:  "plugins/my-skill"         ← plugin root
```

This deduplicates `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and
the root `plugin.json` into the same directory entry.

### Pruning SKILL.md entries nested inside plugin.json dirs

A plugin often stores its SKILL.md at `skills/<slug>/SKILL.md`, which is a
descendant of the plugin root that already has `plugin.json`. Without pruning, this
would generate a spurious second scan entry for the nested path.

```python
# github.py:578–584
pruned_skill_md = {
    d for d in skill_md_dirs
    if not any(
        d != p and d.startswith(p.rstrip("/") + "/")
        for p in plugin_json_dirs
    )
}
```

Any `skill_md_dirs` entry that is a child of a `plugin_json_dirs` entry is dropped.
The union of surviving entries is the final scan list:

```python
skill_file_dirs = plugin_json_dirs | pruned_skill_md
```

### Concurrency and cap

Up to 20 directories are scanned in parallel via `asyncio.gather`. If more than 20
are found, the result is marked `capped = True` and only the first 20 are scanned.

---

## Phase 2 — File Fetching (`GitHubScanner.scan`)

**Code:** `github.py:355–484`  
**API used:** `GET /repos/{owner}/{repo}/contents/{path}` (directory listing + per-file fetch)

### Step 1 — Directory listing

```python
contents_url = f"/repos/{owner}/{repo}/contents/{dir_path}?ref={branch}"
contents_data, contents_status = await self._api_get(contents_url, token, owner=owner)
```

The GitHub Contents API returns a flat JSON array of the **direct children** of the
directory — one level deep, not recursive. Each entry has `type` (`"file"`, `"dir"`,
`"symlink"`, `"submodule"`), `name`, `path`, and `download_url`.

### Step 2 — Recognised file filter

```python
# github.py (module constant)
_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md", "README.md",
                "package.json", "pyproject.toml", "plugin.json"}

# github.py:396–398
recognised = [f for f in contents_data
              if f.get("type") == "file" and f.get("name") in _SKILL_FILES]
```

Only items with `type == "file"` (not `"dir"`, `"symlink"`, or `"submodule"`) are
retained. **Symlinks in the directory listing appear as `type: "symlink"` and are
therefore skipped.**

### Step 3 — Parallel file fetch (API-based)

```python
# github.py:400–413
file_tasks = {
    item["name"]: asyncio.create_task(self._fetch_text(
        f"/repos/{owner}/{repo}/contents/{item['path']}?ref={branch}",
        token,
    ))
    for item in recognised
}
```

Each recognised file is fetched via `_fetch_text`, which calls `_api_get` (hitting
`api.github.com`) and base64-decodes the `content` field from the JSON response.

**Why `_fetch_text` and not `download_url`:**  
The `download_url` field points to `raw.githubusercontent.com`. For internal/private
GitHub Enterprise Cloud repos, raw downloads require a separate authentication step
that differs from the standard GitHub API bearer token. Using the Contents API
endpoint directly is reliable for all visibility levels (public, private, internal).

For symlinks, the Contents API returns `content: null` — `_fetch_text` returns
`None`, correctly skipping them without corrupting the `files` dict.

### Step 4 — `.claude-plugin/plugin.json` fallback

```python
# github.py:415–423
if "plugin.json" not in files:
    plugin_dir = f"{path}/.claude-plugin"
    alt_url = f"/repos/{owner}/{repo}/contents/{plugin_dir}/plugin.json?ref={branch}"
    alt_content = await self._fetch_text(alt_url, token)
    if alt_content:
        files["plugin.json"] = alt_content
```

If the root directory has no `plugin.json` directly, the scanner checks
`.claude-plugin/plugin.json` as a fallback. This handles repos that place metadata
inside a hidden platform-specific subdirectory without a root-level `plugin.json`.

If `.claude-plugin/plugin.json` is a **symlink** (common when a repo uses the same
`plugin.json` for multiple managers), `_fetch_text` returns `None` because the
Contents API response for a symlink has `content: null`. The fallback produces
nothing, and the scanner proceeds without `plugin.json`.

### Step 5 — SKILL.md subdirectory lookup

```python
# github.py:425–474
if "plugin.json" in files and not any(k in files for k in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md")):
    plugin_data = json.loads(files["plugin.json"])
    skills_val = plugin_data.get("skills")
    if isinstance(skills_val, str):
        # e.g. "skills": "./skills"
        skills_abs = f"{path}/{skills_rel}"
        skills_listing = await self._api_get(f".../contents/{skills_abs}", token)
        # Look for SKILL.md/AGENTS.md directly in skills_abs/
        direct = next((f for f in skills_listing if f["name"] in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md")), None)
        if direct:
            files[direct["name"]] = await self._fetch_text(direct["path"], token)
        else:
            # One level deeper: skills/<slug>/SKILL.md or AGENTS.md
            for subdir in subdirs[:5]:
                sub_listing = await self._api_get(f".../contents/{subdir['path']}", token)
                skill_file = next((f for f in sub_listing if f["name"] in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md")), None)
                if skill_file:
                    files[skill_file["name"]] = await self._fetch_text(skill_file["path"], token)
                    break
```

This step only runs when:
1. `plugin.json` is present (either from the directory listing or the fallback), AND
2. No SKILL.md / skill.md / CLAUDE.md / AGENTS.md was found in the root directory listing.

It handles the pattern where `plugin.json` declares skills as a directory path
string (e.g., `"skills": "./skills"`) rather than a list of file paths. The scanner:

1. Lists the `skills/` directory.
2. If a SKILL.md is directly inside, fetches it.
3. Otherwise, looks one level deeper into each subdirectory (up to 5), picking the
   first subdirectory that contains a SKILL.md.

### Step 6 — Repo-root README fallback

```python
# github.py:467–473
root_readme: Optional[str] = None
if path:
    root_readme = await self._fetch_text(
        f"/repos/{owner}/{repo}/contents/README.md?ref={branch}", token)
```

When the skill path is a subdirectory (not the repo root), the scanner also fetches
the repo-root `README.md`. This is stored as `RawScanResult.root_readme` and used
as a fallback when the skill directory has no `README.md` of its own.

---

## Phase 3 — Metadata Extraction (`MetadataExtractor.extract`)

**Code:** `github.py:614–665`

After `scan()` returns a `RawScanResult` with `files: Dict[str, str]`, the
extractor derives structured fields from the file contents. Priority order for
each field:

| Field         | Priority order |
|---------------|----------------|
| `name`        | SKILL.md → skill.md → CLAUDE.md → AGENTS.md frontmatter → plugin.json `name` → package.json → pyproject.toml → last path segment → repo name |
| `description` | SKILL.md → skill.md → CLAUDE.md → AGENTS.md frontmatter → plugin.json `description` → README.md first paragraph → repo description |
| `version`     | SKILL.md → skill.md → CLAUDE.md → AGENTS.md frontmatter → plugin.json `version` → package.json → pyproject.toml |
| `keywords`    | plugin.json `keywords` → all instruction files (additive, deduped): SKILL.md → skill.md → CLAUDE.md → AGENTS.md |
| `platforms`   | plugin.json `platforms` → instruction file frontmatter `platforms` (SKILL.md → … → AGENTS.md) → inferred: CLAUDE.md/SKILL.md/skill.md → `"claude-code"`, AGENTS.md → `"codex"` |
| `readme_html` | README.md from skill dir → `root_readme` (repo-root README) |

**`readme_html` naming note:** despite the field name, this stores raw Markdown
text from `README.md`, not rendered HTML. The frontend renders it client-side.

---

## Storage in the Database

`skill_repository.create()` (`skill.py:115–233`) calls `scan()` independently of the
frontend scan and stores the results in the `Skill` document:

| DB field            | Source |
|---------------------|--------|
| `readme_raw`        | `scan.files.get("README.md") or scan.root_readme` |
| `readme_html`       | `github_data.readme_html` (GitHub-rendered HTML of repo-root README, from `GitHubFetcher`) |
| `skill_md_raw`      | First of `scan.files["SKILL.md"]`, `scan.files["skill.md"]`, `scan.files["CLAUDE.md"]`, `scan.files["AGENTS.md"]` |
| `skill_md_filename` | Whichever of the four was found (`"SKILL.md"`, `"skill.md"`, `"CLAUDE.md"`, or `"AGENTS.md"`) |
| `plugin_author`     | `plugin_meta.get("plugin_author")` |
| `agent_count`       | `plugin_meta.get("agent_count", 0)` |
| `has_mcp_server`    | `plugin_meta.get("has_mcp_server", False)` |
| `has_scripts`       | `plugin_meta.get("has_scripts", False)` |

For an existing skill, `skill_repository.refetch()` (`skill.py:255–300`) re-runs
`scan()` and updates the same fields. Trigger this via the **Rescan from GitHub**
button on the skill edit page after deploying backend changes.

---

## File Layout Compatibility

### Layouts that work

```
repo/
├── SKILL.md                    ← flat layout, SKILL.md at root
├── README.md
└── plugin.json
```

```
repo/
├── plugin.json                 ← plugin.json at root with SKILL.md alongside
├── SKILL.md
└── README.md
```

```
repo/
├── plugin.json
├── README.md
└── .claude-plugin/
    └── plugin.json             ← symlink → ../plugin.json (symlink, ignored safely)
```

```
repo/
└── plugins/
    └── my-skill/
        ├── plugin.json         ← plugin root at a subpath; works when URL includes /tree/main/plugins/my-skill
        ├── README.md
        └── skills/
            └── my-skill/
                └── SKILL.md    ← found via Step 5 (string-form "skills" in plugin.json)
```

```
repo/
└── plugins/
    └── my-skill/
        ├── plugin.json
        ├── README.md
        ├── .claude-plugin/
        │   └── plugin.json     ← symlink → ../plugin.json (deduped in discover, ignored safely in scan)
        └── .codex-plugin/
            └── plugin.json     ← real file; also deduped to same root by _plugin_subdir_re
```

```
repo/
└── my-skill/
    ├── CLAUDE.md               ← CLAUDE.md accepted as equivalent to SKILL.md
    └── README.md
```

```
repo/                           ← entire repo is one skill (URL = repo root)
├── SKILL.md
└── README.md
```

### Layouts that do NOT work

```
repo/
└── plugins/
    └── my-skill/
        ├── plugin.json
        └── skills/
            └── my-skill/
                └── subdir/
                    └── SKILL.md    ← more than 2 levels below plugin.json; Step 5 looks 1 level into skills/
```
Fix: Move SKILL.md up to `skills/my-skill/SKILL.md` or `skills/SKILL.md`.

---

```
repo/
└── my-skill/
    ├── plugin.json
    └── skill_instructions.md   ← non-standard filename; only SKILL.md / skill.md / CLAUDE.md / AGENTS.md recognised
```
Fix: Rename to `SKILL.md`.

---

```
repo/
└── my-skill/
    ├── plugin.json
    └── docs/
        └── SKILL.md            ← arbitrary subdirectory name; Step 5 looks inside the path declared
                                   by plugin.json "skills": "..." only, not arbitrary "docs/" dirs
```
Fix: Declare `"skills": "./docs"` in `plugin.json`, or move SKILL.md alongside `plugin.json`.

---

```
repo/
└── my-skill/
    └── SKILL.md                ← SKILL.md with NO plugin.json and NO README.md
```
Works for discover (SKILL.md is found) and scan (SKILL.md is fetched). However,
`readme_raw` will be None and the README tab will fall back to the repo-root README
if one exists. No metadata from `plugin.json`.

---

```
repo/                           ← repo submitted at root, but >20 skill subdirectories found
├── plugin-a/
│   └── SKILL.md
...
└── plugin-u/
    └── SKILL.md                ← 21st skill; beyond the 20-dir cap, never scanned
```
Fix: Submit each plugin subdirectory URL individually
(`https://github.com/org/repo/tree/main/plugin-a`).

---

```
repo/
└── my-skill/
    ├── plugin.json             ← "skills": ["./skills/skill.md"]  ← array of file paths
    └── skills/
        └── skill.md            ← Step 5 only handles string-form "skills" (a dir path);
                                   array-form "skills" lists are NOT traversed for SKILL.md
```
Fix: Use `"skills": "./skills"` (directory path) in `plugin.json`, or place SKILL.md
at the same level as `plugin.json`.

---

```
repo/
└── my-skill/
    ├── plugin.json
    └── SKILL.md                ← symlink → ../../shared/SKILL.md
```
Discover: the symlink appears as `type: "blob"` with `mode: "120000"` in the Git
Tree API and will be picked up by the candidate-detection pass. However, in the
scan step, the Contents API returns this entry as `type: "symlink"` (not `"file"`),
so it is filtered out by the `type == "file"` check. `skill_md_raw` will be None.

Fix: Replace the symlink with the actual file, or copy the content inline.

---

## Authentication and Rate Limits

`_best_token` (`github.py:334–340`) selects the GitHub credential for all API calls:

- If the repo owner is listed in `settings.github_private_orgs`: the GitHub App
  installation token for that org is used. This is required for internal/SLAC-only repos.
- Otherwise: the PAT from `settings.github_token` is used (may be `None` for public repos).

All file fetches in `scan()` go through `_api_get` → `api.github.com`. This means
they count against the GitHub API rate limit (5 000 requests/hour for authenticated
requests). A single full scan of a plugin with the subdirectory SKILL.md lookup
makes approximately 4–6 API calls.

The `_scan_cache` (`TTLCache(maxsize=256, ttl=60)`) caches `scan()` and `discover()`
results for 60 seconds per cache key. The cache is keyed only when the caller passes
a `cache_key` argument; the `create()` path in `skill_repository` does not pass one
and always performs a fresh scan.

---

## Content Visibility for Internal (SLAC-Only) Skills

Skills fetched from repos in `settings.github_private_orgs` (e.g. `SLAC-National-Accelerator-Laboratory`)
are stored with `visibility = "internal"`. The frontend gates their tab content behind an
authentication check so only SLAC-authenticated users can read the SKILL.md / README body.

### Two independent gates

Content for internal skills is controlled by two independent mechanisms:

1. **Backend `omit_content`** — the API response strips `readme_raw`, `skill_md_raw`, `readme_html` when the caller is not authenticated
2. **Frontend `contentGated`** — the component hides content when `isAuthenticated` is false and no content arrived from the API

Both must be unblocked for content to be visible.

#### Backend gate: `omit_content`

**`backend/app/routers/skills.py:171`**

```python
omit_content = skill.visibility == VisibilityEnum.internal and not viewer
return _skill_to_out(skill, labels=..., omit_content=omit_content)
```

When `omit_content=True` the API returns `null` for all content fields. The backend
authenticates callers via `get_optional_user`, which checks the `Authorization` header
(JWT) and the `X-Internal-Secret` + `X-Forwarded-User` headers for server-side callers.

**Root cause (now fixed):** `getSkill(slug, true)` in `page.tsx` previously called the
backend with no auth headers — `viewer` was always `None`, content always stripped.

**Fix — `frontend/lib/api.ts` `getSkill`:**

```typescript
export async function getSkill(
  slug: string,
  server = false,
  viewerName?: string,
) {
  const fetchHeaders: HeadersInit = {};
  if (server && viewerName) {
    fetchHeaders["X-Forwarded-User"] = viewerName;
    const secret = process.env.INTERNAL_API_SECRET;
    if (secret) fetchHeaders["X-Internal-Secret"] = secret;
  }
  const res = await fetch(`${b}/skills/${slug}`, { cache: "no-store", headers: fetchHeaders });
```

`INTERNAL_API_SECRET` is a Kubernetes secret injected into the Next.js pod as an
environment variable. The backend validates the `(X-Internal-Secret, X-Forwarded-User)`
pair to authenticate server-to-server calls without a JWT.

#### Frontend gate: `contentGated`

**`frontend/components/skill-content-tabs.tsx:28`**

```typescript
const contentGated = isInternal && !isAuthenticated && !readmeRaw && !skillMdRaw;
```

When `contentGated` is `true`, all tab content is hidden and replaced with a
"Sign in to view content for SLAC-only skills." message. The belt-and-suspenders
condition (`&& !readmeRaw && !skillMdRaw`) means: if the backend did return content
(e.g. the server-side `getSkill` call had valid auth), display it regardless of whether
the client-side `isAuthenticated` derived from Vouch headers is reliable.

Public skills are never gated (`isInternal = false`).

### How `isAuthenticated` is determined

**`frontend/app/skills/[slug]/page.tsx:22-24`**

```typescript
const h = headers();
const viewer =
  h.get("x-vouch-idp-claims-name") ||
  h.get("x-vouch-user") ||
  h.get("x-forwarded-user");
const { skill, ... } = await getSkill(params.slug, true, viewer ?? undefined);
...
isAuthenticated={!!viewer}
```

`viewer` is read from the incoming Next.js request headers **before** `getSkill` is
called so it can be forwarded to the backend. `isAuthenticated` is `true` when at least
one Vouch header is non-empty. All three are injected by nginx-ingress from the Vouch
auth service response.

### Auth flow: Vouch → nginx-ingress → Next.js

```
Browser
  │  GET /skills/<slug>
  ▼
nginx-ingress
  │  auth_request → vouch.slac.stanford.edu/validate
  │  Vouch validates cookie → returns response headers:
  │    X-Vouch-Idp-Claims-Name: ytl
  │    X-Vouch-User: ytl
  │  nginx-ingress copies those headers to the upstream request
  │  + auth-snippet captures: $forwarded_user = X-Vouch-Idp-Claims-Name value
  ▼
Next.js (server component)
  │  headers().get("x-vouch-idp-claims-name")  →  "ytl"
  │  viewer = "ytl"  →  isAuthenticated = true
  ▼
SkillContentTabs: contentGated = isInternal && false  →  content shown
```

### The forwarding bug and fix

The ingress `auth-snippet` captured the Vouch username into `$forwarded_user` but
never forwarded it to the upstream. The `auth-response-headers` annotation was
intended to handle this, but doesn't reliably carry `X-Vouch-Idp-Claims-Name`
through for all nginx-ingress versions or Vouch configurations.

**Fix — both overlay ingress files now have:**

```yaml
# kubernetes/overlays/{dev,prod2}/agent-knowledge-hub/ingress-frontend.yaml
nginx.ingress.kubernetes.io/auth-snippet: |
  auth_request_set $auth_resp_jwt $upstream_http_x_vouch_IdToken;
  auth_request_set $auth_resp_err $upstream_http_x_vouch_err;
  auth_request_set $auth_resp_failcount $upstream_http_x_vouch_failcount;
  auth_request_set $forwarded_user $upstream_http_x_vouch_idp_claims_name;
nginx.ingress.kubernetes.io/configuration-snippet: |
  proxy_set_header X-Forwarded-User $forwarded_user;
```

The `configuration-snippet` runs in the nginx `location` block (proxy phase) and
explicitly sets `X-Forwarded-User` from the `$forwarded_user` variable that
`auth-snippet` already populated from the Vouch response. This is the reliable path:
`auth_request_set` → `$forwarded_user` → `proxy_set_header` → Next.js request header.

`page.tsx:42` checks `x-forwarded-user` as the last fallback, so this header reaches
`viewer` and unblocks `isAuthenticated` for all authenticated users.

### Debug logging

Both the Next.js proxy route and the backend `/me` endpoint log incoming headers at
`DEBUG` level to help diagnose auth issues:

- `frontend/app/api/me/route.ts` — logs all headers from nginx and the resolved user
- `frontend/app/api/_internal.ts` — logs each Vouch header and the resolved `X-Forwarded-User`
- `backend/app/routers/me.py` + `backend/app/auth.py` — log which auth path matched and the final user_id
