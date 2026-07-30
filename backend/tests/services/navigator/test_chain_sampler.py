from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from app.services.navigator.chain_sampler import (
    ChainSamplerCoordinator,
    backoff_seconds,
    compute_counter_delta,
    evaluate_chain_sample,
    parse_quote_row,
)
from app.services.navigator.instrument_slice import OptionInstrument, OptionInstrumentSlice

_INST = OptionInstrument(
    tradingsymbol="NIFTY26AUG24500CE", exchange="NFO", strike=24500.0, option_type="CE",
    expiry="2026-08-06", token=111, lot_size=75, tick_size=0.05,
)


def _slice(contracts=None, expected=2):
    contracts = contracts if contracts is not None else [_INST]
    return OptionInstrumentSlice(
        underlying="NIFTY", exchange="NFO", expiry="2026-08-06", atm_strike=24500.0,
        strike_step=100.0, contracts=contracts, expected_contract_count=expected, found_contract_count=len(contracts),
    )


class TestParseQuoteRow:
    def test_ok_quote_computes_mid_from_depth(self):
        raw = {"depth": {"buy": [{"price": 100.0}], "sell": [{"price": 101.0}]}, "last_price": 100.5, "oi": 1000, "volume": 5000}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.mid == pytest.approx(100.5)
        assert snap.quote_quality == "ok"
        assert snap.open_interest == 1000
        assert snap.cumulative_volume == 5000

    def test_crossed_quote_is_flagged(self):
        raw = {"depth": {"buy": [{"price": 105.0}], "sell": [{"price": 100.0}]}, "last_price": 102.0}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.quote_quality == "crossed"

    def test_wide_spread_is_flagged(self):
        raw = {"depth": {"buy": [{"price": 90.0}], "sell": [{"price": 110.0}]}, "last_price": 100.0}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.05)
        assert snap.quote_quality == "wide"

    def test_no_depth_and_zero_ltp_is_incomplete(self):
        raw = {"depth": {}, "last_price": 0}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.quote_quality == "incomplete"

    def test_falls_back_to_ltp_when_no_depth(self):
        raw = {"depth": {}, "last_price": 55.5}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.mid == pytest.approx(55.5)

    def test_missing_iv_is_none_not_zero(self):
        raw = {"depth": {}, "last_price": 50.0}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.implied_volatility is None

    def test_exchange_timestamp_parsed_when_present(self):
        raw = {"depth": {}, "last_price": 50.0, "timestamp": "2026-07-27 10:15:00"}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.exchange_timestamp_ms is not None

    def test_exchange_timestamp_is_none_when_absent(self):
        raw = {"depth": {}, "last_price": 50.0}
        snap = parse_quote_row(_INST, raw, received_at_ms=1000, max_spread_pct=0.08)
        assert snap.exchange_timestamp_ms is None


class TestEvaluateChainSample:
    def test_full_fresh_chain_is_ok(self):
        snap = parse_quote_row(_INST, {"depth": {"buy": [{"price": 100}], "sell": [{"price": 101}]}, "last_price": 100.5}, received_at_ms=1000, max_spread_pct=0.08)
        result = evaluate_chain_sample(_slice([_INST], expected=1), [snap], now_ms=1000, max_quote_age_seconds=20, min_chain_completeness=0.8)
        assert result.quality == "ok"
        assert result.completeness == 1.0

    def test_empty_chain_is_unavailable(self):
        result = evaluate_chain_sample(_slice([], expected=0), [], now_ms=1000, max_quote_age_seconds=20, min_chain_completeness=0.8)
        assert result.quality == "unavailable"

    def test_incomplete_chain_is_degraded(self):
        snap = parse_quote_row(_INST, {"depth": {}, "last_price": 50.0}, received_at_ms=1000, max_spread_pct=0.08)
        result = evaluate_chain_sample(_slice([_INST], expected=4), [snap], now_ms=1000, max_quote_age_seconds=20, min_chain_completeness=0.8)
        assert result.quality == "degraded"  # 1/4 = 0.25 completeness

    def test_stale_quote_is_degraded(self):
        snap = parse_quote_row(_INST, {"depth": {}, "last_price": 50.0}, received_at_ms=1000, max_spread_pct=0.08)
        result = evaluate_chain_sample(_slice([_INST], expected=1), [snap], now_ms=1000 + 30_000, max_quote_age_seconds=20, min_chain_completeness=0.8)
        assert result.quality == "degraded"
        assert result.stale_count == 1


