"""Global (engine-level) derivatives config. Distinct from the per-strategy
`profile_overrides`: this picks WHICH engine produces candidates and how it
behaves (active alpha sources, risk posture, validation method)."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EngineMode(str, Enum):
    ROUTING_GATE = "routing_gate"   # existing selector.decide_both (default)
    NATIVE = "native"               # new native_engine.decide_both


class RiskPosture(str, Enum):
    LONG_ONLY = "long_only"         # buy premium only (max loss = premium)
    DEFINED_RISK = "defined_risk"   # + spreads/condors (Phase 2b)
    NAKED = "naked"                 # + short options (Phase 2d, opt-in)


ALPHA_SOURCES = {"directional_futures", "vrp_voltiming", "skew_put", "gex_pinning"}


class DerivativesEngineConfig(BaseModel):
    engine_mode: EngineMode = EngineMode.ROUTING_GATE
    active_alpha_sources: list[str] = Field(
        default_factory=lambda: ["directional_futures"])
    risk_posture: RiskPosture = RiskPosture.LONG_ONLY
    validation_method: int = 1      # 1=calibrate-live, 2=real-only, 3=snapshot

    @field_validator("active_alpha_sources")
    @classmethod
    def _known_sources(cls, v: list[str]) -> list[str]:
        bad = set(v) - ALPHA_SOURCES
        if bad:
            raise ValueError(f"unknown alpha sources: {sorted(bad)}")
        return v

    @field_validator("validation_method")
    @classmethod
    def _valid_method(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("validation_method must be 1, 2 or 3")
        return v
