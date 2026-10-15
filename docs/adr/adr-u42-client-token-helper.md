# ADR-U42: The client sends the S3DF token only through a fixed-destination helper

**Status:** Accepted
**Date:** 2026-10-15
**Context:** todo/050-client-token-helper.md

## Context

The `/agent-knowledge-hub` client is `skill/SKILL.md`, which is prose the model follows. Every catalog request needs the account's S3DF token, and the model builds each request from that prose and from catalog text it has read. An instruction cannot guarantee where the token goes: text in a catalog entry can ask the model to send a request somewhere else, and the model can write any command line it likes.

The token also has to be found. In a Cogito session `$HOME` is a per-machine directory that holds no token file, while the account's real home, which `getent passwd` reports, does. On S3DF nodes outside Cogito, `/proc` is mounted without `hidepid`, so any user can read another user's process arguments.

The client has to pass Cogito's content rule for skills it loads into every session. That rule allows only a fixed list of frontmatter keys, refuses inline shell (`` !` `` and ```` ```! ````), and refuses symlinks and submodules in the skill folder.

## Decision

The client makes every catalog request through one shell script, `skill/hub-request.sh`, run as `sh ${CLAUDE_SKILL_DIR}/hub-request.sh <GET|POST> <path>`. The four parts below are one decision, because each depends on the others.

- **One helper.** The script is the only reader of the token. It has no mode that prints the token or the `Authorization` header, because the model can run any mode a script has. `SKILL.md` runs it through `sh` because Cogito installs skill files with mode 0644.
- **Token location.** The helper reads `.s3df-access-token` from the account's real home and falls back to `$HOME/.s3df-access-token` when the lookup returns no home or the file is absent. An empty lookup counts as no home, so the helper never checks `/.s3df-access-token`. A file in the real home that fails the shape check (base64url segments and dots only) is refused, not skipped. The helper reads no environment variable for the token.
- **No argument, no file.** The header reaches curl on file descriptor 3 through a pipe from the `printf` builtin, so the token appears in no process's arguments and in no file. Every other command that touches the token reads it from the token file or a pipe. Before anything else the helper turns off tracing and allexport, removes functions that an exported environment could have defined for the commands it runs, clears every variable it assigns, and fixes `PATH` and `LC_ALL`. It never runs `[`, because bash 4.4 run as `sh` imports an exported `[` function and refuses to unset it.
- **Fixed destination.** The helper takes exactly a method and a path. It sends requests only to `https://agent-knowledge-hub.slac.stanford.edu`, with no override. The path must begin with `/cli/api/`, use a fixed character set, and hold no `.` or `..` segment and no `//`. The method and path must also match a row of a route table that lists the requests the client sends. A request body comes on standard input and reaches curl as `--data-binary @-`. The helper runs `/usr/bin/curl -q`, does not follow redirects, and unsets `CURL_CA_BUNDLE`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `SSLKEYLOGFILE`, and `CURL_HOME`. It keeps the proxy variables. It uses only options that curl 7.61.1, the version on RHEL 8, supports.

The helper's exit status separates success, a refused argument, a missing or malformed token file, HTTP 401, other HTTP statuses, and network failures. `SKILL.md` › Error handling maps each status to a message.

## Rejected alternatives

| Alternative | Fact that rules it out |
|---|---|
| A header built with `$(cat …)` in curl's arguments | The token would be in curl's `/proc/<pid>/cmdline`, which any user on the node can read. |
| Pre-approving the helper with `allowed-tools`, or running it through inline shell | Cogito's content rule refuses both, and Cogito's build then refuses the lock row that pins this repository. |
| A helper that accepts any URL | Text in a catalog entry could steer the token to another host through the helper's own interface. |
| A helper mode that prints the header | The model can run any mode the helper has. |
| An origin set by an environment variable or an argument, for tests | The model could set it too. Tests instead run a copy of the helper with two lines replaced. |
| Replacing only the origin in the test copy | The copy would read the developer's real token from the real home, and a failing assertion could print it. |
| `--data-raw`, or `-d`/`--data`/`--data-binary` with the body as the argument | Linux caps one argument at 128 KiB, the body would be readable in `/proc/<pid>/cmdline`, and a value starting with `@` makes curl read that file, so `@<home>/.s3df-access-token` would publish the token as a body. |
| A body file named by the caller | The helper would need its own rule for which files it may read. |
| curl's `--variable` with `--expand-header` | It needs curl 8.3.0; RHEL 8 ships 7.61.1. |
| `--fail-with-body`, or `%{stderr}` in `-w` | They need curl 7.76.0 and 7.63.0. |
| Following redirects with `-L` | A redirect could send the token to another host. |
| Clearing the proxy variables | Claude Code's Bash sandbox reaches the network only through the proxy they name. With the trust store fixed and no key log, a proxy sees the host in `CONNECT` and not the header. |
| Methods other than `GET` and `POST` | The method is copied into the request line, and the backend's `DELETE`, `PUT`, and `PATCH` routes are ones the client never sends. |
| Keeping the `AGENT_KNOWLEDGE_HUB_TOKEN` override | The Bash tool runs each command as `<shell> -c '<command>'`, so `AGENT_KNOWLEDGE_HUB_TOKEN=<token> sh …` puts the token in that shell's `/proc/<pid>/cmdline`. |

## Consequences

- A change to the catalog's hostname needs a client release.
- The dev and stage catalogs are out of the client's reach.
- A task that adds a catalog request adds its row to the route table in `skill/hub-request.sh`, and to the table in `todo/050-client-token-helper.md` › FR-5, in the same change.
- Automation writes the token to `.s3df-access-token` in the job's home directory instead of setting a variable.
- The helper cannot stop a model that reads the token file itself, or that runs a changed copy of the helper. `SKILL.md` forbids both, and that rule is the only control against them. A deployment that wants the read blocked adds a `permissions.deny` rule such as `Read(//sdf/home/**/.s3df-access-token)`. Claude Code applies it to its file tools and to `cat`, `head`, `tail`, `sed`, `tee`, and redirection targets, but not to a subprocess that opens the file, so the helper keeps working.
- A `headersHelper` for MCP servers, which #047 or a follow-up to #051 may add, has to print the header to Claude Code. It would be a separate script that shares this helper's token lookup and shape check, never a mode of this one.
- In a session that asks before each Bash command, every catalog request causes one permission prompt.
