"""Backward-compatible behavior for exact expiry-series integration.

The expiry fix must not silently broaden an existing user's selected strike ladder.
Deep ITM through far OTM remain supported choices, but the established default
ITM1/ATM/OTM1 selection is preserved unless the user changes it.

Moneyness ranks are anchored to the nearest listed ATM strike. ITM1 and OTM1 are
therefore the first distinct strikes on either side of ATM, rather than potentially
collapsing onto the ATM contract when spot lies between listed strikes.
"""
from __future__ import annotations

from functools import wraps

from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine import expiry_series_runtime as runtime
from app.services.kite_engine import strikes as strikes_mod

_EXISTING_STRIKE_DEFAULT = ["ITM1", "ATM", "OTM1"]
_original_normalise = runtime._normalise_engine_config
_original_resolve_option_legs = runtime.resolve_option_legs


def _normalise_without_strike_migration(cfg: EngineConfigModel) -> EngineConfigModel:
    selected = list(cfg.strike_moneyness or _EXISTING_STRIKE_DEFAULT)
    normalised = _original_normalise(cfg)
    return normalised.model_copy(update={"strike_moneyness": selected})


def _select_distinct_from_atm(rows, *, spot: float, want_call: bool, moneyness: str):
    ordered = sorted(rows, key=lambda row: float(row["strike"]))
    if not ordered:
        return None
    atm_index = min(
        range(len(ordered)),
        key=lambda index: abs(float(ordered[index]["strike"]) - spot),
    )
    if moneyness == "ATM":
        return ordered[atm_index]

    depth = int(strikes_mod._DEPTH[moneyness])
    is_itm = moneyness.startswith("ITM")
    # Calls: ITM lower / OTM higher. Puts: ITM higher / OTM lower.
    move_higher = is_itm != want_call
    if move_higher:
        if atm_index >= len(ordered) - 1:
            return None
        return ordered[min(len(ordered) - 1, atm_index + depth)]
    if atm_index <= 0:
        return None
    return ordered[max(0, atm_index - depth)]


@wraps(_original_resolve_option_legs)
def _resolve_with_fresh_trigger_spot(row, option_rows, **kwargs):
    """Fresh rows resolve their ladder at the TRIGGER spot; retained rows at today's.

    UNRESOLVED CONFLICT (audit lead 7, 2026-08-04 — left deliberately, see
    docs/kite_signal_audit_2026-08-04.md). Two decisions were each made on purpose and
    point opposite ways:

      * a RETAINED row resolves its ladder at today's spot, so its candidate strikes
        are ones you could actually trade now — pinned by
        `test_resolve_option_legs_uses_selected_listed_series_and_latest_spot`;
      * `_stamp_spot_leg_premiums` stamps each leg's entry premium from the SIGNAL
        bar, because "today's LTP is not what a signal from three sessions ago entered
        at, and stamping it would invent an entry price and a fake P&L".

    Together they describe different trades: a NIFTY long triggered at 24,000 with
    spot now 25,100 gets a leg labelled ATM 25100 priced at what that strike closed at
    when it was 1,100 points OTM. Each half is defensible; the PAIR is not, and which
    one gives way is a product decision (coherent history vs. a tradeable-now roll
    priced at today's LTP) rather than something to settle in a compat shim.
    """
    if getattr(row, "is_fresh", False):
        kwargs["latest_spot"] = None
    return _original_resolve_option_legs(row, option_rows, **kwargs)


def install() -> None:
    runtime._normalise_engine_config = _normalise_without_strike_migration
    runtime.resolve_option_legs = _resolve_with_fresh_trigger_spot
    strikes_mod._select_row = _select_distinct_from_atm
    EngineConfigModel.__pydantic_fields__["strike_moneyness"].default = list(
        _EXISTING_STRIKE_DEFAULT
    )
    EngineConfigModel.model_rebuild(force=True)
