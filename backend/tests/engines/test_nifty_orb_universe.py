import asyncio
from datetime import datetime, timedelta, timezone

from app.engines.nifty_orb_options import Bar, StrategyConfig
from app.engines.nifty_orb_universe import (
    UniverseInstrument,
    UniverseScanConfig,
    normalize_universe,
    scan_universe,
)

IST = timezone(timedelta(hours=5, minutes=30))


def breakout_bars():
    start = datetime(2026, 8, 18, 9, 15, tzinfo=IST)
    rows = []
    price = 24000.0
    for i in range(40):
        ts = start + timedelta(minutes=5 * i)
        if i < 3:
            o, h, l, c = price, price + 10, price - 10, price + 2
        else:
            o = price
            h, l, c = price + 8, price - 2, price + 6
        rows.append(Bar(ts, o, h, l, c, 1000 if i < 3 else 2500))
        price = c
    return rows


def test_normalize_universe_deduplicates_and_bounds():
    items = [
        UniverseInstrument(" nifty ", "index"),
        UniverseInstrument("NIFTY", "index"),
        UniverseInstrument("RELIANCE", "stock"),
        UniverseInstrument("TCS", "stock"),
    ]
    result = normalize_universe(items, config=UniverseScanConfig(max_candidates=2))
    assert [x.symbol for x in result] == ["NIFTY", "RELIANCE"]


def test_normalize_universe_can_exclude_indices():
    result = normalize_universe(
        [UniverseInstrument("NIFTY", "index"), UniverseInstrument("RELIANCE", "stock")],
        config=UniverseScanConfig(include_indices=False),
    )
    assert [x.symbol for x in result] == ["RELIANCE"]


def test_scan_universe_returns_strongest_signals_first():
    async def fetch(item, cfg):
        return breakout_bars()

    result = asyncio.run(
        scan_universe(
            [UniverseInstrument("RELIANCE"), UniverseInstrument("NIFTY", "index")],
            strategy_config=StrategyConfig(),
            scan_config=UniverseScanConfig(concurrency=2),
            fetch_bars=fetch,
        )
    )
    assert len(result) == 2
    assert all(item.signal.direction == "LONG" for item in result)
    assert result == sorted(result, key=lambda item: item.rank_key, reverse=True)


def test_scan_universe_skips_failed_candidates():
    async def fetch(item, cfg):
        if item.symbol == "BAD":
            raise RuntimeError("data source failed")
        return breakout_bars()

    result = asyncio.run(
        scan_universe(
            [UniverseInstrument("BAD"), UniverseInstrument("GOOD")],
            strategy_config=StrategyConfig(),
            fetch_bars=fetch,
        )
    )
    assert [item.instrument.symbol for item in result] == ["GOOD"]
