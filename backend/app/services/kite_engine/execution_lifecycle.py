"""Recover durable live entries and protect only broker-confirmed holdings.

Broker observations are journaled before projection. Recovery repeats projection,
never submission. An uncertain initial GTT request requires reconciliation, not a
second trigger. Live scale-ins are blocked until a signed lot ledger is available.
"""
from __future__ import annotations

import asyncio
from dataclasses import fields

from app.services.kite_engine import order_journal as journal, positions, state

_locks: dict[tuple[str, str], asyncio.Lock] = {}


def account_id(client) -> str:
    value = str(getattr(client, "_account_id", "") or "")
    if not value:
        raise ValueError("live_account_identity_missing")
    return value


def register_pending(intent, order_id: str) -> positions.OpenPosition:
    """Idempotent projection of an accepted entry; ACK carries zero filled qty."""
    prior = positions.get(intent.uid, intent.symbol)
    if prior and prior.order_id == order_id and prior.account_id == intent.account_id:
        return prior
    if prior and prior.status in (positions.OPEN, positions.PENDING):
        raise ValueError("live_scale_in_or_account_collision")
    allowed = {f.name for f in fields(positions.OpenPosition)}
    payload = {k: v for k, v in intent.payload.items() if k in allowed}
    payload.update(uid=intent.uid, account_id=intent.account_id, product="NRML",
                   symbol=intent.symbol, exchange=intent.exchange, qty=0,
                   order_id=order_id, entry_requested_qty=intent.quantity,
                   entry_pending=True, status=positions.PENDING, qty_by_order={})
    p = positions.register(positions.OpenPosition(**payload))
    positions.persist_strict(intent.uid)
    if p.guard_key:
        state.mark_auto_open(intent.uid, p.guard_key)
    return p


async def _protect(client, p) -> None:
    from app.services.exchanges.kite import constants as K, ticker_manager
    from app.services.kite_engine import protective_stop as stops

    if p.qty <= 0 or p.status != positions.OPEN:
        return
    if p.token:
        try:
            await ticker_manager.subscribe(p.uid, [p.token], mode=K.MODE_LTP)
        except Exception:
            state.log(p.uid, "order_failed", f"{p.symbol}: live tick subscription unavailable")
    if p.stop_mode not in {"broker", "both"} or p.stop_premium <= 0:
        return
    if p.protection_pending:
        return  # prior placement could have succeeded; do not create a rival stop
    kwargs = dict(tradingsymbol=p.symbol, exchange=p.exchange, qty=p.qty,
                  trigger_premium=p.stop_premium, last_price=p.fill_price,
                  direction=p.direction, target_premium=p.target_premium)
    if p.gtt_id:
        if not await stops.move_stop(client, trigger_id=p.gtt_id, **kwargs):
            p.protection_pending = True
            positions.persist_strict(p.uid)
        return
    p.protection_pending = True
    positions.persist_strict(p.uid)  # durable before network: crash/timeout is uncertain
    gid = await stops.place_stop(client, **kwargs)
    if gid:
        p.gtt_id = int(gid)
        p.protection_pending = False
        positions.persist_strict(p.uid)
    else:
        state.log(p.uid, "order_failed", f"{p.symbol}: GTT outcome unresolved; reconcile before retry")


async def consume_order(client, uid: str, order: dict) -> bool:
    """True means a journal-owned entry was handled (including blocked evidence)."""
    aid = account_id(client)
    oid = str(order.get("order_id") or "")
    symbol = str(order.get("tradingsymbol") or "")
    intent = journal.find(uid=uid, account_id=aid, order_id=oid,
                          tag=str(order.get("tag") or ""))
    if intent is None:
        return False
    # The active client's authenticated order book/postback must agree with the
    # persisted contract. Missing or contradictory identity is never inferred.
    if (symbol != intent.symbol or order.get("exchange") != intent.exchange
            or str(order.get("transaction_type") or "").upper() != intent.side.upper()
            or order.get("product") != "NRML"
            or int(order.get("quantity") or 0) != intent.quantity):
        state.log(uid, "order_failed", f"{intent.symbol}: journal/broker identity mismatch")
        return True
    async with _locks.setdefault((uid, aid), asyncio.Lock()):
        observed = journal.observe_order(
            intent.intent_key, status=str(order.get("status") or ""), order_id=oid,
            filled_quantity=order.get("filled_quantity", 0),
            average_price=order.get("average_price", 0), raw=order)
        if observed.reconciliation_required:
            state.log(uid, "order_failed", f"{symbol}: conflicting broker fill evidence")
            return True
        if not observed.accepted and not observed.intent.projection_pending:
            p = positions.get(uid, symbol)
            if p and p.order_id == oid and p.account_id == aid and not p.gtt_id:
                await _protect(client, p)
            return True
        # Replaying a terminal event for an already closed position must not reopen it.
        p = register_pending(observed.intent, oid)
        if p.status in (positions.CLOSED, positions.REJECTED):
            journal.mark_projected(intent.intent_key, observed.intent.projection_version)
            return True
        latest = observed.intent
        filled = latest.filled_quantity
        p.qty = filled
        p.qty_by_order = {oid: filled} if filled else {}
        p.fill_price = latest.filled_value / filled if filled else 0.0
        p.entry_pending = latest.state not in journal.TERMINAL
        p.status = (positions.OPEN if filled else
                    positions.PENDING if p.entry_pending else positions.REJECTED)
        positions.persist_strict(uid)
        journal.mark_projected(intent.intent_key, latest.projection_version)
        if p.status == positions.REJECTED and p.guard_key:
            state.clear_auto_open(uid, p.guard_key)
        await _protect(client, p)
    return True


async def recover(client, uid: str) -> None:
    """Find accepted/unknown entries even when the registry was never written."""
    aid = account_id(client)
    candidates = {i.intent_key: i for i in
                  journal.unresolved(uid, account_id=aid) + journal.pending_projection(uid, aid)}
    # Repair a known missing trigger after restart/cancel, never an unknown submit.
    for p in positions.open_positions(uid):
        if p.account_id == aid and not p.gtt_id and not p.protection_pending:
            await _protect(client, p)
    if not candidates:
        return
    book = await client.get_orders()
    if not isinstance(book, list):
        raise ValueError("malformed_broker_order_book")
    for intent in candidates.values():
        if intent.state == "RESERVED":
            continue  # no send claim; only the originating validated request may claim
        matches = [o for o in book if isinstance(o, dict) and
                   ((intent.order_id and o.get("order_id") == intent.order_id)
                    or o.get("tag") == intent.tag)]
        if not matches and intent.order_id:
            history = await client.get_order_history(intent.order_id)
            matches = [history[-1]] if history and isinstance(history[-1], dict) else []
        if len(matches) == 1:
            await consume_order(client, uid, matches[0])
        else:
            state.log(uid, "order_failed", f"{intent.symbol}: broker entry unresolved; no resubmission")
