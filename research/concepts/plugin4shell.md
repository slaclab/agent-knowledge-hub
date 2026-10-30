> **Concept:** Plugin4Shell — Git SHA-Pinning Bypass in AI Coding Agent Plugin Installers
> **Source:** Air Security (original disclosure), Anthropic GitHub Security Advisory
> GHSA-pq7j-f95f-qfcv / CVE-2026-86063, The Hacker News (news coverage)
> **Relevance:** A general vulnerability class in how agent plugin installers verify a pinned Git
> commit — directly relevant to AKH's own install flow, which hands off to Claude Code's native
> `/plugin install` mechanism for skills hosted in arbitrary SLAC GitHub repos, including private
> "SLAC Members Only" ones

*Generated 2026-10-16 / Confidence: High (vendor security advisory + original researcher disclosure, cross-checked against independent news coverage)*

---

## 1. Overview

Plugin4Shell is the public name Air Security gave to a vulnerability class it found in the plugin
install flow of four AI coding agents: Anthropic Claude Code, OpenAI Codex, GitHub Copilot, and
Google Gemini CLI. Each agent lets a plugin be pinned to a specific, previously-reviewed Git commit
SHA so that an install or auto-update always resolves to exactly that reviewed code. All four
implementations shared the same gap: they ran `git checkout` against the pinned SHA but never
verified, after the checkout completed, that the resulting working tree actually landed on that
commit. An attacker who controls the plugin's upstream repository can exploit how Git resolves
references to make the checkout silently land on different, attacker-controlled code while the
agent continues to report the pin as honored.

This is a vulnerability *class* that recurred independently across four separately-implemented
agents, not a single-product bug. That is confirmed by two independent facts: Anthropic's own
GitHub Security Advisory for Claude Code describes the identical mechanism, and Air Security's
original write-up documents two distinct exploitation methods depending on the agent.

## 2. Attack Mechanism

Git's reference resolution prefers a resolvable ref (branch or tag name) over a bare object ID
when a string could be read as either. The Claude Code advisory states the general case plainly:

> "The plugin install flow in Claude Code and Claude Desktop checked out a marketplace's pinned
> commit SHA using `git checkout` without verifying that the resulting HEAD matched the pinned
> SHA. An attacker controlling a plugin's upstream repository could create a branch named
> identically to the pinned 40-character SHA, causing the checkout to silently resolve to the
> attacker's branch tip instead of the reviewed commit, resulting in attacker-controlled code
> being installed bypassing the pinned hash."

Two exploitation variants, per Air Security's original disclosure:

- **Method 1** (Claude Code, Codex, GitHub Copilot): the attacker creates a branch whose name is
  the exact 40-character commit hash that was reviewed and pinned, and sets it as the repository's
  default branch. `git checkout <sha>` then resolves to the branch, not the object.
- **Method 2** (Gemini CLI): the attacker names the default branch `FETCH_HEAD`, which resolves
  ahead of the actually-fetched commit during checkout.

In both cases the agent's own bookkeeping (what it believes is pinned) stays unchanged — it is the
on-disk code that silently diverges from it. The attack requires no action from the installing
user beyond having previously installed and pinned the plugin; a later auto-update (enabled by
default in some of the affected agents) is enough to trigger the swap with no further click.

One structural constraint limits where this is exploitable: Git hosts that reject SHA-shaped
branch names (GitHub is reported to be one) close off Method 1 on that host. The attack surface is
therefore narrower on github.com than on hosts that allow arbitrary branch names, such as
Bitbucket or a self-hosted Git server — important context for source 5, below.

## 3. Affected Systems & Patch Status

| Agent | Status at Air Security's September 2026 disclosure | Fix |
|---|---|---|
| Anthropic Claude Code | Patched | 2.1.179 (confirmed 2026-06-17, shipped ahead of public disclosure) |
| OpenAI Codex | Patched | 0.146.0 (confirmed 2026-08-12) |
| GitHub Copilot | Unpatched | No fix shipped as of disclosure |
| Google Gemini CLI | Will not be patched | Google deprecated Gemini CLI in favor of Antigravity, which has no marketplace plugin-pinning feature to exploit |

This is a general pattern affecting the plugin-install layer of multiple, independently-built
agents — not a defect specific to one vendor's codebase. The common root cause is a missing
post-checkout integrity check, which is a design gap any agent implementing "pin to a commit SHA"
over Git can reproduce if it omits the same verification step.

## 4. Disclosure Timeline & Vendor Confirmation

- May 2026 — Air Security's research lab discovers the flaw and builds a working proof-of-concept
  against all four agents.
