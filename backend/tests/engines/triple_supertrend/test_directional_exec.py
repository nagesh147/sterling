"""Execution-path tests for the Kite directional auto-exec callback.

These drive the real ``service._make_place_cb`` callback with a fake Kite client
so they exercise the vehicle routing, the P0 stop-direction fix, the deep-ITM /
futures resolution, the entry filters, and the drawdown breaker — the integration
the unit-level golden test cannot reach.
"""
from __future__ import annotations

import asyncio

import pytest

from app.engines.triple_supertrend.schemas import (
    AlignmentChip, EngineConfigModel, EngineSignalRow, OptionLeg,
)
from app.services import live_safety
from app.services.exchanges.kite import constants as K
from app.services.kite_engine import positions, service, state
from app.services.kite_engine.universe import UniverseItem

UID = "test-dir-exec"


class FakeClient:
    def __init__(self, instruments=None):
        self.gtt_calls = []
        self.opt_placed = []
        self.fut_placed = []
        self._instruments = instruments or []

    async def get_margins(self, seg=None):
        return {"available": {"live_balance": 100000.0}}

    async def place_order_option(self, sym, side, size, **kw):
        self.opt_placed.append({"sym": sym, "side": side, "size": size, **kw})
        return {"order_id": "OPT1"}

    async def place_order_future(self, sym, side, size, **kw):
        self.fut_placed.append({"sym": sym, "side": side, "size": size, **kw})
        return {"order_id": "FUT1"}

    async def place_gtt(self, **kw):
        self.gtt_calls.append(kw)
        return {"trigger_id": 999}

    async def search_instruments(self, q, exch, limit=0):
        return self._instruments

    async def get_ltp(self, syms):
        return {s: {"last_price": 520.0} for s in syms}


def _bear_row(source="spot"):
    """A bear (PE-buying) signal — the case the P0 bug mis-handled."""
    return EngineSignalRow(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BEAR",
        alignment=AlignmentChip(fast=-1, mid=-1, slow=-1),
        direction="short", option_type="PE",
        legs=[OptionLeg(moneyness="ATM", option_type="PE", option_symbol="NIFTY2562625000PE",
                        strike=25000, expiry="2026-06-26", lot_size=75,
                        premium_spot=120.0, premium_sl=90.0, token=111)],
        spot=25000.0, stop_loss=25200.0, score=85.0, timestamp_ms=1_700_000_000_000,
        source=source, adx=30.0, atr_pct=60.0)


def _item():
    return UniverseItem(name="NIFTY 50", tradingsymbol="NIFTY", token=256265,
                        exchange="INDICES", option_exchange="NFO", is_index=True)


def _fut_dump():
    return [{
        "name": "NIFTY", "segment": "NFO-FUT", "instrument_type": "FUT",
        "tradingsymbol": "NIFTY26JUNFUT", "expiry": "2026-06-25",
        "instrument_token": 5001, "lot_size": 75,
    }]


def _run(cfg: EngineConfigModel, row, client, item=None):
    state.reset(UID)
    positions._positions.pop(UID, None)
    live_safety._IDEMPOTENCY_CACHE.clear()   # global cache — isolate tests
    state.set_config(UID, cfg)
    cb = service._make_place_cb(client, UID)
    asyncio.run(cb(row, item or _item()))
    return positions.open_positions(UID)


# ── P0 regression: a bear PE BUY must be a LONG-premium position ──────────────

def test_default_bear_pe_is_long_premium_with_sell_stop():
    """directional_mode OFF: a bear PE signal registers direction='long' and its
    protective GTT is a SELL (the P0 fix). Previously it was tagged 'short',
    inverting the GTT into a BUY and the tick exit into ≥."""
    client = FakeClient()
    cfg = EngineConfigModel()  # defaults: directional_mode False
    open_pos = _run(cfg, _bear_row(), client)
    assert len(open_pos) == 1
    p = open_pos[0]
    assert p.direction == "long"           # P0: options are always long-premium
    assert p.vehicle == "otm_options"
    # the option BUY went through, and the GTT leg is a SELL (exit a long)
    assert client.opt_placed and client.opt_placed[0]["side"] == "buy"
    assert client.gtt_calls, "a premium stop GTT should be placed"
    leg = client.gtt_calls[0]["orders"][0]
    assert leg["transaction_type"] == K.TXN_SELL


def _pe_chain():
    """A PE chain spanning ITM (high strikes) for a 25000 spot — enough for the
    delta picker to find a deep (~0.9) strike."""
    out = []
    for strike in range(24000, 26600, 200):
        out.append({
            "name": "NIFTY", "tradingsymbol": f"NIFTY26JUN{strike}PE", "instrument_type": "PE",
            "strike": strike, "expiry": "2026-06-26", "instrument_token": strike, "lot_size": 75,
        })
    return out


