"""Non-transient Kite errors must not be retried.

A universe scan while logged out used to emit, per symbol, four WARNING lines,
one ERROR with a full traceback, and 2s of pointless sleeping — because the
retry loop caught `Exception` and a missing session looks exactly like a flaky
network to `except Exception`. It is not: the second attempt has identical
inputs and an identical outcome.
"""
import pytest

from app.services.exchanges.kite.errors import (
    KiteError, KiteInputError, KiteMarginError, KiteNetworkError, KiteOrderError,
    KitePermissionError, KiteTokenError, is_retryable,
)


@pytest.mark.parametrize("exc", [
    KiteTokenError("log in first", error_type="TokenException"),
    KitePermissionError("not permitted", error_type="PermissionException"),
    KiteInputError("bad params", error_type="InputException"),
    KiteOrderError("rejected", error_type="OrderException"),
    KiteMarginError("no funds", error_type="MarginException"),
])
def test_deterministic_failures_are_not_retryable(exc):
    assert is_retryable(exc) is False


@pytest.mark.parametrize("exc", [
    KiteNetworkError("oms down", error_type="NetworkException"),
    KiteError("general failure", error_type="GeneralException"),
    KiteError("data again", error_type="DataException"),
    TimeoutError("socket timeout"),
    RuntimeError("transport closed"),
])
def test_transient_failures_stay_retryable(exc):
    assert is_retryable(exc) is True


def test_rate_limit_is_retryable_even_wearing_another_error_type():
    """429 is transient regardless of how Kite labelled it."""
    assert is_retryable(KiteInputError("too many", error_type="InputException", status_code=429)) is True
    assert is_retryable(RuntimeError("HTTP 429 Too Many Requests")) is True


@pytest.mark.asyncio
async def test_get_candles_fails_fast_on_a_missing_session(monkeypatch, caplog):
    """One attempt, one concise line, no traceback, no sleeping."""
    import logging
    from app.services.exchanges.kite.client import KiteClient

    client = KiteClient.__new__(KiteClient)          # no network, no session
    calls = {"n": 0}

    async def boom(*a, **k):
        calls["n"] += 1
        raise KiteTokenError("Kite account access requires api_key + access_token — log in first.",
                             error_type="TokenException")

    slept = {"n": 0}

    async def no_sleep(_):
        slept["n"] += 1

    monkeypatch.setattr(client, "get_historical", boom, raising=False)
    monkeypatch.setattr("app.services.exchanges.kite.client.asyncio.sleep", no_sleep)

    class Inst:
        underlying = "TCS"
        zerodha_token = 1
        instrument_token = 1
        tradingsymbol = "TCS"

    with caplog.at_level(logging.WARNING):
        out = await client.get_candles(Inst(), "60m", limit=10)

    assert out == []
    assert calls["n"] == 1, "a missing session must not be retried"
    assert slept["n"] == 0, "a missing session must not sleep between retries"
    records = [r for r in caplog.records if "TCS" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].exc_info is None, "an expected state must not log a traceback"
