from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.engines.nifty_orb_options import Bar
from app.services import opening_volume_leaders as service

IST = timezone(timedelta(hours=5, minutes=30))
REFERENCE_LEADERS = {"GODREJCP", "RBLBANK", "SOLARINDS", "INOXWIND", "PAGEIND"}


class FakeInstrumentClient:
    def __init__(self, fno_symbols=REFERENCE_LEADERS):
        self.fno_symbols = set(fno_symbols)

    async def search_instruments(self, _query, exchange, limit=50):
        assert limit == service._INSTRUMENT_MASTER_LIMIT
        if exchange == "NFO":
            rows = [
                {"name": symbol, "instrument_type": option_type}
                for symbol in sorted(self.fno_symbols)
                for option_type in ("CE", "PE")
            ]
            rows.extend(
                [
                    {"name": "NIFTY", "instrument_type": "CE"},
                    {"name": "FUTUREONLY", "instrument_type": "FUT"},
                ]
            )
            return rows
        if exchange == "NSE":
            return [
                {"tradingsymbol": symbol, "instrument_type": "EQ"}
                for symbol in sorted(self.fno_symbols | {"CASHONLY"})
            ]
        raise AssertionError(f"unexpected exchange: {exchange}")


def _sessions(count: int, before: date) -> list[date]:
    rows: list[date] = []
    cursor = before
    while len(rows) < count:
        cursor -= timedelta(days=1)
        if cursor.weekday() < 5:
            rows.append(cursor)
    return list(reversed(rows))


def _bars() -> list[Bar]:
    session = date(2026, 9, 3)
    rows: list[Bar] = []
    for day in _sessions(20, session):
        for minute in range(300):
            timestamp = datetime.combine(day, time(9, 15), tzinfo=IST) + timedelta(
                minutes=minute
            )
            rows.append(Bar(timestamp, 110.0, 111.0, 109.0, 110.5, 2_000.0))
    rows.extend(
        [
            Bar(
                datetime(2026, 9, 3, 9, 15, tzinfo=IST),
                110.0,
                112.0,
                109.5,
                111.8,
                10_000.0,
            ),
            Bar(
                datetime(2026, 9, 3, 9, 16, tzinfo=IST),
                111.8,
                113.0,
                111.5,
                112.8,
                4_000.0,
            ),
        ]
    )
    return rows


def test_live_config_rejects_an_empty_custom_universe():
    with pytest.raises(ValueError, match="select symbols"):
        service.LiveLeaderScanConfig(scan_all_stocks=False).validate()


@pytest.mark.asyncio
async def test_broker_discovery_includes_reference_leaders_and_excludes_indices():
    symbols = await service._discover_fno_equity_symbols(FakeInstrumentClient())

    assert REFERENCE_LEADERS <= set(symbols)
    assert "NIFTY" not in symbols
    assert "FUTUREONLY" not in symbols
    assert "CASHONLY" not in symbols


@pytest.mark.asyncio
async def test_full_universe_is_current_broker_fno_not_the_legacy_curated_subset():
    cfg = service.LiveLeaderScanConfig(max_candidates=500)
    symbols, metadata = await service._resolve_universe(
        FakeInstrumentClient(),
        cfg,
    )

    assert set(symbols) == REFERENCE_LEADERS
    assert metadata == {
        "source": "kite_nfo_options_intersect_nse_equities",
        "available_fno_equity_count": 5,
        "requested_count": 5,
        "selected_count": 5,
        "truncated": False,
        "symbols": sorted(REFERENCE_LEADERS),
    }


@pytest.mark.asyncio
async def test_custom_universe_accepts_current_fno_names_and_rejects_non_fno_names():
    cfg = service.LiveLeaderScanConfig(
        scan_all_stocks=False,
        symbols=("RBLBANK", "THIN-NAME"),
    )
    with pytest.raises(ValueError, match="THIN-NAME"):
        await service._resolve_universe(FakeInstrumentClient(), cfg)

    valid, metadata = await service._resolve_universe(
        FakeInstrumentClient(),
        service.LiveLeaderScanConfig(
            scan_all_stocks=False,
            symbols=("rblbank", "RBLBANK"),
        ),
    )
    assert valid == ["RBLBANK"]
    assert metadata["source"] == "explicit_current_fno_equities"


@pytest.mark.asyncio
async def test_universe_cap_is_explicitly_reported_as_truncation():
    symbols, metadata = await service._resolve_universe(
        FakeInstrumentClient(),
        service.LiveLeaderScanConfig(max_candidates=2),
    )

    assert len(symbols) == 2
    assert metadata["available_fno_equity_count"] == 5
    assert metadata["selected_count"] == 2
    assert metadata["truncated"] is True
    assert metadata["symbols"] == symbols


