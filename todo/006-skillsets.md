# 006 — Skillsets: Curated Skill Collections

**Status:** 🔄 In Progress (Slice 1 implemented on its branch, not merged)
**Branch:** `feat/skillsets-backend`
**PR:** —

---

## Problem & Goal

**Problem:** Users from different facilities and groups (USDF, LCLS, SCS, etc.) need a way to discover and install a curated bundle of skills relevant to their context. Today, every skill is standalone — there is no concept of a collection, no way for a facility lead to say "these 12 skills are what LCLS users should start with", and no signal on a skill's detail page that it belongs to a well-known set.

**Goal:** Introduce **Skillsets** — named, curated collections of skills maintained by a submitter. A skillset can be discovered, browsed, and installed as a unit. Each skill surfaces a reverse link showing which skillsets it belongs to, giving a secondary popularity signal beyond star ratings.

**Success metrics:**
- A user can browse skillsets, see which skills they contain, and install the full set in one action (via `/agent-knowledge-hub install skillset <slug>`)
- A curator can create, name, describe, and manage a skillset (add, remove, and reorder skills)
- A skill's author can remove their skill from any skillset
- Every skill detail page shows "Part of N skillset(s)" with links to those skillsets
- Skillset membership count is visible on the skills browse/list page as a lightweight popularity indicator

**Out of scope:**
- Automated skillset generation (ML-based recommendations)
- Versioned skillsets (pinning specific skill versions)
- Skillset ratings or reviews (separate feature)
- Private/org-restricted skillsets (initial version is public only)

---

## User Stories

1. As a facility lead, I want to create a named skillset, so that I can curate a starter bundle for my team.
2. As a facility lead, I want to add existing catalog skills to my skillset, so that the collection reflects our actual toolkit.
2a. As a facility lead browsing a skill's page, I want to add that skill to one of my skillsets from the same page, so that I do not have to switch to the skillset page to find it again.
2b. As a facility lead, I want to submit a new skill directly from the skillset detail page, so that I can add skills that don't yet exist in the catalog without losing my context.
2c. As a skill submitter, I want to assign my new skill to one of my skillsets during submission, so that it's immediately part of my curated set when it's created.
3. As a facility lead, I want to remove a skill from my skillset, so that I can keep the collection current.
4. As a facility lead, I want to write a description for my skillset, so that visitors understand its purpose and audience.
5. As a user, I want to browse all public skillsets, so that I can discover curated bundles relevant to my role.
6. As a user, I want to see the skills inside a skillset before installing, so that I know what I'm getting.
7. As a user, I want to run `install skillset <slug>` in my AKH skill, so that all skills in the set install in one command.
8. As a user, I want to see on a skill's detail page which skillsets it belongs to, so that I can discover related bundles.
9. As a user, I want to see a "member of N skillset(s)" count on skill cards, so that popular curated skills stand out.
10. As an admin, I want to delete or rename any skillset, so that I can clean up spam or outdated collections.
11. As a curator, I want to edit a skillset I own (rename, re-describe, reorder skills), so that I can maintain it over time. The order I set is the order the skills are listed and installed in.
12. As a curator, I want to delete a skillset I own, so that I can remove collections I no longer maintain.
13. As a user, I want the skillset install command to skip skills I already have installed, so that re-running is safe.
14. As a signed-in user without access to SLAC's private GitHub repositories, I want a clear message when an internal member skill cannot be cloned, so that I understand why part of the install was skipped.
15. As an API consumer (LLM agent), I want to query `GET /api/skillsets` with metadata, so that skill discovery from within an agent session is possible.
16. As a skill author, I want to remove my skill from a skillset that someone else curates, so that I keep a say in where my work is promoted.
17. As a user, I want `install skillset` to keep going when one member skill fails to install, so that one broken catalog entry does not block the rest of the set.

---

## Requirements

### Functional

