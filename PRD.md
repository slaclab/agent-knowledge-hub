# PRD: Agent Knowledge Hub

**Version:** 0.1 (draft)
**Date:** 2026-04-18
**Status:** Draft

---

## 1. Problem & Goal

**Problem:** There is no central, discoverable catalog for agent skills, MCP servers, and plugins available to SLAC/S3DF users and the broader developer community. Skills live scattered across GitHub repos with no standardized way to find, evaluate, or compare them.

**Goal:** Build a web-based marketplace that indexes agent skills and plugins by reference (GitHub repo URL), allows users to rate and label them, and provides a clean browsable/searchable interface — styled after the simplicity of skills.sh but extended with community metadata. The catalog surfaces knowledge and capabilities, not low-level tools.

**Success metric:**
- At least 20 skills listed within 30 days of launch
- Median time-to-submit a new skill < 5 minutes
- Ratings and labels present on > 50% of listed skills within 60 days

**Out of scope (v1):**
- Hosting or executing skills directly
- Automated skill testing or CI integration
- Billing or monetization
- Semantic/vector search (planned for v2)
- Mobile-native apps
- CLI client (`skills search`, `skills install`) — implemented as `/slac-skills` skill in v1, see Section 15
- **MCP server catalog** — MCP servers are infrastructure, centrally controlled at `mcp.sdf.slac.stanford.edu` (SLAC Agent Gateway) with auth/authz managed by the platform team. Users never configure MCP directly; skills consume gateway knowledge transparently. Skills that depend on gateway knowledge show a "Uses SLAC Agent Gateway" badge on their detail page — no further MCP surface in the catalog UI.

> **Open Question OQ-3:** Should a v2 include a CLI command (e.g. `skills search <query>` or `skills install <slug>`) so scientists can discover and install skills without leaving the terminal? This would significantly improve workflow fit for Claude Code users.

**Constraints:**
- Auth via SLAC VouchProxy / JWT (no separate user account system)
- Deployment on S3DF Kubernetes cluster using standard SLAC mechanisms
- Stack: FastAPI (Python) + Next.js (React) + MongoDB
- No external SaaS dependencies for core functionality

---

## 2. User Stories

### Browsing & Discovery
1. As a developer, I want to browse a list of all available agent skills so that I can discover knowledge and capabilities that may help my work.
2. As a developer, I want to filter skills by label (e.g. "data-analysis", "llm", "web-scraping") so that I can narrow results to my domain.
3. As a developer, I want to search skills by name and description so that I can find something specific quickly.
4. As a developer, I want to sort skills by rating, recency, or GitHub stars so that I can prioritize high-quality options.
5. As a developer, I want to view a skill's detail page (description, repo link, labels, rating, version, license) so that I can decide whether to use it.
6. As a developer, I want to see a skill's README (fetched from GitHub at submission time) on the detail page so that I don't have to leave the site to evaluate it.
7. As a developer, I want to see which AI platforms a skill is compatible with (e.g. Claude, OpenAI, LangChain) so that I know if it works in my stack.
8. As a developer, I want to click through to the source GitHub repo directly so that I can inspect the code or file an issue.
9. As a developer, I want to see other marketplaces (LobeHub, AgentSkill.sh) listed as catalog entries so that the site is a meta-index, not just a walled garden.

### Submitting Skills
10. As a skill author, I want to submit a new skill by providing a GitHub repo URL so that it appears in the catalog.
11. As a skill author, I want to optionally fill in metadata (description, compatible platforms, license, version) so that my skill is well-represented.
12. As a skill author, I want GitHub metadata (repo name, description, stars, last commit, README) to be fetched automatically at submission so that I don't have to duplicate information already on GitHub.
13. As a skill author, I want my SLAC identity attached to the submission automatically (from the auth header/JWT) so that I don't need to fill in author fields manually.
14. As a skill author, I want to edit my own submission after the fact so that I can keep metadata accurate.
15. As a skill author, I want to delete my own submission so that I can remove deprecated or incorrect entries.
16. As a skill author, I want to see a "how to create a skill" guide linked from the submission page so that first-time authors can get started quickly.
17. As a skill author, I want to submit a "marketplace reference" (link to LobeHub, agentskill.sh, etc.) as a top-level catalog entry so that the site surfaces other discovery resources.

### Rating
18. As a user, I want to give a skill a 1–5 star rating so that I can express my experience with it.
19. As a user, I want to update my rating if my opinion changes so that my feedback stays accurate.
20. As a user, I want to see the aggregate star rating and total vote count on every skill card so that I can quickly gauge community opinion.
21. As a user, I should only be able to rate once per skill (one rating per SLAC identity) so that ratings are not gamed.
22. As a user, I want to see my own rating highlighted on a skill I've already rated so that I know I've already voted.

### Labeling
23. As a user, I want to add a free-form label to any skill so that I can help others find it through better categorization.
24. As a user, I want to see all labels applied to a skill on its detail page so that I understand how the community categorizes it.
25. As a user, I want to click a label and see all skills sharing that label so that I can explore a topic.
26. As a user, I want to remove a label I personally applied to a skill so that I can correct a mistake.
27. As an admin, I want to rename a label globally (e.g. "ml" → "machine-learning") and have all affected skills automatically updated so that the taxonomy stays clean.
28. As an admin, I want to merge two labels into one (e.g. "llms" + "llm" → "llm") so that duplicates are consolidated.
29. As an admin, I want to delete a label and remove it from all skills so that stale or inappropriate labels are removed.
30. As an admin, I want to see a label management dashboard listing all labels, their usage counts, and tools to rename/merge/delete them.

