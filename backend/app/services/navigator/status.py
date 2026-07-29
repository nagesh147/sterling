"""Navigator health/status (spec §18.3). The point of this module is to
make "no signal" externally distinguishable from "no data" — a status API
consumer should never have to guess which one they're looking at."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

NavigatorHealth = Literal["DISABLED", "STARTING", "WARMING_UP", "HEALTHY", "DEGRADED", "STALE", "ERROR"]


@dataclass(frozen=True)
class ComponentStatus:
    name: str
    quality: Literal["ok", "degraded", "unavailable"]
    last_updated_ms: Optional[int] = None
    reason_codes: list = field(default_factory=list)


@dataclass(frozen=True)
class NavigatorStatusSnapshot:
    health: NavigatorHealth
    enabled: bool
    operating_mode: str
    calibration_readiness: str
    config_revision: int
    activation_watermark_ms: int
    components: list[ComponentStatus]
    last_decision_at_ms: Optional[int]
    sampler_running: bool


def derive_health(
    *, enabled: bool, components: list[ComponentStatus], sampler_running: bool,
    now_ms: int, max_feature_age_seconds: int,
) -> NavigatorHealth:
    if not enabled:
        return "DISABLED"
    if not components:
        return "STARTING"

    def _age_s(c: ComponentStatus) -> Optional[float]:
        return None if c.last_updated_ms is None else (now_ms - c.last_updated_ms) / 1000.0

    # An unavailable component might just be within its normal warmup window,
    # or it might be genuinely stuck — staleness (3x the configured max
    # feature age) is what distinguishes the two.
    if any(c.quality == "unavailable" for c in components):
        stuck = any((a := _age_s(c)) is not None and a > max_feature_age_seconds * 3 for c in components)
        return "STALE" if stuck else "WARMING_UP"

    if any((a := _age_s(c)) is not None and a > max_feature_age_seconds for c in components):
        return "STALE"
    if any(c.quality == "degraded" for c in components):
        return "DEGRADED"
    return "HEALTHY"


def build_status_snapshot(
    *, enabled: bool, operating_mode: str, calibration_readiness: str, config_revision: int,
    activation_watermark_ms: int, components: list[ComponentStatus], last_decision_at_ms: Optional[int],
    sampler_running: bool, now_ms: int, max_feature_age_seconds: int,
) -> NavigatorStatusSnapshot:
    health = derive_health(
        enabled=enabled, components=components, sampler_running=sampler_running,
        now_ms=now_ms, max_feature_age_seconds=max_feature_age_seconds,
    )
    return NavigatorStatusSnapshot(
        health=health, enabled=enabled, operating_mode=operating_mode, calibration_readiness=calibration_readiness,
        config_revision=config_revision, activation_watermark_ms=activation_watermark_ms, components=components,
        last_decision_at_ms=last_decision_at_ms, sampler_running=sampler_running,
    )
