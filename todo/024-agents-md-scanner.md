# TODO #024 — AGENTS.md Scanner Support: Recognise Codex/OpenCode Instruction Files

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-06-02
> **Shipped:** —
> **Depends on:** —

---

## Problem Statement

The AKH scanner hard-codes the set of recognised skill instruction filenames as `{"SKILL.md", "skill.md", "CLAUDE.md"}`. The Codex CLI (codex-rs) and OpenCode both use `AGENTS.md` as their primary instruction file — OpenCode walks the git tree reading `AGENTS.md` before `CLAUDE.md`; Codex loads `~/.codex/AGENTS.md` as global instructions and a project-level `AGENTS.md` for per-project context.

As a result, any skill directory whose author targets Codex-first or OpenCode-first workflows will have an `AGENTS.md` rather than a `SKILL.md` or `CLAUDE.md`. The scanner currently ignores those directories entirely: `discover()` skips them, `MetadataExtractor` never reads their frontmatter, and the catalog never registers them.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Directory contains only `AGENTS.md` | `discover()` never adds the directory to `skill_file_dirs` — skill silently not found | Treated as a valid skill directory; included in discovery results |
| `AGENTS.md` frontmatter declares `name`, `description`, `keywords` | Ignored; name falls back to repo name or directory path | Extracted identically to `SKILL.md` frontmatter |
| `AGENTS.md` present but no `SKILL.md`/`CLAUDE.md` | Platform inference produces empty list | Heuristic infers `codex` and/or `opencode` from AGENTS.md presence |
| `discover()` subdir scan for `"skills": "./skills"` in plugin.json | Only looks for `SKILL.md`, `skill.md`, `CLAUDE.md` inside skill subdirs | Also recognises `AGENTS.md` as a valid skill file inside subdir scans |
| Skill detail page `skill_md_filename` field | Can be `null`, `"SKILL.md"`, or `"CLAUDE.md"` | Can also be `"AGENTS.md"` |

---

## Goals

1. Add `"AGENTS.md"` to `_SKILL_FILES` so the scanner fetches it alongside the existing recognised filenames
2. Add `"AGENTS.md"` as a fourth skill directory marker in `discover()` so AGENTS.md-only directories are found during multi-skill scans
3. Update all `MetadataExtractor` extraction methods to read `AGENTS.md` frontmatter — identical treatment to `CLAUDE.md`
4. Add `AGENTS.md`-based platform heuristic: infer `"codex"` and `"opencode"` when `AGENTS.md` is present and no explicit platform list is declared
5. Propagate `skill_md_filename = "AGENTS.md"` correctly in the registration pipeline so the source-file indicator on the detail page shows the right filename

## Non-Goals

