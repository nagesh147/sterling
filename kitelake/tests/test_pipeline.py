"""The tick pipeline: enrichment correctness, hot reads, backpressure honesty, durability.

No sockets and no credentials — ticks are synthesised in the shape kiteconnect delivers
them, so the whole path from ``submit()`` to parquet is exercised deterministically.
"""

from __future__ import annotations

import math
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pytest

from kitelake.config import IST
from kitelake.hotstore import HotQuote, HotStore
from kitelake.pipeline import InstrumentRef, TickPipeline, build_refs

SPOT_TOKEN = 256265
CE_TOKEN = 111111
PE_TOKEN = 222222
STRIKE = 24500.0


def _master(expiry: date) -> pa.Table:
    from kitelake.instruments import INSTRUMENT_SCHEMA

    return pa.table(
        {
            "instrument_token": [SPOT_TOKEN, CE_TOKEN, PE_TOKEN],
            "exchange_token": [1, 2, 3],
            "tradingsymbol": ["NIFTY 50", "NIFTY26AUG24500CE", "NIFTY26AUG24500PE"],
            "name": ["NIFTY", "NIFTY", "NIFTY"],
            "last_price": [0.0] * 3,
            "expiry": [None, expiry, expiry],
            "strike": [0.0, STRIKE, STRIKE],
            "tick_size": [0.05] * 3,
            "lot_size": [0, 75, 75],
            "instrument_type": ["EQ", "CE", "PE"],
            "segment": ["INDICES", "NFO-OPT", "NFO-OPT"],
            "exchange": ["NSE", "NFO", "NFO"],
        },
        schema=INSTRUMENT_SCHEMA,
    )


@pytest.fixture
def refs(lake: Path) -> dict[int, InstrumentRef]:
    from kitelake.instruments import write_instrument_master

    expiry = date.today() + timedelta(days=7)
    write_instrument_master(_master(expiry))
    return build_refs([SPOT_TOKEN, CE_TOKEN, PE_TOKEN])


def tick(token: int, price: float, *, bid: float | None = None, ask: float | None = None,
         oi: int = 0) -> dict[str, Any]:
    return {
        "instrument_token": token,
        "last_price": price,
        "oi": oi,
        "last_traded_quantity": 50,
        "volume_traded": 1000,
        # kiteconnect delivers naive IST datetimes.
        "exchange_timestamp": datetime.now(IST).replace(tzinfo=None),
        "depth": {
            "buy": [{"price": bid if bid is not None else price - 0.5, "quantity": 100}],
            "sell": [{"price": ask if ask is not None else price + 0.5, "quantity": 120}],
        },
    }


