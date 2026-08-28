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


@dataclass(frozen=True)
class OIWallFlowConfig:
    """Immutable strategy configuration. Construct, then :meth:`validate`."""

    enabled: bool = True

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

    # --- risk ---------------------------------------------------------------
    lot_size: int = 1
    lots: int = 1
    max_premium_at_risk_inr: float = 20_000.0
    max_concurrent_positions: int = 1
    max_new_trades_per_day: int = 1
    daily_loss_limit_inr: float = 15_000.0
    descale_after_losses: int = 3
    rescale_after_wins: int = 2

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
        return self

    def as_dict(self) -> dict:
        out = {}
        for f in fields(self):
            val = getattr(self, f.name)
            if isinstance(val, tuple):
                val = list(val)
            out[f.name] = val
        return out