### Administration
31. As an admin, I want to take down any skill listing so that I can remove inappropriate or broken submissions.
32. As an admin, I want to see a list of all submissions with submitter identity and timestamp so that I have an audit trail.
33. As an admin, I want to impersonate a skill entry's owner to make corrections so that broken entries can be fixed without contacting the author.

### Guides & Onboarding
34. As a new user, I want to see a "getting started" page explaining what the catalog is and how to use it so that I'm not confused on first visit.
35. As a potential contributor, I want a link to a skill creation guide (or template repo) so that I can quickly scaffold a new skill.

### Agent-Native Discovery & Install (`/slac-skills`)
36. As a Claude Code user, I want to type `/slac-skills I need something to query EPICS` and get back a ranked list of matching skills so that I can discover knowledge and capabilities without leaving my agent session.
37. As a Claude Code user, I want to type `/slac-skills install <slug>` and have the skill cloned into `~/.claude/skills/` automatically so that I don't have to find the repo and copy files manually.
38. As a Claude Code user, I want to type `/slac-skills list` to see what skills I have installed so that I have a quick inventory.
39. As a Claude Code user, I want to type `/slac-skills update <slug>` to pull the latest version of an installed skill so that I stay current without manual git operations.
40. As a Claude Code user, I want to type `/slac-skills remove <slug>` to uninstall a skill so that I can keep my environment clean.
41. As a Claude Code user, I want to type `/slac-skills rate <slug> <1-5>` to submit a rating directly from my agent session so that I don't have to open a browser to give feedback.
42. As a Claude Code user, I want `/slac-skills` to explain *why* it's recommending each match (e.g. "this skill matches because it provides EPICS Channel Access bindings") so that I can make an informed choice.
43. As an OpenCode user, I want the same `/slac-skills` commands to work in my environment so that I'm not excluded from the catalog ecosystem.
44. As an S3DF admin, I want `/slac-skills` to be seeded into the global Claude Code skills directory on S3DF so that all users get it without having to install anything manually.
45. As a skill author, I want to run `/slac-skills submit` and be walked through the entire publishing process — creating or selecting a GitHub repo, scaffolding the skill structure, and registering it in the catalog — so I never have to leave my agent session or open a browser.

---

## 3. Requirements

### Functional Requirements

**Skill catalog**
- FR-1: A skill entry stores: `name`, `repo_url` (required); `description`, `readme_html`, `compatible_platforms`, `license`, `version`, `github_stars`, `last_commit_at`, `submitter_id`, `submitted_at`, `entry_type` (skill | marketplace_ref) — all optional.
- FR-2: On submission, the system fetches repo metadata from the GitHub API (name, description, default branch README, stars, last commit date, license) and stores a snapshot.
- FR-3: Skills are publicly browsable without authentication.
- FR-4: Submission, rating, and labeling require SLAC authentication (identity derived from VouchProxy headers or JWT).
- FR-5: A submitter can edit or delete their own skill entry.
- FR-6: An admin can edit or delete any skill entry.

**Ratings**
- FR-7: A user may submit one integer rating (1–5) per skill.
- FR-8: A user may update their rating; the aggregate recalculates immediately.
- FR-9: Each skill card displays aggregate rating (average, rounded to 1 decimal) and total rating count.
- FR-10: A user's own rating is visually indicated on skills they have rated.

**Labels**
- FR-11: Any authenticated user may add a free-form label (string, normalized to lowercase, hyphens only) to any skill.
- FR-12: Labels are stored globally; a label document holds a canonical name and a list of aliases.
- FR-13: A user may remove a label they personally applied to a skill.
- FR-14: Admin can rename a label — all skill associations update atomically.
- FR-15: Admin can merge label B into label A — all occurrences of B on skills are replaced with A, B is deleted.
- FR-16: Admin can delete a label — it is removed from all skill entries.

**Search & filtering**
- FR-17: Full-text search over `name` and `description` fields (MongoDB text index).
- FR-18: Filter by one or more labels (AND or OR, configurable).
- FR-19: Sort by: newest, highest rated, most rated, most GitHub stars.
- FR-20: Pagination: 20 skills per page, cursor-based.

**Guides**
- FR-21: A static "How to create a skill" guide page is linked from the submission form and the nav. The guide must include: (a) a minimal working skill repo structure, (b) a link to the template repo, (c) a step-by-step walkthrough of submitting to the catalog, (d) a "does it work?" verification checklist.
- FR-22: The guide links to a canonical template repo (configurable by admins via site settings).
- FR-23: The submission form shows inline validation: on blur from the repo URL field, attempt GitHub fetch and display a live preview (repo name, description, star count) before the user submits — so they know the fetch will succeed.
- FR-24: If GitHub fetch fails during submission, the form must display a plain-language error (e.g. "Couldn't reach this repo — is it public? You can still submit with a manual description.") and allow the user to proceed with manually entered metadata.
- FR-25: The submission form must show an example of a valid repo URL (e.g. `https://github.com/slaclab/my-skill`) as placeholder text.
- FR-26: Compatible platforms field must use a predefined suggestion list (typeahead, not free-form) with canonical names: `claude-code`, `openai`, `langchain`, `crewai`, `autogen`, `mcp`, `other` — to prevent fragmentation. Users may still type custom values.
- FR-27: The site must include a "Troubleshooting" section (or FAQ) accessible from the nav or footer, covering at minimum: (a) "My submission failed — GitHub fetch error", (b) "I can browse but can't rate or label — auth issue", (c) "My skill shows stale information — how to re-fetch", (d) "Who do I contact if something is broken?"
- FR-28: A skill entry may set `uses_agent_gateway: true`. When set, the skill's detail page and card display a "Uses SLAC Agent Gateway" badge. No further MCP configuration is shown — the badge is purely informational, linking to the gateway docs at `mcp.sdf.slac.stanford.edu`.

