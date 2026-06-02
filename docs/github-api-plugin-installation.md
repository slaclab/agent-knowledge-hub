# GitHub API Approaches for Plugin Installation

*Researched: 2026-05-28 | Sources: GitHub REST API docs, live API, Claude Code docs*

## Summary

There are three viable mechanisms for fetching plugin files from GitHub repos. They differ significantly in capabilities, rate limits, and recursive support. Claude Code's native `/plugin` system uses git clone — not the Contents API — which is the correct approach for arbitrary repo structures.

---

## GitHub Contents API

**Endpoint:** `GET /repos/{owner}/{repo}/contents/{path}`

| Property | Behaviour |
|---|---|
| Directory path | Returns direct children only — **one level, non-recursive** |
| `type` values | `"file"`, `"dir"`, `"symlink"`, `"submodule"` |
| Subdirectory entry | Appears as `{type: "dir"}` — contents NOT included; separate call required |
| Recursive option | **None** — no parameter to enable it |
| File limit | 1,000 entries per directory; truncated beyond that |
| Rate limit | 60 req/hr unauthenticated; 5,000 req/hr with token |

**Implication for AKH installer:** To traverse a nested directory tree, the installer must make O(depth × breadth) API calls — one per subdirectory level. For a plugin with `skills/myplugin/scripts/` this means 3 round trips minimum just to enumerate files, before downloading any.

**Current AKH installer uses this API.** Directory-form plugins (`"skills": "./skills"`) require recursive Contents API fetching, which was the design decision in [TODO #020 ADR-001](../todo/020-installer-skill-extension.md).

---

## Git Trees API

**Endpoint:** `GET /repos/{owner}/{repo}/git/trees/{sha}?recursive=1`

| Property | Behaviour |
|---|---|
| `type` values | `"blob"` (file), `"tree"` (directory), `"commit"` (submodule) |
| Recursive option | **Yes** — `?recursive=1` returns full flat tree in one call |
| Entry limit | 100,000 entries or 7 MB; `truncated: true` flag if exceeded |
| Requires tree SHA | Yes — must first resolve branch/tag to a commit SHA |

**Advantage over Contents API:** Single API call returns every file path in the entire repo tree. No recursion logic needed in the installer. Better for repos with deep directory structures.

**Limitation:** Returns paths only — you still need individual Contents API calls (or raw blob fetches) to download each file's content.

---

## Git Clone (what Claude Code native uses)

**Claude Code's native `/plugin install` mechanism:** Git clone or sparse clone.

```
source types:
  github    → full git clone of the repo at a pinned ref/sha
  git-subdir → sparse clone of a subdirectory (minimises bandwidth for monorepos)
  url       → direct git URL clone
  npm       → npm install
```

| Property | Behaviour |
|---|---|
| Recursion | Full — entire repo or subdirectory tree, arbitrary depth |
| Rate limits | No GitHub API rate limits (uses git protocol) |
| Auth | Uses existing Git credential helpers (gh auth, SSH keys) |
| Private repos | Works transparently via credential helpers |
| Version pinning | SHA-pinned via `ref` + `sha` fields in marketplace.json |
| Cache location | `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` |

**Plugin manifest location:** `.claude-plugin/plugin.json` (note: inside a `.claude-plugin/` subdirectory, not at root)

---

## Comparison

| | Contents API | Trees API | Git Clone |
|---|---|---|---|
| Recursive | No — must implement manually | Yes — single call | Yes — native |
| Downloads file content | Yes — inline in response | No — paths only | Yes — all files |
| API rate limits | Yes (5k/hr with token) | Yes (5k/hr with token) | No |
| Private repo support | Yes (token) | Yes (token) | Yes (credential helpers) |
| Complexity to implement | Low (current AKH approach) | Medium | Medium–High |
| Handles monorepos | Poorly | Well | Well (sparse clone) |
| Pinnable to commit SHA | Yes (`?ref=<sha>`) | Yes (sha is required) | Yes (`ref` field) |

---

## Implications for AKH Installer

### Current approach (Contents API, recursive)

The `#020` design implements recursive Contents API fetching for directory-form plugins. This works but requires multiple round trips and is rate-limit sensitive for deep trees.

### Alternative: Git Trees API

Switch the directory-enumeration step to use the Trees API. Benefits:
- One API call to enumerate all file paths (vs O(n) Contents API calls)
- No manual recursion logic
- Still need individual file downloads (raw content endpoint or Contents API per file)

### Alternative: Git clone

Adopt the same approach as Claude Code native — clone the repo (or sparse clone the `skill_path` subdirectory) at a pinned SHA.

**Pros:**
- Handles arbitrary repo structures without any enumeration logic
- No GitHub API rate limits
- Consistent with how Claude Code's own plugin system works
- Sparse clone minimises bandwidth for monorepos

**Cons:**
- Requires `git` to be available on the user's PATH
- More complex error handling (auth failures, network, disk space)
- Cannot be implemented purely via HTTP fetch in a skill (requires Bash execution)
- AKH installer skill runs inside Claude Code — `git clone` via Bash tool is feasible but adds a system dependency

### Recommendation

For the near term (#020), the recursive Contents API approach is sufficient for the expected scale of AKH plugins (< 50 files, < 5 directory levels). The Trees API is a better choice than recursive Contents API for the enumeration step and should be adopted when the installer is next significantly refactored.

Git clone is the right long-term architecture if AKH ever needs to handle large monorepos or wants to match the Claude Code native experience exactly. It should be a separate TODO (likely post-#020).

---

## References

- [GitHub REST API: Contents](https://docs.github.com/en/rest/repos/contents)
- [GitHub REST API: Git Trees](https://docs.github.com/en/rest/git/trees)
- [Claude Code: Plugins](https://code.claude.com/docs/en/plugins)
- [Claude Code: Plugin Marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)
- [Claude Code: Discover and Install Plugins](https://code.claude.com/docs/en/discover-plugins)
- [TODO #020: Installer Skill Extension](../todo/020-installer-skill-extension.md)
