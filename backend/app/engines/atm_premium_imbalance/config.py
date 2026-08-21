"""Configuration for the ATM Premium Imbalance strategy.

Defaults reproduce the observed baseline wherever the evidence is strong, and
refuse to guess wherever it is not:

* ``target_points = 15.0`` and ``exit_buffer_points = 0.5`` are OBSERVED and
  identical across two builds of the source bot.
* ``entry_price_policy`` defaults to ``MARKETABLE_ASK`` -- the *mechanism* the
  bot used (a limit deliberately through the market) expressed as a rule rather
  than as the operator-maintained price file it actually read.
  ``FIRST_TICK_PLUS_BUFFER`` exists only so the rejected model stays replayable;
  it is never a default. See A232.
* ``enabled`` defaults ``False``. Nothing about this strategy has been through a
  walk-forward, so it must be switched on deliberately.

Validation lives here rather than at the API boundary so a config persisted by
an older build -- or edited straight in the database -- cannot become a trading
config that the engine rejects mid-session.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Literal

EXPIRY_POLICIES: frozenset[str] = frozenset({"SAME_DAY", "NEAREST", "NEXT", "EXPLICIT"})
STRIKE_POLICIES: frozenset[str] = frozenset({"ATM_NEAREST"})
QUOTE_MODES: frozenset[str] = frozenset({"COMPATIBILITY", "SYNCHRONIZED", "EXECUTABLE"})
SIGNAL_MODES: frozenset[str] = frozenset({"CHEAPER_LEG"})
DATA_SOURCES: frozenset[str] = frozenset({"kite", "truedata"})
EXECUTION_MODES: frozenset[str] = frozenset({"paper", "live"})

#: How the entry limit price is produced. Every policy is then capped at the
#: instrument's upper circuit.
ENTRY_PRICE_POLICIES: frozenset[str] = frozenset(
    {"MARKETABLE_ASK", "PERCENT_THROUGH", "MANUAL_FILE",
     "FIRST_TICK_PERCENT", "FIRST_TICK_PLUS_BUFFER"}
)

#: The observed automatic entry path: ``first_tick x (1 + entry_through_pct)``
#: rounded to one decimal, with ``entry_through_pct = 0.10``. Both decoded
#: sessions satisfy it exactly -- 102.85 -> 113.1 and 379.0 -> 416.9 -- and no
#: fixed *points* buffer fits both (A232).
OBSERVED_ENTRY_POLICY = "FIRST_TICK_PERCENT"
OBSERVED_ENTRY_THROUGH_PCT = 0.10

#: Where the "first tick" reference comes from.
#:
#: ``SESSION_TICK``   the first tick proven to have traded in this session.
#: ``OFFICIAL_OPEN``  the exchange's published open. Still dated indirectly --
#:                     ohlc.open reports the PREVIOUS session's open until this
#:                     session's first trade, so it is withheld until the leg has
#:                     traded today.
FIRST_TICK_SOURCES: frozenset[str] = frozenset({"SESSION_TICK", "OFFICIAL_OPEN"})

#: Policies we refuse to run against real money.
#:
#: ``FIRST_TICK_PLUS_BUFFER`` is a *points* variant that no observed session
#: satisfies -- it fits 2026-08-20 only by coincidence and fails 2026-08-21
#: outright (A232). Kept because the written specification asked for it, but it
#: is research-only. The observed rule is ``FIRST_TICK_PERCENT``.
RESEARCH_ONLY_ENTRY_POLICIES: frozenset[str] = frozenset({"FIRST_TICK_PLUS_BUFFER"})

EXIT_POLICIES: frozenset[str] = frozenset({"FIXED_POINT_TARGET", "PREMIUM_CONVERGENCE"})

#: Where the protective exit lives. NONE = nowhere, i.e. only this process.
PROTECTION_MODES: frozenset[str] = frozenset({"NONE", "RESTING_TARGET_LIMIT", "GTT"})
RESEARCH_ONLY_EXIT_POLICIES: frozenset[str] = frozenset({"PREMIUM_CONVERGENCE"})


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
class ATMPremiumImbalanceConfig:
    """Immutable strategy configuration. Construct, then :meth:`validate`."""

    enabled: bool = False

    # --- universe -----------------------------------------------------------
    underlying: str = "SENSEX"
    # NEAREST, not SAME_DAY: the 2026-08-21 recording traded the *monthly*
    # August contract (`SENSEX26AUG7...`) on a non-expiry day, so the bot takes
    # whichever expiry is soonest rather than requiring one to expire today.
    expiry_policy: str = "NEAREST"
    explicit_expiry: str = ""
    strike_policy: str = "ATM_NEAREST"

    # --- session ------------------------------------------------------------
    session_start: str = "09:15"
    session_end: str = "15:25"

    # --- quotes -------------------------------------------------------------
    quote_mode: str = "COMPATIBILITY"
    max_quote_age_ms: int = 2000
    max_ce_pe_skew_ms: int = 1000

    # --- signal -------------------------------------------------------------
    signal_mode: str = "CHEAPER_LEG"
    minimum_difference: float = 0.0
    minimum_difference_percent: float = 0.0

    # --- entry --------------------------------------------------------------
    # MARKETABLE_ASK is an operator choice, not the observed default. The
    # faithful reproduction of the automatic path is FIRST_TICK_PERCENT with
    # entry_through_pct = 0.10. See A232.
    entry_price_policy: str = "MARKETABLE_ASK"
    #: Refuse to signal or price from a quote whose trade is stamped before the
    #: session open. The recorded bot had no such gate and priced an entry from a
    #: day-old price; see A231/E14. Cannot be disabled in live mode.
    require_session_origin_tick: bool = True
    first_tick_source: str = "SESSION_TICK"
    entry_buffer_points: float = 0.50
    entry_through_pct: float = 0.0
    manual_price_file: str = ""
    max_entry_attempts: int = 3
    entry_attempt_timeout_ms: int = 1500

    # --- exit ---------------------------------------------------------------
    exit_policy: str = "FIXED_POINT_TARGET"
    target_points: float = 15.0
    exit_buffer_points: float = 0.50
    # Broker-side protection for an open position. NONE reproduces the observed
    # bot (which had none); live mode refuses NONE.
    protection_mode: str = "NONE"
    stop_enabled: bool = False
    stop_points: float = 0.0
    max_hold_seconds: int = 0

    # --- session policy -----------------------------------------------------
    max_trades_per_session: int = 1

    # --- sizing & risk ------------------------------------------------------
    quantity: int = 0
    max_quantity: int = 500
    max_premium_at_risk_inr: float = 25000.0
    daily_loss_limit_inr: float = 10000.0

    # --- plumbing -----------------------------------------------------------
    data_source: str = "kite"
    execution_mode: str = "paper"

    def validate(self) -> "ATMPremiumImbalanceConfig":
        if self.expiry_policy not in EXPIRY_POLICIES:
            raise ValueError(f"expiry_policy must be one of {sorted(EXPIRY_POLICIES)}")
        if self.expiry_policy == "EXPLICIT" and not self.explicit_expiry:
            raise ValueError("expiry_policy=EXPLICIT requires explicit_expiry")
        if self.strike_policy not in STRIKE_POLICIES:
            raise ValueError(f"strike_policy must be one of {sorted(STRIKE_POLICIES)}")
        if self.quote_mode not in QUOTE_MODES:
            raise ValueError(f"quote_mode must be one of {sorted(QUOTE_MODES)}")
        if self.signal_mode not in SIGNAL_MODES:
            raise ValueError(f"signal_mode must be one of {sorted(SIGNAL_MODES)}")
        if self.first_tick_source not in FIRST_TICK_SOURCES:
            raise ValueError(f"first_tick_source must be one of {sorted(FIRST_TICK_SOURCES)}")
        if self.entry_price_policy not in ENTRY_PRICE_POLICIES:
            raise ValueError(f"entry_price_policy must be one of {sorted(ENTRY_PRICE_POLICIES)}")
        if self.protection_mode not in PROTECTION_MODES:
            raise ValueError(f"protection_mode must be one of {sorted(PROTECTION_MODES)}")
        if self.exit_policy not in EXIT_POLICIES:
            raise ValueError(f"exit_policy must be one of {sorted(EXIT_POLICIES)}")
        if self.entry_price_policy == "MANUAL_FILE" and not self.manual_price_file:
            raise ValueError("entry_price_policy=MANUAL_FILE requires manual_price_file")
        if self.data_source not in DATA_SOURCES:
            raise ValueError(f"data_source must be one of {sorted(DATA_SOURCES)}")
        if self.execution_mode not in EXECUTION_MODES:
            raise ValueError(f"execution_mode must be one of {sorted(EXECUTION_MODES)}")

        if not str(self.underlying).strip():
            raise ValueError("underlying is required")

        start = _hhmm(self.session_start, "session_start")
        end = _hhmm(self.session_end, "session_end")
        if start >= end:
            raise ValueError("session_start must be before session_end")

        if self.target_points <= 0:
            raise ValueError("target_points must be > 0")
        if self.exit_buffer_points < 0:
            raise ValueError("exit_buffer_points cannot be negative")
        if self.entry_buffer_points < 0:
            raise ValueError("entry_buffer_points cannot be negative")
        if self.entry_through_pct < 0 or self.entry_through_pct > 5:
            raise ValueError("entry_through_pct must be between 0 and 5 (500%)")
        if not 1 <= self.max_entry_attempts <= 10:
            raise ValueError("max_entry_attempts must be between 1 and 10")
        if self.entry_attempt_timeout_ms <= 0:
            raise ValueError("entry_attempt_timeout_ms must be > 0")
        if self.max_trades_per_session < 1:
            raise ValueError("max_trades_per_session must be >= 1")
        if self.minimum_difference < 0:
            raise ValueError("minimum_difference cannot be negative")
        if self.minimum_difference_percent < 0:
            raise ValueError("minimum_difference_percent cannot be negative")
        if self.max_quote_age_ms <= 0:
            raise ValueError("max_quote_age_ms must be > 0")
        if self.max_ce_pe_skew_ms <= 0:
            raise ValueError("max_ce_pe_skew_ms must be > 0")

        if self.stop_enabled and self.stop_points <= 0:
            raise ValueError("stop_enabled requires stop_points > 0")
        if self.max_hold_seconds < 0:
            raise ValueError("max_hold_seconds cannot be negative")

        if self.quantity < 0:
            raise ValueError("quantity cannot be negative")
        if self.max_quantity <= 0:
            raise ValueError("max_quantity must be > 0")
        if self.quantity > self.max_quantity:
            raise ValueError("quantity exceeds max_quantity")
        if self.max_premium_at_risk_inr <= 0:
            raise ValueError("max_premium_at_risk_inr must be > 0")
        if self.daily_loss_limit_inr <= 0:
            raise ValueError("daily_loss_limit_inr must be > 0")

        # Live-money guards. Research policies exist so the rejected and the
        # unproven models stay *replayable*; they must not become tradable by
        # flipping one unrelated switch.
        if self.execution_mode == "live":
            if self.entry_price_policy in RESEARCH_ONLY_ENTRY_POLICIES:
                raise ValueError(
                    f"entry_price_policy={self.entry_price_policy} is research-only "
                    "and cannot run in live mode"
                )
            if self.exit_policy in RESEARCH_ONLY_EXIT_POLICIES:
                raise ValueError(
                    f"exit_policy={self.exit_policy} is research-only and cannot run in live mode"
                )
            if self.quote_mode != "EXECUTABLE":
                raise ValueError(
                    "live mode requires quote_mode=EXECUTABLE: pricing a real order off a "
                    "cached LTP is what COMPATIBILITY mode exists to reproduce, not to trade"
                )
            if self.quantity <= 0:
                raise ValueError("live mode requires an explicit positive quantity")
            if not self.require_session_origin_tick:
                raise ValueError(
                    "live mode requires require_session_origin_tick: pricing a real order "
                    "from a quote that cannot be proved to belong to this session is how "
                    "the recorded bot sent 416.90 into a market that opened at 356.70"
                )
            if self.protection_mode == "NONE":
                raise ValueError(
                    "live mode requires broker-side protection: with protection_mode=NONE "
                    "a crash or a dropped socket leaves the open position with nothing "
                    "watching it"
                )
        return self

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def field_names(cls) -> frozenset[str]:
        return frozenset(f.name for f in fields(cls))
