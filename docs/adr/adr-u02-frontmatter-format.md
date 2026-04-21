# ADR-U02: Frontmatter format for skill metadata extraction

**Status:** Accepted
**Date:** 2026-04-21
**Context:** todo/002-skill-registration-ux.md

## Context

Skills can declare metadata (name, description, platforms, version) inside their markdown files. A standard extraction format is needed.

## Decision

Use YAML frontmatter (Jekyll/Hugo convention) at the top of `skill.md` and `CLAUDE.md` files. Parse with the `python-frontmatter` library.

```yaml
---
name: Coding Orchestrator
description: Orchestrates multi-agent coding workflows
platforms: [claude-code, openai]
version: 1.2.0
---
```

## Rationale

1. YAML frontmatter is the de facto standard in the markdown ecosystem (Jekyll, Hugo, Docusaurus, Obsidian).
2. `python-frontmatter` is a well-maintained library with zero heavy dependencies.
3. Graceful degradation: files without frontmatter are handled by the fallback extraction chain (package.json, pyproject.toml, directory name, repo name).

## Consequences

- Add `python-frontmatter` to `requirements.txt`.
- The `MetadataExtractor` must handle: (a) valid frontmatter, (b) empty frontmatter, (c) no frontmatter delimiter, (d) malformed YAML. All non-(a) cases fall through to the next source in the priority chain.
- No requirement is placed on skill authors to add frontmatter -- it is purely additive UX improvement.
