# TODO #057 — The client installs into a workspace, installs exactly a confirmed list, and reaches the development catalog

> **Priority:** 🟡 P2 — Medium
> **Status:** 🏁 Implementation Done — client 2.4.0 on branch `feat/057-client-workspace-install`, reviews pending
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
- [ ] Code review and security review of the branch's diff, and their findings fixed
- [ ] Merged to `main` and pushed, so that Cogito's lock can name the commit

## Test results

`backend/tests/test_client_install_rules.py` and `backend/tests/test_hub_request_helper.py`: 421
passed on 2026-10-16, against 360 before the branch.
