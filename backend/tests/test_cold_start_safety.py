"""
Phase 3 cold-start fail-closed tests.

Confirms calibration silence is gone and that sizing refuses to create
positive contracts without a calibrated edge.
"""
from collections import deque

import pytest

from app.engines.directional.sizing_engine import size_trade, _fractional_kelly
from app.schemas.directional import Direction
from app.schemas.execution import TradeStructure
from app.schemas.risk import RiskParams
from app.services.calibration import CalibrationService


def _structure(rr: float = 2.0) -> TradeStructure:
    return TradeStructure(
        structure_type="bull_call_spread",
        direction=Direction.LONG, legs=[],
        max_loss=100.0, max_gain=rr * 100.0,
        net_premium=100.0, risk_reward=rr,
        score=80.0, score_breakdown={},
    )


def _svc() -> CalibrationService:
    svc = CalibrationService.__new__(CalibrationService)
    svc._db_path = ":memory:"
    svc._ivr_history = {}
    svc._closed_trades = deque(maxlen=CalibrationService.WIN_RATE_N)
    return svc


# ── Calibration ───────────────────────────────────────────────────────────────


def test_empty_calibration_gives_no_win_rate_by_default():
    svc = _svc()
    assert svc.win_rate() is None
    assert svc.is_cold_start() is True


def test_explicit_fallback_works_only_when_requested():
    svc = _svc()
    assert svc.win_rate(fallback=0.55) == 0.55
    # Without fallback, still None
    assert svc.win_rate() is None


def test_regime_filtering_after_sufficient_sample():
    svc = _svc()
    for _ in range(10):
        svc._closed_trades.append({"pnl": 0.01, "regime": "BULL", "ts": 0})
    for _ in range(2):
        svc._closed_trades.append({"pnl": -0.01, "regime": "BULL", "ts": 0})
    wr_all  = svc.win_rate()
    wr_bull = svc.win_rate(regime="BULL")
    wr_bear = svc.win_rate(regime="BEAR")  # 0 samples → cold
    assert wr_all is not None
    assert wr_bull is not None and wr_bull == pytest.approx(10 / 12, abs=0.01)
    assert wr_bear is None


def test_track_filtering_when_track_recorded():
    """track filter narrows the sample; insufficient track → None."""
    svc = _svc()
    for _ in range(10):
        svc._closed_trades.append({
            "pnl": 0.01, "regime": "BULL", "track": "directional", "ts": 0,
        })
    wr_dir   = svc.win_rate(track="directional")
    wr_mean  = svc.win_rate(track="mean_reversion")
    assert wr_dir is not None
    assert wr_mean is None


# ── Sizing ────────────────────────────────────────────────────────────────────


def test_size_trade_zero_when_win_rate_unknown():
    """RiskParams flagged as win_rate_known=False → no positive contracts."""
    risk = RiskParams(win_rate=0.55, win_rate_known=False)
    out = size_trade(_structure(), risk)
    assert out.contracts == 0
    assert out.max_risk_usd == 0
    assert out.blocked_reason == "cold_start_win_rate_unknown"


def test_size_trade_zero_when_weak_edge():
    """Negative kelly (win_rate below breakeven) → fail closed."""
    risk = RiskParams(win_rate=0.20, win_rate_known=True)  # < 1/3 break-even for rr=2
    out = size_trade(_structure(rr=2.0), risk)
    assert out.contracts == 0
    assert out.blocked_reason == "non_positive_kelly_edge"


def test_size_trade_zero_when_win_rate_is_none():
    """Explicit None win_rate fails closed even with win_rate_known True."""
    risk = RiskParams(win_rate_known=True)
    risk = risk.model_copy(update={"win_rate": None})
    out = size_trade(_structure(), risk)
    assert out.contracts == 0
    assert out.blocked_reason == "cold_start_win_rate_unknown"


def test_size_trade_positive_with_known_calibrated_edge():
    risk = RiskParams(win_rate=0.55, win_rate_known=True)
    out  = size_trade(_structure(rr=2.0), risk)
    assert out.contracts >= 1
    assert out.blocked_reason is None


def test_kelly_breakeven_threshold_unchanged():
    """Sanity: the fractional-Kelly formula itself was not broken."""
    assert _fractional_kelly(0.55, 2.0) > 0
    assert _fractional_kelly(0.30, 2.0) == 0.0
