> **Concept:** open-agent-hub — Curated Skill/Agent/Command Bundle with Local CLI Linker
> **Source:** GitHub (`guanyang/open-agent-hub`)
> **Relevance:** Comparator to Agent Knowledge Hub's own product, though not a marketplace peer —
> it is a single curated bundle repo plus a local link manager, not a hosted multi-publisher
> catalog

*Generated 2026-10-16 / Confidence: High (README + repo metadata, corroborated by independent WebSearch; root directory listing not retrieved — rate-limited)*

---

## 1. Overview

open-agent-hub is a TypeScript CLI tool (`oah`, aliases `open-agent-hub`, `ahub`) that links a
single bundled collection of capability files — 83+ **Skills**, expert-role **Agents**, and
slash-command **Commands** — into the project or user-global configuration directories of eight
AI coding assistants. It is MIT-licensed, 980 stars, 165 forks as of 2026-10-16, created
2026-01-13 and pushed as recently as 2026-10-13 — actively maintained. It has no hosted website
(`homepage` is empty in repo metadata); distribution is entirely through the GitHub repository
and two CLI install paths.

**Repo:** https://github.com/guanyang/open-agent-hub

A same-named but unrelated project, `robertdalla/open-agent-hub`, also exists on GitHub with a
different description; a straight fork, `xizhuomengcontin/open-agent-hub`, also surfaced in
search. This entry documents only `guanyang/open-agent-hub`, the repository the catalog request
specified and the one matching the install commands quoted below.

---

## 2. Capability Representation

Each capability is a standalone Markdown file with YAML frontmatter, organised by type into three
top-level directories:

```
skills/     # 83+ modular capability skills (SKILL.md-style)
agents/     # System prompts for expert Agents (agent-*.md) — Orchestrator, Evaluator, Optimizer roles
commands/   # Agent-facing slash commands (*.md), e.g. /commit, /review, /test-tdd
```

A generated `skills_index.json` holds scanned metadata for all capabilities; `skills_sources.json`
configures upstream repos that `oah sync` pulls from (one named source is "anthropics-skills").
Some bundled content is explicitly derived from other skill repos rather than originally authored
here — the project's own `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` guideline files are noted in the
README as "derived from andrej-karpathy-skills (github.com/multica-ai/andrej-karpathy-skills)."

This format is structurally compatible with AKH's own `SKILL.md` convention, but the unit of
distribution differs: AKH treats each skill as an independently publishable, independently rated
artifact; open-agent-hub treats its entire 83+-skill set as one bundle, selectively activated by
name or by `--skills`/`--agents`/`--commands` filters at link time.

---

## 3. Discovery & Search

There is no search backend, no hosted index, and no web UI. Discovery is one of:

- **Browse the repository** directly on GitHub.
- **`oah list`** — a local filesystem scan of the cloned repo's `skills/`, `agents/`, `commands/`
  directories, producing (or reading) `skills_index.json`. This lists everything available; it
  does not rank, filter semantically, or search by natural language.

