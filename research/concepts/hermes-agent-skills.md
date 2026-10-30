> **Concept:** Hermes Agent — Skills Subsystem (Search, Scan, Install, Audit)
> **Source:** GitHub (`NousResearch/hermes-agent`) — `hermes_cli/subcommands/skills.py`, `tools/skills_guard.py`, `tools/skills_hub.py`
> **Relevance:** The most complete open-source implementation of skill search + security scanning + install provenance tracking — a direct reference implementation for AKH's trust and discovery pipeline

*Generated 2026-06-08 / Confidence: High (source code + README)*

---

## 1. Overview

Hermes Agent (NousResearch) is a self-improving CLI agent with a built-in `hermes skills` subsystem covering the full skill lifecycle: search across 8+ registries, security scan before install, provenance-tracked installation, and periodic re-audit. Skills use the `SKILL.md` format (same as SkillNet and SkillClaw). Compatible with the **agentskills.io** open standard.

**Repo:** https://github.com/NousResearch/hermes-agent
**Skills dir:** `~/.hermes/skills/`
**Hub state:** `~/.hermes/skills/.hub/` (lock file, quarantine, audit log, taps, index cache)

---

## 2. Search & Browse

### Sources searched

| Source ID | What it is |
|-----------|-----------|
| `official` | Nous Research's curated optional skills shipped with the repo |
| `github` | GitHub repos (DEFAULT_TAPS + user-added taps) |
| `skills-sh` | skills.sh registry |
| `well-known` | Agent skill endpoints at well-known URLs |
| `clawhub` | ClawHub registry |
| `lobehub` | LobeHub skills |
| `browse-sh` | browse.sh |
| `hermes-index` | Centralised cached index (serves all sources from disk, TTL 3600s) |

**DEFAULT_TAPS** (hardcoded GitHub repos always included):
```python
DEFAULT_TAPS = [
    {"repo": "openai/skills",      "path": "skills/.curated/"},
    {"repo": "openai/skills",      "path": "skills/.system/"},
    {"repo": "anthropics/skills",  "path": "skills/"},
    {"repo": "huggingface/skills", "path": "skills/"},
    {"repo": "NVIDIA/skills",      "path": "skills/"},
    {"repo": "garrytan/gstack",    "path": ""},
]
```

### CLI

```bash
hermes skills search <query>
  --source  all | official | skills-sh | well-known | github | clawhub | lobehub | browse-sh
  --limit   <int>       (default 10)
  --json                (output JSON — full identifiers preserved for scripting)

hermes skills browse
  --page    <int>       (default 1)
  --size    <int>       (default 20, max 100)
  --source  <source>

hermes skills inspect <identifier>   # preview without installing
```

### Result deduplication

Browse deduplicates by `identifier` (not name — names collide across sources). On collision: higher trust level wins. Sort order: trust rank desc → non-official first → alphabetical.

### Short-name resolution

If an identifier contains no `/`, `_resolve_short_name` runs `unified_search(name, limit=20)`, filters to exact case-insensitive name matches. If 1 match: resolves automatically. If multiple: shows table and asks user to use full identifier. If none: shows fuzzy suggestions.

---

## 3. Security Scanning (`tools/skills_guard.py`)

Every skill passes through `skills_guard.py` before installation. Regex-based static analysis — no sandboxed execution.

### Trust levels

| Trust | Who | Policy |
|-------|-----|--------|
| `builtin` | Ships with Hermes | Never scanned |
| `trusted` | `openai/skills`, `anthropics/skills`, `huggingface/skills`, `NVIDIA/skills` | Caution allowed, dangerous blocked |
| `community` | Everything else | Any finding → blocked (unless `--force`) |
| `agent-created` | Skills created by the agent itself | Caution requires user confirmation |

Install policy matrix:

```
#               safe    caution  dangerous
builtin:        allow   allow    allow
trusted:        allow   allow    block
community:      allow   block    block
agent-created:  allow   allow    ask
```

### Threat categories

1. **Exfiltration** — curl/wget with secret env vars, reading `~/.ssh`, `~/.aws`, `~/.kube`, `~/.docker`, base64-encoding of env values, DNS exfiltration, `/tmp` staging, markdown URL injection, `os.environ` dumps, `process.env`, `ENV[]`
2. **Prompt injection** — "ignore previous instructions", role hijacking, "hide from user", system prompt override, "pretend you are", "disregard rules", "leak system prompt", HTML comment injection, hidden divs
3. **Destructive operations** — `rm -rf /`, `rm $HOME`, `chmod 777`, `/etc/` overwrite, `mkfs`, `dd` to `/dev/`, `shutil.rmtree` on absolute paths, file truncation
4. **Persistence** — crontab, shell rc files, `authorized_keys`, `ssh-keygen`, systemd, launchd, sudoers, `git config --global`
5. **Network** — reverse shells (`nc`, `socat`, `bash /dev/tcp`, Python socket one-liners), tunneling (`ngrok`, `localtunnel`, `cloudflared`), hardcoded IPs+ports, bind-all-interfaces, known exfil services (`webhook.site`, `requestbin`, `pipedream`, `pastebin`)
6. **Obfuscation** — base64 decode pipe, hex strings, `eval()`/`exec()` with strings, echo piped to interpreter, `Python compile(exec)`, `getattr builtins`, `__import__('os')`, `codecs.decode`, JS `charCodeAt`

