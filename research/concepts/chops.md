> **Concept:** chops — Local macOS Skill/Agent File Manager
> **Source:** GitHub (`Shpigford/chops`) — README, repo metadata
> **Relevance:** Landscape / low relevance — a single-user local GUI for editing skill files
> already on disk, not a registry, marketplace, or install source; no catalog, security scanning,
> or trust model to compare against AKH's own

*Generated 2026-10-16 / Confidence: High (README + repo metadata; single source, no corroboration needed — no security or quantitative claims to verify)*

---

## 1. Overview

`chops` (github.com/Shpigford/chops) is a native macOS desktop application for browsing, editing,
and organizing AI coding-agent skill and agent-definition files that already exist on the local
filesystem. It targets Claude Code, Cursor, Codex, Windsurf, GitHub Copilot, Aider, and Amp — it
discovers each tool's own on-disk skill/agent directory conventions and presents them in one
unified interface.

It is not a registry or marketplace. It does not fetch, install, or vet third-party skill code on
its own; it operates purely on files a user has already placed on disk by some other means (manual
clone, another installer, hand-authored files). It does have one registry-adjacent feature: it can
browse the skills.sh registry and connect to remote servers running OpenClaw or a compatible
layout, but installing or trusting third-party code is not its job.

## 2. How It Works

Built with SwiftUI + SwiftData, described in its own README as "native macOS with zero web views."
Layout is a three-column `NavigationSplitView`: sidebar filters, skill list, and a detail editor
pane. Skills are identified and deduplicated by resolved symlink path rather than by nominal file
path, which avoids double-counting a skill that is symlinked into more than one tool's directory.
The app explicitly disables the macOS app sandbox to get unrestricted filesystem access to
dotfile directories (e.g., `~/.claude/skills/`) — a deliberate trade-off the README states
outright rather than something discovered by inspection.

Key features: a built-in monospaced editor with YAML-frontmatter parsing and Cmd+S save; real-time
file watching via FSEvents so external edits appear instantly; full-text search across skill name,
description, and body; and "Collections" — user-defined groupings that organize skills for
browsing without moving or modifying the underlying source files.

## 3. Key Facts

| Fact | Detail |
|------|--------|
| Repo | github.com/Shpigford/chops |
| License | FSL-1.1-MIT (Functional Source License, converts to MIT after a delay — source-available, not immediately open-source) |
| Language / runtime | Swift / SwiftUI, macOS 15 (Sequoia) or later |
| Stars / forks | ~1.9k stars, ~120 forks (at fetch time) |
| Testing | README states manual validation only; no automated test suite |
| Maturity | Active community project; not a SLAC/AKH-affiliated tool |

## 4. Relevance to AKH

Low relevance, stated plainly rather than forced: chops solves a different problem at a different
layer than AKH. AKH is a server-hosted, multi-tenant catalog with a submission flow, ratings, and
install distribution across a community; chops is a single-user local GUI for organizing skills
that are already installed by some other means. It has no catalog of its own, no security scanning
of third-party code, and no install/trust flow comparable to AKH's — there is nothing in its
design to borrow for AKH's discovery, trust, or install mechanisms.

The one point of contact: chops is evidence of independent, organic demand for a unified,
cross-tool skill-management experience — the same underlying need AKH serves, just at the
catalog/install layer rather than the local file-browsing layer. That is a market-landscape
observation, not an architectural or security lesson.

## 5. Known Gaps / Limitations

Single-platform (macOS only), no automated test suite per its own README, and it disables macOS's
app sandbox by design — a reasonable trade-off for its stated purpose (unrestricted dotfile
access) but one that would be a red flag in a tool with any multi-tenant or networked install
surface. None of this bears on AKH, since AKH does not share chops's threat model or user base.

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — landscape-only, no action (L-6)

## Sources

- https://github.com/Shpigford/chops — fetched 2026-10-16
- https://raw.githubusercontent.com/Shpigford/chops/main/README.md — fetched 2026-10-16
