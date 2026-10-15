# TODO #051 — Client Leaves MCP Servers to the User and Refuses Agents It Cannot Vet

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open (narrowed 2026-10-15 after an UNSTABLE board review; fresh review pending)
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Provenance

**Raised by:** Cogito (`slaclab/cogito`) TODO #200, hub request H-7, 2026-10-14, after Cogito's Open Question 1 left the control over MCP servers and agents to this client.

**Revised:** 2026-10-15. The first design asked the user before the client added each MCP server and agent. Its board review ended UNSTABLE after three rounds: every round found another way configuration written by a skill's author could harm the user despite the question (§ Board Review). The user chose to narrow the task so that the client never adds an MCP server and never writes an agent that declares anything beyond a fixed set of keys. The first design's text is in git history at commit `48f3b9c`.

**References:** Relationship to Other Tasks gives each related task and why it matters.

---

## Problem Statement

`/agent-knowledge-hub install <slug>` (`skill/SKILL.md` › Install, step 4) writes every component a skill's `plugin.json` lists: skill folders into `~/.claude/skills/<slug>/`, commands into `~/.claude/commands/`, agent files into `~/.claude/agents/`, and MCP servers through `claude mcp add <name> <command> [args...]`. It asks the user nothing beyond the install itself. Any signed-in user can submit a skill, so the author of that configuration is any signed-in user.

Three routes let what an install writes act long after the install, in every later session of the account:

- **An MCP server added with `claude mcp add`** is either a `stdio` command that runs as the user, with every file the user can read in reach, or an `http` server. A `${VAR}` in its configuration is filled from Claude Code's environment each time the server starts or connects, so a header such as `Authorization: Bearer ${GITHUB_TOKEN}` sends that value to the author's URL (Measured facts › `${VAR}` references). A static `--header` puts the header, and any token in it, in `claude mcp add`'s arguments and in `~/.claude.json`.
- **An agent file in `~/.claude/agents/`** may declare `mcpServers`, `hooks` and `permissionMode`, which Claude Code honours for agents in that folder; hooks there run, and inline `mcpServers` there connect, without a folder-trust check, and an `http` hook can send environment values to its URL (Claude Code documentation, `sub-agents` and `hooks`). Claude Code ignores all three fields for an agent that a plugin brings.
- **A skill folder that carries `.claude-plugin/plugin.json`**, once copied into `~/.claude/skills/<slug>/`, loads in every later session as the plugin `<name>@skills-dir`, with the MCP servers and hooks its manifest, `.mcp.json` and `hooks/hooks.json` declare. Claude Code asks nothing first for a plugin under `~/.claude/skills/` (Claude Code documentation, `plugins/loading`; `claude plugin init --help` on 2.1.281).

