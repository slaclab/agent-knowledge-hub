> **Concept:** AgenticSkills.io — Curated Third-Party Directory for Agent Skills and MCP Servers
> **Source:** agenticskills.io (homepage, /about, /skills, /mcp, /submit, and the
> /skills/find-skills detail page); vercel-labs/skills (primary source for the cataloged skill)
> **Relevance:** Registry comparator, analogous in kind to the five-registry survey in
> concepts/mcp-registry-landscape.md but for skills rather than MCP servers — and a second
> catalog, alongside open-agent-hub, that delegates installation entirely to Vercel Labs' `npx
> skills` CLI rather than building its own

*Generated 2026-10-16 / Confidence: Medium-High for platform structure and verbatim site content (fetched via an HTTP reader-mode proxy after direct WebFetch failed twice with a connection error specific to this environment; content cross-validated verbatim against the primary-source SKILL.md on GitHub). Low for the "97M+ SDK Downloads" and "100% Open Source" marketing figures, which could not be independently corroborated.*

---

## 1. Overview

AgenticSkills.io is a hosted, curated directory — not a package registry or install tool — for
discovering AI agent skills (`SKILL.md` packages), MCP servers, and bundled "Workflows" of the
two. As of the 2026-10-16 snapshot (site banner "Index live · v1.7.0"): 193+ skills across 16
categories, 196 MCP servers across 22 categories, 22 Workflows, and install-path tracking for 9
agent platforms. Per its own `/about` page: "AgenticSkills is a curated directory that helps
developers discover and install AI agent skills... We catalog skills across development, DevOps,
data, security, design, and more — giving you a single place to browse, compare, and get started."

No GitHub repository for the AgenticSkills.io platform itself was found; it appears to be a
closed-source hosted site, despite depending entirely on the open-source `npx skills` CLI for its
own install mechanism (§4).

---

## 2. What the find-skills Page Specifically Documents

The URL given for this catalog entry, `/skills/find-skills`, is AgenticSkills.io's detail page for
**Find Skills**, a meta-skill published by Vercel Labs
(`vercel-labs/skills/skills/find-skills/SKILL.md`). The page title is "Find Skills — AI Agent
Skill by Vercel Labs," establishing that detail pages show at minimum a skill name and attributed
author/organisation.

The page body reproduces the skill's `SKILL.md` content verbatim: it teaches an agent when to
reach for skill discovery (phrases like "find a skill for X," "is there a skill that can..."),
documents the underlying `npx skills` CLI (`find`, `add`, `update`), and gives a five-step
workflow for recommending skills to a user, including an explicit quality-verification checklist —
prefer skills with 1K+ installs, be cautious under 100; prefer official sources
(`vercel-labs`, `anthropics`, `microsoft`); check the source repository's GitHub stars, treat
anything under 100 with scepticism.

One link is altered from the GitHub original: the source SKILL.md's "Check the Leaderboard First"
step links to `skills.sh` (Vercel's own leaderboard); the AgenticSkills.io-rendered version points
the same anchor text at the GitHub repository instead. The extracted page closes with what reads
as the site's own editorial disclosure, not part of the original skill text: *"Text is reproduced
unmodified. Links to competing skill directories are shown as plain text or point to the source
repository instead."* This is a concrete, observable curation policy: content is mirrored
verbatim, but outbound links to a competing discovery surface are rerouted to the upstream source.

No ratings, install counts, or AgenticSkills-specific metadata badges were visible appended to the
skill body in this fetch; any such chrome either lives elsewhere on the page (not captured by
text extraction) or does not exist for individual skill pages — see §5.

---

## 3. Browse & Search UX

The `/skills` index page ("AI Agent Skills — The Curated Directory") presents a flat "Complete
Skill Index" of roughly 140 entries, each a title, one-line description, and link — e.g. "Find
Skills — Discover and install agent skills from the ecosystem — the meta-skill for skill
discovery." A `Sort:` control offers "Updated" and "Rank" orderings. Category-filter controls
likely exist (16 categories are claimed) but were not captured in the rendered text extraction, so
their exact mechanics are unconfirmed here.

The `/mcp` page follows the identical pattern for MCP servers: a "Complete MCP Server Index" flat
list plus featured/"Editor's picks" servers, with the addition of a security/trust scorecard not
offered on the skills side (§5).

---

## 4. Install Mechanism

AgenticSkills.io has no installer of its own. Per its homepage "How It Works" section: *"One-command
installation via CLI or drag-and-drop the SKILL.md file into your agent's skills folder"* —
`npx skills add owner/repo@skill-name`. This is the same Vercel Labs `skills` CLI documented in
[concepts/open-agent-hub.md](open-agent-hub.md) — both catalogs in this research batch delegate
the actual install plumbing to the same third-party tool rather than building their own.

---

## 5. Rating / Trust / Curation Model

**No star rating or community review system exists anywhere on the site** — confirmed across the
homepage, `/about`, `/skills`, `/mcp`, and `/submit` pages. The only quantified trust mechanism
found is an automated security/supply-chain audit, and it applies to MCP servers only, not skills:

> "We ran every server in the catalog through the same automated framework on August 7, 2026.
> 106 of 192 servers exposed a source we could check. The remaining 86 (45%) publish no
> repository or hosted endpoint URL, so no automated check can be applied to them at all."

27 servers received a full repository supply-chain audit (releases, lockfile, SBOM, CI,
contributors, licence); 79 received a lighter hosted-endpoint check (TLS-only transport, OAuth
2.1/RFC 9728 metadata discovery). Selected pass rates: TLS-only 100% (79/79); OAuth 2.1 metadata
13% (10/79); SECURITY.md published 64% (16/25); commit in last 90 days 92% (23/25); ≥2 active
contributors 100% (25/25); SBOM 0% (0/25); licence declared 100% (25/25). The site states rates
exclude not-applicable checks rather than counting them as failures, and that deeper checks
(OAuth 2.1/PKCE implementation, input validation, sandboxing) require human review, tracked
separately. **No equivalent audit exists for skills** — skills receive editorial admission control
only.

Submission (`/submit`) requires GitHub repository URL, category, a 200-character description,
tags, and author contact details. Per the page text: *"Every submission is checked for a public
source, a valid format, and security, then triaged weekly against our inclusion criteria. Listing
is selective — not every submission is added."* "Featured placement" (top-of-category, newsletter)
is available on request — a monetisation lever layered on editorial curation.

> ⚠️ **Conflicting sources:** a WebSearch-only summary (no direct fetch) characterised submission
> review as "within 48 hours." The directly fetched `/submit` page states review is "triaged
> weekly" instead. The directly fetched page text is treated as authoritative; the 48-hour figure
> is not used and should be treated as unconfirmed.

---

## 6. Comparison to the Registry Landscape Already in This Corpus

AgenticSkills.io sits closest in spirit to PulseMCP's model in
[concepts/mcp-registry-landscape.md](mcp-registry-landscape.md) — "intentional quality curation...
smaller than raw aggregators by editorial decision" — but at a far smaller absolute scale (196 MCP
servers and 193+ skills, versus PulseMCP's 16,000+ servers). Unlike every registry surveyed there,
AgenticSkills.io is not itself an installable API or ETL source: it is a human-browsable directory
with no documented programmatic search endpoint, and it depends entirely on the `npx skills` CLI
(a separate, independently-governed open-source project) for the actual install step.

| Dimension | AKH | AgenticSkills.io |
|---|---|---|
| Hosted marketplace | Yes | Yes |
| Covers both skills and MCP servers | Skills, with MCP bundling as a documented exception | Both, as separate first-class catalogs, plus "Workflows" bundling both |
| Install mechanism | Built-in (`/agent-knowledge-hub` slash command) | Delegated entirely to `npx skills` (third party) |
| Rating system | 1–5 star community ratings | None |
| Trust signal | SLAC Members Only badges (access gating) | Automated security audit scorecard — MCP servers only, not skills |
| Curation | Open submission, authenticated rating | Selective: public-source/format/security check, weekly triage against published inclusion criteria, paid featured placement |
| Auth | S3DF sign-in (SLAC-gated) | None found (public directory) |

---

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — scorecard checks adopted as dated repository-hygiene facts plus an RFC 9728 probe (A-3); install counts as a trust signal (A-7); directory model and `npx skills` landscape-only (L-1, L-5)

Candidate noted at cataloguing: an amendment or companion report to
[reports/mcp-registry-for-akh.md](../reports/mcp-registry-for-akh.md) comparing AgenticSkills.io's
MCP-server security-audit scorecard (§5) against the five registries already surveyed there — none
of which publish an equivalent automated trust scorecard.

---

## Sources

- https://agenticskills.io/skills/find-skills — fetched 2026-10-16 (direct WebFetch failed twice
  with `connect ECONNREFUSED`; fetched via an HTTP reader-mode proxy; content cross-validated
  verbatim against the GitHub primary source below)
- https://agenticskills.io/ — fetched 2026-10-16 (via reader-mode proxy)
- https://agenticskills.io/about — fetched 2026-10-16 (via reader-mode proxy)
- https://agenticskills.io/skills — fetched 2026-10-16 (via reader-mode proxy)
- https://agenticskills.io/mcp — fetched 2026-10-16 (via reader-mode proxy)
- https://agenticskills.io/submit — fetched 2026-10-16 (via reader-mode proxy)
- https://raw.githubusercontent.com/vercel-labs/skills/main/skills/find-skills/SKILL.md — fetched
  2026-10-16 (primary source, used to validate the proxied page's fidelity)
- https://raw.githubusercontent.com/vercel-labs/skills/main/README.md — fetched 2026-10-16
  (context on the `npx skills` CLI this entire ecosystem depends on)
- WebSearch "agenticskills.io find-skills marketplace" — fetched 2026-10-16 (secondary; the
  48-hour review-time claim from this search is contradicted by the direct fetch above and not
  used)
- WebSearch ""agenticskills.io" MCP servers directory 190" — fetched 2026-10-16 (secondary,
  corroborates the MCP audit figures)