class TestCounterDelta:
    def _snap(self, token=111, expiry="2026-08-06", cum_vol=5000, oi=1000, received_at_ms=2000):
        inst = OptionInstrument(tradingsymbol="X", exchange="NFO", strike=24500.0, option_type="CE", expiry=expiry, token=token, lot_size=75, tick_size=0.05)
        return SimpleNamespace(instrument=inst, cumulative_volume=cum_vol, open_interest=oi, received_at_ms=received_at_ms)

    def test_first_sample_is_warmup(self):
        result = compute_counter_delta(None, self._snap(), max_sample_gap_seconds=150, prev_session_date=None, curr_session_date=date(2026, 7, 27))
        assert result.valid is False and result.reset_reason == "warmup"

    def test_normal_delta_is_valid(self):
        prev = dict(instrument_token=111, expiry="2026-08-06", cumulative_volume=4000, open_interest=900, received_at_ms=1000)
        curr = self._snap(cum_vol=4500, oi=950, received_at_ms=1060_000)
        result = compute_counter_delta(prev, curr, max_sample_gap_seconds=150, prev_session_date=date(2026, 7, 27), curr_session_date=date(2026, 7, 27))
        # gap here is huge on purpose below; use a tight gap instead
        prev2 = dict(instrument_token=111, expiry="2026-08-06", cumulative_volume=4000, open_interest=900, received_at_ms=1000)
        curr2 = self._snap(cum_vol=4500, oi=950, received_at_ms=61_000)
        result2 = compute_counter_delta(prev2, curr2, max_sample_gap_seconds=150, prev_session_date=date(2026, 7, 27), curr_session_date=date(2026, 7, 27))
        assert result2.valid is True
        assert result2.delta_volume == 500
        assert result2.delta_oi == 50

    def test_session_reset_invalidates(self):
        prev = dict(instrument_token=111, expiry="2026-08-06", cumulative_volume=4000, open_interest=900, received_at_ms=1000)
        curr = self._snap(received_at_ms=61_000)
        result = compute_counter_delta(prev, curr, max_sample_gap_seconds=150, prev_session_date=date(2026, 7, 27), curr_session_date=date(2026, 7, 28))
        assert result.valid is False and result.reset_reason == "session_reset"

    def test_instrument_rollover_invalidates(self):
        prev = dict(instrument_token=999, expiry="2026-08-06", cumulative_volume=4000, open_interest=900, received_at_ms=1000)
        curr = self._snap(token=111, received_at_ms=61_000)
        result = compute_counter_delta(prev, curr, max_sample_gap_seconds=150, prev_session_date=date(2026, 7, 27), curr_session_date=date(2026, 7, 27))
        assert result.valid is False and result.reset_reason == "instrument_rollover"

    def test_large_gap_invalidates(self):
        prev = dict(instrument_token=111, expiry="2026-08-06", cumulative_volume=4000, open_interest=900, received_at_ms=1000)
        curr = self._snap(received_at_ms=1000 + 300_000)
        result = compute_counter_delta(prev, curr, max_sample_gap_seconds=150, prev_session_date=date(2026, 7, 27), curr_session_date=date(2026, 7, 27))
        assert result.valid is False and result.reset_reason == "sample_gap"

    def test_negative_volume_delta_invalidates_not_clamped(self):
        prev = dict(instrument_token=111, expiry="2026-08-06", cumulative_volume=9000, open_interest=900, received_at_ms=1000)
        curr = self._snap(cum_vol=4000, received_at_ms=61_000)
        result = compute_counter_delta(prev, curr, max_sample_gap_seconds=150, prev_session_date=date(2026, 7, 27), curr_session_date=date(2026, 7, 27))
        assert result.valid is False and result.reset_reason == "negative_volume_delta"
        assert result.delta_volume is None  # never a synthetic clamp to zero


