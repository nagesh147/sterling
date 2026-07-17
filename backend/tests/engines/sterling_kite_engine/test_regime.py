import numpy as np

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions


def test_regime_shapes_and_warmup(uptrend):
    o, h, l, c = uptrend
    cfg = SterlingKiteEngineConfig()
    r = compute_regime(o, h, l, c, cfg)
    n = len(c)
    assert r.bull.shape == (n,) and r.bear.shape == (n,)
    # warmup bars are flat (not enough data for all three STs)
    assert not r.bull[: cfg.warmup].any()
    # a strong sustained uptrend ends fully bull-aligned
    assert r.bull[-1] and not r.bear[-1]


def test_three_trend_arrays_present(uptrend):
    o, h, l, c = uptrend
    cfg = SterlingKiteEngineConfig()
    r = compute_regime(o, h, l, c, cfg)
    for tr in (r.t_fast, r.t_mid, r.t_slow):
        # past the largest warmup, every trend is committed (+1 / -1)
        assert set(np.unique(tr[cfg.warmup:])).issubset({-1, 1})


def test_trail_value_for_threshold_maps_to_line(uptrend):
    """exit-mode-aligned trail: threshold 1→fast, 2→mid, 3→slow line value, so the
    price stop is breached on the threshold-th red (not always the tightest/fast)."""
    o, h, l, c = uptrend
    cfg = SterlingKiteEngineConfig()
    r = compute_regime(o, h, l, c, cfg)
    i = len(c) - 1
    assert r.trail_value_for_threshold(i, 1) == float(r.l_fast[i])
    assert r.trail_value_for_threshold(i, 2) == float(r.l_mid[i])
    assert r.trail_value_for_threshold(i, 3) == float(r.l_slow[i])
    # unknown thresholds fall back to the tightest (fast) line — fail safe.
    assert r.trail_value_for_threshold(i, 9) == float(r.l_fast[i])
    # in a long, the wider line gives more room: fast (tightest) sits ABOVE slow.
    assert r.l_fast[i] >= r.l_slow[i]


def test_fresh_transition_fires_once(down_then_up):
    o, h, l, c = down_then_up
    cfg = SterlingKiteEngineConfig()
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    # exactly the bars where alignment becomes fresh — not every aligned bar
    assert longs.sum() >= 1
    # a transition bar must NOT have been aligned the bar before
    for i in np.where(longs)[0]:
        assert not r.bull[i - 1]
    # aligned-but-not-fresh bars exist and are excluded from the mask
    assert (r.bull & ~longs).any()
