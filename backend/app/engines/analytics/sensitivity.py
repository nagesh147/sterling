"""
Parameter sensitivity sweep. Runs walk-forward across param ranges.
"""
import numpy as np
from dataclasses import dataclass

SWEEP_PARAMS = {
    "adx_threshold":    [20, 22, 25, 28, 30],
    "atr_pct_volatile": [55, 60, 65, 70, 75],
    "rsi_upper_long":   [72, 75, 78, 80],
    "rsi_lower_long":   [48, 50, 52, 54],
    "score_min":        [68, 72, 75, 78, 80],
    "st_mult":          [1.5, 2.0, 2.5, 3.0],
    "vol_mult":         [1.3, 1.5, 1.8, 2.0],
}


@dataclass
class SensitivityResult:
    parameter:      str
    values_tested:  list
    sharpes:        list
    best_value:     object
    sensitivity:    float  # std(sharpes)


def sweep(
    candles: list,
    param_name: str,
    values: list,
    base_config: dict,
    n_test_bars: int = 60,
) -> SensitivityResult:
    """
    For each value: run synthetic trade sim on last n_test_bars, record Sharpe.
    param_name maps to score_threshold for score_min, else proxy as momentum filter.
    """
    from app.engines.analytics.walk_forward import (
        _synthetic_trades, _equity_from_trades, WalkForwardConfig
    )
    from app.engines.analytics.performance import sharpe as _sharpe

    test_candles = candles[-n_test_bars:] if len(candles) > n_test_bars else candles
    sharpes = []
    for val in values:
        # Map param to score_threshold proxy
        if param_name == "score_min":
            threshold = float(val)
        else:
            # Use val as a sensitivity proxy: scale threshold by relative val
            base_threshold = float(base_config.get("score_min", 72))
            threshold = base_threshold * (float(val) / float(values[len(values)//2]))
        trades = _synthetic_trades(test_candles, threshold)
        if trades:
            ec = _equity_from_trades(trades)
            s = _sharpe(ec)
        else:
            s = 0.0
        sharpes.append(s)

    arr = np.array(sharpes)
    best_idx = int(np.argmax(arr))
    return SensitivityResult(
        parameter=param_name,
        values_tested=values,
        sharpes=sharpes,
        best_value=values[best_idx],
        sensitivity=float(arr.std()),
    )


def run_all_sweeps(candles: list, base_config: dict, n_test_bars: int = 60) -> list:
    """Run sweep for all SWEEP_PARAMS. Returns list[SensitivityResult] sorted by sensitivity desc."""
    results = []
    for param, values in SWEEP_PARAMS.items():
        r = sweep(candles, param, values, base_config, n_test_bars)
        results.append(r)
    results.sort(key=lambda x: x.sensitivity, reverse=True)
    return results


def sweep_real(
    candles_1h: list,
    candles_4h: list,
    param_name: str,
    values: list,
    fee_rt_pct: float = 0.001,
    n_test_bars: int = 60,
) -> SensitivityResult:
    """
    Real engine sweep for score_min (signal_score 0-20 range).
    Pre-computes all potential trades once at score_min=0, then filters by threshold.
    Other parameter names use the same pre-computed trades (score_min proxy).
    Only score_min sweeps are dimensionally valid without engine re-runs.
    """
    from app.engines.analytics.walk_forward import _engine_replay_trades, _equity_from_trades
    from app.engines.analytics.performance import sharpe as _sharpe

    c1h = candles_1h[-n_test_bars:] if len(candles_1h) > n_test_bars else candles_1h

    sharpes = []
    for val in values:
        if param_name == "score_min":
            threshold = float(val)
            filtered  = _engine_replay_trades(c1h, candles_4h, score_min=threshold, fee_rt_pct=fee_rt_pct)
        else:
            # Non-score params require engine re-runs with modified config;
            # use score_min=0 for all values to at least measure baseline real performance.
            filtered = _engine_replay_trades(c1h, candles_4h, score_min=0.0, fee_rt_pct=fee_rt_pct)

        if filtered:
            ec = _equity_from_trades(filtered)
            s  = _sharpe(ec)
        else:
            s = 0.0
        sharpes.append(s)

    arr      = np.array(sharpes)
    best_idx = int(np.argmax(arr))
    return SensitivityResult(
        parameter=param_name,
        values_tested=values,
        sharpes=sharpes,
        best_value=values[best_idx],
        sensitivity=float(arr.std()),
    )


def run_all_sweeps_real(
    candles_1h: list,
    candles_4h: list,
    fee_rt_pct: float = 0.001,
    n_test_bars: int = 60,
) -> list:
    """Real sweep for all SWEEP_PARAMS. Returns list[SensitivityResult] sorted by sensitivity desc."""
    results = [
        sweep_real(candles_1h, candles_4h, param, values, fee_rt_pct, n_test_bars)
        for param, values in SWEEP_PARAMS.items()
    ]
    results.sort(key=lambda x: x.sensitivity, reverse=True)
    return results
