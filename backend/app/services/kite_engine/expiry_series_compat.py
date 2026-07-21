"""Backward-compatible behavior for exact expiry-series integration.

The expiry fix must not silently broaden an existing user's selected strike ladder.
Deep ITM through far OTM remain supported choices, but the established default
ITM1/ATM/OTM1 selection is preserved unless the user changes it.

Fresh signals resolve their candidate ladder from the trigger-bar spot. Retained
historical signals use the latest underlying close so their displayed contracts remain
relevant. This prevents a same-scan latest close from shifting and de-duplicating a
fresh signal's OTM1 leg.
"""
from __future__ import annotations

from functools import wraps

from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine import expiry_series_runtime as runtime

_EXISTING_STRIKE_DEFAULT = ["ITM1", "ATM", "OTM1"]
_original_normalise = runtime._normalise_engine_config
_original_resolve_option_legs = runtime.resolve_option_legs


def _normalise_without_strike_migration(cfg: EngineConfigModel) -> EngineConfigModel:
    selected = list(cfg.strike_moneyness or _EXISTING_STRIKE_DEFAULT)
    normalised = _original_normalise(cfg)
    return normalised.model_copy(update={"strike_moneyness": selected})


@wraps(_original_resolve_option_legs)
def _resolve_with_fresh_trigger_spot(row, option_rows, **kwargs):
    if getattr(row, "is_fresh", False):
        kwargs["latest_spot"] = None
    return _original_resolve_option_legs(row, option_rows, **kwargs)


def install() -> None:
    runtime._normalise_engine_config = _normalise_without_strike_migration
    runtime.resolve_option_legs = _resolve_with_fresh_trigger_spot
    EngineConfigModel.__pydantic_fields__["strike_moneyness"].default = list(
        _EXISTING_STRIKE_DEFAULT
    )
    EngineConfigModel.model_rebuild(force=True)
