import json

import pytest

from app.security.moderation import MAX_FLAG_LOG_ENTRIES, flag_entity, list_flags


class FakeRedis:
    """In-memory stand-in for the list ops moderation.py uses."""

    def __init__(self):
        self.lists: dict[str, list[str]] = {}

    async def rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        values = self.lists.get(key, [])
        # Python slicing with a negative start/-1 end matches Redis LTRIM semantics here.
        self.lists[key] = values[start : end + 1] if end != -1 else values[start:]

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.lists.get(key, [])
        return values[start:] if end == -1 else values[start : end + 1]


@pytest.mark.asyncio
async def test_flag_entity_then_list_flags_round_trips():
    redis = FakeRedis()

    await flag_entity(redis, entity_id="e1", reason="looks fake", ip_hash="ip-a")

    flags = await list_flags(redis)
    assert len(flags) == 1
    assert flags[0]["entity_id"] == "e1"
    assert flags[0]["reason"] == "looks fake"
    assert flags[0]["ip_hash"] == "ip-a"
    assert "flagged_at" in flags[0]


@pytest.mark.asyncio
async def test_list_flags_returns_most_recent_first():
    redis = FakeRedis()

    await flag_entity(redis, entity_id="first", reason=None, ip_hash="ip-a")
    await flag_entity(redis, entity_id="second", reason=None, ip_hash="ip-a")

    flags = await list_flags(redis)
    assert [f["entity_id"] for f in flags] == ["second", "first"]


@pytest.mark.asyncio
async def test_list_flags_respects_limit():
    redis = FakeRedis()
    for i in range(5):
        await flag_entity(redis, entity_id=f"e{i}", reason=None, ip_hash="ip-a")

    flags = await list_flags(redis, limit=2)
    assert len(flags) == 2
    assert [f["entity_id"] for f in flags] == ["e4", "e3"]


@pytest.mark.asyncio
async def test_flag_log_is_capped_at_max_entries():
    redis = FakeRedis()
    for i in range(MAX_FLAG_LOG_ENTRIES + 10):
        await flag_entity(redis, entity_id=f"e{i}", reason=None, ip_hash="ip-a")

    stored = redis.lists["moderation:flags"]
    assert len(stored) == MAX_FLAG_LOG_ENTRIES
    # oldest entries were trimmed off, newest kept
    assert json.loads(stored[-1])["entity_id"] == f"e{MAX_FLAG_LOG_ENTRIES + 9}"
