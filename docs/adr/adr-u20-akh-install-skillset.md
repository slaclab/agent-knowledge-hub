# ADR-U20: `install skillset` loops the per-skill install on the client

**Status:** Accepted
**Date:** 2026-10-16
**Context:** todo/006-skillsets.md

## Context

A skillset is an ordered list of catalog skills chosen by its owner, who can be any signed-in user. Installing one means installing each member. Either the backend could return an install bundle, or the client could reuse its own per-skill install for each member.

## Decision

The client's `install skillset <slug>` (`skill/SKILL.md`) fetches `GET /cli/api/skillsets/<slug>`, then for each member, in stored order, fetches its catalog entry and runs the same install as `install <slug>`. The backend gains no install logic; only the skillset read endpoint is new.

- **One question.** Before installing anything, the command fetches every member, checks its values, and asks any replace question a member needs. It then lists what it will install, with each repository and whether the skill brings an MCP server or scripts, and asks once. After that answer the run needs no attention.
- **Fixed commands for the values.** `akh-skillset-members` reads the skillset response and prints the members, refusing a slug that is not a catalog slug. `akh-member-check` reads each catalog entry and refuses a `repo_url`, `skill_path` or `pinned_commit_sha` outside the characters the shell commands can take. The model uses only the values these print. Plain `install` runs the same check.
- **Failures stay local.** A member that fails is reported, and the loop goes on. A summary line, one recap line per failure and a re-run hint end the run; installed members are skipped on a re-run.
- **Install rules unchanged.** Each member gets #051's rules and #053's pinned fetch. The members' agent, left-out and MCP server lines print after the summary, grouped by member, with one lead-in for the run.

## Rejected alternatives

| Alternative | Fact that rules it out |
|---|---|
| A backend `/api/skillsets/{slug}/install-manifest` endpoint | The backend would have to know client install paths and would duplicate the client's install rules |
| Installing members in parallel | GitHub rate limits; the order the curator chose would no longer be the order of output and of failures |
| One question per member | A skillset of ten members would need ten answers, and the run could not be left unattended |
| Letting the model read `repo_url` and `skill_path` from the JSON and build the commands | Any signed-in user can store an entry, and a value with a quote or `$(…)` would run in the user's shell |

## Consequences

- The skillset owner decides what the run installs; the listed members and their repositories are the user's only review point.
- A skillset with many members makes one catalog request per member before the question.
- The command needs `python3` for the two checks, as #051's MCP file command already does.
