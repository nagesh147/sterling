import numpy as np
from app.engines.sterling_v2.sizing import vol_target_weights


def test_weights_no_lookahead_prefix_stable():
    r = np.random.default_rng(1).normal(0, 0.03, 100)
    w_full = vol_target_weights(r)
    w_pref = vol_target_weights(r[:60])
    assert np.allclose(w_full[:60], w_pref)  # weight_i uses only returns[:i]


def test_low_vol_scales_up_high_vol_scales_down():
    # Use returns with real dispersion (constant arrays have std 0 -> weight 1.0).
    rng = np.random.default_rng(2)
    calm = rng.normal(0.0, 0.002, 40)   # low vol -> scale up (toward the cap)
    wild = rng.normal(0.0, 0.10, 40)    # high vol -> scale down
    assert vol_target_weights(calm, target_vol=0.02)[-1] > 1.0
    assert vol_target_weights(wild, target_vol=0.02)[-1] < 1.0


def test_weight_is_capped():
    rng = np.random.default_rng(3)
    tiny = rng.normal(0.0, 1e-4, 40)    # near-zero vol would imply huge leverage
    assert vol_target_weights(tiny, target_vol=0.02, cap=3.0).max() <= 3.0


def test_first_five_trades_are_unit_weight():
    r = np.random.default_rng(4).normal(0, 0.05, 20)
    assert np.all(vol_target_weights(r)[:5] == 1.0)
