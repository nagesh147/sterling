"""The universe scanner must not signal off a still-forming candle.

`scan_kite_universe` fed `client.get_candles(...)` straight through, and
`scan_universe` called `generate_signal` without a clock, so the current
incomplete bar became the signal bar. The other two bar adapters filtered; this
one did not. The fix is at the choke point: `scan_universe` always passes
`as_of`, so no adapter can reintroduce the repaint by forgetting to filter.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import Bar, StrategyConfig
from app.engines.nifty_orb_universe import (
    UniverseInstrument,
    UniverseScanConfig,
    scan_universe,
)

IST = timezone(timedelta(hours=5, minutes=30))
OPEN = datetime(2026, 8, 18, 9, 15, tzinfo=IST)


def _session(bars: int = 30, *, direction: str = "LONG") -> list[Bar]:
    """A clean ORB day; the final bar closes at 11:40 IST on a 30-bar series."""
    rows, price = [], 24000.0
    for i in range(bars):
        ts = OPEN + timedelta(minutes=5 * i)
        if i < 3:
            rows.append(Bar(ts, price, 24012.0, 23988.0, price, 1200))
        else:
            close = price + ((18.0 if direction == "LONG" else -18.0) if i >= bars - 5
                             else (2.0 if i % 2 else -2.0))
            pad = 4.0 if i >= bars - 5 else 3.0
            vol = 1000 + 500 * (i - (bars - 6)) if i >= bars - 5 else 1000
            rows.append(Bar(ts, price, max(price, close) + pad, min(price, close) - pad, close, vol))
            price = close
    return rows


def _run(bars, *, as_of=None, cfg=None, scan=None):
    async def fetch(item, strategy_cfg):
        return bars

    return asyncio.run(scan_universe(
        [UniverseInstrument("NIFTY", "index")],
        strategy_config=cfg or StrategyConfig(),
        scan_config=scan or UniverseScanConfig(concurrency=1),
        fetch_bars=fetch,
        as_of=as_of,
    ))


def test_an_unfinished_final_candle_is_not_used_as_the_signal():
    """One minute before the 11:40 candle closes, the signal is still 11:35."""
    bars = _session()
    closing = bars[-1].timestamp
    mid_candle = _run(bars, as_of=closing + timedelta(minutes=4))
    assert len(mid_candle) == 1
    assert mid_candle[0].signal.timestamp == closing - timedelta(minutes=5)


def test_the_signal_appears_once_the_candle_closes():
    bars = _session()
    closing = bars[-1].timestamp
    settled = _run(bars, as_of=closing + timedelta(minutes=5))
    assert len(settled) == 1
    assert settled[0].signal.direction == "LONG"
    assert settled[0].signal.timestamp == closing


def test_an_adapter_that_forgets_to_filter_cannot_cause_a_repaint():
    """The unfiltered-adapter case: bars include a candle that has not closed."""
    bars = _session()
    forming = bars[-1]
    result = _run(bars, as_of=forming.timestamp + timedelta(minutes=1))
    assert len(result) == 1
    assert result[0].signal.timestamp == forming.timestamp - timedelta(minutes=5)


def test_a_bad_strategy_config_surfaces_instead_of_becoming_no_signals():
    """Per-instrument failures are swallowed; a misconfiguration must not be."""
    with pytest.raises(ValueError, match="volume_multiplier"):
        _run(_session(), cfg=StrategyConfig(volume_multiplier=0.0))


def test_a_per_instrument_data_failure_is_still_skipped():
    async def fetch(item, cfg):
        if item.symbol == "BAD":
            raise RuntimeError("candles unavailable")
        return _session()

    result = asyncio.run(scan_universe(
        [UniverseInstrument("BAD"), UniverseInstrument("GOOD")],
        strategy_config=StrategyConfig(),
        fetch_bars=fetch,
        as_of=datetime(2026, 8, 18, 12, 0, tzinfo=IST),
    ))
    assert [item.instrument.symbol for item in result] == ["GOOD"]


def test_the_runtime_adapter_and_the_engine_agree_on_the_clock():
    """scan_kite_universe must hand its clock to the engine, not omit it."""
    import inspect
    from app.services import nifty_orb_universe_runtime as runtime
    engine_source = inspect.getsource(scan_universe)
    assert "as_of=now" in engine_source
    assert "generate_signal(bars, strategy_config)" not in engine_source
    # The runtime relies on the choke point rather than its own filter.
    assert "scan_universe(" in inspect.getsource(runtime.scan_kite_universe)
