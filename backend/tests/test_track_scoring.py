"""
Tests for track_scoring — compute_ensemble_signal with edge-weighted voting,
max-score selection, linear_agree boost, and composite_vote strength.
"""
import pytest

from app.engines.directional.tracks.base import TrackSignal
from app.schemas.directional import SignalResult


def _make_ts(track: str, score: float, trend_dir: int, strength: str = "SIGNAL") -> TrackSignal:
    return TrackSignal(
        track=track,
        trend_dir=trend_dir,
        score=score,
        strength=strength,
        reason=f"{track} test",
        signal=SignalResult(
            trend=trend_dir,
            all_green=False, all_red=False,
            green_arrow=False, red_arrow=False,
            st_trends=[0, 0, 0], st_values=[0.0, 0.0, 0.0],
            close_1h=50000.0, score_long=0.0, score_short=0.0,
        ),
        features={},
    )


class TestComputeEnsembleSignal:
    def test_single_track_returns_direction(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        candidates = [_make_ts("trend_following", 12.0, 1)]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.direction == 1
        assert result.strength == "SIGNAL"  # score 12 < 14, so SIGNAL
        assert len(result.tracks) == 1

    def test_edge_vote_by_direction(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        # VCP (edge=1.8×0.45=0.81 for long) vs TF (edge=1.4×0.58=0.81)
        # Both positive, direction = +1
        candidates = [
            _make_ts("vcp", 10.0, 1),
            _make_ts("trend_following", 10.0, 1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.direction == 1
        assert result.agreement_count == 2

    def test_edge_vote_opposing_directions(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        # MR short edge in bull_trend = 1.5×0.65=0.975 (strong short)
        # TF long edge = 1.4×0.58=0.812 (moderate long)
        # Direction should be -1 (MR edge > TF edge)
        candidates = [
            _make_ts("trend_following", 12.0, 1),
            _make_ts("mean_reversion", 10.0, -1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.direction == -1
        assert result.agreement_count == 1

    def test_max_score_selection(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        # VCP score=15 (max), TF score=8, MR score=6 — all +1, 3 agreeing → 30% boost
        # → composite = 15 * 1.30 = 19.5
        candidates = [
            _make_ts("vcp", 15.0, 1),
            _make_ts("trend_following", 8.0, 1),
            _make_ts("mean_reversion", 6.0, 1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.composite_score == 19.5
        assert result.agreement_count == 3
        assert result.strength == "STRONG"

    def test_linear_agree_boost_2_tracks(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        candidates = [
            _make_ts("vcp", 10.0, 1),
            _make_ts("trend_following", 10.0, 1),
            _make_ts("mean_reversion", 8.0, -1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        # 2 agreeing (+1) → 15% boost → 10 * 1.15 = 11.5
        assert result.composite_score == 11.5
        assert result.agreement_count == 2

    def test_linear_agree_boost_3_tracks(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        candidates = [
            _make_ts("vcp", 10.0, 1),
            _make_ts("trend_following", 10.0, 1),
            _make_ts("mean_reversion", 10.0, 1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        # 3 agreeing → 30% boost → 10 * 1.30 = 13.0
        assert result.composite_score == 13.0
        assert result.agreement_count == 3

    def test_strong_signal_with_high_score_and_2_agree(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        # VCP at 15 (≥14 threshold) + 2 agreeing → STRONG
        candidates = [
            _make_ts("vcp", 15.0, 1),
            _make_ts("trend_following", 12.0, 1),
            _make_ts("mean_reversion", 8.0, -1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.strength == "STRONG"
        assert result.agreement_count == 2

    def test_strong_signal_demoted_without_2_agree(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        # VCP fires +1 but TF (edge 0.812) + MR (edge 0.975) combined beat VCP → direction=-1
        # Agreement: TF and MR agree on -1 (2 agreeing) but the MAX SCORE track (VCP, 15) disagrees
        # → demoted to SIGNAL (max score track must also agree)
        candidates = [
            _make_ts("vcp", 15.0, 1),
            _make_ts("trend_following", 8.0, -1),
            _make_ts("mean_reversion", 6.0, -1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.strength == "SIGNAL"  # demoted: max_score track (VCP) disagrees with ensemble
        assert result.direction == -1
        # TF and MR both agree on -1 → 2 agreeing tracks
        assert result.agreement_count == 2

    def test_no_signal_below_threshold(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        candidates = [
            _make_ts("vcp", 5.0, 1),
            _make_ts("trend_following", 4.0, 1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        # max(5,4) = 5 < 6 threshold → NONE
        assert result.strength == "NONE"

    def test_edge_per_trade_from_registry(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        # In bull_trend, VCP long edge = 1.8×0.45 = 0.81
        # 2 agreeing → avg edge = 0.81
        candidates = [
            _make_ts("vcp", 10.0, 1),
            _make_ts("trend_following", 9.0, 1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.edge_per_trade > 0
        assert result.direction == 1

    def test_empty_candidates_returns_neutral(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal

        result = compute_ensemble_signal([], "bull_trend")

        assert result.direction == 0
        assert result.strength == "NONE"
        assert result.ensemble_score == 0.0

    def test_cross_regime_correlation_full_agreement(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        candidates = [
            _make_ts("vcp", 10.0, 1),
            _make_ts("trend_following", 9.0, 1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.cross_regime_corr == 1.0

    def test_cross_regime_correlation_disagreement(self):
        from app.engines.directional.track_scoring import compute_ensemble_signal, _TRACK_WINDOWS
        _TRACK_WINDOWS.clear()

        candidates = [
            _make_ts("vcp", 10.0, 1),
            _make_ts("mean_reversion", 9.0, -1),
        ]
        result = compute_ensemble_signal(candidates, "bull_trend")

        assert result.cross_regime_corr == 0.0


class TestScoreHistory:
    def test_update_history_maintains_window_size(self):
        from app.engines.directional.track_scoring import update_history, get_history, _TRACK_WINDOWS

        _TRACK_WINDOWS.clear()
        for i in range(250):
            update_history("trend_following", float(i))

        history = get_history("trend_following")
        assert len(history) == 200
        assert history[-1] == 249.0

    def test_normalize_score_with_empty_history(self):
        from app.engines.directional.track_scoring import _normalise_score

        result = _normalise_score(10.0, [])
        assert result == 0.5

    def test_normalize_score_percentile_rank(self):
        from app.engines.directional.track_scoring import _normalise_score

        history = list(range(10))
        result = _normalise_score(8.0, history)
        assert result == 0.8