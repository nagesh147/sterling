import numpy as np
from typing import Generator, List
from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend

_ST_CONFIGS = [(7, 3.0), (14, 2.0), (21, 1.0)]


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
        # Shift all OHLC by (vwap - close) so spread is preserved around VWAP
        offset = vwap - c.close
        yield Candle(
            timestamp_ms=c.timestamp_ms,
            open=c.open + offset,
            high=c.high + offset,
            low=c.low + offset,
            close=vwap,
            volume=c.volume,
        )


def compute_signal(candles_1h: List[Candle], st_threshold: int = 3) -> SignalResult:
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

    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)

    # ST1: Heikin-Ashi — smoothed, filters noise
    st1_line, st1_trend = compute_supertrend(ha_h, ha_l, ha_c, 7, 3.0)

    # ST2: Real candles — medium sensitivity
    st2_line, st2_trend = compute_supertrend(h, l, c, 14, 2.0)

    # ST3: VWAP-adjusted candles — slower, trend-anchored perspective
    # H/L/O shifted by (vwap - close) so the candle is centred on VWAP
    # while preserving relative spread; avoids ATR distortion from raw VWAP lag
    vwap_candles = list(_to_vwap_candles(candles_1h))
    vwap_h = np.array([v.high for v in vwap_candles], dtype=np.float64)
    vwap_l = np.array([v.low for v in vwap_candles], dtype=np.float64)
    vwap_c = np.array([v.close for v in vwap_candles], dtype=np.float64)
    st3_line, st3_trend = compute_supertrend(vwap_h, vwap_l, vwap_c, 21, 2.0)

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

    # all_green / all_red respect the mode threshold (e.g. intraday needs 2/3, swing 3/3)
    all_green_now = green_count >= st_threshold
    all_red_now = red_count >= st_threshold
    all_green_prev = prev_green_count >= st_threshold
    all_red_prev = prev_red_count >= st_threshold

    # Arrow fires on the bar where threshold is first crossed
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
    )
