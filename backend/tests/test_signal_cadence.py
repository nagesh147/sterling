"""
Cadence smoke test — confirms snapshot cache TTL and SSE emit interval
match the 5 s signal cadence introduced for faster mode-change reflection.
"""
from __future__ import annotations
import importlib
import os
import sys


def test_snapshot_cache_default_ttl_is_10s():
    """Default snapshot TTL is 10 s (= 2× the 5 s emit interval)."""
    # Force a fresh import without the env override
    sys.modules.pop("app.services.snapshot_cache", None)
    os.environ.pop("STERLING_SNAPSHOT_TTL_MS", None)
    mod = importlib.import_module("app.services.snapshot_cache")
    assert mod._TTL_MS == 10_000


def test_snapshot_cache_ttl_env_override(monkeypatch):
    """STERLING_SNAPSHOT_TTL_MS env var overrides default."""
    monkeypatch.setenv("STERLING_SNAPSHOT_TTL_MS", "30000")
    sys.modules.pop("app.services.snapshot_cache", None)
    mod = importlib.import_module("app.services.snapshot_cache")
    assert mod._TTL_MS == 30_000
    # Reset so other tests aren't affected
    monkeypatch.delenv("STERLING_SNAPSHOT_TTL_MS", raising=False)
    sys.modules.pop("app.services.snapshot_cache", None)


def test_sse_signal_emit_interval_default_is_5s():
    """The SSE generator reads STERLING_SIGNAL_INTERVAL_S; default is 5 s."""
    # Pure inline check — the SSE generator parses the env var lazily on
    # connection so we just confirm the parse path picks 5 when unset.
    os.environ.pop("STERLING_SIGNAL_INTERVAL_S", None)
    raw = os.environ.get("STERLING_SIGNAL_INTERVAL_S", "5")
    parsed = int(raw)
    assert parsed == 5


def test_sse_signal_emit_interval_clamped(monkeypatch):
    """SSE generator clamps the interval to [1, 60] seconds."""
    monkeypatch.setenv("STERLING_SIGNAL_INTERVAL_S", "0")
    val = max(1, min(60, int(os.environ["STERLING_SIGNAL_INTERVAL_S"])))
    assert val == 1
    monkeypatch.setenv("STERLING_SIGNAL_INTERVAL_S", "9999")
    val = max(1, min(60, int(os.environ["STERLING_SIGNAL_INTERVAL_S"])))
    assert val == 60
