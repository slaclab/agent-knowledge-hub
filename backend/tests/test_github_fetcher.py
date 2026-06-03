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
    "default_branch": "main",
}

_FAKE_SHA = "a" * 40


def _mock_head_sha(repo_path: str, sha: str = _FAKE_SHA):
    respx.get(f"https://api.github.com/repos/{repo_path}/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": sha}})
    )


def _mock_tags(repo_path: str, tags=None):
    respx.get(f"https://api.github.com/repos/{repo_path}/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=tags or [])
    )


@pytest.mark.asyncio
@respx.mock
async def test_fetch_success():
    respx.get("https://api.github.com/repos/slaclab/my-skill").mock(
        return_value=httpx.Response(200, json=FAKE_REPO_RESPONSE)
    )
    respx.get("https://api.github.com/repos/slaclab/my-skill/readme").mock(
        return_value=httpx.Response(200, text="<h1>My Skill</h1>")
    )
    _mock_head_sha("slaclab/my-skill")
    _mock_tags("slaclab/my-skill")

    fetcher = GitHubFetcher()
    snap = await fetcher.fetch("https://github.com/slaclab/my-skill")

    assert snap.name == "my-skill"
    assert snap.description == "A test skill"
    assert snap.stars == 42
    assert snap.license == "MIT"
    assert snap.readme_html == "<h1>My Skill</h1>"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_populates_head_sha():
    respx.get("https://api.github.com/repos/slaclab/sha-test").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO_RESPONSE, "name": "sha-test"})
    )
    respx.get("https://api.github.com/repos/slaclab/sha-test/readme").mock(
        return_value=httpx.Response(404)
    )
    _mock_head_sha("slaclab/sha-test", sha=_FAKE_SHA)
    _mock_tags("slaclab/sha-test")

    snap = await GitHubFetcher().fetch("https://github.com/slaclab/sha-test")
    assert snap.head_sha == _FAKE_SHA


@pytest.mark.asyncio
@respx.mock
async def test_fetch_head_sha_graceful_on_api_error():
    """If the git/ref endpoint fails, head_sha is None but fetch still succeeds."""
    respx.get("https://api.github.com/repos/slaclab/sha-fail").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO_RESPONSE, "name": "sha-fail"})
    )
    respx.get("https://api.github.com/repos/slaclab/sha-fail/readme").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://api.github.com/repos/slaclab/sha-fail/git/ref/heads/main").mock(
        return_value=httpx.Response(500)
    )

    snap = await GitHubFetcher().fetch("https://github.com/slaclab/sha-fail")
    assert snap.head_sha is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_tag_lookup_finds_matching_tag():
    respx.get("https://api.github.com/repos/slaclab/tagged").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO_RESPONSE, "name": "tagged"})
    )
    respx.get("https://api.github.com/repos/slaclab/tagged/readme").mock(
        return_value=httpx.Response(404)
    )
    _mock_head_sha("slaclab/tagged")
    respx.get("https://api.github.com/repos/slaclab/tagged/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=[
            {"name": "v1.0.0", "commit": {"sha": _FAKE_SHA}},
            {"name": "v0.9.0", "commit": {"sha": "c" * 40}},
        ])
    )

    snap = await GitHubFetcher().fetch("https://github.com/slaclab/tagged")
    assert snap.head_tag == "v1.0.0"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_tag_lookup_no_match_returns_none():
    respx.get("https://api.github.com/repos/slaclab/untagged").mock(
        return_value=httpx.Response(200, json={**FAKE_REPO_RESPONSE, "name": "untagged"})
    )
    respx.get("https://api.github.com/repos/slaclab/untagged/readme").mock(
        return_value=httpx.Response(404)
    )
    _mock_head_sha("slaclab/untagged")
    respx.get("https://api.github.com/repos/slaclab/untagged/tags", params={"per_page": "10"}).mock(
        return_value=httpx.Response(200, json=[
            {"name": "v0.9.0", "commit": {"sha": "c" * 40}},
        ])
    )

    snap = await GitHubFetcher().fetch("https://github.com/slaclab/untagged")
    assert snap.head_tag is None


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
    _mock_head_sha("slaclab/no-readme")
    _mock_tags("slaclab/no-readme")

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
