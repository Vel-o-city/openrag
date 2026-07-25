"""Reserve-before-spend cost budget guard: estimate the worst-case cost of
an LLM call *before* making it, and reject if that would exceed either a
global daily cap or a smaller per-IP cap. The global cap is the real
backstop — an IP-only limit is trivially bypassed by rotating IPs.

Deliberately approximate: this project runs entirely on Gemini's free tier,
so no real charges are possible today. This exists as a safety net for if/
when it's ever pointed at a paid plan or a costlier model.
"""

import time

from redis.asyncio import Redis

from app.config import settings

DAILY_TTL_SECONDS = 60 * 60 * 25  # a little over a day, so a key always expires


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens / 1000) * settings.cost_per_1k_input_tokens_usd + (
        output_tokens / 1000
    ) * settings.cost_per_1k_output_tokens_usd


def _daily_key(prefix: str, ip_hash: str | None = None) -> str:
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if ip_hash:
        return f"budget:{prefix}:{today}:{ip_hash}"
    return f"budget:{prefix}:{today}"


async def _adjust(redis: Redis, key: str, amount: float) -> float:
    new_total = await redis.incrbyfloat(key, amount)
    await redis.expire(key, DAILY_TTL_SECONDS)
    return float(new_total)


async def _reserve(redis: Redis, key: str, amount: float, cap: float) -> bool:
    new_total = await _adjust(redis, key, amount)
    if new_total > cap:
        await _adjust(redis, key, -amount)
        return False
    return True


async def reserve_budget(redis: Redis, ip_hash: str, estimated_cost_usd: float) -> bool:
    """Reserves the estimated cost against both the global daily cap and the
    per-IP cap. Both must hold for the call to proceed; if the per-IP
    reservation fails after the global one already succeeded, the global
    reservation is rolled back too, so one throttled IP can't hold a slice
    of the shared budget hostage."""
    global_key = _daily_key("global")
    ip_key = _daily_key("ip", ip_hash)

    if not await _reserve(redis, global_key, estimated_cost_usd, settings.daily_cost_budget_usd):
        return False

    if not await _reserve(redis, ip_key, estimated_cost_usd, settings.per_ip_daily_cost_budget_usd):
        await _adjust(redis, global_key, -estimated_cost_usd)
        return False

    return True
