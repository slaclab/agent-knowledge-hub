# TODO #026 — Package-Embedded Skill Discovery: `.agents/skills/` Convention

> **Priority:** 🟢 P3 — Low
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-06-02
> **Shipped:** —
> **Depends on:** —

---

## Problem Statement

Python and npm packages are beginning to ship skills directly inside their package source trees under a `.agents/skills/` directory convention. For example, FastAPI ships:

```
site-packages/fastapi/.agents/skills/fastapi/SKILL.md
```

Claude Code auto-loads skills found at this tier whenever the package is installed in the active project environment. This constitutes a **third skill discovery tier**, alongside:

- Global: `~/.claude/skills/`
- Project-local: `.claude/skills/`
- Package-embedded: `<package-root>/.agents/skills/`

AKH's GitHub scanner currently only looks for skill files at the repository root and inside `.claude-plugin/` directories. It does not recurse into package source trees for `.agents/` directories. As a result:

1. **Package-embedded skills are invisible in the catalog** — a user who has FastAPI installed gains FastAPI's skill automatically but has no way to discover this from AKH.
2. **No provenance link** — the catalog cannot tell a user "if you `pip install fastapi`, this skill is auto-loaded." That relationship is implicit and undiscoverable.
3. **No filter surface** — users cannot ask "what skills do I already have, given my `requirements.txt`?" because the catalog has no concept of package embedding.
4. **Scanner gap widens over time** — as more packages adopt this pattern, AKH's coverage of the real skill ecosystem degrades silently.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| Repo contains `.agents/skills/foo/SKILL.md` | Skill not found; directory not scanned | Skill discovered and registered with `embedded_in_package: true` |
| Package ships `.agents/skills/` with multiple skill dirs | All missed | Each sub-directory registered as a separate embedded skill |
| User views a skill detail page for an embedded skill | No context about package origin | Banner: "This skill is automatically available when `fastapi` is installed" |
| User wants to filter catalog by already-available skills | Not possible | Filter by `embedded_in_package` narrows to package-sourced skills |
| `pyproject.toml` / `package.json` already fetched at scan time | Package name available but unused for this purpose | `package_name` extracted from manifest and stored on skill record |

---

## Goals

1. Extend `GitHubScanner.discover()` to find `.agents/skills/**/SKILL.md` paths in addition to existing skill file patterns
2. Identify that a repo is a Python or npm package by checking for `pyproject.toml`, `setup.py`, or `package.json` — files already fetched by `_SKILL_FILES` — and extract the canonical package name
3. Register each discovered embedded skill with `embedded_in_package: true` and a populated `package_name` field
4. Surface a contextual notice on the skill detail page: "This skill is automatically available when `<package>` is installed"
5. Add an `embedded_in_package` filter facet to the catalog so users can browse skills they may already have without knowing it

## Non-Goals

