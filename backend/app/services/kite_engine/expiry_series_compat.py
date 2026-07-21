"""Backward-compatible defaults for the exact expiry-series integration.

The expiry fix must not silently broaden an existing user's selected strike ladder.
Deep ITM through far OTM remain supported choices, but the established default
ITM1/ATM/OTM1 selection is preserved unless the user changes it.
"""
from __future__ import annotations

from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine import expiry_series_runtime as runtime

_EXISTING_STRIKE_DEFAULT = ["ITM1", "ATM", "OTM1"]
_original_normalise = runtime._normalise_engine_config


def _normalise_without_strike_migration(cfg: EngineConfigModel) -> EngineConfigModel:
    selected = list(cfg.strike_moneyness or _EXISTING_STRIKE_DEFAULT)
    normalised = _original_normalise(cfg)
    return normalised.model_copy(update={"strike_moneyness": selected})


def install() -> None:
    runtime._normalise_engine_config = _normalise_without_strike_migration
    EngineConfigModel.__pydantic_fields__["strike_moneyness"].default = list(
        _EXISTING_STRIKE_DEFAULT
    )
    EngineConfigModel.model_rebuild(force=True)