class TestBackoff:
    def test_non_rate_limited_is_short(self):
        assert backoff_seconds(1, is_rate_limited=False) == 0.5

    def test_rate_limited_grows_and_caps(self):
        s0 = backoff_seconds(0, is_rate_limited=True, jitter=0.0)
        s3 = backoff_seconds(3, is_rate_limited=True, jitter=0.0)
        s10 = backoff_seconds(10, is_rate_limited=True, jitter=0.0)
        assert s0 < s3 <= 8.0
        assert s10 == 8.0  # capped


class TestChainSamplerCoordinator:
    @pytest.mark.asyncio
    async def test_sample_once_calls_quote_fetcher_with_one_batch(self):
        calls = []

        async def quote_fetcher(symbols):
            calls.append(symbols)
            return {"NFO:NIFTY26AUG24500CE": {"depth": {"buy": [{"price": 100}], "sell": [{"price": 101}]}, "last_price": 100.5}}

        class FakeIndex:
            async def option_slice(self, **kwargs):
                return _slice([_INST], expected=1)

        coordinator = ChainSamplerCoordinator(quote_fetcher=quote_fetcher, instrument_index=FakeIndex(), on_sample=None, now_ms=lambda: 12345)
        config = SimpleNamespace(mode="dynamic", dynamic_strike_radius=2, broad_strike_radius=5, strike_step_override=None, max_spread_pct=0.08, max_quote_age_seconds=20, min_chain_completeness=0.8, flow_sample_seconds=1)

        async def spot_provider():
            return 24500.0

        slice_, result = await coordinator.sample_once(account_scope="acct1", underlying="NIFTY", exchange="NFO", expiry="2026-08-06", spot_provider=spot_provider, config=config)
        assert len(calls) == 1
        assert calls[0] == ["NFO:NIFTY26AUG24500CE"]
        assert result.quality == "ok"

    @pytest.mark.asyncio
    async def test_shared_poller_is_not_duplicated(self):
        async def quote_fetcher(symbols):
            return {}

        class FakeIndex:
            async def option_slice(self, **kwargs):
                return _slice([], expected=0)

        sampled = []

        async def on_sample(key, slice_, result, now_ms):
            sampled.append(key)

        coordinator = ChainSamplerCoordinator(quote_fetcher=quote_fetcher, instrument_index=FakeIndex(), on_sample=on_sample)
        config = SimpleNamespace(mode="dynamic", dynamic_strike_radius=2, broad_strike_radius=5, strike_step_override=None, max_spread_pct=0.08, max_quote_age_seconds=20, min_chain_completeness=0.8, flow_sample_seconds=60)

        async def spot_provider():
            return 24500.0

        coordinator.ensure_started(account_scope="acct1", underlying="NIFTY", exchange="NFO", expiry="2026-08-06", spot_provider=spot_provider, config=config)
        coordinator.ensure_started(account_scope="acct1", underlying="NIFTY", exchange="NFO", expiry="2026-08-06", spot_provider=spot_provider, config=config)
        assert len(coordinator._tasks) == 1
        await asyncio.sleep(0.05)
        await coordinator.stop_all()
        assert len(sampled) >= 1

    @pytest.mark.asyncio
    async def test_rebind_moves_running_pollers_onto_a_fresh_client(self):
        """A coordinator outlives the client it was built from.

        When a Kite session expires the cached client is closed and rebuilt on
        re-login. Without rebinding, the already-running pollers keep calling
        the dead one and flow/gamma go permanently unavailable with nothing
        visible to the user. Restarting the tasks is not an option — they hold
        the per-contract counter state OI/volume deltas depend on."""
        dead_calls, live_calls, sampled = [], [], []

        async def dead_fetcher(symbols):
            dead_calls.append(symbols)
            raise RuntimeError("client is closed")

        async def live_fetcher(symbols):
            live_calls.append(symbols)
            return {}

        class FakeIndex:
            async def option_slice(self, **kwargs):
                return _slice([], expected=0)

        async def on_sample(key, slice_, result, now_ms):
            sampled.append("v1")

        async def on_sample_v2(key, slice_, result, now_ms):
            sampled.append("v2")

        coordinator = ChainSamplerCoordinator(
            quote_fetcher=dead_fetcher, instrument_index=FakeIndex(), on_sample=on_sample)
        config = SimpleNamespace(mode="dynamic", dynamic_strike_radius=2, broad_strike_radius=5, strike_step_override=None, max_spread_pct=0.08, max_quote_age_seconds=20, min_chain_completeness=0.8, flow_sample_seconds=60)

        async def spot_provider():
            return 24500.0

        coordinator.ensure_started(account_scope="acct1", underlying="NIFTY", exchange="NFO", expiry="2026-08-06", spot_provider=spot_provider, config=config)
        task = coordinator._tasks[("acct1", "NIFTY", "2026-08-06")]

        coordinator.rebind(
            quote_fetcher=live_fetcher, instrument_index=FakeIndex(), on_sample=on_sample_v2)
        await asyncio.sleep(0.05)
        await coordinator.stop_all()

        # same poll loop, now talking to the live client and the current sink
        assert coordinator._tasks == {}
        assert task.done()
        assert sampled and set(sampled) == {"v2"}

    @pytest.mark.asyncio
    async def test_stop_all_cancels_running_tasks(self):
        async def quote_fetcher(symbols):
            return {}

        class FakeIndex:
            async def option_slice(self, **kwargs):
                return _slice([], expected=0)

        async def on_sample(key, slice_, result, now_ms):
            pass

        coordinator = ChainSamplerCoordinator(quote_fetcher=quote_fetcher, instrument_index=FakeIndex(), on_sample=on_sample)
        config = SimpleNamespace(mode="dynamic", dynamic_strike_radius=2, broad_strike_radius=5, strike_step_override=None, max_spread_pct=0.08, max_quote_age_seconds=20, min_chain_completeness=0.8, flow_sample_seconds=60)

        async def spot_provider():
            return 24500.0

        coordinator.ensure_started(account_scope="acct1", underlying="NIFTY", exchange="NFO", expiry="2026-08-06", spot_provider=spot_provider, config=config)
        await asyncio.sleep(0.02)
        await coordinator.stop_all()
        assert coordinator._tasks == {}

    @pytest.mark.asyncio
    async def test_error_triggers_backoff_not_a_crash(self):
        attempts = {"n": 0}

        async def quote_fetcher(symbols):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise RuntimeError("transient network error")
            return {}

        class FakeIndex:
            async def option_slice(self, **kwargs):
                return _slice([_INST], expected=1)

        sampled = []

        async def on_sample(key, slice_, result, now_ms):
            sampled.append(result)

        coordinator = ChainSamplerCoordinator(quote_fetcher=quote_fetcher, instrument_index=FakeIndex(), on_sample=on_sample)
        config = SimpleNamespace(mode="dynamic", dynamic_strike_radius=2, broad_strike_radius=5, strike_step_override=None, max_spread_pct=0.08, max_quote_age_seconds=20, min_chain_completeness=0.8, flow_sample_seconds=60)

        async def spot_provider():
            return 24500.0

        coordinator.ensure_started(account_scope="acct1", underlying="NIFTY", exchange="NFO", expiry="2026-08-06", spot_provider=spot_provider, config=config)
        await asyncio.sleep(0.6)  # long enough for the fast (non-rate-limited attempt#... ) retry to land
        await coordinator.stop_all()
        assert attempts["n"] >= 2
