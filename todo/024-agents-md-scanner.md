# TODO #024 — AGENTS.md Scanner Support: Recognise Codex/OpenCode Instruction Files

> **Priority:** 🟡 P2 — Medium
> **Status:** ✅ Complete
> **Branch:** —
> **PR:** —
> **Created:** 2026-06-02
> **Shipped:** 2026-06-03
> **Depends on:** —

---

## Problem Statement

The AKH scanner hard-codes the set of recognised skill instruction filenames as `{"SKILL.md", "skill.md", "CLAUDE.md"}`. The Codex CLI (codex-rs) uses `AGENTS.md` as its primary instruction file — Codex loads `~/.codex/AGENTS.md` as global instructions and a project-level `AGENTS.md` walking up from the git root. OpenCode does NOT read `AGENTS.md`; it reads `CLAUDE.md`, `opencode.md`, `OpenCode.md`, and `OPENCODE.md`.

As a result, any skill directory whose author targets Codex-first or OpenCode-first workflows will have an `AGENTS.md` rather than a `SKILL.md` or `CLAUDE.md`. The scanner currently ignores those directories entirely: `discover()` skips them, `MetadataExtractor` never reads their frontmatter, and the catalog never registers them.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Directory contains only `AGENTS.md` | `discover()` never adds the directory to `skill_file_dirs` — skill silently not found | Treated as a valid skill directory; included in discovery results |
| `AGENTS.md` frontmatter declares `name`, `description`, `keywords` | Ignored; name falls back to repo name or directory path | Extracted identically to `SKILL.md` frontmatter |
| `AGENTS.md` present but no `SKILL.md`/`CLAUDE.md` | Platform inference produces empty list | Heuristic infers `codex` from AGENTS.md presence |
| `discover()` subdir scan for `"skills": "./skills"` in plugin.json | Only looks for `SKILL.md`, `skill.md`, `CLAUDE.md` inside skill subdirs | Also recognises `AGENTS.md` as a valid skill file inside subdir scans |
| Skill detail page `skill_md_filename` field | Can be `null`, `"SKILL.md"`, or `"CLAUDE.md"` | Can also be `"AGENTS.md"` |

---

## Goals

1. Add `"AGENTS.md"` to `_SKILL_FILES` so the scanner fetches it alongside the existing recognised filenames
2. Add `"AGENTS.md"` as a fourth skill directory marker in `discover()` so AGENTS.md-only directories are found during multi-skill scans
3. Update all `MetadataExtractor` extraction methods to read `AGENTS.md` frontmatter — identical treatment to `CLAUDE.md`
4. Add `AGENTS.md`-based platform heuristic: infer `"codex"` when `AGENTS.md` is present and no explicit platform list is declared (OpenCode does not read AGENTS.md — omit `"opencode"` from this heuristic)
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

`github.py` line 351:

```python
_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml", "plugin.json"}
```

→ add `"AGENTS.md"`. One extra file fetched per skill directory when present. At ~1–5 KB typical size, negligible cost.

### `discover()`: AGENTS.md as skill dir marker

The tree-walk at line 764 currently checks:

```python
if fname in ("SKILL.md", "skill.md", "CLAUDE.md", "plugin.json"):
```

Add `"AGENTS.md"` to this set. A directory containing only `AGENTS.md` (and no `SKILL.md`/`CLAUDE.md`) is a valid Codex/OpenCode skill directory and must be included in `skill_md_dirs`. The existing pruning logic (dropping nested `skill_md_dirs` that are subdirectories of `plugin_json_dirs`) applies unchanged.

Three additional call sites inside `scan()` also need `"AGENTS.md"` added:

1. Line 543 — `has_skill_md` check (decides whether to attempt plugin.json subdir traversal)
2. Line 566 — direct file lookup inside the `"skills"` directory (plugin.json directory-form traversal)
3. Line 594 — file lookup inside each subdir of the `"skills"` directory

### MetadataExtractor: treat AGENTS.md identically to CLAUDE.md

All extraction methods that currently iterate over `("SKILL.md", "skill.md", "CLAUDE.md")` must add `"AGENTS.md"` to the tuple:

