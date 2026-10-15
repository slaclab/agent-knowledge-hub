# TODO #047 — marketplace.json Route That Claude Code Can Reach

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Problem Statement

`README.md` and `PRD.md` tell users to register the catalog with `/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json`. That URL answers 401 to a request without a bearer token: Cogito measured 401 with `WWW-Authenticate: Bearer realm="S3DF"` on 2026-10-05, and #006 recorded a 401 for an anonymous GET on 2026-10-14 (Measured facts). Claude Code sends a token to a URL marketplace only through `headers` or a `headersHelper` declared in an `extraKnownMarketplaces` entry, and `claude plugin marketplace add` cannot set either (Measured facts). The documented step therefore fails for every user, in a Cogito session or not.

The backend does not produce that 401. `marketplace_json` in `backend/app/routers/catalog.py` takes no user dependency, and `create_app` in `backend/app/main.py` adds only rate-limit and CORS middleware. Neither `no_token` nor `WWW-Authenticate` appears under `backend/app`, `frontend/app`, `frontend/lib`, or `kubernetes/`. The `Makefile` applies the overlays named by `DEV_OVERLAY` and `PROD_OVERLAY`, which live outside this repository, so the rule that answers 401 is not visible here. Unknown: which component in front of the backend answers it.

The Cogito deployment (`slaclab/cogito`, TODO #200) files this task as hub request H-3, for its Open Question 3. Until a route works, Cogito's user documentation says that the README's marketplace step answers 401 from a session and points users to the `/agent-knowledge-hub` client instead.

### What fails today

As of 2026-10-14:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A user runs the README's `/plugin marketplace add` step | 401 without a token; Claude Code sends none for a marketplace added this way | The marketplace is added |
| A user requests `/marketplace.json` | `redirects()` in `frontend/next.config.mjs` answers a permanent redirect to `/cli/api/marketplace.json`; in this repository's manifests, `/` is behind the Vouch browser sign-in (`ingress-frontend.yaml`) | The documented URL reaches the manifest without a browser |
| A user looks for another marketplace | #021's target, `slaclab/slac-agent-plugin-marketplace`, is not anonymously readable (Measured facts) | One documented route works |

---

## Goals

1. A user following `README.md` can add the catalog as a Claude Code marketplace and install from it, on an S3DF node or in a Cogito session, without a browser.

## Non-Goals

- What each plugin entry installs. That is #046.
- Publishing into `slaclab/slac-agent-plugin-marketplace`. That is #021.

---

## Requirements

### Functional

- **FR-1:** Claude Code can reach the catalog's `marketplace.json` at a documented URL: a route that Claude Code fetches successfully from an S3DF node and from a Cogito session, with no browser sign-in.
- **FR-2:** `README.md` and `PRD.md` give the steps that work and drop the `/plugin marketplace add` step that answers 401.
- **FR-3:** If the route keeps the token (Open Design Question 1, option B), the helper that supplies it follows #050's FR-2 and FR-3 and sends the token for this catalog's URL only.

### Acceptance Criteria

- **AC-1:** Given Claude Code with no browser session, when a user follows the steps in `README.md`, then the marketplace `SLAC-Agent-Knowledge-Hub` is added, and `/plugin install agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` installs the client.
- **AC-2:** Given the same steps run in a Cogito session, then AC-1's outcome holds.
- **AC-3:** Under option B, given an expired token, when Claude Code refreshes the marketplace, then the error the user sees is recorded in this file, and `README.md` names it beside the renewal steps of #050's FR-7.

### Definition of Done

- [ ] The route chosen under Open Design Question 1, and the reason, recorded in this file
- [ ] AC-1 to AC-3 checked by hand and recorded with the Claude Code version used
- [ ] `README.md` and `PRD.md` updated; CHANGELOG entry

---

## Open Design Questions

1. **Which route.**
   - **A. Serve `marketplace.json` without a token.** Users keep the one-line `/plugin marketplace add`. The cost is disclosure: the manifest lists every active entry of type `skill`, `internal` ones included, with name, description, and repository, so anyone who can reach the host reads the internal catalog's metadata. The rule that answers 401 is not in this repository, so option A also needs a change wherever that rule lives.
   - **B. Keep the token and document an `extraKnownMarketplaces` entry whose `headersHelper` prints the bearer header.** The internal catalog stays behind sign-in. The cost falls on each user, who edits their Claude Code settings and keeps a helper script, and on the helper, which must meet FR-3. Cogito's Open Question 3 recommends this route for its sessions once #046 ships. How Claude Code tells a marketplace `headersHelper` which URL it serves was not checked.
2. **Which URL to document.** Whether Claude Code follows the permanent redirect from `/marketplace.json` was not checked. Documenting `/cli/api/marketplace.json` directly avoids the redirect and, in this repository's manifests, the Vouch-gated frontend ingress.

---

## Measured facts — read 2026-10-14, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| `/marketplace.json` without a token | 401 with `WWW-Authenticate: Bearer realm="S3DF"` | Cogito TODO #200 › Measured facts, `curl -D -`, 2026-10-05 |
| The same, later | 401 for an anonymous GET | #006 › Follow-ups › Outside this task, 2026-10-14 |
| CLI paths without a token | 401 `{"error":"no_token"}` | #006 › Measured facts › cli-auth |
| Claude Code and URL marketplaces | A `url` marketplace source accepts `headers` and a `headersHelper` command (Claude Code 2.1.238 or later); `claude plugin marketplace add` cannot set either, so the route is an `extraKnownMarketplaces` entry | Recorded in Cogito TODO #200 from the Claude Code `plugins/marketplace-reference` documentation; not re-checked here |
| `slaclab/slac-agent-plugin-marketplace` | Not anonymously readable: `fatal: could not read Username for 'https://github.com': terminal prompts disabled` | Cogito TODO #200 › Measured facts, `git ls-remote` with prompts disabled, 2026-10-05 |
| Backend authentication on this route | None: `marketplace_json` has no `Depends`, and `create_app` adds `SlowAPIMiddleware` and `CORSMiddleware` only | Read `backend/app/routers/catalog.py` and `backend/app/main.py` |
| Ingress in this repository | `/cli(/\|$)(.*)` goes to the backend with no authentication annotation (`ingress-api.yaml`); `/` goes to the frontend behind Vouch's `auth-url` (`ingress-frontend.yaml`) | Read `kubernetes/overlays/prod/` |

---

## Relationship to Other Tasks

- **Cogito TODO #200 (`slaclab/cogito`), hub request H-3:** answers Cogito's Open Question 3. No Cogito slice waits for it; when it ships with #046, Cogito's user documentation can name a marketplace route instead of the 401.
- **#046 (`git-subdir` plugin sources):** makes the entries install the right content once the route is reachable.
- **#050 (Client token helper):** option B's helper needs the same token rules.
- **#021 (Marketplace monorepo publish):** not a fallback, because its target repository is not anonymously readable.
- **#007 (`/agent-knowledge-hub` skill):** introduced the README's marketplace step.