- Scanning installed site-packages on a live Python environment (AKH is a GitHub-based catalog, not a runtime introspection tool)
- Tracking which version of a package first introduced a given skill (version pinning is #017)
- Detecting `.agents/` directories at arbitrary nesting depths beyond the package convention (only one level inside repo root or package root)
- Supporting non-GitHub sources (separate, #004)
- npm workspaces or monorepo sub-packages (first-class support deferred; basic case is root `package.json`)

---

## Design

### Scanner change: add `.agents/skills/` to discovery paths

`GitHubScanner.discover()` currently builds a candidate directory list from the repo tree by matching against known skill file names (`_SKILL_FILES`). The change adds a second pass: any path matching `.agents/skills/*/SKILL.md` (or `.agents/skills/*/CLAUDE.md`) is treated as a skill directory root, where the directory is `.agents/skills/<skill-name>/`.

This path is already present in the GitHub tree blob list fetched during `discover()`. No extra API call is needed — only an additional pattern match over the existing tree.

### Package identification: reuse already-fetched manifests

`_SKILL_FILES` already includes `pyproject.toml`, `package.json`, and `setup.py`. When those files are present in the fetched file set for the repo root, the scanner already has access to them. A new helper `_extract_package_name(files: dict) -> Optional[str]` reads them in priority order:

1. `pyproject.toml` → `project.name` (PEP 621) or `tool.poetry.name`
2. `setup.py` → regex match on `name=` argument (best-effort; not always static)
3. `package.json` → `name` field

If none yield a name, `package_name` is left null and the skill is still registered with `embedded_in_package: true`.

### New `Skill` model fields

```python
embedded_in_package: bool = False
package_name: Optional[str] = None   # e.g. "fastapi", "anthropic"
```

Both nullable/defaulted — additive change, no migration required.

### New `SkillScanSnapshot` fields

Mirror the same fields on `SkillScanSnapshot` so the submit preview can surface the package origin to the submitter before registration.

### Auto-label at registration

Apply a system label `package-embedded` (via `applied_by: "system"`) for all skills where `embedded_in_package: true`. This allows label-based filtering without requiring a dedicated schema migration for the filter UI — the existing label filter infrastructure already works.

A second label `python-package` or `npm-package` is applied based on which manifest was detected.

### Skill detail page notice

When `embedded_in_package: true`, the frontend renders an informational banner above the skill description:

> This skill is embedded in the **`<package_name>`** package and is automatically loaded by Claude Code when that package is installed.

When `package_name` is null, the notice reads:

> This skill is embedded inside a package and may be automatically loaded by Claude Code when the package is installed.

### Catalog filter

Add `embedded_in_package` as a boolean facet filter alongside the existing label and platform filters. Implemented as a query parameter on `GET /skills?embedded_in_package=true`. The frontend exposes this as a checkbox in the filter sidebar: "Show only package-embedded skills."

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `GitHubScanner.discover()` | Modify | Match `.agents/skills/*/SKILL.md` paths in tree blob list as skill dir candidates |
| `_extract_package_name()` | New helper | Parse `pyproject.toml` / `package.json` / `setup.py` → package name string |
| `MetadataExtractor` | Modify | Populate `embedded_in_package`, `package_name` on `SkillScanSnapshot` when `.agents/` path detected |
| `SkillScanSnapshot` | Modify | Add `embedded_in_package: bool`, `package_name: Optional[str]` |
| `Skill` model | Modify | Add same two fields |
| `skill_repository.create()` | Modify | Propagate new scan fields; apply `package-embedded` and language auto-labels |
| `skill_repository.refetch()` | Modify | Update `embedded_in_package`, `package_name` if manifest changes |
| `SkillOut` / `SkillListOut` | Modify | Expose new fields in API response |
| `GET /skills` query params | Modify | Add `embedded_in_package: bool` filter |
| Frontend: skill detail | Modify | Render package-origin banner when `embedded_in_package: true` |
| Frontend: catalog filter sidebar | Modify | Add "Package-embedded" boolean facet |

---

## ADRs

### ADR-001: Detect package type at the repo level, not the skill level

**Status:** Accepted

**Context:** A repo may ship multiple `.agents/skills/` sub-directories, each a separate skill. The package identity (name, ecosystem) belongs to the repo, not to any individual skill within it. Detecting the package once per repo and stamping all its embedded skills is cleaner than re-detecting per skill directory.

**Decision:** Package identification (`pyproject.toml` / `package.json` detection) runs once per repo scan. The resulting `package_name` and `embedded_in_package` flag are propagated to all skill scan snapshots produced from that repo's `.agents/skills/` paths.

**Consequences:** If a repo contains both a top-level SKILL.md (a standalone skill) and a `.agents/skills/` directory (embedded skills), only the `.agents/skills/` skills receive `embedded_in_package: true`. The top-level skill does not, even if the repo is a package. This is the correct semantic: the top-level skill is an explicit, independently-distributed skill; the embedded ones are the auto-load package behavior.

---

### ADR-002: Use the existing label system for `package-embedded` filtering, not a dedicated boolean facet schema

**Status:** Accepted

**Context:** Adding a true boolean facet in the API and filter UI requires schema work in the query layer. The label system already supports arbitrary string tags with filter-by-label infrastructure.

**Decision:** Apply a system label `package-embedded` at registration. The filter sidebar renders this as a checkbox by detecting the well-known label name — no schema change to the filter API is required. The `embedded_in_package` boolean field is also stored on the model for programmatic use.

**Consequences:** The label appears in the public label list alongside author-declared labels. Filter it from the general label browse UI using the `applied_by: "system"` flag (already used for `mcp`, `multi-agent` labels from #019).

---

### ADR-003: `.agents/skills/` path depth is fixed at one level below `.agents/skills/`

**Status:** Accepted

**Context:** The FastAPI convention is `.agents/skills/<skill-name>/SKILL.md` — exactly one directory level between `.agents/skills/` and the SKILL.md. Deeper nesting is not part of the current convention.

**Decision:** Only match paths of the form `.agents/skills/<one-level>/SKILL.md`. Do not recurse further. If the convention evolves to support deeper nesting, this can be relaxed in a follow-up.

**Consequences:** A package that accidentally nests skills two levels deep (`.agents/skills/group/skill/SKILL.md`) will not be discovered. Acceptable at current adoption stage — keep it simple and revisit if the convention drifts.

---

## Trade-offs

```
Choice: Detect embedded skills via tree blob pattern vs. explicit directory listing API call
  + Tree blob: no extra API call; tree already fetched in discover(); fast
  - Tree blob: relies on GitHub tree depth limit (recursive=1 fetches all paths); very large repos truncate
  Decision: Use tree blob. Repos large enough to hit truncation limits are unusual for package authors.
    Add a warning log if the tree is flagged as truncated.

Choice: Store package_name from manifest vs. derive from repo name
  + Manifest: accurate; matches what users `pip install <name>` or `npm install <name>`
  - Manifest: setup.py name is not always statically parseable; may be None
  Decision: Manifest-first with repo-name fallback only if manifest yields nothing.
    Repo name is a reasonable approximation (e.g. github.com/encode/httpx → "httpx").

Choice: Boolean `embedded_in_package` field vs. new `skill_source_type` enum
  + Boolean: minimal change; clear semantics for the current single variant
  - Boolean: if other auto-load tiers emerge (e.g. VS Code extensions), we'd add more booleans
  Decision: Boolean for now. A `source_type` enum can subsume it in a future refactor when
    there are multiple auto-load tiers to distinguish.

Choice: System label `package-embedded` vs. dedicated filter facet
  + System label: zero extra schema work; reuses existing label filter UI
  - System label: clutters label list if not properly suppressed from public browse
  Decision: System label (applied_by="system"), suppressed from public label browse, surfaced
    as a named checkbox in the filter sidebar. Same pattern as `mcp`, `multi-agent` (#019).
```

---

## Delivery Slices

**Slice 1 — Scanner: `.agents/` path detection**
- Extend `discover()` to match `.agents/skills/*/SKILL.md` and `.agents/skills/*/CLAUDE.md` in tree blob
- Implement `_extract_package_name()` helper
- Populate `embedded_in_package` and `package_name` on `SkillScanSnapshot`

**Slice 2 — Model + registration pipeline**
- Add `embedded_in_package`, `package_name` to `Skill` model
- `skill_repository.create()`: propagate fields + apply `package-embedded` and language auto-labels
- `skill_repository.refetch()`: update fields if manifest or `.agents/` structure changes

**Slice 3 — API filter**
- Expose `embedded_in_package`, `package_name` in `SkillOut` / `SkillListOut`
- Add `embedded_in_package` query param to `GET /skills`

**Slice 4 — Frontend**
- Package-origin banner on skill detail page
- "Package-embedded" facet checkbox in catalog filter sidebar

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Very few repos currently use `.agents/skills/` convention | High | Low | Feature is additive; zero impact if no repos match |
| `pyproject.toml` name not parseable (dynamic / computed) | Medium | Low | Fall back to `None`; skill still registers with `embedded_in_package: true` |
| GitHub tree truncation on large repos hides `.agents/` paths | Low | Low | Log warning; re-scan can be triggered manually; most package repos are small |
| Convention evolves (different path, different filename) | Medium | Medium | Parameterise path pattern as a constant; easy to update |
| `package-embedded` label clutters public label browse | Low | Low | `applied_by="system"` flag allows suppression; same pattern already in use |

---

## Implementation Checklist

- [ ] `GitHubScanner.discover()`: add `.agents/skills/*/SKILL.md` and `.agents/skills/*/CLAUDE.md` as skill dir markers
- [ ] `_extract_package_name(files: dict) -> Optional[str]`: parse `pyproject.toml` → `project.name` / `tool.poetry.name`, `package.json` → `name`, `setup.py` → regex fallback
- [ ] `MetadataExtractor`: detect `.agents/skills/` path origin; set `embedded_in_package = True`, `package_name` from helper
- [ ] `SkillScanSnapshot`: add `embedded_in_package: bool = False`, `package_name: Optional[str] = None`
- [ ] `Skill` model: add same two fields
- [ ] `skill_repository.create()`: propagate `embedded_in_package`, `package_name`; apply `package-embedded` system label; apply `python-package` or `npm-package` label based on manifest type
- [ ] `skill_repository.refetch()`: update `embedded_in_package`, `package_name`
- [ ] `SkillOut` / `SkillListOut`: expose new fields
- [ ] `GET /skills`: add `embedded_in_package: Optional[bool]` query filter
- [ ] Frontend: package-origin banner on skill detail page (conditional on `embedded_in_package`)
- [ ] Frontend: "Package-embedded" facet checkbox in catalog filter sidebar
- [ ] Tests: `.agents/` path detection in `discover()`, `_extract_package_name()` for pyproject.toml + package.json, auto-label application, filter query param
- [ ] Log warning when GitHub tree response is truncated

---

## Definition of Done

- [ ] A GitHub repo containing `.agents/skills/foo/SKILL.md` is discovered and registered as a skill with `embedded_in_package: true`
- [ ] `package_name` is populated from `pyproject.toml` or `package.json` when present
- [ ] Skill detail page shows the package-origin banner for embedded skills
- [ ] `GET /skills?embedded_in_package=true` returns only package-embedded skills
- [ ] `package-embedded` system label is applied and surfaced as a filter facet in the catalog UI
- [ ] Existing skills (not in `.agents/` paths) are unaffected: `embedded_in_package` defaults to `false`
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

- **#004 (Multi-source scanner):** Any scanner abstraction built in #004 should inherit the `.agents/` path pattern as a first-class discovery strategy alongside existing patterns.
- **#017 (Commit pinning):** Package-embedded skills should be pinnable to a package version the same way any skill can be pinned to a commit. No dependency; independent additive fields.
- **#019 (plugin.json scan pipeline):** The `_SKILL_FILES` set and `MetadataExtractor` patterns established in #019 are the extension points for this work. Builds on top of, does not conflict with.
- **#023 (MCP server registry):** Packages may also embed MCP server configs in `.agents/`. Out of scope here but the discovery mechanism established in this task is the natural precursor.
