"""An unreachable expiry window must say so, not return an empty chain.

The live config carried ``expiry_dte_min=0, expiry_dte_max=0`` -- only contracts
expiring *today*. On every non-expiry day that filtered the whole chain away, and
``_kite_option_contracts`` returned ``[]``. ``select_option`` then raised the
generic "No liquid CE contracts satisfy expiry and liquidity settings", which
points at liquidity when the actual cause was the DTE window, so the board showed
a blocked signal with a reason that sent you looking in the wrong place.

Single-stock options make this permanent rather than occasional: they are
monthly-only, so their nearest expiry can sit ~30 days out and no DTE ceiling of
7 (the shipped default) can ever reach one.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.engines.nifty_orb_options import StrategyConfig
from app.services import nifty_orb_scanner as scanner

IST = timezone(timedelta(hours=5, minutes=30))


class _Client:
    """Minimal Kite stand-in: an instrument list and a quote per symbol."""

    def __init__(self, expiries: list[date]):
        self._expiries = expiries

    async def search_instruments(self, name, exchange, limit=0):
        if exchange != "NFO":
            return []
        return [
            {"name": name, "instrument_type": "CE", "expiry": e.isoformat(),
             "tradingsymbol": f"{name}{e:%y%b}".upper() + f"{strike}CE",
             "exchange": "NFO", "strike": strike, "lot_size": 50}
            for e in self._expiries
            for strike in (24000, 24100, 24200)
        ]

    async def get_quote(self, keys):
        return {k: {"last_price": 120.0, "volume": 50000, "oi": 900000,
                    "depth": {"buy": [{"price": 119.5}], "sell": [{"price": 120.5}]}}
                for k in keys}


@pytest.fixture
def kite(monkeypatch):
    """Route the scanner's account lookup at the fake client above."""
    def _install(expiries):
        client = _Client(expiries)

        class _Accounts:
            @staticmethod
            def get_active(uid):
                return object()

            @staticmethod
            async def acquire_client(acct):
                return client

        import app.services.exchanges.kite as kite_pkg
        monkeypatch.setattr(kite_pkg, "accounts", _Accounts, raising=False)
        scanner._option_cache.clear()
        return client

    return _install


def _today() -> date:
    return datetime.now(IST).date()


@pytest.mark.asyncio
async def test_window_that_reaches_no_expiry_names_the_window_and_the_gap(kite):
    """The failure has to be self-diagnosing: which window, and how far off."""
    kite([_today() + timedelta(days=33)])          # monthly-only, like a stock
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=0)

    with pytest.raises(ValueError) as exc:
        await scanner._kite_option_contracts("u1", "RELIANCE", "LONG", cfg)

    message = str(exc.value)
    assert "0-0" in message                        # the window that was applied
    assert "33" in message                         # the nearest expiry that exists
    assert "RELIANCE" in message


@pytest.mark.asyncio
async def test_the_shipped_default_still_cannot_reach_a_monthly_stock_expiry(kite):
    """Documents why `expiry_dte_max` had to move, not just be un-zeroed."""
    kite([_today() + timedelta(days=33)])
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=7)

    with pytest.raises(ValueError, match="33"):
        await scanner._kite_option_contracts("u1", "RELIANCE", "LONG", cfg)


@pytest.mark.asyncio
async def test_a_window_that_reaches_the_expiry_returns_the_chain(kite):
    kite([_today() + timedelta(days=33)])
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=35)

    contracts = await scanner._kite_option_contracts("u1", "RELIANCE", "LONG", cfg)

    assert [c.strike for c in contracts] == [24000.0, 24100.0, 24200.0]
    assert {c.option_type for c in contracts} == {"CE"}


@pytest.mark.asyncio
async def test_an_underlying_with_no_listed_options_is_still_an_empty_chain(kite):
    """No instruments at all is a different condition from a missed window.

    It must not masquerade as one -- there is no nearest expiry to report.
    """
    kite([])
    cfg = StrategyConfig(expiry_dte_min=0, expiry_dte_max=35)

    assert await scanner._kite_option_contracts("u1", "NOSUCH", "LONG", cfg) == []
