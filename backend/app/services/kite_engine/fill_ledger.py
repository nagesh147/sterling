"""Signed, transactional execution ledger: the one place account inventory,
average cost, fees and realized PnL are derived from broker fill evidence.

Why a ledger rather than a running total
----------------------------------------
Realized PnL used to be a single float per user (``state.record_realized_pnl``)
booked once per POSITION from one "exit price", guarded by a boolean on the
in-memory position row. That cannot survive the things a real broker feed does:
two partial exits at different prices collapse to one average, a restated
average price silently changes a number that was already spent, fees never enter
the figure at all, and a crash between the fill and the write loses the whole
day. The daily-loss breaker reads that number, so a wrong one is a real-money
failure, not a reporting one.

This module records one immutable row per execution INCREMENT and derives
everything else by REPLAYING those rows in a canonical order on every write.
Replay is what makes the ledger converge instead of drift:

* **Duplicate / replayed evidence** — an increment is keyed by the cumulative
  quantity the broker reported for that order, so the same postback twice lands
  on the same row and books nothing the second time.
* **Out-of-order evidence** — cumulative quantity below what is already recorded
  is older evidence and is ignored; an increment that arrives late relative to
  *another* order for the same symbol is reordered by timestamp during replay,
  so average cost and realized PnL come out as if it had arrived on time.
* **Corrections** — the same cumulative quantity with a different value is a
  restatement, not a fill. It is quarantined in ``kite_execution_conflicts`` and
  the inventory is flagged; it is never dropped and never silently applied.
* **Crash** — the increment, every recomputed ``realized_delta`` and the derived
  inventory are written in ONE ``BEGIN IMMEDIATE`` transaction at
  ``synchronous=FULL``. There is no window in which quantity is booked but its
  cost or realized value is not.

Sign convention: ``signed_quantity`` is positive for BUY and negative for SELL,
so one formula serves long options and short futures alike.

Costs are levied per ORDER and are only knowable from the broker, so they arrive
separately through ``apply_fees`` and always reduce realized PnL. Until every
fill behind a holding has been costed, ``Inventory.realized_is_gross`` is true
and the realized figure reads BETTER than the truth — the direction that delays
the daily-loss breaker rather than tripping it early. A recorded cost must carry
its provenance: "0 because nobody asked" and "0 because it was free" are
different claims, and ``record`` refuses a fee without a source.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from math import isclose, isfinite
import time
from typing import Any, Dict, List, Optional, Tuple

from app.services import db

#: Sources allowed to book quantity. Kept explicit so a new execution path has to
#: declare itself rather than inheriting the entry path's accounting by accident.
SOURCES = {"entry", "exit", "gtt", "recovery", "reconciliation"}

_IST = timezone(timedelta(hours=5, minutes=30))


@dataclass(frozen=True)
class Inventory:
    """Derived holding for one (account, uid, symbol). Signed quantity."""
    account_id: str
    uid: str
    symbol: str
    exchange: str
    net_quantity: int
    average_cost: float
    realized_pnl: float
    fees: float
    reconciliation_required: bool
    reconciliation_reason: str
    version: int
    lot_size: int = 0
    fees_complete: bool = False

    @property
    def is_flat(self) -> bool:
        return self.net_quantity == 0

    @property
    def realized_is_gross(self) -> bool:
        """True while some fill's costs are still unknown, so ``realized_pnl`` is
        better than the true figure. Charges are only knowable from the broker."""
        return not self.fees_complete

    @property
    def net_lots(self) -> Optional[int]:
        """Signed exchange lots, or None when no fill has told us the lot size.

        Quantity stays the unit for every value and risk figure — lots are what an
        operator and the broker's own screens count in, so the ledger records the
        lot size the fill was booked against rather than leaving it to a join
        against an instrument master that may have moved on since.
        """
        if not self.lot_size or self.net_quantity % self.lot_size:
            return None
        return self.net_quantity // self.lot_size


@dataclass(frozen=True)
class Applied:
    """Outcome of one ``record`` call."""
    accepted: bool
    reason: str
    delta_quantity: int
    delta_value: float
    realized_delta: float
    inventory: Inventory

    @property
    def reconciliation_required(self) -> bool:
        return self.inventory.reconciliation_required


# ── validation ───────────────────────────────────────────────────────────────
# Deliberately strict: a NaN price or a bool masquerading as an int must fail at
# the door, because the ledger is what the breaker and the exit paths trust.

def _ready() -> None:
    if not db.is_available():
        raise RuntimeError("durable_fill_ledger_unavailable")


@contextmanager
def _transaction():
    _ready()
    with db._conn() as conn:
        conn.execute("PRAGMA synchronous=FULL")
        if conn.execute("PRAGMA synchronous").fetchone()[0] != 2:
            raise RuntimeError("durable_fill_ledger_full_sync_unavailable")
        conn.execute("BEGIN IMMEDIATE")
        yield conn


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"invalid_{label}")
    return value


def _int(value: Any, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"invalid_{label}")
    return value


def _amount(value: Any, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise ValueError(f"invalid_{label}")
    value = float(value)
    if not isfinite(value) or value < minimum:
        raise ValueError(f"invalid_{label}")
    return value


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      default=str)


def ist_day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, _IST).date().isoformat()


def ist_today() -> str:
    return datetime.now(_IST).date().isoformat()


# ── replay ───────────────────────────────────────────────────────────────────

def _canonical(conn, account_id: str, uid: str, symbol: str) -> List[Any]:
    """Every increment for one holding, in the order the exchange saw them.

    Ordering by the exchange timestamp (falling back to arrival, then the insert
    id) is what lets a late increment for an earlier fill land in its true place:
    average cost is path-dependent, so replaying in arrival order would book a
    different realized PnL than the same fills in the right order.
    """
    return list(conn.execute(
        """SELECT id, signed_quantity, lot_size, price, fees, fees_source, realized_delta
             FROM kite_execution_increments
            WHERE account_id=? AND uid=? AND symbol=?
            ORDER BY COALESCE(NULLIF(exchange_ts_ms,0), received_ts_ms),
                     received_ts_ms, id""",
        (account_id, uid, symbol)))


def _replay(rows: List[Any]) -> Tuple[int, float, float, float, Dict[int, float]]:
    """Average-cost replay. Returns net, average cost, realized, fees, per-row realized."""
    net = 0
    avg = 0.0
    realized = 0.0
    fees_total = 0.0
    per_row: Dict[int, float] = {}
    for row in rows:
        qty = int(row["signed_quantity"])
        price = float(row["price"])
        fees = float(row["fees"])
        fees_total += fees
        row_realized = -fees  # fees hit PnL when they are incurred
        if qty == 0:
            per_row[int(row["id"])] = row_realized
            realized += row_realized
            continue
        if net == 0 or (net > 0) == (qty > 0):
            # Opening or adding to the same side: blend the cost.
            gross = abs(net) + abs(qty)
            avg = (avg * abs(net) + price * abs(qty)) / gross
            net += qty
        else:
            # Reducing, closing, or flipping through zero.
            closing = min(abs(net), abs(qty))
            direction = 1.0 if net > 0 else -1.0
            row_realized += (price - avg) * closing * direction
            remaining = abs(qty) - closing
            net += qty
            if remaining > 0:
                avg = price      # flipped: the surplus opens the other side
            elif net == 0:
                avg = 0.0
        realized += row_realized
        per_row[int(row["id"])] = row_realized
    return net, avg, realized, fees_total, per_row


def _row_to_inventory(row) -> Inventory:
    return Inventory(
        account_id=row["account_id"], uid=row["uid"], symbol=row["symbol"],
        exchange=row["exchange"], net_quantity=int(row["net_quantity"]),
        average_cost=float(row["average_cost"]), realized_pnl=float(row["realized_pnl"]),
        fees=float(row["fees"]),
        reconciliation_required=bool(row["reconciliation_required"]),
        reconciliation_reason=row["reconciliation_reason"], version=int(row["version"]),
        lot_size=int(row["lot_size"]), fees_complete=bool(row["fees_complete"]))


def _read_inventory(conn, account_id: str, uid: str, symbol: str) -> Optional[Inventory]:
    row = conn.execute("SELECT * FROM kite_inventory WHERE account_id=? AND uid=? AND symbol=?",
                       (account_id, uid, symbol)).fetchone()
    return _row_to_inventory(row) if row else None


def _empty(account_id: str, uid: str, symbol: str, exchange: str, *,
           reason: str = "") -> Inventory:
    return Inventory(account_id=account_id, uid=uid, symbol=symbol, exchange=exchange,
                     net_quantity=0, average_cost=0.0, realized_pnl=0.0, fees=0.0,
                     reconciliation_required=bool(reason), reconciliation_reason=reason,
                     version=0)


def _project(conn, account_id: str, uid: str, symbol: str, exchange: str, *,
             flag: str = "") -> Inventory:
    """Recompute the derived row from the increments and persist it.

    ``flag`` sets (never clears) the reconciliation reason: quarantined evidence
    must keep the holding flagged until an operator resolves it.
    """
    rows = _canonical(conn, account_id, uid, symbol)
    net, avg, realized, fees_total, per_row = _replay(rows)
    # The most recent fill that knew the lot size wins: a contract's lot size can
    # be revised, and what matters is the size the position is actually held in.
    lot_size = next((int(r["lot_size"]) for r in reversed(rows) if r["lot_size"]), 0)
    fees_complete = bool(rows) and all(r["fees_source"] for r in rows)
    for row in rows:
        recomputed = per_row[int(row["id"])]
        if not isclose(recomputed, float(row["realized_delta"]), rel_tol=1e-12, abs_tol=1e-9):
            conn.execute("UPDATE kite_execution_increments SET realized_delta=? WHERE id=?",
                         (recomputed, int(row["id"])))
    existing = _read_inventory(conn, account_id, uid, symbol)
    reason = flag or (existing.reconciliation_reason if existing else "")
    required = 1 if reason else 0
    now = int(time.time() * 1000)
    version = (existing.version if existing else 0) + 1
    conn.execute(
        """INSERT INTO kite_inventory
             (account_id,uid,symbol,exchange,net_quantity,lot_size,average_cost,
              realized_pnl,fees,fees_complete,reconciliation_required,
              reconciliation_reason,version,updated_ms)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(account_id,uid,symbol) DO UPDATE SET
             exchange=excluded.exchange, net_quantity=excluded.net_quantity,
             lot_size=excluded.lot_size,
             average_cost=excluded.average_cost, realized_pnl=excluded.realized_pnl,
             fees=excluded.fees, fees_complete=excluded.fees_complete,
             reconciliation_required=excluded.reconciliation_required,
             reconciliation_reason=excluded.reconciliation_reason,
             version=excluded.version, updated_ms=excluded.updated_ms""",
        (account_id, uid, symbol, exchange, net, lot_size, avg, realized, fees_total,
         1 if fees_complete else 0, required, reason, version, now))
    return Inventory(account_id=account_id, uid=uid, symbol=symbol, exchange=exchange,
                     net_quantity=net, average_cost=avg, realized_pnl=realized,
                     fees=fees_total, reconciliation_required=bool(reason),
                     reconciliation_reason=reason, version=version, lot_size=lot_size,
                     fees_complete=fees_complete)


def _quarantine(conn, *, account_id: str, uid: str, symbol: str, exchange: str,
                order_id: str, side: str, cumulative_quantity: int,
                cumulative_value: float, reason: str, raw: str) -> Inventory:
    conn.execute(
        """INSERT INTO kite_execution_conflicts
             (account_id,uid,symbol,order_id,side,cumulative_quantity,cumulative_value,
              reason,received_ts_ms,raw_json) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (account_id, uid, symbol, order_id, side, cumulative_quantity, cumulative_value,
         reason, int(time.time() * 1000), raw))
    return _project(conn, account_id, uid, symbol, exchange, flag=reason)


