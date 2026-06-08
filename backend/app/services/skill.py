from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import List, Literal, Optional, Tuple

import bson
import bson.errors
from cachetools import TTLCache

logger = logging.getLogger(__name__)

from beanie.operators import In, Text
from pymongo.errors import DuplicateKeyError
from slugify import slugify

from app.models.flag import SkillFlag
from app.models.label import Label, SkillLabel
from app.models.rating import Rating
from app.models.revision import RevisionAction, SkillRevision
from app.models.skill import Skill, SkillStatus, VisibilityEnum
from app.schemas.skill import SkillCreate, SkillUpdate
from app.services.github import GitHubFetchError, GitHubRef, _normalize_github_url, extract_repo_root_url, github_fetcher, github_scanner
from app.services.revision import revision_service
from app.services import label as label_module


SortField = Literal["newest", "highest_rated", "most_rated", "most_stars"]

# In-process count cache: keyed by filter fingerprint, 30s TTL, bounded at 1000 entries (LRU eviction)
_count_cache: TTLCache = TTLCache(maxsize=1000, ttl=30)

_OID_RE = re.compile(r"^[0-9a-f]{24}$")


def _encode_cursor(sv: datetime, oid: str) -> str:
    if sv.tzinfo is None:
        sv = sv.replace(tzinfo=timezone.utc)
    payload = {"sv": sv.isoformat(), "id": oid}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(token: str) -> Tuple[datetime, str]:
    """Decode and validate an opaque base64 cursor. Raises ValueError with a safe message on any failure."""
    try:
        raw = base64.b64decode(token.encode())
        data = json.loads(raw)
    except Exception:
        raise ValueError("Invalid or expired cursor")

    sv = data.get("sv")
    oid = data.get("id")

    # sv must be a non-null scalar string (submitted_at is non-nullable)
    if sv is None or not isinstance(sv, str):
        raise ValueError("Invalid or expired cursor")

    # id must match the 24-hex ObjectId regex (anchored)
    if not isinstance(oid, str) or not _OID_RE.fullmatch(oid):
        raise ValueError("Invalid or expired cursor")

    # Parse sv as a UTC datetime; assume UTC if no tz (cursor was encoded from UTC-aware datetime)
    try:
        dt = datetime.fromisoformat(sv)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except Exception:
        raise ValueError("Invalid or expired cursor")

    # Validate oid as a real ObjectId
    try:
        bson.ObjectId(oid)
    except bson.errors.InvalidId:
        raise ValueError("Invalid or expired cursor")

    return dt, oid


def _filter_fingerprint(
    q, labels, visibility, forked_from, sort, submitted_by, include_deactivated,
    platforms=None,
) -> str:
    key = json.dumps(
        [q, sorted(labels or []), visibility, forked_from, sort, submitted_by,
         include_deactivated, sorted(platforms or [])],
        sort_keys=True,
    )
    return hashlib.md5(key.encode()).hexdigest()


class DuplicateSkillError(Exception):
    def __init__(self, existing_slug: Optional[str] = None):
        self.existing_slug = existing_slug
        super().__init__("Skill already exists")


class PinNotSupportedError(Exception):
    pass


async def _unique_slug(base: str) -> str:
    slug = slugify(base)
    if not await Skill.find_one(Skill.slug == slug):
        return slug
    i = 2
    while await Skill.find_one(Skill.slug == f"{slug}-{i}"):
        i += 1
    return f"{slug}-{i}"


