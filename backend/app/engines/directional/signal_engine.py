import numpy as np
from typing import List
from app.schemas.market import Candle
from app.schemas.directional import SignalResult
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.indicators.supertrend import compute_supertrend

_ST_CONFIGS = [(7, 3.0), (14, 2.0), (21, 1.0)]


def compute_signal(candles_1h: List[Candle]) -> SignalResult:
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

    st_trends: List[int] = []
    st_values: List[float] = []
    prev_trends: List[int] = []

    for period, mult in _ST_CONFIGS:
        _, trend = compute_supertrend(ha_h, ha_l, ha_c, period, mult)
        st_trends.append(int(trend[-1]))
        st_values.append(0.0)  # placeholder; line value not needed here
        prev_trends.append(int(trend[-2]) if len(trend) >= 2 else 0)

    all_green_now = all(t == 1 for t in st_trends)
    all_red_now = all(t == -1 for t in st_trends)
    all_green_prev = all(t == 1 for t in prev_trends)
    all_red_prev = all(t == -1 for t in prev_trends)

    green_arrow = all_green_now and not all_green_prev
    red_arrow = all_red_now and not all_red_prev

    if all_green_now:
        trend_val = 1
    elif all_red_now:
        trend_val = -1
    else:
        trend_val = 0

    green_count = st_trends.count(1)
    red_count = st_trends.count(-1)

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