- **FR-1:** Any authenticated user can create a skillset with a name, slug, and description.
- **FR-2:** A skillset curator can add and remove existing catalog skills. Who may change membership is defined once, in ADR-U19 › Permission rules. The UI offers two entry points for adding, FR-2c and FR-2d.
- **FR-2a:** The skillset detail page (owner-only view) shows an "Add new skill →" button that navigates to `/skills/submit?skillset=<slug>`. After successful submission, the new skill is automatically added to the skillset and the user is redirected back to the skillset detail page.
- **FR-2b:** The skill submit form accepts an optional `skillset` query parameter. When present and the submitter owns that skillset, the newly created skill is automatically added to it after creation. If the submitter does not own the skillset (or it doesn't exist), the skill is still created normally — the `skillset` param is silently ignored (cross-ownership addition is handled by #029).
- **FR-2c:** Search picker. Where: `/skillsets/[slug]` page, owner view, above the skill list. The typeahead calls `GET /api/skills/summary?q=<text>`; choosing a result calls `PUT /api/skillsets/{slug}/skills/{skill_slug}`. Results already in the set are shown disabled. The picker does not use `GET /api/skills?q=`, because that endpoint matches with `$text`, which does not match partial words (Measured facts › text-vs-substring).
- **FR-2d:** "Add to skillset" menu. Where: `/skills/[slug]` page header, shown to signed-in users who own at least one skillset. The menu lists `GET /api/skillsets?created_by=<user_id>`, with `user_id` taken from `useAuth()`. An entry is checked when the skill's `skillsets` field (FR-6) contains that skillset. Checking an entry calls `PUT /api/skillsets/{slug}/skills/{skill_slug}`; unchecking it calls `DELETE` on the same path.
- **FR-2e:** Author removal. Where: the "Part of N skillset(s)" section on `/skills/[slug]` (FR-10). When the viewer is the skill's submitter, each skillset link carries a Remove control that calls `DELETE /api/skillsets/{slug}/skills/{skill_slug}`. The control's accessible name is "Remove <skill name> from <skillset name>". It asks for confirmation first, with the same two-step pattern as `delete-skill-button.tsx`, and the confirmation reads "Remove <skill name> from <skillset name>? Only the skillset's curator can add it back." A submitter cannot re-add the skill (ADR-U19 › Permission rules), so the confirmation is the author's only chance to back out.
- **FR-2f:** Reorder. Where: `/skillsets/[slug]` page, owner view, up and down controls on each member row. Each move sends `PUT /api/skillsets/{slug}/order` with the full new list of member slugs and the page's current `version`. The current version is the one in the last order response, or in the page's last `GET /api/skillsets/{slug}`; the page repeats that GET after each add or remove, because those return 204 with no body. The up and down controls are disabled while a move is in flight, so a second click cannot send a version the first move has already replaced. A stale `version` returns 409. A list that is not exactly the current member set returns 422. When both apply, ADR-U18 › Write shapes › reorder returns 409. On either status the page reloads the skillset and shows "This skillset changed since you loaded it, so your move was not saved. The list below is up to date; try the move again." Newly added members go to the end. The stored order is the display order (FR-9) and the install order (FR-7).
- **FR-2g:** Membership feedback. This rule covers the controls in FR-2c, FR-2d, and FR-2e and the owner's Remove on the skillset page; FR-2f covers reorder. Each control is disabled while its request is in flight. After a successful change on the skill page, the page re-fetches the skill with `router.refresh()`, so the FR-2d menu's checks and the "Part of N skillset(s)" section (FR-10) agree; the skillset page re-reads as FR-2f describes. A 409 on add or a 404 on remove means the change had already been made elsewhere, so the page treats it as success and re-reads. Other outcomes show an inline message next to the control, as `label-section.tsx` does for labels:

  | Outcome | Message |
  |---|---|
  | Picker search returns no results | No skills match "<text>". Search looks at skill names and descriptions. The owner view adds an "Add new skill →" link (FR-2a). |
  | Picker search request fails | Search failed. Try again. |
  | 401 | Your session has expired. Reload the page to sign in again. |
  | 403 | You are not allowed to change this skillset. Reload the page. |
  | 404 on add | This skill was deactivated or deleted, or the skillset was deleted. Reload the page. |
  | 429 | Too many additions in the last hour. Try again later. |
  | Any other failure | Could not save the change. Try again. |
- **FR-3:** Skillset slugs are unique, URL-safe, lowercase, and auto-derived from the name (editable at creation).
- **FR-4:** `GET /api/skillsets` returns a page-number paginated list (`page`, `page_size`, the same parameters `GET /api/skills` accepts) with member counts and curator. An optional `created_by=<user_id>` filter serves FR-2d. Results are sorted by `created_at` descending and then `_id` descending, so consecutive pages neither repeat nor skip a skillset.
- **FR-5:** `GET /api/skillsets/{slug}` returns the skillset with its `version` and its members in stored order, each hydrated with a skill summary. Every member is returned, including skills whose `status` is not `active`, except orphans (ADR-U18 › Orphan members); each summary carries `status`, and the detail page marks non-active members as deactivated. Returning all members keeps the FR-2f order list equal to what the page shows.
- **FR-6:** `GET /api/skills/{slug}` response includes `skillset_count` and a `skillsets` list (names + slugs).
- **FR-7:** The AKH skill gains `install skillset <slug>`. Where: `skill/SKILL.md`, a new sub-command section after `### Install`. It installs each member in stored order using the existing per-skill install flow, with these rules:
  - **Confirm rule:** before it installs anything, the command fetches each member's `GET /api/skills/{slug}`, applies the skip rule, and asks the skip rule's replace question for each member that needs one. Every question therefore comes before the first clone, and a user who confirms can leave the run unattended. The command then prints one line for every member it will install: the slug, the `repo_url`, and the words "MCP server" or "scripts" when `has_mcp_server` or `has_scripts` is true. It then asks once: "Install these N of M skills from skillset <slug>? (y/N)", where M is the number of entries in the response's `skills` list, the same M as the `[i/M]` progress lines. No installs nothing, prints `Nothing installed.`, and ends without the summary line. When N is 0 there is nothing to confirm, so the command does not ask and goes on to print the skip lines, failure lines, and summary line. The member list is chosen by the skillset's owner, who can be any signed-in user, and it can change after the user last looked at the skillset page, so this list is the only point where the user sees what will be installed, including MCP servers that the per-skill flow registers with `claude mcp add`. A member whose fetch fails, or whose values fail the argument rule, is not listed; the loop reports it at its position under the failure rule.
  - **Skip rule:** a member is skipped when `~/.claude/skills/<slug>/.installed-manifest.json` exists, with the progress line in ADR-U20 › Consequences. A skill directory without that manifest may be a partial install or the user's own files under the same name, so the command asks before replacing it, at the point the confirm rule sets: "`~/.claude/skills/<slug>/` exists but was not installed by /agent-knowledge-hub. Replace it? (y/N)". Yes lists the member for install, and its install replaces the directory. No skips the member, counts it as skipped, and prints `[i/M] Skipping <slug> (kept your existing directory)`.
  - **Failure rule:** a member that fails is reported and the loop continues. Failures include 404, 410, a clone error, a `skill_path` missing from the clone, and a path-guard abort. When the failed member's `visibility` is `internal` and the failure is a clone error, the report points the user to `gh auth login` and to the `/guides/slac-github-access` page, printed as a full URL on the catalog site because a terminal cannot follow a relative path (user story 14). Each clone runs with `GIT_TERMINAL_PROMPT=0 GIT_ASKPASS= GCM_INTERACTIVE=0`, so a repository the user cannot read fails as a clone error instead of waiting on a credential prompt; the install-loop dry run behind this rule set the first of these. `GIT_TERMINAL_PROMPT=0` alone does not do it: git asks an askpass program (`GIT_ASKPASS`, `core.askPass`, then `SSH_ASKPASS`) before the terminal, and an empty `GIT_ASKPASS` skips all three; Git Credential Manager prompts in its own window unless `GCM_INTERACTIVE` is `0` or `false`. A credential that a helper already stores still works. Where: the clone step of `skill/SKILL.md` › Install, so plain `install` clones the same way.
  - **Argument rule:** before a member is cloned, the command checks its `repo_url` against `^https://github\.com/[A-Za-z0-9-]+/[A-Za-z0-9._-]+$` and its `skill_path` against `^/[A-Za-z0-9._/-]*$`, and passes both to `git` and `cp` inside single quotes. A value that fails either check is a path-guard abort under the failure rule, and no command runs for that member. The catalog does not make these values safe for a shell: `_GITHUB_URL_RE` in `backend/app/schemas/skill.py` accepts any character except `/` in the owner and repository segments, `skill_path` is checked only for `..` components and length, and `create()` in `backend/app/services/skill.py` stores a skill even when GitHub cannot fetch it, so an entry can carry `$(...)` or `;`. Where: stated once in `skill/SKILL.md` › Install, so plain `install` applies it too.
  - **Auth rule:** every catalog request the command makes, the skillset fetch and each member's `GET /api/skills/{slug}`, sends `Authorization: Bearer <token>` with the token from `~/.s3df-access-token`, because the catalog refuses unauthenticated reads (Measured facts › cli-auth). A 401 on the skillset fetch stops the command and tells the user to run `s3df login`. The token is read inside the command that sends it, as `-H "Authorization: Bearer $(cat ~/.s3df-access-token)"`, so its value never enters the session transcript or the model's context, and it is sent only to the catalog base URL, never to GitHub or to a member's `repo_url`. Where: the rule is stated once in `skill/SKILL.md`, next to **Token file** in the header block, so the per-skill install flow the loop reuses also sends the token.
  - **Summary line:** the command ends by printing how many members were installed, skipped, and failed, for example `Done: 3 installed, 1 skipped, 1 failed (5 members).` Below it, each failed member gets one line with its slug, the reason, and the next step, for example `✗ compress: skill_path /skills/compress is not in the repository. Tell the skill's submitter, or flag the skill on its catalog page.` A failure that scrolled past mid-run is then still visible at the end. When any member failed, a last line says that running the command again retries only the failed members, because installed members are skipped.
- **FR-8:** A `/skillsets` page in the frontend lists all skillsets as cards. A "Skillsets" link is added to the top nav alongside "Guides". Authenticated users see a persistent "+ Create Skillset" page-header button (visible whether or not skillsets exist). Empty state for authenticated: "No skillsets yet. [Create a skillset →]". Empty state for unauthenticated: "No skillsets yet. Skillsets are curated bundles of skills. Sign in to create one." (no button).
- **FR-9:** A `/skillsets/[slug]` detail page shows description, curator, skill list, and a copyable command block: `/agent-knowledge-hub install skillset <slug>`, the same form as the success metrics (no browser-side install action). If any member skill has `visibility: internal`, show an amber notice **above the skill list**: "N skill(s) in this set require SLAC GitHub access." Skills are displayed in the stored order (FR-2f).
- **FR-10:** Skill detail page shows "Part of N skillset(s)" section with links. Section is hidden when `skillset_count === 0`.
- **FR-11:** Skill list cards show "in N skillset(s)" count as a separate line below the description (not in the badge row), rendered only when `skillset_count > 0`.
- **FR-12:** Admin can delete or rename any skillset.
- **FR-13:** Curator can edit name/description and delete their own skillset.

### Non-functional

- **NFR-1:** Skillset list and detail pages load in < 500ms (p95).
- **NFR-2:** No membership change uses a multi-document transaction. Add, remove, and reorder are each one single-document update on `Skillset`. The cascade when a skill is deleted is one `update_many`, which is atomic for each `Skillset` document it changes but not across them. The test database (`mongomock`) cannot run transactions, so this keeps every membership path testable (Measured facts › transactions-in-tests).
- **NFR-3:** `batch_skillsets_for_skills` hydrates a page of skills with one query on `members.skill_id` — no N+1.
- **NFR-4:** AKH `install skillset` is safe to re-run (idempotent per skill).
- **NFR-5:** Every successful skillset write logs one INFO line from `services/skillset.py` with the actor's `user_id`, the action (create, edit, delete, add, remove, reorder, cascade), the stored skillset slug, and the stored skill slug when there is one. Removal pulls the member's `added_by` with it and deleting a skillset deletes the document, so this line is the only record of who removed a member, including a submitter removing their skill from another user's skillset or an admin moderating one. The line uses the stored slugs, which the slug validators have checked, rather than raw path parameters. The cascade writes one line per skill delete, and only when the skill was in at least one skillset; the line names every skillset slug the cascade changed. `update_many` returns only a count, so `purge_for_skill(skill_id, skill_slug, actor_id)` reads the slugs of the skillsets holding the skill just before its `update_many`; a skillset that gains the skill between the read and the update is still cleaned but goes unnamed. `skill_repository.delete()` gains an `actor_id` parameter, which `delete_skill` in `routers/skills.py` passes as `user.user_id`, as `update_skill` already does for `skill_repository.update()`.

### Acceptance Criteria

- **AC-1:** Given an authenticated user, when they POST `/api/skillsets` with a valid name, then a skillset is created and returned with slug, curator, and empty member list.
- **AC-2:** Given a skillset curator, when they PUT `/api/skillsets/{slug}/skills/{skill_slug}`, then the skill is appended to the end of the skillset's members.
- **AC-3:** Given a skillset curator, when they DELETE `/api/skillsets/{slug}/skills/{skill_slug}`, then the skill is removed from the skillset's members.
- **AC-4:** Given a user, when they GET `/api/skillsets/{slug}`, then the response includes `version` and the members in stored order, each with a hydrated skill summary (name, slug, description, labels, visibility, status).
- **AC-5:** Given a skill in 2 skillsets, when the skill detail page loads, then "Part of 2 skillset(s)" appears with links to both.
- **AC-6:** Given `install skillset lcls-starter` in an AKH session, when the command runs, then members install in stored order, with skips and failures reported per FR-7 and a summary line at the end.
- **AC-7:** Given a signed-in user who is not allowed to change a skillset under ADR-U19 › Permission rules, when they PUT or DELETE a member of it, then a 403 is returned.
- **AC-8:** Given an admin, when they DELETE `/api/skillsets/{slug}`, then the skillset and its members are removed in one delete.
- **AC-9:** Given a curator on the skillset detail page, when they click "Add new skill →", they land on `/skills/submit?skillset=<slug>`. After successful submission, the new skill appears in the skillset.
- **AC-10:** Given a submit form loaded with `?skillset=<slug>` where the submitter owns the skillset, when the skill is created, it is automatically added to that skillset. If the submitter does not own the skillset, the skill is created normally with no skillset assignment.
- **AC-11:** Given a skill submitted by user U and a skillset curated by user V that contains it, when U sends DELETE `/api/skillsets/{slug}/skills/{skill_slug}`, then 204 is returned and the skill leaves the skillset. When U sends the same DELETE for a skill U did not submit, 403 is returned.
- **AC-12:** Given a skillset owner, when they PUT `/api/skillsets/{slug}/order` with the current `version` and a permutation of the members, then the new order is stored and `version` increments. A stale `version` returns 409 and the stored order is unchanged. A list that adds, drops, or repeats a member returns 422.
- **AC-13:** Given the search picker on the skillset page, when the owner types a fragment of a skill name that is not a whole word (for example "depl" for a skill named with "deploy"), then that skill appears in the results.
- **AC-14:** Given a skillset whose second member's `skill_path` no longer exists in its repository, when `install skillset` runs, then that member is reported as failed and the remaining members still install.
- **AC-15:** Given a skill that is in two skillsets, when the skill is deleted, then it is removed from both skillsets' members.

---

## Architecture Decision Records

### ADR-U18: Skillset data model — embedded ordered member list

**Status:** Proposed
**Date:** 2026-10-14

#### Context
A skillset is an ordered many-to-many relationship between a `Skillset` and `Skill` documents. The design must support add, remove, curator-set order (FR-2f), a reverse lookup from a skill to its skillsets (FR-6, FR-11), and removal from every skillset when a skill is deleted. NFR-2 rules out a multi-document transaction for each of these.

#### Options

| Option | Fact that decides it |
|---|---|
| **Embedded ordered list of member subdocuments on `Skillset`** (chosen) | Add, remove, reorder, and the delete cascade are each one atomic update on a `Skillset` document. A multikey index on `members.skill_id` answers the reverse lookup for a page of skills in one indexed query. Subdocuments keep `added_by` and `added_at`, so each current member records who added it and when; removals and deletes are recorded only by NFR-5's log line. |
| Separate member collection, one document per membership | Order needs a position on every member document, so a reorder writes many documents, and an add or remove also writes the count on `Skillset`. Those writes are atomic only inside a transaction, and the test database cannot run transactions (Measured facts › transactions-in-tests). |
| Integer `position` on member documents | Renumbering in one pass violates a unique `(skillset_id, position)` index. A two-phase renumber takes 2N writes and is not atomic. Two concurrent adds read the same maximum position and collide. |
| Float `position` on member documents | A move is one write, but repeated moves into the same slot run out of float precision (Measured facts › float-gap), so a renumber job is needed. |
| Ordered id list on `Skillset` plus member documents | A reorder is atomic, but membership is stored in two places. A crash between the two writes of an add leaves a member that is missing from the order. |

#### Decision
**Store members as an ordered list of subdocuments on `Skillset`, with a `version` counter for optimistic concurrency.** There is no separate member collection.

#### Consequences
- `Skillset`: `slug`, `name`, `description`, `created_by`, `created_at`, `updated_at`, `members: List[SkillsetMember]`, `version: int`.
- `SkillsetMember` is an embedded Pydantic `BaseModel`, not a Beanie `Document`: `skill_id` (stringified ObjectId, the same convention as `SkillLabel.skill_id`), `added_by`, `added_at`.
- The member count is derived when a response is built; ADR-U18 › Orphan members says how for `SkillsetOut` and `SkillsetListOut`. No count is stored, so no count can drift.
- Indexes: `slug` unique, `created_by`, and `members.skill_id` (multikey).
- **Write shapes** (normative; other sections reference these by name):
  - *add:* `update_one({_id, "members.skill_id": {$ne: skill_id}}, {$push: {members: member}, $inc: {version: 1}})`. No match on an existing skillset means the skill is already a member (409).
  - *remove:* `update_one({_id, "members.skill_id": skill_id}, {$pull: {members: {skill_id}}, $inc: {version: 1}})`. No match means the skill is not a member (404).
  - *reorder:* the service reads the skillset and compares the request's `version` with the stored one before anything else; a mismatch returns 409. Only then does it compare `skill_slugs` with the member slugs (ADR-U18 › Member resolution), and a list that adds, drops, or repeats a member returns 422. A page made stale by a concurrent add or remove therefore always gets 409, although its list also differs. `reordered` is built from the subdocuments of that read, so `added_by` and `added_at` are kept. The write is `update_one({_id, version: v}, {$set: {members: reordered}, $inc: {version: 1}})` with the request's `v`; no match means another write landed after the read (409).
  - *edit details:* `update_one({_id}, {$set: {<name and description fields present in the request>, updated_at: now}})`. No `Skillset` write calls Beanie `save()` or `replace()`. Beanie 1.26 `save()` writes every field of the copy it holds, so a PATCH that read the document before a concurrent add would drop that member and set `version` back to a value a stale page may still hold.
  - *cascade:* `update_many({"members.skill_id": skill_id}, {$pull: {members: {skill_id}}, $inc: {version: 1}})`, run from `skill_repository.delete()` in `backend/app/services/skill.py` before its `skill.delete()`. If the delete fails partway, the skill document still exists, so the user can repeat the delete and the cascade finishes on the second run.
  - *delete skillset:* delete the `Skillset` document. Its members go with it.
- **Member resolution** (normative). Add accepts only an active skill, as `skill_repository.get(skill_slug)` does by default, so adding a deactivated skill returns 404. Remove accepts a skill of any status, as `skill_repository.get(skill_slug, include_deactivated=True)` does, and the submitter check in ADR-U19 › Permission rules uses that document. Reorder maps the stored `skill_id`s to slugs with one `Skill` query and no status filter. A deactivated member can therefore be removed and reordered, which FR-5 requires because the page shows it. `services/skillset.py` queries `app.models.skill.Skill` directly and does not import `app.services.skill`, which imports the skillset service for the cascade.
- **Orphan members.** A member whose `skill_id` has no `Skill` document is an orphan. One appears when an add resolves the skill before a concurrent skill delete runs the cascade and pushes after it, and one appears for every skill deleted while Slice 1 is rolled back. FR-5's hydration omits orphans, a reorder's `skill_slugs` must not include them, and the reorder's `$set` drops them. Without this rule an orphan could be neither hydrated nor removed by slug, and every later reorder of that skillset would return 422. `SkillsetOut.member_count` is the number of hydrated members, so the detail page and the install loop's empty-skillset check never count an orphan. `SkillsetListOut.member_count` stays `len(members)` and counts an orphan until a reorder drops it, which avoids a `Skill` query on the list endpoint.
- #029 cannot store pending inclusion requests as a status on `SkillsetMember`, because every reader treats `members` as the member set: the count, the display order, and the install order. Requests need their own collection.
- The 16 MB BSON document limit is far above any expected skillset size, so the design sets no member cap.

---

### ADR-U19: Curator permissions — any authenticated user (not admin-only)

**Status:** Proposed
**Date:** 2026-06-03, amended 2026-10-14

#### Context
Should skillset creation be open to all authenticated users (like label application), or restricted to admins? And what say does a skill's author have when someone else's skillset includes their skill?

#### Options

| Option | Pros | Cons |
|---|---|---|
| Admin-only | Prevents spam/low-quality collections | Blocks facility leads from self-serving; admin bottleneck |
| Any authenticated user | Facility leads are self-sufficient | Potential for low-quality or duplicate collections |

Skill author's say over inclusion:

| Option | Fact that decides it |
|---|---|
| **Author can remove their skill from any skillset** (chosen) | One extra condition on the existing remove endpoint. No new collection, no queue. |
| Per-skill "allow inclusion" flag | Adds a schema field and an edit-form control, and does nothing about a membership the author objects to after it exists. |
| Author approval for every add | Membership could not ship until #029's request queue exists. |
| No say | An author has no way to withdraw a skill from a set they object to. |

#### Decision
**Any authenticated user can create and manage their own skillsets.** Same model as label application — community-driven. Admins retain delete/rename powers for moderation. With a small, known user community (SLAC), spam risk is low. **A skill's submitter can remove that skill from any skillset.**

#### Permission rules (normative)

| Action | Allowed for |
|---|---|
| Create a skillset | Any signed-in user |
| Edit name or description, delete a skillset | Skillset owner, admin |
| Add a member, reorder members | Skillset owner, admin |
| Remove a member | Skillset owner, admin, or the member skill's submitter |
| Auto-add on submit (FR-2b) | Skillset owner only; otherwise the `skillset` parameter is ignored |

"Skillset owner" means `skillset.created_by == user.user_id`. "The member skill's submitter" means `skill.submitter_id == user.user_id`. Both fields hold `User.user_id` from `backend/app/auth.py`; `create_skill` in `backend/app/routers/skills.py` passes `submitter_id=user.user_id`. "Admin" means `user.is_admin`.

#### Consequences
- `POST /api/skillsets` requires `get_current_user`; sets `created_by = user.user_id`
- `PATCH /api/skillsets/{slug}` (name/description update) and `DELETE /api/skillsets/{slug}` live on the main skillsets router and are gated by the permission rules above. No separate admin router is needed for these operations.
- Note: `slug` is immutable post-creation and must not appear in `SkillsetUpdate`.
- A submitter's removal is not sticky. Nothing records it, so the owner or an admin can add the skill again. A durable opt-out is out of scope for this version.

---

### ADR-U20: AKH `install skillset` — sequential per-skill install reuse

**Status:** Proposed
**Date:** 2026-06-03, amended 2026-10-14

#### Context
"Install a skillset" means installing N individual skills. Options: new dedicated endpoint that returns a bundle manifest, or reuse the existing per-skill install flow in the AKH skill.

#### Options

| Option | Pros | Cons |
|---|---|---|
| New `/api/skillsets/{slug}/install-manifest` endpoint | Single API call from agent | Duplicates install logic in backend; backend shouldn't know about agent install paths |
| Agent-side loop using existing per-skill install | Reuses all existing install primitives (path guard, git-clone, copy-from-clone, idempotency) | N API calls, slightly slower |

#### Decision
**Agent-side loop.** The AKH skill's `install skillset <slug>` fetches `GET /api/skillsets/{slug}`, extracts the member slugs in stored order, asks once under FR-7's confirm rule, and runs the existing `install <slug>` flow for each. Skips and failures follow FR-7's skip rule and failure rule. No new backend install logic needed — only the skillset read endpoint is new.

#### Consequences
- Requires `GET /api/skillsets/{slug}` to return member skill slugs in stored order
- AKH SKILL.md gains one new sub-command section
- Install is sequential (not parallel) to avoid thundering-herd on GitHub rate limits
- Progress reported per skill: `[1/5] Installing lcls-tools... ✓`, `[2/5] Skipping akh-core (already installed)`

---

## Module Design

### Backend

| Module | Responsibility | Interface | Status | Testable |
|---|---|---|---|---|
| `models/skillset.py` | `Skillset` Beanie document with an embedded `SkillsetMember` model (ADR-U18) | Document class + indexes | New | Yes |
| `schemas/skillset.py` | Pydantic I/O: `SkillsetCreate`, `SkillsetUpdate`, `SkillsetOrderIn`, `SkillsetOut`, `SkillsetListOut` | Pydantic models | New | Yes |
| `services/skillset.py` | CRUD, membership, order, and batch hydration for skills. Writes follow ADR-U18 › Write shapes; checks follow ADR-U19 › Permission rules. | `create()`, `get()`, `list(created_by=None)`, `update()`, `delete()`, `add_skill()`, `remove_skill()`, `reorder()`, `batch_skillsets_for_skills()`, `purge_for_skill()` | New | Yes |
| `routers/skillsets.py` | HTTP layer: CRUD, membership, and order endpoints | REST routes | New | Integration |
| `routers/skills.py` | `_skill_to_out()` gains one parameter, `skillsets: Optional[List[SkillsetRef]] = None`, and sets `skillset_count` to its length; only `get_skill` passes real values, and the write handlers pass none. `_skill_to_list_out()` gains `skillset_count: int = 0`; the three calls in `routers/users.py` pass none and show no count, as they already show no labels. `list_skills` calls `batch_skillsets_for_skills()` next to its `label_service.batch_labels_for_skills()` call and passes `skillset_count` to `_skill_to_list_out()`. | Modify `_skill_to_out()`, `_skill_to_list_out()`, `list_skills` | Modify | Yes |
| `schemas/skill.py` | Add `skillset_count: int`, `skillsets: List[SkillsetRef]` to `SkillOut`; add `skillset_count: int` to `SkillListOut` | Schema fields | Modify | Yes |
| `app/models/__init__.py` | Add `Skillset` to `ALL_MODELS` (required for Beanie initialization). `SkillsetMember` is embedded and is not registered. | Module list | Modify | Yes |
| `app/main.py` | Register `routers/skillsets.py` router with `app.include_router()` | App wiring | Modify | Yes |
| `services/skill.py` | `delete(skill, actor_id)` calls `skillset_service.purge_for_skill(skill_id, skill.slug, actor_id)` next to its existing `label_service.purge_for_skill(skill_id)` call (ADR-U18 › Write shapes › cascade; NFR-5 gives the reason for the extra arguments) | Cascade | Modify | Yes |

### Frontend

| Module | Responsibility | Status |
|---|---|---|
| `frontend/app/skillsets/page.tsx` | List all skillsets (cards: name, description, skill count, curator); persistent "+ Create Skillset" header button for authenticated users | New |
| `frontend/app/skillsets/[slug]/page.tsx` | Skillset detail: description, curator, copyable install command block, amber SLAC-only notice above skill list (if any internal), skill list in stored order with deactivated members marked. Owner view adds the search picker (FR-2c), up and down controls (FR-2f), Remove per member, and "Add new skill →" (FR-2a). | New |
| `frontend/app/skillsets/create/page.tsx` | Create skillset form (name, slug auto-derive, description); `<AuthGuard>` fallback banner | New |
| `frontend/components/skillset-card.tsx` | Reusable skillset card component | New |
| `frontend/components/skill-search-picker.tsx` | Typeahead over `GET /api/skills/summary?q=` (FR-2c), using the same fetch-per-keystroke with `AbortController` cancellation as `label-picker.tsx`. Unlike `label-picker.tsx`, which shows nothing on an empty result and swallows fetch errors, it shows the FR-2g messages for both. | New |
| `frontend/components/add-to-skillset-menu.tsx` | "Add to skillset" menu on the skill page (FR-2d) | New |
| `frontend/app/skills/[slug]/page.tsx` | Add "Part of N skillset(s)" section (hidden when count=0), with a Remove control per skillset for the skill's submitter (FR-2e); host the add-to-skillset menu | Modify |
| `frontend/components/skill-card.tsx` | Add "in N skillsets" count as separate text line below description (when `skillset_count > 0`) | Modify |
| `frontend/types/skillset.ts` | TypeScript interfaces for `SkillsetOut`, `SkillsetListOut` | New |
| `frontend/types/skill.ts` | Add `skillset_count: number` and `skillsets: SkillsetRef[]` fields | Modify |
| `frontend/app/api/skillsets/route.ts`, `frontend/app/api/skillsets/[slug]/route.ts`, `frontend/app/api/skillsets/[slug]/order/route.ts`, `frontend/app/api/skillsets/[slug]/skills/[skill_slug]/route.ts` | Next.js route handlers that forward the browser's skillset calls to the backend with `backendHeaders()` from `frontend/app/api/_internal.ts`, as the existing `frontend/app/api/skills/...` handlers do. The list handler forwards the query string (`page`, `page_size`, `created_by`) the way `frontend/app/api/labels/route.ts` does. The member handler (PUT and DELETE) and the skillset DELETE return `new NextResponse(null, { status: 204 })` when the backend answers 204, as the DELETE in `frontend/app/api/skills/[slug]/route.ts` does; `NextResponse.json(data, { status: 204 })`, the pattern in `frontend/app/api/skills/[slug]/flag/route.ts`, throws on a 204, so every successful add or remove would reach FR-2g as a failure. Every browser call reaches the backend through such a handler; without them the calls carry neither `X-Internal-Secret` nor the user. | New |
| `frontend/app/api/skills/summary/route.ts` | Forwards `GET /api/skills/summary` with its query string, for the FR-2c picker. Without it, `frontend/app/api/skills/[slug]/route.ts` serves the request with slug `summary` and builds the backend URL without the query string, so the picker would receive every active skill unfiltered. | New |
| `frontend/lib/api.ts` | Add `listSkillsets()` and `getSkillset()` for the server-rendered skillset pages, next to `getSkill()` | Modify |

### AKH Skill

| Module | Responsibility | Status |
|---|---|---|
| `skill/SKILL.md` | Add `install skillset <slug>` sub-command | Modify |

---

## System Design

Permissions on every write below follow ADR-U19 › Permission rules.

```
Browser / AKH skill
        │
        ├─ GET  /api/skillsets[?created_by=<user_id>]        → list skillsets (page-number pagination)
        ├─ POST /api/skillsets                               → create
        ├─ GET  /api/skillsets/{slug}                        → detail: version + members in stored order
        ├─ PATCH /api/skillsets/{slug}                       → update name/description
        ├─ DELETE /api/skillsets/{slug}                      → delete
        ├─ PUT  /api/skillsets/{slug}/order                  → reorder
        ├─ PUT  /api/skillsets/{slug}/skills/{skill_slug}    → add member
        └─ DELETE /api/skillsets/{slug}/skills/{skill_slug}  → remove member

GET /api/skills/{slug}
  → SkillOut now includes:
      skillset_count: int
      skillsets: [{ slug, name }]   ← reverse lookup on members.skill_id

GET /api/skills (list)
  → SkillListOut now includes:
      skillset_count: int           ← batch hydrated in list_skills

AKH skill: install skillset <slug>
  1. GET /api/skillsets/{slug}          → member slugs in stored order
     GET /api/skills/{slug} per member  → repo_url, skill_path, pinned_commit_sha, has_mcp_server, has_scripts
     FR-7's confirm rule                → replace questions, then one prompt; no installs nothing
  2. for each member in stored order, printing [i/M]: skip or failure line for an unlisted member,
     otherwise install it under FR-7's failure rule:
       git-clone-to-temp(...)           → existing primitive
       copy-from-clone(...)             → existing primitive
  3. print FR-7's summary line
```

**Data model** (fields and write shapes are normative in ADR-U18):

```python
# models/skillset.py
_SKILLSET_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")  # mirrors _LABEL_NAME_RE

class SkillsetMember(BaseModel):
    skill_id: str                # stringified ObjectId — matches SkillLabel.skill_id (str, not PydanticObjectId)
    added_by: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Skillset(Document):
    slug: str                    # unique, URL-safe; validated by @field_validator below
    name: str                    # max_length=200
    description: str = ""        # max_length=2000
    created_by: str
    created_at: datetime
    updated_at: datetime
    members: List[SkillsetMember] = Field(default_factory=list)   # stored order is display and install order
    version: int = 0             # incremented by every membership write

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not v or len(v) > 100 or not _SKILLSET_SLUG_RE.match(v):
            raise ValueError("slug must be lowercase alphanumeric/hyphen, 1–100 chars")
        return v

    class Settings:
        name = "skillsets"
        indexes = [
            IndexModel([("slug", ASCENDING)], unique=True),
            IndexModel([("created_by", ASCENDING)]),
            IndexModel([("members.skill_id", ASCENDING)]),   # multikey reverse lookup
        ]
```

**API contract additions:**

```
GET /api/skillsets?page=&page_size=&created_by=
  → { items: SkillsetListOut[], total, page, page_size }
  SkillsetListOut: { slug, name, description, created_by, member_count, created_at }
  member_count = len(members), computed when the response is built

GET /api/skillsets/{slug}
  → SkillsetOut: { slug, name, description, created_by, member_count, created_at, version,
                   skills: [{ slug, name, description, labels, avg_rating, visibility, status }] }
  skills are in stored order and include members whose status is not active (FR-5)

POST /api/skillsets
  Body: { name, slug (optional, auto-derived), description }
  → SkillsetOut (201)
  → 409 Conflict if slug already taken (body: { detail, suggested_slug })

PATCH /api/skillsets/{slug}
  Body: { name?, description? }   ← slug is immutable and excluded from update
  → SkillsetOut

PUT /api/skillsets/{slug}/order
  Body: SkillsetOrderIn { skill_slugs: [...], version }
  → SkillsetOut (200) with the new order and version
  → 409 if version is stale; 422 if skill_slugs is not exactly the current member set

PUT /api/skillsets/{slug}/skills/{skill_slug}
  → 204 No Content; 409 if already a member; 404 if the skill does not exist or is deactivated (ADR-U18 › Member resolution)
  rate-limited at 50/hour per user across all skillsets and skills, with
  Limiter(key_func=user_id_key_func, key_style="endpoint"); user_id_key_func is in
  backend/app/auth.py. key_style="endpoint" counts per route function. slowapi's default,
  key_style="url", counts per request path, as create_flag in routers/skills.py does, so each
  (skillset, skill) path would get its own 50 and no user would reach the limit, because a
  repeated add returns 409. The labels pattern keys by get_remote_address, and every browser
  request reaches the backend from the Next.js server, so with an endpoint scope that key
  would give all web users one shared bucket.

DELETE /api/skillsets/{slug}/skills/{skill_slug}
  → 204 No Content; 404 if not a member

DELETE /api/skillsets/{slug}
  → 204 No Content

Every endpoint under /api/skillsets/{slug} returns 404 when no skillset has that slug.
```

---

## Trade-offs

```
Choice: Derive member_count from len(members) (vs. a stored counter)
  + The count lives in the same document as the members, so it cannot drift
  - The list endpoint reads each skillset's members array to count it
  Decision: Derive. Skillsets are small, and a stored counter would need its own update path.

Choice: Optimistic version check on reorder (vs. last write wins)
  + A reorder sent from a stale page cannot silently undo a concurrent add or remove
  - The owner sees a 409 and a reload when two edits race
  Decision: Version check. Races on one skillset are rare, and a reload is cheap.

Choice: Include skillsets on SkillOut (vs. separate endpoint GET /api/skills/{slug}/skillsets)
  + One round-trip for skill detail page
  - Adds ~50 bytes per skill on every detail fetch
  Decision: Include in SkillOut. Omit from SkillListOut (same as labels approach).

Choice: Agent-side loop for install (vs. new bundle install endpoint)
  + Zero new backend install logic; reuses all existing primitives incl. path guards
  - N sequential API calls from agent
  Decision: Agent-side loop. Backend shouldn't own agent install paths.

Choice: Auto-derive slug from name (vs. user-chosen slug only)
  + Curator convenience
  - May collide; curator must be allowed to override before creation
  Decision: Auto-derive with editable override in creation form. Validate uniqueness on submit.
```

---

## Delivery Slices

**Placement invariant:** every artefact — requirement, acceptance criterion, doc edit, test — lands in the slice where its statement first becomes true.

**Build-order prerequisites:** Slice 2+3 and Slice 4 each depend on Slice 1, because they call its endpoints. Slice 4 does not depend on Slice 2+3, but Slice 2+3 must not ship before Slice 4: the skillset page's copyable command block (FR-9) tells users to run `install skillset <slug>`, and that command exists only once Slice 4 lands, so Slice 4 merges before Slice 2+3 is deployed to production. Slice 4 ships when it merges to `main`, not at a deploy: the AKH plugin's entry in `marketplace_json` (`backend/app/routers/catalog.py`) names no ref, so `/plugin install agent-knowledge-hub` fetches the default branch, and the root `.claude-plugin/plugin.json` points `skills` at `./skill/`. That holds for a new install. An existing install gets a new copy only when the plugin's computed version changes (References › Claude Code plugin updates), so Slice 4 bumps `version` in `.claude-plugin/plugin.json`. Because Slice 4 goes live when it merges, it merges only after Slice 1 is deployed to production, or every `install skillset` returns "Skillset not found". Slice 4 also waits for the server-side validation task in Follow-ups. Together these rules give one order: deploy Slice 1 and the validation task to production, in one release or two; merge Slice 4; then deploy Slice 2+3 in a later production release than Slice 1.

**Slice 1 — Backend data model + API** (no frontend, no AKH change). Covers AC-1 to AC-4, AC-7, AC-8, AC-11, AC-12, AC-15, and the backend halves of AC-5 and AC-10.
- `Skillset` model with embedded `SkillsetMember` and indexes (ADR-U18); register `Skillset` in `app/models/__init__.py` `ALL_MODELS`
- `services/skillset.py` with the interface in Module Design; writes follow ADR-U18 › Write shapes, checks follow ADR-U19 › Permission rules, and each write logs the NFR-5 line
- `routers/skillsets.py`: CRUD, membership, and order endpoints, including the `created_by` list filter
- Register skillsets router in `app/main.py`
- Extend `SkillOut` / `SkillListOut` with `skillset_count` + `skillsets`, and change `_skill_to_out()` and `_skill_to_list_out()` as the `routers/skills.py` row in Module Design describes; only the `get_skill` handler fetches skillsets
- `SkillCreate` gains optional `skillset_slug: str | None = None`. After a successful skill insert, `create_skill` loads that skillset and checks `skillset.created_by == user.user_id` itself before it calls `skillset_service.add_skill()`. The router makes this check because `add_skill()` also admits admins, while ADR-U19 › Permission rules makes auto-add owner-only, so an admin's `skillset_slug` for another user's skillset is ignored as well. A missing skillset, a non-owner, and the skillset service's own errors are skipped silently and logged at INFO, with the requested `skillset_slug` formatted by `%r` as `get_current_user` in `backend/app/auth.py` logs a rejected `X-Forwarded-User`: the value is unvalidated request text, and a newline in it could otherwise write a line that reads as an NFR-5 record. The response is still 201 with the created skill: the skill already exists, so failing the request would make the user's retry fail with 409 (cross-ownership deferred to #029)
- Add `skillset_service.purge_for_skill(skill_id, skill_slug, actor_id)` to the `skill_repository.delete()` cascade (ADR-U18 › Write shapes › cascade), with the `actor_id` parameter NFR-5 adds to `skill_repository.delete()`. The parameter is required, as it is on `update()`, so the four existing tests that call `skill_repository.delete(skill)` (two in `backend/tests/test_user_activity.py`, one each in `test_skill_crud.py` and `test_catalog_scale.py`; `grep -rn "skill_repository.delete(" backend/tests`) pass an actor id in the same change, and M13 and O9 do too
- `list_skills` in `routers/skills.py` batch-hydrates `skillset_count`
- Rate-limit `POST /api/skillsets` creation at 20/hour per user, keyed the same way as `PUT /api/skillsets/{slug}/skills/{skill_slug}` in the API contract
- Unit + integration tests

**Slice 2+3 — Frontend: skillset browse, detail, and create/manage** (shipped together — browse-only page without create CTA is a broken UX). Covers AC-9 and AC-13, and the frontend halves of AC-5 and AC-10.
- `/skillsets` list page with "Skillsets" top-nav link
- `/skillsets/[slug]` detail page with copyable install command block, stored order, and deactivated members marked
- Skill detail page: "Part of N skillset(s)" section (hidden when count=0), with the submitter's Remove control (FR-2e) and the "Add to skillset" menu (FR-2d)
- Skill card: "in N skillsets" line below description (when count > 0)
- Create skillset form (name, slug, description) wrapped in `<AuthGuard>` with same fallback banner as `skills/submit/page.tsx`
- Slug collision: inline error "Slug already taken. Try: <suggested-alternative>" with one-click accept
- Admin management is API-only in this version; `/admin/skillsets` page is deferred
- Owner view of the skillset page: search picker (FR-2c), Remove per member, up and down controls (FR-2f)
- "Add new skill →" button on skillset detail page (owner only) — links to `/skills/submit?skillset=<slug>`; after submission redirects back to skillset detail
- Skill submit form (`/skills/submit`) reads optional `skillset` query param: if set and submitter owns that skillset, passes `skillset_slug` to the create endpoint; shows a subtle "Will be added to skillset: <name>" notice above the submit button
- Edit name/description and delete skillset, shown per ADR-U19 › Permission rules
- The Next.js route handlers under `frontend/app/api/skillsets/`, the `frontend/app/api/skills/summary/route.ts` handler, and the `frontend/lib/api.ts` additions, as listed in Module Design › Frontend

**Slice 4 — AKH skill: `install skillset <slug>`**. Covers AC-6 and AC-14.
- New sub-command in `skill/SKILL.md`
- Fetches skillset detail and loops the per-skill install in stored order, applying FR-7's confirm rule, skip rule, failure rule, argument rule, auth rule, and summary line
- New cases in `skill/SKILL.md` › Error handling, as listed in the Definition of Done
- "Install a skillset" entry in the Commands section of `frontend/app/guides/agent-knowledge-hub/page.tsx`
- Bump `version` in `.claude-plugin/plugin.json`. Without the bump, every user who already installed the plugin keeps the cached copy and never receives `install skillset`. The CHANGELOG note for existing users names the update commands: `/plugin marketplace update SLAC-Agent-Knowledge-Hub` in a session, or `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub` in a shell, because auto-update is off by default for a third-party marketplace

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Slug collision on auto-derive | Medium | Low | Validate uniqueness server-side; return 409 with suggested alternative |
| A member's `skill_path` no longer exists upstream, so its install fails | Medium | Low | No guard exists today: `skill/SKILL.md` › Error handling has no case for it. This task adds FR-7's failure rule. Observed on dev (Measured facts › stale-skill-path). |
| AKH install skillset hits GitHub rate limit mid-install | Low | Medium | `skill/SKILL.md` › Error handling suggests `GITHUB_TOKEN` on a 403. Under FR-7's failure rule the loop continues, so later members likely fail the same way and the summary line shows it. |
| Two writers race on one skillset: two tabs, the owner and an admin, or the owner and a submitter's removal | Low | Low | The `version` check in ADR-U18 › Write shapes › reorder refuses a stale reorder with 409, and ADR-U18 › Write shapes › edit details keeps a PATCH from overwriting `members`. |
| A member's skill document is gone (an add raced a skill delete, or skills were deleted while Slice 1 was rolled back) | Low | Low | ADR-U18 › Orphan members: hydration omits the member and the next reorder drops it. |
| A skill's author removes it from a curated skillset without telling the curator | Low | Low | Accepted for this version; no notification is sent. |
| Large skillsets (50+ skills) slow install | Low | Low | Sequential by design; user sees progress. Per-member time is in Measured facts › install-time. |

---

## Definition of Done

- [ ] All acceptance criteria pass
- [x] Unit tests: `Skillset` model, `skillset_service` (create, add, remove, reorder, cascade, batch hydration, permission rules), slug validation
- [x] Integration tests: all CRUD endpoints, membership add/remove, order endpoint (200, 409, 422), 403 per ADR-U19 › Permission rules, submitter removal (AC-11), skill detail includes skillsets
- [ ] Frontend: `/skillsets` and `/skillsets/[slug]` render correctly; skill detail shows reverse links; create form submits and handles slug collision; owner management actions (search picker, remove, reorder, edit, delete) work; the "Add to skillset" menu and the submitter's Remove control, with its FR-2e confirmation, work on the skill page; each FR-2g outcome shows its message; `<AuthGuard>` fallback renders for unauthenticated users
- [ ] Frontend: "Add new skill →" button on skillset detail page (owner-only) links to `/skills/submit?skillset=<slug>`; submit form shows "Will be added to skillset: <name>" notice when `skillset` param is present and submitter owns it; after submission redirects to skillset detail page
- [x] Backend: `SkillCreate.skillset_slug` adds new skill to owned skillset post-creation; silently ignored if skillset not found or not owned
- [x] Backend: each of the seven actions in NFR-5 writes NFR-5's log line, including a submitter's removal from another user's skillset and the cascade (Slice 1)
- [ ] AKH skill: `install skillset <slug>` installs members in stored order and follows FR-7's confirm rule, skip rule, failure rule, argument rule, auth rule, and summary line
- [x] Security: every row of ADR-U19 › Permission rules has an allow test and a deny test
- [x] No N+1 queries on list views (batch hydration verified)
- [ ] CHANGELOG entry under `## Unreleased`: a feature headline plus bullets, each added in the slice that makes it true. Slice 1: the skillset endpoints, including `PUT /api/skillsets/{slug}/order` and the `created_by` filter on `GET /api/skillsets`; `skillset_count` and `skillsets` on skill responses; removal from every skillset when a skill is deleted; the rule that a skill's submitter can remove the skill from any skillset; and the per-user rate limits on creating a skillset and adding a member (the Slice 1 bullet and the API contract give the numbers). Slice 2+3: the skillset pages, the search picker (which matches part of a word), the "Add to skillset" menu, the submitter's Remove control, and reordering. Slice 4: `install skillset <slug>` with FR-7's confirm prompt and its skip, failure, and summary behaviour; plain `install` now refusing a `repo_url` or `skill_path` that fails FR-7's argument rule; Search and Install now sending the bearer token under FR-7's auth rule; and a note telling existing users how to pick up the updated `/agent-knowledge-hub` skill
- [ ] ADR files written to `docs/adr/` as `adr-u18-skillset-data-model.md`, `adr-u19-curator-permissions.md`, `adr-u20-akh-install-skillset.md`
- [ ] `README.md`: in Slice 2+3, a Skillsets paragraph with the `/skillsets` link, covering browsing and creating a skillset, adding a skill from its page with "Add to skillset", reordering, and a skill author's right to remove their skill from any skillset. In Slice 4, `install skillset <slug>` added to the "Install without leaving your assistant" section
- [x] `PRD.md` › 5. API Contract (summary): a `# Skillsets` block listing every endpoint in the System Design diagram, including `PUT /api/skillsets/:slug/order` and the `created_by` parameter on `GET /api/skillsets` (Slice 1). The #012 close-out updated the same block.
- [ ] `skill/SKILL.md` `install skillset <slug>` sub-command includes: the member list and single prompt from FR-7's confirm rule; the progress line format in ADR-U20 › Consequences; a failure line with the same `[i/M]` prefix that names the member and the reason; the empty-skillset message (`⚠ Skillset '<slug>' contains no skills.`); a 404 error for an unknown skillset slug; the 401 message from FR-7's auth rule; and FR-7's summary line
- [ ] `skill/SKILL.md` header block states FR-7's auth rule next to **Token file**, and `skill/SKILL.md` › Install states FR-7's argument rule and runs its clone step with the environment from FR-7's failure rule (Slice 4)
- [ ] `.claude-plugin/plugin.json` `version` is higher than on `main` before Slice 4 (Slice 4)
- [ ] `skill/SKILL.md` › Error handling gains four cases, each of which also applies to plain `install`: a `skill_path` missing from the clone; a clone failure on an internal repository, with FR-7's access hint; a 401, which points to `s3df login`; and a `repo_url` or `skill_path` that fails FR-7's argument rule, which aborts the install before any command runs. The existing path-traversal case and the argument-rule case together are FR-7's "path-guard abort". The section also states that inside `install skillset` each of its cases fails only that member, and the loop continues under FR-7's failure rule (Slice 4)
- [ ] `frontend/app/guides/agent-knowledge-hub/page.tsx` › Commands gains an "Install a skillset" entry with the command, one sentence saying it lists the members and asks once before installing (FR-7's confirm rule), one sentence on the skip and failure behaviour, and a note that it needs a SLAC token. The CLI authentication paragraph on the same page, which says read-only commands work without authentication, is corrected to match Measured facts › cli-auth (Slice 4)

---

## Measured facts — measured 2026-10-14, re-derive before implementing

No other section restates these values; they reference a row by its name.

| Fact | Value | How it was measured |
|---|---|---|
| text-vs-substring | On dev, `$text` returned 0 hits for `vclus` and `depl`; a case-insensitive substring match on name and description returned 2 for each. Whole words (`vcluster`, `deploy`) returned 2 both ways. | Read-only `count_documents` on the `skills` collection, run with `kubectl exec` in the dev backend pod against Percona Server for MongoDB `8.0.19-7`, comparing `{"$text": {"$search": q}}` with `{"$or": [{"name": {"$regex": q, "$options": "i"}}, {"description": {"$regex": q, "$options": "i"}}]}` |
| transactions-in-tests | 5 tests in `backend/tests/test_labels.py` are skipped because the test database cannot run transactions | `grep -c 'mongomock does not support MongoDB transactions' backend/tests/test_labels.py` |
| float-gap | 52 moves into the same slot before the midpoint of two float positions equals one of them | Start from positions 1.0, 2.0, 3.0; repeatedly move a member to the slot after the first member at the midpoint of its new neighbours; count moves until the midpoint equals a neighbour |
| summary-size | 13 active skills on dev; their slug, name, description, and rating serialize to about 5.9 KB of JSON | `find({"status": "active"})` with that projection in the dev backend pod, then `len(json.dumps(...))` |
| install-time | 1.3 s and 2.3 s for the two members that installed (`pptx`, `caveman`) | The SKILL.md install steps run in a loop under a temporary HOME, with metadata read from the dev DB |
| stale-skill-path | The dev catalog entry `compress` points at `/skills/compress`, which no longer exists in its repository; the entry has no pinned SHA | Shallow clone of `https://github.com/juliusbrussee/caveman` at HEAD `d262ab3` (2026-10-13); the skill now lives at `skills/caveman-compress` |
| test-baseline | 377 passed, 5 skipped, before any change for this task |
| slice-1-suite | 478 passed, 5 skipped after Slice 1; the new skillset modules (`models`, `schemas`, `services`, and `routers/skillsets.py`) have 100% line coverage | `python -m pytest -q` in `backend/`, and `--cov` over the four modules with `test_skillset_service.py` and `test_skillset_routes.py`, measured 2026-10-14 | `python -m pytest -q` in `backend/`, in a fresh venv built from `requirements.txt` and `requirements-dev.txt` |
| cli-auth | Without a token, the prod API answers with 401 `{"error":"no_token"}` on the browser path `/api/skills/summary` and on the CLI paths the AKH skill uses (ADR-P08): `/cli/api/skills/summary`, `/cli/api/skills`, and `/cli/api/skills/<slug>` | `curl -s https://agent-knowledge-hub.slac.stanford.edu/api/skills/summary`, and the same with `/cli/api/skills/summary`, `/cli/api/skills`, and `/cli/api/skills/pptx` |

---

## Board Review

**Amendment 2026-10-14:** ADR-U18 was replaced, and ADR-U19 gained the permission rules and author removal. User stories 2a, 16, and 17, FR-2c to FR-2g, NFR-5, AC-11 to AC-15, the Measured facts block, the Follow-ups section, and the Problems & Solutions and References entries were added. The success metrics, user stories 11 and 14, FR-2, FR-4, FR-5, FR-7, FR-9, NFR-2, NFR-3, AC-2 to AC-8, ADR-U20 (stored order and FR-7's rules), Module Design, System Design, Trade-offs, Delivery Slices, Risk Register, Definition of Done, and Test Plan were revised. The re-review of these changes follows; the original 2026-06-03 review is kept below it.

### Re-review of the 2026-10-14 amendment

**Verdict:** CLEAR WITH WARNINGS
**Date:** 2026-10-14
**Rounds:** 2

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | R1 0 design / 4 precision; R2 3 design / 5 precision | ADR-U18's MongoDB 8.0 claims hold. Existing installs never receive Slice 4 while `plugin.json` keeps `version` at 1.0.0. `GIT_TERMINAL_PROMPT=0` alone leaves askpass and GCM prompts. |
| codebase-arch-review | ⚠️ WARN | R1 4 design / 8 precision; R2 0 design / 3 precision | Added the edit-details write shape (a `save()` from a stale read drops members and rewinds `version`), member resolution and orphan rules, 409 before 422, and the one valid build order. |
| codebase-eng-review | ⚠️ WARN | R1 7 design / 3 precision; R2 2 design / 6 precision | Added the missing Next.js route handlers (the summary query string was dropped), per-user rate limits with `key_style="endpoint"`, and permission, cascade, frontend, and log tests. |
| doc-review | ⚠️ WARN | R1 2 design / 9 precision; R2 0 design / 8 precision | Added FR-7's auth rule (the CLI catalog paths return 401 without a token), the Slice 4 ordering, and Definition of Done rows for `skill/SKILL.md`, `PRD.md`, the guide page, and CHANGELOG. |
| security-review | ⚠️ WARN | R1 4 design / 2 precision; R2 1 design / 2 precision | Added FR-7's confirm and argument rules after finding that catalog `repo_url` values can carry shell syntax, the token-handling rule, NFR-5's audit log line, and escaping of request text in logs. |
| codebase-ux-review | ⚠️ WARN | R1 5 design / 2 precision; R2 2 design / 4 precision | Added FR-2g's feedback rule, a confirm step for the author's Remove, questions before the first clone, the replace prompt instead of overwriting a directory, and the failure recap in the summary line. |

**Amendments:** 30 design / 56 precision (Round 1: 22 / 28; Round 2: 8 / 28). Round 2's design amendments were closed by checks in the main session instead of a third round. `GIT_ASKPASS=` was tested on git 2.47.3: without it, a clone with `GIT_TERMINAL_PROMPT=0` still called the askpass helper twice; with it, no helper ran and the clone failed with `terminal prompts disabled`. The remaining Round 2 design amendments were probed by their reviewer or confirmed by another reviewer in the same round.
**Decisions:** 0 blocking; 9 judgement calls, all accepted by the user as defaulted (author removal is not sticky; per-user rate-limit key; the token rule in the `skill/SKILL.md` header; fix the guide's "no authentication" paragraph in this task; a confirm step before `install skillset`; server-side `repo_url` validation as a separate task deployed before Slice 4 merges; no "Add to skillset" menu for users who own no skillset; no curator signal on removal; keep 50 adds per user per hour); 19 defaulted.
**Accepted warnings:** The AKH install loop and the frontend checks are manual tests. mongomock does not exercise concurrency or index use. Motor, which Beanie 1.26 uses, was deprecated on 2026-05-14. A skill submitted from local files (`local://` repo URL) fails `install skillset` as a path-guard abort. A submitter has no UI path to remove a deactivated skill from someone else's skillset. The identity-header lead under Follow-ups › Outside this task is unverified.
**Unresolved decisions:** none

#### Reviewer output (final round)

<details>
<summary>research — Round 2 (PASS WITH WARNINGS)</summary>

**Summary**
- Most of the Round 1 factual claims hold. `user_id_key_func` exists and sees the user, because slowapi checks inside the endpoint after `get_current_user` sets `request.state.user`. Another reviewer's `key_style="endpoint"` correction is right (slowapi's default scopes by path). The `[slug]` route handler does drop the query string. The FR-7 regexes accept every stored GitHub entry and make single-quoting safe. The `/cli` ingress already routes the new endpoint.
- One claim was wrong, and this reviewer amended it (design). "Slice 4 ships when it merges" is true only for new installs. Root `.claude-plugin/plugin.json` pins `version: 1.0.0`, and Claude Code updates an installed plugin only when its version changes, so existing users would never get `install skillset`. Slice 4 now bumps the version, and the CHANGELOG note names the update commands.
- A second claim was partly wrong, and this reviewer amended it too (design). `GIT_TERMINAL_PROMPT=0` does not stop askpass programs or Git Credential Manager, so a clone could still stop for input mid-run, against the confirm rule's promise of an unattended run. Each clone now also sets `GIT_ASKPASS=` and `GCM_INTERACTIVE=0`.
- Amendments from different reviewers left two problems, both fixed by precision edits. The new required `actor_id` on `skill_repository.delete()` would break four existing tests. ADR-U18 still said `member_count` is `len(members)` after the Orphan members rule changed it. R17 also needed its own user ids, because the limiter keeps its counts across the whole test run.
- Total: 3 design and 5 precision amendments, and 2 defaulted decisions. A local-file skill being reported as a path-guard abort is recorded as LOW and not amended.

**Issues**

*Claim verdicts (Round 1 amendments)*

| Claim | Verdict | Evidence |
|---|---|---|
| `user_id_key_func` exists and `create_flag` uses it (API contract › add) | confirmed | `user_id_key_func` in `backend/app/auth.py` returns `user:<user_id>` from `request.state.user`; `_flag_limiter = Limiter(key_func=user_id_key_func)` decorates `create_flag` in `routers/skills.py`; `routers/me.py` uses it too. |
| The per-user key sees the user, not the address | confirmed | slowapi 0.1.9 runs `_check_request_limit` inside the endpoint wrapper (`extension.py`, `async_wrapper`), which FastAPI calls after resolving `Depends(get_current_user)`; both auth paths in `get_current_user` set `request.state.user`. The `SlowAPIMiddleware` in `main.py` checks only the main limiter, which has no default limits. |
| The labels limiter keys by address and browser calls all arrive from Next.js | confirmed | `routers/labels.py`: `Limiter(key_func=get_remote_address)`. Prod `ingress-frontend.yaml` sends `/` to the frontend; `ingress-api.yaml` sends only `/cli` and `/health` to the backend. `backendHeaders()` sets no `X-Forwarded-For`. |
| `frontend/app/api/skills/[slug]/route.ts` drops the query string (Module Design) | confirmed | GET builds `` `${BACKEND}/api/skills/${params.slug}` `` with no search params; no `frontend/app/api/skills/summary/` exists. A static `summary` segment takes precedence over `[slug]` in the App Router (Next.js 14.2.35), so the new handler fixes it. `labels/route.ts` forwards `request.nextUrl.searchParams` as cited. |
| FR-7 argument-rule regexes accept every stored GitHub entry | confirmed | Stored `repo_url` passes `_GITHUB_URL_RE` (`^https://github\.com/[^/]+/[^/]+$`) after `strip()`; GitHub owner names are alphanumeric plus `-`, repository names add `.` and `_`. The `Skill.skill_path` validator prefixes `/`, so `^/…` matches stored paths. Neither class contains `'`, so single quotes are sound, and neither value can start with `-`. |
| FR-7: `_GITHUB_URL_RE` accepts any character except `/` "in the repository segment" | partly wrong | It accepts any character except `/` in the owner segment too (`[^/]+/[^/]+`); Follow-ups already says "owner and repository segments". The argument-rule regex covers both, so only the justification is short. |
| FR-7: `skill_path` is checked only for `..` components | confirmed in substance | `Skill.validate_skill_path` also prefixes `/` and caps length at 500, but restricts no characters. |
| FR-7: `create()` stores a skill when GitHub cannot fetch it | confirmed | `services/skill.py` `create()` logs `github_fetcher failed` and `scan failed` and goes on to build the `Skill`. |
| `GIT_TERMINAL_PROMPT=0` makes an unreadable repository fail instead of prompting | partly true; amended (see Findings) | git docs: "If this Boolean environment variable is set to false, git will not prompt on the terminal". `prompt.c` `git_prompt()` tries `GIT_ASKPASS`, `core.askPass`, then `SSH_ASKPASS` first, so an askpass helper (for example one an IDE terminal exports) can still prompt. The argument rule forces `https://`, so SSH prompts cannot arise. |
| FR-7 auth rule reaches the new endpoint | confirmed | SKILL.md base URL is `https://agent-knowledge-hub.slac.stanford.edu/cli`; `ingress-api.yaml` rewrites `/cli/(.*)` to the backend, so `/cli/api/skillsets/{slug}` needs no ingress change; `get_current_user` Path 3 accepts the Bearer JWT. |
| Slice 4: the marketplace entry names no ref, so install takes the default branch | confirmed | `marketplace_json` entry is `{"source": "github", "repo": "slaclab/agent-knowledge-hub", "path": "skill"}`. Claude Code docs: `ref` "Defaults to the repository's default branch" (`origin/main`). The `path` key is not a `github` source field ("fields `repo`, `ref`, and `sha`, and no `path`"); `skill/` is reached through the root `.claude-plugin/plugin.json` (`"skills": "./skill/"`). |
| Slice 4: "ships when it merges to `main`" | wrong for existing installs | Root `.claude-plugin/plugin.json` sets `"version": "1.0.0"`, unchanged since it was created (`git log -- .claude-plugin/plugin.json`). Claude Code docs: "If you set `"version": "1.0.0"` and push new commits without changing it, users don't receive them." Only new installs get Slice 4 on merge. |

*Findings*

- HIGH | Delivery Slices › Build-order prerequisites, Slice 4 | The Round 1 claim "Slice 4 ships when it merges to `main`" holds only for new installs. Root `.claude-plugin/plugin.json` pins `"version": "1.0.0"` and has never changed, and Claude Code gives an installed plugin a new copy only when its computed version changes, with auto-update off by default for this marketplace. Without a bump, every existing user keeps a skill with no `install skillset`, while the FR-9 command block tells them to run it, and the DoD's "note telling existing users how to pick up the updated skill" has no command that works. Amended: Slice 4 bumps `version`, the CHANGELOG note names the two update commands, the build-order paragraph states the new-versus-existing split, and References cites the docs.
- LOW | Test Plan › R17 | R17 would be the first test to drive a slowapi limit to 429 (the label test that expects 429 hits `label_service`'s own cap). Each module-level `Limiter` uses in-memory storage that lives for the whole pytest run, and `conftest.py` never resets it, so 50 adds under a user id other tests share would make later add tests return 429. Amended: a fixture rule gives R17 its own two user ids.
- LOW | FR-7 › Argument rule | The justification said `_GITHUB_URL_RE` is loose in the repository segment only; it is loose in the owner segment too, as Follow-ups says. Amended. The regexes themselves are right.
- LOW | FR-7 › Argument rule | A skill submitted from local files stores `repo_url` as `local://<path>` (`_create_local` in `services/skill.py`; `test_local_submit.py`). The argument rule rejects it, so such a member is reported as a path-guard abort with the "tell the submitter" next step, although nothing is wrong with the entry; plain `install` could not clone it before either. Not amended: the member still fails safely, and a distinct reason is a wording choice for Slice 4.
- MEDIUM | FR-7 › Failure rule vs Confirm rule | The Round 1 fix for the credential-prompt hang sets only `GIT_TERMINAL_PROMPT=0`, which stops git's own terminal prompt and nothing else. `git_prompt()` in `prompt.c` runs `GIT_ASKPASS`, `core.askPass`, or `SSH_ASKPASS` first (an IDE terminal commonly exports `GIT_ASKPASS`), and Git Credential Manager, the case Round 1 named, prompts in its own window under `GCM_INTERACTIVE`, not `GIT_TERMINAL_PROMPT`. Either way a clone of an unreadable internal repository can stop mid-run for input, which contradicts the confirm rule's "a user who confirms can leave the run unattended". Amended: each clone runs with `GIT_TERMINAL_PROMPT=0 GIT_ASKPASS= GCM_INTERACTIVE=0`, the rule says why, and References cites `prompt.c`, the git docs, and GCM's `environment.md`. Stored credentials still work, so a readable private repository still clones.
- MEDIUM | NFR-5, Module Design › `services/skill.py`, Slice 1 | The amendment that gives `skill_repository.delete()` an `actor_id` (modelled on `update()`, where `actor_id: str` is required) did not account for the existing callers. Besides `delete_skill` in `routers/skills.py`, four tests call `skill_repository.delete(skill)` with one argument: `test_user_activity.py` (2), `test_skill_crud.py`, `test_catalog_scale.py`. A required parameter breaks all four with `TypeError`, against Measured facts › test-baseline. Amended: the Slice 1 bullet says the parameter is required and names the call sites and the grep that finds them, including M13 and O9.
- LOW | ADR-U18 › Consequences | "The member count is `len(members)`" contradicted the Orphan members bullet another reviewer amended, which makes `SkillsetOut.member_count` the number of hydrated members and keeps `len(members)` only for `SkillsetListOut`. Amended: the Consequences line now points to Orphan members, which owns the rule.
- INFO | API contract › add rate limit | Confirmed another reviewer's `key_style` claim: slowapi 0.1.9 defaults to `key_style="url"` (`Limiter.__init__`), and `__evaluate_limits` scopes the counter by `request["path"]`, so the `create_flag` and labels limits count per skill path. `key_style="endpoint"` scopes by the route function name, which makes the 50/hour a per-user total as the contract says.
- INFO | FR-4 | Confirmed: `list_skills` accepts `page` (1–1000) and `page_size` (1–100) besides `cursor`.
- INFO | NFR-5, Slice 1 | Confirmed: `update_skill` passes `actor_id=user.user_id` to `skill_repository.update()`; `get_current_user` logs a rejected `X-Forwarded-User` with `%r`.
- INFO | Module Design › route handlers | Another reviewer's Round 2 edit already covers the 204 case (`NextResponse.json(data, { status: 204 })` throws); confirmed against `frontend/app/api/skills/[slug]/route.ts`, whose DELETE returns `new NextResponse(null, { status: 204 })`.
- INFO | Test Plan › Fixture rules | Confirmed the mongomock datetime rule: mongomock 4.3.0 returns a stored `datetime(…, 394251, tzinfo=utc)` as naive `datetime(…, 394000)`. Confirmed the admin rule: `_auth_headers(is_admin=True)` in `test_labels.py` assigns `config.settings.admin_users` and never restores it; `test_moderation.py` uses `monkeypatch.setattr`.


**Opportunities**

- Remove `version` from `.claude-plugin/plugin.json` instead of bumping it. Claude Code docs: "Omit `version`: users track your commits instead." That matches the plan's "ships when it merges" model and cannot be forgotten. The evidence that a bump gets forgotten: `skill/SKILL.md` changed in 8 commits since `e95e8f4` (2026-05-04) created `plugin.json`, including #022's switch to `git clone`, and `version` never moved, so an install from May still runs the May skill.
- The `"path": "skill"` key in the AKH entry of `marketplace_json` is not a `github` source field and does nothing; the root `plugin.json` does the work. Dropping it, or switching to `git-subdir`, would stop the next reader from relying on it. Not needed for this task.
- On git 2.47 and later, `-c credential.interactive=false` on the clone covers interactive credential helpers in general, not only GCM. Not required: the FR-7 environment covers the helpers named.

**Decisions Required**

*Decision: how existing installs of the AKH plugin receive Slice 4*
- **Severity:** defaulted
- **Question:** Root `.claude-plugin/plugin.json` pins `version` at `1.0.0`, so an existing install never sees new commits. Should Slice 4 bump the version or remove it?
- **Options:** A) Bump `version` in Slice 4, and in every later change to `skill/`. B) Remove `version`, so the commit SHA is the version and every merge reaches users on their next update.
- **Assumed:** A. It is the smaller change and keeps a visible version string. The plan now says so in Slice 4, the build-order paragraph, and the DoD.
- **Impact if wrong:** B needs one line changed in the Slice 4 bullet and the DoD; either way existing users must still run an update command, because auto-update is off by default.

*Decision: whether `skill_repository.delete()` takes `actor_id` as a required parameter*
- **Severity:** defaulted
- **Question:** NFR-5 adds `actor_id` to `skill_repository.delete()`. Required, as on `update()`, or optional with a default?
- **Options:** A) Required; the four existing test call sites pass an actor. B) Optional (`actor_id: str | None = None`); existing tests stay unchanged, and the NFR-5 cascade line can carry no actor.
- **Assumed:** A. The plan says it mirrors `update()`, and NFR-5 needs a real actor on every cascade line.
- **Impact if wrong:** B saves four one-line test edits but lets a future caller omit the actor and write an NFR-5 line with none.

**Amendments**

- design: Delivery Slices › Build-order prerequisites — states that "ships when it merges" holds for new installs only, says the root `plugin.json` (not the entry's `path`) points at `skill/`, and says Slice 4 bumps `version`.
- design: Delivery Slices › Slice 4 — new bullet: bump `version` in `.claude-plugin/plugin.json`; the CHANGELOG note names `/plugin marketplace update SLAC-Agent-Knowledge-Hub` and `claude plugin update agent-knowledge-hub@SLAC-Agent-Knowledge-Hub`. Definition of Done gains the matching item, and References gains "Claude Code plugin updates".
- design: FR-7 › Failure rule — each clone runs with `GIT_TERMINAL_PROMPT=0 GIT_ASKPASS= GCM_INTERACTIVE=0`, with the reason; References gains the git and GCM sources.
- precision: FR-7 › Failure rule and Definition of Done — the clone environment is stated in `skill/SKILL.md` › Install's clone step, so plain `install` uses it too.
- precision: FR-7 › Argument rule — `_GITHUB_URL_RE` is loose in the owner and repository segments, and `skill_path` is checked for `..` components and length.
- precision: Delivery Slices › Slice 1 — the required `actor_id` on `skill_repository.delete()` names the four existing test call sites, the grep that finds them, and M13 and O9.
- precision: ADR-U18 › Consequences — the member-count line defers to ADR-U18 › Orphan members instead of saying `len(members)`.
- precision: Test Plan › Fixture rules — R17 uses two user ids no other test uses, because the slowapi limiters keep in-memory counts for the whole run.

TOTAL: 3 design, 5 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-arch-review — Round 2 (PASS WITH WARNINGS)</summary>

**Summary**
- The Round 1 amendments fit together and with ADR-U18's write shapes. FR-2g's rule that a 409 on add or a 404 on remove means success is correct under ADR-U18 › Member resolution, edit details and reorder cannot undo each other, and the AKH skill's `/cli/api/` calls do not touch the new Next.js handlers.
- NFR-5 (security) could not be met for the cascade. One `update_many` returns no slugs, and `skill_repository.delete()` carries no actor. NFR-5 now says what the cascade logs, and `purge_for_skill()` and `skill_repository.delete()` gain the arguments it needs.
- Orphan members made `member_count` disagree with `skills`. ADR-U18 › Orphan members now defines the count on each response.
- Delivery: the ordering rules from doc-review, arch-review, and security-review still give one valid order. Build-order prerequisites now states it, links the Follow-ups validation task, and requires that task to be deployed, not only merged, before Slice 4 merges, since Slice 4 goes live at merge.
- Three precision amendments and no design amendments. Two defaulted decisions. Remaining warnings: no test pins NFR-5, and a submitter has no UI to remove a deactivated skill from another user's skillset.

**Issues**
- LOW | NFR-5 vs ADR-U18 › Write shapes › cascade | NFR-5 asks every successful write, the cascade included, for one line with the actor's `user_id`, the stored skillset slug, and the stored skill slug. The cascade is one `update_many` over every skillset holding the skill, and it returns only a count, so no slug is available after it. The interface the plan gives, `purge_for_skill(skill_id)` called from `skill_repository.delete(skill)` (`backend/app/services/skill.py:755`, which takes no actor; `delete_skill` in `routers/skills.py:315` has `user`), carries neither the actor nor the skill slug. Read literally, NFR-5 also logs a cascade line on every skill delete, including the many that touch no skillset. An implementer cannot meet NFR-5 for the cascade from the plan text.
- LOW | NFR-5 vs ADR-U18 › Orphan members | A reorder's `$set` drops orphans, and no `remove` line records that. The orphan's skill no longer exists, so nothing a support question needs is lost. No amendment.
- LOW | ADR-U18 › Orphan members vs API contract | `member_count = len(members)` counts an orphan, while FR-5's hydration omits it. A three-member skillset with one orphan shows "3 skills" on its `/skillsets` card and lists two on its page, and a skillset whose only member is an orphan reports `member_count: 1` with an empty `skills` list. The install loop reads `skills`, but the plan does not say which field the empty-skillset message tests.
- LOW | Delivery Slices | The ordering rules from doc-review, arch-review, and security-review still admit a valid order: deploy Slice 1 and the validation task to production, merge Slice 4, then deploy Slice 2+3. Three pieces of text obscured it. "Ship Slice 4 first or in the same release as Slice 2+3" predates the merge-is-ship rule in the same paragraph, and the two together forbid Slice 1 and Slice 2+3 from sharing a production deploy, which the paragraph never said. Production deploys are manual (`make prod-deploy` in `.claude/skills/deploy/SKILL.md`), so merging Slice 2+3 to `main` early is harmless. The validation task's constraint lived only under "Follow-ups (non-blocking)", although it blocks Slice 4. It also said "merge before Slice 4 merges", and since Slice 4 goes live at merge, a merged but undeployed validation fix protects nothing at that moment. The task has no `todo/` file or `TODO.md` row yet. `todo/040-sec-repo-url-validation.md` is the completed task that introduced `_GITHUB_URL_RE`, not this one.
- Verified, no defect | FR-2g vs ADR-U18 › Member resolution | Each 404 a remove can return leaves the skill outside the set: the skillset is gone, the skill is gone (the cascade already pulled it), or the skill is not a member. Remove resolves any status, so a deactivated member never returns a false 404. A 409 on add comes only from the add guard; M6 keeps a missing skillset at 404. FR-2g's success-and-reread rule is correct, and the re-read shows a member that a mis-routed 404 left in place.
- Verified, no defect | FR-7 auth rule vs Module Design route handlers | The AKH skill calls `/cli/api/...`, which the `/cli(/|$)(.*)` ingress rule (`kubernetes/overlays/{dev,stage,prod}/ingress-api.yaml:17`) strips and sends straight to the backend, so `/cli/api/skillsets/{slug}` needs no ingress change and does not pass through the new Next.js handlers. The deploy skill applies prod from the `prod2` overlay in another repository, which this review did not read; the AKH skill's existing `/cli/api/skills/<slug>` calls work on prod, so the new path works there if that overlay routes the whole `/cli` prefix, as this repository's overlays do (assumed, not verified).
- Verified, no defect | ADR-U18 › edit details vs reorder | Edit details does not increment `version` and reorder's `$set` touches only `members`, so a PATCH and a reorder cannot undo each other and a rename does not 409 an open reorder page. P6 pins the `save()` ban.
- LOW | FR-2e vs ADR-U18 › Member resolution | The API lets a submitter remove a deactivated skill from another user's skillset. The only UI for it, FR-2e, sits in the "Part of N skillset(s)" section, and `frontend/app/skills/[slug]/page.tsx:34` renders a Tombstone for a deactivated skill, so the submitter has no control. The skillset's owner still sees the member marked deactivated and can remove it. No amendment; noted for UX.
- LOW | Test Plan | No row tests NFR-5's log line, and the Definition of Done does not list it, so the only record of removals is unverified. Left to eng review.

**Opportunities**
- FR-2e's confirmation says "Only the skillset's curator can add it back", while ADR-U19 › Consequences says the owner or an admin can. "Curator" is the user-facing word for owner, so the string is accurate for the person reading it; UX may want to keep it short rather than name admins.
- The Tombstone that `frontend/app/skills/[slug]/page.tsx` renders for a deactivated skill could carry the submitter's FR-2e Remove controls, so the API right that ADR-U18 › Member resolution grants has a UI path. Only worth it if submitters ask for it.
- A unit row for NFR-5 (for example, `caplog` shows one `remove` line naming the submitter's `user_id` after M10, and one `cascade` line naming both skillsets after M13) would pin the only removal record. Eng review owns the Test Plan.

**Decisions Required**
*Decision: What the cascade's NFR-5 line names*
- **Severity:** defaulted
- **Question:** NFR-5 wants the skillset slug in every line, and the cascade's `update_many` returns only a count. Should the cascade line name the changed skillsets or only count them?
- **Options:** A) `purge_for_skill()` reads the slugs of the skillsets holding the skill just before its `update_many`, and logs one line naming them, only when there is at least one. B) Log the skill slug, actor, and `modified_count` with no skillset slugs.
- **Assumed:** A. NFR-5 exists to answer "who removed this from my skillset", and a curator searches by skillset slug, which B never logs. The extra read is one indexed query on a rare path. Both options need the new `actor_id` parameter on `skill_repository.delete()`.
- **Impact if wrong:** Under B, the NFR-5 cascade sentences shorten to the count, and `purge_for_skill()` drops the read. The signature change stays.

*Decision: Validation task merged or deployed before Slice 4*
- **Severity:** defaulted
- **Question:** The Follow-ups item said the server-side `repo_url` validation task "must merge before Slice 4 merges". Slice 4 goes live at merge, and the backend goes live only at a manual production deploy. Must the validation task be deployed, or only merged, before Slice 4 merges?
- **Options:** A) Deployed to production before Slice 4 merges. B) Merged before Slice 4 merges, as written in Round 1.
- **Assumed:** A. The user accepted the task landing "before Slice 4", and under B the fix can still be undeployed when Slice 4 goes live. Slice 1 already has to be in production by then, so A adds no extra release if the task ships with Slice 1.
- **Impact if wrong:** Under B, the Follow-ups item and the order sentence in Build-order prerequisites say "merged" for the validation task. Slice 4 then relies on FR-7's argument rule alone until the next production deploy.