> **Resolved OQ-2:** Support path is via SLAC Slack. The footer/troubleshooting page should link to the relevant Slack channel. **Open sub-question: which Slack channel(s)?** (e.g. `#s3df-help`, `#ai-tools`, a dedicated `#agent-skills` channel?)

### Non-Functional Requirements

- NFR-1: Page load (skill list) < 1s p95 on the SDF internal network.
- NFR-2: GitHub metadata fetch at submission < 5s; failures surface a plain-language error and allow manual metadata entry as fallback.
- NFR-3: Rating and label writes acknowledge within 500ms.
- NFR-4: The system handles 50 concurrent users without degradation.
- NFR-5: MongoDB data is persisted on a PVC with daily backup via standard S3DF mechanisms.
- NFR-6: All auth is delegated to SLAC VouchProxy — no passwords or secrets are stored in the app.
- NFR-7: The app is stateless (12-factor); config via environment variables.
- NFR-8: Images are containerized and published to the S3DF container registry.
- NFR-9: API and frontend are independently deployable as separate k8s Deployments.
- NFR-10: A `/health` endpoint on the backend returns `200 OK` when the service and MongoDB connection are healthy; used by k8s liveness probe and optionally surfaced on a public status page.
- NFR-11: Each skill detail page shows a "Catalog entry last updated" timestamp and a "README fetched on <date>" notice so users know how fresh the data is.
- NFR-12: The site footer or About page must state: the support contact (Slack channel or GitHub issues URL — see OQ-2), the expected availability (best-effort / S3DF standard), and a link to the changelog or release notes.

### Acceptance Criteria

- AC-1: Given a valid GitHub repo URL, when a user submits it, then a skill card appears in the catalog within 10 seconds.
- AC-2: Given an invalid or private GitHub repo URL, when submitted, the form shows: _"This repo couldn't be found or is private. Check the URL and make sure the repo is public. You can still submit with a manual description."_ — and does not create the entry unless user proceeds with manual metadata.
- AC-3: Given a user rates a skill 4 stars, when they later change it to 2, then the aggregate updates correctly and their old rating is replaced.
- AC-8: Given a user's VouchProxy session has expired, when they attempt to rate or label, the page shows: _"Your session has expired — please refresh the page to log in again."_ and does not silently fail or show a raw 401.
- AC-9: Given the GitHub API is unavailable during submission, the form shows: _"GitHub is unreachable right now. You can submit with a manual description and re-fetch later from your skill's edit page."_
- AC-10: Given a user tries to add a label that already exists on a skill, the UI shows a subtle indicator (e.g. label already highlighted) rather than an error, and takes no action.
- AC-4: Given a user adds label "data-viz" to a skill, when an admin renames "data-viz" to "data-visualization", then the skill now carries "data-visualization" and "data-viz" no longer appears anywhere.
- AC-5: Given two labels "llms" and "llm" exist, when an admin merges "llms" into "llm", then all skills formerly tagged "llms" are now tagged "llm" and "llms" is gone.
- AC-6: Given a user filters by label "web-scraping", only skills carrying that label appear in results.
- AC-7: Given an unauthenticated visitor, they can browse and search but the rate/label/submit UI is hidden or prompts login.

---

## 4. System Architecture

```
Browser (Next.js SSR/CSR)
  │  HTTPS
  ▼
SLAC Ingress / VouchProxy
  │  injects X-Forwarded-User header (or validates JWT)
  ▼
Next.js Frontend (k8s Deployment, port 3000)
  │  REST calls to /api/*
  ▼
FastAPI Backend (k8s Deployment, port 8000)
  ├─── MongoDB (StatefulSet + PVC)
  └─── GitHub API (external, fetched at submission time)
```

**Component responsibilities:**

| Component | Responsibility |
|---|---|
| Next.js frontend | SSR skill list/detail pages, CSR for rating/label interactions, auth header forwarding |
| FastAPI backend | REST API, business logic, MongoDB ODM (Beanie/Motor), GitHub fetch at submission |
| MongoDB | Skills, ratings, labels, users (identity cache), site settings |
| VouchProxy | All auth — no credentials stored in app |
| GitHub API | Metadata snapshot at submission (unauthenticated or with a read-only token for rate limits) |

---

### Data Model

```
Skill {
  _id: ObjectId
  slug: str                  # url-safe unique identifier
  name: str                  # required
  repo_url: str              # required, unique
  entry_type: enum           # "skill" | "marketplace_ref"
  description: str           # optional, submitter-provided or from GitHub
  readme_html: str           # fetched from GitHub at submission
  compatible_platforms: [str]# e.g. ["claude", "openai", "langchain"]
  license: str               # e.g. "MIT"
  version: str               # e.g. "1.2.0"
  github_stars: int
  last_commit_at: datetime
  submitter_id: str          # SLAC username from VouchProxy
  submitted_at: datetime
  updated_at: datetime
  label_ids: [ObjectId]      # references to Label documents
  uses_agent_gateway: bool   # true = shows "Uses SLAC Agent Gateway" badge
  avg_rating: float          # denormalized, updated on each rating write
  rating_count: int          # denormalized
}

Rating {
  _id: ObjectId
  skill_id: ObjectId
  user_id: str               # SLAC username
  value: int                 # 1–5
  created_at: datetime
  updated_at: datetime
  # unique index on (skill_id, user_id)
}

Label {
  _id: ObjectId
  name: str                  # canonical, lowercase, hyphens
  aliases: [str]             # previous names after renames
  created_by: str
  created_at: datetime
  usage_count: int           # denormalized
}

SkillLabel {
  _id: ObjectId
  skill_id: ObjectId
  label_id: ObjectId
  applied_by: str            # SLAC username
  applied_at: datetime
  # unique index on (skill_id, label_id, applied_by)
}

SiteSettings {
  _id: ObjectId
  skill_template_repo_url: str
  updated_by: str
  updated_at: datetime
}
```