- June 2026 — coordinated disclosure to all four vendors.
- June 17, 2026 — Anthropic confirms the fix, shipped in Claude Code 2.1.179.
- August 4, 2026 — Google confirms it will not patch Gemini CLI; recommends migrating to
  Antigravity.
- August 12, 2026 — OpenAI's Codex 0.146.0 verified fixed.
- September 17–18, 2026 — Air Security publishes the public write-up; The Hacker News and other
  outlets cover it the same week. No CVE had been assigned at that point.
- October 9, 2026 — Anthropic publishes **GHSA-pq7j-f95f-qfcv**, assigning **CVE-2026-86063**
  (High severity, CVSS v4 7.7: `CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N`),
  crediting the same researcher named in the original disclosure (Or Nevo Michrowski, Air
  Security) — confirming the news coverage and the vendor's own record describe the same incident.

**Corroboration note:** this claim clears the "do not rely on a single news article" bar. The
chain here is: (1) Air Security's own original technical write-up (primary source, the discovering
party), independently confirmed by (2) Anthropic's own GitHub Security Advisory assigning a CVE
(primary source, the affected vendor) — not merely a second news outlet repeating the first. No
equivalent vendor advisory or CVE was found for GitHub Copilot or Gemini CLI; that is consistent
with their reported unpatched/no-fix status (an advisory crediting a fix is not expected to exist
for an issue with no fix), not a gap in this research pass.

## 5. Recommended Mitigations

- Update the agent client to a patched version — this is the only mitigation that closes the gap,
  because the vulnerable step happens entirely client-side at install/update time.
- For Gemini CLI, which will not receive a fix: migrate to Antigravity, disable automatic
  background plugin updates where possible, and remove plugins that are not strictly needed.
- For GitHub Copilot, which also has no fix: the same reduce-attack-surface guidance applies
  (disable background updates, minimize installed plugin count) pending a vendor fix.
- A marketplace or catalog that lists plugins cannot itself close this gap. Air Security states
  the reason directly: "the pin is resolved on the client, so no marketplace can enforce the
  guarantee." The fix has to live in the agent that performs the `git checkout`, not in any
  metadata the catalog serves.

## 6. Relevance to AKH

AKH's own README documents that skills are installed through Claude Code's native plugin
mechanism, not a bespoke AKH installer:

```
/plugin marketplace add https://agent-knowledge-hub.slac.stanford.edu/marketplace.json
/plugin install agent-knowledge-hub
```

AKH publishes a `marketplace.json` that Claude Code's own `/plugin install` flow consumes. That
means the specific vulnerable code path described in GHSA-pq7j-f95f-qfcv — `git checkout` of a
pinned commit SHA with no post-checkout verification — sat in the exact client every AKH user was
running, for every skill AKH catalogued, independent of anything AKH itself did or reviewed. This
is a direct, not analogous, exposure: AKH does not merely resemble a system with this class of
bug, it distributes plugins through the literal client (Claude Code) in which this CVE was found
and fixed.

Three points follow directly from the mechanism documented above:

1. **AKH could not have closed this gap on its own.** Per Air Security's own framing, the pin is
   resolved client-side; a catalog can review and correctly pin a commit SHA in `marketplace.json`
   and the install can still be hijacked, because the vulnerability is in how the installing
   client resolves that SHA against the target repository, not in what the catalog records. The
   only fix available to AKH was indirect: depend on its users running Claude Code >= 2.1.179.
   AKH's own marketplace metadata offers no way to verify or enforce that from the catalog side.
2. **AKH's private-repo and "SLAC Members Only" model does not add protection against this
   specific bypass, and does not add exposure beyond what any GitHub-hosted plugin already has.**
   The attack depends on the Git host permitting a branch name shaped like a commit SHA; GitHub is
   reported to block that. Since AKH's skills (public or private-SLAC) are GitHub-hosted, the
   access-control tier (public vs. "SLAC Members Only") is orthogonal to this exposure — both tiers
   sit on the same host-level protection, or lack of it, independent of who is authorized to view
   the repo. A private repo owner is no more or less able to execute Method 1 against a GitHub
   host than a public repo owner; the bypass is about ref-naming on the host, not read access.
