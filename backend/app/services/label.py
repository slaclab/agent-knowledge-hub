from __future__ import annotations

import re
from typing import List, Optional

from beanie.operators import In
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.models.label import Label, SkillLabel
from app.schemas.skill import LabelOut


class LabelNotFoundError(Exception):
    pass


class LabelAlreadyAppliedError(Exception):
    pass


class LabelRateLimitError(Exception):
    pass


class InvalidObjectIdError(Exception):
    pass


def _to_oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise InvalidObjectIdError(f"Invalid ObjectId: {value!r}")


class LabelService:
    async def add(self, skill_id: str, name: str, actor_id: str) -> LabelOut:
        name = name.strip().lower()
        # Validate via model (raises ValueError on invalid name)
        Label.model_validate({"name": name, "created_by": actor_id})

        per_skill_count = await SkillLabel.find(
            SkillLabel.skill_id == skill_id,
            SkillLabel.applied_by == actor_id,
        ).count()
        if per_skill_count >= 5:
            raise LabelRateLimitError("Maximum 5 labels per user per skill")

        label = await Label.find_one(Label.name == name)
        if label is None:
            label = Label(name=name, created_by=actor_id)
            try:
                await label.insert()
            except DuplicateKeyError:
                label = await Label.find_one(Label.name == name)

        skill_label = SkillLabel(
            skill_id=skill_id,
            label_id=str(label.id),
            applied_by=actor_id,
        )
        try:
            await skill_label.insert()
        except DuplicateKeyError:
            raise LabelAlreadyAppliedError("You have already applied this label")

        await Label.find_one(Label.id == label.id).update({"$inc": {"usage_count": 1}})
        label = await Label.get(label.id)
        return LabelOut(name=label.name, usage_count=label.usage_count, applied_by_me=True)

    async def remove(self, skill_id: str, name: str, actor_id: str) -> None:
        label = await Label.find_one(Label.name == name.strip().lower())
        if label is None:
            raise LabelNotFoundError("Label not found")
        skill_label = await SkillLabel.find_one(
            SkillLabel.skill_id == skill_id,
            SkillLabel.label_id == str(label.id),
            SkillLabel.applied_by == actor_id,
        )
        if skill_label is None:
            raise LabelNotFoundError("You have not applied this label")
        await skill_label.delete()
        await Label.find_one(Label.id == label.id).update({"$inc": {"usage_count": -1}})

    async def purge_for_skill(self, skill_id: str) -> None:
        """Remove all SkillLabel rows for a skill and decrement each Label's usage_count."""
        skill_labels = await SkillLabel.find(SkillLabel.skill_id == skill_id).to_list()
        for sl in skill_labels:
            try:
                oid = _to_oid(sl.label_id)
                await Label.find_one(Label.id == oid).update({"$inc": {"usage_count": -1}})
            except InvalidObjectIdError:
                pass
        if skill_labels:
            await SkillLabel.find(SkillLabel.skill_id == skill_id).delete()

    async def list_for_skill(
        self, skill_id: str, viewer_id: Optional[str] = None
    ) -> List[LabelOut]:
        skill_labels = await SkillLabel.find(SkillLabel.skill_id == skill_id).to_list()
        if not skill_labels:
            return []
        label_ids = list({sl.label_id for sl in skill_labels})
        labels = await Label.find(In(Label.id, [_to_oid(lid) for lid in label_ids])).to_list()
        label_map = {str(l.id): l for l in labels}
        applied_by_me = {sl.label_id for sl in skill_labels if sl.applied_by == viewer_id}
        return [
            LabelOut(
                name=label_map[lid].name,
                usage_count=label_map[lid].usage_count,
                applied_by_me=lid in applied_by_me,
            )
            for lid in label_ids
            if lid in label_map
        ]

    async def search(self, q: Optional[str] = None, limit: int = 20) -> List[LabelOut]:
        if q:
            escaped = re.escape(q.strip().lower())
            labels = await Label.find(
                {"name": {"$regex": f"^{escaped}"}}
            ).sort([("usage_count", -1)]).limit(limit * 2).to_list()
        else:
            labels = await Label.find().sort([("usage_count", -1)]).limit(limit * 2).to_list()

        if not labels:
            return []

        label_ids = [str(l.id) for l in labels]
        collection = SkillLabel.get_motor_collection()
        pipeline = [
            {"$match": {"label_id": {"$in": label_ids}}},
            {"$group": {"_id": {"lid": "$label_id", "sid": "$skill_id"}}},
            {"$group": {"_id": "$_id.lid", "count": {"$sum": 1}}},
        ]
        counts: dict[str, int] = {}
        async for doc in collection.aggregate(pipeline):
            counts[doc["_id"]] = doc["count"]

        results = [
            LabelOut(name=l.name, usage_count=counts[str(l.id)])
            for l in labels
            if counts.get(str(l.id), 0) > 0
        ]
        results.sort(key=lambda x: x.usage_count, reverse=True)
        return results[:limit]

    async def get_by_name(self, name: str) -> Optional[Label]:
        return await Label.find_one(Label.name == name.strip().lower())

    async def list_all(self, include_zero: bool = False) -> List[LabelOut]:
        query = Label.find() if include_zero else Label.find(Label.usage_count > 0)
        labels = await query.sort([("usage_count", -1)]).to_list()
        return [LabelOut(name=l.name, usage_count=l.usage_count) for l in labels]

    async def list_all_with_ids(self, include_zero: bool = False) -> List[dict]:
        from app.schemas.skill import AdminLabelOut
        query = Label.find() if include_zero else Label.find(Label.usage_count > 0)
        labels = await query.sort([("usage_count", -1)]).to_list()
        return [AdminLabelOut(id=str(l.id), name=l.name, usage_count=l.usage_count) for l in labels]

    async def rename(self, label_id: str, new_name: str, actor_id: str) -> LabelOut:
        oid = _to_oid(label_id)
        new_name = new_name.strip().lower()
        Label.model_validate({"name": new_name, "created_by": actor_id})

        client = Label.get_motor_collection().database.client
        async with await client.start_session() as session:
            async with session.start_transaction():
                label = await Label.get(oid)
                if label is None:
                    raise LabelNotFoundError("Label not found")
                old_name = label.name
                await Label.find_one(Label.id == oid).update(
                    {"$set": {"name": new_name}, "$push": {"aliases": old_name}},
                    session=session,
                )
        label = await Label.get(oid)
        return LabelOut(name=label.name, usage_count=label.usage_count)

    async def merge(self, source_id: str, target_id: str, actor_id: str) -> LabelOut:
        src_oid = _to_oid(source_id)
        tgt_oid = _to_oid(target_id)

        client = Label.get_motor_collection().database.client
        async with await client.start_session() as session:
            async with session.start_transaction():
                source = await Label.get(src_oid)
                target = await Label.get(tgt_oid)
                if source is None or target is None:
                    raise LabelNotFoundError("One or both labels not found")

                # Re-parent SkillLabel records from source → target; drop duplicates
                src_skill_labels = await SkillLabel.find(
                    SkillLabel.label_id == source_id
                ).to_list()
                for sl in src_skill_labels:
                    exists = await SkillLabel.find_one(
                        SkillLabel.skill_id == sl.skill_id,
                        SkillLabel.label_id == target_id,
                        SkillLabel.applied_by == sl.applied_by,
                    )
                    if exists:
                        await sl.delete()
                    else:
                        await SkillLabel.find_one(SkillLabel.id == sl.id).update(
                            {"$set": {"label_id": target_id}}
                        )
                await source.delete()

                # Recount from actual records
                count = await SkillLabel.find(SkillLabel.label_id == target_id).count()
                await Label.find_one(Label.id == tgt_oid).update(
                    {"$set": {"usage_count": count}}
                )
        target = await Label.get(tgt_oid)
        return LabelOut(name=target.name, usage_count=target.usage_count)

    async def delete(self, label_id: str, actor_id: str) -> None:
        oid = _to_oid(label_id)
        client = Label.get_motor_collection().database.client
        async with await client.start_session() as session:
            async with session.start_transaction():
                label = await Label.get(oid)
                if label is None:
                    raise LabelNotFoundError("Label not found")
                await SkillLabel.find(SkillLabel.label_id == label_id).delete()
                await label.delete()

    async def batch_labels_for_skills(
        self, skill_ids: List[str], viewer_id: Optional[str] = None
    ) -> dict[str, List[LabelOut]]:
        """Fetch labels for a list of skill IDs in 2 queries (batch hydration)."""
        if not skill_ids:
            return {}
        skill_labels = await SkillLabel.find(In(SkillLabel.skill_id, skill_ids)).to_list()
        if not skill_labels:
            return {sid: [] for sid in skill_ids}
        label_ids = list({sl.label_id for sl in skill_labels})
        labels = await Label.find(In(Label.id, [_to_oid(lid) for lid in label_ids])).to_list()
        label_map = {str(l.id): l for l in labels}

        result: dict[str, List[LabelOut]] = {sid: [] for sid in skill_ids}
        for sl in skill_labels:
            if sl.label_id not in label_map:
                continue
            lbl = label_map[sl.label_id]
            existing = next(
                (lo for lo in result[sl.skill_id] if lo.name == lbl.name), None
            )
            if existing is None:
                result[sl.skill_id].append(
                    LabelOut(
                        name=lbl.name,
                        usage_count=lbl.usage_count,
                        applied_by_me=sl.applied_by == viewer_id,
                    )
                )
            elif sl.applied_by == viewer_id:
                existing.applied_by_me = True
        return result


label_service = LabelService()
