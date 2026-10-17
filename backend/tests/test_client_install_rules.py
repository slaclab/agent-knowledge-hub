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
    result = run_command(command("akh-user-agent-names"), awk, tmp_path, home=str(home), base=str(home / ".claude"))
    assert result.returncode == 0
    lines = sorted(result.stdout.decode().splitlines())
    assert lines == sorted([f"{nested / 'reviewer.md'}\tmy-reviewer", f"{home / '.claude' / 'agents' / 'plain.md'}\tQuoted Name"])


@each_awk
def test_user_agent_names_with_no_agents_folder(awk, tmp_path):
    home = tmp_path / "empty-home"
    home.mkdir()
    result = run_command(command("akh-user-agent-names"), awk, tmp_path, home=str(home), base=str(home / ".claude"))
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


def run_mcp_file(python: str, tmp_path: Path, name: str, servers=None,
                 base: Path | None = None, umask: int | None = None) -> tuple[subprocess.CompletedProcess, Path]:
    """Run akh-mcp-file with HOME at tmp_path; `base` defaults to the user install's, HOME/.claude."""
    import json

    base = base or tmp_path / ".claude"

    plugin = tmp_path / "plugin.json"
    plugin.write_text(json.dumps({"name": "s", "mcp-servers": SERVERS if servers is None else servers},
                                 ensure_ascii=False), encoding="utf-8")
    bindir = tmp_path / "pybin"
    bindir.mkdir(exist_ok=True)
    if not (bindir / "python3").exists():
        (bindir / "python3").symlink_to(python)
    cmd = (command("akh-mcp-file").replace("<plugin.json>", str(plugin)).replace("<name>", name)
           .replace("<slug>", "s").replace("<base>", str(base)))
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)}
    import os
    pre = (lambda: os.umask(umask)) if umask is not None else None
    result = subprocess.run(["/bin/sh", "-c", cmd], env=env, capture_output=True, timeout=20, preexec_fn=pre)
    return result, base / "skills/s/.akh-mcp" / f"{name}.json"


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



# ---------------------------------------------------------------------------
# #057 — workspace installs, and installing exactly what the user confirmed
# ---------------------------------------------------------------------------

import json as _json
import os as _os
import stat as _stat

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x"}


def run_marked(marker: str, tmp_path: Path, cwd: Path | None = None, umask: int | None = None,
               home: Path | None = None, **substitutions: str) -> subprocess.CompletedProcess:
    """Run a SKILL.md command through sh with python3 on PATH, placeholders replaced, nothing else."""
    bindir = tmp_path / "pybin"
    bindir.mkdir(exist_ok=True)
    if not (bindir / "python3").exists():
        (bindir / "python3").symlink_to(_pythons()[0])
    cmd = command(marker)
    for key, value in substitutions.items():
        cmd = cmd.replace(f"<{key}>", value)
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(home or tmp_path / "home")}
    pre = (lambda: _os.umask(umask)) if umask is not None else None
    return subprocess.run(["/bin/sh", "-c", cmd], env=env, cwd=cwd or tmp_path, capture_output=True,
                          text=True, timeout=30, preexec_fn=pre)


def mode(path: Path) -> int:
    return _stat.S_IMODE(_os.lstat(path).st_mode)


def manifest(base: Path, slug: str, commands=(), agents=()):
    folder = base / "skills" / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ".installed-manifest.json").write_text(
        _json.dumps({"commands": list(commands), "agents": list(agents), "mcp_servers": []}))


class TestWorkspaceBase:
    def test_new_folders_are_made_without_group_write_and_reported(self, tmp_path):
        ws = tmp_path / "proj"
        ws.mkdir()
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, umask=0o002, mode="make")
        assert result.stdout.strip() == f"akh-workspace: base {ws.resolve()}/.claude new"
        assert mode(ws / ".claude") == 0o755 and mode(ws / ".claude" / "skills") == 0o755

    def test_existing_folders_are_used_as_they_are(self, tmp_path):
        ws = tmp_path / "proj"
        (ws / ".claude" / "skills").mkdir(parents=True)
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, mode="make")
        assert result.stdout.strip() == f"akh-workspace: base {ws.resolve()}/.claude"

    @pytest.mark.parametrize("folder", [".claude", ".claude/skills", ".claude/commands", ".claude/agents"])
    def test_a_folder_other_accounts_can_write_is_refused(self, tmp_path, folder):
        ws = tmp_path / "proj"
        for f in (".claude/skills", ".claude/commands", ".claude/agents"):
            (ws / f).mkdir(parents=True, exist_ok=True)
        _os.chmod(ws / folder, 0o775)
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, mode="make")
        assert result.stdout.strip() == f"akh-workspace: refused writable {(ws / folder).resolve()}"

    def test_find_makes_nothing(self, tmp_path):
        ws = tmp_path / "proj"
        ws.mkdir()
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, mode="find")
        assert result.stdout.strip() == f"akh-workspace: base {ws.resolve()}/.claude"
        assert not (ws / ".claude").exists()

    @pytest.mark.parametrize("name", ["my proj", "it's", "a$b", "tab\there"])
    def test_a_path_the_client_does_not_put_in_commands_is_refused(self, tmp_path, name):
        ws = tmp_path / name
        ws.mkdir()
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, mode="make")
        assert result.stdout.strip() == "akh-workspace: refused path"
        assert not (ws / ".claude").exists()

    def test_root_is_refused(self, tmp_path):
        result = run_marked("akh-workspace-base", tmp_path, cwd=Path("/"), mode="make")
        assert result.stdout.strip() == "akh-workspace: refused path"

    def test_the_home_folder_is_not_a_workspace(self, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        result = run_marked("akh-workspace-base", tmp_path, cwd=home, home=home, mode="make")
        assert result.stdout.strip() == "akh-workspace: refused home"
        assert not (home / ".claude").exists()

    def test_nothing_is_made_when_a_later_folder_is_refused(self, tmp_path):
        ws, elsewhere = tmp_path / "proj", tmp_path / "elsewhere"
        (ws / ".claude").mkdir(parents=True)
        elsewhere.mkdir()
        (ws / ".claude" / "commands").symlink_to(elsewhere)
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, mode="make")
        assert result.stdout.strip() == "akh-workspace: refused folder"
        assert not (ws / ".claude" / "skills").exists()

    @pytest.mark.parametrize("layout", ["claude-link", "skills-link", "claude-file"])
    def test_a_link_or_a_file_in_place_of_a_folder_is_refused(self, tmp_path, layout):
        ws, elsewhere = tmp_path / "proj", tmp_path / "elsewhere"
        ws.mkdir()
        (elsewhere / "skills").mkdir(parents=True)
        if layout == "claude-link":
            (ws / ".claude").symlink_to(elsewhere)
        elif layout == "skills-link":
            (ws / ".claude").mkdir()
            (ws / ".claude" / "skills").symlink_to(elsewhere / "skills")
        else:
            (ws / ".claude").write_text("x")
        result = run_marked("akh-workspace-base", tmp_path, cwd=ws, mode="make")
        assert result.stdout.strip() == "akh-workspace: refused folder"