**Amendments**
- precision: NFR-5 now says what the cascade logs. It writes one line per skill delete, only when the skill was in a skillset, and the line names the changed skillsets, which `purge_for_skill()` reads just before its `update_many`. The actor reaches it through a new `actor_id` parameter on `skill_repository.delete()`. The Module Design `services/skill.py` row, the Slice 1 cascade bullet, and M9 now use the signature `purge_for_skill(skill_id, skill_slug, actor_id)`.
- precision: ADR-U18 › Orphan members now defines `member_count` around orphans. On `SkillsetOut` it is the number of hydrated members, so the detail page and the empty-skillset check agree with `skills`. On `SkillsetListOut` it stays `len(members)` and counts an orphan until a reorder drops it.
- precision: Delivery Slices › Build-order prerequisites now states the one valid order (Slice 1 and the validation task deployed to production, then Slice 4 merged, then Slice 2+3 deployed in a later production release than Slice 1) and points to the Follow-ups constraint. It drops "Ship Slice 4 first or in the same release as Slice 2+3", which conflicted with the merge-is-ship rule. The Follow-ups item now says it blocks only Slice 4, requires the validation task to be deployed rather than merged before Slice 4 merges, and records that the task is not yet filed. A parallel Round 2 edit inserted the `plugin.json` version-bump sentences before "Slice 4 therefore merges only after Slice 1 is deployed", which left "therefore" pointing at the bump; that sentence now opens "Because Slice 4 goes live when it merges".