class SkillRepository:
    async def _build_query_parts(
        self,
        q: Optional[str],
        labels: Optional[List[str]],
        sort: SortField,
        include_deactivated: bool,
        forked_from: Optional[str],
        visibility: Optional[str],
        submitted_by: Optional[str],
    ):
        """Build and return (query_parts, early_empty) where early_empty=True means zero results."""
        query_parts = []
        if not include_deactivated:
            query_parts.append(Skill.status == SkillStatus.active)

        if submitted_by:
            query_parts.append(Skill.submitter_id == submitted_by)

        if q:
            query_parts.append({"$text": {"$search": q}})

        if forked_from:
            normalized = _normalize_github_url(forked_from)
            query_parts.append(Skill.forked_from_url == normalized)

        if visibility and visibility != "all":
            query_parts.append(Skill.visibility == VisibilityEnum(visibility))

        if labels:
            label_names = [n.strip().lower() for n in labels if n.strip()]
            label_docs = await Label.find(In(Label.name, label_names)).to_list()
            if len(label_docs) < len(label_names):
                return None, True
            label_ids = [str(l.id) for l in label_docs]
            collection = SkillLabel.get_motor_collection()
            pipeline = [
                {"$match": {"label_id": {"$in": label_ids}}},
                {"$group": {"_id": {"skill_id": "$skill_id", "label_id": "$label_id"}}},
                {"$group": {"_id": "$_id.skill_id", "cnt": {"$sum": 1}}},
                {"$match": {"cnt": len(label_ids)}},
            ]
            agg_cursor = collection.aggregate(pipeline)
            matching_skill_ids = [doc["_id"] async for doc in agg_cursor]
            if not matching_skill_ids:
                return None, True
            query_parts.append({"_id": {"$in": [
                bson.ObjectId(sid) for sid in matching_skill_ids
            ]}})

        return query_parts, False

    async def _get_total(
        self,
        base_query,
        q: Optional[str],
        labels: Optional[List[str]],
        visibility: Optional[str],
        forked_from: Optional[str],
        sort: SortField,
        submitted_by: Optional[str],
        include_deactivated: bool,
        platforms: Optional[List[str]] = None,
    ) -> int:
        """Return total count, using estimatedDocumentCount for unfiltered or cache for filtered."""
        is_filtered = bool(
            q or labels or (visibility and visibility != "all") or forked_from
            or submitted_by or include_deactivated or platforms
        )
        if not is_filtered:
            # O(1) — reads collection metadata; may slightly over-count deactivated docs
            try:
                collection = Skill.get_motor_collection()
                return await collection.estimated_document_count()
            except Exception:
                pass  # fall through to count()

        fingerprint = _filter_fingerprint(
            q, labels, visibility, forked_from, sort, submitted_by, include_deactivated, platforms
        )
        if fingerprint in _count_cache:
            return _count_cache[fingerprint]

        total = await base_query.count()
        _count_cache[fingerprint] = total
        return total

    async def list(
        self,
        q: Optional[str] = None,
        labels: Optional[List[str]] = None,
        sort: SortField = "newest",
        page: int = 1,
        page_size: int = 20,
        include_deactivated: bool = False,
        forked_from: Optional[str] = None,
        visibility: Optional[str] = None,
        submitted_by: Optional[str] = None,
        cursor: Optional[str] = None,
        platforms: Optional[List[str]] = None,
    ) -> Tuple[List[Skill], int]:
        items, total, _, _, _ = await self.list_with_cursors(
            q=q, labels=labels, sort=sort, page=page, page_size=page_size,
            include_deactivated=include_deactivated, forked_from=forked_from,
            visibility=visibility, submitted_by=submitted_by, cursor=cursor,
            platforms=platforms,
        )
        return items, total

    async def _platform_counts_aggregation(
        self,
        raw_match: dict,
    ) -> dict[str, int]:
        """Compute per-platform skill counts via $unwind + $group.

        raw_match is a plain MongoDB filter dict (no Beanie operator objects).
        """
        pipeline: list = [{"$match": raw_match}] if raw_match else []
        pipeline += [
            {"$unwind": "$compatible_platforms"},
            {"$group": {"_id": "$compatible_platforms", "count": {"$sum": 1}}},
        ]
        collection = Skill.get_motor_collection()
        cursor = collection.aggregate(pipeline)
        return {doc["_id"]: doc["count"] async for doc in cursor}

    async def list_with_cursors(
        self,
        q: Optional[str] = None,
        labels: Optional[List[str]] = None,
        sort: SortField = "newest",
        page: int = 1,
        page_size: int = 20,
        include_deactivated: bool = False,
        forked_from: Optional[str] = None,
        visibility: Optional[str] = None,
        submitted_by: Optional[str] = None,
        cursor: Optional[str] = None,
        platforms: Optional[List[str]] = None,
    ) -> Tuple[List[Skill], int, Optional[str], Optional[str], dict]:
        """Return (items, total, next_cursor, prev_cursor, platform_counts)."""
        sort_exprs = {
            "newest": [("submitted_at", -1), ("_id", -1)],
            "highest_rated": [("avg_rating", -1), ("submitted_at", -1)],
            "most_rated": [("rating_count", -1), ("submitted_at", -1)],
            "most_stars": [("github_stars", -1), ("submitted_at", -1)],
        }
        sort_expr = sort_exprs[sort]

        # Normalise platforms: lowercase, strip, cap at 20, drop empties
        platform_list: Optional[List[str]] = None
        if platforms:
            platform_list = [p.strip().lower() for p in platforms if p.strip()][:20] or None

        query_parts, early_empty = await self._build_query_parts(
            q=q, labels=labels, sort=sort, include_deactivated=include_deactivated,
            forked_from=forked_from, visibility=visibility, submitted_by=submitted_by,
        )
        if early_empty:
            return [], 0, None, None, {}

        # Apply platforms filter AFTER _build_query_parts so base_query_parts
        # can be reused for the platform_counts aggregation without the platforms clause.
        base_query_parts = list(query_parts) if query_parts else []
        if platform_list:
            query_parts = base_query_parts + [{"compatible_platforms": {"$in": platform_list}}]

        base_query = Skill.find(*query_parts) if query_parts else Skill.find()
        total = await self._get_total(
            base_query, q=q, labels=labels, visibility=visibility,
            forked_from=forked_from, sort=sort, submitted_by=submitted_by,
            include_deactivated=include_deactivated, platforms=platform_list,
        )

        # Build raw $match for aggregation — mirrors base_query_parts but as plain dicts
        # only (no Beanie operator objects). Skips $text (not safe in aggregation $match).
        agg_raw_match: dict = {}
        if not include_deactivated:
            agg_raw_match["status"] = SkillStatus.active.value
        if submitted_by:
            agg_raw_match["submitter_id"] = submitted_by
        if visibility and visibility != "all":
            agg_raw_match["visibility"] = VisibilityEnum(visibility).value
        if forked_from:
            normalized = _normalize_github_url(forked_from)
            if normalized:
                agg_raw_match["forked_from_url"] = normalized
        # label filter produces an _id $in — extract it from base_query_parts if present
        for part in base_query_parts:
            if isinstance(part, dict) and "_id" in part:
                agg_raw_match["_id"] = part["_id"]
                break

        # platform_counts: skip when q= active ($text in aggregation $match is complex)
        platform_counts: dict[str, int] = {}
        if not q:
            platform_counts = await self._platform_counts_aggregation(agg_raw_match)

        # Atlas Search path (feature-flagged — dead-letter on self-hosted PSMDB, ADR-U34)
        atlas_used = False
        items = None
        if q and os.environ.get("MONGODB_ATLAS_SEARCH", "0").strip() == "1":
            from app.services import search as search_svc
            try:
                extra_filters = {}
                if not include_deactivated:
                    extra_filters["status"] = SkillStatus.active.value
                if platform_list:
                    extra_filters["compatible_platforms"] = {"$in": platform_list}
                atlas_pipeline = search_svc.build_atlas_pipeline(q, extra_filters)
                collection = Skill.get_motor_collection()
                raw = await collection.aggregate(atlas_pipeline).to_list(length=page_size)
                items = [Skill.model_validate(doc) for doc in raw]
                atlas_used = True
            except Exception as exc:
                logger.warning("[SEARCH] Atlas Search fallback to $text: %s", exc)
                items = None

        if not atlas_used:
            # Keyset path — only for sort=newest when cursor is provided
            if cursor is not None and sort == "newest":
                sv, oid = _decode_cursor(cursor)
                keyset_filter = {"$or": [
                    {"submitted_at": {"$lt": sv}},
                    {"submitted_at": sv, "_id": {"$lt": bson.ObjectId(oid)}},
                ]}
                keyset_parts = list(query_parts) + [keyset_filter] if query_parts else [keyset_filter]
                keyset_query = Skill.find(*keyset_parts)
                items = await keyset_query.sort(sort_expr).limit(page_size).to_list()
            else:
                items = (
                    await base_query.sort(sort_expr)
                    .skip((page - 1) * page_size)
                    .limit(page_size)
                    .to_list()
                )

        # Apply name boost when q is present (skip if atlas already ranked results)
        if q and items is not None and not atlas_used:
            from app.services import search as search_svc
            items = await search_svc.name_boost(q, items)

        # Compute next_cursor (only for sort=newest)
        next_cursor = None
        prev_cursor = None  # deferred per ADR-U32 Slice 2
        if sort == "newest" and items:
            last = items[-1]
            fetched_count = (page - 1) * page_size + len(items) if cursor is None else len(items)
            has_more = fetched_count < total if cursor is None else len(items) == page_size
            if has_more:
                sv = last.submitted_at
                if sv.tzinfo is None:
                    sv = sv.replace(tzinfo=timezone.utc)
                next_cursor = _encode_cursor(sv, str(last.id))

        return items, total, next_cursor, prev_cursor, platform_counts

    async def get(self, slug: str, include_deactivated: bool = False) -> Optional[Skill]:
        skill = await Skill.find_one(Skill.slug == slug)
        if skill and not include_deactivated and skill.status == SkillStatus.deactivated:
            return None
        return skill

    async def create(self, data: SkillCreate, submitter_id: str) -> Skill:
        skill_path = data.skill_path or "/"

        logger.info("[CREATE] submitter=%s source_type=%s repo_url=%s skill_path=%s",
                    submitter_id, data.source_type, data.repo_url, skill_path)

        # Validate skill_path (also enforced by model validator on save)
        if ".." in skill_path.split("/"):
            raise ValueError("skill_path must not contain '..' components")

        if data.source_type == "local":
            return await self._create_local(data, submitter_id, skill_path)

        repo_url = extract_repo_root_url(data.repo_url) or data.repo_url

        github_data = None
        try:
            github_data = await github_fetcher.fetch(repo_url)
            logger.info("[CREATE] github_fetcher ok name=%r visibility=%s stars=%s",
                        github_data.name, github_data.visibility, github_data.stars)
        except GitHubFetchError as exc:
            logger.warning("[CREATE] github_fetcher failed: %s", exc)

        # Scan skill_path directory to capture file content
        skill_md_raw: Optional[str] = None
        skill_md_filename: Optional[str] = None
        readme_raw: Optional[str] = None
        plugin_meta: dict = {}
        file_manifest: list = []
        manifest_truncated: bool = False
        try:
            from app.services.github import github_url_parser, metadata_extractor
            ref = github_url_parser.parse(repo_url)
            ref = GitHubRef(owner=ref.owner, repo=ref.repo, branch=ref.branch, path=skill_path)
            logger.info("[CREATE] scanning ref owner=%s repo=%s branch=%r path=%s",
                        ref.owner, ref.repo, ref.branch, ref.path)
            scan = await github_scanner.scan(ref)
            file_manifest = scan.all_files
            manifest_truncated = scan.manifest_truncated
            logger.info("[CREATE] scan complete files=%s root_readme=%s",
                        list(scan.files.keys()), "set" if scan.root_readme else "None")
            for fname in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md"):
                if fname in scan.files:
                    skill_md_raw = scan.files[fname][:100_000]  # cap at 100 KB
                    skill_md_filename = fname
                    logger.info("[CREATE] skill_md_filename=%s length=%d", fname, len(skill_md_raw))
                    break
            if skill_md_filename is None:
                logger.warning("[CREATE] no SKILL.md/skill.md/CLAUDE.md/AGENTS.md found in scan")
            readme_raw = scan.files.get("README.md") or scan.root_readme
            if readme_raw:
                logger.info("[CREATE] readme_raw set from %s, length=%d",
                            "README.md" if "README.md" in scan.files else "root_readme", len(readme_raw))
            else:
                logger.warning("[CREATE] readme_raw is None — neither README.md in dir nor root_readme")
            if "plugin.json" in scan.files:
                plugin_meta = metadata_extractor._parse_plugin_json(scan.files["plugin.json"])
                logger.info("[CREATE] plugin_meta=%s", plugin_meta)
            else:
                logger.debug("[CREATE] no plugin.json in scan files")
        except (GitHubFetchError, ValueError) as exc:
            logger.warning("[CREATE] scan failed: %s", exc, exc_info=True)

        name = data.name or (github_data.name if github_data else repo_url.split("/")[-1])
        slug = await _unique_slug(name)

        skill = Skill(
            slug=slug,
            name=name,
            repo_url=repo_url,
            skill_path=skill_path,
            entry_type=data.entry_type,
            description=data.description or (github_data.description if github_data else None),
            readme_html=github_data.readme_html if github_data else None,
            readme_fetched_at=github_data.fetched_at if github_data else None,
            skill_md_raw=skill_md_raw,
            skill_md_filename=skill_md_filename,
            readme_raw=readme_raw,
            compatible_platforms=data.compatible_platforms,
            license=data.license or (github_data.license if github_data else None),
            version=data.version,
            github_stars=github_data.stars if github_data else None,
            last_commit_at=github_data.last_commit_at if github_data else None,
            uses_agent_gateway=data.uses_agent_gateway,
            visibility=github_data.visibility if github_data else VisibilityEnum.public,
            forked_from_url=github_data.forked_from_url if github_data else None,
            agent_count=plugin_meta.get("agent_count", 0),
            agent_names=plugin_meta.get("agent_names", []),
            has_mcp_server=plugin_meta.get("has_mcp_server", False),
            has_scripts=plugin_meta.get("has_scripts", False),
            plugin_author=plugin_meta.get("plugin_author"),
            file_manifest=file_manifest,
            manifest_truncated=manifest_truncated,
            pinned_commit_sha=github_data.head_sha if github_data else None,
            pinned_ref=github_data.head_tag if github_data else None,
            submitter_id=submitter_id,
        )
        try:
            await skill.insert()
        except DuplicateKeyError:
            existing = await Skill.find_one(
                Skill.repo_url == repo_url,
                Skill.skill_path == skill_path,
            )
            existing_slug = existing.slug if existing else None
            raise DuplicateSkillError(existing_slug)
        _count_cache.clear()

        # Auto-labels from plugin.json structural metadata
        auto_labels: list[str] = []
        if plugin_meta.get("has_mcp_server"):
            auto_labels.append("mcp")
        if plugin_meta.get("agent_count", 0) > 0:
            auto_labels.append("multi-agent")
        if plugin_meta.get("has_scripts"):
            auto_labels.append("has-scripts")
        # Merge with keywords from submit form
        all_label_names = list(data.keywords or []) + [l for l in auto_labels if l not in (data.keywords or [])]
        # Also include plugin.json keywords
        for kw in plugin_meta.get("keywords", []):
            if kw not in all_label_names:
                all_label_names.append(kw)
        data = data.model_copy(update={"keywords": all_label_names})

        # Convert keywords → labels BEFORE recording revision so labels appear in snapshot
        if data.keywords:
            from app.services.label import label_service as _ls
            from pymongo.errors import DuplicateKeyError as _DKE
            from app.models.label import Label as _Label, SkillLabel as _SkillLabel
            for kw in data.keywords:
                kw = kw.strip().lower()
                if not kw:
                    continue
                label = await _Label.find_one(_Label.name == kw)
                if label is None:
                    label = _Label(name=kw, created_by="system")
                    try:
                        await label.insert()
                    except _DKE:
                        label = await _Label.find_one(_Label.name == kw)
                sl = _SkillLabel(skill_id=str(skill.id), label_id=str(label.id), applied_by="system")
                try:
                    await sl.insert()
                    await _Label.find_one(_Label.id == label.id).update({"$inc": {"usage_count": 1}})
                except _DKE:
                    pass  # already tagged

        # Fetch applied label names for snapshot embedding
        try:
            applied = await label_module.label_service.list_for_skill(str(skill.id))
            label_names = [l.name for l in applied]
        except Exception:
            label_names = []

        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=submitter_id,
            action=RevisionAction.create,
            snapshot=skill.model_dump(mode="json"),
            labels=label_names,
        )
        return skill

    async def _create_local(self, data: SkillCreate, submitter_id: str, skill_path: str) -> Skill:
        """Create a skill from snapshotted local files — no GitHub calls."""
        from app.services.github import metadata_extractor
        from app.services.local import local_scanner
        from app.services.scanner import LocalRef, RawScanResult

        files = data.snapshotted_files
        ref = LocalRef(path=data.repo_url.removeprefix("local://"))
        local_manifest = local_scanner._build_local_manifest(files)
        scan = RawScanResult(ref=ref, files=files, snapshotted_files=files, all_files=local_manifest)
        snap = metadata_extractor.extract(scan)

        skill_md_raw: Optional[str] = None
        skill_md_filename: Optional[str] = None
        for fname in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md"):
            if fname in files:
                skill_md_raw = files[fname][:100_000]
                skill_md_filename = fname
                break

        readme_raw = files.get("README.md")
        plugin_meta: dict = {}
        if "plugin.json" in files:
            plugin_meta = metadata_extractor._parse_plugin_json(files["plugin.json"])

        name = data.name or snap.name or ref.path.rsplit("/", 1)[-1]
        slug = await _unique_slug(name)

        skill = Skill(
            slug=slug,
            name=name,
            repo_url=data.repo_url,
            skill_path=skill_path,
            entry_type=data.entry_type,
            description=data.description or snap.description,
            skill_md_raw=skill_md_raw,
            skill_md_filename=skill_md_filename,
            readme_raw=readme_raw,
            compatible_platforms=data.compatible_platforms or snap.compatible_platforms,
            license=data.license,
            version=data.version or snap.version,
            uses_agent_gateway=data.uses_agent_gateway,
            visibility=VisibilityEnum.public,
            source_type="local",
            snapshotted_files=files,
            agent_count=plugin_meta.get("agent_count", 0),
            agent_names=plugin_meta.get("agent_names", []),
            has_mcp_server=plugin_meta.get("has_mcp_server", False),
            has_scripts=plugin_meta.get("has_scripts", False),
            plugin_author=plugin_meta.get("plugin_author"),
            file_manifest=snap.file_manifest,
            manifest_truncated=snap.manifest_truncated,
            submitter_id=submitter_id,
        )
        try:
            await skill.insert()
        except DuplicateKeyError:
            existing = await Skill.find_one(
                Skill.repo_url == data.repo_url,
                Skill.skill_path == skill_path,
            )
            raise DuplicateSkillError(existing.slug if existing else None)
        _count_cache.clear()
        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=submitter_id,
            action=RevisionAction.create,
            snapshot=skill.model_dump(mode="json"),
            labels=[],
        )
        return skill

    async def update(
        self,
        skill: Skill,
        data: SkillUpdate,
        actor_id: str,
    ) -> Skill:
        update_fields = data.model_dump(exclude_none=True, exclude={"changelog_note"})
        for k, v in update_fields.items():
            setattr(skill, k, v)
        skill.updated_at = datetime.now(timezone.utc)
        await skill.save()
        try:
            applied = await label_module.label_service.list_for_skill(str(skill.id))
            label_names = [l.name for l in applied]
        except Exception:
            label_names = []
        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=actor_id,
            action=RevisionAction.edit,
            snapshot=skill.model_dump(mode="json"),
            changelog_note=data.changelog_note,
            labels=label_names,
        )
        return skill

    async def refetch(self, skill: Skill, actor_id: str) -> Skill:
        logger.info("[REFETCH] slug=%s actor=%s repo_url=%s skill_path=%s",
                    skill.slug, actor_id, skill.repo_url, skill.skill_path)
        try:
            # Skip fallback chain for known-internal skills (optimized refetch path)
            force_app = skill.visibility == VisibilityEnum.internal
            logger.info("[REFETCH] force_app_token=%s (visibility=%s)", force_app, skill.visibility)
            gh = await github_fetcher.fetch(skill.repo_url, force_app_token=force_app)
            skill.github_stars = gh.stars
            skill.last_commit_at = gh.last_commit_at
            skill.readme_html = gh.readme_html
            skill.readme_fetched_at = gh.fetched_at
            skill.visibility = gh.visibility
            if not skill.description:
                skill.description = gh.description
            # Update upstream_sha so update_available stays current
            if gh.head_sha:
                skill.upstream_sha = gh.head_sha
            logger.info("[REFETCH] github_fetcher ok stars=%s visibility=%s head_sha=%s",
                        gh.stars, gh.visibility, gh.head_sha)
            # Refresh readme_raw and plugin.json fields from HEAD
            try:
                from app.services.github import github_url_parser, metadata_extractor
                ref = github_url_parser.parse(skill.repo_url)
                ref = GitHubRef(owner=ref.owner, repo=ref.repo, branch=ref.branch, path=skill.skill_path)
                logger.info("[REFETCH] scanning ref owner=%s repo=%s branch=%r path=%s",
                            ref.owner, ref.repo, ref.branch, ref.path)
                scan = await github_scanner.scan(ref)
                logger.info("[REFETCH] scan complete files=%s root_readme=%s",
                            list(scan.files.keys()), "set" if scan.root_readme else "None")
                new_readme = scan.files.get("README.md") or scan.root_readme
                if new_readme is not None:
                    skill.readme_raw = new_readme
                    logger.info("[REFETCH] readme_raw updated from %s length=%d",
                                "README.md" if "README.md" in scan.files else "root_readme", len(new_readme))
                else:
                    logger.warning("[REFETCH] readme_raw still None after rescan")
                skill_md_found = False
                for fname in ("SKILL.md", "skill.md", "CLAUDE.md", "AGENTS.md"):
                    if fname in scan.files:
                        skill.skill_md_raw = scan.files[fname][:100_000]
                        skill.skill_md_filename = fname
                        skill_md_found = True
                        logger.info("[REFETCH] skill_md_filename=%s length=%d", fname, len(skill.skill_md_raw))
                        break
                if not skill_md_found:
                    logger.warning("[REFETCH] no SKILL.md/skill.md/CLAUDE.md/AGENTS.md found in rescan")
                if "plugin.json" in scan.files:
                    pm = metadata_extractor._parse_plugin_json(scan.files["plugin.json"])
                    skill.agent_count = pm.get("agent_count", 0)
                    skill.agent_names = pm.get("agent_names", [])
                    skill.has_mcp_server = pm.get("has_mcp_server", False)
                    skill.has_scripts = pm.get("has_scripts", False)
                    skill.plugin_author = pm.get("plugin_author")
                    logger.info("[REFETCH] plugin_meta updated: %s", pm)
                skill.file_manifest = scan.all_files
                skill.manifest_truncated = scan.manifest_truncated
                logger.info("[REFETCH] file_manifest updated: %d entries, truncated=%s",
                            len(scan.all_files), scan.manifest_truncated)
            except (GitHubFetchError, ValueError) as exc:
                logger.warning("[REFETCH] scan failed: %s", exc, exc_info=True)
            skill.updated_at = datetime.now(timezone.utc)
            await skill.save()
            try:
                applied = await label_module.label_service.list_for_skill(str(skill.id))
                label_names = [l.name for l in applied]
            except Exception:
                label_names = []
            await revision_service.record(
                skill_id=str(skill.id),
                actor_id=actor_id,
                action=RevisionAction.refetch,
                snapshot=skill.model_dump(mode="json"),
                labels=label_names,
            )
            logger.info("[REFETCH] done slug=%s", skill.slug)
        except GitHubFetchError as exc:
            logger.warning("[REFETCH] github_fetcher failed: %s", exc)
        return skill

    async def pin(self, skill: Skill, actor_id: str) -> Skill:
        """Advance the install pin to the current HEAD. Self-contained — no prior refetch needed."""
        if skill.source_type != "github":
            raise PinNotSupportedError("Version pinning is not available for locally-submitted skills.")

        logger.info("[PIN] slug=%s actor=%s", skill.slug, actor_id)
        try:
            force_app = skill.visibility == VisibilityEnum.internal
            gh = await github_fetcher.fetch(skill.repo_url, force_app_token=force_app)
            if not gh.head_sha:
                logger.warning("[PIN] could not fetch HEAD SHA for slug=%s", skill.slug)
                return skill
            skill.pinned_commit_sha = gh.head_sha
            skill.pinned_ref = gh.head_tag
            skill.upstream_sha = gh.head_sha
            skill.updated_at = datetime.now(timezone.utc)
            await skill.save()
            try:
                applied = await label_module.label_service.list_for_skill(str(skill.id))
                label_names = [l.name for l in applied]
            except Exception:
                label_names = []
            await revision_service.record(
                skill_id=str(skill.id),
                actor_id=actor_id,
                action=RevisionAction.pin,
                snapshot=skill.model_dump(mode="json"),
                labels=label_names,
            )
            logger.info("[PIN] done slug=%s pinned_commit_sha=%s pinned_ref=%s",
                        skill.slug, skill.pinned_commit_sha, skill.pinned_ref)
        except GitHubFetchError as exc:
            logger.warning("[PIN] github_fetcher failed: %s", exc)
        return skill

    async def delete(self, skill: Skill) -> None:
        skill_id = str(skill.id)

        await label_module.label_service.purge_for_skill(skill_id)
        await Rating.find(Rating.skill_id == skill_id).delete()
        await SkillRevision.find(SkillRevision.skill_id == skill_id).delete()
        await SkillFlag.find(SkillFlag.skill_id == skill_id).delete()

        # Null out skill_id on install events so the event record survives
        from app.models.install_event import SkillInstallEvent
        collection = SkillInstallEvent.get_motor_collection()
        await collection.update_many({"skill_id": skill_id}, {"$set": {"skill_id": None}})

        await skill.delete()

    async def deactivate(
        self,
        slug: str,
        reason: str,
        admin_id: str,
        superseded_by_slug: Optional[str] = None,
    ) -> tuple[Skill, list[str]]:
        """Deactivate a skill. Writes revision. Bulk-resolves active flags."""
        from app.models.skill import SkillStatus
        import app.services.flag as flag_service

        skill = await self.get(slug, include_deactivated=True)
        if not skill:
            raise ValueError("not_found")
        if skill.status == SkillStatus.deactivated:
            raise ValueError("already_deactivated")

        skill.status = SkillStatus.deactivated
        skill.deactivation_reason = reason
        if superseded_by_slug is not None:
            skill.superseded_by_slug = superseded_by_slug
        await skill.save()
        _count_cache.clear()

        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=admin_id,
            action=RevisionAction.deactivate,
            snapshot={"reason": reason, "superseded_by_slug": superseded_by_slug},
        )

        await flag_service.resolve_all_for_skill(str(skill.id), resolved_by=admin_id)

        warnings = []
        if superseded_by_slug:
            ref = await self.get(superseded_by_slug, include_deactivated=True)
            if ref and ref.status == SkillStatus.deactivated:
                warnings.append(f"superseded_by_slug '{superseded_by_slug}' is itself deactivated")
        return skill, warnings

    async def reactivate(self, slug: str, reason: Optional[str], admin_id: str) -> Skill:
        """Reactivate a deactivated skill. Writes revision."""
        from app.models.skill import SkillStatus

        skill = await self.get(slug, include_deactivated=True)
        if not skill:
            raise ValueError("not_found")
        if skill.status == SkillStatus.active:
            raise ValueError("already_active")

        skill.status = SkillStatus.active
        skill.deactivation_reason = None
        await skill.save()
        _count_cache.clear()

        await revision_service.record(
            skill_id=str(skill.id),
            actor_id=admin_id,
            action=RevisionAction.reactivate,
            snapshot={"reason": reason},
        )
        return skill


skill_repository = SkillRepository()
