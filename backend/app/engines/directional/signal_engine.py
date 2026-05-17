import numpy as np
from typing import Generator, List, Optional, Tuple
from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.indicators.heikin_ashi import compute_heikin_ashi, ha_body_bull
from app.engines.indicators.supertrend import compute_supertrend
from app.engines.indicators.rsi import rsi as compute_rsi
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.keltner import keltner


def _to_vwap_candles(candles: List[Candle]) -> Generator[Candle, None, None]:
    """
    Replace close with cumulative VWAP per session (reset at 00:00 UTC).
    H/L/Open are shifted by the same VWAP offset so ATR stays proportional
    and the supertrend is not distorted by VWAP lag relative to real price.
    """
    sessions: dict = {}
    for c in candles:
        day_key = c.timestamp_ms // 86_400_000
        if day_key not in sessions:
            sessions[day_key] = {"cum_pv": 0.0, "cum_vol": 0.0}
        typical = (c.high + c.low + c.close) / 3.0
        sessions[day_key]["cum_pv"] += typical * c.volume
        sessions[day_key]["cum_vol"] += c.volume
        vwap = (
            sessions[day_key]["cum_pv"] / sessions[day_key]["cum_vol"]
            if sessions[day_key]["cum_vol"] > 0
            else c.close
        )
        offset = vwap - c.close
        yield Candle(
            timestamp_ms=c.timestamp_ms,
            open=c.open + offset,
            high=c.high + offset,
            low=c.low + offset,
            close=vwap,
            volume=c.volume,
        )


