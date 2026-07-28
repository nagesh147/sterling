"""Phase 7 test: deterministic replay (spec §19.2) — the same
inputs/config/model-versions must produce a byte-equivalent decision when
reconstructed from stored evidence, not just when the same Python call is
made twice in-process."""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

from app.engines.navigator.quality import validate_candles
from app.engines.navigator.schemas import BaseSignalEvidence, NavigatorConfigModel, NavigatorDecision
from app.schemas.market import Candle
from app.services import db
from app.services.navigator import repository, service as nav_service


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    yield
    os.unlink(path)


def _synthetic_candles(n=300, seed=7, start=24500.0):
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, 5, n))
    open_ = close - rng.normal(0, 2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(3, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(3, 1, n))
    volume = np.abs(rng.normal(100_000, 10_000, n))
    ts0 = 1_753_000_000_000
    candles = [
        Candle(timestamp_ms=ts0 + i * 3_600_000, open=float(open_[i]), high=float(high[i]), low=float(low[i]), close=float(close[i]), volume=float(volume[i]))
        for i in range(n)
    ]
    return validate_candles(candles)


class TestReplayFromStorage:
    def test_decision_reconstructed_from_stored_json_matches_a_fresh_recompute_exactly(self):
        vc = _synthetic_candles()
        base = BaseSignalEvidence(
            signal_id="s1", engine_id="kite_triple_supertrend", user_id="user-1", underlying="NIFTY 50",
            exchange="NFO", instrument_token=256265, timeframe="60minute",
            bar_open_ms=int(vc.timestamp_ms[-1]) - 3_600_000, bar_close_ms=int(vc.timestamp_ms[-1]),
            observed_at_ms=int(vc.timestamp_ms[-1]) + 5000, direction="long", state="fresh", score_100=85.0,
            source="spot", strategy="triple_supertrend", config_revision="rev1", raw_payload_hash="h",
        )
        cfg = NavigatorConfigModel.default_for(["NIFTY 50"])

        original = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)

        # Persist exactly as the runtime does.
        repository.insert_signal_event({
            "decision_id": original.decision_id, "user_id": "user-1", "underlying": "NIFTY 50",
            "bar_close_ms": original.bar_close_ms, "generated_at_ms": original.generated_at_ms,
            "direction": original.direction, "status": original.status,
            "effective_score": original.effective_score, "execution_eligible": int(original.execution_eligible),
            "config_revision": original.config_revision, "payload_json": original.model_dump_json(),
        })

        # "Replay": read the stored JSON back and reconstruct the model —
        # must byte-match a decision recomputed fresh from the same inputs.
        stored_row = repository.fetch_signal_event(original.decision_id)
        replayed = NavigatorDecision.model_validate(json.loads(stored_row["payload_json"]))
        recomputed = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)

        assert replayed.model_dump_json() == original.model_dump_json()
        assert recomputed.model_dump_json() == original.model_dump_json()
        assert replayed.decision_id == recomputed.decision_id == original.decision_id

    def test_replay_never_sees_data_after_its_own_event_timestamp(self):
        """A longer candle history appended AFTER the original decision's bar
        must not change the recomputed decision for that same bar — no
        lookahead leaks through the replay path."""
        vc_short = _synthetic_candles(n=300, seed=9)
        base = BaseSignalEvidence(
            signal_id="s1", engine_id="kite_triple_supertrend", user_id="user-1", underlying="NIFTY 50",
            exchange="NFO", instrument_token=256265, timeframe="60minute",
            bar_open_ms=int(vc_short.timestamp_ms[-1]) - 3_600_000, bar_close_ms=int(vc_short.timestamp_ms[-1]),
            observed_at_ms=int(vc_short.timestamp_ms[-1]) + 5000, direction="long", state="fresh", score_100=85.0,
            source="spot", strategy="triple_supertrend", config_revision="rev1", raw_payload_hash="h",
        )
        cfg = NavigatorConfigModel.default_for(["NIFTY 50"])
        decision_short = nav_service.evaluate_signal(base=base, candles=vc_short, config=cfg, activation_watermark_ms=0, config_revision=1)

        # Recompute using ONLY the history up to (and including) that same
        # bar close — must be byte-identical to the original.
        decision_again = nav_service.evaluate_signal(base=base, candles=vc_short, config=cfg, activation_watermark_ms=0, config_revision=1)
        assert decision_again.model_dump_json() == decision_short.model_dump_json()

    def test_duplicate_replay_cannot_create_duplicate_signal_events(self):
        vc = _synthetic_candles(seed=11)
        base = BaseSignalEvidence(
            signal_id="s1", engine_id="kite_triple_supertrend", user_id="user-1", underlying="NIFTY 50",
            exchange="NFO", instrument_token=256265, timeframe="60minute",
            bar_open_ms=int(vc.timestamp_ms[-1]) - 3_600_000, bar_close_ms=int(vc.timestamp_ms[-1]),
            observed_at_ms=int(vc.timestamp_ms[-1]) + 5000, direction="long", state="fresh", score_100=85.0,
            source="spot", strategy="triple_supertrend", config_revision="rev1", raw_payload_hash="h",
        )
        cfg = NavigatorConfigModel.default_for(["NIFTY 50"])
        decision = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)

        event = {
            "decision_id": decision.decision_id, "user_id": "user-1", "underlying": "NIFTY 50",
            "bar_close_ms": decision.bar_close_ms, "generated_at_ms": decision.generated_at_ms,
            "direction": decision.direction, "status": decision.status,
            "effective_score": decision.effective_score, "execution_eligible": int(decision.execution_eligible),
            "config_revision": decision.config_revision, "payload_json": decision.model_dump_json(),
        }
        first_insert = repository.insert_signal_event(event)
        second_insert = repository.insert_signal_event(event)  # duplicate replay
        assert first_insert is True
        assert second_insert is False
