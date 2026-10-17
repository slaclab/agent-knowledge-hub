# TODO #058 — The exact install compares each skill's path, not only its repository and commit

> **Priority:** 🔵 P3 — Low
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-17
> **Shipped:** —

---

## Provenance

**Raised by:** the security review of Cogito (`slaclab/cogito`) TODO #241 slices 2 to 4, on
2026-10-17, rated low. Cogito's owner chose on 2026-10-17 to release #241 with the gap open and
track it here.

**References:**

- [#057](057-client-workspace-install.md) — dependency: this task extends the line format and the
  comparison that #057's `install --exact` introduced.

---

## Problem Statement

`install --exact` installs an item only while the catalog's entry equals the line the user
confirmed. A `skill` or `member` line carries the slug, `repo_url` and the pinned commit or `none`,
and `akh-exact`'s `why()` compares only those. The install also uses the entry's `skill_path`
(`akh-member-check`), which the line does not carry. Between the user's confirmation and the
install, the skill's submitter can change `skill_path` to another folder of the same commit, and
the install goes ahead with it. A skill pinned to `none` installs whatever its default branch holds
at install time, which the confirmation cannot fix either.

Cogito's New session dialog marks an unpinned skill in its confirmation list, so the second case is
visible to the user. The first is not.

## Goals

- A changed `skill_path` stops the item, as a changed `repo_url` or pin does.
- Cogito's dialog shows each skill's path in its confirmation list and writes it into the line.

## Non-Goals

- Requiring a pin for `install --exact`. That would refuse every unpinned catalog skill.

## Design

Not yet drafted. The line format gains a field, so the client and Cogito's
`web/src/shell/sessionSettings/hubCatalog.ts` change together, and an image whose lock pins the old
client keeps the old format.