3. **The open question this research pass could not resolve** (and was out of scope to resolve, by
   reading only the README rather than AKH's source) is whether AKH's submission or catalog flow
   ever admits a non-GitHub Git host — a self-hosted GitLab instance, Bitbucket, or similar — for
   a skill's source repository. If AKH's model assumes GitHub exclusively (as the README's
   description of "SLAC GitHub repos" suggests), the host-level mitigation that protects
   github.com-hosted plugins against Method 1 would apply uniformly to AKH's catalog. If AKH ever
   accepts a non-GitHub source, that assumption no longer holds and would need separate
   verification against that host's branch-naming rules.

This is the single most safety-relevant item in this research batch: it is not a comparator to
learn design ideas from, it is a named CVE in the exact client AKH's own install flow depends on.
The practical action for AKH is to confirm, not assume, that its documented minimum/supported
Claude Code client version is >= 2.1.179, since that is the only lever AKH's own instructions
(README, submission flow) can actually pull.

## Amendment 2026-10-16 — AKH's own installer reimplements the vulnerable pattern, independent of any CVE patch

Section 6, as originally written, assessed only AKH's `/plugin install agent-knowledge-hub` step — the
one-time install of the AKH catalog browser itself via Claude Code's native marketplace mechanism,
the code path GHSA-pq7j-f95f-qfcv patched in 2.1.179. A closer read of AKH's own per-skill installer
surfaces a second, more direct exposure that a client upgrade cannot fix, because the vulnerable
instruction is AKH's own, not Claude Code's.

`skill/SKILL.md` § Install, step 2 (confirmed by reading the file directly, not inferred):

> Make a new directory for the clone with `d=$(mktemp -d)` [...] and clone into it (`git clone
> --depth 1 <repo_url> "$d/repo"`, or check out the pinned SHA if present).

This is Method 1 from Section 2 above, reimplemented independently in AKH's own install
instructions: clone, then `git checkout <pinned_sha>`, with no instruction anywhere in `skill/SKILL.md`
to verify afterward that the resulting `HEAD` actually equals the pinned SHA (confirmed by `grep -n -i
"checkout\|HEAD\|rev-parse\|verify" skill/SKILL.md` — no match near the install step). A skill author
who controls the upstream repo can create a branch named identically to the 40-character
`pinned_commit_sha` AKH stored at registration (see `todo/017-skill-version-pinning.md`) and set it as
the repository's default branch; the agent's `git checkout <sha>` then resolves to that branch's tip,
not the reviewed object, and installs attacker-controlled files onto the user's machine while AKH's
own `pinned_commit_sha` field — and any "pinned" badge the catalog shows — stays unchanged.

This differs from the Section 6 finding in one important way: **no vendor patch closes this one.**
Section 6's exposure (the marketplace install) was already fixed upstream in Claude Code 2.1.179;
this one is AKH's own bash instruction, interpreted fresh by whatever agent runs `/agent-knowledge-hub
install`, and stays open until `skill/SKILL.md` itself adds a post-checkout verification step —
for example `git -C "$d/repo" rev-parse HEAD`, compared against `pinned_commit_sha` before any file is
read from the clone, aborting the install on a mismatch.

One mitigating factor, carried over from Section 2: this requires a Git host that permits a branch
name shaped like a 40-character hex SHA, which GitHub is reported to reject — and AKH's submission
flow accepts `https://github.com/...` repos only (per `backend/app/schemas/skill.py`'s
`_GITHUB_URL_RE`, confirmed in `todo/045-sec-repo-url-skill-path-allowlist.md`). That single-host
assumption is doing real protective work here; Section 6's open question 3 (whether AKH ever admits a
non-GitHub source) applies with more force to this exposure than to the marketplace one, since this
is the install path every catalog skill goes through, not a one-time setup step.

Filed as [todo/053](../../todo/053-sec-skill-install-sha-checkout-verification.md).

## Applied in

- [todo/053-sec-skill-install-sha-checkout-verification.md](../../todo/053-sec-skill-install-sha-checkout-verification.md) — fixes the gap this amendment documents
- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — Claude Code ≥ 2.1.179 as a declared dependency of the `marketplace.json` route (I-1); further pin gaps in AKH's own installer (A-1). Refines §6: `marketplace_json` emits no `sha`, so the marketplace route had no pin to bypass until #046 adds one

## Sources

- https://www.air.security/blog-posts/plugin4shell — fetched 2026-10-16 (primary: original
  researcher disclosure)
- https://github.com/anthropics/claude-code/security/advisories/GHSA-pq7j-f95f-qfcv — fetched
  2026-10-16 (primary: vendor security advisory, CVE-2026-86063)
- https://thehackernews.com/2026/09/plugin4shell-lets-repository-owners.html?m=1 — fetched
  2026-10-16 (secondary: news coverage, used for the assignment's source URL and initial framing)
- https://www.strix.ai/cve/CVE-2026-86063 — fetched 2026-10-16 (secondary: CVE aggregator, used
  only to cross-check the CVSS score against the GHSA's own figure)
- WebSearch corroboration pass (Help Net Security, SecurityOnline.info, The Next Web, Forkast,
  Cloud Security Alliance research notes) — fetched 2026-10-16 (secondary: used only to confirm
  consensus on timeline and patch status, not cited individually as primary evidence)
