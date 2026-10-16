# TODO #053 — **SEC HIGH** — Verify post-checkout HEAD against the pinned SHA in skill install

> **Priority:** 🟠 P1 — High
> **Severity:** HIGH
> **Status:** ✅ Complete — client 2.2.0, on `main` 2026-10-16
> **Branch:** —
> **PR:** —
> **Created:** 2026-10-16
> **Shipped:** 2026-10-16, `.claude-plugin/plugin.json` 2.2.0; reaches a plugin install after the user updates the plugin

---

## Provenance

**Raised by:** `research/concepts/plugin4shell.md`, Amendment 2026-10-16, written while cataloguing
the "Plugin4Shell" vulnerability class (Air Security disclosure; Anthropic GHSA-pq7j-f95f-qfcv /
CVE-2026-86063, patched in Claude Code 2.1.179) for the research corpus. That vulnerability was in
Claude Code's own `/plugin install` mechanism and is already fixed upstream. Reading AKH's own
`skill/SKILL.md` to assess whether AKH's install flow runs through the patched client surfaced a
second, separate instance of the identical defect in AKH's own install instructions — one no vendor
patch touches, because the code in question is AKH's, not Claude Code's.

**References:**
- [#017](017-skill-version-pinning.md) — introduced `pinned_commit_sha`, the value this task must
  verify the clone actually landed on. Complete; this task does not change #017's data model.
- [#022](022-installer-git-clone.md) — introduced the `git clone` + `git checkout <sha>` install
  mechanism this task adds a verification step to. Complete; this task does not change the clone
  mechanism itself, only adds a check after it.
- [#045](045-sec-repo-url-skill-path-allowlist.md) — the `_GITHUB_URL_RE` check this task's mitigating
  factor (GitHub-only submissions) depends on. If that allow-list is ever loosened to accept a
  non-GitHub Git host, this task's risk assessment should be re-run.

**Revised 2026-10-16**, per `research/reports/oct2026-skill-hub-batch-vs-akh.md` (Recommendation 1,
finding A-1). That report read `skill/SKILL.md`'s git history and found two further gaps alongside
the one this task originally scoped, both introduced by the same commit, `0be429a` (2026-06-08,
"docs: overhaul presentation and trim agent-knowledge-hub skill"), which shrank `skill/SKILL.md` from
roughly 610 to 90 lines and silently dropped two lines of pin-handling text that predate this task.
Problem Statement, Goals, Requirements, Non-Goals, Design, and Risk Register below are updated
accordingly; nothing in the original FR-1 through FR-3 scope is removed.

---

## Problem Statement

`skill/SKILL.md` § Install, step 2, instructs the installing agent to run:

```
git clone --depth 1 <repo_url> "$d/repo"
```

then, "check out the pinned SHA if present" — understood from context and from #022's design as
`git -C "$d/repo" checkout <pinned_commit_sha>`. No step in `skill/SKILL.md`, before or after this
one, verifies that the resulting `HEAD` actually equals `pinned_commit_sha`.

Git resolves a ref name ambiguous between a branch and a bare object ID in favor of the branch. A
skill author who controls the upstream repository can create a branch literally named the
40-character SHA that AKH stored as `pinned_commit_sha` at registration time, and set it as the
repository's default branch. The checkout then silently lands on that branch's current tip — fully
controlled by the author, and changeable at any time after registration — while AKH's own
`pinned_commit_sha` field, and the "pinned" / reviewed signal the catalog shows for it, remain
unchanged. The next `/agent-knowledge-hub install <slug>` installs whatever the attacker currently
has at that branch tip onto the user's machine, with no indication to the user or to AKH that the
installed code differs from what was reviewed.

This is the same attack Air Security documented against Claude Code, Codex, and GitHub Copilot
(`research/concepts/plugin4shell.md`), reimplemented independently in AKH's own install instructions.
Unlike that case, no vendor fix applies here: `skill/SKILL.md` is AKH's own text, executed fresh by
whatever agent runs the install, so the gap persists until AKH's own instructions add the check.

**Mitigating factor, not a fix:** AKH's skill submission flow accepts only `https://github.com/...`
repository URLs (`_GITHUB_URL_RE` in `backend/app/schemas/skill.py`, tightened by #045), and GitHub is
reported to reject a branch name shaped like a 40-character hex SHA. That host-level restriction is
currently the only thing standing between this instruction and exploitation — it is a property of
GitHub's ref-naming rules, not anything AKH's own code enforces, and would stop applying the moment
AKH accepts a skill from any other Git host.

### Two further gaps in the same install step (added 2026-10-16)

`0be429a` also removed two other lines that predate this task, which together with the missing
`HEAD` check leave the pin unenforceable on two of the installer's three paths:

- **The Contents API fallback drops the pin entirely.** `skill/SKILL.md` § Install step 2 says
  "Fall back to the GitHub Contents API if git is unavailable, writing into the same directory," with
  no ref. Before `0be429a`, the fallback instruction read `?ref=<pinned_commit_sha>` on every call.
  A user without `git` on `PATH` who installs a pinned skill today gets the unpinned default branch,
  with no indication that the pin was not honored.
- **A shallow clone cannot reach a pinned commit behind the tip.** `git clone --depth 1` fetches only
  the tip of the default branch's history. If `pinned_commit_sha` is not that tip — the ordinary case,
  since a pin exists precisely to hold a skill at a commit before the latest push — `git checkout
  <pinned_commit_sha>` fails outright with "fatal: reference is not a tree," because the object was
  never fetched. Before `0be429a`, step 2 specified a full clone (no `--depth`) whenever a pinned SHA
  was present, which this task's original Design and Risk Register assumed was still true; it is not.
  An install that merely fails safe is not itself a vulnerability, but it means a pinned install cannot
  succeed at all until this is fixed, independent of FR-1's verification check.

---

## Goals

1. `skill/SKILL.md` § Install verifies, immediately after checkout and before any file is read from
   the clone, that `git -C "$d/repo" rev-parse HEAD` equals the `pinned_commit_sha` fetched in step 1.
2. On a mismatch, the install aborts before copying any file, and reports a clear failure to the user
   naming the expected and actual SHA — never silently falling back to "install whatever HEAD is."
3. The check applies whenever `pinned_commit_sha` is present; an unpinned (legacy) skill continues to
   install from `--depth 1` HEAD as it does today, since there is nothing to verify against.
4. When `pinned_commit_sha` is present, `skill/SKILL.md` § Install step 2 obtains that exact commit —
   via a full clone, or a shallow fetch of that SHA specifically — before step 2's checkout, so FR-1
   has a commit to succeed against rather than failing on every non-tip pin.
5. The Contents API fallback either carries the pin (`?ref=<pinned_commit_sha>` on every call) or
   refuses to install a pinned skill at all when `git` is unavailable — never installs a pinned skill
   unpinned.

## Non-Goals

- Does not change the `pinned_commit_sha` data model or the `pin()` / `refetch()` endpoints — #017 is
  complete and unaffected.
- Does not change *whether* `git clone` or the Contents API is used — #022's choice of mechanism is
  unaffected. It does change how each path handles a pin (Goals 4–5), since `0be429a` left both paths
  unable to honor one.
- Does not add support for non-GitHub Git hosts, and does not re-assess the GitHub-only restriction
  that #045 enforces — that restriction is the mitigating factor this task's Problem Statement relies
  on, not something this task changes.
- Does not attempt to detect or block the attacker from creating the SHA-named branch upstream —
  that is outside AKH's control; this task only ensures AKH's own installer refuses to install from it.
- Does not decide whether `skill/SKILL.md`'s `--depth 1` default for an *unpinned* install should
  change — Goal 4 only concerns the pinned case, where a shallow clone cannot succeed at all.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| FR-1 | After `git -C "$d/repo" checkout <pinned_commit_sha>` (or equivalent), and before any file in `$d/repo` is read, run `git -C "$d/repo" rev-parse HEAD` and compare the result to `pinned_commit_sha`. |
| FR-2 | On a mismatch, delete `$d` and stop the install with a line naming both the expected (`pinned_commit_sha`) and actual (`rev-parse HEAD`) SHA. Write nothing to `~/.claude/skills/`, `~/.claude/commands/`, or `~/.claude/agents/`. |
| FR-3 | When `pinned_commit_sha` is absent (legacy/unpinned skill), the install proceeds as today — FR-1 does not apply, since there is no pin to check against. |
| FR-4 | When `pinned_commit_sha` is present, step 2 clones or fetches that exact commit — full clone, or a shallow fetch of the specific SHA — before checkout, instead of today's unconditional `--depth 1` of the default branch tip. The fetched ref is the pinned SHA itself, never `FETCH_HEAD` (a default branch literally named `FETCH_HEAD` is Air Security's Method 2 against Gemini CLI — `research/concepts/plugin4shell.md` §2). |
| FR-5 | When `git` is unavailable and the skill is pinned, the Contents API fallback either passes `?ref=<pinned_commit_sha>` on every call, or refuses the install with a clear message, rather than silently fetching the unpinned default branch. |

---

## Design

```
# pinned install
git clone <repo_url> "$d/repo"                        # full clone — FR-4, no --depth for a pinned SHA
git -C "$d/repo" fetch origin <pinned_commit_sha>      # or: shallow fetch of the SHA itself — FR-4
git -C "$d/repo" checkout <pinned_commit_sha>          # existing step, from #022 — never FETCH_HEAD
actual=$(git -C "$d/repo" rev-parse HEAD)              # new — FR-1
[ "$actual" = "<pinned_commit_sha>" ] || abort          # new — FR-1 / FR-2
# only past this point does step 3 onward read plugin.json or copy any file

# unpinned install — unchanged
git clone --depth 1 <repo_url> "$d/repo"

# git unavailable, skill is pinned — FR-5
# either: every Contents API call carries ?ref=<pinned_commit_sha>
# or: refuse the install and say why
```

The check is a single `git rev-parse` call and a string comparison — no new dependency, no network
call, and no change to what gets cloned or checked out. It belongs in `skill/SKILL.md` § Install step
2, immediately after the existing checkout instruction and before step 3 reads `plugin.json`.

### Key decision

**Verify in the install instructions, not in the backend.** The backend already stores
`pinned_commit_sha` correctly (#017); the defect is that nothing on the installing agent's side
confirms the clone actually landed there. The fix has to live in `skill/SKILL.md`, the same place
#022's clone-and-checkout instruction lives, since that is what executes on the installing user's
machine.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A legitimate skill's upstream repo is force-pushed, moving `pinned_commit_sha` off the branch history entirely | Low | Low | `git checkout <sha>` already fails cleanly in this case (object not found); FR-1's check only matters when checkout *succeeds* but lands somewhere unexpected |
| A pinned install today fails outright, not silently, because `skill/SKILL.md` currently clones `--depth 1` unconditionally (`0be429a`, 2026-06-08) and the pinned commit is usually behind that shallow tip | Confirmed present today, not hypothetical | Medium (fails safe, but pinned installs are broken until fixed) | FR-4 fixes this directly; corrected from this task's original Risk Register, which assumed #022's original full-clone-for-pinned design was still in effect — it was removed by the same commit that dropped the fallback's `?ref=` (§ Problem Statement) |
| The Contents API fallback silently drops the pin when `git` is unavailable | Confirmed present today, not hypothetical | High (installs unpinned code with no signal to the user) | FR-5 |
| AKH later accepts a non-GitHub source and this check is the only remaining protection | Unknown until that decision is made | High | Flagged explicitly in Problem Statement; re-assess this task's risk register if #045's GitHub-only restriction is ever loosened |

---

## Definition of Done

- [x] FR-1 through FR-5 implemented in `skill/SKILL.md` § Install
- [x] A test install (manual or scripted) against a repo with a branch named as a decoy SHA confirms the install aborts with the FR-2 message and writes nothing *(scripted: the decoy is never fetched, so the install gets the reviewed commit; a pin the remote does not serve aborts with `fetch-failed`, and a HEAD other than the pin with `mismatch`. See Verification.)*
- [x] A pinned install whose commit is behind the default branch's tip succeeds (FR-4) — this currently fails outright
- [x] A pinned install with `git` unavailable either carries the pin through the Contents API fallback or refuses with a clear message (FR-5) — today it silently installs unpinned *(refuses; checked by the static test, not run by hand)*
- [x] A normal pinned install (matching SHA) and a normal unpinned/legacy install both continue to succeed unchanged *(pinned: scripted and against GitHub; unpinned: the instruction is unchanged apart from quoting, not run by hand)*
- [x] CHANGELOG entry added under `## Unreleased`

---

## Problems & Solutions

### Decision: fetch the pinned commit by its ID into an empty repository (FR-4)
**Encountered:** 2026-10-16
**Root cause:** a full clone creates a local branch for the remote's default branch, and `git checkout <sha>` switches to a local branch of that name before it considers the commit ID. That is the attack.
**Solution:** `skill/SKILL.md` › Install › Pinned fetch runs a fixed command, `# akh-pinned-fetch`: `git init`, `remote add`, `fetch --depth 1 origin <pinned_commit_sha>`, `checkout --detach <pinned_commit_sha>`, then compares `rev-parse HEAD` with the pin (FR-1). No branch exists in that repository, so the checkout can only resolve the commit, and the check stays as defence in depth. Its last line, `akh-pin: ok`, `akh-pin: fetch-failed` or `akh-pin: mismatch <actual>`, chooses the next step, and each failure has its own stop line (FR-2). A pin that is not 40 characters of `0-9a-f` stops the install before any command runs.

### Decision: no Contents API fallback for a pinned skill (FR-5)
**Encountered:** 2026-10-16
**Root cause:** the Contents API resolves `?ref=` as a branch or tag name as well as a commit, and the result cannot be checked against the pin the way `rev-parse HEAD` can.
**Solution:** a pinned install without `git` stops with "installing a pinned skill needs git, which this computer does not have". Unpinned skills keep the fallback.

### Verification, 2026-10-16
- With git 2.47.3, a bare repository whose default branch is named like commit A and points to an attacker's commit: `git clone` followed by `git checkout <A>` printed only `warning: refname '<A>' is ambiguous` and left `SKILL.md` reading `attacker`. The `akh-pinned-fetch` command, extracted from `SKILL.md`, printed `akh-pin: ok` with `SKILL.md` reading `reviewed`. `backend/tests/test_client_install_rules.py::TestPinnedFetch` runs both, plus a pin behind the tip, a pin the remote does not have (`fetch-failed`, no files), and a HEAD other than the pin (`mismatch`).
- Against GitHub, the catalog's `grill-me` skill is pinned to `694fa303…`, behind its tip `49dd158d…`. Today's `git clone --depth 1` and `git checkout <pin>` failed with `fatal: unable to read tree (694fa303…)`; the new command printed `akh-pin: ok` with `HEAD` at the pin and a 98 KiB pack.
- Mutation check: making the command print `ok` without comparing `HEAD` failed 1 test; going back to clone-then-checkout failed 3.
- Not run: a full `/agent-knowledge-hub install` in a signed-in Claude Code session, as #051's hand-run checks did.

## Board Review

> *Populated by `/board-review` after the board completes. Do not fill manually.*

---

## Relationship to Other Tasks

- **#017 (Commit pinning):** Complete. This task verifies the field #017 introduced is honored at
  install time; it does not change #017's data model or endpoints.
- **#022 (Installer git clone):** Complete. This task adds a verification step immediately after
  #022's existing checkout step; it does not change the clone mechanism.
- **#045 (repo_url / skill_path allow-list):** Complete. Its GitHub-only restriction on `repo_url` is
  the mitigating factor noted in this task's Problem Statement and Risk Register, not something this
  task modifies.
