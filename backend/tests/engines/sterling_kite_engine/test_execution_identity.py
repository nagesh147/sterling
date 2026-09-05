"""Broker identity and exposure safety mechanics; no market-performance evidence."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.exchanges.kite import accounts
from app.services.exchanges.kite.models import KiteAccountCreate, KiteAccountUpdate
from app.services.kite_engine import monitor, positions, state


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["paper", "secret", "token", "broker_identity"])
async def test_cached_client_rebuilt_after_execution_identity_change(monkeypatch, change):
    account = accounts.add("identity-cache", KiteAccountCreate(
        label="test", api_key="test-key", api_secret="test-secret", is_paper=False))
    created = []

    def build(value):
        client = SimpleNamespace(close=AsyncMock(), _is_paper=value.is_paper)
        created.append(client)
        return client

    monkeypatch.setattr(accounts, "build_client", build)
    original = await accounts.acquire_client(account)
    assert await accounts.acquire_client(account) is original
    if change == "paper":
        accounts.update(account.user_id, account.id, KiteAccountUpdate(is_paper=True))
    elif change == "secret":
        accounts.update(account.user_id, account.id, KiteAccountUpdate(api_secret="new-secret"))
    elif change == "token":
        accounts.save_session(account.user_id, account.id, access_token="new-token")
    else:
        account.kite_user_id = "another-broker-user"
    replacement = await accounts.acquire_client(account)
    assert replacement is not original and len(created) == 2
    original.close.assert_awaited_once()
    if change == "paper":
        assert replacement._is_paper is True


def test_retained_client_identity_is_invalidated_immediately_on_mode_change():
    account = accounts.add("identity-retained", KiteAccountCreate(
        label="test", api_key="test-key", api_secret="test-secret", is_paper=False))
    client = accounts.build_client(account)
    assert accounts.client_is_current(client, user_id=account.user_id)
    accounts.update(account.user_id, account.id, KiteAccountUpdate(is_paper=True))
    assert not accounts.client_is_current(client, user_id=account.user_id)


def _row(quantity=50, **changes):
    return {"tradingsymbol": "OPT", "exchange": "NFO", "product": "NRML",
            "quantity": quantity, **changes}


def _client(rows=None, account_id="account-a"):
    return SimpleNamespace(
        _is_paper=False, _account_id=account_id, _account_generation="",
        get_positions_raw=AsyncMock(return_value={"net": rows if rows is not None else [_row()]}),
        place_order_option=AsyncMock(return_value={"order_id": "exit-1"}),
        cancel_order=AsyncMock(return_value={"order_id": "entry-1"}),
        get_order_history=AsyncMock(return_value=[]))


@pytest.mark.asyncio
@pytest.mark.parametrize("rows", [[], [_row(exchange="BFO")], [_row(product="MIS")],
    [{"tradingsymbol": "OPT", "quantity": 50}], [_row(quantity=float("nan"))],
    [_row(quantity=1.5)], [_row(), _row()]])
async def test_live_holdings_need_unambiguous_matching_contract_rows(rows):
    assert await monitor._broker_holding(_client(rows), "identity-holdings", "OPT", fresh=True) is None


@pytest.mark.asyncio
async def test_holdings_cache_is_account_scoped_and_exit_can_force_fresh_read():
    monitor.forget_holdings("identity-cache-holdings")
    first, second = _client([_row(50)]), _client([_row(0)], account_id="account-b")
    assert await monitor._broker_holding(first, "identity-cache-holdings", "OPT") == 50
    assert await monitor._broker_holding(second, "identity-cache-holdings", "OPT") == 0
    first.get_positions_raw.return_value = {"net": [_row(10)]}
    assert await monitor._broker_holding(first, "identity-cache-holdings", "OPT", fresh=True) == 10
    assert first.get_positions_raw.await_count == 2


def _position(uid, **changes):
    positions.reset(uid)
    state.reset(uid)
    values = dict(uid=uid, symbol="OPT", exchange="NFO", qty=50,
                  status=positions.OPEN, order_id="entry-1", stop_premium=80,
                  entry_premium=100, fill_price=100, gtt_id=123, account_id="account-a")
    return positions.register(positions.OpenPosition(**{**values, **changes}))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "missing", "other_account", "opposite"])
async def test_unknown_or_mismatched_live_holdings_preserve_gtt(monkeypatch, failure):
    uid = "identity-exit-" + failure
    p = _position(uid)
    client = _client()
    if failure == "timeout":
        client.get_positions_raw.side_effect = TimeoutError("unavailable")
    elif failure == "missing":
        client.get_positions_raw.return_value = {"net": []}
    elif failure == "opposite":
        client.get_positions_raw.return_value = {"net": [_row(-50)]}
    else:
        client._account_id = "account-b"
    cancel = AsyncMock(return_value=monitor.pstop.CANCELLED)
    monkeypatch.setattr(monitor.pstop, "cancel_stop_result", cancel)
    assert not await monitor._exit_position(client, uid, p, 79)
    cancel.assert_not_awaited()
    client.place_order_option.assert_not_awaited()
    assert p.gtt_id == 123 and p.status == positions.OPEN


@pytest.mark.asyncio
async def test_pending_entry_cancel_ack_without_terminal_history_preserves_protection(monkeypatch):
    uid = "identity-pending-entry"
    p = _position(uid, entry_pending=True)
    client = _client()
    client.get_order_history.return_value = [dict(order_id="entry-1", status="OPEN")]
    cancel = AsyncMock(return_value=monitor.pstop.CANCELLED)
    monkeypatch.setattr(monitor.pstop, "cancel_stop_result", cancel)
    assert not await monitor._exit_position(client, uid, p, 79)
    client.cancel_order.assert_awaited_once_with("entry-1")
    cancel.assert_not_awaited()
    client.place_order_option.assert_not_awaited()
    assert p.gtt_id == 123


@pytest.mark.asyncio
async def test_live_exit_rechecks_matching_holdings_after_gtt_cancel(monkeypatch):
    uid = "identity-fresh-exit"
    p = _position(uid)
    client = _client()
    client.get_positions_raw.side_effect = [{"net": [_row(50)]}, {"net": [_row(10)]}]
    cancel = AsyncMock(return_value=monitor.pstop.CANCELLED)
    monkeypatch.setattr(monitor.pstop, "cancel_stop_result", cancel)
    assert await monitor._exit_position(client, uid, p, 79)
    assert client.get_positions_raw.await_count == 2
    assert client.place_order_option.await_args.args == ("OPT", "sell", 10)
    assert p.pnl_reconciliation_required


@pytest.mark.asyncio
async def test_live_exit_storage_failure_precedes_broker_mutation(monkeypatch):
    uid = "identity-durability"
    p = _position(uid)
    client = _client()
    cancel = AsyncMock(return_value=monitor.pstop.CANCELLED)
    monkeypatch.setattr(monitor.pstop, "cancel_stop_result", cancel)

    def fail(uid):
        raise OSError("storage unavailable")

    monkeypatch.setattr(positions, "persist_strict", fail)
    assert not await monitor._exit_position(client, uid, p, 79)
    cancel.assert_not_awaited()
    client.cancel_order.assert_not_awaited()
    client.place_order_option.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_holdings_failure_after_confirmed_cancel_allows_protection_repair(monkeypatch):
    uid = "identity-postcancel-read"
    p = _position(uid)
    client = _client()
    client.get_positions_raw.side_effect = [{"net": [_row(50)]}, TimeoutError("unavailable")]
    cancel = AsyncMock(return_value=monitor.pstop.CANCELLED)
    monkeypatch.setattr(monitor.pstop, "cancel_stop_result", cancel)
    assert not await monitor._exit_position(client, uid, p, 79)
    assert p.gtt_id == 0 and not p.protection_pending
    client.place_order_option.assert_not_awaited()
