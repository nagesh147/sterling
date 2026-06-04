"""
OBSERVABILITY (Phase 2) — structured JSON logging + correlation IDs + metrics.

All additive: the existing plain-text logging and the UI WsLogHandler are
untouched. These tests pin the new opt-in surface.
"""
import json
import logging

import pytest

from app.core import observability as obs
from app.core import metrics


# ── correlation IDs ───────────────────────────────────────────────────────
def test_correlation_id_roundtrip():
    assert obs.get_correlation_id() is None
    token = obs.set_correlation_id("abc123")
    assert obs.get_correlation_id() == "abc123"
    obs.reset_correlation_id(token)
    assert obs.get_correlation_id() is None


def test_new_correlation_id_is_unique():
    a, b = obs.new_correlation_id(), obs.new_correlation_id()
    assert a != b and len(a) >= 8


def test_correlation_scope_binds_and_restores():
    with obs.correlation_scope("trace-1") as cid:
        assert cid == "trace-1"
        assert obs.get_correlation_id() == "trace-1"
    assert obs.get_correlation_id() is None


# ── JSON formatter ────────────────────────────────────────────────────────
def test_json_formatter_emits_valid_json_with_fields():
    fmt = obs.JsonLogFormatter()
    rec = logging.LogRecord("svc", logging.INFO, __file__, 10, "hello %s", ("world",), None)
    line = fmt.format(rec)
    data = json.loads(line)
    assert data["level"] == "INFO"
    assert data["logger"] == "svc"
    assert data["message"] == "hello world"
    assert "timestamp" in data


def test_json_formatter_includes_correlation_id_when_set():
    fmt = obs.JsonLogFormatter()
    with obs.correlation_scope("cid-9"):
        rec = logging.LogRecord("svc", logging.INFO, __file__, 1, "m", (), None)
        data = json.loads(fmt.format(rec))
    assert data["correlation_id"] == "cid-9"


# ── metrics ───────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _reset_metrics():
    metrics.reset()
    yield
    metrics.reset()


def test_counter_increments():
    metrics.incr("orders_submitted")
    metrics.incr("orders_submitted", 2)
    snap = metrics.snapshot()
    assert snap["counters"]["orders_submitted"] == 3


def test_observe_summarizes():
    for v in (10.0, 20.0, 30.0):
        metrics.observe("latency_ms", v)
    s = metrics.snapshot()["summaries"]["latency_ms"]
    assert s["count"] == 3
    assert s["sum"] == 60.0
    assert s["min"] == 10.0
    assert s["max"] == 30.0
    assert s["avg"] == 20.0


def test_timer_records_a_summary():
    with metrics.timer("op_ms"):
        pass
    s = metrics.snapshot()["summaries"]
    assert "op_ms" in s and s["op_ms"]["count"] == 1
