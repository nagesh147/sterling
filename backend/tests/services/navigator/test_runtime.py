from __future__ import annotations

import os
import tempfile

import pytest

from app.engines.navigator.schemas import NavigatorDecision
from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.engines.navigator.schemas import NavigatorConfigModel
from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services import db
from app.services.kite_engine import state as kite_state
from app.services.kite_engine.universe import UniverseItem
from app.services.navigator import config_store, runtime, service as nav_service


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    kite_state.reset("user-1")
    nav_service.clear_cache("user-1")
    runtime._status.pop("user-1", None)
    runtime._snapshots.pop("user-1", None)
    runtime._activity.pop("user-1", None)
    yield
    kite_state.reset("user-1")
    nav_service.clear_cache("user-1")
    runtime._status.pop("user-1", None)
    runtime._snapshots.pop("user-1", None)
    runtime._activity.pop("user-1", None)
    os.unlink(path)


class FakeClient:
    pass


def _item(name="NIFTY 50", token=256265, is_index=True):
    return UniverseItem(
        name=name, tradingsymbol="NIFTY", token=token, exchange="INDICES",
        option_exchange="NFO", is_index=is_index,
    )


def _enable_nav(**updates):
    rec = config_store.get("user-1", default_underlyings=["NIFTY 50"])
    cfg = rec.config.model_copy(update={"enabled": True, "signal_origination": "heads_up", **updates})
    return config_store.save("user-1", cfg, expected_revision=rec.revision, default_underlyings=["NIFTY 50"])


def _decision(status="CONFIRMED", ts=1_700_000_000_000):
    return NavigatorDecision(
        decision_id=f"d-{status}-{ts}",
        config_revision=2,
        model_versions={"fusion": "test"},
        generated_at_ms=ts + 1,
        bar_close_ms=ts,
        activation_watermark_ms=0,
        base_signal_id=f"navigator_origin_NIFTY 50:256265:long:{ts}",
        trigger="base_fresh",
        direction="long",
        status=status,
        base_score=50.0,
        suite_score=80.0 if status == "CONFIRMED" else None,
        effective_score=80.0 if status == "CONFIRMED" else None,
        execution_eligible=status == "CONFIRMED",
        data_quality="ok",
        reason_codes=["OK"],
    )


def _nav_row(**updates):
    ts = updates.pop("timestamp_ms", 1_700_000_000_000)
    row = EngineSignalRow(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL",
        alignment=AlignmentChip(fast=0, mid=0, slow=0),
        direction="long", option_type="CE", legs=[],
        spot=22000.0, stop_loss=21900.0, score=50.0,
        timestamp_ms=ts, is_active=True, is_fresh=False, source="navigator",
        navigator=_decision(ts=ts),
    )
    return row.model_copy(update=updates)


async def _empty_dumps(_client):
    return ([{}], [], [], [])


async def _noop_async(*_args, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_runtime_scans_when_supertrend_engine_disabled(monkeypatch):
    kite_state.set_config("user-1", EngineConfigModel(engine_enabled=False, scan_indices=["NIFTY 50"]))
    _enable_nav()
    calls = []
    monkeypatch.setattr(runtime, "_instrument_dumps", _empty_dumps)
    monkeypatch.setattr(runtime, "build_universe", lambda **kw: [_item()])
    monkeypatch.setattr(runtime, "_start_samplers", _noop_async)

    async def fake_pass(client, uid, rows, **kwargs):
        calls.append(kwargs["underlying_tokens"])
        return rows

    monkeypatch.setattr(runtime.nav_service, "run_navigator_pass", fake_pass)
    count = await runtime.scan_user(FakeClient(), "user-1", acct=object())

    assert count == 0
    assert calls == [{"NIFTY 50": 256265}]
    assert runtime.status("user-1").last_scan_ms > 0


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["spot", "derivatives", "both", "confluence"])
async def test_runtime_preserves_scan_source_modes(monkeypatch, source):
    kite_state.set_config("user-1", EngineConfigModel(scan_indices=["NIFTY 50"]))
    _enable_nav(scan_source=source)
    seen_kwargs = []
    monkeypatch.setattr(runtime, "_instrument_dumps", _empty_dumps)
    monkeypatch.setattr(runtime, "build_universe", lambda **kw: [_item()])
    monkeypatch.setattr(runtime, "_start_samplers", _noop_async)
    monkeypatch.setattr(runtime, "_flow_history", lambda *a, **kw: ([], [], None, "unavailable"))

    async def fake_pass(client, uid, rows, **kwargs):
        seen_kwargs.append(kwargs)
        return rows

    monkeypatch.setattr(runtime.nav_service, "run_navigator_pass", fake_pass)
    await runtime.scan_user(FakeClient(), "user-1", acct=object())

    assert runtime.status("user-1").scan_source == source
    assert seen_kwargs[0]["underlying_tokens"] == {"NIFTY 50": 256265}
    eval_kwargs = seen_kwargs[0]["evaluation_kwargs"]
    if source == "spot":
        assert "flow_not_applicable" not in eval_kwargs
    else:
        assert eval_kwargs["flow_not_applicable"] is False
        assert eval_kwargs["chain_quality"] == "unavailable"