TOTAL: 0 design, 3 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 2 (PASS WITH WARNINGS)</summary>

**Summary**

- No test IDs collide after the parallel edits, every row of ADR-U19 › Permission rules has an allow test and a deny test, and the ADR-U18 rules (member resolution, orphans, 409 before 422, the edit-details write shape) each have a row that runs under `mongomock_motor`. Expected status codes agree with the API contract, which now also states the 404 for a missing skillset.
- A probe found that this reviewer's Round 1 rate-limit amendment does not do what it says. slowapi scopes counts by request path by default, so "50/hour per user, as `create_flag` does" is a separate 50 for each (skillset, skill) pair, which nobody reaches. The contract now uses `key_style="endpoint"`, and R17 now fails under either a per-path scope or a per-address key.
- The Test Plan had no rows for FR-2g, FR-2e, FR-2f, AC-9, the frontend halves of AC-5, AC-10, and AC-13, or NFR-5, and FR-7's argument and auth rules had only partial negative tests. It now has F1–F8 (manual, because `frontend/` has no component tests), L1–L4 (`caplog` under mongomock), and the missing narrative tests, plus a fixture rule that keeps hostile entries out of every real catalog.
- Parallel Round 2 edits had already fixed the NFR-5 cascade signature, the duplicated confirm-prompt tests, R17's shared limiter state, and `member_count` with orphans, so this review made no second edit for them.
- What still needs a warning: the AKH and frontend checks are manual, and mongomock does not exercise concurrency or index use.

