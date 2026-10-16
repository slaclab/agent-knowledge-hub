"""Static checks on the /agent-knowledge-hub client's install rules (#051).

The client is prose in skill/SKILL.md that the model follows. The rules that decide whether an
agent file is written are fixed shell commands in that file, so these tests extract each command
from SKILL.md and run it over agent files built here, under every awk on the machine. The rest
of the file checks that SKILL.md carries the wording #051 › Server block fixes, and that it gives
the model no instruction to add or remove an MCP server on its own.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

SKILL_MD = Path(__file__).resolve().parents[2] / "skill" / "SKILL.md"

ALLOWED_KEYS = ("name", "description", "tools", "disallowedTools", "model", "color")


def skill_text() -> str:
    return SKILL_MD.read_text()


def fenced_blocks(text: str) -> list[str]:
    return re.findall(r"^```[^\n]*\n(.*?)^```", text, flags=re.S | re.M)


def command(marker: str) -> str:
    blocks = [b for b in fenced_blocks(skill_text()) if f"# {marker}" in b]
    assert len(blocks) == 1, f"SKILL.md must hold exactly one block marked '# {marker}'"
    return blocks[0]


def _awks() -> list[tuple[str, str]]:
    found = []
    for name in ("gawk", "mawk", "busybox"):
        path = shutil.which(name)
        if path and name != "busybox":
            found.append((name, path))
    if not found and shutil.which("awk"):
        found.append(("awk", shutil.which("awk")))
    return found


AWKS = _awks()
each_awk = pytest.mark.parametrize("awk", [p for _, p in AWKS], ids=[n for n, _ in AWKS])


def run_command(cmd: str, awk: str, tmp_path: Path, **substitutions: str) -> subprocess.CompletedProcess:
    """Run a SKILL.md command through sh, with `awk` resolving to the given implementation."""
    bindir = tmp_path / "awkbin"
    bindir.mkdir(exist_ok=True)
    link = bindir / "awk"
    if not link.exists():
        link.symlink_to(awk)
    for key, value in substitutions.items():
        cmd = cmd.replace(f"<{key}>", value)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": substitutions.get("home", str(tmp_path))}
    return subprocess.run(["/bin/sh", "-c", cmd], env=env, capture_output=True, timeout=20)


# ---------------------------------------------------------------------------
# Agent files
# ---------------------------------------------------------------------------

LONG_DESCRIPTION = "description: |\n" + "".join(f"  line {i}\n" for i in range(2500))

AGENTS: dict[str, bytes] = {
    "agent-plain": b"---\nname: agent-plain\ndescription: Plain agent.\n---\nBody.\n",
    "agent-tools": b"---\nname: agent-tools\ndescription: x\ntools: Read, Grep\nmodel: sonnet\ncolor: blue\n"
                   b"disallowedTools:\n  - Bash\n---\nBody.\n",
    "agent-quoted": b"---\nname: 'agent-quoted'\ndescription: \"x\"\n---\n",
    "agent-block-desc": b"---\nname: agent-block-desc\ndescription: |\n  hooks: inside the text\n  more\n---\n",
    "agent-hooks": b"---\nname: agent-hooks\ndescription: x\nhooks:\n  PreToolUse:\n    - matcher: Bash\n---\n",
    "agent-servers": b"---\nname: agent-servers\ndescription: x\nmcpServers:\n  s: {}\npermissionMode: bypassPermissions\n---\n",
    "agent-memory": b"---\nname: agent-memory\ndescription: x\nmemory: user\n---\n",
    "agent-nul": b"---\nname: agent-nul\ndescription: x\nhooks:\n  PreToolUse: []\n---\nBody \x00 with a NUL.\n",
    "agent-indented": b"---\n  name: agent-indented\n  description: x\n  hooks: {}\n---\n",
    "agent-long": ("---\nname: agent-long\n" + LONG_DESCRIPTION + "hooks: {}\n---\n").encode(),
    "agent-flow": b"---\n{name: agent-flow, hooks: {}}\n---\n",
    "agent-quoted-key": b"---\nname: agent-quoted-key\n\"hooks\": {}\n---\n",
    "agent-merge": b"---\nname: agent-merge\n<<: {hooks: {}}\n---\n",
    "agent-explicit": b"---\nname: agent-explicit\n? hooks\n: {}\n---\n",
    "agent-colon": b"---\nname:hooks: {}\ndescription: x\n---\n",
    "agent-bom": b"\xef\xbb\xbf---\nname: agent-bom\nhooks: {}\n---\n",
    "agent-crlf": b"---\r\nname: agent-crlf\r\nhooks: {}\r\n---\r\n",
    "agent-unclosed": b"---\nname: agent-unclosed\ndescription: x\n",
    "agent-trailing-space": b"---\nname: agent-trailing-space\n--- \nhooks: {}\n---\n",
    "agent-comment": b"---\nname: agent-comment\n# a comment\n---\n",
    "agent-escaped": b"---\nname: \"\\x45xplore\"\ndescription: x\n---\n",
    "agent-nextline": b"---\nname:\n  Explore\ndescription: x\n---\n",
    "agent-folded": b"---\nname: >-\n  Explore\ndescription: x\n---\n",
    "agent-tag": b"---\nname: !!str Explore\n---\n",
    "agent-anchor": b"---\nname: &a Explore\n---\n",
    "agent-hash": b"---\nname: Explore # c\n---\n",
    "agent-twice": b"---\nname: agent-twice\nname: Explore\n---\n",
    "agent-noname": b"---\ndescription: x\n---\n",
    "agent-kelvin": "---\nname: wor\u212aer\n---\n".encode(),
    "agent-explore": b"---\nname: explore\ndescription: x\n---\n",
    "agent-samename": b"---\nname: my-reviewer\ndescription: x\n---\n",
}

KEYS_ACCEPTED = {"agent-plain", "agent-tools", "agent-quoted", "agent-block-desc", "agent-escaped", "agent-nextline",
                 "agent-folded", "agent-tag", "agent-anchor", "agent-hash", "agent-twice", "agent-noname",
                 "agent-kelvin", "agent-explore", "agent-samename"}
KEYS_NAMED = {"agent-hooks": ["hooks:"], "agent-servers": ["mcpServers:", "permissionMode: bypassPermissions"],
              "agent-memory": ["memory: user"], "agent-nul": ["hooks:"], "agent-long": ["hooks: {}"],
              "agent-quoted-key": None, "agent-merge": None, "agent-explicit": None, "agent-colon": None,
              "agent-flow": None, "agent-indented": None, "agent-bom": None, "agent-crlf": None,
              "agent-unclosed": None, "agent-trailing-space": None, "agent-comment": None}
NAME_OK = {"agent-plain": "agent-plain", "agent-tools": "agent-tools", "agent-quoted": "agent-quoted",
           "agent-explore": "explore", "agent-samename": "my-reviewer", "agent-hooks": "agent-hooks"}
NAME_REFUSED = ["agent-escaped", "agent-nextline", "agent-folded", "agent-tag", "agent-anchor", "agent-hash",
                "agent-twice", "agent-noname", "agent-kelvin", "agent-colon", "agent-unclosed", "agent-bom"]

KEY_LINE = re.compile(rb"^[A-Za-z0-9_-]+:( |$)")


@pytest.fixture
def agents(tmp_path) -> Path:
    directory = tmp_path / "agents"
    directory.mkdir()
    for name, content in AGENTS.items():
        (directory / f"{name}.md").write_bytes(content)
    return directory


def key_output(awk, tmp_path, agents, name) -> list[bytes]:
    result = run_command(command("akh-agent-keys"), awk, tmp_path, file=str(agents / f"{name}.md"))
    assert result.returncode == 0, result.stderr
    return [l for l in result.stdout.split(b"\n") if l]


@each_awk
class TestAgentKeyCommand:  # FR-2
    @pytest.mark.parametrize("name", sorted(KEYS_ACCEPTED))
    def test_allowed_keys_print_nothing(self, awk, tmp_path, agents, name):
        assert key_output(awk, tmp_path, agents, name) == []

    @pytest.mark.parametrize("name", sorted(KEYS_NAMED))
    def test_other_layouts_print_a_line(self, awk, tmp_path, agents, name):
        lines = key_output(awk, tmp_path, agents, name)
        assert lines, f"{name} would be written although it declares a key outside the set"
        expected = KEYS_NAMED[name]
        if expected is not None:
            assert [l.decode() for l in lines] == expected
            assert all(KEY_LINE.match(l) for l in lines), "these lines must name keys"
        else:
            assert not all(KEY_LINE.match(l) for l in lines), f"{name} must read as frontmatter that cannot be parsed"


@each_awk
class TestAgentNameCommand:  # FR-2 name rule
    @pytest.mark.parametrize("name", sorted(NAME_OK))
    def test_plain_name_is_printed(self, awk, tmp_path, agents, name):
        result = run_command(command("akh-agent-name"), awk, tmp_path, file=str(agents / f"{name}.md"))
        assert result.returncode == 0
        assert result.stdout == NAME_OK[name].encode() + b"\n"

    @pytest.mark.parametrize("name", NAME_REFUSED)
    def test_other_name_forms_are_refused(self, awk, tmp_path, agents, name):
        result = run_command(command("akh-agent-name"), awk, tmp_path, file=str(agents / f"{name}.md"))
        assert result.returncode != 0
        assert result.stdout == b""


@each_awk
def test_user_agent_names_are_listed_recursively(awk, tmp_path):  # FR-2 name clash
    home = tmp_path / "home"
    nested = home / ".claude" / "agents" / "mine"
    nested.mkdir(parents=True)
    (nested / "reviewer.md").write_bytes(b"---\nname: my-reviewer\n---\n")
    (home / ".claude" / "agents" / "plain.md").write_bytes(b"---\nname: \"Quoted Name\"\n---\n")
    (home / ".claude" / "agents" / "notes.txt").write_bytes(b"---\nname: ignored\n---\n")
    result = run_command(command("akh-user-agent-names"), awk, tmp_path, home=str(home))
    assert result.returncode == 0
    lines = sorted(result.stdout.decode().splitlines())
    assert lines == sorted([f"{nested / 'reviewer.md'}\tmy-reviewer", f"{home / '.claude' / 'agents' / 'plain.md'}\tQuoted Name"])


@each_awk
def test_user_agent_names_with_no_agents_folder(awk, tmp_path):
    home = tmp_path / "empty-home"
    home.mkdir()
    result = run_command(command("akh-user-agent-names"), awk, tmp_path, home=str(home))
    assert result.stdout == b""


# ---------------------------------------------------------------------------
# SKILL.md wording and instructions
# ---------------------------------------------------------------------------

SERVER_BLOCK_LINES = [
    "uses <N> MCP server(s) that were not added",
    "The parts of <slug> that use them will not work until you add them yourself.",
    'MCP server "<name>" (<stdio | http | sse>) — not added',
    "Warning: this runs a program as you, with access to every file you can read.",
    "Warning: runs inline shell code (sh -c, bash -c, python -c).",
    "This server needs your S3DF sign-in, which /agent-knowledge-hub cannot yet pass to an MCP server, so there is no command to add it.",
    "To add it, run:",
    'claude mcp add-json --scope user <name> "$(cat ~/.claude/skills/<slug>/.akh-mcp/<name>.json)"',
    "Changed since the last install of <slug>. If you added it before, remove the old one first: claude mcp remove --scope user <name>",
    "Agent <name> installed as ~/.claude/agents/<file>; it can use <tools | every tool this session has, because it lists no tools>.",
    "Agent <name> not installed: it declares <keys>, which /agent-knowledge-hub does not install.",
    "Not installed: <slug> is already installed, so nothing was written. To replace it with the current version, run /agent-knowledge-hub update <slug>.",
    "Not installed: ~/.claude/skills/<slug>/ already exists and has no record of an install by /agent-knowledge-hub, so nothing was written.",
    "Left out of ~/.claude/skills/<slug>/: <.claude-plugin/ | .installed-manifest.json | .akh-mcp/>, which /agent-knowledge-hub never copies from a skill.",
    "MCP server \"<name>\" from <slug> is still set up if you added it. To remove it: claude mcp remove --scope user <name>",
    "To remove it, run this from that directory: claude mcp remove --scope local <name>",
    "Not removed: <entry>, which the manifest of <slug> lists but which is not a file in ~/.claude/agents/ or ~/.claude/commands/, so it was left in place.",
]


class TestSkillMd:
    @pytest.mark.parametrize("line", SERVER_BLOCK_LINES)
    def test_server_block_wording(self, line):  # FR-4, § Server block
        assert line in skill_text()

    def test_no_instruction_to_run_claude_mcp(self):  # FR-1, FR-5
        text = skill_text()
        assert "claude mcp add <name>" not in text
        assert "deregister" not in text.lower()
        in_block = set()
        for block in fenced_blocks(text):
            in_block.update(block.splitlines())
        prose = [l for l in text.splitlines() if "claude mcp" in l and l not in in_block]
        assert prose, "FR-1 (f) must be stated in SKILL.md"
        assert all("exactly as printed" in l for l in prose), prose

    def test_no_positional_argument_placeholder(self):  # FR-2
        # Claude Code replaces $0, $1, ... in a skill's text with the skill's arguments before
        # the model reads it, so an awk $0 reaches the model as "install". awk's $(0) is the
        # same field and is left alone (Claude Code 2.1.281, 2026-10-16).
        assert not re.findall(r"\$[0-9]", skill_text())

    def test_clone_directory_is_made_by_mktemp(self):  # FR-3
        install = skill_text().split("### Install", 1)[1].split("\n### ", 1)[0]
        assert "mktemp -d" in install
        assert "/tmp/" not in install

    def test_folder_copy_leaves_out_three_names(self):  # FR-3
        install = skill_text().split("### Install", 1)[1].split("\n### ", 1)[0]
        for name in (".claude-plugin/", ".installed-manifest.json", ".akh-mcp/"):
            assert name in install

    def test_create_scaffold_agent_stub_uses_allowed_keys(self):  # DoD › Create scaffold
        create = skill_text().split("### Create scaffold", 1)[1].split("\n### ", 1)[0]
        for key in ALLOWED_KEYS:
            assert f"`{key}`" in create
        assert "${HOME}/.claude/skills/<slug>/" in create


# ---------------------------------------------------------------------------
# MCP server configuration file (FR-1 (b) and (c), AC-2, AC-9)
# ---------------------------------------------------------------------------

def _pythons() -> list[str]:
    found = []
    for candidate in (shutil.which("python3"), "/usr/bin/python3", "/usr/bin/python3.6"):
        if candidate and Path(candidate).exists() and str(Path(candidate).resolve()) not in found:
            found.append(str(Path(candidate).resolve()))
    return found


each_python = pytest.mark.parametrize("python", _pythons())

SERVERS = [
    {"name": "akh-stdio", "transport": "stdio", "command": "/bin/true", "env": {"T": "${AKH_TEST_SECRET}"}},
    {"name": "akh-http", "transport": "http", "url": "https://gіthub.invalid/mcp",
     "headers": {"X": "a\nb c", "Y": "\U0001F600"}},
    {"name": "akh-notransport", "command": "/bin/true", "args": ["--x", "${HOME}/.claude/skills/s/run.sh"]},
    {"name": "akh-tilde", "transport": "stdio", "command": "~/.claude/skills/s/s.sh"},
    {"name": "akh-dollar-arg", "transport": "stdio", "command": "/bin/true", "args": ["--a=$HOME/x"]},
    {"name": "akh-eq-tilde", "transport": "stdio", "command": "/bin/true", "args": ["--a=~/x"]},
    {"name": "akh-long", "transport": "stdio", "command": "/bin/true", "args": ["x" * 5000]},
    {"name": "-sproject", "transport": "stdio", "command": "/bin/true"},
    {"name": "akh-bad-env", "transport": "stdio", "command": "/bin/true", "env": {"A": {"description": "x"}}},
    {"name": "akh-bad-args", "transport": "stdio", "command": "/bin/true", "args": "--x"},
    {"name": "akh-bad-headers", "transport": "sse", "url": "https://h.invalid/", "headers": {"A": 1}},
    {"name": "akh-no-command", "transport": "stdio"},
    {"name": "akh-no-url", "transport": "http"},
    {"name": "akh-ws", "transport": "ws", "url": "wss://h.invalid/"},
    {"name": "akh-dup", "transport": "stdio", "command": "/bin/true", "args": ["1"]},
    {"name": "AKH-DUP", "transport": "stdio", "command": "/bin/true", "args": ["2"]},
    {"name": "akh-sso", "transport": "http", "url": "https://akh-sso.invalid/mcp", "auth": {"type": "slac-sso"}},
    {"name": "akh-extra", "transport": "stdio", "command": "/bin/true", "description": "left out"},
]


def run_mcp_file(python: str, tmp_path: Path, name: str, servers=None) -> tuple[subprocess.CompletedProcess, Path]:
    import json

    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"name": "s", "mcp-servers": SERVERS if servers is None else servers},
                                 ensure_ascii=False), encoding="utf-8")
    bindir = tmp_path / "pybin"
    bindir.mkdir(exist_ok=True)
    if not (bindir / "python3").exists():
        (bindir / "python3").symlink_to(python)
    cmd = command("akh-mcp-file").replace("<plugin.json>", str(plugin)).replace("<name>", name).replace("<slug>", "s")
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)}
    result = subprocess.run(["/bin/sh", "-c", cmd], env=env, capture_output=True, timeout=20)
    return result, tmp_path / ".claude/skills/s/.akh-mcp" / f"{name}.json"


def out_lines(result) -> list[str]:
    return result.stdout.decode("ascii").splitlines()


def reason_patterns() -> list[re.Pattern]:
    """Each no-command reason in SKILL.md as a regex: `<a | b>` is one of its choices, `<x>` any text."""
    section = skill_text().split("The no-command reasons:", 1)[1].split("\n---", 1)[0]
    patterns = []
    for line in section.splitlines():
        found = re.search(r'— "(.*)"', line)
        if not found:
            continue
        parts = re.split(r"<([^<>]*)>", found.group(1))
        regex = "".join(re.escape(p) if i % 2 == 0 else
                        ("(?:" + "|".join(re.escape(c) for c in p.split(" | ")) + ")" if " | " in p else ".+")
                        for i, p in enumerate(parts))
        patterns.append(re.compile(regex))
    return patterns


@each_python
class TestMcpFileCommand:
    def test_stdio_written_and_shown(self, python, tmp_path):
        import json

        result, target = run_mcp_file(python, tmp_path, "akh-stdio")
        assert result.returncode == 0, result.stderr
        assert out_lines(result) == ["  Runs: /bin/true", "  env T=${AKH_TEST_SECRET}", f"file: {target}"]
        assert json.loads(target.read_bytes()) == {"type": "stdio", "command": "/bin/true", "args": [],
                                                   "env": {"T": "${AKH_TEST_SECRET}"}}

    def test_http_values_escaped_and_file_exact(self, python, tmp_path):  # AC-9
        import json

        result, target = run_mcp_file(python, tmp_path, "akh-http")
        assert result.returncode == 0, result.stderr
        assert out_lines(result)[:3] == ["  Connects to: https://g\\u0456thub.invalid/mcp",
                                         "  header X: a\\u000Ab\\u2028c", "  header Y: \\u{1F600}"]
        raw = target.read_bytes()
        assert raw.isascii() and len(raw) <= 4096
        assert json.loads(raw) == {"type": "http", "url": "https://gіthub.invalid/mcp",
                                   "headers": {"X": "a\nb c", "Y": "\U0001F600"}}

    def test_absent_transport_is_stdio_and_home_path_accepted(self, python, tmp_path):
        import json

        result, target = run_mcp_file(python, tmp_path, "akh-notransport")
        assert result.returncode == 0, result.stderr
        assert json.loads(target.read_bytes()) == {"type": "stdio", "command": "/bin/true",
                                                   "args": ["--x", "${HOME}/.claude/skills/s/run.sh"]}

    def test_other_fields_left_out(self, python, tmp_path):
        import json

        result, target = run_mcp_file(python, tmp_path, "akh-extra")
        assert result.returncode == 0, result.stderr
        assert json.loads(target.read_bytes()) == {"type": "stdio", "command": "/bin/true", "args": []}

    @pytest.mark.parametrize("name, reason", [
        ("akh-tilde", "its command ~/.claude/skills/s/s.sh starts with ~ or $, which Claude Code does not expand, so "
                      "it would run whatever file has that name in the directory a session starts in; the submitter "
                      "should write ${HOME} instead"),
        ("akh-dollar-arg", "its argument --a=$HOME/x starts with ~ or $, which Claude Code does not expand, so it "
                           "would run whatever file has that name in the directory a session starts in; the submitter "
                           "should write ${HOME} instead"),
        ("akh-eq-tilde", "its argument --a=~/x starts with ~ or $, which Claude Code does not expand, so it would "
                         "run whatever file has that name in the directory a session starts in; the submitter should "
                         "write ${HOME} instead"),
        ("akh-long", "its configuration is too long to show in full"),
        ("akh-bad-env", "its env is not in the form Claude Code accepts (each env or header value must be text)"),
        ("akh-bad-args", "its args is not in the form Claude Code accepts (args must be a list of text values)"),
        ("akh-bad-headers", "its headers is not in the form Claude Code accepts (each env or header value must be text)"),
        ("akh-no-command", "it has no command, which a stdio server needs"),
        ("akh-no-url", "it has no url, which a http or sse server needs"),
        ("akh-ws", 'its transport "ws" is not stdio, http or sse'),
    ])
    def test_refusals_print_their_reason(self, python, tmp_path, name, reason):
        result, target = run_mcp_file(python, tmp_path, name)
        assert result.returncode == 1, result.stderr
        assert out_lines(result) == [f"refused: {reason}"]
        assert not target.exists()
        assert any(p.fullmatch(reason) for p in reason_patterns()), reason

    @pytest.mark.parametrize("name", ["-sproject", "akh-dup", "akh-missing", "../x"])
    def test_name_it_should_not_be_given_fails(self, python, tmp_path, name):
        result, target = run_mcp_file(python, tmp_path, name)
        assert result.returncode == 2
        assert result.stdout == b""
        assert not (tmp_path / ".claude/skills/s/.akh-mcp").exists() or not any((tmp_path / ".claude/skills/s/.akh-mcp").iterdir())

    def test_slac_sso_shown_not_written(self, python, tmp_path):
        result, target = run_mcp_file(python, tmp_path, "akh-sso")
        assert result.returncode == 3, result.stderr
        assert out_lines(result) == ["  Connects to: https://akh-sso.invalid/mcp", "no file: slac-sso"]
        assert not target.exists()

    def test_existing_file_is_not_replaced(self, python, tmp_path):
        target = tmp_path / ".claude/skills/s/.akh-mcp/akh-stdio.json"
        target.parent.mkdir(parents=True)
        target.write_text("{}")
        result, _ = run_mcp_file(python, tmp_path, "akh-stdio")
        assert result.returncode == 2
        assert target.read_text() == "{}"

    def test_unreadable_plugin_json_fails(self, python, tmp_path):
        result, target = run_mcp_file(python, tmp_path, "akh-stdio", servers={"akh-stdio": {}})
        assert result.returncode == 2
        assert not target.exists()


@each_python
def test_mcp_file_ignores_modules_in_working_directory(python, tmp_path):
    """`python3 -` would import a json.py from the directory the session runs in; -I prevents it."""
    work = tmp_path / "work"
    work.mkdir()
    (work / "json.py").write_text("raise SystemExit(9)\n")
    import json

    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"mcp-servers": SERVERS[:1]}))
    bindir = tmp_path / "pybin"
    bindir.mkdir()
    (bindir / "python3").symlink_to(python)
    cmd = command("akh-mcp-file").replace("<plugin.json>", str(plugin)).replace("<name>", "akh-stdio").replace("<slug>", "s")
    result = subprocess.run(["/bin/sh", "-c", cmd], env={"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)},
                            cwd=work, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_mcp_file_without_python3_exits_127(tmp_path):  # § Server rules › Result
    empty = tmp_path / "bin"
    empty.mkdir()
    cmd = command("akh-mcp-file").replace("<plugin.json>", "/nonexistent").replace("<name>", "akh-stdio").replace("<slug>", "s")
    result = subprocess.run(["/bin/sh", "-c", cmd], env={"PATH": str(empty), "HOME": str(tmp_path)},
                            capture_output=True, timeout=20)
    assert result.returncode == 127
    assert "writes a server's configuration with python3, which this computer does not have" in skill_text()


# ---------------------------------------------------------------------------
# #053 — a pinned install fetches exactly the pinned commit and checks HEAD
# ---------------------------------------------------------------------------

GIT_ENV = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@invalid"}


def _git(*args, cwd=None, home=None):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home or cwd), **GIT_ENV}
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def remote(tmp_path):
    """A bare repository like GitHub: main is A then B, and a commit can be fetched by its ID.

    It also has commit C, the attacker's, on a branch whose name is A's commit ID.
    """
    src = tmp_path / "src"
    _git("init", "-q", "-b", "main", str(src), home=tmp_path)
    (src / "SKILL.md").write_text("reviewed\n")
    _git("add", "-A", cwd=src, home=tmp_path)
    _git("commit", "-q", "-m", "A", cwd=src, home=tmp_path)
    a = _git("rev-parse", "HEAD", cwd=src, home=tmp_path)
    (src / "SKILL.md").write_text("tip\n")
    _git("commit", "-q", "-am", "B", cwd=src, home=tmp_path)
    _git("checkout", "-q", "--orphan", "evil", cwd=src, home=tmp_path)
    (src / "SKILL.md").write_text("attacker\n")
    _git("add", "-A", cwd=src, home=tmp_path)
    _git("commit", "-q", "-m", "C", cwd=src, home=tmp_path)
    _git("branch", "-q", "-m", "evil", a, cwd=src, home=tmp_path)
    bare = tmp_path / "remote.git"
    _git("clone", "-q", "--bare", str(src), str(bare), home=tmp_path)
    _git("config", "uploadpack.allowReachableSHA1InWant", "true", cwd=bare, home=tmp_path)
    return {"url": f"file://{bare}", "bare": bare, "A": a}


def pinned_fetch(tmp_path, url, sha, path=None):
    d = tmp_path / "d"
    d.mkdir(exist_ok=True)
    cmd = (command("akh-pinned-fetch").replace("<dir>", str(d)).replace("<repo_url>", url)
           .replace("<pinned_commit_sha>", sha))
    env = {"PATH": path or "/usr/bin:/bin", "HOME": str(tmp_path), **GIT_ENV}
    result = subprocess.run(["/bin/sh", "-c", cmd], env=env, capture_output=True, text=True, timeout=60)
    return result, d / "repo"


class TestPinnedFetch:
    def test_pin_behind_the_tip_is_installed(self, tmp_path, remote):  # FR-4
        result, repo = pinned_fetch(tmp_path, remote["url"], remote["A"])
        assert result.stdout.splitlines()[-1] == "akh-pin: ok", result.stderr
        assert (repo / "SKILL.md").read_text() == "reviewed\n"

    def test_branch_named_like_the_pin_is_not_installed(self, tmp_path, remote):  # FR-1, the attack
        _git("symbolic-ref", "HEAD", f"refs/heads/{remote['A']}", cwd=remote["bare"], home=tmp_path)
        old = tmp_path / "old"
        _git("clone", "-q", remote["url"], str(old), home=tmp_path)
        _git("checkout", "-q", remote["A"], cwd=old, home=tmp_path)
        assert (old / "SKILL.md").read_text() == "attacker\n", "the attack no longer reproduces with this git"

        result, repo = pinned_fetch(tmp_path, remote["url"], remote["A"])
        assert result.stdout.splitlines()[-1] == "akh-pin: ok", result.stderr
        assert (repo / "SKILL.md").read_text() == "reviewed\n"

    def test_pin_the_remote_does_not_have_fails(self, tmp_path, remote):  # FR-2
        missing = "0" * 40
        _git("branch", "-q", missing, "main", cwd=remote["bare"], home=tmp_path)
        result, repo = pinned_fetch(tmp_path, remote["url"], missing)
        assert result.stdout.splitlines()[-1] == "akh-pin: fetch-failed"
        assert not (repo / "SKILL.md").exists()

    def test_head_other_than_the_pin_is_reported(self, tmp_path, remote):  # FR-1, FR-2
        fake = tmp_path / "fakebin"
        fake.mkdir()
        (fake / "git").write_text(
            '#!/bin/sh\nfor a; do last=$a; done\n'
            'if test "$last" = HEAD; then echo ' + "f" * 40 + '; exit 0; fi\nexec /usr/bin/git "$@"\n')
        (fake / "git").chmod(0o755)
        result, _ = pinned_fetch(tmp_path, remote["url"], remote["A"], path=f"{fake}:/usr/bin:/bin")
        assert result.stdout.splitlines()[-1] == "akh-pin: mismatch " + "f" * 40

    def test_install_step_forbids_other_routes_for_a_pinned_skill(self):  # FR-4, FR-5
        install = skill_text().split("### Install", 1)[1].split("\n### ", 1)[0]
        assert "git clone --depth 1 '<repo_url>'" in install
        for phrase in ("Never get a pinned skill any other way", "`FETCH_HEAD`", "GitHub Contents API",
                       "installing a pinned skill needs git, which this computer does not have",
                       "could not be fetched from <repo_url>",
                       "served commit <actual> where the catalog pins <sha>",
                       "is not a commit ID"):
            assert phrase in install, phrase


# ---------------------------------------------------------------------------
# #006 Slice 4 — catalog values checked before any command uses them, and install skillset
# ---------------------------------------------------------------------------

def run_python_command(marker: str, tmp_path: Path, payload, name: str):
    import json
    d = tmp_path / "dir"
    d.mkdir(exist_ok=True)
    (d / name).write_text(payload if isinstance(payload, str) else json.dumps(payload))
    bindir = tmp_path / "pybin"
    bindir.mkdir(exist_ok=True)
    if not (bindir / "python3").exists():
        (bindir / "python3").symlink_to(_pythons()[0])
    cmd = command(marker).replace("<dir>", str(d))
    result = subprocess.run(["/bin/sh", "-c", cmd], env={"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)},
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()


GOOD_ENTRY = {"slug": "x", "repo_url": "https://github.com/slaclab/lcls-tools", "skill_path": "/skills/x",
              "pinned_commit_sha": "a" * 40, "visibility": "internal", "has_mcp_server": True, "has_scripts": False}


class TestMemberCheck:  # #006 FR-7 › Argument rule
    def test_good_entry_prints_its_values(self, tmp_path):
        assert run_python_command("akh-member-check", tmp_path, GOOD_ENTRY, "skill.json") == [
            "akh-member: ok repo_url=https://github.com/slaclab/lcls-tools skill_path=/skills/x pin=" + "a" * 40
            + " visibility=internal mcp=yes scripts=no"]

    def test_unpinned_entry(self, tmp_path):
        entry = {**GOOD_ENTRY, "pinned_commit_sha": None, "skill_path": "/", "visibility": "public", "has_mcp_server": False}
        (line,) = run_python_command("akh-member-check", tmp_path, entry, "skill.json")
        assert line.endswith("skill_path=/ pin=none visibility=public mcp=no scripts=no")

    @pytest.mark.parametrize("field,value,refused", [
        ("repo_url", "https://github.com/a/b$(touch {marker})", "repo_url"),
        ("repo_url", "https://github.com/a/b';touch {marker};'", "repo_url"),
        ("repo_url", "local://dir", "repo_url"),
        ("repo_url", None, "repo_url"),
        ("skill_path", "/skills/$(touch {marker})", "skill_path"),
        ("skill_path", "/a/../b", "skill_path"),
        ("skill_path", "/a\nb", "skill_path"),
        ("pinned_commit_sha", "main", "pinned_commit_sha"),
        ("pinned_commit_sha", "A" * 40, "pinned_commit_sha"),
    ])
    def test_hostile_values_are_refused_and_never_run(self, tmp_path, field, value, refused):
        marker = tmp_path / "akh-pwned"
        entry = {**GOOD_ENTRY, field: value.format(marker=marker) if isinstance(value, str) else value}
        assert run_python_command("akh-member-check", tmp_path, entry, "skill.json") == [f"akh-member: refused {refused}"]
        assert not marker.exists()

    def test_unreadable_entry(self, tmp_path):
        assert run_python_command("akh-member-check", tmp_path, "<html>404</html>", "skill.json") == ["akh-member: unreadable"]


class TestSkillsetMembers:  # #006 FR-7, ADR-U20
    def test_members_in_stored_order(self, tmp_path):
        payload = {"slug": "set", "version": 3, "skills": [{"slug": "b-skill"}, {"slug": "a-skill"}, {"slug": "c"}]}
        assert run_python_command("akh-skillset-members", tmp_path, payload, "skillset.json") == [
            "akh-skillset: 3 members", "1 b-skill", "2 a-skill", "3 c"]

    def test_empty_skillset(self, tmp_path):
        assert run_python_command("akh-skillset-members", tmp_path, {"skills": []}, "skillset.json") == ["akh-skillset: 0 members"]

    def test_slug_that_is_not_a_catalog_slug_is_refused(self, tmp_path):
        payload = {"skills": [{"slug": "ok"}, {"slug": "x;touch y"}, {"slug": "Upper"}, {}]}
        assert run_python_command("akh-skillset-members", tmp_path, payload, "skillset.json") == [
            "akh-skillset: 4 members", "1 ok", "2 refused", "3 refused", "4 refused"]

    def test_unreadable_response(self, tmp_path):
        assert run_python_command("akh-skillset-members", tmp_path, "not json", "skillset.json") == ["akh-skillset: unreadable"]


INSTALL_SKILLSET_LINES = [
    "Install these <N> of <M> skills from skillset <slug>? (y/N)",
    "Nothing installed.",
    "[<i>/<M>] Installing <member>... ✓",
    "[<i>/<M>] Skipping <member> (already installed)",
    "[<i>/<M>] Skipping <member> (kept your existing directory)",
    "[<i>/<M>] ✗ <member>: <reason>",
    "`~/.claude/skills/<member>/` exists but was not installed by /agent-knowledge-hub. Replace it? (y/N)",
    "Done: <installed> installed, <skipped> skipped, <failed> failed (<M> members).",
    "Run /agent-knowledge-hub install skillset <slug> again to retry the failed members; installed members are skipped.",
    "⚠ Skillset '<slug>' contains no skills.",
    "✗ Skillset not found.",
    "MCP server, not added",
    "<K> of the installed skills use MCP servers that were not added: <member> (<name>, <name>), <member> (<name>). Each of these skills works only in part until you add its servers.",
    "── <member> ──",
    "Another skill in this run also brings a server named \"<name>\"; only one of them can be added under that name.",
    "https://agent-knowledge-hub.slac.stanford.edu/guides/slac-github-access",
]


class TestInstallSkillsetSection:
    def section(self) -> str:
        return skill_text().split("### Install skillset", 1)[1].split("\n### ", 1)[0]

    @pytest.mark.parametrize("line", INSTALL_SKILLSET_LINES)
    def test_words(self, line):
        assert line in skill_text()

    def test_fetches_through_the_helper(self):
        assert "sh ${CLAUDE_SKILL_DIR}/hub-request.sh GET /cli/api/skillsets/<slug> > '<dir>/skillset.json'" in self.section()

    def test_every_clone_and_fetch_skips_credential_prompts(self):  # FR-7 › Failure rule
        for block in (command("akh-pinned-fetch"),):
            assert "export GIT_TERMINAL_PROMPT=0 GIT_ASKPASS= GCM_INTERACTIVE=0" in block
        install = skill_text().split("### Install\n", 1)[1].split("\n### ", 1)[0]
        assert "GIT_TERMINAL_PROMPT=0 GIT_ASKPASS= GCM_INTERACTIVE=0 git clone --depth 1 '<repo_url>' '<dir>/repo'" in install

    def test_install_checks_the_entry_before_any_command(self):  # FR-7 › Argument rule, plain install too
        install = skill_text().split("### Install\n", 1)[1].split("\n### ", 1)[0]
        assert "sh ${CLAUDE_SKILL_DIR}/hub-request.sh GET /cli/api/skills/<slug> > '<dir>/skill.json'" in install
        assert "akh-member-check" in install
