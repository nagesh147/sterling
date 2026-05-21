"""
Smoke test for the Hybrid VCP-Momentum Scalper engine.
Runs a backtest on synthetic 15m candles to verify the full pipeline
(entry gate → position tracking → exits) produces a valid result.
"""
from __future__ import annotations

import numpy as np

from app.schemas.market import Candle
from app.engines.hybrid_vcp import run_backtest, PROFILES, BacktestReport
from app.engines.hybrid_vcp.backtest import _ohlcv_to_arrays, _atr_pct


def _synthetic_candles(n: int = 500, seed: int = 42) -> list[Candle]:
    """Generate realistic-looking synthetic BTC candles."""
    rng = np.random.default_rng(seed)
    ts = int(1718000000_000)  # start: June 2024

    candles = []
    close = 65_000.0
    for i in range(n):
        # Random walk with mild trend
        change = rng.normal(0, 200) + (i * 0.5)   # slight upward drift
        open_  = close
        close  = open_ + change
        high   = max(open_, close) + abs(rng.normal(0, 100))
        low    = min(open_, close) - abs(rng.normal(0, 100))
        vol    = rng.lognormal(8.0, 0.8)   # mean ~3000 BTC

        candles.append(Candle(
            timestamp_ms=ts + i * 15 * 60_000,
            open=round(open_, 2),
            high=round(high, 2),
            low=round(max(low, 100), 2),
            close=round(close, 2),
            volume=round(vol, 2),
        ))
    return candles


def _assert_report(r: BacktestReport) -> None:
    assert isinstance(r, BacktestReport), f"Expected BacktestReport, got {type(r)}"
    assert r.trade_count >= 0, f"trade_count should be >= 0, got {r.trade_count}"
    assert abs(r.win_rate) <= 1.0, f"win_rate {r.win_rate} out of [0,1]"
    assert len(r.equity_curve) > 0, "equity_curve should not be empty"
    # Equity should start at 1.0
    assert abs(r.equity_curve[0] - 1.0) < 1e-6, f"equity_curve[0] should be 1.0, got {r.equity_curve[0]}"
    # Equity should never be zero or negative
    assert all(e > 0 for e in r.equity_curve), "equity_curve contains non-positive values"
    # Trades if any should have valid fields
    for t in r.trades:
        assert -5.0 < t.net_pnl < 5.0, f"Trade pnl {t.net_pnl} out of reasonable range"
        # entry_bar may equal exit_bar (same-bar entry+exit) or be less (exit after entry).
        # entry_bar > exit_bar is the only impossible case.
        assert t.entry_bar <= t.exit_bar, f"entry_bar {t.entry_bar} > exit_bar {t.exit_bar}"
        assert t.direction in (-1, 1), f"direction should be ±1, got {t.direction}"
    print(f"  PASS: {r.profile} — {r.trade_count} trades | win_rate={r.win_rate:.1%} "
          f"| sharpe={r.sharpe:.2f} | max_dd={r.max_drawdown:.2%} | cagr={r.cagr:+.2%}")


def main() -> None:
    print("=== VCP Engine Smoke Test ===\n")
    print("Profiles:", list(PROFILES.keys()), "\n")

    profile_keys = list(PROFILES.keys())

    for key in profile_keys:
        profile = PROFILES[key]
        print(f"Running backtest: {key} ({profile.signal_tf} signal / {profile.regime_tf} regime)")
        try:
            candles = _synthetic_candles(n=800, seed=hash(key) & 0xFFFFFFFF)
            result = run_backtest(candles, profile, apply_slippage=True)
            _assert_report(result)
        except Exception as exc:
            print(f"  FAIL: {key} — {exc}")
            raise

    print("\n=== All profile backtests passed ===")


if __name__ == "__main__":
    main()