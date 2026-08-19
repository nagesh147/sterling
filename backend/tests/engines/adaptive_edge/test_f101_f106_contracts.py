from __future__ import annotations

import pytest

from app.engines.adaptive_edge.f101_f106_contracts import (
    F101NormalizedState, F102ProbabilityState, F103Eligibility,
    F104HorizonState, F105Economics, F106OptionCandidate,
    ResearchContractError, select_f106_candidate,
)


def test_f101_rejects_lookahead_and_missing_quality():
    with pytest.raises(ResearchContractError):
        F101NormalizedState({"vwap": 100.0}, True, "2026-08-19T10:01:00Z", "2026-08-19T10:00:00Z")
    with pytest.raises(ResearchContractError):
        F101NormalizedState({"vwap": 100.0}, False, "2026-08-19T10:00:00Z", "2026-08-19T10:00:00Z")


def test_f102_requires_normalized_probability_distribution():
    F102ProbabilityState(.5, .3, .2)
    with pytest.raises(ResearchContractError):
        F102ProbabilityState(.6, .3, .2)


def test_f103_requires_explicit_reason_and_quality_for_admission():
    F103Eligibility(True, "directional_edge", .2, True)
    with pytest.raises(ResearchContractError):
        F103Eligibility(True, "directional_edge", .2, False)


def test_f104_requires_valid_distribution_and_selected_member():
    F104HorizonState({"MICRO": .5, "SCALP": .5}, "MICRO")
    with pytest.raises(ResearchContractError):
        F104HorizonState({"MICRO": 1.0}, "INTRADAY")


def test_f105_missing_gross_fails_closed():
    economics = F105Economics(None, 2.0, None, 0.0)
    assert economics.eligible is False
    with pytest.raises(ResearchContractError):
        F105Economics(10.0, 2.0, None, 0.0)


def test_f106_selects_best_eligible_candidate_only():
    candidates = (
        F106OptionCandidate("OTM", 20.0, True, True, True, True),
        F106OptionCandidate("ATM", 30.0, False, True, True, True),
        F106OptionCandidate("ITM", 18.0, True, True, True, True),
    )
    assert select_f106_candidate(candidates).instrument_id == "OTM"
    assert select_f106_candidate((F106OptionCandidate("ATM", 10.0, False, True, True, True),)) is None
