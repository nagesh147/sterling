import numpy as np

from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions


def test_regime_shapes_and_warmup(uptrend):
    o, h, l, c = uptrend
    cfg = TripleSupertrendConfig()
    r = compute_regime(o, h, l, c, cfg)
    n = len(c)
    assert r.bull.shape == (n,) and r.bear.shape == (n,)
    # warmup bars are flat (not enough data for all three STs)
    assert not r.bull[: cfg.warmup].any()
    # a strong sustained uptrend ends fully bull-aligned
    assert r.bull[-1] and not r.bear[-1]


def test_three_trend_arrays_present(uptrend):
    o, h, l, c = uptrend
    cfg = TripleSupertrendConfig()
    r = compute_regime(o, h, l, c, cfg)
    for tr in (r.t_fast, r.t_mid, r.t_slow):
        # past the largest warmup, every trend is committed (+1 / -1)
        assert set(np.unique(tr[cfg.warmup:])).issubset({-1, 1})


def test_fresh_transition_fires_once(down_then_up):
    o, h, l, c = down_then_up
    cfg = TripleSupertrendConfig()
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    # exactly the bars where alignment becomes fresh — not every aligned bar
    assert longs.sum() >= 1
    # a transition bar must NOT have been aligned the bar before
    for i in np.where(longs)[0]:
        assert not r.bull[i - 1]
    # aligned-but-not-fresh bars exist and are excluded from the mask
    assert (r.bull & ~longs).any()
