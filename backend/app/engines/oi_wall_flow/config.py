"""Configuration for the OI Wall Flow strategy.

This engine reads an option chain the way a desk reads one: classify each
strike's OI+premium change, locate the put/call walls, compute PCR and max
pain, then buy the first-resistance CE (or first-support PE) when flow agrees.

Thresholds here are judgement calls from the BSE Ltd Sep-29 2026 chain that
motivated the engine, not a calibrated sample. They live in ``JUDGEMENT`` so
the API can say so, instead of pretending they were measured.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Optional

from app.engines.option_contracts import EXPIRY_SELECTIONS, EXPIRY_SERIES

#: Same vocabulary and default as SuperTrend / Gamma Move. ``broker`` is a GTT
#: at Zerodha that survives this process dying; ``monitor`` is our own tick
#: loop; ``both`` is the production answer.
STOP_MODES: frozenset[str] = frozenset({"broker", "monitor", "both"})
DATA_SOURCES: frozenset[str] = frozenset({"kite"})

JUDGEMENT = {
    "oi_chg_deadband_pct": "0.5 — noise floor; a 0.00% print is not a buildup",
    "ltp_chg_deadband_pct": "0.5 — same, for premium",
    "atm_window_strikes": "2 — ATM ±2 strikes carry the directional vote",
    "min_bias_score": "3.0 — three confirming flow votes before a trade",
    "prefer_wall_strike": "True — buy the wall, not ATM, when the wall is first OTM",
    "stop_premium_pct": "40.0 — premium cut that killed the BSE 3500 CE thesis",
    "target_premium_pct": "50.0 — first scale, ~spot into the wall",
    "target_2_premium_pct": "100.0 — runner if the wall gives way",
    "min_option_premium": "10.0 — below this the 0.05 tick is a >0.5% quantum",
    "avoid_expiry_day": "True — OI on expiry day is settlement, not positioning",
}

JUDGEMENT_FIELDS: frozenset[str] = frozenset(JUDGEMENT)


def _hhmm(value: str, label: str) -> str:
    parts = str(value).split(":")
    if len(parts) != 2:
        raise ValueError(f"{label} must be HH:MM")
    try:
        hh, mm = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"{label} must be HH:MM") from exc
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"{label} must be a valid HH:MM time")
    return f"{hh:02d}:{mm:02d}"


@dataclass(frozen=True)
class OIWallFlowConfig:
    """Immutable strategy configuration. Construct, then :meth:`validate`."""

    enabled: bool = True

    # --- universe -----------------------------------------------------------
    # Same field names, semantics and liquidity boundary as every other engine
    # here. Indices are stored as the display names InstrumentsGroup writes
    # ("NIFTY 50"), then mapped onto NFO option names ("NIFTY") at scan time.
    scan_stocks: tuple[str, ...] = ()
    #: True = every eligible high-liquidity stock, never every listed F&O name.
    scan_all_stocks: bool = True
    #: Master switch above the stock list, as in the SuperTrend engine.
    stock_contracts: bool = True
    #: Default on: this engine reads any chain, and the motivating example is a
    #: stock, but indices are the liquid walls operators actually watch.
    scan_indices: tuple[str, ...] = ("NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE")

    # --- chain reading ------------------------------------------------------
    oi_chg_deadband_pct: float = 0.5
    ltp_chg_deadband_pct: float = 0.5
    atm_window_strikes: int = 2
    min_bias_score: float = 3.0
    #: If True, the selected strike is the call/put wall when it is the first
    #: OTM wall in the trade's direction. If False, always the nearest OTM.
    prefer_wall_strike: bool = True
    #: Skip ATM even when it is the wall. ATM premia pay more theta for less RR.
    skip_atm: bool = True

    # --- contracts ----------------------------------------------------------
    expiry_selection: str = "nearest"
    expiry_dte_min: int = 1
    expiry_dte_max: int = 45
    avoid_expiry_day: bool = True
    min_option_oi: int = 100
    min_option_premium: float = 10.0
    scan_expiries_indices: tuple[str, ...] = ("weekly", "monthly")
    scan_expiries_stocks: tuple[str, ...] = ("monthly",)
    scan_weekly_series_indices: tuple[int, ...] = (0, 1, 2, 3)
    scan_monthly_series_indices: tuple[int, ...] = (0, 1)
    scan_monthly_series_stocks: tuple[int, ...] = (0, 1)

    # --- exits (premium, not spot, unless the wall breaks) ------------------
    stop_premium_pct: float = 40.0
    target_premium_pct: float = 50.0
    target_2_premium_pct: float = 100.0
    #: Exit if spot prints through the opposing wall. That is the thesis break.
    wall_invalidation: bool = True
    stop_mode: str = "both"

    # --- session ------------------------------------------------------------
    #: A few minutes after the open so session OI has something to difference
    #: against. The first quote of the day is the baseline (Kite quotes have no
    #: previous-close OI); scanning at the bell would arm on a 0% change.
    session_start: str = "09:20"
    session_end: str = "15:15"
    scan_interval_seconds: int = 300

    # --- risk ---------------------------------------------------------------
    lot_size: int = 1
    lots: int = 1
    max_premium_at_risk_inr: float = 20_000.0
    max_concurrent_positions: int = 1
    max_new_trades_per_day: int = 1
    daily_loss_limit_inr: float = 15_000.0
    descale_after_losses: int = 3
    rescale_after_wins: int = 2

    # --- plumbing -----------------------------------------------------------
    # Paper/live is account.is_paper. Manual/auto is the engine's auto_execute.
    # Neither is stored here — a second copy can disagree with the client that
    # actually places the order.
    data_source: str = "kite"

    def effective_quantity(self, lot_size: int, lots: int) -> int:
        return int(lot_size) * int(lots)

    def stop_price(self, entry: float) -> Optional[float]:
        if entry <= 0 or self.stop_premium_pct <= 0:
            return None
        stop = entry * (1.0 - self.stop_premium_pct / 100.0)
        return None if stop <= 0 else round(stop + 0.0, 2)

    def target_price(self, entry: float) -> Optional[float]:
        if entry <= 0 or self.target_premium_pct <= 0:
            return None
        return round(entry * (1.0 + self.target_premium_pct / 100.0) + 0.0, 2)

    def target_2_price(self, entry: float) -> Optional[float]:
        if entry <= 0 or self.target_2_premium_pct <= 0:
            return None
        return round(entry * (1.0 + self.target_2_premium_pct / 100.0) + 0.0, 2)

    def validate(self) -> "OIWallFlowConfig":
        if self.oi_chg_deadband_pct < 0 or self.ltp_chg_deadband_pct < 0:
            raise ValueError("deadbands cannot be negative")
        if self.atm_window_strikes < 0:
            raise ValueError("atm_window_strikes cannot be negative")
        if self.min_bias_score <= 0:
            raise ValueError("min_bias_score must be > 0")
        if self.expiry_dte_min < 0 or self.expiry_dte_max < self.expiry_dte_min:
            raise ValueError("expiry window is inverted")
        if self.expiry_selection not in EXPIRY_SELECTIONS:
            raise ValueError(f"expiry_selection must be one of {sorted(EXPIRY_SELECTIONS)}")
        for series in self.scan_expiries_indices + self.scan_expiries_stocks:
            if series not in EXPIRY_SERIES:
                raise ValueError(f"unknown expiry series {series!r}")
        if not (0 < self.stop_premium_pct < 100):
            raise ValueError("stop_premium_pct must be in (0, 100)")
        if self.target_premium_pct <= 0 or self.target_2_premium_pct < self.target_premium_pct:
            raise ValueError("targets must be positive and ordered")
        if self.min_option_premium <= 0:
            raise ValueError("min_option_premium must be > 0")
        if self.lots < 1 or self.lot_size < 1:
            raise ValueError("lots and lot_size must be >= 1")
        if self.max_concurrent_positions < 1 or self.max_new_trades_per_day < 1:
            raise ValueError("position/day caps must be >= 1")
        if self.max_premium_at_risk_inr <= 0 or self.daily_loss_limit_inr <= 0:
            raise ValueError("risk caps must be > 0")
        if self.stop_mode not in STOP_MODES:
            raise ValueError(f"stop_mode must be one of {sorted(STOP_MODES)}")
        if self.data_source not in DATA_SOURCES:
            raise ValueError(f"data_source must be one of {sorted(DATA_SOURCES)}")
        if self.avoid_expiry_day and self.expiry_dte_min == 0 and self.expiry_dte_max == 0:
            raise ValueError(
                "avoid_expiry_day leaves no eligible expiry when the DTE range is 0-0")
        for name, limit in (("scan_weekly_series_indices", 4),
                            ("scan_monthly_series_indices", 2),
                            ("scan_monthly_series_stocks", 2)):
            ranks = getattr(self, name)
            if any(not isinstance(r, int) or r < 0 or r >= limit for r in ranks):
                raise ValueError(f"{name} ranks must be between 0 and {limit - 1}")
            if len(set(ranks)) != len(ranks):
                raise ValueError(f"{name} contains a duplicate rank")
        from app.services.kite_engine.stock_registry import HIGH_LIQUIDITY_STOCK_NAMES
        unknown = sorted(set(n.upper() for n in self.scan_stocks)
                         - set(HIGH_LIQUIDITY_STOCK_NAMES))
        if unknown:
            raise ValueError(
                f"scan_stocks contains names outside the curated high-liquidity "
                f"registry: {', '.join(unknown)}")
        if not self.stock_contracts and not self.scan_indices:
            raise ValueError(
                "nothing to scan: stock_contracts is off and no indices are selected")
        start = _hhmm(self.session_start, "session_start")
        end = _hhmm(self.session_end, "session_end")
        if start >= end:
            raise ValueError("session_start must be before session_end")
        if self.scan_interval_seconds < 60:
            raise ValueError("scan_interval_seconds must be >= 60")
        return self

    def warnings(self) -> list[str]:
        """Configured choices worth saying out loud. Not errors."""
        out: list[str] = []
        if self.stop_mode == "monitor":
            out.append("stop_mode=monitor leaves nothing at the broker — if this "
                       "process dies while holding, the position is unprotected")
        if not self.skip_atm:
            out.append("skip_atm is off — ATM premia pay more theta for a worse RR, "
                       "which is why the default refuses them")
        return out

    def as_dict(self) -> dict:
        out = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, tuple):
                val = list(val)
            out[f.name] = val
        return out

    @classmethod
    def field_names(cls) -> frozenset[str]:
        return frozenset(f.name for f in fields(cls))