| Method | Approx line | Change |
|---|---|---|
| `_extract_keywords()` | 962 | Add `"AGENTS.md"` to iteration tuple |
| `_extract_name()` | 973 | Add `"AGENTS.md"` to iteration tuple |
| `_extract_description()` | 998 | Add `"AGENTS.md"` to iteration tuple |
| `_extract_platforms()` | 1015 | Add `"AGENTS.md"` to iteration tuple; also extend the heuristic check |
| `_extract_version()` | 1036 | Add `"AGENTS.md"` to iteration tuple |

Priority rule: `SKILL.md` > `skill.md` > `CLAUDE.md` > `AGENTS.md` for all fields where multiple files might be present. The iteration order in each method already implements priority — `AGENTS.md` is appended last.

### Platform heuristic for AGENTS.md

The current heuristic at line 1021:

```python
if "CLAUDE.md" in files or "SKILL.md" in files or "skill.md" in files:
    platforms.append("claude-code")
```

When `AGENTS.md` is present, append `"codex"` only (OpenCode reads `CLAUDE.md`/`opencode.md`, not `AGENTS.md`):

```python
if "AGENTS.md" in files:
    platforms.append("codex")
```

This is only reached when `plugin.json` has no explicit `platforms` field and no `platforms` key in the markdown frontmatter — the existing priority chain remains intact.

### `skill_md_filename` propagation

Three call sites in `services/skill.py` populate `skill_md_filename` by iterating over recognised filenames:

| Location | Current tuple | Action |
|---|---|---|
| `create()` GitHub path, line 163 | `("SKILL.md", "skill.md", "CLAUDE.md")` | Add `"AGENTS.md"` |
| `create()` local path, line 288 | `("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md")` | Already done ✅ |
| `refetch()` path, line 402 | `("SKILL.md", "skill.md", "CLAUDE.md")` | Add `"AGENTS.md"` |

No schema change needed — `skill_md_filename` is already `Optional[str]`.

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

### ADR-002: Infer `codex` platform from AGENTS.md presence

**Status:** Accepted (amended — `opencode` removed per research review)

**Context:** Platform inference is the fallback when no explicit `platforms` field appears in plugin.json or frontmatter. Currently CLAUDE.md/SKILL.md → `claude-code`. AGENTS.md is the primary instruction file for OpenAI Codex CLI (`codex-rs`). Research confirmed OpenCode does NOT read `AGENTS.md` — it reads `CLAUDE.md`, `opencode.md`, `OpenCode.md`, `OPENCODE.md`.

**Decision:** When `AGENTS.md` is present and no explicit platform list is declared, append `"codex"` only. The existing `claude-code` heuristic fires independently if CLAUDE.md/SKILL.md are also present.

**Consequences:** A repository with only `AGENTS.md` gets `["codex"]` as its inferred platforms. A repository with both `CLAUDE.md` and `AGENTS.md` gets `["claude-code", "codex"]`.

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

Choice: Infer "codex" only vs. "codex" + "opencode"
  + "codex" only: accurate — OpenCode does NOT read AGENTS.md (confirmed by research review); no false positive platform tags
  - "codex" only: future tool adopting AGENTS.md would require a plan update
  Decision: "codex" only. OpenCode reads CLAUDE.md/opencode.md, not AGENTS.md. Authors can add explicit frontmatter `platforms:` to override.

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
| `"opencode"` not yet in frontend platform lists | Low | Low | Added to Implementation Checklist; note: heuristic only infers "codex" (not "opencode") — opencode can be declared explicitly |

---

## Implementation Checklist

**`backend/app/services/github.py`**
- [x] Add `"AGENTS.md"` to `_SKILL_FILES` (line 351)
- [x] `discover()` tree-walk: add `"AGENTS.md"` to `if fname in (...)` check (line 764)
- [x] `scan()` line 543: add `"AGENTS.md"` to `has_skill_md` check
- [x] `scan()` line 566: add `"AGENTS.md"` to direct file lookup in skills dir
- [x] `scan()` line 594: add `"AGENTS.md"` to subdir file lookup
- [x] `_extract_keywords()` (~line 962): add `"AGENTS.md"` to frontmatter iteration tuple
- [x] `_extract_name()` (~line 973): add `"AGENTS.md"` to frontmatter iteration tuple
- [x] `_extract_description()` (~line 998): add `"AGENTS.md"` to frontmatter iteration tuple
- [x] `_extract_platforms()` (~line 1015): add `"AGENTS.md"` to frontmatter iteration tuple; add `if "AGENTS.md" in files: platforms.append("codex")` heuristic branch (codex only — not opencode)
- [x] `_extract_version()` (~line 1036): add `"AGENTS.md"` to frontmatter iteration tuple

