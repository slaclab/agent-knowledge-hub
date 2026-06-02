---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 28px;
    padding: 48px 60px;
  }
  h1 { color: #1a1a2e; font-size: 2em; margin-bottom: 0.3em; }
  h2 { color: #16213e; font-size: 1.4em; border-bottom: 2px solid #0077b6; padding-bottom: 0.2em; }
  h3 { color: #0077b6; font-size: 1.1em; margin-bottom: 0.2em; }
  .lead { color: #555; font-size: 1.1em; margin-top: 0; }
  code { background: #f0f4f8; border-radius: 4px; padding: 0 6px; font-size: 0.85em; }
  pre code { background: none; padding: 0; font-size: 0.78em; }
  pre { background: #1e1e2e; color: #cdd6f4; border-radius: 8px; padding: 20px; }
  blockquote { border-left: 4px solid #0077b6; padding-left: 1em; color: #444; font-style: italic; }
  ul li, ol li { margin-bottom: 0.3em; }
  section.title { text-align: center; display: flex; flex-direction: column; justify-content: center; }
  section.title h1 { font-size: 2.4em; }
  section.title p { color: #555; font-size: 1em; }
  section.section-break { background: #1a1a2e; color: white; display: flex; flex-direction: column; justify-content: center; text-align: center; }
  section.section-break h2 { color: white; border-bottom-color: #0077b6; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
  .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; }
  .card h3 { margin-top: 0; }
  .card p { color: #555; font-size: 0.85em; margin: 0; }
  .highlight { background: #e8f4fd; border-left: 4px solid #0077b6; padding: 12px 16px; border-radius: 0 8px 8px 0; }
  .badge { display: inline-block; background: #0077b6; color: white; border-radius: 4px; padding: 2px 8px; font-size: 0.7em; font-weight: bold; vertical-align: middle; }
  footer { font-size: 0.6em; color: #aaa; }
---

<!-- _class: title -->

# Agent Skills &
# Agent Knowledge Hub

### What they are, why they matter, and how to use them at SLAC

<br>

**S3DF / SLAC Computing**
agent-knowledge-hub.slac.stanford.edu

---

## You probably already feel this problem

> *"Every time I start a Claude session I have to explain how our cluster works, which tools to use, and what our naming conventions are."*

> *"My colleague built something useful for analysing log files — but I only found out by accident at a group meeting."*

> *"I wrote a script to automate our data archiving workflow, but nobody else on my team knows how to use it with Claude."*

<br>

These are not individual problems. They are organisational problems with an organisational solution.

---

## What is a skill?

A **skill** is a reusable set of instructions you give to an AI agent — like Claude — so it consistently follows a specific workflow, applies domain knowledge, or enforces a process every time it is invoked.

<br>

<div class="highlight">
Think of a skill the way you think of a <strong>Standard Operating Procedure</strong>: it records the right way to do something so that anyone — or any AI — can follow it without needing to be re-taught every time.
</div>

<br>

In practice: a skill is a **plain Markdown file** stored in `~/.claude/skills/` that Claude reads when you invoke it.

---

## Without a skill vs. with a skill

<div class="grid-2">
<div>

**Without a skill** — every session, you:

- Re-explain your data format
- Remind Claude of your cluster's layout
- Paste the same conventions from a wiki page
- Hope it remembers from context

*Same prompt written 50 times by 50 people.*

</div>
<div>

**With a skill** — you:

- Type `/slurm-helper submit my_job.sh`
- Get the same correct, checked result every time
- Share it once; everyone benefits

*Written once, used by everyone.*

</div>
</div>

---

<!-- _class: section-break -->

## Part 1: Skills

### What they do and who they're for

---

## What skills are good for

<div class="grid-3">
<div class="card">
<h3>📋 Runbooks</h3>
<p>Convert an existing runbook into a skill. The agent walks an on-call engineer through diagnosis steps without hunting the wiki at 2 am.</p>
</div>
<div class="card">
<h3>⚗️ Analysis workflows</h3>
<p>Define how to load, clean, and plot data from a specific instrument so every analysis starts from the same baseline.</p>
</div>
<div class="card">
<h3>🔬 Domain knowledge</h3>
<p>Embed preferred physical constants, unit conventions, simulation parameters — things the agent would otherwise have to guess.</p>
</div>
<div class="card">
<h3>💻 Coding standards</h3>
<p>Encode your team's naming conventions, testing rules, or security checklist so reviews are consistent.</p>
</div>
<div class="card">
<h3>🛡️ Safety guardrails</h3>
<p>Rules the agent must check before acting — e.g. never delete raw data, always confirm before writing to a shared path.</p>
</div>
<div class="card">
<h3>🎓 Onboarding</h3>
<p>Walk new collaborators through the cluster, data systems, or codebase so they get consistent, up-to-date answers.</p>
</div>
</div>

---

## Examples: for researchers (non-programming)

**Experiment log reviewer**
A skill that reads a standard LCLS log format, flags anomalous readings, and generates a summary in your group's preferred template — same output every run.

**Beam-time request assistant**
Guides the agent through the correct steps and required fields for submitting a beam-time request — with the right internal links already embedded.

**NeXus file analyst**
Knows your instrument's data schema. Ask: *"Plot the detector image for run 42"* and get a working analysis without writing a line of code.

**Safety checklist enforcer**
Before any destructive operation on experiment data: the agent checks a hardcoded list of safety questions and refuses to proceed until each is confirmed.

---

## Examples: for platform / infra engineers

**Kubernetes deployment helper**
Knows the S3DF cluster layout, approved Helm chart patterns, and the dev → staging → prod promotion steps. Ask *"deploy my app"* and get it right every time.

**SLURM job submission skill**
Correct partition selection, memory limits, MPI flags, and email-on-fail settings for SLAC HPC — no more searching the wiki for the right `#SBATCH` options.

**On-call incident runbook**
A skill built from a real runbook: check the right dashboards, run the right queries, escalate in the right order. No memory required at 3 am.

**Kubernetes diagnostics**
*"Why is my pod crashlooping?"* — the skill knows to check events, recent log lines, resource limits, and liveness probe config in a defined order.

---

## Examples: for software engineers

**Code review checklist**
Acts like a senior reviewer who never forgets a step: security issues, test coverage, style violations, API backwards-compatibility — applied consistently on every PR.

**TDD workflow enforcer**
Ensures the agent follows your team's red→green→refactor cycle, writes tests before implementation, and does not add speculative features.

**Python data science starter**
Preferred libraries (pandas, polars, matplotlib), your team's plotting style, common dataset paths — loaded automatically so every analysis starts from the same scaffold.

**Multi-agent pipeline builder**
Orchestrates a fleet of sub-agents: one reads files, one analyses, one writes the report. Skills can coordinate complex multi-step workflows automatically.

---

## A skill can also include tools (MCP servers)

Some skills ship not just instructions but **live tool integrations**:

```json
{
  "mcp-servers": [{
    "name": "slurm-mcp",
    "command": "python",
    "args": ["-m", "slurm_mcp.server"]
  }]
}
```

When installed, this registers a **Model Context Protocol server** — Claude can now call real functions like `submit_job()`, `get_queue_status()`, or `cancel_job()` directly during the conversation.

<br>

MCP turns a skill from *instructions* into *actual capabilities*.

---

<!-- _class: section-break -->

## Part 2: Agent Knowledge Hub

### The catalog that makes skills shareable at SLAC

---

## The problem with skills today

Skills are just Markdown files in GitHub repos.

Without a shared registry:

- **Discovery** — finding useful skills means knowing the right people or trawling Slack
- **Duplication** — the same skill gets written three times in three groups, all slightly different
- **Trust** — no way to tell if a skill is maintained, tested, or even intentionally malicious
- **Visibility** — skills that took real effort to build stay in one person's dotfiles

<br>

**Agent Knowledge Hub is the solution to all four.**

---

## What Agent Knowledge Hub provides

<div class="grid-2">
<div>

**Browse & discover**
- Full-text search: name, description, README, labels
- Filter by label (AND semantics — narrow precisely)
- Sort: newest, highest rated, most stars

**Trust signals**
- ⭐ Community ratings (real SLAC users)
- 📅 Last commit date (spot abandoned skills)
- 👤 Submitter + revision history
- 🔗 One click to the source repo

</div>
<div>

**Publish**
- Paste a GitHub URL — that's it
- Metadata extracted automatically from `SKILL.md`, `README.md`, `plugin.json`
- SLAC-internal (private repo) skills fully supported

**Install**
- From inside Claude Code — no manual file copying
- `/agent-knowledge-hub install slurm-helper`
- Handles skills, commands, agents, and MCP servers in one step

</div>
</div>

---

## Install without leaving your session

```
/agent-knowledge-hub I'm trying to figure out what's wrong with my Kubernetes deployment
```

→ Claude searches the catalog, finds the most relevant skills, explains each one, and asks if you want to install.

<br>

```
/agent-knowledge-hub install slurm-helper
```

→ Downloads and registers all components (skill files, agents, MCP servers) to the right places automatically. No `git clone`, no copying files.

<br>

Register the marketplace once to get started:

```
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json
/plugin install agent-knowledge-hub
```

---

## Visibility control for SLAC-internal skills

Not everything should be public. Agent Knowledge Hub supports two levels:

| Level | Who can see metadata? | Who can read content? |
|---|---|---|
| **Public** | Everyone | Everyone |
| **SLAC Only** | Everyone | Authenticated SLAC users |

<br>

This means platform teams can publish skills that wrap **internal APIs**, reference **internal hostnames**, or contain **operational detail** — visible and discoverable inside SLAC, without exposing anything outside.

SLAC-internal skills are shown with a 🔒 **SLAC Only** badge so you know upfront.

---

## Who should publish to the catalog?

**Platform teams** building reusable infrastructure skills (HPC, storage, experiment control) that multiple groups will use.

**Research groups** that have invested in a well-tested agent workflow and want others to benefit from it.

**Anyone** who has built a skill that took non-trivial effort to get right.

<br>

<div class="highlight">
Publishing is low-friction: paste a GitHub URL, confirm the metadata, submit.<br>
<strong>The effort you put in compounds across the lab rather than staying in one person's dotfiles.</strong>
</div>

---

## Create and share your own skill

Scaffold a new skill from scratch — without leaving your session:

```
/agent-knowledge-hub create
```

Prompts for name, description, agents, MCP servers, and platform support.
Generates the correct directory structure, `SKILL.md`, and `plugin.json`.

<br>

Then submit it:

```
/agent-knowledge-hub submit
```

Or submit a local skill directory (no GitHub required):

```
/agent-knowledge-hub submit ./my-skill/
```

---

## Summary

<div class="grid-2">
<div>

**Skills** let you:
- Capture workflows, domain knowledge, and standards once
- Apply them consistently in every AI session
- Share them so colleagues don't start from zero

</div>
<div>

**Agent Knowledge Hub** gives you:
- A searchable catalog of skills built for S3DF
- Trust signals to evaluate before installing
- One-command install from inside your session
- Safe sharing of SLAC-internal skills

</div>
</div>

<br>

**Get started:**

```
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json
/plugin install agent-knowledge-hub
```

Or browse the catalog: **agent-knowledge-hub.slac.stanford.edu**

---

<!-- _class: title -->

## Questions?

<br>

**Catalog:** agent-knowledge-hub.slac.stanford.edu

**Install the hub skill:**
`/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json`

**Find us:** SLAC Slack

<br>

*Skills are just Markdown files — the hard part is knowing they exist.*
