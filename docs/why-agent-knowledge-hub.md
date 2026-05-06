# Why Use Agent Knowledge Hub

**Audience:** SLAC researchers, engineers, and teams evaluating whether to use the catalog  
**Updated:** 2026-05-06

---

## The problem it solves

Claude Code skills and agents are just Markdown files in GitHub repos. Without a shared
registry, finding useful ones means knowing the right people, trawling Slack channels, or
re-inventing what a colleague already built. The same skill gets written three times in three
different groups, diverges, and none of the versions is documented well enough for anyone else
to trust.

Agent Knowledge Hub is a curated, searchable catalog of skills and agents built for the
SLAC S3DF environment. It gives teams a single place to publish, find, and evaluate AI
productivity tools — with enough metadata to make an informed decision before installing
anything.

---

## Benefits

### Centralised catalog

Every published skill lives at one URL. Whether you need a skill for running SLURM jobs,
querying experiment databases, or navigating SLAC's internal systems, the catalog is the
first place to look — not a Slack message or a colleague's dotfiles.

- Full-text search across name, description, README, and labels.
- Browse by label to explore a domain without knowing what to search for.
- Sort by newest, highest-rated, most-rated, or most GitHub stars to surface the most
  relevant or trusted options.

### Organisation through labels

Skills are tagged with labels that describe what they do, what they integrate with, and
what kind of component they contain. Labels are applied both automatically (from
`plugin.json` metadata) and manually by the community.

```
mcp          — skill ships an MCP server
multi-agent  — skill coordinates multiple sub-agents
has-scripts  — skill includes shell or Python helper scripts
slurm        — SLAC HPC job submission
python       — Python-focused tooling
data-science — data analysis and visualisation
```

AND-filter semantics: selecting `slurm` + `python` returns only skills tagged with
both, narrowing results precisely. A skill with no relevant labels simply does not
appear in filtered views, keeping the signal clean.

### Provenance and trust

Every skill in the catalog has a clear chain of custody:

- **Submitter** — who added the skill and when.
- **GitHub source** — the exact repo URL and subdirectory path; one click to audit the
  raw files before installing anything.
- **Revision history** — a timestamped log of every edit, refetch, and status change,
  with the actor recorded. You can see when a skill was last updated and why.
- **Last commit date** — pulled live from GitHub at submission and on each rescan, so
  stale or abandoned skills are visible at a glance.
- **License** — surfaced automatically from the GitHub repo, so compliance questions
  have an immediate answer.
- **Fork lineage** — if a skill was derived from another catalog entry, the fork
  relationship is recorded. You can see the upstream source and whether the fork has
  diverged or improved on the original.

### Quality signals

The catalog surfaces signals that help you judge a skill before installing it:

| Signal | What it tells you |
|---|---|
| Average rating (1–5 stars) | Community experience with the skill in practice |
| Rating count | How widely the skill has been tried |
| GitHub stars | Broader upstream adoption beyond the catalog |
| Last commit | Whether the skill is actively maintained |
| Agent count | How many sub-agents the skill orchestrates |
| MCP server | Whether the skill exposes tool endpoints to Claude |

Ratings are per-user and authenticated — you know real humans at SLAC tried the skill,
not a bot inflating scores.

### Visibility control for SLAC-internal skills

Some skills wrap internal APIs, reference internal hostnames, or contain logic that should
not be public. The catalog supports two visibility levels:

- **Public** — visible and readable by anyone, including unauthenticated users.
- **Internal (SLAC-only)** — metadata (name, description, labels) is visible to all, but
  README and skill instruction content is shown only to authenticated SLAC users. The
  underlying GitHub repo is a private or internal SLAC Enterprise Cloud repo; the GitHub
  App credential ensures the backend can fetch it without exposing a personal token.

This means internal teams can publish and share skills safely without making sensitive
operational detail visible outside the organisation.

### Automatic metadata extraction

Submitting a skill requires only a GitHub URL. The catalog fetches and indexes:

- `SKILL.md` or `CLAUDE.md` — the instruction file Claude reads when the skill is active.
- `README.md` — rendered in the catalog detail page so you can read full documentation
  without leaving the browser.
- `plugin.json` — parsed for agent count, MCP server presence, scripts, author, version,
  keywords, and compatible platforms.

The same scan runs on every **Rescan from GitHub** action, so the catalog stays current as
skills evolve. No manual metadata entry is required.

### Reduced duplication

Before publishing, the submission form checks whether a skill with the same repo URL and
path already exists. Duplicate submissions are blocked and the existing entry is linked
instead. This keeps the catalog free of near-identical forks that fragment the community
around subtly different versions of the same tool.

For intentional forks (a team customises an upstream skill for local infrastructure), the
fork relationship is recorded so both the upstream and the local variant are discoverable
and their lineage is clear.

### In-agent installation

Skills in the catalog can be installed directly from inside a Claude Code session using the
`/agent-knowledge-hub` skill:

```
/agent-knowledge-hub search slurm job submission
/agent-knowledge-hub install slurm-helper
```

The installer reads `plugin.json` and places skill files in `~/.claude/skills/`, commands
in `~/.claude/commands/`, and registers any MCP servers — in one step, without leaving the
terminal. No manual `git clone`, no copying files by hand.

---

## Who should publish to the catalog

- **Platform teams** building reusable infrastructure skills (HPC, storage, experiment
  control) that multiple groups will use.
- **Research groups** that have invested in a well-tested agent workflow and want others
  to benefit from it.
- **Anyone** who has built a skill that took non-trivial effort to get right — the catalog
  is the mechanism for that effort to compound across the lab rather than staying in one
  person's dotfiles.

Publishing is low-friction: paste a GitHub URL, confirm the metadata, submit. The catalog
does the rest.
