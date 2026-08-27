"""Adaptive Edge research UI API. Does not unlock ExecutionGate or F-101."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.engines.adaptive_edge.execution_gate import evaluate_execution_gate
from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.option_ladder import (
    AE_DEFAULT_LADDER,
    ALLOWED_MONEYNESS,
    INDEX_TO_TAPE,
    build_snapshot_signals,
    load_live_spot_scans,
)
from app.engines.adaptive_edge.production_readiness import production_readiness
from app.services import db

router = APIRouter(prefix="/adaptive-edge", tags=["adaptive-edge"])
CONFIG_KEY = "adaptive_edge_settings"
ARTIFACT = Path(__file__).resolve().parents[4] / "data" / "adaptive_edge" / "research_e2e.json"
MANIFEST = ARTIFACT.with_name("software_e2e_manifest.json")
DEFAULT_INDICES = ["NIFTY 50", "NIFTY BANK", "NIFTY FIN SERVICE", "SENSEX"]
ScanSource = Literal["spot", "derivatives", "both", "confluence"]
ScanExpiry = Literal["weekly", "monthly"]


class AdaptiveEdgeSettings(BaseModel):
    enabled: bool = False
    symbol: str = "NIFTY-I"
    symbols: list[str] = Field(default_factory=lambda: ["NIFTY-I"])
    scan_source: ScanSource = "spot"
    scan_indices: list[str] = Field(default_factory=lambda: list(DEFAULT_INDICES))
    scan_stocks: list[str] = Field(default_factory=list)
    scan_all_stocks: bool = False
    scan_stock_contracts: bool = False
    strike_moneyness: list[str] = Field(default_factory=lambda: list(AE_DEFAULT_LADDER))
    scan_expiries: list[ScanExpiry] = Field(default_factory=lambda: ["weekly", "monthly"])
    scan_expiries_indices: list[ScanExpiry] = Field(default_factory=lambda: ["weekly", "monthly"])
    # The expiry window, same three names every other engine's Contracts section
    # uses. Permissive defaults: this adds a control, not a policy.
    expiry_dte_min: int = 0
    expiry_dte_max: int = 400
    avoid_expiry_day: bool = False
    w_short: int = Field(5, ge=2, le=60)
    w_long: int = Field(15, ge=3, le=120)
    stop_points: float = Field(80.0, gt=0)
    trail_points: float = Field(40.0, gt=0)
    profit_lock_activation_points: float = Field(50.0, gt=0)
    profit_lock_offset_points: float = Field(15.0, gt=0)
    persistence_bars: int = Field(3, ge=1, le=30)
    scalp_favorable_points: float = Field(5.0, gt=0)
    extended_favorable_points: float = Field(15.0, gt=0)
    intraday_favorable_points: float = Field(25.0, gt=0)
    tick_size: float = Field(1.0, gt=0)
    ib_minutes: int = Field(15, ge=5, le=60)
    drawdown_circuit_breaker_enabled: bool = True
    max_daily_drawdown_pct: float = Field(3.0, ge=0.5, le=10.0)

    @field_validator("scan_indices")
    @classmethod
    def _known_indices(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("select at least one index")
        unknown = [item for item in value if item not in INDEX_TO_TAPE]
        if unknown:
            raise ValueError(f"unknown scan_indices: {unknown}")
        return value

    @field_validator("strike_moneyness")
    @classmethod
    def _known_moneyness(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("select at least one strike")
        unknown = [item for item in value if item not in ALLOWED_MONEYNESS]
        if unknown:
            raise ValueError(f"unknown strike_moneyness: {unknown}")
        return value

    @field_validator("scan_expiries", "scan_expiries_indices")
    @classmethod
    def _known_expiries(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("select at least one expiry cycle")
        return value

    @model_validator(mode="after")
    def _sync_symbols(self) -> "AdaptiveEdgeSettings":
        if self.scan_indices:
            self.symbols = [INDEX_TO_TAPE[name] for name in self.scan_indices]
            self.symbol = self.symbols[0]
        elif self.symbols:
            self.symbol = self.symbols[0]
        if self.scan_expiries_indices:
            self.scan_expiries = list(self.scan_expiries_indices)
        return self


def _default_settings() -> AdaptiveEdgeSettings:
    return AdaptiveEdgeSettings()


def _load_settings() -> AdaptiveEdgeSettings:
    raw = db.get_config(CONFIG_KEY, "")
    if not raw:
        return _default_settings()
    try:
        return AdaptiveEdgeSettings.model_validate(json.loads(raw))
    except Exception:
        return _default_settings()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None



#: Legacy settings fields that map onto the real engine configuration. Anything
#: written here is mirrored into AdaptiveEdgeConfig, which is what the scanner
#: and runner actually read.
_MIRRORED_TO_ENGINE: dict[str, str] = {
    "enabled": "enabled",
    "scan_indices": "scan_indices",
    "scan_stocks": "scan_stocks",
    "scan_all_stocks": "scan_all_stocks",
    "scan_stock_contracts": "stock_contracts",
    "scan_expiries_indices": "scan_expiries_indices",
    "expiry_dte_min": "expiry_dte_min",
    "expiry_dte_max": "expiry_dte_max",
    "avoid_expiry_day": "avoid_expiry_day",
}

#: Fields this surface accepts and stores but which reach no engine. They belong
#: to an earlier moving-average scalper, not to the Master Specification strategy
#: this engine now implements. They are reported rather than quietly accepted,
#: because a setting that saves successfully and changes nothing is the worst of
#: both worlds — the operator believes they configured something.
_INERT_FIELDS: tuple[str, ...] = (
    "symbol", "symbols", "scan_source", "strike_moneyness", "scan_expiries",
    "w_short", "w_long", "stop_points", "trail_points",
    "profit_lock_activation_points", "profit_lock_offset_points",
    "persistence_bars", "scalp_favorable_points", "extended_favorable_points",
    "intraday_favorable_points", "tick_size", "ib_minutes",
    "drawdown_circuit_breaker_enabled", "max_daily_drawdown_pct",
)


def _mirror_into_engine_config(settings: "AdaptiveEdgeSettings") -> list[str]:
    """Push the mappable settings into the configuration the engine reads.

    Returns any problems as strings rather than raising: a legacy write that
    cannot be represented in the engine config must not 500 the settings page,
    but it must not silently vanish either.
    """
    from app.services.adaptive_edge import set_config
    payload: dict[str, Any] = {}
    for legacy, engine in _MIRRORED_TO_ENGINE.items():
        value = getattr(settings, legacy, None)
        if value is None:
            continue
        payload[engine] = list(value) if isinstance(value, (list, tuple)) else value
    if not payload:
        return []
    try:
        set_config(payload)
        return []
    except (ValueError, TypeError) as exc:
        return [str(exc)]


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    """Legacy settings surface, now backed by the real engine configuration.

    ``inert_fields`` is published so the UI can mark the controls that reach no
    engine. They were accepted and stored here long after the strategy they
    belonged to was replaced, which meant an operator could set a stop distance
    that nothing would ever read.
    """
    return {
        "settings": _load_settings().model_dump(),
        "live_trading": False,
        "inert_fields": list(_INERT_FIELDS),
        "engine_fields": sorted(_MIRRORED_TO_ENGINE),
    }


@router.put("/settings")
def put_settings(body: AdaptiveEdgeSettings) -> dict[str, Any]:
    if body.w_short >= body.w_long:
        raise HTTPException(400, "w_short must be < w_long")
    if not (
        body.scalp_favorable_points
        <= body.extended_favorable_points
        <= body.intraday_favorable_points
    ):
        raise HTTPException(400, "mode rungs must be non-decreasing")
    db.set_config(CONFIG_KEY, json.dumps(body.model_dump()))
    # Mirror the mappable fields into the configuration the scanner and runner
    # actually read. Without this the page saves successfully and the engine
    # keeps running on whatever it had.
    problems = _mirror_into_engine_config(body)
    return {
        "settings": body.model_dump(),
        "live_trading": False,
        "inert_fields": list(_INERT_FIELDS),
        "engine_fields": sorted(_MIRRORED_TO_ENGINE),
        "engine_config_errors": problems,
    }


@router.get("/snapshot")
def get_snapshot() -> dict[str, Any]:
    gate = evaluate_execution_gate()
    artifact = _load_json(ARTIFACT) or {}
    manifest = _load_json(MANIFEST) or {}
    locked = all(
        FORMULAS[f"F-{n:03d}"].status is FormulaStatus.LOCKED for n in range(101, 115)
    )
    return {
        "label": artifact.get("label", "RESEARCH_NOT_LIVE"),
        "software_complete": bool(artifact.get("software_complete") or manifest.get("software_complete")),
        "production_gate_authorized": bool(gate.authorized),
        "meets_a197": bool(artifact.get("coverage", {}).get("meets_a197")),
        "registry_locked": locked,
        "live_trading": False,
        "settings": _load_settings().model_dump(),
        "readiness": [
            {"name": item.name, "label": item.label or item.name, "ready": item.ready, "detail": item.detail}
            for item in production_readiness()
        ],
        "session": {
            "entries": artifact.get("entries"),
            "exits": artifact.get("exits"),
            "reentries": artifact.get("reentries"),
            "blocked_pyramid": artifact.get("blocked_pyramid"),
            "last_mode": artifact.get("last_mode"),
            "last_thesis": artifact.get("last_thesis"),
            "last_protection_stage": artifact.get("last_protection_stage"),
            "last_overlays": artifact.get("last_overlays") or [],
            "last_operating_mode": artifact.get("last_operating_mode"),
            "last_horizon": artifact.get("last_horizon"),
            "last_poc": artifact.get("last_poc"),
            "last_cvd": artifact.get("last_cvd"),
            "last_location": artifact.get("last_location"),
            "last_bar_delta": artifact.get("last_bar_delta"),
            "last_vwap": artifact.get("last_vwap"),
            "last_or_location": artifact.get("last_or_location"),
            "last_poc_migration": artifact.get("last_poc_migration"),
            "peak_pnl": artifact.get("peak_pnl"),
            "current_pnl": artifact.get("current_pnl"),
            "profit_giveback": artifact.get("profit_giveback"),
            "lifecycle_action": artifact.get("lifecycle_action"),
            "last_position_quantity": artifact.get("last_position_quantity"),
            "exit_fill_price": artifact.get("exit_fill_price"),
            "audit_stages": artifact.get("audit_stages") or [],
        },
        "legs": artifact.get("legs") or [],
        "signals": build_snapshot_signals(
            legs=artifact.get("legs") or [],
            session={
                "last_poc": artifact.get("last_poc"),
                "last_vwap": artifact.get("last_vwap"),
                "last_cvd": artifact.get("last_cvd"),
                "exit_fill_price": artifact.get("exit_fill_price"),
            },
            settings=_load_settings().model_dump(),
            spot_scans=load_live_spot_scans(),
        ),
        "daily": artifact.get("daily") or [],
        "quality": artifact.get("quality"),
        "holdout": artifact.get("holdout"),
        "coverage": artifact.get("coverage"),
        "walk_forward": artifact.get("walk_forward"),
        "mode_counts": artifact.get("mode_counts") or {},
        "mode_transitions": artifact.get("mode_transitions") or [],
        "formula_table": artifact.get("formula_table") or {},
        "incomplete_reasons": artifact.get("incomplete_reasons") or [],
    }
