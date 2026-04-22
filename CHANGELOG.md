# Changelog

## v0.3.0 — 2026-04-22

### Skill ratings (#005)

Authenticated users can now rate any skill 1–5 stars from the detail page.

- **Interactive star picker** — authenticated users see a clickable 5-star picker on the skill detail page. Stars highlight on hover; keyboard navigation (Tab, Enter/Space) and `aria-label` attributes are included for accessibility.
- **Optimistic update** — the picker and average update instantly on click; reverts cleanly if the API call fails with an inline error message.
- **Upsert semantics** — re-rating a skill updates your previous vote rather than creating a duplicate. One rating per user per skill, enforced via a unique MongoDB index.
- **Your prior rating pre-filled** — when you revisit a skill you've already rated, your previous star choice is shown in the picker after a client-side fetch.
- **Read-only view for guests** — unauthenticated visitors see the current average and count with a "Sign in to rate." prompt.

## v0.2.0 — 2026-04-22

### Label UX: community tagging, filter, and admin tools (#003)

You can now tag any skill with free-form labels — and use those labels to find skills by topic.

- **Add labels to skills** — authenticated users can apply community labels (e.g. `python`, `data-viz`) to any skill from the detail page. A compact typeahead combobox suggests existing labels as you type to avoid duplicates.
- **Remove your own labels** — made a mistake? Remove any label you personally applied with one click.
- **Label chips on cards** — up to 5 label chips appear on each skill card in the list view; click any chip to filter to skills sharing that label.
- **Filter by label** — multi-select label filter in the skill list controls bar; AND semantics (skill must carry all selected labels); reflected in the URL so filtered views are shareable.
- **Browse all labels** — new `/labels` page lists every label with usage counts; click through to the filtered skill list.
- **Admin label management** — admins can rename, merge, and delete labels globally at `/admin/labels`. Rename updates all skills atomically; merge consolidates duplicates; delete removes the label from every skill. All operations wrapped in MongoDB transactions.

### Auth header hardening (#008)

- Internal API secret (`INTERNAL_API_SECRET`) required for Next.js → backend trust; `X-Forwarded-User` is only accepted after the secret check passes.
- Three new ADRs documenting the ingress header stripping decision, shared-secret choice over mTLS, and removal of bare forwarded-user fallback.
- k8s network policy added to all overlays restricting backend ingress to frontend pods only.

## v0.1.0 — initial release

- Skill catalog: browse, search, submit, edit, delete
- GitHub metadata auto-fetch at submission with manual re-fetch
- Revision history timeline on skill detail pages
- Private/internal GitHub repo support via GitHub App
- SLAC VouchProxy authentication
