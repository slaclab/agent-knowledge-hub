## Summary

Three factual errors found in the Problem Statement. Codex claim is broadly correct; OpenCode claim is incorrect — OpenCode does NOT read AGENTS.md at all. One platform string needs a decision. One missed tool (Gemini CLI uses GEMINI.md). No simplification opportunity from an upstream schema — AGENTS.md has no frontmatter convention. Core design (Goals, ADRs, line numbers) is accurate and implementable.

---

## Issues

### ISSUE-1 [BLOCKER] — OpenCode does not read AGENTS.md

- Claim: "OpenCode walks the git tree reading AGENTS.md before CLAUDE.md"
- Finding: `opencode-ai/opencode` `internal/config/config.go` `defaultContextPaths` list (lines 108–119) contains `CLAUDE.md`, `CLAUDE.local.md`, `opencode.md`, `opencode.local.md`, `OPENCODE.md`, `OPENCODE.local.md`, `.cursorrules`, `.cursor/rules/`, `.github/copilot-instructions.md`. AGENTS.md is absent.
- Finding: GitHub code search for "AGENTS" across the entire `opencode-ai/opencode` repo returns 0 results.
- Finding: OpenCode does NOT walk the git tree — it reads files at the working directory root only, not parent directories.
- Verdict: **FALSE**. OpenCode does not use AGENTS.md. The plan's rationale for inferring `"opencode"` from AGENTS.md presence is therefore unsupported.

### ISSUE-2 [MEDIUM] — Codex global path described as `~/.codex/AGENTS.md` (approximately correct)

- Claim: "Codex loads `~/.codex/AGENTS.md` as global instructions"
- Finding: `codex-rs/core/src/agents_md.rs` confirms global AGENTS.md is loaded from `codex_home` directory. `codex-rs/config/src/config_toml.rs` comments confirm `~/.codex/config.toml` is the canonical path, so `codex_home` defaults to `~/.codex`. CODEX_HOME env var overrides this.
- Verdict: **CORRECT** — `~/.codex/AGENTS.md` is the global path. Minor caveat: CODEX_HOME env var can change this, but the description is accurate for the typical case.

### ISSUE-3 [MEDIUM] — Codex project-level AGENTS.md claim is correct but incomplete

- Claim: "a project-level AGENTS.md for per-project context"
- Finding: `codex-rs/core/src/agents_md.rs` confirms project-level AGENTS.md: "Collect every `AGENTS.md` found from the project root down to the current working directory (inclusive) and concatenate their contents." Project root is determined by walking up to a `project_root_markers` entry (default: `.git`).
- Finding: `project_doc_fallback_filenames` config field allows users to configure additional fallback filenames; CLAUDE.md is NOT a built-in fallback — it must be explicitly added by the user via config.
- Verdict: **CORRECT**. Codex does use project-level AGENTS.md. Additional accuracy note: CLAUDE.md is not a default fallback in Codex.

### ISSUE-4 [LOW] — AGENTS.md has no frontmatter convention

- Claim (ADR-001): "Both CLAUDE.md and AGENTS.md are natural-language instruction files carrying YAML frontmatter (name, description, version, keywords, platforms)."
- Finding: The `agentsmd/agents.md` format (the canonical open format at agents.md) shows only plain markdown with headings. No frontmatter in any example.
- Finding: `codex-rs/core/src/agents_md.rs` reads AGENTS.md as raw text — no frontmatter parsing in Codex.
- Finding: OpenAI Codex docs at developers.openai.com/codex/guides/agents-md describe plain markdown only.
- Verdict: **AGENTS.md carries no frontmatter convention.** The plan's extraction approach (reading YAML frontmatter from AGENTS.md) will work for AKH-authored AGENTS.md files that happen to include frontmatter, but this is not a real-world convention. Most AGENTS.md files in the wild will have no frontmatter and fall through to fallbacks — this is low impact but the ADR claim overstates the convention.

### ISSUE-5 [LOW] — Missing tool: GEMINI.md (not AGENTS.md)

- Finding: Gemini CLI uses `GEMINI.md` as its instruction file, not AGENTS.md. GitHub code search on `google-gemini/gemini-cli` returns 0 hits for AGENTS.md. README explicitly says "Custom context files (GEMINI.md)".
- Verdict: Gemini CLI is not a consumer of AGENTS.md. Plan correctly excludes it. No gap.

### ISSUE-6 [LOW] — Line numbers in scan() are off by ~5 lines

- Claim: `has_skill_md` check is at line 543; skills dir lookup at line 566; subdir lookup at line 594.
- Finding: The actual code at line 543 of `github.py` is the tree-walk section (DISCOVER, not SCAN). The `has_skill_md` check in `scan()` is near line 565 (off by ~22 lines). Subdir direct lookup is near line 566, subdir iteration near line 594.
- Verdict: Minor drift — `discover()` tree-walk and `scan()` subdir lookups are interleaved; the plan labels are close enough to guide implementation but will require line-by-line verification during coding. Not a design error.

---

## Decisions Required

### DR-1 [BLOCKER] — Should `"opencode"` still be inferred from AGENTS.md presence?

- Evidence: OpenCode (opencode-ai/opencode) does not read AGENTS.md. It reads `opencode.md`/`OpenCode.md`/`OPENCODE.md`.
- Options:
  - A) Remove `"opencode"` from the heuristic. Only infer `"codex"` from AGENTS.md. (Accurate.)
  - B) Keep `"opencode"` — treat it as aspirational/forward-looking in case OpenCode adds AGENTS.md support.
  - C) Add `"opencode.md"` and `"OPENCODE.md"` to `_SKILL_FILES` and infer `"opencode"` from those filenames instead.
- Recommendation: Option A in the short term. Option C in a follow-on task. Option B is misleading to users.

### DR-2 [LOW] — Should the ADR-001 claim about AGENTS.md frontmatter be narrowed?

- Evidence: AGENTS.md has no frontmatter convention in the real world. Extraction will silently produce empty fields for most real AGENTS.md files.
- Options:
  - A) Keep as-is; the fallback chain handles empty frontmatter gracefully.
  - B) Add a note to ADR-001 acknowledging that AGENTS.md frontmatter is an AKH-specific convention, not an upstream one.
- Recommendation: Option B (documentation fix only, no code change needed).

---

## Amendments

### AMENDMENT-1 (required, fixes ISSUE-1)

In the **Problem Statement**, replace:
> "OpenCode walks the git tree reading AGENTS.md before CLAUDE.md"

With:
> "OpenCode reads CLAUDE.md, opencode.md, and OPENCODE.md as its instruction files; it does not use AGENTS.md. Codex CLI (codex-rs) is the primary consumer of AGENTS.md."

### AMENDMENT-2 (required, fixes DR-1)

In the **Platform heuristic** section, change:
```python
if "AGENTS.md" in files:
    platforms.append("codex")
    platforms.append("opencode")
```
To:
```python
if "AGENTS.md" in files:
    platforms.append("codex")
```
Remove `"opencode"` from the heuristic until OpenCode adds AGENTS.md support.

### AMENDMENT-3 (optional, fixes DR-2)

In **ADR-001**, add:
> "Note: AGENTS.md frontmatter (name, description, keywords, platforms) is an AKH-specific convention. The upstream AGENTS.md format (agents.md) and Codex CLI both use plain markdown without YAML frontmatter. Extraction from AGENTS.md will typically return empty fields and fall through to the plugin.json / README / repo-name fallback chain — identical to how CLAUDE.md behaves when no frontmatter is present."

---

## Status
COMPLETE
