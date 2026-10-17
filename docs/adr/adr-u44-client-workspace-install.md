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
- **Checked component paths.** A fixed command lists the command and agent files `plugin.json`
  names and refuses any path outside letters, digits, `.`, `_`, `-` and `/`, or with a `.` or `..`
  part, before any command takes one. The same check closes that exposure for user installs, whose
  agent checks took agent paths unchecked. The workspace commands take no placeholder that carries
  text from a skill; they read the manifest themselves.
- **Fixed commands copy and delete.** The skill folder is copied, and `remove`, `update` and a
  failed install delete files, with fixed commands that read the manifest and the clone themselves,
  never follow a link, and delete only regular files whose real path lies inside the base.
- **No window for other accounts.** Commands the model composes to write under a workspace base start
  with `umask 022`, `akh-mcp-file` sets its own umask, and the base command refuses a `.claude/`
  folder that is a link, belongs to another account or that other accounts can write, and the home
  folder as a workspace. The modes command opens every path without following links and reports a
  link or another account's file, and the install is then removed.
- **The list is never shell input.** The model writes the exact list with its file-writing tool, and
  runs `install --exact` only for a list in the user's own message.
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
  environment assignment, or any session environment that sets it, such as a workspace's
  `.claude/settings.json`, makes a session read the development catalog, sending it the development
  token only, and install that catalog's content. It cannot send the production token anywhere new.
  Success lines name the development catalog when it is in use.
- "Exactly what was confirmed" holds fully only for a pinned item. An item confirmed with pin `none`
  installs whatever its repository's default branch holds at install time, as a plain install of an
  unpinned skill does; a dialog that offers such items has to say so.
- A skill whose text names `~/.claude/skills/<slug>/` works only in part from a workspace install;
  the closing message says which files name it.
- A workspace install's files sit in the user's working tree. Anyone who can write that tree, a
  group project folder of mode 2775 among them, could change or replace them, as they could already
  change the tree's code and project settings; the client checks the `.claude/` folders, not the
  workspace itself.
