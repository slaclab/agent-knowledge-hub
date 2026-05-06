# TODO #018 — Skill File Cache (SKILL.md + README display storage)

> **Priority:** 🟡 P2 — Medium
> **Status:** 🏁 Implementation Done
> **Branch:** main
> **PR:** —
> **Created:** 2026-05-05
> **Shipped:** 2026-05-05 (`bb6df03`)
> **Depends on:** — (Slice 2 `pin()` integration is enhanced by #017 but all other slices are independent)

---

## Problem Statement

The catalog stores `readme_html` (rendered HTML fetched at latest HEAD) but not the raw skill instruction file (SKILL.md / CLAUDE.md). This has three consequences:

1. **README drifts** — `readme_html` is fetched from HEAD, not the pinned commit, so what users read in the catalog can differ from what they actually install.
2. **Skill instructions invisible** — the SKILL.md that defines exactly how the skill behaves is not displayed anywhere in the catalog; users have to click through to GitHub to read it.
3. **No version diff** — there is no way to show what changed between pin updates, making the revision history (#013) metadata-only with no content context.

### What fails today

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| "What does this skill do?" | Read readme (may lag behind installed version) | See SKILL.md content inline, at pinned commit |
| "What changed in the latest update?" | No diff available | Visual diff of SKILL.md between previous and current pin |
| README vs installed version | readme_html fetched from HEAD | README stored at same commit as pinned install |
| Internal skill file exposure | readme_html served to all (unauthenticated) | File content gated behind auth for internal skills |

---

## Goals

1. Store raw SKILL.md (or CLAUDE.md) content at the pinned commit in the `Skill` document
2. Store raw README markdown at the pinned commit (replacing the current HEAD-fetched `readme_html`)
3. Display both README and SKILL.md on the skill detail page in a **tabbed interface** (README tab + Skill Instructions tab)
4. Show a visual diff of SKILL.md between the previous and current pin on the revision history view
5. Gate file content behind authentication for internal (`visibility: internal`) skills

## Non-Goals

- Serving stored files as install artifacts — **install always goes direct to GitHub at `?ref=<pinned_sha>`**
- Storing all component files listed in plugin.json (commands, agents, etc.)
- Storing plugin.json contents (manifest metadata already captured in the Skill document fields)
- Full-text search of SKILL.md content (possible follow-on, not in this task)

---

## Design

### What to store

| Field | Content | Source |
|---|---|---|
| `skill_md_raw` | Raw markdown of SKILL.md / CLAUDE.md | `RawScanResult.files` — already fetched at scan time |
| `skill_md_filename` | Which file was found: `"SKILL.md"`, `"CLAUDE.md"`, etc. | Same |
| `readme_raw` | Raw README markdown | `RawScanResult.files["README.md"]` — already fetched |

`readme_html` **retained** for now — it powers the current detail page. Once the frontend switches to rendering `readme_raw` locally (via react-markdown), `readme_html` can be dropped in a follow-up. Both fields populated during the transition.

### Storage size

SKILL.md: ~2–20 KB. README raw markdown: ~5–50 KB. Well within MongoDB's 16 MB document limit. At 1,000 skills with 10 revisions each: ~500 MB in revision snapshots — manageable.

### Relationship to #017 (commit pinning)

Content is populated/updated at the same moments as `pinned_commit_sha`:
- **`create()`** — populate from `RawScanResult.files` (already in memory during submission)
- **`pin()`** (#017) — re-fetch files at new pinned SHA, update both `skill_md_raw` and `readme_raw`
- **`refetch()`** — update `readme_raw` only (keeps README fresh alongside metadata; does NOT advance `skill_md_raw`, which stays at pinned commit)

### Diff via revision snapshots

`revision_service.record()` snapshots the full `Skill` document. Once `skill_md_raw` is a field on `Skill`, it is automatically included in every revision snapshot. The frontend diff view reads two revision snapshots and diffs their `skill_md_raw` values — no extra storage or backend work required.

### Access control for internal skills

`readme_html` is currently served unauthenticated for all skills, including internal ones — this is a latent bug. With this task:

- `GET /api/skills/<slug>` — for `visibility: internal` skills, omit `skill_md_raw`, `readme_raw`, and `readme_html` from the response unless the caller is authenticated (SLAC user)
- `GET /api/skills/<slug>/revisions` — same gate; omit snapshot content for internal skills when unauthenticated

### API changes

**`GET /api/skills/<slug>` response** — add fields:
```json
{
  "skill_md_raw":    "---\nname: my-skill\n...",
  "skill_md_filename": "SKILL.md",
  "readme_raw":      "# My Skill\n\nDoes X...",
  "readme_html":     "<h1>My Skill</h1>..."
}
```
For `visibility: internal` + unauthenticated caller: all four fields omitted (null).

**No new endpoints required.** Content arrives via existing `create` flow and the `pin` action from #017.

---

## Module Design

| Module | Change | Responsibility |
|---|---|---|
| `Skill` model | Modify | Add `skill_md_raw`, `skill_md_filename`, `readme_raw` |
| `SkillOut` / `SkillListOut` schemas | Modify | Expose new fields; apply internal-skill auth gate |
| `skill_repository.create()` | Modify | Populate `skill_md_raw`, `skill_md_filename`, `readme_raw` from `RawScanResult.files` |
| `skill_repository.pin()` (#017) | Modify | Re-fetch and update `skill_md_raw`, `readme_raw` at new pinned SHA |
| `skill_repository.refetch()` | Modify | Update `readme_raw` (and `readme_html` for now) at upstream HEAD |
| `GET /api/skills/<slug>` router | Modify | Gate file content fields for internal skills behind auth |
| Skill detail page (frontend) | Modify | Tabbed interface: **README** tab (renders `readme_raw`) + **Skill Instructions** tab (renders `skill_md_raw`); auth-gate for internal |
| Revision diff view (frontend) | New | Diff `skill_md_raw` between two revision snapshots; rendered side-by-side or inline |

---

## ADRs

### ADR-001: Raw markdown stored, not re-rendered HTML

**Status:** Accepted

**Context:** Currently `readme_html` is fetched as GitHub-rendered HTML. Storing raw markdown instead gives smaller payloads, better diff (semantic text diff vs HTML diff), and removes dependency on GitHub's markdown rendering API.

**Decision:** Store raw markdown for both README and SKILL.md. Render on the frontend via react-markdown (already a common dependency). Retain `readme_html` during transition; drop once frontend is migrated.

**Consequences:** Frontend needs a markdown renderer component. Existing `readme_html`-based display works until migration is complete.

---

### ADR-002: skill_md_raw stored at pinned commit; readme_raw updated on refetch

**Status:** Accepted

**Context:** SKILL.md defines what the skill does — it should be consistent with what's installed (the pinned commit). README is documentation — keeping it current with upstream HEAD is acceptable and expected.

**Decision:** `skill_md_raw` updates only when the pin advances (via #017 `pin()` action). `readme_raw` updates on every `refetch()`. Makes the source of truth for "what this skill does" immutable between explicit updates.

**Consequences:** README may show content slightly ahead of the installed version. SKILL.md in catalog always matches what gets installed.

---

### ADR-003: Internal skill content gated behind auth

**Status:** Accepted

**Context:** Internal skills' content is proprietary. Currently `readme_html` is inadvertently served unauthenticated. Storing richer content makes fixing this more urgent.

**Decision:** For `visibility: internal`, omit all file content fields (`skill_md_raw`, `skill_md_filename`, `readme_raw`, `readme_html`) from API responses for unauthenticated callers. Name, description, labels, and metadata remain public.

**Consequences:** Internal skill detail page requires login to see content. Small UX friction; correct security posture.

---

## Trade-offs

```
Choice: Store readme_raw alongside readme_html (transition period)
  + No frontend regression during migration
  - Doubles README storage temporarily (~25KB per skill)
  Decision: Accept. Drop readme_html in follow-up once frontend migrated to react-markdown.

Choice: Diff at read time (compare two revision snapshots) vs store diffs
  + Read-time: zero extra storage, always accurate
  - Read-time: slightly more work per diff request; large SKILL.md diffs computed in browser
  Decision: Read-time diff. SKILL.md files are small; browser diff is fine. Revisit if perf is an issue.

Choice: Gate ALL internal content vs only file content
  + Gate all: simplest rule, most secure
  - Gate all: public metadata (stars, labels) useful for internal skill discovery
  Decision: Gate file content only (skill_md_raw, readme_raw, readme_html). Metadata stays public.
```

---

## Delivery Slices

**Slice 1 — Backend model + populate at create**
- Add `skill_md_raw`, `skill_md_filename`, `readme_raw` to `Skill` model
- Populate from `RawScanResult.files` in `create()`
- Add fields to `SkillOut`; apply internal-skill auth gate

**Slice 2 — Populate on pin / refetch**
- `pin()` (#017 dependency): re-fetch and store `skill_md_raw`, `readme_raw` at new pinned SHA
- `refetch()`: update `readme_raw` (and `readme_html`)

**Slice 3 — Frontend: tabbed content view**
- Replace current single-content area on skill detail page with a tab bar: **README** | **Skill Instructions**
- README tab: render `readme_raw` via react-markdown (replaces current `readme_html` display)
- Skill Instructions tab: render `skill_md_raw` via react-markdown
- Default to README tab; if `skill_md_raw` is present show tab, otherwise hide it
- Auth-gate for internal skills: show "Sign in to view" placeholder in both tabs when unauthenticated

**Slice 4 — Frontend: diff view**
- Revision history page: diff `skill_md_raw` between selected revisions
- Side-by-side or inline unified diff (e.g. `react-diff-viewer` or `diff` + custom render)

**Slice 5 — README migration**
- Switch detail page README display from `readme_html` to rendered `readme_raw`
- Drop `readme_html` field from model + API (follow-on, low urgency)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| RawScanResult.files missing SKILL.md for some repos | Medium | Low | Fields nullable; detail page shows "No skill file found" |
| Large SKILL.md blows out revision snapshot storage | Low | Low | Cap `skill_md_raw` at 100 KB on write; log and truncate |
| Internal skill content accidentally leaked | Low | High | Auth gate in router layer; integration test for unauthenticated access to internal skill |
| readme_html removal breaks existing installs/API consumers | Low | Medium | Keep readme_html until Slice 5; version the deprecation |

---

## Implementation Checklist

- [x] `Skill` model: add `skill_md_raw`, `skill_md_filename`, `readme_raw`
- [x] `skill_repository.create()`: populate from `RawScanResult.files`
- [ ] `skill_repository.pin()`: re-fetch and update `skill_md_raw`, `readme_raw` at new SHA (blocked on #017)
- [x] `skill_repository.refetch()`: update `readme_raw` (keep `readme_html` during transition)
- [x] `SkillOut` schema: expose new fields
- [x] Router `GET /{slug}`: omit file content for unauthenticated callers on internal skills
- [x] Fix latent bug: also apply auth gate to `readme_html` for internal skills
- [x] Frontend: tabbed interface on detail page — README tab + Skill Instructions tab
- [x] Frontend: README tab renders `readme_raw` via react-markdown (falls back to `readme_html` for old skills)
- [x] Frontend: Skill Instructions tab renders `skill_md_raw` via react-markdown; tab hidden if no content
- [x] Frontend: auth-gated "Sign in to view" placeholder in both tabs for unauthenticated internal skills
- [ ] Frontend: diff view on revision history page (Slice 4 — deferred)
- [x] Backfill script: populate `skill_md_raw` + `readme_raw` for existing skills (`scripts/002_backfill_skill_file_content.py`)
- [x] Tests: auth gate (unauthenticated internal skill returns null content fields) — 10/10 pass

---

## Definition of Done

- [ ] New skills store SKILL.md content + README raw markdown at registration
- [ ] SKILL.md displayed inline on skill detail page
- [ ] Visual diff shown between revisions in revision history
- [ ] Internal skill file content not returned to unauthenticated callers
- [ ] `readme_html` latent auth bug fixed for internal skills
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

- **#017 (Commit pinning):** `pin()` from #017 is where `skill_md_raw` gets re-fetched at a new SHA. Slice 2's `pin()` integration can only be wired up after #017 ships, but all other slices (1, 3, 4, 5) are fully independent of #017 and can ship first.
- **#013 (Revision history):** Diff view builds directly on revision snapshots. Once `skill_md_raw` is in the Skill model it's automatically snapshotted — no extra work in #013.
- **#014 (Provenance tree):** Tree nodes could eventually show a preview of `skill_md_raw` on hover.
