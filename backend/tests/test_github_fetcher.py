import pytest
import respx
import httpx

from app.services.github import GitHubFetcher, GitHubFetchError, github_url_parser


FAKE_REPO_RESPONSE = {
    "name": "my-skill",
    "description": "A test skill",
    "stargazers_count": 42,
    "pushed_at": "2024-01-15T10:00:00Z",
    "license": {"spdx_id": "MIT", "name": "MIT License"},
}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_success():
    respx.get("https://api.github.com/repos/slaclab/my-skill").mock(
        return_value=httpx.Response(200, json=FAKE_REPO_RESPONSE)
    )
    respx.get("https://api.github.com/repos/slaclab/my-skill/readme").mock(
        return_value=httpx.Response(200, text="<h1>My Skill</h1>")
    )

    fetcher = GitHubFetcher()
    snap = await fetcher.fetch("https://github.com/slaclab/my-skill")

    assert snap.name == "my-skill"
    assert snap.description == "A test skill"
    assert snap.stars == 42
    assert snap.license == "MIT"
    assert snap.readme_html == "<h1>My Skill</h1>"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_not_found():
    respx.get("https://api.github.com/repos/bad/repo").mock(
        return_value=httpx.Response(404)
    )

    fetcher = GitHubFetcher()
    with pytest.raises(GitHubFetchError, match="couldn't be found"):
        await fetcher.fetch("https://github.com/bad/repo")


@pytest.mark.asyncio
async def test_fetch_invalid_url():
    fetcher = GitHubFetcher()
    with pytest.raises(GitHubFetchError, match="valid public GitHub"):
        await fetcher.fetch("https://gitlab.com/some/repo")


@pytest.mark.asyncio
@respx.mock
async def test_fetch_no_readme():
    respx.get("https://api.github.com/repos/slaclab/no-readme").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO_RESPONSE, "name": "no-readme"})
    )
    respx.get("https://api.github.com/repos/slaclab/no-readme/readme").mock(
        return_value=httpx.Response(404)
    )

    fetcher = GitHubFetcher()
    snap = await fetcher.fetch("https://github.com/slaclab/no-readme")
    assert snap.readme_html is None


def test_url_parser_tree():
    ref = github_url_parser.parse("https://github.com/owner/repo/tree/main/some/path")
    assert ref.owner == "owner"
    assert ref.repo == "repo"
    assert ref.branch == "main"
    assert ref.path == "/some/path"


def test_url_parser_blob_nested():
    ref = github_url_parser.parse(
        "https://github.com/alirezarezvani/claude-skills/blob/main/engineering/SKILL.md"
    )
    assert ref.owner == "alirezarezvani"
    assert ref.repo == "claude-skills"
    assert ref.branch == "main"
    assert ref.path == "/engineering"


def test_url_parser_blob_root():
    ref = github_url_parser.parse(
        "https://github.com/owner/repo/blob/main/SKILL.md"
    )
    assert ref.owner == "owner"
    assert ref.repo == "repo"
    assert ref.branch == "main"
    assert ref.path == "/"


def test_url_parser_root():
    ref = github_url_parser.parse("https://github.com/owner/repo")
    assert ref.owner == "owner"
    assert ref.repo == "repo"
    assert ref.branch is None
    assert ref.path == "/"
