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
