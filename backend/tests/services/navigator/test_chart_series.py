"""Tests for the Navigator chart overlay series (`chart_series.py`).

The overlay's whole value is that it shows what the engine actually saw, so
these tests pin the two properties that make that true: the per-bar setups it
draws are the engine's own `family_timeline`, and anything Navigator never
recorded comes back as a gap rather than a zero.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime

import numpy as np
import pytest

from app.engines.navigator import avwap
from app.engines.navigator.quality import validate_candles
from app.schemas.market import Candle
from app.services import db
from app.services.navigator import chart_series, config_store, service as nav_service
from app.services.navigator.calendar import IST

_UID = "chart-user"
_UNDERLYINGS = ["NIFTY 50"]


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    nav_service.clear_cache(_UID)
    yield
    nav_service.clear_cache(_UID)
    os.unlink(path)


def _kite_rows(n=300, seed=7, start=24500.0, step_ms=3_600_000):
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, 5, n))
    open_ = close - rng.normal(0, 2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(3, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(3, 1, n))
    volume = np.abs(rng.normal(100_000, 10_000, n))
    now_ms = int(time.time() * 1000)
    last_closed = now_ms - (now_ms % step_ms) - step_ms
    rows = []
    for i in range(n):
        ts = last_closed - (n - 1 - i) * step_ms
        rows.append([
            datetime.fromtimestamp(ts / 1000, tz=IST).strftime("%Y-%m-%d %H:%M:%S+0530"),
            float(open_[i]), float(high[i]), float(low[i]), float(close[i]), float(volume[i]),
        ])
    return rows


class FakeKiteClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[tuple] = []

    async def get_historical(self, token, interval, frm, to, continuous=False, oi=False):
        self.calls.append((token, interval))
        return {"candles": self.rows}


def _record(**overrides):
    rec = config_store.get(_UID, default_underlyings=_UNDERLYINGS)
    if overrides:
        config_store.save(
            _UID, rec.config.model_copy(update=overrides),
            expected_revision=rec.revision, default_underlyings=_UNDERLYINGS,
        )
        rec = config_store.get(_UID, default_underlyings=_UNDERLYINGS)
    return rec


async def _build(client=None, record=None, underlying="NIFTY 50", bars=320):
    client = client or FakeKiteClient(_kite_rows())
    record = record or _record()
    return await chart_series.build_chart_series(
        client, _UID, underlying, token=256265, record=record, bars=bars,
    )


class TestStructureSeries:
    @pytest.mark.asyncio
    async def test_reads_navigators_own_hourly_timeframe(self):
        client = FakeKiteClient(_kite_rows())
        out = await _build(client)
        assert out["timeframe"] == "60minute"
        assert client.calls and client.calls[0][1] == "60minute"

    @pytest.mark.asyncio
    async def test_per_bar_setups_match_the_engines_family_timeline(self):
        """The overlay must not be able to show a setup the engine never saw."""
        rows = _kite_rows()
        out = await _build(FakeKiteClient(rows))

        candles = validate_candles([
            Candle(
                timestamp_ms=int(datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S%z").timestamp() * 1000),
                open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5],
            ) for r in rows
        ])
        record = config_store.get(_UID, default_underlyings=_UNDERLYINGS)
        structure = avwap.compute_structure(candles, record.config.avwap)
        timeline = avwap.family_timeline(candles, structure, record.config.avwap)

        # The overlay drops the still-forming bar, so align on the tail it kept.
        assert out["bar_count"] <= candles.n
        offset = candles.n - out["bar_count"]
        for i, bar in enumerate(out["structure"]):
            expected = timeline.family_at(i + offset)
            assert bar["setup"] == (expected[0] if expected else None)
            assert bar["fired"] is bool(timeline.fired[i + offset])

    @pytest.mark.asyncio
    async def test_warmup_bars_come_back_as_nulls_not_zeroes(self):
        out = await _build()
        warming = [b for b in out["structure"] if b["warming_up"]]
        assert warming, "expected some warm-up bars in a 300-bar window"
        assert all(b["mid"] is None for b in warming)
        assert all(b["upper"] is None and b["lower"] is None for b in warming)

    @pytest.mark.asyncio
    async def test_every_number_is_json_safe(self):
        """NaN is the engine's "no value" marker and is not valid JSON."""
        out = await _build()
        encoded = json.dumps(out, allow_nan=False)
        assert "NaN" not in encoded

    @pytest.mark.asyncio
    async def test_anchors_report_both_the_pivot_bar_and_its_confirmation_bar(self):
        out = await _build()
        assert out["anchors"], "a 300-bar window should confirm some pivots"
        for anchor in out["anchors"]:
            # Confirmation always lags the pivot — this is what makes the
            # overlay evidence that Navigator does not backfill anchors.
            assert anchor["confirmed_t"] > anchor["pivot_t"]
            assert anchor["kind"] in ("high", "low")

    @pytest.mark.asyncio
    async def test_too_few_bars_says_so_instead_of_drawing_a_stub(self):
        out = await _build(FakeKiteClient(_kite_rows(n=20)))
        assert out["structure"] == []
        assert any("needs 60" in note for note in out["notes"])


