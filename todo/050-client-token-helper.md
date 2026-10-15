# TODO #050 — Client Token Helper: S3DF Token from the Real Home, Kept Out of Process Arguments, Sent Only to the Catalog

> **Priority:** 🟡 P2 — Medium
> **Status:** 🔄 In Progress
> **Branch:** `feat/client-token-helper`
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Provenance

**Raised by:** Cogito TODO #200 (`slaclab/cogito`), hub request H-1, filed 2026-10-14.

**References:** § Relationship to Other Tasks links each related task and says why it is related.

---

## Problem Statement

The `/agent-knowledge-hub` client in `skill/SKILL.md` is prose that the model follows. It names `~/.s3df-access-token` as its token file and asks for `Authorization: Bearer <token>` on rate and submit, but it leaves the command that sends the token to the model. Every catalog request needs the token, because the catalog answers 401 on each CLI path the client uses when no token is sent (#006 › Measured facts › cli-auth). Four defects follow.

1. The token can land in a process's arguments. `curl -H "Authorization: Bearer $(cat ~/.s3df-access-token)"`, the form #006 › FR-7 › Auth rule plans, expands the token into curl's command line, where other users of a shared S3DF node can read it from `/proc/<pid>/cmdline`, for example with `ps`.
2. Nothing fixes where the token goes. Any signed-in user can submit a skill, so catalog text comes from any signed-in user. Text that steers the model to a curl call with another URL, `--url`, `-K`/`--config`, or `@` user information in the address sends the token to that host, because curl sends the same headers to every URL it is given. A helper that accepted any URL would make that theft look like a sanctioned hub request; with a fixed destination, the theft needs the model to step outside the helper's interface, by reading the token file or by running a changed copy of the helper, which FR-6 forbids and which the permission prompt shows the user in a session that asks before that command.
3. The client cannot find the token in a Cogito session. Cogito sets `$HOME` to a per-machine directory, where `.s3df-access-token` does not exist (Measured facts), and Cogito records that a browser sign-in renews the token in the account's real home directory.
4. Error handling in `skill/SKILL.md` has no 401 case, so an expired or missing sign-in reaches the user as a bare HTTP error.

The Cogito deployment (`slaclab/cogito`, TODO #200) files this task as hub request H-1. Cogito copies this repository's `skill/` folder into its host image as a Claude Code managed skill, so every Cogito session carries the client, and its NFR-3 requires that the client never places the token in a process's arguments or in a file outside the real home. Cogito's slice 2, which ships the client in the image, pins a commit of this repository that includes this task.

### What fails today

As of 2026-10-14:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A user searches from a Cogito session | The client looks for `~/.s3df-access-token`, which is absent from a Cogito session's `$HOME`, and the catalog answers 401 | The helper reads the token from the account's real home, and the search returns results |
| The client sends a token on a shared S3DF node | The model writes the command; the `$(cat …)` form puts the token in curl's arguments | The token reaches curl through a pipe (FR-4) and appears in no process's arguments |
| A catalog entry's text asks the model to run curl against another host | Nothing in the client stops the token going there | The helper sends only to `https://agent-knowledge-hub.slac.stanford.edu` and refuses a URL or a curl option as an argument |
| The token has expired or was never written | The 401 has no case in Error handling | The client says the S3DF sign-in is missing or has expired, and how to renew it |

---

## Goals

1. Every catalog request the client makes goes through one shell helper shipped in `skill/`, and only the helper reads the token.
2. The token appears in no process's arguments and in no file other than the token file.
3. The token goes only to `https://agent-knowledge-hub.slac.stanford.edu`.
4. A missing, malformed, or refused token gets a message that names the cause and says how to renew it (FR-7).

## Non-Goals

- Changing the token's audience. Token exposure, below, states what that leaves in place.
- Requests to GitHub. Clones carry no catalog token, and the helper never sends one there.
- The dev and stage catalogs. The helper's origin is the production catalog only.
- Pre-approving the helper so that a prompting session does not ask before each call. FR-6 rules out `allowed-tools`; a managed-settings allow rule is for each deployment to decide. § Permission prompts counts the prompts this leaves.

---

## Requirements

### Functional

- **FR-1:** One helper. The client makes every authenticated request through a shell helper shipped in `skill/` and run as `sh ${CLAUDE_SKILL_DIR}/<helper>`. Claude Code replaces `${CLAUDE_SKILL_DIR}` with the directory holding the skill's `SKILL.md`, and for a plugin skill with the skill's subdirectory inside the plugin (Measured facts). The `SKILL.md` runs the helper through `sh` because Cogito installs the folder's files with mode 0644, so the helper is not executable there. A helper is needed at all because the client is otherwise prose the model follows, and an instruction cannot guarantee where the token goes. The helper has no mode that prints the token or the `Authorization` header, because the model can run any mode it has; a `headersHelper` that a later task adds for #047 or for #051's deferred SLAC servers must print the header to Claude Code, so it would be a separate script that shares FR-2 and FR-3 (Relationship to Other Tasks).
- **FR-2:** Token location. The helper reads the token from the account's real home, `$(getent passwd "$(id -un)" | cut -d: -f6)/.s3df-access-token`, and falls back to `~/.s3df-access-token` when `getent` returns no home or that file is absent. An empty result, including from a system without `getent` such as macOS, counts as no home, so the helper never checks `/.s3df-access-token`. A file present in the real home that FR-3 refuses is refused, not skipped: the helper does not fall back to `$HOME` for it. The helper reads no environment variable for the token, and Submit's `AGENT_KNOWLEDGE_HUB_TOKEN` override is removed (Open Design Question 5).
- **FR-3:** Token shape. The helper refuses a token file holding anything but base64url segments and dots. After carriage returns and newlines are removed, the content must be non-empty and contain only `A`–`Z`, `a`–`z`, `0`–`9`, `.`, `_`, and `-`. Cogito's `s3df-mcp-headers`, the helper that hands the same token to its MCP gateway, applies the same rule.
- **FR-4:** No argument, no file. The helper hands the `Authorization` header to curl through a pipe on file descriptor 3 (`printf 'Authorization: Bearer %s\n' "$token" | /usr/bin/curl ... -H @/dev/fd/3 ... 3<&0`, with curl's standard input given back to the caller's for FR-5's body), so the token is in no process's arguments and in no file (Measured facts › Header on file descriptor 3). Every command that receives the token is a shell builtin (`printf`, `case`, `read`) or reads it from a pipe or from the token file itself, as `tr -d '\r\n' < "$file"` does for FR-3: the helper gives the token to no external command as an argument, and carries it in no here-document or here-string, because bash before 5.1 writes a here-document to a temporary file and `/bin/sh` is bash on some S3DF nodes. It writes no file holding the token. As its first commands, before FR-10's argument check and before it reads the token file, the helper runs, in this order: `set +ax`, so tracing (`sh -x`, or `SHELLOPTS=xtrace` under bash) and allexport (`sh -a`) are off; `unset -f` for `printf`, `test`, and every other command name it runs, because bash run as `sh` lets an exported function replace a builtin, and a `test` that always succeeds would pass any argument check written with it; `unset` for every variable it assigns, because a variable that arrives exported stays exported after `set +a`, so a token assigned to it would reach curl's environment; `PATH=/usr/bin:/bin` and `LC_ALL=C`, so `getent`, `id`, and `cut` are the system's and FR-3's character check is byte-wise; and `ulimit -c 0` (Measured facts › Shell tracing and exported functions). The helper never runs `[` and writes each check with `test` or `case`, because bash 4.4 run as `sh`, which is `/bin/sh` on RHEL 8, imports an exported `BASH_FUNC_[%%` but refuses `unset -f '['` as not a valid identifier: the function would survive the prologue, and the refused `unset` would print an error line on every call (same row).
- **FR-5:** Fixed destination. The helper takes exactly two arguments, a method and a path, and passes curl nothing else from its arguments. The method is `GET` or `POST`. The path begins with `/cli/api/`, contains only `A`–`Z`, `a`–`z`, `0`–`9`, `.`, `_`, `~`, `-`, and `/`, and holds no `.` or `..` segment and no `//`, because curl resolves dot segments, `%2e%2e` included, before it sends a request (Measured facts › curl and the path), and a path outside `/cli` reaches `ingress-frontend` and its Vouch `auth-url` subrequest instead of the backend. A request body, when there is one, comes on the helper's standard input and reaches curl as `--data-binary @-`; it is never an argument, because `-d`, `--data`, and `--data-binary` read a file when their value begins with `@`. For `POST` the helper also passes the fixed argument `-H 'Content-Type: application/json'`, because `--data-binary` otherwise labels the body `application/x-www-form-urlencoded` and the backend answers a JSON body under that type with 422 (Measured facts › Request body type). The helper refuses any other method, any other path, and a third argument, and then makes no request. It sends the request only to `https://agent-knowledge-hub.slac.stanford.edu` joined with the path; runs curl as `/usr/bin/curl` with `-q` as its first argument, so no `.curlrc` is read; passes no `-L`, so curl does not follow a redirect; and unsets `CURL_CA_BUNDLE`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `SSLKEYLOGFILE`, and `CURL_HOME` before running curl, because curl honours the first four from its environment even with `-q` (Measured facts › curl's environment). It keeps the proxy variables: with the trust store fixed and no key log, a proxy sees the host in CONNECT and not the header, and Claude Code's Bash sandbox reaches the network only through the proxy those variables name, so clearing them would break sandboxed sessions (Measured facts › curl's environment). Every curl option and `-w` variable the helper uses exists in curl 7.61.1, the version on S3DF nodes outside Cogito (Measured facts › curl on S3DF nodes); FR-7's HTTP status therefore comes from `-w '%{http_code}'`, not from `--fail-with-body` (curl 7.76.0) or a `%{stderr}` write-out (curl 7.63.0). Text in a catalog entry therefore cannot steer the token to another host through a call that uses the helper's interface; FR-6 states what the helper cannot bind.

  The method and path must also match a row of the table below, where `<slug>` and `<file path>` stand for text that meets the path rule above and `<slug>` is one path segment. The helper refuses any other pair, because the token authorises routes the client never sends, such as `POST /cli/api/admin/skills/<slug>/deactivate` for an admin and `POST /cli/api/skills/<slug>/flag` for anyone (`backend/app/routers/admin.py`, `backend/app/routers/skills.py`), and once a user stops the prompts for the helper (FR-9), the helper's own checks are all that stand between a catalog entry's text and those routes. A task that adds a catalog request adds its row in the same change.

  | Method | Path | Sent by |
  |---|---|---|
  | `GET` | `/cli/api/skills/summary` | Search |
  | `GET` | `/cli/api/skills/<slug>` | Install, Validate's slug check |
  | `POST` | `/cli/api/me/installs/<slug>` | The install event |
  | `POST` | `/cli/api/skills/<slug>/rate` | Rate |
  | `POST` | `/cli/api/skills` | `submit <path>` |
  | `GET` | `/cli/api/skills/<slug>/files/<file path>` | #048's file fetches; added by #048 |
  | `GET` | `/cli/api/skillsets/<slug>` | #006's `install skillset`; added by #006 Slice 4 |
- **FR-6:** `SKILL.md` rules. The `SKILL.md` tells the model to call only the helper for hub requests and never to read, print, or decode the token file. It also tells the model to run the helper only as `sh ${CLAUDE_SKILL_DIR}/<helper> <method> <path>`, with no environment assignment before it and no `sh` option such as `-x`, and, for a `POST` (FR-10), with standard input from a `printf` pipe, a `<` redirect of a file the client wrote for that request, or, for the install event, `< /dev/null`, never from the token file; never to copy, edit, or pipe the helper's code into a shell; and never to give the token file to any command, as an argument or as a redirection. These rules are the client's only control against a model that runs other commands: a changed copy of the helper, or a body redirected from the token file, sends the token without the model reading it, and the helper cannot detect either. The permission prompt is not a control on reading the token, because Claude Code runs `cat`, `head`, and its other read-only commands without a prompt in every mode; it shows the user only the later command that sends the token somewhere (Measured facts › Claude Code permissions). A deployment that wants the read blocked adds a `permissions.deny` rule such as `Read(//sdf/home/**/.s3df-access-token)`: Claude Code applies a Read deny rule to its file tools, to `cat`, `head`, `tail`, `sed`, and `tee`, and to redirection targets, but not to a subprocess that opens the file itself, so the helper keeps working. A sandbox `denyRead` rule would stop the helper too. It must still pass Cogito's content rule for skills it loads into every session, or Cogito's build refuses the lock row that pins this repository. That rule admits only the frontmatter keys `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `version`, `license`, `metadata`, `disable-model-invocation`, `user-invocable`, and `disallowed-tools`; refuses inline shell, meaning any `` !` `` and any fence opened with ```` ```! ````; and refuses a symlink or submodule in the skill folder. The helper therefore cannot be pre-approved with `allowed-tools` or run through inline shell. The `SKILL.md` on `main` carries only `name` and `description` and no inline shell, so it passes as of 2026-10-14.
- **FR-7:** Sign-in messages. Error handling in `skill/SKILL.md` gains the three cases below. For each, the client shows the case's cause line and then the renewal steps, as written here. The client does not print or read out the token. For a 401 it shows these lines instead of the response body, because the catalog answers an expired token with "Token expired. Re-run 's3df login' to refresh your session." (`_validate_slac_jwt` in `backend/app/auth.py`), which is the wrong step in Cogito. In the first two cases the helper makes no request. The helper reads the token file on every call (FR-2), so a renewed token works on the next request without restarting the session.

  | Case | Signalled by | Cause line |
  |---|---|---|
  | No token file | The helper finds neither file in FR-2 | `No S3DF sign-in found at <each path the helper checked>.` |
  | Malformed token file | The helper refuses the file under FR-3 | `The S3DF token file <path> does not hold a valid token.` |
  | Token refused | The catalog answers 401 | `The catalog did not accept your S3DF sign-in. It has most likely expired.` |

  Renewal steps, shown after every cause line:

  ```
  To sign in again:
    - In Cogito: open Cogito in a new private browser window and sign in.
    - On an S3DF node outside Cogito: run  s3df login
      (if the shell cannot find s3df: /sdf/sw/s3df-cli/bin/s3df login)
    - On a computer outside S3DF: use this client from Cogito or from an S3DF node.
  Then ask again here; this session does not need to restart.
  If the same message comes back right after you sign in, the problem is probably
  on the catalog's side: report it at https://agent-knowledge-hub.slac.stanford.edu
  ```

  The helper's exit status tells these cases apart from each other, from an HTTP error, from a network failure, and from an argument it refused under FR-5; FR-10's table gives each value. On an HTTP error it still prints the status and the response body, so the existing 404 and 410 cases keep working; the 410 case reads `superseded_by_slug` from the body. Error handling also gains the cases below, one for each FR-10 outcome that the three sign-in cases and the existing 404, 410, and network-error cases do not cover. The existing network-error case, which suggests retrying, keeps exit 7 with any curl exit other than 60. The report line is `Report it at https://agent-knowledge-hub.slac.stanford.edu`.

  | FR-10 exit | The client shows | Next step |
  |---|---|---|
  | 2 | `The hub client refused a request it does not make (<argument>). Nothing was sent.` | The client does not retry the request another way. When the request came from a catalog entry's text, it suggests flagging that entry on its catalog page; otherwise it shows the report line |
  | 6 with a 3xx status | `The catalog answered with a redirect (HTTP <status>), which this client does not follow.` | The report line |
  | 6 with any other status that has no case | `The catalog answered HTTP <status>.`, then the response body's `detail` field when the body is JSON and `detail` is a string | For a 5xx, `Try again in a few minutes.` and then the report line. For a 4xx, the report line only when there is no string `detail` |
  | 7 with `curl exit 60` | `The catalog's certificate could not be checked against this computer's own certificates (curl exit 60). The client sends your sign-in only over a connection it can check that way, so it does not work through a proxy that decrypts HTTPS.` | `If this session runs behind such a proxy, for example Claude Code's sandbox with network.tlsTerminate set, use the client from a session without it.` and then the report line. Exit 60 is curl's answer to a certificate outside its trust store (Measured facts › curl's environment), which is what FR-5's unset variables produce behind such a proxy |
  | 1 | `The hub client failed before sending a request: <last line of standard error>` | The report line |
