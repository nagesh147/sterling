"""Listed-only F-109 selection. Empty chain and lookahead fail closed."""
from __future__ import annotations

import pytest

from app.engines.adaptive_edge.formula_registry import FORMULAS, FormulaStatus
from app.engines.adaptive_edge.instrument_selection import (
    InstrumentSelectionError,
    ListedOptionCandidate,
    select_listed_instrument,
)


DECISION = "2026-08-17T03:50:00+00:00"


def _cand(**overrides) -> ListedOptionCandidate:
    values = dict(
        instrument_id="NIFTY26AUG24500CE",
        option_type="CE",
        strike=24500.0,
        expiry="2026-08-27",
        expected_net_value=80.0,
        available_at="2026-08-17T03:49:00+00:00",
    )
    values.update(overrides)
    return ListedOptionCandidate(**values)


def test_empty_listed_universe_fails_closed():
    with pytest.raises(InstrumentSelectionError, match="empty_listed_universe"):
        select_listed_instrument((), decision_time=DECISION, option_type="CE")


def test_lookahead_listed_quote_fails_closed():
    with pytest.raises(InstrumentSelectionError, match="lookahead"):
        select_listed_instrument(
            [_cand(available_at="2026-08-17T03:51:00+00:00")],
            decision_time=DECISION,
            option_type="CE",
        )


def test_selects_argmax_expected_net_value_with_deterministic_tie_break():
    chosen = select_listed_instrument(
        (
            _cand(instrument_id="NIFTY26AUG24600CE", strike=24600.0, expected_net_value=50.0),
            _cand(instrument_id="NIFTY26AUG24400CE", strike=24400.0, expected_net_value=90.0),
            _cand(instrument_id="NIFTY26AUG24500CE", strike=24500.0, expected_net_value=90.0),
            _cand(instrument_id="NIFTY26AUG24500PE", option_type="PE", expected_net_value=120.0),
        ),
        decision_time=DECISION,
        option_type="CE",
    )
    assert chosen.instrument_id == "NIFTY26AUG24500CE"
    assert chosen.expected_net_value == 90.0


def test_illiquid_or_nonpositive_ev_is_not_selected():
    with pytest.raises(InstrumentSelectionError, match="no_eligible"):
        select_listed_instrument(
            (
                _cand(liquidity_ok=False, expected_net_value=200.0),
                _cand(instrument_id="NIFTY26AUG24600CE", expected_net_value=0.0),
            ),
            decision_time=DECISION,
            option_type="CE",
        )


def test_f109_stays_locked():
    assert FORMULAS["F-109"].status is FormulaStatus.LOCKED
