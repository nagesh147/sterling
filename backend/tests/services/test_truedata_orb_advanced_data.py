"""TrueData refresh boundary: a failed data-quality check must never pass through.

``refresh_contract`` returns ``(contract, quote_age_seconds)``. Every required
check raises instead of returning a sentinel, so a rejected quote cannot reach
order admission by being mistaken for an empty-but-valid result.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import OptionContract, StrategyConfig
from app.services.providers.truedata.orb_provider import TrueDataOrbProvider


class FakeTrueData:
    def __init__(self, tick):
        self.tick = tick

    async def get_last_ticks(self, symbol, n, **kwargs):
        return [self.tick] if self.tick else []


def _contract():
    return OptionContract('NIFTY26AUG25000CE', 25000, '2026-08-27', 'CE', 10, 9.95, 10.05, 65, None, 5000, 20000)


def _tick(age_s=0.0, **overrides):
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=age_s)).strftime('%Y-%m-%dT%H:%M:%S+00:00')
    return {'timestamp': stamp, 'ltp': 10, 'bid': 9.95, 'ask': 10.05, 'volume': 5000, 'oi': 20000, **overrides}


@pytest.mark.asyncio
async def test_truedata_refresh_returns_contract_and_quote_age():
    provider = TrueDataOrbProvider(FakeTrueData(_tick(age_s=1)))
    refreshed, age = await provider.refresh_contract(_contract(), StrategyConfig(max_quote_staleness_s=15))
    assert refreshed.symbol == 'NIFTY26AUG25000CE'
    assert refreshed.bid == 9.95 and refreshed.ask == 10.05
    assert 0.0 <= age <= 15.0


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_stale_quote():
    provider = TrueDataOrbProvider(FakeTrueData(_tick(age_s=120)))
    with pytest.raises(ValueError, match="TrueData quote is stale"):
        await provider.refresh_contract(_contract(), StrategyConfig(max_quote_staleness_s=15))


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_a_missing_tick():
    provider = TrueDataOrbProvider(FakeTrueData(None))
    with pytest.raises(ValueError, match="no latest tick"):
        await provider.refresh_contract(_contract(), StrategyConfig())


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_an_undated_quote_when_freshness_is_required():
    provider = TrueDataOrbProvider(FakeTrueData({'ltp': 10, 'bid': 9.95, 'ask': 10.05, 'volume': 5000, 'oi': 20000}))
    with pytest.raises(ValueError, match="stale: unknown"):
        await provider.refresh_contract(_contract(), StrategyConfig())


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_a_crossed_market():
    provider = TrueDataOrbProvider(FakeTrueData(_tick(bid=10.5, ask=10.0)))
    with pytest.raises(ValueError, match="invalid TrueData bid/ask"):
        await provider.refresh_contract(_contract(), StrategyConfig())


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_a_spread_above_the_ceiling():
    provider = TrueDataOrbProvider(FakeTrueData(_tick(bid=9.0, ask=11.0)))
    with pytest.raises(ValueError, match="spread above configured maximum"):
        await provider.refresh_contract(_contract(), StrategyConfig())


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_insufficient_open_interest():
    provider = TrueDataOrbProvider(FakeTrueData(_tick(oi=10)))
    with pytest.raises(ValueError, match="OI below configured minimum"):
        await provider.refresh_contract(_contract(), StrategyConfig(min_open_interest=10000))


@pytest.mark.asyncio
async def test_truedata_refresh_rejects_insufficient_volume():
    provider = TrueDataOrbProvider(FakeTrueData(_tick(volume=10)))
    with pytest.raises(ValueError, match="volume below configured minimum"):
        await provider.refresh_contract(_contract(), StrategyConfig(min_option_volume=1000))


@pytest.mark.asyncio
async def test_truedata_refresh_can_disable_tick_validation():
    """With ticks off the contract passes through unchanged and reports no age."""
    provider = TrueDataOrbProvider(FakeTrueData(None))
    contract = _contract()
    cfg = StrategyConfig(truedata_use_ticks=False, truedata_use_quote_freshness=False)
    refreshed, age = await provider.refresh_contract(contract, cfg)
    assert refreshed == contract
    assert age is None
