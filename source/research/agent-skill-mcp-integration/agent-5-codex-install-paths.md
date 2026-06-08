# OpenAI Codex CLI: Install Paths, Config Directory Conventions, and Skill Files

**Research date:** 2026-06-02  
**Status:** Complete — source-verified from openai/codex GitHub (codex-rs, main branch)

---

## Summary

OpenAI Codex CLI (Rust implementation — now the maintained default) uses `~/.codex/` as its home directory with a rich file layout. It has a full skills system with `SKILL.md` files, a plugin/marketplace installer, and both global and project-level `AGENTS.md` instruction loading. The TypeScript CLI (`@openai/codex`) was a legacy predecessor; the Rust CLI (`codex-rs`) is the current canonical implementation.

---

## 1. CODEX_HOME: The Root Config Directory

### Default path
`~/.codex/` — set by the `CODEX_HOME` environment variable.

**Source:** `codex-rs/utils/home-dir/src/lib.rs`

```rust
/// Returns the path to the Codex configuration directory, which can be
/// specified by the `CODEX_HOME` environment variable. If not set, defaults to `~/.codex`.
pub fn find_codex_home() -> std::io::Result<AbsolutePathBuf>
```

If `CODEX_HOME` is set, the directory must already exist and be a real directory; it is canonicalized. If unset, `~/.codex` is returned without verifying existence.

### Files in `~/.codex/`

Confirmed from source code references across the codebase:

| Path | Purpose |
|------|---------|
| `~/.codex/config.toml` | Main user config (all settings) |
| `~/.codex/AGENTS.md` | Global instruction file (loaded before project AGENTS.md) |
| `~/.codex/AGENTS.override.md` | Local override for global instructions (takes precedence over AGENTS.md) |
| `~/.codex/history.jsonl` | Session history |
| `~/.codex/auth.json` | CLI auth credentials (default; keyring is alternative) |
| `~/.codex/.credentials.json` | MCP OAuth credentials (when `store = file`) |
| `~/.codex/log/` | Log files (override via `log_dir` in config) |
| `~/.codex/memories/` | Auto-generated agent memories (writable in sandbox-write mode) |
| `~/.codex/.tmp/marketplaces/` | Installed marketplace snapshots (see Plugins section) |
| `~/.codex/.tmp/plugins/` | Bundled/curated plugin cache |
| `~/.codex/packages/standalone/releases/` | Standalone release binaries (self-managed installs) |
| `~/.codex/environments.toml` | Optional multi-environment config (local + remote) |

**Source files:** `codex-rs/install-context/src/lib.rs`, `codex-rs/core/src/config/mod.rs`, `codex-rs/config/src/config_toml.rs`, `codex-rs/core-plugins/src/installed_marketplaces.rs`

---

## 2. AGENTS.md: Global vs. Project Instructions

Codex implements a **hierarchical AGENTS.md loading system**.

### Global instructions
Loaded from `$CODEX_HOME/AGENTS.md` (or `$CODEX_HOME/AGENTS.override.md` which takes precedence).

**Source:** `codex-rs/core/src/agents_md.rs`

```rust
pub(crate) async fn load_global_instructions(
    fs: &dyn ExecutorFileSystem,
    codex_dir: Option<&AbsolutePathBuf>,
    startup_warnings: &mut Vec<String>,
) -> Option<LoadedAgentsMd> {
    let base = codex_dir?;
    for candidate in [LOCAL_AGENTS_MD_FILENAME, DEFAULT_AGENTS_MD_FILENAME] {
        let path = base.join(candidate);
        // ... reads and returns content
    }
}
```

Constants:
```rust
pub const DEFAULT_AGENTS_MD_FILENAME: &str = "AGENTS.md";
pub const LOCAL_AGENTS_MD_FILENAME: &str = "AGENTS.override.md";
```

### Project instructions
Loaded hierarchically from the project root down to the cwd. The project root is detected by walking up from cwd looking for markers (default: `.git`). All `AGENTS.md` files from root to cwd are concatenated in order.

**Configured in `config.toml`:**
- `project_root_markers` — list of filenames marking the project root (default: `[".git"]`)
- `project_doc_max_bytes` — max bytes to read (default: 32 KiB = 32,768 bytes)
- `project_doc_fallback_filenames` — additional filenames to check when `AGENTS.md` is absent

**Also checks:** `AGENTS.override.md` (local override, takes precedence per directory)

