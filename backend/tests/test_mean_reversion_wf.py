"""Walk-forward mean-reversion search — the no-lookahead guarantee.

The whole point of anchored walk-forward is that the parameters traded in a
window were chosen using ONLY data before that window. `select_best` is the
pure function that enforces it; these tests pin that it cannot see the future.
"""
import pandas as pd

from study.mean_reversion_wf import select_best


def _combo(name, entry_times, pnls):
    return (name, pd.DataFrame({"entry_time": pd.to_datetime(entry_times),
                                "pnl_pct": pnls}))


def test_select_best_ignores_trades_after_cutoff():
    cutoff = pd.Timestamp("2025-01-01")
    # A: 20 strong, varied trades entirely BEFORE the cutoff (high train Sharpe).
    a = _combo("A", ["2024-06-01"] * 20, [0.06, 0.04] * 10)
    # B: flat/zero before the cutoff, then enormous wins AFTER it. If selection
    # leaked future data, B's full Sharpe would dominate and B would be picked.
    b = _combo("B", ["2024-06-01"] * 20 + ["2025-06-01"] * 20,
               ([0.005, -0.005] * 10) + [0.5] * 20)
    # B listed first so A must win on merit, not iteration order.
    sel = select_best([b, a], cutoff, min_train_trades=20)
    assert sel is not None and sel[0] == "A"


def test_select_best_requires_min_train_trades():
    cutoff = pd.Timestamp("2025-01-01")
    a = _combo("A", ["2024-06-01"] * 5, [0.06, 0.04, 0.06, 0.04, 0.06])
    assert select_best([a], cutoff, min_train_trades=20) is None


def test_select_best_returns_none_when_no_combo_has_enough_history():
    cutoff = pd.Timestamp("2024-01-01")
    # All trades fall after the cutoff → zero train trades for everyone.
    a = _combo("A", ["2025-06-01"] * 30, [0.06, 0.04] * 15)
    assert select_best([a], cutoff, min_train_trades=20) is None
