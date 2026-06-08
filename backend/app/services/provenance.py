"""Provenance service for #014 — builds fork/upstream/supersession tree."""
from __future__ import annotations

import logging
from typing import List, Optional

from beanie.operators import In

from app.models.skill import Skill, SkillStatus, VisibilityEnum
from app.schemas.provenance import ProvenanceNode, ProvenanceTree
from app.services.github import GitHubFetchError, _normalize_github_url, github_fetcher

logger = logging.getLogger(__name__)

MAX_UPSTREAM_HOPS = 3
MAX_SUPERSESSION_HOPS = 10
MAX_FORKS_PER_LEVEL = 20
MAX_FORKS_DISPLAY = 5


def _redact_node(slug: str, name: str, repo_url: str) -> ProvenanceNode:
    return ProvenanceNode(
        slug=None,
        name="[internal skill]",
        repo_url=repo_url,
        in_catalog=True,
        visibility="internal",
    )


def _skill_to_node(skill: Skill, viewer_authenticated: bool) -> ProvenanceNode:
    if skill.visibility == VisibilityEnum.internal and not viewer_authenticated:
        return _redact_node(skill.slug, skill.name, skill.repo_url)
    return ProvenanceNode(
        slug=skill.slug,
        name=skill.name,
        repo_url=skill.repo_url,
        in_catalog=True,
        visibility=skill.visibility.value,
        submitter_id=skill.submitter_id,
        github_stars=skill.github_stars,
        avg_rating=skill.avg_rating if skill.avg_rating > 0 else None,
        last_commit_at=skill.last_commit_at,
        status=skill.status.value,
    )


async def _resolve_upstream(
    forked_from_url: Optional[str],
    viewer_authenticated: bool,
    visited_slugs: set,
    external_fetches_remaining: list,  # mutable counter: [remaining]
) -> List[ProvenanceNode]:
    """Walk the upstream chain up to MAX_UPSTREAM_HOPS."""
    chain: List[ProvenanceNode] = []
    url = _normalize_github_url(forked_from_url) if forked_from_url else None

    for _ in range(MAX_UPSTREAM_HOPS):
        if not url:
            break

        # Try to find a catalog skill with this repo_url
        # Prefer skill_path="/" (root), fall back to oldest by submitted_at
        candidates = await Skill.find(Skill.repo_url == url).sort([("submitted_at", 1)]).to_list()
        # Exclude local source_type skills (their repo_url starts with "local://")
        candidates = [c for c in candidates if c.source_type != "local"]

        catalog_match: Optional[Skill] = None
        for c in candidates:
            if c.skill_path == "/":
                catalog_match = c
                break
        if catalog_match is None and candidates:
            catalog_match = candidates[0]

        if catalog_match:
            if catalog_match.slug in visited_slugs:
                break  # cycle detected
            visited_slugs.add(catalog_match.slug)
            chain.append(_skill_to_node(catalog_match, viewer_authenticated))
            url = _normalize_github_url(catalog_match.forked_from_url) if catalog_match.forked_from_url else None
        else:
            # External (non-catalog) node — fetch metadata best-effort
            node_data: dict = {"slug": None, "name": url.split("/")[-1] if "/" in url else url, "repo_url": url, "in_catalog": False}
            if external_fetches_remaining[0] > 0:
                external_fetches_remaining[0] -= 1
                try:
                    gh = await github_fetcher.fetch(url)
                    node_data["name"] = gh.name
                    node_data["github_stars"] = gh.stars
                    node_data["last_commit_at"] = gh.last_commit_at
                except GitHubFetchError:
                    pass  # null metadata — degrade gracefully
            chain.append(ProvenanceNode(**node_data))
            break  # can't follow further from external node

    return chain


async def _resolve_forks(
    skill: Skill, viewer_authenticated: bool
) -> tuple[List[ProvenanceNode], bool, int]:
    """Return (level1_nodes_capped, forks_truncated, total_fork_count)."""
    level1 = (
        await Skill.find(Skill.forked_from_url == skill.repo_url)
        .sort([("github_stars", -1)])
        .limit(MAX_FORKS_PER_LEVEL)
        .to_list()
    )
    # total_fork_count is approximate (we only fetched up to MAX_FORKS_PER_LEVEL)
    total_fork_count = await Skill.find(Skill.forked_from_url == skill.repo_url).count()
    forks_truncated = total_fork_count > MAX_FORKS_DISPLAY

    # Batch level-2 forks in a single $in query
    l1_repo_urls = [f.repo_url for f in level1 if f.repo_url]
    level2_by_parent: dict[str, List[Skill]] = {url: [] for url in l1_repo_urls}
    if l1_repo_urls:
        level2_all = (
            await Skill.find(In(Skill.forked_from_url, l1_repo_urls))
            .sort([("github_stars", -1)])
            .to_list()
        )
        for f2 in level2_all:
            if f2.forked_from_url in level2_by_parent:
                level2_by_parent[f2.forked_from_url].append(f2)

    nodes: List[ProvenanceNode] = []
    for f in level1:
        node = _skill_to_node(f, viewer_authenticated)
        l2_skills = level2_by_parent.get(f.repo_url, [])
        node.forks = [_skill_to_node(f2, viewer_authenticated) for f2 in l2_skills]
        nodes.append(node)

    return nodes, forks_truncated, total_fork_count


async def _resolve_supersession(
    skill: Skill, viewer_authenticated: bool
) -> List[ProvenanceNode]:
    """Follow superseded_by_slug links up to MAX_SUPERSESSION_HOPS."""
    chain: List[ProvenanceNode] = []
    visited: set = {skill.slug}
    current_slug = skill.superseded_by_slug

    for _ in range(MAX_SUPERSESSION_HOPS):
        if not current_slug:
            break
        if current_slug in visited:
            break  # cycle detected
        visited.add(current_slug)

        s = await Skill.find_one(Skill.slug == current_slug)
        if not s:
            break
        chain.append(_skill_to_node(s, viewer_authenticated))
        current_slug = s.superseded_by_slug

    return chain


async def build_tree(skill: Skill, viewer_authenticated: bool) -> ProvenanceTree:
    """Build the full provenance tree for a skill."""
    visited_slugs: set = {skill.slug}
    external_fetches_remaining = [1]  # cap: max 1 external GitHub metadata fetch

    upstream = await _resolve_upstream(
        skill.forked_from_url,
        viewer_authenticated,
        visited_slugs,
        external_fetches_remaining,
    )
    forks, forks_truncated, total_fork_count = await _resolve_forks(skill, viewer_authenticated)
    supersession = await _resolve_supersession(skill, viewer_authenticated)

    if not upstream and not forks and not supersession:
        subject = _skill_to_node(skill, viewer_authenticated)
        return ProvenanceTree(empty=True, subject=subject)

    subject = _skill_to_node(skill, viewer_authenticated)
    subject.forks = forks
    subject.forks_truncated = forks_truncated
    subject.total_fork_count = total_fork_count

    return ProvenanceTree(
        empty=False,
        subject=subject,
        upstream=upstream,
        supersession=supersession,
    )