---

## 3. Skills System

Codex has a full, first-class skills system — this is not just AGENTS.md renaming; it is a distinct feature.

### What is a Skill?

A skill is a `SKILL.md` file (named `skills/SKILL_NAME/SKILL.md` or `skills/SKILL.md`) within a plugin root. Skills are loaded from plugin directories, referenced by name in prompts using a `@skill-name` mention syntax.

**Source:** `codex-rs/core/src/skills.rs`, `codex-rs/core-plugins/src/loader.rs`

```rust
const DEFAULT_SKILLS_DIR_NAME: &str = "skills";
```

### SkillScope values
Skills have a scope: `User`, `Repo`, `System`, or `Admin` (from `codex_protocol::protocol::SkillScope`).

### Skills config in `config.toml`
```toml
[skills]
bundled.enabled = true        # whether built-in bundled skills are active
include_instructions = true   # inject skills instruction block into turns

[[skills.config]]
name = "my-skill"
enabled = true

[[skills.config]]
path = "/absolute/path/to/skill"
enabled = false
```

**Source:** `codex-rs/config/src/skills_config.rs`

---

## 4. Plugin System and Install Paths

Codex has a full plugin marketplace system via `codex plugin add/list/remove`.

### Plugin manifest location
A plugin is any directory containing either:
- `.codex-plugin/plugin.json`
- `.claude-plugin/plugin.json` (cross-agent compatibility path)

**Source:** `codex-rs/utils/plugins/src/plugin_namespace.rs`

```rust
const DISCOVERABLE_PLUGIN_MANIFEST_PATHS: &[&str] =
    &[".codex-plugin/plugin.json", ".claude-plugin/plugin.json"];
```

### Plugin directory structure (installed)
Installed plugins from marketplaces are stored under:

```
~/.codex/.tmp/marketplaces/<marketplace-name>/<plugin-name>/
    .codex-plugin/plugin.json   # or .claude-plugin/plugin.json
    skills/
        <skill-name>/
            SKILL.md
    hooks/
        hooks.json              # optional lifecycle hooks
    .mcp.json                   # optional MCP server configs
    .app.json                   # optional app connector configs
    config.toml                 # optional plugin-specific config
```

**Source:** `codex-rs/core-plugins/src/installed_marketplaces.rs`

```rust
pub const INSTALLED_MARKETPLACES_DIR: &str = ".tmp/marketplaces";

pub fn marketplace_install_root(codex_home: &Path) -> PathBuf {
    codex_home.join(INSTALLED_MARKETPLACES_DIR)
}
```

### Plugin config in `config.toml`
```toml
[plugins."my-plugin@my-marketplace"]
enabled = true
```

Plugins are identified by the `PLUGIN@MARKETPLACE` key format.

**Source:** `codex-rs/config/src/plugin_edit.rs`

---

## 5. Cross-Agent Compatibility: `.claude-plugin/plugin.json`

**Key finding:** Codex explicitly recognizes `.claude-plugin/plugin.json` as an alternate plugin manifest path (alongside `.codex-plugin/plugin.json`). This is a confirmed, intentional cross-agent compatibility path in the Codex source.

```rust
const DISCOVERABLE_PLUGIN_MANIFEST_PATHS: &[&str] =
    &[".codex-plugin/plugin.json", ".claude-plugin/plugin.json"];
```

This means a plugin repo that already has `.claude-plugin/plugin.json` (Claude Code style) will be recognized by Codex without any additional manifest files.

---

## 6. TypeScript CLI vs Rust CLI Differences

| Feature | TypeScript CLI (legacy) | Rust CLI (current) |
|---------|------------------------|---------------------|
| Config format | `config.json` | `config.toml` |
| Maintenance status | Deprecated/legacy | Actively maintained |
| Skills system | Unknown/not documented | Full `SKILL.md` + marketplace |
| Plugin system | Unknown/not documented | Full `codex plugin add/list/remove` |
| AGENTS.md | Basic support | Hierarchical + global `~/.codex/AGENTS.md` |
| CODEX_HOME | `~/.codex` | `~/.codex` (same, via `CODEX_HOME` env) |
| Install path | npm-managed shim | Standalone binary or npm shim |

The Rust CLI is the canonical implementation. The TypeScript CLI reference docs and behavior should not be relied on for AKH integration planning.

---

