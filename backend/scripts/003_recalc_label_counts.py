"""Migration 003: Recalculate Label.usage_count from SkillLabel documents.

Fixes counts that were corrupted by skill deletions that did not clean up
SkillLabel rows or decrement usage_count.  Also removes orphaned SkillLabel
rows whose skill_id no longer exists.

Run once:
    cd backend && python -m scripts.003_recalc_label_counts

Idempotent: safe to re-run; always sets counts to the correct value.
Dry-run mode: set DRY_RUN=1 to log what would change without writing.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/agent-skills")
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_default_database()

    skills_col = db["skill"]
    labels_col = db["label"]
    skill_labels_col = db["skilllabel"]

    # Collect all live skill IDs
    live_skill_ids: set[str] = set()
    async for doc in skills_col.find({}, {"_id": 1}):
        live_skill_ids.add(str(doc["_id"]))
    log.info("Live skills: %d", len(live_skill_ids))

    # Find and remove orphaned SkillLabel rows
    orphaned_ids = []
    async for sl in skill_labels_col.find({}, {"_id": 1, "skill_id": 1}):
        if sl["skill_id"] not in live_skill_ids:
            orphaned_ids.append(sl["_id"])
    log.info("Orphaned SkillLabel rows: %d", len(orphaned_ids))
    if orphaned_ids and not DRY_RUN:
        await skill_labels_col.delete_many({"_id": {"$in": orphaned_ids}})
        log.info("Deleted %d orphaned rows", len(orphaned_ids))

    # Count remaining SkillLabel rows per label_id
    counts: dict[str, int] = defaultdict(int)
    async for sl in skill_labels_col.find({"skill_id": {"$in": list(live_skill_ids)}}, {"label_id": 1}):
        counts[sl["label_id"]] += 1

    # Update every Label document
    updated = 0
    async for label in labels_col.find({}, {"_id": 1, "usage_count": 1, "name": 1}):
        label_id = str(label["_id"])
        correct = counts.get(label_id, 0)
        current = label.get("usage_count", 0)
        if current != correct:
            log.info("Label %r: %d → %d", label.get("name", label_id), current, correct)
            if not DRY_RUN:
                await labels_col.update_one({"_id": label["_id"]}, {"$set": {"usage_count": correct}})
            updated += 1

    log.info("Labels updated: %d%s", updated, " (dry run)" if DRY_RUN else "")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
