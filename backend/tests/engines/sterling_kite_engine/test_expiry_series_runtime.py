"""Integration coverage for exact listed-expiry runtime wiring."""
from datetime import date

from app.engines.sterling_kite_engine.schemas import (
    AlignmentChip,
    EngineConfigModel,
    EngineSignalRow,
)
from app.services.kite_engine.expiry_series_runtime import (
    _normalise_engine_config,
    _series_maps,
    resolve_option_legs,
)


def _signal(*, spot: float = 100.0) -> EngineSignalRow:
    return EngineSignalRow(
        underlying="NIFTY 50",
        token=1,
        exchange="NFO",
        regime="BULL",
        alignment=AlignmentChip(fast=1, mid=1, slow=1),
        direction="long",
        option_type="CE",
        spot=spot,
        stop_loss=90.0,
        score=85.0,
        timestamp_ms=123,
    )


def _instrument(expiry: str, strike: int, token: int) -> dict:
    return {
        "name": "NIFTY",
        "tradingsymbol": f"NIFTY{expiry.replace('-', '')}{strike}CE",
        "instrument_type": "CE",
        "strike": strike,
        "expiry": expiry,
        "instrument_token": token,
        "lot_size": 75,
    }


def test_runtime_config_defaults_are_category_specific():
    cfg = _normalise_engine_config(EngineConfigModel())
    assert cfg.scan_expiries_indices == ["weekly", "monthly"]
    assert cfg.scan_expiries_stocks == ["monthly"]
    assert cfg.scan_weekly_series_indices == [0, 1, 2, 3]
    assert cfg.scan_monthly_series_indices == [0, 1]
    assert "scan_weekly_series_stocks" not in cfg.model_dump()
    assert cfg.scan_monthly_series_stocks == [0, 1]
    # The expiry integration must not silently broaden an existing user's strike
    # selection. Deep ITM through far OTM remain available in the schema/UI.
    assert cfg.strike_moneyness == ["ITM1", "ATM", "OTM1"]


def test_model_and_runtime_normalise_stocks_to_monthly_only():
    cfg = EngineConfigModel(scan_expiries_stocks=["weekly", "monthly"])
    assert cfg.scan_expiries_stocks == ["monthly"]

    normalised = _normalise_engine_config(cfg)
    assert normalised.scan_expiries_stocks == ["monthly"]
    _, stock_series = _series_maps(normalised)
    assert stock_series == {"weekly": [], "monthly": [0, 1]}


def test_resolve_option_legs_uses_selected_listed_series_and_latest_spot():
    # Listed dates only. July 28 is July monthly; August 4/11/18 are weekly;
    # August 25 is August monthly. No weekday is calculated by the resolver.
    rows = []
    token = 1000
    for expiry in (
        "2026-07-21",
        "2026-07-28",
        "2026-08-04",
        "2026-08-11",
        "2026-08-18",
        "2026-08-25",
    ):
        for strike in (90, 100, 110, 120):
            token += 1
            rows.append(_instrument(expiry, strike, token))

    legs, reason = resolve_option_legs(
        _signal(spot=100.0),
        rows,
        option_name="NIFTY",
        moneynesses=["ATM"],
        today=date(2026, 7, 1),
        expiry_types=["weekly", "monthly"],
        expiry_ranks_by_type={"weekly": [0, 1, 2, 3], "monthly": [0, 1]},
        latest_spot=118.0,
    )

    assert reason is None
    assert {leg.expiry for leg in legs} == {
        "2026-07-21",
        "2026-07-28",
        "2026-08-04",
        "2026-08-11",
        "2026-08-18",
        "2026-08-25",
    }
    # The retained row's trigger spot was 100, but current spot is 118; ATM must
    # therefore resolve to the listed 120 strike, not the historical 100 strike.
    assert {leg.strike for leg in legs} == {120.0}


def test_resolution_reason_is_precise_not_a_liquidity_claim():
    legs, reason = resolve_option_legs(
        _signal(),
        [],
        option_name="NIFTY",
        moneynesses=["ATM"],
        today=date(2026, 7, 1),
        expiry_types=["weekly"],
        expiry_ranks_by_type={"weekly": [0]},
    )
    assert legs == []
    assert reason == "No listed option-chain rows were found for NIFTY."
    assert "liquid" not in reason.lower()
