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
