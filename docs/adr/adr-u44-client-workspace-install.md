# ADR-U44: The client installs into a workspace, installs exactly a confirmed list, and reaches the development catalog

**Status:** Accepted
**Date:** 2026-10-16
**Context:** todo/057-client-workspace-install.md

## Context

The client installed every skill into `~/.claude/`, so a skill reached every session of the account
in every project. The Cogito deployment wants a user to add catalog skills to one project from its
New session dialog (Cogito TODO #241): the dialog lists the catalog with the user's token, shows
exactly what will install, and the session's first turn installs it. Three facts shape the client
side:

- Claude Code reads a project's skills from `.claude/skills/` in the folder a session runs in and
  its parents up to the repository root. A skill added there mid-session loads at the next turn only
  when that folder existed when Claude Code started (Claude Code 2.1.281, measured 2026-10-16).
- A skillset's members can change after a user looked at it: its owner or an admin adds, removes
  and reorders them, and a member's submitter can remove it. Each change increments the skillset's
  `version`.
- A question asked in the session's first turn would take the user's next message, sent by the
  dialog, as its answer.

The helper sent requests only to the production catalog, with no override, because anything that
could change the origin could be set by text the model was steered by (ADR-U42). Cogito's
development servers use dex-dev tokens, which only the development catalog accepts.

## Decision

- **`--workspace`.** `install`, `install skillset`, `list`, `update` and `remove` take it, and then
  work on `<workspace>/.claude/`, the base, in place of `~/.claude/`. A fixed command refuses a
  workspace path with a character other than letters, digits, `.`, `_`, `-` and `/`, so that every
  command can carry the base unchanged, and makes the base and its `skills/` folder with mode
  `0755`. After an install, a fixed command sets the skill's folders to `0755` and files to `0644`,
  or `0755` where executable, never following a link, and another adds the skill's folder to the
  file `git rev-parse --git-path info/exclude` names, which is local to the clone and never
  committed. A workspace agent may not take the name of an agent in the user's own folder, which it
  would replace. A server's printed command adds it with `--scope local`, and a server that runs a
  file from `${HOME}/.claude/skills/` gets no command, since a workspace install does not create
  that folder.
- **`install --exact`.** The command reads a list of `skill`, `skillset` and `member` lines, each
  with the repository and pinned commit the user saw, or the skillset's `version`. A fixed command
  compares the list with the catalog entries the helper fetched, and an item installs only when
  they are equal; for a skillset, its version, its member order and every member's entry. A changed
  item installs nothing and is reported. The command asks nothing. It saves each entry once and
  installs from that saved copy, so the entry compared is the entry installed.
- **`AKH_INSTANCE=dev`.** The helper sends to the development catalog with `.s3df-dev-access-token`
  when that variable is exactly `dev`, and otherwise to production with `.s3df-access-token`. Each
  origin is fixed in the helper and takes its own token file.

## Rejected alternatives

| Rejected | Fact that rules it out |
|---|---|
| Keep `install skillset`'s question for the dialog's installs | The dialog sends the user's message next, which would become the answer |
| Compare only the skillset's `version` | A member's own entry, its repository or pin, changes without changing the skillset's version |
| Re-fetch each entry at install time after the comparison | The entry could change between the two fetches, so what installs could differ from what was compared |
| An origin taken from a variable's value | Text the model was steered by could then send a token to any host (ADR-U42) |
| Pass the development token to the production origin, or the reverse | Each catalog accepts only its own issuer's tokens, and a token must never reach the other instance |
| Add the workspace folder to the repository's `.gitignore` | That edits a tracked file, which the user would then commit or revert |

## Consequences

- A steered model that set `AKH_INSTANCE=dev`, against the rule that the helper runs with no
  environment assignment, could make a production session read the development catalog, sending it
  the development token only. It cannot send the production token anywhere new.
- A skill whose text names `~/.claude/skills/<slug>/` works only in part from a workspace install;
  the closing message says which files name it.
- A workspace install's files sit in the user's working tree. Anyone who can write that tree could
  change them, as they could already change the tree's code.
