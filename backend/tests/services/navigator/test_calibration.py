"""Tests for Navigator calibration scoring and the §19.5 promotion gate.

The properties that actually matter here are safety properties, so they get
the most direct tests: no lookahead, no crediting an undecided call, no
session straddling the train/eval boundary, and — above all — nothing in
this module ever promoting anything by itself.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from app.engines.navigator.schemas import NavigatorConfigModel
from app.services import db
from app.services.navigator import calibration, config_store, repository
from app.services.navigator.calendar import IST
from app.services.navigator.repository import RevisionConflict

_UNDERLYINGS = ["NIFTY 50"]
_HOUR_MS = 3_600_000


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    yield
    os.unlink(path)


def _ms(day: int, hour: int = 10) -> int:
    """A bar close on a given day of Jan 2026, in IST."""
    return int(datetime(2026, 1, day, hour, 15, tzinfo=IST).timestamp() * 1000)


def _decision(bar_close_ms: int, *, status="CONFIRMED", direction="long",
              underlying="NIFTY 50", decision_id=None) -> dict:
    return {
        "decision_id": decision_id or f"d{bar_close_ms}_{direction}_{status}",
        "underlying": underlying, "bar_close_ms": bar_close_ms, "status": status,
        "direction": direction,
    }


def _rising_series(start_ms: int, n: int, *, start=100.0, step=1.0, underlying="NIFTY 50"):
    return {underlying: [
        calibration.PricePoint(bar_close_ms=start_ms + i * _HOUR_MS, close=start + i * step)
        for i in range(n)
    ]}


class TestNoLookahead:
    def test_a_decision_without_enough_forward_bars_is_unscored_not_wrong(self):
        """The last few decisions in any real sample have no verdict yet.
        Counting them as misses would make every fresh report look worse
        than reality; counting them as hits would be worse still."""
        series = _rising_series(_ms(5), 4)  # only 4 bars exist
        decisions = [_decision(_ms(5) + 2 * _HOUR_MS)]  # needs 6 bars ahead
        report = calibration.score_decisions(decisions, series, horizon_bars=6)
        window = report["calibration"]
        assert window["actionable"] == 1
        assert window["actionable_scored"] == 0
        assert window["unscorable"] == 1
        assert window["hit_rate"] is None

    def test_scoring_uses_only_bars_after_the_decision_bar(self):
        """Entry is the decision's own bar; exit is exactly horizon bars
        later. A price spike BEFORE the decision must not affect the score."""
        pts = [calibration.PricePoint(bar_close_ms=_ms(5) + i * _HOUR_MS, close=c)
               for i, c in enumerate([999.0, 100.0, 101.0, 102.0])]
        report = calibration.score_decisions(
            [_decision(_ms(5) + _HOUR_MS)], {"NIFTY 50": pts}, horizon_bars=2,
        )
        # entry 100 -> exit 102 = +2%, unaffected by the 999 bar before it
        assert report["calibration"]["mean_return_pct"] == pytest.approx(2.0)

    def test_a_decision_whose_bar_is_missing_from_the_series_is_unscored(self):
        report = calibration.score_decisions(
            [_decision(_ms(9) + 37)], _rising_series(_ms(5), 20), horizon_bars=2,
        )
        assert report["calibration"]["unscorable"] == 1


class TestDirectionality:
    def test_a_short_call_is_right_when_price_falls(self):
        falling = {"NIFTY 50": [
            calibration.PricePoint(bar_close_ms=_ms(5) + i * _HOUR_MS, close=100.0 - i)
            for i in range(10)
        ]}
        report = calibration.score_decisions(
            [_decision(_ms(5), direction="short")], falling, horizon_bars=4,
        )
        w = report["calibration"]
        assert w["actionable_hits"] == 1
        assert w["mean_return_pct"] > 0  # scored in the direction taken

    def test_a_long_call_is_wrong_when_price_falls(self):
        falling = {"NIFTY 50": [
            calibration.PricePoint(bar_close_ms=_ms(5) + i * _HOUR_MS, close=100.0 - i)
            for i in range(10)
        ]}
        report = calibration.score_decisions(
            [_decision(_ms(5), direction="long")], falling, horizon_bars=4,
        )
        assert report["calibration"]["actionable_hits"] == 0
        assert report["calibration"]["mean_return_pct"] < 0


class TestAbstentionsAreNotFailures:
    @pytest.mark.parametrize("status", ["WAIT", "CONFLICT", "WATCH"])
    def test_standing_aside_is_never_scored_as_a_wrong_call(self, status):
        """Abstaining is the gate doing its job — it must not drag the hit
        rate down, or the metric would punish the safest behaviour."""
        report = calibration.score_decisions(
            [_decision(_ms(5), status=status)], _rising_series(_ms(5), 20),
        )
        w = report["calibration"]
        assert w["total_decisions"] == 1
        assert w["actionable"] == 0
        assert w["hit_rate"] is None

    def test_no_data_is_counted_separately_as_a_data_quality_signal(self):
        report = calibration.score_decisions(
            [_decision(_ms(5), status="NO_DATA"), _decision(_ms(5, 11), status="CONFIRMED")],
            _rising_series(_ms(5), 20),
        )
        w = report["calibration"]
        assert w["no_data"] == 1
        assert w["no_data_rate"] == pytest.approx(0.5)


class TestChronologicalSplit:
    def test_no_session_straddles_the_train_eval_boundary(self):
        """A day that contributed to tuning must not also appear in the
        supposedly-untouched evaluation window."""
        decisions = [
            _decision(_ms(day, hour), decision_id=f"d{day}-{hour}")
            for day in range(5, 15) for hour in (10, 11, 12)
        ]
        report = calibration.score_decisions(decisions, _rising_series(_ms(5), 500))
        cal_days = set(report["calibration"]["session_dates"])
        ev_days = set(report["evaluation"]["session_dates"])
        assert cal_days and ev_days
        assert not (cal_days & ev_days), "a session appeared in both windows"

    def test_evaluation_window_is_chronologically_after_calibration(self):
        decisions = [_decision(_ms(day)) for day in range(5, 15)]
        report = calibration.score_decisions(decisions, _rising_series(_ms(5), 500))
        assert report["calibration"]["last_bar_close_ms"] < report["evaluation"]["first_bar_close_ms"]

    def test_a_single_session_stays_wholly_in_calibration(self):
        """With only one day there is no honest out-of-sample window, so the
        evaluation side must come back empty rather than fabricated."""
        decisions = [_decision(_ms(5, h)) for h in (10, 11, 12)]
        report = calibration.score_decisions(decisions, _rising_series(_ms(5), 50))
        assert report["calibration"]["total_decisions"] == 3
        assert report["evaluation"]["total_decisions"] == 0


class TestPromotionCriteria:
    def test_a_fresh_empty_history_is_not_eligible(self):
        verdict = calibration.evaluate_criteria(calibration.score_decisions([], {}))
        assert verdict["eligible"] is False
        assert all(not c["passed"] for c in verdict["criteria"])

    def test_criteria_report_progress_rather_than_a_bare_no(self):
        """The UI needs "12 of 20 sessions", not just a red cross."""
        decisions = [_decision(_ms(day)) for day in range(5, 12)]
        verdict = calibration.evaluate_criteria(
            calibration.score_decisions(decisions, _rising_series(_ms(5), 500)))
        sessions = next(c for c in verdict["criteria"] if c["key"] == "min_sessions")
        assert "of 20 sessions" in sessions["detail"]

    def test_a_thin_sample_never_reads_as_eligible_however_good_it_looks(self):
        """Three perfect calls is not evidence. Sample-size criteria must
        veto even a 100% hit rate."""
        decisions = [_decision(_ms(day)) for day in (5, 6, 7)]
        report = calibration.score_decisions(decisions, _rising_series(_ms(5), 500))
        verdict = calibration.evaluate_criteria(report)
        assert verdict["eligible"] is False
        assert not next(c for c in verdict["criteria"] if c["key"] == "min_sessions")["passed"]

    def test_losing_out_of_sample_expectancy_blocks_promotion(self):
        falling = {"NIFTY 50": [
            calibration.PricePoint(bar_close_ms=_ms(5) + i * _HOUR_MS, close=1000.0 - i)
            for i in range(2000)
        ]}
        decisions = [
            _decision(_ms(day, hour), decision_id=f"d{day}-{hour}")
            for day in range(1, 29) for hour in (10, 11, 12)
        ]
        verdict = calibration.evaluate_criteria(calibration.score_decisions(decisions, falling))
        expectancy = next(c for c in verdict["criteria"] if c["key"] == "evaluation_expectancy")
        assert expectancy["passed"] is False
        assert verdict["eligible"] is False

    def test_the_report_states_that_costs_are_not_modelled(self):
        """Expectancy here is gross. Saying so in the artifact keeps a future
        reader from mistaking it for a net result."""
        report = calibration.score_decisions([], {})
        assert any("gross" in c for c in report["caveats"])


class TestCalibrationStateArtifact:
    def test_state_is_deterministic_for_identical_inputs(self):
        report = calibration.score_decisions(
            [_decision(_ms(5))], _rising_series(_ms(5), 20))
        criteria = calibration.evaluate_criteria(report)
        a = calibration.build_calibration_state("u1", report, criteria, now_ms=1)
        b = calibration.build_calibration_state("u1", report, criteria, now_ms=2)
        assert a["report_id"] == b["report_id"] == a["report_id"]
        assert a["artifact_hash"] == b["artifact_hash"]

    def test_state_never_claims_promoted(self):
        """`promotion_state` records what the EVIDENCE supports. Only the
        explicit human action may record an actual promotion."""
        report = calibration.score_decisions([], {})
        state = calibration.build_calibration_state(
            "u1", report, calibration.evaluate_criteria(report))
        assert state["promotion_state"] == "not_eligible"
        assert state["promotion_state"] != "promoted"

    def test_state_round_trips_through_the_repository(self):
        report = calibration.score_decisions(
            [_decision(_ms(5))], _rising_series(_ms(5), 20))
        state = calibration.build_calibration_state(
            "u1", report, calibration.evaluate_criteria(report))
        repository.insert_calibration_state(state)
        stored = repository.fetch_latest_calibration_state("u1")
        assert stored["report_id"] == state["report_id"]
        assert stored["promotion_state"] == state["promotion_state"]


class TestPromotionIsExplicitOnly:
    def _rec(self):
        return config_store.get("user-1", default_underlyings=_UNDERLYINGS)

    def test_generating_evidence_never_flips_readiness(self):
        """The core safety property: scoring, evaluating, and even STORING a
        fully-eligible report must leave the gate shut."""
        report = calibration.score_decisions(
            [_decision(_ms(5))], _rising_series(_ms(5), 20))
        state = calibration.build_calibration_state(
            "user-1", report, calibration.evaluate_criteria(report))
        repository.insert_calibration_state(state)
        assert self._rec().calibration_readiness == "not_ready"

    def test_an_ordinary_save_cannot_promote(self):
        rec = self._rec()
        saved = config_store.save(
            "user-1", rec.config.model_copy(update={"enabled": True}),
            expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)
        assert saved.calibration_readiness == "not_ready"

    def test_promote_sets_readiness_and_records_the_report_id(self):
        rec = self._rec()
        promoted = config_store.promote_calibration(
            "user-1", report_id="navcal_abc", expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS)
        assert promoted.calibration_readiness == "ready"
        assert promoted.calibration_report_id == "navcal_abc"

    def test_promote_leaves_the_editable_config_untouched(self):
        """Promotion is metadata. It must not quietly change a setting —
        least of all the operating mode or auto-execute (§19.5)."""
        rec = self._rec()
        before = rec.config.model_dump(mode="json")
        promoted = config_store.promote_calibration(
            "user-1", report_id="navcal_abc", expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS)
        assert promoted.config.model_dump(mode="json") == before
        assert promoted.config.operating_mode != "gate"
        assert promoted.config.auto_execute_originated is False

    def test_promote_is_revision_checked(self):
        self._rec()
        with pytest.raises(RevisionConflict):
            config_store.promote_calibration(
                "user-1", report_id="navcal_abc", expected_revision=999,
                default_underlyings=_UNDERLYINGS)

    def test_a_later_save_keeps_the_promotion(self):
        rec = self._rec()
        promoted = config_store.promote_calibration(
            "user-1", report_id="navcal_abc", expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS)
        saved = config_store.save(
            "user-1", promoted.config.model_copy(update={"enabled": True}),
            expected_revision=promoted.revision, default_underlyings=_UNDERLYINGS)
        assert saved.calibration_readiness == "ready"
        assert saved.calibration_report_id == "navcal_abc"

    def test_reset_to_defaults_keeps_the_promotion(self):
        """Resetting SETTINGS shouldn't silently discard reviewed evidence —
        nor silently re-promote. It carries readiness through untouched."""
        rec = self._rec()
        promoted = config_store.promote_calibration(
            "user-1", report_id="navcal_abc", expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS)
        after = config_store.reset("user-1", default_underlyings=_UNDERLYINGS)
        assert after.calibration_readiness == "ready"
        assert after.config.enabled is False

    def test_demote_reverts_readiness_and_drops_gate_mode(self):
        """A gate that can no longer be satisfied would block every order in
        silence — demotion must visibly fall back to advisory."""
        rec = self._rec()
        promoted = config_store.promote_calibration(
            "user-1", report_id="navcal_abc", expected_revision=rec.revision,
            default_underlyings=_UNDERLYINGS)
        gated = config_store.save(
            "user-1", promoted.config.model_copy(update={"enabled": True, "operating_mode": "gate"}),
            expected_revision=promoted.revision, default_underlyings=_UNDERLYINGS)
        assert gated.config.operating_mode == "gate"

        demoted = config_store.demote_calibration(
            "user-1", expected_revision=gated.revision, default_underlyings=_UNDERLYINGS)
        assert demoted.calibration_readiness == "not_ready"
        assert demoted.calibration_report_id is None
        assert demoted.config.operating_mode == "advisory"
