from datetime import date

import numpy as np
import pytest

from app.domain.models import Candle
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import TripleSupertrendEngine
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from app.services.kite_engine.scanner import (
    KiteEngineScanner, attach_strikes, drop_forming, evaluate_item, option_order_args,
)
from app.services.kite_engine.universe import UniverseItem


def _candles(close_path, start_ms=0):
    c = np.asarray(close_path, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    out = []
    for i in range(len(c)):
        hi = max(o[i], c[i]) + 1.0
        lo = min(o[i], c[i]) - 1.0
        out.append(Candle(timestamp_ms=start_ms + i * 3_600_000, open=float(o[i]),
                          high=float(hi), low=float(lo), close=float(c[i]), volume=1.0))
    return out


def _fresh_long_path():
    return list(np.linspace(300, 150, 60)) + list(np.linspace(150, 600, 80))


def _trim_to_transition(candles, cfg):
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, _ = entry_transitions(r)
    idx = int(np.where(longs)[0][0])
    return candles[: idx + 1]


def test_drop_forming_removes_open_bar():
    candles = _candles([1, 2, 3])  # last ts = 2h
    # "now" only 30 min past the last bar's open → bar still forming
    assert len(drop_forming(candles, now_ms=2 * 3_600_000 + 1_800_000)) == 2
    # well past close → keep it
    assert len(drop_forming(candles, now_ms=10 * 3_600_000)) == 3


def test_evaluate_item_emits_row_on_fresh_transition():
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    item = UniverseItem("RELIANCE", "RELIANCE", 111, "NSE", "NFO")
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    row = evaluate_item(eng, item, candles, cfg)
    assert row is not None
    assert row.regime == "BULL" and row.option_type == "CE" and row.direction == "long"
    assert row.token == 111 and row.exchange == "NFO" and row.stop_loss > 0


def test_attach_strike_uses_option_name_for_indices():
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    nifty = UniverseItem("NIFTY 50", "NIFTY", 256265, "INDICES", "NFO", is_index=True)
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    row = evaluate_item(eng, nifty, candles, cfg)
    assert row is not None
    spot = row.spot
    base = int(round(spot / 50) * 50)
    dump = [
        {"name": "NIFTY", "tradingsymbol": f"NIFTY25JUN{base}CE", "instrument_type": "CE",
         "strike": base, "expiry": "2026-06-26"},
        {"name": "NIFTY", "tradingsymbol": f"NIFTY25JUN{base}PE", "instrument_type": "PE",
         "strike": base, "expiry": "2026-06-26"},
    ]
    attach_strikes(row, dump, option_name="NIFTY", moneynesses=["ATM"], today=date(2026, 6, 13))
    assert len(row.legs) == 1
    assert row.legs[0].option_symbol == f"NIFTY25JUN{base}CE" and row.legs[0].strike == base


def test_attach_strikes_multi_moneyness_legs():
    cfg = TripleSupertrendConfig()
    eng = TripleSupertrendEngine(cfg)
    item = UniverseItem("ACME", "ACME", 1, "NSE", "NFO")
    candles = _trim_to_transition(_candles(_fresh_long_path()), cfg)
    row = evaluate_item(eng, item, candles, cfg)
    assert row is not None
    spot = row.spot
    base = int(round(spot / 50) * 50)
    dump = [
        {"name": "ACME", "tradingsymbol": f"ACME{base}CE", "instrument_type": "CE",
         "strike": base, "expiry": "2099-01-01", "lot_size": 50},
        {"name": "ACME", "tradingsymbol": f"ACME{base-50}CE", "instrument_type": "CE",
         "strike": base - 50, "expiry": "2099-01-01", "lot_size": 50},
        {"name": "ACME", "tradingsymbol": f"ACME{base-100}CE", "instrument_type": "CE",
         "strike": base - 100, "expiry": "2099-01-01", "lot_size": 50},
    ]
    attach_strikes(row, dump, option_name="ACME", moneynesses=["ATM", "ITM1", "ITM2"],
                   today=date(2026, 6, 13))
    assert [leg.moneyness for leg in row.legs] == ["ATM", "ITM1", "ITM2"]
    assert [leg.strike for leg in row.legs] == [base, base - 50, base - 100]


@pytest.mark.asyncio
async def test_scan_end_to_end_with_fake_client():
    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            # one item fires (fresh transition), the other is flat noise
            if inst.zerodha_token == 1:
                return _trim_to_transition(_candles(_fresh_long_path()),
                                           TripleSupertrendConfig())
            return _candles(list(np.linspace(100, 101, 30)))

    base = 400  # rough ATM for the fired item (rises to ~600 region trimmed earlier)
    nfo = [
        {"name": "ACME", "tradingsymbol": "ACME25JUN300CE", "instrument_type": "CE",
         "strike": 300, "expiry": "2099-01-01"},
        {"name": "ACME", "tradingsymbol": "ACME25JUN300PE", "instrument_type": "PE",
         "strike": 300, "expiry": "2099-01-01"},
    ]
    universe = [
        UniverseItem("ACME", "ACME", 1, "NSE", "NFO"),
        UniverseItem("DULL", "DULL", 2, "NSE", "NFO"),
    ]
    sc = KiteEngineScanner()
    # candles are far in the past, so drop_forming keeps the last bar
    await sc.scan(uid="u1", client=FakeClient(), universe=universe, nfo_rows=nfo,
                  bfo_rows=[], cfg=TripleSupertrendConfig(), moneyness=["ATM"])
    snap = sc.snapshot("u1")
    assert not snap.scanning and snap.generated_ms > 0
    names = [r.underlying for r in snap.rows]
    assert names == ["ACME"]  # only the firing item
    assert snap.rows[0].legs[0].option_symbol == "ACME25JUN300CE"


def test_option_order_args_maps_buy_one_lot():
    from app.engines.triple_supertrend.schemas import AlignmentChip, EngineSignalRow, OptionLeg

    row = EngineSignalRow(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL",
        alignment=AlignmentChip(fast=1, mid=1, slow=1), direction="long", option_type="CE",
        legs=[OptionLeg(moneyness="ATM", option_type="CE", option_symbol="NIFTY25JUN22000CE",
                        strike=22000.0, expiry="2026-06-26", lot_size=75)],
        spot=22010.0, stop_loss=21900.0, score=85.0, timestamp_ms=123,
    )
    args = option_order_args(row)  # primary leg
    assert args == {
        "option_symbol": "NIFTY25JUN22000CE", "side": "buy", "size": 75,
        "exchange": "NFO", "stop_loss": 21900.0,
    }
    # a put (bear) is still a BUY — this is an options-buying engine
    row.direction = "short"; row.option_type = "PE"
    assert option_order_args(row)["side"] == "buy"
    # no legs → no order
    row.legs = []
    assert option_order_args(row) is None


@pytest.mark.asyncio
async def test_scan_invokes_place_cb_for_ready_rows():
    class FakeClient:
        async def get_candles(self, inst, resolution, limit):
            if inst.zerodha_token == 1:
                return _trim_to_transition(_candles(_fresh_long_path()), TripleSupertrendConfig())
            return _candles(list(np.linspace(100, 101, 30)))

    nfo = [
        {"name": "ACME", "tradingsymbol": "ACME25JUN300CE", "instrument_type": "CE",
         "strike": 300, "expiry": "2099-01-01", "lot_size": 50},
        {"name": "ACME", "tradingsymbol": "ACME25JUN300PE", "instrument_type": "PE",
         "strike": 300, "expiry": "2099-01-01", "lot_size": 50},
    ]
    universe = [
        UniverseItem("ACME", "ACME", 1, "NSE", "NFO"),
        UniverseItem("DULL", "DULL", 2, "NSE", "NFO"),
    ]
    calls = []

    async def cb(row, item):
        leg = row.legs[0]
        calls.append((row.underlying, leg.option_symbol, leg.lot_size))

    sc = KiteEngineScanner()
    await sc.scan(uid="u1", client=FakeClient(), universe=universe, nfo_rows=nfo,
                  bfo_rows=[], cfg=TripleSupertrendConfig(), moneyness=["ATM"], place_cb=cb)
    assert calls == [("ACME", "ACME25JUN300CE", 50)]
