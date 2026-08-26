"""A126 thesis, overlays, protection stages, H4, operating posture.

Numeric rungs are ManagementPolicy, not recovered F-105/F-106/F-110.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import DynamicMode
from .lifecycle_engine import OverlayState, ProtectionState, ThesisState
from .opportunity_mode import OpportunityMode
from .protection import ProtectionDecision
from .structure import StructureSnapshot


@dataclass(frozen=True)
class ManagementPolicy:
    label: str
    thesis_invalid_bars: int = 15
    strong_giveback_ratio: float = 0.25
    weakening_giveback_ratio: float = 0.6
    collapse_giveback_ratio: float = 0.95
    collapse_min_peak_points: float = 20.0
    burst_volatility_ratio: float = 2.0
    extension_max_minutes_remaining: float = 90.0
    extension_min_favorable_points: float = 15.0
    breakeven_favorable_points: float = 0.0

    def __post_init__(self) -> None:
        if self.thesis_invalid_bars < 1:
            raise ValueError("thesis_invalid_bars must be >= 1")
        if not (
            0
            <= self.strong_giveback_ratio
            <= self.weakening_giveback_ratio
            <= self.collapse_giveback_ratio
            <= 1
        ):
            raise ValueError("giveback rungs must be ordered in [0, 1]")


def research_management_policy() -> ManagementPolicy:
    return ManagementPolicy(label="RESEARCH_NOT_LIVE_EXPLICIT_MANAGEMENT_POLICY")


@dataclass(frozen=True)
class ManagementSnapshot:
    thesis: ThesisState
    protection_stage: ProtectionState
    overlays: tuple[OverlayState, ...]
    operating_mode: DynamicMode
    want_session_extension: bool
    reason: str


def classify_thesis(
    *,
    score_aligned: bool,
    features_valid: bool,
    giveback_ratio: float,
    favorable_points: float,
    misaligned_streak: int,
    policy: ManagementPolicy,
) -> ThesisState:
    if (not features_valid and misaligned_streak >= policy.thesis_invalid_bars) or (
        not score_aligned and misaligned_streak >= policy.thesis_invalid_bars
    ):
        return ThesisState.THESIS_INVALID
    if not score_aligned:
        return ThesisState.THESIS_WEAKENING
    if giveback_ratio > policy.weakening_giveback_ratio:
        return ThesisState.THESIS_WEAKENING
    if giveback_ratio <= policy.strong_giveback_ratio and favorable_points > 0:
        return ThesisState.THESIS_STRONG
    return ThesisState.THESIS_VALID


def classify_overlays(
    *,
    features_valid: bool,
    li_valid: bool,
    giveback_ratio: float,
    peak_favorable_points: float,
    volatility_ratio: float | None,
    structure: StructureSnapshot | None,
    side: str | None,
    policy: ManagementPolicy,
) -> tuple[OverlayState, ...]:
    found: list[OverlayState] = []
    if not features_valid:
        found.append(OverlayState.DATA_UNCERTAINTY)
    if not li_valid:
        found.append(OverlayState.LIQUIDITY_STRESS)
    if (
        peak_favorable_points >= policy.collapse_min_peak_points
        and giveback_ratio > policy.collapse_giveback_ratio
    ):
        found.append(OverlayState.ECONOMIC_COLLAPSE)
    if volatility_ratio is not None and volatility_ratio >= policy.burst_volatility_ratio:
        found.append(OverlayState.BURST)
    if structure is not None and side in {"BUY", "SELL"}:
        if side == "BUY" and structure.location == "below_value":
            found.append(OverlayState.OUTSIDE_VALUE)
        if side == "SELL" and structure.location == "above_value":
            found.append(OverlayState.OUTSIDE_VALUE)
        want = 1 if side == "BUY" else -1
        if structure.flow_sign != 0 and structure.flow_sign != want:
            found.append(OverlayState.FLOW_AGAINST)
        if side == "BUY" and structure.vwap_location == "below_vwap":
            found.append(OverlayState.AGAINST_VWAP)
        if side == "SELL" and structure.vwap_location == "above_vwap":
            found.append(OverlayState.AGAINST_VWAP)
        if side == "BUY" and structure.or_location == "below_or":
            found.append(OverlayState.OUTSIDE_OR)
        if side == "SELL" and structure.or_location == "above_or":
            found.append(OverlayState.OUTSIDE_OR)
        if side == "BUY" and structure.poc_migration == "down":
            found.append(OverlayState.VALUE_MIGRATION_AGAINST)
        if side == "SELL" and structure.poc_migration == "up":
            found.append(OverlayState.VALUE_MIGRATION_AGAINST)
        if (
            structure.close is not None
            and structure.nearest_lvn is not None
            and abs(structure.close - structure.nearest_lvn) <= 1.0
        ):
            found.append(OverlayState.AT_LVN)
    return tuple(found)


def classify_protection_stage(
    *,
    favorable_points: float,
    protection: ProtectionDecision | None,
    stop_points: float | None,
) -> ProtectionState:
    if protection is not None and protection.lock_active:
        if protection.trail_price is not None and stop_points and favorable_points >= stop_points:
            return ProtectionState.P3_AGGRESSIVE_TRAIL
        return ProtectionState.P2_PROFIT_PROTECTED
    if favorable_points > 0 and protection is not None and protection.trail_price is not None:
        return ProtectionState.P1_BREAKEVEN_PROTECTED
    if favorable_points > 0:
        return ProtectionState.P1_BREAKEVEN_PROTECTED
    return ProtectionState.P0_RISK_CONTROLLED


def want_session_extension(
    *,
    mode: OpportunityMode | None,
    minutes_to_cutoff: float,
    favorable_points: float,
    score_aligned: bool,
    policy: ManagementPolicy,
) -> bool:
    return bool(
        mode is OpportunityMode.INTRADAY
        and score_aligned
        and 0 < minutes_to_cutoff <= policy.extension_max_minutes_remaining
        and favorable_points >= policy.extension_min_favorable_points
    )


def classify_operating_mode(
    *,
    in_position: bool,
    cutoff: bool,
    thesis: ThesisState,
    opportunity_mode: OpportunityMode | None,
    overlays: tuple[OverlayState, ...],
) -> DynamicMode:
    if OverlayState.EMERGENCY in overlays:
        return DynamicMode.HALTED
    if cutoff or thesis is ThesisState.THESIS_INVALID:
        return DynamicMode.EXIT_ONLY
    if not in_position:
        return DynamicMode.OBSERVE
    if (
        thesis is ThesisState.THESIS_WEAKENING
        or OverlayState.LIQUIDITY_STRESS in overlays
        or OverlayState.ECONOMIC_COLLAPSE in overlays
        or OverlayState.FLOW_AGAINST in overlays
        or OverlayState.OUTSIDE_VALUE in overlays
        or OverlayState.AGAINST_VWAP in overlays
        or OverlayState.OUTSIDE_OR in overlays
        or OverlayState.VALUE_MIGRATION_AGAINST in overlays
    ):
        return DynamicMode.DEFENSIVE
    if opportunity_mode is OpportunityMode.INTRADAY:
        return DynamicMode.INTRADAY
    return DynamicMode.ACTIVE


def evaluate_management(
    *,
    score_aligned: bool,
    features_valid: bool,
    li_valid: bool,
    giveback_ratio: float,
    favorable_points: float,
    peak_favorable_points: float,
    misaligned_streak: int,
    minutes_to_cutoff: float,
    volatility_ratio: float | None,
    opportunity_mode: OpportunityMode | None,
    protection: ProtectionDecision | None,
    stop_points: float | None,
    cutoff: bool,
    in_position: bool,
    policy: ManagementPolicy,
    structure: StructureSnapshot | None = None,
    side: str | None = None,
) -> ManagementSnapshot:
    thesis = classify_thesis(
        score_aligned=score_aligned,
        features_valid=features_valid,
        giveback_ratio=giveback_ratio,
        favorable_points=favorable_points,
        misaligned_streak=misaligned_streak,
        policy=policy,
    )
    overlays = classify_overlays(
        features_valid=features_valid,
        li_valid=li_valid,
        giveback_ratio=giveback_ratio,
        peak_favorable_points=peak_favorable_points,
        volatility_ratio=volatility_ratio,
        structure=structure,
        side=side,
        policy=policy,
    )
    stage = classify_protection_stage(
        favorable_points=favorable_points,
        protection=protection,
        stop_points=stop_points,
    )
    extension = want_session_extension(
        mode=opportunity_mode,
        minutes_to_cutoff=minutes_to_cutoff,
        favorable_points=favorable_points,
        score_aligned=score_aligned,
        policy=policy,
    )
    posture = classify_operating_mode(
        in_position=in_position,
        cutoff=cutoff,
        thesis=thesis,
        opportunity_mode=opportunity_mode,
        overlays=overlays,
    )
    return ManagementSnapshot(
        thesis=thesis,
        protection_stage=stage,
        overlays=overlays,
        operating_mode=posture,
        want_session_extension=extension,
        reason=f"{thesis.value}|{stage.value}|{posture.value}",
    )