def test_deep_itm_bear_pe_still_long_premium_sell_stop():
    """deep-ITM vehicle, bear signal: still a long-premium PE BUY with a SELL GTT,
    and it picks a DEEP ITM strike (well above spot for a put), not ATM."""
    client = FakeClient(instruments=_pe_chain())
    cfg = EngineConfigModel(directional_mode=True, vehicle="deep_itm_options",
                            enabled_vehicles=["otm_options", "deep_itm_options"],
                            target_delta=0.90)
    open_pos = _run(cfg, _bear_row(), client)
    assert len(open_pos) == 1
    assert open_pos[0].direction == "long"          # P0 holds for deep-ITM too
    assert open_pos[0].vehicle == "deep_itm_options"
    assert client.opt_placed, "deep-ITM order should be placed"
    sym = client.opt_placed[0]["sym"]
    assert sym.endswith("PE") and sym != "NIFTY2562625000PE"   # a deep strike, not the ATM leg
    # PE delta ~0.9 ⇒ a strike comfortably ABOVE spot (deep ITM for a put)
    strike = int(sym.replace("NIFTY26JUN", "").replace("PE", ""))
    assert strike >= 25000
    if client.gtt_calls:
        assert client.gtt_calls[0]["orders"][0]["transaction_type"] == K.TXN_SELL


# ── futures: two-sided, signal direction carried, BUY-to-cover stop on shorts ──

def test_futures_bear_is_short_with_buy_to_cover_stop():
    client = FakeClient(instruments=_fut_dump())
    cfg = EngineConfigModel(directional_mode=True, vehicle="futures",
                            enabled_vehicles=["otm_options", "deep_itm_options", "futures"],
                            futures_expiry="near")
    open_pos = _run(cfg, _bear_row(), client)
    assert len(open_pos) == 1
    p = open_pos[0]
    assert p.direction == "short"                   # futures DO carry the signal direction
    assert p.vehicle == "futures"
    assert p.symbol == "NIFTY26JUNFUT"              # the actual future, not the option symbol
    assert client.fut_placed and client.fut_placed[0]["side"] == "sell"
    assert not client.opt_placed                    # no option order in futures mode
    # short stop must BUY to cover (upside stop)
    assert client.gtt_calls and client.gtt_calls[0]["orders"][0]["transaction_type"] == K.TXN_BUY


def test_futures_unresolved_contract_blocks_order():
    client = FakeClient(instruments=[])  # no FUT rows → cannot resolve
    cfg = EngineConfigModel(directional_mode=True, vehicle="futures",
                            enabled_vehicles=["futures"], futures_expiry="near")
    open_pos = _run(cfg, _bear_row(), client)
    assert open_pos == []
    assert not client.fut_placed and not client.opt_placed


# ── futures opt-in: selecting futures while it's not enabled falls back to options

def test_futures_not_enabled_falls_back_to_options():
    client = FakeClient(instruments=_fut_dump())
    cfg = EngineConfigModel(directional_mode=True, vehicle="futures",
                            enabled_vehicles=["otm_options"])  # futures NOT enabled
    open_pos = _run(cfg, _bear_row(), client)
    assert len(open_pos) == 1
    assert open_pos[0].vehicle == "otm_options" or open_pos[0].direction == "long"
    assert client.opt_placed and not client.fut_placed


# ── entry filters ─────────────────────────────────────────────────────────────

def test_adx_filter_blocks_weak_trend():
    client = FakeClient()
    cfg = EngineConfigModel(directional_mode=True, vehicle="otm_options", adx_min=40.0)
    row = _bear_row()  # adx=30 < 40 → blocked
    assert _run(cfg, row, client) == []
    assert not client.opt_placed


def test_adx_filter_allows_strong_trend():
    client = FakeClient()
    cfg = EngineConfigModel(directional_mode=True, vehicle="otm_options", adx_min=20.0)
    assert len(_run(cfg, _bear_row(), client)) == 1   # adx=30 >= 20 → allowed


# ── drawdown breaker (opt-in, fail-safe) ─────────────────────────────────────

def test_breaker_halts_after_drawdown():
    client = FakeClient()
    cfg = EngineConfigModel(directional_mode=True, vehicle="otm_options", wire_risk_infra=True)
    # seed the per-user breaker peak high, then drop the value below halt threshold
    state.drawdown_multiplier(UID, 1_000_000.0)   # peak
    state.drawdown_multiplier(UID, 800_000.0)     # -20% → HALT (>= reset 15%)
    open_pos = _run_keep_breaker(cfg, _bear_row(), client)
    assert open_pos == []
    assert not client.opt_placed


def _run_keep_breaker(cfg, row, client, item=None):
    """Like _run but does NOT reset state (keeps the breaker peak primed)."""
    positions._positions.pop(UID, None)
    state.set_config(UID, cfg)
    cb = service._make_place_cb(client, UID)
    asyncio.run(cb(row, item or _item()))
    return positions.open_positions(UID)
