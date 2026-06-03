from __future__ import annotations
from dataclasses import dataclass
from .config import (SPLIT, MAX_DD_CAP, MIN_TEST_TRADES, MAX_PBO, MAX_P_LOSS,
                     MIN_OOS_SHARPE, MIN_DSR)


def split_indices(n: int) -> tuple[slice, slice, slice]:
    """Chronological train/validation/test split (no shuffling)."""
    a = int(n * SPLIT[0])
    b = int(n * (SPLIT[0] + SPLIT[1]))
    return slice(0, a), slice(a, b), slice(b, n)


@dataclass
class GateReport:
    passed: bool
    reasons: list[str]
    metrics: dict


def check_gates(test_metrics: dict, oos_sharpe: float, pbo: float,
                p_loss: float, dsr: float) -> GateReport:
    """Evaluate the pre-registered acceptance gates against test-set results.
    All thresholds come from config.py and are fixed BEFORE the test set is seen."""
    reasons: list[str] = []
    if test_metrics["trades"] < MIN_TEST_TRADES:
        reasons.append(f"trades {test_metrics['trades']} < {MIN_TEST_TRADES}")
    if test_metrics["max_dd"] < -MAX_DD_CAP:
        reasons.append(f"maxDD {test_metrics['max_dd']:.2%} worse than -{MAX_DD_CAP:.0%}")
    if oos_sharpe <= MIN_OOS_SHARPE:
        reasons.append(f"oos_sharpe {oos_sharpe:.2f} <= {MIN_OOS_SHARPE}")
    if pbo >= MAX_PBO:
        reasons.append(f"PBO {pbo:.2f} >= {MAX_PBO}")
    if p_loss > MAX_P_LOSS:
        reasons.append(f"p_loss {p_loss:.2f} > {MAX_P_LOSS}")
    if dsr <= MIN_DSR:
        reasons.append(f"DSR {dsr:.2f} <= {MIN_DSR}")
    return GateReport(passed=not reasons, reasons=reasons, metrics=test_metrics)
