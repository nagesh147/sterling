"""Domain models for the Sterling Value-Flow Navigator.

This build is Kite-only: `BaseSignalEvidence.engine_id` is a single-value
`Literal` on purpose so a second engine source (e.g. the crypto/directional
path) cannot be wired in without deliberately widening this contract. See
`app.services.navigator.adapters.KiteTripleSupertrendAdapter` for the only
adapter that produces one.

Grown incrementally across phases; this file currently defines only the
Phase 0 base-signal contract.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def canonical_json_hash(payload: Any) -> str:
    """Deterministic sha256 hex digest of a JSON-serializable payload.

    Used everywhere Navigator needs a stable fingerprint (raw signal rows,
    config payloads, feature inputs) — key order and float/str formatting
    must not affect the digest, so this always re-serializes with sorted
    keys and compact separators before hashing.
    """
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class BaseSignalEvidence(BaseModel):
    """Immutable, broker-neutral snapshot of one Sterling base-signal event.

    Produced only by an adapter (never hand-constructed by fusion code), so
    every field here is already validated evidence, not a raw engine row.
    """

    model_config = ConfigDict(frozen=True)

    signal_id: str
    engine_id: Literal["kite_triple_supertrend"] = "kite_triple_supertrend"
    user_id: str
    underlying: str
    exchange: str
    instrument_token: int
    timeframe: str
    bar_open_ms: int
    bar_close_ms: int
    observed_at_ms: int
    direction: Literal["long", "short"]
    state: Literal["fresh", "active"]
    score_100: float
    source: str
    strategy: str
    config_revision: str
    raw_payload_hash: str

    @field_validator("score_100")
    @classmethod
    def _score_bounds(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"score_100 must be within [0, 100], got {v!r}")
        return v

    @field_validator("signal_id", "user_id", "underlying", "exchange", "timeframe", "source", "strategy", "config_revision", "raw_payload_hash")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("field must not be empty")
        return v

    @model_validator(mode="after")
    def _bar_timing_is_sane(self) -> "BaseSignalEvidence":
        if self.bar_open_ms > self.bar_close_ms:
            raise ValueError(
                f"bar_open_ms ({self.bar_open_ms}) must not be after "
                f"bar_close_ms ({self.bar_close_ms})"
            )
        if self.bar_close_ms > self.observed_at_ms:
            raise ValueError(
                f"bar_close_ms ({self.bar_close_ms}) is after observed_at_ms "
                f"({self.observed_at_ms}) — refusing evidence from the future"
            )
        return self


# ─────────────────────────────────────────────────────────────────────────
# Section 5 — evidence + fused decision domain models
# ─────────────────────────────────────────────────────────────────────────

#: Closed reason-code enum. Starts from spec §5.3's list, extended with the
#: deterministic volatility notes from §9.4 and a small set of Sterling-
#: designed additions needed to make §13's hard-gate table and §6.5's
#: not-applicable renormalization expressible as closed codes instead of
#: free text ("Do not use free-form errors for decision logic.").
NAVIGATOR_REASON_CODES: tuple[str, ...] = (
    # --- §5.3 starter closed enum (source-defined by the implementation spec) ---
    "OK", "MARKET_CLOSED", "CALENDAR_UNKNOWN", "AUTH_REQUIRED",
    "UNSUPPORTED_INSTRUMENT", "PRICE_BARS_MISSING", "PRICE_BAR_OPEN",
    "PRICE_VOLUME_INVALID", "CHAIN_UNAVAILABLE", "CHAIN_INCOMPLETE",
    "CHAIN_STALE", "CHAIN_CLOCK_SKEW", "QUOTE_CROSSED", "QUOTE_TOO_WIDE",
    "COUNTER_RESET", "FLOW_WARMING_UP", "IV_MISSING", "IV_INVALID",
    "EXPIRY_INVALID", "GAMMA_WARMING_UP", "CONFIG_INVALID", "RATE_LIMITED",
    "COMPONENT_CONFLICT", "ACTIVATION_WATERMARK",
    # --- §9.4 deterministic volatility notes ---
    "TREND_FORMING_WAIT", "BULLISH_EXPANSION", "BEARISH_EXPANSION",
    "NO_DIRECTIONAL_EDGE", "VOLATILITY_FADING", "COMPRESSION_NO_TREND",
    "LATE_AFTER_FLIP", "VOL_WARMING_UP", "AVWAP_WARMING_UP",
    # --- Sterling-designed additions (fusion-layer bookkeeping) ---
    "GAMMA_UNAVAILABLE_OPTIONAL", "COMPONENT_NOT_APPLICABLE",
    "NO_FRESH_TRIGGER", "STRONG_OPPOSING_EVIDENCE",
    "SCORE_BELOW_THRESHOLD", "CONFIG_REVISION_STALE",
)
_REASON_CODE_SET = frozenset(NAVIGATOR_REASON_CODES)

ReasonCode = Literal[
    "OK", "MARKET_CLOSED", "CALENDAR_UNKNOWN", "AUTH_REQUIRED",
    "UNSUPPORTED_INSTRUMENT", "PRICE_BARS_MISSING", "PRICE_BAR_OPEN",
    "PRICE_VOLUME_INVALID", "CHAIN_UNAVAILABLE", "CHAIN_INCOMPLETE",
    "CHAIN_STALE", "CHAIN_CLOCK_SKEW", "QUOTE_CROSSED", "QUOTE_TOO_WIDE",
    "COUNTER_RESET", "FLOW_WARMING_UP", "IV_MISSING", "IV_INVALID",
    "EXPIRY_INVALID", "GAMMA_WARMING_UP", "CONFIG_INVALID", "RATE_LIMITED",
    "COMPONENT_CONFLICT", "ACTIVATION_WATERMARK",
    "TREND_FORMING_WAIT", "BULLISH_EXPANSION", "BEARISH_EXPANSION",
    "NO_DIRECTIONAL_EDGE", "VOLATILITY_FADING", "COMPRESSION_NO_TREND",
    "LATE_AFTER_FLIP", "VOL_WARMING_UP", "AVWAP_WARMING_UP",
    "GAMMA_UNAVAILABLE_OPTIONAL", "COMPONENT_NOT_APPLICABLE",
    "NO_FRESH_TRIGGER", "STRONG_OPPOSING_EVIDENCE",
    "SCORE_BELOW_THRESHOLD", "CONFIG_REVISION_STALE",
]

NavigatorComponent = Literal["avwap", "volatility", "option_flow", "gamma"]
NavigatorStatus = Literal[
    "NO_DATA", "WAIT", "CONFLICT", "WATCH", "CONFIRMED", "HIGH_CONVICTION",
]
AvwapGrade = Literal["A+", "A", "B"]


class DirectionalEvidence(BaseModel):
    """Common shape every Navigator component (AVWAP/volatility/flow/gamma)
    returns. `direction=0` means genuinely neutral, never "missing" — missing
    always uses `quality="unavailable"` instead."""

    model_config = ConfigDict(frozen=True)

    component: NavigatorComponent
    as_of_bar_close_ms: int
    observed_at_ms: int
    direction: Literal[-1, 0, 1]
    confidence_100: float
    quality: Literal["ok", "degraded", "unavailable"]
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    diagnostics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)

    @field_validator("confidence_100")
    @classmethod
    def _confidence_bounds(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"confidence_100 must be within [0, 100], got {v!r}")
        return v

    @model_validator(mode="after")
    def _timing_and_quality_consistency(self) -> "DirectionalEvidence":
        if self.as_of_bar_close_ms > self.observed_at_ms:
            raise ValueError("as_of_bar_close_ms must not be after observed_at_ms")
        if self.quality == "unavailable" and self.direction != 0:
            raise ValueError(
                "unavailable evidence must report direction=0 — missing "
                "evidence is never allowed to imply a side"
            )
        return self


class NavigatorDecision(BaseModel):
    """One immutable fused decision. Reprocessing identical inputs is
    idempotent — the same inputs/config always produce the same
    `decision_id` and the same field values (see `fusion.py`)."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    schema_version: int = 1
    config_revision: int
    model_versions: dict[str, str]
    generated_at_ms: int
    bar_close_ms: int
    activation_watermark_ms: int
    base_signal_id: str
    trigger: Literal["base_fresh", "avwap_fresh"]
    direction: Literal["long", "short"]
    status: NavigatorStatus
    base_score: float
    suite_score: Optional[float] = None
    effective_score: Optional[float] = None
    execution_eligible: bool = False
    data_quality: str
    reason_codes: list[ReasonCode] = Field(default_factory=list)
    avwap: Optional[DirectionalEvidence] = None
    volatility: Optional[DirectionalEvidence] = None
    option_flow: Optional[DirectionalEvidence] = None
    gamma: Optional[DirectionalEvidence] = None

    @field_validator("base_score")
    @classmethod
    def _base_score_bounds(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError(f"base_score must be within [0, 100], got {v!r}")
        return v

    @field_validator("suite_score", "effective_score")
    @classmethod
    def _optional_score_bounds(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError(f"score must be within [0, 100], got {v!r}")
        return v

    @model_validator(mode="after")
    def _status_invariants(self) -> "NavigatorDecision":
        if self.status == "NO_DATA" and self.effective_score is not None:
            raise ValueError("effective_score must be None for status=NO_DATA")
        if self.execution_eligible and self.status not in ("CONFIRMED", "HIGH_CONVICTION"):
            raise ValueError(
                "execution_eligible=True requires status CONFIRMED or "
                f"HIGH_CONVICTION, got {self.status!r}"
            )
        return self


# ─────────────────────────────────────────────────────────────────────────
# Section 6 — configuration contract (Kite-only build: `engine_sources` is
# fixed to a single value; there is no directional/crypto config surface).
# ─────────────────────────────────────────────────────────────────────────


class AvwapConfig(BaseModel):
    """§6.2 — STERLING-DESIGNED formula; numeric defaults CALIBRATION-REQUIRED."""

    enabled: bool = True
    pivot_left_bars: int = Field(3, ge=1, le=20)
    pivot_right_bars: int = Field(3, ge=1, le=20)
    slope_lookback_bars: int = Field(5, ge=2, le=50)
    min_slope_atr_per_bar: float = Field(0.02, ge=0.0, le=2.0)
    atr_period: int = Field(14, ge=5, le=100)
    relative_volume_period: int = Field(20, ge=5, le=200)
    touch_tolerance_atr: float = Field(0.20, ge=0.01, le=1.00)
    min_body_atr: float = Field(0.35, ge=0.0, le=3.0)
    min_relative_volume: float = Field(1.20, ge=0.0, le=10.0)
    breakout_buffer_atr: float = Field(0.10, ge=0.0, le=2.0)
    max_extension_atr: float = Field(1.50, ge=0.25, le=10.0)
    cooldown_bars: int = Field(5, ge=0, le=100)
    grade_a_plus_min: float = Field(85.0, ge=0.0, le=100.0)
    grade_a_min: float = Field(75.0, ge=0.0, le=100.0)
    grade_b_min: float = Field(65.0, ge=0.0, le=100.0)
    stop_buffer_atr: float = Field(0.15, ge=0.0, le=3.0)
    max_stop_distance_atr: float = Field(2.00, gt=0.0)
    target_r: float = Field(2.00, ge=0.5, le=10.0)

    @model_validator(mode="after")
    def _grade_and_stop_ordering(self) -> "AvwapConfig":
        if not (self.grade_a_plus_min > self.grade_a_min > self.grade_b_min):
            raise ValueError(
                "grade thresholds must satisfy grade_a_plus_min > grade_a_min "
                "> grade_b_min "
                f"(got {self.grade_a_plus_min}, {self.grade_a_min}, {self.grade_b_min})"
            )
        if self.max_stop_distance_atr <= self.stop_buffer_atr:
            raise ValueError("max_stop_distance_atr must exceed stop_buffer_atr")
        return self


class RangesConfig(BaseModel):
    """§6.3 — STERLING-DESIGNED; target/lookbacks CALIBRATION-REQUIRED."""

    method: Literal["rolling_empirical_quantile_v1"] = "rolling_empirical_quantile_v1"
    target_coverage: float = Field(0.80, gt=0.0, lt=1.0)
    daily_lookback_sessions: int = Field(120, ge=1)
    daily_min_sessions: int = Field(60, ge=1)
    weekly_lookback_periods: int = Field(104, ge=1)
    weekly_min_periods: int = Field(52, ge=1)
    condition_on_volatility: bool = True
    min_condition_bucket: int = Field(30, ge=1)
    decay: float = Field(0.98, gt=0.0, le=1.0)
    edge_tolerance_atr: float = Field(0.25, gt=0.0)

    @model_validator(mode="after")
    def _min_not_above_lookback(self) -> "RangesConfig":
        if self.daily_min_sessions > self.daily_lookback_sessions:
            raise ValueError("daily_min_sessions must not exceed daily_lookback_sessions")
        if self.weekly_min_periods > self.weekly_lookback_periods:
            raise ValueError("weekly_min_periods must not exceed weekly_lookback_periods")
        return self


class VolatilityConfig(BaseModel):
    """§6.4 — STERLING-DESIGNED; all weights/thresholds CALIBRATION-REQUIRED."""

    enabled: bool = True
    atr_period: int = Field(14, ge=2)
    rv_short_bars: int = Field(8, ge=2)
    rv_long_bars: int = Field(32, ge=2)
    band_period: int = Field(20, ge=2)
    band_stddev: float = Field(2.0, gt=0.0)
    percentile_lookback: int = Field(120, ge=60)
    gradient_bars: int = Field(5, ge=2, le=50)
    expansion_min: float = Field(65.0, ge=0.0, le=100.0)
    compression_max: float = Field(35.0, ge=0.0, le=100.0)
    adx_period: int = Field(14, ge=2)
    adx_min: float = Field(18.0, ge=0.0, le=100.0)
    ema_fast_period: int = Field(8, ge=1)
    ema_slow_period: int = Field(21, ge=2)
    trend_confirm_bars: int = Field(2, ge=1)
    max_flip_age_bars: int = Field(8, ge=1)
    min_direction_confidence: float = Field(60.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _window_ordering(self) -> "VolatilityConfig":
        if self.rv_long_bars <= self.rv_short_bars:
            raise ValueError("rv_long_bars must exceed rv_short_bars")
        if self.compression_max >= self.expansion_min:
            raise ValueError("compression_max must be less than expansion_min")
        if self.ema_slow_period <= self.ema_fast_period:
            raise ValueError("ema_slow_period must exceed ema_fast_period")
        return self


class FlowConfig(BaseModel):
    """§6.5 — behavior SOURCE-DEFINED, formula STERLING-DESIGNED, thresholds
    CALIBRATION-REQUIRED."""

    enabled: bool = True
    mode: Literal["dynamic", "broad"] = "dynamic"
    dynamic_strike_radius: int = Field(2, ge=1, le=20)
    broad_strike_radius: int = Field(5, ge=1, le=50)
    expiry_policy: Literal["nearest_valid"] = "nearest_valid"
    manual_expiry: Optional[str] = None
    manual_atm: Optional[float] = None
    strike_step_override: Optional[float] = None
    max_quote_age_seconds: int = Field(20, ge=1)
    max_sample_gap_seconds: int = Field(150, ge=1)
    min_chain_completeness: float = Field(0.80, gt=0.0, le=1.0)
    max_spread_pct: float = Field(0.08, gt=0.0, le=1.0)
    warmup_samples: int = Field(30, ge=1)
    robust_window_samples: int = Field(120, ge=1)
    price_scale_floor: float = Field(0.0001, gt=0.0)
    oi_intensity_weight: float = Field(0.25, ge=0.0, le=1.0)
    z_scale: float = Field(2.0, gt=0.0)
    zero_hysteresis: float = Field(10.0, ge=0.0, le=100.0)
    strong_zone: float = Field(68.0, ge=0.0, le=100.0)
    extreme_zone: float = Field(96.0, ge=0.0, le=100.0)
    require_for_index_gate: bool = True

    @model_validator(mode="after")
    def _radius_and_window_ordering(self) -> "FlowConfig":
        if self.broad_strike_radius <= self.dynamic_strike_radius:
            raise ValueError("broad_strike_radius must exceed dynamic_strike_radius")
        if self.robust_window_samples <= self.warmup_samples:
            raise ValueError("robust_window_samples must exceed warmup_samples")
        if self.extreme_zone <= self.strong_zone:
            raise ValueError("extreme_zone must exceed strong_zone")
        return self


class GammaConfig(BaseModel):
    """§6.6 — behavior SOURCE-DEFINED, formula STERLING-DESIGNED, thresholds
    CALIBRATION-REQUIRED. `risk_free_rate`/`dividend_yield` default to None —
    gamma stays unavailable (never a fabricated rate) until an operator sets
    a verified value."""

    enabled: bool = True
    rate_source: Literal["manual"] = "manual"
    risk_free_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    dividend_yield: Optional[float] = Field(None, ge=0.0, le=1.0)
    min_iv: float = Field(0.01, gt=0.0, le=5.0)
    max_iv: float = Field(5.00, gt=0.0, le=20.0)
    robust_window_samples: int = Field(120, ge=1)
    min_samples: int = Field(30, ge=1)
    blast_z_min: float = Field(3.0, gt=0.0)
    acceleration_z_min: float = Field(2.0, gt=0.0)
    expiry_profile_start_ist: str = "14:00"
    require_flow_alignment: bool = True
    required_for_gate: bool = False

    @field_validator("expiry_profile_start_ist")
    @classmethod
    def _hh_mm_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            raise ValueError(f"expiry_profile_start_ist must be 'HH:MM', got {v!r}")
        hh, mm = int(parts[0]), int(parts[1])
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            raise ValueError(f"expiry_profile_start_ist out of range: {v!r}")
        return v

    @model_validator(mode="after")
    def _iv_and_sample_ordering(self) -> "GammaConfig":
        if self.max_iv <= self.min_iv:
            raise ValueError("max_iv must exceed min_iv")
        if self.min_samples > self.robust_window_samples:
            raise ValueError("min_samples must not exceed robust_window_samples")
        return self


class ExpiryProfileConfig(BaseModel):
    """§6.7 — expiry identity always comes from the listed contract + official
    session calendar, never a weekday rule or integer DTE."""

    enabled: bool = True
    require_expansion: bool = True
    min_avwap_grade: AvwapGrade = "A"
    min_abs_flow: float = Field(68.0, ge=0.0, le=100.0)
    max_extension_atr: float = Field(1.00, gt=0.0)
    emit_tighten_note: bool = True


class FusionConfig(BaseModel):
    """§6.8 — all weights CALIBRATION-REQUIRED; weights must sum to 100."""

    base_weight: float = Field(35.0, ge=0.0, le=100.0)
    avwap_weight: float = Field(25.0, ge=0.0, le=100.0)
    volatility_weight: float = Field(20.0, ge=0.0, le=100.0)
    flow_weight: float = Field(15.0, ge=0.0, le=100.0)
    gamma_weight: float = Field(5.0, ge=0.0, le=100.0)
    min_avwap_grade: AvwapGrade = "A"
    strong_conflict_confidence: float = Field(70.0, ge=0.0, le=100.0)
    confirmed_score_min: float = Field(70.0, ge=0.0, le=100.0)
    high_conviction_score_min: float = Field(85.0, ge=0.0, le=100.0)
    require_fresh_trigger: bool = True
    require_all_gate_components: bool = True

    @model_validator(mode="after")
    def _weights_sum_to_100(self) -> "FusionConfig":
        total = (
            self.base_weight + self.avwap_weight + self.volatility_weight
            + self.flow_weight + self.gamma_weight
        )
        if abs(total - 100.0) > 1e-6:
            raise ValueError(f"fusion weights must sum to 100, got {total!r}")
        if self.high_conviction_score_min < self.confirmed_score_min:
            raise ValueError(
                "high_conviction_score_min must be >= confirmed_score_min"
            )
        return self


class NavigatorConfigModel(BaseModel):
    """§6 root settings. Kite-only build: `engine_sources` is a fixed
    single-value list — there is no directional/crypto config surface, and
    none is planned. (`engine_sources` says whose signals Navigator ALSO
    comments on; it is not a claim that Navigator can only run downstream of
    that engine — see `scan_scope_mode`.) This is the client-editable payload
    only; server-owned metadata (revision, timestamps, watermark, calibration
    readiness) lives in `NavigatorConfigRecord` below, never here."""

    # Literal[1], not int: an unsupported version must fail Pydantic
    # validation (→ HTTP 400 INVALID_CONFIG at both /config and
    # /config/validate) rather than pass validation and only fail later as
    # a raw ValueError out of config_store.save (→ an uncaught 500).
    schema_version: Literal[1] = 1
    enabled: bool = False
    operating_mode: Literal["shadow", "advisory", "gate"] = "advisory"
    engine_sources: list[Literal["kite_triple_supertrend"]] = Field(
        default_factory=lambda: ["kite_triple_supertrend"]
    )
    #: DEPRECATED and no longer read by any scan path. Navigator's universe is
    #: now resolved per-scan from `scan_scope_mode` below. Retained only so
    #: configs persisted before the peer-engine change still deserialize; it
    #: is not editable in the UI and changing it has no effect.
    underlyings: list[str] = Field(default_factory=list)
    # ── Scan scope: shared with the Kite engine, or Navigator's own ─────────
    # Navigator started life as a confirmation layer over the Kite engine, so
    # it had no universe of its own — it saw whatever that engine scanned.
    # Now that it can also originate signals it is a peer engine, and needs
    # its own answer to "what do I cover".
    #
    #   "shared" (default) — Navigator covers exactly what the Kite engine
    #       covers: same universe, same scan_source. Preserves the behaviour
    #       every existing config already has, so this is a no-op upgrade.
    #   "custom" — Navigator resolves its OWN universe from the
    #       `scan_indices`/`scan_stocks`/`scan_all_stocks` fields below and
    #       uses its own `scan_source`. The Kite engine is unaffected either
    #       way; the two universes may overlap fully, partly, or not at all.
    #
    # The four fields below are read ONLY when scan_scope_mode == "custom".
    # In shared mode they are inert (kept, not cleared, so flipping back and
    # forth doesn't lose a configured custom universe).
    scan_scope_mode: Literal["shared", "custom"] = "shared"
    scan_indices: list[str] = Field(default_factory=list)
    scan_stocks: list[str] = Field(default_factory=list)
    scan_all_stocks: bool = False
    #: Master switch above Navigator's own stock list — see the engine field of
    #: the same name. Read only when scan_scope_mode == "custom".
    scan_stock_contracts: bool = True
    scan_source: Literal["spot", "derivatives", "both", "confluence"] = "spot"
    #: Navigator's OWN contract coverage. ``None`` (default) means "follow the
    #: Kite engine's", which is what every existing config does and what the
    #: runtime did unconditionally before these existed. Set them to give
    #: Navigator a different strike ladder or expiry cycle from SuperTrend —
    #: the two engines look for different things, so a user who wants Navigator
    #: on ATM-only while SuperTrend sweeps the full ladder can now say so.
    #:
    #: Read independently of ``scan_scope_mode``: contract coverage and the
    #: instrument universe are separate choices, and forcing them to move
    #: together is what made the old "shared" flag confusing.
    strike_moneyness: Optional[list[Literal[
        "ATM", "ITM1", "ITM2", "ITM3", "ITM4", "ITM5",
        "OTM1", "OTM2", "OTM3", "OTM4", "OTM5",
    ]]] = None
    scan_expiries_indices: Optional[list[Literal["weekly", "monthly"]]] = None
    #: Empty list = do not scan single-stock contracts at all (the exchange
    #: lists only a monthly cycle, so "monthly" is the sole thing to include).
    scan_expiries_stocks: Optional[list[Literal["monthly"]]] = None
    # ── Structure Radar / Signal Origination (additive, all off by default) ──
    # See docs/superpowers/specs/2026-07-28-navigator-structure-radar-origination-design.md.
    # Orthogonal to `operating_mode` — none of these change how Navigator
    # attaches to a real SuperTrend row; they only add a NEW, independent
    # path where Navigator can compute/surface evidence with no SuperTrend
    # trigger at all.
    #
    # Continuously compute AVWAP + Volatility for every configured underlying
    # (both directions) every scan, whether or not SuperTrend has a live row
    # there. Feeds /snapshot, /series, /status. Never adds a signal-table row
    # by itself.
    structure_radar_enabled: bool = False
    # Off: today's behaviour, unchanged. Heads-up: a Navigator-only CONFIRMED/
    # HIGH_CONVICTION decision with no accompanying real SuperTrend row is
    # surfaced as a new signal-table row (source="navigator"), visible but
    # never executable. Full: same, plus a real ATM leg is resolved and the
    # row becomes tradeable like any other row (manual + eligible for
    # auto-exec, subject to `auto_execute_originated` below).
    signal_origination: Literal["off", "heads_up", "full"] = "off"
    # Only takes effect when signal_origination == "full". Lets a
    # Navigator-originated row fire through the SAME auto-exec path as every
    # other row, gated by the base engine's own `auto_execute` switch,
    # `calibration_readiness == "ready"`, and the decision's own
    # `execution_eligible` — at least as conservative as the existing `gate`
    # operating mode's own calibration gate.
    auto_execute_originated: bool = False
    price_timeframe: Literal["60minute"] = "60minute"
    flow_sample_seconds: int = Field(60, ge=15, le=300)
    max_feature_age_seconds: int = Field(120, ge=10, le=3600)
    event_alignment_bars: int = Field(2, ge=0, le=20)
    entry_delay_after_open_minutes: int = Field(5, ge=0, le=60)
    retention_raw_days: int = Field(30, ge=1, le=365)
    retention_features_days: int = Field(365, ge=1, le=3650)

    avwap: AvwapConfig = Field(default_factory=AvwapConfig)
    ranges: RangesConfig = Field(default_factory=RangesConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    flow: FlowConfig = Field(default_factory=FlowConfig)
    gamma: GammaConfig = Field(default_factory=GammaConfig)
    expiry_profile: ExpiryProfileConfig = Field(default_factory=ExpiryProfileConfig)
    fusion: FusionConfig = Field(default_factory=FusionConfig)

    @field_validator("engine_sources")
    @classmethod
    def _kite_only(cls, v: list[str]) -> list[str]:
        if v != ["kite_triple_supertrend"]:
            raise ValueError(
                "this build only supports engine_sources=['kite_triple_supertrend'] "
                f"— got {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _custom_scope_needs_a_universe(self) -> "NavigatorConfigModel":
        """Custom scope with nothing selected would silently scan nothing —
        Navigator would look enabled and simply never produce evidence. Fail
        loud at save time instead (same ethos as the fusion-weight and
        grade-ordering validators above)."""
        if self.scan_scope_mode == "custom" and not (
            self.scan_indices or self.scan_stocks or self.scan_all_stocks
        ):
            raise ValueError(
                "scan_scope_mode='custom' needs at least one of scan_indices, "
                "scan_stocks, or scan_all_stocks — an empty custom universe "
                "would scan nothing at all. Pick instruments, or switch back "
                "to scan_scope_mode='shared'."
            )
        return self

    @model_validator(mode="after")
    def _auto_execute_originated_requires_full(self) -> "NavigatorConfigModel":
        if self.auto_execute_originated and self.signal_origination != "full":
            raise ValueError(
                "auto_execute_originated=True requires signal_origination='full' "
                f"— got signal_origination={self.signal_origination!r}"
            )
        return self

    @classmethod
    def default_for(cls, underlyings: list[str]) -> "NavigatorConfigModel":
        """Construct the off-by-default config, seeded with the caller's
        current Kite engine underlyings so enabling Navigator for the first
        time scans exactly what the user already scans — no surprise
        universe expansion on first enable."""
        return cls(underlyings=list(underlyings))


class NavigatorConfigRecord(BaseModel):
    """§6.9 — server-owned settings metadata layered on top of the
    client-editable `NavigatorConfigModel`. Returned by every config API
    response so the client always sees the authoritative revision."""

    user_id: str
    config: NavigatorConfigModel
    revision: int
    activation_watermark_ms: int
    calibration_readiness: Literal["not_ready", "ready"] = "not_ready"
    calibration_report_id: Optional[str] = None
    created_at_ms: int
    updated_at_ms: int