**`backend/app/services/skill.py`**
- [x] `create()` GitHub path (line 163): add `"AGENTS.md"` to `skill_md_filename` iteration tuple
- [x] `create()` local path (line 288): already includes `"AGENTS.md"` ✅
- [x] `refetch()` path (line 402): add `"AGENTS.md"` to `skill_md_filename` iteration tuple

**Tests**
- [x] `discover()` finds a directory with only `AGENTS.md`
- [x] frontmatter extraction from `AGENTS.md` (name, description, keywords, version)
- [x] platform inference produces `["codex"]` for `AGENTS.md`-only dirs (not `"opencode"` — OpenCode does not read AGENTS.md)
- [x] priority order: when both `CLAUDE.md` and `AGENTS.md` present, `CLAUDE.md` values win
- [x] `skill_md_filename` is `"AGENTS.md"` when it's the only instruction file

**Documentation**
- [x] `docs/skill-file-discovery.md`: update all filename references (7+ locations — fname checks, _SKILL_FILES, has_skill_md, MetadataExtractor priority table, skill_md_filename source, file layout example, non-standard filename section)
- [x] `docs/adr/adr-u02-frontmatter-format.md`: add `"AGENTS.md"` to scope statement (line 14)
- [x] `CHANGELOG.md`: add Unreleased entry for AGENTS.md scanner support (recognised filename, codex/opencode inference, skill_md_filename)

**Frontend**
- [x] `frontend/components/platform-badges.tsx`: add `"opencode"` entry to `PLATFORM_COLORS` (authors may declare it explicitly via frontmatter even though the heuristic does not auto-infer it)
- [x] `frontend/components/platform-section.tsx`: add `"opencode"` to `KNOWN_PLATFORMS`
- [x] `frontend/lib/utils.ts`: add `"opencode"` to `PLATFORM_SUGGESTIONS`
- [x] `frontend/components/submit-form.tsx` (~line 279): update "no skills found" hint to mention `AGENTS.md` alongside `SKILL.md` and `CLAUDE.md`

---

## Definition of Done

- [x] A GitHub directory containing only `AGENTS.md` (no `SKILL.md`, no `CLAUDE.md`) appears in `discover()` results
- [x] `name`, `description`, `keywords` declared in `AGENTS.md` frontmatter are extracted and registered
- [x] Platform heuristic produces `["codex"]` for an `AGENTS.md`-only directory with no explicit `platforms` declaration
- [x] When both `CLAUDE.md` and `AGENTS.md` are present, `CLAUDE.md` frontmatter values win for all fields
- [x] `skill_md_filename` is `"AGENTS.md"` for skills where `AGENTS.md` is the only instruction file found
- [x] `docs/skill-file-discovery.md` updated to reflect all new filename sets and platform inference
- [x] `docs/adr/adr-u02-frontmatter-format.md` scope updated to include `AGENTS.md`
- [x] `CHANGELOG.md` Unreleased section includes AGENTS.md scanner support entry
- [x] `"opencode"` added to frontend platform lists (badges, picker, suggestions) — for explicit author use, not auto-inferred
- [x] Submit form "no skills found" hint mentions `AGENTS.md`
- [x] All checklist items complete

---

## Problems & Solutions

<!-- Add entries as you hit walls. -->

---

## Board Review

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-03
**Rounds:** 1

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ late | Y | Completed after board closed; found OpenCode does NOT read AGENTS.md — heuristic corrected to `"codex"` only, Problem Statement and ADR-002 amended |
| codebase-arch-review | — SKIP | — | Single service, no new data stores or service boundaries |
| codebase-eng-review | ✅ PASS | N | All 12 call sites verified; test plan (23 cases) added; 2 non-blocking observations noted |
| doc-review | ✅ PASS | Y | 3 blocking doc gaps identified (skill-file-discovery.md, CHANGELOG, adr-u02); added to checklist |
| security-review | — SKIP | — | No user input, no auth changes, no new endpoints |
| codebase-ux-review | ✅ PASS | Y | "opencode" missing from frontend platform lists + submit form hint; both added to checklist |

