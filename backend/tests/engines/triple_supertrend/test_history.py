import numpy as np
import pytest

from app.domain.models import Candle
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.services.kite_engine.history import (
    deriv_history_signals, duration_window, spot_history_signals,
)
from app.services.kite_engine.strikes import OptionPick
from app.services.kite_engine.universe import UniverseItem

_H = 3_600_000


def _candles(close_path, start_ms=0):
    c = np.asarray(close_path, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    out = []
    for i in range(len(c)):
        hi = max(o[i], c[i]) + 1.0
        lo = min(o[i], c[i]) - 1.0
        out.append(Candle(timestamp_ms=start_ms + i * _H, open=float(o[i]),
                          high=float(hi), low=float(lo), close=float(c[i]), volume=1.0))
    return out


def _long_path():
    return list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))


def test_duration_window_buckets():
    now = 1_000_000_000_000  # fixed "now"
    day = 86_400_000
    assert duration_window("week", now) == (now - 7 * day, now)
    assert duration_window("15d", now) == (now - 15 * day, now)
    assert duration_window("month", now) == (now - 30 * day, now)
    # today = since IST midnight → strictly within the last 24h and <= now
    f, t = duration_window("today", now)
    assert t == now and 0 < now - f <= day


def test_spot_history_collects_entries_in_window():
    cfg = TripleSupertrendConfig()
    candles = _candles(_long_path())
    item = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    sigs = spot_history_signals(item, candles, cfg, from_ms=0, to_ms=candles[-1].timestamp_ms)
    assert len(sigs) >= 1
    assert all(s.source == "spot" and s.underlying == "NIFTY 50" and s.entry_price > 0 for s in sigs)
    # down-then-up path → a short (PE) then a long (CE); both mappings exercised
    longs = [s for s in sigs if s.direction == "long"]
    assert longs and longs[0].option_type == "CE" and longs[0].stop_loss > 0
    assert all(s.option_type == "PE" for s in sigs if s.direction == "short")
    # window filter: excluding bars at/before the first entry drops it
    first_ts = sigs[0].ts_ms
    later = spot_history_signals(item, candles, cfg, from_ms=first_ts + 1, to_ms=candles[-1].timestamp_ms)
    assert all(x.ts_ms > first_ts for x in later)


@pytest.mark.asyncio
async def test_replay_window_collects_spot_and_deriv_sorted():
    from app.services.kite_engine.scanner import KiteEngineScanner
    fired = _candles(_long_path())

    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            return fired  # underlying + every option premium fire in-window

    nfo = [
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100CE", "instrument_type": "CE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7001, "lot_size": 75},
        {"name": "NIFTY", "tradingsymbol": "NIFTY25JUN100PE", "instrument_type": "PE",
         "strike": 100, "expiry": "2099-01-01", "instrument_token": 7002, "lot_size": 75},
    ]
    idx = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    sc = KiteEngineScanner()
    sigs = await sc.replay_window(
        uid="u1", client=FakeClient(), spot_universe=[idx], deriv_universe=[idx],
        nfo_rows=nfo, bfo_rows=[], cfg=TripleSupertrendConfig(), moneyness=["ATM"],
        from_ms=0, to_ms=fired[-1].timestamp_ms)
    assert any(s.source == "spot" and s.underlying == "NIFTY 50" for s in sigs)
    assert any(s.source == "derivatives" for s in sigs)
    assert all(sigs[i].ts_ms >= sigs[i + 1].ts_ms for i in range(len(sigs) - 1))  # newest first


def test_deriv_history_is_buy_only_and_tags_contract():
    cfg = TripleSupertrendConfig()
    item = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    pick = OptionPick("NIFTY25JUN24000CE", 24000.0, "CE", "2099-01-01", 8, 75, 44001)
    candles = _candles(_long_path())  # rising premium → BUY entries only
    sigs = deriv_history_signals(item, "ATM", pick, candles, cfg,
                                 from_ms=0, to_ms=candles[-1].timestamp_ms)
    assert len(sigs) >= 1
    assert all(s.direction == "long" and s.source == "derivatives" for s in sigs)
    assert sigs[0].option_symbol == "NIFTY25JUN24000CE" and sigs[0].moneyness == "ATM"
