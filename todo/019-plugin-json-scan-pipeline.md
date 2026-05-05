# TODO #019 — plugin.json-First Scan Pipeline + Rich Component Metadata

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** —
> **Depends on:** —

---

## Problem Statement

The backend scanner (`github.py`) fetches a fixed set of files at scan time (`_SKILL_FILES`) but `plugin.json` is not in that set. This means every piece of structured metadata an author has declared in `plugin.json` — keywords, agents, MCP servers, compatible platforms, author info — is silently ignored at registration time.

Consequences:

1. **Labels are under-populated** — `plugin.json["keywords"]` are never converted to labels, even though the keyword→label pipeline already exists for SKILL.md keywords.
2. **Component metadata invisible** — the catalog has no way to surface "this skill has 7 agents", "this skill registers an MCP server", or "this skill ships Python scripts" because those facts live only in plugin.json.
3. **Platform support undeclared** — `Skill.compatible_platforms` is populated only by heuristic inference from `package.json` dependencies. Authors who declare `"compatible_platforms": ["claude-code", "codex"]` in plugin.json get nothing.
4. **`discover()` misses plugin-only dirs** — skill directories that contain a `plugin.json` but no `SKILL.md`/`CLAUDE.md` are never found during multi-skill discovery scans.
5. **Directory-form skills never parsed** — the marketplace uses `"skills": "./skills"` (a directory string, not an array). The current scanner and MetadataExtractor only understand the array form.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Author declares `"keywords": ["mcp", "python"]` in plugin.json | Keywords ignored | Labels `mcp`, `python` applied at registration |
| Skill has `"agents": [...]` in plugin.json | Agent info invisible | `agent_count`, `agent_names` stored; `multi-agent` label auto-applied |
| Skill has `"mcp-servers": [...]` in plugin.json | MCP presence invisible | `has_mcp_server: true`; `mcp` label auto-applied |
| `"compatible_platforms": ["claude-code", "codex"]` declared | Ignored, heuristic only | Stored directly from plugin.json |
| `"skills": "./skills"` (directory form) | MetadataExtractor silently skips | Directory resolved, component count surfaced |
| Plugin dir has plugin.json but no SKILL.md | `discover()` skips the dir | Dir included in discovery results |

---

## Goals

1. Add `plugin.json` to the set of files fetched at scan time
2. Extend `MetadataExtractor` to parse plugin.json: keywords → labels, agents, MCP, platforms, author, directory-form skills
3. Add component metadata fields to the `Skill` model and expose them in API responses
4. Auto-apply structural labels (`mcp`, `multi-agent`, `has-scripts`) at registration — no author action required
5. Update `discover()` to also identify skill directories by `plugin.json` presence
6. Align plugin.json schema documentation with the marketplace format

## Non-Goals

