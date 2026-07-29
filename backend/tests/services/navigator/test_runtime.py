from __future__ import annotations

import os
import tempfile

import pytest

from app.engines.navigator.schemas import NavigatorConfigModel
from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services import db
from app.services.kite_engine import state as kite_state
from app.services.kite_engine.universe import UniverseItem
from app.services.navigator import config_store, runtime


@pytest.fixture(autouse=True)
def isolated_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    kite_state.reset("user-1")
    runtime._status.pop("user-1", None)
    runtime._snapshots.pop("user-1", None)
    runtime._activity.pop("user-1", None)
    yield
    kite_state.reset("user-1")
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
    monkeypatch.setattr(runtime, "_flow_history", lambda *a, **kw: ([], [], None))

    async def fake_pass(client, uid, rows, **kwargs):
        seen_kwargs.append(kwargs)
        return rows

    monkeypatch.setattr(runtime.nav_service, "run_navigator_pass", fake_pass)
    await runtime.scan_user(FakeClient(), "user-1", acct=object())

    assert runtime.status("user-1").scan_source == source
    assert seen_kwargs[0]["underlying_tokens"] == {"NIFTY 50": 256265}


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