**Issues**

*Reconciliation checks*

- INFO | test IDs | No ID collides after the parallel edits. Each of U1–U7, M1–M16, O1–O11, B1–B4, P1–P6, C1–C4, I1–I13, R1–R17, and S1–S4 heads exactly one row (`grep -oE '^\| [A-Z][0-9]+ '` over the Test Plan, then `uniq -c`). Outside the Test Plan, only the 2026-06-03 reviewer summary cites IDs ("insertion-order test I12, slug immutability test I13"); today I12 is slug immutability and I13 is the orphan read. That block records the earlier verdict, so this review leaves it alone.
- INFO | permission matrix | Every row of ADR-U19 › Permission rules has an allow test and a deny test: create (I1, I2), edit and delete (P1, P3, I7, I9, I10 against P2, P5, I8, I11, R16), add and reorder (M1, M8, O1, O7, R1, R9 against M7, M12, O6, R6, R13, R16), remove (M4, M10, M14, R4, R8 against M11, R7), auto-add (C1 against C2, C3).
- INFO | ADR-U18 rules | Member resolution (M15, M16, O10, R15), orphan members (O11, I13), the 409-before-422 order (O8, O9), and the edit-details write shape (P6) each have a row that runs under `mongomock_motor`. P6's monkeypatched lookup is what makes it fail on a `save()` implementation.
- INFO | status codes | Every expected status in I1–I13, R1–R17, and C1–C4 agrees with the API contract and with `get_current_user` in `backend/app/auth.py`, which returns 401 before any route code runs when neither the internal secret nor a Bearer token is present (I2, R14). The contract does not state the 404 for a missing skillset that M6 and FR-2g's "404 on add" row rely on (amended).

*Amendment-created defects*

- HIGH | API contract › `PUT .../skills/{skill_slug}` rate limit | The Round 1 amendment (this reviewer's) says the limit is "50/hour per user ... as create_flag in routers/skills.py does". slowapi's `Limiter` defaults to `key_style="url"`, which scopes every count to the request path. A probe against `create_flag` under mongomock sent 12 flags as one user on 12 skills and got `[200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200]`; the limiter's storage held one counter per path, `LIMITER/user:alice//api/skills/s0/flag/10/1/hour` and so on. Built as written, the add limit is 50 per user per (skillset, skill) path, which no user reaches because a repeated add returns 409, so FR-2g's 429 row can never appear and R17 fails if it adds distinct skills. A second probe with `Limiter(key_func=..., key_style="endpoint")` returned `[204, 204, 204, 429]` across four different paths with a 3/hour limit, a second user still got 204, and `limiter.reset()` cleared the count (amended). Round 1's reasoning for per-user keying was also wrong for this endpoint under the default style, because a per-IP count per path is not one shared bucket; the reasoning holds once the scope is the endpoint. `create_flag`'s own limit has the same per-path scope; that predates this task and is out of scope.
- MEDIUM | Test Plan › R17 fixture | slowapi keeps counts in module-level memory storage, so they survive from one test to the next in a pytest process (the first probe showed counters accumulating across two `create_app()` instances). Once the add limit counts per user across paths, R17's 51 adds put that user over the limit for every later test that adds as the same user. A parallel Round 2 edit added the fixture rule that R17 uses two user ids no other test uses, which is enough once the scope is the endpoint, so this review made no second edit.
- MEDIUM | NFR-5 › cascade | NFR-5 required the cascade's log line to carry "the actor's `user_id`" and "the stored skillset slug", but `purge_for_skill(skill_id)` received no actor, its caller `skill_repository.delete(self, skill: Skill)` in `backend/app/services/skill.py` takes none, and `update_many` returns counts, not slugs. A parallel Round 2 edit (round-2-ar) fixed this: `purge_for_skill(skill_id, skill_slug, actor_id)` reads the slugs before its `update_many`, and `skill_repository.delete()` gains `actor_id`. This review checked that M9 and M13 still agree with the new signature and made no second edit.
- MEDIUM | Test Plan › NFR-5 | NFR-5 has no test. A `services/skillset.py` that logs nothing, or logs the raw path parameter, passes every row. `caplog` runs under mongomock, so the rule is testable (amended: L1–L4).
- MEDIUM | Test Plan › FR-7 argument rule | The "Hostile repo_url" narrative test covers the `repo_url` check only. No test sends a `skill_path` that fails `^/[A-Za-z0-9._/-]*$`, so half of a shell-injection control has no negative test (amended).
- MEDIUM | Test Plan › FR-7 auth rule | No narrative test checks the auth rule's two security clauses: the token value never appears in the session transcript, and no `git` command or request to a `repo_url` carries it. "No token" checks only the 401 stop (amended).
- MEDIUM | Test Plan › frontend | The Test Plan has no frontend section, manual or otherwise, although `frontend/` runs vitest only for `lib/*.test.ts` and has no component tests. FR-2g's seven outcomes, the FR-2e confirmation, FR-2f's disabled controls and stale-page message, AC-9, and the frontend halves of AC-5, AC-10, and AC-13 therefore have no test row. The Definition of Done lists most of them, so the Test Plan disagrees with it. AC-13's frontend half is the only check that catches the `frontend/app/api/skills/summary/route.ts` defect from Round 1, because S4 calls the backend directly (amended: F1–F8).
- LOW | Test Plan › duplicated narrative rows | "Confirm prompt" (Round 1, this reviewer) and "Confirm declined" (Round 1, another reviewer) both tested the confirm list, the "MCP server" marker, and a declined prompt. A parallel Round 2 edit (round-2-ux) merged them, so this review made no edit.
- LOW | Test Plan › narrative fixture | "Hostile repo_url" says the entry is "stored directly in the test database", but the narrative tests have no test database: the AKH skill's **Catalog base URL** in `skill/SKILL.md` is the production catalog. Read literally, the instruction puts a hostile entry where `marketplace.json` serves it to every user (amended).
- LOW | Test Plan › Scope | The scope block omits the rate-limit test (R17), lists `/api/skills/summary` (S4, served by `routers/catalog.py`) under `routers/skills.py`, and omits four narrative tests (fetch fails before the prompt, failed member recap, confirm declined, hostile repo_url) (amended).
- LOW | Test Plan › I5 | AC-4 names `labels` in each member's summary. I5 checks `version`, order, and `status`, so a hydration that drops labels passes (amended).
- LOW | orphan members and `member_count` | ADR-U18 › Orphan members has FR-5's hydration omit orphans, while the API contract computes `member_count = len(members)`, which counts them. For a skillset holding an orphan, `SkillsetOut.member_count` exceeded `len(skills)` until the next reorder dropped the orphan. A parallel Round 2 edit (round-2-ar) now defines `member_count` on `SkillsetOut` as the number of hydrated members, so this review made no edit.

*Test diagram after this round*

```
Rule or AC                 tests                               runs under
AC-1..AC-4, AC-7, AC-8     U1, I1; M1, R1; M4, R4; I5; ...     mongomock
AC-5, AC-10, AC-13         S1, C1-C4, S4 + F3, F1, F2          mongomock + manual
AC-6, AC-14                narrative (happy path, failed)      manual
AC-9                       F1                                  manual
AC-11, AC-12, AC-15        M10, M11, R8; O1-O4, O8, R9-R11;    mongomock
                           M9, M13
FR-2b auto-add             C1-C4                               mongomock
FR-2e, FR-2f, FR-2g        F5, F6, F7 (429 by R17 only)        manual
FR-7 confirm, skip         narrative (confirm, nothing to      manual
                           confirm, skip, partial install)
FR-7 failure, summary      narrative (fetch fails, failed,     manual
                           recap, no GitHub access)
FR-7 argument, auth        narrative (hostile values, token    manual
                           handling, no token)
NFR-5                      L1-L4                               mongomock (caplog)
ADR-U18 resolution         M15, M16, O10, R15                  mongomock
ADR-U18 orphans            O11, I13                            mongomock
ADR-U18 edit details       P6                                  mongomock
ADR-U18 reorder order      O8, O9                              mongomock
add rate limit             R17                                 mongomock
```

Test-adequacy verdict: no blocking item remains. The warnings are the same as Round 1's: the AKH and frontend checks are manual, and mongomock does not exercise concurrency or index use.

**Opportunities**

- Extract FR-2g's status-to-message mapping and FR-2f's up and down move as pure functions in `frontend/lib/`, each with a vitest test next to `frontend/lib/platform-filter.test.ts`. F6 and F7 would then check only the wiring, and the 429 row, which nobody provokes by hand, would get an automated check.
- Reset the skillsets router's limiter with `limiter.reset()` in an autouse fixture instead of relying on R17's unique user ids. The probe confirmed that `reset()` clears the counts. With the endpoint scope, every add by a shared test user counts toward that user's 50 for the whole pytest run, so a later suite that adds more membership tests could reach the limit.
- `create_flag`'s "10/hour" limit in `backend/app/routers/skills.py` has slowapi's default per-path scope, so it limits flags per user per skill, not per user. That predates this task and could go to a separate ticket if a per-user cap was intended.

**Decisions Required**

*Decision: Scope of the membership add rate limit*
- **Severity:** defaulted
- **Question:** Should the 50/hour limit on `PUT /api/skillsets/{slug}/skills/{skill_slug}` count a user's adds across every skillset and skill, or per request path?
- **Options:** A) Across every path, with `key_style="endpoint"` on the skillsets router's `Limiter`. B) Per path, slowapi's default, as `create_flag` does, and state in the contract that the limit is per (skillset, skill) pair.
- **Assumed:** A. The contract says "50/hour per user", FR-2g's 429 message says "Too many additions in the last hour", and under B no user can reach the limit, because a repeated add of the same pair returns 409.
- **Impact if wrong:** With B, the contract text changes, FR-2g's 429 row and R17 are dropped, and adds are not rate-limited in practice.

*Decision: 50 adds per hour once the limit applies*
- **Severity:** judgement-call
- **Question:** Under the endpoint scope, a curator who adds more than 50 skills within an hour gets 429 until the hour passes. Is 50 still the right number?
- **Options:** A) Keep 50/hour. B) Raise it, for example to 200/hour, so that building a large set in one sitting never meets the limit.
- **Assumed:** A, the number earlier rounds chose. The dev catalog has far fewer active skills than 50 (Measured facts › summary-size), so no set that can be built today reaches it.
- **Impact if wrong:** A curator building a set of more than 50 skills sees FR-2g's 429 message and waits up to an hour. Only the API contract's number and R17's counts change.

**Amendments**

- design: API contract › `PUT /api/skillsets/{slug}/skills/{skill_slug}` now uses `Limiter(key_func=user_id_key_func, key_style="endpoint")` and explains why slowapi's default `key_style="url"` would never reach the limit. R17 now adds 51 different skills, so it fails under a per-path scope (the 51st returns 204) and under a per-address key (user B gets 429). This corrects this reviewer's Round 1 amendment, whose shared-bucket reasoning assumed an endpoint scope.
- design: Test Plan › AKH skill narrative tests gains negative tests for the security clauses of FR-7 that had none. "Hostile repo_url and skill_path" adds a `skill_path` carrying `$(...)`. "Token handling" checks that the token value never appears in the transcript and that no `git` command or `repo_url` request carries it. "No GitHub access" now checks `GIT_TERMINAL_PROMPT=0` and the full guide URL.
- precision: Test Plan gains `### Frontend (manual)`, F1 to F8, for FR-2e, FR-2f, FR-2g, FR-8, FR-9, AC-9, and the frontend halves of AC-5, AC-10, and AC-13, matching the Definition of Done's frontend rows. F2 is the only check that exercises `frontend/app/api/skills/summary/route.ts`.
- precision: Test Plan gains `TestSkillsetServiceAuditLog`, L1 to L4, for NFR-5, matching the Definition of Done row a parallel reviewer added. L4 uses the cascade signature from round-2-ar's amendment.
- precision: Test Plan › Scope now lists the model validators, the NFR-5 log tests, 401 and 429, `routers/catalog.py` (S4), the frontend manual checks, and every narrative test by reference to the list.
- precision: Test Plan › AKH skill narrative tests now opens with a fixture paragraph: a temporary HOME, and a local backend for entries no real catalog should hold. It replaces "stored directly in the test database", which, given the production **Catalog base URL** in `skill/SKILL.md`, read as an instruction to put hostile entries into a served catalog.
- precision: I5 now applies a label to one member and asserts it in that member's `labels`, because AC-4 names labels in the hydrated summary.
- precision: API contract now states that every endpoint under `/api/skillsets/{slug}` returns 404 when no skillset has that slug, which M6 and FR-2g's "404 on add" row already assume.

TOTAL: 2 design, 6 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>doc-review — Round 2 (PASS WITH WARNINGS)</summary>

**Summary**

- No amendment from Round 1 or Round 2 introduced a breaking change, and no doc row is duplicated. README, CHANGELOG, `PRD.md`, the ADR files, the AKH guide page, and the three `skill/SKILL.md` rows each appear once.
- The Round 1 rules each had a doc home, but several were incomplete. The CHANGELOG row was missing the confirm prompt, the argument rule's effect on plain `install`, Search and Install now sending the token, and the per-user rate limits. The guide-page row was missing the confirm prompt. The Error handling row had no argument-rule case and used a second name for "path-guard abort". NFR-5 had no Definition of Done row. All are amended (precision).
- The Board Review "Amendment 2026-10-14" note did not list FR-2g, NFR-5, user stories 2a, 11, 14, 16, and 17, the success metrics, FR-2, Follow-ups, Problems & Solutions, or References. It now lists them.
- The Next.js route handlers had no slice, so Slice 2+3 now names them. The security follow-up that blocks Slice 4 is not yet filed in `todo/`. The entry now asks for a `todo/` file and a `TODO.md` row and names #040.
- Two warnings remain. The confirm list and the per-skill install each fetch `GET /api/skills/{slug}`, so what is cloned may differ from what the user approved (deferred to security). The Test Plan has no NFR-5 test (deferred to eng).

**Issues**

> Mode: Codebase. Scope: the Round 1 amendments and the doc rows they need. Round 1 matters are not re-raised.

- MEDIUM | Board Review › Amendment 2026-10-14 | The note does not list everything that changed since the committed text. Missing: FR-2g, NFR-5, user stories 2a, 16, and 17, the Follow-ups section, and the Problems & Solutions and References entries (all added; the last two were "_None yet._" in `HEAD`), plus the revised success metrics, user stories 11 and 14, and FR-2. Amended.
- MEDIUM | Definition of Done › CHANGELOG | The Slice 4 bullet names only "skip, failure, and summary behaviour". It leaves out three Round 1 rules that users will notice: the confirm prompt (FR-7 › Confirm rule); plain `install` now refusing a `repo_url` or `skill_path` that fails FR-7 › Argument rule; and Search and Install now sending the bearer token, because the auth rule moves into the SKILL.md header. The Slice 1 bullet leaves out the per-user rate limits (20 creates and 50 adds per hour). The repository's CHANGELOG already records per-user limits for flags (line 59) and install events (line 84). Amended.
- MEDIUM | Delivery Slices / Follow-ups | When this review started, the Follow-ups entry said "That task must merge before Slice 4 merges", and Delivery Slices › Build-order prerequisites did not carry that constraint. Another Round 2 reviewer has since moved it into the build-order prerequisites, and the entry now says the task "is not yet filed in `todo/` or `TODO.md`". Still open: nothing assigned filing the task, and the entry did not mention that #040 (complete) introduced the `_GITHUB_URL_RE` this task tightens. Amended the entry to ask for a `todo/0NN-sec-*` file and a `TODO.md` row before Slice 4 starts, and to name #040. The section heading still reads "Follow-ups (non-blocking)" while the entry blocks Slice 4. I left the template heading alone and record it here.
- LOW | Definition of Done › `skill/SKILL.md` › Error handling | FR-7 calls an argument-rule rejection a "path-guard abort", but the row calls the existing case "the path-traversal abort" and adds no Error handling case for the argument rule. Plain `install` applies that rule too (FR-7 › Argument rule › Where), so the section needs a case for it. Amended.
- LOW | Definition of Done › AKH guide page | The "Install a skillset" entry is asked to describe the skip and failure behaviour and the token, but not the confirm prompt. The prompt is the step a first-time user meets first, and it is the only place they see MCP servers before installing. Amended.
- LOW | NFR-5 | No Definition of Done row and no Test Plan test checks NFR-5's log line. NFR-5 calls it "the only record of who removed a member", and only the Slice 1 bullet mentions it. Amended the Definition of Done. The missing Test Plan test is left to eng review.
- LOW | Module Design › Next.js route handlers | Module Design adds five route handlers and a `lib/api.ts` change, but no Slice 2+3 bullet names them. Without them, every browser call fails, and the FR-2c picker gets unfiltered results. No repository doc lists route handlers (only `docs/skill-file-discovery.md` mentions two, for debugging), so no doc row is needed. Amended Slice 2+3.
- LOW | Duplicate rows check | No doc row is duplicated after the parallel edits: README, CHANGELOG, `PRD.md`, ADR files, the AKH guide page, and the three `skill/SKILL.md` rows each appear once. When this review started, two AKH narrative tests overlapped: "Confirm prompt" and "Confirm declined" both checked that a no installs nothing and registers no MCP server. A parallel Round 2 edit has since removed "Confirm declined", so nothing is left to fix.
- LOW | FR-7 › Confirm rule (outside doc lane, created by a Round 1 amendment) | The confirm list shows the `repo_url` from the loop's own `GET /api/skills/{slug}`. The per-skill flow it then runs fetches the same endpoint again (`skill/SKILL.md` › Install step 1), so the repository that gets cloned can differ from the one the user approved. Deferred to security review; not amended. A parallel Round 2 edit has already settled the second gap I found, the order of the replace question and the confirm prompt.
- LOW | Definition of Done › `skill/SKILL.md` sub-command row | A parallel Round 2 edit to FR-7 now uses `N` for the count in the confirm prompt ("Install these N of M skills") and `[i/M]` for the progress prefix. The Definition of Done still wrote the failure-line prefix as `[N/M]`, which would collide with the prompt's N. Amended to `[i/M]`.
- LOW | `PRD.md` › 15 command table (pre-existing, outside the round bar) | The `/agent-knowledge-hub` command table near line 871 lists every AKH command and will lack `install skillset`. This gap predates Round 1, so it is recorded as an opportunity rather than amended.

**Opportunities**

- Add an `install skillset <slug>` row to the `/agent-knowledge-hub` command table in `PRD.md` › 15 (lines 871 to 879). It would sit beside the Slice 1 `PRD.md` › 5 row that is already in the Definition of Done. This gap predates Round 1, so I have not added it to the plan.
- Eng review: add a unit test for NFR-5's log line to the Test Plan, for example with `caplog`, covering at least a submitter's removal and the cascade. The new Definition of Done row names the requirement, but no test in the plan checks it.

**Decisions Required**

*Decision: When the server-side validation task is filed*
- **Severity:** defaulted
- **Question:** The Follow-ups entry blocks Slice 4 on a security task that has no `todo/` file and no `TODO.md` row yet. When should it be filed?
- **Options:** A) Before Slice 4 starts, as the amended entry says. B) At the close of this board review, before any slice starts. C) Fold it into Slice 1.
- **Assumed:** A. It is the latest point that still keeps Slice 4 unblocked, and it needs no change to the slices. Round 1 already settled that the work is a separate task (security-review decision, accepted).
- **Impact if wrong:** Under B, the orchestrator files the task now and the entry's sentence gets the task number. C reopens a decision Round 1 settled.

