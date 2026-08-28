from dataclasses import replace

from app.engines.oi_wall_flow import (ChainSnapshot, OIWallFlowConfig,
                                      OIWallFlowStrategy, SessionState)
from tests.engines.oi_wall_flow.conftest import rows_from


def test_watching_row_always_has_a_reason(bse_snap):
    cfg = OIWallFlowConfig(min_bias_score=999).validate()
    sig = OIWallFlowStrategy(cfg).evaluate(bse_snap)
    assert sig.state == "watching"
    assert sig.reason


def test_expiry_day_excluded(bse_snap, cfg):
    snap = replace(bse_snap, days_to_expiry=0)
    sig = OIWallFlowStrategy(cfg).evaluate(snap)
    assert sig.state == "watching"
    assert "expiry day" in (sig.reason or "")


def test_dte_window(bse_snap, cfg):
    snap = replace(bse_snap, days_to_expiry=90)
    sig = OIWallFlowStrategy(cfg).evaluate(snap)
    assert sig.state == "watching"
    assert "outside" in (sig.reason or "")


def test_disabled_refuses_admission(bse_snap):
    cfg = OIWallFlowConfig(enabled=False, max_premium_at_risk_inr=50_000).validate()
    s = OIWallFlowStrategy(cfg)
    sig = s.evaluate(bse_snap)
    assert s.admit(sig, "2026-08-28") == "strategy disabled"


def test_daily_trade_limit(bse_snap, cfg):
    s = OIWallFlowStrategy(OIWallFlowConfig(max_new_trades_per_day=1,
                                            max_premium_at_risk_inr=50_000).validate(),
                           SessionState(day="2026-08-28"))
    sig = s.evaluate(bse_snap)
    s.on_entry(sig, 84.15, bse_snap.at_ms, "2026-08-28")
    s.state.positions.clear()
    assert "daily trade limit" in (s.admit(sig, "2026-08-28") or "")


def test_same_chain_twice_refused(bse_snap, cfg):
    s = OIWallFlowStrategy(cfg)
    sig = s.evaluate(bse_snap)
    s.on_entry(sig, 84.15, bse_snap.at_ms, "2026-08-28")
    assert s.admit(sig, "2026-08-28") == "already holding this chain"


def test_bearish_mirror_buys_put_wall():
    """Flip every CE/PE change sign so the same walls vote the other way."""
    flipped = []
    for r in rows_from():
        flipped.append(replace(
            r,
            call_oi_chg_pct=-r.call_oi_chg_pct,
            call_ltp_chg_pct=-r.call_ltp_chg_pct,
            put_oi_chg_pct=-r.put_oi_chg_pct,
            put_ltp_chg_pct=-r.put_ltp_chg_pct,
        ))
    snap = ChainSnapshot(underlying="BSE", spot=3392.50, expiry="2026-09-29",
                         rows=flipped, at_ms=1, days_to_expiry=32, lot_size=200)
    cfg = OIWallFlowConfig(max_premium_at_risk_inr=80_000).validate()
    sig = OIWallFlowStrategy(cfg).evaluate(snap)
    assert sig.bias.bias == "bearish"
    assert sig.state == "armed"
    assert sig.plan is not None
    assert sig.plan.option_type == "PE"
    assert sig.plan.strike == 3300


def test_config_rejects_inverted_window():
    import pytest
    with pytest.raises(ValueError):
        OIWallFlowConfig(expiry_dte_min=10, expiry_dte_max=1).validate()