@pytest.mark.asyncio
async def test_cancel_marks_running_scan_cancelled():
    st = runtime.status("user-1")
    st.scanning = True
    assert runtime.cancel("user-1") is True
    assert runtime.status("user-1").cancelled is True
    assert runtime.status("user-1").scanning is False


@pytest.mark.asyncio
async def test_partial_universe_failure_does_not_abort_remaining(monkeypatch):
    kite_state.set_config("user-1", EngineConfigModel(scan_indices=["NIFTY 50", "NIFTY BANK"]))
    _enable_nav()
    good = _item("NIFTY 50", 1)
    bad = _item("NIFTY BANK", 2)
    monkeypatch.setattr(runtime, "_instrument_dumps", _empty_dumps)
    monkeypatch.setattr(runtime, "build_universe", lambda **kw: [bad, good])
    monkeypatch.setattr(runtime, "_start_samplers", _noop_async)

    async def fake_pass(client, uid, rows, **kwargs):
        if "NIFTY BANK" in kwargs["underlying_tokens"]:
            raise RuntimeError("bad token")
        return rows

    monkeypatch.setattr(runtime.nav_service, "run_navigator_pass", fake_pass)
    await runtime.scan_user(FakeClient(), "user-1", acct=object())

    assert runtime.status("user-1").failures == [{"underlying": "NIFTY BANK", "error": "bad token"}]
    assert runtime.status("user-1").last_scan_ms > 0


def test_sampler_config_contains_flow_fields_and_interval():
    cfg = NavigatorConfigModel(enabled=True, flow_sample_seconds=75)
    sampler_cfg = runtime._sampler_config(cfg)
    assert sampler_cfg.mode == cfg.flow.mode
    assert sampler_cfg.dynamic_strike_radius == cfg.flow.dynamic_strike_radius
    assert sampler_cfg.flow_sample_seconds == 75


def test_lifecycle_marks_missing_completed_setup_ended_and_forgets_cache():
    row = _nav_row(is_active=True, is_fresh=False)
    nav_service.cache_decision("user-1", underlying=row.underlying, token=row.token, direction=row.direction, decision=row.navigator)

    merged = runtime._merge_with_lifecycle("user-1", [row], [], {"NIFTY 50"})

    assert len(merged) == 1
    assert merged[0].source == "navigator"
    assert merged[0].is_active is False
    assert merged[0].is_fresh is False
    assert nav_service.get_cached_decision("user-1", underlying=row.underlying, token=row.token, direction=row.direction) is None


def test_lifecycle_preserves_prior_row_when_underlying_failed():
    row = _nav_row(is_active=True, is_fresh=False)

    merged = runtime._merge_with_lifecycle("user-1", [row], [], set())

    assert len(merged) == 1
    assert merged[0].is_active is True
    assert merged[0].is_fresh is False


def test_widest_retention_keeps_what_the_longest_retaining_user_needs():
    """The snapshot tables are shared but retention is per-user config, so one
    pass has to keep the most generous window asked for — trimming to a
    shorter user's window would delete history another user still relies on."""
    defaults = NavigatorConfigModel()
    kite_state.set_config("user-1", EngineConfigModel(scan_indices=["NIFTY 50"]))
    rec = config_store.get("user-1", default_underlyings=["NIFTY 50"])
    config_store.save(
        "user-1",
        rec.config.model_copy(update={
            "enabled": True,
            "retention_raw_days": defaults.retention_raw_days + 11,
            "retention_features_days": defaults.retention_features_days + 22,
        }),
        expected_revision=rec.revision, default_underlyings=["NIFTY 50"],
    )

    raw, feature = runtime._widest_retention(["user-1", "user-unknown"])

    assert raw == defaults.retention_raw_days + 11
    assert feature == defaults.retention_features_days + 22


def test_widest_retention_falls_back_to_schema_defaults():
    defaults = NavigatorConfigModel()
    assert runtime._widest_retention([]) == (
        defaults.retention_raw_days, defaults.retention_features_days,
    )


def test_snapshot_hydrates_active_navigator_decision_cache():
    row = _nav_row(is_active=True, is_fresh=False)
    db.set_config(
        "navigator_runtime_rows_user-1",
        '{"generated_ms": 1700000000001, "rows": [' + row.model_dump_json() + ']}',
    )
    runtime._snapshots.pop("user-1", None)
    nav_service.clear_cache("user-1")

    snap = runtime.snapshot("user-1")

    assert snap.rows[0].underlying == "NIFTY 50"
    assert nav_service.get_cached_decision("user-1", underlying=row.underlying, token=row.token, direction=row.direction) is not None