@pytest.mark.asyncio
async def test_history_cache_rolls_forward_when_another_minute_completes(monkeypatch):
    service._history_cache.clear()

    class FakeClient:
        calls = 0

        async def get_historical(self, *_args, **_kwargs):
            self.calls += 1
            return {
                "candles": [["2026-09-03 09:15:00", 100.0, 101.0, 99.0, 100.5, 1_000.0]]
            }

    async def no_wait():
        return None

    monkeypatch.setattr(service._historical_pacer, "wait", no_wait)
    fake_client = FakeClient()
    common = {
        "client": fake_client,
        "uid": "tenant-a",
        "symbol": "RELIANCE",
        "token": 123,
        "history_calendar_days": 45,
    }

    await service._history(
        **common,
        as_of=datetime(2026, 9, 3, 9, 16, 10, tzinfo=IST),
    )
    await service._history(
        **common,
        as_of=datetime(2026, 9, 3, 9, 16, 50, tzinfo=IST),
    )
    assert fake_client.calls == 1

    await service._history(
        **common,
        as_of=datetime(2026, 9, 3, 9, 17, 0, tzinfo=IST),
    )
    assert fake_client.calls == 2
    service._history_cache.clear()


@pytest.mark.asyncio
async def test_kite_runtime_returns_advisory_leaders_without_execution(monkeypatch):
    from app.services import nifty_orb_scanner
    from app.services.exchanges.kite import accounts

    class FakeClient:
        async def search_instruments(self, _query, exchange, limit=50):
            assert limit == service._INSTRUMENT_MASTER_LIMIT
            if exchange == "NFO":
                return [{"name": "RELIANCE", "instrument_type": "CE"}]
            if exchange == "NSE":
                return [{"tradingsymbol": "RELIANCE", "instrument_type": "EQ"}]
            raise AssertionError(f"unexpected exchange: {exchange}")

    fake_client = FakeClient()
    monkeypatch.setattr(
        accounts, "get_active", lambda uid: SimpleNamespace(user_id=uid)
    )

    async def acquire_client(_account):
        return fake_client

    async def instrument(_client, symbol):
        assert _client is fake_client
        assert symbol == "RELIANCE"
        return SimpleNamespace(zerodha_token=123)

    async def history(_client, **kwargs):
        assert _client is fake_client
        assert kwargs["uid"] == "tenant-a"
        assert kwargs["token"] == 123
        return _bars()

    monkeypatch.setattr(accounts, "acquire_client", acquire_client)
    monkeypatch.setattr(nifty_orb_scanner, "_kite_instrument", instrument)
    monkeypatch.setattr(service, "_history", history)

    result = await service.scan_kite_leaders(
        "tenant-a",
        as_of=datetime(2026, 9, 3, 9, 17, tzinfo=IST),
        scan_config=service.LiveLeaderScanConfig(
            scan_all_stocks=False,
            symbols=("RELIANCE",),
        ),
    )

    assert result["strategy"]["execution"] == "advisory_only"
    assert result["universe"]["source"] == "explicit_current_fno_equities"
    assert result["universe"]["available_fno_equity_count"] == 1
    assert result["universe_count"] == 1
    assert result["evaluated_count"] == 1
    assert result["leader_count"] == 1
    assert result["leaders"][0]["symbol"] == "RELIANCE"
    assert result["leaders"][0]["tier"] == "strong"
    assert result["failures"] == []


@pytest.mark.asyncio
async def test_full_runtime_evaluates_every_broker_discovered_reference_leader(
    monkeypatch,
):
    from app.services import nifty_orb_scanner
    from app.services.exchanges.kite import accounts

    fake_client = FakeInstrumentClient()
    monkeypatch.setattr(
        accounts, "get_active", lambda uid: SimpleNamespace(user_id=uid)
    )

    async def acquire_client(_account):
        return fake_client

    async def instrument(_client, symbol):
        assert _client is fake_client
        assert symbol in REFERENCE_LEADERS
        return SimpleNamespace(zerodha_token=abs(hash(symbol)) or 1)

    async def history(_client, **kwargs):
        assert _client is fake_client
        assert kwargs["symbol"] in REFERENCE_LEADERS
        return _bars()

    monkeypatch.setattr(accounts, "acquire_client", acquire_client)
    monkeypatch.setattr(nifty_orb_scanner, "_kite_instrument", instrument)
    monkeypatch.setattr(service, "_history", history)

    result = await service.scan_kite_leaders(
        "tenant-a",
        as_of=datetime(2026, 9, 3, 9, 17, tzinfo=IST),
        scan_config=service.LiveLeaderScanConfig(max_candidates=500),
    )

    assert result["universe"]["source"] == ("kite_nfo_options_intersect_nse_equities")
    assert result["universe_count"] == len(REFERENCE_LEADERS)
    assert result["evaluated_count"] == len(REFERENCE_LEADERS)
    assert {row["symbol"] for row in result["leaders"]} == REFERENCE_LEADERS
    assert result["failures"] == []
