from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.engines.nifty_orb_options import Bar
from app.services import opening_volume_leaders as service

IST = timezone(timedelta(hours=5, minutes=30))


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


def test_custom_universe_cannot_bypass_sterlings_liquidity_registry():
    cfg = service.LiveLeaderScanConfig(
        scan_all_stocks=False,
        symbols=("RELIANCE", "THIN-NAME"),
    )
    with pytest.raises(ValueError, match="THIN-NAME"):
        service._normalize_universe(cfg)


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
        pass

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
    assert result["universe_count"] == 1
    assert result["evaluated_count"] == 1
    assert result["leader_count"] == 1
    assert result["leaders"][0]["symbol"] == "RELIANCE"
    assert result["leaders"][0]["tier"] == "strong"
    assert result["failures"] == []
