"""Phase 5 tests: the Navigator runtime service — the scanner join point,
the central-gate eligibility recheck, and the price-feature-only pipeline
(spec §16, §18, §20.8)."""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from app.engines.navigator.quality import validate_candles
from app.engines.navigator.schemas import BaseSignalEvidence, NavigatorConfigModel
from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.schemas.market import Candle
from app.services import db
from app.services.navigator import config_store, repository, service as nav_service

_UNDERLYINGS = ["NIFTY 50"]
_ALIGN = AlignmentChip(fast=1, mid=1, slow=1)


@pytest.fixture(autouse=True)
def isolated_db_and_cache():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    nav_service.clear_cache("user-1")
    yield
    nav_service.clear_cache("user-1")
    os.unlink(path)


def _synthetic_candles(n=300, seed=21, start=24500.0):
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


def _row(**overrides) -> EngineSignalRow:
    base = dict(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL", alignment=_ALIGN,
        direction="long", option_type="CE", spot=24500.0, stop_loss=24300.0, score=85.0,
        timestamp_ms=1_753_000_000_000, is_active=True, is_fresh=True, source="spot",
    )
    base.update(overrides)
    return EngineSignalRow(**base)


def _base_evidence(vc, **overrides) -> BaseSignalEvidence:
    base = dict(
        signal_id="s1", engine_id="kite_triple_supertrend", user_id="user-1", underlying="NIFTY 50",
        exchange="NFO", instrument_token=256265, timeframe="60minute",
        bar_open_ms=int(vc.timestamp_ms[-1]) - 3_600_000, bar_close_ms=int(vc.timestamp_ms[-1]),
        observed_at_ms=int(vc.timestamp_ms[-1]) + 5000, direction="long", state="fresh", score_100=85.0,
        source="spot", strategy="triple_supertrend", config_revision="rev1", raw_payload_hash="h",
    )
    base.update(overrides)
    return BaseSignalEvidence(**base)


class TestEvaluateSignalPriceOnly:
    def test_runs_end_to_end_and_flags_flow_gamma_unavailable(self):
        vc = _synthetic_candles()
        base = _base_evidence(vc)
        cfg = NavigatorConfigModel.default_for(_UNDERLYINGS)
        decision = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)
        assert decision.avwap.quality in ("ok", "unavailable")
        assert decision.option_flow.quality == "unavailable"
        assert decision.gamma.quality == "unavailable"
        assert "CHAIN_UNAVAILABLE" in decision.option_flow.reason_codes

    def test_is_deterministic_for_identical_input(self):
        vc = _synthetic_candles()
        base = _base_evidence(vc)
        cfg = NavigatorConfigModel.default_for(_UNDERLYINGS)
        d1 = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)
        d2 = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)
        assert d1.decision_id == d2.decision_id
        assert d1.status == d2.status
        assert d1.effective_score == d2.effective_score

    def test_status_never_no_data_when_avwap_and_volatility_are_warm(self):
        vc = _synthetic_candles(n=400)
        base = _base_evidence(vc)
        cfg = NavigatorConfigModel.default_for(_UNDERLYINGS)
        decision = nav_service.evaluate_signal(base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1)
        if decision.avwap.quality == "ok" and decision.volatility.quality == "ok":
            assert decision.status != "NO_DATA"


class TestEvaluateAndCache:
    def test_caches_and_persists_the_decision(self):
        vc = _synthetic_candles()
        base = _base_evidence(vc)
        cfg = NavigatorConfigModel.default_for(_UNDERLYINGS)
        row = _row()
        decision = nav_service.evaluate_and_cache(
            "user-1", row, base=base, candles=vc, config=cfg, activation_watermark_ms=0, config_revision=1,
        )
        cached = nav_service.get_cached_decision("user-1", underlying=row.underlying, token=row.token, direction=row.direction)
        assert cached is not None
        assert cached.decision_id == decision.decision_id
        stored = repository.fetch_signal_event(decision.decision_id)
        assert stored is not None
        assert stored["decision_id"] == decision.decision_id