## 7. Implications for AKH Codex Install Support

### Where to install files for Codex

For a plugin declared `"compatible_platforms": ["codex"]`, AKH should install:

1. **Plugin manifest:** `~/.codex/.tmp/marketplaces/<marketplace-name>/<plugin-name>/.codex-plugin/plugin.json`
   - Or equivalently `.claude-plugin/plugin.json` (recognized by Codex cross-agent compat)

2. **Skill files:** `~/.codex/.tmp/marketplaces/<marketplace-name>/<plugin-name>/skills/<skill-name>/SKILL.md`

3. **Global instruction injection:** `~/.codex/AGENTS.md`
   - Append to or create this file; Codex reads it before every session as global instructions
   - Use `~/.codex/AGENTS.override.md` if you want it to take priority over other global configs

4. **Register marketplace in config:** Add to `~/.codex/config.toml`:
   ```toml
   [marketplaces."akh"]
   source_type = "local"
   source = "/path/to/akh/marketplace"
   ```

5. **Enable plugin in config:** Add to `~/.codex/config.toml`:
   ```toml
   [plugins."<plugin-name>@akh"]
   enabled = true
   ```

### Key constraints
- The plugin marketplace directory (`~/.codex/.tmp/marketplaces/`) is a **temporary/managed directory** — files placed there directly may be overwritten if Codex upgrades or syncs. The safer path for AKH-managed plugins is to use a `local` source_type marketplace pointing to an AKH-controlled directory outside `.tmp/`.
- For "local" marketplace type, the `source` field should point to the AKH plugin directory directly.

### Preferred local marketplace approach
```toml
# in ~/.codex/config.toml
[marketplaces."agent-knowledge-hub"]
source_type = "local"
source = "~/.akh/plugins"   # AKH-managed directory
```

Then the plugin directory structure would be:
```
~/.akh/plugins/
    marketplace.json         # marketplace manifest
    <plugin-name>/
        .codex-plugin/plugin.json
        skills/
            <skill-name>/
                SKILL.md
```

---

## 8. Gaps and Open Questions

| Gap | Impact | Notes |
|-----|--------|-------|
| `marketplace.json` format not verified | Blocks implementation | Need to find `codex-rs/core-plugins/src/marketplace.rs` for the manifest schema |
| Skills injection mechanism | Medium | How `SKILL.md` content is injected into prompts at runtime needs verification |
| Global AGENTS.md append safety | Low | Need to determine if AKH should append, prepend, or use `AGENTS.override.md` |
| Project `.codex/` directory | Low | Whether a per-project `.codex/config.toml` + `AGENTS.md` layer exists is not yet verified (likely yes based on `ConfigLayerSource::Project { dot_codex_folder }`) |
| Sandbox write-access to `~/.codex/memories` | None for install | Only relevant for runtime operation, not install |
| TypeScript CLI legacy compatibility | Low | Users on old npm install may still be using JSON config — AKH installer should detect |

---

## Sources

- `codex-rs/utils/home-dir/src/lib.rs` — CODEX_HOME resolution
- `codex-rs/core/src/agents_md.rs` — AGENTS.md discovery and loading
- `codex-rs/core/src/skills.rs` — Skills module entry point
- `codex-rs/config/src/skills_config.rs` — SkillConfig/SkillsConfig types
- `codex-rs/config/src/config_toml.rs` — Full ConfigToml schema including `skills`, `plugins`, `marketplaces`
- `codex-rs/config/src/plugin_edit.rs` — Plugin config editing (codex_home + config.toml)
- `codex-rs/core-plugins/src/installed_marketplaces.rs` — `marketplace_install_root` = `~/.codex/.tmp/marketplaces`
- `codex-rs/core-plugins/src/loader.rs` — `DEFAULT_SKILLS_DIR_NAME = "skills"`, `DEFAULT_HOOKS_CONFIG_FILE`, `DEFAULT_MCP_CONFIG_FILE`
- `codex-rs/utils/plugins/src/plugin_namespace.rs` — `.codex-plugin/plugin.json` and `.claude-plugin/plugin.json` as discoverable manifest paths
- `codex-rs/install-context/src/lib.rs` — Install methods, `~/.codex/packages/standalone/releases/` layout
- `codex-rs/README.md` — Current vs legacy CLI distinction, config.toml vs config.json
- Repository: https://github.com/openai/codex (main branch, June 2026)
