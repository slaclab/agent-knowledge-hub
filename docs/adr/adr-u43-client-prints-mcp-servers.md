# ADR-U43: The client prints MCP servers for the user to add, and writes agents only within a fixed key set

**Status:** Accepted
**Date:** 2026-10-15
**Context:** todo/051-client-confirms-mcp-servers-and-agents.md

## Context

`/agent-knowledge-hub install <slug>` wrote every component a skill's `plugin.json` listed. It added each MCP server with `claude mcp add` and copied each agent file into `~/.claude/agents/`, asking the user nothing beyond the install itself. Any signed-in user can submit a skill, so the author of that configuration can be any signed-in user.

Three routes let what an install writes act in every later session of the account:

- An MCP server runs a program as the user, or connects to a URL. Claude Code fills each `${VAR}` in its configuration from its own environment, so a header such as `Authorization: Bearer ${GITHUB_TOKEN}` sends that value to the author's URL.
- An agent file in `~/.claude/agents/` may declare `hooks`, `mcpServers` and `permissionMode`. Claude Code honours all three for agents in that folder without a folder-trust check, and ignores them for an agent that a plugin brings.
- A skill folder that carries `.claude-plugin/plugin.json` loads, once it is under `~/.claude/skills/`, as the plugin `<name>@skills-dir`, with the servers and hooks its manifest declares. Claude Code asks nothing first.

The Cogito deployment loads this client in every session and does not lock MCP servers or agents deployment-wide, because every such lock also disables users' own servers. It relies on this client instead (Cogito TODO #200, request H-7).

The first design asked the user before the client added each server and agent. Its board review ended UNSTABLE after three rounds: each round found configuration that acted despite the question, because the only gate was text the model is told to follow.

## Decision

- **Servers are printed, not added.** The client runs no `claude mcp` command on its own. For each server, a fixed Python command in `skill/SKILL.md` builds the configuration Claude Code takes from `plugin.json`, writes it as JSON with every non-ASCII character escaped to `~/.claude/skills/<slug>/.akh-mcp/<name>.json`, reads it back, and prints the configuration's lines already escaped. The client prints a block with those lines, plain-language warnings, and the command `claude mcp add-json --scope user <name> "$(cat …)"`. The user runs that command, or asks Claude to run it by name in a later message; Claude then runs it exactly as printed. A server whose name, transport, value types, `~` or `$` paths, or size the client cannot show safely gets no command, only a line with the reason. The model never retypes a configuration value: in the hand-run checks on 2026-10-16, when it wrote the file itself, it turned a header's U+2028 into a space in 2 of 4 installs, and its read-back compared the file with its own copy. The command needs `python3`, which the Cogito image and RHEL 8 S3DF nodes both have; without it, a server gets no command.
- **Agents by allow-list.** The client writes an agent file only when every frontmatter key is one of `name`, `description`, `tools`, `disallowedTools`, `model` and `color`, and its `name` is not a built-in agent's name or the name of an agent the user already has. Fixed `awk` commands in `SKILL.md` read the keys and the name from the clone, so the file's length and wording cannot change the result. `grep` is not used, because it prints nothing for a file that holds a NUL byte.
- **No plugin manifest, no foreign install manifest.** The folder copy leaves out `.claude-plugin/`, `.installed-manifest.json`, `.akh-mcp/` and every symbolic link, and a filesystem test after the copy stops the install if any of the three names exists.
- **No new question.** The install asks nothing it did not ask before, so `install skillset` stays unattended after its one confirmation (#006).

## Trade-offs

| Decision | Gains | Costs | Accepted because |
|---|---|---|---|
| Never add an MCP server | No author-controlled server reaches the user's configuration through the client | A skill that needs a server takes one extra step by the user | The user sees the full configuration and the warnings before choosing |
| Agent keys by allow-list | A key that a later Claude Code release adds cannot be written unseen; `hooks`, `mcpServers` and `permissionMode` are refused | An agent with a harmless key outside the set, for example `memory`, is refused | The closing message links the file, and the user can copy it by hand |
| Ask no new question | `install skillset` stays unattended; nothing depends on the model reproducing a prompt | Plain agents are written without a question | A plain agent carries a prompt and a tool list, the same trust as the skill the user asked for |

## Rejected alternatives

| Alternative | Fact that rules it out |
|---|---|
| Ask before adding each server and agent | Three review rounds kept finding configuration that acted despite the question |
| Install through Claude Code's `/plugin` system | Claude Code only; Codex and OpenCode have no such route, and #046 and #047 are not built |
| A `headersHelper` that supplies the S3DF token to a server | No catalog skill names a SLAC endpoint for its origin list; deferred |
| Claude declines to run a printed command even when the user asks | A Cogito session may offer neither `!` nor a terminal, which would leave its users no way to add a server; and with no rule for the request the model would compose a command from the block's values |

## Consequences

- A skill whose `SKILL.md` itself runs `claude mcp add-json` or writes into `~/.claude/agents/` when invoked is not stopped. Its commands and `SKILL.md` carry the same trust as installing the skill.
- A server an earlier client added stays at local scope for the directory the install ran in. `remove` and the first `update` print `claude mcp remove --scope local <name>` for it and run nothing.
- A plugin install keeps the earlier client, which still adds servers without asking, until the user updates the plugin.
- The client cannot pass the S3DF token to an MCP server; a server marked `auth.type: slac-sso` gets its block without a command.
