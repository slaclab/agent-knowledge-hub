# TODO #051 — Client Asks Before It Adds an MCP Server or an Agent, and Keeps Credentials Out of Them

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Problem Statement

`/agent-knowledge-hub install <slug>` (`skill/SKILL.md` › Install, step 4) writes every component a
skill's `plugin.json` lists: skill folders into `~/.claude/skills/<slug>/`, commands into
`~/.claude/commands/`, agent files into `~/.claude/agents/`, and MCP servers through
`claude mcp add <name> <command> [args...]`. It asks the user nothing beyond the install itself.

Two of those components act long after the install, in every later session of the account:

- **An MCP server added with `claude mcp add`** is either a `stdio` command that runs as the user,
  with every file the user can read in reach, or an `http` server. An `http` server added with a
  static `--header` puts that header, and any token in it, in `claude mcp add`'s arguments, where
  other users of a shared node can read it from `/proc/<pid>/cmdline`, and in `~/.claude.json`.
- **An agent file in `~/.claude/agents/`** may declare `mcpServers`, `hooks` and `permissionMode`,
  which Claude Code honours for agents in that folder, and hooks there run without a folder-trust
  check (Claude Code documentation, `sub-agents` and `hooks`).

The Cogito deployment (`slaclab/cogito`, TODO #200) carries this client in every session. It
measured Claude Code's managed controls on 2026-10-14 (#200, Open Question 1) and chose not to lock
MCP servers or agents deployment-wide: every lock that blocks the client's servers also disables
users' own `claude mcp add` servers and project `.mcp.json` files, and no managed setting limits
what an agent file declares without also stopping Cogito's own hooks. Cogito relies on this client
instead, and files this task as hub request H-7.

### What fails today

As of 2026-10-14:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A skill's `plugin.json` lists an MCP server | The client runs `claude mcp add` without asking | The client shows the server's name, transport and command or URL, and adds it only after the user agrees |
| A listed agent declares `hooks` or `mcpServers` | The client copies it into `~/.claude/agents/` without asking | The client shows what the agent declares, and writes it only after the user agrees |
| A listed `http` server needs the user's S3DF token | Nothing stops the token going into `--header` | The client never puts a credential in arguments or in `~/.claude.json`; it uses a headers helper or refuses |
| The user runs the install on one machine and uses another | The skill folder appears on every machine, because `~/.claude` is shared, but the server only on the first: `claude mcp add` with no `--scope` records it for the current project in that machine's `~/.claude.json` (measured by Cogito on Claude Code 2.1.281) | The client says where the server lands before adding it |

---

## Requirements

| ID | Requirement |
|---|---|
| FR-1 | Before it writes any agent file or adds any MCP server, the client lists each one and asks the user to confirm. For an MCP server it shows the name, the transport, and the command with its arguments or the URL. For an agent it shows the name and any `mcpServers`, `hooks`, `permissionMode` and `tools` it declares. It adds nothing of either kind without an explicit yes; a refusal still installs the skill folder and its commands, and says what was left out |
| FR-2 | The client never passes a credential in `claude mcp add`'s arguments, including `--header` and `-e`, and never writes one into `~/.claude.json`. An `http` server that needs the S3DF token is added with a `headersHelper` command that reads the token at request time, the way #050's helper reads it, or is refused with a message saying why |
| FR-3 | The client passes `--scope` explicitly and tells the user, before adding, where the server will apply: for `--scope user`, every project on this machine; for the default local scope, this project on this machine only. It says that the skill folder itself appears on every machine that shares `~/.claude` |
| FR-4 | `update` and `remove` list the MCP servers and agent files they will remove and ask the same way, and `remove` says when a server was added on another machine and cannot be removed from this one |
| FR-5 | Each confirmation is the client's own prompt to the user in the conversation, not a tool permission prompt, so it also appears in a session whose permission mode approves tools without asking |

## Acceptance criteria

- [ ] AC-1: Installing a test skill whose `plugin.json` lists one `stdio` server and one agent with `hooks` shows both, with their command and declarations, and adds neither when the user declines; the skill folder is installed.
- [ ] AC-2: With the user's agreement, the server is added with an explicit `--scope`, and the client's message names that scope.
- [ ] AC-3: A test `http` server that needs a bearer token is added with a `headersHelper`, or refused; `ps` during the add and `~/.claude.json` afterwards show no token.
- [ ] AC-4: `remove` lists the server and the agent before removing them.

## References

- [#050](050-client-token-helper.md) — the token helper FR-2 reuses for a `headersHelper`.
- [#006](006-skillsets.md) — skill sets; a set that bundles servers or agents installs through the same confirmation.
- Cogito `slaclab/cogito` TODO #200, Open Question 1, decided 2026-10-14: no managed MCP or agent lock; the client's own confirmation is the control. Cogito's slice 2 FAQ answer describes this behaviour.
