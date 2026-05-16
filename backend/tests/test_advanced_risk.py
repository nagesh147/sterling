"""
Sterling v4 — Advanced risk modules (vol-of-vol, microstructure, regime-adaptive).
"""
from __future__ import annotations

import pytest

from app.engines.risk.vol_of_vol_gate import (
    VolOfVolThresholds, compute as vov_compute,
)
from app.engines.risk.microstructure_veto import (
    MicroSnapshot, MicroVetoConfig, evaluate as micro_evaluate,
)
from app.engines.risk.regime_adaptive_sizer import (
    AdaptiveSizingConfig, adapt, regime_label, portfolio_bucket_check,
)


# ─── Vol-of-Vol ──────────────────────────────────────────────────────────


class TestVolOfVolGate:

    def test_insufficient_samples_does_not_block(self) -> None:
        d = vov_compute([50.0, 55.0])
        assert d.block_naked is False
        assert d.reason == "insufficient_data"

    def test_stable_history_does_not_block(self) -> None:
        # 30 readings hovering around 50 with std ~2 — stable
        history = [50.0 + (i % 5) for i in range(30)]
        d = vov_compute(history)
        assert d.block_naked is False
        assert d.std_pct_pts < 12.0

    def test_high_std_high_delta_blocks_naked(self) -> None:
        # Wild oscillation — std > 12 and last spike > 8 points
        history = [20.0, 60.0] * 10 + [70.0, 30.0]
        d = vov_compute(history)
        assert d.block_naked is True
        assert "vol_of_vol_unstable" in d.reason

    def test_high_std_but_calm_24h_does_not_block(self) -> None:
        # Variance over the window is high but the last 24h is quiet.
        history = [20.0, 60.0] * 10 + [50.0, 50.5]   # |Δ24h| = 0.5 < 8
        d = vov_compute(history)
        assert d.block_naked is False

    def test_custom_thresholds_apply(self) -> None:
        cfg = VolOfVolThresholds(std_threshold_pct_pts=3.0, delta_24h_threshold_pts=3.0)
        history = [50.0, 55.0, 50.0, 58.0, 49.0, 56.0, 50.0, 57.0,
                   48.0, 55.0, 51.0, 56.0, 50.0, 60.0, 50.0]
        d = vov_compute(history, cfg)
        # Should now block under the relaxed thresholds (std ~3.7, Δ24h=10)
        assert d.block_naked is True


# ─── Microstructure veto ─────────────────────────────────────────────────


def _snap(bid_qty=10.0, ask_qty=10.0, mid_spread=0.001, ref=0.001, trades=None) -> MicroSnapshot:
    return MicroSnapshot(
        bid_qty=bid_qty, ask_qty=ask_qty,
        mid_spread=mid_spread, ref_spread_1h=ref,
        last_trades=trades or [],
    )


class TestMicrostructureVeto:

    def test_balanced_book_no_veto(self) -> None:
        d = micro_evaluate("long", _snap())
        assert d.veto is False

    def test_book_heavy_against_long_vetos(self) -> None:
        # Only 5 bid vs 95 ask — long is buying into a wall of sellers
        d = micro_evaluate("long", _snap(bid_qty=5.0, ask_qty=95.0))
        assert d.veto is True
        assert d.code == "micro_book_imbalance"

    def test_book_heavy_against_short_vetos(self) -> None:
        d = micro_evaluate("short", _snap(bid_qty=95.0, ask_qty=5.0))
        assert d.veto is True

    def test_friendly_book_no_veto(self) -> None:
        # Long with heavy bid (buyers in control) — friendly
        d = micro_evaluate("long", _snap(bid_qty=95.0, ask_qty=5.0))
        assert d.veto is False

    def test_trade_pressure_veto(self) -> None:
        # 90% sell-pressure, going long
        prints = [(1.0, "sell")] * 45 + [(1.0, "buy")] * 5
        d = micro_evaluate("long", _snap(trades=prints))
        assert d.veto is True
        assert d.code == "micro_trade_pressure"

    def test_spread_blow_out_veto(self) -> None:
        d = micro_evaluate("long", _snap(mid_spread=0.005, ref=0.001))
        assert d.veto is True
        assert d.code == "micro_spread_blow_out"

    def test_disabled_when_no_data(self) -> None:
        # Empty book + no trades + no ref → no veto
        s = MicroSnapshot(bid_qty=0, ask_qty=0, mid_spread=0, ref_spread_1h=0, last_trades=[])
        d = micro_evaluate("long", s)
        assert d.veto is False

    def test_custom_config(self) -> None:
        # Tighten the imbalance threshold to 0.4
        cfg = MicroVetoConfig(book_imbalance_max=0.4)
        # bid=25, ask=75 → hostile=0.5 > 0.4
        d = micro_evaluate("long", _snap(bid_qty=25.0, ask_qty=75.0), cfg)
        assert d.veto is True


# ─── Regime-adaptive sizer ───────────────────────────────────────────────


class TestRegimeAdaptiveSizer:

    def test_compression_returns_half(self) -> None:
        assert adapt(15.0) == 0.5
        assert regime_label(15.0) == "compression"

    def test_normal_returns_one(self) -> None:
        assert adapt(45.0) == 1.0
        assert regime_label(45.0) == "normal"

    def test_healthy_expansion_boosts(self) -> None:
        assert adapt(75.0) == 1.25
        assert regime_label(75.0) == "expansion"

    def test_hyper_expansion_caps(self) -> None:
        assert adapt(95.0) == 0.75
        assert regime_label(95.0) == "hyper"

    def test_none_input_fails_open(self) -> None:
        assert adapt(None) == 1.0
        assert regime_label(None) == "unknown"

    def test_custom_config(self) -> None:
        cfg = AdaptiveSizingConfig(
            mult_compression=0.3, mult_normal=1.0,
            mult_healthy=1.5, mult_hyper=0.6,
        )
        assert adapt(10.0, cfg) == 0.3
        assert adapt(95.0, cfg) == 0.6


class TestPortfolioBucket:

    def test_fits_returns_none(self) -> None:
        assert portfolio_bucket_check(1.0, 2.0, 4.5) is None

    def test_breach_returns_reason(self) -> None:
        result = portfolio_bucket_check(3.0, 2.0, 4.5)   # 5.0 > 4.5
        assert result is not None
        assert "5.00%" in result
        assert "cap" in result.lower()

    def test_exact_fit_at_cap_passes(self) -> None:
        # 2.0 used + 2.5 new = 4.5 == cap → allowed (uses strict '>')
        assert portfolio_bucket_check(2.5, 2.0, 4.5) is None
        # One basis point over → blocked
        assert portfolio_bucket_check(2.51, 2.0, 4.5) is not None
