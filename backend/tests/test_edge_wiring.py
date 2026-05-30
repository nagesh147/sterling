"""Edge feed wiring: derivatives profiles, source labelling, decide_both path."""
from __future__ import annotations

import pytest

from app.engines.derivatives.profiles import get_profile
from app.engines.derivatives.schemas import (
    InstrumentBias,
    MarketContext,
    SignalContext,
)
from app.engines.derivatives.selector import decide_both


# --- edge derivatives profiles ------------------------------------------

@pytest.mark.parametrize("strat", ["ma_crossover", "mean_reversion", "breakout",
                                   "price_action", "smc"])
def test_edge_profile_enabled_but_not_auto(strat):
    p = get_profile(f"edge/{strat}")
    assert p.enabled is True                      # candidates display
    assert p.auto_execute_futures is False        # but never auto-fire
    assert p.auto_execute_options is False
    assert p.instrument_bias == InstrumentBias.AUTO


# --- source labelling ----------------------------------------------------

def test_signal_source_helper():
    from app.api.v1.endpoints.derivatives import _signal_source
    assert _signal_source("edge/ma_crossover") == "edge"
    assert _signal_source("scalping/price_action") == "engine"
    assert _signal_source("triple_st") == "engine"


def test_candidate_row_has_source_field():
    from app.api.v1.endpoints.derivatives import _CandidateRow
    assert "source" in _CandidateRow.model_fields


# --- decide_both produces a futures leg for an edge signal ---------------

def _edge_signal(atr=3.0, entry=115.0):
    return SignalContext(
        strategy="edge/breakout",
        underlying="BTCUSD",
        direction="long",
        entry=entry,
        stop_loss=entry - 2.0 * atr,
        take_profit=entry + 3.5 * atr,
        atr=atr,
        rr_target=1.75,
        signal_score=82.0,
        signal_strength="STRONG",
        expected_hold_minutes=2880,
        mode_name="swing",
        presized=True,            # edge SL/TP are backtest-validated → no re-cushion
    )


def test_solve_futures_passthrough_keeps_validated_levels():
    """A pre-validated swing stop (~5.9% of entry, wider than the 3% scalping
    cap) must pass through unchanged so the live trade matches the backtest."""
    from app.engines.derivatives.sl_tp_solver import solve_futures
    res = solve_futures(direction="long", entry=115.0, structure_stop=109.0,
                        atr_val=3.0, take_profit=125.5, rr=1.75, validated=True)
    assert res.ok
    assert res.stop_loss == 109.0          # untouched, no cushion
    assert res.take_profit == 125.5


def test_solve_futures_passthrough_rejects_wrong_side_stop():
    from app.engines.derivatives.sl_tp_solver import solve_futures
    # long with stop ABOVE entry is incoherent → reject even in passthrough
    res = solve_futures(direction="long", entry=115.0, structure_stop=120.0,
                        atr_val=3.0, take_profit=125.5, rr=1.75, validated=True)
    assert not res.ok


def test_decide_both_emits_futures_for_edge_signal():
    sig = _edge_signal()
    market = MarketContext(spot=115.0, underlying="BTCUSD")
    dual = decide_both(signal=sig, market=market, chain=None)
    assert dual.futures is not None
    assert dual.futures.status.value == "ok"
    assert dual.futures.chosen is not None
    assert dual.futures.chosen.instrument_type == "futures"
