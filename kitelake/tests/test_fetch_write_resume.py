"""Fetching, rate limiting, writing, and resume — the paths where bugs cost data.

Everything here runs against ``httpx.MockTransport``: no network, no credentials.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from kitelake.config import Credentials
from kitelake.fetcher import (
    KitelakeInstrumentRejected,
    KiteHistoricalFetcher,
    KitelakeAuthError,
    KitelakeInputError,
    KitelakePermissionError,
)
from kitelake.ratelimit import AdaptiveLimiter, PacedRateLimiter

CREDS = Credentials("test_key", "test_token")


def _ok(n: int = 3) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "candles": [
                [f"2026-02-03T09:{15 + i:02d}:00+0530", 1.0, 2.0, 0.5, 1.5, 100 + i]
                for i in range(n)
            ]
        },
    }


def _err(message: str, error_type: str) -> dict[str, Any]:
    return {"status": "error", "message": message, "data": None, "error_type": error_type}


# ─── rate limiting ───────────────────────────────────────────────────────────
class TestPacing:
    @pytest.mark.asyncio
    async def test_no_second_window_exceeds_the_cap(self) -> None:
        """The property a token bucket violates: <= 3 grants in ANY 1s window."""
        stamps: list[float] = []
        limiter = PacedRateLimiter(2.5)

        async def one() -> None:
            await limiter.acquire()
            stamps.append(time.perf_counter())

        await asyncio.gather(*[one() for _ in range(20)])
        worst = max(sum(1 for s in stamps if t <= s < t + 1.0) for t in stamps)
        assert worst <= 3, f"{worst} grants landed inside one second"

    @pytest.mark.asyncio
    async def test_idle_then_burst_does_not_bank_credit(self) -> None:
        """A bucket banks a token while idle and then emits rate+1. Pacing must not."""
        stamps: list[float] = []
        limiter = PacedRateLimiter(2.5)

        async def one() -> None:
            await limiter.acquire()
            stamps.append(time.perf_counter())

        await one()
        await asyncio.sleep(1.2)
        await asyncio.gather(*[one() for _ in range(8)])
        worst = max(sum(1 for s in stamps if t <= s < t + 1.0) for t in stamps)
        assert worst <= 3

    @pytest.mark.asyncio
    async def test_fifo_fairness(self) -> None:
        """Without FIFO, one instrument's chunks can starve for minutes."""
        order: list[int] = []
        limiter = PacedRateLimiter(200.0)

        async def worker(i: int) -> None:
            await limiter.acquire()
            order.append(i)

        await asyncio.gather(*[worker(i) for i in range(15)])
        assert order == sorted(order)

    def test_adaptive_halves_then_recovers(self) -> None:
        limiter = AdaptiveLimiter(2.5)
        assert limiter.current_rate == 2.5
        limiter.penalize()
        assert limiter.current_rate == 1.25
        limiter.penalize()
        assert limiter.current_rate == 0.625
        for _ in range(AdaptiveLimiter.REWARD_AFTER * 10):
            limiter.reward()
        assert limiter.current_rate == pytest.approx(2.5), "must recover to the ceiling"

    def test_never_exceeds_the_hard_ceiling(self) -> None:
        assert AdaptiveLimiter(99.0).current_rate == 3.0

    def test_penalty_has_a_floor(self) -> None:
        limiter = AdaptiveLimiter(2.5)
        for _ in range(40):
            limiter.penalize()
        assert limiter.current_rate == AdaptiveLimiter.MIN_RATE