The Cogito deployment (`slaclab/cogito`, TODO #200) carries this client in every session and chose not to lock MCP servers or agents deployment-wide, because every lock that blocks the client's servers also disables users' own servers and project `.mcp.json` files. Cogito relies on this client instead, and files this task as hub request H-7.

### What fails today

As of 2026-10-14:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A skill's `plugin.json` lists an MCP server | The client runs `claude mcp add` without asking | The client adds no server. It shows the server's configuration with plain-language warnings and the command that would add it, and the user decides (FR-1) |
| A listed agent declares `hooks`, `mcpServers`, `permissionMode`, or any other key outside a fixed set | The client copies it into `~/.claude/agents/` without asking | The client does not write it, names the keys, and links the file so the user can read it (FR-2) |
| A listed `http` server needs the user's S3DF token | Nothing stops the token going into `--header` | The client writes no credential anywhere and says the server needs a sign-in the client cannot provide (FR-1) |
| A skill folder carries `.claude-plugin/plugin.json` with `mcpServers` or `hooks` | Claude Code loads the copied folder as a plugin with those servers and hooks, unasked | The client copies no plugin manifest into `~/.claude/skills/<slug>/` (FR-3) |

---

## Goals

1. The client never adds, changes, or removes an MCP server. The user adds one, if at all, after reading its configuration.
2. The client writes an agent file only when every frontmatter key it declares is in FR-2's set.
3. The client writes no plugin manifest and no install manifest taken from the skill's own files.
4. The install asks no new question, so `install skillset` stays unattended after its one confirmation (#006 › FR-7).

## Non-Goals

- Commands in `~/.claude/commands/` and the skill's own `SKILL.md`, including their `allowed-tools` and `hooks` frontmatter. They carry the same trust as installing the skill, which the user asked for.
- Supplying the S3DF token to an MCP server (Follow-ups).
- The forms Codex and OpenCode need for a server's configuration (Follow-ups).
- Installing through Claude Code's `/plugin` system (#046, #047).
- Removing servers that an earlier version of this client added. `remove` prints the command; it runs nothing.

---

## Requirements

Where: `skill/SKILL.md` › Install, step 4 (FR-1 to FR-3), step 5 and the success line (FR-4, FR-5), and › Update and › Remove (FR-5).

| ID | Requirement |
|---|---|
| FR-1 | **MCP servers.** The client runs no `claude mcp` command at any point. For each entry in the skill's `plugin.json` `mcp-servers` list it does the following. (a) If the entry's `name` does not match `^[A-Za-z0-9][A-Za-z0-9_-]*$`, the server is not shown with a command, and the closing message names it with that reason; a name such as `-sproject` or `$(touch x)` therefore never appears in a command. (b) Otherwise it builds the configuration Claude Code takes: `type` from `transport` (`stdio`, `http` or `sse`); for `stdio`, `command`, `args` (`[]` when absent) and `env`; for `http` and `sse`, `url` and `headers`. Other fields are left out and named. A `transport` outside those three, an `args` that is not a list of strings, or an `env` or `headers` that is not a map of strings to strings leaves the server without a command, with the reason, because `claude mcp add-json` refuses such a configuration (Measured facts › `claude mcp add-json`). (c) It writes the configuration as JSON to `~/.claude/skills/<slug>/.akh-mcp/<name>.json` with its file-writing tool, never through a shell `echo`. (d) After the closing message it prints one block per server in the words of § Server block. (e) An entry whose `auth.type` is `slac-sso` gets its block without a command, and the block says the server needs an S3DF sign-in the client cannot pass to an MCP server. |
| FR-2 | **Agents.** The client reads each listed agent file's frontmatter from the clone. It writes the file to `~/.claude/agents/` only if every key is one of `name`, `description`, `tools`, `disallowedTools`, `model` and `color`, and only if no file of that name exists there that this skill's manifest does not record. Otherwise it does not write the file, and the closing message names the agent, the keys outside the set or the clash, and the file's address in the repository at the installed commit (`<repo_url>/blob/<commit>/<path>`). Frontmatter the client cannot parse counts as outside the set. A set of allowed keys, not a list of refused ones, keeps a key that a later Claude Code release adds from being written unseen. An agent with no `tools` key gets every tool the session has, which the closing message says. |
| FR-3 | **Folder copy.** Copying the skill folder into `~/.claude/skills/<slug>/` leaves out `.claude-plugin/`, `.installed-manifest.json` and `.akh-mcp/` from the source, and the closing message names any it left out. The first stops the copied folder from loading as a plugin; the second and third stop the skill's own files from standing in for what the client records (FR-5) or prints (FR-1). |
| FR-4 | **Closing message.** The success line is followed by: the agents written, each with its `tools` or "every tool"; the agents and servers left out, each with its reason; and then the FR-1 blocks. Values from the skill's files are shown with control characters and Unicode line separators, paragraph separators and format characters (categories Zl, Zp, Cf) written as `\uXXXX`, so a value cannot add lines or reorder what is shown. |
| FR-5 | **Manifest, update, remove.** `.installed-manifest.json` records the agent files the install wrote and the server names it printed a block for. `remove` deletes the recorded agent files and the skill folder, and for each recorded server name prints `claude mcp remove --scope user <name>`, saying the user added it themselves and can remove it with that command; it runs no `claude mcp` command. `update` keeps today's order (remove, then install) and, before it overwrites a server's `.akh-mcp/<name>.json`, compares the old file with the new configuration as parsed JSON; a block whose configuration changed says so, so a user who added that server knows to review it again. |

---

## Server block

The block FR-1 prints for each server, with `<…>` filled from the configuration and each line after the first present only when it applies:

```
MCP server "<name>" (<stdio | http | sse>) — not added
  Runs: <command> <args…>                    (stdio)
  Connects to: <url>                         (http, sse)
  env <KEY>=<value>  /  header <Name>: <value>   (one line each, in full)
  Warning: this runs a program as you, with access to every file you can read.   (stdio)
  Warning: ${<VAR>} is filled from your environment and sent to this server.     (any ${…})
  Warning: <npx | uvx | pipx> downloads and runs code each time the server starts.
  Warning: runs inline shell code (sh -c, bash -c, python -c).
  Warning: <~/… | $VAR/…> is not expanded by Claude Code and is read from the directory the session starts in.
  Runs <path> from this skill's folder.      (a ${HOME}/.claude/skills/<slug>/… path)
  Changed since the last install of <slug>.  (update, FR-5)
  This server needs your S3DF sign-in, which this client cannot pass to an MCP server yet, so it is not added.   (auth.type slac-sso; no command line follows)
  To add it yourself after reviewing the above:
    claude mcp add-json --scope user <name> "$(cat ~/.claude/skills/<slug>/.akh-mcp/<name>.json)"
  With --scope user it applies in every project <on this machine (Cogito) | on every S3DF machine that shares your home>.
```

The command reads the configuration from the file FR-1 wrote, so no value from the skill's author is parsed by the shell: a command substitution's output is not expanded again (Measured facts › Command substitution). The scope line follows Measured facts › `$HOME` and `~/.claude` in a Cogito session and › `~/.claude.json` outside Cogito.

---

## Design

### Why print, not add

The first design added a server or agent after a question the model showed (§ Board Review). Each review round found configuration that acted despite the question, because the client was copying author-controlled configuration into the user's account and the only gate was text the model is told to follow. Printing the configuration and the command moves the decision to the user, who acts outside the client; the client then needs no clash checks, staging directory, manifest of server configurations, or prompt that the model must reproduce exactly. A refusal by key set, for agents, fails closed where a question would rely on the model's summary.

### Trade-offs

| Decision | Gains | Costs | Accepted because |
|---|---|---|---|
| Never add an MCP server | No author-controlled server reaches the user's configuration through the client | A skill that needs a server takes one extra step by the user | The user sees the full configuration and the warnings before choosing |
| Agent keys by allow-list | A new Claude Code key cannot be written unseen; `hooks`, `mcpServers` and `permissionMode` are refused | An agent with a harmless key outside the set (for example `skills` or `memory`) is refused | The closing message links the file, and the user can copy it by hand |
| Ask no new question | `install skillset` stays unattended (#006); nothing depends on the model reproducing a prompt | Plain agents are written without a question | A plain agent carries a prompt and a tool list, the same trust as the skill the user asked for |

### Rejected alternatives

| Alternative | Fact that rules it out |
|---|---|
| Ask before adding each server and agent (the first design) | Three review rounds kept finding configuration that acted despite the question (§ Board Review) |
| Install through Claude Code's `/plugin` system | Claude Code only; Codex and OpenCode have no such route, and #046 and #047 are not built (Follow-ups) |
| A `headersHelper` that supplies the S3DF token | No catalog skill names a SLAC endpoint for its origin list; deferred (Follow-ups) |

---

## Measured facts — measured 2026-10-14 and 2026-10-15 on `sdfiana008`, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| Claude Code version | 2.1.281 | `claude --version` |
| `claude mcp add-json` | Takes `<name> <json>` and `--scope` (`local`, `user` or `project`; default `local`). It refuses, with `Invalid configuration: : Invalid input` and exit 1, a configuration that has a `url` and no `type`, one that names the transport as `transport`, and one whose `env` value is an object. It stores a stdio configuration with no `args` with `"args": []` added and its top-level keys reordered. It refuses a name that already exists at that scope | `claude mcp add-json --help`; `add-json -s user` probes with `HOME` and `CLAUDE_CONFIG_DIR` set to a scratch directory, then reading that directory's `.claude.json` |
| `${VAR}` references | Claude Code stores a `${VAR}` in a stdio server's `env` or `args` or an `http` server's `headers` unexpanded, and expands it from its own environment when it starts or connects the server: a local listener received the expanded header value. A stdio server also inherits Claude Code's whole environment | Same scratch setup, with `PROBE_SECRET=<value> claude mcp get <name>` |
| `~` and `$VAR` in a stdio server | Claude Code expands only `${VAR}`. `command` `~/tilde.sh` fails with `ENOENT: no such file or directory, posix_spawn '~/tilde.sh'`, while `${HOME}/brace.sh` runs. An unexpanded `~/…` is a path relative to the directory `claude` runs in | Same scratch setup |
| Command substitution | `"$(cat <file>)"` passes the file's content as one argument without expanding a `$(…)` or `'` inside it, in bash and zsh | Measured in the first design's review, round 2 |
| `$HOME` and `~/.claude` in a Cogito session | `$HOME` is a per-machine directory, so `~/.claude.json` is per machine; `~/.claude` is a symlink to the real home's `.claude`, so skill folders and agent files are shared | `ls -ld ~/.claude` gave `/sdf/home/y/ytl/.cogito/hosts/sdfiana008/.claude -> /sdf/home/y/ytl/.claude` |
| `~/.claude.json` outside Cogito | The real home holds its own `.claude.json` on the `sdfhome/home` network filesystem | `ls -l /sdf/home/y/ytl/.claude.json`; `df -h /sdf/home/y/ytl` gave `sdfhome/home` |

---

## Acceptance criteria

The fixture is § Test Plan › Fixture; each run uses a throwaway `HOME`.

- [ ] AC-1: Installing the fixture adds no MCP server: the throwaway `.claude.json` has no `mcpServers` entry at any level afterwards, and the client ran no `claude mcp` command.
- [ ] AC-2: Each fixture server with a valid name and valid values has `~/.claude/skills/<slug>/.akh-mcp/<name>.json` and a printed block with its warning lines and the command; `-sproject`, `akh-bad-env` and `akh-sso` have no command line, each with its reason.
- [ ] AC-3: Running the printed command for `akh-stdio` adds it at user scope, and `claude mcp get akh-stdio` exits 0.
- [ ] AC-4: `agent-hooks`, `agent-servers` and `agent-memory` are not written, and the closing message names each one's keys and repository address; `agent-plain` is written, with "every tool" shown.
- [ ] AC-5: `~/.claude/skills/<slug>/` holds no `.claude-plugin/`, no `.installed-manifest.json` from the source, and no `.akh-mcp/` file the client did not write; `claude plugin list` in a new session shows no `<name>@skills-dir` row for it.
- [ ] AC-6: A pre-existing `~/.claude/agents/agent-plain.md` that the manifest does not record is unchanged after the install, and the closing message names the clash.
- [ ] AC-7: After AC-3, `remove` deletes `agent-plain`, leaves `akh-stdio` in `.claude.json`, and prints `claude mcp remove --scope user akh-stdio`.
- [ ] AC-8: `update` from a fixture commit whose `akh-stdio` `args` differ prints that block with "Changed since the last install".
- [ ] AC-9: A header value holding a newline and a U+2028 character prints as `\n` and ` `.

---

## Implementation Plan

1. **Re-derive Measured facts** with `HOME` and `CLAUDE_CONFIG_DIR` set to a scratch directory. A changed result changes FR-1 before anything is written.
2. **`skill/SKILL.md` › Install.** Step 4's `skills` line states FR-3; its `agents` line states FR-2; its `mcp-servers` line states FR-1 and points to the § Server block wording, which goes into `SKILL.md` verbatim. Step 5 states FR-5's manifest records. The success line states FR-4.
3. **`skill/SKILL.md` › Update and › Remove** per FR-5.
4. **`skill/SKILL.md` › Error handling** gains the FR-1 and FR-2 reasons.
5. **Fixture and checks** per § Test Plan.

---

## Definition of Done

- [ ] AC-1 to AC-9 checked and recorded with the Claude Code version used
- [ ] `skill/SKILL.md` › Install, Update, Remove and Error handling carry FR-1 to FR-5 and § Server block; no line of `SKILL.md` tells the model to run `claude mcp add` or `claude mcp add-json`, and the only `add-json` text is inside the Server block the client prints
- [ ] `frontend/app/guides/agent-knowledge-hub/page.tsx`, `frontend/app/guides/why-agent-knowledge-hub/page.tsx`, `docs/why-agent-knowledge-hub.md` and `README.md` no longer say install registers MCP servers; they say the client shows each server's configuration and the command, and leaves adding it to the user
- [ ] `frontend/app/guides/create-a-skill/page.tsx` states FR-2's agent key set, that servers are shown rather than added, and that a script in the installed folder is named as `${HOME}/.claude/skills/<slug>/…`, never `~/…`
- [ ] `PRD.md` › 15 › Skill file structure ("No execution happens at install time") checked against FR-1 and corrected if needed
- [ ] An ADR in `docs/adr/`, numbered with the next ADR-U number not already used in `docs/adr/` or `todo/` (`grep -rhoE 'ADR-U[0-9]+' docs todo | sort -uV | tail -1`), recording § Design › Why print, not add and the rejected alternatives
- [ ] CHANGELOG entry under `## Unreleased`. Install no longer adds MCP servers and refuses agents outside FR-2's set; servers that an earlier client added stay, and `remove` prints the command to remove one. It names the update commands for existing plugin installs (#006 › References › Claude Code plugin updates)
- [ ] `version` in `.claude-plugin/plugin.json` raised above the value on `main` at merge, rechecked after any rebase, because #006 Slice 4, #048 and #050 raise it too

---

## Test Plan

### Fixture

A skill `akh-test-051` at a commit of a test repository, reached through a fake catalog, whose `plugin.json` lists:

| Item | Declaration | Expected |
|---|---|---|
| server `akh-stdio` | `stdio`, `command` `/bin/true`, `env` `{"T": "${AKH_TEST_SECRET}"}` | block with the stdio and `${…}` warnings and a command |
| server `akh-http` | `http`, `url` `https://example.invalid/mcp`, `headers` `{"X": "a\nb c"}` | block with escaped header value (AC-9) and a command |
| server `-sproject` | `stdio`, `command` `/bin/true` | no command; name reason |
| server `akh-bad-env` | `stdio`, `env` `{"A": {"description": "x"}}` | no command; value-type reason |
| server `akh-sso` | `http`, `auth.type` `slac-sso` | block without a command, sign-in line |
| agent `agent-plain` | `name`, `description` only | written; "every tool" |
| agent `agent-hooks` | `hooks` with a `PreToolUse` `Bash` hook | not written; key named |
| agent `agent-servers` | `mcpServers` and `permissionMode` | not written; keys named |
| agent `agent-memory` | `memory: user` | not written; key named |
| folder files | `.claude-plugin/plugin.json` with `mcpServers`, `.installed-manifest.json`, `.akh-mcp/akh-stdio.json` holding a different configuration | all three left out; the client's own `.akh-mcp/akh-stdio.json` written (AC-5) |

### Checks

- **T1 — static, in `backend/tests/`:** `skill/SKILL.md` has no instruction to run `claude mcp add` or `claude mcp add-json`, holds § Server block's lines, and passes #050 › AC-7's frontmatter and inline-shell rule.
- **N1 to N7 — by hand, in a throwaway `HOME` with a signed-in Claude Code:** N1 install (AC-1, AC-2, AC-4, AC-5, AC-9); N2 run the printed `akh-stdio` command (AC-3); N3 pre-existing agent clash (AC-6); N4 remove (AC-7); N5 update to the changed commit (AC-8); N6 `install skillset` with a member that brings servers: no new question, and the blocks print after the summary line (#006); N7 the same install in a Cogito session, checking the scope line.

`AKH_TEST_SECRET`'s value must appear in no file under the throwaway directory and in no transcript line other than the block's unexpanded `${AKH_TEST_SECRET}`.

---

## Relationship to Other Tasks

- **#006 (Skillsets), Slice 4:** `install skillset` keeps FR-7's single confirmation and its "MCP server" marker, which now means the member brings servers the user can add afterwards. The command prints every member's FR-1 blocks after its summary line. FR-2 and FR-3 apply to each member without a question, so "a user who confirms can leave the run unattended" stays true.
- **#050 (Client token helper):** both rewrite `skill/SKILL.md` › Install, so the second to merge rebases on the first; each raises `version` under the rule in the Definition of Done. This task reads no token.
- **#023 (MCP server registry):** defines `auth.type`, which FR-1 reads. If #023 ships, the skill page can show the same configuration before install.
- **#046 and #047 (marketplace sources and route):** a `/plugin` install, once they ship, gives Claude Code users Claude Code's own handling of plugin agents and servers; this client's rules still apply to its own install.
- **#048 (Install through the files route):** installs skill-folder files only, so FR-3 applies to it.
- **#020 (installer extension):** its planned Codex slice is where printed Codex and OpenCode forms would go (Follow-ups).
- **Cogito TODO #200 (`slaclab/cogito`), H-7:** the control is now refusal plus the user's own action, not a confirmation; Cogito's slice 2 FAQ answer should say so.

---

## Follow-ups (non-blocking)

- **Supply the S3DF token to SLAC MCP servers (deferred 2026-10-15, board review Round 1).** When a catalog skill needs a named SLAC endpoint, add a client-owned `headersHelper` for servers marked `auth.type: slac-sso`. Round 1 settled its shape: its own script, not #050's helper, because a `headersHelper`'s output is the header itself and #050 › AC-2 forbids the token in that helper's output; #050's location and shape rules for the token file; an origin list held in the helper that matches scheme, host and port exactly, checked against `CLAUDE_CODE_MCP_SERVER_URL`, writing `{}` for any other origin; the `headersHelper` value naming the hub client's own folder by absolute path, never the installed skill's folder; and `skill/SKILL.md` telling the model never to run it. A plugin's cache folder changes on every update, so the helper's location needs settling then.

The items below come from the 2026-10-14 to 2026-10-15 board review's Opportunities sections, deduplicated, keeping only those that still apply to the narrowed design. The reviewer codes in brackets are research (dr), engineering (er), documentation (dc), security (sr), and UX (ux).

- Install through Claude Code's plugin system once #046 and #047 land: Claude Code ignores `hooks`, `mcpServers`, and `permissionMode` for agents a plugin brings, and handles scope and uninstall itself. Claude Code only; Codex and OpenCode need their own route. [dr, ux]
- A small script in `skill/`, run like #050's helper, that parses `plugin.json` and agent frontmatter and prints the listing, so the model relays the script's output instead of composing it from author-controlled text. [dr, sr, ux]
- Print the server configuration in the forms other harnesses need: an `opencode.json` `mcp` block and a Codex `config.toml` entry (#020's planned Codex slice). [main session]
- Have the catalog check each `mcp-servers` entry at submit time and show the server's command or URL and each agent's declarations on the web skill page, so users can judge before installing. [sr, ux, dc]
- Use `claude plugin validate`'s existing checks, which warn on literal credentials in header values. [dr]
- A Cogito managed PreToolUse hook that returns `ask` for `claude mcp add*` and for writes under `~/.claude/agents/`, enforced outside the model. [sr]
- Have `/agent-knowledge-hub create` scaffold MCP stubs that use `${HOME}/…` for skill-folder scripts and carry no literal credential, and have `validate` flag `~/…` and `${VAR}` in server configs. [dc, dr]
- Remove `version` from `.claude-plugin/plugin.json` so the four tasks that raise it cannot collide. [dc]
- Link a refused agent to the catalog's flag feature (`backend/app/services/flag.py`). [ux]

---

## References

- [#050](050-client-token-helper.md) — the client's token helper; both tasks rewrite `skill/SKILL.md` › Install.
- [#006](006-skillsets.md) — skill sets; `install skillset` prints each member's server blocks after its summary line (Relationship to Other Tasks).
- Cogito `slaclab/cogito` TODO #200, Open Question 1, decided 2026-10-14: no managed MCP or agent lock; this client is the control.
- Claude Code MCP documentation, read 2026-10-14: https://code.claude.com/docs/en/mcp — installation scopes and where each is stored; environment variable expansion; plugin-provided servers.
- Claude Code sub-agents documentation, read 2026-10-14: https://code.claude.com/docs/en/sub-agents — frontmatter fields; `hooks`, `mcpServers` and `permissionMode` ignored for plugin subagents; hooks and inline servers from `~/.claude/agents/` run without the folder-trust check.
- Claude Code hooks documentation, read 2026-10-15: https://code.claude.com/docs/en/hooks — hook types, including `http` hooks and `allowedEnvVars`.
- Claude Code plugin loading reference, read 2026-10-14: https://code.claude.com/docs/en/plugins/loading — `<name>@skills-dir` plugins under `~/.claude/skills/`.
- Claude Code plugin manifest reference, read 2026-10-14: https://code.claude.com/docs/en/plugins-reference — `mcpServers`, `agents` and `hooks` keys; unknown top-level keys, such as this catalog's `mcp-servers`, are stripped.

---

## Board Review

**Verdict:** UNSTABLE
**Date:** 2026-10-15
**Rounds:** 3

Round 3 still produced design amendments (10 design / 10 precision; the research reviewer tagged two behaviour changes as precision). No reviewer raised a blocking issue, but every round found a new way a skill's author-controlled configuration could harm the user despite the confirmation: `${VAR}` expansion in headers and a skill folder loading as a plugin (Round 1); servers defined inline in agent files and a pre-creatable staging directory (Round 2); `~` paths resolving against the session's directory, a clash check that printed the user's tokens, a forgeable manifest, and agent `http` hooks (Round 3). The cause is the design: the client copied configuration chosen by any signed-in author into the user's account, gated only by a prompt the model is told to show. On 2026-10-15 the user chose to narrow the task so that the client refuses risky agents and prints MCP server configuration for the user to apply, and to review the narrowed plan afresh.

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | R1 4/4 · R2 2/9 · R3 1/7 | A skill folder holding `.claude-plugin/plugin.json` loads as a plugin; `add-json` needs `type` and stores `args: []`; Claude Code does not expand `~`; agent `http` hooks with `allowedEnvVars` |
| codebase-arch-review | — | skipped | Client-only change |
| codebase-eng-review | ⚠️ WARN | R1 8/5 · R2 3/7 · R3 5/0 | `${VAR}` in headers is expanded at every connection (measured); staged install; `update` and subagent edge cases |
| doc-review | ⚠️ WARN | R1 4/10 · R2 0/11 | Scope messages outside Cogito; manifest records; Definition of Done |
| security-review | ⚠️ WARN | R1 7/3 · R2 5/0 · R3 3/0 | Inline agent servers; `mktemp -d` staging; `~/` paths; `claude mcp get` prints tokens; forgeable manifest |
| codebase-ux-review | ⚠️ WARN | R1 7/8 · R2 5/10 · R3 1/3 | Prompt copy; `update` defaulting to `cancel`; silent removal on `update` |

**Accepted warnings:** none; the design is being replaced.
**Unresolved decisions:** none
**Amendments:** 55 design / 77 precision (Round 1 30/30, Round 2 15/37, Round 3 10/10)

### Reviewer output (final round per reviewer)

<details>
<summary>research — Round 3 (PASS WITH WARNINGS)</summary>

# Round 3 — Deep Research (DR) — #051 client confirms MCP servers and agents

**Summary**

- `claude mcp add-json --scope user` accepts every configuration the Copy rule now builds, with `type`. It stores a stdio configuration with no `args` as `"args": []` and reorders top-level keys. Under FR-4's "still equals the recorded configuration" test, that would make `remove` and `update` treat the skill's own server as changed or as a clash. Amended: the Copy rule sets `args: []`, and FR-4 compares parsed JSON.
- Claude Code 2.1.281 does not expand `~` in a stdio `command` or `args` (`posix_spawn '~/tilde.sh'` ENOENT). It expands `${HOME}`. So `${HOME}/.claude/skills/<slug>/…` is the only working form, and FR-4's file-changed test and the flag line, which looked only for `~/` and absolute paths, would mark a changed script `(unchanged)`. Amended, and the fixture now uses `${HOME}/`.
- Unbraced `$VAR` is never expanded in stdio servers, in `http` headers or in URLs, and a `${…}` header name fails the connection. The Copy rule's `${` test is therefore complete.
- The agent inline-server rule matches the `sub-agents` docs. Agent `http` hooks with `allowedEnvVars` were not covered, though they leak environment values the same way. Amended to refuse such an agent (Decision, assumed A). The hook line now has a form for each hook type. This rests on the docs, not on a run.
- Real `~/.claude.json` files were not touched. All probes ran in `scratchpad/r3/home`.

**Issues**

Measured 2026-10-15 on `sdfiana008`, Claude Code 2.1.281, `HOME` and `CLAUDE_CONFIG_DIR` set to `scratchpad/r3/home` (wrapper `r3/c.sh`).

- PASS | Copy rule + `type` | `add-json --scope user` accepted all ten shapes the rule builds: stdio with `type` and command only, with args and env, with `[]`/`{}`; http and sse with and without headers, with `{}` headers; names `K_9-x` and `9k`. Each exit 0.
- HIGH | precision | FR-4 / Copy rule | `add-json` does not store what it is given: a stdio configuration without `args` is stored with `"args": []`, and top-level keys are reordered to `type, command, args, env` (`{"type":"stdio","command":"/bin/true"}` stored as `{"type":"stdio","command":"/bin/true","args":[]}`). FR-4's "still equals the configuration the manifest recorded" then fails for the skill's own server: `remove` leaves it as "changed since install", and `update`'s not-a-clash test fails, so it is left out as a clash. Amended.
- HIGH | precision | FR-4, flag line, fixture, Implementation step 1 | Claude Code does not expand `~` in a stdio `command` or `args`: `command` `~/tilde.sh` failed with `ENOENT: no such file or directory, posix_spawn '~/tilde.sh'`, and `args` `~/x`, `~`, `x~/y`, `~root/q` reached the program as written. `${HOME}` is expanded in `command` (`${HOME}/brace.sh` ran), `args` and `env`. So `${HOME}/.claude/skills/<slug>/…` is the only form a `plugin.json` can use to run a file from the installed folder, not `~/…`, and FR-4's file-changed test, which names only absolute and `~/` paths, misses it: an `update` that changes only that script shows the server `(unchanged)`. Amended FR-4, the flag line, the fixture row and step 1; Measured facts gains the row.
- PASS | Copy rule stdio row | Unbraced `$HOME` and `$PROBE_SECRET` in `command`, `args` and `env` were passed literally (`posix_spawn '$HOME/unbrace.sh'`; `arg=[$PROBE_SECRET]` with `PROBE_SECRET` set), so testing for `${` catches every expansion Claude Code does there.
- PASS | Copy rule http row | Against a local listener, only `X-Braced: ${PROBE_SECRET}` arrived expanded (`sekrit-value`); `a $PROBE_SECRET b`, `~/h` and the URL path `/p/$PROBE_SECRET/q` arrived as written. A `${…}` in a header name is not expanded: `get` reported `Invalid header [redacted]: 'X-${PROBE_SECRET}'` and sent nothing.
- PASS | FR-1 clash check | `claude mcp get` exits 0 for a server that fails to connect (`t2`, ENOENT) and 1 for an unknown name, so a broken same-named server still counts as a clash.
- PASS | agent inline-server rule | `sub-agents` docs (read 2026-10-15): `mcpServers` is a list whose entries are a name string or a single-key map of name to a `.mcp.json` configuration, with types `stdio`, `http`, `sse`, `ws`, and inline servers from `~/.claude/agents/` connect with no trust check. The rule's fields match; `ws` falls under "any other value" and is refused, which fails closed; an entry without `type` that has `url` is refused, because `url` is not a stdio field.
- HIGH | design | Copy rule (agents), hook lines | `hooks` docs (read 2026-10-15): a hook's `type` is `command`, `http`, `mcp_tool`, `prompt` or `agent`, and subagent frontmatter takes "the same configuration format as settings-based hooks". An `http` hook POSTs each event's JSON, which holds the tool's input, to its `url`, and resolves `$VAR` or `${VAR}` in its `headers` for each name in `allowedEnvVars`. An agent with `allowedEnvVars: ["GITHUB_TOKEN"]` therefore sends that token to its author's server, the leak Round 2's inline-server bullet closes for `mcpServers` and leaves open here. § Prompt copy's hook line is "one line per hook command, `<when>: runs <command>`", which has no form for a hook without `command`, so an agent whose only hook is `http` can be summarised as `nothing`. Not measured by a run, because that needs a signed-in session. Amended: an `http` hook that sets `allowedEnvVars` refuses the agent, and the hook line gains a form for each other type. Decision 1.
- LOW | precision | Non-Goals | `hooks` docs: a skill's frontmatter hooks are registered when the skill is invoked "and keeps running them for the rest of the session", not "only while that skill or command is in use". This is the rationale for leaving `SKILL.md` out, and the ADR repeats it. Not amended under the round bar: it changes no client behaviour, and the ADR author can take the docs wording.

- LOW | precision | DoD › create-a-skill guide | The guide line says `${HOME}` is allowed but not that `~` is not expanded, so an author who writes `~/.claude/skills/<slug>/serve.sh` as the `command` gets a server that fails with ENOENT. The client is still right: it installs what the user agreed to, and FR-4 also tracks the `~/` form. Not amended under the round bar.
- PASS | `update` re-add | `add-json` on a name already at user scope exits 1 (`MCP server k1 already exists in user config`), and succeeds after `claude mcp remove --scope user k1`. That is safe because `skill/SKILL.md` › Update removes the whole old install, recorded servers included, before the install flow re-adds approved ones; with the `args` default above, FR-4's equality test lets that removal find the skill's own server.

**Opportunities**

- The create-a-skill guide and › Validate could tell authors to write `${HOME}/.claude/skills/<slug>/…`, never `~/…`, for a script in the installed folder (LOW above). One sentence; it fixes no client defect.

**Decisions Required**

*Decision: an agent's `http` hook that reads environment variables*
- **Severity:** judgement-call
- **Question:** An agent's `http` hook with `allowedEnvVars` sends those variables' values, in its headers, to the URL the author chose, along with each tool's input. Does the client refuse such an agent, as Round 2 made it refuse an agent whose inline server has a `${…}` header?
- **Options:** A) refuse it before the question and name the event and `url` (amended). B) ask about it like any other hook, with the hook line showing the `url` and the `Declares:` line showing `allowedEnvVars`, on the grounds that a `command` hook can send the same values and is only shown.
- **Assumed:** A. It matches Round 2's inline-server rule and Goal 2, and it fails closed. A `command` hook that sends a token puts the variable name in a command line the user reads; `allowedEnvVars` resolves the value through Claude Code's own expansion, which is the case the Copy rule refuses everywhere else.
- **Impact if wrong:** an agent whose author reports tool use to their own service with a key from the user's environment cannot be installed by the client; the user can still copy the file into `~/.claude/agents/` by hand.

**Amendments**

- precision: Design › Copy rule — a stdio configuration with no `args` gets `args: []`, because `add-json` stores it that way and FR-4's equality test would otherwise never match the skill's own server.
- precision: FR-4 — the stored entry and the recorded configuration are compared as parsed JSON, not as text, because `add-json` reorders top-level keys.
- precision: FR-4 — the forms that name a file in the skill folder are the absolute path, `${HOME}/.claude/skills/<slug>/…` (the only form that works, since Claude Code passes `~` unexpanded) and `~/…`; replaces "with `~/`, the only form … because the Copy rule refuses `${`".
- precision: § Prompt copy › flag line — `Runs <file> from this skill's folder` matches the same three forms.
- precision: Measured facts — `add-json` row gains the acceptance of every Copy-rule shape and the stored-form normalisation; new row `~` and `$VAR` in a stdio server, with the `http` header and URL results.
- precision: Implementation Plan step 1 and the fixture's `akh-test-stdio` row — the `~/` probe is now a measured result; the fixture names its script with `${HOME}/`, so it tests the form a real skill must use.
- design: Design › Copy rule — an agent with an `http` hook that sets `allowedEnvVars` is refused before the question; § Prompt copy › Messages gains its refusal wording; AC-11 and the fixture gain `akh-test-httphook`; the create-a-skill DoD line names the rule (Decision).
- precision: § Prompt copy › hook lines — one line per hook, with an action for each `type` (`command`, `http`, `mcp_tool`, `prompt`, `agent`, other), so an agent whose only hook is `http` is not summarised as `nothing`.

TOTAL: 1 design, 7 precision

**Status**

PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 3 (PASS WITH WARNINGS)</summary>

# Round 3 — Engineering Review (codebase-eng-review)

**Summary**

- An implementer can now write `skill/SKILL.md` › Install, Update, Remove and `install skillset` from the plan without meeting two rules that contradict each other. Five places where the rules disagreed, or where a path had no rule and the natural reading was wrong, were amended in the plan. Each amendment adds one or two sentences and changes no other section.
- The two most serious defects found, a stdio configuration that `add-json` stores with `"args": []` and FR-4 still treating `~/` as the only skill-folder path form, were also found by the parallel research reviewer, who fixed them first. Both fixes were checked against this review's own probe, and neither is counted here.
- This review's own design amendments are these. A skillset run whose only items are all refused no longer installs every member without a question. `update` inside a subagent no longer removes the servers and agents the user agreed to before. A failed `claude mcp remove` no longer leaves a server with no record. A reply that arrives after the staged clone is gone causes a fresh clone and a new question. The test environment no longer sets `CLAUDE_CONFIG_DIR`, which with `HOME` set to the same directory made AC-5's `claude plugin list` check pass for any client.
- Every AC except the withdrawn AC-6 still has a test row. The three amendments that change behaviour have no fixture test yet, and Opportunities lists the cheap ones.
- Warning: these are 5 `design:` amendments in the final round. Each is a self-contained rule, and the main session can check it by reading the amended sentence against the walk in Issues. No reviewer judgement is needed for that check. Both Decisions are defaults that a single question to the user can settle.

**Issues**

This review walked Install flow, Staged install, Copy rule, FR-1 to FR-6, Prompt copy and the manifest format once for a single skill (`install`, then `update`, then `remove`) and once for a three-member skillset in which member B's agent has an inline `http` server and member C brings a server named like member A's. Three scratch probes on `sdfiana008` (Claude Code 2.1.281), with `HOME` and `CLAUDE_CONFIG_DIR` pointed at the session scratchpad, checked the facts the walk depended on. Neither real `~/.claude.json` gained a server; a check that printed only whether the probe names were present confirmed it.

- HIGH | design | Design › Copy rule vs FR-1's clash exemption and FR-4's removal check | Both tests require the server's entry in `~/.claude.json` to equal "the configuration the manifest recorded", which is the configuration passed to `add-json`. Measured 2026-10-15: `add-json -s user s1 '{"type":"stdio","command":"/bin/true"}'` stores `{"type":"stdio","command":"/bin/true","args":[]}`, and a configuration given as `{"env":…,"args":…,"command":…,"type":"stdio"}` is stored with its keys in the order `type`, `command`, `args`, `env`. `http` and `sse` configurations without `headers`, and a `stdio` one without `env`, are stored with no key added. So for every `stdio` server whose entry has no `args`, such as one whose `command` is the server binary itself, the stored entry never equals the record: `update` treats the skill's own server as a clash and leaves it out, and `remove` reports it as changed since install and leaves it in place. AC-14 and N16 do not catch this, because the fixture's only installed server has `args`. The parallel Round 3 research reviewer measured the same result and fixed it before this review edited the plan: the Copy rule sets `args` to `[]` when a `stdio` entry has none, FR-4 compares the entry with the record as parsed JSON, and Measured facts › `claude mcp add-json` records both behaviours. Verified against this review's own probe; not counted under Amendments.
- HIGH | design | FR-4 file test vs Design › Copy rule | Round 2's parallel edits left FR-4 saying that `~/` is "the only form a `plugin.json` written before install can use, because Design › Copy rule refuses `${`", while the Copy rule allows `${HOME}`. An implementer following FR-4 would not recognise `${HOME}/.claude/skills/<slug>/serve.sh` as a skill-folder file, so `update` would mark such a server `(unchanged)` after its script changed, which breaks the promise in the `Runs <file>` flag line. The research reviewer has since measured that Claude Code passes `~` unexpanded and expands `${HOME}`, and rewrote FR-4, the fixture's `akh-test-stdio` and Implementation step 1 around `${HOME}/`. Verified; not counted under Amendments.
- INFO | verified | FR-6 | With `HOME` set to a scratch directory, `claude plugin list` listed a skills-directory plugin only for a folder with a top-level `.claude-plugin/plugin.json`. It listed nothing for a folder whose only manifest is a root `plugin.json`, which is the catalog's usual layout, and nothing for a folder with `.claude-plugin/` one level down. Leaving out `.claude-plugin/` is therefore enough for Goal 4.
- MEDIUM | design | § Prompt copy › The skillset question vs § Prompt copy › Messages | In the three-member walk, suppose member A's only server is marked `auth.type: slac-sso`, so FR-2 refuses it before the question, and no other member brings anything askable. The skillset question replaces #006's question "when at least one member brings an MCP server or an agent", which A does, but Messages says "when nothing is left to ask about, the client asks nothing and installs the rest". Read together, the run installs all three skills with no question at all. That breaks #006 › FR-7 › Confirm rule, under which the member list, chosen by the skillset's owner, is "the only point where the user sees what will be installed". The other reading, a skillset question with no items under it, offers `yes` and `no` that do the same thing. Amended: the skillset question replaces #006's only when an item is still left to ask about after the messages; otherwise #006's question is asked unchanged, and the ask-nothing rule applies to one skill's install only. Relationship › #006 part (2) points to this paragraph, and the plan says Prompt copy wins where a paraphrase differs, so part (2) was left as it is.
- MEDIUM | design | Test Plan environment vs AC-5 and Critical Paths | Every run set `HOME` and `CLAUDE_CONFIG_DIR` to one throwaway directory. Measured 2026-10-15: with both set to directory X, `claude plugin list` listed `p1@skills-dir` from `X/skills/p1/` and did not list `p2` from `X/.claude/skills/p2/`; with only `HOME=X`, it listed `p2` and not `p1`. A second probe confirmed that `.claude.json` follows `CLAUDE_CONFIG_DIR`. The client writes to `~/.claude/skills/`, which in that setup is a directory Claude Code does not read, so AC-5's `claude plugin list` half passes even for a client that copies `.claude-plugin/`. The Critical Path's "see the agent in `/agents`" check would fail for a correct client, assuming agents follow the same rule, which was not run. The `claude mcp` checks were unaffected, because the client's `~/.claude.json` and Claude Code's were the same file. Amended: runs set `HOME` only and leave `CLAUDE_CONFIG_DIR` unset, and the Test Plan says why. Implementation step 1's probes keep both set, because they use only `claude mcp` and `.claude.json`.
- MEDIUM | design | FR-5 vs Design › Staged install | FR-5 counts a reply sent later with `claude -p --continue "<reply>"`, and the install then reads the staged clone from the `mktemp -d` directory. Nothing said what happens when that directory is gone at reply time. `/tmp` is per node, while `~/.claude/projects/`, which `--continue` resumes from, is shared in Cogito through the `~/.claude` symlink, so a `--continue` on another host finds the conversation but not the clone; a `/tmp` clean-up has the same effect. The natural recovery, cloning again and acting on the earlier `yes`, installs whatever the default branch holds for an unpinned skill, which the question never showed. Amended in Staged install: when the directory or a staged clone is gone at reply time, the client stages again and asks again.
- MEDIUM | design | FR-5 vs FR-4 in `update` | FR-5 says a client inside a subagent "adds no MCP server or agent", and FR-4 says any reply other than `cancel` sets what the updated install holds, so a reply that adds nothing removes every server and agent file the old install added. When Claude hands "update my skills" to a subagent that runs `/agent-knowledge-hub update <slug>`, the two rules together remove the servers and agents the user agreed to before, with no reply from the user, and print a message that tells them to run `update` again to get them back. Amended: in `update`, when the old install added an item or the new version brings one, a client inside a subagent changes nothing, as after `cancel`; Prompt copy › Messages gains the `update` wording, and N14 gains the case. Plain `install` inside a subagent keeps its current rule, because it removes nothing.
- MEDIUM | design | FR-4 partial failure in `update` and `remove` | Nothing said what happens when `claude mcp remove` fails, or when `claude` is not on `PATH`, which Prompt copy › Messages already treats as a case that occurs. Today's removal order deletes the skill folder last, but the plan states no order. If the folder, and with it `.installed-manifest.json`, goes while a server it recorded is still in `~/.claude.json`, the server is left without a record: `remove` reports success while the server stays, and every later `install` or `update` finds an unrecorded server of that name, names it as the user's own clash ("Yours is unchanged"), and leaves the skill's server out for good. Amended in FR-4: recorded servers are removed first, and a failure stops the run with the rest of the old install and its manifest in place. A re-run converges, because FR-4 already counts a recorded server with no entry as removed.
- LOW | not amended | § Prompt copy, agent block | "Its own MCP servers: an indented block like 1 or 2" carries over "It starts with each Claude Code session" and the reach line, both untrue for an inline server, which lives in the agent file and connects only while the agent runs. The error makes the agent look broader than it is, never narrower, and "like" leaves the implementer room. Wording, so out of scope for this round.
- LOW | not amended | § Prompt copy › The skillset question, cross-member clash | When the earlier member's item of that name is refused, clashes, or is declined, the later member's item is still left out. The message's "if you add that one" then cannot happen, and the closing message gives no `update` hint, although `update <later member>` would now ask about the item. This fails closed, and the fix is wording.
- LOW | not amended | FR-3 and FR-4 with `CLAUDE_CONFIG_DIR` set in production | Claude Code then keeps `.claude.json` in that directory (measured above), so the reach line would name the wrong file and FR-4's match check would read it. This is not new: the client already writes to `~/.claude/skills/`, which Claude Code does not read in that case, so such a user's installs already fail today. `CLAUDE_CONFIG_DIR` is unset in this Cogito session.
- LOW | not amended | Implementation Plan step 1 | Step 1 keeps `HOME` and `CLAUDE_CONFIG_DIR` set to one scratch directory. That is correct for its `claude mcp` probes, and a probe that needs a skills-directory plugin must put it under `<dir>/skills/`, not `<dir>/.claude/skills/`. Measured facts › `claude mcp get` already used that setup.
- INFO | verified | Test coverage after Round 2 and this round's parallel edits | AC-1 to AC-5 and AC-7 to AC-14 each have a test row (AC-6 is withdrawn): AC-1 and AC-10 in N1, AC-2 in N2, AC-3 in T1 and N5, AC-4 in N15, AC-5 in N6, AC-7 in N4, AC-8 in N3, AC-9 in N9, AC-11 in T1 and N5, AC-12 in N7, AC-13 in T1, AC-14 in N16. AC-11's sixth item, the agent with an `http` hook, has its fixture row. Each of T1, T3 and N1 to N17 is used once, and T2 stays withdrawn.
- INFO | verified | Single-skill walk | The single-skill walk now gives one order with no conflicting rule: clone into `mktemp -d`, read, Copy rule and FR-2 with `args` defaulted, clash check with the manifest exemption compared as parsed JSON, messages, one question, folder without `.claude-plugin/` or a source `.installed-manifest.json`, commands, agents, servers, with a manifest rewrite after each. `update` asks first, then removes, then installs, and `remove` removes only recorded, matching entries at the recorded scope. In the skillset walk, B's inline `http` server passes the Copy rule's inline rule and is listed under the agent. C's server named like A's is reported before the question with the cross-member message. Items are numbered across members, and #006's skip rule keeps `install`'s redirect to `update` out of the loop.

**Opportunities**

- A fixture `stdio` server with no `args`, installed in N2 and checked in N15 and N16, would test the `args: []` default against FR-4's comparison. That default is the fix for the most likely silent failure this round found, and no test exercises it.
- A fixture `stdio` server whose first argument starts with `~/` would test the Copy rule's new `~` refusal and its message.
- Running `remove` after N2 with `claude` taken off `PATH` would test FR-4's new stop-on-failure rule. Afterwards the skill folder and manifest should still be there, and the `claude mcp remove` command should be printed.
- #006 Slice 4's skillset narrative test could add a member whose only server is marked `slac-sso`, to check that #006's question is still asked when nothing is left to ask about.
- FR-1's clash check runs `claude mcp get`, which health-checks the existing server of that name, starting the user's own `stdio` program or connecting to its URL during an install. A match-only read of `~/.claude.json` for user and local scope, and of `.mcp.json` for project scope, would avoid that, at the cost of re-implementing Claude Code's scope lookup.

**Decisions Required**

*Decision: `update` inside a subagent*
- **Severity:** defaulted
- **Question:** A client inside a subagent cannot ask the user. In `update`, should it change nothing, keep the old items while installing the new version, or install the new version without them?
- **Options:** A) Change nothing, as after `cancel`, when the old install or the new version has an MCP server or agent. B) Install the new skill folder and commands, and keep the old servers and agent files as they were. C) Install the new version without them, which removes the items the user agreed to before (the plan's reading before this round).
- **Assumed:** A. It is the only option that neither removes something the user agreed to nor leaves an old server running beside a new skill version the user has not seen. It matches what `claude -p` already gets, a turn that ends with nothing written.
- **Impact if wrong:** Under B, FR-5's new sentence and the `update` message change, and FR-4 needs a rule for keeping a record whose server the new version changes. Under C, the amendment is reverted, and the subagent message must say that the old items were removed.

*Decision: A server that `update` or `remove` cannot remove*
- **Severity:** defaulted
- **Question:** When `claude mcp remove` fails or `claude` is missing, should the run stop with the old install in place, or go on and keep the record somewhere?
- **Options:** A) Remove recorded servers first, and stop on the first failure with the rest of the old install and its manifest in place. B) Go on, and copy the failed server's record into the new manifest in `update`, or keep a manifest file after `remove` deletes the rest of the folder.
- **Assumed:** A. It needs no new record type, a re-run converges because FR-4 counts a recorded server with no entry as removed, and the user sees the error. B leaves a `remove` that does not remove the folder, and an `update` that records a server whose configuration the new version may have changed.
- **Impact if wrong:** Under B, FR-4's new sentence changes, `remove` gets a partial-folder state to describe, and the Prompt copy messages need a "could not remove" line.

**Amendments**

- design: § Prompt copy › The skillset question — it replaces #006's question only while an item is still left to ask about after the messages printed before it; otherwise #006's question is asked unchanged, so a skillset run never installs without a question.
- design: Test Plan — runs set `HOME` to the throwaway directory and leave `CLAUDE_CONFIG_DIR` unset, because with it set Claude Code does not read `~/.claude/skills/`, which makes AC-5's `claude plugin list` check vacuous.
- design: Design › Staged install — when the temporary directory or a staged clone is gone when the reply arrives, the client stages again and asks again instead of installing a fresh clone on the earlier reply.
- design: FR-5, § Prompt copy › Messages and N14 — `update` inside a subagent changes nothing when the old install or the new version has an MCP server or agent, instead of removing the items the user agreed to before.
- design: FR-4 — `update` and `remove` remove recorded servers before the rest of the old install, and stop with the manifest in place when `claude mcp remove` fails or `claude` is missing, so no server the client added is left without a record.

TOTAL: 5 design, 0 precision

**Status**

PASS WITH WARNINGS

</details>

<details>
<summary>doc-review — Round 2 (PASS WITH WARNINGS)</summary>

# Round 2 — Documentation review (dc) — #051

**Summary**

- Each rule added in Round 1 now has a Definition of Done row in `skill/SKILL.md`, the guide pages, CHANGELOG and the ADR: the Copy rule refusals, § Prompt copy, `--scope user`, FR-6, FR-5's subagent and `claude -p` rule, `update` asking first, and the refusal of `slac-sso` servers. Eight DoD rows were amended to get there. The Install step 4 row still allowed a `claude mcp add` form, which FR-3 and T3 forbid.
- I found and fixed three remnants of the `headersHelper`: the FR-2 refusal reasons in § Prompt copy, and the "What fails today" token row. A parallel edit removed the third, the install question's `Signs in as you` line. § Prompt copy gained message rows for Copy rule refusals, FR-6 and FR-5, which ACs and T1 assert on.
- No row still describes a per-member skillset prompt. The `version` row and the build order agree with #050. The build order now also gives T1's dependency on #050's helper copy as a reason.
- Warning: `todo/050-client-token-helper.md` still describes a #051 `headersHelper` in FR-1, its ADR row and Relationship › #051. This review was not allowed to edit it (Decision, defaulted).

**Issues**

- HIGH | Definition of Done › Install step 4 row | "The `mcp-servers` line no longer shows `claude mcp add` without `--scope`" lets `claude mcp add --scope user <name> <command> [args...]` stand, which FR-3 forbids ("never with `claude mcp add`") and T3 fails ("no `claude mcp add ` command line"). The row also never names Design › Copy rule or § Prompt copy, the two amendments the step 4 text must carry (amended).
- MEDIUM | § Prompt copy › After the reply › Refused under FR-2 | Both reasons describe the dropped `headersHelper`: "sends your sign-in only to the SLAC services on its list" names a list that no longer exists, and the second reason describes a choice the client no longer makes. FR-2 now says the message says this version cannot connect such a server. The Error handling DoD row takes its wording from this row, so `SKILL.md` would ship the stale reason (amended).
- MEDIUM | § Prompt copy › install question | `Signs in as you: <yes, with your S3DF sign-in | no>` can only print `no`: FR-2 refuses every `slac-sso` server before the question, and the Copy rule refuses a `${…}` header. The line is left over from the `headersHelper` design (removed by a parallel Round 2 edit before this review reached it; no amendment here).
- MEDIUM | What fails today › S3DF token row | Desired behaviour "it uses a headers helper or refuses" describes the dropped design; CHANGELOG and guide text are written from this table (amended).
- MEDIUM | § Prompt copy › After the reply (since renamed › Messages by a parallel edit) | The heading claimed FR-6, but no row gave FR-6's message, and there was no wording for a Copy rule refusal or FR-5's no-reply case. AC-11, AC-13 and T1 assert on those messages, and `SKILL.md` › Error handling had no source text for them (amended: three rows, which the parallel rewrite kept).
- MEDIUM | Definition of Done › Error handling row | It lists three cases. Copy rule refusals, FR-1's name clash, FR-5's no-reply case and FR-6's left-out manifest are also cases the client must word, and the row omits them (amended).
- MEDIUM | Definition of Done › Update and Remove row | "a server added from another host" contradicts FR-4, which decides by the recorded `~/.claude.json` path and says a host comparison would refuse a removal that works. The row also omits the update ordering (question before removal, new/changed/unchanged marks) and Design › Install flow's rule that `install` of an installed slug runs `update` (amended).
- MEDIUM | Definition of Done › guide row | › Manage installed skills says `update` and `remove` "list the servers and agents they remove and ask first", the FR-4 of the plan before Round 1. `update` now asks about the new version before it removes anything, and `cancel` keeps the old install. › Install a skill does not say that a server needing the S3DF sign-in is left out (FR-2), that servers go in at user scope (FR-3), or that a session that cannot reply adds none (FR-5) (amended).
- MEDIUM | Definition of Done › troubleshooting row | With `--scope user`, a new install no longer goes missing in another project. For a Cogito user it still comes from another machine; in another project it now comes only from installs made by the earlier client (FR-4's local-scope note), and in the project where that install ran FR-1's clash rule makes `update` leave the old local-scope server in place. The row said only "run update there" (amended).
- MEDIUM | Definition of Done › Validate and create-a-skill row | `frontend/app/guides/create-a-skill/page.tsx` has no `plugin.json` content today (no occurrence of "plugin"; its only structure block lists `skill.md`, `README.md` and `CLAUDE.md`), so the row must say the page gains a section. "the fields it refuses" misses the Copy rule's `name` pattern and its `${` refusal, which are not fields. FR-6 is absent, so an author who declares `mcpServers` or `hooks` in `.claude-plugin/plugin.json` is not told they do not install. `skill/SKILL.md` › Create scaffold writes "optional agent/MCP stubs", and nothing requires the stub to pass the Copy rule (amended).
- MEDIUM | Definition of Done › ADR row | It records the prompt as the control and its alternatives, but not FR-6 (the route around the prompt it closes), FR-5's no-reply rule, or FR-2's refusal with the deferred `headersHelper`. #050's ADR row says it will record "how any header-printing helper that #047 or #051 adds relates to this one", so #051's ADR is the place that says it adds none (amended).
- MEDIUM | Definition of Done › CHANGELOG row | The existing-install note does not say what `update` does to a server the earlier client added. In the project where that install ran, FR-1's clash rule finds the old local-scope server and leaves the new one out, so the user keeps a local-scope server until they remove it with the command FR-4 gives (amended).
- MEDIUM | #050's plan is stale about #051 (cross-plan; not amended, outside the files this review may edit) | `todo/050-client-token-helper.md` › FR-1 ("a `headersHelper` for #047 or #051 … is a separate script"), › Definition of Done › ADR row ("how any header-printing helper that #047 or #051 adds"), and › Relationship to Other Tasks › #051 ("its FR-2 reads the token for a `headersHelper` the way this helper does … #051 attaches it only to servers whose URL is on a fixed list") describe the design FR-2 dropped. #051 › Relationship › #050 now says #051 adds none. Whoever next edits #050 changes its #051 line to say that #051 adds no `headersHelper` and its Follow-ups hold the deferred design.
- LOW | References › #050 and the build-order line | The order still agrees with #050, which states no order of its own with #051. The reason given ("both rewrite `skill/SKILL.md` › Install") is now the weaker of two: T1's fixture runs a client copy whose catalog origin is replaced as in #050 › Open Design Question 1, which needs #050's helper (amended).
- LOW | References › #006 | "installs through the same confirmation" reads as the per-member prompt the staged install replaced (amended).
- LOW | Test Plan coverage map | The "writes agent, then server with --scope user" line cites AC-3, which now tests FR-2's refusal, not an add (amended).
- PASS | `.claude-plugin/plugin.json` version row | Agrees with #050 › Definition of Done: both raise above the value on `main` at merge, not to a fixed number. #050's row names #006 Slice 4 and #048 but not #051; its Relationship › #051 says #051 needs its own raise under the same rule, so the two plans agree. When #050 and #051 ship in one change, one raise satisfies both rows.
- PASS | Staged install | DoD › `install skillset` row, Affected commands, Critical Paths and Relationship › #006 all describe one question after every member is staged. No row still describes a per-member prompt; the only per-member text is Design › Staged install's Rejected table.
- PASS | `headersHelper` residue elsewhere | AC-6, T2 and Implementation step 3 are marked withdrawn; FR-2, Copy rule, Trade-offs and Follow-ups agree. The remaining mentions (Copy rule's refusal of the field, Measured facts, References › MCP documentation, fixture `akh-test-hh`) are correct as they stand.
- PASS | ADR numbering | `docs/adr/` ends at `adr-u31-flag-count-sync.md`, and `todo/` claims ADR-U32 to ADR-U41, as the ADR row says.

**Opportunities**

- `/agent-knowledge-hub validate` could check each `mcp-servers` entry against Design › Copy rule and FR-2 and name every server the installer would refuse, so an author learns before a user meets the refusal. The DoD row now only documents the rule. This replaces my Round 1 opportunity that the scaffold's MCP stub show a `headersHelper` form, which the Copy rule now refuses.

**Decisions Required**

*Decision: #050's references to a #051 `headersHelper`*
- **Severity:** defaulted
- **Question:** Who corrects `todo/050-client-token-helper.md` › FR-1, › Definition of Done › ADR row and › Relationship to Other Tasks › #051, which still describe a `headersHelper` that #051 no longer adds?
- **Options:** A) The board-review orchestrator edits #050 now, as part of this reconciliation. B) #050's next review round or its implementer makes the change. C) Leave #050 as it is, because #051 › Relationship › #050 states the current position.
- **Assumed:** B, because this review may edit only #051 and its own output file. #051's ADR row now records that #051 adds no `headersHelper`, so #050's ADR has a statement to cite.
- **Impact if wrong:** #050's ADR records a relationship to a helper that does not exist, and #050's implementer may shape FR-2 and FR-3 to be shared with a script no task writes. Under C, a reader of #050 alone learns the dropped design.

**Amendments**

- precision: Definition of Done › Install step 4 — names § Prompt copy, Design › Copy rule and FR-3's `--scope user` and reach line; the `mcp-servers` line shows `claude mcp add-json --scope user` with the Copy rule's configuration file, and no `claude mcp add` form (T3).
- precision: Definition of Done › Update and Remove — `update` asks about the new version with § Prompt copy › Update and remove's marks before it removes anything; the other-machine message is keyed to the recorded `~/.claude.json`, not the host; › Install says `install` of an installed slug runs `update`.
- precision: Definition of Done › Error handling — one case for each row of § Prompt copy › Messages except `cancel`, the reply check and the closing message, and one for each server that `update` or `remove` leaves in place, replacing the list of three.
- precision: Definition of Done › Validate and create-a-skill — the guide gains a new section (it has no `plugin.json` content today); adds the Copy rule's `name` pattern and `${` refusal, FR-6's left-out `.claude-plugin/`, and that the Create scaffold MCP stub passes the Copy rule.
- precision: Definition of Done › `agent-knowledge-hub` guide — › Install a skill adds FR-2's refusal, user scope, and FR-5's no-reply case; › Manage installed skills describes `update` asking before it removes anything and `cancel` keeping the old install.
- precision: Definition of Done › troubleshooting entry — adds the cause for installs made by the earlier client, and the remove-then-`update` step that gets past FR-1's clash in the project where that install ran.
- precision: Definition of Done › ADR — adds the consequences: FR-5's no-reply rule, FR-6's closed route, and FR-2's refusal with no `headersHelper` (deferred design in Follow-ups), which #050's ADR row expects to describe.
- precision: Definition of Done › CHANGELOG — the existing-install note says that `update` from the old install's project leaves the old local-scope server as a clash, and that removing it first lets `update` add it for every project.
- precision: § Prompt copy › Messages — replaced the stale `headersHelper` reasons in the FR-2 refusal with FR-2's wording (a parallel edit then reworded the contact line), and added rows for a Copy rule refusal, FR-6's left-out `.claude-plugin/`, and FR-5's no-reply case.
- precision: What fails today › S3DF token row — desired behaviour is FR-2's refusal of a server marked `auth.type: slac-sso`, not "a headers helper or refuses".
- precision: cross-references — References › #050 gives T1's dependency on #050's helper copy as a second reason for the build order; References › #006 describes the one staged question; the Test Plan coverage map's add line no longer cites AC-3.

TOTAL: 0 design, 11 precision

**Status**

PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 3 (PASS WITH WARNINGS)</summary>

# Security Review — Round 3 (final) — #051 client confirms MCP servers and agents

**Summary**

- Three Round 2 changes left a path where something runs, or a token leaves, without the user's informed yes. Each is now amended, and each has a measured or traced attack path.
- **`~/` form.** A throwaway-config probe on Claude Code 2.1.281 showed that `~` is not expanded. A `~/.claude/skills/<slug>/serve.sh` path is therefore read from the directory the session started in, and a file planted there ran. The plan accepted this form and labelled it "from this skill's folder". The Copy rule now refuses a leading `~`, and `${HOME}/` is the form to use.
- **FR-1's clash test.** It ran `claude mcp get <name>` on a name the skill's author chose. The probe showed that `get` prints an entry's environment and header values in full, so naming a server `github` would put the user's own GitHub token into the transcript. FR-1 now reads only the exit status and the `Scope:` line.
- **The manifest.** The exemption that lets `update` keep the skill's own server trusts `.installed-manifest.json`, and that file sits in the folder the author's files are copied into. An author's copy left behind by an interrupted run would let the next run overwrite or delete the user's own commands with no question. The copy now leaves that file out.
- **`--continue`.** Another reviewer amended the staged-clone gap this round: a reply that finds the clone gone, for example one sent with `--continue` on another Cogito machine, stages again and asks again. A `--continue "yes"` from something other than the user gains nothing that a process running as the user does not already have. That residual risk was accepted in Round 2, so it is recorded here as LOW.
- Three LOW findings remain, with two opportunities. Status is PASS WITH WARNINGS.

**Issues**

Threat model, unchanged from Round 2: the asset is code execution as the user and the user's tokens (S3DF token, tokens in the user's own MCP servers' `env` and `headers`). The adversaries are a skill author, another user of a shared node or a shared directory, and a model that answers instead of the user. This round traced each Round 2 change by another reviewer: the manifest exemption, `update` semantics, the `~/…` path form, `type`, the value-type refusals, FR-5's `--continue`, and the skillset question.

Probe, run 2026-10-15 on `sdfiana008` with Claude Code 2.1.281, `HOME` and `CLAUDE_CONFIG_DIR` set to a throwaway directory, dummy values only, and the directory deleted afterwards:
- A leading `~/` in a `stdio` server's `command` is not expanded. `claude mcp get` reported `ENOENT: no such file or directory, posix_spawn '~/.claude/skills/p/s.sh'`. In `args` it reaches the program as the literal string `~/.claude/skills/p/s.sh`.
- Run from a directory that held `~/.claude/skills/p/s.sh` as a relative path (a folder literally named `~`), both the `command` form and the `/bin/sh` `args` form ran the planted file.
- `${HOME}/.claude/skills/p/s.sh` in `args` ran the file in the home directory.
- `claude mcp get <name>` printed `Environment:` with `FOO=dummy-visible-value`, and `Headers:` with `X-Dummy: dummy-header-value`, in full.

- MEDIUM | FR-1 clash check | plan FR-1 ("When `claude mcp get <name>` exits 0"); § Prompt copy › Update and remove ("whose configuration `claude mcp get` no longer matches") | FR-1's clash test runs `claude mcp get <name>` with a name the skill's author chose. The model sees the whole output, and the probe shows that this output includes the existing entry's environment values and header values. **Attack path:** the author names a server `github`. The user's own `github` server was added the way GitHub's instructions give, with `-e GITHUB_PERSONAL_ACCESS_TOKEN=…` or `-H "Authorization: Bearer …"`. Before the question, the client runs `claude mcp get github`, and the token enters the model's context and the session transcript. That is the transcript exposure Measured facts already treats as a leak for `-H`. FR-4 avoids `get` for its own check for this reason, but FR-1 did not. **Status:** amended (design). FR-1 now reads only the exit status and the `Scope:` line, which the update Name clash message needs, and Measured facts › `claude mcp get` records that `get` prints these values. § Prompt copy › Update and remove also named `claude mcp get` for FR-4's changed-since-install case, and another reviewer reworded that in parallel this round to cite the entry in `~/.claude.json`.
- MEDIUM | manifest trust | plan Design › Install flow (manifest paragraph); FR-1 ("a file of the same name that this skill's manifest does not record"); FR-4 | `.installed-manifest.json` sits in `~/.claude/skills/<slug>/`, which the skill folder copy writes from the author's files. Nothing leaves out an `.installed-manifest.json` that the source folder holds. Normally the client's own manifest write overwrites it after the commands are copied. If the run stops between the folder copy and that write, for example because a command copy fails or the session ends, the author's file stays. **Attack path:** the author ships a manifest that records `commands: ["commit.md"]` and agent `code-reviewer.md`, the names of the user's own files → the install stops after the copy → the user runs `install <slug>` again, which runs `update` because the manifest exists → FR-1 no longer counts the user's `commit.md` as a clash, so the author's command overwrites it with no question, because commands install without one → `remove` later deletes the user's files, and its confirmation does not list commands. A forged server record that matches a predictable configuration, such as `npx @playwright/mcp@latest`, turns the user's own server into a `(changed: was …)` item in the question, which hides that the server is the user's own. **Status:** amended (design): the copy leaves out a source `.installed-manifest.json`, as it leaves out `.claude-plugin/`.
- MEDIUM | `~/` path form (Round 2) | plan Design › Copy rule, `stdio` row; FR-4; § Prompt copy flag line ("in any form FR-4 lists (absolute, `${HOME}/…` or `~/.claude/skills/<slug>/`)") | In Round 2, FR-4 named `~/` as "the only form" because it assumed the Copy rule refused every `${`, but the Copy rule allows `${HOME}`. Another reviewer corrected that in parallel this round and measured that `~` is not expanded, but kept `~/` as a form "which the program it is passed to may expand itself", and the Copy rule still accepted it. The probe shows the consequence: a program that does not expand `~`, such as `/bin/sh`, or a `command` itself, resolves the path against the directory the session started in. **Attack path:** a skill names `~/.claude/skills/<slug>/serve.sh` → the question says `Runs ~/.claude/skills/<slug>/serve.sh from this skill's folder` → the user agrees → another member of the user's group creates `~/.claude/skills/<slug>/serve.sh` inside a shared experiment or `$SCRATCH` directory → each session the user starts there runs that file as the user. The file the user agreed to is not the file that runs, and the flag line says it is. **Status:** amended (design). The Copy rule refuses a `stdio` `command` or argument that starts with `~` or holds `=~`, and `${HOME}/` names the same path. FR-4 and the flag line no longer list `~/`. Measured facts records the relative-path run, the fixture gains `akh-test-tilde`, which the client must refuse, and § Prompt copy and the create-a-skill guide row gain the reason.
- MEDIUM | FR-5 `--continue` (Round 2) and staged install | plan FR-5 ("a reply sent later into the same session, such as `claude -p --continue \"<reply>\"`, is a reply given after the listing"); Design › Staged install and #006 | A reply can now arrive in a later process. In a Cogito session it can also arrive on another machine: `~/.claude` (and with it `~/.claude/projects/`) is shared, while `mktemp -d` puts the staged clone under a per-node `/tmp`, because `TMPDIR` is unset on `sdfiana008`. A model that found the clone gone, cloned again and went on would install, for an unpinned skill, whatever the default branch held at that point. **Status:** amended by another reviewer in parallel this round: a reply that finds the staged clone gone stages again and asks again. The new question's reach line then names the new machine's `~/.claude.json`, so no separate check is needed. No amendment from this reviewer.
- LOW | FR-5 `--continue` supplied by a non-user | plan FR-5 | A `--continue "yes"` can come from any process that runs as the user, including a model in another session that drives `claude -p`, which is the subagent case in another form, and which the client cannot detect. No privilege is gained, because such a process can already run `claude mcp add` itself, and no other account can write the session. The question appears in the first run's output in full. This is the residual risk that Round 2's DR Decision 2 accepted, which the user accepted. **Status:** no amendment.
- LOW | FR-4 file-changed mark | plan FR-4; § Prompt copy flag line | The mark covers only the file named on the command line. A `serve.sh` that runs `exec python3 "$(dirname "$0")/impl.py"` lets `impl.py` change while the server shows `(unchanged)`. A malicious author has equal routes the mark can never see, such as fetching code at run time, so the mark is a signal for honest changes and not a control. This dates from Round 1. **Status:** no amendment; see O1.
- LOW | path traversal in the skill-folder flag line | plan § Prompt copy flag line ("names a path inside `~/.claude/skills/<slug>/`") | A textual match accepts `${HOME}/.claude/skills/<slug>/../<other>/run.sh`, which labels a file in another skill's folder as "from this skill's folder". The raw path, `..` included, is shown in full on the `Runs:` line. **Status:** no amendment; see O2.

**Unverified Leads**

- That a running session starts a `stdio` server in the session's directory, as `claude mcp get` did under `env -C`. If it starts the server elsewhere, the `~` refusal is defence in depth: an unexpanded `~/…` still never names the home directory.
- How often S3DF group and experiment directories are writable by other members of the group. The `~` attack needs one such directory. Without one, the refusal still stops a flag line that would wrongly call the file the skill's.
- That the manifest can be left behind in practice. That needs a run to stop between the skill folder copy and the client's first manifest write. The plan does not say whether a refused command copy aborts the run, so this reviewer could not show that an author can cause the stop on purpose.

**Opportunities**

- O1: For a server whose command line names a file in the skill folder, FR-4 could mark the server changed when any file in that folder differs, not only the named one. That would close the `exec "$(dirname "$0")/impl.py"` route to an `(unchanged)` mark.
- O2: The flag line could match "inside the installed skill folder" after resolving `.` and `..`, so that a path that leaves the folder is not called the skill's.

**Decisions Required**

*Decision: a leading `~` in a `stdio` server's command line*
- **Severity:** defaulted
- **Question:** May a `stdio` server's `command` or arguments start a path with `~`?
- **Options:** A) No: refuse `~` at the start of `command` or an argument, or after `=`, and have authors write `${HOME}/` (the plan as amended). B) Refuse `~` only in `command` and allow it in arguments for programs that expand it themselves. Option B keeps the relative-path run for `/bin/sh`, `python3` and any program that does not expand it, and keeps the flag line's false label. C) Allow it, as the plan read before this round.
- **Assumed:** A, because `${HOME}/` names the same path, is expanded by Claude Code, and is measured to work.
- **Impact if wrong:** a server whose program expands `~` itself is refused, with a message that gives the reason. Its author changes `~/` to `${HOME}/`.