---

## 5. API Contract (summary)

```
# Skills
GET    /api/skills                  # list + search + filter + sort + paginate
GET    /api/skills/summary          # lightweight list for LLM context (slug, name, description, labels, avg_rating)
GET    /api/marketplace.json        # Claude Code marketplace manifest (dynamically generated from catalog)
POST   /api/skills                  # submit new skill (auth required)
GET    /api/skills/:slug            # skill detail
PATCH  /api/skills/:slug            # edit own skill (auth required)
DELETE /api/skills/:slug            # delete own skill (auth required)

# Ratings
PUT    /api/skills/:slug/rating     # upsert rating 1–5 (auth required)
GET    /api/skills/:slug/rating/me  # fetch caller's own rating

# Labels
GET    /api/labels                  # list all labels (name + usage_count)
POST   /api/skills/:slug/labels     # add label to skill (auth required)
DELETE /api/skills/:slug/labels/:name  # remove label applied by caller

# Admin
GET    /api/admin/labels            # label list with rename/merge/delete tools
PATCH  /api/admin/labels/:id        # rename label
POST   /api/admin/labels/:id/merge  # merge label into another
DELETE /api/admin/labels/:id        # delete label + remove from all skills
DELETE /api/admin/skills/:slug      # admin force-delete any skill
GET    /api/admin/skills            # all skills with submitter info + timestamps

# Settings
GET    /api/admin/settings
PATCH  /api/admin/settings
```

Auth identity: all write endpoints read `X-Forwarded-User` (VouchProxy) or validate a JWT; the value becomes `user_id` in the request context. Admin role checked against a configurable allowlist in `SiteSettings`.

---

## 6. Architecture Decision Records

### ADR-001: MongoDB over PostgreSQL

**Status:** Accepted

**Context:** Skills have flexible, optional metadata fields; label associations evolve; no complex relational joins needed. Team targets S3DF k8s deployment.

| Option | Pros | Cons |
|---|---|---|
| MongoDB | Flexible schema, easy to add fields, native array ops for labels | Weaker consistency guarantees, no foreign keys |
| PostgreSQL | Strong consistency, JSONB for flex fields, familiar | Schema migrations for optional fields are more ceremonial |

**Decision:** MongoDB — the catalog data is document-shaped, schema flexibility reduces friction for optional metadata, and array operations on labels are natural. Denormalized `avg_rating` / `rating_count` on the Skill document avoids costly aggregations on reads.

**Consequences:** Must enforce data integrity in the application layer. Use MongoDB transactions for label merge/rename to keep skill associations consistent.

---

### ADR-002: GitHub metadata fetched once at submission (no sync)

**Status:** Accepted

**Context:** Keeping data fresh requires either polling or webhooks. Both add operational complexity.

**Decision:** Fetch once at submission time. Store a snapshot. Provide a manual "re-fetch from GitHub" button on the edit page so authors can refresh their own entry.

**Consequences:** Data may drift from GitHub over time. This is acceptable for v1 — the repo link is always present so users can check the source. Re-fetch button mitigates the worst staleness.

---

### ADR-003: Free-form labels with admin merge/rename tooling

**Status:** Accepted

**Context:** Predefined taxonomies require upfront agreement and admin overhead. Fully free-form labels accumulate duplicates ("llm" vs "llms").

**Decision:** Free-form submission, normalized to lowercase + hyphens on write. Admin label dashboard provides merge/rename/delete. Aliases stored on Label documents so renamed labels remain discoverable.

**Consequences:** Requires admin tooling to be built (label management UI). Label quality depends on admin responsiveness to clean up duplicates.

---

### ADR-004: Auth fully delegated to VouchProxy/JWT

**Status:** Accepted

**Context:** This runs inside SLAC/S3DF. Users already have SLAC accounts. Building a separate auth system is unnecessary complexity.

**Decision:** Trust `X-Forwarded-User` header injected by VouchProxy, or validate a SLAC-issued JWT. No passwords, no sessions, no tokens stored in the app.

**Consequences:** App is only correctly secured when deployed behind VouchProxy. Local dev requires a mock header or dev-mode bypass (env flag).

---

## 7. Module Design

| Module | Responsibility | Interface | Status |
|---|---|---|---|
| `SkillRepository` | CRUD on Skill documents, text search, filter/sort/paginate | `list(filters, sort, page)`, `get(slug)`, `create(data)`, `update(slug, data)`, `delete(slug)` | New |
| `GitHubFetcher` | Fetch repo metadata + README from GitHub API | `fetch(repo_url) → GitHubSnapshot` | New |
| `RatingService` | Upsert rating, recompute denormalized avg + count atomically | `upsert(skill_id, user_id, value)`, `get_mine(skill_id, user_id)` | New |
| `LabelService` | Add/remove labels; admin rename/merge/delete with atomic skill updates | `add(skill_id, label_name, user_id)`, `remove(...)`, `rename(id, new_name)`, `merge(src_id, dst_id)`, `delete(id)` | New |
| `AuthMiddleware` | Extract user identity from VouchProxy header or JWT; attach to request context | FastAPI dependency `get_current_user(request) → User` | New |
| `AdminGuard` | Check user is in admin allowlist (from SiteSettings) | FastAPI dependency `require_admin(user)` | New |
| `SkillListPage` | SSR Next.js page: skill cards, search bar, label filter chips, sort dropdown | Props: `skills[]`, `labels[]`, `filters` | New |
| `SkillDetailPage` | SSR Next.js page: full skill info, README render, rating widget, label editor | Props: `skill`, `userRating` | New |
| `SubmitForm` | CSR form: repo URL input → auto-fill from GitHub fetch → optional metadata fields | Calls `POST /api/skills` | New |
| `AdminLabelDashboard` | CSR page: label list, usage counts, rename/merge/delete actions | Calls admin label endpoints | New |

