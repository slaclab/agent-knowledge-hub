# TODO #050 — Client Token Helper: S3DF Token from the Real Home, Kept Out of Process Arguments, Sent Only to the Catalog

> **Priority:** 🟡 P2 — Medium
> **Status:** ⬜ Open
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-14
> **Shipped:** —

---

## Problem Statement

The `/agent-knowledge-hub` client in `skill/SKILL.md` is prose that the model follows. It names `~/.s3df-access-token` as its token file and asks for `Authorization: Bearer <token>` on rate and submit, but it leaves the command that sends the token to the model. Every catalog request needs the token, because the catalog answers 401 on each CLI path the client uses when no token is sent (#006 › Measured facts › cli-auth). Four defects follow.

1. The token can land in a process's arguments. `curl -H "Authorization: Bearer $(cat ~/.s3df-access-token)"`, the form #006 › FR-7 › Auth rule plans, expands the token into curl's command line, where other users of a shared S3DF node can read it from `/proc/<pid>/cmdline`, for example with `ps`.
2. Nothing fixes where the token goes. Any signed-in user can submit a skill, so catalog text comes from any signed-in user. Text that steers the model to a curl call with another URL, `--url`, `-K`/`--config`, or `@` user information in the address sends the token to that host, because curl sends the same headers to every URL it is given. A helper that accepted any URL would make that theft look like a sanctioned hub request; with a fixed destination, the theft needs the model to read the token file, which FR-6 forbids.
3. The client cannot find the token in a Cogito session. Cogito sets `$HOME` to a per-machine directory, where `.s3df-access-token` does not exist (Measured facts), and Cogito records that a browser sign-in renews the token in the account's real home directory.
4. Error handling in `skill/SKILL.md` has no 401 case, so an expired or missing sign-in reaches the user as a bare HTTP error.

The Cogito deployment (`slaclab/cogito`, TODO #200) files this task as hub request H-1. Cogito copies this repository's `skill/` folder into its host image as a Claude Code managed skill, so every Cogito session carries the client, and its NFR-3 requires that the client never places the token in a process's arguments or in a file outside the real home. Cogito's slice 2, which ships the client in the image, pins a commit of this repository that includes this task.

### What fails today

As of 2026-10-14:

| Scenario | Current behaviour | Desired behaviour |
|---|---|---|
| A user searches from a Cogito session | The client looks for `~/.s3df-access-token`, which is absent from a Cogito session's `$HOME`, and the catalog answers 401 | The helper reads the token from the account's real home, and the search returns results |
| The client sends a token on a shared S3DF node | The model writes the command; the `$(cat …)` form puts the token in curl's arguments | The token reaches curl on standard input and appears in no process's arguments |
| A catalog entry's text asks the model to run curl against another host | Nothing in the client stops the token going there | The helper sends only to `https://agent-knowledge-hub.slac.stanford.edu` and refuses a URL or a curl option as an argument |
| The token has expired or was never written | The 401 has no case in Error handling | The client says the S3DF sign-in is missing or has expired, and how to renew it |

---

## Goals

1. Every catalog request the client makes goes through one shell helper shipped in `skill/`, and only the helper reads the token.
2. The token appears in no process's arguments and in no file other than the token file.
3. The token goes only to `https://agent-knowledge-hub.slac.stanford.edu`.
4. A missing, malformed, or expired token gets one message that says how to renew it.

## Non-Goals

- Changing the token's audience. Token exposure, below, states what that leaves in place.
- Requests to GitHub. Clones carry no catalog token, and the helper never sends one there.
- The dev and stage catalogs. The helper's origin is the production catalog only.
- Pre-approving the helper so that a prompting session does not ask before each call. FR-6 rules out `allowed-tools`; a managed-settings allow rule is for each deployment to decide.

---

## Requirements

### Functional

- **FR-1:** One helper. The client makes every authenticated request through a shell helper shipped in `skill/` and run as `sh ${CLAUDE_SKILL_DIR}/<helper>`. Claude Code replaces `${CLAUDE_SKILL_DIR}` with the directory holding the skill's `SKILL.md`, and for a plugin skill with the skill's subdirectory inside the plugin (Measured facts). The `SKILL.md` runs the helper through `sh` because Cogito installs the folder's files with mode 0644, so the helper is not executable there. A helper is needed at all because the client is otherwise prose the model follows, and an instruction cannot guarantee where the token goes.
- **FR-2:** Token location. The helper reads the token from the account's real home, `$(getent passwd "$(id -un)" | cut -d: -f6)/.s3df-access-token`, and falls back to `~/.s3df-access-token` when `getent` returns no home or that file is absent.
- **FR-3:** Token shape. The helper refuses a token file holding anything but base64url segments and dots. After carriage returns and newlines are removed, the content must be non-empty and contain only `A`–`Z`, `a`–`z`, `0`–`9`, `.`, `_`, and `-`. Cogito's `s3df-mcp-headers`, the helper that hands the same token to its MCP gateway, applies the same rule.
- **FR-4:** No argument, no file. The helper hands the `Authorization` header to curl on standard input (`curl -H @-`), so the token is in no process's arguments and in no file. It writes no temporary file holding the token.
- **FR-5:** Fixed destination. The helper takes a method, a path beginning with `/`, and an optional request body, and passes curl nothing else from its arguments. It sends the request only to `https://agent-knowledge-hub.slac.stanford.edu`, joined with the path, and does not follow redirects. It refuses a URL or a curl option given as an argument. Text in a catalog entry therefore cannot steer the token to another host through what the model takes for a hub request.
- **FR-6:** `SKILL.md` rules. The `SKILL.md` tells the model to call only the helper for hub requests and never to read, print, or decode the token file. It must still pass Cogito's content rule for skills it loads into every session, or Cogito's build refuses the lock row that pins this repository. That rule admits only the frontmatter keys `name`, `description`, `when_to_use`, `argument-hint`, `arguments`, `version`, `license`, `metadata`, `disable-model-invocation`, `user-invocable`, and `disallowed-tools`; refuses inline shell, meaning any `` !` `` and any fence opened with ```` ```! ````; and refuses a symlink or submodule in the skill folder. The helper therefore cannot be pre-approved with `allowed-tools` or run through inline shell. The `SKILL.md` on `main` carries only `name` and `description` and no inline shell, so it passes as of 2026-10-14.
- **FR-7:** 401 and missing token. Error handling in `skill/SKILL.md` gains a 401 case. The client tells the user that the S3DF sign-in is missing or has expired, and that running `/sdf/sw/s3df-cli/bin/s3df login` on an S3DF node, or opening Cogito in a new private browser window, renews it. The client does not print or read out the token. A token file that is absent from both places in FR-2, or that the helper refuses under FR-3, gets the same message, and the helper then makes no request.
- **FR-8:** Test. A test in this repository runs the helper against a fake server and asserts that the token appears neither in curl's `/proc/<pid>/cmdline` nor in the helper's output, and that a URL or a curl option given as an argument is refused.

### Acceptance Criteria

- **AC-1:** Given a token file in the real home and none in `$HOME`, when the helper sends `GET /cli/api/skills/summary` to the fake server, then the request carries that token.
- **AC-2:** Given a request the fake server holds open, when the test reads curl's `/proc/<pid>/cmdline`, then the token is absent from it, and it is absent from the helper's standard output and standard error.
- **AC-3:** Given an argument that is a URL, a path not beginning with `/`, or a curl option such as `--url`, `-K`, `--config`, or `-x`, when the helper runs, then it exits non-zero and makes no request.
- **AC-4:** Given a fake server that answers with a redirect to another host, when the helper sends a request, then it does not request the redirect target.
- **AC-5:** Given no token file in either place, or one holding a character outside FR-3's set, when the helper runs, then it makes no request, and the client shows FR-7's message.
- **AC-6:** Given a 401 from the catalog, when the client handles it, then it shows FR-7's message and prints no token.
- **AC-7:** Given `skill/SKILL.md` at the commit that ships this task, then its frontmatter has no key outside FR-6's list and its text holds neither `` !` `` nor ```` ```! ````.

### Definition of Done

- [ ] FR-1 to FR-8 built; AC-1 to AC-7 pass
- [ ] The **Token file** line in the header block of `skill/SKILL.md` names the real home and the fallback, and every section that sends a request (Search, Install, the install event, Rate, Submit) calls the helper
- [ ] `version` in `.claude-plugin/plugin.json` raised, because an existing plugin install receives a new copy only when the plugin's computed version changes (#006 › References › Claude Code plugin updates)
- [ ] CHANGELOG entry naming the helper, the new token location, and the 401 message
- [ ] The shipping commit is on `main` or a tag of `slaclab/agent-knowledge-hub`, because Cogito's lock refuses a commit that no branch or tag contains

---

## Token exposure

The helper makes the catalog one more service that receives the account's S3DF token. The token is not bound to the catalog: the backend accepts the audience `s3df` (Measured facts), which Cogito TODO #200 records as the audience every other S3DF service accepts. A compromise of the backend, or of anything that records its request headers, therefore exposes the token of every user whose session calls it, and that token works at every other S3DF service. This task does not change the exposure. An audience issued for the catalog alone would bound it and is outside this task.

---

## Open Design Questions

1. **How the test reaches a fake server when the origin is fixed.** An environment variable or an argument that changes the origin would let the model change it too, so the shipped helper reads neither. One way: the test runs a copy of the helper with the origin constant replaced by the fake server's address, and separately asserts that the shipped helper's constant is `https://agent-knowledge-hub.slac.stanford.edu`.
2. **How the request body reaches curl when standard input carries the header.** `--data-raw` keeps the body in curl's arguments, which is acceptable because the body holds no secret, but Linux caps one argument at 128 KiB (`MAX_ARG_STRLEN`), and a `submit` of a skill directory can exceed that. A body file named by the caller is the alternative; the helper then needs a rule for which files it reads.
3. **Whether curl's environment and configuration can change the destination.** curl reads `~/.curlrc`, or `$CURL_HOME/.curlrc`, unless `-q` is its first argument, and the model can prefix the helper call with environment variables such as `PATH` or `CURL_HOME`. Running curl by absolute path with `-q` first closes the configuration-file route. Whether the proxy and CA-bundle variables need the same treatment is a question for the security review.
4. **Which methods the helper accepts.** The client uses `GET` (Search, Install, file fetches) and `POST` (Rate, the install event, Submit). A fixed list makes FR-5's refusal of an option-shaped method a one-line check.
5. **Whether Submit keeps its `AGENT_KNOWLEDGE_HUB_TOKEN` override.** FR-2 names the token files only.

---

## Measured facts — read 2026-10-14, re-derive before implementing

| Fact | Value | How |
|---|---|---|
| The client's token handling | `skill/SKILL.md` names `~/.s3df-access-token` as **Token file** and mentions the bearer header only under Rate and Submit; Submit also accepts `AGENT_KNOWLEDGE_HUB_TOKEN` | Read `skill/SKILL.md` on `main` |
| The client's error cases | 404, 410, path traversal, 403 rate limit, network error; no 401 | Same file, § Error handling |
| The client's frontmatter | `name` and `description` only; no `` !` `` and no ```` ```! ```` in the text | Same file |
| Request paths | The catalog base URL is `https://agent-knowledge-hub.slac.stanford.edu/cli`, so every request path begins with `/cli/api/` | Same file; `docs/adr/adr-p08-split-ingress.md` |
| Token audience and issuer | `JWT_AUDIENCE=s3df`, `JWT_ISSUER=https://dex.slac.stanford.edu` | `kubernetes/overlays/prod/kustomization.yaml` |
| `$HOME` in a Cogito session | A per-machine directory, not the account's home; `.s3df-access-token` is absent there | Recorded in Cogito TODO #200 › Measured facts, measured 2026-10-05 with `stat`; not re-measured here |
| `${CLAUDE_SKILL_DIR}` | "The directory containing the skill's `SKILL.md` file. For plugin skills, this is the skill's subdirectory within the plugin" | Quoted in Cogito TODO #200 from the Claude Code `skills` documentation; not re-checked here |

---

## Relationship to Other Tasks

- **Cogito TODO #200 (`slaclab/cogito`), hub request H-1:** Cogito's slice 2 adds a lock row, its FR-5, that loads this repository's `skill/` folder into every Cogito session at a commit that includes this task. That row, and with it slice 2, waits for this task. Cogito reviews the row against FR-8's test; its AC-7 checks the 401 case by reading `SKILL.md` at that commit and checks with `ps` during a live search that no token appears. Slice 2 also waits on a question of Cogito's own, about the MCP servers and agents the client installs, which does not involve this task.
- **#006 (Skillsets):** FR-7 › Auth rule reads the token with `$(cat ~/.s3df-access-token)` inside curl's arguments, which breaks FR-2 and FR-4 here. Slice 4 of #006 should send its requests through this helper. #006's 401 message points to `s3df login`; FR-7 here gives the message for both tasks.
- **#007 (`/agent-knowledge-hub` skill):** the client this task changes.
- **#016 (Bearer JWT auth):** the token `s3df login` writes and the backend validates. This task changes where the client finds it, not how the backend checks it.
- **#047 (marketplace.json reachable from Claude Code):** a marketplace `headersHelper`, if #047 chooses one, needs FR-2, FR-3, and a fixed destination too.
- **#048 (install internal skills through the files route):** its file fetches are catalog requests and go through this helper.