**Amendments**

- design: FR-1 — the clash test reads only `claude mcp get`'s exit status and `Scope:` line, because `get` prints the existing entry's environment and header values in full. Measured facts › `claude mcp get` records this, with how it was measured.
- design: Design › Install flow — the skill folder copy leaves out any `.installed-manifest.json` in the source folder, as it leaves out `.claude-plugin/`, because FR-1, `update` and `remove` trust that file's records.
- design: Design › Copy rule, `stdio` row — `command` or an argument that starts with `~` or holds `=~` refuses the server. FR-4 and the skill-folder flag line drop the `~/` form. Measured facts › `~` and `$VAR` records that an unexpanded `~/…` ran a planted file relative to the session's directory. § Prompt copy › Messages gains the reason, the create-a-skill guide row in the Definition of Done names the refusal, and the fixture gains `akh-test-tilde`.

TOTAL: 3 design, 0 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-ux-review — Round 3 (PASS WITH WARNINGS)</summary>

# Round 3 — UX review — #051 client confirms MCP servers and agents

**Summary**

| Dimension | As received (Round 3) | After amendments | Key Gap |
|-----------|-------|-------|---------|
| Discoverability | 6/10 | 6/10 | Unchanged: what a decline left out is visible nowhere after the install |
| First-Use Clarity | 8/10 | 8/10 | None new |
| Documentation Quality | 7/10 | 7/10 | None new |
| Error UX | 7/10 | 8/10 | The value-type refusal had no reason; `remove` told a user a server they had removed "stays" |
| Workflow Fit | 7/10 | 7/10 | None new |
| Trust & Reliability | 7/10 | 7/10 | An `update` that drops a server removed it without notice; now announced |
| **UX Readiness Score** | **7.0/10** | **7.2/10** | |

