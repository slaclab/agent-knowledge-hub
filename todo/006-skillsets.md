# 006 — Skillsets: Curated Skill Collections

**Status:** 🔍 Reviewed
**Branch:** —
**PR:** —

---

## Problem & Goal

**Problem:** Users from different facilities and groups (USDF, LCLS, SCS, etc.) need a way to discover and install a curated bundle of skills relevant to their context. Today, every skill is standalone — there is no concept of a collection, no way for a facility lead to say "these 12 skills are what LCLS users should start with", and no signal on a skill's detail page that it belongs to a well-known set.

**Goal:** Introduce **Skillsets** — named, curated collections of skills maintained by a submitter. A skillset can be discovered, browsed, and installed as a unit. Each skill surfaces a reverse link showing which skillsets it belongs to, giving a secondary popularity signal beyond star ratings.

**Success metrics:**
- A user can browse skillsets, see which skills they contain, and install the full set in one action (via `/agent-knowledge-hub install skillset <slug>`)
- A curator can create, name, describe, and manage a skillset (add/remove skills)
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
11. As a curator, I want to edit a skillset I own (rename, re-describe, reorder skills), so that I can maintain it over time.
12. As a curator, I want to delete a skillset I own, so that I can remove collections I no longer maintain.
13. As a user, I want the skillset install command to skip skills I already have installed, so that re-running is safe.
14. As a user, I want a clear error if a skill in the skillset is internal and I'm not authenticated, so that I understand why part of the install was skipped.
15. As an API consumer (LLM agent), I want to query `GET /api/skillsets` with metadata, so that skill discovery from within an agent session is possible.

---

## Requirements

### Functional

