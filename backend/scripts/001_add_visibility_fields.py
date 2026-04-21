"""Migration 001: Add visibility and forked_from_url fields to existing Skill documents.

Run once:
    cd backend && python -m scripts.001_add_visibility_fields

Idempotent: safe to re-run.
"""
from __future__ import annotations

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, IndexModel


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/agent-skills")


async def main():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client.get_default_database()
    skills = db["skills"]

    # Backfill missing fields on existing documents
    result = await skills.update_many(
        {"visibility": {"$exists": False}},
        {"$set": {"visibility": "public", "forked_from_url": None}},
    )
    print(f"Backfilled {result.modified_count} documents")

    # Create sparse index on forked_from_url (skip null values)
    await skills.create_indexes([
        IndexModel([("forked_from_url", ASCENDING)], sparse=True, name="forked_from_url_sparse"),
        IndexModel(
            [("visibility", ASCENDING), ("submitted_at", DESCENDING)],
            name="visibility_submitted_at",
        ),
    ])
    print("Indexes created (idempotent)")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