**Verdict:** UX WARNINGS, computed from the after column. No blocking defect remains.

- § Prompt copy › Update and remove matches engineering's `update` semantics: `no` removes the items the user agreed to before, numbers keep or add, and `cancel` is the safe answer and keeps the old install.
- Four defects would have shown the user something false or removed a server without notice. A value-type refusal had no reason, and the nearest one was false. The "changed since" condition named `claude mcp get`, which FR-4 rules out because it starts the server. An item the new version drops was removed without a word. A server the user had already removed was reported as "stays", with a command that fails. Each is amended.
- Every other new refusal (`${…}` limits, inline agent servers, transport, name, FR-2, the cross-member clash) has its message.
- One defaulted decision: an `update` whose only change is a removal prints a notice and does not ask.
- Not a UX defect, flagged for engineering and security: under `claude -p`, FR-5's "as after `cancel`" can delete the staged clone before a `--continue` reply arrives.

**Issues**

- MEDIUM | Prompt copy › Refused under Design › Copy rule | Research's Round 2 value-type rule (Copy rule: "`command` and `url` must be strings, `args` a list of strings, and `env` and `headers` maps whose values are strings, or the server is refused before the question and the message names the field") has no reason in the message row. The nearest reason, `it sets <field>, which this client does not add`, is false for `env`, `args` or `headers`, which the client does add. An implementer following § Prompt copy, which wins over paraphrase, either improvises or prints the false reason. Amending: a reason for a value of the wrong type.
- MEDIUM | Prompt copy › Update and remove | The "changed since" message's condition reads "a server whose configuration `claude mcp get` no longer matches the manifest's record", while FR-4 says "`claude mcp get <name>` cannot make this check: it shows only the scope that wins in the current directory, prints `args` joined by spaces, and starts the server for a health check". § Prompt copy wins where a paraphrase differs, so an implementer can run `claude mcp get` during `remove`, which starts the server's command and can report a false match. Amending: the condition names the entry in this session's `~/.claude.json`, as FR-4 does.
- MEDIUM | Prompt copy › Update and remove | Engineering's `update` semantics hold in the copy: `no` "would remove every item the user agreed to before, whether marked changed or unchanged", the reply line says `no` "also removes the ones you added before", numbers are "to keep or add", and `cancel` keeps the old install. One gap remains: a server or agent file the old install added that the new version no longer lists is removed with the old install (FR-4, engineering's Round 2 decision), but the question has no mark for it, and the `Removed <items>` line covers only an item "the reply leaves out". The user replies `yes` without being told a server they rely on will go, and may not be told afterwards. When the new version brings nothing left to ask about, no question appears and the removal is silent. Amending: a notice before the question, or in its place, and the `Removed` line covers these items.
- LOW | FR-4 › a recorded server the user already removed | A recorded server with no entry at the recorded scope fails FR-4's match check, so `remove` prints `MCP server "<name>" has changed since <slug> added it, so it stays. If you no longer want it, run claude mcp remove --scope <scope> <name>.` Both halves are false: nothing stays, and the command fails because there is no such server. In `update` the same server is marked `(unchanged)`, because the manifest records it and the new configuration matches the record, though it is not set up. A user who removed a failing server by hand and then runs `remove` hits this. Amending: such a server counts as already removed, and `update` marks it `(new)`.
- INFO | Prompt copy › Messages › new refusals | Every other refusal added in Round 2 has words: the `${…}` limits (the `http`/`sse` and `stdio` reasons, with `${HOME}` allowed), inline agent servers (`Left out agent "<agent>": its MCP server "<name>"` plus the reason, with `it sets <field>` covering a field beyond `type` and the copied ones), a non-`stdio`/`http`/`sse` transport, the `name` pattern, FR-2, FR-6, the subagent case, a missing `claude`, `add-json` failing, and security's cross-member clash in the skillset question.
- INFO | FR-5 › `claude -p` | The copy matches research's change: the subagent row says a `claude -p` run gets no line and ends at the question, AC-13 and T1 expect the transcript to end with the question, and the guide row says a reply can arrive through `claude -p --continue`. Not a UX defect, flagged for engineering and security: FR-5 says the `-p` run ends "as after `cancel`", and `cancel` deletes the clone (Install flow). If the staged clone is gone when a `--continue` reply arrives, the plan does not say whether the client re-clones and asks again or installs from a new clone the user has not seen, which matters for a skill without a `pinned_commit_sha`.
- INFO | Prompt copy › escapes | Security's Unicode rule (Zl, Zp, Cf as `\uXXXX`) covers every filled-in value, including `<description>`, `Declares:` and the messages. No user-facing gap.

