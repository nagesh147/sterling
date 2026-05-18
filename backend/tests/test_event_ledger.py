"""
Phase 4 research event ledger tests.

Verifies:
  * default backtest output is unchanged (no `events` key when not requested)
  * `events` appear when explicitly requested
  * events are appended in chronological / append order
  * exit / trade events include cost breakdowns
  * trade events include gross + net PnL
  * rejected candidates carry a veto reason
"""
import time as _time

import pytest

from app.engines.backtest.event_ledger import EventKind, EventLedger
from app.engines.backtest.backtest_mtf import run_mtf_backtest
from app.schemas.market import Candle as _Candle


def _make_candles_ms(n, base, trend, bar_ms):
    now_ms = int(_time.time() * 1000)
    out = []
    for i in range(n):
        ts = now_ms - (n - i) * bar_ms
        price = base + trend * i + (i % 3) * 0.5
        out.append(_Candle(
            timestamp_ms=ts, open=price, high=price * 1.001,
            low=price * 0.999, close=price, volume=100.0 + i,
        ))
    return out


# ── unit: EventLedger ─────────────────────────────────────────────────────────


def test_event_ledger_append_order_preserved():
    led = EventLedger()
    led.record_candidate(bar_idx=1, ts_ms=100, asset="BTC",
                         profile="P", track="t")
    led.record_skip(bar_idx=2, ts_ms=200, asset="BTC", profile="P",
                    track="t", reason="filtered")
    led.record_entry({
        "bar_idx": 3, "ts_ms": 300, "asset": "BTC",
        "profile": "P", "track": "t",
        "direction": "long", "entry_price": 100.0,
    })
    assert [e.kind for e in led.events] == [
        EventKind.CANDIDATE, EventKind.SKIP, EventKind.ENTRY,
    ]
    assert [e.seq for e in led.events] == [0, 1, 2]


def test_ledger_event_has_serializable_dict():
    led = EventLedger()
    led.record_skip(
        bar_idx=1, ts_ms=100, asset="BTC", profile="P", track="t",
        reason="setup_filtered",
    )
    d = led.events_as_dicts()[0]
    assert d["kind"] == "skip"
    assert d["payload"]["reason"] == "setup_filtered"
    assert d["seq"] == 0


def test_trade_event_contains_gross_and_net_pnl():
    led = EventLedger()
    led.record_trade({
        "entry_bar": 1, "exit_bar": 5,
        "entry_ts_ms": 100, "exit_ts_ms": 500,
        "entry_price": 100.0, "exit_price": 105.0,
        "direction": "long", "regime": "BULL",
        "gross_pnl_pct": 0.05, "net_pnl_pct": 0.045, "cost_pct": 0.005,
        "asset": "BTC", "profile": "P", "track": "t",
    })
    ev = led.events_as_dicts()[0]
    assert ev["kind"] == "trade"
    assert ev["payload"]["gross_pnl_pct"] == pytest.approx(0.05)
    assert ev["payload"]["net_pnl_pct"]   == pytest.approx(0.045)


def test_exit_event_includes_cost_breakdown():
    led = EventLedger()
    led.record_exit({
        "exit_bar": 5, "exit_ts_ms": 500, "asset": "BTC",
        "profile": "P", "track": "t",
        "direction": "long", "exit_price": 105.0,
        "forced_end": False,
        "slippage_pct": 0.001, "fee_pct": 0.001,
        "funding_pct": 0.0002, "option_spread_pct": 0.0,
        "cost_pct": 0.0022,
    })
    payload = led.events_as_dicts()[0]["payload"]
    assert payload["slippage_pct"] == pytest.approx(0.001)
    assert payload["fee_pct"]      == pytest.approx(0.001)
    assert payload["funding_pct"]  == pytest.approx(0.0002)
    assert payload["cost_pct"]     == pytest.approx(0.0022)


def test_skip_event_can_carry_veto_reason():
    led = EventLedger()
    led.record_skip(
        bar_idx=4, ts_ms=400, asset="ETH", profile="Intraday 1H",
        track="directional", reason="choppy_regime_veto",
        features={"adx": 8.0, "atr_pct": 0.4},
    )
    payload = led.events_as_dicts()[0]["payload"]
    assert payload["reason"] == "choppy_regime_veto"
    assert payload["features"]["adx"] == 8.0


# ── integration: MTF backtest emission ────────────────────────────────────────


def test_mtf_default_output_has_no_events_key():
    """Default output shape unchanged (back-compat)."""
    c_15m = _make_candles_ms(200, 30000, 5, 15 * 60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60 * 60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4 * 60 * 60_000)
    result = run_mtf_backtest("BTC", c_15m, c_1h, c_4h, profiles=["scalping_15m"])
    r = result["scalping_15m"]
    assert "events" not in r


def test_mtf_emits_events_when_requested():
    c_15m = _make_candles_ms(200, 30000, 5, 15 * 60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60 * 60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4 * 60 * 60_000)
    result = run_mtf_backtest(
        "BTC", c_15m, c_1h, c_4h, profiles=["scalping_15m"],
        emit_events=True,
    )
    r = result["scalping_15m"]
    assert "events" in r
    assert isinstance(r["events"], list)


def test_mtf_event_order_is_chronological_within_replay():
    """Events emitted by the engine should be in append order = chronological."""
    c_15m = _make_candles_ms(200, 30000, 5, 15 * 60_000)
    c_1h  = _make_candles_ms(120, 30000, 5, 60 * 60_000)
    c_4h  = _make_candles_ms(80,  30000, 5, 4 * 60 * 60_000)
    result = run_mtf_backtest(
        "BTC", c_15m, c_1h, c_4h, profiles=["scalping_15m"],
        emit_events=True,
    )
    events = result["scalping_15m"]["events"]
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs)