def compute_signal(
    candles_1h: List[Candle],
    st_threshold: int = 3,
    st_configs: Optional[List[Tuple[int, float]]] = None,
) -> SignalResult:
    if len(candles_1h) < 30:
        return SignalResult(
            trend=0, all_green=False, all_red=False,
            green_arrow=False, red_arrow=False,
            st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
            close_1h=candles_1h[-1].close if candles_1h else 0.0,
            score_long=0.0, score_short=0.0,
        )

    o = np.array([c.open for c in candles_1h], dtype=np.float64)
    h = np.array([c.high for c in candles_1h], dtype=np.float64)
    l = np.array([c.low for c in candles_1h], dtype=np.float64)
    c = np.array([c.close for c in candles_1h], dtype=np.float64)
    volume = np.array([candle.volume for candle in candles_1h], dtype=np.float64)

    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)

    _st_cfgs = st_configs if st_configs is not None else [(7, 3.0), (14, 2.0), (21, 2.0)]
    if len(_st_cfgs) != 3:
        raise ValueError(f"st_configs must have exactly 3 (period, multiplier) tuples, got {len(_st_cfgs)}")
    p1, m1 = _st_cfgs[0]
    p2, m2 = _st_cfgs[1]
    p3, m3 = _st_cfgs[2]

    # ST1: Heikin-Ashi — smoothed, filters noise
    st1_line, st1_trend = compute_supertrend(ha_h, ha_l, ha_c, p1, m1)

    # ST2: Real candles — medium sensitivity
    st2_line, st2_trend = compute_supertrend(h, l, c, p2, m2)

    # ST3: VWAP-adjusted candles — slower, trend-anchored perspective
    vwap_candles = list(_to_vwap_candles(candles_1h))
    vwap_h = np.array([v.high for v in vwap_candles], dtype=np.float64)
    vwap_l = np.array([v.low for v in vwap_candles], dtype=np.float64)
    vwap_c = np.array([v.close for v in vwap_candles], dtype=np.float64)
    st3_line, st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, p3, m3)

    st_trends = [int(st1_trend[-1]), int(st2_trend[-1]), int(st3_trend[-1])]
    st_values = [float(st1_line[-1]), float(st2_line[-1]), float(st3_line[-1])]
    prev_trends = [
        int(st1_trend[-2]) if len(st1_trend) >= 2 else 0,
        int(st2_trend[-2]) if len(st2_trend) >= 2 else 0,
        int(st3_trend[-2]) if len(st3_trend) >= 2 else 0,
    ]

    green_count = st_trends.count(1)
    red_count = st_trends.count(-1)
    prev_green_count = prev_trends.count(1)
    prev_red_count = prev_trends.count(-1)

    all_green_now = green_count >= st_threshold
    all_red_now = red_count >= st_threshold
    all_green_prev = prev_green_count >= st_threshold
    all_red_prev = prev_red_count >= st_threshold

    green_arrow = all_green_now and not all_green_prev
    red_arrow = all_red_now and not all_red_prev

    if all_green_now:
        trend_val = 1
    elif all_red_now:
        trend_val = -1
    else:
        trend_val = 0

    score_long = round(green_count / 3.0 * 100.0, 2)
    score_short = round(red_count / 3.0 * 100.0, 2)

    # ── v2 confluence scoring ──────────────────────────────────────────────
    rsi_vals = compute_rsi(c, 14)
    cur_rsi = float(rsi_vals[-1])

    # Volume: median (spike-resistant). Spike = > 1.5x median
    vol_median = float(np.median(volume[-20:])) if len(volume) >= 20 else float(np.median(volume))
    vol_spike = bool(volume[-1] > 1.5 * vol_median) if vol_median > 0 else False

    # BB + KC squeeze (LazyBear method)
    squeezed = False
    breakout_long = False
    breakout_short = False
    if len(c) >= 22:
        bb_lo, _, bb_hi = bollinger_bands(c, 20, 2.0)
        kc_lo, _, kc_hi = keltner(h, l, c, 20, 10, 1.5)
        squeezed = bool(bb_lo[-2] > kc_lo[-2] and bb_hi[-2] < kc_hi[-2])
        breakout_long = bool(c[-1] > bb_hi[-1])
        breakout_short = bool(c[-1] < bb_lo[-1])
    squeeze_ok = squeezed and (breakout_long or breakout_short)

    # HA body direction
    ha_bull_arr = ha_body_bull(o, h, l, c)
    if trend_val == 1:
        ha_aligned = bool(ha_bull_arr[-1])
    elif trend_val == -1:
        ha_aligned = not bool(ha_bull_arr[-1])
    else:
        ha_aligned = False

    # ST flip
    st_flip = (green_arrow if trend_val == 1 else red_arrow) if trend_val != 0 else False

    # ── HA/Real divergence filter (v3) ────────────────────────────────────────
    # When |Real close − HA close| / Real close > 0.3%, HA is smoothing reality
    # too aggressively → degrade signal quality (not a hard veto, a weight hit).
    real_close = float(c[-1])
    ha_close_cur = float(ha_c[-1]) if len(ha_c) > 0 else real_close
    ha_real_div_pct = abs(real_close - ha_close_cur) / real_close * 100.0 if real_close > 0 else 0.0
    ha_real_aligned = ha_real_div_pct < 0.3   # True = HA faithfully tracks real price

    # RSI adaptive scoring: Bull >60 / Bear <40 earns max weight (momentum confirmation).
    # Bull 40-60 / Bear 40-60 earns half weight (neutral zone, valid but weaker).
    # Outside overbought/oversold bounds vetoed elsewhere.
    if trend_val == 1:
        rsi_ok = 40.0 < cur_rsi < 78.0        # hard gate (unchanged)
        rsi_momentum = cur_rsi > 60.0          # bonus: RSI confirms momentum
    elif trend_val == -1:
        rsi_ok = 22.0 < cur_rsi < 60.0
        rsi_momentum = cur_rsi < 40.0
    else:
        rsi_ok = False
        rsi_momentum = False

    weights = {
        "st_flip":     3,
        "rsi":         2,   # base RSI gate
        "rsi_momentum":1,   # bonus for strong RSI positioning
        "squeeze":     4,
        "volume":      4,
        "ha_aligned":  4,   # was 5; split 1 pt to ha_real_aligned
        "ha_real_aligned": 2,
    }
    flags = {
        "st_flip":         st_flip,
        "rsi":             rsi_ok,
        "rsi_momentum":    rsi_momentum,
        "squeeze":         squeeze_ok,
        "volume":          vol_spike,
        "ha_aligned":      ha_aligned,
        "ha_real_aligned": ha_real_aligned,
    }
    total_weight = sum(weights.values())  # 20
    earned = sum(w for k, w in weights.items() if flags[k])
    pct = earned / total_weight

    if pct >= 0.75:
        signal_strength = "STRONG"
    elif pct >= 0.35:
        signal_strength = "SIGNAL"
    else:
        signal_strength = "NONE"

    signal_score = round(pct * 20, 2)
    # ─────────────────────────────────────────────────────────────────────

    return SignalResult(
        trend=trend_val,
        all_green=all_green_now,
        all_red=all_red_now,
        green_arrow=green_arrow,
        red_arrow=red_arrow,
        st_trends=st_trends,
        st_values=st_values,
        close_1h=float(c[-1]),
        score_long=score_long,
        score_short=score_short,
        signal_strength=signal_strength,
        signal_score=signal_score,
        rsi=round(cur_rsi, 2),
        squeezed=squeezed,
        ha_real_divergence_pct=round(ha_real_div_pct, 4),
        vol_confirm=vol_spike,
    )
