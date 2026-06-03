"""Tests for #024 — AGENTS.md recognised as a skill instruction file."""
import base64

import httpx
import pytest
import respx

from app.services.github import MetadataExtractor, GitHubScanner
from app.schemas.skill import SkillCreate
from app.services.skill import skill_repository


metadata_extractor = MetadataExtractor()

AGENTS_MD_WITH_FRONTMATTER = """\
---
name: my-codex-skill
description: A skill for Codex users.
keywords:
  - codex
  - automation
version: 2.1.0
---

# My Codex Skill

Instructions for Codex.
"""

AGENTS_MD_NO_FRONTMATTER = "# My Codex Skill\n\nInstructions for Codex.\n"

AGENTS_MD_WITH_PLATFORMS = """\
---
name: explicit-platform-skill
platforms:
  - codex
  - other-tool
---
"""


# ---------------------------------------------------------------------------
# MetadataExtractor — extraction from AGENTS.md frontmatter
# ---------------------------------------------------------------------------

def test_extract_name_from_agents_md():
    files = {"AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    repo = {"name": "fallback-repo"}
    ref = type("Ref", (), {"path": ""})()
    assert metadata_extractor._extract_name(files, repo, ref) == "my-codex-skill"


def test_extract_description_from_agents_md():
    files = {"AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    repo = {"description": "fallback"}
    assert metadata_extractor._extract_description(files, repo) == "A skill for Codex users."


def test_extract_keywords_from_agents_md():
    files = {"AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    assert metadata_extractor._extract_keywords(files, {}) == ["codex", "automation"]


def test_extract_version_from_agents_md():
    files = {"AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    assert metadata_extractor._extract_version(files) == "2.1.0"


def test_agents_md_explicit_platforms_field():
    """Explicit platforms: in AGENTS.md frontmatter is respected."""
    files = {"AGENTS.md": AGENTS_MD_WITH_PLATFORMS}
    platforms = metadata_extractor._extract_platforms(files)
    assert platforms == ["codex", "other-tool"]


def test_agents_md_heuristic_infers_codex_only():
    """AGENTS.md presence with no explicit platforms → ["codex"] only (not opencode)."""
    files = {"AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    platforms = metadata_extractor._extract_platforms(files)
    assert "codex" in platforms
    assert "opencode" not in platforms


def test_agents_md_heuristic_does_not_fire_when_plugin_json_has_platforms():
    """plugin.json platforms takes highest priority over AGENTS.md heuristic."""
    files = {"AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    plugin = {"platforms": ["custom-platform"]}
    platforms = metadata_extractor._extract_platforms(files, plugin)
    assert platforms == ["custom-platform"]


def test_agents_md_and_claude_md_both_present_heuristic():
    """Both CLAUDE.md and AGENTS.md present → ["claude-code", "codex"]."""
    claude_md = "---\nname: my-skill\n---\n"
    files = {"CLAUDE.md": claude_md, "AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    platforms = metadata_extractor._extract_platforms(files)
    assert "claude-code" in platforms
    assert "codex" in platforms


# ---------------------------------------------------------------------------
# Priority order — CLAUDE.md wins over AGENTS.md
# ---------------------------------------------------------------------------

CLAUDE_MD = "---\nname: claude-name\ndescription: Claude desc.\nkeywords: [claude]\nversion: 1.0.0\n---\n"

def test_claude_md_name_wins_over_agents_md():
    files = {"CLAUDE.md": CLAUDE_MD, "AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    repo = {"name": "repo"}
    ref = type("Ref", (), {"path": ""})()
    assert metadata_extractor._extract_name(files, repo, ref) == "claude-name"


def test_claude_md_description_wins_over_agents_md():
    files = {"CLAUDE.md": CLAUDE_MD, "AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    repo = {}
    assert metadata_extractor._extract_description(files, repo) == "Claude desc."


def test_keywords_merged_from_both_claude_md_and_agents_md():
    """Keywords are additive — both CLAUDE.md and AGENTS.md keywords are collected."""
    files = {"CLAUDE.md": CLAUDE_MD, "AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    kws = metadata_extractor._extract_keywords(files, {})
    assert "claude" in kws
    assert "codex" in kws
    assert kws.index("claude") < kws.index("codex")  # CLAUDE.md first


def test_claude_md_version_wins_over_agents_md():
    files = {"CLAUDE.md": CLAUDE_MD, "AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    assert metadata_extractor._extract_version(files) == "1.0.0"


SKILL_MD = "---\nname: my-real-skill\ndescription: Skill desc.\n---\n"

def test_skill_md_wins_over_agents_md():
    files = {"SKILL.md": SKILL_MD, "AGENTS.md": AGENTS_MD_WITH_FRONTMATTER}
    repo = {}
    ref = type("Ref", (), {"path": ""})()
    assert metadata_extractor._extract_name(files, repo, ref) == "my-real-skill"


# ---------------------------------------------------------------------------
# Edge cases — AGENTS.md with no frontmatter
# ---------------------------------------------------------------------------

def test_agents_md_no_frontmatter_name_falls_back():
    """No frontmatter in AGENTS.md → fallback to plugin.json/repo name."""
    files = {"AGENTS.md": AGENTS_MD_NO_FRONTMATTER}
    repo = {"name": "repo-fallback"}
    ref = type("Ref", (), {"path": ""})()
    name = metadata_extractor._extract_name(files, repo, ref)
    assert name == "repo-fallback"


def test_agents_md_no_frontmatter_platforms_heuristic_still_fires():
    """Platform heuristic fires based on file PRESENCE, not frontmatter content."""
    files = {"AGENTS.md": AGENTS_MD_NO_FRONTMATTER}
    platforms = metadata_extractor._extract_platforms(files)
    assert "codex" in platforms


def test_agents_md_empty_file_no_crash():
    """Empty AGENTS.md does not crash extraction."""
    files = {"AGENTS.md": ""}
    platforms = metadata_extractor._extract_platforms(files)
    assert "codex" in platforms
    name = metadata_extractor._extract_name(files, {"name": "repo"}, type("Ref", (), {"path": ""})())
    assert name is not None  # falls back


# ---------------------------------------------------------------------------
# GitHubScanner.discover() — AGENTS.md as skill dir marker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_discover_agents_md_only_dir():
    """A directory containing only AGENTS.md is included in discovery results."""
    from app.services.github import GitHubScanner
    from app.services.scanner import GitHubRef

    scanner = GitHubScanner()
    ref = GitHubRef(owner="ex", repo="repo2", branch="main", path="")

    tree_items = [
        {"type": "blob", "path": "tools/AGENTS.md"},
    ]
    respx.get("https://api.github.com/repos/ex/repo2/git/trees/main").mock(
        return_value=httpx.Response(200, json={"tree": tree_items, "truncated": False})
    )
    # discover() runs scan() on each found dir — mock repo + contents for tools/
    respx.get("https://api.github.com/repos/ex/repo2").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO, "name": "repo2"})
    )
    respx.get("https://api.github.com/repos/ex/repo2/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo2/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "d" * 40}})
    )
    respx.get("https://api.github.com/repos/ex/repo2/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/ex/repo2/contents/tools").mock(
        return_value=httpx.Response(200, json=[
            {"name": "AGENTS.md", "type": "file", "path": "tools/AGENTS.md",
             "download_url": "https://raw.githubusercontent.com/ex/repo2/main/tools/AGENTS.md"},
        ])
    )
    respx.get("https://api.github.com/repos/ex/repo2/contents/tools/AGENTS.md").mock(
        return_value=httpx.Response(200, json={"type": "file", "content": _b64(AGENTS_MD_WITH_FRONTMATTER)})
    )
    respx.get("https://api.github.com/repos/ex/repo2/contents/tools/.claude-plugin/plugin.json").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo2/contents/tools/.claude-plugin/plugin.json?ref=main").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo2/contents/tools/README.md?ref=main").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo2/contents/README.md?ref=main").mock(
        return_value=httpx.Response(404)
    )

    valid, _truncated, _capped = await scanner.discover(ref)
    assert len(valid) == 1
    assert valid[0].ref.path == "/tools"


@pytest.mark.asyncio
@respx.mock
async def test_discover_agents_md_and_claude_md_same_dir_no_duplicates():
    """Dir with both AGENTS.md and CLAUDE.md appears once, not twice."""
    from app.services.github import GitHubScanner
    from app.services.scanner import GitHubRef

    scanner = GitHubScanner()
    ref = GitHubRef(owner="ex", repo="repo3", branch="main", path="")

    tree_items = [
        {"type": "blob", "path": "tools/CLAUDE.md"},
        {"type": "blob", "path": "tools/AGENTS.md"},
    ]
    respx.get("https://api.github.com/repos/ex/repo3/git/trees/main").mock(
        return_value=httpx.Response(200, json={"tree": tree_items, "truncated": False})
    )
    respx.get("https://api.github.com/repos/ex/repo3").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO, "name": "repo3"})
    )
    respx.get("https://api.github.com/repos/ex/repo3/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo3/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "e" * 40}})
    )
    respx.get("https://api.github.com/repos/ex/repo3/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/tools").mock(
        return_value=httpx.Response(200, json=[
            {"name": "CLAUDE.md", "type": "file", "path": "tools/CLAUDE.md",
             "download_url": "https://raw.githubusercontent.com/ex/repo3/main/tools/CLAUDE.md"},
            {"name": "AGENTS.md", "type": "file", "path": "tools/AGENTS.md",
             "download_url": "https://raw.githubusercontent.com/ex/repo3/main/tools/AGENTS.md"},
        ])
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/tools/CLAUDE.md").mock(
        return_value=httpx.Response(200, json={"type": "file", "content": _b64("---\nname: my-claude-skill\n---\n")})
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/tools/AGENTS.md").mock(
        return_value=httpx.Response(200, json={"type": "file", "content": _b64(AGENTS_MD_WITH_FRONTMATTER)})
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/tools/.claude-plugin/plugin.json").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/tools/.claude-plugin/plugin.json?ref=main").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/tools/README.md?ref=main").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/repo3/contents/README.md?ref=main").mock(
        return_value=httpx.Response(404)
    )

    valid, _truncated, _capped = await scanner.discover(ref)
    tools_results = [r for r in valid if r.ref.path == "/tools"]
    assert len(tools_results) == 1


# ---------------------------------------------------------------------------
# skill.py create() — skill_md_filename from AGENTS.md
# ---------------------------------------------------------------------------

def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


FAKE_REPO = {
    "name": "codex-skill",
    "description": "A Codex skill",
    "stargazers_count": 0,
    "pushed_at": "2024-01-01T00:00:00Z",
    "default_branch": "main",
    "visibility": "public",
    "private": False,
    "fork": False,
}


def _mock_agents_md_repo() -> None:
    """Mock a repo that has only AGENTS.md (no SKILL.md or CLAUDE.md)."""
    respx.get("https://api.github.com/repos/ex/codex-skill").mock(
        return_value=httpx.Response(200, json=FAKE_REPO)
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "b" * 40}})
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/contents/").mock(
        return_value=httpx.Response(200, json=[{
            "name": "AGENTS.md",
            "type": "file",
            "path": "AGENTS.md",
            "download_url": "https://raw.githubusercontent.com/ex/codex-skill/main/AGENTS.md",
        }])
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/contents/AGENTS.md").mock(
        return_value=httpx.Response(200, json={"type": "file", "content": _b64(AGENTS_MD_WITH_FRONTMATTER)})
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/contents/.claude-plugin/plugin.json").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/codex-skill/contents/.claude-plugin/plugin.json?ref=main").mock(
        return_value=httpx.Response(404)
    )


