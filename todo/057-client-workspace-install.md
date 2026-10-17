# TODO #057 — The client installs into a workspace, installs exactly a confirmed list, and reaches the development catalog

> **Priority:** 🟡 P2 — Medium
> **Status:** 🏁 Implementation Done — client 2.4.0 on branch `feat/057-client-workspace-install`; three review rounds done and their findings fixed
> **Branch:** `feat/057-client-workspace-install`
> **PR:** —
> **Created:** 2026-10-16
> **Shipped:** —

---

## Provenance

**Raised by:** Cogito (`slaclab/cogito`) TODO #241, slice 1, 2026-10-16. Cogito's New session
dialog will list this catalog with the user's token, show exactly what will install, and have the
session's first turn install it into the project the session runs in, with this client. Cogito's
owner chose to build the client change in this repository.

**References:**

- [#006](006-skillsets.md) and its `install skillset`: the command this task's exact install follows
  for progress and recap lines.
- [#051](051-client-confirms-mcp-servers-and-agents.md): the server and agent rules a workspace
  install keeps.
- [#053](053-sec-skill-install-sha-checkout-verification.md): the pinned fetch every install still
  uses.
- [ADR-U42](../docs/adr/adr-u42-client-token-helper.md): the helper's fixed origin, which this task
  widens to the two catalog instances.

---

## Problem Statement

The client installs only into `~/.claude/`, so a skill reaches every session of the account in every
project. It cannot install exactly what a user confirmed elsewhere, because `install skillset` asks
its own question and nothing compares an entry with what the user saw. And it reaches only the
production catalog, which refuses the dex-dev tokens of Cogito's development servers.

## Goals

1. `--workspace` on `install`, `install skillset`, `list`, `update` and `remove`, with modes that
   carry no group or other write and the skill's folder kept out of git.
2. `install --exact`, which installs an item only when the catalog equals the confirmed list, and
   asks nothing.
3. `AKH_INSTANCE=dev` selects the development catalog and its token file, and nothing else does.

## Non-Goals

- A workspace scope for `rate`, `validate`, `create` or `submit`, which write nothing under
  `.claude/`.
- Changing what a user install does.

---

## Design

[ADR-U44](../docs/adr/adr-u44-client-workspace-install.md) records the decision and the rejected
alternatives. `skill/SKILL.md` § Workspace installs and § Install exactly what was confirmed hold
the client text and its fixed commands: `akh-workspace-base`, `akh-workspace-modes`,
`akh-workspace-exclude`, `akh-home-paths` and `akh-exact`. `akh-mcp-file` and
`akh-user-agent-names` take the base as `<base>`.

## Acceptance criteria

| ID | Given / when / then | Verified by |
|---|---|---|
| AC-1 | A workspace path with a character outside the allowed set, or `/`, is refused and nothing is made; otherwise the base and its `skills/` folder are made `0755` under umask 002, and existing folders keep their modes | `TestWorkspaceBase` in `backend/tests/test_client_install_rules.py` |
| AC-2 | After a workspace install, the skill's folders are `0755` and files `0644` or `0755`; a link is never followed; a `commands` or `agents` folder holding another file keeps its mode | `TestWorkspaceModes` |
| AC-3 | The skill's folder is excluded once, for a top-level, a subfolder and a worktree workspace, and the line goes on remove; outside git nothing is written | `TestWorkspaceExclude` |
| AC-4 | An exact list installs only items equal to the catalog: a changed repository, pin or missing entry, a skillset's version, members or a member's entry each install nothing from that item; a line outside the grammar refuses the list | `TestExactInstall` |
| AC-5 | In a workspace install, a server running a file from `${HOME}/.claude/skills/` gets no command, and other servers are written under the workspace | `TestMcpFileInAWorkspace` |
| AC-6 | `AKH_INSTANCE=dev` sends the development token to the development origin; any other value uses production; the production token never reaches the development origin | `TestInstance` in `backend/tests/test_hub_request_helper.py` |
| AC-7 | The client text names each workspace command form, the workspace server lines and the new lines, and the exact install asks nothing | `TestWorkspaceSection` |

## Implementation Checklist

- [x] The helper's development catalog, test-first (`6970624`)
- [x] Workspace installs and the exact install, test-first (`adc76ea`); four mutations of the new
  commands each failed their test
- [x] Client 2.4.0, `CHANGELOG.md`, `README.md`, ADR-U44
- [x] Code review and security review of the branch's diff, and their findings fixed (§ Problems & Solutions)
- [ ] Merged to `main` and pushed, so that Cogito's lock can name the commit

## Test results

`backend/tests/test_client_install_rules.py` and `backend/tests/test_hub_request_helper.py`: 458
passed on 2026-10-16, after the review fixes, against 360 before the branch. Each security fix was
broken in turn (the writable-folder refusal, the component check, the exclude file's no-follow open,
the normalised server check, `akh-mcp-file`'s umask) and each break failed a test.

## Problems & Solutions

### Problem: the reviews of the first version, 2026-10-16
**Encountered:** the code review and the security review of `6970624..de45bd7`
**Root cause and solution, one per finding, each with a test that failed before its fix:**

- **High, both reviews: file names from a skill reached a shell.** `akh-workspace-modes` took the
  manifest's command and agent entries as a quoted placeholder, so a file named with a `'` and a
  command substitution ran as the user (proven by both reviewers). The workspace commands now read
  the manifest themselves and take no placeholder with skill text, and the new `akh-component-check`
  refuses any command or agent path outside a safe character set before any command takes it, which
  also closes the same exposure in the agent checks of user installs on `main`.
- **Medium: the `--exact` list went through a here-document**, whose end marker a list line could
  hold, running the lines after it (proven). The model now writes the list with its file-writing
  tool, and runs `--exact` only for a list in the user's own message.
- **Medium: a window in which other accounts could edit a workspace install** under umask 002
  (proven for `.akh-mcp`). Composed writes start with `umask 022`, `akh-mcp-file` sets its own,
  `akh-workspace-modes` uses file descriptors without following links and reports a link or another
  account's file, after which the install is removed.
- **Medium and low: `.claude` checks.** The base command now refuses the home folder as a workspace,
  a `.claude/`, `skills/`, `commands/` or `agents/` that is a link, not a folder, or another
  account's, and one other accounts can write, each with its own line, and has a `find` mode that
  makes nothing for `list`, `update` and `remove`. It reports a `skills/` folder it made, since
  Claude Code reads it only from the next session. The exclude file is opened without following a
  link.
- **Medium: the workspace "Changed" line printed `--scope user`**, which would remove the home
  server. It has a workspace form.
- **Medium: commands and agents showed as untracked.** The exclude command now writes a line for each
  file the manifest lists, and removes them before `remove` deletes anything.
- **Medium: `install --exact` step 5 could not run**: it pointed at Install step 1, which needs a
  fresh directory. It now runs `akh-member-check` on the saved entry and Install from step 2.
- **Low:** destructive steps in Update and Remove spell `<base>`, and Remove checks each target stays
  under it; `akh-home-paths` matches `~`, `$HOME` and `${HOME}` spellings, not project paths, and
  reads the command and agent files too; nested command folders are tidied; the blanket reading rule
  names its exceptions; the server check normalises the path and covers `env` values; success lines
  name the development catalog.

**Kept, as a known cost:** an item confirmed with pin `none` installs its repository's current default
branch (ADR-U44 › Consequences).

### Problem: the re-review of the fixes, 2026-10-16
**Encountered:** a combined code and security re-review of `de45bd7..6c2423a`
**Root cause and solution, each with a test that failed before its fix:**

- **Medium: manifest entries still reached a shell** in Remove, Update and the foreign cleanup, which
  composed their deletes; a repository can commit a hostile manifest under `.claude/skills/`
  (proven). The fixed `akh-remove` reads the manifest and deletes only regular files whose real path
  lies inside the base, keeping and reporting every other entry; all three steps use it.
- **Medium: a path through a link copied any readable file** into the install, made world-readable by
  the modes step (proven with `sub -> /`). `akh-component-check` and the new `akh-copy-skill` refuse a
  path with a symbolic link in any part or one that resolves outside its root, and the modes step
  clears write bits only, never adding read.
- **Medium: the folder copy was composed by the model.** `akh-copy-skill` copies without a shell,
  leaves out links, special files and the reserved names, refuses an existing target, and runs the
  filesystem test.
- **Low:** the modes step stops at a skill folder that is a link (proven to walk it before); the base
  command checks all four folders before making any (proven to leave `skills/` behind); refusal lines
  read "Stopped:" and name all four folders; lines naming a command carry `--workspace`; Update runs
  the exclude removal; a non-UTF-8 exclude file keeps its bytes (proven to crash); `"$HOME"` is
  matched; a path part may not start with `-` or `.`.
- **Low, documented:** the workspace folder itself may be group-writable (ADR-U44 › Consequences).

The two client test files pass, 479 tests, after this round; dropping each new link check, the
remove rule or the write-only mode change fails a test.

### Problem: the third review, of the copy and remove commands, 2026-10-16
**Encountered:** a focused review of `06490d4`
**Root cause and solution, each with a test that failed before its fix:**

- **Medium: `akh-remove` took any slug**, so `remove ..` emptied the base, all of `~/.claude` for a
  home install, and `remove .` every skill (proven). Every fixed command that takes `<slug>` now
  refuses one outside `[a-z0-9-]{1,200}`, and Remove refuses it before asking for confirmation.
- **Medium: the plugin root was not anchored in the clone**, so a committed `.claude-plugin` link
  took commands, agents and server definitions from outside the pinned commit (proven).
  `akh-component-check` takes `<dir>` and refuses a root with a link on its path or outside the
  clone.
- **Medium: a failed copy left a half-written skill that loads**, and printed no line (proven for a
  missing parent folder, a tree deeper than Python's recursion limit, and a read error).
  `akh-copy-skill` makes the parent folder, walks without recursion, removes its partial copy on any
  error and prints `failed`, which has a line; its `check` step runs in Install step 2, so Update
  removes nothing for a skill path it would refuse.
- **Low:** manifests are read without following a link, as a regular file of at most 1 MiB, and
  type-checked, `akh-remove` keeping everything when it cannot read one (proven to read `/dev/zero`
  and to drop components silently); `akh-remove` walks each entry by file descriptor without following
  links, and the base command sets modes by file descriptor; the exclude file keeps its line endings
  (proven to rewrite them); a skill path of `/` leaves the clone's `.git` out; the existing-folder line
  has a label.

The two client test files pass, 499 tests, after this round. Two mutations first survived because a
second guard caught the test case; cases that reach each guard alone were added, and every guard of
this round now fails a test when removed.
