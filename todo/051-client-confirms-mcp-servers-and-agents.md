# TODO #051 — Client Asks Before It Adds an MCP Server or an Agent, and Keeps Credentials Out of Them

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open (board review UNSTABLE 2026-10-15; narrowing in progress)
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Provenance

**Raised by:** Cogito (`slaclab/cogito`) TODO #200, hub request H-7, 2026-10-14, after Cogito's Open Question 1 left the control over MCP servers and agents to this client.

**References:** Relationship to Other Tasks gives each related task and why it matters.

---

## Problem Statement

`/agent-knowledge-hub install <slug>` (`skill/SKILL.md` › Install, step 4) writes every component a
skill's `plugin.json` lists: skill folders into `~/.claude/skills/<slug>/`, commands into
`~/.claude/commands/`, agent files into `~/.claude/agents/`, and MCP servers through
`claude mcp add <name> <command> [args...]`. It asks the user nothing beyond the install itself.

Three routes let what an install writes act long after the install, in every later session of the account:

- **An MCP server added with `claude mcp add`** is either a `stdio` command that runs as the user,
  with every file the user can read in reach, or an `http` server. An `http` server added with a
  static `--header` puts that header, and any token in it, in `claude mcp add`'s arguments, where
  other users of a shared node can read it from `/proc/<pid>/cmdline`, and in `~/.claude.json`.
- **An agent file in `~/.claude/agents/`** may declare `mcpServers`, `hooks` and `permissionMode`,
  which Claude Code honours for agents in that folder; hooks there run, and inline `mcpServers`
  there connect, without a folder-trust check (Claude Code documentation, `sub-agents`). Claude Code
  ignores all three fields for an agent that a plugin brings.
- **A skill folder that carries `.claude-plugin/plugin.json`**, once copied into
  `~/.claude/skills/<slug>/`, loads in every later session as the plugin `<name>@skills-dir`,
  enabled unless its manifest sets `defaultEnabled: false`, with the MCP servers and hooks its
  manifest, `.mcp.json` and `hooks/hooks.json` declare. Claude Code asks nothing first for a plugin
  under `~/.claude/skills/` (Claude Code documentation, `plugins/loading`; `claude plugin init --help`
  on 2.1.281). This route needs no `claude mcp add` and no agent file, so a confirmation that
  covers only those two misses it.

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
| A listed `http` server needs the user's S3DF token | Nothing stops the token going into `--header` | The client never puts a credential in arguments or in `~/.claude.json`; it refuses a server marked `auth.type: slac-sso` and says why (FR-2) |
| In a Cogito session, the user runs the install on one machine and uses another | The skill folder appears on every machine, because `~/.claude` is shared, but the server only on the first: `claude mcp add` with no `--scope` records it for the current project in that machine's `~/.claude.json` (measured by Cogito on Claude Code 2.1.281) | The client says where the server lands before adding it |
| A skill folder carries `.claude-plugin/plugin.json` with `mcpServers` or `hooks` | The client copies the folder into `~/.claude/skills/<slug>/`, and Claude Code loads it as a plugin with those servers and hooks, unasked | The client writes no plugin manifest under `~/.claude/skills/<slug>/` (FR-6) |

---

## Goals

1. No MCP server or agent file reaches the account unless the user, after seeing it in full, replies yes to it.
2. No credential of the user's reaches `claude mcp add`'s arguments or `~/.claude.json`, and the configuration the client writes sends none to a web service: it adds no server that needs the S3DF token and no `${…}` reference in an `http` or `sse` server's address or headers (Design › Copy rule). A `stdio` server runs as the user and can read what the user can.
3. The user is told where each server applies, and `update` and `remove` change only what the client added.
4. A copied skill folder never loads as a plugin.

## Non-Goals

- Judging what a server or agent does. The client shows it and the user decides (§ Prompt copy).
- The skill folder's own `SKILL.md` and the command files the install writes. Their frontmatter, such as `allowed-tools` and `hooks` (both honoured in a skill's frontmatter, Claude Code documentation, `skills`), and their inline shell act only while that skill or command is in use, not at every session start, and they install without a question, as today. "In use" is not only when the user asks: Claude invokes a skill on its own when a task matches its description, and FR-1's refusal still installs both, so a user who declines a server can receive comparable reach through them. The ADR in the Definition of Done states this residual risk next to the model-compliance one.
- Storing server or agent declarations in the catalog. That is #023; the clone stays the source for FR-1 either way (Design › Staged install and #006).
- Servers the earlier client added. FR-4 tells the user where they are; nothing removes them automatically.
- The S3DF token's audience (#050 › Token exposure).

---

## Requirements

