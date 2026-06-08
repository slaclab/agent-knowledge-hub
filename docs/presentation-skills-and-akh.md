---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 20px;
    padding: 36px 48px;
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
  .card-blue { background: #eff6ff; border: 1px solid #93c5fd; border-radius: 8px; padding: 16px; }
  .card-blue h3 { color: #0077b6; margin-top: 0; }
  .card-blue p { color: #555; font-size: 0.85em; margin: 0; }
  .card-orange { background: #fff7ed; border: 1px solid #fdba74; border-radius: 8px; padding: 16px; }
  .card-orange h3 { color: #0077b6; margin-top: 0; }
  .card-orange p { color: #555; font-size: 0.85em; margin: 0; }
  .card-amber { background: #fef9f0; border: 1px solid #fbbf24; border-radius: 8px; padding: 16px; }
  .card-amber h3 { color: #0077b6; margin-top: 0; }
  .card-amber p { color: #555; font-size: 0.85em; margin: 0; }
  .card-slate { background: #f1f5f9; border: 1px solid #94a3b8; border-radius: 8px; padding: 16px; }
  .card-slate h3 { color: #0077b6; margin-top: 0; }
  .card-slate p { color: #555; font-size: 0.85em; margin: 0; }
  .card-green { background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 16px; }
  .card-green h3 { color: #0077b6; margin-top: 0; }
  .card-green p { color: #555; font-size: 0.85em; margin: 0; }
  .card-red { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 16px; }
  .card-red h3 { color: #0077b6; margin-top: 0; }
  .card-red p { color: #555; font-size: 0.85em; margin: 0; }
---

<!-- _class: title -->

# Agent Skills &
# Agent Knowledge Hub

### What they are, why they matter, and how to use them at SLAC

<br>

**S3DF**
https://agent-knowledge-hub.slac.stanford.edu

---

## You probably already feel this problem

> *"Every time I start a Claude session I have to explain how the project works, which tools to use, and what our naming conventions are."*

> *"I was trying to debug a service and Claude kept suggesting the wrong approach — I had to keep correcting it and explaining our setup before it would do anything useful."*

> *"Every time I ask Claude to make a small change it re-reads the entire codebase and imposes a completely different coding style — it takes forever and undoes the conventions we spent weeks establishing."*

> *"My colleague built something useful for analysing log files — but I only found out by accident at a group meeting."*

<br>

These are not individual problems. They are organisational problems with an organisational solution. **The solution is encoding your knowledge once — so your AI doesn't have to be re-taught every session.**

---

## What is a skill?

A **skill** is a plain Markdown file that tells Claude how to follow a workflow, apply domain knowledge, or enforce a process — consistently, every time it is invoked.

<div class="highlight">
Think of it as a <strong>Standard Operating Procedure</strong> your AI follows every time, without needing to be re-taught.
</div>

<br>

<div class="grid-2">
<div class="card-red">

**❌ Without a skill**

- Re-explain your cluster layout
- Paste the same conventions
- Hope Claude remembers
- Correct the same mistakes again

<br>

*Same prompt. 50 times. 50 people.*

</div>
<div class="card-green">

**✅ With a skill**

- Type `/ad-logbook-summary run 42`
- Same correct result every time
- Share once — everyone benefits
- Claude never needs re-teaching

<br>

*Written once. Used by everyone.*

</div>
</div>

---

## Examples

<div class="grid-3">
<div class="card-blue">
<h3>📋 Beamline logbook</h3>
<p>Reads the shift logbook, generates a structured summary: run list, key parameters, anomalies flagged — ready to drop into an elog.</p>
</div>
<div class="card-blue">
<h3>⚡ LCLS beam tuning</h3>
<p>Steering magnet adjustments, BPM readings, beam position correction, and known failure signatures — the same methodology an experienced operator applies.</p>
</div>
<div class="card-blue">
<h3>🔭 Rubin/LSST transfer</h3>
<p>Monitors nightly image transfer from Chile, verifies file completeness, retries failures, and debugs stalled pipelines for prompt data processing.</p>
</div>
<div class="card-blue">
<h3>🔬 Geant4 starter</h3>
<p>Preferred geometry conventions, standard physics lists, and known-good macro patterns — every simulation starts from a validated baseline.</p>
</div>
<div class="card-blue">
<h3>💾 Data archiving</h3>
<p>S3DF archiving workflow, required metadata fields, and checksum verification — no more hunting the wiki at end-of-run.</p>
</div>
<div class="card-blue">
<h3>📝 Proposal reviewer</h3>
<p>Checks a beam time draft against current template requirements, flags missing sections, and suggests improvements before submission.</p>
</div>
<div class="card-orange">
<h3>🖥️ HPC job submission</h3>
<p>Correct partition selection, memory limits, and MPI flags via the IRI Facility API across S3DF, NERSC, and ALCF.</p>
</div>
<div class="card-orange">
<h3>☸️ Kubernetes deploy</h3>
<p>S3DF cluster layout, approved Helm patterns, resource sizing, and dev → staging → prod promotion steps.</p>
</div>
<div class="card-orange">
<h3>🚨 On-call runbook</h3>
<p>Check the right dashboards, run the right queries, escalate in the right order. No memory required at 3 am.</p>
</div>
</div>
<p style="font-size:0.75em;color:#888;margin-top:8px;">🔵 Science &amp; experiment &nbsp;&nbsp; 🟠 Platform &amp; infrastructure</p>

---

## Skills can invoke themselves automatically

Add a routing table to `CLAUDE.md` — Claude loads the right skill from natural language, no slash command needed:

```markdown
| Intent | Skill |
|---|---|
| Deploy, apply Helm, promote to prod | `k8s-deploy` |
| Debug an issue, "why is X broken" | `troubleshoot` |
| Write code, fix a bug, refactor | `tdd-standards` |
```

*"Why is my pod crashlooping?"* → `/troubleshoot` loads automatically.

The routing lives in the repo — every team member gets the same behaviour without any setup.

---

## 10 lines of Markdown. Real results.

Skills can be as elaborate as `/troubleshoot` — or as simple as this. The entire `grill-me` skill:

```markdown
---
name: grill-me
description: Interview the user relentlessly about a plan until reaching shared
  understanding. Use when user wants to stress-test a plan.
---

Interview me relentlessly about every aspect of this plan until we reach shared
understanding. Walk down each branch of the decision tree, resolving dependencies
one-by-one. For each question, provide your recommended answer.

Ask questions one at a time. If a question can be answered by exploring the
codebase, explore the codebase instead.
```

Invoke `/grill-me` and Claude becomes an adversarial interviewer — working through every assumption in your plan before you write a line of code.

> *"Markdown is the new programming language" — and this is a 10-line program.*

---

## A real skill: /troubleshoot

Enforces a disciplined diagnostic workflow — the agent never jumps straight to a fix.

**Reproduce → map dependencies → hypothesise → instrument → confirm → fix → post-mortem**

<div class="grid-2" style="margin-top:12px;">
<div class="card">
<h3>🔄 General layer</h3>
<p>The high-level troubleshooting flow — reproduce, map dependencies, hypothesise, instrument, confirm, fix, post-mortem. Domain-agnostic methodology that applies to any problem.</p>
<p style="margin-top:8px;">Always available, regardless of project.</p>
</div>
<div class="card">
<h3>📁 Project-local layer</h3>
<p>Project-specific <code>debug-*</code> skills that contain the <em>actual</em> commands, known failure patterns, and component-specific runbooks for your stack.</p>
<p style="margin-top:8px;"><code>debug-authnz/</code> · <code>debug-postgres/</code> · <code>debug-ingress/</code></p>
<p style="margin-top:8px;">Drop one into your repo — <code>/troubleshoot</code> picks it up automatically and applies it over the generic approach.</p>
</div>
</div>

---

## A real skill: /board-review

Convenes parallel expert subagents against a code change or PRD. If any reviewer amends the plan, the full board re-reviews. Repeats until all pass in the same round.

**Reviewers:** architecture · engineering · security · UX · documentation

<div class="grid-2" style="margin-top:12px;">
<div class="card-red">
<h3>⚠️ The cost</h3>
<p>Each round spawns 3–5 Opus subagents in parallel. A thorough PRD review can cost more than an entire normal session.</p>
</div>
<div class="card-green">
<h3>✅ What you get</h3>
<p>Best-practice enforcement with no reviewer fatigue. Expert opinion on your design <strong>before</strong> writing code. Catches what hurried human review misses.</p>
</div>
</div>


---

## Skills improve themselves

The same agent that uses a skill can update it. After a session where you corrected Claude, steered it back on track, or found a better approach — ask it to capture that:

```
"Update the troubleshoot skill to always check network policies before 
 checking pod logs — that's what fixed it today."

"Add our standard dark subtraction snippet to the data analysis skill."

"The deploy skill told you to use the wrong namespace. Fix it."
```

Claude reads the current `SKILL.md`, applies the change, and writes it back. Next session starts with the improvement already baked in.

<div class="highlight" style="margin-top:16px;">
🔄 <strong>Use skill → discover gap → correct Claude → update skill → repeat.</strong> Skills accumulate institutional knowledge over time — without anyone sitting down to write documentation.
</div>

---

## When skills go wrong

<div class="grid-3">
<div class="card-amber">
<h3>🧠 Context pollution</h3>
<p>Every skill's preamble is injected into <em>every</em> context window — even when never used. Invoke a skill and the full body stays for the session. Too many skills and the model degrades before you notice why.</p>
</div>
<div class="card-amber">
<h3>💸 Cost</h3>
<p>Multi-agent skills like <code>/board-review</code> spawn several Opus subagents in parallel. A single review pass can cost more than an entire normal session.</p>
</div>
<div class="card-amber">
<h3>🕰️ Stale instructions</h3>
<p>A skill written six months ago may reference tools or paths that no longer exist — and the model will follow them confidently.</p>
</div>
<div class="card-amber">
<h3>⚡ Conflicting skills</h3>
<p>Two skills governing the same workflow give contradictory instructions. The model may blend them, ignore one, or oscillate unpredictably.</p>
</div>
<div class="card-amber">
<h3>🎯 Over-specificity</h3>
<p>A skill tuned for one team becomes wrong in a slightly different context — silently, with no warning.</p>
</div>
</div>

<div class="highlight" style="margin-top:24px;">
✅ <strong>The fix:</strong> load only what you need, keep skills short, use routing rules to load on demand, and review them regularly.
</div>

---

## Anatomy of a skill

```
~/.claude/skills/        ← global (all projects)
  troubleshoot/
    SKILL.md             ← workflow, methodology, general instructions
    references/          ← domain specifics loaded on demand
      k8s.md             ← Kubernetes-specific commands and failure patterns
      code.md

.claude/skills/          ← project-local (this repo only, takes precedence)
  debug-ingress/
    SKILL.md             ← environment-specific overrides: cluster names, URLs
```

- **General flow lives globally** — the main `SKILL.md` owns the methodology and workflow
- **Specifics live in `references/`** — domain commands, failure patterns, instrument schemas loaded on demand, keeping the main skill lean
- **Project-local overrides global** — drop a same-named skill in `.claude/skills/` to add environment-specific detail (cluster names, internal URLs) without touching the shared version

---

## How skills are loaded

- **Session start** — only the `description` field of each skill is loaded: a compact listing so Claude knows what's available (~1,500 chars per skill)
- **On invocation** — the full `SKILL.md` body enters the conversation as a single message and stays for the session — no truncation at this point
- **References** — supporting files are **not** loaded automatically; SKILL.md must instruct Claude to read them on demand
- **After `/compact`** — skills are re-attached at up to 5,000 tokens each, shared budget of 25,000 tokens across all re-attached skills

Keep `SKILL.md` under ~500 lines and put the most important instructions near the top.

**Tip:** run `/context` at any point to see a breakdown of what's consuming your context window — useful for spotting skills that are adding unexpected bloat.

**Note:** this describes Claude Code's behaviour today. Different agents load skills differently — Codex, Cursor, and others have their own conventions. The ecosystem is moving quickly; specifics may change.

---

## Skills are (almost too) easy to create — and that's the problem

Ask Claude mid-session and a `SKILL.md` appears in seconds:

```
"Turn what you just did into a skill so I can reuse it."
```

<div class="grid-2" style="margin-top:16px;">
<div class="card-green">
<h3>✅ The promise</h3>
<p>The barrier is low enough that knowledge <strong>actually gets captured</strong> — unlike wikis, runbooks, and documentation that never gets written.</p>
<br>
<p>Every researcher, platform team, and engineer can encode their working knowledge in minutes.</p>
</div>
<div class="card-red">
<h3>⚠️ The risk</h3>
<p>That same low barrier means <strong>hundreds of half-finished, overlapping, untested, or abandoned skills</strong> accumulate across the lab.</p>
<br>
<p>Each lives in a private dotfile nobody else knows about. The knowledge exists. Nobody can find it. Nobody knows if it works.</p>
</div>
</div>

<div class="highlight" style="margin-top:16px;">
<strong>Skills only become valuable when shared, reviewed, and maintained as a community.</strong> Agent Knowledge Hub exists to turn individual effort into collective knowledge.
</div>

---

## Why not one big shared GitHub repo?

It seems obvious — one repo, everyone commits skills, done. In practice it breaks quickly:

<div class="grid-3" style="margin-top:12px;">
<div class="card-slate">
<h3>📁 Skills live with their code</h3>
<p>A beamline skill belongs next to the beamline code — <strong>same repo, same version, same PR review, same CI</strong>. A central repo severs that relationship.</p>
</div>
<div class="card-slate">
<h3>🔒 Private skills can't be public</h3>
<p>Skills referencing <strong>internal hostnames or APIs</strong> can't go in a public repo. AKH supports both public and SLAC-internal skills in the same catalog.</p>
</div>
<div class="card-slate">
<h3>👤 Ownership becomes unclear</h3>
<p>Who <strong>maintains</strong> it? Who <strong>reviews PRs</strong>? Who <strong>retires stale skills</strong>? A monorepo needs governance that nobody wants to own.</p>
</div>
<div class="card-slate">
<h3>🔍 Discovery still doesn't exist</h3>
<p>A flat directory of Markdown files is <strong>not searchable, not rated, has no trust signals</strong> — and requires knowing the repo exists in the first place.</p>
</div>
<div class="card-slate">
<h3>🌿 Forking diverges silently</h3>
<p>Groups fork skills for their specific setup. Forks of a central repo drift apart with no visibility; AKH tracks <strong>provenance</strong> and lineage.</p>
</div>
</div>

<div class="highlight" style="margin-top:16px;">
💡 <strong>Agent Knowledge Hub is the index, not the storage.</strong> Skills stay in the repos that own them. The catalog makes them <strong>discoverable, trustworthy, and installable</strong> — without centralising ownership.
</div>

---

## Agent Knowledge Hub

<div class="highlight" style="font-size: 1.2em; text-align: center; margin-bottom: 20px;">
🌐 <strong>https://agent-knowledge-hub.slac.stanford.edu</strong>
</div>

```
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json
/plugin install agent-knowledge-hub
```

<div class="grid-3" style="margin-top:12px;">
<div class="card">
<h3>🔍 Browse & discover</h3>
<p>Full-text search across name, description, README, labels. Sort by newest, highest rated, most stars.</p>
<p style="margin-top:8px;">📦 <strong>Skillsets</strong> — curated collections for a domain or workflow</p>
</div>
<div class="card">
<h3>🛡️ Trust signals</h3>
<p>⭐ Community ratings · 📅 Last commit · 👤 Submitter</p>
<p style="margin-top:8px;">🔗 Provenance — fork lineage, revision history, supersession chain</p>
<p style="margin-top:8px;">🔒 <strong>SLAC Only</strong> badge for internal skills</p>
</div>
<div class="card">
<h3>📤 Publish</h3>
<p>Paste a GitHub URL — metadata extracted automatically. SLAC GitHub Enterprise repos fully supported.</p>
</div>
<div class="card">
<h3>⚡ Install</h3>
<p>From inside your session, no file copying:</p>
<p><code>/agent-knowledge-hub install troubleshoot</code></p>
</div>
<div class="card-amber">
<h3>🛠️ Create <em style="font-size:0.75em;font-weight:normal;">(alpha)</em></h3>
<p>Scaffold a new skill interactively — generates the directory structure, <code>SKILL.md</code>, and <code>plugin.json</code>.</p>
<p style="margin-top:8px;"><code>/agent-knowledge-hub create</code></p>
</div>
<div class="card-amber">
<h3>📨 Submit <em style="font-size:0.75em;font-weight:normal;">(alpha)</em></h3>
<p>Publish to the catalog — paste a GitHub URL or submit a local directory directly.</p>
<p style="margin-top:8px;"><code>/agent-knowledge-hub submit</code></p>
</div>
</div>

---

<!-- _class: title -->

## Questions?

https://agent-knowledge-hub.slac.stanford.edu

*Skills are just Markdown files — the hard part is knowing they exist.*