**Opportunities**

- The Test Plan has no N row for an `update` whose new version drops a server the old install added, or for `remove` after the user removed a recorded server by hand. Either could join N9 or N16 without a new fixture item. Not amended: the round bar excludes test additions that no defect requires.
- When `update` meets a server the user changed since install, it prints both the Name clash message and the "has changed since" message for the same server. Neither is false. Merging them would read better, but that is wording.

**Decisions Required**

*Decision: an `update` whose only change to servers and agents is a removal*
- **Severity:** defaulted
- **Question:** When the new version drops a server or agent the old install added and brings nothing else to ask about, does `update` ask before removing it?
- **Options:** A) No question; `update` prints the "no longer brings" notice in the question's place and goes on, as any `update` with nothing to ask does. B) Ask "Update <slug> and remove these? Reply yes or cancel."
- **Assumed:** A, in § Prompt copy › Update and remove. The user asked for the update, and the new version of the skill no longer uses the item.
- **Impact if wrong:** A user who called that server's tools from their own work loses it without a chance to cancel, and must add it again by hand with `claude mcp add`.

**Amendments**

- precision: § Prompt copy › Messages › Refused under Design › Copy rule — a reason for the value-type refusal: `its <field> is not <a string | a list of strings | a map of names to strings>, the only form this client adds`.
- precision: § Prompt copy › Update and remove — the "has changed since" message's condition names the entry in this session's `~/.claude.json` (FR-4), not `claude mcp get`, which FR-4 rules out because it starts the server and joins `args`.
- design: § Prompt copy › Update and remove — for each server and agent file the old install added, the new version no longer lists, and FR-4 removes, `update` prints `The new version of <slug> no longer brings <items>, so updating removes them.` before the question, or in its place when nothing is left to ask about; the `Removed <items>` closing line covers these items.
- precision: FR-4 — a recorded server with no entry at the recorded scope counts as removed: it is not listed as changed, `remove` drops its record and runs nothing for it, and `update` marks it new.

TOTAL: 1 design, 3 precision

**Status**

PASS WITH WARNINGS

</details>
