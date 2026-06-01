"""
Lot-aware sizing: a position's `contracts` is the number of EXCHANGE lots, and
`contract_value` is the size of one lot in the underlying (Delta India: BTC=0.001,
ETH=0.01, SOL=1). Coin quantity = contracts * contract_value, and ALL value / risk
/ P&L must be derived from that quantity — not from `contracts` treated as coins.

`contract_value` defaults to 1.0 so every legacy path (options, directional, manual)
keeps its old coin-based behavior unchanged.
"""
import time
import uuid
import pytest


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_futures_sized(contracts: int, contract_value: float, entry: float,
                        stop: float, max_risk: float):
    from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract
    from app.schemas.directional import Direction
    leg = CandidateContract(
        instrument_name="ETH-PERP", underlying="ETH", option_type="futures",
        strike=entry, expiry_date="", dte=0, mark_price=entry, mid_price=entry,
        bid=0.0, ask=0.0, mark_iv=0.0, delta=1.0,
        open_interest=0.0, volume_24h=0.0, spread_pct=0.0,
        health_score=0.0, healthy=True,
    )
    struct = TradeStructure(
        structure_type="futures", direction=Direction.LONG, legs=[leg],
        net_premium=entry, max_loss=entry * 0.03, max_gain=None,
        risk_reward=2.0, score=0.0, score_breakdown={}, leverage=2,
    )
    return SizedTrade(
        structure=struct, contracts=contracts, contract_value=contract_value,
        position_value=contracts * contract_value * entry,
        max_risk_usd=max_risk, capital_at_risk_pct=0.0,
    )


def _make_open_pos(sized, entry_spot: float):
    from app.schemas.positions import PaperPosition, PositionStatus
    return PaperPosition(
        id=uuid.uuid4().hex[:8].upper(), underlying="ETH",
        sized_trade=sized, status=PositionStatus.OPEN,
        entry_timestamp_ms=int(time.time() * 1000), entry_spot_price=entry_spot,
        is_paper=True,
    )


# ─── SizedTrade.qty ──────────────────────────────────────────────────────────

def test_qty_defaults_to_contracts_when_cv_unset():
    """Legacy positions (no contract_value) keep qty == contracts (coin == lot)."""
    from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract
    from app.schemas.directional import Direction
    leg = CandidateContract(
        instrument_name="BTC-PERP", underlying="BTC", option_type="futures",
        strike=50000.0, expiry_date="", dte=0, mark_price=50000.0, mid_price=50000.0,
        bid=0.0, ask=0.0, mark_iv=0.0, delta=1.0, open_interest=0.0, volume_24h=0.0,
        spread_pct=0.0, health_score=0.0, healthy=True,
    )
    struct = TradeStructure(
        structure_type="futures", direction=Direction.LONG, legs=[leg],
        net_premium=50000.0, max_loss=1.0, max_gain=None, risk_reward=2.0,
        score=0.0, score_breakdown={}, leverage=1,
    )
    st = SizedTrade(structure=struct, contracts=4, position_value=200000.0,
                    max_risk_usd=400.0, capital_at_risk_pct=0.0)
    assert st.contract_value == 1.0
    assert st.qty == pytest.approx(4.0)


def test_qty_scales_by_contract_value():
    """ETH: 42 lots * 0.01 = 0.42 ETH."""
    st = _make_futures_sized(contracts=42, contract_value=0.01, entry=1976.3,
                             stop=1973.34, max_risk=1000.0)
    assert st.qty == pytest.approx(0.42)


# ─── close_position P&L scales by contract_value ─────────────────────────────

def test_close_position_pnl_uses_contract_value():
    """ETH 42 lots (0.42 ETH), entry 1976 -> exit 1986 => +10 * 0.42 = +4.2."""
    from app.services import paper_store as ps
    sized = _make_futures_sized(contracts=42, contract_value=0.01, entry=1976.0,
                                stop=1973.0, max_risk=1000.0)
    pos = _make_open_pos(sized, entry_spot=1976.0)
    ps._positions[pos.id] = pos
    try:
        r = ps.close_position(pos.id, exit_spot_price=1986.0)
        assert r.realized_pnl_usd == pytest.approx(4.2, abs=0.01)
    finally:
        ps._positions.pop(pos.id, None)


def test_close_position_legacy_cv1_unchanged():
    """A legacy cv=1.0 futures position keeps the old coin P&L: +1 * 4 = +4 per $1."""
    from app.services import paper_store as ps
    sized = _make_futures_sized(contracts=4, contract_value=1.0, entry=50000.0,
                                stop=49000.0, max_risk=100000.0)
    pos = _make_open_pos(sized, entry_spot=50000.0)
    pos = pos.model_copy(update={"underlying": "BTC"})
    ps._positions[pos.id] = pos
    try:
        r = ps.close_position(pos.id, exit_spot_price=50100.0)
        # +100 spot move * 4 contracts * cv 1.0 = +400
        assert r.realized_pnl_usd == pytest.approx(400.0, abs=0.5)
    finally:
        ps._positions.pop(pos.id, None)