@pytest.mark.asyncio
@respx.mock
async def test_create_github_picks_agents_md_as_skill_md_filename():
    """create() sets skill_md_filename='AGENTS.md' when only AGENTS.md is present."""
    _mock_agents_md_repo()
    data = SkillCreate(repo_url="https://github.com/ex/codex-skill", name="codex-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    assert skill.skill_md_filename == "AGENTS.md"
    assert skill.skill_md_raw == AGENTS_MD_WITH_FRONTMATTER


@pytest.mark.asyncio
@respx.mock
async def test_create_github_prefers_claude_md_over_agents_md():
    """create() picks CLAUDE.md over AGENTS.md when both present."""
    claude_content = "---\nname: claude-skill\n---\n"
    respx.get("https://api.github.com/repos/ex/both").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO, "name": "both"})
    )
    respx.get("https://api.github.com/repos/ex/both/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/both/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "c" * 40}})
    )
    respx.get("https://api.github.com/repos/ex/both/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://api.github.com/repos/ex/both/contents/").mock(
        return_value=httpx.Response(200, json=[
            {"name": "CLAUDE.md", "type": "file", "path": "CLAUDE.md",
             "download_url": "https://raw.githubusercontent.com/ex/both/main/CLAUDE.md"},
            {"name": "AGENTS.md", "type": "file", "path": "AGENTS.md",
             "download_url": "https://raw.githubusercontent.com/ex/both/main/AGENTS.md"},
        ])
    )
    respx.get("https://api.github.com/repos/ex/both/contents/CLAUDE.md").mock(
        return_value=httpx.Response(200, json={"type": "file", "content": _b64(claude_content)})
    )
    respx.get("https://api.github.com/repos/ex/both/contents/AGENTS.md").mock(
        return_value=httpx.Response(200, json={"type": "file", "content": _b64(AGENTS_MD_WITH_FRONTMATTER)})
    )
    respx.get("https://api.github.com/repos/ex/both/contents/.claude-plugin/plugin.json").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/ex/both/contents/.claude-plugin/plugin.json?ref=main").mock(
        return_value=httpx.Response(404)
    )

    data = SkillCreate(repo_url="https://github.com/ex/both", name="both-skill")
    skill = await skill_repository.create(data, submitter_id="alice")

    assert skill.skill_md_filename == "CLAUDE.md"
