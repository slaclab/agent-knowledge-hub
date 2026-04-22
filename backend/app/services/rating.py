"""Rating service: atomic upsert + aggregation pipeline."""
from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.models.rating import Rating
from app.models.skill import Skill


async def rate_skill(skill_id: str, user_id: str, value: int) -> tuple[float, int]:
    """Upsert a rating and recompute avg_rating/rating_count on the Skill.

    Returns (avg_rating, rating_count) after the update.
    """
    now = datetime.now(timezone.utc)
    collection = Rating.get_motor_collection()

    for _ in range(2):  # retry once on DuplicateKeyError race
        try:
            await collection.find_one_and_update(
                {"skill_id": skill_id, "user_id": user_id},
                {
                    "$set": {"value": value, "updated_at": now},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            break
        except DuplicateKeyError:
            continue

    pipeline = [
        {"$match": {"skill_id": skill_id}},
        {"$group": {"_id": None, "avg": {"$avg": "$value"}, "count": {"$sum": 1}}},
    ]
    cursor = collection.aggregate(pipeline)
    result = await cursor.to_list(length=1)

    if result:
        avg = round(result[0]["avg"], 2)
        count = result[0]["count"]
    else:
        avg, count = 0.0, 0

    await Skill.find_one(Skill.id == ObjectId(skill_id)).update(
        {"$set": {"avg_rating": avg, "rating_count": count}}
    )

    return avg, count