class TestRecordedEvidence:
    @pytest.mark.asyncio
    async def test_no_recorded_chain_evidence_is_a_gap_and_a_note(self):
        out = await _build()
        assert out["flow"] == [] and out["gamma"] == []
        assert any("No option-chain evidence" in note for note in out["notes"])
        assert any("no decision" in note for note in out["notes"])

    @pytest.mark.asyncio
    async def test_recorded_flow_and_gamma_are_read_back_per_bar(self, monkeypatch):
        bar_ms = int(time.time() * 1000) - 3_600_000
        monkeypatch.setattr(nav_service, "get_feature_series", lambda *a, **k: [{
            "bar_close_ms": bar_ms,
            "flow_json": json.dumps({
                "component": "option_flow", "direction": 1, "confidence_100": 61.0, "quality": "ok",
                "diagnostics": {"oscillator": 0.42, "state": "CALL_DOMINANT"},
            }),
            "gamma_json": json.dumps({
                "component": "gamma", "direction": -1, "confidence_100": 30.0, "quality": "degraded",
                "diagnostics": {},
            }),
        }])
        out = await _build()
        assert out["flow"] == [{
            "t": bar_ms // 1000, "oscillator": 0.42, "state": "CALL_DOMINANT",
            "direction": 1, "confidence": 61.0, "quality": "ok",
        }]
        assert out["gamma"][0]["signed_confidence"] == -30.0

    @pytest.mark.asyncio
    async def test_decisions_never_invent_a_plan(self, monkeypatch):
        """A NavigatorDecision holds evidence and a verdict, not entry/stop/target."""
        from app.services.navigator import repository

        bar_ms = int(time.time() * 1000) - 3_600_000
        monkeypatch.setattr(repository, "fetch_signal_events_page", lambda *a, **k: [{
            "decision_id": "d-1", "bar_close_ms": bar_ms, "direction": "long",
            "status": "CONFIRMED", "effective_score": 71.5, "execution_eligible": 1,
            "payload_json": json.dumps({
                "trigger": "avwap_fresh", "base_score": 85.0, "data_quality": "ok",
                "reason_codes": ["OK"],
            }),
        }])
        out = await _build()
        assert len(out["decisions"]) == 1
        decision = out["decisions"][0]
        assert decision["status"] == "CONFIRMED" and decision["execution_eligible"] is True
        assert "entry" not in decision and "stop" not in decision and "target" not in decision

    @pytest.mark.asyncio
    async def test_storage_failure_degrades_the_overlay_instead_of_the_chart(self, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("db gone")
        monkeypatch.setattr(nav_service, "get_feature_series", _boom)
        out = await _build()
        assert out["structure"], "price structure must still render"
        assert out["flow"] == []


class TestHonestLabelling:
    @pytest.mark.asyncio
    async def test_disabled_navigator_is_labelled_not_hidden(self):
        out = await _build(record=_record(enabled=False))
        assert out["enabled"] is False
        assert out["structure"], "the maths still renders so it can be evaluated before trusting it"
        assert any("Navigator is off" in note for note in out["notes"])

    @pytest.mark.asyncio
    async def test_unscanned_underlying_is_flagged_as_never_evaluated(self):
        out = await _build(record=_record(enabled=True), underlying="RELIANCE")
        assert out["configured"] is False
        assert any("does not scan RELIANCE" in note for note in out["notes"])

    @pytest.mark.asyncio
    async def test_configured_underlying_carries_no_scope_caveat(self):
        out = await _build(record=_record(enabled=True, underlyings=["NIFTY 50"]))
        assert out["configured"] is True
        assert not any("does not scan" in note for note in out["notes"])


class TestTokenResolution:
    def test_matches_an_index_on_any_of_its_three_names(self):
        indices = [{"name": "NIFTY BANK", "spot_symbol": "NIFTY BANK",
                    "spot_token": 260105, "option_name": "BANKNIFTY"}]
        for name in ("NIFTY BANK", "banknifty", "  BANKNIFTY  "):
            assert chart_series.resolve_underlying_token(indices, name) == 260105

    def test_unknown_name_resolves_to_none_rather_than_a_wrong_instrument(self):
        indices = [{"name": "NIFTY 50", "spot_symbol": "NIFTY 50",
                    "spot_token": 256265, "option_name": "NIFTY"}]
        assert chart_series.resolve_underlying_token(indices, "NIFTY IT") is None
        assert chart_series.resolve_underlying_token(indices, "") is None