- **FR-8:** Test. A test in this repository runs the helper against a fake server and asserts that the token appears neither in curl's `/proc/<pid>/cmdline` nor in the helper's output, and that a URL or a curl option given as an argument is refused. The test is `backend/tests/test_hub_request_helper.py`, in the existing pytest suite, so `make -C backend test` and `python -m pytest -q` in `backend/` run it; the repository has no CI, and a test under `skill/` would ship to every Cogito session, because Cogito copies the whole folder. It runs the helper through `subprocess` and serves the fake server from a thread in the test process, and its cases that run the helper are skipped where `/proc/self/cmdline` does not exist; its static checks on `skill/` (§ Test Plan) are not. It never runs the shipped helper, only the copy that Open Design Question 1 describes, so that a refusal that regressed cannot send the developer's real token to the production catalog. It generates the fake token at run time, for example with `secrets.token_urlsafe`, so that no command line of the test run holds it; a fake token written as a literal in a command shows up in the Bash tool's own command line and makes the scan report a leak that is not the helper's (Measured facts › Bash tool streams and `/dev/fd`). AC-2's check reads every `/proc/<pid>/cmdline` it can open while the fake server holds the request, not only curl's. For each refusal in AC-3, it asserts that the fake server logged no request, not only that the exit status is non-zero. It runs every case under `dash` and under bash invoked through a link named `sh`, each when present, because `/bin/sh` is dash in Cogito and is bash on RHEL 8, the system on S3DF nodes outside Cogito (not measured; Measured facts › Shell tracing and exported functions). It passes the helper an environment with no proxy variable, except in the one case that checks FR-5 keeps them, because curl sends even a loopback URL through `http_proxy`, and Claude Code's Bash sandbox sets the proxy variables (Measured facts › curl and a loopback proxy, › curl's environment).
- **FR-9:** First-call notice. Before its first helper call in a conversation, the client tells the user: `Catalog requests run through <script>, a script in this skill that reads your S3DF token and sends it only to https://agent-knowledge-hub.slac.stanford.edu. If Claude Code asks before running it, you can stop the questions: choose "don't ask again" only if the rule it offers starts with sh <script>, or add the rule Bash(sh <script> *) with /permissions. A rule for all of sh would let any shell command run without asking. After a client update the script's path can change, and Claude Code then asks again until you add the rule for the new path.` `<script>` is the helper's full path, `${CLAUDE_SKILL_DIR}/hub-request.sh` as Claude Code expands it (FR-1): the dialog shows the rule it would save, as `Yes, and don't ask again for: <rule>`, but the user can check that rule only against a path the notice prints, and cannot type the rule into `/permissions` without it. The warning in the notice is there because Claude Code's documentation does not say how many words of `sh <path> GET <path>` the offered rule keeps, and a rule matching `sh` with any arguments approves `sh -c` with any command (Measured facts › Claude Code permissions). The rule to accept, or to add with `/permissions`, is `Bash(sh <skill directory>/<helper> *)`. A rule accepted in the dialog is saved for the current git repository only; one added with `/permissions` to user settings, `~/.claude/settings.json`, applies in every project (Measured facts › Claude Code permissions). For a plugin install, `<skill directory>` holds the plugin's version, so the rule stops matching after each client update and the prompts return (Measured facts › `${CLAUDE_SKILL_DIR}`); in Cogito the managed skill's path does not change between releases. A rule that replaces the version with `*` would also approve a changed copy of the helper placed at a path that matches it. `<helper>` is the helper's file name, `hub-request.sh` (FR-10), which says what the script does, because a session that asks before each Bash command shows the user only the command line. When the user declines the install event's helper call, the install still counts as done, as for any other install-event failure. § Permission prompts counts the prompts each command causes.
- **FR-10:** Helper interface. The helper is `skill/hub-request.sh`, run as `sh ${CLAUDE_SKILL_DIR}/hub-request.sh <method> <path>` (FR-1, FR-5, FR-6). A `GET` never reads standard input. Every `POST` sends its standard input as the body (FR-5): Rate pipes its body in (`printf '{"value":%d}' <n> | sh ...`), Submit redirects from the JSON file it wrote (`sh ... < <file>`), and the install event, which has no body, runs with `< /dev/null`, because from a terminal curl would otherwise wait for input. The helper checks its arguments before it opens the token file. This table is the single statement of the helper's outcomes; FR-7 and `skill/SKILL.md` › Error handling map to it.

  | Exit | Outcome | Request sent | Standard output | Last line of standard error |
  |---|---|---|---|---|
  | 0 | HTTP 2xx | Yes | The response body, unchanged | `agent-knowledge-hub: HTTP <status>` |
  | 2 | Argument refused under FR-5 | No | Nothing | `agent-knowledge-hub: refused <argument>` |
  | 3 | No token file (FR-7, first case) | No | Nothing | `agent-knowledge-hub: no token file: <each path checked>` |
  | 4 | Token file refused under FR-3 (FR-7, second case) | No | Nothing | `agent-knowledge-hub: malformed token file: <path>` |
  | 5 | HTTP 401 (FR-7, third case) | Yes | The response body, which the client does not show | `agent-knowledge-hub: HTTP 401` |
  | 6 | Any other HTTP status, including a 3xx the helper did not follow | Yes | The response body, unchanged | `agent-knowledge-hub: HTTP <status>` |
  | 7 | curl exited non-zero: it failed to resolve, connect, complete TLS, or finish the transfer. curl's exit status decides this row, not `%{http_code}`, because a response cut short leaves a status and part of the body behind (Measured facts › Truncated response) | Attempted | Nothing; the partial body is discarded | `agent-knowledge-hub: network error (curl exit <n>)`, after curl's own `curl: (<n>) ...` line, which `-sS` keeps while it hides the progress meter |
  | 1 | The helper failed for another reason, such as `mktemp` | No | Nothing | The failing command's message |

  The status line starts with a newline, so that it does not join the last line of a body that has none. The helper writes the response body to a file in `$TMPDIR`, taking the name from `mktemp -u` with no template and no directory, because Claude Code's Bash sandbox points `$TMPDIR` at the one temporary directory a sandboxed command may write to (Measured facts › Temporary files). The caller can set `$TMPDIR`, and curl opens an `-o` path only when the response arrives, so another user who can write that directory could by then have replaced the file with a symlink, and curl would write the response through it (Measured facts › Response file). The helper therefore opens the file once and never by name again: after the token check, under `umask 077` and `set -C`, it runs `command exec 5>"$name" || exit 1`, which refuses a name that already exists as a regular file, as a symlink to one, or as a symlink to nothing; it still opens an existing FIFO or device, or a symlink to one, which another user could place there only by guessing the random name before the open (Measured facts › Response file); it also exits 1 rather than dash's 2 when the open fails; it then removes the name, passes curl `-o /dev/fd/5`, and copies `/dev/fd/5` to its standard output. On Linux, opening `/dev/fd/5` opens the file again even after its name is removed. With no name left once curl starts, a killed helper leaves no file behind, which a `trap ... EXIT` does not ensure under dash. It reads the status from `-w '%{http_code}'` (FR-5); the file holds the response, never the token. It never names `/dev/stdout`, `/dev/stderr`, or a `/dev/fd/<n>` that is a copy of either as curl's `-o` or `-D` target; file descriptor 5 is not such a copy, because only this call writes its file, so reopening it at offset 0 loses nothing. On Linux, curl opening such a path opens the file behind it again, at offset 0 and truncated, and the Bash tool gives every command a regular file as standard output and standard error, so two helper calls in one command would leave only the second response, after a run of NUL bytes (Measured facts › Bash tool streams and `/dev/fd`). The header's `-H @/dev/fd/3` (FR-4) is not affected, because file descriptor 3 is a pipe.

### Acceptance Criteria

- **AC-1:** Given a fake token file in the test copy's real-home directory (Open Design Question 1) and none in `$HOME`, when the helper sends `GET /cli/api/skills/summary` to the fake server, then the request carries that token.
- **AC-2:** Given a request the fake server holds open, when the test reads curl's `/proc/<pid>/cmdline` and `/proc/<pid>/environ`, then the token is absent from both, and it is absent from the helper's standard output and standard error, including when the helper runs as `sh -x`, as `sh -a`, with an exported variable of the same name as the one the helper holds the token in, and, where `/bin/sh` is bash, with `SHELLOPTS=xtrace` in its environment. `sh -a` and the exported variable put the token in curl's environment and nowhere else, so only the `environ` check detects them (Measured facts › Shell tracing and exported functions).
- **AC-3:** Given an argument that is a URL, a path not beginning with `/cli/api/`, a path with a `..` or `.` segment, `//`, `%`, or `\`, a method other than `GET` or `POST`, a method and path that match no row of FR-5's route table (for example `POST /cli/api/admin/skills/x/deactivate`), a third argument, or a curl option such as `--url`, `-K`, `--config`, or `-x`, when the helper runs, then it exits non-zero and makes no request.
- **AC-4:** Given a fake server that answers with a redirect to another host, when the helper sends a request, then it does not request the redirect target.
- **AC-5:** Given no token file in either place, or one holding a character outside FR-3's set, when the helper runs, then it makes no request, the client shows FR-7's cause line for that case, naming the path or paths the helper checked, followed by FR-7's renewal steps, and neither the helper's standard output nor its standard error contains the file's content, tested with a fresh fake token followed by a space.
- **AC-6:** Given a 401 from the catalog, when the client handles it, then it shows FR-7's "Token refused" cause line and renewal steps, not the response body, and prints no token.
- **AC-7:** Given `skill/SKILL.md` at the commit that ships this task, then its frontmatter has no key outside FR-6's list and its text holds neither `` !` `` nor ```` ```! ````.
- **AC-8:** Given a fake server that answers 404, then 410 with a body holding `superseded_by_slug`, then 401, and then no server listening, when the helper sends a request to each, then its output carries the HTTP status and the response body for the 404 and the 410, and its exit status differs between the HTTP-error, 401, network-failure, and refused-argument (AC-3) cases, with the values in FR-10's table.
- **AC-9:** Given a local TLS server that presents a self-signed certificate for the test copy's origin host, and `CURL_CA_BUNDLE`, `SSL_CERT_FILE`, or `SSL_CERT_DIR` naming that certificate, or `SSLKEYLOGFILE` naming a path, when the helper sends a request, then curl refuses the certificate and no file exists at the key-log path.
- **AC-10:** Given one command that runs the helper twice with its standard output and standard error redirected to one regular file, with a line written before, between, and after the two calls, then the file holds all three lines and both responses in order and no NUL byte; and given a `POST` whose standard input is 300,000 random bytes, then the fake server receives a body of the same length and SHA-256 digest (FR-10).

### Definition of Done

- [ ] FR-1 to FR-10 built; AC-1 to AC-10 pass
- [ ] The **Token file** line in the header block of `skill/SKILL.md` names the real home and the fallback, and every section that sends a catalog request (Search, Install and the install event, Validate's slug check, Rate, Submit; Update reaches the catalog through Install) calls the helper with a path that begins with `/cli/api/` (Measured facts › Request paths). The **Catalog base URL** line agrees with those paths. Rate and Submit no longer name the token file or `s3df login` themselves, and Submit no longer mentions `AGENT_KNOWLEDGE_HUB_TOKEN` (Open Design Question 5)
- [ ] `version` in `.claude-plugin/plugin.json` higher than its value on `main` immediately before the shipping commit merges, checked again after any rebase, because an existing plugin install receives a new copy only when the plugin's computed version changes (#006 › References › Claude Code plugin updates). #006 Slice 4 and #048 raise the same field, and a value equal to one they already merged gives existing installs nothing new
- [ ] CHANGELOG entry under `## Unreleased` naming the helper, the new token location, FR-7's sign-in messages, and the commands an existing plugin user runs to receive the update (#006 › Delivery Slices › Slice 4 names them). It says, in a user's terms, that every catalog command, Search and Install included, sends the S3DF sign-in, that the client now finds it in a Cogito session, that a user whose token is in their own home directory needs to do nothing, and that a session which asks before each Bash command now asks before each catalog request. Because Open Design Question 5 drops `AGENT_KNOWLEDGE_HUB_TOKEN`, the entry carries a paragraph inside it with the bold lead-in **Breaking change:**, the form the file uses for **New config keys:**, not a `###` heading, since each `###` heading under `## Unreleased` is one task's entry. The paragraph says that a job which set the variable now gets FR-7's "No S3DF sign-in found" message, and that writing the token to `.s3df-access-token` in the job's home directory replaces the variable and also works with the previous client, which reads that file when the variable is unset
- [ ] An ADR in `docs/adr/`, numbered with the next ADR-U number not already used in `docs/adr/` or `todo/` (`grep -rhoE 'ADR-U[0-9]+' docs todo | sort -uV | tail -1`). It records FR-1, FR-2, FR-4, and FR-5 as one decision; each rejected alternative with the fact that rules it out (the `$(cat …)` header in curl's arguments, `allowed-tools` or inline shell, a helper that accepts any URL, and each alternative that FR-1, FR-5, and Open Design Questions 1, 2, 4, and 5 reject); and the consequences: a hostname change needs a client release, the dev and stage catalogs are out of the client's reach, a task that adds a catalog request adds a row to FR-5's route table, automation writes the token file instead of setting a variable, the helper cannot stop a model that reads the token file or runs a changed copy (FR-6, with the Read deny rule a deployment can add), and how a header-printing helper that #047 or a follow-up to #051 adds would relate to this one
- [ ] `skill/hub-request.sh` opens with a comment stating FR-4, FR-5, and FR-10's exit statuses, saying why the origin has no override and that `skill/SKILL.md` › Error handling depends on those exit statuses, and naming the ADR and the test, `backend/tests/test_hub_request_helper.py`. The test says in a comment how it reaches the fake server (Open Design Question 1)
- [ ] `frontend/app/guides/agent-knowledge-hub/page.tsx` › CLI authentication says that every command that contacts the catalog needs the S3DF sign-in, replacing the sentence that read-only commands work without authentication. It says where the client finds the token (FR-2), including in a Cogito session, gives FR-7's renewal steps as FR-7 writes them, and applies the **Token expiry** note to every catalog command, not only write commands, quoting FR-7's "Token refused" cause line in place of *"Token expired"*, which the client no longer shows (FR-7). It keeps the sentence that the user never pastes a token and adds that the token goes only to the catalog. It carries FR-9's notice, says that a session which asks before each Bash command asks before each catalog request (§ Permission prompts), and says how to stop those prompts with the rule FR-9 names, adding that a rule accepted in the dialog applies in the current repository only, that one added with `/permissions` to user settings applies in every project, and that, for a plugin install, the prompts return after each client update (FR-9). It says that catalog commands are supported in Cogito and on S3DF nodes only, as FR-7's third renewal step says
- [ ] `frontend/app/guides/troubleshooting/page.tsx` gains an entry for FR-7's sign-in messages that gives FR-7's renewal steps and links to `/guides/agent-knowledge-hub#cli-auth`, an entry for FR-7's `curl exit 60` certificate message that gives its next step, and an entry for permission prompts that return after a client update, which links to the same section
- [ ] `README.md` › Install without leaving your assistant says in one sentence that the client needs an S3DF sign-in and how to renew it (FR-7); #047 AC-3 places its own error message beside that sentence
- [ ] The shipping commit is on `main` or a tag of `slaclab/agent-knowledge-hub`, because Cogito's lock refuses a commit that no branch or tag contains

---

## Token exposure

The helper makes the catalog one more service that receives the account's S3DF token. The token is not bound to the catalog: the backend accepts the audience `s3df` (Measured facts), which Cogito TODO #200 records as the audience every other S3DF service accepts. A compromise of the backend, or of anything that records its request headers, therefore exposes the token of every user whose session calls it, and that token works at every other S3DF service. This task does not change the exposure. An audience issued for the catalog alone would bound it and is outside this task.

---

## Permission prompts

In a session that asks before each Bash command, every helper call is one prompt, because nothing pre-approves the helper (Non-Goals). The counts below follow from the flows in `skill/SKILL.md` and #006 › FR-7, at one helper call per catalog request. They leave out the git, `cp`, and `claude mcp add` calls that Install already makes, which prompt today.

| Command | Helper calls | Requests |
|---|---|---|
| Search | 1 | `GET /cli/api/skills/summary` |
| Install | 2 | `GET /cli/api/skills/<slug>`, then the install event `POST /cli/api/me/installs/<slug>` |
| Rate, Validate, `submit <path>` | 1 each | The command's one catalog request |
| `install skillset` with M members (#006 › FR-7) | 1 + 3M, or 1 + 2M if the loop reuses the confirm rule's member fetch instead of repeating Install's first request | The skillset fetch and M member fetches before the confirm question, then Install's requests for each member |

A skillset of 10 members therefore causes 21 to 31 prompts, 10 to 20 of them after the user has confirmed. #006 › FR-7's confirm rule, which says "a user who confirms can leave the run unattended", holds only in a session that does not prompt for the helper. #048's file fetches add one helper call per file. FR-9's notice tells the user what the prompt is for and that it can be silenced.

A saved rule for the helper does not silence every call. Claude Code matches each part of a pipeline and checks an input redirect's file (Measured facts › Claude Code permissions), so Submit's `< <file>` (FR-10) still asks when the file is outside the session's working directories, and Rate's `printf … |` still asks unless `printf` is one of Claude Code's read-only commands, which the documentation does not say. Neither was observed. The install event's `< /dev/null` is not checked.

---

## Open Design Questions

1. **How the test reaches a fake server when the origin is fixed.** *Resolved by the security review, round 1.* An environment variable or an argument that changes the origin would let the model change it too, so the shipped helper reads neither. The test runs a copy of the helper in which two lines are replaced: the origin constant, by the fake server's address, and the real-home lookup of FR-2, by a temporary directory the test creates. It asserts that the copy differs from the shipped helper on those two lines only, and that the shipped helper's origin is `https://agent-knowledge-hub.slac.stanford.edu`. Replacing only the origin is rejected: the copy would then read the developer's real token from the real home and send it to the fake server, and a failing assertion on the received header would print it into the test output. For the same reason the fake server's assertions report a mismatch without printing the header they received.
2. **How the request body reaches curl when standard input carries the header.** *Resolved by the security review, round 1: the header moves to file descriptor 3 (FR-4) and the body comes on standard input (FR-5).* Rejected: `--data-raw`, because Linux caps one argument at 128 KiB (`MAX_ARG_STRLEN`), a `submit` of a skill directory can exceed that, and the body would be readable in `/proc/<pid>/cmdline`; `-d`, `--data`, or `--data-binary` with the body as the argument, because a value beginning with `@` makes curl read that file, so `@<real home>/.s3df-access-token` would send the token as a body, and `POST /cli/api/skills` publishes `snapshotted_files` to every signed-in user; and a body file named by the caller, because the helper would need a rule for which files it reads. Also rejected: curl's `--variable token@<file>` with `--expand-header`, which would read the token without any descriptor, because it needs curl 8.3.0 (Measured facts › curl on S3DF nodes).
3. **Whether curl's environment and configuration can change the destination.** curl reads `~/.curlrc`, or `$CURL_HOME/.curlrc`, unless `-q` is its first argument, and the model can prefix the helper call with environment variables such as `PATH` or `CURL_HOME`. Running curl by absolute path with `-q` first closes the configuration-file route. *Resolved by the security review, round 1, in FR-4 and FR-5:* the CA-bundle variables and `SSLKEYLOGFILE` are unset, because curl honours them even with `-q` (Measured facts › curl's environment); the proxy variables are kept, because a proxy cannot read the header once the trust store is fixed and no key log is written; `PATH` is set inside the helper. DNS needs no treatment: a resolver variable such as `LOCALDOMAIN` or `RES_OPTIONS` can send curl to another address, but that address cannot present a certificate for the hub's hostname from the fixed trust store. The helper cannot bind variables that run code in `sh` itself, such as `LD_PRELOAD`; those are the class FR-6 describes.
4. **Which methods the helper accepts.** The client uses `GET` (Search, Install, file fetches) and `POST` (Rate, the install event, Submit). A fixed list makes FR-5's refusal of an option-shaped method a one-line check. *Resolved by the security review, round 1:* `GET` and `POST` only, with FR-5's route table on top, because a method is copied into the request line and the backend's `DELETE`, `PUT`, and `PATCH` routes are ones the client never sends.
5. **Whether Submit keeps its `AGENT_KNOWLEDGE_HUB_TOKEN` override.** FR-2 names the token files only. *Resolved by the engineering review, round 1: the override is removed (FR-2).* A token given to the helper through a variable reaches it from a command the model writes, and Claude Code's Bash tool runs each command as `<shell> -c '<command>'`, so `AGENT_KNOWLEDGE_HUB_TOKEN=<token> sh ...` puts the token in that shell's `/proc/<pid>/cmdline` (Measured facts › Bash tool streams and `/dev/fd`), which FR-4 exists to prevent; FR-6 also forbids an environment assignment before the helper. The automation use case that #004 recorded for the variable is served by writing the token file in the job's home directory.
6. **Where `s3df login` writes in a Cogito session, and whether `s3df` is on `PATH` there and on a plain S3DF node.** A Cogito session's shell runs on an S3DF node, so a user may run `s3df login` there instead of FR-7's browser step. If it writes to `$HOME`, the new token lands in the per-machine directory while FR-2 keeps reading the expired one in the real home, and FR-7's message returns after every sign-in. Measure both, record them in Measured facts, and either keep FR-2 or have the helper read the newer of the two files. The `PATH` answer decides whether FR-7's renewal steps need the `/sdf/sw/s3df-cli/bin/s3df` line, which no Measured facts row backs yet.

---

## Measured facts — read 2026-10-14, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| The client's token handling | `skill/SKILL.md` names `~/.s3df-access-token` as **Token file** and mentions the bearer header only under Rate and Submit; Submit also accepts `AGENT_KNOWLEDGE_HUB_TOKEN` | Read `skill/SKILL.md` on `main` |
| The client's error cases | 404, 410, path traversal, 403 rate limit, network error; no 401 | Same file, § Error handling |
| The client's frontmatter | `name` and `description` only; no `` !` `` and no ```` ```! ```` in the text | Same file |
| Request paths | The catalog base URL is `https://agent-knowledge-hub.slac.stanford.edu/cli`, so every request path begins with `/cli/api/` | Same file; `docs/adr/adr-p08-split-ingress.md` |
| Token audience and issuer | `JWT_AUDIENCE=s3df`, `JWT_ISSUER=https://dex.slac.stanford.edu` | `kubernetes/overlays/prod/kustomization.yaml` |
| `$HOME` in a Cogito session | A per-machine directory, not the account's home; `.s3df-access-token` is absent there and present in the real home | In a Cogito session on `sdfiana008`, 2026-10-14: `$HOME` was `/sdf/home/y/ytl/.cogito/hosts/sdfiana008`, `getent passwd "$(id -un)" \| cut -d: -f6` gave `/sdf/home/y/ytl`, and `ls` found the token file only in the latter. The image's `/etc/nsswitch.conf` reads `passwd: files`, so in Cogito `getent` answers from the image's own `/etc/passwd`, not from SSSD; the lookup on a plain S3DF node was not run. Cogito TODO #200 › Measured facts records the same from 2026-10-05 |
| `curl -H @-` | curl 8.14.1 in the Cogito image on `sdfiana008` reads the header line from standard input and sends it, and curl's `/proc/<pid>/cmdline` holds no token while the request is open | A local Python server held the request open for 2 seconds while `tr '\0' ' ' < /proc/<pid>/cmdline` printed curl's arguments, 2026-10-14. The header was written by `printf`, a shell builtin, so no other process carried the token either |
| `/proc` on `sdfiana008` | Mounted without `hidepid`, so any user can read another user's process arguments | `grep '^proc ' /proc/mounts`, 2026-10-14 |
| `${CLAUDE_SKILL_DIR}` | "The directory containing the skill's `SKILL.md` file. For plugin skills, this is the skill's subdirectory within the plugin". `.claude-plugin/plugin.json` sets `"skills": "./skill/"`, the manifest form for "one folder holding `SKILL.md` directly", so for a plugin install the variable names `skill/` inside the plugin's cache directory, `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, whose last segment changes with each `version` raise. A managed skill, the kind Cogito installs, lives at `.claude/skills/<skill-name>/SKILL.md` in the managed settings directory, which is `/etc/claude-code/` on Linux, a path with no version segment; the path in the Cogito image was not checked | Quoted in Cogito TODO #200 from the Claude Code `skills` documentation; re-checked against `https://code.claude.com/docs/en/skills` by the security review, 2026-10-14. Manifest form from `https://code.claude.com/docs/en/plugins-reference` › Fields › `skills`; cache layout from `ls -d ~/.claude/plugins/cache/*/*/*` on `sdfiana008`, which listed `mempalace/mempalace/3.3.3` (data-research review). Managed skill location from the same `skills` page › Where skills live and from `https://code.claude.com/docs/en/managed-settings`, read 2026-10-15 (data-research review, round 2) |
| curl and the path | curl 8.14.1 keeps the host of `<origin><path>` for a path beginning with `/`, including `//host/x`, `/@host/x`, and `/\host/x`; it resolves `/cli/api/../../x` and `/cli/api/%2e%2e/%2e%2e/x` to `/x` before sending; it refuses a path holding a space or a newline (exit 3) | A local Python server logged the request line for each path, with curl's `--connect-to` pointing the hub's hostname at it, in a Cogito session on `sdfiana008`, 2026-10-14 (security review) |
| curl's environment | With `-q` first, curl 8.14.1 still trusts a certificate named by `CURL_CA_BUNDLE`, `SSL_CERT_FILE`, or `SSL_CERT_DIR`, and writes TLS session keys to the file `SSLKEYLOGFILE` names, created mode 0644 under umask 022; an explicit `--cacert` overrides `CURL_CA_BUNDLE` and `SSL_CERT_DIR` (`SSL_CERT_FILE` not tried); `OPENSSL_CONF` with `VerifyCAFile` did not change trust. A CONNECT proxy named by `https_proxy` receives only `CONNECT <host>:<port>` with `Host`, `User-Agent`, and `Proxy-Connection`, and no `Authorization`. Claude Code's Bash sandbox "directs commands to it [its proxy] with `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and related environment variables", and `curl --noproxy '*'` inside it fails with `Could not resolve host`; the sandbox proxy does not terminate TLS unless the experimental `network.tlsTerminate` is set | A local TLS server presented a self-signed certificate for `agent-knowledge-hub.slac.stanford.edu`: curl exited 60 without the variables and completed the request with each CA variable, 2026-10-14 (security review). A local proxy logged the CONNECT request head while curl sent a fake token, 2026-10-14 (data-research review). Sandbox behaviour from `https://code.claude.com/docs/en/sandboxing`, read 2026-10-14 |
| Header on file descriptor 3 | `exec 4<&0; printf 'Authorization: Bearer %s\n' "$tok" \| curl -q ... -H @/dev/fd/3 --data-binary @- "$url" 3<&0 0<&4` sends the header from the pipe and the body from the caller's standard input, under dash and under bash 5.2 | Local fake server, fake token, 2026-10-14 (security review) |
| Shell tracing and exported functions | `dash -x` prints `printf`'s arguments, header included, to standard error, and `set +x` stops it from that line on; bash run as `sh` turns tracing on from `SHELLOPTS=xtrace`; bash run as `sh` runs an exported function `BASH_FUNC_printf%%` in place of the `printf` builtin, and `unset -f printf` restores the builtin; a `printf` earlier on `PATH` does not replace the builtin in dash or bash; dash ignores `BASH_FUNC_*`. Under bash run as `sh`, exported `BASH_FUNC_set%%` and `BASH_FUNC_unset%%` do not replace those builtins, `BASH_FUNC_case%%` is refused at import, and an exported `BASH_FUNC_[%%` or `BASH_FUNC_test%%` that returns 0 makes `[ "/etc/passwd" = "/cli/api/x" ]` succeed until `unset -f '[' test` runs. After `set +ax`, a variable the script assigns is absent from a child's environment under `sh -a`, `sh -ax`, and `SHELLOPTS=allexport`; without `set +a`, `sh -a` puts it in the child's `/proc/<pid>/environ` and not in its `/proc/<pid>/cmdline`. A variable that arrives exported, as from `env tok=x sh <script>`, stays exported after `set +a`, so its new value reaches the child's environment; `unset tok` before the assignment stops that. `/proc/<pid>/environ` is mode 0400. Each result holds under dash and under bash run as `sh`, except where it names one shell. `/bin/sh` is dash and bash is 5.2.37 in the Cogito image on `sdfiana008`; `/bin/sh` on S3DF's RHEL 8 nodes outside Cogito was not measured. RHEL 8.10's bash is 4.4.20, and its package installs `/usr/bin/sh` as a link to `bash`. Run as `sh`, that bash imports an exported `BASH_FUNC_[%%` that returns 0, and `unset -f '['` then prints ``unset: `[': not a valid identifier``, returns 1, and leaves the function in place, so `[ a = b ]` still succeeds; it prints that line even when no such function is exported, and the shell carries on. `unset -f` restores `test`, `printf`, `command`, and `umask` there, and exported `BASH_FUNC_set%%` and `BASH_FUNC_unset%%` do not replace those builtins | Fake tokens, 2026-10-14 (security review); the `set`, `unset`, `[`, `test`, allexport, and exported-variable results with run-time fake tokens and `/usr/bin/env` or a background `sleep` as the child, in the Cogito session on `sdfiana008`, 2026-10-15 (data-research review, round 2). The bash 4.4 results with the `/usr/bin/bash` of `bash-4.4.20-6.el8_10.x86_64.rpm` from AlmaLinux 8.10 BaseOS, extracted from the package and run through a link named `sh` in the same session, 2026-10-15; the `/usr/bin/sh` link read from the same package's payload; the cause read from bash 4.4.18's `builtins/set.def`, which checks a function name with `legal_identifier` in posix mode, and `shell.c`, which imports functions before it turns posix mode on for `sh` (engineering review, round 3) |
| Claude Code permissions | "Yes, and don't ask again" for a Bash command saves a prefix rule (the documented example offers `npm test *` for `npm test`) to `.claude/settings.local.json` at the repository root; the documentation does not say how many words of a longer command the offered prefix keeps. An allow rule does not match past a leading assignment of a variable outside a built-in safe list. `cat`, `head`, `tail`, and the other read-only commands run without a prompt in every mode. Read deny rules apply to `cat`, `head`, `tail`, `sed`, `tee`, and redirection targets, and not to a subprocess that opens a file itself. A skill's `disallowed-tools` removes tools only until the user's next message. The Bash prompt shows the rule it would save, as `Yes, and don't ask again for: npm test *`, and offers that option only "when the prompt can show you everything they would allow". A rule saved from the prompt applies in that git repository; to apply a rule in every project, the documentation says to add it to user settings, `~/.claude/settings.json`, and `/permissions` saves a rule to the settings file the user picks. An allow rule must match each subcommand of a pipeline separately; an input redirect `< file` is checked against Read rules and needs approval when the file is outside the working directories, and `/dev/null` is not checked. The read-only set "includes `ls`, `cat`, `echo`, …" and does not say whether it includes `printf` | `https://code.claude.com/docs/en/permissions` and `https://code.claude.com/docs/en/skills`, read 2026-10-14 (security review); the prompt, scope, pipeline, and redirect sentences from the same permissions page, read 2026-10-15 (ux review). The offered prefix for `sh <path> ...` was not observed, because the reviewing sessions ran without prompts |
| curl on S3DF nodes | The Cogito image is Debian 13 (`/etc/os-release`) with curl 8.14.1 (`curl --version`: `security patched: 8.14.1-2+deb13u5`) on the host kernel `4.18.0-553.158.1.el8_10`. RHEL 8.10, the system on S3DF nodes outside Cogito, ships curl 7.61.1 (`curl-7.61.1-34.el8_10.*`). Version floors from curl's documentation: `-H @file` and `-H @-` 7.55.0; `-w '%{http_code}'` 7.18.2; `%{stderr}` in `-w` 7.63.0; `--fail-with-body` 7.76.0; `--variable` and `--expand-*` 8.3.0. The 7.61.1 source confirms the options FR-4, FR-5, and FR-10 use: it skips `.curlrc` only when `argv[1]` is `-q` or `--disable`; `-H @<file>` opens the file and adds one header per line; `%{http_code}` prints as `%03ld`, so `000` when no response arrived; `-s`, `-S`, `-o`, and `--data-binary @-` exist. When it cannot open the `-H @<file>` file, 7.61.1 prints `Failed to open <file>!` and sends the request without that header, where curl 8.14.1 stops with exit 26 and sends nothing. With OpenSSL, 7.61.1 exits 60 (`CURLE_SSL_CACERT`) for a certificate from an untrusted CA, as 8.14.1 does, and 51 for a certificate whose names do not match the host, where 8.14.1 gives 60 | In the Cogito session, 2026-10-14; the image has no `rpm`, so the plain-node version comes from the AlmaLinux 8.10 BaseOS package index and was not run. Floors from `https://raw.githubusercontent.com/curl/curl/master/docs/cmdline-opts/header.md`, `…/write-out.md`, and `…/fail-with-body.md` (data-research review). 7.61.1 behaviour read from `src/tool_operate.c`, `src/tool_getparam.c`, and `src/tool_writeout.c` at tag `curl-7_61_1`, not run; the 8.14.1 exit 26 measured with `-H @/nonexistent/hdr`, 2026-10-15 (data-research review, round 2) |
| Request body type | `--data-binary @-` sends `Content-Type: application/x-www-form-urlencoded`. FastAPI 0.143.0 answers a JSON body to a Pydantic body model with 422 under that type, and also with no `Content-Type`, and with 200 under `application/json`; the backend requires `fastapi>=0.111.0`. The Bash tool gives commands `/dev/null` as standard input, so a `POST` with nothing piped in sends an empty body | A local server echoed curl 8.14.1's `Content-Type`; a three-request `TestClient` script against a one-field model; `backend/requirements.txt`; `ls -l /proc/self/fd/0` in a Bash tool call, 2026-10-14 (data-research review) |
| Bash tool streams and `/dev/fd` | The Bash tool runs each command as `/usr/bin/zsh -c '<command>'`, so the command's text is in that shell's `/proc/<pid>/cmdline`, and gives it one regular file, `.../tasks/<id>.output`, as both standard output and standard error. A prototype helper that wrote the body with `curl -o /dev/fd/3`, fd 3 a copy of standard output, run twice in one command into one regular file, left only the second response at offset 0, then NUL bytes, then the lines written after it; the lines and the response written before it were lost. The same prototype with the body written to a `mktemp` file and copied out kept every line, under dash and under bash 5.2 run as `sh`. A fake token written as a literal in a Bash tool command appeared in that command's `zsh -c` line during a `/proc/*/cmdline` scan; a token generated at run time appeared in no command line | `tr '\0' ' ' < /proc/$$/cmdline` and `ls -l /proc/$$/fd/1 /proc/$$/fd/2` in a Bash tool call in the Cogito session on `sdfiana008`; the prototypes against a local fake server, 2026-10-14 (engineering review) |
| Truncated response | Against a server that announced `Content-Length: 100` and closed the connection after 11 bytes, `curl -q -sS -o <file> -w '%{http_code}'` printed `200`, left the 11 bytes in the file, and exited 18 with `curl: (18) end of response with 89 bytes missing` | curl 8.14.1 against a local Python socket server in the Cogito session on `sdfiana008`, 2026-10-15 (engineering review, round 2) |
| Temporary files | `mktemp` with no arguments is GNU coreutils 9.7 at `/usr/bin/mktemp` in the Cogito image and created `/tmp/tmp.<10 characters>` with mode 0600 while `$TMPDIR` was unset, and `mktemp -u` ("do not create anything; merely print a name") printed such a name and created nothing; `getent`, `id`, `cut`, `tr`, `rm`, `cat`, and `curl` all resolve under `PATH=/usr/bin:/bin` there. Claude Code's Bash sandbox makes "a per-user temp directory" writable and "sets `$TMPDIR` to this directory for sandboxed commands". RHEL 8 ships `mktemp` in coreutils, not run | `mktemp --version` and `command -v` in the Cogito session on `sdfiana008`, 2026-10-15; `https://code.claude.com/docs/en/sandboxing` › Temporary directories, read 2026-10-15 (data-research review, round 2) |
| Response file | curl 8.14.1 held no descriptor on its `-o` file while the server held the request for 1.5 seconds; replacing the `mktemp` file with a symlink during the hold made curl write the response into the symlink's target. Under `set -C`, `exec 5>` onto an existing symlink failed in dash and in bash run as `sh`, and created nothing at the target; it also refused an existing regular file, a symlink to one, and a symlink to nothing, but opened a symlink to `/dev/null` and a symlink to a FIFO, where it waited for a reader (data-research review, round 2); a failed `exec 5>` exited dash with status 2 and bash with 1, and `command exec 5>... \|\| exit 1` exited both with 1. A prototype that opened the file that way, removed its name, ran curl with `-o /dev/fd/5`, and copied `/dev/fd/5` out returned the full response under both shells, and two such calls into one regular file kept every line in order with no NUL byte. A `trap 'rm -f "$f"' EXIT` left the `mktemp` file behind when dash was killed with `SIGTERM` or `SIGHUP`; bash run as `sh` removed it | Prototypes against a local fake server with a token generated at run time, in the Cogito session on `sdfiana008`, 2026-10-15 (security review, round 2) |
| curl and a loopback proxy | With `http_proxy` naming one local server, curl 8.14.1 sent its requests for `http://127.0.0.1:<port>/...` and `http://localhost:<port>/...` on another local server to the proxy, not to the address in the URL | Two local Python HTTP servers logged which one received each request, with no other proxy variable set, in the Cogito session on `sdfiana008`, 2026-10-15 (engineering review, round 2) |

---

## Relationship to Other Tasks

- **Cogito TODO #200 (`slaclab/cogito`), hub request H-1:** Cogito's slice 2 adds a lock row, its FR-5, that loads this repository's `skill/` folder into every Cogito session at a commit that includes this task. That row, and with it slice 2, waits for this task. Cogito reviews the row against FR-8's test; its AC-7 checks the 401 case by reading `SKILL.md` at that commit and checks with `ps` during a live search that no token appears. Whether Cogito's managed settings add FR-6's Read deny rule for the token file, or an allow rule for the helper (Non-Goals), is Cogito's decision; this task ships neither. Slice 2 also waits on a question of Cogito's own, about the MCP servers and agents the client installs, which does not involve this task.
- **#006 (Skillsets):** FR-7 › Auth rule reads the token with `$(cat ~/.s3df-access-token)` inside curl's arguments, which breaks FR-2 and FR-4 here. Slice 4 of #006 should send its requests through this helper. #006's 401 message points to `s3df login`; FR-7 here gives the message for both tasks. #006 Slice 4's Definition of Done also edits four places this task edits: the CLI authentication paragraph of `frontend/app/guides/agent-knowledge-hub/page.tsx`, a 401 case in `skill/SKILL.md` › Error handling, an auth rule next to **Token file**, and a CHANGELOG bullet saying Search and Install send the token. This task owns all four, because Slice 4 is to call this helper and so lands after it; Slice 4 keeps its skillset-specific text and refers to this task for the rest, and adds the `GET /cli/api/skillsets/<slug>` row to FR-5's route table in the same change. Both tasks raise `version` in `.claude-plugin/plugin.json`, under the rule in this task's Definition of Done. § Permission prompts counts the helper calls `install skillset` makes; #006 › FR-7's promise that a confirmed run can be left unattended needs a session that does not prompt for the helper, and #006 should say so. In the `install skillset` loop, exit statuses 3, 4, and 5 from FR-10, and exit 7 with `curl exit 60` (FR-7), stop the loop, because every later member would get the same answer; every other non-zero exit from a member's request, exit 6 with a 404 or 410 included, fails that member alone, under #006 › FR-7's skip and failure rules.
- **#004 (Multi-source scanner abstraction):** added Submit's `AGENT_KNOWLEDGE_HUB_TOKEN` override for automation. This task removes it (Open Design Question 5), and the CHANGELOG entry records the break.
- **#007 (`/agent-knowledge-hub` skill):** the client this task changes.
- **#016 (Bearer JWT auth):** the token `s3df login` writes and the backend validates. This task changes where the client finds it, not how the backend checks it.
- **#047 (marketplace.json reachable from Claude Code):** a marketplace `headersHelper`, if #047 chooses one, needs FR-2, FR-3, and a fixed destination too.
- **#048 (install internal skills through the files route):** its file fetches are catalog requests and go through this helper, and #048 adds their row to FR-5's route table in the same change. FR-5's path rule refuses a `file_manifest` path that holds a space, `+`, `@`, `%`, or any other character outside its set, so #048 either skips and reports such a file or asks this task for a wider rule that still refuses `%2e` and `%2f` in either case. The helper writes a fetched file's bytes to its standard output on every HTTP status (FR-10), so a fetch redirected straight to its destination leaves an error body there on a non-zero exit; #048 writes to a temporary name and renames it only on exit 0.
- **#051 (client confirms MCP servers and agents):** its FR-2 refuses every MCP server that needs the S3DF token and adds no `headersHelper`, so this helper stays the client's only reader of the token. #051's Follow-ups record the deferred `headersHelper`: a separate script that shares FR-2 and FR-3, is not a mode of this one (FR-1), attaches only to servers whose URL is on a fixed list, and is never run by the model. #051 also changes `skill/SKILL.md`, so it needs its own `version` raise under the same rule.

---

## References

Sources the review read on 2026-10-14; Measured facts names the row each one backs.

- curl `-H`/`--header`, including `@-` (7.55.0) and `--proxy-header`: https://raw.githubusercontent.com/curl/curl/master/docs/cmdline-opts/header.md
- curl environment variables (`HTTPS_PROXY`, `ALL_PROXY`, `NO_PROXY`, `CURL_CA_BUNDLE`, `SSL_CERT_DIR`, `SSL_CERT_FILE`, `SSLKEYLOGFILE`, `CURL_HOME`, `XDG_CONFIG_HOME`): https://raw.githubusercontent.com/curl/curl/master/docs/cmdline-opts/_ENVIRONMENT.md
- curl `-w` variables and their versions: https://raw.githubusercontent.com/curl/curl/master/docs/cmdline-opts/write-out.md
- curl `--fail-with-body` (7.76.0): https://raw.githubusercontent.com/curl/curl/master/docs/cmdline-opts/fail-with-body.md
- curl manual (`-q`, `--variable`, `--globoff`): https://curl.se/docs/manpage.html
- curl 7.61.1 source (`.curlrc` and `-q`, `-H @<file>`, `%{http_code}`), read 2026-10-15: https://raw.githubusercontent.com/curl/curl/curl-7_61_1/src/tool_operate.c, https://raw.githubusercontent.com/curl/curl/curl-7_61_1/src/tool_getparam.c, https://raw.githubusercontent.com/curl/curl/curl-7_61_1/src/tool_writeout.c
- RHEL 8.10 curl package (AlmaLinux BaseOS index): https://www.rpmfind.net/linux/RPM/almalinux/8.10/baseos/x86_64/curl-7.61.1-34.el8_10.2.x86_64.html
- RHEL 8.10 bash package, read and run 2026-10-15: https://repo.almalinux.org/almalinux/8.10/BaseOS/x86_64/os/Packages/bash-4.4.20-6.el8_10.x86_64.rpm; bash 4.4.18 source: https://ftp.gnu.org/gnu/bash/bash-4.4.18.tar.gz
- RHEL life cycle: https://access.redhat.com/support/policy/updates/errata
- Linux `MAX_ARG_STRLEN`: https://raw.githubusercontent.com/torvalds/linux/master/include/uapi/linux/binfmts.h
- Claude Code skills (`${CLAUDE_SKILL_DIR}`, `allowed-tools`, managed skills): https://code.claude.com/docs/en/skills
- Claude Code plugin manifest (`skills` path forms, `${CLAUDE_PLUGIN_ROOT}`, hooks): https://code.claude.com/docs/en/plugins-reference
- Claude Code managed settings directory (`/etc/claude-code/` on Linux): https://code.claude.com/docs/en/managed-settings
- Claude Code permissions ("Yes, and don't ask again"): https://code.claude.com/docs/en/permissions
- Claude Code hooks (PreToolUse `permissionDecision`): https://code.claude.com/docs/en/hooks
- Claude Code Bash sandbox (proxy variables, `network.tlsTerminate`, the temporary directory and `$TMPDIR`): https://code.claude.com/docs/en/sandboxing

---

## Test Plan

Generated by /codebase-eng-review on 2026-10-14 and updated in its rounds 2 and 3 on 2026-10-15. The automated cases live in `backend/tests/test_hub_request_helper.py` (FR-8) and run against the test copy of the helper only, never the shipped file, under dash and under bash invoked as `sh` where each exists. The fake token is generated at run time.

Fixtures shared by the automated cases: the test copy (Open Design Question 1), with its origin set to `http://127.0.0.1:<port>` of a fake server that runs in a thread, logs each request's method, path, headers, and body length and SHA-256 digest, and never prints a received header; temporary directories for the copy's real home, for `HOME`, and for `TMPDIR`; and an environment built for each run with no proxy variable (FR-8). AC-9's TLS server uses a self-signed certificate made at run time with `cryptography`, which `PyJWT[crypto]` in `backend/requirements.txt` already installs.

### Affected commands and paths

- `skill/hub-request.sh` — the five rows of FR-5's route table that this task ships (the two marked "added by" #048 and #006 Slice 4 come with those tasks), every exit status in FR-10's table, and the token lookup in FR-2.
- `skill/SKILL.md` — Search, Install and the install event, Validate's slug check, Rate, and `submit <path>` call the helper; Error handling maps FR-10's exit statuses to FR-7's messages and the existing 404, 410, and network-error cases.
- `GET /cli/api/skills/summary`, `GET /cli/api/skills/<slug>`, `POST /cli/api/me/installs/<slug>`, `POST /cli/api/skills/<slug>/rate`, `POST /cli/api/skills` — the requests the helper sends, against the fake server. The rows that #048 and #006 Slice 4 add are tested by those tasks, as new cases of the route-table test below.

### Key interactions to verify

- The token from the test copy's real-home directory reaches the fake server as `Authorization: Bearer <token>` (AC-1), and the token from `$HOME` does when the real-home file is absent.
- Each row of FR-5's route table, with `x` for `<slug>` and `a/b.md` for `<file path>`, reaches the fake server with its own method and path and exits 0; the same path with the other method exits 2, and the fake server logs nothing.
- While the fake server holds a request open, no readable `/proc/<pid>/cmdline` holds the token, curl's `/proc/<pid>/environ` does not, and neither do standard output, standard error, or any file under the test's `TMPDIR`, including under `sh -x`, `sh -a`, `SHELLOPTS=xtrace`, and an exported variable named like the helper's token variable (AC-2).
- A `POST` with a 300,000-byte body on standard input arrives with the same length and digest, labelled `application/json` (AC-10, FR-5).
- A bodiless `POST` with `< /dev/null` sends `Content-Length: 0`.
- A `GET` whose standard input is a pipe the test holds open and never writes to exits within 10 seconds, and the fake server logs no body (FR-10).
- Two helper calls in one command with output redirected to one regular file keep every line in order and write no NUL byte (AC-10).
- A response body with no trailing newline, with standard output and standard error sent to one file, is followed by the status line on a line of its own (FR-10).
- 404, 410, 401, any other status, and no listener give FR-10's exit statuses, the 404 and 410 bodies reach standard output, and the last line of standard error is FR-10's line for each (AC-8).
- On exit 0, standard error holds only FR-10's status line and the newline before it, so a line from the shell itself, such as bash 4.4's refusal of `unset -f '['`, fails the case in the run on a plain S3DF node (FR-4, FR-10).
- A server that announces `Content-Length: 100` and closes after 11 bytes gives exit 7, empty standard output, and `agent-knowledge-hub: network error (curl exit 18)` (FR-10, Measured facts › Truncated response).
- A redirect to a second fake server is not followed: the second server logs nothing, and the exit status is 6 (AC-4).
- The CA-bundle variables and `SSLKEYLOGFILE` change nothing: the TLS server logs no request, the exit status is 7 with `curl exit 60`, and no file exists at the key-log path (AC-9). The last assertion catches a helper that keeps `SSLKEYLOGFILE` although curl refuses the certificate, because curl creates the key-log file before it refuses (engineering review, round 2).
- With `http_proxy` naming a second fake server, the request arrives there, so the helper keeps the proxy variables (FR-5; Measured facts › curl and a loopback proxy).
- Static checks in the same file, which run where `/proc` does not exist too (FR-8): `skill/SKILL.md` frontmatter keys and inline shell (AC-7); `skill/SKILL.md` holds FR-7's three cause lines, its renewal steps, and each message in FR-7's second table verbatim, names `hub-request.sh` for every catalog request, and holds neither `Authorization: Bearer` nor `AGENT_KNOWLEDGE_HUB_TOKEN` (FR-1, FR-7, Definition of Done); no symlink under `skill/`; the shipped helper's origin line is the production origin; the shipped helper runs no `[` command, meaning no `[` at the start of a line or after `;`, `&`, `|`, `(`, `!`, `if`, `elif`, `then`, `while`, or `until` (FR-4); the test copy differs from the shipped helper on exactly two lines.
- Once before merge, on a plain S3DF node (RHEL 8, curl 7.61.1, `/bin/sh` bash): `python -m pytest -q tests/test_hub_request_helper.py` in `backend/`, with the backend's requirements installed. It is the only run that covers FR-5's curl 7.61.1 limit and bash as `/bin/sh`.
- By hand, in a Cogito session and on a plain S3DF node: Search returns results; the first helper call shows FR-9's notice with the helper's expanded path in place of `<script>`; in a session that asks before Bash commands, the rule the prompt offers for the helper is recorded in Measured facts › Claude Code permissions, which has not observed it; during a Search, `ps -ef` from another shell shows no token.
- By hand, by the developer and not the model (FR-6), with the real-home token file moved aside and put back afterwards, which also takes away Cogito's own MCP sign-in for that time: with no file, Search shows FR-7's "No S3DF sign-in found at" line naming both paths; with a file holding `not a token`, the malformed-file line; with a well-formed fake token such as `aaa.bbb.ccc`, the catalog answers 401 and the client shows the "Token refused" lines, not the response body (AC-5, AC-6).
- By hand, in a session that asks before Bash commands: declining the install event's prompt still reports the install as done (FR-9); with the helper's rule saved, whether Rate's `printf` pipe and Submit's `< <file>` still ask is recorded in § Permission prompts, which has not observed it.

### Edge cases

- Each refusal in AC-3 leaves the fake server's request log empty and standard output empty, and the exit status is 2.
- No token file in either place gives exit 3 and names both paths; a file with a space, `$`, or a non-ASCII byte gives exit 4, and so do an empty file and a file holding only a newline (FR-3); a file that ends in `\r\n` is accepted. Standard output is empty on exits 3 and 4.
- `AGENT_KNOWLEDGE_HUB_TOKEN` set to a fresh fake token, with no token file, gives exit 3, and the fake server logs nothing (FR-2).
- `TMPDIR` naming a directory that does not exist gives exit 1, empty standard output, and no request (FR-10).
- An empty real-home lookup falls back to `$HOME` and never reads `/.s3df-access-token`.
- A malformed file in the real home gives exit 4 even when `$HOME` holds a good one (FR-2).
- An exported `BASH_FUNC_printf%%` or `BASH_FUNC_tr%%` under bash run as `sh`, and a directory earlier on `PATH` holding a fake `tr`, receive no token.
- An exported `BASH_FUNC_[%%` and `BASH_FUNC_test%%` that return 0, under bash run as `sh`, do not let an AC-3 argument through, a third argument included: exit 2 and an empty request log (FR-4). Under bash 5.2 this passes even for a helper that runs `[` and removes it with `unset -f`; the run on a plain S3DF node, where `/bin/sh` is bash 4.4, and the static check for `[` are what catch that helper (Measured facts › Shell tracing and exported functions).
- No entry the helper created remains in `$TMPDIR` after exit 0, exit 6, or exit 7, or after the helper is killed with `SIGTERM` while the fake server holds the request.
- With `$TMPDIR` naming a directory where the test replaces each new entry with a symlink to a file the test owns, that file is unchanged afterwards, and the helper still prints the response (FR-10, Measured facts › Response file).

### Critical paths

- Search, then Install, in a Cogito session whose `$HOME` has no token file.
- A refused token: the catalog's 401 gives exit 5 and the client shows FR-7's "Token refused" lines, not the response body (AC-6, by hand, with the fixture under Key interactions).
- `submit <path>` of a skill directory larger than 128 KiB. Against the production catalog this publishes the skill to every signed-in user, so run it with a skill meant for the catalog; AC-10 covers the body size without publishing anything.

---

## Follow-ups (non-blocking)

Collected from the 2026-10-14 to 2026-10-15 board review's Opportunities sections, deduplicated, with items the plan already adopted left out. The reviewer codes in brackets are research (dr), engineering (er), documentation (dc), security (sr), and UX (ux).

**Helper**
- Refuse a path or body that contains the token string (`case` on the token), a cheap backstop against a model steered to put an already-read token into a request. [dr, sr]
- Pass `--connect-timeout 10` so a stalled connection fails in seconds rather than at the Bash tool's timeout; avoid `--max-time`, which a large Submit on a slow link could hit. [er]
- Run curl under `/usr/bin/env -i` with a re-exported proxy allow-list instead of FR-5's list of unset variables. [dr, sr]
- Clear errexit and nounset in the prologue (`set +aeux`): with `SHELLOPTS=errexit` exported, a truncated response ends the helper with exit 18, outside FR-10's table. [er]
- Key FR-7's exit 7 messages by curl's exit code (for example 23 for a full `$TMPDIR`, 26 for an unopenable `/dev/fd/3`, 56 for a sandbox that blocks the hub), and add the post-request copy failure to FR-10's exit 1 row, marked as sent. [ux, er]
- Have `skill/SKILL.md` › Error handling treat an exit status outside FR-10's table (127 when `sh` cannot open the helper; dash's 2 for an unopenable script, which collides with FR-10's 2) as "the helper did not run", showing the refused message only when the last standard-error line starts with `agent-knowledge-hub: refused`. [er]
- Quote the helper path in FR-6's required form, `sh "${CLAUDE_SKILL_DIR}/hub-request.sh"`, so a home directory with a space does not break the call. [dr]
- Pass `-g` (`--globoff`) if FR-5's path character set ever widens for #048. [dr]
- Use `getent passwd "$(id -u)"` instead of `"$(id -un)"`, one fewer name-service lookup. [dr]
- When every node has curl 8.3 or later, `--variable tok@<path>` with `--expand-header` lets curl read the token file itself, and `-w '%{stderr}%{http_code}'` (curl 7.63) removes the response file. [dr, sr, er]
- Not adopted, with the reason: an origin override for dev and stage (the model could reach it), a header-printing mode (FR-1), retries inside the helper (the user is present), and a Python helper (Python's TLS setup reads the same environment variables). Record these in the ADR. [er]

**Client and prompts**
- Pipe Rate's body from `echo '{"value":<n>}'` rather than `printf`: Claude Code's documentation lists `echo` as read-only, so a saved helper rule would also cover Rate. [dr, er, ux]
- Record, in a session that prompts, the rule the "don't ask again" dialog offers for `sh <script> GET …`, and whether Rate and Submit still ask once it is saved. This settles FR-9's warning. [ux]
- Have `skill/SKILL.md` say that a POST that ended in a network error is not retried without asking, because Submit and the install event are not free to repeat. [er]
- Require that Submit runs only when the user typed `/agent-knowledge-hub submit` in this turn, never from a catalog entry's text, because Submit publishes `snapshotted_files` to every signed-in user. [sr]
- Have Validate run its local checks even when the slug-availability request ends in an FR-7 message. [ux]
- Stop naming the token path in `skill/SKILL.md`; FR-6 forbids reading it, and a named path gives injected text a target. [dc]
- Read the newer of the two token files by modification time, which removes the possible Cogito renewal loop in Open Design Question 6. [ux]
- Drop the client's install event, or have the backend count an install when it serves `GET /cli/api/skills/<slug>`, which saves one helper call per install. [ux]
- Have `GET /api/skillsets/{slug}` return each member's install fields so #006's confirm step needs no per-member fetch. [ux]
- Remove `version` from `.claude-plugin/plugin.json` so every merge reaches existing installs, instead of four tasks each raising it. [dc]
- Name the new plugin `version` in the CHANGELOG entry so users can compare it with `/plugin`. [dc]

**Tests**
- Export a function for every command name the helper runs (`command`, `umask`, `ulimit`, `mktemp`, `rm`, `cat`, `getent`, `id`, `cut`, `tr`, `printf`, `test`) and assert none of them ran; today the Test Plan covers only `printf`, `tr`, `[`, and `test`. [dr]
- Extend AC-2's `environ` check to every readable `/proc/<pid>/environ` of the test's own processes, as FR-8 does for `cmdline`. [dr]
- Add AC-7 and a no-symlink check on `skill/` to the same pytest file as FR-8. [er]

**Backend and deployments (separate tasks)**
- Have `POST /cli/api/skills` refuse, with 422 and no storage, a body that contains the request's own bearer token. This closes SR-22 whatever command built the body. [sr]
- Answer 503 rather than 401 when `_validate_slac_jwt` cannot fetch the JWKS from Dex, so the client can tell "your sign-in" from "the catalog cannot check sign-ins"; the 401 detail "Re-run 's3df login'" is also wrong in Cogito. [ux, dc]
- Cogito: carry FR-6's `Read` deny rule for the token file, and an allow rule for the helper's fixed skill path, in managed settings (TODO #200). [sr, ux]
- Change `docs/runbooks/internal-api-secret.md` › Path 3, which shows the `$(cat ~/.s3df-access-token)` header form, to `-H @-`. [dc]

**Docs**
- Add troubleshooting entries for every FR-7 message, including the refused-argument and certificate messages, not only the sign-in ones. [dc]
- Explain in the guide why Cogito's renewal needs a private window, once Cogito TODO #200 states it. [ux]

---

## Board Review

**Verdict:** CLEAR WITH WARNINGS
**Date:** 2026-10-15
**Rounds:** 3

The board's rule marks a plan UNSTABLE when any reviewer makes a design amendment in Round 3. This plan had one: FR-4 now says the helper never runs `[`, because RHEL 8's bash 4.4.20, run as `sh`, refuses `unset -f '['` and keeps an exported `[` function, which let a check for two arguments pass with three. The reviewer measured it with RHEL 8.10's own bash and verified the fix under dash, bash 5.2, and bash 4.4; the main session reproduced the defect and the fix. The user accepted the plan as CLEAR WITH WARNINGS on that basis.

| Reviewer | Result | Amended | Key findings |
|---|---|---|---|
| research | ⚠️ WARN | R1 2/9 · R2 1/8 · R3 0/0 | curl 7.61.1 on RHEL 8 limits the options; POSTs need `Content-Type: application/json`; prologue order and unsets; a prototype passed every case in Round 3 |
| codebase-arch-review | — | skipped | Client-only change: no new data store, async channel, service boundary, or infrastructure |
| codebase-eng-review | ⚠️ WARN | R1 3/5 · R2 1/4 · R3 1/0 | FR-10 interface and exit codes; `/dev/fd` output truncation; exit 7 on any non-zero curl exit; never run `[` |
| doc-review | ⚠️ WARN | R1 1/9 · R2 0/9 | Plugin version collisions; client guide wrongly says search needs no sign-in; ADR and CHANGELOG breaking-change note |
| security-review | ✅ PASS | R1 9/4 · R2 1/2 · R3 0/0 | CA-bundle and key-log variables, shell tracing, path rule, route allow-list, response file opened once and unlinked |
| codebase-ux-review | ✅ PASS | R1 3/7 · R2 2/7 · R3 0/0 | FR-7 messages for every exit code; FR-9 notice with the helper's full path; permission-prompt counts |

**Accepted warnings:** curl 7.61.1 and bash 4.4 as `/bin/sh` are covered by one by-hand run of FR-8's tests on a plain S3DF node before merge. The rule the "don't ask again" dialog offers for `sh <script>` has not been observed. Open Design Question 6 (where `s3df login` writes in Cogito) is open. A model steered to pipe the token file into a Submit body would publish it (SR-22); FR-6's `Read` deny rule is the deployment's option. The helper fails closed behind a proxy that decrypts HTTPS.
**Unresolved decisions:** none
**Amendments:** 24 design / 64 precision (Round 1 18/34, Round 2 5/30, Round 3 1/0)

### Reviewer output (final round per reviewer)

<details>
<summary>research — Round 3 (PASS WITH WARNINGS)</summary>

# Round 3 — Deep Research — #050 client token helper

**Summary**

- The round 2 changes work together. A prototype built to FR-4, FR-5, and FR-10 as written passed every case tried under dash and bash run as `sh` with curl 8.14.1: the prologue, then `set -C`, then `command exec 5>`, unlink, `-o /dev/fd/5`, and `cat /dev/fd/5`. The cases were 2xx, 204 with an empty body, 404, an unfollowed 302, a truncated response (exit 7), a 300,000-byte `POST`, two calls into one file, and `SIGTERM` mid-request.
- curl 7.61.1's source opens the `-o` path lazily with `fopen(..., "wb")` and creates an empty file after an empty successful transfer, the same as 8.14.1. Reopening through `/dev/fd/5` is kernel behaviour, measured on the RHEL 8 kernel that S3DF nodes run.
- The prologue's unset list breaks nothing later: `PATH` and `LC_ALL` become shell-only variables, which is all the helper needs. `TMPDIR` and `HOME` are not assigned, so they survive. `unset -f '['` works in dash too.
- Warnings, none amended. An exported `command` function replaces `command exec` under bash run as `sh` and runs after the token is read. FR-4's "every other command name it runs" covers `command`, but no listed test would catch it if it were left out. curl 7.61.1, bash 4.4 as `/bin/sh`, a `wekafs` `$TMPDIR`, and Claude Code's sandbox were not run; nested `bwrap` fails in this container.
- No amendments; PASS WITH WARNINGS.

**Issues**

Measured in the Cogito session on `sdfiana008` (Debian 13, dash 0.5.12, bash 5.2.37 through a link named `sh`, curl 8.14.1, host kernel `4.18.0-553.158.1.el8_10`) with a prototype that follows FR-4, FR-5, and FR-10 as written, a local fake server, and a token generated at run time. curl 7.61.1 read from source at tag `curl-7_61_1`, not run (no compiler or container runtime in the image).

- CONFIRMED | FR-10 › `-o /dev/fd/5` after `command exec 5>` and unlink, curl 8.14.1 | Under dash and bash as `sh`: 200 body, 204 with an empty body (exit 0, empty output), 404 body (exit 6), 302 not followed (exit 6), truncated response (exit 7, `curl exit 18`, empty output), `POST` with a 300,000-byte body (length and SHA-256 match, `application/json`); two calls into one regular file kept all five lines in order with no NUL byte; `SIGTERM` during a held request left no entry in `$TMPDIR`. `cat /dev/fd/5` reads the file although fd 5 is write-only, because the magic link reopens the inode.
- CONFIRMED | FR-10 › `-o /dev/fd/5` on curl 7.61.1 (source) | `tool_operate.c` sets `outs.stream = NULL; /* open when needed */` without `-C`, and `tool_cb_wrt.c` opens the path on first write with `fopen(outs->filename, append?"ab":"wb")`; after a successful transfer with no data it creates the file the same way (`force cration of an empty output file`). That is the same `open(O_WRONLY|O_CREAT|O_TRUNC)` curl 8.14.1 makes, and the reopen is kernel behaviour, measured here on the RHEL 8 kernel that plain S3DF nodes run. The binary-to-terminal refusal in `tool_write_cb` applies only when the output stream is a tty, which `-o` never is, so #048's binary fetches are not refused when the user's terminal is the helper's standard output.
- CONFIRMED | FR-10 › `set -C` with `command exec 5>` | Both shells: an existing regular file, a symlink to one, and a dangling symlink give exit 1 and create nothing at the dangling target; a symlink to `/dev/null` opens; a new name opens. Plain `exec` gives 2 in dash and 1 in bash, so the `command` prefix with `|| exit 1` is what makes the status 1 in both.
- CONFIRMED | FR-4 › prologue unset list against later steps | With `env -i HOME=... TMPDIR=... LC_ALL=en_US.UTF-8 PATH=/nonexistent:/usr/bin`, a prologue that runs `unset ... PATH LC_ALL` and then assigns them found `tr`, `mktemp`, `rm`, and `cat` and passed every case above in both shells. After `unset` and reassignment `PATH` and `LC_ALL` are shell variables only, not exported; nothing breaks, because the shell's own lookup uses `PATH` and FR-3's check is `case`, which uses the shell's locale, not a child's. `TMPDIR` and `HOME` are read, not assigned, so the unset rule leaves them alone and the sandbox's `$TMPDIR` reaches `mktemp`. `unset -f '['` and `unset -f test` succeed in dash too, so the prologue does not stop dash at its first line.
- WARNING | FR-4 › `command` is one of the names `unset -f` must cover | Under bash run as `sh`, an exported `BASH_FUNC_command%%` replaced `command` in `command exec 5>/dev/null`; the function ran in the helper's own shell, after the token check, where it can read the token variable, and fd 5 was not left open. `unset -f command` restored the builtin. Exported `umask` and `ulimit` functions also replaced those builtins. FR-4's "every other command name it runs" covers all three, so the requirement is right as written; the Test Plan edge case exports functions only for `printf`, `tr`, `[`, and `test`, so an implementation that left `command` out of the list would pass every listed test. Functions whose names hold a slash, such as `/usr/bin/curl`, are refused at import (`error importing function definition`), so the absolute curl path needs no entry.
- WARNING | Not measured | curl 7.61.1 and bash 4.4 as `/bin/sh` were not run, as in round 2. A `$TMPDIR` on `wekafs` (`/sdf/home`, `/sdf/scratch`) was not tried, because this review writes only to its scratchpad on `xfs`; if reopening an unlinked file failed there, curl would exit 23 and the helper 7, which fails closed. Claude Code's Bash sandbox was not tried either, because `bwrap` cannot bind-mount inside this container (`Can't bind mount /usr on /usr: ... Invalid argument`); the reopen depends only on the sandbox mounting `/proc`, which FR-4's `/dev/fd/3` already requires.

- CONFIRMED | FR-3 with the prologue's `LC_ALL` | With `LC_ALL=C.UTF-8` in the environment, a token followed by `é` or by ` x` gave exit 4 in both shells, and a token ending in `\r\n` was accepted, so the reassigned, unexported `LC_ALL=C` still makes the `case` check byte-wise.
- CONFIRMED | FR-4 › no startup file runs before the prologue | bash run as `sh` did not read `BASH_ENV` (a script that printed a marker did not run), so nothing can disable a builtin with `enable -n` before `set +ax`.
- CONFIRMED | #051 corrections | #051 › FR-2 refuses servers marked `auth.type: slac-sso`, its AC-6 and Open Question 3 are withdrawn, and its Follow-ups defer the `headersHelper` as a separate script; FR-1, the ADR item, and § Relationship to Other Tasks › #051 here now agree with that.

**Opportunities**

- The Test Plan edge case for exported functions could export one for every command name the helper runs (`command`, `umask`, `ulimit`, `mktemp`, `rm`, `cat`, `getent`, `id`, `cut`, `tr`, `printf`, `[`, `test`), each recording that it ran, and assert that none ran. That catches a name left out of FR-4's `unset -f` list, which the current four-name case does not.

**Decisions Required**

None.

**Amendments**

None. No finding meets the round's bar: FR-4, FR-5, and FR-10 as amended in round 2 build and behave as specified under dash and bash run as `sh` with curl 8.14.1, and curl 7.61.1's source opens the `-o` path the same way.

TOTAL: 0 design, 0 precision

**Status**
PASS WITH WARNINGS

</details>

<details>
<summary>codebase-eng-review — Round 3 (PASS WITH WARNINGS)</summary>

# Round 3 — Engineering Review (codebase-eng-review) — #050 client token helper

**Summary**

- The helper can be built from FR-4, FR-5, and FR-10 in one order: prologue, argument check, token read, fd 5 open, curl, status, exit. A prototype written to the plan passed every automated Test Plan row it exercises under dash and bash 5.2 as `sh`, and under the RHEL 8.10 bash 4.4.20 binary as `sh`, extracted from AlmaLinux's package. That includes two calls into one output file with no NUL byte, a 300,000-byte body with a matching digest, the truncated response as exit 7, AC-9 with no key log, and no entry left in `$TMPDIR`.
- One design defect, found only because this round ran RHEL 8's own bash. bash 4.4 run as `sh` imports an exported `BASH_FUNC_[%%` and refuses `unset -f '['`. FR-4's protection for `[` therefore fails on every S3DF node outside Cogito, and the refused `unset` prints an error line on every call there. Amended: the helper runs no `[`, writes its checks with `test` or `case`, and drops `[` from `unset -f`. The fix was measured under all three shells. The Measured facts row, References, and the Test Plan (a static check and an exact standard-error check) were updated with it.
- FR-7's tables and FR-10's exit codes match one-to-one, and every Test Plan row matches the FRs as amended in Round 2.
- Warnings: curl 7.61.1 is still covered only by the Test Plan's single run on a plain S3DF node. A1 was made in the final round, so no other reviewer has seen it.

**Issues**

Format: `SEVERITY | area | description`. "Measured" means run on 2026-10-15 in this Cogito session on `sdfiana008` (curl 8.14.1), with a token generated at run time by `secrets.token_urlsafe` and local servers only. The prototype and its runners are in this session's scratchpad under `er050r3/` (`hub-request.sh`, `run3.sh`, `tlsrun.sh`, `fake3.py`, `swap.py`), not in the repository. Three shells were used: dash, the image's `/bin/sh`; bash 5.2.37 through a link named `sh`; and the RHEL 8.10 bash, the `/usr/bin/bash` of `bash-4.4.20-6.el8_10.x86_64.rpm` from AlmaLinux 8.10 BaseOS, extracted from the package and run through a link named `sh`. Matters settled in Rounds 1 and 2 are not re-raised.

*Build order (FR-4, FR-5, FR-10)*

- INFO | build order, verified | An implementer can build the helper from FR-4, FR-5, and FR-10 in one consistent order: the FR-4 prologue (`set +ax`, `unset -f`, `unset` of every assigned variable including `PATH` and `LC_ALL`, `PATH`, `LC_ALL`, `ulimit -c 0`), then FR-5's argument and route checks, then FR-2's lookup and FR-3's check, then FR-10's `umask 077`, `set -C`, `name=$(mktemp -u)`, `command exec 5>"$name" || exit 1`, and removal of the name, then curl with `-H @/dev/fd/3`, `-o /dev/fd/5`, and `-w '%{http_code}'`, then the exit 7 branch on curl's exit status, then `cat /dev/fd/5` and the status line. No FR requires a step out of that order, and none of the three descriptors (3 the header pipe, 4 the saved standard input, 5 the response file) serves two roles.
- INFO | prototype results, verified | Under dash, bash 5.2 as `sh`, and the RHEL 8.10 bash as `sh`, the prototype gave the same results: exit 0 for each of the five route-table rows and exit 2 with no request for each row's path under the other method; exit 2 with no request and empty standard output for every AC-3 argument tried; exit 5 for 401, exit 6 for 403, 404, 410, 500, and a 302 whose target logged nothing; exit 7 with empty standard output and `agent-knowledge-hub: network error (curl exit 18)` for a response cut short; exit 7 with `curl exit 7` with no listener; exit 7 with `curl exit 60` and no key-log file for AC-9 with `CURL_CA_BUNDLE` and with `SSL_CERT_FILE`; exit 3, exit 4, and exit 1 for the token-file and missing-`TMPDIR` cases in the Test Plan; and the request through `http_proxy` when it was set. Two calls in one command into one regular file kept `before`, both bodies, both status lines, `between`, and `after` in order with no NUL byte. A 300,000-byte random body arrived with the same length and SHA-256 digest under `application/json`. No readable `/proc/<pid>/cmdline` or `/proc/<pid>/environ` held the token during a held request, under `sh -x`, `sh -a`, an exported `token`, or `SHELLOPTS=xtrace`. No entry remained in `$TMPDIR` after any exit or after `SIGTERM` during a held request, and a watcher that replaced the new entry with a symlink left its target unchanged while the helper still printed the response.

*FR-4 prologue on RHEL 8*

- HIGH | FR-4, `unset -f '['` | FR-4 removes an exported `[` with `unset -f`, and that fails in the shell that runs the helper on every S3DF node outside Cogito. Measured with the RHEL 8.10 bash run as `sh`: it imports an exported `BASH_FUNC_[%%`, `unset -f '['` prints ``unset: `[': not a valid identifier`` and returns 1, and the function stays in place, so `[ a = b ]` is still true afterwards. `unset -f test` works, and the shell does not exit. The bash 4.4.18 source explains it: `unset_builtin` checks `legal_identifier` for a function name in posix mode (`builtins/set.def`, line 875), and functions are imported before `act_like_sh` turns posix mode on (`shell.c`, lines 570 and 687). bash 5.2 accepts `unset -f '['`, which is why Rounds 1 and 2, run under bash 5.2 only, did not see this. Two consequences follow for a helper written as FR-4 reads. First, an exported `[` that returns 0 passes every check written with `[`. With the prototype's `[ "$#" -eq 2 ]` and `[ -z "$tokfile" ]`, a third argument got past the count check, and the helper exited 3 with "no token file" although the file existed. A helper that also chose curl's method with `[ "$method" = POST ]`, as the prototype does, would send a `GET` row's request as a `POST` with the caller's standard input as its body, wherever its token lookup did not exit first. Second, the refused `unset` prints that error line on every call on RHEL 8, with nothing exported. The Test Plan's exported-`[` case runs under bash 5.2 in Cogito, where it passes. The only run that would catch either consequence is the plain-node run before merge, and by then the remedy FR-4 prescribes is shown not to work. Amended: the helper runs no `[` and writes each check with `test` or `case`. `[` leaves the `unset -f` list and `test` stays in it. The Measured facts row gains the RHEL 8.10 result, and the Test Plan gains a static check and a standard-error check (A1). Measured after the change: with `[` replaced by `test` and dropped from the list, all three shells pass the whole suite, an exported `[` and `test` with a third argument give exit 2 and no request, and standard error on exit 0 is exactly the status line.
- INFO | FR-8, `/bin/sh` on RHEL 8 | FR-8 and Measured facts record `/bin/sh` on RHEL 8 as bash, not measured. The `bash-4.4.20-6.el8_10` package installs `./usr/bin/sh` as a symbolic link to `bash` (read from the package's payload). Recorded in the Measured facts row as part of A1, and FR-8 is left as written, because no S3DF node was checked.
- INFO | other prologue steps on RHEL 8, verified | Under the RHEL 8.10 bash as `sh`, `unset -f printf command umask` restored the builtins after exported functions of those names, exported `BASH_FUNC_set%%` and `BASH_FUNC_unset%%` did not replace those builtins, `SHELLOPTS=xtrace` traced only `set +ax`, and `set -C` with `command exec 5>` refused a regular file, a symlink to one, and a symlink to nothing, opened a symlink to `/dev/null`, and exited 1 when the directory was missing, the same as dash and bash 5.2. An exported `BASH_FUNC_/usr/bin/curl%%` is not imported by bash 5.2 ("error importing function definition"), and bash 4.4's import skips any name for which `absolute_program` is true (`variables.c`, line 391), so `/usr/bin/curl` needs no `unset -f`.

*FR-7 and FR-10*

- INFO | FR-7 vs FR-10, verified one-to-one | Every FR-10 exit maps to exactly one client case. Exit 2 maps to FR-7's exit 2 row. Exits 3, 4, and 5 map to the three sign-in cases. Exit 6 maps to the existing 404, 410, and 403 rate-limit cases, to the 3xx row, and to the row for any other status. Exit 7 maps to the `curl exit 60` row and, for every other curl exit, to the existing network-error case. Exit 1 maps to FR-7's exit 1 row. Exit 0 is success. FR-10's exit 7 row ("curl exited non-zero") and FR-7's "keeps exit 7 with any curl exit other than 60" agree. Each `Last line of standard error` in FR-10 is the line FR-7's messages quote from, and each line the prototype printed matched it under all three shells.

*Test Plan rows vs the amended FRs*

- INFO | Test Plan, verified | Each automated row was checked against FR-4, FR-5, FR-7, and FR-10 as amended in Round 2, and the prototype passed each row it exercises. The rows for no entry left in `$TMPDIR`, including after `SIGTERM`, and for the symlink watcher fit the fd-5 design: the name is gone before curl starts, and the watcher row still fails a helper that goes back to `-o "$name"`, because that name exists for the whole request. The row for `TMPDIR` naming a missing directory gives exit 1 through `command exec 5>`, as FR-10 now says. The exported-`[` edge case was the only row that passes under the Cogito shells while the requirement fails on RHEL 8. It is extended under A1, which leaves the Test Plan rows consistent with the FRs.
- INFO | FR-10, `mktemp -u` on RHEL 8, verified | `/usr/bin/mktemp` from AlmaLinux 8.10's `coreutils-8.30-21.el8_10` printed `$TMPDIR/tmp.<10 characters>` and created nothing, including for a `TMPDIR` that does not exist (exit 0), so on RHEL 8 too, FR-10's `command exec 5>` is the step that fails with exit 1 there. Measured facts › Temporary files still says "not run" for RHEL 8. That is wording, so it is left alone this round.
- INFO | not covered this round | curl 7.61.1 was not run. FR-5's options and the exit 7 rule still rest on the 7.61.1 source and on the Test Plan's single run on a plain S3DF node, as in Round 2.

**Opportunities**

- FR-4's `set +ax` leaves errexit and nounset alone. Under the RHEL 8.10 bash run as `sh` with `SHELLOPTS=errexit` exported, a response cut short ended the helper at `code=$(...)` with exit 18 and no `agent-knowledge-hub:` line. That status is outside FR-10's table, though no body and no token were printed. `set +aeux` would close this at no cost. FR-6 already forbids `sh` options, and an exported `SHELLOPTS` is rare, so this is not a defect.
- dash exits 2 when it cannot open the script (`dash: 0: cannot open ...: No such file`), which collides with FR-10's exit 2 for a refused argument; bash exits 127. `skill/SKILL.md` › Error handling could show FR-7's exit 2 row only when the last line of standard error begins with `agent-knowledge-hub: refused`, and show "the helper did not run" otherwise. Round 2 raised the 127 half of this.
- Round 2's Opportunities still apply: `echo` instead of `printf` for Rate's body, and wording for curl exit 26 under exit 7.

**Decisions Required**

*Decision: How the helper defends against an exported `[` on RHEL 8*
- **Severity:** defaulted
- **Question:** bash 4.4 run as `sh`, `/bin/sh` on RHEL 8, cannot remove an exported `[` function with `unset -f`. Should the helper stop running `[`, or keep `[` and accept the gap there?
- **Options:** A) The helper never runs `[` and writes each check with `test` or `case`, `[` leaves the `unset -f` list, and a static check enforces it. B) Keep `[` and `unset -f '['` as written, and accept that on RHEL 8 an exported `[` survives and every call prints ``unset: `[': not a valid identifier``. C) Keep `[` with `unset -f '[' 2>/dev/null`, which hides the line but still leaves the function in place on RHEL 8.
- **Assumed:** A. It costs nothing at build time, it works the same under dash, bash 5.2, and bash 4.4 (measured with the prototype), and it removes the only part of the FR-4 prologue that depends on the bash version. B and C keep a control that is shown not to work on the platform it was written for.
- **Impact if wrong:** one FR-4 sentence and one static check in the Test Plan change back; the helper's code changes by replacing `test` with `[` in its checks.

**Amendments**

- A1 design: FR-4: the helper never runs `[` and writes each check with `test` or `case`; `[` leaves the `unset -f` list, and the reason given names `test`, because bash 4.4 run as `sh` (`/bin/sh` on RHEL 8) imports an exported `BASH_FUNC_[%%`, refuses `unset -f '['`, and prints an error line on every call. Measured facts › Shell tracing and exported functions gains the RHEL 8.10 bash 4.4.20 results and the package's `/usr/bin/sh` link, and References gains the package and the bash 4.4.18 source.
- Not counted: `## Test Plan` updated in place, the required output of this review. The header now names round 3. A Key interactions row requires standard error on exit 0 to hold only FR-10's status line. The static checks gain "the shipped helper runs no `[` command". The exported-`[` edge case now includes a third argument and says which runs catch a helper that runs `[`.

TOTAL: 1 design, 0 precision

**Status**

PASS WITH WARNINGS

</details>

<details>
<summary>doc-review — Round 2 (PASS WITH WARNINGS)</summary>

# Round 2 — Documentation coverage (dc)

**Summary**

- Every rule added in Round 1 now has a doc row. FR-7's messages, FR-9's notice and its rule advice, `skill/hub-request.sh`, the removed `AGENT_KNOWLEDGE_HUB_TOKEN`, the route allow-list, and the `backend/tests/` test each appear in the Definition of Done. No row is duplicated, and none contradicts another.
- Three rows predated the Round 1 changes and disagreed with them. The guide's **Token expiry** note would still quote the 401 body that FR-7 now hides. The CHANGELOG row named "the 401 message", left out the Search and Install bullet that § Relationship › #006 says this task owns, and placed the breaking-change note under a `###` heading, which in `CHANGELOG.md` starts a new task's entry. The ADR row's lists stopped short of the resolved Open Design Questions. All three are amended.
- § Relationship now has a #004 row for the removed variable, says that #006 Slice 4 and #048 each add their route row, and leaves FR-6's deny rule and any allow rule to Cogito. Problem Statement › defect 2 no longer claims the permission prompt shows the user every step outside the interface. Goals 1 to 4 already agreed with the requirements.
- Nine precision amendments and no design amendments. One Decision is defaulted: a **Breaking change:** paragraph in the CHANGELOG instead of a separate upgrade guide.

**Issues**

> Mode: Codebase. Round 2 checks each rule added in Round 1 against the Definition of Done, and the Problem Statement, Goals, and § Relationship to Other Tasks against the amended requirements.

*Coverage of the rules added in Round 1*

| Rule | Doc rows that carry it | Gap found |
|---|---|---|
| FR-7 sign-in messages per cause | `skill/SKILL.md` (FR-7 itself), guide, troubleshooting, README, CHANGELOG | Guide's **Token expiry** note still quotes the 401 body that FR-7 now hides; CHANGELOG row still says "the 401 message" |
| FR-9 first-call notice and rule advice | `skill/SKILL.md` (FR-9 itself), guide, CHANGELOG | Guide row does not carry FR-9's per-repository and per-update limits of the rule |
| FR-10 `skill/hub-request.sh` and its exit statuses | `skill/SKILL.md` › Error handling (FR-10 itself), header comment | Header-comment row names neither the file, the exit statuses, nor the test that guards it |
| `AGENT_KNOWLEDGE_HUB_TOKEN` removed | `skill/SKILL.md` row, CHANGELOG row | CHANGELOG row's heading clashes with the file's form and says nothing on detection or migration; § Relationship has no #004 row |
| FR-5 route allow-list | ADR row (through FR-5), header comment (through FR-5) | ADR row's consequences omit the rule that a new request adds a row; § Relationship › #006 and #048 do not say they add their rows |
| FR-6 Read deny rule for deployments | none | Nothing hands it to Cogito, the one deployment named |
| FR-8 test in `backend/tests/` | FR-8 itself, header-comment row | Header-comment row does not name the test file |

*Findings*

- MEDIUM | Guide | DoD › guide row applies the **Token expiry** note to every catalog command but leaves its quoted text, *"Token expired"*, which is the 401 body that FR-7 (rewritten in Round 1) now replaces with its "Token refused" cause line. A user who searches the page for the message they see will not find it. Amended.
- MEDIUM | Guide | DoD › guide row says only "how to stop those prompts". FR-9 (Round 1) says the rule is saved for the current repository only and, for a plugin install, stops matching after each client update. Without those two facts in the guide, a user who followed it sees the prompts return and has no explanation. Amended.
- MEDIUM | CHANGELOG | DoD › CHANGELOG row lacks the bullet that Search and Install now send the sign-in, which § Relationship › #006 says this task owns, and still names "the 401 message" where FR-7 now has three. Amended.
- MEDIUM | Breaking change | The removed `AGENT_KNOWLEDGE_HUB_TOKEN` gets a note "under a `### Breaking changes` heading". In `CHANGELOG.md` every `###` heading under `## Unreleased` is one task's entry (`### Skillsets: curated skill collections (#006, backend)`), so such a heading would sit beside this task's entry rather than in it, and no entry in the file uses one. The note also does not say how a job detects the break or migrates. Amended to a bold lead-in inside the entry with what breaks, the message a job then gets, and the replacement; Decision recorded on the upgrade guide.
- MEDIUM | ADR | DoD › ADR row's list of rejected alternatives predates the Round 1 resolutions. It omits what FR-1 and Open Design Questions 2, 4, and 5 reject (a mode that prints the header, the body as a curl argument, `--variable`, other methods, the token in a variable), and its consequences omit the route-table rule for new requests, the token file for automation, and the residual risk FR-6 states. Amended by reference rather than by copying the lists.
- LOW | Header comment | DoD › header-comment row says "the helper" though FR-10 now names `skill/hub-request.sh`, and does not ask the comment to name FR-10's exit statuses, on which `skill/SKILL.md` › Error handling depends, or the test, which lives in `backend/tests/`, away from `skill/`. Amended.
- LOW | Relationship › #006, #048 | FR-5's route table marks two rows "added by #006 Slice 4" and "added by #048", and FR-5 says a task that adds a request adds its row in the same change. Neither Relationship row says so. Amended.
- LOW | Relationship › #004 | Open Design Question 5 removes the variable that #004 introduced for its automation use case (`todo/004-multi-source-scanner-abstraction.md`), and § Relationship has no #004 row. Amended.
- LOW | Relationship › Cogito | FR-6 (Round 1) addresses its `permissions.deny` rule to "a deployment", and Non-Goals leaves an allow rule to each deployment. Nothing hands either decision to Cogito, the deployment that filed this task. Amended.
- LOW | Problem Statement | Defect 2 (amended in Round 1) says a theft outside the helper's interface is one that "the permission prompt shows the user". FR-9 lets the user stop the prompts, and a session that does not prompt shows nothing. Amended to scope the claim.
- LOW | FR-9 | FR-9 gives `hub-request.sh` "for example", while FR-10 fixes the name. Amended to refer to FR-10.
- Checked, no gap: Goals 1–4 agree with FR-2, FR-4, FR-5, and FR-7; What fails today agrees with FR-4 and FR-5; the DoD's FR and AC ranges match FR-10 and AC-10; the `skill/SKILL.md` row's section list matches FR-5's "Sent by" column; no DoD row is duplicated. `AGENT_KNOWLEDGE_HUB_TOKEN` appears in no shipped file other than `skill/SKILL.md` › Submit, which the `skill/SKILL.md` row covers. The `#cli-auth` anchor the troubleshooting row links to exists in the guide.

**Opportunities**

- FR-7 gained, during this round, client messages for exit 2, a 3xx, other statuses, curl exit 60 behind a TLS-decrypting proxy, and exit 1. The troubleshooting row covers only "FR-7's sign-in messages". The exit-60 message names its own next step, so an entry is not required; a user who meets it on a site proxy may still search the troubleshooting page for it. Not amended, because the change belongs to another reviewer's edit in the same round.

**Decisions Required**

*Decision: Upgrade guide for the removed `AGENT_KNOWLEDGE_HUB_TOKEN`*
- **Severity:** defaulted
- **Question:** The doc-review rule asks for a dedicated upgrade guide, not only a CHANGELOG entry, when an environment variable is removed. Does this removal need one?
- **Options:** A) A **Breaking change:** paragraph inside this task's CHANGELOG entry that says what breaks, the message a job then gets, and the replacement (amended into the DoD). B) A separate upgrade guide under `docs/`.
- **Assumed:** A. The repository has no upgrade guides, the variable served only Submit, and the replacement is one file that the previous client also reads, so a job can move to it before it updates and needs no rollback step.
- **Impact if wrong:** Under B, one more DoD row and one more file; the CHANGELOG paragraph would then link to it.

**Amendments**

- precision: Problem Statement › defect 2 says the permission prompt shows a step outside the helper's interface only "in a session that asks before that command", since FR-9 lets the user stop the prompts.
- precision: FR-9 names the helper as `hub-request.sh` (FR-10) instead of giving it "for example".
- precision: DoD › CHANGELOG row names FR-7's sign-in messages instead of "the 401 message"; adds that every catalog command, Search and Install included, sends the sign-in, the bullet § Relationship › #006 says this task owns; and replaces the `### Breaking changes` heading with a **Breaking change:** paragraph inside the entry, the file's own form, which says what a job that set the variable now sees and what replaces it.
- precision: DoD › ADR row takes its rejected alternatives by reference to FR-1, FR-5, and Open Design Questions 1, 2, 4, and 5, and its consequences add the route-table rule for new requests, the token file for automation, and the residual risk FR-6 states with the deployment Read deny rule.
- precision: DoD › header-comment row names `skill/hub-request.sh`, adds FR-10's exit statuses and the dependency of `skill/SKILL.md` › Error handling on them, and names the test `backend/tests/test_hub_request_helper.py`.
- precision: DoD › guide row has the **Token expiry** note quote FR-7's "Token refused" cause line in place of the 401 body FR-7 hides, and says the rule FR-9 names is kept for the current repository only and, for a plugin install, stops matching after each client update.
- precision: § Relationship › #006 and › #048 each say that task adds its row to FR-5's route table in the same change.
- precision: § Relationship gains a #004 row: #004 added the `AGENT_KNOWLEDGE_HUB_TOKEN` override that this task removes.
- precision: § Relationship › Cogito says that adding FR-6's Read deny rule or an allow rule for the helper to Cogito's managed settings is Cogito's decision, and that this task ships neither.

TOTAL: 0 design, 9 precision

**Status**

PASS WITH WARNINGS

</details>

<details>
<summary>security-review — Round 3 (PASS)</summary>

# Round 3 — Security Review — #050 client token helper

**Summary**

- PASS, no amendments. This review covered Round 2's changes, and each one was attacked with a prototype or checked against the source it cites. No change reopens a token path that Rounds 1 and 2 closed: argv, environ, standard output and standard error, a file, or a destination other than the catalog.
- FR-4's prologue (measured). It runs first and unsets every assigned variable and the `[` and `test` functions. That keeps the token out of every `/proc/<pid>/cmdline`, out of curl's `environ`, and out of the helper's output under dash and under bash run as `sh`. The tested cases were `-x`, `-a`, `-k`, `SHELLOPTS`, an exported variable of the token variable's name, and exported functions. A negative control confirmed the scanner catches the leaks it looks for. bash's `_` reaches curl only as `/usr/bin/curl`.
- FR-10's file descriptor 5 (measured). The file holds only the body, has no name once curl starts, and leaves nothing in `$TMPDIR`.
- FR-9's printed rule. It approves only commands that begin with the helper's full path. Claude Code checks the other parts of a pipeline and any redirect target separately. Printing the path discloses nothing, and the notice appears before any catalog text could change it.
- Residual recorded, not amended (SR-22). Round 1 accepted that feeding the token file into Submit's body is FR-6's residual. With FR-9's rule saved, that publication route needs no prompt, and Round 2's `/permissions` option widens the rule from one repository to every project. A backend check that refuses a submit body holding the request's own token is listed as a follow-up opportunity.
- Two leads remain unverified: an allow rule's `*` over a command substitution, and bash 4.4.
- Basis for PASS. The Round 1 and 2 entrypoint traces still hold, because Round 2 added no entrypoint. Grep hunt tables do not apply to a plan with no code change. Every claim above cites a measurement or a documentation page.

**Issues**

Format: `SEVERITY | area | location | finding`. Numbering continues from Round 2. "Measured" means run on 2026-10-15 in the Cogito session on `sdfiana008` (dash; bash 5.2.37 through a link named `sh`; curl 8.14.1), with a prototype helper written from the FR-4, FR-5, and FR-10 text as amended in Round 2, a token generated at run time by `secrets.token_urlsafe`, and a local fake server that held each request for 1.2 seconds while a scanner read every readable `/proc/<pid>/cmdline` and curl's `/proc/<pid>/environ`. The prototype and its driver are in the review's scratchpad, not in the repository. A negative control (the prototype without `unset tok`, plus the token in an extra `-H` argument) made the scanner report both the `cmdline` hit and the `environ` hit, so the scanner detects what it looks for.

- None at the Round 3 bar. No Round 2 change reopens a token path closed in Rounds 1 and 2.

Verified, no change needed:

- FR-4 prologue order (research, Round 2). Written as FR-4 orders it (`set +ax`; `unset -f` for `printf`, `[`, `test`, `command`, and every other command name the helper runs; `unset` for every variable it assigns; `PATH=/usr/bin:/bin` and `LC_ALL=C`; `ulimit -c 0`) and run before the argument check and the token read, the prototype sent the token correctly and left it in no process's `cmdline`, out of curl's `environ`, and out of standard output and standard error under each shell plain, `-x`, `-a`, `-ax`, `-k` (bash), with an exported variable of the token variable's name (also with `-a`), with `SHELLOPTS=xtrace` and `SHELLOPTS=allexport`, and with exported `BASH_FUNC_printf%%`, `BASH_FUNC_command%%`, and `BASH_FUNC_cat%%`. With exported `BASH_FUNC_[%%` and `BASH_FUNC_test%%` that return 0, a URL as the path exited 2 and sent nothing. Unsetting before assigning is the order that matters: the negative control shows that an inherited exported name carries the token into curl's `environ` when the `unset` is missing.
- bash's `_` variable. bash run as `sh` sets `_` to the last argument of the previous command, which after the header `printf` would be the token, but it gives each child `_=<the child's path>`: measured `_=/usr/bin/curl` in curl's `environ` in every bash case, and the caller's value under dash, which does not maintain `_`. No token.
- `sh -k` (bash). It moves `name=value` arguments into a command's environment. FR-3's character set has no `=`, so the token cannot take that form, and only builtins receive it. Measured: no token in curl's `environ`.
- FR-10's file descriptor 5 (security review, Round 2). Opened after the token check, under `umask 077` and `set -C`, then unlinked: the prototype returned the full body on standard output, left no entry in `$TMPDIR` in any run, and wrote no token anywhere. curl writes only the response body to `-o`. The prototype passes no `-v`, `--trace`, or `-D`, so no header reaches the file. On exit 7 the file is not copied out.
- FR-9's printed rule (UX, Round 2). `Bash(sh <script> *)`, with `<script>` the full expanded helper path, approves only commands whose text begins with `sh <script>`. Claude Code splits `&&`, `||`, `;`, `|`, `|&`, `&`, and newlines and requires each subcommand to match a rule. It checks `<` and `>` targets against Read and Edit rules. An allow rule does not match past a leading assignment of a variable outside its known-safe set. It asks before a command it "can't fully analyze" even when part of the command matches an allow rule (`https://code.claude.com/docs/en/permissions` › Compound commands, › Wrappers, › Redirections; `https://code.claude.com/docs/en/security` › Command injection detection, read 2026-10-15). The rule therefore does not approve `sh -c`, `sh -x <script>`, another script path, or a pipeline's other parts. Printing the path adds nothing secret. FR-9 shows the notice before the first helper call, so before any catalog text is in the conversation, and catalog text cannot change the path that the user checks the prompt against.
- FR-9's `/permissions` scope. A rule in user settings applies in every project instead of one repository. That widens where the rule applies, not which command it approves. For Cogito's managed skill the path is under `/etc/claude-code/`, which the user cannot write. For a plugin install the path is in the user's own cache, which only the user, or a command the user approves, can write.
- FR-7's tables (UX, Round 2) and the exit 7 rule (engineering, Round 2). Exit 6 relays only the body's string `detail`. On the client's routes, and in `backend/app/auth.py`, that string is fixed text or fixed text plus an existing slug, never the token. The 401 `detail` strings are fixed text, and the client does not show them. Exit 1 relays the last standard-error line of a failing command. None of the commands that see the token (`printf`, `case`, `tr` reading the file) prints its input on failure. The "flag that entry" step on exit 2 sends the user to the catalog page and does not call the helper, so it adds no route outside FR-5's table. Exit 7 discards the partial body and adds no output.
- The #051 `headersHelper` corrections. FR-1, § Relationship › #051, and Goal 1 now agree: the client's only reader of the token is this helper, and a future header-printing script is separate and never run by the model.
- LOW, already accepted | model-level bypass, scope | FR-6, FR-9 | **SR-22.** Recorded so that the scope change is visible, not amended. FR-6's residual (SR-08 and SR-14, Round 1) is a command that feeds the token file to the helper's body, for example `sed 's/^/{.../;s/$/...}/' <real home>/.s3df-access-token | sh <script> POST /cli/api/skills`. Such a command publishes the token through Submit to every signed-in user. With FR-9's rule saved, it runs with no prompt in Manual mode, because `sed` without `-i` and `cat` are read-only commands. This is the trade-off FR-5 states ("the helper's own checks are all that stand between a catalog entry's text and those routes"). FR-6's Read deny rule covers `cat` and `sed`. Round 2's `/permissions` option changes the rule's reach from one repository to every project. It does not change what the rule approves. Under the Round 3 bar this is not a new defect. See Opportunities.

**Unverified Leads**

- Whether a saved allow rule's trailing `*` also covers a command substitution in the helper's arguments, as in `sh <script> GET "$(<other command>)"`. The permissions page says deny and ask rules apply inside a command substitution, and the security page says a command Claude Code cannot fully analyze prompts despite a matching allow rule. Neither page says that an allow rule requires the inner command to match too. This holds for every prefix rule, Cogito's possible managed allow rule included, and is not specific to FR-9. Not observed, because this session runs without prompts. The FR-9 test by hand in a prompting session could add this case.
- Carried from Round 2: the prologue and `set -C` under bash 4.4, RHEL 8's `/bin/sh`, were not run. FR-8's one run on a plain S3DF node covers them.

**Opportunities**

- Follow-up, not this task: `POST /cli/api/skills` could refuse a body that contains the request's own bearer token, which the backend already holds, with a 422 and no storage. That closes SR-22's publication route on the server, whatever command fed the body, and costs one substring check in `create_skill`. Round 1's opportunity (Submit only when the user typed the command in this turn) still stands beside it.

**Decisions Required**

None.

**Amendments**

None.

TOTAL: 0 design, 0 precision

**Status**

PASS

</details>

<details>
<summary>codebase-ux-review — Round 3 (PASS)</summary>

# Round 3 UX Review — #050 client token helper

**Summary**

No Round 2 change leaves a user with a false or missing instruction on a supported system, so this round makes no amendment.

- A truncated response now reaches the network-error case. That message is true, and a retry is safe on every route the client sends: a repeated Submit gets a 409 whose `detail` names the existing skill.
- A failed response-file open exits 1, not dash's 2, so the user is not told the request was refused. FR-7's exit 1 line, "failed before sending a request", is true, and the shell's message names the bad directory (measured under dash and bash).
- Remaining gaps are wording or unsupported systems: curl exit 23 is labelled a network error, and the `/dev/fd/5` read-back has no FR-10 row and fails on macOS. They are recorded under Issues and Opportunities.

| Dimension | As received | After amendments | Key Gap |
|-----------|-------|-------|---------|
| Discoverability | 8/10 | 8/10 | The guide, README, troubleshooting, and CHANGELOG lines are all in the Definition of Done |
| First-Use Clarity | 8/10 | 8/10 | Nobody has observed the rule the prompt offers for `sh <script> …` |
| Documentation Quality | 8/10 | 8/10 | None at this round's bar |
| Error UX | 8/10 | 8/10 | Curl failures other than exit 60 all read as network errors, curl exit 23 included |
| Workflow Fit | 7/10 | 7/10 | One prompt per call in a session that asks; whether a saved rule silences Rate and Submit is not observed; Open Design Question 6 is still open |
| Trust & Reliability | 7/10 | 7/10 | The report line points to the site's home page only |
| **UX Readiness Score** | **7.7/10** | **7.7/10** | |

**Verdict:** UX WARNINGS. The skill's table would map a score of 7.7 to PASS WITH WARNINGS. The status below is PASS because the round bar says to return PASS when no finding is a defect that makes the implementation wrong, unsafe, or unbuildable. The warnings behind the score all come from Round 2 and are recorded there.

**Top 3 user risks if shipped as-is:** (1) A session that asks before each Bash command prompts on every catalog request, 21 to 31 times for a 10-member skillset. (2) If `s3df login` in a Cogito shell writes to `$HOME`, FR-7's message returns after every sign-in (Open Design Question 6). (3) A full `$TMPDIR` reads as a network error.

**Highest-impact fix:** Run the Test Plan's check by hand to record the rule the prompt offers for the helper. That one observation settles FR-9's warning and the prompt counts.

**Issues**

- info | Error UX | A truncated response now gives exit 7 (engineering A1) and reaches the user as the existing network-error case, which suggests retrying. That message is true, because the connection did fail mid-response. A retry is also safe on every route the client sends. For `POST /cli/api/skills`, a retry after a truncated 201 gets 409 with `A skill with this repo URL and path already exists. See /skills/<slug>` (`create_skill` in `backend/app/routers/skills.py`, and the `local://` duplicate check in `backend/app/services/skill.py`), and FR-7's exit 6 row shows that string `detail`. A repeated install event adds one more install count, and nothing more. No amendment.
- info | Error UX | A failed response-file open (security A1) exits 1, so it does not reach FR-7's exit 2 message, which would wrongly say the request was refused and suggest flagging a catalog entry. FR-7's exit 1 line, "The hub client failed before sending a request", is true here, because the open comes after the token check and before curl. Measured under dash and under bash with `TMPDIR=/nonexistent/dir`: both exited 1, with the last line of standard error reading `cannot create /nonexistent/dir/tmp.<random>: Directory nonexistent` (dash) or `/nonexistent/dir/tmp.<random>: No such file or directory` (bash), so the cause line names the bad directory. The next step, the report line, does not tell a user that their own `TMPDIR` is wrong, but the cause line shows it. No amendment.
- info | Error UX | Engineering A1 also sends curl failures that are not network failures to exit 7: curl exit 23, a failed write to `-o /dev/fd/5` when `$TMPDIR`'s file system is full, would read as `network error (curl exit 23)`, with a suggestion to retry. This is rare, and curl's own `curl: (23) Failure writing output ...` line comes just before it. The change still improves on the plan before Round 2, where `%{http_code}` would have printed `200` and the helper would have exited 0 with a cut-off body. Wording only, so it is out of scope for this round. No amendment.
- info | Error UX | The read-back of `/dev/fd/5` after curl exits 0 has no row in FR-10. The plan relies on Linux here, and the copy succeeded in security's prototypes, so on supported systems it fails only when the helper's own standard output cannot be written. On macOS, which FR-7's third renewal step and the guide line declare unsupported, opening `/dev/fd/5` duplicates the descriptor, which was opened write-only, according to the macOS fd(4) manual page (not run). A user who has copied a token file to a laptop would then get an empty body and no FR-7 message. This applies only to an unsupported system, and a laptop holds a token file only if the user copies one there, assuming `s3df login` runs only on S3DF nodes (the plan names only `/sdf/sw/s3df-cli/bin/s3df`). No amendment.
- info | Error UX | The prologue (research's round 2 amendment) and the `< /dev/null` admission (engineering A2) change no message the user sees. FR-7's exit 2 line still says "Nothing was sent", which stays true because the prologue runs before the argument check and sends nothing.
- info | First-Use Clarity | FR-9's notice (Round 2) still agrees with FR-1, FR-10, and § Permission prompts after the other Round 2 edits. `hub-request.sh` is now named in FR-9 and FR-10 alike (doc-review's amendment), and the rule `Bash(sh <script> *)` matches the command form FR-6 now fixes.

**Opportunities**

- FR-7's exit 7 rows could be keyed by curl's exit code instead of treating everything except 60 as a network failure. Exit 23 would get "the response could not be written to `$TMPDIR`", and exit 56 after a refused `CONNECT` would get "this session's network rules block the catalog", which is a case where a retry cannot help, for example a sandbox whose allowed domains leave out the hub. Neither case was observed, and both are wording.
- FR-10's exit 1 row could add "or after the response arrived, when its copy to standard output fails", with the request marked as sent, so that the table covers the read-back as well.
- Carried from Round 2, not yet done: record the rule the Bash prompt offers for `sh <script> GET …`. That observation settles FR-9's warning and whether Rate and Submit still ask once the rule is saved.

**Decisions Required**

None. No finding in this round needs a decision.

**Amendments**

None. No finding meets the Round 3 bar of a defect that would make the implementation wrong, unsafe, or unbuildable.

TOTAL: 0 design, 0 precision

**Status**

PASS

</details>
