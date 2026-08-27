"""One quote call per chain, not one per strike.

``_kite_option_contracts`` awaited ``get_quote`` once per contract, sequentially.
A NIFTY chain is ~100 strikes, so resolving a single signal cost ~100 round
trips; with eight signals firing, a scan took 65 seconds against a board that
refetches every 5, so requests piled up faster than they drained.

The Kite quote endpoint is a batch endpoint and always was. Nothing about the
data changes here — only how many requests it takes to fetch it.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import StrategyConfig
from app.services import nifty_orb_scanner as scanner

IST = timezone(timedelta(hours=5, minutes=30))


class _CountingClient:
    """Records how many quote round trips a chain resolution actually costs."""

    def __init__(self, strikes: int):
        self.expiry = datetime.now(IST).date() + timedelta(days=5)
        self.strikes = strikes
        self.quote_calls: list[int] = []

    async def search_instruments(self, name, exchange, limit=0):
        if exchange != "NFO":
            return []
        return [
            {"name": name, "instrument_type": "CE", "expiry": self.expiry.isoformat(),
             "tradingsymbol": f"{name}CE{s}", "exchange": "NFO",
             "strike": float(s), "lot_size": 65}
            for s in range(24000, 24000 + self.strikes * 50, 50)
        ]

    async def get_quote(self, keys):
        self.quote_calls.append(len(keys))
        return {k: {"last_price": 120.0, "volume": 50000, "oi": 900000,
                    "depth": {"buy": [{"price": 119.5}], "sell": [{"price": 120.5}]}}
                for k in keys}


@pytest.fixture
def client(monkeypatch):
    def _install(strikes):
        c = _CountingClient(strikes)

        class _Accounts:
            @staticmethod
            def get_active(uid):
                return object()

            @staticmethod
            async def acquire_client(acct):
                return c

        import app.services.exchanges.kite as kite_pkg
        monkeypatch.setattr(kite_pkg, "accounts", _Accounts, raising=False)
        scanner._option_cache.clear()
        return c

    return _install


@pytest.mark.asyncio
async def test_a_hundred_strike_chain_costs_one_quote_call(client):
    c = client(100)

    contracts = await scanner._kite_option_contracts(
        "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))

    assert len(contracts) == 100
    assert len(c.quote_calls) == 1, f"expected one batched call, got {c.quote_calls}"
    assert c.quote_calls[0] == 100


@pytest.mark.asyncio
async def test_a_chain_larger_than_the_batch_ceiling_is_chunked(client):
    """Kite caps a quote request; oversized chains split rather than truncate."""
    c = client(450)

    contracts = await scanner._kite_option_contracts(
        "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))

    assert len(contracts) == 450
    assert len(c.quote_calls) > 1
    assert max(c.quote_calls) <= scanner._QUOTE_BATCH
    assert sum(c.quote_calls) == 450


@pytest.mark.asyncio
async def test_the_contracts_carry_the_same_fields_as_before(client):
    c = client(3)

    contracts = await scanner._kite_option_contracts(
        "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))

    first = sorted(contracts, key=lambda x: x.strike)[0]
    assert first.strike == 24000.0
    assert first.option_type == "CE"
    assert first.ltp == 120.0
    assert first.bid == 119.5 and first.ask == 120.5
    assert first.lot_size == 65
    assert first.volume == 50000.0 and first.open_interest == 900000.0
    assert first.expiry == c.expiry.isoformat()


@pytest.mark.asyncio
async def test_a_strike_the_batch_did_not_quote_is_dropped_not_faked(client):
    """A missing quote must not become a zero-priced contract."""
    c = client(3)
    real = c.get_quote

    async def partial(keys):
        got = await real(keys)
        return {k: v for k, v in got.items() if not k.endswith("24050")}

    c.get_quote = partial

    contracts = await scanner._kite_option_contracts(
        "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))

    assert sorted(x.strike for x in contracts) == [24000.0, 24100.0]


class _FailingClient(_CountingClient):
    """Quotes that fail the way a rate limit fails: an exception, not empty data."""

    def __init__(self, strikes: int, fail_on: set[int]):
        super().__init__(strikes)
        self.fail_on = fail_on

    async def get_quote(self, keys):
        idx = len(self.quote_calls)
        self.quote_calls.append(len(keys))
        if idx in self.fail_on:
            raise RuntimeError("Too many requests")
        return {k: {"last_price": 120.0, "volume": 50000, "oi": 900000,
                    "depth": {"buy": [{"price": 119.5}], "sell": [{"price": 120.5}]}}
                for k in keys}


@pytest.fixture
def failing(monkeypatch):
    def _install(strikes, fail_on):
        c = _FailingClient(strikes, fail_on)

        class _Accounts:
            @staticmethod
            def get_active(uid):
                return object()

            @staticmethod
            async def acquire_client(acct):
                return c

        import app.services.exchanges.kite as kite_pkg
        monkeypatch.setattr(kite_pkg, "accounts", _Accounts, raising=False)
        scanner._option_cache.clear()
        return c

    return _install


@pytest.mark.asyncio
async def test_a_failed_quote_batch_is_reported_not_read_as_an_empty_chain(failing):
    """A rate limit is not a liquidity verdict.

    Swallowing it left `contracts == []`, which `select_option` reports as "no
    liquid contracts satisfy expiry and liquidity settings" -- a sentence that
    sends you to the liquidity settings for a network problem.
    """
    failing(100, fail_on={0})

    with pytest.raises(ValueError, match="quote"):
        await scanner._kite_option_contracts(
            "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))


@pytest.mark.asyncio
async def test_a_failed_batch_is_never_cached(failing):
    """Caching the emptiness would make one throttled call blind the next four
    seconds of scans, long after the throttle cleared."""
    c = failing(100, fail_on={0})

    with pytest.raises(ValueError):
        await scanner._kite_option_contracts(
            "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))

    c.fail_on = set()
    contracts = await scanner._kite_option_contracts(
        "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))
    assert len(contracts) == 100


@pytest.mark.asyncio
async def test_a_partially_failed_chain_is_refused_rather_than_half_reported(failing):
    """Half a chain ranks strikes against a ladder that is missing rungs, so the
    'nearest eligible strike' it picks is not the nearest one that exists."""
    failing(450, fail_on={1})

    with pytest.raises(ValueError, match="quote"):
        await scanner._kite_option_contracts(
            "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))


@pytest.mark.asyncio
async def test_concurrent_chain_resolutions_are_paced_to_the_quote_limit(client, monkeypatch):
    """Kite counts the burst, so spacing has to be minimum-interval, not a bucket.

    `scan_user` gathers every configured underlying at once. With eight signals
    live that is eight simultaneous quote requests against a 3/sec ceiling, and
    Kite answered five of them with "Too many requests" -- which then surfaced as
    a chain failure on rows that had a perfectly good setup.
    """
    import asyncio, time
    c = client(10)
    stamps: list[float] = []
    real = c.get_quote

    async def timed(keys):
        stamps.append(time.monotonic())
        return await real(keys)

    c.get_quote = timed
    monkeypatch.setattr(scanner, "_QUOTE_PACER", scanner._MinSpacing(0.05))

    async def one(sym):
        scanner._option_cache.clear()
        return await scanner._kite_option_contracts(
            "u1", sym, "LONG", StrategyConfig(expiry_dte_max=7))

    await asyncio.gather(*(one(f"SYM{i}") for i in range(6)))

    assert len(stamps) == 6
    gaps = [b - a for a, b in zip(sorted(stamps), sorted(stamps)[1:])]
    assert all(g >= 0.04 for g in gaps), f"quote calls were not spaced: {gaps}"


@pytest.mark.asyncio
async def test_the_pacer_does_not_serialise_a_single_chain_into_slowness(client):
    """One batched call per chain means pacing costs one interval, not a hundred."""
    import time
    c = client(100)
    start = time.monotonic()
    await scanner._kite_option_contracts(
        "u1", "NIFTY", "LONG", StrategyConfig(expiry_dte_max=7))
    assert time.monotonic() - start < 1.0
    assert len(c.quote_calls) == 1