*Decision: Heading of the Follow-ups section*
- **Severity:** defaulted
- **Question:** The section is headed "Follow-ups (non-blocking)", but its only entry blocks Slice 4. Should the heading change?
- **Options:** A) Leave the template heading; the entry says "It blocks only Slice 4" and Delivery Slices › Build-order prerequisites carries the rule. B) Rename it to "Follow-ups".
- **Assumed:** A. The rule is stated once, where the slices are ordered, and the heading follows the draft-prd template.
- **Impact if wrong:** A reader who scans only the headings may assume Slice 4 has no outside prerequisite. Under B, rename the heading; nothing else changes.

**Amendments**

- precision: Board Review › Amendment 2026-10-14 now also lists, as added, user stories 2a, 16, and 17, FR-2g, NFR-5, the Follow-ups section, and the Problems & Solutions and References entries, and lists as revised the success metrics, user stories 11 and 14, and FR-2.
- precision: The Definition of Done CHANGELOG row now names three more Slice 4 bullets: the confirm prompt; plain `install` refusing a value that fails the argument rule; and Search and Install sending the bearer token. Its Slice 1 bullets now include the per-user rate limits, by reference to the Slice 1 bullet and the API contract so the numbers stay in one place, following the repository's CHANGELOG convention for per-user limits.
- precision: The Definition of Done Error handling row now adds a fourth case, a value that fails FR-7's argument rule, which also covers plain `install`. It also says that the existing path-traversal case and the argument-rule case together make up FR-7's "path-guard abort", so the plan and SKILL.md use one name for that failure.
- precision: The Definition of Done row for the AKH guide page's "Install a skillset" entry now asks for one sentence on the confirm prompt.
- precision: A new Definition of Done row (Slice 1) requires NFR-5's log line for each of its seven actions, including a submitter's removal and the cascade. Before this, only the Slice 1 bullet mentioned NFR-5.
- precision: Slice 2+3 gains a bullet for the Next.js route handlers and the `frontend/lib/api.ts` additions that Module Design › Frontend lists. Under the placement invariant, every artefact needs a slice, and these had none.
- precision: The Follow-ups entry on server-side validation now asks for a `todo/0NN-sec-*` file and a `TODO.md` row before Slice 4 starts, and names #040 as the task that added `_GITHUB_URL_RE`. Another Round 2 reviewer had already moved the ordering constraint into Delivery Slices › Build-order prerequisites, so I made no further change there.
- precision: The Definition of Done `skill/SKILL.md` sub-command row now writes the failure-line prefix as `[i/M]`, matching FR-7's progress lines. The old `[N/M]` reused the letter that the confirm prompt uses for the install count.

TOTAL: 0 design, 8 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 2 (PASS WITH WARNINGS)</summary>

**Summary**

- The Round 1 amendments by other reviewers hold up on security. The new BFF handlers forward identity only through `backendHeaders()`. Their extra query parameters reach nothing, and the summary handler exposes no new field. FR-2g's success handling of a 409 on add or a 404 on remove cannot hide a write, because both statuses mean nothing was written. The per-user limit key is `user:<id>` for browser and CLI callers alike, and an unauthenticated caller gets 401 before any bucket is used.
- All six of my Round 1 amendments survived intact or strengthened. Parallel Round 2 edits had already closed the gaps I came to fix: the replace question now comes before the confirm list, members that fail the argument rule are left out of the list, the cascade log line gets an actor, and the validation task must be deployed before Slice 4 merges.
- One design amendment, LOW: the FR-2b skip log line added in Round 1 would log the unvalidated `skillset_slug`, so a newline could fake an NFR-5 audit record. It now uses `%r`. There are also two precision amendments: the follow-up task checks stored rows, and the hostile-input test pins the confirm-list exclusion.
- One MEDIUM finding, pre-existing and outside the plan: `create()`'s `[CREATE]` log line writes the raw `repo_url` (`_GITHUB_URL_RE` accepts a newline) and `skill_path`. Any signed-in user can therefore forge the log that NFR-5 makes the audit record. It is recorded as an Opportunity for the follow-up security task.
- Status is PASS WITH WARNINGS. This was a plan review checked against the code it builds on (`auth.py`, slowapi 0.1.9, the BFF handlers, `schemas/skill.py`), not an attack on running code, and Round 1's identity-source lead is still open.

**Issues**

Format: `SEVERITY | area | location | finding`. Every line concerns an amendment made in Round 1; nothing settled in Round 1 is re-raised.

*BFF route handlers (Module Design)*

- LOW | identity forwarding (verified, no defect) | `todo/006-skillsets.md` Module Design, the four `frontend/app/api/skillsets/...` rows and `frontend/app/api/skills/summary/route.ts`; `frontend/app/api/_internal.ts` `backendHeaders()` | The new handlers forward identity the same way every existing handler does: `backendHeaders()` sets `X-Forwarded-User` and `X-Internal-Secret` and passes `Authorization` through, and the backend trusts `X-Forwarded-User` only after `hmac.compare_digest` on the secret and a `^[a-zA-Z0-9._\-@]{1,128}$` check (`backend/app/auth.py` `get_current_user`, Path 2). The handlers add no identity source of their own. The client-header fallback inside `backendHeaders()` is Round 1's open identity lead and is not re-raised.
- LOW | query forwarding (verified, no defect) | `frontend/app/api/labels/route.ts`; `backend/app/routers/catalog.py` `skills_summary` | "Forwards the query string (`page`, `page_size`, `created_by`) the way `labels/route.ts` does" forwards the whole `request.nextUrl.searchParams`, not only the three named parameters. FastAPI ignores parameters a route does not declare, `created_by` filters a public list, and `skills_summary` declares only `q`, so an extra or repeated parameter reaches nothing. The summary handler exposes no field the existing `[slug]` handler does not already return for slug `summary` (Round 1 verified that the summary's `repo_url` and `skill_path` for internal skills are no new exposure); it only stops the query string being dropped.
- LOW | path parameter encoding | `frontend/app/api/skills/[slug]/route.ts` (the pattern the plan says to copy); `frontend/app/api/me/installs/[slug]/route.ts` (the encoded pattern) | The existing `skills/[slug]` handlers interpolate `params.slug` into the backend URL unencoded, and the plan tells the new handlers to work "as the existing `frontend/app/api/skills/...` handlers do". A slug carrying an encoded `../` can therefore point a BFF request at another backend path. The request still carries only the caller's own identity, and the same user can already reach every backend route directly through `/cli/api` with a bearer token, so this grants nothing; recorded as an Opportunity, no amendment.

*Rate-limit key*

- LOW | rate limiting (verified, no defect) | `backend/app/auth.py` `user_id_key_func`; `backend/app/routers/skills.py` `_flag_limiter`, `create_flag`; `backend/.venv/.../slowapi/extension.py` (decorator check), `slowapi/middleware.py` `_check_limits` | The decorator's limit check runs inside the wrapper FastAPI calls after resolving dependencies, so `get_current_user` has set `request.state.user` before the key function reads it. A browser caller is keyed `user:<X-Forwarded-User>` and a CLI caller `user:<JWT name claim>` (Path 3 also sets `request.state.user`). An unauthenticated caller gets 401 from `get_current_user` before the wrapper runs, so it consumes no bucket, and the remote-address fallback is reachable only on a limited route without a user dependency; every limited skillset route (create, add) requires a user under ADR-U19 › Permission rules. The app-wide `SlowAPIMiddleware` (`backend/app/main.py`) uses a limiter with no default limits and does not set `_rate_limiting_complete`, so it neither applies an IP limit to these routes nor suppresses the decorator. The `user_id_key_func` docstring's claim that the middleware runs before auth resolves is true of the middleware but not of the decorator check that applies these limits.

*FR-2g idempotent outcomes*

- LOW | authorisation masking (verified, no defect) | `todo/006-skillsets.md` FR-2g; ADR-U18 › Write shapes › add, remove | A 409 on add and a 404 on remove are returned only when the write matched nothing, which means no change was made and the requested end state already holds; the page then re-reads, so it shows the true state. A 403 cannot be turned into a success by this rule unless the service checks membership before permission, and even then nothing is written and the re-read shows the truth. A refused caller sees the controls only if their rights changed after the page loaded, because `created_by` and `submitter_id` never change. Recorded as an Opportunity: state the check order (skillset lookup, permission, skill resolution, write) so a refused caller always gets 403.

*FR-7 confirm, skip, and argument rules*

- LOW | install trust (verified after parallel Round 2 edits) | `todo/006-skillsets.md` FR-7 › Confirm rule, › Skip rule | Round 1 left an ordering gap between the skip rule's replace question and the confirm list: a member whose directory had no manifest could be installed after the confirm without having been listed with its `repo_url` and markers. A parallel Round 2 edit closed it: the confirm rule now asks every replace question first, then lists every member it will install, and the Partial install narrative test checks that no question follows the confirm. The replace question defaults to No, so the user's own files under a catalog slug are kept unless the user agrees. No further amendment.
- LOW | command injection via the confirm list (verified after parallel Round 2 edits) | FR-7 › Confirm rule, › Argument rule | The confirm list prints each member's `repo_url`, so before Round 2 an agent could have shown a value the argument rule would later reject, possibly by writing it into an `echo` command, where `$(...)` would run. The confirm rule now leaves out any member whose values fail the argument rule, so only checked values reach the list. I added that property to the Hostile repo_url narrative test (Amendment B3). One gap remains: the failure report and summary line could repeat the rejected value. The test's `/tmp/akh-pwned` check would catch it being executed, so this is recorded as an Opportunity: name the failed field, not its value.
- LOW | argument completeness (verified, no defect) | `backend/app/models/skill.py` `validate_sha`; `skill/SKILL.md` › Install step 2 | The per-skill flow also puts `pinned_commit_sha` into a git command, and the argument rule does not check it. No change is needed: the model rejects anything other than a 40-character lowercase hex SHA-1, and only `create()` and the pin path set it, from GitHub's `head_sha`.

*Logging (NFR-5 and the FR-2b skip line)*

- LOW | log forging into the audit record | `todo/006-skillsets.md` Delivery Slices › Slice 1, `skillset_slug` bullet; `backend/app/main.py` (`logging.basicConfig`, plain text) | A Round 1 edit made `create_skill` log a skipped auto-add at INFO, and the most natural line includes the requested `skillset_slug`. `SkillCreate.skillset_slug` is unvalidated `str`, a JSON `\n` decodes to a newline, and plain-text logs split on it, so a signed-in user could add a fabricated line, for example one that reads as an NFR-5 record of another user's removal. Fix: format the value with `%r`, as `get_current_user` already does for a rejected `X-Forwarded-User` (Amendment B1). Severity is LOW because the next item already makes the same forgery possible.
- MEDIUM | log forging into the audit record (pre-existing, outside this plan) | `backend/app/services/skill.py` `create()`, the `[CREATE]` `logger.info`; `backend/app/schemas/skill.py` `_GITHUB_URL_RE` | `create()` logs `repo_url` and `skill_path` with `%s`. `_GITHUB_URL_RE`'s `[^/]+` matches a newline (checked: `re.match(..., "https://github.com/a/b\n2026 INFO forged")` is truthy), `source_type: "local"` skips the URL check, and `skill_path` has no character check. So any signed-in user can write a line into the log that NFR-5 makes the only record of removals. Attack path: `POST /api/skills {"repo_url": "https://github.com/a/b\n<a line formatted as an NFR-5 remove record>"}` → the value passes `_GITHUB_URL_RE` and `create()` logs it → the log shows a removal that never happened, or hides a real one among fakes. This does not breach access control, but it weakens the audit control NFR-5 adds. The Follow-ups security task's stricter patterns remove newlines from `skill_path` and from GitHub `repo_url` values, but not from `local` ones. Fix: format the `[CREATE]` values with `%r` in that task (Opportunity). No plan amendment, because the line is not part of this plan.
- LOW | NFR-5 (verified after parallel Round 2 edits) | NFR-5; Module Design `services/skill.py` row; Slice 1 | My Round 1 NFR-5 asked for an actor on the cascade line, but `skill_repository.delete()` received no user. A parallel Round 2 edit adds `actor_id` to `delete()` and `purge_for_skill()`, passed from `delete_skill` as `user.user_id`. Every other NFR-5 field is a stored slug or the authenticated `user_id`, and the Path 2 `user_id` has a character allow-list, so no new log line built under NFR-5 carries raw request text.

*Ordering constraints*

- LOW | release ordering (verified after parallel Round 2 edits) | Delivery Slices › Build-order prerequisites; Follow-ups | The Round 1 Follow-ups bullet said the validation task "must merge before Slice 4 merges", but a backend check protects only once it is deployed, and Slice 4 goes live when it merges. Parallel Round 2 edits now require deployment to production before Slice 4 merges, and the build-order paragraph refers to it. Slice 4 also carries FR-7's argument rule, so the installer is protected even if this order slips. One gap remained: the bullet left out the check of existing rows that the Round 1 decision included, and a stricter create-time pattern does not change stored entries. Fixed by Amendment B2. `create()` is the only write path for `repo_url` and `skill_path` (`grep -rnE "(repo_url|skill_path)\s*=" backend/app`), and `SkillUpdate` has neither field, so one query of stored rows covers every entry.
- LOW | live-on-merge exposure (verified, no defect) | Delivery Slices › Build-order prerequisites | Because `marketplace_json` names no ref, every `skill/SKILL.md` change in Slice 4, including the auth and argument rules, goes live on merge, and existing installs pick it up only after the `version` bump. Users who keep an older AKH skill have no `install skillset` command, so the skillset path exposes nothing to them. Their plain `install` keeps its existing exposure until they update, and Round 1 already raised that.

*Round 1 security amendments: survival check*

- LOW | A1 to A6 (verified intact) | FR-7, NFR-5, ADR-U18 › Options, Test Plan, Definition of Done | All six of my Round 1 amendments survived the parallel edits. A1, the confirm rule, was strengthened: replace questions come first, failing members are left out, and the prompt reads "N of M". It is still cited in ADR-U20 › Decision, System Design, Slice 4, and two Definition of Done bullets, and its narrative test was merged into "Confirm prompt", which keeps the checks that nothing is written under `~/.claude/` and no `claude mcp add` runs. A2 (NFR-5) was extended to cover the cascade actor. A3 is in ADR-U18 › Options. A4 is R16 and R17. A5 is in FR-7, the `skill/SKILL.md` › Install Definition of Done bullet, a new Error handling case, and the Hostile repo_url test. A6 is in FR-7 › Auth rule and the header-block Definition of Done bullet.


**Unverified Leads**

No new leads. Round 1's three leads (identity source in `backendHeaders()`, the browser-versus-CLI `user_id` namespace, and CSRF through the BFF's forced JSON content type) stand unchanged. The new `frontend/app/api/skillsets/route.ts` POST handler inherits the CSRF lead as Round 1 described it. The new PUT and DELETE handlers need a CORS preflight, which the BFF does not answer.

**Opportunities**

- Pass every path parameter through `encodeURIComponent` in the new `frontend/app/api/skillsets/...` handlers, as `frontend/app/api/me/installs/[slug]/route.ts` does, rather than copying the unencoded `frontend/app/api/skills/[slug]/route.ts`.
- State the check order for add and remove in ADR-U18 › Write shapes (skillset lookup, permission check, skill resolution, write), and give R6 a skill that is already a member, so a refused caller gets 403 rather than a 409 or 404 that FR-2g treats as success.
- In FR-7's failure report and summary line, name the field that failed the argument rule (`repo_url` or `skill_path`), not its value, so a rejected value never appears in any later output an agent might produce with a shell command.
- In the Follow-ups security task, format `repo_url` and `skill_path` with `%r` in the `[CREATE]` log line of `create()` in `backend/app/services/skill.py`. Alternatively, give `logging.basicConfig` in `backend/app/main.py` a formatter that escapes CR and LF in every message, which closes log forging for the NFR-5 record across the whole backend.
- Correct the `user_id_key_func` docstring in `backend/app/auth.py`: the slowapi decorator check runs after dependencies resolve, so `request.state.user` is set for every limited route that depends on `get_current_user`, and the remote-address fallback is reached only on a limited route without a user dependency.

**Decisions Required**

None. This round raises no new decision, and the three Round 1 decisions, which the user accepted, are reflected in the plan.

**Amendments**

- design: (B1) Delivery Slices › Slice 1, `skillset_slug` bullet: the INFO line for a skipped auto-add formats the requested `skillset_slug` with `%r`, so a newline in this unvalidated request text cannot write a line that reads as an NFR-5 record.
- precision: (B2) Follow-ups › server-side validation: the task also runs one read-only query for stored skills whose `repo_url` or `skill_path` fails the new check, as the Round 1 decision the user accepted said. A stricter create-time check does not change stored entries, and `SkillUpdate` cannot edit either field.
- precision: (B3) Test Plan › AKH narrative tests › Hostile repo_url: the hostile member is missing from the confirm prompt's list, which pins the confirm rule's exclusion of members that fail the argument rule. A parallel Round 2 rewrite of the same test, which added a hostile `skill_path`, kept this clause.

TOTAL: 1 design, 2 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-ux-review — Round 2 (PASS WITH WARNINGS)</summary>

**Summary**

- The security confirm prompt and this reviewer's Round 1 replace question did not say which came first. Read in order, the replace question came mid-loop, after the user had confirmed, so an unattended run would stall at that member. FR-7 now asks every question before the first clone.
- The confirm prompt also produced three outputs the plan did not define: "Install these 0 skills?", a summary and re-run hint after the user answered No, and a count N with no link to the member count M. The question now reads "N of M", N = 0 asks nothing, and No prints `Nothing installed.`.
- FR-2g's table covers every status the API contract returns for PUT and DELETE on a member. The 429 copy is right for the per-user limit. The 404-on-add copy now names the deactivated-skill cause added by ADR-U18 › Member resolution.
- The Round 1 Next.js route-handler row could be read as allowing `NextResponse.json` on a 204, which throws. Every successful add or remove would then show "Could not save the change". The row now names the 204 pass-through.
- Settled matters (menu visibility, curator removal signal) were not re-raised.

| Dimension | As received (Round 2) | After amendments | Key gap |
|---|---|---|---|
| Discoverability | 7/10 | 7/10 | No CLI listing of skillsets (Round 1 opportunity, unchanged) |
| First-Use Clarity | 7.5/10 | 7.5/10 | Prerequisite line under FR-9's command block is still an opportunity |
| Documentation Quality | 7.5/10 | 7.5/10 | No troubleshooting entry for `install skillset` (Round 1 opportunity) |
| Error UX | 7.5/10 | 8.5/10 | A 0-skill question, a summary printed after No, and a 204 handler pattern that turns a success into an error |
| Workflow Fit | 7/10 | 8/10 | A replace question that lands mid-loop after the user has confirmed |
| Trust & Reliability | 6.5/10 | 6.5/10 | No curator signal on removal (settled in Round 1); `member_count` counts orphans |
| **UX Readiness Score** | **7.2/10** | **7.5/10** | |

**Verdict:** UX WARNINGS (7.5/10 as amended). The Round 1 amendments fit together once the order of questions is fixed. What remains are Round 1 opportunities the user has already accepted as non-blocking.

**Top 3 user risks if shipped as received in Round 2:** (1) an `install skillset` run the user confirmed and left stalls mid-loop on a replace question; (2) every web add and remove reports failure while the change was saved, if the member route handler copies the `flag/route.ts` pattern; (3) the CLI asks to install 0 skills, or prints a failure recap after the user cancelled.

**Highest-impact fix:** the questions-first order in FR-7 › Confirm rule. It removes the only point where a confirmed run waits for the user.