### Result types

```python
@dataclass
class Finding:
    pattern_id: str
    severity: str       # "critical" | "high" | "medium" | "low"
    category: str       # "exfiltration" | "injection" | "destructive" | "persistence" | "network" | "obfuscation"
    file: str
    line: int
    match: str
    description: str

@dataclass
class ScanResult:
    skill_name: str
    source: str
    trust_level: str    # "builtin" | "trusted" | "community"
    verdict: str        # "safe" | "caution" | "dangerous"
    findings: List[Finding]
    scanned_at: str
    summary: str
```

### Public API

```python
from tools.skills_guard import scan_skill, should_allow_install, format_scan_report

result = scan_skill(Path("skills/.hub/quarantine/some-skill"), source="community")
allowed, reason = should_allow_install(result)
if not allowed:
    print(format_scan_report(result))
```

---

## 4. Install Flow (`tools/skills_hub.py`)

1. **Fetch** `SkillBundle` from source adapter (files dict: `{relative_path → content}`)
2. **Quarantine** bundle to `skills/.hub/quarantine/<name>/`
3. **Scan** with `scan_skill()` — static analysis against threat patterns
4. **Policy check** via `should_allow_install(result)` — blocked for community skills with any finding
5. **Show** `format_scan_report(result)` if blocked or caution
6. **Confirm** — prompt user (skipped with `--yes`)
7. **Install** from quarantine to `skills/<category>/<name>/`
8. **Lock** — write provenance to `HubLockFile` (source, identifier, hash, timestamp)
9. **Invalidate** search index cache

`--force` overrides step 4 for blocked verdicts (explicit user override).

### GitHub authentication (priority order)
1. `GITHUB_TOKEN` / `GH_TOKEN` env var
2. `gh auth token` (gh CLI)
3. GitHub App JWT + installation token
4. Unauthenticated (60 req/hr rate limit)

---

## 5. Audit & Update

```bash
hermes skills audit [name]      # re-scan installed skills
  --deep                        # AST-level Python analysis (opt-in)

hermes skills check [name]      # check for updates
hermes skills update [name]     # update outdated skills

hermes skills list [--source all|hub|builtin|local] [--enabled-only]
hermes skills uninstall <name>
hermes skills reset <name> [--restore]
```

---

## 6. Source Management (Taps)

```bash
hermes skills tap list
hermes skills tap add <owner/repo>
hermes skills tap remove <name>
```

User taps extend the DEFAULT_TAPS list. Any GitHub repo in SKILL.md format can be tapped.

---

## 7. Skill Data Model

```python
@dataclass
class SkillMeta:
    name: str
    description: str
    source: str           # "official" | "github" | "clawhub" | "claude-marketplace" | "lobehub"
    identifier: str       # source-specific: "openai/skills/skill-creator"
    trust_level: str      # "builtin" | "trusted" | "community"
    repo: Optional[str]
    path: Optional[str]
    tags: List[str]
    extra: Dict[str, Any]

@dataclass
class SkillBundle:
    name: str
    files: Dict[str, Union[str, bytes]]   # relative_path → content
    source: str
    identifier: str
    trust_level: str
    metadata: Dict[str, Any]
```

---

## 8. Hermes + SkillClaw Integration

SkillClaw installs alongside Hermes as a skill *evolution* layer — it does not replace Hermes's own scan/install/audit pipeline:

| Responsibility | Owner |
|---------------|-------|
| Skill search across registries | Hermes (`skills_hub.py`) |
| Security scan before install | Hermes (`skills_guard.py`) |
| Provenance tracking at install | Hermes (`HubLockFile`) |
| LLM traffic interception + skill injection | SkillClaw proxy |
| Post-session skill evolution from trajectory | SkillClaw evolve server |
| Quality validation before shared publish | SkillClaw `validation_worker.py` |

SkillClaw patches `~/.hermes/config.yaml` to route LLM traffic through its proxy. `hermes claw migrate` in the Hermes CLI suggests a first-class migration path from OpenClaw to Hermes.

---

## 9. Comparison: Hermes vs SkillNet search

| Feature | Hermes `skills_hub.py` | SkillNet `searcher.py` |
|---------|----------------------|----------------------|
| Search modes | Unified keyword across all sources | Keyword OR vector |
| Source count | 8+ sources | Single API endpoint |
| Security scan | Full 6-category regex scanner | None |
| Quality scoring | Trust level only | 5-dimension rubric |
| Install flow | fetch → quarantine → scan → confirm → install → lock | download (no scan) |
| Provenance | `HubLockFile` (source, identifier, hash) | Not documented |
| Tap/extension | `hermes skills tap add` | Not documented |

---

## Applied in

- [reports/oct2026-skill-hub-batch-vs-akh.md](../reports/oct2026-skill-hub-batch-vs-akh.md) — `skills_guard.py` categories as the rule specification for AKH's server-side scan (A-2); `HubLockFile` as the precedent for recording the installed commit (A-1 e)

## Sources

- https://github.com/NousResearch/hermes-agent — fetched 2026-06-08
- `hermes_cli/subcommands/skills.py` — fetched 2026-06-08
- `tools/skills_guard.py` — fetched 2026-06-08
- `tools/skills_hub.py` — fetched 2026-06-08
- `hermes_cli/skills_hub.py` — fetched 2026-06-08 (partial)