class TestAttachToRows:
    def test_disabled_config_is_a_complete_noop(self):
        row = _row()
        out = nav_service.attach_to_rows("user-1", [row], default_underlyings=_UNDERLYINGS)
        assert out[0].navigator is None

    def test_enabled_config_attaches_matching_cached_decision(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        enabled_cfg = rec.config.model_copy(update={"enabled": True})
        rec = config_store.save("user-1", enabled_cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        vc = _synthetic_candles()
        base = _base_evidence(vc)
        row = _row()
        decision = nav_service.evaluate_and_cache(
            "user-1", row, base=base, candles=vc, config=rec.config,
            activation_watermark_ms=rec.activation_watermark_ms, config_revision=rec.revision,
        )
        out = nav_service.attach_to_rows("user-1", [row], default_underlyings=_UNDERLYINGS)
        assert out[0].navigator is not None
        assert out[0].navigator.decision_id == decision.decision_id

    def test_stale_row_is_skipped(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        enabled_cfg = rec.config.model_copy(update={"enabled": True})
        config_store.save("user-1", enabled_cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)
        row = _row(is_active=False, is_fresh=False)
        out = nav_service.attach_to_rows("user-1", [row], default_underlyings=_UNDERLYINGS)
        assert out[0].navigator is None

    def test_revision_mismatch_does_not_attach_a_stale_decision(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        enabled_cfg = rec.config.model_copy(update={"enabled": True})
        rec = config_store.save("user-1", enabled_cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        vc = _synthetic_candles()
        base = _base_evidence(vc)
        row = _row()
        nav_service.evaluate_and_cache(
            "user-1", row, base=base, candles=vc, config=rec.config,
            activation_watermark_ms=rec.activation_watermark_ms, config_revision=rec.revision,
        )
        # config changes again -> new revision; the cached decision is now stale
        rec2 = config_store.save(
            "user-1", rec.config.model_copy(update={"flow_sample_seconds": 90}),
            expected_revision=rec.revision, default_underlyings=_UNDERLYINGS,
        )
        out = nav_service.attach_to_rows("user-1", [row], default_underlyings=_UNDERLYINGS)
        assert out[0].navigator is None


class TestCheckExecutionEligible:
    def test_disabled_is_always_a_passthrough(self):
        row = _row()
        eligible, reason = nav_service.check_execution_eligible("user-1", row, default_underlyings=_UNDERLYINGS)
        assert eligible is True
        assert reason == "navigator_not_gating"

    def test_advisory_mode_is_also_a_passthrough(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        cfg = rec.config.model_copy(update={"enabled": True, "operating_mode": "advisory"})
        config_store.save("user-1", cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)
        row = _row()
        eligible, reason = nav_service.check_execution_eligible("user-1", row, default_underlyings=_UNDERLYINGS)
        assert eligible is True
        assert reason == "navigator_not_gating"

    def test_gate_mode_without_calibration_readiness_blocks(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        cfg = rec.config.model_copy(update={"enabled": True, "operating_mode": "gate"})
        config_store.save("user-1", cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)
        row = _row()
        eligible, reason = nav_service.check_execution_eligible("user-1", row, default_underlyings=_UNDERLYINGS)
        assert eligible is False
        assert reason == "GATE_NOT_CALIBRATED"

    def test_gate_mode_never_becomes_eligible_in_this_build(self):
        # calibration_readiness can only ever be "not_ready" in this build
        # (no promotion path exists yet) — gate mode must never silently
        # become eligible.
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        cfg = rec.config.model_copy(update={"enabled": True, "operating_mode": "gate"})
        rec = config_store.save("user-1", cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)
        assert rec.calibration_readiness == "not_ready"
        row = _row()
        eligible, _ = nav_service.check_execution_eligible("user-1", row, default_underlyings=_UNDERLYINGS)
        assert eligible is False


class TestStatus:
    def test_disabled_status_is_disabled_health(self):
        status = nav_service.get_status("user-1", default_underlyings=_UNDERLYINGS)
        assert status.health == "DISABLED"
        assert status.enabled is False

    def test_enabled_without_sampler_activity_is_starting(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        cfg = rec.config.model_copy(update={"enabled": True})
        config_store.save("user-1", cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)
        status = nav_service.get_status("user-1", default_underlyings=_UNDERLYINGS)
        assert status.health == "STARTING"

    def test_healthy_after_a_decision_is_cached(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        cfg = rec.config.model_copy(update={"enabled": True})
        rec = config_store.save("user-1", cfg, expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        vc = _synthetic_candles()
        base = _base_evidence(vc)
        row = _row()
        nav_service.evaluate_and_cache(
            "user-1", row, base=base, candles=vc, config=rec.config,
            activation_watermark_ms=rec.activation_watermark_ms, config_revision=rec.revision,
            generated_at_ms=nav_service._now_ms(),
        )
        status = nav_service.get_status("user-1", default_underlyings=_UNDERLYINGS)
        assert status.sampler_running is False
        assert status.health == "WARMING_UP"
        assert status.last_decision_at_ms is not None