**Issues**
- warning | Workflow Fit | FR-7's skip-rule replace question (Round 1, this reviewer) and the confirm rule (Round 1, security) did not say which comes first. Read in order, the replace question lands mid-loop after the user has already answered "Install these N skills?", so one member gets two questions and an unattended 12-member run stalls at the member with a manifest-less directory. The confirm rule's "every member the skip rule will not skip" was also undefined for that member, whose outcome depends on an answer not yet given. Amended: every question is asked before the first clone.
- warning | Error UX | The confirm rule created three outputs the plan did not define: "Install these 0 skills from skillset <slug>? (y/N)" when every member is installed or unavailable; a summary line, failure recap, and "re-run retries the failed members" hint printed after the user answered No; and a question count N that differs from the member count M on the skillset page and in the `[i/M]` progress lines, with no hint why. Amended: the question reads "N of M", N = 0 asks nothing, and No prints `Nothing installed.` with no summary.
- info | Error UX | A member whose `repo_url` or `skill_path` fails FR-7's argument rule was listed in the confirm prompt and then aborted. The argument check needs only the fetched values, so the confirm rule now leaves such a member out of the list, as it already did for a member whose fetch failed; no command runs for it either way.
- info | Error UX | System Design's install sketch looped "for each confirmed slug, applying FR-7's skip rule", while ADR-U20 › Consequences prints `[2/5] Skipping akh-core (already installed)` inside the loop and the summary counts every member. A loop over confirmed slugs only would never print a skip line and would number progress out of N, not M. Amended to loop over every member in stored order.
- info | Documentation Quality | The Test Plan carried two narrative tests for declining the confirm prompt ("Confirm prompt" and "Confirm declined"), added by two reviewers in Round 1. Merged into one, which now also expects the "N of M" question and `Nothing installed.`; added a "Nothing to confirm" case and placed the partial-install prompt before the confirm list.
- warning | Error UX | FR-2g's "404 on add" row read "This skill or skillset no longer exists." ADR-U18 › Member resolution (Round 1) made a 404 on add also mean the skill is deactivated, which still exists and whose page shows a tombstone. The skill page returns the tombstone before rendering its header (`frontend/app/skills/[slug]/page.tsx`), so the FR-2d menu never appears on a deactivated skill; the 404 reaches a user only when the skill is deactivated between page load and click, or between picker search and click. Copy amended to name both causes.
- info | Error UX | FR-2g's 429 row ("Too many additions in the last hour") now matches the API contract: the add limit is keyed by `user_id_key_func`, so the count is the user's own additions, and no other membership endpoint is rate-limited (no `default_limits` on any `Limiter` in `backend/app`). The 401, 403, 409-on-add, and 404-on-remove rows still match every status the contract lists for PUT and DELETE on a member.
- warning | Error UX | FR-2g's messages depend on the backend status reaching the browser through the Next.js route handlers that Module Design added in Round 1, "as the existing `frontend/app/api/skills/...` handlers do". Those handlers follow two patterns: every 204 endpoint special-cases `if (res.status === 204) return new NextResponse(null, { status: 204 })`, while `flag/route.ts` returns `NextResponse.json(data, { status: res.status })`, which throws on a 204 under the Fetch spec (a null-body status with a body). Copying the second pattern for the membership PUT and DELETE would turn every successful add or remove into a 500, and the user would see "Could not save the change" for a change that was saved. Amended to name the 204 pass-through.
- info | Documentation Quality | The guide entry and the CHANGELOG Slice 4 bullet in the Definition of Done did not mention the confirm prompt, the first thing a user meets. Another reviewer fixed both while this review ran; no further change.
- info | Trust & Reliability | ADR-U18 › Orphan members (Round 1) omits orphans from FR-5's hydrated `skills` list, but the API contract computes `member_count` as `len(members)` on both `SkillsetListOut` and `SkillsetOut`, so a skillset holding an orphan shows one more skill on its card than its page lists, until the next reorder drops the orphan. Orphans need a race or a Slice 1 rollback, so this is left as written; FR-7's M is defined from the `skills` list, not `member_count`, so the CLI's numbers agree with what it lists.
- info | Error UX | Read in the order a user meets them, the CLI messages are now one flow: the 401 stop with `s3df login` (auth rule), `✗ Skillset not found.`, `⚠ Skillset '<slug>' contains no skills.`, the replace questions, the member list and "Install these N of M skills" question, `Nothing installed.` on No, `[i/M]` install, skip, and failure lines, and the summary with its `✗` recap and re-run hint. No two rules now give different copy for the same event. `GIT_TERMINAL_PROMPT=0` (failure rule) and the questions-first order serve the same goal, a run that needs no input once confirmed.

**Opportunities**
- Mark internal members in the confirm list, for example "(needs SLAC GitHub access)", from the `visibility` that FR-5 already returns. The web page's FR-9 notice then has a CLI counterpart that the user sees before answering, not only as a clone failure afterwards.
- Give the confirm list's line an example form, as the summary line has one, for example `lcls-tools  https://github.com/slaclab/lcls-tools  (MCP server)`, so the `skill/SKILL.md` text and the narrative test check the same layout.

**Decisions Required**

*Decision: When the install loop asks the replace question*
- **Severity:** defaulted
- **Question:** For a member whose directory exists without `.installed-manifest.json`, should `install skillset` ask its replace question before the confirm list, inside the confirm list, or mid-loop?
- **Options:** A) Before the list: one replace question per such member, then the list and the single confirm question. B) Inside the list: mark the member "replaces ~/.claude/skills/<slug>/, not installed by /agent-knowledge-hub" and let the one confirm answer cover it. C) Mid-loop, when the loop reaches the member.
- **Assumed:** A, amended into FR-7 › Confirm rule and Skip rule. Every question comes before the first clone, the confirm count N is final when asked, and the user can decline one replacement without declining the whole set. B cannot keep one member and install the rest; C stalls an unattended run and asks two questions about one member.
- **Impact if wrong:** B drops the separate question and adds a marker to the list line; C restores the mid-loop prompt and needs the "N of M" count to be provisional. Either changes only FR-7's text and two narrative tests.

**Amendments**
- design: FR-7 › Confirm rule and Skip rule — the skip rule's replace questions are asked during the confirm step, before the member list, so every question comes before the first clone and a confirmed run needs no further input. A member the user keeps prints `[i/M] Skipping <slug> (kept your existing directory)` instead of the "already installed" line.
- design: FR-7 › Confirm rule — the question reads "Install these N of M skills from skillset <slug>? (y/N)", with M taken from the response's `skills` list and shared with the `[i/M]` progress lines; when N is 0 the command does not ask; No prints `Nothing installed.` and no summary line; a member whose values fail the argument rule is left out of the list, as a member whose fetch failed already was.
- precision: System Design › install sketch — step 2 loops over every member in stored order and prints a skip or failure line for an unlisted member, matching ADR-U20 › Consequences; it said "for each confirmed slug".
- precision: FR-2g — the "404 on add" message names a deactivated skill as a cause, matching ADR-U18 › Member resolution.
- precision: Module Design › Next.js route handlers — the member PUT and DELETE and the skillset DELETE pass a backend 204 through as `new NextResponse(null, { status: 204 })`, as `frontend/app/api/skills/[slug]/route.ts` does, not with `NextResponse.json`, which throws on a 204.
- precision: Test Plan › AKH skill narrative tests — merged the duplicate "Confirm declined" test into "Confirm prompt", which now expects the "N of M" question and `Nothing installed.`; added "Nothing to confirm"; the "Partial install" test expects the replace question before the list and none after the confirm.

TOTAL: 2 design, 4 precision

**Status**
PASS WITH WARNINGS

</details>

### Original review (2026-06-03)

**Verdict:** CLEAR TO BUILD
**Date:** 2026-06-03
**Rounds:** 3

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | YES | FK types must be `str` not `PydanticObjectId`; `ALL_MODELS` registration gap; admin routing contradiction resolved |
| codebase-arch-review | ⚠️ WARN | YES | All blocking gaps fixed: `ALL_MODELS`, `main.py` wiring, `purge_for_skill` cascade, FK types, `_skill_to_out` call-site scope |
| codebase-eng-review | ✅ PASS | YES | Test plan produced; slug validator, `ALL_MODELS`, and permission surface all verified; `frontend/types/skill.ts` Modify row added |
| doc-review | ✅ PASS | YES | README, CHANGELOG format, ADR filenames, SKILL.md sub-command spec all added to DoD; empty-skillset message added |
| security-review | ✅ PASS | YES | Slug `field_validator` with regex added; rate limit on `POST /api/skillsets`; membership endpoint `owner or admin`; PATCH routing resolved |
| codebase-ux-review | ⚠️ WARN | YES | Nav link, empty state CTA, copyable install block, mixed-visibility amber notice, `visibility` in API contract all specified; create page module entry added |

**Accepted warnings:** Skillset names are not unique by design (intentional, differs from Labels). `GET /api/skills/summary` (`SkillSummaryOut`) does not include `skillset_count` (out of scope for this task). PRD.md still lists skillsets as out-of-scope (documentation debt, deferred). No concept guide in `docs/` for this version.
**Unresolved decisions:** none

#### Reviewer output (2026-06-03)

<details>
<summary>research — Round 1+2 (PASS WITH WARNINGS)</summary>

Key findings: FK type mismatch (`PydanticObjectId` vs `str`), `ALL_MODELS` omission, admin routing contradiction, batch hydration wiring gap. All resolved via amendments.

</details>

<details>
<summary>codebase-arch-review — Round 1+2+3 (PASS)</summary>

Key findings: `ALL_MODELS` registration, `main.py` router wiring, `purge_for_skill` cascade, ADR-U19 contradiction (owner-or-admin on main router). Also: `_skill_to_out` call-site scope (only `get_skill` handler fetches skillsets), `routers/catalog.py` clarified. All resolved.

</details>

<details>
<summary>codebase-eng-review — Round 1+2 (PASS)</summary>

Full test plan appended under `## Test Plan`. Key additions: `purge_for_skill` test M9, `frontend/types/skill.ts` modify row, insertion-order test I12, slug immutability test I13. Coverage targets: services 90%, routers 85%.

</details>

<details>
<summary>doc-review — Round 1+2 (PASS)</summary>

DoD additions: CHANGELOG format, exact ADR filenames, README update scoped to Slice 2, SKILL.md sub-command detail spec including empty-skillset message. Merged Slice 2+3 introduces no new doc needs.

</details>

<details>
<summary>security-review — Round 1+2 (PASS)</summary>

Key findings: slug `@field_validator` with regex `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` + max 100 chars added to model spec. Rate limit `@limiter.limit("20/hour")` on `POST /api/skillsets`, `50/hour` on membership PUT. PATCH routing resolved to owner-or-admin on main router. Membership `owner only` → `owner or admin` alignment fixed in API contract.

</details>

<details>
<summary>codebase-ux-review — Round 1+2 (PASS WITH WARNINGS)</summary>

Key findings: nav entry point (Skillsets top-nav link added to FR-8), copyable CLI command block spec (FR-9), mixed-visibility amber notice above skill list (FR-9), skillset_count as separate line not badge (FR-11), persistent "+ Create Skillset" page-header button, `/skillsets/create` page added to module table, `visibility` added to API contract, DoD frontend bullet expanded.

</details>

---

## Problems & Solutions

### Problem: MongoDB sorts skillset names case-sensitively (2026-10-14, Slice 1)
`batch_skillsets_for_skills` first sorted with `.sort("name")`, which put "Second" before "first" in a skill's `skillsets` list, because MongoDB compares uppercase letters before lowercase ones.
**Solution:** the service sorts the matching skillsets in Python by the casefolded name, then the slug. The lookup is still one query.

### Problem: R17 passed before anyone checked that it could fail (2026-10-14, Slice 1)
The membership route tests were written after the router existed, so R17 passed on its first run.
**Solution:** R17 was run against two deliberate breakages of the add limiter in `app/routers/skillsets.py`: `key_style="url"`, and a per-address key. It failed under both and passed once the limiter was restored.

### Problem: manual reordering needs multi-document writes the tests cannot run (2026-10-14)
The 2026-06-03 design kept members in a `SkillsetMember` collection and ruled reordering out of scope. Adding reordering to that design means writing a position on many member rows at once. Those writes are atomic only inside a transaction, and the test database cannot run transactions (Measured facts › transactions-in-tests).
**Solution:** a throwaway prototype compared four storage designs under `mongomock_motor`, and its tests passed for each design's claimed behaviour. The embedded member list made every membership change one atomic write, so ADR-U18 now specifies it. The prototype also showed that the original reasons for rejecting an embedded list do not hold: a multikey index answers the reverse lookup, and subdocuments keep the audit fields. The prototype ran under mongomock only, not on a real MongoDB server; the operator behaviour it relied on was then checked against the MongoDB documentation and the 8.0 server source (References).

### Problem: `GET /api/skills?q=` cannot drive a typeahead (2026-10-14)
`list_skills` matches `q` with `$text`, which matches whole words only (Measured facts › text-vs-substring).
**Solution:** the search picker calls `GET /api/skills/summary?q=`, which filters by substring on name and description (FR-2c). That filter does not match slugs or labels.

### Problem: the install loop's skip rule and failure handling (2026-10-14)
A dry run of the per-skill install under a temporary HOME found three issues. Skipping on "directory exists" skips a partial install that has no manifest. One member with a missing `skill_path` (Measured facts › stale-skill-path) crashed the first version of the loop and stopped every member after it. The planned "internal skill, user not signed in" case cannot happen from the CLI, because the skillset fetch already fails without a token (Measured facts › cli-auth).
**Solution:** FR-7 now carries the skip rule, the failure rule, and the summary line, and user story 14 describes the real case: a token without access to SLAC's private GitHub repositories.

### Problem: list hydration pointed at the wrong router (2026-10-14)
The 2026-06-03 text put `skillset_count` hydration in `routers/catalog.py`. That router serves `/api/skills/summary` and `/marketplace.json`, not the paginated list. The paginated list is `list_skills` in `routers/skills.py`, which already batch-hydrates labels.
**Solution:** Module Design and Slice 1 now name `list_skills`. `GET /api/skillsets` keeps page-number pagination instead of the keyset cursors `list_skills` added in #015, because skillsets are few.

---

## Follow-ups (non-blocking)