# ─── error classification ────────────────────────────────────────────────────
class TestErrorClassification:
    @pytest.mark.asyncio
    async def test_bad_credentials_arrive_as_400_and_are_fatal(self) -> None:
        """VERIFIED against the live API: an invalid api_key returns HTTP 400, not 403.

        Misclassifying this as an ordinary input error would mark every chunk failed and
        permanently poison resume.
        """
        attempts = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(
                400, json=_err("Invalid `api_key` or `access_token`.", "InputException")
            )

        async with KiteHistoricalFetcher(
            CREDS, transport=httpx.MockTransport(handler)
        ) as fetcher:
            with pytest.raises(KitelakeAuthError) as err:
                await fetcher.fetch_chunk(1, "minute", date(2026, 2, 1), date(2026, 2, 2))
        assert attempts["n"] == 1, "a dead token must not be retried"
        assert "kitelake auth" in str(err.value)

    @pytest.mark.asyncio
    async def test_missing_subscription_is_fatal_and_distinct(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403, json=_err("app is not subscribed to historical data", "PermissionException")
            )

        async with KiteHistoricalFetcher(
            CREDS, transport=httpx.MockTransport(handler)
        ) as fetcher:
            with pytest.raises(KitelakePermissionError):
                await fetcher.fetch_chunk(1, "minute", date(2026, 2, 1), date(2026, 2, 2))

    @pytest.mark.asyncio
    async def test_genuine_input_error_is_per_chunk_not_fatal(self) -> None:
        attempts = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(400, json=_err("interval is not valid", "InputException"))

        async with KiteHistoricalFetcher(
            CREDS, transport=httpx.MockTransport(handler)
        ) as fetcher:
            with pytest.raises(KitelakeInputError):
                await fetcher.fetch_chunk(1, "minute", date(2026, 2, 1), date(2026, 2, 2))
        assert attempts["n"] == 1, "a malformed request must not be retried either"

    @pytest.mark.asyncio
    async def test_429_backs_off_then_succeeds(self) -> None:
        state = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            state["n"] += 1
            if state["n"] <= 2:
                return httpx.Response(429, json=_err("Too many requests", "NetworkException"))
            return httpx.Response(200, json=_ok(2))

        limiter = AdaptiveLimiter(2.5)
        async with KiteHistoricalFetcher(
            CREDS, limiter=limiter, transport=httpx.MockTransport(handler)
        ) as fetcher:
            rows = await fetcher.fetch_chunk(1, "minute", date(2026, 2, 1), date(2026, 2, 2))
        assert len(rows) == 2
        assert limiter.penalties == 2
        assert limiter.current_rate < 2.5

    @pytest.mark.asyncio
    async def test_5xx_retried(self) -> None:
        state = {"n": 0}

        def handler(_request: httpx.Request) -> httpx.Response:
            state["n"] += 1
            return (
                httpx.Response(502, text="bad gateway")
                if state["n"] < 3
                else httpx.Response(200, json=_ok(1))
            )

        async with KiteHistoricalFetcher(
            CREDS, transport=httpx.MockTransport(handler)
        ) as fetcher:
            assert len(await fetcher.fetch_chunk(1, "minute", date(2026, 2, 1), date(2026, 2, 2))) == 1

    @pytest.mark.asyncio
    async def test_empty_candles_is_success_not_error(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "success", "data": {"candles": []}})

        async with KiteHistoricalFetcher(
            CREDS, transport=httpx.MockTransport(handler)
        ) as fetcher:
            assert await fetcher.fetch_chunk(1, "minute", date(2026, 2, 1), date(2026, 2, 2)) == []

    @pytest.mark.asyncio
    async def test_request_covers_whole_sessions(self) -> None:
        """00:00 bounds would clip the final day's bars."""
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen.update(dict(request.url.params))
            return httpx.Response(200, json=_ok(1))

        async with KiteHistoricalFetcher(
            CREDS, transport=httpx.MockTransport(handler)
        ) as fetcher:
            await fetcher.fetch_chunk(
                256265, "minute", date(2026, 2, 13), date(2026, 4, 13), oi=True
            )
        assert seen["from"] == "2026-02-13 09:15:00"
        assert seen["to"] == "2026-04-13 15:30:00"
        assert seen["oi"] == "1"