class TestWorkspaceModes:
    def test_install_loses_group_and_other_write(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        skill = base / "skills" / "x"
        (skill / "bin").mkdir(parents=True)
        (skill / "SKILL.md").write_text("x")
        (skill / "bin" / "run.sh").write_text("x")
        _os.chmod(skill / "bin" / "run.sh", 0o775)
        _os.chmod(skill / "SKILL.md", 0o666)
        for d in (skill, skill / "bin"):
            _os.chmod(d, 0o777)
        (base / "commands" / "sub").mkdir(parents=True)
        (base / "commands" / "x.md").write_text("x")
        (base / "commands" / "sub" / "y.md").write_text("x")
        for p in (base / "commands", base / "commands" / "sub"):
            _os.chmod(p, 0o775)
        _os.chmod(base / "commands" / "x.md", 0o664)
        manifest(base, "x", commands=["commands/x.md", "commands/sub/y.md"])
        result = run_marked("akh-workspace-modes", tmp_path, base=str(base), slug="x")
        assert result.returncode == 0, result.stderr
        assert mode(skill) == 0o755 and mode(skill / "bin") == 0o755
        assert mode(skill / "SKILL.md") == 0o644 and mode(skill / "bin" / "run.sh") == 0o755
        assert mode(base / "commands" / "x.md") == 0o644
        assert mode(base / "commands") == 0o755 and mode(base / "commands" / "sub") == 0o755

    def test_a_file_name_from_the_skill_never_reaches_the_shell(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        marker = tmp_path / "akh-pwned"
        name = "commands/x'$(touch akh-pwned)'.md"  # run_marked's working folder is tmp_path
        (base / "commands").mkdir(parents=True)
        (base / name).write_text("x")
        _os.chmod(base / name, 0o666)
        manifest(base, "x", commands=[name])
        result = run_marked("akh-workspace-modes", tmp_path, base=str(base), slug="x")
        assert result.returncode == 0, result.stderr
        assert not marker.exists()
        assert mode(base / name) == 0o644

    def test_only_write_is_cleared(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        manifest(base, "x")
        secret = base / "skills" / "x" / "secret"
        secret.write_text("x")
        _os.chmod(secret, 0o600)
        _os.chmod(base / "skills" / "x", 0o700)
        run_marked("akh-workspace-modes", tmp_path, base=str(base), slug="x")
        assert mode(secret) == 0o600 and mode(base / "skills" / "x") == 0o700

    def test_a_skill_folder_that_is_a_link_is_reported_and_not_walked(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        (base / "skills").mkdir(parents=True)
        victim = tmp_path / "victim"
        victim.mkdir()
        (victim / "f").write_text("x")
        _os.chmod(victim / "f", 0o666)
        (base / "skills" / "x").symlink_to(victim)
        result = run_marked("akh-workspace-modes", tmp_path, base=str(base), slug="x")
        assert result.stdout.strip() == f"akh-workspace: foreign {base / 'skills' / 'x'}"
        assert mode(victim / "f") == 0o666

    def test_a_folder_holding_files_of_others_is_left_alone(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        (base / "agents").mkdir(parents=True)
        (base / "agents" / "theirs.md").write_text("x")
        (base / "agents" / "ours.md").write_text("x")
        _os.chmod(base / "agents", 0o775)
        manifest(base, "x", agents=["agents/ours.md"])
        run_marked("akh-workspace-modes", tmp_path, base=str(base), slug="x")
        assert mode(base / "agents") == 0o775

    def test_a_link_is_never_followed(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        manifest(base, "x")
        outside = tmp_path / "outside"
        outside.write_text("x")
        _os.chmod(outside, 0o666)
        (base / "skills" / "x" / "link").symlink_to(outside)
        result = run_marked("akh-workspace-modes", tmp_path, base=str(base), slug="x")
        assert mode(outside) == 0o666
        assert result.stdout.strip() == f"akh-workspace: foreign {base / 'skills' / 'x' / 'link'}"


def git(*args, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env={**_os.environ, **GIT_ENV}, check=True,
                          capture_output=True, text=True).stdout.strip()


def exclude_lines(repo: Path) -> list[str]:
    path = repo / ".git" / "info" / "exclude"
    return [l for l in path.read_text().splitlines() if l and not l.startswith("#")] if path.exists() else []


def installed(base: Path, slug="x", commands=(), agents=()):
    manifest(base, slug, commands, agents)
    (base / "skills" / slug / "SKILL.md").write_text("x")
    for entry in (*commands, *agents):
        (base / entry).parent.mkdir(parents=True, exist_ok=True)
        (base / entry).write_text("x")


class TestWorkspaceExclude:
    def test_skill_commands_and_agents_excluded_once_then_removed(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        info = repo / ".git" / "info" / "exclude"
        info.write_text("# mine\n/keep/")
        base = repo / ".claude"
        installed(base, commands=["commands/c.md"], agents=["agents/a.md"])
        want = ["/.claude/skills/x/", "/.claude/commands/c.md", "/.claude/agents/a.md"]
        for _ in range(2):
            r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
            assert r.stdout.strip().splitlines() == ["akh-workspace: excluded " + l for l in want], r.stderr
        assert exclude_lines(repo) == ["/keep/", *want]
        assert git("status", "--porcelain", "--untracked-files=all", cwd=repo) == ""
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="remove")
        assert r.stdout.strip().splitlines() == ["akh-workspace: unexcluded " + l for l in want]
        assert exclude_lines(repo) == ["/keep/"]

    def test_subfolder_workspace(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "sub").mkdir(parents=True)
        git("init", "-q", cwd=repo)
        base = repo / "sub" / ".claude"
        installed(base)
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        assert r.stdout.strip() == "akh-workspace: excluded /sub/.claude/skills/x/"
        assert exclude_lines(repo) == ["/sub/.claude/skills/x/"]

    def test_worktree_writes_the_common_exclude_file(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", "-b", "main", cwd=repo)
        (repo / "f").write_text("x")
        git("add", "f", cwd=repo)
        git("commit", "-q", "-m", "f", cwd=repo)
        wt = tmp_path / "wt"
        git("worktree", "add", "-q", "-b", "w", str(wt), cwd=repo)
        base = wt / ".claude"
        installed(base)
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        assert r.stdout.strip() == "akh-workspace: excluded /.claude/skills/x/"
        assert "/.claude/skills/x/" in exclude_lines(repo)
        assert git("status", "--porcelain", "--untracked-files=all", cwd=wt) == ""

    def test_outside_git(self, tmp_path):
        base = tmp_path / "plain" / ".claude"
        installed(base)
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        assert r.stdout.strip() == "akh-workspace: not in git"

    def test_an_exclude_file_that_is_not_utf8_keeps_its_bytes(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        info = repo / ".git" / "info" / "exclude"
        info.write_bytes(b"/caf\xe9/\n")
        base = repo / ".claude"
        installed(base)
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        assert r.stdout.strip() == "akh-workspace: excluded /.claude/skills/x/"
        assert info.read_bytes() == b"/caf\xe9/\n/.claude/skills/x/\n"
        run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="remove")
        assert info.read_bytes() == b"/caf\xe9/\n"

    def test_a_linked_exclude_file_is_not_written(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        outside = tmp_path / "outside"
        outside.write_text("")
        info = repo / ".git" / "info" / "exclude"
        info.unlink()
        info.symlink_to(outside)
        base = repo / ".claude"
        installed(base)
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        assert r.stdout.strip() == "akh-workspace: not excluded"
        assert outside.read_text() == ""


SHA = "b" * 40
REPO_A = "https://github.com/slaclab/a"
REPO_B = "https://github.com/slaclab/b"


def exact(tmp_path: Path, expected: str, entries: dict | None = None, sets: dict | None = None):
    d = tmp_path / "dir"
    d.mkdir(exist_ok=True)
    (d / "expected.txt").write_text(expected)
    for slug, entry in (entries or {}).items():
        (d / f"skill-{slug}.json").write_text(entry if isinstance(entry, str) else _json.dumps(entry))
    for slug, entry in (sets or {}).items():
        (d / f"skillset-{slug}.json").write_text(entry if isinstance(entry, str) else _json.dumps(entry))
    plan = run_marked("akh-exact", tmp_path, dir=str(d), step="plan").stdout.strip().splitlines()
    check = run_marked("akh-exact", tmp_path, dir=str(d), step="check").stdout.strip().splitlines()
    return plan, check


def entry(slug, repo=REPO_A, pin=SHA):
    return {"slug": slug, "repo_url": repo, "skill_path": "/", "pinned_commit_sha": pin}


class TestExactInstall:
    def test_matching_skill_and_set_install_in_order(self, tmp_path):
        expected = (f"skill solo {REPO_A} {SHA}\n"
                    "skillset kit 4\n"
                    f"member m1 {REPO_B} none\n"
                    f"member solo {REPO_A} {SHA}\n")
        plan, check = exact(tmp_path, expected,
                            entries={"solo": entry("solo"), "m1": entry("m1", REPO_B, None)},
                            sets={"kit": {"slug": "kit", "version": 4, "skills": [{"slug": "m1"}, {"slug": "solo"}]}})
        assert plan == ["akh-exact: fetch skill solo", "akh-exact: fetch skillset kit", "akh-exact: fetch skill m1"]
        assert check == ["akh-exact: ok skill solo", "akh-exact: ok skillset kit 2 members",
                         "akh-exact: install solo m1"]

    def test_crlf_lines_are_read(self, tmp_path):
        _, check = exact(tmp_path, f"skill solo {REPO_A} {SHA}\r\n", entries={"solo": entry("solo")})
        assert check == ["akh-exact: ok skill solo", "akh-exact: install solo"]

    @pytest.mark.parametrize("now,why", [
        (entry("solo", REPO_B), "repo_url"),
        (entry("solo", pin="c" * 40), "pin"),
        (entry("solo", pin=None), "pin"),
        ('{"detail": "Not found"}', "missing"),
        ("not json", "missing"),
    ])
    def test_a_changed_skill_installs_nothing(self, tmp_path, now, why):
        _, check = exact(tmp_path, f"skill solo {REPO_A} {SHA}\n", entries={"solo": now})
        assert check == [f"akh-exact: changed skill solo {why}", "akh-exact: install none"]

    @pytest.mark.parametrize("now,why", [
        ({"slug": "kit", "version": 5, "skills": [{"slug": "m1"}]}, "version"),
        ({"slug": "kit", "version": 4, "skills": [{"slug": "m1"}, {"slug": "m2"}]}, "members"),
        ({"slug": "kit", "version": 4, "skills": []}, "members"),
        ('{"detail": "Skillset not found"}', "missing"),
        (None, "missing"),
    ])
    def test_a_changed_set_installs_none_of_its_members(self, tmp_path, now, why):
        expected = f"skillset kit 4\nmember m1 {REPO_A} {SHA}\nskill other {REPO_B} none\n"
        _, check = exact(tmp_path, expected, entries={"m1": entry("m1"), "other": entry("other", REPO_B, None)},
                         sets={} if now is None else {"kit": now})
        assert check == [f"akh-exact: changed skillset kit {why}", "akh-exact: ok skill other",
                         "akh-exact: install other"]

    def test_a_set_with_a_changed_member_installs_none_of_its_members(self, tmp_path):
        expected = f"skillset kit 4\nmember m1 {REPO_A} {SHA}\nmember m2 {REPO_A} {SHA}\n"
        _, check = exact(tmp_path, expected, entries={"m1": entry("m1"), "m2": entry("m2", REPO_B)},
                         sets={"kit": {"slug": "kit", "version": 4, "skills": [{"slug": "m1"}, {"slug": "m2"}]}})
        assert check == ["akh-exact: changed skillset kit member m2 repo_url", "akh-exact: install none"]

    @pytest.mark.parametrize("expected", [
        f"skill Bad {REPO_A} {SHA}\n",
        f"skill x;touch y {REPO_A} {SHA}\n",
        f"skill x https://evil.example/a {SHA}\n",
        f"skill x {REPO_A} main\n",
        f"member x {REPO_A} {SHA}\n",
        "skillset kit four\n",
        f"skill x {REPO_A} {SHA} extra\n",
    ])
    def test_a_line_outside_the_grammar_refuses_the_whole_list(self, tmp_path, expected):
        plan, check = exact(tmp_path, expected)
        assert plan == ["akh-exact: refused line 1"]
        assert check == ["akh-exact: refused line 1"]

    def test_an_empty_list(self, tmp_path):
        plan, check = exact(tmp_path, "\n")
        assert plan == ["akh-exact: empty"] and check == ["akh-exact: empty"]


@each_python
class TestMcpFileInAWorkspace:
    @pytest.mark.parametrize("server,what,value", [
        ({"command": "/bin/sh", "args": ["${HOME}/.claude/skills/s/run.sh"]}, "argument", "${HOME}/.claude/skills/s/run.sh"),
        ({"command": "${HOME}/.claude/skills/s/run.sh"}, "command", "${HOME}/.claude/skills/s/run.sh"),
        ({"command": "/bin/true", "env": {"TOOL": "${HOME}/.claude/skills/s/tool"}}, "env value", "${HOME}/.claude/skills/s/tool"),
    ])
    def test_a_server_using_the_home_skills_folder_is_refused(self, python, tmp_path, server, what, value):
        base = tmp_path / "proj" / ".claude"
        result, target = run_mcp_file(python, tmp_path, "akh-home", [{"name": "akh-home", **server}], base=base)
        assert result.returncode == 1
        assert out_lines(result) == [f"refused: its {what} {value} uses ${{HOME}}/.claude/skills/, which a workspace "
                                     "install does not create; install s without --workspace to use this server"]
        assert not target.exists()

    def test_other_servers_are_written_under_the_workspace(self, python, tmp_path):
        base = tmp_path / "proj" / ".claude"
        servers = [{"name": "akh-plain", "command": "/bin/true", "args": ["--x"]}]
        result, target = run_mcp_file(python, tmp_path, "akh-plain", servers, base=base)
        assert result.returncode == 0, result.stderr
        assert out_lines(result)[-1] == f"file: {target}"


def test_home_paths_are_listed(tmp_path):
    base = tmp_path / "proj" / ".claude"
    skill = base / "skills" / "x"
    (skill / "docs").mkdir(parents=True)
    (skill / "SKILL.md").write_text("Run ${HOME}/.claude/skills/x/run.sh first.\n")
    (skill / "docs" / "tilde.md").write_text("See ~/.claude/skills/x\n")
    (skill / "docs" / "home.md").write_text("PATH=$HOME/.claude/skills/x:$PATH\n")
    (skill / "docs" / "quoted.md").write_text('sh "$HOME"/.claude/skills/x/run.sh\n')
    (skill / "docs" / "relative.md").write_text("Run .claude/skills/x/run.sh from the project.\n")
    (skill / "docs" / "other.md").write_text("Run ${HOME}/.claude/skills/xy/run.sh.\n")
    (base / "commands").mkdir()
    (base / "commands" / "c.md").write_text("Call ${HOME}/.claude/skills/x/run.sh\n")
    manifest(base, "x", commands=["commands/c.md"])
    result = run_marked("akh-home-paths", tmp_path, base=str(base), slug="x")
    assert sorted(result.stdout.strip().splitlines()) == sorted(
        str(p) for p in (skill / "SKILL.md", skill / "docs" / "tilde.md", skill / "docs" / "home.md",
                         skill / "docs" / "quoted.md", base / "commands" / "c.md"))


WORKSPACE_LINES = [
    "`/agent-knowledge-hub install --workspace <slug>`",
    "`/agent-knowledge-hub install skillset --workspace <slug>`",
    "`/agent-knowledge-hub install --exact`",
    "`/agent-knowledge-hub list --workspace`",
    "`/agent-knowledge-hub update --workspace <slug>`",
    "`/agent-knowledge-hub remove --workspace <slug>`",
    'claude mcp add-json --scope local <name> "$(cat \'<base>/skills/<slug>/.akh-mcp/<name>.json\')"',
    "Changed since the last install of <slug>. If you added it to this workspace before, run this from the workspace first: claude mcp remove --scope local <name>",
    "<slug> refers to ~/.claude/skills/<slug>/ in <files>, which a workspace install does not create, so those parts may not work. Install it without --workspace to use them.",
    "Stopped: this workspace's path holds characters the client does not put in commands, so nothing was written. Start the session in a folder whose path uses only letters, digits, ., _, - and /.",
    "Stopped: this session runs in your home folder, whose .claude/ is your own install, not a workspace's, so nothing was written. Start the session in a project folder, or run the command without --workspace.",
    "Stopped: this workspace's .claude/, or its skills/, commands/ or agents/ folder, is a link, is not a folder, is not yours, or could not be made, so nothing was written.",
    "Claude Code reads a workspace's .claude/skills/ folder only when a session starts, and this install made it, so the skills load in the next session you start in this workspace.",
]


class TestWorkspaceSection:
    @pytest.mark.parametrize("line", WORKSPACE_LINES)
    def test_words(self, line):
        assert line in skill_text()

    def test_every_marked_command_that_touches_the_base_takes_it_as_a_placeholder(self):
        for marker in ("akh-mcp-file", "akh-user-agent-names", "akh-workspace-modes", "akh-workspace-exclude",
                       "akh-home-paths"):
            block = command(marker)
            assert "<base>" in block, marker
            assert "~/.claude" not in block.split("\n", 2)[2], marker

    def test_no_placeholder_carries_text_from_a_skill(self):
        for marker in ("akh-workspace-modes", "akh-workspace-exclude", "akh-home-paths"):
            assert set(re.findall(r"<([a-z.]+)>", command(marker))) <= {"base", "slug", "action"}, marker

    def test_exact_install_asks_nothing(self):
        section = skill_text().split("### Install exactly what was confirmed", 1)[1].split("\n---", 1)[0].lower()
        assert "(y/n)" not in section and "confirm with" not in section
        assert "ask" not in section.replace("asks nothing", "")



@each_python
class TestMcpFileModesAndSpellings:
    def test_written_without_group_write_under_umask_002(self, python, tmp_path):
        base = tmp_path / "proj" / ".claude"
        servers = [{"name": "akh-plain", "command": "/bin/true"}]
        result, target = run_mcp_file(python, tmp_path, "akh-plain", servers, base=base, umask=0o002)
        assert result.returncode == 0, result.stderr
        assert mode(target) == 0o644 and mode(target.parent) == 0o755

    @pytest.mark.parametrize("value", ["${HOME}/.claude//skills/s/run.sh", "${HOME}/.claude/./skills/s/run.sh",
                                       "/x:${HOME}/.claude/skills/s"])
    def test_other_spellings_of_the_home_skills_folder_are_refused(self, python, tmp_path, value):
        base = tmp_path / "proj" / ".claude"
        result, target = run_mcp_file(python, tmp_path, "akh-home", [{"name": "akh-home", "command": "/bin/sh",
                                                                       "args": [value]}], base=base)
        assert result.returncode == 1 and not target.exists()


def run_component_check(tmp_path: Path, plugin: dict, files=()):
    root = tmp_path / "repo" / "plug"
    root.mkdir(parents=True, exist_ok=True)
    for f in files:
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        (root / f).write_text("x")
    (root / "plugin.json").write_text(_json.dumps(plugin))
    return run_marked("akh-component-check", tmp_path, dir=str(tmp_path),
                      **{"plugin.json": str(root / "plugin.json")}).stdout.strip().splitlines()


class TestComponentCheck:
    def test_listed_files_are_printed(self, tmp_path):
        lines = run_component_check(tmp_path, {"commands": ["commands/a.md"], "agents": "agents"},
                                    files=["commands/a.md", "agents/r.md", "agents/notes.txt"])
        assert lines == ["akh-component: ok command commands/a.md", "akh-component: ok agent agents/r.md"]

    @pytest.mark.parametrize("name", ["commands/x'$(touch m)'.md", "commands/a b.md", "../escape.md",
                                      "/etc/passwd", "commands/ .md"])
    def test_a_path_the_client_does_not_put_in_commands_is_refused(self, tmp_path, name):
        marker = tmp_path / "m"
        lines = run_component_check(tmp_path, {"commands": [name]})
        assert lines == ["akh-component: refused command"]
        assert not marker.exists()

    @pytest.mark.parametrize("name", ["sub/etc/passwd", "sub", "-rf.md", "commands/-x.md", "commands/.hidden.md"])
    def test_a_path_through_a_link_or_starting_with_a_dash_or_dot_is_refused(self, tmp_path, name):
        root = tmp_path / "repo" / "plug"
        root.mkdir(parents=True)
        (root / "sub").symlink_to("/")
        lines = run_component_check(tmp_path, {"commands": [name]})
        assert lines == ["akh-component: refused command"]

    def test_a_link_inside_the_plugin_root_is_not_followed_either(self, tmp_path):
        root = tmp_path / "repo" / "plug"
        (root / "commands").mkdir(parents=True)
        (root / "commands" / "a.md").write_text("x")
        (root / "alias").symlink_to(root / "commands")
        assert run_component_check(tmp_path, {"commands": ["alias/a.md"]}) == ["akh-component: refused command"]

    def test_an_agent_folder_entry_with_a_bad_name_is_refused(self, tmp_path):
        lines = run_component_check(tmp_path, {"agents": "agents"}, files=["agents/ok.md", "agents/b'd.md"])
        assert lines == ["akh-component: refused agent", "akh-component: ok agent agents/ok.md"]

    def test_a_plugin_root_reached_through_a_link_is_refused(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "plugin.json").write_text(_json.dumps({"commands": ["evil.md"]}))
        (outside / "evil.md").write_text("x")
        (tmp_path / "repo").mkdir()
        (tmp_path / "repo" / ".claude-plugin").symlink_to(outside)
        out = run_marked("akh-component-check", tmp_path, dir=str(tmp_path),
                         **{"plugin.json": str(tmp_path / "repo" / ".claude-plugin" / "plugin.json")})
        assert out.stdout.strip() == "akh-component: refused root"

    def test_a_plugin_root_linked_inside_the_clone_is_refused_too(self, tmp_path):
        real = tmp_path / "repo" / "real"
        real.mkdir(parents=True)
        (real / "plugin.json").write_text(_json.dumps({"commands": ["a.md"]}))
        (real / "a.md").write_text("x")
        (tmp_path / "repo" / ".claude-plugin").symlink_to(real)
        out = run_marked("akh-component-check", tmp_path, dir=str(tmp_path),
                         **{"plugin.json": str(tmp_path / "repo" / ".claude-plugin" / "plugin.json")})
        assert out.stdout.strip() == "akh-component: refused root"

    def test_a_plugin_json_that_is_a_link_is_refused(self, tmp_path):
        shared = tmp_path / "shared.json"
        shared.write_text(_json.dumps({"commands": ["c.md"]}))
        root = tmp_path / "repo" / "plug"
        root.mkdir(parents=True)
        (root / "c.md").write_text("x")
        (root / "plugin.json").symlink_to(shared)
        out = run_marked("akh-component-check", tmp_path, dir=str(tmp_path), **{"plugin.json": str(root / "plugin.json")})
        assert out.stdout.strip() == "akh-component: refused root"

    def test_unreadable_plugin_json(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        (root / "plugin.json").write_text("{")
        out = run_marked("akh-component-check", tmp_path, dir=str(tmp_path), **{"plugin.json": str(root / "plugin.json")})
        assert out.stdout.strip() == "akh-component: unreadable"


MORE_LINES = [
    "Stopped: <path> can be changed by other accounts (group or other write), so a skill installed below it could be too, and nothing was written. Run chmod go-w <path> and run the command again.",
    "Not installed: <path> in <slug>'s folder is a link, or belongs to another account, which /agent-knowledge-hub never writes, so the folder was removed and nothing else was written.",
    "Left out: a <command | agent> of <slug> whose file name holds characters /agent-knowledge-hub does not pass to a command. Tell the skill's submitter.",
]


@pytest.mark.parametrize("line", MORE_LINES)
def test_security_lines(line):
    assert line in skill_text()


def test_the_exact_list_is_written_without_a_shell():
    section = skill_text().split("### Install exactly what was confirmed", 1)[1].split("\n---", 1)[0]
    assert "here-document" not in section
    assert "file-writing tool" in section and "the user's own message" in section


def test_destructive_steps_name_the_base():
    text = skill_text()
    update = text.split("### Update", 1)[1].split("\n### ", 1)[0]
    remove = text.split("### Remove", 1)[1].split("\n### ", 1)[0]
    for section in (update, remove):
        assert "<base>/skills/<slug>" in section
        assert "~/.claude/skills/<slug>" not in section



def run_copy(tmp_path: Path, skill_path: str, umask: int | None = None):
    target = tmp_path / "proj" / ".claude" / "skills" / "x"
    target.parent.mkdir(parents=True, exist_ok=True)
    return run_marked("akh-copy-skill", tmp_path, umask=umask, dir=str(tmp_path / "d"), skill_path=skill_path,
                      target=str(target), step="copy"), target


class TestCopySkill:
    def make_repo(self, tmp_path: Path) -> Path:
        src = tmp_path / "d" / "repo" / "skills" / "x"
        (src / "bin").mkdir(parents=True)
        (src / "SKILL.md").write_text("x")
        (src / "bin" / "run.sh").write_text("x")
        _os.chmod(src / "bin" / "run.sh", 0o775)
        (src / "x'$(touch akh-pwned)'").write_text("data")
        for reserved in (".claude-plugin", ".akh-mcp"):
            (src / reserved).mkdir()
            (src / reserved / "f").write_text("x")
        (src / ".installed-manifest.json").write_text("{}")
        (src / "link").symlink_to("/etc/passwd")
        (src / "dirlink").symlink_to(tmp_path)
        _os.mkfifo(src / "fifo")
        return src

    def test_files_are_copied_and_links_reserved_names_and_specials_left_out(self, tmp_path):
        self.make_repo(tmp_path)
        result, target = run_copy(tmp_path, "/skills/x", umask=0o002)
        lines = result.stdout.strip().splitlines()
        assert lines[-1] == "akh-copy: ok", result.stderr
        assert sorted(lines[:-1]) == sorted([
            "akh-copy: left out .akh-mcp", "akh-copy: left out .claude-plugin", "akh-copy: left out .installed-manifest.json",
            "akh-copy: left out dirlink", "akh-copy: left out fifo", "akh-copy: left out link"])
        assert sorted(p.name for p in target.iterdir()) == ["SKILL.md", "bin", "x'$(touch akh-pwned)'"]
        assert mode(target / "bin" / "run.sh") == 0o755 and mode(target / "SKILL.md") == 0o644
        assert mode(target) == 0o755 and mode(target / "bin") == 0o755
        assert not (tmp_path / "akh-pwned").exists()

    def test_a_skill_path_through_a_link_is_refused(self, tmp_path):
        repo = tmp_path / "d" / "repo"
        repo.mkdir(parents=True)
        (repo / "sub").symlink_to(tmp_path)
        (tmp_path / "skills" / "x").mkdir(parents=True)
        result, target = run_copy(tmp_path, "/sub/skills/x")
        assert result.stdout.strip() == "akh-copy: refused path"
        assert not target.exists()

    def test_a_link_inside_the_clone_is_not_followed_either(self, tmp_path):
        repo = tmp_path / "d" / "repo"
        (repo / "real" / "x").mkdir(parents=True)
        (repo / "real" / "x" / "SKILL.md").write_text("x")
        (repo / "alias").symlink_to(repo / "real")
        result, target = run_copy(tmp_path, "/alias/x")
        assert result.stdout.strip() == "akh-copy: refused path"
        assert not target.exists()

    def test_check_reports_without_writing(self, tmp_path):
        self.make_repo(tmp_path)
        target = tmp_path / "proj" / ".claude" / "skills" / "x"
        r = run_marked("akh-copy-skill", tmp_path, dir=str(tmp_path / "d"), skill_path="/skills/x",
                       target=str(target), step="check")
        assert r.stdout.strip() == "akh-copy: ok" and not target.exists()

    def test_a_missing_parent_folder_is_made(self, tmp_path):
        self.make_repo(tmp_path)
        target = tmp_path / "home" / ".claude" / "skills" / "x"
        r = run_marked("akh-copy-skill", tmp_path, umask=0o002, dir=str(tmp_path / "d"), skill_path="/skills/x",
                       target=str(target), step="copy")
        assert r.stdout.strip().splitlines()[-1] == "akh-copy: ok", r.stderr
        assert mode(target.parent) == 0o755

    def test_a_tree_at_the_depth_limit_is_copied(self, tmp_path):
        src = tmp_path / "d" / "repo" / "skills" / "x"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("x")
        deep = src.joinpath(*["a"] * 64)
        deep.mkdir(parents=True)
        (deep / "f").write_text("x")
        result, target = run_copy(tmp_path, "/skills/x")
        assert result.stdout.strip() == "akh-copy: ok", result.stderr
        assert target.joinpath(*["a"] * 64, "f").read_text() == "x"

    def test_a_failed_copy_leaves_nothing(self, tmp_path):
        src = self.make_repo(tmp_path)
        (src / "zz-unreadable").write_text("x")
        _os.chmod(src / "zz-unreadable", 0)
        result, target = run_copy(tmp_path, "/skills/x")
        assert result.stdout.strip() == "akh-copy: failed"
        assert not target.exists()

    def test_the_clone_s_own_git_folder_is_left_out(self, tmp_path):
        repo = tmp_path / "d" / "repo"
        (repo / ".git" / "objects").mkdir(parents=True)
        (repo / "SKILL.md").write_text("x")
        result, target = run_copy(tmp_path, "/")
        assert result.stdout.strip() == "akh-copy: ok"
        assert sorted(p.name for p in target.iterdir()) == ["SKILL.md"]

    def test_a_missing_skill_path(self, tmp_path):
        (tmp_path / "d" / "repo").mkdir(parents=True)
        result, target = run_copy(tmp_path, "/nothere")
        assert result.stdout.strip() == "akh-copy: missing"

    def test_an_existing_target_is_not_written(self, tmp_path):
        self.make_repo(tmp_path)
        target = tmp_path / "proj" / ".claude" / "skills" / "x"
        target.mkdir(parents=True)
        result, _ = run_copy(tmp_path, "/skills/x")
        assert result.stdout.strip() == "akh-copy: exists"
        assert list(target.iterdir()) == []


def run_remove(tmp_path: Path, base: Path, slug: str = "x"):
    return run_marked("akh-remove", tmp_path, base=str(base), slug=slug).stdout.strip().splitlines()


class TestRemove:
    def test_listed_files_and_the_skill_folder_are_deleted(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        installed(base, commands=["commands/c.md"], agents=["agents/a.md"])
        assert run_remove(tmp_path, base) == ["akh-remove: done"]
        assert not (base / "commands" / "c.md").exists() and not (base / "agents" / "a.md").exists()
        assert not (base / "skills" / "x").exists()

    def test_an_entry_from_an_earlier_client_is_read_after_its_last_claude(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        installed(base, commands=["commands/c.md"])
        manifest(base, "x", commands=["/somewhere/.claude/commands/c.md"])
        assert run_remove(tmp_path, base) == ["akh-remove: done"]
        assert not (base / "commands" / "c.md").exists()

    def test_a_hostile_entry_is_kept_and_never_reaches_a_shell(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        name = "commands/x'$(touch akh-pwned)'.md"
        installed(base, commands=[name])
        assert run_remove(tmp_path, base) == ["akh-remove: kept commands/x'$(touch akh-pwned)'.md", "akh-remove: done"]
        assert (base / name).exists() and not (tmp_path / "akh-pwned").exists()

    def test_an_entry_through_a_link_or_outside_the_base_is_kept(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "c.md").write_text("mine")
        installed(base, agents=["agents/a.md"])
        (base / "commands").symlink_to(outside)
        manifest(base, "x", commands=["commands/c.md"], agents=["agents/a.md", "agents/../../escape.md", "skills/y"])
        lines = run_remove(tmp_path, base)
        assert lines == ["akh-remove: kept commands/c.md", "akh-remove: kept agents/../../escape.md",
                         "akh-remove: kept skills/y", "akh-remove: done"]
        assert (outside / "c.md").read_text() == "mine"

    def test_a_skill_folder_that_is_a_link_loses_only_the_link(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        (base / "skills").mkdir(parents=True)
        victim = tmp_path / "victim"
        victim.mkdir()
        (victim / "keep").write_text("x")
        (base / "skills" / "x").symlink_to(victim)
        assert run_remove(tmp_path, base) == ["akh-remove: done"]
        assert not (base / "skills" / "x").is_symlink() and (victim / "keep").exists()


def test_fixed_commands_do_the_copy_and_the_deletes():
    text = skill_text()
    install = text.split("### Install\n", 1)[1].split("\n### ", 1)[0]
    update = text.split("### Update", 1)[1].split("\n### ", 1)[0]
    remove = text.split("### Remove", 1)[1].split("\n### ", 1)[0]
    assert "akh-copy-skill" in install
    assert "akh-remove" in update and "akh-remove" in remove
    assert "akh-workspace-exclude" in update



class TestSlugsAndManifests:
    @pytest.mark.parametrize("slug", ["..", ".", "a/b", "", "X"])
    def test_remove_refuses_a_slug_that_is_not_a_catalog_slug(self, tmp_path, slug):
        base = tmp_path / "proj" / ".claude"
        installed(base)
        (base / "settings.json").write_text("{}")
        assert run_remove(tmp_path, base, slug) == ["akh-remove: refused slug"]
        assert (base / "settings.json").exists() and (base / "skills" / "x").exists()

    @pytest.mark.parametrize("marker", ["akh-workspace-modes", "akh-home-paths"])
    def test_other_commands_refuse_such_a_slug(self, tmp_path, marker):
        base = tmp_path / "proj" / ".claude"
        installed(base)
        out = run_marked(marker, tmp_path, base=str(base), slug="..").stdout.strip()
        assert out == "akh-workspace: refused slug"

    def test_exclude_refuses_such_a_slug(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        installed(repo / ".claude")
        out = run_marked("akh-workspace-exclude", tmp_path, base=str(repo / ".claude"), slug="..", action="add")
        assert out.stdout.strip() == "akh-workspace: refused slug"

    @pytest.mark.parametrize("content", ['["commands/c.md"]', '{"commands": "ab"}', '{"agents": null}', "{"])
    def test_remove_keeps_everything_for_a_manifest_it_cannot_read(self, tmp_path, content):
        base = tmp_path / "proj" / ".claude"
        installed(base, commands=["commands/c.md"])
        (base / "skills" / "x" / ".installed-manifest.json").write_text(content)
        assert run_remove(tmp_path, base) == ["akh-remove: unreadable"]
        assert (base / "skills" / "x").exists() and (base / "commands" / "c.md").exists()

    def test_a_manifest_that_is_a_link_is_not_read(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        installed(base, commands=["commands/c.md"])
        m = base / "skills" / "x" / ".installed-manifest.json"
        m.unlink()
        m.symlink_to("/dev/zero")
        assert run_remove(tmp_path, base) == ["akh-remove: unreadable"]
        assert (base / "commands" / "c.md").exists()

    def test_a_manifest_linked_to_a_readable_file_is_not_read(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        installed(base, commands=["commands/c.md"])
        forged = tmp_path / "forged.json"
        forged.write_text(_json.dumps({"commands": ["commands/c.md"], "agents": []}))
        m = base / "skills" / "x" / ".installed-manifest.json"
        m.unlink()
        m.symlink_to(forged)
        assert run_remove(tmp_path, base) == ["akh-remove: unreadable"]
        assert (base / "commands" / "c.md").exists()

    def test_an_exclude_file_keeps_its_line_endings(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        info = repo / ".git" / "info" / "exclude"
        info.write_bytes(b"/a/\r\n/b\rc/\r\n")
        base = repo / ".claude"
        installed(base)
        run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="remove")
        assert info.read_bytes() == b"/a/\r\n/b\rc/\r\n"



@each_python
def test_mcp_file_never_reads_a_linked_plugin_json(python, tmp_path):
    shared = tmp_path / "shared.json"
    shared.write_text(_json.dumps({"name": "s", "mcp-servers": [{"name": "akh-evil", "command": "sh", "args": ["-c", "id"]}]}))
    bindir = tmp_path / "pybin"
    bindir.mkdir(exist_ok=True)
    if not (bindir / "python3").exists():
        (bindir / "python3").symlink_to(python)
    link = tmp_path / "plugin.json"
    link.symlink_to(shared)
    base = tmp_path / ".claude"
    cmd = (command("akh-mcp-file").replace("<plugin.json>", str(link)).replace("<name>", "akh-evil")
           .replace("<slug>", "s").replace("<base>", str(base)))
    result = subprocess.run(["/bin/sh", "-c", cmd], env={"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path)},
                            capture_output=True, timeout=20)
    assert result.returncode == 2
    assert not (base / "skills" / "s" / ".akh-mcp" / "akh-evil.json").exists()


class TestTreesAndSteps:
    def test_a_tree_deeper_than_the_limit_is_refused_at_check(self, tmp_path):
        src = tmp_path / "d" / "repo" / "skills" / "x"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("x")
        deep = str(src)
        for _ in range(65):
            deep = _os.path.join(deep, "a")
            _os.mkdir(deep)
        target = tmp_path / "proj" / ".claude" / "skills" / "x"
        for step in ("check", "copy"):
            r = run_marked("akh-copy-skill", tmp_path, dir=str(tmp_path / "d"), skill_path="/skills/x",
                           target=str(target), step=step)
            assert r.stdout.strip() == "akh-copy: refused tree"
        assert not target.exists()

    def test_a_path_longer_than_the_limit_is_refused(self, tmp_path):
        src = tmp_path / "d" / "repo" / "skills" / "x"
        src.mkdir(parents=True)
        (src / ("n" * 200)).mkdir()
        deep = src / ("n" * 200)
        for _ in range(5):
            deep = deep / ("m" * 200)
            deep.mkdir()
        target = tmp_path / "proj" / ".claude" / "skills" / "x"
        r = run_marked("akh-copy-skill", tmp_path, dir=str(tmp_path / "d"), skill_path="/skills/x",
                       target=str(target), step="check")
        assert r.stdout.strip() == "akh-copy: refused tree"

    def test_an_unknown_step_is_refused(self, tmp_path):
        (tmp_path / "d" / "repo" / "skills" / "x").mkdir(parents=True)
        target = tmp_path / "proj" / ".claude" / "skills" / "x"
        r = run_marked("akh-copy-skill", tmp_path, dir=str(tmp_path / "d"), skill_path="/skills/x",
                       target=str(target), step="Copy")
        assert r.stdout.strip() == "akh-copy: refused step"

    def test_a_skills_path_that_is_a_file_fails(self, tmp_path):
        src = tmp_path / "d" / "repo" / "skills" / "x"
        src.mkdir(parents=True)
        (src / "SKILL.md").write_text("x")
        base = tmp_path / "proj" / ".claude"
        base.mkdir(parents=True)
        (base / "skills").write_text("not a folder")
        r = run_marked("akh-copy-skill", tmp_path, dir=str(tmp_path / "d"), skill_path="/skills/x",
                       target=str(base / "skills" / "x"), step="copy")
        assert r.stdout.strip() == "akh-copy: failed"

    def test_the_git_folder_is_left_out_for_a_dot_skill_path(self, tmp_path):
        repo = tmp_path / "d" / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "SKILL.md").write_text("x")
        result, target = run_copy(tmp_path, "/.")
        assert result.stdout.strip() == "akh-copy: ok"
        assert sorted(p.name for p in target.iterdir()) == ["SKILL.md"]

    def test_remove_deletes_a_deep_tree(self, tmp_path):
        base = tmp_path / "proj" / ".claude"
        installed(base)
        deep = str(base / "skills" / "x")
        for _ in range(1100):
            deep = _os.path.join(deep, "a")
            _os.mkdir(deep)
        assert run_remove(tmp_path, base) == ["akh-remove: done"]
        assert not (base / "skills" / "x").exists()

    def test_exclude_changes_nothing_for_a_manifest_it_cannot_read(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        git("init", "-q", cwd=repo)
        base = repo / ".claude"
        installed(base)
        run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="add")
        before = (repo / ".git" / "info" / "exclude").read_bytes()
        (base / "skills" / "x" / ".installed-manifest.json").write_text("[]")
        r = run_marked("akh-workspace-exclude", tmp_path, base=str(base), slug="x", action="remove")
        assert r.stdout.strip() == "akh-workspace: unreadable"
        assert (repo / ".git" / "info" / "exclude").read_bytes() == before


def test_python_blocks_use_nothing_newer_than_python_3_6():
    # The commands run under whatever python3 is first on PATH; RHEL 8's is 3.6.8, which lacks these
    # (checked on sdfiana008, 2026-10-16: every block compiles and runs there).
    for block in fenced_blocks(skill_text()):
        if block.startswith("python3 "):
            for newer in ("capture_output", "text=True", ":=", "removeprefix", "removesuffix", "is_relative_to"):
                assert newer not in block, (newer, block.splitlines()[1])
