# 010 — Document-to-Skill Conversion

**Status:** ⬜ Open
**Branch:** —

---

## Problem & Goal

**Problem:** When a user submits a GitHub URL pointing to a document that is not a recognised skill file (`SKILL.md`, `skill.md`, `CLAUDE.md`), the backend scan currently returns `no_skill_files: true` and the UI shows a warning: "No skill files found in this directory." The user is left with a blank form and no guidance — even though the document they pointed to (a runbook, SOP, how-to guide, architecture doc, etc.) could be a perfectly valid agent skill with minor reformatting.

**Goal:** When a scan detects a non-skill document at the submitted path, offer the user an explicit conversion flow: preview the document, generate a draft `SKILL.md` (or equivalent metadata), and guide them through submitting it as a skill entry — without requiring them to touch the source repo.

---

## User Stories

1. As a submitter, when I paste a URL to a runbook or SOP, I want the UI to recognise it as a convertible document and offer to register it as a skill, so I don't have to manually create a `SKILL.md` in the repo.
2. As a submitter, I want to preview the auto-generated skill metadata (name, description, compatible platforms) derived from the document before submitting, so I can correct anything the extraction got wrong.
3. As a submitter, I want to optionally generate and open a PR to the source repo that adds the `SKILL.md` alongside the document, so the skill stays versioned with the source material.
4. As an admin, I want converted skills to be clearly tagged with their source document type (runbook, SOP, guide, etc.), so the catalog reflects provenance.

---

## Open Questions

- **Document detection heuristics**: How do we identify that a file is a convertible document vs. just random code?
  - Extension allowlist: `.md`, `.rst`, `.txt`, `.html`
  - Filename patterns: `runbook*`, `*sop*`, `*guide*`, `*procedure*`, `README*` at non-root paths
  - Fallback: any markdown file the user explicitly pointed to
- **Metadata extraction**: Rule-based (parse headings/frontmatter) vs. LLM-assisted (call an AI API to summarise the doc into skill fields). LLM approach gives better results but adds a backend dependency.
- **PR generation**: Out of scope for phase 1 (requires GitHub write token scoped to the user's repo). Defer to a later slice.
- **Skill entry vs. catalog entry**: Should a converted document produce a `skill` entry or a new `entry_type` (e.g. `document_ref`)? Keeping it as a `skill` is simpler; a new type adds filtering flexibility.

---

## Proposed Approach (sketch)

### Phase 1 — Detection + manual conversion UX (low effort)
- In `runScan` response handling: when `no_skill_files: true` AND the scanned path points to a recognised document file (by extension or filename), set a new `convertible_document: true` flag on the scan result (or infer it frontend-side).
- In the submit form: replace the generic "No skill files found" warning with a **"Convert to skill"** card:
  - Shows document filename and a short excerpt (first 200 chars of description if available).
  - Pre-fills Name from the document title, Description from first heading/paragraph.
  - Adds a `source_document` label automatically.
  - User edits metadata and submits normally.

### Phase 2 — LLM-assisted metadata extraction (medium effort)
- Backend adds a `POST /api/github-scan/convert` endpoint that accepts a raw document URL, fetches the content, and returns extracted `name`, `description`, `compatible_platforms` fields.
- Frontend calls this endpoint after the user clicks "Convert to skill", then populates the form.

### Phase 3 — PR generation (deferred)
- After submit, offer "Open a PR to add SKILL.md to this repo."
- Requires GitHub OAuth write scope for the submitter — significant auth work.

---

## Definition of Done

- [ ] Backend scan result includes a signal when the path points to a document with no skill files (already partially present via `no_skill_files`)
- [ ] Submit form detects a convertible document and renders a "Convert to skill" prompt instead of the generic warning
- [ ] Pre-fills Name and Description from document metadata where available
- [ ] Automatically applies a `source-document` label to the submitted skill
- [ ] Phase 2: `/api/github-scan/convert` endpoint extracts metadata from document content
- [ ] Phase 3: post-submit PR generation flow (deferred)
