from __future__ import annotations

import csv
import io

import pytest

from app.services.exchanges.kite.instruments import InstrumentCache
from app.services.navigator.instrument_slice import InstrumentSliceIndex

_COLUMNS = [
    "instrument_token", "exchange_token", "tradingsymbol", "name", "last_price",
    "expiry", "strike", "tick_size", "lot_size", "instrument_type", "segment", "exchange",
]


def _row(token, tradingsymbol, name, expiry, strike, itype, segment, exchange, lot_size=75, tick_size=0.05):
    return dict(
        instrument_token=token, exchange_token=token // 10, tradingsymbol=tradingsymbol, name=name,
        last_price="0", expiry=expiry, strike=strike, tick_size=tick_size, lot_size=lot_size,
        instrument_type=itype, segment=segment, exchange=exchange,
    )


def _csv_text(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_COLUMNS)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue()


def _make_cache(rows, ttl=3600.0):
    async def fetch_csv(exchange):
        return _csv_text(rows)
    return InstrumentCache(fetch_csv, ttl=ttl)


def _nfo_chain_rows(underlying="NIFTY", expiry="2026-08-06", strikes=None, step=100):
    strikes = strikes or list(range(24000, 25100, step))
    rows = []
    tok = 1000
    for s in strikes:
        rows.append(_row(tok, f"{underlying}26AUG{s}CE", underlying, expiry, s, "CE", "NFO-OPT", "NFO"))
        tok += 1
        rows.append(_row(tok, f"{underlying}26AUG{s}PE", underlying, expiry, s, "PE", "NFO-OPT", "NFO"))
        tok += 1
    return rows


class TestOptionSlice:
    @pytest.mark.asyncio
    async def test_selects_atm_and_symmetric_strikes(self):
        cache = _make_cache(_nfo_chain_rows())
        idx = InstrumentSliceIndex(cache)
        result = await idx.option_slice(
            exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500, strike_radius=2,
        )
        assert result.atm_strike == 24500
        assert result.expected_contract_count == 5 * 2  # 5 strikes (radius 2 each side), CE+PE
        assert result.found_contract_count == 10
        strikes_seen = sorted({c.strike for c in result.contracts})
        assert strikes_seen == [24300, 24400, 24500, 24600, 24700]

    @pytest.mark.asyncio
    async def test_strike_step_is_inferred_from_listed_contracts(self):
        cache = _make_cache(_nfo_chain_rows(step=50))
        idx = InstrumentSliceIndex(cache)
        result = await idx.option_slice(
            exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500, strike_radius=1,
        )
        assert result.strike_step == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_reports_expected_vs_found_when_some_strikes_missing_a_side(self):
        rows = _nfo_chain_rows(strikes=[24400, 24500, 24600])
        # drop the PE contract at 24600 to simulate a missing side
        rows = [r for r in rows if not (r["strike"] == 24600 and r["instrument_type"] == "PE")]
        cache = _make_cache(rows)
        idx = InstrumentSliceIndex(cache)
        result = await idx.option_slice(
            exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500, strike_radius=1,
        )
        assert result.expected_contract_count == 6
        assert result.found_contract_count == 5

    @pytest.mark.asyncio
    async def test_never_infers_expiry_from_weekday_only_lists_actual_expiries(self):
        rows = _nfo_chain_rows(expiry="2026-08-06") + _nfo_chain_rows(expiry="2026-08-13")
        cache = _make_cache(rows)
        idx = InstrumentSliceIndex(cache)
        expiries = await idx.listed_expiries("NFO", "NIFTY")
        assert expiries == ["2026-08-06", "2026-08-13"]

    @pytest.mark.asyncio
    async def test_supports_bfo_exchange_independently_of_nfo(self):
        nfo_rows = _nfo_chain_rows(underlying="NIFTY")
        bfo_rows = [
            _row(9001, "SENSEX26AUG80000CE", "SENSEX", "2026-08-06", 80000, "CE", "BFO-OPT", "BFO"),
            _row(9002, "SENSEX26AUG80000PE", "SENSEX", "2026-08-06", 80000, "PE", "BFO-OPT", "BFO"),
        ]

        async def fetch_csv(exchange):
            return _csv_text(bfo_rows if exchange == "BFO" else nfo_rows)

        cache = InstrumentCache(fetch_csv)
        idx = InstrumentSliceIndex(cache)
        nfo_result = await idx.option_slice(exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500, strike_radius=1)
        bfo_result = await idx.option_slice(exchange="BFO", underlying="SENSEX", expiry="2026-08-06", spot=80000, strike_radius=1)
        assert nfo_result.found_contract_count > 0
        assert bfo_result.found_contract_count == 2

    @pytest.mark.asyncio
    async def test_unknown_underlying_or_expiry_returns_empty_not_an_error(self):
        cache = _make_cache(_nfo_chain_rows())
        idx = InstrumentSliceIndex(cache)
        result = await idx.option_slice(exchange="NFO", underlying="BANKNIFTY", expiry="2026-08-06", spot=50000, strike_radius=1)
        assert result.found_contract_count == 0
        assert result.expected_contract_count == 0

    @pytest.mark.asyncio
    async def test_index_rebuilds_when_cache_ttl_refreshes(self):
        calls = {"n": 0}

        async def fetch_csv(exchange):
            calls["n"] += 1
            strikes = [24400, 24500, 24600] if calls["n"] == 1 else [24400, 24500, 24600, 24700]
            return _csv_text(_nfo_chain_rows(strikes=strikes))

        cache = InstrumentCache(fetch_csv, ttl=0.01)
        idx = InstrumentSliceIndex(cache)
        first = await idx.option_slice(exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500, strike_radius=5)
        import asyncio
        await asyncio.sleep(0.02)  # let the TTL lapse
        second = await idx.option_slice(exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500, strike_radius=5)
        assert first.found_contract_count == 6
        assert second.found_contract_count == 8

    @pytest.mark.asyncio
    async def test_strike_step_override_is_honored(self):
        cache = _make_cache(_nfo_chain_rows(step=100))
        idx = InstrumentSliceIndex(cache)
        result = await idx.option_slice(
            exchange="NFO", underlying="NIFTY", expiry="2026-08-06", spot=24500,
            strike_radius=1, strike_step_override=250.0,
        )
        assert result.strike_step == 250.0
