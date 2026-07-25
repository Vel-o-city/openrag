"""Append-only moderation log: visitors can flag an entity as objectionable
via a public endpoint; an admin periodically reviews the log manually via
GET /api/admin/moderation. No ML scanning or moderation dashboard in MVP —
a deliberate scope call given the timeline (see README).
"""

import json
import time

from redis.asyncio import Redis

FLAG_LOG_KEY = "moderation:flags"
MAX_FLAG_LOG_ENTRIES = 5000


async def flag_entity(redis: Redis, *, entity_id: str, reason: str | None, ip_hash: str) -> None:
    entry = {
        "entity_id": entity_id,
        "reason": reason,
        "ip_hash": ip_hash,
        "flagged_at": time.time(),
    }
    await redis.rpush(FLAG_LOG_KEY, json.dumps(entry))
    await redis.ltrim(FLAG_LOG_KEY, -MAX_FLAG_LOG_ENTRIES, -1)


async def list_flags(redis: Redis, limit: int = 200) -> list[dict]:
    raw_entries = await redis.lrange(FLAG_LOG_KEY, -limit, -1)
    return [json.loads(entry) for entry in reversed(raw_entries)]
