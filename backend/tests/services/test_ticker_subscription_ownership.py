"""Refcounted tick subscriptions.

There is one subscription set per Kite account, shared by the operator's UI, the
protection tick monitor and any strategy that needs quotes. The property under
test is that giving a token back never takes ticks away from somebody who still
needs them -- starving the protection monitor would leave a real stop unguarded.
"""
import pytest

from app.services.exchanges.kite import ticker_manager as TM


class FakeTicker:
    is_active = True

    def __init__(self):
        self.subscribed: dict[int, str] = {}

    async def subscribe(self, tokens, mode="quote"):
        for t in tokens:
            self.subscribed[int(t)] = mode

    async def unsubscribe(self, tokens):
        for t in tokens:
            self.subscribed.pop(int(t), None)

    async def stop(self):
        self.subscribed.clear()

    def status(self):
        return {"active": True, "connected": True,
                "subscribed": sorted(self.subscribed), "tick_count": 0}


@pytest.fixture
def ticker(monkeypatch):
    fake = FakeTicker()
    TM.clear()
    monkeypatch.setattr(TM, "ensure", lambda uid: _ready(fake))
    TM._tickers["u1"] = fake
    yield fake
    TM.clear()


async def _ready(value):
    return value


@pytest.mark.asyncio
async def test_sole_owner_release_unsubscribes(ticker):
    await TM.subscribe("u1", [111, 222], "full", owner="strategy_a")
    assert ticker.status()["subscribed"] == [111, 222]

    await TM.release("u1", [111, 222], "strategy_a")
    assert ticker.status()["subscribed"] == []


@pytest.mark.asyncio
async def test_release_keeps_a_token_another_owner_still_claims(ticker):
    await TM.subscribe("u1", [111], "full", owner="strategy_a")
    await TM.subscribe("u1", [111], "ltp", owner="protection")

    await TM.release("u1", [111], "strategy_a")
    # protection is still watching it for a stop
    assert ticker.status()["subscribed"] == [111]
    assert TM.owners_of("u1", 111) == {"protection"}

    await TM.release("u1", [111], "protection")
    assert ticker.status()["subscribed"] == []


@pytest.mark.asyncio
async def test_untagged_subscription_is_never_auto_released(ticker):
    """The operator's UI and the protection monitor do not claim ownership.

    A caller that never said "this is mine" cannot be assumed to be finished, so
    a release must leave its token alone.
    """
    await TM.subscribe("u1", [111], "quote")                      # e.g. a chart
    await TM.subscribe("u1", [111], "full", owner="strategy_a")

    await TM.release("u1", [111], "strategy_a")
    assert ticker.status()["subscribed"] == [111]
    assert TM.owners_of("u1", 111) == {TM._ANY}


@pytest.mark.asyncio
async def test_release_ignores_tokens_it_never_saw(ticker):
    """Not knowing who wants a token is a reason to keep it, not to drop it."""
    await TM.subscribe("u1", [999], "quote")
    TM._owners.pop(("u1", 999), None)          # simulate a pre-registry subscription

    await TM.release("u1", [999], "strategy_a")
    assert ticker.status()["subscribed"] == [999]


@pytest.mark.asyncio
async def test_release_is_idempotent(ticker):
    await TM.subscribe("u1", [111], "full", owner="strategy_a")
    await TM.release("u1", [111], "strategy_a")
    await TM.release("u1", [111], "strategy_a")          # must not raise
    assert ticker.status()["subscribed"] == []


@pytest.mark.asyncio
async def test_explicit_unsubscribe_clears_every_claim(ticker):
    """An operator unsubscribe is an instruction, not a hint."""
    await TM.subscribe("u1", [111], "full", owner="strategy_a")
    await TM.subscribe("u1", [111], "ltp", owner="protection")

    await TM.unsubscribe("u1", [111])
    assert ticker.status()["subscribed"] == []
    assert TM.owners_of("u1", 111) == set()


@pytest.mark.asyncio
async def test_stop_forgets_claims(ticker):
    """The ticker's subscription set dies with it, so the claims must go too."""
    await TM.subscribe("u1", [111], "full", owner="strategy_a")
    await TM.stop("u1")
    assert TM.owners_of("u1", 111) == set()


@pytest.mark.asyncio
async def test_claims_do_not_leak_across_users(ticker):
    await TM.subscribe("u1", [111], "full", owner="strategy_a")
    assert TM.owners_of("u2", 111) == set()
    await TM.release("u2", [111], "strategy_a")
    assert ticker.status()["subscribed"] == [111]