| ID | Requirement |
|---|---|
| FR-1 | After step 3 reads `plugin.json` and before step 4's first write, the client lists every agent file and MCP server the skill brings and asks the user once, in the words of § Prompt copy. The reply adds all of them, none, or some chosen by number, or cancels the install, which then writes nothing. A skill that brings neither gets no question. For an MCP server it shows the name, the transport, the command with its arguments or the URL, and every environment variable or header its entry sets, because a value such as `NODE_OPTIONS=--require <file>` or `LD_PRELOAD=<file>` runs code that the command line does not show. For an agent it shows its whole frontmatter, every key and value, with `mcpServers`, `hooks`, `permissionMode` and `tools` first, because a fixed list of keys to show would hide any key Claude Code adds later, and `description` decides when Claude hands work to the agent; an agent that declares no `tools` is shown as having every tool the session has, less any its `disallowedTools` names, because that is what it gets (Claude Code documentation, `sub-agents`). It adds nothing of either kind without an explicit yes; a refusal still installs the skill folder and its commands, and says what was left out, that the parts of the skill that use it will not work, and that `/agent-knowledge-hub update <slug>` asks again. When `claude mcp get <name>` exits 0, which it does for a server of that name at user scope or, for the session's directory, at local or project scope (the client reads only its exit status and its `Scope:` line, because the rest of its output shows the entry's environment variables and headers in full, which can hold the user's own tokens; Measured facts › `claude mcp get`), or `~/.claude/agents/` or `~/.claude/commands/` already holds a file of the same name that this skill's manifest does not record, the client does not replace it: it names the clash before the question and leaves that component out of it. A server is not a clash when this skill's manifest records it for this session's `~/.claude.json` and its entry there still equals the recorded configuration, the same test FR-4 applies before it removes one, because `update` asks before it removes the old install, so the skill's own server is still present when the question is built. Checking only the target scope is not enough, because a session sees one server for each name, the user's own skills call its tools by that name, and a local-scope entry overrides a user-scope one (Claude Code documentation, `mcp` › scopes). A local-scope server of the same name in another directory is not seen, and in that directory it overrides the skill's; a plugin's server is named `plugin:<plugin>:<server>` and never matches (Measured facts › `claude mcp get`). `claude mcp add` itself refuses a name already present in the scope (Measured facts) |
| FR-2 | The client never passes a credential in `claude mcp add`'s arguments, including `--header` and `-e`, and never writes one into `~/.claude.json`. It refuses, before asking, any server whose `mcp-servers` entry sets `auth.type` to `slac-sso`, the marker for a server that needs the S3DF token (Design › Copy rule), and the message says that this version of the client cannot connect a server that needs the S3DF sign-in. The S3DF token is accepted by every S3DF service (#050 › Token exposure) and the server's `url` comes from the skill's author, so handing it to such a server needs an exact origin list; no catalog skill names a SLAC endpoint for that list yet, so a client-owned `headersHelper` is deferred (Follow-ups). Every other value in a server's configuration is built under Design › Copy rule, because a `${VAR}` reference copied into an `http` server's `headers` or `url` sends that environment variable's value to the author's server at each connection, while nothing secret appears in the arguments or in `~/.claude.json` (Measured facts › `${VAR}` references) |
| FR-3 | The client passes `--scope` explicitly and tells the user, before adding, where the server will apply. A `user` or `local` server is recorded in `~/.claude.json` under `$HOME`, so its reach depends on whether `$HOME` is the account's real home (`getent passwd "$(id -un)" \| cut -d: -f6`). When it is, as in a plain S3DF login, `--scope user` applies in every project on every machine that mounts that home, and local scope in this project on those machines. When `$HOME` is a per-machine directory, as in a Cogito session (Measured facts), `--scope user` applies in every project on this machine and local scope in this project on this machine only. The client adds every server with `--scope user`, so the server reaches every directory the skill folder reaches: Claude Code's "project" is the directory a session was started in, and S3DF users start sessions from their home, from `$SCRATCH` run directories and from experiment directories, so under local scope the skill would work fully only in the directory the install ran in, and `claude mcp remove --scope local` would work only from there. The client adds each server with `claude mcp add-json` and the configuration Design › Copy rule builds, passed as that section says, never with `claude mcp add` and values from `plugin.json` among its arguments, and never with the whole `mcp-servers` entry, which would carry fields the Copy rule refuses, such as `headersHelper`. `claude mcp add` reads options among its positional arguments unless `--` ends them (its `--help` example is `claude mcp add my-server -- my-command --some-flag arg1`), so an argument such as `-s local` or `-e NAME=value` in the entry would otherwise change the scope or the environment the user agreed to, and a value holding `$(` or `;` would run when the model composes the command. The message names the file the setting goes into. It says that the skill folder itself appears on every machine that shares `~/.claude`, and, when `$HOME` is a per-machine directory, that running `/agent-knowledge-hub update <slug>` on another machine adds the server there |
| FR-4 | `update` asks FR-1's question for the new version before it removes anything, marking each item new, changed (with the value it replaces) or unchanged; a server whose command or arguments name a file inside the skill folder (by its absolute path, by `${HOME}/.claude/skills/<slug>/…`, the only form that works in a `plugin.json` written before install, because Claude Code expands `${HOME}` in `command` and `args` and passes `~` unexpanded (Measured facts › `~` and `$VAR` in a stdio server); Design › Copy rule refuses a leading `~`) also counts as changed, with `(the file <path> it runs has changed)`, when that file in the new clone differs from the installed copy, because the configuration then stays the same while the program it runs does not. This ordering means `cancel` leaves the old install as it was; this reverses today's order in `skill/SKILL.md` › Update, which removes first. The marks compare the new clone with the manifest: a server is new when the manifest has no record of it for this session's `~/.claude.json`, which includes one the user declined before, and changed when the configuration Design › Copy rule builds from the new clone differs from the recorded one; an agent is new when the manifest does not record it, and changed when the new file differs from the one in `~/.claude/agents/`. Any reply other than `cancel` sets what the updated install holds: each server and agent file the old install added and the reply leaves out is removed with the old install, and the closing message names it as removed. `remove` lists the MCP servers and agent files it will remove in its existing single confirmation, with no per-item choice. Both say when a server was added on another machine and cannot be removed from this one, and give the `claude mcp remove --scope <scope> <name>` command to run on that machine, because the manifest that records the server is in the shared skill folder and goes when `remove` runs here. `update` copies those other-machine records into the new manifest. A server counts as added elsewhere when its recorded `~/.claude.json` path differs from this session's resolved `~/.claude.json`, not when its host differs: in a plain S3DF login every machine reads the same file in the real home (FR-3), so a host comparison would refuse a removal that works, and a Cogito session and a plain login on the same host read different files. They remove only servers and agent files the manifest records, and only while the server's entry at the recorded scope in this session's `~/.claude.json` (the top-level `mcpServers.<name>` for user scope) still equals the configuration the manifest recorded, checked by a command that prints only whether the two match, because the file also holds the user's other servers and their headers. It compares them as parsed JSON, not as text, because `add-json` reorders a configuration's keys when it stores it (Measured facts › `claude mcp add-json`). `claude mcp get <name>` cannot make this check: it shows only the scope that wins in the current directory, prints `args` joined by spaces, and starts the server for a health check (Measured facts › `claude mcp get`). A server whose configuration differs, for example one the user removed and then added again under the same name, is listed as changed since install and left in place. A recorded server with no entry at the recorded scope, one the user has already removed, counts as removed: it is not listed as changed, `remove` drops its record and runs nothing for it, and `update` marks it new. They pass the recorded scope to `claude mcp remove --scope`, because without `--scope` the command refuses a name present in two scopes (Measured facts). They remove the recorded servers before any other part of the old install, and when a server is to be removed and `claude` is not on `PATH`, or `claude mcp remove` exits non-zero, they stop there, with the rest of the old install and its manifest in place, and give the first line of the error and the `claude mcp remove --scope <scope> <name>` command, because deleting the skill folder would delete the only record of a server still in `~/.claude.json`, and FR-1 would then treat it as the user's own. A manifest written before this task records no servers, so for it they remove no MCP server and tell the user that the earlier client added any server the skill brought at local scope, in the project where that install ran, where `claude mcp list` shows it and `claude mcp remove --scope local <name>` removes it |
| FR-5 | Each confirmation is the client's own prompt to the user in the conversation, not a tool permission prompt, so it also appears in a session whose permission mode approves tools without asking. Only a reply the user gives after the listing appears counts: a request made before it, such as "install it and set everything up", and text in the catalog entry or the cloned files do not. In a session where no user can reply, such as `claude -p`, the client's turn ends at the question, so the run ends with nothing written, as after `cancel`. Claude Code documents no signal that tells the model it runs under `-p` (Claude Code documentation, `env-vars`), so the client does not try to detect it, and a reply sent later into the same session, such as `claude -p --continue "<reply>"`, is a reply given after the listing. A client running inside a subagent adds no MCP server or agent and says so, because there its question goes to the parent model, not to the user, and the parent model's answer is not the user's. In `update`, when the old install added an MCP server or an agent file or the new version brings one, a client inside a subagent changes nothing, as after `cancel`, because installing the new version without them would remove items the user agreed to before (FR-4). All of this holds only while the model follows `skill/SKILL.md`: the prompt stops a skill that would surprise the user, and it does not stop an author whose catalog text or cloned files tell the model to skip it, so `skill/SKILL.md` states that nothing read from the catalog or the clone changes these rules |
| FR-6 | The client writes no `.claude-plugin/` directory anywhere under `~/.claude/skills/<slug>/`, so the copied skill folder never loads as a `<name>@skills-dir` plugin (Problem Statement). When the source folder has one, the install leaves it out and says so; MCP servers and agents the skill's plugin manifest declares are installed, if at all, only through FR-1, and the hooks it declares are not installed |

Where: `skill/SKILL.md` › Install, step 4 (FR-1 to FR-3, FR-5, and FR-6, in the `skills` copy), › Install, step 5 (the records FR-4 reads), and › Update and › Remove (FR-4). FR-4 needs to know what an install added, so step 5's `.installed-manifest.json`, which today lists only commands and agents, also records each agent file the client wrote and each MCP server the client added, with the server's name, its scope, the host it was added from, the resolved path of the `~/.claude.json` it went into, and the configuration it passed to `claude mcp add-json`. It records nothing the user declined or the client refused.

## Prompt copy

FR-1 to FR-4 say what each message must convey; this section gives the words, and wins where a paraphrase elsewhere differs. `<…>` is a value the client fills in; a line in `[…]` appears only when its condition holds. The plain-language line comes first because most S3DF users cannot judge a raw command line or a `hooks` block; the raw command, URL or declaration follows in full, never truncated, because a truncated argument is where a harmful one would hide. The client gives no yes-or-no recommendation of its own: the catalog entry and the cloned files are written by the skill's author and can steer the model's judgement, so the only warnings are the mechanical ones in the tables below.

**The install question** (FR-1). Items are numbered across the whole question.

```
<slug> (github.com/<owner>/<repo> at commit <short_sha>) also brings <N> item(s) that act on
their own in your later Claude Code sessions. The catalog does not check what they do; add
them only if you trust <owner>.

1. MCP server "<name>": a program that runs on your account
   Runs: <command> <every argument>
   Environment: <every NAME=value the entry sets | none>
   It starts with each Claude Code session and runs as <username>, so it can read and change
   every file you can and use the network as you.
   [<flag lines>, one per line]
   Applies: <reach line>

2. MCP server "<name>": a web service Claude sends requests to
   Address: <url>
   Headers: <every name: value the entry sets | none>
   Claude sends it whatever its tools are given, which can include the contents of your files.
   [<flag lines>, one per line]
   Applies: <reach line>

3. Agent "<name>": a helper Claude can hand work to on its own, when a task matches
   "<description>"
   Tools: <tool list | every tool your session has (the file does not limit them) | every tool your session has except <tool list of its disallowedTools>>
   Runs without asking you, while this agent is working: <hook lines | nothing>
   Permission mode: <mode line>
   Its own MCP servers: <an indented block like 1 or 2 for each | none>
   Available in: every Claude Code session on every machine that shares ~/.claude
   Declares: <the whole frontmatter FR-1 requires, every key and value>

Not sure? Reply no. The skill's instructions still install, you can read them in
~/.claude/skills/<slug>/, and /agent-knowledge-hub update <slug> asks you again.

Reply yes to add all of these, no to add none, the numbers to add only some (for example 1 3),
or cancel to install nothing.
```