This is a materially different discovery model from AKH's `/agent-knowledge-hub find me something
for X` natural-language request matching, and from the keyword/semantic registries surveyed in
[concepts/mcp-registry-landscape.md](mcp-registry-landscape.md) — open-agent-hub has no query
interface of its own at all.

---

## 4. Install Flow

Two independent paths, documented side by side in the README:

**Path A — Vercel Labs' `skills` CLI** (external tool this project does not build or control):

```bash
npx skills@latest add guanyang/open-agent-hub
npx skills@latest add guanyang/open-agent-hub --skill remotion
```

This is the same `npx skills` ecosystem documented in
[concepts/agenticskills-find-skills.md](agenticskills-find-skills.md) — open-agent-hub piggybacks
on a third party's install plumbing for GitHub-wide distribution rather than building its own.

**Path B — the project's own `oah` CLI**, after `git clone` + `npm link`:

```bash
oah list                                    # scan and list everything available
oah status [--global]                       # check current link state
oah enable [<name>|--skills|--agents|--commands|--all] [-p|-g] [-t <target>|--path <dir>]
oah disable [...]
oah sync [<source>]                         # pull from skills_sources.json upstreams
```

`oah` links (symlinks by default) capability files into eight target clients' project or global
config paths — e.g. `.claude/` (project) / `~/.claude/` (global) for Claude Code, and similarly
for Antigravity, Gemini CLI, Codex, Cursor, Trae, OpenCode, and Kiro. Native plugin manifests are
additionally provided for Claude Code, Codex, and Cursor (`.claude-plugin/`, `.codex-plugin/`,
`.cursor-plugin/`).

---

## 5. Rating / Trust System

None. No per-capability star rating, review, or community voting mechanism exists. The only trust
signals are repo-level: GitHub stars (980) and forks (165) on the whole bundle, a `SECURITY.md`
vulnerability-reporting policy, and a `CONTRIBUTING.md` for community submissions. There is no
approval gate, moderation queue, or quality score comparable to AKH's rating system or to the
five-dimension scoring scheme documented in [concepts/skillnet.md](skillnet.md).

---

## 6. Tech Stack

TypeScript, Node.js. Registers as a global CLI (`npm link`) under the command `open-agent` with
aliases `oah` and `ahub`. Declared "zero-dependency" in the project description. Sync mechanism is
a shell script (`scripts/sync_skills.sh`) driven by `skills_sources.json`. No backend service, no
database — everything is static files plus a local CLI.

---

## 7. Comparison to AKH

| Dimension | AKH | open-agent-hub |
|---|---|---|
| Distribution unit | Many independently published skills, one hosted catalog | One curated monorepo (83+ skills) cloned or filtered as a whole |
| Hosted marketplace | Yes — web UI, browse, filter by label | No — GitHub repo only, no homepage |
| Auth | S3DF sign-in (SLAC-gated) | None — public GitHub, standard OSS contribution |
| Discovery | Natural-language request matched by the assistant, plus label-filtered browsing | `oah list` (static local scan) or Vercel's separate `skills find` (see §4, Path A) |
| Ratings | 1–5 star community ratings, live average | None |
| Multi-client reach | claude-code + codex | 8 clients (adds Antigravity, Gemini CLI, Cursor, Trae, OpenCode, Kiro) |
| MCP server bundling | Yes (one documented exception in install flow) | Not mentioned anywhere in the README |
| Governance | SLAC Members Only badges for access-gated skills | None described |

**Net assessment:** the task framing calls this a direct architectural comparator, and it is one
on *format* (SKILL.md-equivalent files with YAML frontmatter) and on *multi-client link mechanics*
(project vs. global scope, per-client path tables) — both are patterns AKH already follows or
could extend. It is not a comparator on *marketplace mechanics*: open-agent-hub has no search
backend, no ratings, no auth, and no hosted site of its own. Its broader client reach (8 targets
vs. AKH's 2) is the most directly actionable fact for AKH's own multi-platform roadmap.

---

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — multi-client reach adopted conditionally (A-6); `oah` linker and `npx skills` landscape-only (L-1, L-2). Corrects §7: AKH's install reach is one client (Claude Code), not two; `codex` is `compatible_platforms` metadata only since commit `0be429a`.

Candidate noted at cataloguing: a report assessing whether AKH should extend
client-target coverage (Antigravity, Gemini CLI, Trae, OpenCode, Kiro) the way open-agent-hub has,
and whether AKH should interoperate with the `npx skills` ecosystem rather than compete with it —
see also [concepts/agenticskills-find-skills.md](agenticskills-find-skills.md), which documents
the same underlying CLI from the discovery-directory side.

---

## Sources

- https://github.com/guanyang/open-agent-hub — fetched 2026-10-16 (README via
  raw.githubusercontent.com; repo metadata via api.github.com; root directory listing attempted
  but hit the GitHub API rate limit — 403 — on the second call)
- WebSearch "github guanyang open-agent-hub" — fetched 2026-10-16 (independent corroboration of
  README facts: CLI commands, directory structure, install paths)