- Installer changes (separate, #020 and #022)
- Parsing AGENTS.md semantic content beyond frontmatter (same treatment as CLAUDE.md — we read frontmatter, not instruction body)
- Adding `AGENTS.md` generation to the `/agent-knowledge-hub create` scaffold (separate, #021)
- Validating that `AGENTS.md` content conforms to Codex or OpenCode syntax
- Fetching or validating `~/.codex/AGENTS.md` global files (project-level only)

---

## Design

### Scanner change: add `AGENTS.md` to `_SKILL_FILES`

`github.py` line 277:

```python
_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml", "plugin.json"}
```

→ add `"AGENTS.md"`. One extra file fetched per skill directory when present. At ~1–5 KB typical size, negligible cost.

### `discover()`: AGENTS.md as skill dir marker

The tree-walk at line 659 currently checks:

```python
if fname in ("SKILL.md", "skill.md", "CLAUDE.md", "plugin.json"):
```

Add `"AGENTS.md"` to this set. A directory containing only `AGENTS.md` (and no `SKILL.md`/`CLAUDE.md`) is a valid Codex/OpenCode skill directory and must be included in `skill_md_dirs`. The existing pruning logic (dropping nested `skill_md_dirs` that are subdirectories of `plugin_json_dirs`) applies unchanged.

Three additional call sites inside `scan()` also need `"AGENTS.md"` added:

1. Line 470 — `has_skill_md` check (decides whether to attempt plugin.json subdir traversal)
2. Line 493 — direct file lookup inside the `"skills"` directory (plugin.json directory-form traversal)
3. Line 521 — file lookup inside each subdir of the `"skills"` directory

### MetadataExtractor: treat AGENTS.md identically to CLAUDE.md

All extraction methods that currently iterate over `("SKILL.md", "skill.md", "CLAUDE.md")` must add `"AGENTS.md"` to the tuple:

| Method | Line range | Change |
|---|---|---|
| `_extract_keywords()` | 851–858 | Add `"AGENTS.md"` to iteration tuple |
| `_extract_name()` | 862–866 | Add `"AGENTS.md"` to iteration tuple |
| `_extract_description()` | 887–892 | Add `"AGENTS.md"` to iteration tuple |
| `_extract_platforms()` | 903–911 | Add `"AGENTS.md"` to iteration tuple; also extend the heuristic check at line 911 |
| `_extract_version()` | 926–929 | Add `"AGENTS.md"` to iteration tuple |

Priority rule: `SKILL.md` > `skill.md` > `CLAUDE.md` > `AGENTS.md` for all fields where multiple files might be present. The iteration order in each method already implements priority — `AGENTS.md` is appended last.

### Platform heuristic for AGENTS.md

The current heuristic at line 910–911:

```python
if "CLAUDE.md" in files or "SKILL.md" in files or "skill.md" in files:
    platforms.append("claude-code")
```

When `AGENTS.md` is present, append `"codex"` and `"opencode"`:

```python
if "AGENTS.md" in files:
    platforms.append("codex")
    platforms.append("opencode")
```

This is only reached when `plugin.json` has no explicit `platforms` field and no `platforms` key in the markdown frontmatter — the existing priority chain remains intact.

### `skill_md_filename` propagation

The Skill model stores `skill_md_filename` to identify which instruction file was found. The repository layer that populates this field must check `"AGENTS.md"` as a fourth candidate after `SKILL.md`, `skill.md`, and `CLAUDE.md`. No schema change needed — the field is already `Optional[str]`.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `_SKILL_FILES` constant | Modify | Add `"AGENTS.md"` |
| `GitHubScanner.scan()` | Modify | `has_skill_md` check; subdir scan name sets (3 call sites) |
| `GitHubScanner.discover()` | Modify | Tree-walk fname check: add `"AGENTS.md"` as skill dir marker |
| `MetadataExtractor._extract_keywords()` | Modify | Add `"AGENTS.md"` to iteration tuple |
| `MetadataExtractor._extract_name()` | Modify | Add `"AGENTS.md"` to iteration tuple |
| `MetadataExtractor._extract_description()` | Modify | Add `"AGENTS.md"` to iteration tuple |
| `MetadataExtractor._extract_platforms()` | Modify | Add `"AGENTS.md"` to iteration tuple; add Codex/OpenCode heuristic |
| `MetadataExtractor._extract_version()` | Modify | Add `"AGENTS.md"` to iteration tuple |
| `skill_repository` (populate `skill_md_filename`) | Modify | Check `"AGENTS.md"` as fourth candidate |

All changes are in `backend/app/services/github.py`. The `skill_md_filename` propagation touches the repository layer but no schema migration is required.

---

## ADRs

### ADR-001: AGENTS.md treated identically to CLAUDE.md for metadata extraction

**Status:** Accepted

**Context:** Both CLAUDE.md and AGENTS.md are natural-language instruction files carrying YAML frontmatter (name, description, version, keywords, platforms). The scanner already reads CLAUDE.md without any special parsing beyond its frontmatter — the instruction body is stored raw but not interpreted. AGENTS.md carries the same frontmatter convention.

**Decision:** AGENTS.md is given identical treatment to CLAUDE.md in all extraction methods. No new extraction logic is needed — only the filename lookup tuples are extended. SKILL.md frontmatter retains the highest priority; AGENTS.md is the lowest-priority markdown source (after SKILL.md, skill.md, CLAUDE.md).

**Consequences:** Authors who write AGENTS.md with standard frontmatter get the same quality of registration as CLAUDE.md authors. Authors who use both CLAUDE.md and AGENTS.md in the same directory see CLAUDE.md win for all metadata fields, which matches the priority established by OpenCode (reads AGENTS.md first but CLAUDE.md is the Claude-native file).

---

### ADR-002: Infer `codex` and `opencode` platforms from AGENTS.md presence

**Status:** Accepted

**Context:** Platform inference is the fallback when no explicit `platforms` field appears in plugin.json or frontmatter. Currently CLAUDE.md/SKILL.md → `claude-code`. AGENTS.md has two consumers: OpenAI Codex CLI (`codex`) and OpenCode (`opencode`). OpenCode also reads CLAUDE.md, so a repo with both files could legitimately target all three platforms.

**Decision:** When `AGENTS.md` is present and no explicit platform list is declared, append both `"codex"` and `"opencode"` to the inferred platform list. The existing `claude-code` heuristic fires independently if CLAUDE.md/SKILL.md are also present — a multi-file repo gets all applicable platforms. Adding both `codex` and `opencode` avoids having to pick one; authors who care can pin explicitly via frontmatter.

**Consequences:** A repository with only `AGENTS.md` gets `["codex", "opencode"]` as its inferred platforms. A repository with both `CLAUDE.md` and `AGENTS.md` gets `["claude-code", "codex", "opencode"]`. Both outcomes are more informative than the current empty list.

---

### ADR-003: No new schema fields — AGENTS.md is a filename variant, not a new entity type

**Status:** Accepted

**Context:** One could model `source_file_type` as an enum (`skill_md`, `claude_md`, `agents_md`) and add fields specific to AGENTS.md. This would enable frontend filtering by instruction file type.

**Decision:** No new schema fields. `skill_md_filename` already captures the source filename as a string. AGENTS.md is a filename variant, not a structurally distinct entity — adding enum fields for it would be premature without a clear user need for filtering by instruction file convention.

**Consequences:** The detail page source-file indicator already works via `skill_md_filename`; showing "AGENTS.md" requires no schema change. Frontend filtering by instruction file type remains impossible without a future field addition.

---

## Trade-offs

```
Choice: Add AGENTS.md as a peer of CLAUDE.md vs. treat it as a lower-priority alias
  + Peer: parity for Codex-first authors; no silent degradation
  - Peer: if both AGENTS.md and CLAUDE.md exist, ambiguous which wins
  Decision: Peer in the file set; explicit priority order (SKILL.md > skill.md > CLAUDE.md > AGENTS.md) resolves ambiguity deterministically.

Choice: Infer both "codex" and "opencode" vs. only one
  + Both: accurate — both tools use AGENTS.md; no information loss
  - Both: platform list may be longer than expected for a skill targeting only Codex
  Decision: Both. Authors who want to declare only one platform can add an explicit frontmatter `platforms:` list, which takes priority over heuristic inference.

Choice: Scope to github.py only vs. also update plugin.json schema docs
  + github.py only: minimal blast radius; schema docs are a separate concern
  - github.py only: AGENTS.md support is undocumented for plugin authors
  Decision: Code change only in this todo. Documentation update deferred to #020 or #021 where the full plugin.json format is documented.
```

---

## Delivery Slices

**Slice 1 — File set and discovery**
- Add `"AGENTS.md"` to `_SKILL_FILES`
- `discover()` tree-walk: add `"AGENTS.md"` to the fname check
- `scan()`: update `has_skill_md`, subdir direct-lookup, and subdir iteration sets

**Slice 2 — Metadata extraction**
- `_extract_keywords()`, `_extract_name()`, `_extract_description()`, `_extract_version()`: add `"AGENTS.md"` to iteration tuples
- `_extract_platforms()`: add `"AGENTS.md"` to iteration tuple + Codex/OpenCode heuristic
- Repository layer: check `"AGENTS.md"` when setting `skill_md_filename`

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| False positives: repo with AGENTS.md that is not a skill | Medium | Low | `no_skill_files` flag and skill detail page give submitter full visibility; no auto-registration |
| AGENTS.md without frontmatter produces empty name/description | High | Low | Fallback chain (plugin.json, README, repo name) already handles this; same as CLAUDE.md without frontmatter |
| Priority ambiguity when CLAUDE.md and AGENTS.md coexist | Low | Low | Explicit priority order (CLAUDE.md before AGENTS.md) is consistent and documented in ADR-001 |
| `"codex"` and `"opencode"` platform values not yet known to the frontend | Low | Low | `compatible_platforms` is a free string list; unknown values are rendered as-is; no enum validation in schemas |

---

## Implementation Checklist

- [ ] Add `"AGENTS.md"` to `_SKILL_FILES`
- [ ] `discover()` tree-walk: add `"AGENTS.md"` to `if fname in (...)` check (line 659)
- [ ] `scan()` line 470: add `"AGENTS.md"` to `has_skill_md` check
- [ ] `scan()` line 493: add `"AGENTS.md"` to direct file lookup in skills dir
- [ ] `scan()` line 521: add `"AGENTS.md"` to subdir file lookup
- [ ] `_extract_keywords()`: add `"AGENTS.md"` to frontmatter iteration tuple
- [ ] `_extract_name()`: add `"AGENTS.md"` to frontmatter iteration tuple
- [ ] `_extract_description()`: add `"AGENTS.md"` to frontmatter iteration tuple
- [ ] `_extract_platforms()`: add `"AGENTS.md"` to frontmatter iteration tuple; add codex/opencode heuristic branch
- [ ] `_extract_version()`: add `"AGENTS.md"` to frontmatter iteration tuple
- [ ] Repository layer: check `"AGENTS.md"` when populating `skill_md_filename`
- [ ] Tests: `discover()` finds a directory with only `AGENTS.md`; frontmatter extraction from `AGENTS.md`; platform inference for `AGENTS.md`-only dirs; priority order when both `CLAUDE.md` and `AGENTS.md` present

---

## Definition of Done

- [ ] A GitHub directory containing only `AGENTS.md` (no `SKILL.md`, no `CLAUDE.md`) appears in `discover()` results
- [ ] `name`, `description`, `keywords` declared in `AGENTS.md` frontmatter are extracted and registered
- [ ] Platform heuristic produces `["codex", "opencode"]` for an `AGENTS.md`-only directory with no explicit `platforms` declaration
- [ ] When both `CLAUDE.md` and `AGENTS.md` are present, `CLAUDE.md` frontmatter values win for all fields
- [ ] `skill_md_filename` is `"AGENTS.md"` for skills where `AGENTS.md` is the only instruction file found
- [ ] All checklist items complete

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

> *Populated by `/codebase-board-review` after the board completes. Do not fill manually.*

**Verdict:** —
**Date:** —
**Rounds:** —

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research-handbook | — | — | — |
| codebase-arch-review | — | — | — |
| codebase-eng-review | — | — | — |
| codebase-doc-review | — | — | — |
| security-review | — | — | — |

---

## Relationship to Other Tasks

- **#019 (plugin.json scan pipeline):** No dependency. Both extend the set of recognised files in `_SKILL_FILES`; the changes are orthogonal and do not conflict.
- **#020 (Installer skill extension):** The installer needs to copy `AGENTS.md` into the target environment for Codex/OpenCode skills. The canonical list of instruction filenames documented here is the spec #020 implements against when deciding what to install.
- **#021 (Marketplace monorepo publish):** The `create` scaffold should offer an `AGENTS.md` template for Codex/OpenCode target platforms. Blocked until this todo establishes AGENTS.md as a first-class filename.
- **#022 (Installer git clone):** No dependency; both are independent installer-path changes.
- **#004 (Multi-source scanner abstraction):** Any scanner abstraction built in #004 inherits the updated filename set and extraction logic developed here.
