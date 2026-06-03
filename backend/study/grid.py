"""Staged sweep driver for the derivatives edge study.

Builds the grid of (symbol × TF × strategy × profile × direction × instrument)
configs for Stage A (~15k coarse) and Stage B (refine top 50 survivors).

GridConfig is the canonical config object — each instance represents one
unique combination that will be simulated independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.engines.edge.strategies import SIGNAL_FNS
from app.engines.edge.registry import PROFILE_CONFIG
from study.surface_snapshot import SurfaceSnapshot

# ── Grid dimensions ────────────────────────────────────────────────────

_SYMBOLS_DEFAULT = ["BTCUSD", "ETHUSD", "SOLUSD"]

_TIMEFRAMES = [
    ("15min", "15m"), ("30min", "30m"), ("1h", "1h"),
    ("2h", "2h"), ("4h", "4h"),
]

_STRATEGIES = list(SIGNAL_FNS.keys())  # ~5

_PROFILES = {k: (v["atr_sl"], v["atr_tp"]) for k, v in PROFILE_CONFIG.items()}

_DIRECTIONS = ["long", "short"]

# Options grid extras
_DELTA_TARGETS = [0.20, 0.30, 0.40]
_DTE_TARGETS = [7, 14, 30]

# Exit types (spec Component 3)
_EXIT_TYPES = ["fixed_tp", "atr_trailing", "time_stop"]

# Regime filter options
_REGIME_FILTERS = ["none", "ema200_trend", "adx_20", "atr_band"]


@dataclass
class GridConfig:
    """One unique simulation configuration."""
    symbol: str
    tf_rule: str              # "15min", etc.
    tf_label: str             # "15m", etc.
    strategy: str             # "ma_crossover", etc.
    profile: str              # "Scalping", etc.
    sl_mult: float
    tp_mult: float
    direction: str            # "long" | "short"
    instrument: str           # "futures" | "call" | "put"
    # Options-only
    delta_target: float | None = None
    dte: int | None = None
    # Exit type
    exit_type: str = "fixed_tp"
    # Regime filter
    regime_filter: str = "none"
    # Computed during sweep
    n_trades: int = 0
    metrics: Optional[dict] = None
    robustness: Optional[dict] = None
    note: str = ""

    @property
    def id(self) -> str:
        """Compact identifier for logging/output."""
        base = f"{self.strategy}/{self.symbol[:3]}/{self.tf_label}/{self.direction}/{self.instrument}"
        if self.exit_type != "fixed_tp":
            base += f"/{self.exit_type}"
        if self.regime_filter != "none":
            base += f"/{self.regime_filter}"
        if self.instrument in ("call", "put"):
            base += f"/d{self.delta_target}/dte{self.dte}"
        return base


def _instruments_for(symbol: str, surfaces: dict[str, SurfaceSnapshot | None]) -> list[str]:
    """Return which instrument types are valid for a symbol.

    SOL has no listed options → futures only.
    """
    instruments = ["futures"]
    snap = surfaces.get(symbol)
    if snap is not None:
        instruments.extend(["call", "put"])
    return instruments


def build_stage_a(
    symbols: list[str] | None = None,
    surfaces: dict[str, SurfaceSnapshot | None] | None = None,
) -> list[GridConfig]:
    """Build Stage A coarse grid (~15k configs).

    Dimensions:
    - symbols: 3 (BTC, ETH, SOL)
    - TFs: 5 (15m → 4h)
    - strategies: 5 (ma_crossover, mean_reversion, breakout, price_action, smc)
    - profiles: 3 (Scalping, Intraday, Aggressive) → SL/TP pairs
    - directions: 2 (long, short)
    - exit types: 3 (fixed_tp, atr_trailing, time_stop)
    - regime filters: 4 (none, ema200_trend, adx_20, atr_band)

    Futures: 3×5×5×3×2×3×4 = 5,400
    Options: multiplied by 3 delta × 3 DTE × 2 (call/put) per direction
             but SOL has no options → subtract SOL options.
    """
    syms = symbols or _SYMBOLS_DEFAULT
    surfs = surfaces or {}

    configs: list[GridConfig] = []

    for sym in syms:
        instruments = _instruments_for(sym, surfs)
        for rule, tf_lbl in _TIMEFRAMES:
            for strat in _STRATEGIES:
                for prof_name, (sl, tp) in _PROFILES.items():
                    for direction in _DIRECTIONS:
                        for exit_type in _EXIT_TYPES:
                            for regime_filt in _REGIME_FILTERS:
                                # ── Futures ───────────────────────────
                                if "futures" in instruments:
                                    configs.append(GridConfig(
                                        symbol=sym, tf_rule=rule, tf_label=tf_lbl,
                                        strategy=strat, profile=prof_name,
                                        sl_mult=sl, tp_mult=tp, direction=direction,
                                        instrument="futures",
                                        exit_type=exit_type,
                                        regime_filter=regime_filt,
                                    ))

                                # ── Options (calls + puts) ────────────
                                if sym not in surfs or surfs[sym] is None:
                                    continue  # no options surface for this symbol
                                for delta_tgt in _DELTA_TARGETS:
                                    for dte in _DTE_TARGETS:
                                        for opt_type in ("call", "put"):
                                            configs.append(GridConfig(
                                                symbol=sym, tf_rule=rule, tf_label=tf_lbl,
                                                strategy=strat, profile=prof_name,
                                                sl_mult=sl, tp_mult=tp, direction=direction,
                                                instrument=opt_type,
                                                delta_target=delta_tgt,
                                                dte=dte,
                                                exit_type=exit_type,
                                                regime_filter=regime_filt,
                                                note="modeled: calibrated to live surface",
                                            ))

    return configs


def build_stage_b(survivors: list[GridConfig]) -> list[GridConfig]:
    """Refine the top ~50 Stage A survivors with finer grids.

    Refinements:
    - Delta ±0.05 on the best delta
    - DTE ±1 on the best DTE
    - SL/TP ±20% on the best SL/TP
    - Additional entry-param grid (EMA pairs, RSI thresholds, Donchian periods)
    """
    refined: list[GridConfig] = []

    for orig in survivors:
        # ── Finer delta steps ──────────────────────────────────────────
        if orig.delta_target is not None:
            for delta in [orig.delta_target - 0.05, orig.delta_target, orig.delta_target + 0.05]:
                if 0.10 <= delta <= 0.60:
                    cfg = GridConfig(
                        symbol=orig.symbol, tf_rule=orig.tf_rule, tf_label=orig.tf_label,
                        strategy=orig.strategy, profile=orig.profile,
                        sl_mult=orig.sl_mult, tp_mult=orig.tp_mult,
                        direction=orig.direction, instrument=orig.instrument,
                        delta_target=round(delta, 2), dte=orig.dte,
                        exit_type=orig.exit_type, regime_filter=orig.regime_filter,
                        note=orig.note,
                    )
                    refined.append(cfg)

        # ── Finer DTE steps ────────────────────────────────────────────
        if orig.dte is not None:
            for dte in [orig.dte - 1, orig.dte, orig.dte + 1]:
                if 5 <= dte <= 45:
                    cfg = GridConfig(
                        symbol=orig.symbol, tf_rule=orig.tf_rule, tf_label=orig.tf_label,
                        strategy=orig.strategy, profile=orig.profile,
                        sl_mult=orig.sl_mult, tp_mult=orig.tp_mult,
                        direction=orig.direction, instrument=orig.instrument,
                        delta_target=orig.delta_target, dte=dte,
                        exit_type=orig.exit_type, regime_filter=orig.regime_filter,
                        note=orig.note,
                    )
                    refined.append(cfg)

        # ── SL/TP ±20% ─────────────────────────────────────────────────
        for sl_pct in [0.8, 1.0, 1.2]:
            for tp_pct in [0.8, 1.0, 1.2]:
                new_sl = round(orig.sl_mult * sl_pct, 2)
                new_tp = round(orig.tp_mult * tp_pct, 2)
                if new_tp > new_sl and new_sl >= 0.5:
                    cfg = GridConfig(
                        symbol=orig.symbol, tf_rule=orig.tf_rule, tf_label=orig.tf_label,
                        strategy=orig.strategy, profile=orig.profile,
                        sl_mult=new_sl, tp_mult=new_tp,
                        direction=orig.direction, instrument=orig.instrument,
                        delta_target=orig.delta_target, dte=orig.dte,
                        exit_type=orig.exit_type, regime_filter=orig.regime_filter,
                        note=orig.note,
                    )
                    refined.append(cfg)

    # Deduplicate by id
    seen: set[str] = set()
    unique: list[GridConfig] = []
    for c in refined:
        if c.id not in seen:
            seen.add(c.id)
            unique.append(c)

    return unique