def drain(pipe: TickPipeline, expected: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while pipe.stats.processed < expected and time.monotonic() < deadline:
        time.sleep(0.01)


class TestSpotWiring:
    def test_options_resolve_to_their_underlying(self, refs) -> None:
        assert refs[CE_TOKEN].spot_token == SPOT_TOKEN
        assert refs[PE_TOKEN].spot_token == SPOT_TOKEN

    def test_the_underlying_itself_has_no_spot_token(self, refs) -> None:
        assert refs[SPOT_TOKEN].spot_token == 0
        assert refs[SPOT_TOKEN].is_option is False

    def test_index_beats_a_same_named_equity(self, lake: Path) -> None:
        """NIFTY options price off the NIFTY 50 index, not a stock that shares the name."""
        from kitelake.instruments import INSTRUMENT_SCHEMA, write_instrument_master

        expiry = date.today() + timedelta(days=7)
        rows = _master(expiry).to_pylist()
        rows.append({
            "instrument_token": 999999, "exchange_token": 9, "tradingsymbol": "NIFTY",
            "name": "NIFTY", "last_price": 0.0, "expiry": None, "strike": 0.0,
            "tick_size": 0.05, "lot_size": 1, "instrument_type": "EQ",
            "segment": "NSE", "exchange": "NSE",
        })
        write_instrument_master(pa.Table.from_pylist(rows, schema=INSTRUMENT_SCHEMA))
        assert build_refs([CE_TOKEN])[CE_TOKEN].spot_token == SPOT_TOKEN


class TestDte:
    def test_measured_to_the_close_not_midnight(self) -> None:
        ref = InstrumentRef(1, "X", "NFO", "CE", STRIKE, date(2026, 8, 20))
        now = datetime(2026, 8, 19, 15, 30, tzinfo=IST)
        assert ref.dte_days(now) == pytest.approx(1.0, abs=1e-6)

    def test_expiry_day_still_has_time_left(self) -> None:
        """0.0 would collapse the model to intrinsic and report every greek as flat."""
        ref = InstrumentRef(1, "X", "NFO", "CE", STRIKE, date(2026, 8, 20))
        morning = datetime(2026, 8, 20, 9, 15, tzinfo=IST)
        assert 0 < ref.dte_days(morning) < 0.3

    def test_never_negative_after_expiry(self) -> None:
        ref = InstrumentRef(1, "X", "NFO", "CE", STRIKE, date(2026, 8, 20))
        assert ref.dte_days(datetime(2026, 9, 1, tzinfo=IST)) == 0.0


class TestEnrichment:
    def test_option_without_a_spot_is_left_unpriced(self, refs) -> None:
        """A greek computed against a zero spot is confidently wrong — worse than missing."""
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.submit([tick(CE_TOKEN, 156.0)])
            drain(pipe, 1)
            quote = pipe.hot.get(CE_TOKEN)
            assert quote is not None
            assert quote.iv is None and quote.delta is None
            assert pipe.stats.unpriced_no_spot == 1
            assert pipe.stats.priced == 0
        finally:
            pipe.stop()

    def test_greeks_appear_once_the_spot_is_known(self, refs) -> None:
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
            pipe.submit([tick(CE_TOKEN, 156.28)])
            drain(pipe, 1)
            q = pipe.hot.get(CE_TOKEN)
            assert q.iv is not None and q.iv > 0
            assert 0 < q.delta < 1, "a slightly OTM call sits between 0 and 1"
            assert q.gamma > 0
            assert q.theta < 0, "long options decay"
            assert q.vega > 0
            assert q.spot_used == 24400.0, "must record what it priced against"
            assert q.greeks_solved is True
        finally:
            pipe.stop()

    def test_call_and_put_deltas_obey_parity(self, refs) -> None:
        """delta_call - delta_put == 1 for the same strike and expiry. Catches sign errors."""
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
            # Premiums consistent with one IV, so both should imply the same vol.
            pipe.submit([tick(CE_TOKEN, 156.28), tick(PE_TOKEN, 225.76)])
            drain(pipe, 2)
            ce, pe = pipe.hot.get(CE_TOKEN), pipe.hot.get(PE_TOKEN)
            assert pe.delta < 0 < ce.delta
            assert ce.delta - pe.delta == pytest.approx(1.0, abs=0.02)
            # Same strike/expiry/vol ⇒ identical gamma and vega.
            assert ce.gamma == pytest.approx(pe.gamma, rel=0.05)
            assert ce.vega == pytest.approx(pe.vega, rel=0.05)
        finally:
            pipe.stop()

    def test_mid_is_preferred_over_last_traded(self, refs) -> None:
        """Last-traded can be stale or printed on the far side of a wide option spread."""
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
            # Wide, asymmetric quote: mid (160) is far from last-traded (100).
            pipe.submit([tick(CE_TOKEN, 100.0, bid=150.0, ask=170.0)])
            drain(pipe, 1)
            q = pipe.hot.get(CE_TOKEN)
            from kitelake.greeks_bridge import implied_vol

            # Compare against both candidates rather than reproducing the exact arithmetic:
            # the stored dte_days is rounded for display, so an equality check against a
            # recomputed IV fails on rounding rather than on behaviour.
            iv_from_mid = implied_vol(price=160.0, spot=24400.0, strike=STRIKE,
                                      dte_days=q.dte_days, option_type="CE")
            iv_from_last = implied_vol(price=100.0, spot=24400.0, strike=STRIKE,
                                       dte_days=q.dte_days, option_type="CE")
            assert abs(q.iv - iv_from_mid) < abs(q.iv - iv_from_last) / 100, (
                f"iv {q.iv} should track the mid ({iv_from_mid}), not last-traded ({iv_from_last})"
            )
        finally:
            pipe.stop()

    def test_unsolvable_premium_is_counted_not_faked(self, refs) -> None:
        """Below intrinsic there is no IV; iv must land at 0 and greeks stay absent."""
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 30000.0)  # deep ITM call
            pipe.submit([tick(CE_TOKEN, 1.0, bid=0.5, ask=1.5)])
            drain(pipe, 1)
            q = pipe.hot.get(CE_TOKEN)
            assert q.iv == 0.0
            assert q.delta is None, "no IV means no greeks, not default greeks"
            assert pipe.stats.iv_unsolved == 1
        finally:
            pipe.stop()

    def test_non_options_are_not_priced(self, refs) -> None:
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.submit([tick(SPOT_TOKEN, 24400.0)])
            drain(pipe, 1)
            q = pipe.hot.get(SPOT_TOKEN)
            assert q.iv is None and q.delta is None
            assert pipe.stats.unpriced_no_spot == 0, "an index is not an unpriced option"
        finally:
            pipe.stop()