# ─── writing ─────────────────────────────────────────────────────────────────
class TestWriter:
    def test_merge_is_idempotent_to_the_byte(self, lake: Path, instrument, candles) -> None:
        from kitelake.writer import append_candles

        first = append_candles(instrument, "minute", candles(50), with_oi=False)
        second = append_candles(instrument, "minute", candles(50), with_oi=False)
        assert first["rows"] == second["rows"] == 50
        assert first["sha256"] == second["sha256"]

    def test_merge_adds_new_bars(self, lake: Path, instrument, candles) -> None:
        from kitelake.writer import append_candles

        append_candles(instrument, "minute", candles(10), with_oi=False)
        result = append_candles(
            instrument, "minute", candles(10, start=(11, 0)), with_oi=False
        )
        assert result["rows"] == 20

    def test_duplicate_timestamp_keeps_newest(self, lake: Path, instrument, candles) -> None:
        import pyarrow.parquet as pq

        from kitelake.schema import decode_price
        from kitelake.writer import append_candles

        append_candles(instrument, "minute", candles(3), with_oi=False)
        revised = candles(1)
        revised[0][4] = 999.0
        result = append_candles(instrument, "minute", revised, with_oi=False)
        table = pq.read_table(result["path"])
        assert table.num_rows == 3
        assert decode_price(table.column("close")[0].as_py()) == 999.0

    def test_no_staging_leftovers(self, lake: Path, instrument, candles) -> None:
        from kitelake.volume import staging_dir
        from kitelake.writer import append_candles

        append_candles(instrument, "minute", candles(20), with_oi=False)
        assert list(staging_dir().iterdir()) == []

    def test_empty_input_writes_no_file(self, lake: Path, instrument) -> None:
        from kitelake.writer import append_candles

        result = append_candles(instrument, "minute", [], with_oi=False)
        assert result["written"] is False
        assert not Path(result["path"]).exists(), "an empty file would fake 'no trades'"

    def test_symbol_with_slash_stays_inside_bars(self, lake: Path, candles) -> None:
        from kitelake.universe import Instrument
        from kitelake.volume import bars_dir
        from kitelake.writer import append_candles

        evil = Instrument(
            token=1, tradingsymbol="../../../etc/passwd", exchange="NSE", segment="NSE"
        )
        result = append_candles(evil, "minute", candles(3), with_oi=False)
        assert str(bars_dir().resolve()) in str(Path(result["path"]).resolve())

    def test_parquet_is_sorted_and_has_statistics(self, lake: Path, instrument, candles) -> None:
        import pyarrow.parquet as pq

        from kitelake.writer import append_candles

        result = append_candles(instrument, "minute", candles(500), with_oi=False)
        meta = pq.ParquetFile(result["path"]).metadata
        assert meta.num_row_groups == 1
        assert meta.row_group(0).column(0).statistics is not None
        assert meta.row_group(0).column(1).compression == "ZSTD"

    def test_distinct_symbols_never_share_a_file(self, lake: Path, candles) -> None:
        """Sanitising is lossy, so the token prefix must keep files distinct."""
        from kitelake.universe import Instrument
        from kitelake.writer import append_candles

        a = Instrument(token=111, tradingsymbol="A B", exchange="NSE", segment="NSE")
        b = Instrument(token=222, tradingsymbol="A/B", exchange="NSE", segment="NSE")
        pa_ = append_candles(a, "minute", candles(3), with_oi=False)["path"]
        pb_ = append_candles(b, "minute", candles(3), with_oi=False)["path"]
        assert pa_ != pb_


