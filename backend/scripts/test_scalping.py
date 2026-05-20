import sys
from pathlib import Path
import sqlite3
import numpy as np

_HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HERE))

from app.schemas.market import Candle
from app.engines.backtest import backtest_mtf
from app.engines.backtest.backtest_mtf import run_mtf_backtest, PROFILES, TFProfile
from app.services.funding import default_funding_8h_pct
from app.schemas.directional import TradeState, Direction, MacroRegime, SetupResult
from app.engines.directional import setup_engine

def _load_candles(symbol: str, resolution: str, db_path: Path):
    db_res = {"15m": "15m", "1H": "1h", "4H": "4h", "1D": "1D"}.get(resolution, resolution.lower())
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=30.0)
    rows = conn.execute(
        "SELECT time, open, high, low, close, volume FROM ohlcv "
        "WHERE symbol=? AND resolution=? ORDER BY time ASC",
        (symbol, db_res),
    ).fetchall()
    conn.close()
    return [
        Candle(timestamp_ms=int(t) * 1000, open=float(o), high=float(h),
               low=float(l), close=float(c), volume=float(v or 0.0))
        for t, o, h, l, c, v in rows
    ]

# Original evaluate_setup from backtest_mtf
_orig_evaluate_setup = backtest_mtf.evaluate_setup

def run_test(st_configs, stop_mult, tp_mult, trail_mult, hold_bars, score_min, trend_only=False):
    db_path = _HERE / "sterling_paper.db"
    candles_15m = _load_candles("BTCUSD", "15m", db_path)
    candles_1h  = _load_candles("BTCUSD", "1H", db_path)
    candles_4h  = _load_candles("BTCUSD", "4H", db_path)
    
    # Configure PROFILES["scalping_15m"]
    PROFILES["scalping_15m"].st_configs = st_configs
    PROFILES["scalping_15m"].hold_bars = hold_bars
    PROFILES["scalping_15m"].exit_atr_tf = "signal"
    PROFILES["scalping_15m"].payoff_mode = "signal_atr_v4"
    PROFILES["scalping_15m"].v4_stop_mult = stop_mult
    PROFILES["scalping_15m"].v4_tp_mult = tp_mult
    PROFILES["scalping_15m"].v4_trail_mult = trail_mult
    
    if trend_only:
        def patched_evaluate_setup(regime, signal):
            res = _orig_evaluate_setup(regime, signal)
            macro = regime.macro_regime
            is_trend = macro in {
                MacroRegime.BULLISH, MacroRegime.BEARISH,
                MacroRegime.BULL_TRENDING, MacroRegime.BEAR_TRENDING,
                MacroRegime.BULL_TREND, MacroRegime.BEAR_TREND
            }
            if not is_trend and res.state == TradeState.CONFIRMED_SETUP_ACTIVE:
                return SetupResult(
                    state=TradeState.FILTERED,
                    direction=Direction.NEUTRAL,
                    reason="Scalping 15m trend-only mode vetoes non-trending regime",
                    macro_regime=macro,
                    signal_trend=signal.trend
                )
            return res
        backtest_mtf.evaluate_setup = patched_evaluate_setup
    else:
        backtest_mtf.evaluate_setup = _orig_evaluate_setup
        
    funding = default_funding_8h_pct("BTC")
    
    results = run_mtf_backtest(
        underlying="BTC",
        candles_15m=candles_15m, candles_1h=candles_1h,
        candles_4h=candles_4h, c_1d=[],
        profiles=["scalping_15m"],
        funding_8h_pct=funding,
        apply_slippage=True,
        emit_events=True,
        score_min=score_min,
    )
    
    # Restore original function
    backtest_mtf.evaluate_setup = _orig_evaluate_setup
    
    res = results.get("scalping_15m", {})
    sh = res.get('sharpe')
    sh_val = float(sh) if sh is not None else -99.0
    return {
        "trades": res.get("total_trades"),
        "sharpe": sh_val,
        "net_sum": res.get("net_pnl_pct_sum"),
        "win_rate": res.get("win_rate"),
        "pf": res.get("profit_factor")
    }

if __name__ == "__main__":
    import itertools

    st_opts = [
        [(10, 2.5), (15, 2.0), (20, 1.5)],
        [(10, 3.0), (14, 2.0), (20, 1.5)],
    ]
    mults = [
        (2.0, 4.0, 3.0),
        (3.0, 6.0, 4.5),
        (4.0, 8.0, 6.0),
    ]
    holds = [24, 48, 72]
    scores = [14.0, 16.0, 18.0]
    
    for trend_only in [True, False]:
        print(f"\n--- SWEEPING (trend_only={trend_only}) ---")
        best_sharpe = -99.0
        best_params = None
        
        for st, m, hold, sc in itertools.product(st_opts, mults, holds, scores):
            res = run_test(st, m[0], m[1], m[2], hold, sc, trend_only=trend_only)
            sh = res["sharpe"]
            trades = res["trades"]
            if trades >= 20:
                if sh > -0.5 or sh > best_sharpe:
                    print(f"STs: {st} | M: {m} | Hold: {hold} | Score: {sc} | Trades: {trades} | Sharpe: {sh:.3f} | Net: {res['net_sum']:.4f} | WinRate: {res['win_rate']}%")
                if sh > best_sharpe:
                    best_sharpe = sh
                    best_params = (st, m, hold, sc, res)

        print("\n" + "="*50)
        print(f"BEST PARAMETERS FOUND FOR trend_only={trend_only}:")
        if best_params:
            print(f"STs: {best_params[0]}")
            print(f"Multipliers: {best_params[1]}")
            print(f"Hold Bars: {best_params[2]}")
            print(f"Score Min: {best_params[3]}")
            print(f"Result: {best_params[4]}")
        else:
            print("No configuration with >= 20 trades found.")
        print("="*50)