**Accepted warnings:** none
**Unresolved decisions:** none

### Reviewer output

<details>
<summary>codebase-eng-review — Round 1 (PASS)</summary>

## Summary
The plan is well-scoped and targets the correct files. All 10 call sites in github.py and 2 in skill.py verified against source. No blocking issues; 2 observations noted for implementer clarity. Test plan covers 23 cases.

## Issues
- OBS-1 (non-blocking): `_extract_platforms` has TWO distinct roles — frontmatter iteration tuple (line 1015) AND heuristic block (line 1021). Both need AGENTS.md but are separate if-blocks (not elif), per ADR-002.
- OBS-2 (non-blocking): Pre-existing `no_skill_files` semantic difference between github.py (len==0) and local.py (marker-based). Not introduced by this change.

## Test Plan (23 cases)
MetadataExtractor: name/description/keywords/version from AGENTS.md frontmatter; explicit platforms field; heuristic inference; coexistence priority (CLAUDE.md wins; SKILL.md wins). Scanner: scan fetches AGENTS.md; has_skill_md True; discover finds AGENTS.md-only dir; no duplicates when both present. skill.py: create/refetch pick AGENTS.md; prefer CLAUDE.md/SKILL.md when both present. Edge cases: no frontmatter, empty file, subdir lookup, no_skill_files flag. Regression: existing SKILL.md skills unchanged; local.py already works.

## Status
PASS

</details>

<details>
<summary>doc-review — Round 1 (PASS)</summary>

## Summary
3 blocking doc gaps: skill-file-discovery.md (7+ filename references), CHANGELOG.md (missing Unreleased entry), adr-u02-frontmatter-format.md (scope statement). 4 warning-level frontend gaps (opencode missing from platform lists, create-a-skill guide). All blocking gaps added to Implementation Checklist and DoD.

## Issues
- BLOCKING: `docs/skill-file-discovery.md` — 7+ locations listing filenames must include AGENTS.md
- BLOCKING: `CHANGELOG.md` — needs Unreleased entry
- BLOCKING: `docs/adr/adr-u02-frontmatter-format.md` line 14 — scope statement must add AGENTS.md
- WARNING: frontend platform-badges.tsx, platform-section.tsx, lib/utils.ts — missing opencode
- WARNING: create-a-skill guide doesn't mention AGENTS.md

## Status
PASS

</details>

<details>
<summary>codebase-ux-review — Round 1 (PASS WITH AMENDMENTS)</summary>

## Summary
Scanner delivers correct AGENTS.md parity. Three frontend gaps: (1) "opencode" renders as grey blob with no picker entry; (2) submit form "no skills found" hint omits AGENTS.md; (3) no platform-based catalog filter (pre-existing, track as follow-up). A-1 and A-2 added to Implementation Checklist.

## Issues
- UX-1 (MEDIUM): "opencode" missing from PLATFORM_COLORS, KNOWN_PLATFORMS, PLATFORM_SUGGESTIONS — renders grey, cannot be manually added
- UX-2 (LOW): submit-form.tsx line 279 hint text omits AGENTS.md
- UX-3 (LOW-MEDIUM): No platform filter in catalog — pre-existing gap, amplified by new values; track as follow-up

## Status
PASS WITH AMENDMENTS

</details>

---

## Relationship to Other Tasks

- **#019 (plugin.json scan pipeline):** No dependency. Both extend the set of recognised files in `_SKILL_FILES`; the changes are orthogonal and do not conflict.
- **#020 (Installer skill extension):** The installer needs to copy `AGENTS.md` into the target environment for Codex/OpenCode skills. The canonical list of instruction filenames documented here is the spec #020 implements against when deciding what to install.
- **#021 (Marketplace monorepo publish):** The `create` scaffold should offer an `AGENTS.md` template for Codex/OpenCode target platforms. Blocked until this todo establishes AGENTS.md as a first-class filename.
- **#022 (Installer git clone):** No dependency; both are independent installer-path changes.
- **#004 (Multi-source scanner abstraction):** Any scanner abstraction built in #004 inherits the updated filename set and extraction logic developed here.
