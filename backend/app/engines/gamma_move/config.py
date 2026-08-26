"""Configuration for the Gamma Move strategy.

Every threshold here was measured, not guessed. The calibration ran on 598 NSE
stock-option contracts across 104 underlyings -- 193,135 fifteen-minute bars
carrying real open interest, plus 35,020 daily spot bars -- pulled 2026-08-26.
The full record is ``backend/study/gamma_move/`` and
``docs/strategy/gamma-move/VALIDATION_REPORT.md``.

The headline result is not the one the source predicts, and the defaults encode
it rather than the story:

* **The entry triple alone has no measurable edge.** Bars passing it reached a
  30% favourable excursion within two sessions 24.7% of the time [20.9, 28.9]
  against an unconditional 21.7% [21.5, 21.9]. The intervals overlap.
* **The level filter is what carries it.** Restricting the same triple to bars
  where spot sat within 1% of a confirmed level lifted that to 46.2%
  [31.6, 61.4] -- a lower bound above the baseline's upper bound. (Re-measured
  through the shipped :func:`levels.find_levels` after a plateau bug in the
  pivot rule was fixed; the earlier figure through the study's own copy was
  45.0% [30.7, 60.2].)
* **The regime multiplier was actively harmful at the obvious default.**
  SuperTrend at multiplier 3.0 made agreeing trades *worse* than disagreeing
  ones (-3.3pp at period 10). At multiplier 2.0 the sign flips and holds
  positive across every period tested (+5.1 to +7.0pp). 2.0 is the default for
  that reason and 3.0 is the trap it was chosen over.

So ``level_proximity_pct`` is the load-bearing setting in this file, and
loosening it is not a small change -- it is the difference between a measured
edge and none.

Validation is here rather than at the API boundary so a config persisted by an
older build, or edited straight in the database, cannot become a trading config
the engine rejects mid-session.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Optional

LEVEL_TIMEFRAMES: frozenset[str] = frozenset({"day", "60minute", "15minute"})
TRIGGER_TIMEFRAMES: frozenset[str] = frozenset({"5minute", "15minute", "30minute"})
EXIT_POLICIES: frozenset[str] = frozenset({"TIME_STOP", "PERCENT_TARGET", "TRAILING_STOP"})
STOP_BASES: frozenset[str] = frozenset({"POINTS", "PERCENT"})
SIZING_MODES: frozenset[str] = frozenset({"LOTS", "RISK_PCT"})
PROTECTION_MODES: frozenset[str] = frozenset({"NONE", "GTT", "RESTING_STOP_LIMIT"})
DATA_SOURCES: frozenset[str] = frozenset({"kite"})
EXECUTION_MODES: frozenset[str] = frozenset({"paper", "live"})

#: Exit policies that have never been validated against anything. The source
#: gives no exit rule at all -- its 2x and 3x figures are outcomes, not a rule --
#: so only the time stop it does support may run with real money.
RESEARCH_ONLY_EXIT_POLICIES: frozenset[str] = frozenset({"PERCENT_TARGET", "TRAILING_STOP"})

#: Bars per session on a 15-minute chart, 09:15-15:30. Used to express holding
#: periods in sessions rather than in bars.
BARS_PER_SESSION: dict[str, int] = {"5minute": 75, "15minute": 25, "30minute": 13}

#: What the calibration measured, published so the API can show provenance
#: beside each number instead of asking the reader to trust it.
CALIBRATION = {
    "sample": "598 contracts / 104 underlyings / 193,135 15m OI bars, 2026-08-26",
    "level_proximity_pct": "1.0 — MFE>=30% 46.2% [31.6,61.4] vs 21.7% [21.5,21.9] baseline (n=39)",
    "min_oi_drop_pct": "3.0 — the 98.6th percentile of observed bar-on-bar OI drops",
    "volume_spike_mult": "2.5 — the 87th percentile of volume against a 20-bar mean",
    "min_price_gain_pct": "2.0 — the 93rd percentile of bar-on-bar premium change",
    "regime_multiplier": "2.0 — +5.1pp; multiplier 3.0 measured -3.3pp, i.e. inverted",
    "min_option_premium": "10.0 — below this the 0.05 tick is a >0.5% price quantum",
    "stop_percent": "30.0 — hit by 16% of calibrated signals; a 20% stop by 41%",
}

#: Fields whose defaults came from the calibration run above. Anything NOT in
#: this set is a judgement call, and the UI says so.
CALIBRATED_FIELDS: frozenset[str] = frozenset(CALIBRATION) - {"sample"}


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
class GammaMoveConfig:
    """Immutable strategy configuration. Construct, then :meth:`validate`."""

    enabled: bool = False

    # --- universe -----------------------------------------------------------
    #: Indices are excluded: every worked example in the source is a stock, and
    #: the mechanism needs writers concentrated at one strike, which an index
    #: chain spreads across many.
    include_indices: bool = False
    max_universe: int = 150
    explicit_symbols: tuple[str, ...] = ()
    min_option_oi: int = 50_000
    min_option_volume: int = 1_000
    #: MEASURED. At a 0.05 tick, a 0.73 option moves in 7% steps, so
    #: `min_price_gain_pct` would be measuring tick granularity rather than a
    #: gamma move. The source's own entries were at 75, 540 and 600.
    min_option_premium: float = 10.0
    max_spread_pct: float = 3.0

    # --- levels -------------------------------------------------------------
    level_timeframe: str = "day"
    level_lookback_days: int = 120
    pivot_lookback: int = 5
    level_cluster_pct: float = 0.75
    min_level_touches: int = 2
    #: MEASURED, and the single most important number in this file. See module
    #: docstring. Must be > 0: zero would mean "exactly on the level", which no
    #: tick ever is, so the strategy would silently never fire.
    level_proximity_pct: float = 1.0

    # --- strike -------------------------------------------------------------
    strike_window_pct: float = 2.0
    max_candidates: int = 25

    # --- expiry -------------------------------------------------------------
    #: The source trades only the last week or two of a contract. NSE stock
    #: options are monthly-only, so this window is roughly the 15th onward.
    min_days_to_expiry: int = 1
    max_days_to_expiry: int = 14

    # --- trigger ------------------------------------------------------------
    trigger_timeframe: str = "15minute"
    volume_lookback: int = 20
    min_oi_drop_pct: float = 3.0          # MEASURED
    volume_spike_mult: float = 2.5        # MEASURED
    min_price_gain_pct: float = 2.0       # MEASURED
    confirm_bars: int = 1

    # --- regime -------------------------------------------------------------
    regime_enabled: bool = True
    regime_timeframe: str = "day"
    regime_period: int = 10
    regime_multiplier: float = 2.0        # MEASURED — 3.0 inverts the gate

    # --- stop ---------------------------------------------------------------
    stop_basis: str = "PERCENT"
    swing_lookback: int = 6
    stop_percent: float = 30.0            # MEASURED
    stop_points: float = 0.0

    # --- exit ---------------------------------------------------------------
    exit_policy: str = "TIME_STOP"
    max_hold_days: int = 2
    target_pct: float = 0.0
    trail_pct: float = 0.0
    trail_start_pct: float = 0.0
    close_at_session_end: bool = False
    protection_mode: str = "NONE"

    # --- session ------------------------------------------------------------
    #: Not 09:15. The first bar of a session has no prior bar inside the same
    #: session, and differencing OI across the boundary produces a phantom
    #: unwind -- measured at 2.95% of boundaries versus 0.85% within a session.
    session_start: str = "09:30"
    session_end: str = "15:15"
    scan_interval_seconds: int = 300

    # --- risk ---------------------------------------------------------------
    sizing_mode: str = "RISK_PCT"
    risk_per_trade_pct: float = 1.0
    capital_inr: float = 500_000.0
    lots: int = 0
    max_concurrent_positions: int = 3
    max_new_trades_per_day: int = 2
    #: One lot of a typical NSE stock option costs more than Rs 25,000 in
    #: premium (RELIANCE 500 x ~53 = Rs 26,500 in the calibration sample), and a
    #: cap below one lot silently refuses every trade while looking like a
    #: risk setting rather than an off switch.
    max_premium_at_risk_inr: float = 60_000.0
    daily_loss_limit_inr: float = 10_000.0
    descale_after_losses: int = 3
    descale_factor: float = 0.5
    rescale_after_wins: int = 2

    # --- plumbing -----------------------------------------------------------
    data_source: str = "kite"
    execution_mode: str = "paper"

    # ------------------------------------------------------------------ rules
    def validate(self) -> "GammaMoveConfig":
        for name, vocab in (("level_timeframe", LEVEL_TIMEFRAMES),
                            ("trigger_timeframe", TRIGGER_TIMEFRAMES),
                            ("regime_timeframe", LEVEL_TIMEFRAMES),
                            ("exit_policy", EXIT_POLICIES),
                            ("stop_basis", STOP_BASES),
                            ("sizing_mode", SIZING_MODES),
                            ("protection_mode", PROTECTION_MODES),
                            ("data_source", DATA_SOURCES),
                            ("execution_mode", EXECUTION_MODES)):
            if getattr(self, name) not in vocab:
                raise ValueError(f"{name} must be one of {sorted(vocab)}")

        # Thresholds. None of these may be zero: a zero threshold does not
        # "disable" its condition, it makes the condition trivially true, which
        # silently deletes a third of the entry rule while looking like a
        # setting. Where a rule can genuinely be switched off it has a boolean.
        if self.level_proximity_pct <= 0:
            raise ValueError(
                "level_proximity_pct must be > 0 — it is the measured edge in this "
                "strategy, and 0 would mean 'exactly on the level', which never happens")
        if self.min_oi_drop_pct <= 0:
            raise ValueError("min_oi_drop_pct must be > 0")
        if self.volume_spike_mult <= 1.0:
            raise ValueError(
                "volume_spike_mult must be > 1.0 — at or below 1 every bar is "
                "'abnormal' and the volume condition stops filtering anything")
        if self.min_price_gain_pct <= 0:
            raise ValueError("min_price_gain_pct must be > 0")
        if not 1 <= self.confirm_bars <= 3:
            raise ValueError("confirm_bars must be between 1 and 3")
        if self.volume_lookback < 5:
            raise ValueError("volume_lookback must be >= 5")
        if self.pivot_lookback < 2:
            raise ValueError("pivot_lookback must be >= 2")
        if self.level_cluster_pct <= 0:
            raise ValueError("level_cluster_pct must be > 0")
        if self.min_level_touches < 1:
            raise ValueError("min_level_touches must be >= 1")
        if self.level_lookback_days < 30:
            raise ValueError("level_lookback_days must be >= 30 to find any pivots")
        if self.strike_window_pct <= 0:
            raise ValueError("strike_window_pct must be > 0")
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        if self.max_universe < 1:
            raise ValueError("max_universe must be >= 1")

        # Expiry window. max_days_to_expiry = 0 is a mistake, not "no limit".
        if self.max_days_to_expiry <= 0:
            raise ValueError("max_days_to_expiry must be > 0 (0 is not 'no limit')")
        if self.min_days_to_expiry < 0:
            raise ValueError("min_days_to_expiry cannot be negative")
        if self.min_days_to_expiry >= self.max_days_to_expiry:
            raise ValueError("min_days_to_expiry must be below max_days_to_expiry")

        if self.regime_period < 2:
            raise ValueError("regime_period must be >= 2")
        if self.regime_multiplier <= 0:
            raise ValueError("regime_multiplier must be > 0")

        if self.swing_lookback < 2:
            raise ValueError("swing_lookback must be >= 2")
        if self.stop_percent >= 100:
            raise ValueError("stop_percent must be below 100 — a 100% stop is the premium")
        for name in ("stop_percent", "stop_points", "target_pct", "trail_pct",
                     "trail_start_pct", "risk_per_trade_pct"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.max_hold_days < 1:
            raise ValueError("max_hold_days must be >= 1")
        if self.exit_policy == "PERCENT_TARGET" and self.target_pct <= 0:
            raise ValueError("exit_policy=PERCENT_TARGET requires target_pct > 0")
        if self.exit_policy == "TRAILING_STOP" and self.trail_pct <= 0:
            raise ValueError("exit_policy=TRAILING_STOP requires trail_pct > 0")

        start = _hhmm(self.session_start, "session_start")
        end = _hhmm(self.session_end, "session_end")
        if start >= end:
            raise ValueError("session_start must be before session_end")
        if self.scan_interval_seconds < 60:
            raise ValueError("scan_interval_seconds must be >= 60")

        if self.lots < 0:
            raise ValueError("lots cannot be negative")
        if self.capital_inr <= 0:
            raise ValueError("capital_inr must be > 0")
        if self.max_concurrent_positions < 1:
            raise ValueError("max_concurrent_positions must be >= 1")
        if self.max_new_trades_per_day < 1:
            raise ValueError("max_new_trades_per_day must be >= 1")
        if self.max_premium_at_risk_inr <= 0:
            raise ValueError("max_premium_at_risk_inr must be > 0")
        if self.daily_loss_limit_inr <= 0:
            raise ValueError("daily_loss_limit_inr must be > 0")
        if self.descale_after_losses < 1:
            raise ValueError("descale_after_losses must be >= 1")
        if not 0 < self.descale_factor <= 1:
            raise ValueError("descale_factor must be in (0, 1]")
        if self.rescale_after_wins < 1:
            raise ValueError("rescale_after_wins must be >= 1")
        if self.min_option_premium < 0:
            raise ValueError("min_option_premium cannot be negative")

        if self.execution_mode == "live":
            self._validate_live()
        return self

    def _validate_live(self) -> None:
        """Guards that only apply to real money, kept apart so they read as a set."""
        if self.exit_policy in RESEARCH_ONLY_EXIT_POLICIES:
            raise ValueError(
                f"exit_policy={self.exit_policy} is research-only: the source gives no "
                "exit rule at all, so only TIME_STOP is supported by evidence")
        if self.stop_basis != "PERCENT":
            raise ValueError(
                "live mode requires stop_basis=PERCENT: these premiums run from roughly "
                "10 to 600, so a points stop is a 5% risk at one end and 100% at the other")
        if self.stop_percent <= 0:
            raise ValueError("live mode requires a positive stop_percent")
        if self.protection_mode == "NONE":
            raise ValueError(
                "live mode requires broker-side protection: with protection_mode=NONE a "
                "crash or a dropped socket leaves the open position with nothing watching it")
        if not self.size_is_set:
            raise ValueError("live mode requires an explicit positive size")
        if not self.regime_enabled:
            raise ValueError(
                "live mode requires the regime gate: the source names a corrective market "
                "as the flaw that broke this strategy")
        if self.min_option_premium < 5.0:
            raise ValueError(
                "live mode requires min_option_premium >= 5: below that the tick size is a "
                "larger move than the entry threshold, so the trigger measures rounding")

    # ------------------------------------------------------------- accessors
    @property
    def size_is_set(self) -> bool:
        return (self.lots > 0) if self.sizing_mode == "LOTS" else (self.risk_per_trade_pct > 0)

    @property
    def bars_per_session(self) -> int:
        return BARS_PER_SESSION.get(self.trigger_timeframe, 25)

    def stop_distance_inr(self, reference: float) -> float:
        """The initial stop distance in rupees, whichever way it was expressed."""
        if self.stop_basis == "PERCENT":
            return abs(float(reference)) * (self.stop_percent / 100.0)
        return float(self.stop_points)

    def effective_quantity(self, lot_size: int, lots: int) -> int:
        return max(0, int(lots)) * max(1, int(lot_size or 1))

    def sizing_blocker(self, lot_size: int, lots: int) -> Optional[str]:
        """Why this size cannot be traded, in words, or None if it can.

        One function, asked by both the board and arm(), so they cannot disagree
        about a size the broker would refuse.
        """
        lot = max(1, int(lot_size or 1))
        if lots <= 0:
            return ("lots not set" if self.sizing_mode == "LOTS"
                    else "risk budget is too small for one lot")
        qty = self.effective_quantity(lot, lots)
        if qty <= 0:
            return "size resolves to zero quantity"
        return None

    def as_dict(self) -> dict:
        out = {}
        for f in fields(self):
            v = getattr(self, f.name)
            out[f.name] = list(v) if isinstance(v, tuple) else v
        return out

    @classmethod
    def field_names(cls) -> frozenset[str]:
        return frozenset(f.name for f in fields(cls))
