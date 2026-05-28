"""Multi-asset Statistical Arbitrage (3D Spread) scanner.

Evaluates co-integrated pairs/triads to find mean-reverting spread opportunities.
"""
from __future__ import annotations

import time
import numpy as np
from typing import List, Dict

from app.engines.statarb.config import StatArbConfig, StatArbPairConfig
from app.engines.statarb.schemas import StatArbSignal, StatArbScanResponse


def _compute_zscore_stats(spread_series: np.ndarray, window: int):
    if len(spread_series) < window:
        return 0.0, 0.0, 0.0
    recent = spread_series[-window:]
    mean = np.mean(recent)
    std = np.std(recent)
    if std == 0:
        return 0.0, float(mean), float(std)
    return float((spread_series[-1] - mean) / std), float(mean), float(std)


def scan_pair(
    pair_cfg: StatArbPairConfig,
    cfg: StatArbConfig,
    candles_x: list,
    candles_y: list,
    candles_z: list | None = None,
) -> StatArbSignal:
    """Evaluate a single pair for statistical arbitrage opportunities."""
    now_ms = int(time.time() * 1000)
    
    # We default to empty if not enough data
    def _empty(state="neutral", action="NONE"):
        return StatArbSignal(
            pair_name=pair_cfg.name, timestamp_ms=now_ms,
            asset_x=pair_cfg.asset_x, asset_y=pair_cfg.asset_y, asset_z=pair_cfg.asset_z,
            current_z=0.0, current_spread=0.0, mean_spread=0.0, std_dev=0.0,
            state=state, action=action,
            suggested_size_x=0.0, suggested_size_y=0.0, suggested_size_z=0.0
        )
        
    if not pair_cfg.enabled:
        return _empty()

    if len(candles_x) < pair_cfg.lookback_window or len(candles_y) < pair_cfg.lookback_window:
        return _empty()
        
    if pair_cfg.asset_z and (not candles_z or len(candles_z) < pair_cfg.lookback_window):
        return _empty()
        
    # Align by minimum length
    lengths = [len(candles_x), len(candles_y)]
    if candles_z:
        lengths.append(len(candles_z))
    min_len = min(lengths)
    
    cx = candles_x[-min_len:]
    cy = candles_y[-min_len:]
    cz = candles_z[-min_len:] if candles_z else None
    
    prices_x = np.maximum(np.array([float(c.close) for c in cx], dtype=np.float64), 1e-8)
    prices_y = np.maximum(np.array([float(c.close) for c in cy], dtype=np.float64), 1e-8)
    
    if cz:
        prices_z = np.maximum(np.array([float(c.close) for c in cz], dtype=np.float64), 1e-8)
        # Triangular spread: log(Y) - hedge_ratio_z * log(Z) - log(X)
        log_spread = np.log(prices_y) - pair_cfg.hedge_ratio_z * np.log(prices_z) - np.log(prices_x)
    else:
        # Standard pairs spread: log(Y) - hedge_ratio_y * log(X)
        log_spread = np.log(prices_y) - pair_cfg.hedge_ratio_y * np.log(prices_x)
        
    current_spread = float(log_spread[-1])
    zscore, mean_spread, std_dev = _compute_zscore_stats(log_spread, pair_cfg.lookback_window)
    
    state = "neutral"
    action = "NONE"
    
    # Calculate sizes based on max_position_usd (simplified equal weight for demo)
    # Size is $ value to allocate per leg. We just set target size in contracts.
    spot_x = prices_x[-1]
    spot_y = prices_y[-1]
    size_x = (cfg.max_position_usd / spot_x) if spot_x > 0 else 0
    size_y = (cfg.max_position_usd / spot_y) * pair_cfg.hedge_ratio_y if spot_y > 0 else 0
    size_z = 0
    if cz:
        spot_z = prices_z[-1]
        size_z = (cfg.max_position_usd / spot_z) * pair_cfg.hedge_ratio_z if spot_z > 0 else 0

    if zscore >= pair_cfg.zscore_entry:
        if zscore < pair_cfg.stop_loss_zscore:
            state = "armed"
            action = "ENTRY_SHORT" # Short spread (Short Y, Long X)
    elif zscore <= -pair_cfg.zscore_entry:
        if zscore > -pair_cfg.stop_loss_zscore:
            state = "armed"
            action = "ENTRY_LONG" # Long spread (Long Y, Short X)

    # In a real implementation we would track active positions to emit 'EXIT' actions
    # when zscore reverts to zscore_exit. For stateless scanning, we just mark state.
    if abs(zscore) <= pair_cfg.zscore_exit:
        action = "EXIT"

    return StatArbSignal(
        pair_name=pair_cfg.name,
        timestamp_ms=int(cx[-1].timestamp_ms),
        asset_x=pair_cfg.asset_x,
        asset_y=pair_cfg.asset_y,
        asset_z=pair_cfg.asset_z,
        current_z=zscore,
        current_spread=current_spread,
        mean_spread=mean_spread,
        std_dev=std_dev,
        state=state,
        action=action,
        suggested_size_x=float(size_x),
        suggested_size_y=float(size_y),
        suggested_size_z=float(size_z)
    )

def scan_statarb_universe(
    candles_by_res: Dict[str, Dict[str, list]],
    cfg: StatArbConfig,
) -> StatArbScanResponse:
    """Iterate over all configured pairs and evaluate stat-arb conditions."""
    now_ms = int(time.time() * 1000)
    all_signals: List[StatArbSignal] = []
    
    if not cfg.enabled:
        return StatArbScanResponse(signals=[], count=0, armed_count=0, timestamp_ms=now_ms)
        
    timeframe = cfg.timeframe
    data_tf = candles_by_res.get(timeframe, {})
    
    for pair in cfg.pairs:
        if not pair.enabled:
            continue
            
        candles_x = data_tf.get(pair.asset_x, [])
        candles_y = data_tf.get(pair.asset_y, [])
        candles_z = data_tf.get(pair.asset_z, []) if pair.asset_z else None
        
        sig = scan_pair(pair, cfg, candles_x, candles_y, candles_z)
        all_signals.append(sig)
        
    armed = sum(1 for s in all_signals if s.state == "armed" or s.action != "NONE")
    
    return StatArbScanResponse(
        signals=all_signals,
        count=len(all_signals),
        armed_count=armed,
        timestamp_ms=now_ms,
    )
