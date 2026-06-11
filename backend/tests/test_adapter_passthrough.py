"""The adapter wrapper stack (CachingAdapter(RetryingAdapter(raw))) must delegate
methods it doesn't explicitly wrap — get_product_id / get_funding_rate — to the
inner adapter. Missing passthroughs made every funding fetch throw
AttributeError, so the futures "Funding" column was stuck at 0."""
import asyncio

from app.services.retry import RetryingAdapter
from app.services.cache import CachingAdapter


class _Raw:
    def __init__(self):
        self.calls = []

    async def get_product_id(self, symbol):
        self.calls.append(("pid", symbol))
        return 27

    async def get_funding_rate(self, product_id):
        self.calls.append(("funding", product_id))
        return {"funding_rate_8h_pct": 0.00012}


def test_stack_delegates_product_id_and_funding():
    raw = _Raw()
    stack = CachingAdapter(RetryingAdapter(raw))

    async def run():
        pid = await stack.get_product_id("BTCUSD")
        fr = await stack.get_funding_rate(pid)
        return pid, fr

    pid, fr = asyncio.run(run())
    assert pid == 27
    assert fr["funding_rate_8h_pct"] == 0.00012
    assert ("pid", "BTCUSD") in raw.calls
    assert ("funding", 27) in raw.calls


def test_caching_adapter_caches_product_id():
    # second call within TTL must not hit the inner adapter again
    raw = _Raw()
    stack = CachingAdapter(RetryingAdapter(raw))

    async def run():
        await stack.get_product_id("ETHUSD")
        await stack.get_product_id("ETHUSD")

    asyncio.run(run())
    assert sum(1 for c in raw.calls if c == ("pid", "ETHUSD")) == 1
