import pytest

from backend.app.engines.adaptive_edge.statistical_uncertainty import (
    DependenceClass,
    DependenceUnit,
    StatisticalUncertaintyError,
    UncertaintyEvidence,
    UncertaintySpecification,
)


def unit(unit_id="u1", dependence=DependenceClass.SERIAL):
    return DependenceUnit(
        unit_id=unit_id,
        cycle_id="cycle-1",
        episode_id="episode-1",
        start_time="2026-01-01T09:15:00+05:30",
        end_time="2026-01-01T09:30:00+05:30",
        dependence_class=dependence,
    )


def test_unknown_dependence_cannot_be_treated_as_iid():
    evidence = UncertaintyEvidence.build("eval-1", "fp-1", [unit(dependence=DependenceClass.UNKNOWN)])
    assert evidence.iid_justified is False
    with pytest.raises(StatisticalUncertaintyError, match="known dependence"):
        evidence.attach_specification(
            UncertaintySpecification("iid-method", DependenceClass.UNKNOWN, "", "1")
        )


def test_duplicate_dependence_units_are_rejected():
    with pytest.raises(StatisticalUncertaintyError, match="duplicate"):
        UncertaintyEvidence.build("eval-1", "fp-1", [unit(), unit()])


def test_iid_requires_every_unit_to_be_explicitly_justified():
    evidence = UncertaintyEvidence.build(
        "eval-1", "fp-1", [unit("u1", DependenceClass.IID_JUSTIFIED), unit("u2", DependenceClass.IID_JUSTIFIED)]
    )
    assert evidence.iid_justified is True


def test_mixed_dependence_cannot_be_labeled_iid():
    evidence = UncertaintyEvidence.build(
        "eval-1", "fp-1", [unit("u1", DependenceClass.IID_JUSTIFIED), unit("u2", DependenceClass.SERIAL)]
    )
    assert evidence.iid_justified is False


def test_uncertainty_method_must_match_observed_dependence_class():
    evidence = UncertaintyEvidence.build("eval-1", "fp-1", [unit()])
    spec = UncertaintySpecification("serial-method", DependenceClass.SERIAL, "predefined dependence model", "1")
    assert evidence.attach_specification(spec).specification == spec

    wrong = UncertaintySpecification("iid-method", DependenceClass.IID_JUSTIFIED, "claimed IID", "1")
    with pytest.raises(StatisticalUncertaintyError, match="does not match"):
        evidence.attach_specification(wrong)


def test_temporal_order_is_required():
    with pytest.raises(StatisticalUncertaintyError, match="end_time"):
        DependenceUnit(
            unit_id="u1", cycle_id="c1", episode_id="e1",
            start_time="2026-01-02T09:30:00+05:30",
            end_time="2026-01-01T09:30:00+05:30",
            dependence_class=DependenceClass.SERIAL,
        )