- **FR-1:** Any authenticated user can create a skillset with a name, slug, and description.
- **FR-2:** A skillset curator can add and remove existing catalog skills by slug.
- **FR-2a:** The skillset detail page (owner-only view) shows an "Add new skill →" button that navigates to `/skills/submit?skillset=<slug>`. After successful submission, the new skill is automatically added to the skillset and the user is redirected back to the skillset detail page.
- **FR-2b:** The skill submit form accepts an optional `skillset` query parameter. When present and the submitter owns that skillset, the newly created skill is automatically added to it after creation. If the submitter does not own the skillset (or it doesn't exist), the skill is still created normally — the `skillset` param is silently ignored (cross-ownership addition is handled by #029).
- **FR-3:** Skillset slugs are unique, URL-safe, lowercase, and auto-derived from the name (editable at creation).
- **FR-4:** `GET /api/skillsets` returns paginated list with skill counts and curator.
- **FR-5:** `GET /api/skillsets/{slug}` returns full skillset with hydrated skill summaries.
- **FR-6:** `GET /api/skills/{slug}` response includes `skillset_count` and a `skillsets` list (names + slugs).
- **FR-7:** The AKH skill gains `install skillset <slug>` — installs each member skill in sequence using the existing per-skill install flow, skipping already-installed ones.
- **FR-8:** A `/skillsets` page in the frontend lists all skillsets as cards. A "Skillsets" link is added to the top nav alongside "Guides". Authenticated users see a persistent "+ Create Skillset" page-header button (visible whether or not skillsets exist). Empty state for authenticated: "No skillsets yet. [Create a skillset →]". Empty state for unauthenticated: "No skillsets yet. Skillsets are curated bundles of skills. Sign in to create one." (no button).
- **FR-9:** A `/skillsets/[slug]` detail page shows description, curator, skill list, and a copyable command block: `install skillset <slug>` (no browser-side install action). If any member skill has `visibility: internal`, show an amber notice **above the skill list**: "N skill(s) in this set require SLAC GitHub access." Skills are displayed in insertion order (`added_at ASC`); manual reordering is out of scope.
- **FR-10:** Skill detail page shows "Part of N skillset(s)" section with links. Section is hidden when `skillset_count === 0`.
- **FR-11:** Skill list cards show "in N skillset(s)" count as a separate line below the description (not in the badge row), rendered only when `skillset_count > 0`.
- **FR-12:** Admin can delete or rename any skillset.
- **FR-13:** Curator can edit name/description and delete their own skillset.

### Non-functional

- **NFR-1:** Skillset list and detail pages load in < 500ms (p95).
- **NFR-2:** Adding/removing a skill from a skillset updates `member_count` atomically.
- **NFR-3:** `batch_skillsets_for_skills` hydration follows the same 2-query pattern as labels — no N+1.
- **NFR-4:** AKH `install skillset` is safe to re-run (idempotent per skill).

### Acceptance Criteria

- **AC-1:** Given an authenticated user, when they POST `/api/skillsets` with a valid name, then a skillset is created and returned with slug, curator, and empty member list.
- **AC-2:** Given a skillset curator, when they PUT `/api/skillsets/{slug}/skills/{skill_slug}`, then the skill is added and `member_count` increments.
- **AC-3:** Given a skillset curator, when they DELETE `/api/skillsets/{slug}/skills/{skill_slug}`, then the skill is removed and `member_count` decrements.
- **AC-4:** Given a user, when they GET `/api/skillsets/{slug}`, then the response includes hydrated skill summaries (name, slug, description, labels).
- **AC-5:** Given a skill in 2 skillsets, when the skill detail page loads, then "Part of 2 skillset(s)" appears with links to both.
- **AC-6:** Given `install skillset lcls-starter` in an AKH session, when the command runs, then each skill in the set is installed, with skips reported for any already-installed ones.
- **AC-7:** Given a non-owner authenticated user, when they try to PUT/DELETE skills in someone else's skillset, then a 403 is returned.
- **AC-8:** Given an admin, when they DELETE `/api/skillsets/{slug}`, then the skillset and all its membership rows are removed.
- **AC-9:** Given a curator on the skillset detail page, when they click "Add new skill →", they land on `/skills/submit?skillset=<slug>`. After successful submission, the new skill appears in the skillset.
- **AC-10:** Given a submit form loaded with `?skillset=<slug>` where the submitter owns the skillset, when the skill is created, it is automatically added to that skillset. If the submitter does not own the skillset, the skill is created normally with no skillset assignment.

---

## Architecture Decision Records

### ADR-U18: Skillset data model — first-class document + junction collection

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Skillsets are a many-to-many relationship between a Skillset entity and Skill documents. Two options: embed skill slugs as an array on the Skillset document, or use a separate `SkillsetMember` junction collection.

#### Options

| Option | Pros | Cons |
|---|---|---|
| Embedded slug array on Skillset | Simple reads, one document | Hard to query "which skillsets contain skill X" (reverse lookup requires scanning all skillsets), no membership audit trail |
| First-class `Skillset` doc + `SkillsetMember` junction | Efficient reverse lookup via index on `skill_id`, audit trail (added_by, added_at), mirrors proven Labels pattern | Two collections |

#### Decision
**First-class `Skillset` document + `SkillsetMember` junction collection.** Mirrors the `Label`+`SkillLabel` pattern which is already proven. Reverse lookup (skills → skillsets) requires an index on `SkillsetMember.skill_id` — one query, no scan. Membership audit trail is a bonus.

#### Consequences
- `Skillset`: `slug`, `name`, `description`, `created_by`, `created_at`, `updated_at`, `member_count` (denormalized)
- `SkillsetMember`: `skillset_id`, `skill_id`, `skill_slug`, `added_by`, `added_at`
- Index: `(skill_id)` on `SkillsetMember` for reverse lookup; `(skillset_id, skill_id)` unique for dedup

---

### ADR-U19: Curator permissions — any authenticated user (not admin-only)

**Status:** Proposed
**Date:** 2026-06-03

#### Context
Should skillset creation be open to all authenticated users (like label application), or restricted to admins?

#### Options

| Option | Pros | Cons |
|---|---|---|
| Admin-only | Prevents spam/low-quality collections | Blocks facility leads from self-serving; admin bottleneck |
| Any authenticated user | Facility leads are self-sufficient | Potential for low-quality or duplicate collections |

#### Decision
**Any authenticated user can create and manage their own skillsets.** Same model as label application — community-driven. Admins retain delete/rename powers for moderation. With a small, known user community (SLAC), spam risk is low.

#### Consequences
- `POST /api/skillsets` requires `get_current_user`; sets `created_by = user.user_id`
- Owner check on edit/delete: `skillset.created_by == user.user_id or user.is_admin`
- `PATCH /api/skillsets/{slug}` (name/description update) and `DELETE /api/skillsets/{slug}` on the main router, gated by owner-or-admin check — consistent with the API contract. No separate admin router needed for these operations.
- Note: `slug` is immutable post-creation and must not appear in `SkillsetUpdate`.

---

### ADR-U20: AKH `install skillset` — sequential per-skill install reuse

**Status:** Proposed
**Date:** 2026-06-03

#### Context
"Install a skillset" means installing N individual skills. Options: new dedicated endpoint that returns a bundle manifest, or reuse the existing per-skill install flow in the AKH skill.

#### Options

| Option | Pros | Cons |
|---|---|---|
| New `/api/skillsets/{slug}/install-manifest` endpoint | Single API call from agent | Duplicates install logic in backend; backend shouldn't know about agent install paths |
| Agent-side loop using existing per-skill install | Reuses all existing install primitives (path guard, git-clone, copy-from-clone, idempotency) | N API calls, slightly slower |

#### Decision
**Agent-side loop.** The AKH skill's `install skillset <slug>` fetches `GET /api/skillsets/{slug}`, extracts the member slugs, and runs the existing `install <slug>` flow for each. Already-installed skills are detected and skipped. No new backend install logic needed — only the skillset read endpoint is new.

#### Consequences
- Requires `GET /api/skillsets/{slug}` to return member skill slugs
- AKH SKILL.md gains one new sub-command section
- Install is sequential (not parallel) to avoid thundering-herd on GitHub rate limits
- Progress reported per skill: `[1/5] Installing lcls-tools... ✓`, `[2/5] Skipping akh-core (already installed)`

---

## Module Design

### Backend

| Module | Responsibility | Interface | Status | Testable |
|---|---|---|---|---|
| `models/skillset.py` | `Skillset` + `SkillsetMember` Beanie documents | Document classes + indexes | New | Yes |
| `schemas/skillset.py` | Pydantic I/O: `SkillsetCreate`, `SkillsetUpdate`, `SkillsetOut`, `SkillsetListOut` | Pydantic models | New | Yes |
| `services/skillset.py` | CRUD + membership + batch hydration for skills | `create()`, `add_skill()`, `remove_skill()`, `get()`, `list()`, `batch_skillsets_for_skills()` | New | Yes |
| `routers/skillsets.py` | HTTP layer: CRUD endpoints + membership endpoints | REST routes | New | Integration |
| `routers/skills.py` | Add `skillset_count` + `skillsets` to `SkillOut` | Modify `_skill_to_out()` | Modify | Yes |
| `routers/catalog.py` | Batch-hydrate `skillset_count` on `SkillListOut` (mirrors label batch pattern) | Modify catalog list handler | Modify | Yes |
| `schemas/skill.py` | Add `skillset_count: int`, `skillsets: List[SkillsetRef]` to `SkillOut`; add `skillset_count: int` to `SkillListOut` | Schema fields | Modify | Yes |
| `app/models/__init__.py` | Add `Skillset`, `SkillsetMember` to `ALL_MODELS` (required for Beanie initialization) | Module list | Modify | Yes |
| `app/main.py` | Register `routers/skillsets.py` router with `app.include_router()` | App wiring | Modify | Yes |
| `services/skill.py` | Add `skillset_service.purge_for_skill(skill_id)` call inside `delete()` to cascade-remove membership rows | Cascade | Modify | Yes |

### Frontend

| Module | Responsibility | Status |
|---|---|---|
| `frontend/app/skillsets/page.tsx` | List all skillsets (cards: name, description, skill count, curator); persistent "+ Create Skillset" header button for authenticated users | New |
| `frontend/app/skillsets/[slug]/page.tsx` | Skillset detail: description, curator, copyable install command block, amber SLAC-only notice above skill list (if any internal), skill list in insertion order | New |
| `frontend/app/skillsets/create/page.tsx` | Create skillset form (name, slug auto-derive, description); `<AuthGuard>` fallback banner | New |
| `frontend/components/skillset-card.tsx` | Reusable skillset card component | New |
| `frontend/app/skills/[slug]/page.tsx` | Add "Part of N skillset(s)" section (hidden when count=0) | Modify |
| `frontend/components/skill-card.tsx` (or equivalent) | Add "in N skillsets" count as separate text line below description (when `skillset_count > 0`) | Modify |
| `frontend/types/skillset.ts` | TypeScript interfaces for `SkillsetOut`, `SkillsetListOut` | New |
| `frontend/types/skill.ts` | Add `skillset_count: number` and `skillsets: SkillsetRef[]` fields | Modify |

### AKH Skill

| Module | Responsibility | Status |
|---|---|---|
| `skill/SKILL.md` | Add `install skillset <slug>` sub-command | Modify |

---

## System Design

```
Browser / AKH skill
        │
        ├─ GET  /api/skillsets                    → list skillsets (paginated)
        ├─ POST /api/skillsets                    → create (auth required)
        ├─ GET  /api/skillsets/{slug}             → detail with member skill summaries
        ├─ PATCH /api/skillsets/{slug}            → update name/desc (owner or admin)
        ├─ DELETE /api/skillsets/{slug}           → delete (owner or admin)
        ├─ PUT  /api/skillsets/{slug}/skills/{skill_slug}    → add member (owner or admin)
        └─ DELETE /api/skillsets/{slug}/skills/{skill_slug} → remove member (owner or admin)

GET /api/skills/{slug}
  → SkillOut now includes:
      skillset_count: int
      skillsets: [{ slug, name }]   ← from SkillsetMember reverse lookup

GET /api/skills (list)
  → SkillListOut now includes:
      skillset_count: int           ← batch hydrated

AKH skill: install skillset <slug>
  1. GET /api/skillsets/{slug}          → member_slugs[]
  2. for each slug:
       GET /api/skills/{slug}           → repo_url, skill_path, pinned_commit_sha
       git-clone-to-temp(...)           → existing primitive
       copy-from-clone(...)             → existing primitive
       (skip if ~/.claude/skills/<slug>/ exists)
```

**Data model:**

```python
# models/skillset.py
_SKILLSET_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")  # mirrors _LABEL_NAME_RE

class Skillset(Document):
    slug: str                    # unique, URL-safe; validated by @field_validator below
    name: str                    # max_length=200
    description: str = ""        # max_length=2000
    created_by: str
    created_at: datetime
    updated_at: datetime
    member_count: int = 0        # denormalized

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
        ]

class SkillsetMember(Document):
    skillset_id: str             # stringified ObjectId — matches SkillLabel.label_id pattern (str, not PydanticObjectId)
    skill_id: str                # stringified ObjectId — matches SkillLabel.skill_id pattern
    skill_slug: str              # denormalized for fast reads (backs the AKH install loop)
    added_by: str
    added_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "skillset_members"
        indexes = [
            IndexModel([("skillset_id", ASCENDING), ("skill_id", ASCENDING)], unique=True),
            IndexModel([("skill_id", ASCENDING)]),   # reverse lookup
            IndexModel([("skill_slug", ASCENDING)]),
        ]
```

**API contract additions:**

```
GET /api/skillsets
  → { items: SkillsetListOut[], total, page, page_size }
  SkillsetListOut: { slug, name, description, created_by, member_count, created_at }

GET /api/skillsets/{slug}
  → SkillsetOut: { slug, name, description, created_by, member_count, created_at,
                   skills: [{ slug, name, description, labels, avg_rating, visibility }] }

POST /api/skillsets
  Body: { name, slug (optional, auto-derived), description }
  → SkillsetOut (201)
  → 409 Conflict if slug already taken (body: { detail, suggested_slug })

PATCH /api/skillsets/{slug}
  Body: { name?, description? }   ← slug is immutable and excluded from update
  → SkillsetOut (owner or admin)

PUT /api/skillsets/{slug}/skills/{skill_slug}
  → 204 No Content (owner or admin); rate-limited @limiter.limit("50/hour") matching labels pattern

DELETE /api/skillsets/{slug}/skills/{skill_slug}
  → 204 No Content (owner or admin)

DELETE /api/skillsets/{slug}
  → 204 No Content (owner or admin)
```

---

## Trade-offs

```
Choice: Denormalize member_count on Skillset (vs. live COUNT query)
  + Instant reads; consistent with Labels (usage_count)
  - Requires atomic inc/dec on add/remove; eventual inconsistency on crash mid-write
  Decision: Denormalize. Same pattern as labels. Crash risk is negligible at this scale.

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

**Slice 1 — Backend data model + CRUD API** (no frontend, no AKH change)
- `Skillset` + `SkillsetMember` models with indexes; use `str` (not `PydanticObjectId`) for FK fields to match `SkillLabel` pattern
- Register `Skillset`, `SkillsetMember` in `app/models/__init__.py` `ALL_MODELS`
- `services/skillset.py`: create, get, list, add_skill, remove_skill, batch_skillsets_for_skills, purge_for_skill
- `routers/skillsets.py`: all CRUD + membership endpoints (owner-or-admin checks on PATCH/DELETE)
- Register skillsets router in `app/main.py`
- Extend `SkillOut` / `SkillListOut` with `skillset_count` + `skillsets`; update `_skill_to_out()` to accept `skillsets` param — only `get_skill` handler fetches skillsets; all write handlers (`create`, `update`, `refetch`, `pin`, `add_platform`) pass `skillsets=[], skillset_count=0`
- `SkillCreate` gains optional `skillset_slug: str | None = None`; after successful skill insert, if `skillset_slug` is set and the submitter owns that skillset, call `skillset_service.add_skill()` — silently skipped if skillset not found or submitter is not owner (cross-ownership deferred to #029)
- Add `skillset_service.purge_for_skill(skill_id)` to `skill_service.delete()` cascade
- Update `routers/catalog.py` to batch-hydrate `skillset_count`
- Rate-limit `POST /api/skillsets` creation (e.g. `@limiter.limit("20/hour")`)
- Unit + integration tests

**Slice 2+3 — Frontend: skillset browse, detail, and create/manage** (shipped together — browse-only page without create CTA is a broken UX)
- `/skillsets` list page with "Skillsets" top-nav link
- `/skillsets/[slug]` detail page with copyable install command block
- Skill detail page: "Part of N skillset(s)" section (hidden when count=0)
- Skill card: "in N skillsets" line below description (when count > 0)
- Create skillset form (name, slug, description) wrapped in `<AuthGuard>` with same fallback banner as `skills/submit/page.tsx`
- Slug collision: inline error "Slug already taken. Try: <suggested-alternative>" with one-click accept
- Admin management is API-only in this version; `/admin/skillsets` page is deferred
- Add/remove existing catalog skills from skillset (on detail page, owner only)
- "Add new skill →" button on skillset detail page (owner only) — links to `/skills/submit?skillset=<slug>`; after submission redirects back to skillset detail
- Skill submit form (`/skills/submit`) reads optional `skillset` query param: if set and submitter owns that skillset, passes `skillset_slug` to the create endpoint; shows a subtle "Will be added to skillset: <name>" notice above the submit button
- Edit name/description (owner only)
- Delete skillset (owner or admin)

**Slice 4 — AKH skill: `install skillset <slug>`**
- New sub-command in `skill/SKILL.md`
- Fetches skillset detail, loops per-skill install, reports progress + skips
- Idempotent re-run

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `member_count` drifts from actual member rows | Low | Low | Periodic reconciliation script; count is cosmetic |
| Slug collision on auto-derive | Medium | Low | Validate uniqueness server-side; return 409 with suggested alternative |
| AKH install skillset hits GitHub rate limit mid-install | Low | Medium | Existing rate-limit handling in install primitive aborts and reports clearly |
| Admin delete cascade leaves orphan SkillsetMember rows | Low | Medium | Delete members in same request before deleting Skillset doc |
| Large skillsets (50+ skills) slow install | Low | Low | Sequential by design; user sees progress; no timeout risk |

---

## Definition of Done

- [ ] All acceptance criteria pass
- [ ] Unit tests: `Skillset` model, `skillset_service` (create, add, remove, batch hydration), slug validation
- [ ] Integration tests: all CRUD endpoints, membership add/remove, 403 on wrong-owner, skill detail includes skillsets
- [ ] Frontend: `/skillsets` and `/skillsets/[slug]` render correctly; skill detail shows reverse links; create form submits and handles slug collision; owner management actions (add/remove existing skills, edit, delete) work; `<AuthGuard>` fallback renders for unauthenticated users
- [ ] Frontend: "Add new skill →" button on skillset detail page (owner-only) links to `/skills/submit?skillset=<slug>`; submit form shows "Will be added to skillset: <name>" notice when `skillset` param is present and submitter owns it; after submission redirects to skillset detail page
- [ ] Backend: `SkillCreate.skillset_slug` adds new skill to owned skillset post-creation; silently ignored if skillset not found or not owned
- [ ] AKH skill: `install skillset <slug>` installs all members, skips installed, reports progress
- [ ] Security: non-owner cannot modify skillset (403 verified in tests)
- [ ] No N+1 queries on list views (batch hydration verified)
- [ ] CHANGELOG entry added (feature headline + bulleted technical details under `## Unreleased`)
- [ ] ADR files written to `docs/adr/` as `adr-u18-skillset-data-model.md`, `adr-u19-curator-permissions.md`, `adr-u20-akh-install-skillset.md`
- [ ] `README.md` updated with Skillsets feature paragraph and `/skillsets` link (add in Slice 2)
- [ ] `skill/SKILL.md` `install skillset <slug>` sub-command includes: progress line format (`[N/M] Installing <slug>... ✓` / `Skipping <slug> (already installed)`), empty-skillset message (`⚠ Skillset '<slug>' contains no skills.`), 404 error for unknown skillset slug, warning when a member skill is internal and user is unauthenticated

---

## Board Review

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

### Reviewer output

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

_None yet._

---

## References

_None yet._

---

## Test Plan

> Added by eng review (round 1). See full findings in `todo/review/006-skillsets/round-1-er.md`.

### Scope

```
Unit tests (pytest + mongomock)
  services/skillset.py — create, membership, batch hydration, permissions
Integration tests (ASGI + mongomock, AsyncClient)
  routers/skillsets.py — CRUD, membership, auth/403
  routers/skills.py additions — skillset_count + skillsets on detail + list
AKH skill — narrative tests (manual)
  install skillset: happy path, skip-installed, empty, unknown slug, partial-auth
```

### Unit: `TestSkillsetServiceCreate`

| # | Test | Expected |
|---|---|---|
| U1 | `create()` valid → `member_count=0`, `created_by` set | pass |
| U2 | slug auto-derived from name (`"My Skillset"` → `"my-skillset"`) | |
| U3 | duplicate slug raises `SkillsetAlreadyExistsError` with `suggested_slug` | |
| U4 | slug with spaces raises `ValueError` (validator) | |
| U5 | slug `"../etc"` raises `ValueError` | path traversal blocked |
| U6 | empty slug raises `ValueError` | |
| U7 | name > 200 chars raises `ValueError` | |

### Unit: `TestSkillsetServiceMembership`

| # | Test | Expected |
|---|---|---|
| M1 | `add_skill()` → member row created, `member_count=1` | AC-2 |
| M2 | `add_skill()` twice same skill → `SkillsetMemberAlreadyError` (409) | idempotent guard |
| M3 | `add_skill()` unknown slug → `SkillNotFoundError` (404) | |
| M4 | `remove_skill()` → member row removed, `member_count=0` | AC-3 |
| M5 | `remove_skill()` non-member → `SkillsetMemberNotFoundError` (404) | |
| M6 | `member_count` never below 0 | guard in service |
| M7 | `add_skill()` by non-owner raises `PermissionDeniedError` | AC-7 |
| M8 | Admin can `add_skill()` on any skillset | `is_admin=True` bypass |
| M9 | `purge_for_skill(skill_id)` removes all memberships for deleted skill, decrements `member_count` on affected skillsets | HIGH-1 fix |

### Unit: `TestSkillsetServiceBatchHydration`

| # | Test | Expected |
|---|---|---|
| B1 | `batch_skillsets_for_skills([id1, id2])` — 2 queries, no N+1 | NFR-3 |
| B2 | skill in 2 skillsets → `len(result[skill_id]) == 2` | |
| B3 | skill in 0 skillsets → `result[skill_id] == []` | |
| B4 | empty input → `{}` | mirrors labels pattern |

### Unit: `TestSkillsetServicePermissions`

| # | Test | Expected |
|---|---|---|
| P1 | `update()` by owner succeeds | |
| P2 | `update()` by non-owner raises `PermissionDeniedError` | |
| P3 | `update()` by admin succeeds | |
| P4 | `delete()` by owner removes skillset + all members | cascade verified |
| P5 | `delete()` by non-owner raises `PermissionDeniedError` | |

### Integration: `TestSkillsetsRouterCRUD`

| # | Test | Expected |
|---|---|---|
| I1 | `POST /api/skillsets` authenticated → 201 | AC-1 |
| I2 | `POST /api/skillsets` unauthenticated → 401 | |
| I3 | `POST /api/skillsets` duplicate slug → 409 + `suggested_slug` | |
| I4 | `GET /api/skillsets` → 200 paginated | FR-4 |
| I5 | `GET /api/skillsets/{slug}` → 200 with hydrated skills | AC-4 |
| I6 | `GET /api/skillsets/{slug}` unknown → 404 | |
| I7 | `PATCH /api/skillsets/{slug}` by owner → 200 | |
| I8 | `PATCH /api/skillsets/{slug}` by non-owner → 403 | AC-7 |
| I9 | `DELETE /api/skillsets/{slug}` by owner → 204 | |
| I10 | `DELETE /api/skillsets/{slug}` by admin → 204 | AC-8 |
| I11 | `DELETE /api/skillsets/{slug}` by non-owner → 403 | |

### Integration: `TestSkillsetsRouterMembership`

| # | Test | Expected |
|---|---|---|
| R1 | `PUT /api/skillsets/{slug}/skills/{skill_slug}` owner → 204, member_count=1 | AC-2 |
| R2 | `PUT` same skill twice → 409 | |
| R3 | `PUT` unknown skill_slug → 404 | |
| R4 | `DELETE /api/skillsets/{slug}/skills/{skill_slug}` owner → 204, member_count=0 | AC-3 |
| R5 | `DELETE` non-member → 404 | |
| R6 | `PUT` by non-owner → 403 | AC-7 |
| R7 | `DELETE` by non-owner → 403 | AC-7 |

### Integration: `TestSkillDetailIncludesSkillsets`

| # | Test | Expected |
|---|---|---|
| S1 | skill in 2 skillsets → `skillset_count=2`, `skillsets` list populated | AC-5 / FR-6 |
| S2 | skill in 0 skillsets → `skillset_count=0`, `skillsets=[]` | |
| S3 | list endpoint → each item has `skillset_count` (batch, no N+1) | FR-11 / NFR-3 |

### AKH skill narrative tests (manual)

- **Happy path:** 2-skill skillset, both uninstalled → `[1/2] Installing... [2/2] Installing...`
- **Skip already-installed:** 1 installed, 1 not → skip + install, correct counts
- **Empty skillset:** → `⚠ Skillset '<slug>' contains no skills.`
- **Unknown slug:** → `✗ Skillset not found.`
- **Partial auth failure:** 1 public + 1 internal (unauthenticated) → installs public, reports skip with login hint

### Coverage targets

| Module | Target |
|---|---|
| `services/skillset.py` | 90% |
| `routers/skillsets.py` | 85% |
| `routers/skills.py` additions | 80% |
| `models/skillset.py` validators | 100% |