- Installer behavior changes (separate, #020)
- Fetching or storing the full contents of agent `.md` files (only names/count stored in catalog)
- Full-text search on plugin.json fields
- Supporting non-GitHub sources (separate, #004)

---

## Design

### Scanner change: add plugin.json to `_SKILL_FILES`

`github.py` line `_SKILL_FILES = {"SKILL.md", "skill.md", "CLAUDE.md", "README.md", "package.json", "pyproject.toml"}` → add `"plugin.json"`.

One extra file fetched per skill directory. At ~2–5 KB per plugin.json, negligible cost.

### `discover()`: plugin.json as skill dir marker

Currently `discover()` only adds a directory to `skill_file_dirs` when it contains `SKILL.md`, `skill.md`, or `CLAUDE.md`. Add `plugin.json` as a fourth marker. A directory containing a plugin.json but no SKILL.md is a valid skill directory (e.g. a Codex-only plugin).

### MetadataExtractor: parse plugin.json

New method `_parse_plugin_json(files: dict) -> dict` parses `files["plugin.json"]` if present. Extracted fields fed into existing extraction methods:

| plugin.json field | Extraction method | Maps to |
|---|---|---|
| `keywords` | `_extract_keywords()` | keywords → labels (existing pipeline) |
| `agents` | `_extract_agents()` | `agent_count`, `agent_names` |
| `mcp-servers` | `_extract_mcp()` | `has_mcp_server` |
| `skills` (string form `"./skills"`) | `_extract_skills_type()` | `has_scripts` (if dir contains scripts/) |
| `compatible_platforms` | `_extract_platforms()` override | `compatible_platforms` direct |
| `author.name`, `author.email` | `_extract_author()` | `author` string |
| `name`, `description`, `version`, `license` | existing methods | already extracted from SKILL.md; plugin.json as fallback |

Priority rule: SKILL.md frontmatter takes precedence over plugin.json for `name`, `description`, `version`. plugin.json wins for structural metadata (agents, MCP, scripts, author, keywords).

### Structural auto-labels

In `skill_repository.create()`, after the existing keyword→label block, add structural label derivation:

```python
auto_labels = []
if scan_result.agent_count > 0:
    auto_labels.append("multi-agent")
if scan_result.has_mcp_server:
    auto_labels.append("mcp")
if scan_result.has_scripts:
    auto_labels.append("has-scripts")
```

Applied with `applied_by: "system"` — same mechanism as keyword labels today. Idempotent (DuplicateKeyError silently skipped).

### Directory-form skills: `"skills": "./skills"`

When plugin.json `skills` field is a string (not array), record it as a directory path. `has_scripts` is set to `True` if the resolved directory path contains any `.py`, `.js`, `.sh`, `.ts` files visible in the repo tree. The tree walk is already available from `discover()` output.

No need to fetch every file in the directory at scan time — just check for the presence of script-extension files in the tree blob list.

### New `Skill` model fields

```python
agent_count: int = 0
agent_names: List[str] = Field(default_factory=list)
has_mcp_server: bool = False
has_scripts: bool = False
author: Optional[str] = None          # "Name <email>" or just "Name"
```

All nullable/defaulted — additive change, no migration required.

### New `SkillScanSnapshot` fields

Mirror the same fields on `SkillScanSnapshot` so the submit preview form can show component metadata to the submitter before registration.

### API exposure

Add new fields to `SkillOut` and `SkillListOut` schemas. Surface as badges/facets on skill cards and detail page (frontend work tracked separately or as a sub-item here).

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `_SKILL_FILES` constant | Modify | Add `"plugin.json"` |
| `GitHubScanner.discover()` | Modify | Add `plugin.json` as skill dir marker |
| `MetadataExtractor` | Modify | Parse plugin.json; extract agents, MCP, platforms, author, keywords, scripts flag |
| `SkillScanSnapshot` | Modify | Add `agent_count`, `agent_names`, `has_mcp_server`, `has_scripts`, `author` |
| `Skill` model | Modify | Add same five fields |
| `skill_repository.create()` | Modify | Derive + apply structural auto-labels from scan result |
| `skill_repository.refetch()` | Modify | Update `agent_count`, `agent_names`, `has_mcp_server`, `has_scripts` if plugin.json changes |
| `SkillOut` / `SkillListOut` | Modify | Expose new fields |
| plugin.json schema docs | New | Document canonical AKH plugin.json format aligned with marketplace |

---

## ADRs

### ADR-001: plugin.json as the structural source of truth, SKILL.md as behavioral source of truth

**Status:** Accepted

**Context:** Both plugin.json and SKILL.md can carry `name`, `description`, `version`. For structural metadata (agents, MCP, scripts, platforms), plugin.json is the only source. For the skill's behavioral instructions (what Claude does when invoked), SKILL.md is the authoritative source.

**Decision:** SKILL.md frontmatter wins for `name`, `description`, `version` when present. plugin.json used as fallback for those fields and as primary source for all structural fields.

**Consequences:** Authors who put metadata in SKILL.md see it respected. Authors who only write plugin.json (e.g. Codex-only plugins without SKILL.md) still get metadata registered correctly.

---

### ADR-002: Auto-labels derived from structure, not declared by author

**Status:** Accepted

**Context:** Authors could be asked to manually tag `mcp` or `multi-agent`, but they might forget, and the catalog has ground truth in the plugin.json structure anyway.

**Decision:** `mcp`, `multi-agent`, `has-scripts` are system-applied labels at registration, derived deterministically from plugin.json structure. Authors don't declare them; they're computed.

**Consequences:** Labels stay accurate even if authors forget to tag. Labels update on `refetch()` if plugin.json structure changes.

---

### ADR-003: `has_scripts` inferred from file extensions, not stored file content

**Status:** Accepted

**Context:** Storing full directory trees would be expensive. We only need to know if scripts exist.

**Decision:** During `discover()`, the repo tree blob list (already fetched) is scanned for `.py`, `.js`, `.ts`, `.sh` files within the skill_path subtree. No extra API call needed.

**Consequences:** `has_scripts` may be `True` for scripts outside the `skills/` dir (e.g. `scripts/` at plugin root). Acceptable — if the plugin ships any scripts, the label applies.

---

## Trade-offs

```
Choice: Fetch plugin.json in the existing _SKILL_FILES pass (1 extra file per skill dir)
  + No extra API round-trips; fits the existing pattern cleanly
  - plugin.json may be larger than SKILL.md (~5KB vs ~2KB); tiny cost
  Decision: Accept. Negligible at current scale.

Choice: Auto-labels vs explicit label fields
  + Auto-labels: reuse existing label/filter infrastructure; no new UI needed
  - Auto-labels: users may not expect to filter by "multi-agent"; pollutes label namespace
  Decision: Use system-applied labels with applied_by="system". Admin can always remove/rename labels.

Choice: Store agent_names as array vs comma-joined string
  + Array: enables future filtering/faceting by specific agent name
  - String: simpler; no use case for per-agent filtering yet
  Decision: Array. Future-friendly, no cost today.
```

---

## Delivery Slices

**Slice 1 — Scanner + MetadataExtractor**
- Add `plugin.json` to `_SKILL_FILES`
- `discover()` recognizes `plugin.json` as skill dir marker
- `MetadataExtractor` parses plugin.json; populates new fields on `SkillScanSnapshot`

**Slice 2 — Model + registration pipeline**
- Add 5 new fields to `Skill` model
- `skill_repository.create()`: propagate scan result → model fields; apply structural auto-labels
- `skill_repository.refetch()`: update structural fields if plugin.json changed

**Slice 3 — API + schema exposure**
- Add new fields to `SkillOut`, `SkillListOut`
- Surface component badges on skill card + detail page (frontend)

**Slice 4 — Plugin.json format docs**
- Document canonical AKH plugin.json format with all supported fields
- Update `/agent-knowledge-hub validate` validator expectations (in #020)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| plugin.json missing from many existing skills | High | Low | All new fields default to zero/false/None; no regression |
| Malformed plugin.json causes scan failure | Medium | Low | Parse errors caught silently; fields default to empty; log warning |
| `multi-agent` / `mcp` labels pollute label namespace | Low | Low | System labels can be filtered from public label lists if needed |
| Directory-form `"skills"` path outside skill_path | Low | Medium | Resolve path relative to plugin.json location; log warning if outside subtree |

---

## Implementation Checklist

- [ ] Add `"plugin.json"` to `_SKILL_FILES`
- [ ] `discover()`: add `plugin.json` as fourth skill dir marker
- [ ] `MetadataExtractor._parse_plugin_json()`: keywords, agents, MCP, platforms, author, dir-form skills
- [ ] `MetadataExtractor._extract_platforms()`: plugin.json explicit list overrides heuristic inference
- [ ] `MetadataExtractor._extract_keywords()`: merge SKILL.md + plugin.json keywords
- [ ] `SkillScanSnapshot`: add `agent_count`, `agent_names`, `has_mcp_server`, `has_scripts`, `author`
- [ ] `Skill` model: add same five fields
- [ ] `skill_repository.create()`: propagate new scan fields + apply structural auto-labels
- [ ] `skill_repository.refetch()`: update structural metadata fields
- [ ] `SkillOut` / `SkillListOut`: expose new fields
- [ ] Frontend: component badges on skill card (agent count, MCP badge, scripts badge)
- [ ] Tests: plugin.json parsing, auto-label derivation, discover() with plugin.json-only dirs
- [ ] Plugin.json schema documentation

---

## Definition of Done

- [ ] Skills with `plugin.json` keywords have those keywords applied as labels at registration
- [ ] Skills with `"agents"` in plugin.json show agent count in catalog; `multi-agent` label auto-applied
- [ ] Skills with `"mcp-servers"` show MCP badge; `mcp` label auto-applied
- [ ] `discover()` finds skill directories that contain only plugin.json (no SKILL.md)
- [ ] `compatible_platforms` populated from plugin.json explicit declaration
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

- **#017 (Commit pinning):** No dependency; both add fields to `Skill` model independently.
- **#018 (Skill file cache):** No dependency; both add fields to `Skill` model independently.
- **#020 (Installer extension):** Installer needs to handle directory-form `"skills"` and `compatible_platforms` — the canonical plugin.json format documented here is the spec #020 implements against.
- **#004 (Multi-source scanner):** Any scanner abstraction built in #004 inherits the plugin.json parsing logic developed here.