---

## 8. Delivery Slices

### Slice 1 — Skeleton + auth (k8s dev namespace)
- FastAPI app boots, MongoDB connected, health endpoint
- Auth middleware reads VouchProxy header; `/api/me` returns identity
- Next.js app proxies to FastAPI; unauthenticated browse works
- Dockerfiles + k8s manifests (Deployment, Service, Ingress, PVC for Mongo)

### Slice 2 — Skill CRUD + GitHub fetch
- `POST /api/skills` — validates URL, fetches GitHub snapshot, stores skill
- `GET /api/skills` — list with text search, label filter, sort, pagination
- `GET /api/skills/:slug` — detail
- `PATCH/DELETE /api/skills/:slug` — owner-only edit/delete
- Skill list page + detail page in Next.js (no ratings/labels yet)
- Submit form with GitHub auto-fill

### Slice 3 — Ratings
- `PUT /api/skills/:slug/rating` — upsert with atomic avg/count update
- Rating widget (star selector) on detail page; aggregate stars on list cards
- Show user's own rating highlighted

### Slice 4 — Labels
- `POST/DELETE /api/skills/:slug/labels` — add/remove
- Label filter chips on list page; label pills on detail page + cards
- Click label → filtered list

### Slice 5 — Admin tooling
- Admin label dashboard (rename, merge, delete)
- Admin skill list with force-delete
- Site settings (template repo URL, admin allowlist)

### Slice 6 — Guides + polish
- "How to create a skill" static guide page
- Template repo link in submission form
- Empty states, error states, loading skeletons
- Responsive layout pass

### Slice 7 — Production promotion
- Staging deploy + smoke tests
- PVC backup job configured
- Ingress SSL + VouchProxy wired
- Prod deploy at `agent-knowledge-hub.slac.stanford.edu`

### Slice 8 — `/slac-skills` agent skill + marketplace manifest
- `GET /api/skills/summary` — lightweight skill list for LLM context
- `GET /api/marketplace.json` — dynamic Claude Code marketplace manifest
- `slac-skills` GitHub repo with skill markdown file
- `/slac-skills` commands: search (LLM-mediated), install, list, update, remove, submit, rate
- Bootstrap docs: one-time `/plugin marketplace add` + `/plugin install slac-skills@agent-knowledge-hub`
- OpenCode agent install path (`~/.config/opencode/agents/`) supported alongside Claude Code

---

## 9. Trade-offs

| Choice | Given up | Decision |
|---|---|---|
| Fetch GitHub once, no sync | Data freshness | Manual re-fetch button mitigates; full sync is v2 if needed |
| Denormalized avg_rating on Skill | Consistency on concurrent writes | MongoDB `$inc`/`$set` on upsert is atomic enough at this scale |
| Free-form labels | Taxonomy consistency | Admin merge/rename tooling compensates |
| VouchProxy-only auth | Works outside SLAC | Dev-mode env bypass; out-of-SLAC use is not a v1 goal |
| No pre-publish moderation | Risk of spam/bad content | Trust SLAC auth; post-publish admin removal is sufficient |
| Text index search only | Semantic relevance | Vector search is explicitly planned for v2 |

---

## 10. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub API rate limit hit during bulk submissions | Medium | Medium | Cache by repo URL; use a read-only GitHub token; surface clear error |
| Label proliferation becomes unmanageable | Medium | Low | Admin merge/rename tooling; periodic label hygiene by admins |
| VouchProxy not available in dev | High | Low | `DEV_USER` env var bypass for local development |
| MongoDB PVC data loss | Low | High | Daily backup via S3DF standard backup mechanisms; document recovery runbook |
| Stale README content misleads users | Medium | Low | "Last fetched" timestamp shown; re-fetch button available to owner |
| Admin allowlist misconfigured — no admins | Low | Medium | Seed at least one admin on deploy; fallback to env var `ADMIN_USERS` |

---

## 11. Discovery & Onboarding Plan

> Added by UX review — no discovery plan existed in the original PRD.

### How users find this site

- **MOTD / login banner:** Add a one-liner to the S3DF MOTD and OOD login page at launch: _"New: browse and share Claude Code skills at https://agent-knowledge-hub.slac.stanford.edu"_
- **OOD Portal link:** Add a tile or nav link from the OnDemand portal (where scientists already are) to the marketplace.
- **Claude Code `--help` / CLAUDE.md:** Mention the marketplace URL in the global `~/.claude/CLAUDE.md` template distributed to S3DF users.
- **S3DF Confluence / docs landing page:** Add an entry under "AI Tools" in the S3DF user documentation index.
- **Announcement email:** One-time announcement to the S3DF users mailing list at launch.

### Site URL

> **Resolved OQ-1:** Canonical URL is `https://agent-knowledge-hub.slac.stanford.edu`. DNS and Ingress must be configured for this hostname before Slice 7 (prod promotion).

### First-visit experience