# ── the write path ───────────────────────────────────────────────────────────

def record(*, account_id: str, uid: str, symbol: str, exchange: str, side: str,
           order_id: str, cumulative_quantity: int, cumulative_value: float,
           source: str, lot_size: int = 0, fees: float = 0.0,
           fees_source: str = "", exchange_ts_ms: int = 0,
           raw: Optional[Dict[str, Any]] = None) -> Applied:
    """Apply one piece of cumulative broker evidence for ``order_id``.

    Callers forward whatever the broker last said about the order — cumulative
    filled quantity and cumulative value — and never compute a delta themselves.
    The ledger owns that arithmetic against its own durable rows, which is what
    makes the call safe to repeat after a duplicate postback, a reconnect or a
    crash.
    """
    account_id = _text(account_id, "account_id")
    uid = _text(uid, "uid")
    symbol = _text(symbol, "symbol")
    exchange = _text(exchange, "exchange")
    order_id = _text(order_id, "order_id")
    side = _text(side, "side").upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("invalid_side")
    if source not in SOURCES:
        raise ValueError("invalid_source")
    cumulative_quantity = _int(cumulative_quantity, "cumulative_quantity")
    cumulative_value = _amount(cumulative_value, "cumulative_value")
    fees = _amount(fees, "fees")
    if fees and not fees_source:
        # A cost figure with no provenance cannot be told apart from "not asked yet".
        raise ValueError("invalid_fees_source")
    lot_size = _int(lot_size, "lot_size")
    exchange_ts_ms = _int(exchange_ts_ms, "exchange_ts_ms")
    encoded_raw = _json(raw or {})
    now = int(time.time() * 1000)

    with _transaction() as conn:
        prior = conn.execute(
            """SELECT uid, symbol, side, cumulative_quantity, cumulative_value
                 FROM kite_execution_increments WHERE account_id=? AND order_id=?
                ORDER BY cumulative_quantity DESC LIMIT 1""",
            (account_id, order_id)).fetchone()
        prior_qty = int(prior["cumulative_quantity"]) if prior else 0
        if prior is not None and (prior["uid"] != uid or prior["symbol"] != symbol
                                  or prior["side"] != side):
            # One order id cannot belong to two contracts, two users, or change
            # side. Accepting it would attribute someone else's fill to this holding.
            inv = _quarantine(conn, account_id=account_id, uid=uid, symbol=symbol,
                              exchange=exchange, order_id=order_id, side=side,
                              cumulative_quantity=cumulative_quantity,
                              cumulative_value=cumulative_value,
                              reason="order_identity_conflict", raw=encoded_raw)
            return Applied(False, "order_identity_conflict", 0, 0.0, 0.0, inv)

        if cumulative_quantity == 0:
            inv = (_read_inventory(conn, account_id, uid, symbol)
                   or _empty(account_id, uid, symbol, exchange))
            return Applied(False, "no_quantity", 0, 0.0, 0.0, inv)

        existing = conn.execute(
            """SELECT cumulative_value FROM kite_execution_increments
                WHERE account_id=? AND order_id=? AND cumulative_quantity=?""",
            (account_id, order_id, cumulative_quantity)).fetchone()
        if existing is not None:
            if isclose(float(existing["cumulative_value"]), cumulative_value,
                       rel_tol=1e-9, abs_tol=1e-6):
                inv = (_read_inventory(conn, account_id, uid, symbol)
                       or _empty(account_id, uid, symbol, exchange))
                return Applied(False, "duplicate", 0, 0.0, 0.0, inv)
            inv = _quarantine(conn, account_id=account_id, uid=uid, symbol=symbol,
                              exchange=exchange, order_id=order_id, side=side,
                              cumulative_quantity=cumulative_quantity,
                              cumulative_value=cumulative_value,
                              reason="cumulative_value_correction", raw=encoded_raw)
            return Applied(False, "cumulative_value_correction", 0, 0.0, 0.0, inv)

        if cumulative_quantity < prior_qty:
            if cumulative_value >= float(prior["cumulative_value"]):
                # Prices are positive, so fewer shares cannot be worth more. One of
                # the two figures is wrong and we cannot tell which.
                inv = _quarantine(conn, account_id=account_id, uid=uid, symbol=symbol,
                                  exchange=exchange, order_id=order_id, side=side,
                                  cumulative_quantity=cumulative_quantity,
                                  cumulative_value=cumulative_value,
                                  reason="nonmonotonic_cumulative_value", raw=encoded_raw)
                return Applied(False, "nonmonotonic_cumulative_value", 0, 0.0, 0.0, inv)
            # Older evidence, not a contradiction: the broker simply told us about
            # a state we have already moved past. Nothing to book, nothing to flag.
            inv = (_read_inventory(conn, account_id, uid, symbol)
                   or _empty(account_id, uid, symbol, exchange))
            return Applied(False, "older_cumulative", 0, 0.0, 0.0, inv)

        prior_value = float(prior["cumulative_value"]) if prior else 0.0
        delta_qty = cumulative_quantity - prior_qty
        delta_value = cumulative_value - prior_value
        if delta_value <= 0 or not isfinite(delta_value):
            inv = _quarantine(conn, account_id=account_id, uid=uid, symbol=symbol,
                              exchange=exchange, order_id=order_id, side=side,
                              cumulative_quantity=cumulative_quantity,
                              cumulative_value=cumulative_value,
                              reason="nonpositive_incremental_value", raw=encoded_raw)
            return Applied(False, "nonpositive_incremental_value", 0, 0.0, 0.0, inv)
        price = delta_value / delta_qty
        if not isfinite(price) or price <= 0:
            inv = _quarantine(conn, account_id=account_id, uid=uid, symbol=symbol,
                              exchange=exchange, order_id=order_id, side=side,
                              cumulative_quantity=cumulative_quantity,
                              cumulative_value=cumulative_value,
                              reason="invalid_incremental_price", raw=encoded_raw)
            return Applied(False, "invalid_incremental_price", 0, 0.0, 0.0, inv)

        signed = delta_qty if side == "BUY" else -delta_qty
        effective_ms = exchange_ts_ms or now
        conn.execute(
            """INSERT INTO kite_execution_increments
                 (account_id,uid,symbol,exchange,order_id,side,source,cumulative_quantity,
                  cumulative_value,signed_quantity,lot_size,price,fees,fees_source,
                  realized_delta,day_iso,exchange_ts_ms,received_ts_ms,raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (account_id, uid, symbol, exchange, order_id, side, source,
             cumulative_quantity, cumulative_value, signed, lot_size, price, fees,
             fees_source, 0.0, ist_day(effective_ms), exchange_ts_ms, now, encoded_raw))
        inserted_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        inv = _project(conn, account_id, uid, symbol, exchange)
        realized_delta = float(conn.execute(
            "SELECT realized_delta FROM kite_execution_increments WHERE id=?",
            (inserted_id,)).fetchone()["realized_delta"])
        return Applied(True, "accepted", delta_qty, delta_value, realized_delta, inv)


def apply_fees(*, account_id: str, uid: str, symbol: str, order_id: str,
               fees: float, source: str = "broker") -> Optional[Inventory]:
    """Attach an order's broker charges to the ledger and reproject.

    Charges are levied per ORDER, not per execution increment, so splitting them
    across increments would invent a precision the broker never reported. The
    whole figure lands on that order's final increment and every increment of the
    order is marked as costed, which is what turns ``realized_is_gross`` off.

    Unlike a fill, a restated cost is authoritative and simply replaces the
    previous one: charges are computed by the broker after the fact and are
    expected to arrive late, so a changed figure is a better answer rather than a
    contradiction to quarantine. Returns None when the order is not in the ledger.
    """
    account_id = _text(account_id, "account_id")
    uid = _text(uid, "uid")
    symbol = _text(symbol, "symbol")
    order_id = _text(order_id, "order_id")
    source = _text(source, "fees_source")
    fees = _amount(fees, "fees", minimum=0.0)
    with _transaction() as conn:
        rows = list(conn.execute(
            """SELECT id, exchange, cumulative_quantity FROM kite_execution_increments
                WHERE account_id=? AND uid=? AND symbol=? AND order_id=?
                ORDER BY cumulative_quantity""",
            (account_id, uid, symbol, order_id)))
        if not rows:
            return None
        last = rows[-1]["id"]
        for row in rows:
            conn.execute("UPDATE kite_execution_increments SET fees=?, fees_source=? WHERE id=?",
                         (fees if int(row["id"]) == int(last) else 0.0, source, int(row["id"])))
        return _project(conn, account_id, uid, symbol, rows[-1]["exchange"])


# ── the read path ────────────────────────────────────────────────────────────

def inventory(account_id: str, uid: str, symbol: str) -> Optional[Inventory]:
    _ready()
    with db._conn() as conn:
        return _read_inventory(conn, account_id, uid, symbol)


def holdings(uid: str, account_id: str = "") -> List[Inventory]:
    """Every non-flat holding, plus any flagged one. A flagged flat holding still
    matters: it means the quantity we believe we hold is in doubt."""
    _ready()
    sql = ("SELECT * FROM kite_inventory WHERE uid=? "
           "AND (net_quantity != 0 OR reconciliation_required=1)")
    args: List[Any] = [uid]
    if account_id:
        sql += " AND account_id=?"
        args.append(account_id)
    with db._conn() as conn:
        return [_row_to_inventory(r) for r in conn.execute(sql, args)]


def realized_pnl(uid: str, *, day_iso: Optional[str] = None,
                 account_id: str = "") -> float:
    """Durable realized PnL for one IST day, net of recorded fees.

    This is the figure the INR daily-loss breaker must read. It is a SUM over
    immutable rows rather than a stored total, so a restart, a duplicate
    postback or a reordered fill cannot inflate or lose it.
    """
    _ready()
    day = day_iso or ist_today()
    sql = ("SELECT COALESCE(SUM(realized_delta),0) AS total "
           "FROM kite_execution_increments WHERE uid=? AND day_iso=?")
    args: List[Any] = [uid, day]
    if account_id:
        sql += " AND account_id=?"
        args.append(account_id)
    with db._conn() as conn:
        return float(conn.execute(sql, args).fetchone()["total"])


def conflicts(uid: str, *, account_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    _ready()
    sql = "SELECT * FROM kite_execution_conflicts WHERE uid=?"
    args: List[Any] = [uid]
    if account_id:
        sql += " AND account_id=?"
        args.append(account_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))
    with db._conn() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def increments(uid: str, *, account_id: str = "", symbol: str = "") -> List[Dict[str, Any]]:
    _ready()
    sql = "SELECT * FROM kite_execution_increments WHERE uid=?"
    args: List[Any] = [uid]
    if account_id:
        sql += " AND account_id=?"
        args.append(account_id)
    if symbol:
        sql += " AND symbol=?"
        args.append(symbol)
    sql += (" ORDER BY COALESCE(NULLIF(exchange_ts_ms,0), received_ts_ms),"
            " received_ts_ms, id")
    with db._conn() as conn:
        return [dict(r) for r in conn.execute(sql, args)]


def resolve(account_id: str, uid: str, symbol: str, *, note: str = "") -> Inventory:
    """Operator acknowledgement that quarantined evidence has been reconciled.

    Clearing the flag does not change a number: the inventory is reprojected from
    the increments, so whatever the operator actually corrected in the ledger is
    what shows up here.
    """
    account_id = _text(account_id, "account_id")
    uid = _text(uid, "uid")
    symbol = _text(symbol, "symbol")
    with _transaction() as conn:
        existing = _read_inventory(conn, account_id, uid, symbol)
        if existing is None:
            raise ValueError("unknown_inventory")
        conn.execute("""UPDATE kite_inventory SET reconciliation_required=0,
                        reconciliation_reason=? WHERE account_id=? AND uid=? AND symbol=?""",
                     (note, account_id, uid, symbol))
        return _project(conn, account_id, uid, symbol, existing.exchange)


def clear_for_tests(uid: str) -> None:
    with _transaction() as conn:
        conn.execute("DELETE FROM kite_execution_increments WHERE uid=?", (uid,))
        conn.execute("DELETE FROM kite_inventory WHERE uid=?", (uid,))
        conn.execute("DELETE FROM kite_execution_conflicts WHERE uid=?", (uid,))
