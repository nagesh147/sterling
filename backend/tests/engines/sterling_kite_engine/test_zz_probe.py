"""Throwaway probes for the futures price-domain fix."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest

from app.engines.sterling_kite_engine.schemas import (
    AlignmentChip, EngineConfigModel, EngineSignalRow, OptionLeg,
)
from app.services import live_safety
from app.services.exchanges.kite import constants as K
from app.services.kite_engine import positions, service, state
from app.services.kite_engine.universe import UniverseItem

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from tests.engines.sterling_kite_engine.test_directional_exec import (
    FakeClient, _fut_dump, _future_expiry, _item, _run, UID,
)


def _deriv_row():
    """A REAL derivatives-source row as scanner._eval_derivative emits it:
    ``spot`` is the CONTRACT's own premium close and ``stop_loss`` is the premium
    trail. direction is always 'long' (we BUY the contract)."""
    return EngineSignalRow(
        underlying="NIFTY 50", token=111, exchange="NFO", regime="BEAR",
        alignment=AlignmentChip(fast=-1, mid=-1, slow=-1),
        direction="long", option_type="PE",
        legs=[OptionLeg(moneyness="ATM", option_type="PE",
                        option_symbol="NIFTY2562625000PE",
                        strike=25000, expiry=_future_expiry(10), lot_size=75,
                        premium_spot=120.0, premium_sl=90.0, token=111)],
        spot=120.0, stop_loss=90.0, score=85.0, timestamp_ms=1_700_000_000_000,
        source="derivatives", adx=30.0, atr_pct=60.0)


def test_probe_derivatives_row_with_futures_vehicle():
    client = FakeClient(instruments=_fut_dump(),
                        ltp_by_symbol={"NIFTY26JUNFUT": 25_080.0})
    cfg = EngineConfigModel(directional_mode=True, vehicle="futures",
                            enabled_vehicles=["futures"], futures_expiry="near")
    open_pos = _run(cfg, _deriv_row(), client)
    print("\n=== derivatives row + futures vehicle ===")
    print("positions:", open_pos)
    for p in open_pos:
        print(f"  symbol={p.symbol} dir={p.direction} entry={p.entry_premium} "
              f"stop={p.stop_premium} dist={abs(p.entry_premium - p.stop_premium)} qty={p.qty}")
    print("fut_placed:", client.fut_placed)
    print("gtt:", client.gtt_calls)


def test_probe_short_futures_discount_basis():
    from tests.engines.sterling_kite_engine.test_directional_exec import _bear_row
    client = FakeClient(instruments=_fut_dump(),
                        ltp_by_symbol={"NIFTY26JUNFUT": 24_950.0})  # DISCOUNT −50
    cfg = EngineConfigModel(directional_mode=True, vehicle="futures",
                            enabled_vehicles=["futures"], futures_expiry="near")
    open_pos = _run(cfg, _bear_row(), client)
    p = open_pos[0]
    print("\n=== short futures, discount basis ===")
    print(f"  dir={p.direction} entry={p.entry_premium} stop={p.stop_premium}")
    print("  gtt txn:", client.gtt_calls[0]["orders"][0]["transaction_type"],
          "trigger:", client.gtt_calls[0]["trigger_values"],
          "last_price:", client.gtt_calls[0]["last_price"])
    assert p.stop_premium > p.entry_premium
    assert client.gtt_calls[0]["orders"][0]["transaction_type"] == K.TXN_BUY


def _fut_dump_expiring(days: int):
    return [{
        "name": "NIFTY", "segment": "NFO-FUT", "instrument_type": "FUT",
        "tradingsymbol": "NIFTY26JUNFUT", "expiry": _future_expiry(days),
        "instrument_token": 5001, "lot_size": 75,
    }]


def test_probe_entry_inside_square_off_window():
    from tests.engines.sterling_kite_engine.test_directional_exec import _bear_row
    client = FakeClient(instruments=_fut_dump_expiring(1),
                        ltp_by_symbol={"NIFTY26JUNFUT": 25_080.0})
    cfg = EngineConfigModel(directional_mode=True, vehicle="futures",
                            enabled_vehicles=["futures"], futures_expiry="near")
    open_pos = _run(cfg, _bear_row(), client)
    print("\n=== entry on a contract expiring TOMORROW ===")
    print("placed:", client.fut_placed)
    print("pos:", [(p.symbol, p.status, p.expiry) for p in open_pos])
    # now simulate the fill + the very next maintenance pass
    p = open_pos[0]
    positions.mark_open(UID, p.symbol, fill_price=25_080.0) if hasattr(positions, "mark_open") else None
    print("after mark:", [(q.symbol, q.status) for q in positions.open_positions(UID)])
    import app.services.kite_engine.market_hours as mh
    orig = service.is_market_open
    service.is_market_open = lambda: True
    try:
        asyncio.run(service._square_off_expiring(client, UID))
    finally:
        service.is_market_open = orig
    print("fut orders after square-off sweep:", client.fut_placed)
    print("pos after:", [(q.symbol, q.status, q.exit_reason) for q in positions._positions.get(UID, {}).values()])


@pytest.fixture(autouse=True)
def _valid_entry_data_for_execution_plumbing(monkeypatch):
    """Historical row fixtures isolate execution; session gates tested separately."""
    from app.services.kite_engine import service as execution
    monkeypatch.setattr(execution, "entry_data_block_reason", lambda *a, **kw: "")