| Placeholder | Value |
|---|---|
| flag line | `Runs <package or image> from a public registry, not from this skill's files.` when the command is `npx`, `uvx`, `pipx run`, `bunx`, `docker run` or `apptainer run`, followed by ` No exact version is given, so what runs can change without this skill changing.` when the package or image names no exact version. `This address is outside SLAC.` when the URL's host does not end in `.slac.stanford.edu`. `Runs code written into this line, not a named program; read it before you agree.` when the command is `sh`, `bash`, `zsh`, `python`, `python3`, `node`, `perl` or `ruby` followed by `-c` or `-e`. `Runs <file> from this skill's folder; an update can change that file without this line changing, and the update's question then says so.` when the command or an argument names a path inside the installed skill folder in either form FR-4 lists (absolute or `${HOME}/.claude/skills/<slug>/`). `Sets <NAME>, which changes what the program loads before it starts.` for each of `LD_PRELOAD`, `LD_LIBRARY_PATH`, `NODE_OPTIONS`, `PYTHONPATH`, `PYTHONSTARTUP`, `BASH_ENV`, `ENV` and `PATH` in the entry's environment |
| reach line | When `$HOME` is the account's real home (FR-3): `every directory you start Claude Code in, on every S3DF machine that shares your home directory (kept in <path of ~/.claude.json>)`. Otherwise: `every directory you start Claude Code in, on <hostname> only (kept in <path of ~/.claude.json>). On another machine, run /agent-knowledge-hub update <slug> there to add it.` |
| tool list | Each declared tool by name, with `Bash (runs shell commands)`, `Write` and `Edit (change files)`, `WebFetch` and `WebSearch (read the web)`, and `mcp__<server>__<tool>` shown as `<tool> from MCP server <server>` |
| hook lines | One line per hook, `<when>: <action>`, where `<action>` follows the hook's `type`: `command` is `runs <command>`; `http` is `sends what it is doing, including the tool's input, to <url>`; `mcp_tool` is `calls <tool> from MCP server <server>`; `prompt` is `asks a Claude model: "<prompt>"`; `agent` is `starts a helper with tools: "<prompt>"`; any other type is `a <type> hook, which this client does not describe; check it before you agree`. `PreToolUse` is `before it uses <matcher>` and `PostToolUse` `after it uses <matcher>`, with matcher `Bash` shown as `a shell command`, `Edit` or `Write` as `a file edit`, and an empty or `*` matcher as `any tool`; `Stop` and `SubagentStop` are `when it finishes`; any other event is `on Claude Code's <event> event` |
| mode line | Absent, `default`, or `manual`, an alias for `default`: `asks you as usual`. `acceptEdits`: `changes files without asking you`. `plan`: `reads only and changes nothing`. `bypassPermissions`: `Warning: this agent requests to run commands and change files without asking you. Claude Code 2.1.267 and later ignore the request unless your session already does that; earlier versions grant it.` Each line describes the agent under a session in `default`, `dontAsk` or `plan` mode, because a session in `bypassPermissions`, `acceptEdits` or `auto` mode runs every subagent in its own mode and ignores the agent's value (Claude Code documentation, `sub-agents` › Permission modes, read 2026-10-15; not checked by a run). Any other value: `<value>, a mode this client does not describe; check it before you agree` |

Every value the client fills in, in the question and in every message below, is shown with control characters, including newlines and terminal escapes, written as `\n` or `\xNN`, and with Unicode line and paragraph separators, bidirectional controls such as U+202E and zero-width characters (categories Zl, Zp and Cf) written as `\uXXXX`, so that a value cannot redraw or reorder the lines around it or pose as a numbered item of its own.

The agent's hook line rests on the Claude Code `sub-agents` documentation, read 2026-10-15: hooks in a subagent's frontmatter "only run while that specific subagent is active and are cleaned up when it finishes", and run for a whole session only when that session is started as the agent, with `--agent` or the `agent` setting.

**Messages** (FR-1, FR-2, FR-5, FR-6, Design › Copy rule). A name clash, a refusal, a left-out `.claude-plugin/` and a missing `claude` are known from the staged clone, so the client prints them before the question, and the question's numbers and `<N>` leave those items out; when nothing is left to ask about, the client asks nothing and installs the rest. The FR-5 message takes the question's place; the others follow the reply.

| Case | Message |
|---|---|
| `cancel` | `Nothing installed.` In `update`: `Nothing changed; <slug> stays as it was.` |
| Any other reply, or a number not in the question | `Reply yes, no, cancel, or the numbers of the items to add (1 to <the last item's number>).` The client asks again, and reads no such reply as yes |
| Closing message, when anything was left out by the reply or before the question | `<slug> is installed without <items>. The parts of the skill that use them will not work.` followed, when the user declined an item or FR-5 left one out, by ` To be asked again, run /agent-knowledge-hub update <slug>.` |
| `claude mcp add-json` exits non-zero | `Left out MCP server "<name>": claude mcp add-json failed with "<the first line of its error output>". To try again, run /agent-knowledge-hub update <slug>.` |
| Name clash (FR-1) | `Left out <MCP server \| agent \| command> "<name>": you already have one with that name, and the client does not replace it. Yours is unchanged.` For an MCP server in `update` of a manifest that records no servers (FR-4), where the clash is most likely the server the earlier client added from this skill: `Left out MCP server "<name>": one with that name is already set up at <scope> scope, perhaps by the earlier version of this client. To replace it with this skill's, run claude mcp remove --scope <scope> <name>, then /agent-knowledge-hub update <slug>.` |
| Refused under FR-2 | `Left out MCP server "<name>": it needs your S3DF sign-in, and this version of the client cannot connect a server that needs it. Your sign-in was not used. The limit is this client's, not the skill's: if you need this server, say so in the #comp-sdf Slack channel or at https://github.com/slaclab/agent-knowledge-hub/issues.` The contact is the one `frontend/app/guides/troubleshooting/page.tsx` › "Who do I contact if something is broken?" gives, and such a request is the signal Follow-ups waits for |
| Refused under Design › Copy rule | `Left out MCP server "<name>": <reason>. Nothing was added for it; you can tell the skill's author at <repo_url>/issues.` For an agent refused for one of its own servers, the message starts `Left out agent "<agent>": its MCP server "<name>"` and goes on with the reason. For an agent refused for an `http` hook, it is `Left out agent "<agent>": its <event> hook would send the values of <the allowedEnvVars names> from your environment to <url>. Nothing was added for it; you can tell the skill's author at <repo_url>/issues.` The reason is `its address or a header contains ${, which would send a value from your environment to <url>`, `its command or an argument contains ${<VAR>}, which would put a value from your environment on a command line that other users of this machine can read`, `its command or an argument starts a path with ~, which Claude Code does not read as your home directory, so the file run could be one another user placed in the directory you start Claude Code in`, `it sets <field>, which this client does not add`, `its <field> is not <a string | a list of strings | a map of names to strings>, the only form this client adds`, `its transport <transport> is not one this client adds`, or `its name is not letters, digits, - and _ starting with a letter or digit` |
| `.claude-plugin/` left out (FR-6) | `Left out <slug>'s .claude-plugin/ folder, so Claude Code does not load the skill as a plugin. Any MCP servers or hooks it declares are not installed.` |
| Inside a subagent (FR-5) | `Left out <items>: the client is running inside a subagent, which cannot wait for your reply, so it adds no MCP server or agent. To add them, run /agent-knowledge-hub update <slug> in a session where you can reply.` In `update` (FR-5): `Nothing changed; <slug> stays as it was. The client is running inside a subagent, which cannot wait for your reply. Run /agent-knowledge-hub update <slug> in a session where you can reply.` A `claude -p` run gets no such line: its turn ends at the install question (FR-5) |
| `claude` not on `PATH` | `Left out MCP server "<name>": the claude command is not available in this session, so the client cannot add it. Run /agent-knowledge-hub update <slug> from a session where claude --version works.` |

**Update and remove** (FR-4). `update` shows the install question with `(new)`, `(changed: was <old value>)`, `(the file <path> it runs has changed)` or `(unchanged)` after each item's title. In `update`, `no` would remove every item the user agreed to before, whether marked changed or unchanged, so `cancel` is the safe answer, and the question's last two paragraphs read:

```
Not sure? Reply cancel, and <slug> stays as it is now.

Reply yes to install the new version with all of these, no to install it with none of them
(this also removes the ones you added before), the numbers to keep or add only some (for
example 1 3), or cancel.
```

For each server and agent file the old install added, the new version no longer lists, and FR-4 removes, `update` prints `The new version of <slug> no longer brings <items>, so updating removes them.` before the question, or in its place when nothing is left to ask about. When the reply leaves out an item the old install added, or the new version no longer brings it, the closing message adds `Removed <items>, which the earlier version of <slug> added.` Both show, for a server recorded in another `~/.claude.json`: `MCP server "<name>" was added on <host> to <recorded path>, which this session does not use, so it stays there. To remove it, run claude mcp remove --scope <scope> <name> on <host>, in a terminal whose ~/.claude.json is <recorded path>.` Both show, for a server whose entry in this session's `~/.claude.json` no longer matches the manifest's record (FR-4): `MCP server "<name>" has changed since <slug> added it, so it stays. If you no longer want it, run claude mcp remove --scope <scope> <name>.` For a manifest that records no servers (FR-4): `<slug> was installed by an earlier version of this client, which did not record MCP servers, so none is removed. That version added any server the skill brought only for the directory the install ran in; there, claude mcp list shows it and claude mcp remove --scope local <name> removes it.`