- The homepage (skill list) must display a one-sentence tagline explaining what the site is for — visible above the fold without scrolling.
- A persistent "What is this?" / "Getting Started" link in the nav must be present from day one (not deferred to Slice 6).
- Empty state (zero skills listed) must include a CTA: "Be the first to submit a skill →" with a link to the submit form and the creation guide.

---

## 12. Definition of Done

- [ ] All acceptance criteria (AC-1 through AC-7) pass in staging
- [ ] Unit tests: SkillRepository, RatingService, LabelService (merge/rename), GitHubFetcher
- [ ] Integration tests: full submit → rate → label → admin-rename flow
- [ ] Auth middleware tested with mock VouchProxy header and JWT
- [ ] Load test: 50 concurrent users browsing skill list < 1s p95
- [ ] MongoDB PVC backup job configured and verified
- [ ] k8s manifests reviewed and deployed to staging namespace
- [ ] VouchProxy integration tested end-to-end in staging
- [ ] Admin label dashboard manually verified (rename, merge, delete)
- [ ] "How to create a skill" guide page live and linked from submission form
- [ ] README rendered correctly on skill detail page
- [ ] Empty state, error state, and loading skeleton implemented on all pages
- [ ] No hardcoded secrets; all config via environment variables

---

## 14. UX Review

### Persona: S3DF Scientist

| Dimension | Score | Key Gap |
|---|---|---|
| Discoverability | 5/10 | No announcement plan, no cross-links from OOD/Claude Code, no canonical URL confirmed |
| First-Use Clarity | 6/10 | Guide deferred to Slice 6; submit form lacked live GitHub preview and graceful fetch-failure fallback |
| Documentation Quality | 5/10 | No troubleshooting/FAQ planned; compatible_platforms was free-form (fragmentation risk) |
| Error UX | 5/10 | Error message copy unspecified; expired-session and GitHub-unavailable paths unhandled |
| Workflow Fit | 7/10 | Web-only; no CLI path for terminal-first users — noted as v2 OQ |
| Trust & Reliability | 5/10 | No health endpoint, no status page, no support contact, no freshness signals in requirements |
| **UX Readiness Score** | **5.5/10** | |

**Verdict:** ⚠️ UX WARNINGS — Addressable gaps. All 5 dimensions below 7 have been patched in this PRD. Resolve open questions OQ-1 through OQ-3 before shipping.

### Top 3 User Risks (if shipped without UX fixes)

1. **Silent auth failures** — A scientist's VouchProxy session expires, they try to rate a skill, get a raw 401 with no message, and assume the site is broken. They never rate anything.
2. **Platform name fragmentation** — Without a canonical `compatible_platforms` suggestion list, the first 20 submitters use "claude", "Claude", "Claude Code", "anthropic" — the filter becomes useless and trust in the catalog drops.
3. **Nobody finds it** — Without MOTD/OOD cross-linking at launch, only people who already know about it will use it. The "20 skills in 30 days" success metric will not be met.

### Highest-Impact Fix

**Discovery:** Add the marketplace URL to the S3DF MOTD and OOD portal nav at launch. This single change reaches every active S3DF user on their next login without requiring any action from them.

### Open Questions Requiring Resolution Before Launch

| ID | Question | Status |
|---|---|---|
| OQ-1 | Canonical URL | ✅ `https://agent-knowledge-hub.slac.stanford.edu` |
| OQ-2 | Support contact path | ⚠️ Slack — channel name TBD |
| OQ-3 | v2 CLI client decision | 🔲 Deferred, out of scope for v1 |

### Changes Made to PRD by This Review

- Added Section 11 (Discovery & Onboarding Plan) — MOTD, OOD link, CLAUDE.md mention, docs index entry, launch email
- Moved "Getting Started" link from Slice 6 to a day-one requirement
- Added FR-23: live GitHub preview on repo URL field before submit
- Added FR-24: graceful fallback when GitHub fetch fails during submission
- Added FR-25: example placeholder URL in submission form
- Added FR-26: predefined suggestion list for `compatible_platforms` with canonical names
- Added FR-27: Troubleshooting/FAQ page requirement
- Rewrote AC-2 with specific error message copy
- Added AC-8 (expired session UX), AC-9 (GitHub unavailable UX), AC-10 (duplicate label UX)
- Added NFR-10: `/health` endpoint
- Added NFR-11: freshness timestamps on skill detail pages
- Added NFR-12: footer support contact + availability statement
- Added OQ-3 to out-of-scope section re: CLI client for v2


---

## 12. Kubernetes & Makefile Conventions

This project follows the standard SLAC/S3DF deployment pattern used across all k8s workloads.

### Directory Layout

```
kubernetes/
  base/
    backend/
      deployment.yaml       # FastAPI Deployment + Service
    frontend/
      deployment.yaml       # Next.js Deployment + Service
    mongodb/
      statefulset.yaml      # MongoDB StatefulSet + PVC + Service
    kustomization.yaml      # base resources list
  overlays/
    dev/
      kustomization.yaml    # dev image tags, replicas=1, dev namespace
      patch-backend.yaml    # env vars: DEV_USER bypass, DEBUG=true
      Makefile
    stage/
      kustomization.yaml
      patch-backend.yaml
      Makefile
    prod/
      kustomization.yaml    # prod image tags, replicas, resource limits
      patch-backend.yaml    # ADMIN_USERS, GITHUB_TOKEN, etc.
      Makefile
```

### Kustomization Pattern

Each `kustomization.yaml` follows the project-wide convention:

```yaml
# overlays/dev/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

namespace: agent-knowledge-hub-dev

images:
  - name: agent-knowledge-hub-backend
    newTag: dev
  - name: agent-knowledge-hub-frontend
    newTag: dev

configMapGenerator:
  - name: backend-config
    literals:
      - MONGO_URI=mongodb://mongodb:27017/agent-skills
      - GITHUB_API_URL=https://api.github.com
      - AUTH_MODE=vouchproxy
    options:
      disableNameSuffixHash: true

patches:
  - path: patch-backend.yaml
```

### Makefile Pattern

Each overlay has a `Makefile` following the `ensure-context → secrets → apply → clean` pattern:

```makefile
CONTEXT    = agent-knowledge-hub-dev
NAMESPACE  = agent-knowledge-hub-dev
KUBECONFIG ?= $(HOME)/.kube/contexts/s3df/dev

.PHONY: apply diff destroy rollout-restart

apply: ensure-context secrets
	kubectl apply -k .
	$(MAKE) clean-secrets

diff: ensure-context
	kubectl diff -k .

rollout-restart: ensure-context
	kubectl rollout restart deployment/agent-knowledge-hub-backend -n $(NAMESPACE)
	kubectl rollout restart deployment/agent-knowledge-hub-frontend -n $(NAMESPACE)

destroy: ensure-context
	kubectl delete -k .

ensure-context:
	@kubectl config current-context | grep -q "$(CONTEXT)" || \
	  (echo "Wrong context. Expected: $(CONTEXT)"; exit 1)

secrets:
	# Fetch from Vault: GITHUB_TOKEN, MONGO_ROOT_PASSWORD, etc.
	# vault kv get -field=value secret/tid/agent-skills-$(ENV)/github-token > .secrets/github-token
	# kubectl create secret generic agent-knowledge-hub-secrets --from-file=.secrets/ -n $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -

clean-secrets:
	rm -f .secrets/*
```

### Deploy Commands

```bash
# Dev
export KUBECONFIG=~/.kube/contexts/s3df/dev
make -C kubernetes/overlays/dev apply

# Prod
export KUBECONFIG=~/.kube/contexts/s3df/prod
make -C kubernetes/overlays/prod apply

# Check diff before applying
make -C kubernetes/overlays/dev diff

# Restart pods after config change
make -C kubernetes/overlays/dev rollout-restart
```

### Secrets Management

- Secrets fetched from **Vault** at apply time, written to `.secrets/` (gitignored), applied as k8s Secrets, then deleted
- Secret keys: `GITHUB_TOKEN` (read-only, for GitHub API rate limit), `MONGO_ROOT_PASSWORD`, `JWT_SECRET` (if JWT validation used)
- `DEV_USER` env var in dev overlay bypasses VouchProxy for local/dev use — **never present in prod overlay**

### Resource Conventions

- `disableNameSuffixHash: true` on all ConfigMaps (stable names for rolling restarts)
- Backend and frontend are separate `Deployment` resources (independently deployable)
- MongoDB runs as a `StatefulSet` with a named `PVC` (not ephemeral)
- All workloads set `resources.requests` and `resources.limits`
- Liveness + readiness probes on all containers

---

## 15. `/slac-skills` — Agent-Native Discovery & Install (v1 feature)

### Concept

A Claude Code (and OpenCode) skill that lets users discover and install skills from the catalog using natural language — directly inside their agent session, without opening a browser.

Inspired by `agentskill.sh/install`, but SLAC-specific and smarter: instead of a fixed install command, the user describes their problem and the skill finds and installs what they need.

### Invocation examples

```
/slac-skills install something that allows me to query EPICS

/slac-skills I have a problem trying to work out what's wrong with my Kubernetes deployment

/slac-skills find me a skill for analysing NeXus files

$slac-skills search --label hdf5
```

The `$` prefix makes it work identically in OpenCode; `/` prefix is Claude Code.

### How it works

```
User types: /slac-skills <natural language query>
                │
                ▼
        Skill fetches catalog via GET /api/skills (all, or paginated)
                │
                ▼
        Passes catalog + user query to Claude
        ("Given these skills, which best matches '<query>'? Return slug + rationale")
                │
                ▼
        Claude returns ranked matches with explanations
                │
                ▼
        User sees: top 3 matches with descriptions, ratings, repo links
        User picks one (or accepts top match)
                │
                ▼
        Skill installs into target runtime:
          Claude Code → clone/copy to ~/.claude/skills/<slug>/
          OpenCode    → clone/copy to ~/.opencode/skills/<slug>/   (TBC — see OQ-4)
```

### Install targets

> **Resolved OQ-4:** OpenCode does not have "skills" — it uses *custom agents* (markdown files at `~/.config/opencode/agents/`) and *MCP servers* (entries in `opencode.json`). No dedicated install CLI exists in OpenCode; installs are manual config edits.

| Runtime | Install path | Mechanism |
|---|---|---|
| Claude Code | `~/.claude/skills/<slug>/` | `git clone <repo_url>` into skills dir |
| OpenCode (agent) | `~/.config/opencode/agents/<slug>.md` | Write agent markdown file from repo |
| OpenCode (MCP) | Append entry to `~/.config/opencode/opencode.json` | Patch JSON config with MCP server definition |

The `/slac-skills` installer detects which runtime is calling it and installs into the appropriate target. For `entry_type: marketplace_ref`, no file install occurs — the browser is opened to the reference URL instead.

### Skill file structure (what gets installed)

The catalog entry's `repo_url` points to a GitHub repo. The install step clones or copies it to the appropriate skills directory. No execution happens at install time — the agent runtime picks it up on next invocation.

For Claude Code, a valid skill repo must contain at minimum a skill markdown file (e.g. `skill.md` or `<name>.md`). For OpenCode, a valid agent repo must contain a markdown file with YAML frontmatter (agent name, description, model). The `/slac-skills` skill validates this before installing and warns the user if the repo structure is unrecognised.