# ─── verification ────────────────────────────────────────────────────────────
class TestVerify:
    def test_clean_file_passes(self, lake: Path, instrument, candles) -> None:
        from kitelake.verify import verify_file
        from kitelake.writer import append_candles

        result = append_candles(instrument, "minute", candles(100), with_oi=False)
        report = verify_file(result["path"])
        assert report["ok"] is True, report["failures"]

    @pytest.mark.parametrize(
        "check,mutate",
        [
            ("high_ge_low", lambda cols, pa: cols.update(high=pa.array([1] * 5, pa.int64()))),
            ("volume_non_negative", lambda cols, pa: cols.update(volume=pa.array([-5] * 5, pa.int64()))),
        ],
    )
    def test_structural_violations_are_caught(
        self, lake: Path, candles, check: str, mutate
    ) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        from kitelake.schema import BAR_SCHEMA, candles_to_table
        from kitelake.verify import verify_file
        from kitelake.volume import bars_dir

        good = candles_to_table(candles(5), with_oi=False, meta={})
        cols = {name: good.column(name) for name in good.column_names}
        mutate(cols, pa)
        path = bars_dir() / "interval=minute/exchange=NSE/segment=NSE/9001__BAD.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.table(cols).cast(BAR_SCHEMA), path)
        assert check in verify_file(path)["failures"]

    def test_bar_outside_session_is_caught(self, lake: Path) -> None:
        import pyarrow.parquet as pq

        from kitelake.schema import BAR_SCHEMA, candles_to_table
        from kitelake.verify import verify_file
        from kitelake.volume import bars_dir

        night = candles_to_table(
            [["2026-02-03T03:00:00+0530", 1.0, 1.5, 0.5, 1.2, 10]], with_oi=False, meta={}
        )
        path = bars_dir() / "interval=minute/exchange=NSE/segment=NSE/9004__NIGHT.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(night.cast(BAR_SCHEMA), path)
        assert "in_session" in verify_file(path)["failures"]

    def test_misaligned_bar_is_caught(self, lake: Path) -> None:
        import pyarrow.parquet as pq

        from kitelake.schema import BAR_SCHEMA, candles_to_table
        from kitelake.verify import verify_file
        from kitelake.volume import bars_dir

        odd = candles_to_table(
            [["2026-02-03T09:15:30+0530", 1.0, 1.5, 0.5, 1.2, 10]], with_oi=False, meta={}
        )
        path = bars_dir() / "interval=minute/exchange=NSE/segment=NSE/9005__ODD.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(odd.cast(BAR_SCHEMA), path)
        assert "interval_aligned" in verify_file(path)["failures"]