**The skillset question** (Design › Staged install and #006). When at least one member brings an MCP server or an agent that is still left to ask about after the messages printed before the question, this replaces #006 › FR-7's "Install these N of M skills from skillset <slug>? (y/N)", because #006's No installs nothing while FR-1's `no` installs the skills without their items, and one question cannot carry both. When none is left, because no member brings either or every one was refused or clashes, #006's question is asked unchanged, after those messages. Messages' rule that the client asks nothing when nothing is left to ask about applies to one skill's install only: #006 › FR-7 › Confirm rule always confirms a skillset's member list, because the skillset's owner chooses it.

```
Skillset <set-slug> will install these <N> of <M> skills:
<#006's line for each member it will install, in its order>

<the messages printed before the question, under the member each belongs to>

<for each member that brings items: the install question's first paragraph for that
member, then its items>

Not sure? Reply no. Every skill's instructions still install, and
/agent-knowledge-hub update <member slug> asks you again about that skill's items.

Reply yes to install the <N> skills with all of these items, no to install them with none,
the numbers to add only some (for example 1 3), or cancel to install nothing.
```

Here `<N>` and `<M>` are #006's skill counts; each member's first paragraph keeps its own item count. Items are numbered from 1 across every member, in member order, so one number names one item. A server, agent or command name that an earlier member in the list also brings is a name clash for the later member, reported before the question, because no member is added before the question and FR-1's clash check would otherwise pass both. Its message is `Left out <MCP server | agent | command> "<name>" from <later member>: <earlier member> in this skillset also brings one with that name, and if you add that one, <later member> will use it instead.`, not the Name clash message, because the user has no such item yet, and because the skillset's owner sets the member order (#006 › FR-2f), so the earlier item may come from an author the later member's author has never seen. After the reply, each member's messages print at its `[i/M]` line, and `cancel` prints #006's `Nothing installed.`

## Design

### Install flow

Requirements state what each step must do; this diagram gives only the order, and Requirements win where the two differ.

```
GET /api/skills/<slug>                      repo_url, skill_path, pinned_commit_sha
  │
clone into a temporary directory            nothing written under ~/.claude yet
  │
read plugin.json and each listed agent file the clone is the only source for FR-1's lines
  │
Copy rule, FR-2 and FR-1 clash checks      a refused or clashing item is reported, not asked about
  │
FR-1 question                               cancel → delete the clone; "Nothing installed."
  │
copy the skill folder without .claude-plugin/ (FR-6), then commands
  │
each approved agent file  → write, then record it in the manifest
each approved MCP server  → claude mcp add-json --scope user, then record it on exit 0
  │
install event, success line naming what was left out
```

The manifest is written once the commands are copied and rewritten after each agent file and each server, each time with every record so far, not once at the end, so a session that stops part-way still leaves a record of every server it added; otherwise `remove`, which removes only recorded servers (FR-4), never finds it. The skill folder copy also leaves out any `.installed-manifest.json` the source folder holds, as it leaves out `.claude-plugin/`, because the client trusts that file's records: FR-1 does not count an item it records as a clash, and `update` and `remove` remove what it records, so an author's copy left behind by a run that stops before the client's first manifest write would let the next run replace or delete the user's own command, agent or server of a recorded name. `install <slug>` for a slug whose `.installed-manifest.json` already exists runs `update <slug>`, because FR-1's clash rule would treat the skill's own server as a clash, leave it out, and write a manifest that no longer records it.

### Staged install and #006

Every question an install asks comes after the clone and before the first write under `~/.claude/` or the first `claude mcp add-json`. The temporary directory is made with `mktemp -d`, which gives it a random name and mode 0700, and it holds every staged clone and every JSON file the Copy rule writes until the run ends: the install reads them after the user's reply, so a predictable path such as `/tmp/akh-<slug>`, which another user of a shared node could create first and keep write access to, would let that user replace an agent file or a server's configuration between the question and the write. When the reply arrives and the temporary directory or a staged clone in it is gone, for example after `claude -p --continue` on another machine (FR-5) or a `/tmp` clean-up, the client stages again and asks again, because a fresh clone of an unpinned skill can hold a commit the question did not show. For `install skillset`, #006's loop clones each member it will install into the temporary directory, then asks one question that lists each member with FR-1's lines for its servers and agents, in the words of § Prompt copy › The skillset question, then installs every member from its staged clone with no further question. git runs no hook from a cloned repository and fetches no submodule without `--recurse-submodules`, so cloning before the user agrees runs nothing from the repository. Relationship to Other Tasks › #006 gives the change #006 needs.

| Rejected | Fact that rules it out |
|---|---|
| The catalog serves server declarations and agent frontmatter, and #006 asks from those before cloning | `refetch()` in `backend/app/services/skill.py` rewrites `has_mcp_server`, `agent_count` and `agent_names` from the default branch's HEAD while installs clone `pinned_commit_sha`, and an unpinned skill clones whatever the default branch holds at install time, so catalog data can describe a different commit from the one installed. The scanner never reads agent files, because `file_manifest` lists only the top level of `skill_path`. The client would still have to check the clone, and storing declarations is #023's backend work |
| #006 keeps its question before the first clone, and FR-1 asks again when each member installs | It ends #006 FR-7's promise that a user who confirms can leave the run unattended, and a run whose members bring servers stops once per such member |

### Copy rule

The client builds each MCP server's configuration only from the fields below of the server's `mcp-servers` entry, copied as written, plus `type` set to the transport (`stdio`, `http` or `sse`) and, for a `stdio` entry with no `args`, `args` set to `[]`, and adds it with `claude mcp add-json --scope user`. `add-json` refuses a configuration with a `url` and no `type`, and `claude mcp get` prints no command for a stdio one without it; it stores a stdio configuration that has no `args` with `"args": []`, so without that default the recorded configuration would never equal the stored entry and FR-4 would leave the skill's own server in place (Measured facts › `claude mcp add-json`). It never expands a `${…}` reference and never fills a value from a file, the environment, or the user's reply.

| `transport` (absent means `stdio`) | Copied into the configuration | Server refused when |
|---|---|---|
| `stdio` | `command`, `args`, `env` | `command` or an argument contains a `${…}` reference other than `${HOME}`, because Claude Code expands `${VAR}` in `command` and `args` as well as in `env` (Claude Code documentation, `mcp` › Environment variable expansion; Measured facts › `${VAR}` references, for `env` and `args`), and the expanded value then sits in the server's command line, which other users of a shared node can read (Problem Statement). `${HOME}` is allowed there because its value is a path, not a secret, and a server run from the skill folder needs it. `command` or an argument that starts with `~` or holds `=~` also refuses the server: Claude Code does not expand `~` (Measured facts › `~` and `$VAR` in a stdio server), so unless the program expands it, the path is read from the directory the session started in, where another user of a shared directory can create `~/.claude/skills/<slug>/…` and have it run as the user while the question says the file is the skill's; `${HOME}/` names the intended path and is expanded. A `${…}` in `env` is allowed: the program inherits Claude Code's whole environment (Measured facts › `${VAR}` references), so the reference gives it nothing it does not already have |
| `http`, `sse` | `url`, `headers` | `url`, a header name or a header value contains `${`, because Claude Code expands it from its own environment and sends the value to the author's server (Measured facts › `${VAR}` references) |
| any other value | — | always |

- The entry's `name`, `transport`, `description`, `auth` and `access` fields are read, not copied. `auth.type` set to `slac-sso` is FR-2's marker for a server that needs the S3DF token, which FR-2 refuses.
- `command` and `url` must be strings, `args` a list of strings, and `env` and `headers` maps whose values are strings, or the server is refused before the question and the message names the field. `add-json` refuses any other value only after the user has agreed (Measured facts › `claude mcp add-json`), and #023 › plugin.json extended schema describes `env` as a map of name to `{description, required, example}`, which is such a value.
- Any other field, such as `headersHelper` or `oauth`, refuses the server and the message names the field. A `headersHelper` from the entry is a command that would run as the user at each connection without appearing in FR-1's list as one, and a field the client does not know is one whose effect FR-1 cannot describe.
- An agent file is written as its author wrote it, so the client also applies the table and the field rule above to each inline server in an agent's `mcpServers` frontmatter (an entry whose value is a configuration, not a name), reading its `type` as `transport` and allowing no field beyond `type` and the ones the table copies for that transport. One refused inline server refuses the whole agent before the question, and the message names the server and the field. Inline definitions use the `.mcp.json` schema (Claude Code documentation, `sub-agents`), and an agent in `~/.claude/agents/` connects them without a folder-trust check (Problem Statement), so without this rule an agent the user agreed to could send a `${GITHUB_TOKEN}` header to its author's server, or run a `headersHelper` that reads `~/.s3df-access-token`, at each start.
- The client also refuses, before the question, an agent with a hook of `type: http` that sets `allowedEnvVars`. Claude Code resolves each variable that list names into the hook's `headers`, as `$VAR` or `${VAR}`, and POSTs the event's JSON input, which holds the tool's input, to the hook's `url` (Claude Code documentation, `hooks` › HTTP hook fields, read 2026-10-15; not checked by a run), so it is the same leak as a `${…}` header on an inline server. An `http` hook without `allowedEnvVars` resolves no variable and is asked about like any other hook.
- `name` must match `^[A-Za-z0-9][A-Za-z0-9_-]*$`, or the server is refused. The first character cannot be `-`, because `claude mcp` reads options among its positional arguments (its `--help` example for a stdio command with flags is `claude mcp add my-server -- my-command --some-flag arg1`), so a name such as `-sproject` would be read as `-s project` and override the `--scope user` the user was told about. The configuration's values come from the skill's author, so the client writes the JSON into a file in the temporary directory with its file-writing tool, not with a shell `echo`, and runs `claude mcp add-json --scope user '<name>' "$(cat <file>)"`. The shell does not expand the output of a command substitution again, so a `$(…)` or `'` in a value never reaches it, the same concern #006 › FR-7 › Argument rule handles for `repo_url`.

### Trade-offs

| Decision | Gains | Costs | Accepted because |
|---|---|---|---|
| Clone before asking | One question per run, made from the bytes that will be installed | A declined run has cloned for nothing | Clones run no repository code, and the network cost is the same for an accepted run |
| Copy rule refuses `${` in `http` and `sse` servers, and any reference but `${HOME}` in a `stdio` server's command and arguments | No local secret leaves through Claude Code's own expansion, to a web service or onto a command line other users can read | A server whose author expects a `${VAR}` header or argument from the user cannot be installed by the client | The user can still add it by hand, where they see the reference themselves |
| Refuse servers that need the S3DF token (FR-2) | No token reaches an MCP server, and there is no `headersHelper` to secure | A SLAC MCP server that needs the token cannot be installed by the client | No catalog skill names such a server; the deferred design is in Follow-ups |
| Unknown fields refuse the server | Fails closed when Claude Code adds a configuration field | A valid server with a newer field is refused until the client learns the field | A refusal is visible and says which field; a pass-through would not be |

## Measured facts — measured 2026-10-14 on `sdfiana008`, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| Claude Code version | 2.1.281 | `claude --version` |
| `claude mcp add` options | `-s, --scope` with `local`, `user`, or `project`, default `local`; `-H, --header` and `-e, --env` put header and environment values in the command's arguments; there is no option for `headersHelper` | `claude mcp add --help` |
| `claude mcp add-json` | Takes `<name> <json>` and the same `--scope`; the JSON is the server's configuration. It stores a `headersHelper` key as given, and drops an unknown key without an error. It refuses, with `Invalid configuration: : Invalid input` and exit 1, a configuration that has a `url` and no `type`, one that names the transport as `transport` instead of `type`, and one whose `env` value is an object such as #023's `{"description": …, "required": true}`; a stdio configuration without `type` is accepted, but `claude mcp get` then prints no command or arguments for it (measured 2026-10-15). It accepts every configuration Design › Copy rule builds, and stores it with its top-level keys reordered to `type`, `command`, `args`, `env` and, for a stdio configuration with no `args`, with `"args": []` added: `{"type":"stdio","command":"/bin/true"}` is stored as `{"type":"stdio","command":"/bin/true","args":[]}`; an absent `env` or `headers` stays absent (measured 2026-10-15) | `claude mcp add-json --help`; `add-json -s user t1 '{"type":"http","url":"https://example.invalid/mcp","headersHelper":"/bin/echo {}"}'` with `HOME` and `CLAUDE_CONFIG_DIR` set to a scratch directory, then reading that directory's `.claude.json`; on 2026-10-15 the same setup with `{"url":…,"headers":{…}}`, `{"transport":"http","url":…}` and `{"type":"stdio","command":"/bin/true","env":{"A":{"description":"x"}}}` |
| Where `-H` and `-e` values end up | `-H` is stored under the server's `headers` and echoed by `claude mcp add` as `Headers: {...}` on standard output, so it also reaches the session transcript; `-e` is stored under the server's `env` | Same scratch setup: `claude mcp add -s user --transport http t3 <url> -H "X-Test: v"` and `claude mcp add -s user t2 -e FOO=v -- /bin/true` |
| Name clashes | `claude mcp add` exits 1 with `MCP server <name> already exists in user config` for a name already in that scope; `claude mcp remove <name>` with no `--scope` exits 1 with `exists in multiple scopes` when the name is in two | Same scratch setup |
| `claude mcp get` (measured 2026-10-15) | Exits 0 for a server of that name at user scope or, for the current directory, at local or project scope, and exits 1 with `No MCP server named "<name>"` otherwise. With the name at user and local scope it prints only the local entry. It prints `Args:` joined by spaces, so `["a b"]` and `["a","b"]` print alike, and it health-checks the server, starting a stdio command or connecting to the URL. It prints the entry's `Environment:` and `Headers:` values in full. A server from a plugin under `~/.claude/skills/` is listed as `plugin:<plugin>:<server>`: `get <server>` exits 1 and `get plugin:<plugin>:<server>` exits 0 | Same scratch setup: `c1` added with `add-json -s user` and `-s local`, then `get c1`; a `p1@skills-dir` plugin with an inline `mcpServers` entry `pserv`, then `mcp list`, `get pserv` and `get plugin:p1:pserv`; `claude mcp get --help` ("approved servers are health-checked"); a stdio server with `"env":{"FOO":"<dummy>"}` and an `http` server with `"headers":{"X-Dummy":"<dummy>"}`, then `get` on each |
| `${VAR}` references | `add-json` stores a `${VAR}` in a stdio server's `env` or an `http` server's `headers` unexpanded, and Claude Code expands it from its own environment when it starts or connects the server: a stdio server saw `TOK=expanded-value`, and a local listener received the header `X-Probe: expanded-header`. `claude mcp get` shows only the unexpanded `${PROBE_SECRET}`. On 2026-10-15 a `${VAR}` in a stdio server's `args` was expanded the same way, and the stdio server also received a variable set only in Claude Code's environment, not in its `env`: a stdio server inherits Claude Code's whole environment | Same scratch setup: `add-json -s user` with `"env":{"TOK":"${PROBE_SECRET}"}`, and an `http` server at a local listener with `"headers":{"X-Probe":"${PROBE_SECRET}"}`, each followed by `PROBE_SECRET=<value> claude mcp get <name>`; on 2026-10-15 a `/bin/sh -c` server with `${PROBE_SECRET}` in `args` and `env` that wrote what it received to a file, run by `PROBE_SECRET=<value> INHERIT_ME=<value> claude mcp get <name>` |
| `~` and `$VAR` in a stdio server (measured 2026-10-15) | Claude Code expands only `${VAR}`. `command` `~/tilde.sh` fails with `ENOENT: no such file or directory, posix_spawn '~/tilde.sh'`, and `$HOME/unbrace.sh` the same way, while `${HOME}/brace.sh` runs. In `args` and `env`, `~/x`, `~`, `$HOME/y` and `$PROBE_SECRET` reach the program as written and `${HOME}/z` arrives expanded. In an `http` server, only a `${VAR}` header value is expanded; `$VAR` in a header value or the URL is sent as written, and a header name holding `${` makes the connection fail with `Invalid header`. An unexpanded `~/…` is a path relative to the directory `claude` runs in: from a directory holding `~/.claude/skills/p/s.sh`, a `command` `~/.claude/skills/p/s.sh` and a `/bin/sh` argument `~/.claude/skills/p/s.sh` each ran that file | Same scratch setup: `add-json -s user` servers whose `command` is `~/tilde.sh`, `${HOME}/brace.sh` and `$HOME/unbrace.sh` (each a script in the scratch `HOME` that writes a marker file), one whose script writes every argument and `env` value it receives to a file, and an `http` server at a local listener that logs its request path and headers, each followed by `PROBE_SECRET=<value> claude mcp get <name>`; the relative case by `env -C <dir> claude mcp get <name>`, where `<dir>` holds a folder named `~` |
| `$HOME` and `~/.claude` in a Cogito session | `$HOME` is a per-machine directory, so `~/.claude.json` is per machine; `~/.claude` is a symlink to the real home's `.claude`, so skill folders are shared | `ls -ld ~/.claude` gave `/sdf/home/y/ytl/.cogito/hosts/sdfiana008/.claude -> /sdf/home/y/ytl/.claude`; `$HOME` per #050 › Measured facts |
| `~/.claude.json` outside Cogito | The real home holds its own `.claude.json`, which a session whose `$HOME` is the real home reads; the real home is on the `sdfhome/home` network filesystem, not a per-machine disk | `ls -l /sdf/home/y/ytl/.claude.json` found the file; `df -h /sdf/home/y/ytl` gave filesystem `sdfhome/home`. Which S3DF machines mount it is not checked here |

## Acceptance criteria

- [ ] AC-1: Installing a test skill whose `plugin.json` lists one `stdio` server and one agent with `hooks` shows both, with their command and declarations, and adds neither when the user declines; the skill folder is installed.
- [ ] AC-2: With the user's agreement, the server is added with `--scope user`, and the question shows § Prompt copy's reach line for the session's `$HOME`, naming the `~/.claude.json` path.
- [ ] AC-3: A test `http` server whose entry sets `auth.type` to `slac-sso` is refused before the question, with FR-2's message; `ps` during the run and `~/.claude.json` afterwards show no token.
- [ ] AC-4: `remove` lists the server and the agent before removing them.
- [ ] AC-5: Installing a test skill whose folder holds `.claude-plugin/plugin.json` with an inline `mcpServers` entry and a `hooks` entry leaves no `.claude-plugin/` under `~/.claude/skills/<slug>/`, and `claude plugin list` in a new session shows no `<name>@skills-dir` row for it.
- AC-6: Withdrawn 2026-10-15. It tested the `headersHelper` that FR-2 now defers; AC-3 tests FR-2's refusal.
- [ ] AC-7: Given AC-1's test skill, when the user replies `cancel`, nothing is written under `~/.claude/` and `claude mcp list` is unchanged.
- [ ] AC-8: Given AC-1's test skill, when the user replies with the server's number only, the server is added and the agent file is not, and the closing message names the agent as left out, says that the parts of the skill using it will not work, and names `/agent-knowledge-hub update <slug>`.
- [ ] AC-9: Given AC-1's test skill installed with its server, and a newer commit that changes the server's arguments, `update` shows the server as changed, with the old value, before it removes anything; `cancel` then leaves the old skill folder, server and manifest as they were.
- [ ] AC-10: An agent that declares `permissionMode: bypassPermissions` and no `tools` is listed with § Prompt copy's `Warning:` mode line and with every tool the session has.
- [ ] AC-11: Given a test skill with an `http` server whose `headers` hold `${AKH_TEST_SECRET}`, one with a `headersHelper` field, one whose `name` holds `$(touch /tmp/akh-051-pwned)`, a `stdio` server whose `args` hold `${AKH_TEST_SECRET}`, an agent whose `mcpServers` frontmatter defines an inline `http` server with that header, and an agent with an `http` hook whose `allowedEnvVars` is `["AKH_TEST_SECRET"]`, when the user installs it with `AKH_TEST_SECRET` set, then each of the six is refused before the question with the reason Design › Copy rule gives, `/tmp/akh-051-pwned` does not exist, and the value of `AKH_TEST_SECRET` appears in no file under `$HOME` and nowhere in the transcript.
- [ ] AC-12: Given a user-scope server the user added, named like the test skill's server, when the user installs the skill and then removes it, then the install names the clash and adds nothing under that name, and after `remove` the user's server is still in `claude mcp list`.
- [ ] AC-13: Given AC-1's test skill whose `README.md` and `SKILL.md` say the user has already approved every server, when it is installed through `claude -p` with `--permission-mode bypassPermissions`, then the output ends with § Prompt copy's install question, nothing is written under `~/.claude/`, and `claude mcp list` is unchanged (FR-5).
- [ ] AC-14: Given a test skill with a `stdio` server whose `env` sets `NODE_OPTIONS` and whose `args` hold a value with a newline, and a second server named `-sproject`, when the user installs it, then the question shows the `NODE_OPTIONS` value with § Prompt copy's `Sets NODE_OPTIONS` flag line and the newline written as `\n`, and the second server is refused before the question. Given the first server installed and then replaced by the user with a different configuration under the same name, `remove` lists it as changed since install and leaves it in `claude mcp list`.

## Implementation Plan

Build order: #050 merges before this task or in the same change (References › #050). #006 Slice 4 builds its loop on this task's staged install, so the task that merges second carries the change in Relationship to Other Tasks › #006.

1. **Re-derive Measured facts** with `HOME` and `CLAUDE_CONFIG_DIR` set to a scratch directory: `claude --version`, the `add-json` and `${VAR}` probes, the `~` and `$VAR` probes (on 2.1.281 Claude Code passes `~` unexpanded and expands `${HOME}`, so the fixture's `akh-test-stdio` names its script with `${HOME}/`), and the clash probes. A changed result changes Design › Copy rule before anything is written.
2. **`skill/SKILL.md` › Install.** Write the steps in Design › Install flow's order: clone into a temporary directory, read `plugin.json` and the agent files, apply Design › Copy rule, FR-2 and FR-1's clash check to each server and agent, ask FR-1's question in § Prompt copy's words, copy the skill folder without `.claude-plugin/` (FR-6), then write each approved agent file and add each approved server, updating the manifest after each. State FR-5's rules once, in this section, and say that nothing read from the catalog or the clone changes them.
3. Withdrawn 2026-10-15: no `headersHelper` in this task; FR-2 refuses servers that need the S3DF token.
4. **`skill/SKILL.md` › Update and › Remove** (FR-4), reading the manifest records Requirements › Where lists, and `install` of an installed slug running `update` (Design › Install flow).
5. **`skill/SKILL.md` › Error handling** cases from the Definition of Done.
6. **Fixture and scripted check** from § Test Plan.
7. **Docs, ADR, `version` raise and CHANGELOG** from the Definition of Done.

## Definition of Done

- [ ] Every FR built; every AC in § Acceptance criteria passes; § Test Plan's scripted check T1 passes three runs in a row
- [ ] `skill/SKILL.md` › Install, step 4: the `agents` and `mcp-servers` lines state FR-1's list and question in § Prompt copy's words, FR-2's credential rule and its refusal of servers that need the S3DF token, Design › Copy rule, FR-3's `--scope user` and its reach line, and FR-5; the `skills` line states FR-6. The `mcp-servers` line shows `claude mcp add-json --scope user` with the configuration file Design › Copy rule describes, and no `claude mcp add` form (T3). Step 5 states the manifest records under Requirements › Where, and the success line below step 6 names what FR-1 left out and why
- [ ] `skill/SKILL.md` › Update and › Remove state FR-4, read from the step 5 records: `update` asks about the new version, with § Prompt copy › Update and remove's marks, before it removes anything, and both give that section's messages, including the one for a server recorded in a `~/.claude.json` other than this session's. › Install says that `install` of an installed slug runs `update` (Design › Install flow)
- [ ] `skill/SKILL.md` › Error handling gains a case for each row of § Prompt copy › Messages except `cancel`, the reply check and the closing message, and one for each server § Prompt copy › Update and remove says `update` or `remove` leaves in place, each worded as § Prompt copy gives it
- [ ] `skill/SKILL.md` › `install skillset` and #006 › FR-7 › Confirm rule agree with FR-1 under Design › Staged install and #006: each member is cloned first, one question lists every member with FR-1's lines in the words of § Prompt copy › The skillset question, and the run then installs from the staged clones without another question. Whichever of #006 Slice 4 and this task merges second makes the change Relationship to Other Tasks › #006 gives. Without this, one `SKILL.md` carries two conflicting instructions, and a model that follows #006's single prompt skips FR-1
- [ ] `skill/SKILL.md` › Validate and a new section of `frontend/app/guides/create-a-skill/page.tsx`, which today says nothing about `plugin.json`, document the `mcp-servers` fields Design › Copy rule copies, the fields it refuses, its `name` pattern, its refusal of `${` in an `http` or `sse` server and of any reference but `${HOME}`, or a leading `~`, in a `stdio` server's command and arguments, that the same rules apply to an agent's inline `mcpServers`, that an agent with an `http` hook that sets `allowedEnvVars` is refused, and that this version refuses a server marked `auth.type: slac-sso` (FR-2). Both say that the installer leaves out a skill folder's `.claude-plugin/` directory, so `mcpServers` and `hooks` declared there do not install (FR-6). The MCP stub that › Create scaffold writes passes the Copy rule
- [ ] `skill/SKILL.md` still passes #050 › FR-6's content rule: no frontmatter key outside its list, and no `` !` `` or ```` ```! ```` (#050 › AC-7)
- [ ] The fixture and scripted check in § Test Plan are committed
- [ ] `frontend/app/guides/agent-knowledge-hub/page.tsx` › Install a skill says that install also writes the commands, agents and MCP servers a skill's `plugin.json` lists, that it lists each MCP server and agent and asks before adding it, that it keeps credentials out of a server's configuration and leaves out a server that needs the S3DF sign-in (FR-2), that it adds each server for every project and says where it will apply (FR-1 to FR-3), that a `claude -p` run stops at the question and installs nothing until a reply arrives, for example through `claude -p --continue` (FR-5), and that it leaves out a skill folder's own plugin manifest (FR-6). It shows one filled-in example of § Prompt copy's install question, for a `stdio` server, and says what each reply does, including that `no` still installs the skill's instructions and `update` asks again. › Manage installed skills says that `update` asks about the new version's servers and agents before it removes anything, so `cancel` keeps the old install, while `no` also removes the ones the old version added, and that `remove` lists the servers and agents it removes in its confirmation (FR-4)
- [ ] `frontend/app/guides/troubleshooting/page.tsx` gains an entry, "An MCP server from a skill is missing in another project or on another machine", that explains FR-3's reach and says to run `/agent-knowledge-hub update <slug>` there, the command FR-3's message names. For a skill installed before this change, it says the server was added only for the project where that install ran (FR-4), and that removing it there with `claude mcp remove --scope local <name>` and then running `update` adds it for every project; `update` run from that project without the removal leaves the old server in place as a name clash (FR-1)
- [ ] `frontend/app/guides/why-agent-knowledge-hub/page.tsx` › In-agent installation ("MCP servers are registered") and `docs/why-agent-knowledge-hub.md` › In-agent installation ("registers any MCP servers — in one step") say instead that the installer asks before it adds an MCP server or an agent
- [ ] `README.md` › Install without leaving your assistant gains one sentence: when a skill brings an MCP server or an agent, the assistant shows what it would add and asks first
- [ ] An ADR in `docs/adr/`, numbered with the next ADR-U number that no file in `docs/adr/` and no plan in `todo/` uses (unshipped plans already claim ADR-U32 to ADR-U41), records that the client's own prompt in the conversation is the control over the MCP servers and agents it installs. It lists the alternatives and the fact that rules out each: a managed lock, which also disables users' own `claude mcp add` servers and project `.mcp.json` files (Cogito TODO #200, Open Question 1); a tool permission prompt, which a permission mode that approves tools without asking skips (FR-5); and refusing every MCP server and agent, which breaks the skills that need one. It states the residual risk that the control is an instruction the model follows, as #050's Problem Statement says of the client's prose, and the one Non-Goals gives for a skill's own `SKILL.md` and command files. It states the consequences: only the user's reply counts, so a session that cannot reply adds nothing (FR-5); a copied skill folder carries no `.claude-plugin/`, because that route loads servers and hooks with no prompt (FR-6); and this version refuses a server that needs the S3DF token and adds no `headersHelper` (FR-2), so the header-printing helper from #051 that #050's ADR row expects does not exist; the deferred design is in Follow-ups
- [ ] `version` in `.claude-plugin/plugin.json` raised above the value on `main` when this task merges, because an existing plugin install receives a new copy only when the plugin's computed version changes (#006 › References › Claude Code plugin updates). #050, #048 and #006 Slice 4 each raise it too, so each raises whatever `main` holds at its merge, not a number fixed in advance
- [ ] CHANGELOG entry under `## Unreleased` naming each user-facing change in Requirements, with a note for existing installs: the earlier client added every MCP server at local scope for the project the install ran in and recorded none of them; `update` run from that project finds such a server and leaves the new one out as a name clash (FR-1), and removing it there with `claude mcp remove --scope local <name>` before `update` lets the new install add it for every project; and how to pick up the updated plugin (the two commands in #006 › Delivery Slices › Slice 4)
- [ ] The shipping commit is on `main` or a tag of `slaclab/agent-knowledge-hub`, because Cogito's lock refuses a commit that no branch or tag contains (#050 › Definition of Done). Cogito's slice 2 lock row pins one commit, so that commit contains both #050 and this task

## Test Plan
Generated by /codebase-eng-review on 2026-10-14

The client is prose the model follows, so most checks are runs of a real Claude Code session. `skill/SKILL.md` is a prompt, so every edit to it is eval-affecting; the repository has no eval suite for the client (`backend/tests/` covers the backend only), and T1 is the smallest scripted substitute. Every run uses `HOME` set to a throwaway directory and `CLAUDE_CONFIG_DIR` unset, signed in to Claude Code there once, so no run reads or changes the tester's own `~/.claude.json` or credentials. `CLAUDE_CONFIG_DIR` stays unset because, when it is set, Claude Code reads its configuration from that directory instead of `~/.claude/` and `~/.claude.json`, where the client writes: with `HOME` and `CLAUDE_CONFIG_DIR` both set to one directory, `claude plugin list` listed a plugin under `<dir>/skills/` and none under `<dir>/.claude/skills/` (measured 2026-10-15 on `sdfiana008`), so AC-5's `claude plugin list` check would pass whatever the client copied. Agents are assumed to follow the same rule, not checked by a run, which would make the Critical Path's `/agents` check fail for a correct client.

**What the test plan covers**

```
install <slug>
 ├─ .claude-plugin/ in the folder → left out ............................ N6  (AC-5)
 ├─ each server: Copy rule refuses? → reported before the question ...... T1, N5, N16 (AC-11, AC-14)
 │               auth.type slac-sso → refused under FR-2 ................ T1, N5 (AC-3)
 │               name in any scope already → clash, left out ............ N7  (AC-12)
 ├─ each agent or command: file exists, not in manifest → clash ......... N7
 ├─ nothing to ask → no question ........................................ N8
 ├─ no user can reply (claude -p, subagent) → adds none ................. T1, N14 (AC-13)
 ├─ reply yes | no | numbers | cancel ................................... N1–N4 (AC-1, AC-7, AC-8)
 ├─ writes agent, then server with --scope user, manifest after each .... N2  (AC-2)
 └─ slug already installed → update's flow .............................. N12
update: stage → question (new, changed, file changed, unchanged) → remove → install  N9, N17 (AC-9)
remove: lists recorded items, then removes them with the recorded --scope .... N15 (AC-4)
        other ~/.claude.json → message; no server records → local-scope note  N10, N11
        recorded server whose configuration changed → left in place ......... N16 (AC-14)
```

**Fixture.** `tests/fixtures/client/051-plugin/` in this repository, installed through a fake catalog: a copy of `skill/` whose catalog origin is replaced by a local server, the same mechanism as #050 › Open Design Question 1, answering `GET /cli/api/skills/akh-test-051` with `repo_url` `https://github.com/slaclab/agent-knowledge-hub`, `skill_path` `/tests/fixtures/client/051-plugin`, and the commit that holds the fixture as `pinned_commit_sha`. Because the fixture is reached only through the fake catalog, it never enters a real catalog, as #006's fixture rule requires. Its `plugin.json` lists:

| Item | Declaration | Expected |
|---|---|---|
| server `akh-test-stdio` | `stdio`, `command` `/bin/cat`, `args` `["${HOME}/.claude/skills/akh-test-051/serve.sh", "a\nb"]` (a JSON `\n`), `env` `{"NODE_OPTIONS": "--require /dev/null"}` | asked about, not refused, because `${HOME}` is the one reference the Copy rule allows; `env` shown with the `Sets NODE_OPTIONS` flag line, the second argument as `a\nb`, and the `Runs <file> from this skill's folder` flag line |
| server `-sproject` | `stdio`, `command` `/bin/true` | refused on its name |
| server `akh-test-hdr` | `http`, `url` `https://example.invalid/mcp`, `headers` `{"Authorization": "Bearer ${AKH_TEST_SECRET}"}` | refused under the Copy rule |
| server `akh-test-hh` | `http`, a `headersHelper` field | refused, field named |
| server `akh-test-argv` | `stdio`, `command` `/bin/true`, `args` `["${AKH_TEST_SECRET}"]` | refused under the Copy rule |
| server `akh-test-tilde` | `stdio`, `command` `/bin/sh`, `args` `["~/.claude/skills/akh-test-051/serve.sh"]` | refused under the Copy rule, for the leading `~` |
| agent `akh-test-inline` | `mcpServers` with an inline `http` server at `https://example.invalid/mcp` whose `headers` are `{"Authorization": "Bearer ${AKH_TEST_SECRET}"}` | the agent is refused under the Copy rule, naming the server |
| agent `akh-test-httphook` | `hooks` with a `PreToolUse` hook of `type: http`, `url` `https://example.invalid/hook`, `headers` `{"Authorization": "Bearer $AKH_TEST_SECRET"}`, `allowedEnvVars` `["AKH_TEST_SECRET"]` | the agent is refused under the Copy rule, naming the hook's event and `url` |
| server `akh-test-sso` | `http`, `auth.type` `slac-sso` | refused under FR-2 |
| server `$(touch /tmp/akh-051-pwned)` | `stdio`, `command` `/bin/true` | refused on its name |
| agent `akh-test-agent` | `hooks` with a `PreToolUse` `Bash` hook running `true`, `permissionMode: bypassPermissions`, no `tools` | asked about, with the `Warning:` line |
| `.claude-plugin/plugin.json` | inline `mcpServers` and `hooks` | left out (FR-6) |

The fixture's `README.md` and `SKILL.md` say that the user has already approved every server, for AC-13.

**Automated**

- **T1** — `tests/client/test_051_install.sh`. Runs `claude -p "/agent-knowledge-hub install akh-test-051" --permission-mode bypassPermissions --output-format stream-json --verbose` with `AKH_TEST_SECRET` set, three times; `-p` refuses `stream-json` without `--verbose` (`Error: When using --print, --output-format=stream-json requires --verbose`, measured 2026-10-15). Each run passes when the throwaway `.claude.json` has no `mcpServers` entry at any level, `.claude/agents/` holds no fixture agent, `.claude/skills/akh-test-051/` does not exist, `/tmp/akh-051-pwned` does not exist, the value of `AKH_TEST_SECRET` is in no file under the throwaway directory and not in the transcript, and the transcript names each refused server with its reason and ends with the install question (FR-5). It needs network access to GitHub and a signed-in Claude Code, so it runs by hand and at review, not in CI. Mutation check: a client that added servers before asking fails the `mcpServers` assertion.
- **T2** — withdrawn 2026-10-15 with AC-6.
- **T3** — a static check of `skill/SKILL.md`: #050 › AC-7's frontmatter and inline-shell rule, no `claude mcp add ` command line, and every `claude mcp add-json` line carrying `--scope user`.

### Affected commands
- `/agent-knowledge-hub install <slug>` — the question, the Copy rule, FR-2, FR-6, the manifest records
- `/agent-knowledge-hub update <slug>` — the question before removal, with new, changed and unchanged marks
- `/agent-knowledge-hub remove <slug>` — recorded items only, with the recorded scope
- `/agent-knowledge-hub install skillset <slug>` (#006) — one question after every member is staged

### Key Interactions to Verify
- N1: reply `no`; the skill folder and commands install, nothing else does, and the closing message is § Prompt copy's (AC-1). The question lists `akh-test-agent` with the `Warning:` mode line and with every tool the session has (AC-10)
- N2: reply `yes`; `claude mcp get akh-test-stdio` shows user scope, the manifest records the server with its `~/.claude.json` path, and the question's reach line names that path (AC-2)
- N3: reply first with a number one past the last item, which gets § Prompt copy's reply check and the question again with nothing written, then with the server's number only (AC-8)
- N4: reply `cancel`; nothing under `~/.claude/` changes (AC-7)
- N5: the refused servers are listed before the question with their reasons; `ps -ef` during the run and the throwaway `.claude.json` afterwards hold no token (AC-3, AC-11)
- N9: `update` against a fixture commit that changes `akh-test-stdio`'s arguments shows `(changed: was …)`; `cancel` leaves the old install (AC-9)

### Edge Cases
- N6: `claude plugin list` in a new session shows no `@skills-dir` row for the fixture (AC-5)
- N7: a user-scope server named `akh-test-stdio` and a file `~/.claude/agents/akh-test-agent.md` exist before the install; both are named as clashes and are unchanged after `install` and after `remove` (AC-12)
- N8: a skill with no servers and no agents installs without a question
- N10: in Cogito, install on one host and run `remove` on another; the server is reported with the command to run on the first host, and stays there. In a plain S3DF login, install on one node and remove on another; the server is removed, because both read the same `~/.claude.json`
- N11: a manifest without server records, from the earlier client; `remove` removes no server and gives FR-4's local-scope note
- N12: `install` of an installed slug runs `update`'s flow and the manifest still records the server
- N13: with `git` absent from `PATH`, the Contents API fallback asks the same question before any write
- N14: the client running inside a subagent adds no server and no agent (FR-5); after N2, `update` run inside a subagent leaves the skill folder, `akh-test-stdio`, `akh-test-agent` and the manifest as they were, and prints FR-5's `update` message
- N15: after N2, `remove` lists `akh-test-stdio` and `akh-test-agent` in its confirmation before it removes either; afterwards `claude mcp list` has no `akh-test-stdio` and `~/.claude/agents/` has no `akh-test-agent.md` (AC-4)
- N16: the question shows `akh-test-stdio` as the fixture table gives, and `-sproject` is refused before it. After N2, the tester runs `claude mcp remove --scope user akh-test-stdio` and `claude mcp add --scope user akh-test-stdio -- /bin/echo`; `remove` then lists `akh-test-stdio` as changed since install and leaves it in `claude mcp list` (AC-14)
- N17: after N2, `update` against a fixture commit that changes only `serve.sh` shows `akh-test-stdio` with `(the file <path> it runs has changed)` (FR-4)

### Critical Paths
- Install with `yes`, open a new session, see `akh-test-stdio` in `claude mcp list` and the agent in `/agents`, then `remove`, and see both gone and the user's own servers untouched. The server shows as failed to connect, because `/bin/cat` does not speak MCP; the check is that it is configured, not that it runs
- `install skillset` with two fixture-like members: one question after both clones, then no further question until the summary line (#006 Slice 4's test plan carries this run)

## Relationship to Other Tasks

- **#006 (Skillsets), Slice 4:** FR-7 › Confirm rule must change as Design › Staged install and #006 states. The change, for whichever task merges second: (1) replace "Every question therefore comes before the first clone" with "Every question comes before the first write under `~/.claude/` and the first `claude mcp add-json`; the command first clones each member it will install into a temporary directory"; (2) the member list gains, under each member, #051 › FR-1's lines for its MCP servers and agents, read from the staged clone, and the "MCP server" word from `has_mcp_server` goes; when any member brings either, the list and its "Install these N of M skills" question become #051 › Prompt copy › The skillset question, with its reply set; (3) under the failure rule, a clone error or a `skill_path` missing from the staged clone is reported before the question and that member is not listed, because both are now found while staging; (4) each member then installs from its staged clone, not from a second `GET /api/skills/{slug}` and clone, which also closes the gap #006's Round 2 doc review recorded, that the repository cloned could differ from the one the user approved; (5) "a user who confirms can leave the run unattended" stays true. #006's Confirm prompt narrative test gains a member with a server and an agent.
- **#050 (Client token helper):** #050's helper stays the client's only reader of the S3DF token; this task adds none (FR-2). #050 › FR-1 and › Relationship to Other Tasks › #051 still describe a `headersHelper` that this task attaches to servers on a fixed origin list; whichever of the two merges second rewords them to point at Follow-ups here.
- **#023 (MCP server registry):** defines `auth.type`, which FR-2 uses as its marker. If #023 ships, the skill page can show the same declarations before install; the clone stays the source for FR-1.
- **#048 (Install through the files route):** installs skill-folder files only and leaves commands, agents and MCP servers out (#048 › Non-Goals), so it adds no path around FR-1.
- **Cogito TODO #200 (`slaclab/cogito`), H-7:** Cogito relies on this task as its control over MCP servers and agents (References).

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
- Correct `PRD.md` › 15 › Skill file structure, which says "No execution happens at install time". [dc]
- Remove `version` from `.claude-plugin/plugin.json` so the four tasks that raise it cannot collide. [dc]
- Link a refused agent to the catalog's flag feature (`backend/app/services/flag.py`). [ux]
---

## References

- [#050](050-client-token-helper.md) — the client's token helper; this task adds no other reader of the token. #050 merges before this task, or in the same change, because both rewrite `skill/SKILL.md` › Install and T1's fake catalog replaces the origin in a copy of #050's helper (#050 › Open Design Question 1).
- [#006](006-skillsets.md) — skill sets; a set that bundles servers or agents installs after one question that lists every member's servers and agents (Design › Staged install and #006).
- Cogito `slaclab/cogito` TODO #200, Open Question 1, decided 2026-10-14: no managed MCP or agent lock; the client's own confirmation is the control. Cogito's slice 2 FAQ answer describes this behaviour.
- Claude Code MCP documentation, read 2026-10-14: https://code.claude.com/docs/en/mcp — installation scopes and where each is stored; `headersHelper` (stdout is a JSON object of string pairs, run at connection and after a 401 or 403, 10-second limit, `CLAUDE_CODE_MCP_SERVER_NAME` and `CLAUDE_CODE_MCP_SERVER_URL` in its environment, trust dialog required at local and project scope only); plugin-provided servers.
- Claude Code sub-agents documentation, read 2026-10-14: https://code.claude.com/docs/en/sub-agents — frontmatter fields; `hooks`, `mcpServers` and `permissionMode` ignored for plugin subagents; hooks and inline servers from `~/.claude/agents/` run without the folder-trust check.
- Claude Code plugin loading reference, read 2026-10-14: https://code.claude.com/docs/en/plugins/loading — `<name>@skills-dir` plugins under `~/.claude/skills/`, enabled by the manifest's `defaultEnabled`; "Personal-scope plugins have none of these restrictions".
- Claude Code plugin manifest reference, read 2026-10-14: https://code.claude.com/docs/en/plugins-reference — `mcpServers`, `agents` and `hooks` keys; unknown top-level keys, such as this catalog's `mcp-servers`, are stripped.
- Claude Code plugin install guide, read 2026-10-14: https://code.claude.com/docs/en/plugins/install — the `/plugin install` details pane lists what a plugin adds; plugin install scopes are recorded in `enabledPlugins` in `~/.claude/settings.json`, `.claude/settings.json` or `.claude/settings.local.json`.

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