# ─── _create_paper_tracking value/risk use contract_value ────────────────────

def test_paper_tracking_value_and_risk_use_contract_value():
    from app.api.v1.endpoints.trading import _create_paper_tracking, LiveOrderRequest
    from app.services import paper_store as ps
    body = LiveOrderRequest(
        underlying="ETH", direction="long", instrument_type="futures",
        size=42, leverage=2, order_type="market",
        stop_loss=1973.34, take_profit=1985.0, contract_value=0.01,
        notes="[SCALP-PRICE_ACTION] [AUTO] long test",
    )
    pid = _create_paper_tracking(body, "ETH", entry_price=1976.3)
    assert pid
    try:
        pos = ps._positions[pid]
        # notional = 42 * 0.01 * 1976.3 = 829.05
        assert pos.sized_trade.position_value == pytest.approx(829.05, abs=1.0)
        # risk = |1976.3 - 1973.34| * 42 * 0.01 = 2.96 * 0.42 = 1.244
        assert pos.sized_trade.max_risk_usd == pytest.approx(1.244, abs=0.05)
        assert pos.sized_trade.contract_value == pytest.approx(0.01)
    finally:
        ps._positions.pop(pid, None)


# ─── scalping lot sizing helper ──────────────────────────────────────────────

def test_contracts_from_units_eth_lot():
    """0.42 ETH / 0.01 lot = 42 contracts (was floored to 0 by the old coin math)."""
    from app.api.v1.endpoints.scalping import _contracts_from_units
    assert _contracts_from_units(0.4217, 0.01) == 42


def test_contracts_from_units_sol_lot_one():
    from app.api.v1.endpoints.scalping import _contracts_from_units
    assert _contracts_from_units(26.0, 1.0) == 26


def test_contracts_from_units_rejects_sub_lot():
    """A position smaller than one whole lot rounds to 0 (caller treats as too small)."""
    from app.api.v1.endpoints.scalping import _contracts_from_units
    assert _contracts_from_units(0.42, 1.0) == 0      # 0.42 of a 1-coin lot
    assert _contracts_from_units(0.0003, 0.001) == 0  # 0.3 of a BTC lot


# ─── cv source: adapter parses Delta /v2/products contract_value ─────────────

def test_adapter_get_contract_value_from_products(monkeypatch):
    import asyncio
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
    ad = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=True)
    products = {"result": [
        {"symbol": "BTCUSD", "id": 27, "contract_value": "0.001"},
        {"symbol": "ETHUSD", "id": 3136, "contract_value": "0.01"},
        {"symbol": "SOLUSD", "id": 14823, "contract_value": "1"},
    ]}

    async def fake_get(path, params=None):
        return products

    monkeypatch.setattr(ad, "_public_get", fake_get)
    assert asyncio.run(ad.get_contract_value("ETHUSD")) == pytest.approx(0.01)
    # The single /v2/products scan captures every symbol's lot size at once.
    assert asyncio.run(ad.get_contract_value("BTCUSD")) == pytest.approx(0.001)
    assert asyncio.run(ad.get_contract_value("SOLUSD")) == pytest.approx(1.0)


def test_adapter_get_contract_value_when_product_id_already_cached(monkeypatch):
    """Regression: in a live process get_product_id has usually already cached the
    product_id (warmed at startup) and early-returns WITHOUT scanning /v2/products.
    get_contract_value must still resolve the lot size, not silently fall back to
    1.0 (which re-introduces the size_too_small bug for ETH/BTC)."""
    import asyncio
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
    ad = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=True)
    # Simulate a warm process: product_id already known, cv cache still cold.
    ad._product_id_cache["ETHUSD"] = 3136

    async def fake_get(path, params=None):
        return {"result": [{"symbol": "ETHUSD", "id": 3136, "contract_value": "0.01"}]}

    monkeypatch.setattr(ad, "_public_get", fake_get)
    assert asyncio.run(ad.get_contract_value("ETHUSD")) == pytest.approx(0.01)


def test_adapter_get_contract_value_unknown_falls_back_to_one(monkeypatch):
    import asyncio
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
    ad = DeltaIndiaAdapter(api_key="", api_secret="", is_paper=True)

    async def fake_get(path, params=None):
        return {"result": [{"symbol": "ETHUSD", "id": 3136, "contract_value": "0.01"}]}

    monkeypatch.setattr(ad, "_public_get", fake_get)
    # Symbol not in products → lookup fails → safe fallback of 1.0 (coin == lot).
    assert asyncio.run(ad.get_contract_value("DOGEUSD")) == pytest.approx(1.0)
