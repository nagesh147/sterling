"""Tests for the live per-scan Navigator evaluation glue
(`service.run_navigator_pass`) — an independent candle fetch (never the
scanner's), gated entirely on `config.enabled`, deduped per
(underlying, token, direction), and defensive per-row so one bad fetch
can't break the rest of the scan."""
from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime

import numpy as np
import pytest

from app.engines.navigator import avwap
from app.engines.navigator.avwap import AvwapEvaluation, AvwapGradeResult, StopTargetProposal
from app.engines.navigator.schemas import NavigatorDecision
from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.services import db
from app.services.navigator import config_store, service as nav_service
from app.services.navigator.calendar import IST

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


def _row(**overrides) -> EngineSignalRow:
    base = dict(
        underlying="NIFTY 50", token=256265, exchange="NFO", regime="BULL", alignment=_ALIGN,
        direction="long", option_type="CE", spot=24500.0, stop_loss=24300.0, score=85.0,
        timestamp_ms=int(time.time() * 1000) - 3_600_000, is_active=True, is_fresh=True, source="spot",
    )
    base.update(overrides)
    return EngineSignalRow(**base)


def _kite_candle_rows(n=300, seed=3, start=24500.0, step_ms=3_600_000, include_forming=True):
    rng = np.random.default_rng(seed)
    close = start + np.cumsum(rng.normal(0, 5, n))
    open_ = close - rng.normal(0, 2, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(3, 1, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(3, 1, n))
    volume = np.abs(rng.normal(100_000, 10_000, n))
    now_ms = int(time.time() * 1000)
    # Anchor the LAST closed bar just before "now" so drop_forming has a
    # genuinely still-forming bar to drop when include_forming=True.
    last_closed_ts = now_ms - (now_ms % step_ms) - step_ms
    def _ist_str(ts_ms: int) -> str:
        return datetime.fromtimestamp(ts_ms / 1000, tz=IST).strftime("%Y-%m-%d %H:%M:%S+0530")

    rows = []
    for i in range(n):
        ts_ms = last_closed_ts - (n - 1 - i) * step_ms
        rows.append([_ist_str(ts_ms), float(open_[i]), float(high[i]), float(low[i]), float(close[i]), float(volume[i])])
    if include_forming:
        forming_ts = last_closed_ts + step_ms
        rows.append([_ist_str(forming_ts), float(close[-1]), float(close[-1] + 1), float(close[-1] - 1), float(close[-1] + 0.5), 500.0])
    return rows


class FakeKiteClient:
    def __init__(self, candle_rows):
        self.candle_rows = candle_rows
        self.calls: list[tuple] = []

    async def get_historical(self, token, interval, frm, to, continuous=False, oi=False):
        self.calls.append((token, interval, frm, to))
        return {"candles": self.candle_rows}


class TestRunNavigatorPass:
    @pytest.mark.asyncio
    async def test_disabled_config_makes_zero_candle_fetch_calls(self):
        client = FakeKiteClient(_kite_candle_rows())
        await nav_service.run_navigator_pass(
            client, "user-1", [_row()], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_enabled_config_fetches_and_caches_a_decision(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        client = FakeKiteClient(_kite_candle_rows())
        row = _row()
        await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert len(client.calls) == 1
        cached = nav_service.get_cached_decision("user-1", underlying=row.underlying, token=row.token, direction=row.direction)
        assert cached is not None

    @pytest.mark.asyncio
    async def test_drops_the_still_forming_bar(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        with_forming = FakeKiteClient(_kite_candle_rows(include_forming=True))
        without_forming = FakeKiteClient(_kite_candle_rows(include_forming=False))
        row = _row()

        candles_with = await nav_service._fetch_candles_for_navigator(with_forming, row.token)
        candles_without = await nav_service._fetch_candles_for_navigator(without_forming, row.token)
        # dropping the forming bar from the "with" series should land on
        # exactly the same closed-bar count as the series that never had one
        assert len(candles_with) == len(candles_without)

    @pytest.mark.asyncio
    async def test_only_evaluates_configured_underlyings(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        client = FakeKiteClient(_kite_candle_rows())
        row = _row(underlying="NIFTY BANK", token=260105)
        await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert client.calls == []  # NIFTY BANK not in the configured underlyings

    @pytest.mark.asyncio
    async def test_dedupes_by_underlying_token_direction(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        client = FakeKiteClient(_kite_candle_rows())
        rows = [_row(), _row()]  # identical underlying/token/direction twice
        await nav_service.run_navigator_pass(
            client, "user-1", rows, engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert len(client.calls) == 1

    @pytest.mark.asyncio
    async def test_stale_rows_are_skipped_entirely(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        client = FakeKiteClient(_kite_candle_rows())
        row = _row(is_active=False, is_fresh=False)
        await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_derivatives_row_fetches_the_underlyings_own_token_not_the_contract_token(self):
        """A pure `source="derivatives"` row's `token` is the option CONTRACT's
        own instrument token — a fresh weekly listing with only days of price
        history. AVWAP/Volatility read the underlying's price STRUCTURE, so
        when `underlying_tokens` resolves "NIFTY 50" to its real spot token,
        the candle fetch must go against that (deep, continuous) history —
        never the short-lived contract token — even though the cache key
        still identifies the row by its own contract token."""
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        underlying_spot_token = 256265
        contract_token = 9988776
        client = FakeKiteClient(_kite_candle_rows())
        row = _row(token=contract_token, source="derivatives")
        await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
            underlying_tokens={"NIFTY 50": underlying_spot_token},
        )
        assert len(client.calls) == 1
        fetched_token = client.calls[0][0]
        assert fetched_token == underlying_spot_token
        assert fetched_token != contract_token
        # cache identity is still the row's own (contract) token
        cached = nav_service.get_cached_decision("user-1", underlying="NIFTY 50", token=contract_token, direction="long")
        assert cached is not None

    @pytest.mark.asyncio
    async def test_no_underlying_tokens_map_falls_back_to_row_token(self):
        """Omitting `underlying_tokens` entirely (or the underlying missing
        from it) must reproduce the exact prior behaviour — fetch against
        `row.token` — so existing callers/tests are unaffected."""
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save("user-1", rec.config.model_copy(update={"enabled": True}), expected_revision=rec.revision, default_underlyings=_UNDERLYINGS)

        client = FakeKiteClient(_kite_candle_rows())
        row = _row()
        await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert client.calls[0][0] == row.token

    @pytest.mark.asyncio
    async def test_a_broken_row_does_not_stop_the_rest_of_the_pass(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        config_store.save(
            "user-1", rec.config.model_copy(update={"enabled": True, "underlyings": ["NIFTY 50", "NIFTY BANK"]}),
            expected_revision=rec.revision, default_underlyings=_UNDERLYINGS,
        )

        class FlakyClient(FakeKiteClient):
            async def get_historical(self, token, interval, frm, to, continuous=False, oi=False):
                self.calls.append((token, interval, frm, to))
                if token == 111:
                    raise RuntimeError("broker hiccup")
                return {"candles": self.candle_rows}

        client = FlakyClient(_kite_candle_rows())
        rows = [_row(underlying="NIFTY 50", token=111), _row(underlying="NIFTY BANK", token=260105)]
        # should not raise despite the first row's fetch failing
        await nav_service.run_navigator_pass(
            client, "user-1", rows, engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
        )
        assert len(client.calls) == 2
        good_decision = nav_service.get_cached_decision("user-1", underlying="NIFTY BANK", token=260105, direction="long")
        assert good_decision is not None


def _decision(status="CONFIRMED", direction="long", base_signal_id="navigator_origin_test:long") -> NavigatorDecision:
    eligible = status in ("CONFIRMED", "HIGH_CONVICTION")
    return NavigatorDecision(
        decision_id=f"nav_test_{status}_{direction}", config_revision=1, model_versions={},
        generated_at_ms=1_700_000_000_000, bar_close_ms=1_700_000_000_000, activation_watermark_ms=0,
        base_signal_id=base_signal_id, trigger="avwap_fresh", direction=direction, status=status,
        base_score=50.0, suite_score=90.0 if eligible else None, effective_score=90.0 if eligible else None,
        execution_eligible=eligible, data_quality="ok", reason_codes=["OK"],
    )


def _accepted_avwap_eval(stop=24000.0, target=24800.0):
    grade = AvwapGradeResult(grade="A", score=80.0, components={})
    proposal = StopTargetProposal(accepted=True, stop=stop, target=target, risk_points=200.0)
    return AvwapEvaluation(family="PULLBACK_LONG", direction=1, grade=grade, stop_target=proposal, warming_up=False)


def _rejected_avwap_eval():
    grade = AvwapGradeResult(grade="none", score=0.0, components={})
    return AvwapEvaluation(family=None, direction=0, grade=grade, stop_target=None, warming_up=False)


def _enable_with(rec, **updates):
    return config_store.save(
        "user-1", rec.config.model_copy(update={"enabled": True, **updates}),
        expected_revision=rec.revision, default_underlyings=_UNDERLYINGS,
    )


def _fake_evaluate_and_cache(long_status: str, short_status: str = "WATCH"):
    """Fake `evaluate_and_cache` that discriminates by `base.direction`, so a
    test can assert exactly which direction's origination row (if any) got
    appended, instead of both long AND short firing identically."""
    def _fake(uid, row, *, base, **kw):
        return _decision(long_status if base.direction == "long" else short_status, direction=base.direction)
    return _fake


class TestStructureRadarAndOrigination:
    """2026-07-28 structure-radar/origination design: Navigator can compute
    (and, opt-in, surface) evidence for an underlying+direction with NO real
    SuperTrend row at all. All three settings default off — every test here
    explicitly turns them on."""

    @pytest.mark.asyncio
    async def test_off_by_default_never_fetches_beyond_real_rows(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec)  # structure_radar_enabled/signal_origination stay default-off
        client = FakeKiteClient(_kite_candle_rows())
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        assert client.calls == []
        assert out == []

    @pytest.mark.asyncio
    async def test_radar_computes_both_directions_with_no_real_row(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, structure_radar_enabled=True)
        client = FakeKiteClient(_kite_candle_rows())
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        # one candle fetch per underlying, shared by both directions' evaluation
        assert len(client.calls) == 1
        assert nav_service.get_cached_decision("user-1", underlying="NIFTY 50", token=256265, direction="long") is not None
        assert nav_service.get_cached_decision("user-1", underlying="NIFTY 50", token=256265, direction="short") is not None
        # radar alone never adds a signal-table row
        assert out == []

    @pytest.mark.asyncio
    async def test_real_fresh_row_suppresses_radar_for_that_direction_only(self):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, structure_radar_enabled=True)
        client = FakeKiteClient(_kite_candle_rows())
        row = _row(direction="long")  # real, live long row for NIFTY 50
        out = await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        # 1 fetch for the real long row + 1 radar fetch for short — long is NOT double-fetched
        assert len(client.calls) == 2
        assert len(out) == 1  # no new row appended (radar-only)

    @pytest.mark.asyncio
    async def test_include_origination_false_confirms_rows_but_never_originates(self, monkeypatch):
        """Origination has exactly one owner: Navigator's own runtime loop.

        The Kite engine's scan calls this with `include_origination=False` so
        it gets the confirmation half only. If that flag ever stopped being
        honoured, both loops would originate — doubling the candle fetches and,
        once calibration is promoted, letting the same originated setup be
        ordered twice."""
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, structure_radar_enabled=True, signal_origination="full")
        evaluated: list[str] = []
        inner = _fake_evaluate_and_cache("CONFIRMED", "CONFIRMED")

        def _recording(uid, row, *, base, **kw):
            evaluated.append(base.direction)
            return inner(uid, row, base=base, **kw)

        monkeypatch.setattr(nav_service, "evaluate_and_cache", _recording)
        client = FakeKiteClient(_kite_candle_rows())
        row = _row(direction="long")
        out = await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
            include_origination=False,
        )
        assert len(out) == 1              # the real row only — nothing originated
        assert out[0] is row
        assert len(client.calls) == 1     # no radar fetch for the opposite direction
        # confirmation still ran for the real row, and ONLY for it
        assert evaluated == ["long"]

    @pytest.mark.asyncio
    async def test_origination_off_never_appends_a_row_even_when_confirmed(self, monkeypatch):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, structure_radar_enabled=True, signal_origination="off")
        monkeypatch.setattr(nav_service, "evaluate_and_cache", _fake_evaluate_and_cache("CONFIRMED"))
        client = FakeKiteClient(_kite_candle_rows())
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        assert out == []

    @pytest.mark.asyncio
    async def test_watch_status_never_appends_a_row(self, monkeypatch):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, signal_origination="heads_up")
        monkeypatch.setattr(nav_service, "evaluate_and_cache", _fake_evaluate_and_cache("WATCH", "WATCH"))
        monkeypatch.setattr(avwap, "evaluate_avwap", lambda candles, config, **kw: (None, _accepted_avwap_eval()))
        client = FakeKiteClient(_kite_candle_rows())
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        assert out == []

    @pytest.mark.asyncio
    async def test_no_stop_target_proposal_suppresses_the_row_even_when_confirmed(self, monkeypatch):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, signal_origination="heads_up")
        monkeypatch.setattr(nav_service, "evaluate_and_cache", _fake_evaluate_and_cache("CONFIRMED"))
        monkeypatch.setattr(avwap, "evaluate_avwap", lambda candles, config, **kw: (None, _rejected_avwap_eval()))
        client = FakeKiteClient(_kite_candle_rows())
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        assert out == []

    @pytest.mark.asyncio
    async def test_heads_up_appends_a_row_with_no_legs(self, monkeypatch):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, signal_origination="heads_up")
        monkeypatch.setattr(nav_service, "evaluate_and_cache", _fake_evaluate_and_cache("CONFIRMED"))
        monkeypatch.setattr(avwap, "evaluate_avwap", lambda candles, config, **kw: (None, _accepted_avwap_eval(stop=24000.0)))
        client = FakeKiteClient(_kite_candle_rows())
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        origin_rows = [r for r in out if r.source == "navigator"]
        assert len(origin_rows) == 1
        assert origin_rows[0].legs == []
        assert origin_rows[0].stop_loss == 24000.0
        assert origin_rows[0].navigator is not None
        assert origin_rows[0].navigator.status == "CONFIRMED"

    @pytest.mark.asyncio
    async def test_radar_covers_stocks_not_just_indices(self, monkeypatch):
        """Peer-engine change: Navigator's universe is whatever the caller
        resolved (shared with the engine, or its own), so a STOCK in that map
        must get the same radar treatment an index does. Before this,
        coverage was hard-limited to `config.underlyings` — an indices-only
        list — so stocks were silently invisible to Navigator."""
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, structure_radar_enabled=True)
        client = FakeKiteClient(_kite_candle_rows())
        await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
            underlying_tokens={"NIFTY 50": 256265, "RELIANCE": 738561},
        )
        # one candle fetch per underlying in the resolved universe
        assert sorted(c[0] for c in client.calls) == [256265, 738561]
        assert nav_service.get_cached_decision(
            "user-1", underlying="RELIANCE", token=738561, direction="long") is not None

    @pytest.mark.asyncio
    async def test_row_outside_navigators_universe_is_skipped(self):
        """Custom scope: a SuperTrend row for an instrument Navigator doesn't
        cover gets no opinion — Navigator has no evidence there to form one
        from, so it must not fabricate a decision."""
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, scan_scope_mode="custom", scan_stocks=["RELIANCE"])
        client = FakeKiteClient(_kite_candle_rows())
        row = _row(underlying="NIFTY 50", token=256265)
        await nav_service.run_navigator_pass(
            client, "user-1", [row], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS,
            underlying_tokens={"RELIANCE": 738561},  # NIFTY 50 not covered
        )
        assert client.calls == []

    @pytest.mark.asyncio
    async def test_full_mode_without_universe_still_appends_a_row_with_no_legs(self, monkeypatch):
        rec = config_store.get("user-1", default_underlyings=_UNDERLYINGS)
        _enable_with(rec, signal_origination="full")
        monkeypatch.setattr(nav_service, "evaluate_and_cache", _fake_evaluate_and_cache("HIGH_CONVICTION"))
        monkeypatch.setattr(avwap, "evaluate_avwap", lambda candles, config, **kw: (None, _accepted_avwap_eval()))
        client = FakeKiteClient(_kite_candle_rows())
        # universe/nfo_rows/bfo_rows all omitted — leg resolution degrades gracefully
        out = await nav_service.run_navigator_pass(
            client, "user-1", [], engine_config_payload={"trail_target": "fast"},
            default_underlyings=_UNDERLYINGS, underlying_tokens={"NIFTY 50": 256265},
        )
        origin_rows = [r for r in out if r.source == "navigator"]
        assert len(origin_rows) == 1
        assert origin_rows[0].legs == []
