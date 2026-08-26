"""Schema encoding, symbol sanitising, and the chunker.

``chunk_range`` gets the heaviest treatment in the suite because its failure mode is
silent: an off-by-one drops or duplicates a trading day without raising anything, and you
discover it months later when a backtest disagrees with reality.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from kitelake.config import INTERVAL_DAY_CAP, PRICE_SCALE, VALID_INTERVALS
from kitelake.fetcher import chunk_range
from kitelake.schema import (
    BAR_SCHEMA,
    candles_to_table,
    decode_price,
    encode_price,
    parse_bar_filename,
    sanitize_symbol,
)


class TestPriceEncoding:
    @pytest.mark.parametrize(
        "value",
        [0.0, 0.05, 1.0, 100.5, 2543.75, 83.4525, 99_999.9999, 0.0001],
    )
    def test_roundtrip_is_exact(self, value: float) -> None:
        assert decode_price(encode_price(value)) == pytest.approx(value, abs=1e-9)

    def test_four_decimals_survive(self) -> None:
        """CDS pairs quote to 4dp — paise-scaling would truncate this."""
        assert encode_price(83.4525) == 834_525
        assert decode_price(834_525) == 83.4525

    def test_scale_is_ten_thousand(self) -> None:
        assert PRICE_SCALE == 10_000

    def test_negative_rounds_symmetrically(self) -> None:
        assert encode_price(-1.5) == -15_000


class TestSanitizeSymbol:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("M&M", "M&M"),                                # & is legal, must survive
            ("NIFTY 50", "NIFTY_50"),
            ("NIFTY50 PR 2X LEV", "NIFTY50_PR_2X_LEV"),
            ("BAJAJ-AUTO", "BAJAJ-AUTO"),
            ("NIFTY26AUG25000CE", "NIFTY26AUG25000CE"),
            ("500325", "500325"),                          # BSE numeric symbols
            ("A/B", "A_B"),
            ('A*B?C"D<E>F|G:H\\I', "A_B_C_D_E_F_G_H_I"),   # every NTFS-forbidden char
            ("trailing. ", "trailing"),
            (".hidden", "hidden"),                         # no accidental dotfiles
            ("", "UNKNOWN"),
            ("   ", "UNKNOWN"),
        ],
    )
    def test_cases(self, raw: str, expected: str) -> None:
        assert sanitize_symbol(raw) == expected

    def test_deterministic(self) -> None:
        assert sanitize_symbol("NIFTY 50") == sanitize_symbol("NIFTY 50")

    def test_no_path_separators_survive(self) -> None:
        assert "/" not in sanitize_symbol("../../etc/passwd")

    def test_roundtrip_through_filename(self) -> None:
        assert parse_bar_filename("738561__RELIANCE.parquet") == (738561, "RELIANCE")
        assert parse_bar_filename("not-a-bar-file.parquet") is None


class TestCandlesToTable:
    def test_ist_offset_becomes_correct_utc_instant(self, candles) -> None:
        table = candles_to_table(
            [["2026-02-03T09:15:00+0530", 1.0, 2.0, 0.5, 1.5, 10]], with_oi=False, meta={}
        )
        assert table.column("ts")[0].as_py() == datetime(2026, 2, 3, 3, 45, tzinfo=timezone.utc)

    def test_schema_matches_exactly(self, candles) -> None:
        table = candles_to_table(candles(5), with_oi=False, meta={})
        assert table.schema.names == BAR_SCHEMA.names
        assert [f.type for f in table.schema] == [f.type for f in BAR_SCHEMA]

    def test_sorts_and_keeps_last_duplicate(self) -> None:
        """A repeated timestamp means corrected data: the later row wins."""
        rows = [
            ["2026-02-03T09:16:00+0530", 1, 1, 1, 9.0, 5],
            ["2026-02-03T09:15:00+0530", 1, 1, 1, 1.0, 1],
            ["2026-02-03T09:16:00+0530", 1, 1, 1, 7.0, 7],
        ]
        table = candles_to_table(rows, with_oi=False, meta={})
        assert table.num_rows == 2
        stamps = [t.as_py() for t in table.column("ts")]
        assert stamps == sorted(stamps)
        assert decode_price(table.column("close")[1].as_py()) == 7.0

    @pytest.mark.parametrize(
        "bad",
        [None, "not-a-row", [], ["only-ts"], ["bogus-ts", 1, 1, 1, 1, 1],
         ["2026-02-03T09:15:00", 1, 1, 1, 1, 1]],  # naive ts: refuse to guess a zone
    )
    def test_malformed_rows_are_dropped_not_fatal(self, bad) -> None:
        good = ["2026-02-03T09:15:00+0530", 1.0, 2.0, 0.5, 1.5, 10]
        table = candles_to_table([good, bad], with_oi=False, meta={})
        assert table.num_rows == 1

    def test_oi_absent_for_equities(self, candles) -> None:
        table = candles_to_table(candles(3), with_oi=False, meta={})
        assert table.column("oi").null_count == 3

    def test_oi_present_for_derivatives(self, candles) -> None:
        table = candles_to_table(candles(3, with_oi=True), with_oi=True, meta={})
        assert table.column("oi").null_count == 0
        assert table.column("oi")[0].as_py() == 50_000

    def test_credentials_never_reach_metadata(self, candles) -> None:
        table = candles_to_table(
            candles(2), with_oi=False,
            meta={"api_key": "LEAK", "access_token": "LEAK", "tradingsymbol": "RELIANCE"},
        )
        blob = b" ".join(
            (k + b"=" + v) for k, v in (table.schema.metadata or {}).items()
        )
        assert b"LEAK" not in blob
        assert b"RELIANCE" in blob

    def test_empty_input_yields_empty_table(self) -> None:
        assert candles_to_table([], with_oi=False, meta={}).num_rows == 0


class TestChunkRange:
    """Invariants, not examples: gaps and overlaps are the silent killers."""

    @pytest.mark.parametrize("interval", VALID_INTERVALS)
    @pytest.mark.parametrize("span", [1, 2, 59, 60, 61, 120, 182, 365, 400, 733])
    def test_invariants(self, interval: str, span: int) -> None:
        cap = INTERVAL_DAY_CAP[interval]
        frm = date(2025, 11, 20)  # crosses a year boundary for the larger spans
        to = frm + timedelta(days=span - 1)
        chunks = chunk_range(frm, to, interval)

        assert chunks, "must always produce at least one chunk"
        assert chunks[0][0] == frm, "first chunk must start exactly at 'from'"
        assert chunks[-1][1] == to, "last chunk must end exactly at 'to'"
        for a, b in chunks:
            assert a <= b
            assert (b - a).days + 1 <= cap, "chunk exceeds the API's per-request cap"
        for (_a1, b1), (a2, _b2) in zip(chunks, chunks[1:]):
            assert a2 == b1 + timedelta(days=1), "gap or overlap between chunks"
        assert sum((b - a).days + 1 for a, b in chunks) == span, "coverage must be exact"

    def test_single_day(self) -> None:
        day = date(2026, 8, 13)
        assert chunk_range(day, day, "minute") == [(day, day)]

    def test_exactly_the_cap_is_one_chunk(self) -> None:
        frm = date(2026, 6, 15)
        to = frm + timedelta(days=59)  # 60 days inclusive
        assert len(chunk_range(frm, to, "minute")) == 1

    def test_cap_plus_one_splits(self) -> None:
        frm = date(2026, 6, 15)
        to = frm + timedelta(days=60)  # 61 days inclusive
        chunks = chunk_range(frm, to, "minute")
        assert len(chunks) == 2
        assert (chunks[0][1] - chunks[0][0]).days + 1 == 60
        assert chunks[1] == (to, to)

    def test_six_months_of_minutes_is_four_requests(self) -> None:
        assert len(chunk_range(date(2026, 2, 13), date(2026, 8, 13), "minute")) == 4

    def test_reversed_range_rejected(self) -> None:
        with pytest.raises(ValueError, match="before"):
            chunk_range(date(2026, 8, 13), date(2026, 2, 13), "minute")

    def test_unknown_interval_rejected(self) -> None:
        with pytest.raises(ValueError, match="invalid interval"):
            chunk_range(date(2026, 2, 13), date(2026, 8, 13), "7minute")

    def test_second_is_not_a_fetchable_interval(self) -> None:
        """Kite has no sub-minute history; asking must fail loudly, not silently."""
        with pytest.raises(ValueError):
            chunk_range(date(2026, 8, 1), date(2026, 8, 13), "second")
