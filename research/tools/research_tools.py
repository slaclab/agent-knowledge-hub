"""
research_tools.py — Programmatic Tool Calling executor for the AKH research workspace.

Implements the eight tools defined in research/tools/schemas/ as Python functions.
Designed for use via Claude's Programmatic Tool Calling pattern: Claude writes Python
code that imports and calls these functions; intermediate results stay in the execution
environment and never enter the context window as prose.

Usage (from Claude-generated Python):
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from research_tools import search_concepts, get_concept, list_topics, blast_radius

    results = search_concepts("SkillNet skill registry", limit=5)
    concept  = get_concept("skillnet")
    topics   = list_topics(status="todo")
    priority = blast_radius(["npm", "PyPI", "registry"])

All functions return plain dicts or lists of dicts — never prose strings intended for
display. Callers can filter, transform, or pass results into further tool calls without
consuming context tokens on intermediate text.

Root detection: functions locate the research/ directory relative to this file's location,
so they work regardless of where Python is invoked from.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

_TOOLS_DIR   = Path(__file__).parent.resolve()
_RESEARCH_DIR = _TOOLS_DIR.parent.resolve()          # research/
_CONCEPTS_DIR = _RESEARCH_DIR / "concepts"
_REPORTS_DIR  = _RESEARCH_DIR / "reports"
_CHARGES_DIR  = _RESEARCH_DIR / "charges"
_TOPICS_FILE  = _RESEARCH_DIR / "TOPICS.md"
_README_FILE  = _RESEARCH_DIR / "README.md"
_CHARGE_FILE  = _RESEARCH_DIR / "CHARGE.md"

_BLAST_RADIUS_PY  = Path.home() / ".claude/skills/research-workflow/tools/blast-radius.py"
_PRIORITY_AUDIT_PY = Path.home() / ".claude/skills/research-workflow/tools/priority-audit.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kebab(s: str) -> str:
    """Normalise a name to kebab-case for file matching."""
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _snippet(content: str, length: int = 160) -> str:
    """Return first non-empty non-heading line, truncated."""
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith(">") and not line.startswith("---"):
            return line[:length] + ("..." if len(line) > length else "")
    return content[:length]


def _keyword_score(content: str, keywords: list[str]) -> int:
    """Count how many distinct keywords appear in content (case-insensitive)."""
    lower = content.lower()
    return sum(1 for kw in keywords if kw.lower() in lower)


def _fuzzy_find(name: str, directory: Path) -> tuple[Path | None, list[Path]]:
    """
    Find the best-matching .md file in directory for the given name.
    Returns (best_match, alternatives).
    """
    if not directory.exists():
        return None, []

    target = _kebab(name)
    candidates = sorted(directory.glob("*.md"))

    # Exact slug match
    for p in candidates:
        if p.stem == target:
            return p, []

    # Substring match
    matches = [p for p in candidates if target in p.stem or p.stem in target]
    if len(matches) == 1:
        return matches[0], []
    if len(matches) > 1:
        return matches[0], matches[1:]

    # Keyword token match (any token from name appears in filename)
    tokens = [t for t in re.split(r"[\s\-_]+", name.lower()) if len(t) > 2]
    token_matches = [p for p in candidates if any(t in p.stem for t in tokens)]
    if token_matches:
        return token_matches[0], token_matches[1:]

    return None, []


def _parse_topics() -> list[dict[str, Any]]:
    """Parse TOPICS.md rows into a list of dicts."""
    if not _TOPICS_FILE.exists():
        return []

    rows = []
    in_table = False
    for line in _TOPICS_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("| priority") or stripped.startswith("|---"):
            in_table = True
            continue
        if not stripped.startswith("|"):
            if in_table and stripped == "":
                continue
            in_table = False
            continue
        if not in_table:
            continue

        parts = [p.strip() for p in stripped.strip("|").split("|")]
        if len(parts) < 6:
            continue

        priority_raw, status_raw, type_raw, topic, researched, notes = (
            parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        )

        # Extract emoji priority
        priority = "P3"
        if "P1" in priority_raw:
            priority = "P1"
        elif "P2" in priority_raw:
            priority = "P2"

        # Extract status keyword
        status = "unknown"
        for kw, label in [("done", "done"), ("in-progress", "in-progress"),
                          ("blocked", "blocked"), ("deferred", "deferred"), ("todo", "todo")]:
            if kw in status_raw:
                status = label
                break

        rows.append({
            "priority": priority,
            "status": status,
            "type": type_raw if type_raw in ("concept", "report") else "other",
            "topic": topic,
            "researched": None if researched == "—" else researched or None,
            "notes": notes,
        })

    return rows


# ---------------------------------------------------------------------------
# Read / discovery tools
# ---------------------------------------------------------------------------

def search_concepts(query: str, limit: int = 5) -> dict[str, Any]:
    """
    Keyword search across research/concepts/ files.

    Returns:
        {"matches": [...], "total": int}
        Each match: {"file": str, "score": int, "matched_keywords": [...], "snippet": str}
    """
    keywords = query.split()
    results = []

    for path in sorted(_CONCEPTS_DIR.glob("*.md")):
        content = _read_md(path)
        matched = [kw for kw in keywords if kw.lower() in content.lower()]
        if matched:
            results.append({
                "file": str(path.relative_to(_RESEARCH_DIR.parent)),
                "score": len(matched),
                "matched_keywords": matched,
                "snippet": _snippet(content),
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"matches": results[:limit], "total": len(results)}


def search_reports(query: str, limit: int = 5) -> dict[str, Any]:
    """
    Keyword search across research/reports/ files.

    Returns:
        {"matches": [...], "total": int}
    """
    keywords = query.split()
    results = []

    for path in sorted(_REPORTS_DIR.glob("*.md")):
        content = _read_md(path)
        matched = [kw for kw in keywords if kw.lower() in content.lower()]
        if matched:
            results.append({
                "file": str(path.relative_to(_RESEARCH_DIR.parent)),
                "score": len(matched),
                "matched_keywords": matched,
                "snippet": _snippet(content),
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return {"matches": results[:limit], "total": len(results)}


def get_concept(name: str) -> dict[str, Any]:
    """
    Read a concept file in full by name (kebab slug or fuzzy match).

    Returns:
        {"found": bool, "path": str|None, "content": str|None, "alternatives": [...]}
    """
    path, alternatives = _fuzzy_find(name, _CONCEPTS_DIR)
    if path is None:
        return {"found": False, "path": None, "content": None, "alternatives": []}
    return {
        "found": True,
        "path": str(path.relative_to(_RESEARCH_DIR.parent)),
        "content": _read_md(path),
        "alternatives": [str(p.relative_to(_RESEARCH_DIR.parent)) for p in alternatives],
    }


def get_report(name: str) -> dict[str, Any]:
    """
    Read a report file in full by name (kebab slug or fuzzy match).

    Returns:
        {"found": bool, "path": str|None, "content": str|None, "alternatives": [...]}
    """
    path, alternatives = _fuzzy_find(name, _REPORTS_DIR)
    if path is None:
        return {"found": False, "path": None, "content": None, "alternatives": []}
    return {
        "found": True,
        "path": str(path.relative_to(_RESEARCH_DIR.parent)),
        "content": _read_md(path),
        "alternatives": [str(p.relative_to(_RESEARCH_DIR.parent)) for p in alternatives],
    }


def list_topics(status: str = "all", type_: str = "all") -> dict[str, Any]:
    """
    Return TOPICS.md as structured JSON, with optional filtering.

    Args:
        status: "todo"|"in-progress"|"blocked"|"deferred"|"done"|"all"
        type_:  "concept"|"report"|"all"

    Returns:
        {"topics": [...], "total": int}
    """
    rows = _parse_topics()

    if status != "all":
        rows = [r for r in rows if r["status"] == status]
    if type_ != "all":
        rows = [r for r in rows if r["type"] == type_]

    return {"topics": rows, "total": len(rows)}


def blast_radius(keywords: list[str]) -> dict[str, Any]:
    """
    Compute blast-radius priority tier for a set of keywords.
    Wraps the existing blast-radius.py tool; returns structured dict.

    Returns:
        {"keywords": [...], "match_count": int, "priority": "P1"|"P2"|"P3",
         "affected_files": [...], "notes_snippet": str}
    """
    if not _BLAST_RADIUS_PY.exists():
        # Fallback: implement directly
        return _blast_radius_direct(keywords)

    result = subprocess.run(
        ["python3", str(_BLAST_RADIUS_PY)] + keywords,
        capture_output=True, text=True,
        cwd=str(_RESEARCH_DIR),
    )
    output = result.stdout

    # Parse human-readable output into structured form
    match_count = 0
    priority = "P3"
    affected_files: list[str] = []
    notes_snippet = ""

    for line in output.splitlines():
        if line.startswith("Matches"):
            m = re.search(r"(\d+)", line)
            if m:
                match_count = int(m.group(1))
        elif line.startswith("Priority"):
            if "P1" in line:
                priority = "P1"
            elif "P2" in line:
                priority = "P2"
            else:
                priority = "P3"
        elif line.strip().startswith("concepts/") or line.strip().startswith("reports/"):
            affected_files.append(line.strip())
        elif "referenced by" in line:
            notes_snippet = line.strip()

    return {
        "keywords": keywords,
        "match_count": match_count,
        "priority": priority,
        "affected_files": affected_files,
        "notes_snippet": notes_snippet,
    }


def _blast_radius_direct(keywords: list[str]) -> dict[str, Any]:
    """Direct implementation fallback when blast-radius.py is unavailable."""
    all_files = list(_CONCEPTS_DIR.glob("*.md")) + list(_REPORTS_DIR.glob("*.md"))
    matched_files = []

    for path in all_files:
        content = _read_md(path)
        if any(kw.lower() in content.lower() for kw in keywords):
            matched_files.append(str(path.relative_to(_RESEARCH_DIR)))

    count = len(matched_files)
    if count >= 5:
        priority = "P1"
    elif count >= 2:
        priority = "P2"
    else:
        priority = "P3"

    stems = [Path(f).stem for f in matched_files]
    notes = f"referenced by {count} file(s): " + ", ".join(f"`{s}`" for s in stems) if stems else "no existing outputs reference this topic"

    return {
        "keywords": keywords,
        "match_count": count,
        "priority": priority,
        "affected_files": matched_files,
        "notes_snippet": notes,
    }


def priority_audit(recount: bool = False) -> dict[str, Any]:
    """
    Run the priority audit and return mismatches as structured data.
    Wraps the existing priority-audit.py tool.

    Returns:
        {"mismatches": [...], "total_topics": int, "mismatch_count": int}
        Each mismatch: {"topic": str, "stored": str, "computed": str, "refs": int}
    """
    if not _PRIORITY_AUDIT_PY.exists():
        return {"error": f"priority-audit.py not found at {_PRIORITY_AUDIT_PY}", "mismatches": []}

    flags = ["--recount"] if recount else []
    result = subprocess.run(
        ["python3", str(_PRIORITY_AUDIT_PY)] + flags,
        capture_output=True, text=True,
        cwd=str(_RESEARCH_DIR),
    )
    output = result.stdout

    mismatches = []
    total_topics = 0
    for line in output.splitlines():
        m = re.match(r"Topics:\s*(\d+)", line)
        if m:
            total_topics = int(m.group(1))
            continue
        # Table rows: "Topic name   P1  P3  0  ❌ → 🔹 P3"
        m = re.match(r"^(.+?)\s+(P[123])\s+(P[123])\s+(\d+)\s+(✅|❌)", line)
        if m:
            topic_trunc, stored, computed, refs, status = m.groups()
            if status == "❌":
                mismatches.append({
                    "topic": topic_trunc.strip(),
                    "stored": stored,
                    "computed": computed,
                    "refs": int(refs),
                })

    return {
        "mismatches": mismatches,
        "total_topics": total_topics,
        "mismatch_count": len(mismatches),
    }


# ---------------------------------------------------------------------------
# Self-test (run as script to verify imports and basic function)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("research_tools.py — self-test")
    print(f"  Research dir : {_RESEARCH_DIR}")
    print(f"  Concepts dir : {_CONCEPTS_DIR} ({'exists' if _CONCEPTS_DIR.exists() else 'MISSING'})")
    print(f"  Reports dir  : {_REPORTS_DIR} ({'exists' if _REPORTS_DIR.exists() else 'MISSING'})")
    print(f"  TOPICS.md    : {'exists' if _TOPICS_FILE.exists() else 'MISSING'}")

    print("\n--- search_concepts('SkillNet') ---")
    r = search_concepts("SkillNet")
    print(json.dumps(r, indent=2))

    print("\n--- list_topics(status='todo') ---")
    r = list_topics(status="todo")
    print(json.dumps(r, indent=2))

    print("\n--- blast_radius(['SkillNet', 'skill']) ---")
    r = blast_radius(["SkillNet", "skill"])
    print(json.dumps(r, indent=2))

    print("\n--- get_concept('skillnet') ---")
    r = get_concept("skillnet")
    # Truncate content for readability
    if r.get("content"):
        r = {**r, "content": r["content"][:200] + "..."}
    print(json.dumps(r, indent=2))

    print("\nAll checks passed.")