### Claude-mediated matching

The search is intentionally LLM-powered rather than keyword-based:

- Fetch the full catalog (or a paginated summary: slug + name + description + labels + avg_rating)
- Pass to Claude with the user's query as context
- Claude ranks matches, explains why each is relevant, and flags any caveats (e.g. "this skill was last updated 8 months ago and has no ratings")
- This means even vague queries ("something for beam diagnostics") can return useful results

This avoids building a vector index in v2 while still providing semantic matching — Claude is the semantic layer.

### Additional commands

| Command | Behaviour |
|---|---|
| `/slac-skills list` | Show all installed skills (from `~/.claude/skills/`) |
| `/slac-skills search <query>` | Search without installing — show top matches |
| `/slac-skills install <slug>` | Direct install by slug (no LLM step) |
| `/slac-skills update <slug>` | Re-pull latest from the skill's repo |
| `/slac-skills remove <slug>` | Delete from skills directory |
| `/slac-skills submit` | Guided submission flow — walks user through creating/selecting a GitHub repo, scaffolding skill structure, and registering in the catalog via the API. No browser required. |
| `/slac-skills rate <slug> <1-5>` | Submit a rating directly from the agent session |

### API additions required (v2 backend)

```
GET /api/skills/summary   # lightweight: slug, name, description, labels, avg_rating only
                          # no README HTML — keeps payload small for LLM context
```

### `/slac-skills submit` — guided publish flow

The submit command is a fully in-agent walkthrough. No browser required. Flow:

```
Step 1 — Do you have an existing GitHub repo for this skill?
  [yes] → enter repo URL → validate it's accessible → skip to Step 4
  [no]  → continue to Step 2

Step 2 — Create a new GitHub repo
  → suggest a repo name based on what the skill does
  → create repo via GitHub API (uses user's auth token or prompts for one)
  → clone locally or work in-place

Step 3 — Scaffold the skill structure
  → generate skill.md from a template (name, description, usage examples)
  → ask user to describe what the skill does in plain English
  → fill in the template, show a preview, let user edit
  → commit and push to GitHub

Step 4 — Register in the catalog
  → fetch metadata from GitHub (stars, README, license, last commit)
  → show a preview of the catalog entry
  → POST /api/skills with the user's SLAC identity attached automatically
  → confirm: "Your skill is live at agent-knowledge-hub.slac.stanford.edu/skills/<slug>"
  → optionally add labels now
```

The skill template repo (configurable via `SiteSettings.skill_template_repo_url`) is used for Step 3 scaffolding.

### Open Questions

> **Resolved OQ-4:** OpenCode uses custom agents (`~/.config/opencode/agents/<name>.md`) and MCP servers (`opencode.json`). No "skills" concept. Install paths and mechanisms documented in Section 15.

> **OQ-5 — Resolved:** Bootstrap uses Claude Code's native `/plugin marketplace` protocol. The catalog exposes a `marketplace.json` manifest; users register it once and install from it directly. OOD integration (pre-seeding for all S3DF users) is a follow-on task. See Section 15 for full bootstrap flow.

### V2 delivery dependency

- V1 catalog API must be live at `https://agent-knowledge-hub.slac.stanford.edu/api`
- `GET /api/skills/summary` and `GET /api/marketplace.json` endpoints added to backend
- At least ~10 skills in the catalog before LLM matching is useful
- OQ-4 resolved (done — see Install targets section above)

### Bootstrap

Users register the SLAC marketplace once via Claude Code's native `/plugin` protocol, then install any catalog skill by slug:

```bash
# Register the SLAC marketplace (one-time)
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json

# Install the /slac-skills discovery tool itself
/plugin install slac-skills@agent-knowledge-hub

# Install any other skill directly
/plugin install k8s-troubleshooting@agent-knowledge-hub
/plugin install epics-query@agent-knowledge-hub
```

**OOD integration (follow-on):** Pre-seed the `/plugin marketplace add` call into the S3DF-managed Claude Code / OpenCode container so all users have the SLAC marketplace registered automatically on first launch — removing even the one-time step.

### `marketplace.json` manifest

The backend serves a dynamically generated Claude Code marketplace manifest at `GET /api/marketplace.json`. Every `entry_type: skill` in the catalog becomes a plugin entry:

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "agent-knowledge-hub",
  "description": "SLAC S3DF agent skills catalog",
  "owner": { "name": "SLAC S3DF", "email": "s3df-support@slac.stanford.edu" },
  "metadata": { "version": "1.0.0" },
  "plugins": [
    {
      "name": "slac-skills",
      "description": "Discover and install SLAC agent skills from inside your agent session",
      "version": "1.0.0",
      "source": { "source": "github", "repo": "slaclab/slac-skills" },
      "author": { "name": "SLAC S3DF", "url": "https://agent-knowledge-hub.slac.stanford.edu" },
      "homepage": "https://agent-knowledge-hub.slac.stanford.edu",
      "repository": "https://github.com/slaclab/slac-skills",
      "license": "MIT",
      "keywords": ["slac", "s3df", "skills", "marketplace"],
      "category": "productivity",
      "tags": ["slac", "catalog", "install"]
    }
    // ... all other catalog skills appended dynamically
  ]
}
```

This means `/plugin install <slug>@agent-knowledge-hub` works for every skill in the catalog automatically — no manual updates to the manifest needed.

### New API endpoint

```
GET /api/marketplace.json    # dynamically generated Claude Code marketplace manifest
                             # all entry_type=skill entries included as plugin objects
                             # Content-Type: application/json
                             # cached 5 minutes, ETag for freshness
```

