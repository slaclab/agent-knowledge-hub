# Agent Knowledge Hub — TODO

| # | Title | Status |
|---|-------|--------|
| [001](todo/001-private-repos-and-forks.md) | Private/internal GitHub repos, access model, and fork provenance | ✅ Complete |
| [002](todo/002-skill-registration-ux.md) | Improved Skill Registration UX: Directory-Aware Submission | ✅ Complete |
| [003](todo/003-label-ux.md) | Label UX: community tagging, filter, admin rename/merge/delete | ✅ Complete |
| [004](todo/004-multi-source-scanner-abstraction.md) | Multi-source scanner abstraction: local directories, GitLab, and beyond | ✅ Complete |
| [005](todo/005-skill-ratings.md) | Skill ratings: interactive 1–5 star rating with avg display | ✅ Complete |
| [006](todo/006-skillsets.md) | Skillsets: curated skill collections per facility/group with reverse links | 🔄 In Progress |
| [007](todo/007-agent-knowledge-hub-skill.md) | `/agent-knowledge-hub` agent-native discovery, install, and submit skill | ✅ Complete |
| [008](todo/008-auth-header-hardening.md) | Auth header hardening: prevent identity spoofing via ingress/cluster/proxy | ✅ Complete |
| [009](todo/009-duplicate-skill-detection.md) | Duplicate & similar skill detection: near-duplicate warnings in discovery and submit flows | ⬜ Open |
| [010](todo/010-document-to-skill-conversion.md) | Document-to-skill conversion: convert runbooks, SOPs, and guides into skill entries | ⬜ Open |
| [011](todo/011-user-activity-profile.md) | User activity profile: skills submitted, edited, and downloaded by a user | ✅ Complete |
| [012](todo/012-moderation-flags-and-admin-deactivation.md) | Moderation: user flags and admin deactivation/reactivation | ✅ Complete |
| [013](todo/013-revision-history-detail.md) | Rich revision history: field diffs, label changes, upstream links | ✅ Complete |
| [014](todo/014-skill-provenance-tree.md) | Skill provenance tree: fork lineage and supersession graph | ✅ Complete |
| [015](todo/015-catalog-scale-search-pagination.md) | Catalog scale: search quality, keyset pagination, and performance | 🔍 Reviewed |
| [016](todo/016-bearer-jwt-auth.md) | Bearer JWT auth: CLI authentication path for the backend API | ✅ Complete |
| [017](todo/017-skill-version-pinning.md) | Skill version / commit pinning: reproducible installs + update-available badge | ✅ Complete |
| [018](todo/018-skill-file-cache.md) | Skill file cache: store SKILL.md + README in DB; tabbed detail view + diff | ✅ Complete |
| [019](todo/019-plugin-json-scan-pipeline.md) | plugin.json-first scan pipeline: rich component metadata + structural auto-labels | ✅ Complete |
| [020](todo/020-installer-skill-extension.md) | Installer skill extension: directory skills, multi-platform, richer scaffold | ✅ Complete |
| [021](todo/021-marketplace-monorepo-publish.md) | Marketplace monorepo publish: `/agent-knowledge-hub create` → PR to slac-agent-plugin-marketplace | ⬜ Open |
| [022](todo/022-installer-git-clone.md) | Installer: switch from GitHub Contents API to git clone for plugin installation | ✅ Complete |
| [023](todo/023-mcp-server-registry.md) | MCP server registry: rich metadata, autodiscovery, and GUI registration flow | 🔍 Reviewed |
| [024](todo/024-agents-md-scanner.md) | AGENTS.md scanner support: recognise Codex/OpenCode instruction files | ✅ Complete |
| [025](todo/025-platform-filter.md) | Platform filter: compatible_platforms as a searchable, filterable catalog dimension | 🔍 Reviewed |
| [026](todo/026-package-embedded-skills.md) | Package-embedded skill discovery: `.agents/skills/` convention in Python/npm packages | ⬜ Open |
| [027](todo/027-mcp-registry-integration.md) | MCP Registry integration: Pass 0 autodiscovery from modelcontextprotocol.io/registry | ⬜ Open |
| [028](todo/028-skill-file-manifest.md) | Skill file manifest: browsable file listing + inline viewer for skill/plugin repos | ✅ Complete |
| [029](todo/029-skillset-cross-ownership-add.md) | Skillset cross-ownership: request flow for adding skills to another user's skillset | ⬜ Open |
| [030](todo/030-sec-platform-ownership-check.md) | **SEC HIGH** — Missing ownership check on platform add/remove endpoints | ✅ Complete |
| [031](todo/031-sec-github-preview-auth.md) | **SEC HIGH** — Unauthenticated /api/github-preview exposes server's GitHub credentials | ✅ Complete |
| [032](todo/032-sec-internal-secret-in-logs.md) | **SEC HIGH** — Internal API secret logged in plaintext on every /api/me call | ✅ Complete |
| [033](todo/033-sec-kubernetes-security-context.md) | **SEC HIGH** — Containers run as root; add Kubernetes securityContext + USER directive | ⬜ Open |
| [034](todo/034-sec-image-digest-pinning.md) | **SEC HIGH** — Pin production images to digest, not mutable tags | ⬜ Open |
| [035](todo/035-sec-security-headers.md) | **SEC HIGH** — Add HTTP security headers to Next.js (CSP, HSTS, X-Frame-Options) | ✅ Complete |
| [036](todo/036-sec-backend-lockfile.md) | **SEC HIGH** — Add Python lockfile for reproducible backend builds | ⬜ Open |
| [037](todo/037-sec-cors-restrict-origins.md) | **SEC MED** — Restrict CORS origins (allow_origins=["*"] + credentials) | ✅ Complete |
| [038](todo/038-sec-internal-secret-min-length.md) | **SEC MED** — Enforce minimum length on internal_api_secret | ✅ Complete |
| [039](todo/039-sec-rate-limit-skill-creation.md) | **SEC MED** — Rate limit skill creation endpoint (POST /api/skills) | ✅ Complete |
| [040](todo/040-sec-repo-url-validation.md) | **SEC MED** — Validate repo_url format in SkillCreate schema | ✅ Complete |
| [041](todo/041-sec-dompurify-css-injection.md) | **SEC MED** — Restrict DOMPurify config to prevent CSS injection in README renderer | ✅ Complete |
| [042](todo/042-sec-frontend-network-policy.md) | **SEC MED** — Add NetworkPolicy for frontend pods + namespace default-deny | ⬜ Open |
| [043](todo/043-sec-tls-ingress.md) | **SEC MED** — Confirm TLS termination on ingress (HSTS / force SSL redirect) | ✅ Complete |
| [044](todo/044-sec-low-findings.md) | **SEC LOW** — Low-severity hardening batch (L1–L7, I2): health, log level, header validation, lockfile | ✅ Complete |
| [045](todo/045-sec-repo-url-skill-path-allowlist.md) | **SEC HIGH** — Allow-list `repo_url` and `skill_path` characters at create time | 📋 Preparing |
| [046](todo/046-marketplace-git-subdir-sources.md) | marketplace.json plugin sources: `git-subdir` with the skill's path and pinned commit | ⬜ Open |
| [047](todo/047-marketplace-route-reachable.md) | marketplace.json route that Claude Code can reach | ⬜ Open |
| [048](todo/048-install-from-files-route.md) | Install internal skills through the files route, confined to the skill folder | ⬜ Open |
| [049](todo/049-sec-local-file-name-validation.md) | **SEC LOW** — Refuse absolute and `..` file names in local skill submissions | ⬜ Open |
| [050](todo/050-client-token-helper.md) | Client token helper: S3DF token from the real home, kept out of process arguments, sent only to the catalog | 🔍 Reviewed |
| [051](todo/051-client-confirms-mcp-servers-and-agents.md) | Client leaves MCP servers to the user and refuses agents it cannot vet | 🔍 Reviewed |
