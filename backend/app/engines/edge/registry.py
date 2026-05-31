"""Edge registry — which (symbol, tf, strategy, profile) combos may trade live.

Loads `backtest_edge_results.csv` (produced by comprehensive_backtest.py) and
admits only combos that cleared the gate. The live edge feed asks this registry
"am I allowed to emit a signal for this combo, and how strong is it?" — so the
only signals that reach the candidate tables are ones the backtest proved.

Re-run the backtest → re-load the registry and the allow-list updates itself.
No hardcoded winners.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field

# Profiles map to the SL/TP ATR multiples used by both the backtest and the
# live feed. Kept here so signals.py can size stops without re-reading the CSV.
PROFILE_ATR = {
    "Scalping": {"atr_sl": 1.0, "atr_tp": 2.0},
    "Intraday": {"atr_sl": 2.0, "atr_tp": 3.5},
    "Aggressive": {"atr_sl": 1.5, "atr_tp": 4.5},
}


@dataclass(frozen=True)
class EdgeGate:
    """Threshold a combo must clear to emit live signals.

    The raw in-sample gate (net_return / sharpe / trades) is the original floor.
    The robustness gate (min_oos_sharpe / max_p_loss) is additive and reads the
    optional `oos_sharpe` / `p_loss` columns produced by `robustness_scan.py`
    (CPCV out-of-sample Sharpe + Monte-Carlo probability of loss). Its defaults
    are no-ops, so CSVs without those columns behave exactly as before.
    """
    min_net_return: float = 0.0   # strictly positive net return required
    min_sharpe: float = 0.8
    min_trades: int = 50
    # Robustness gate — additive. Defaults disable it (oos always passes a
    # -inf floor; p_loss ≤ 1.0 is vacuous for a probability).
    min_oos_sharpe: float = -1e18
    max_p_loss: float = 1.0

    def passes(
        self, *, net_return: float, sharpe: float, trades: int,
        oos_sharpe: float = float("inf"), p_loss: float = 0.0,
    ) -> bool:
        return (net_return > self.min_net_return
                and sharpe >= self.min_sharpe
                and trades >= self.min_trades
                and oos_sharpe > self.min_oos_sharpe
                and p_loss <= self.max_p_loss)


def signal_score_from_metrics(*, sharpe: float, expectancy: float, pf: float) -> float:
    """Map backtest quality → 0-100 conviction score.

    Anchored on Sharpe (risk-adjusted edge is what survived OOS), nudged by
    per-trade expectancy and profit factor. Clamped to [0, 100].
    """
    raw = 40.0 + 25.0 * sharpe + 2000.0 * expectancy + 15.0 * (pf - 1.0)
    return max(0.0, min(100.0, raw))


@dataclass(frozen=True)
class EdgeCombo:
    symbol: str
    tf: str
    strategy: str
    profile: str
    trades: int
    win_rate: float
    pf: float
    sharpe: float
    expectancy: float
    net_return: float
    pnl_usd: float
    max_dd: float
    signal_score: float
    oos_sharpe: float = float("inf")   # CPCV out-of-sample Sharpe (∞ = not measured)
    p_loss: float = 0.0                # Monte-Carlo probability of loss (0 = not measured)

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.symbol.upper(), self.tf, self.strategy, self.profile)


@dataclass
class EdgeRegistry:
    combos: dict[tuple[str, str, str, str], EdgeCombo] = field(default_factory=dict)

    def allowed(self, symbol: str, tf: str, strategy: str, profile: str) -> bool:
        return (symbol.upper(), tf, strategy, profile) in self.combos

    def get(self, symbol: str, tf: str, strategy: str, profile: str) -> EdgeCombo | None:
        return self.combos.get((symbol.upper(), tf, strategy, profile))

    def all(self) -> list[EdgeCombo]:
        return list(self.combos.values())


def _f(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def load_edge_registry(csv_path: str, gate: EdgeGate | None = None) -> EdgeRegistry:
    gate = gate or EdgeGate()
    reg = EdgeRegistry()
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            net_return = _f(row, "net_return")
            sharpe = _f(row, "sharpe")
            trades = int(_f(row, "trades"))
            # Robustness columns are optional — default to always-pass values so
            # legacy CSVs (no oos_sharpe/p_loss) behave exactly as before.
            oos_sharpe = _f(row, "oos_sharpe", float("inf"))
            p_loss = _f(row, "p_loss", 0.0)
            if not gate.passes(net_return=net_return, sharpe=sharpe, trades=trades,
                               oos_sharpe=oos_sharpe, p_loss=p_loss):
                continue
            pf = _f(row, "pf")
            expectancy = _f(row, "expectancy")
            combo = EdgeCombo(
                symbol=row["symbol"].upper(),
                tf=row["tf"],
                strategy=row["strategy"],
                profile=row["profile"],
                trades=trades,
                win_rate=_f(row, "win_rate"),
                pf=pf,
                sharpe=sharpe,
                expectancy=expectancy,
                net_return=net_return,
                pnl_usd=_f(row, "pnl_usd"),
                max_dd=_f(row, "max_dd"),
                signal_score=signal_score_from_metrics(
                    sharpe=sharpe, expectancy=expectancy, pf=pf),
                oos_sharpe=oos_sharpe,
                p_loss=p_loss,
            )
            reg.combos[combo.key] = combo
    return reg