# ─── manifest / resume ───────────────────────────────────────────────────────
class TestManifestResume:
    def test_plan_is_idempotent(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        chunks = [(date(2026, 2, 13), date(2026, 4, 13)), (date(2026, 4, 14), date(2026, 6, 13))]
        with Manifest() as man:
            man.plan_chunks(1, "minute", chunks)
            man.plan_chunks(1, "minute", chunks)
            assert len(man.pending_chunks("minute")) == 2

    def test_settled_chunks_are_not_re_offered(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        chunks = [
            (date(2026, 2, 13), date(2026, 4, 13)),
            (date(2026, 4, 14), date(2026, 6, 13)),
            (date(2026, 6, 14), date(2026, 8, 13)),
        ]
        with Manifest() as man:
            man.plan_chunks(1, "minute", chunks)
            man.mark_chunk(1, "minute", date(2026, 2, 13), "done", rows=100)
            man.mark_chunk(1, "minute", date(2026, 4, 14), "empty")
            pending = [c["chunk_from"] for c in man.pending_chunks("minute")]
            assert pending == ["2026-06-14"], "done and empty must both be settled"

    def test_failed_needs_opt_in_to_retry(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            man.plan_chunks(1, "minute", [(date(2026, 2, 13), date(2026, 4, 13))])
            man.mark_chunk(1, "minute", date(2026, 2, 13), "failed", error="boom")
            assert man.pending_chunks("minute") == []
            assert len(man.pending_chunks("minute", retry_failed=True)) == 1

    def test_reopening_preserves_state(self, lake: Path) -> None:
        """Resume across process restarts is the whole point."""
        from kitelake.manifest import Manifest

        chunks = [(date(2026, 2, 13), date(2026, 4, 13)), (date(2026, 4, 14), date(2026, 6, 13))]
        with Manifest() as man:
            man.plan_chunks(7, "minute", chunks)
            man.mark_chunk(7, "minute", date(2026, 2, 13), "done", rows=42)
        with Manifest() as reopened:
            assert [c["chunk_from"] for c in reopened.pending_chunks("minute")] == ["2026-04-14"]
            assert reopened.stats("minute")["candles"] == 42

    def test_gaps_lists_unsettled_ranges(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        with Manifest() as man:
            man.plan_chunks(
                1, "minute",
                [(date(2026, 2, 13), date(2026, 4, 13)), (date(2026, 4, 14), date(2026, 6, 13))],
            )
            man.mark_chunk(1, "minute", date(2026, 2, 13), "done", rows=5)
            assert man.gaps("minute", 1) == [("2026-04-14", "2026-06-13")]


# ─── orchestrator ────────────────────────────────────────────────────────────
def _broker(fail_after: int | None = None, bars_per_day: int = 5):
    """A fake Kite that serves plausible candles for whatever window is asked for."""
    from kitelake.calendar_ import session_days

    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if fail_after and state["n"] > fail_after:
            raise httpx.ConnectError("simulated cable yank")
        token = int(request.url.path.rsplit("/", 2)[-2])
        frm = datetime.fromisoformat(request.url.params["from"])
        to = datetime.fromisoformat(request.url.params["to"])
        rows = []
        for day in session_days(frm.date(), to.date()):
            for i in range(bars_per_day):
                stamp = datetime(day.year, day.month, day.day, 9, 15) + timedelta(minutes=i)
                price = 100.0 + (token % 97) + i * 0.01
                rows.append(
                    [
                        stamp.strftime("%Y-%m-%dT%H:%M:%S+0530"),
                        price, price + 0.6, price - 0.4, price + 0.2, 500 + i,
                    ]
                )
        return httpx.Response(200, json={"status": "success", "data": {"candles": rows}})

    handler.state = state  # type: ignore[attr-defined]
    return handler


def _seed_master(lake: Path) -> str:
    """Write a tiny instrument master so resolve_universe works offline."""
    import pyarrow as pa

    from kitelake.instruments import INSTRUMENT_SCHEMA, write_instrument_master

    rows = {
        "instrument_token": [738561, 408065, 341249],
        "exchange_token": [2885, 1594, 1333],
        "tradingsymbol": ["RELIANCE", "INFY", "HDFCBANK"],
        "name": ["RELIANCE", "INFY", "HDFCBANK"],
        "last_price": [0.0, 0.0, 0.0],
        "expiry": [None, None, None],
        "strike": [0.0, 0.0, 0.0],
        "tick_size": [0.05, 0.05, 0.05],
        "lot_size": [1, 1, 1],
        "instrument_type": ["EQ", "EQ", "EQ"],
        "segment": ["NSE", "NSE", "NSE"],
        "exchange": ["NSE", "NSE", "NSE"],
    }
    write_instrument_master(pa.table(rows, schema=INSTRUMENT_SCHEMA))
    return "NSE:RELIANCE,NSE:INFY,NSE:HDFCBANK"


class TestOrchestrator:
    FRM = date(2026, 6, 1)
    TO = date(2026, 8, 13)

    def _run(self, spec: str, handler, **kwargs: Any) -> dict[str, Any]:
        from kitelake.download import run_download

        return asyncio.run(
            run_download(
                spec, "minute", self.FRM, self.TO,
                transport=httpx.MockTransport(handler), rate=1000, concurrency=4,
                progress=lambda _e: None, **kwargs,
            )
        )

    def test_resume_matches_an_uninterrupted_run(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        spec = _seed_master(lake)
        broken = _broker(fail_after=2)
        self._run(spec, broken)
        with Manifest() as man:
            partial = man.stats("minute")
        assert partial["chunks_remaining"] > 0 or partial["chunks_by_status"].get("failed")

        self._run(spec, _broker(), retry_failed=True)
        with Manifest() as man:
            resumed = man.stats("minute")
        assert resumed["pct_complete"] == 100.0
        assert resumed["chunks_by_status"].get("failed", 0) == 0
        assert resumed["candles"] > 0

    def test_dead_token_leaves_chunks_pending(self, lake: Path) -> None:
        """The failure mode that would silently produce a permanently incomplete lake."""
        from kitelake.manifest import Manifest

        spec = _seed_master(lake)

        def dead(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400, json=_err("Invalid `api_key` or `access_token`.", "InputException")
            )

        summary = self._run(spec, dead)
        assert summary["fatal"], "must abort the run, not soldier on"
        with Manifest() as man:
            stats = man.stats("minute")
        assert stats["chunks_by_status"].get("failed", 0) == 0
        assert stats["chunks_by_status"].get("pending", 0) == stats["chunks_total"]

    def test_illiquid_instrument_records_empty_not_failed(self, lake: Path) -> None:
        from kitelake.manifest import Manifest

        spec = _seed_master(lake)

        def nothing(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "success", "data": {"candles": []}})

        self._run(spec, nothing)
        with Manifest() as man:
            stats = man.stats("minute")
        assert stats["chunks_by_status"].get("failed", 0) == 0
        assert stats["chunks_by_status"]["empty"] == stats["chunks_total"]
        assert stats["symbols"] == 0, "no parquet should be written for zero candles"

    def test_dry_run_makes_no_requests(self, lake: Path) -> None:
        spec = _seed_master(lake)
        handler = _broker()
        summary = self._run(spec, handler, dry_run=True)
        assert summary["dry_run"] is True
        assert summary["requests"] > 0, "it should still report the projected count"
        assert handler.state["n"] == 0  # type: ignore[attr-defined]

    def test_oi_requested_only_for_derivatives(self, lake: Path) -> None:
        seen: list[tuple[int, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            token = int(request.url.path.rsplit("/", 2)[-2])
            seen.append((token, request.url.params["oi"]))
            return httpx.Response(200, json={"status": "success", "data": {"candles": []}})

        import pyarrow as pa

        from kitelake.instruments import INSTRUMENT_SCHEMA, write_instrument_master

        write_instrument_master(
            pa.table(
                {
                    "instrument_token": [738561, 12345678],
                    "exchange_token": [2885, 999],
                    "tradingsymbol": ["RELIANCE", "NIFTY26AUG25000CE"],
                    "name": ["RELIANCE", "NIFTY"],
                    "last_price": [0.0, 0.0],
                    "expiry": [None, None],
                    "strike": [0.0, 25000.0],
                    "tick_size": [0.05, 0.05],
                    "lot_size": [1, 75],
                    "instrument_type": ["EQ", "CE"],
                    "segment": ["NSE", "NFO-OPT"],
                    "exchange": ["NSE", "NFO"],
                },
                schema=INSTRUMENT_SCHEMA,
            )
        )
        self._run("NSE:RELIANCE,NFO:NIFTY26AUG25000CE", handler)
        by_token = dict(seen)
        assert by_token[738561] == "0", "equities have no open interest"
        assert by_token[12345678] == "1", "options should carry OI"

    def test_event_log_never_contains_credentials(self, lake: Path) -> None:
        from kitelake.volume import logs_dir

        spec = _seed_master(lake)
        self._run(spec, _broker())
        for path in logs_dir().glob("*.jsonl"):
            body = path.read_text()
            assert "test_token" not in body
            assert "access_token" not in body


class TestObservedErrorMessages:
    """Classification of every error phrasing the live API has actually returned.

    The trap this pins down: Kite's ``"invalid token" (HTTP 400, InputException)`` does
    NOT mean the access token. It means the *instrument* token in the URL is one it will
    not serve historical data for — SME scrips such as SWARAJ-SM return it on a perfectly
    valid session. Proven by probing both on the same connection: NIFTY 50 returned 375
    candles while SWARAJ-SM returned "invalid token".

    Treating it as a credential error was tried and was strictly worse than the original
    behaviour: it turned one unsupported instrument into a fatal abort of a 40,000-chunk
    run. These tests exist so nobody "fixes" it that way again.
    """

    OBSERVED = [
        # instrument-level rejection — must NOT be fatal, and must not be retried forever
        (400, "invalid token", "InputException", KitelakeInstrumentRejected),
        (400, "instrument_token is invalid", "InputException", KitelakeInstrumentRejected),
        (400, "Invalid instrument_token 999", "InputException", KitelakeInstrumentRejected),
        # credential problems — fatal, abort the run
        (400, "Invalid `api_key` or `access_token`.", "InputException", KitelakeAuthError),
        (403, "Incorrect `api_key` or `access_token`.", "TokenException", KitelakeAuthError),
        (400, "Token is invalid or has expired", "InputException", KitelakeAuthError),
        # entitlement
        (403, "app is not subscribed to historical data", "PermissionException",
         KitelakePermissionError),
        # ordinary malformed request — per-chunk, retryable via --retry-failed
        (400, "interval is not valid", "InputException", KitelakeInputError),
        (400, "from date is greater than to date", "InputException", KitelakeInputError),
    ]

    @pytest.mark.parametrize("status,message,error_type,expected", OBSERVED)
    def test_observed_messages_classify_correctly(
        self, status: int, message: str, error_type: str, expected: type
    ) -> None:
        from kitelake.fetcher import _classify

        assert type(_classify(status, message, error_type)) is expected

    def test_instrument_rejection_is_never_fatal(self) -> None:
        """One unserviceable SME scrip must not take down a 40,000-chunk run."""
        from kitelake.fetcher import KitelakeFatal, _classify

        err = _classify(400, "invalid token", "InputException")
        assert isinstance(err, KitelakeInstrumentRejected)
        assert not isinstance(err, KitelakeFatal)

    @pytest.mark.asyncio
    async def test_rejected_instrument_is_skipped_not_failed(self, lake: Path) -> None:
        """'skipped' so --retry-failed does not spend a request on it every single run."""
        import pyarrow as pa

        from kitelake.download import run_download
        from kitelake.instruments import INSTRUMENT_SCHEMA, write_instrument_master
        from kitelake.manifest import Manifest

        write_instrument_master(pa.table({
            "instrument_token": [999001], "exchange_token": [1],
            "tradingsymbol": ["SWARAJ-SM"], "name": ["SWARAJ SME"], "last_price": [0.0],
            "expiry": [None], "strike": [0.0], "tick_size": [0.05], "lot_size": [1],
            "instrument_type": ["EQ"], "segment": ["NSE"], "exchange": ["NSE"],
        }, schema=INSTRUMENT_SCHEMA))

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json=_err("invalid token", "InputException"))

        summary = await run_download(
            "NSE:SWARAJ-SM", "minute", date(2026, 6, 1), date(2026, 8, 13),
            transport=httpx.MockTransport(handler), rate=1000,
            progress=lambda _e: None,
        )
        assert summary["fatal"] is None, "must not abort the run"
        assert summary["failed"] == 0
        assert summary["skipped"] > 0
        with Manifest() as man:
            stats = man.stats("minute")
        assert stats["chunks_by_status"].get("failed", 0) == 0
        assert stats["chunks_by_status"]["skipped"] == stats["chunks_total"]
        # 'skipped' counts as settled, so a later --retry-failed re-asks nothing.
        assert man_pending_is_empty()

def man_pending_is_empty() -> bool:
    from kitelake.manifest import Manifest

    with Manifest() as man:
        return man.pending_chunks("minute", retry_failed=True) == []