class TestBackpressure:
    def test_saturation_is_counted_never_silent(self, refs) -> None:
        """Blocking would stall the socket and get us disconnected, so we shed and say so."""
        pipe = TickPipeline(refs, persist=False)  # not started: nothing drains the queue
        pipe.QUEUE_MAX = 2
        import queue as _q

        pipe._queue = _q.Queue(2)
        events: list[dict[str, Any]] = []
        pipe._on_event = events.append
        for _ in range(6):
            pipe.submit([tick(CE_TOKEN, 100.0)])
        assert pipe.stats.received == 6
        assert pipe.stats.dropped > 0, "a full queue must shed, not block forever"
        assert pipe.stats.to_dict()["no_loss"] is False, "loss must be visible in the stats"
        assert any(e.get("event") == "backpressure_drop" for e in events)

    def test_clean_run_reports_no_loss(self, refs) -> None:
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
            for _ in range(50):
                pipe.submit([tick(CE_TOKEN, 156.0)])
            drain(pipe, 50)
            assert pipe.stats.dropped == 0
            assert pipe.stats.to_dict()["no_loss"] is True
        finally:
            pipe.stop()

    def test_a_bad_tick_does_not_kill_the_worker(self, refs) -> None:
        pipe = TickPipeline(refs, persist=False).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
            pipe.submit([{"instrument_token": CE_TOKEN, "last_price": "not-a-number"}])
            pipe.submit([tick(CE_TOKEN, 156.28)])
            drain(pipe, 1)
            assert pipe.hot.get(CE_TOKEN) is not None, "the worker survived and kept going"
        finally:
            pipe.stop()


class TestDurability:
    def test_ticks_land_in_parquet_with_analytics(self, refs, lake: Path) -> None:
        import pyarrow.parquet as pq

        from kitelake.ticks import ENRICHED_TICK_SCHEMA, enriched_tick_path

        pipe = TickPipeline(refs, persist=True).start()
        try:
            pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
            for _ in range(20):
                pipe.submit([tick(CE_TOKEN, 156.28)])
            drain(pipe, 20)
        finally:
            pipe.stop()

        table = pq.read_table(enriched_tick_path(datetime.now(IST).date()))
        assert table.num_rows == 20
        assert [f.name for f in table.schema] == [f.name for f in ENRICHED_TICK_SCHEMA]
        assert table.column("iv").null_count == 0
        assert table.column("spot_used").null_count == 0

    def test_unpriced_rows_store_null_not_zero(self, refs, lake: Path) -> None:
        """Zero would be indistinguishable from a delta that really is zero."""
        import pyarrow.parquet as pq

        from kitelake.ticks import enriched_tick_path

        pipe = TickPipeline(refs, persist=True).start()
        try:
            pipe.submit([tick(CE_TOKEN, 156.0)])  # no spot yet
            drain(pipe, 1)
        finally:
            pipe.stop()
        table = pq.read_table(enriched_tick_path(datetime.now(IST).date()))
        assert table.column("iv").null_count == table.num_rows
        assert table.column("delta").null_count == table.num_rows

    def test_a_failed_flush_keeps_the_rows(self, refs, monkeypatch) -> None:
        """Drive yanked mid-flush must not lose the batch."""
        pipe = TickPipeline(refs, persist=True)
        monkeypatch.setattr(
            pipe, "_write", lambda rows: (_ for _ in ()).throw(OSError("drive gone"))
        )
        pipe.hot.set_spot(SPOT_TOKEN, 24400.0)
        pipe._process(tick(CE_TOKEN, 156.28))
        assert pipe._flush(force=True) == 0
        assert pipe.stats.flush_failures == 1
        assert len(pipe._buffer) == 1, "the row was put back, not dropped"
        assert pipe.stats.persisted == 0


class TestHotStore:
    def test_reads_are_copies(self) -> None:
        hot = HotStore()
        hot.update(HotQuote(instrument_token=1, last_price=100.0))
        first = hot.get(1)
        first.last_price = 999.0
        assert hot.get(1).last_price == 100.0, "a caller must not mutate the store"

    def test_ring_is_bounded(self) -> None:
        hot = HotStore(ring_size=8)
        for i in range(50):
            hot.update(HotQuote(instrument_token=1, last_price=100.0 + i))
        history = hot.history(1)
        assert len(history) == 8, "fixed capacity, or a busy open is an OOM"
        assert history[-1][1] == 149.0, "newest last"
        assert history[0][1] == 142.0, "oldest dropped"

    def test_tick_counter_accumulates(self) -> None:
        hot = HotStore()
        for _ in range(5):
            hot.update(HotQuote(instrument_token=1, last_price=100.0))
        assert hot.get(1).ticks == 5

    def test_spot_of_unknown_token_is_zero_not_an_error(self) -> None:
        assert HotStore().spot(424242) == 0.0

    def test_mid_falls_back_to_last_when_one_sided(self) -> None:
        assert HotQuote(instrument_token=1, last_price=10.0, bid=9.0, ask=0.0).mid == 10.0
        assert HotQuote(instrument_token=1, last_price=10.0, bid=9.0, ask=11.0).mid == 10.0

    def test_snapshot_can_filter_to_priced_only(self) -> None:
        hot = HotStore()
        hot.update(HotQuote(instrument_token=1, last_price=1.0))
        hot.update(HotQuote(instrument_token=2, last_price=2.0, iv=0.2))
        assert [q.instrument_token for q in hot.snapshot(with_greeks_only=True)] == [2]


class TestProcessHandle:
    def test_register_and_clear(self, refs) -> None:
        from kitelake.pipeline import get_pipeline, set_pipeline

        assert get_pipeline() is None
        pipe = TickPipeline(refs, persist=False)
        set_pipeline(pipe)
        try:
            assert get_pipeline() is pipe
        finally:
            set_pipeline(None)
        assert get_pipeline() is None