- **Server-side `repo_url` and `skill_path` validation (deferred 2026-10-14, board review Round 1, security-review).** `_GITHUB_URL_RE` in `backend/app/schemas/skill.py` accepts shell syntax in the owner and repository segments, `skill_path` is checked only for `..` components, and a skill is stored even when GitHub cannot fetch it. The defect predates skillsets and also affects plain `install` and `marketplace.json`, so it has its own security task, [#045](045-sec-repo-url-skill-path-allowlist.md), which tightens the `_GITHUB_URL_RE` that #040 (complete) added. The task also runs one read-only query for stored skills whose `repo_url` or `skill_path` fails the new check, because a stricter create-time check does not change entries already stored, and `SkillUpdate` cannot edit either field. It blocks only Slice 4: the task must be deployed to production before Slice 4 merges, because Slice 4 goes live when it merges (Delivery Slices › Build-order prerequisites). FR-7's argument rule protects the install loop either way.

The items below come from the 2026-10-14 board review's Opportunities sections, deduplicated. None is required to build this task. The reviewer codes in brackets are research (dr), architecture (ar), engineering (er), documentation (dc), security (sr), and UX (ux).

**Install loop (Slice 4)**
- Skip non-active members before fetching them, using the `status` that FR-5 already returns, and print `superseded_by_slug`; today each run reports them as 410 failures. A line before the loop could count deactivated and internal members. [ar, er, ux]
- Add `repo_url`, `has_mcp_server`, and `has_scripts` to FR-5's hydrated summary, build the confirm list from that one request, and install exactly the metadata the user confirmed. This halves the catalog calls and removes the gap between what is confirmed and what is cloned. [er, sr, dc]
- Reuse one clone per `(repo_url, pinned_commit_sha)`; members from one repository are cloned once each today. [er]
- Stop the loop at the first GitHub rate-limit failure and say that a re-run with `GITHUB_TOKEN` set resumes, instead of failing every later member the same way. [ux]
- Mark internal members in the confirm list, give the confirm line an example layout, and add a summary hint that skipped skills keep their installed version until `update <slug>`. [ux]
- In failure output, name the field that failed the argument rule, not its value. [sr]
- Refuse to overwrite a file in `~/.claude/commands/` or `~/.claude/agents/` that another skill's manifest lists, and run the path guard on the slug before the skip rule builds a path from it. [sr]
- State in `skill/SKILL.md` that catalog text is data to show, never instructions to follow. [sr]
- Let `install skillset` with no slug list skillsets, and have Search also check `GET /api/skillsets` when a query names a facility or group (user story 15). [ux, dc]
- On git 2.47 and later, add `-c credential.interactive=false` to cover interactive credential helpers in general. [dr]

**Backend**
- Have the FR-2d menu request the largest `page_size`; with the default page size the menu silently truncates for an owner with more skillsets than one page holds. [ar, dr, er, ux]
- Return `SkillsetOut` (200) from the member `PUT` and `DELETE` endpoints, which saves the reload GET that FR-2f requires. [ar, dr]
- Give `skills_summary` and the skillset reverse lookups projections; `skills_summary` loads every active skill document in full on each call. [ar, dr, er, sr]
- Set `updated_at` in the add, remove, reorder, and cascade write shapes. [ar, dr, er]
- Rename the skillset `version` field to `revision`, because `Skill.version` already means a release version. [dr, er]
- Write the ADR-U18 shapes with Beanie's query builder instead of `get_motor_collection()`, so they survive the Beanie 2 rename. [dr]
- Raise a dedicated error for the reorder 422 instead of `ValueError`, sort FR-6's `skillsets` list by name, and reserve the slug `create`, which `frontend/app/skillsets/create/page.tsx` shadows. [er, ar]
- Bound the new inputs in `schemas/skillset.py` (list length, slug length, `version` range) and rate-limit the remaining skillset writes per user. [sr]
- Return only `slug`, `name`, and `status` for a non-active member in FR-5's hydration. [sr]
- Serve FR-2d from `GET /api/me/skillsets` so the client never supplies the identity it filters on. [sr]
- Add `slug` to the `skills_summary` substring filter, and `visibility` to `SkillSummaryOut` so the picker can show the "SLAC Only" badge. [ux]
- If remove-and-re-add disputes happen, add a sticky author opt-out (`excluded_skill_ids`) or a short removal trail on `Skillset`; both fit one atomic write. [ar, ux]
- Make the skillset fields on write-handler responses `Optional`, and let `get_skill` and `list_skills` return no skillset data if hydration fails. [ar]

**Frontend**
- Encode every path parameter with `encodeURIComponent` in the new `frontend/app/api/skillsets/...` handlers. [sr]
- Fetch `/api/skills/summary` once when the picker opens and filter in the browser, or debounce it and cap the results. [dr, er, sr, ux]
- Extract FR-2g's status-to-message mapping and FR-2f's move as pure functions in `frontend/lib/` with vitest tests. [er]
- Add "Move to top" and "Move to bottom", show "Replaced by <slug>" for deactivated members, and give the submitter's Remove control a path from the tombstone page. [ux, ar]
- Show the "Add to skillset" menu to users who own no skillset, with one "Create a skillset →" entry (declined for this version). [ux]
- Add a prerequisites line under FR-9's command block, and render skillset names and descriptions as plain text. [ux, sr]

**Tests**
- Run the write-shape tests once against a real MongoDB 8.0 server before merge, and add an integration row for AC-13 on `GET /api/skills/summary?q=`. [er, ar, dr]
- Reset the skillsets limiter with `limiter.reset()` in an autouse fixture instead of relying on R17's unique user ids. [er]
- State the check order for add and remove (lookup, permission, skill resolution, write) and give R6 a skill that is already a member. [sr]

**Docs**
- Add an `install skillset` entry to `frontend/app/guides/troubleshooting/page.tsx`, a short admin runbook for the API-only delete and rename, and a comment at `add_skill` naming ADR-U18 › Write shapes. [dc, ux]
- Add `install skillset` to the command table in `PRD.md` › 15, and update open question 4 in `todo/029-skillset-cross-ownership-add.md` for the embedded member list. [dc]
- Consider removing `version` from `.claude-plugin/plugin.json` so users track commits, and drop the no-op `"path": "skill"` key from the marketplace entry. [dr]

**Outside this task (found during the review; existing code)**
- An anonymous GET to `/marketplace.json` returned 401 on 2026-10-14, so the README's `/plugin marketplace add` step may fail for clients that send no token. [dc]
- `backendHeaders()` in `frontend/app/api/_internal.ts` takes the user from the first non-empty of four client-visible headers. Whether the deployed gateway lets a client set them is unverified; send a signed-in request to `/api/me` on dev with a spoofed `X-Auth-Request-User` to settle it. ADR-P05 deferred the ingress fix. [sr]
- Reject non-GET requests to the Next.js API routes whose `Origin` is not the app's own. [sr]
- The `[CREATE]` log line in `create()` in `backend/app/services/skill.py` writes raw `repo_url` and `skill_path`, which can carry a newline; belongs with the validation task above. [sr]
- `create_flag`'s 10/hour limit uses slowapi's per-path scope, so it limits flags per user per skill; the `user_id_key_func` docstring in `backend/app/auth.py` misdescribes when the user is set. [er, sr]
- `merge()` and `delete()` in `backend/app/services/label.py` open a transaction but pass `session=` to none of their writes, and `rename()` passes it only to its final update. [ar]
---

## References

ADR-U18 › Write shapes and FR-2c rest on these MongoDB behaviours, checked on 2026-10-14 against the documentation and the 8.0 server source:

- Single-document writes are atomic, and putting the expected current value in the filter prevents conflicting concurrent updates. The add guard (`$ne`) and the reorder guard (`version`) both use this. `update_many` is atomic per document, not as a whole. <https://www.mongodb.com/docs/manual/core/write-operations-atomicity/>
- `$pull` with a condition that is a document applies it to each array element as a query, so `{skill_id: x}` removes a subdocument that also carries `added_by` and `added_at`. The `ObjectMatcher` in the 8.0 source does this. <https://www.mongodb.com/docs/manual/reference/operator/update/pull/>, <https://github.com/mongodb/mongo/blob/r8.0.0/src/mongo/db/update/pull_node.cpp>
- An index on a field of an array of subdocuments, such as `members.skill_id`, is multikey and supports queries on that field. <https://www.mongodb.com/docs/manual/core/indexes/index-types/index-multikey/create-multikey-index-embedded/>
- `$text` matches complete stemmed words only: a search for `blue` does not match `blueberry`. <https://www.mongodb.com/docs/manual/reference/operator/query/text/>

Delivery Slices › Build-order prerequisites and Slice 4 rest on this Claude Code behaviour, checked on 2026-10-14:

- **Claude Code plugin updates.** A `github` plugin source takes `repo`, `ref`, and `sha`, has no `path` field, and fetches the default branch when `ref` is omitted. Background auto-update is off for a third-party marketplace by default, and a user receives a new copy of a plugin only when its computed version changes; that version comes from `plugin.json` first. <https://code.claude.com/docs/en/plugins/marketplace-reference>, <https://code.claude.com/docs/en/plugins/host-marketplace>

FR-7 › Failure rule rests on this git behaviour, checked on 2026-10-14:

- `git_prompt()` runs an askpass program from `GIT_ASKPASS`, `core.askPass`, or `SSH_ASKPASS` before it consults `GIT_TERMINAL_PROMPT`, and skips askpass when `GIT_ASKPASS` is set but empty. <https://github.com/git/git/blob/master/prompt.c>, <https://git-scm.com/docs/git#Documentation/git.txt-GITTERMINALPROMPT>. Git Credential Manager's own prompts are governed by `GCM_INTERACTIVE`. <https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/environment.md>

---

## Test Plan

> Added by eng review (round 1). See full findings in `todo/review/006-skillsets/round-1-er.md`.

### Scope

```
Unit tests (pytest + mongomock)
  models/skillset.py — slug and name validators (U4–U7)
  services/skillset.py — create, membership, order, cascade, batch hydration, permissions, NFR-5 log line
Integration tests (ASGI + mongomock, AsyncClient)
  routers/skillsets.py — CRUD, membership, order, auth (401, 403), rate limit (429)
  routers/skills.py additions — skillset_count + skillsets on detail + list, auto-add on create (FR-2b)
  routers/catalog.py — /api/skills/summary substring match (S4)
Frontend — manual, in a browser
  skillset pages, skill page additions, submit form, FR-2g messages
AKH skill — narrative tests (manual)
  install skillset: every case listed under AKH skill narrative tests below
```

mongomock checks the logic of ADR-U18 › Write shapes but not their concurrency or index use. It runs one operation at a time and scans instead of using indexes, so the `$ne` and `version` guards rest on MongoDB's single-document atomicity (References), and NFR-3's use of the `members.skill_id` index is confirmed with one read-only `explain()` on dev after Slice 1. B1 counts queries with a spy on `Skillset.find`, because mongomock has no command monitoring.

Fixture rules:
- Admin identity is set with `monkeypatch.setattr(config.settings, "admin_users", ...)`, as `backend/tests/test_moderation.py` does. The `_auth_headers(is_admin=True)` helper in `backend/tests/test_labels.py` assigns `config.settings.admin_users` without restoring it, so admin status would leak into later deny tests.
- A race is simulated in sequence: read `version`, make the competing write, then call the operation under test with the old value. mongomock runs one operation at a time, and this ordering reproduces every race in ADR-U18.
- Tests compare `added_at` values read back from the database. mongomock returns stored datetimes naive and truncated to milliseconds, so an in-memory `datetime.now(timezone.utc)` never equals the stored value.
- R17 uses two user ids that no other test uses. Every `Limiter` in the repo keeps its counts in process memory for the whole pytest run, and `backend/tests/conftest.py` never resets them, so R17's adds under a shared id would make later add tests return 429. No existing test drives a slowapi limit to 429; the label test that expects 429 hits the label service's own cap.

### Unit: `TestSkillsetServiceCreate`

| # | Test | Expected |
|---|---|---|
| U1 | `create()` valid → `members=[]`, `version=0`, `created_by` set | pass |
| U2 | slug auto-derived from name (`"My Skillset"` → `"my-skillset"`) | |
| U3 | duplicate slug raises `SkillsetAlreadyExistsError` with `suggested_slug` | |
| U4 | slug with spaces raises `ValueError` (validator) | |
| U5 | slug `"../etc"` raises `ValueError` | path traversal blocked |
| U6 | empty slug raises `ValueError` | |
| U7 | name > 200 chars raises `ValueError` | |

### Unit: `TestSkillsetServiceMembership`

| # | Test | Expected |
|---|---|---|
| M1 | `add_skill()` → member appended at the end, `version` incremented | AC-2 |
| M2 | `add_skill()` twice same skill → `SkillsetMemberAlreadyError` (409) | idempotent guard |
| M3 | `add_skill()` unknown slug → `SkillNotFoundError` (404) | |
| M4 | `remove_skill()` → member removed, `version` incremented | AC-3 |
| M5 | `remove_skill()` non-member → `SkillsetMemberNotFoundError` (404) | |
| M6 | `add_skill()` on a missing skillset → `SkillsetNotFoundError` (404), not `SkillsetMemberAlreadyError` | add write shape matches nothing in both cases |
| M7 | `add_skill()` by non-owner raises `PermissionDeniedError` | AC-7 |
| M8 | Admin can `add_skill()` on any skillset | `is_admin=True` bypass |
| M9 | `purge_for_skill(skill_id, skill_slug, actor_id)` removes the skill from every skillset's members and increments each one's `version` | AC-15 |
| M10 | `remove_skill()` by the skill's submitter on another user's skillset succeeds | AC-11 |
| M11 | `remove_skill()` by a user who is neither owner, admin, nor the skill's submitter raises `PermissionDeniedError` | AC-11 |
| M12 | `add_skill()` by the skill's submitter on another user's skillset raises `PermissionDeniedError` | submitters may remove, not add |
| M13 | A skill in two skillsets deleted with `skill_repository.delete()` → neither skillset lists it, and each `version` incremented | AC-15; fails if `delete()` never calls `purge_for_skill()`, which M9 cannot detect |
| M14 | `remove_skill()` by an admin on another user's skillset succeeds | ADR-U19 › Permission rules, admin allow |
| M15 | `remove_skill()` of a deactivated member by the owner succeeds | ADR-U18 › Member resolution |
| M16 | `add_skill()` of a deactivated skill → `SkillNotFoundError` (404) | ADR-U18 › Member resolution |

### Unit: `TestSkillsetServiceOrder`

| # | Test | Expected |
|---|---|---|
| O1 | `reorder()` with current `version` and a permutation → order stored, `version` incremented, `added_by`/`added_at` kept | AC-12 |
| O2 | `reorder()` with stale `version` → `SkillsetVersionConflictError` (409), order unchanged | AC-12 |
| O3 | `reorder()` list missing a member → `ValueError` (422) | AC-12 |
| O4 | `reorder()` list with an extra or repeated slug → `ValueError` (422) | AC-12 |
| O5 | `add_skill()` after `reorder()` appends at the end | FR-2f |
| O6 | `reorder()` by non-owner raises `PermissionDeniedError` | ADR-U19 › Permission rules |
| O7 | `reorder()` by an admin on another user's skillset succeeds | ADR-U19 › Permission rules, admin allow |
| O8 | Read `version`, add a member, then `reorder()` with the old `version` and the old list → `SkillsetVersionConflictError` (409), not `ValueError` | ADR-U18 › Write shapes › reorder, 409 before 422 |
| O9 | Read `version`, delete a member's skill with `skill_repository.delete()`, then `reorder()` with the old `version` and the old list → 409 | the "skill deleted after page load" case |
| O10 | `reorder()` of a skillset with a deactivated member, whose slug is in the list → 200 with the new order | ADR-U18 › Member resolution |
| O11 | A skillset holding an orphan member (a `skill_id` with no `Skill` document, inserted directly): `reorder()` with the other members' slugs → 200, and the stored `members` no longer contain the orphan | ADR-U18 › Orphan members |

### Unit: `TestSkillsetServiceBatchHydration`

| # | Test | Expected |
|---|---|---|
| B1 | `batch_skillsets_for_skills([id1, id2])` — 1 query on `members.skill_id`, no N+1 | NFR-3 |
| B2 | skill in 2 skillsets → `len(result[skill_id]) == 2` | |
| B3 | skill in 0 skillsets → `result[skill_id] == []` | |
| B4 | empty input → `{}` | mirrors labels pattern |

### Unit: `TestSkillsetServicePermissions`

| # | Test | Expected |
|---|---|---|
| P1 | `update()` by owner succeeds | |
| P2 | `update()` by non-owner raises `PermissionDeniedError` | |
| P3 | `update()` by admin succeeds | |
| P4 | `delete()` by owner removes the skillset document and its members with it | AC-8 |
| P5 | `delete()` by non-owner raises `PermissionDeniedError` | |
| P6 | Read the skillset, add a member, then `update()` the name with the service's skillset lookup monkeypatched to return the copy read before the add → the name changes, and `members` and `version` match the values after the add | ADR-U18 › Write shapes › edit details; without the patched lookup, `update()` reads after the add and a `save()` would pass |

### Unit: `TestSkillsetServiceAuditLog`

Each test captures the `app.services.skillset` logger at INFO with pytest's `caplog` and checks the records that one call emits.

| # | Test | Expected |
|---|---|---|
| L1 | Each of `create()`, `update()`, `delete()`, `add_skill()`, `remove_skill()`, and `reorder()` by the owner → exactly one INFO record, naming the owner's `user_id`, the action, and the stored skillset slug, and for add and remove also the stored skill slug | NFR-5 |
| L2 | `remove_skill()` by the skill's submitter on another user's skillset → the record names the submitter's `user_id`, not the owner's | NFR-5: the only record of who removed a member |
| L3 | `add_skill()` refused with `PermissionDeniedError`, and a repeated `add_skill()` of a member (409) → no NFR-5 record | NFR-5 covers successful writes only |
| L4 | `skill_repository.delete()` of a skill in two skillsets → one cascade record naming the actor and both skillset slugs; deleting a skill in no skillset → no cascade record | NFR-5, cascade |

### Integration: `TestCreateSkillAutoAdd`

C1 to C4 submit with `source_type: "local"`, as `backend/tests/test_local_submit.py` does, so no test reaches GitHub.

| # | Test | Expected |
|---|---|---|
| C1 | `POST /api/skills` with `skillset_slug` of a skillset the submitter owns → 201, and the skill is the skillset's last member | AC-10, owner allow |
| C2 | `POST /api/skills` with `skillset_slug` of another user's skillset → 201, and that skillset's `members` and `version` are unchanged | AC-10, non-owner deny |
| C3 | Same as C2 with an admin submitter → 201, and the skillset is unchanged | ADR-U19 › Permission rules: auto-add is owner-only |
| C4 | `POST /api/skills` with a `skillset_slug` that does not exist → 201 | FR-2b |

### Integration: `TestSkillsetsRouterCRUD`

| # | Test | Expected |
|---|---|---|
| I1 | `POST /api/skillsets` authenticated → 201 | AC-1 |
| I2 | `POST /api/skillsets` unauthenticated → 401 | |
| I3 | `POST /api/skillsets` duplicate slug → 409 + `suggested_slug` | |
| I4 | Three skillsets, `page_size=2`: page 1 and page 2 together list each skillset exactly once, newest first | FR-4 sort order |
| I5 | `GET /api/skillsets/{slug}` of a three-member skillset whose second member is deactivated and whose first member carries a label applied with `label_service.add()` → 200 with `version`, the three members in stored order, that label in the first member's `labels`, and `status: "deactivated"` on the second | AC-4, FR-5 |
| I6 | `GET /api/skillsets/{slug}` unknown → 404 | |
| I7 | `PATCH /api/skillsets/{slug}` by owner → 200 | |
| I8 | `PATCH /api/skillsets/{slug}` by non-owner → 403 | AC-7 |
| I9 | `DELETE /api/skillsets/{slug}` by owner → 204 | |
| I10 | `DELETE /api/skillsets/{slug}` by admin → 204 | AC-8 |
| I11 | `DELETE /api/skillsets/{slug}` by non-owner → 403 | |
| I12 | `PATCH /api/skillsets/{slug}` with a `slug` field in the body → the stored slug is unchanged | ADR-U19 › Consequences, slug immutable |
| I13 | `GET /api/skillsets/{slug}` of a skillset holding an orphan member → 200 without that member | ADR-U18 › Orphan members |

### Integration: `TestSkillsetsRouterMembership`

| # | Test | Expected |
|---|---|---|
| R1 | `PUT /api/skillsets/{slug}/skills/{skill_slug}` owner → 204, member appended | AC-2 |
| R2 | `PUT` same skill twice → 409 | |
| R3 | `PUT` unknown skill_slug → 404 | |
| R4 | `DELETE /api/skillsets/{slug}/skills/{skill_slug}` owner → 204, member removed | AC-3 |
| R5 | `DELETE` non-member → 404 | |
| R6 | `PUT` by non-owner → 403 | AC-7 |
| R7 | `DELETE` by a user who is neither owner, admin, nor the skill's submitter → 403 | AC-7 |
| R8 | `DELETE` by the skill's submitter on another user's skillset → 204 | AC-11 |
| R9 | `PUT /api/skillsets/{slug}/order` owner, current `version` → 200 with new order | AC-12 |
| R10 | `PUT .../order` stale `version` → 409 | AC-12 |
| R11 | `PUT .../order` list that is not the member set → 422 | AC-12 |
| R12 | `GET /api/skillsets?created_by=<user_id>` → only that user's skillsets | FR-4 |
| R13 | `PUT .../order` by non-owner → 403 | AC-7, router level for O6 |
| R14 | `PUT .../skills/{skill_slug}`, `DELETE .../skills/{skill_slug}`, and `PUT .../order` with no identity headers → 401 | ADR-U19 › Permission rules |
| R15 | `DELETE .../skills/{skill_slug}` of a deactivated member by the owner → 204 | ADR-U18 › Member resolution, router level for M15 |
| R16 | The submitter of a member skill, on another user's skillset: `PUT .../order`, `PATCH /api/skillsets/{slug}`, and `DELETE /api/skillsets/{slug}` → 403 each, and the skillset is unchanged | ADR-U19 › Permission rules: a submitter may remove, nothing else |
| R17 | User A adds 51 different skills to A's skillset with `PUT .../skills/{skill_slug}` within the hour: the first 50 → 204, the 51st → 429; then user B's first add, to B's own skillset from the same client address → 204 | API contract: the add limit counts per user across every path; fails under slowapi's default `key_style="url"` (51st → 204) and under a per-address key (B → 429) |

### Integration: `TestSkillDetailIncludesSkillsets`

| # | Test | Expected |
|---|---|---|
| S1 | skill in 2 skillsets → `skillset_count=2`, `skillsets` list populated | AC-5 / FR-6 |
| S2 | skill in 0 skillsets → `skillset_count=0`, `skillsets=[]` | |
| S3 | list endpoint → each item has `skillset_count` (batch, no N+1) | FR-11 / NFR-3 |
| S4 | `GET /api/skills/summary?q=depl` with a skill whose name contains "deploy" → that skill is in the results | AC-13 backend half; pins the substring match the FR-2c picker relies on (Measured facts › text-vs-substring) |

### Frontend (manual)

`frontend/` runs vitest only for `lib/*.test.ts` and has no component tests, so these checks run by hand in a browser against a deployment with Slice 1 and Slice 2+3. "The second tab" is the same page open in another tab of the same browser.

| # | Check | Expected |
|---|---|---|
| F1 | The owner clicks "Add new skill →" on a skillset page and submits a skill; separately, opens `/skills/submit?skillset=<slug>` for another user's skillset | The form shows "Will be added to skillset: <name>", and after submission the browser is back on the skillset page with the new skill last; the other user's slug shows no notice (AC-9, AC-10 frontend half) |
| F2 | The owner types `depl` in the search picker | The skill named with "deploy" is listed, unrelated skills are not, and members already in the set are disabled (AC-13 frontend half). Only this check goes through `frontend/app/api/skills/summary/route.ts`; S4 calls the backend directly |
| F3 | A skill in two skillsets, and a skill in none | The first shows "Part of 2 skillset(s)" with both links and "in 2 skillset(s)" on its card; the second shows neither (AC-5 frontend half, FR-10, FR-11) |
| F4 | The FR-2d menu, for a user who owns two skillsets, one of which holds the skill | Only that user's skillsets are listed, the one holding the skill is checked, and checking or unchecking an entry updates "Part of N skillset(s)" after the refresh (FR-2d, FR-2g) |
| F5 | The skill's submitter clicks Remove on another user's skillset link, cancels, then removes; another signed-in user views the same page | The FR-2e confirmation text appears, cancelling keeps the membership, confirming removes it; the other user sees no Remove control |
| F6 | The second tab adds a member, then the first tab moves a member; then a move with DevTools network throttling; then a move right after an add on the same page | FR-2f's stale-page message and the reloaded list; the up and down controls disabled while the throttled move is in flight; the move after an add succeeds |
| F7 | From the second tab: make the same add or remove as the first tab; delete a skill the first tab's picker still lists; sign out; sign in as another user. Also: DevTools offline, and a search no skill matches | The repeated change is treated as success with no message; then FR-2g's "404 on add", 401, 403, "Search failed", "Could not save", and no-results messages appear next to the control, which is disabled while its request is in flight. The 429 row is not provoked by hand; R17 pins the status |
| F8 | `/skillsets` with no skillsets, signed in and signed out; a skillset with an internal member and a deactivated member | FR-8's two empty states; FR-9's amber notice above the skill list, the deactivated member marked, and the command block reading `/agent-knowledge-hub install skillset <slug>` |

### AKH skill narrative tests (manual)

Each test runs under a temporary HOME. A test that needs a catalog entry no real catalog should hold, such as the hostile values below, runs against a local backend whose database holds that entry, with the session told to use it as the catalog base URL. Hostile entries are never inserted into the dev or production catalog, because `marketplace.json` and the search command would serve them to every user.

- **Happy path:** 2-skill skillset, both uninstalled → `[1/2] Installing... [2/2] Installing...`, then the summary line
- **Token handling:** during the happy path, the transcript shows every catalog request with `$(cat ~/.s3df-access-token)` and never the token's value, and no `git` command and no request to a `repo_url` carries an `Authorization` header (FR-7's auth rule)
- **Confirm prompt:** a 3-member skillset with one member already installed and one member with `has_mcp_server` true → the prompt lists only the two uninstalled members, the second line says "MCP server", and the question reads "Install these 2 of 3 skills from skillset <slug>? (y/N)"; answering N prints `Nothing installed.` and no summary line, writes nothing under `~/.claude/`, and runs no `claude mcp add`
- **Nothing to confirm:** every member already installed → no question; one skip line per member, then the summary line
- **Fetch fails before the prompt:** a member that returns 410 → it is missing from the prompt's list and appears as failed in the summary recap
- **Skip already-installed:** 1 member with `.installed-manifest.json`, 1 not → skip + install, correct counts
- **Partial install:** member directory present without `.installed-manifest.json` → the replace prompt from FR-7's skip rule, asked before the confirm prompt's list; yes lists the member and reinstalls it, no prints `Skipping <slug> (kept your existing directory)` and leaves the directory untouched, and no question is asked after the confirm prompt
- **Failed member recap:** a 3-member skillset whose second member fails → the summary line is followed by one `✗` line for that member with its reason and next step, and the re-run hint
- **Failed member:** a member whose `skill_path` is not in the clone → reported as failed, later members still install (AC-14)
- **No GitHub access:** an internal member, with a token but no access to the repository → reported with `gh auth login` and the full URL of `/guides/slac-github-access`; the clone command in the transcript sets `GIT_TERMINAL_PROMPT=0`, the run does not stop at a credential prompt, and the other members install
- **Empty skillset:** → `⚠ Skillset '<slug>' contains no skills.`
- **Unknown slug:** → `✗ Skillset not found.`
- **No token:** `~/.s3df-access-token` absent or expired → the skillset fetch returns 401 and the command stops with the `s3df login` hint from FR-7's auth rule; nothing is installed
- **Hostile repo_url and skill_path:** one member whose `repo_url` is `https://github.com/a/b$(touch /tmp/akh-pwned)` and another whose `skill_path` is `/skills/$(touch /tmp/akh-pwned-path)`, both stored in the local backend's database → both are missing from the confirm prompt's list, and each is reported as a path-guard abort under FR-7's argument rule; neither `/tmp/akh-pwned` nor `/tmp/akh-pwned-path` exists afterwards, and the other members install

### Coverage targets

| Module | Target |
|---|---|
| `services/skillset.py` | 90% |
| `routers/skillsets.py` | 85% |
| `routers/skills.py` additions | 80% |
| `models/skillset.py` validators | 100% |
