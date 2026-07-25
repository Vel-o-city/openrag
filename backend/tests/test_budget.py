import pytest

from app.security import budget


class FakeRedis:
    """Minimal in-memory stand-in for the two Redis ops budget.py uses —
    keeps these tests fast and hermetic instead of depending on a real
    Redis instance being up."""

    def __init__(self):
        self.store: dict[str, float] = {}

    async def incrbyfloat(self, key: str, amount: float) -> float:
        self.store[key] = self.store.get(key, 0.0) + amount
        return self.store[key]

    async def expire(self, key: str, ttl: int) -> None:
        pass


def test_estimate_tokens_is_roughly_length_based():
    assert budget.estimate_tokens("") == 1  # never zero
    assert budget.estimate_tokens("a" * 400) == 100


def test_estimate_cost_usd_combines_input_and_output(monkeypatch):
    monkeypatch.setattr(budget.settings, "cost_per_1k_input_tokens_usd", 0.001)
    monkeypatch.setattr(budget.settings, "cost_per_1k_output_tokens_usd", 0.002)
    assert budget.estimate_cost_usd(1000, 1000) == pytest.approx(0.003)


@pytest.mark.asyncio
async def test_reserve_budget_succeeds_under_cap(monkeypatch):
    monkeypatch.setattr(budget.settings, "daily_cost_budget_usd", 1.0)
    monkeypatch.setattr(budget.settings, "per_ip_daily_cost_budget_usd", 1.0)
    redis = FakeRedis()

    assert await budget.reserve_budget(redis, "ip-a", 0.1) is True


@pytest.mark.asyncio
async def test_reserve_budget_rejects_and_rolls_back_over_global_cap(monkeypatch):
    monkeypatch.setattr(budget.settings, "daily_cost_budget_usd", 0.05)
    monkeypatch.setattr(budget.settings, "per_ip_daily_cost_budget_usd", 1.0)
    redis = FakeRedis()

    assert await budget.reserve_budget(redis, "ip-a", 0.1) is False
    # rolled back to zero, not left holding the failed reservation
    assert redis.store[budget._daily_key("global")] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_reserve_budget_rejects_and_rolls_back_global_over_per_ip_cap(monkeypatch):
    monkeypatch.setattr(budget.settings, "daily_cost_budget_usd", 10.0)
    monkeypatch.setattr(budget.settings, "per_ip_daily_cost_budget_usd", 0.05)
    redis = FakeRedis()

    assert await budget.reserve_budget(redis, "ip-a", 0.1) is False
    # global reservation is unwound too — one throttled IP shouldn't eat
    # into the shared budget it never got to actually use
    assert redis.store[budget._daily_key("global")] == pytest.approx(0.0)
    assert redis.store[budget._daily_key("ip", "ip-a")] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_reserve_budget_accumulates_across_calls(monkeypatch):
    monkeypatch.setattr(budget.settings, "daily_cost_budget_usd", 0.25)
    monkeypatch.setattr(budget.settings, "per_ip_daily_cost_budget_usd", 1.0)
    redis = FakeRedis()

    assert await budget.reserve_budget(redis, "ip-a", 0.1) is True
    assert await budget.reserve_budget(redis, "ip-b", 0.1) is True
    # third reservation would push the global total to 0.3 > 0.25 cap
    assert await budget.reserve_budget(redis, "ip-c", 0.1) is False


@pytest.mark.asyncio
async def test_reserve_budget_per_ip_cap_is_independent_per_ip(monkeypatch):
    monkeypatch.setattr(budget.settings, "daily_cost_budget_usd", 10.0)
    monkeypatch.setattr(budget.settings, "per_ip_daily_cost_budget_usd", 0.15)
    redis = FakeRedis()

    assert await budget.reserve_budget(redis, "ip-a", 0.1) is True
    # a different IP has its own independent cap, unaffected by ip-a's usage
    assert await budget.reserve_budget(redis, "ip-b", 0.1) is True
    # but ip-a itself is now close to its own cap
    assert await budget.reserve_budget(redis, "ip-a", 0.1) is False
