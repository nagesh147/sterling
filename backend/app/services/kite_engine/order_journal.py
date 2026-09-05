"""Durable, fail-closed Kite order intents and immutable broker fill events."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite, isclose
import time
from typing import Any, Dict, List, Optional

from app.services import db

TERMINAL = {"FILLED", "REJECTED", "CANCELLED"}
UNRESOLVED = {"RESERVED", "SUBMITTING", "UNKNOWN", "SUBMITTED", "PARTIAL"}


@dataclass(frozen=True)
class Intent:
    intent_key: str
    uid: str
    account_id: str
    strategy_id: str
    generation_id: str
    signal_id: str
    exchange: str
    symbol: str
    side: str
    quantity: int
    tag: str
    state: str
    order_id: str
    payload: Dict[str, Any]
    error: str
    created_ms: int
    updated_ms: int
    capital_required: float = 0
    filled_quantity: int = 0
    filled_value: float = 0
    reconciliation_required: bool = False
    projection_pending: bool = False
    projection_version: int = 0


@dataclass(frozen=True)
class Observation:
    intent: Intent
    accepted: bool
    delta_quantity: int = 0
    delta_value: float = 0
    reason: str = ""

    @property
    def reconciliation_required(self) -> bool:
        return self.intent.reconciliation_required

    @property
    def state(self) -> str:
        return self.intent.state


@contextmanager
def _transaction():
    _ready()
    with db._conn() as conn:
        conn.execute("PRAGMA synchronous=FULL")
        if conn.execute("PRAGMA synchronous").fetchone()[0] != 2:
            raise RuntimeError("durable_order_journal_full_sync_unavailable")
        conn.execute("BEGIN IMMEDIATE")
        yield conn


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"invalid_{label}")
    return value


def _quantity(value: int, *, zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (0 if zero else 1):
        raise ValueError("invalid_quantity")
    return value


def _amount(value: float, label: str, *, zero: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"invalid_{label}")
    value = float(value)
    if not isfinite(value) or value < 0 or (value == 0 and not zero):
        raise ValueError(f"invalid_{label}")
    return value


def _ready() -> None:
    if not db.is_available():
        raise RuntimeError("durable_order_journal_unavailable")


def _row(row) -> Intent:
    return Intent(
        intent_key=row["intent_key"], uid=row["uid"], account_id=row["account_id"],
        strategy_id=row["strategy_id"], generation_id=row["generation_id"],
        signal_id=row["signal_id"], exchange=row["exchange"], symbol=row["symbol"],
        side=row["side"], quantity=int(row["quantity"]), tag=row["tag"], state=row["state"],
        order_id=row["order_id"], payload=json.loads(row["payload_json"] or "{}"),
        error=row["error"], created_ms=int(row["created_ms"]), updated_ms=int(row["updated_ms"]),
        capital_required=float(row["capital_required"]), filled_quantity=int(row["observed_quantity"]),
        filled_value=float(row["observed_value"]), reconciliation_required=bool(row["reconciliation_required"]),
        projection_pending=bool(row["projection_pending"]), projection_version=int(row["projection_version"]))


def _get(conn, key: str) -> Intent:
    row = conn.execute("SELECT * FROM kite_order_intents WHERE intent_key=?", (key,)).fetchone()
    if row is None:
        raise KeyError(key)
    return _row(row)


def make_key(*, uid: str, account_id: str, strategy_id: str, generation_id: str,
             signal_id: str, exchange: str, symbol: str, side: str) -> str:
    # Configuration generation is metadata, not permission to execute a signal twice.
    values = (uid, account_id, strategy_id, signal_id, exchange, symbol, side)
    for label, value in zip(("uid", "account_id", "strategy_id", "signal_id", "exchange", "symbol", "side"), values):
        _text(value, label)
    if side not in {"BUY", "SELL"}:
        raise ValueError("invalid_side")
    return sha256(_json(["kite-intent-v2", *values]).encode()).hexdigest()


def reserve(*, uid: str, account_id: str, strategy_id: str, generation_id: str,
            signal_id: str, exchange: str, symbol: str, side: str, quantity: int,
            payload: Optional[Dict[str, Any]] = None, capital_required: float = 0,
            available_capital: Optional[float] = None) -> Intent:
    """Reserve immutable intent and pending account capital atomically.

    available_capital must be fresh broker evidence. Unresolved reservations are
    deducted conservatively while holding SQLite's account-wide write lock.
    """
    _quantity(quantity)
    _text(generation_id, "generation_id")
    capital_required = _amount(capital_required, "capital_required", zero=True)
    if capital_required and available_capital is None:
        raise ValueError("available_capital_required")
    if available_capital is not None:
        available_capital = _amount(available_capital, "available_capital", zero=True)
    if payload is not None and not isinstance(payload, dict):
        raise ValueError("invalid_payload")
    encoded = _json(payload or {})
    key = make_key(uid=uid, account_id=account_id, strategy_id=strategy_id,
                   generation_id=generation_id, signal_id=signal_id, exchange=exchange,
                   symbol=symbol, side=side)
    now = int(time.time() * 1000)
    with _transaction() as conn:
        # Match legacy draft identities too; changing key encoding must not resend.
        rows = conn.execute("""SELECT * FROM kite_order_intents WHERE uid=? AND account_id=?
            AND strategy_id=? AND signal_id=? AND exchange=? AND symbol=? AND side=?""",
            (uid, account_id, strategy_id, signal_id, exchange, symbol, side)).fetchall()
        if rows:
            if len(rows) != 1:
                raise ValueError("ambiguous_existing_intents")
            existing = _row(rows[0])
            if (existing.quantity != quantity or _json(existing.payload) != encoded
                    or existing.capital_required != capital_required):
                raise ValueError("immutable_intent_conflict")
            return existing
        if capital_required:
            marks = ",".join("?" for _ in UNRESOLVED)
            held = conn.execute(f"""SELECT COALESCE(SUM(capital_required),0)
                FROM kite_order_intents WHERE account_id=?
                AND (state IN ({marks}) OR reconciliation_required=1)""",
                (account_id, *sorted(UNRESOLVED))).fetchone()[0]
            if capital_required + held > available_capital:
                raise ValueError("insufficient_unreserved_capital")
        conn.execute("""INSERT INTO kite_order_intents
            (intent_key,uid,account_id,strategy_id,generation_id,signal_id,exchange,symbol,
             side,quantity,tag,state,payload_json,capital_required,created_ms,updated_ms)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (key, uid, account_id, strategy_id, generation_id, signal_id, exchange,
             symbol, side, quantity, "ke" + key[:18], "RESERVED", encoded,
             capital_required, now, now))
        return _get(conn, key)


def claim_submission(intent_key: str) -> bool:
    """Only the winning durable RESERVED→SUBMITTING CAS may call the broker."""
    with _transaction() as conn:
        _get(conn, intent_key)
        changed = conn.execute("""UPDATE kite_order_intents SET state='SUBMITTING',updated_ms=?
            WHERE intent_key=? AND state='RESERVED' AND reconciliation_required=0""",
            (int(time.time() * 1000), intent_key)).rowcount
        return changed == 1


def _check_order_id(conn, intent: Intent, order_id: str) -> str:
    if order_id:
        _text(order_id, "order_id")
    if intent.order_id and order_id and intent.order_id != order_id:
        raise ValueError("conflicting_broker_order_id")
    oid = order_id or intent.order_id
    if oid and conn.execute("""SELECT intent_key FROM kite_order_intents
            WHERE account_id=? AND order_id=? AND intent_key<>?""",
            (intent.account_id, oid, intent.intent_key)).fetchone():
        raise ValueError("broker_order_id_already_attributed")
    return oid


def transition(intent_key: str, state: str, *, order_id: str="", error: str="") -> Intent:
    state=state.upper()
    if state == "SUBMITTING":
        raise ValueError("use_claim_submission")
    if state in {"PARTIAL", "FILLED"}:
        raise ValueError("use_observe_order_for_fills")
    if state not in TERMINAL | UNRESOLVED:
        raise ValueError("invalid_intent_state")
    allowed={
      "RESERVED":{"CANCELLED"}, "SUBMITTING":{"SUBMITTED","UNKNOWN","REJECTED"},
      "UNKNOWN":{"SUBMITTED","REJECTED","CANCELLED"},
      "SUBMITTED":{"REJECTED","CANCELLED","UNKNOWN"},
      "PARTIAL":{"CANCELLED","UNKNOWN"}}
    with _transaction() as conn:
        intent = _get(conn, intent_key)
        current=intent.state
        if state != current and state not in allowed.get(current,set()):
            raise ValueError(f"invalid_intent_transition:{current}->{state}")
        oid = _check_order_id(conn, intent, order_id)
        if state == "SUBMITTED" and not oid:
            raise ValueError("submitted_order_id_required")
        conn.execute("UPDATE kite_order_intents SET state=?,order_id=?,error=?,updated_ms=? WHERE intent_key=?",
                     (state,oid,error,int(time.time()*1000),intent_key))
        return _get(conn, intent_key)


def unresolved(uid: str, account_id: Optional[str] = None) -> List[Intent]:
    _ready()
    marks = ",".join("?" for _ in UNRESOLVED)
    query = f"SELECT * FROM kite_order_intents WHERE uid=? AND (state IN ({marks}) OR reconciliation_required=1)"
    args = [uid, *sorted(UNRESOLVED)]
    if account_id is not None:
        query += " AND account_id=?"
        args.append(_text(account_id, "account_id"))
    with db._conn() as conn:
        rows = conn.execute(query + " ORDER BY created_ms", args).fetchall()
    return [_row(r) for r in rows]


def find(*, uid: str, account_id: str, order_id: str = "", tag: str = "",
         exchange: str = "", symbol: str = "", side: str = "") -> Optional[Intent]:
    """Resolve within account+user; tag fallback recovers a lost acknowledgement.

    Supplied identity fields must all agree. Ambiguity is an explicit error.
    """
    _ready()
    _text(uid, "uid")
    _text(account_id, "account_id")
    if not order_id and not tag:
        return None
    with db._conn() as conn:
        rows = conn.execute("""SELECT * FROM kite_order_intents WHERE uid=? AND account_id=?
            AND ((?<>'' AND order_id=?) OR (?<>'' AND tag=?))""",
            (uid, account_id, order_id, order_id, tag, tag)).fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("ambiguous_order_identity")
    intent = _row(rows[0])
    for supplied, actual in ((order_id, intent.order_id), (tag, intent.tag),
                             (exchange, intent.exchange), (symbol, intent.symbol), (side, intent.side)):
        if supplied and actual and supplied != actual:
            raise ValueError("order_identity_conflict")
    return intent


def pending_projection(uid: str, account_id: Optional[str] = None) -> List[Intent]:
    """Include terminal orders whose latest evidence has not reached the registry."""
    _ready()
    query = "SELECT * FROM kite_order_intents WHERE uid=? AND projection_pending=1"
    args = [uid]
    if account_id is not None:
        query += " AND account_id=?"
        args.append(_text(account_id, "account_id"))
    with db._conn() as conn:
        return [_row(r) for r in conn.execute(query + " ORDER BY created_ms", args).fetchall()]


def mark_projected(intent_key: str, projection_version: int) -> bool:
    """Acknowledge exactly the saved registry snapshot, never a newer fill."""
    _quantity(projection_version, zero=True)
    with _transaction() as conn:
        _get(conn, intent_key)
        changed = conn.execute("""UPDATE kite_order_intents SET projection_pending=0
            WHERE intent_key=? AND projection_version=? AND projection_pending=1""",
            (intent_key, projection_version)).rowcount
        return changed == 1


def observe_order(intent_key: str, *, status: str, order_id: str,
                  filled_quantity: int, average_price: float,
                  raw: Optional[Dict[str, Any]] = None) -> Observation:
    """Apply cumulative evidence once; never manufacture per-trade fills.

    Lower cumulative quantity is older evidence. Price corrections, impossible
    quantities/values or conflicting terminal evidence quarantine the intent.
    """
    _text(order_id, "order_id")
    filled_quantity = _quantity(filled_quantity, zero=True)
    average_price = _amount(average_price, "average_price", zero=(filled_quantity == 0))
    status = status.upper()
    allowed_statuses = {"OPEN", "COMPLETE", "CANCELLED", "REJECTED", "UPDATE", "TRIGGER PENDING",
        "PUT ORDER REQ RECEIVED", "VALIDATION PENDING", "OPEN PENDING", "MODIFY VALIDATION PENDING",
        "MODIFY PENDING", "CANCEL PENDING", "AMO REQ RECEIVED"}
    if status not in allowed_statuses:
        raise ValueError("unknown_broker_order_status")
    value = filled_quantity * average_price
    if not isfinite(value):
        raise ValueError("invalid_filled_value")
    fingerprint = sha256(_json([order_id, status, filled_quantity, average_price]).encode()).hexdigest()
    encoded_raw = _json(raw or {})
    with _transaction() as conn:
        current = _get(conn, intent_key)
        _check_order_id(conn, current, order_id)
        if conn.execute("SELECT 1 FROM kite_order_observations WHERE intent_key=? AND fingerprint=?",
                        (intent_key, fingerprint)).fetchone():
            return Observation(current, False, reason="duplicate")
        reason = "accepted"
        target = current.state
        delta_qty = filled_quantity - current.filled_quantity
        delta_value = value - current.filled_value
        if current.reconciliation_required:
            reason = "reconciliation_pending"
        elif current.state == "RESERVED":
            reason = "unclaimed_order_evidence"
        elif filled_quantity > current.quantity:
            reason = "overfilled_order"
        elif status == "COMPLETE" and filled_quantity != current.quantity:
            reason = "incomplete_complete_status"
        elif delta_qty < 0:
            reason = "older_cumulative_observation"
        elif delta_qty == 0 and not isclose(value, current.filled_value, rel_tol=1e-10, abs_tol=1e-8):
            reason = "cumulative_price_correction"
        elif delta_qty > 0 and delta_value <= 0:
            reason = "nonpositive_incremental_fill_value"
        elif current.state in TERMINAL:
            expected = {"COMPLETE": "FILLED", "CANCELLED": "CANCELLED", "REJECTED": "REJECTED"}.get(status)
            if delta_qty > 0 or (expected and expected != current.state):
                reason = "terminal_order_conflict"
            else:
                reason = "terminal_duplicate_or_older_status"
        else:
            target = ("FILLED" if status == "COMPLETE" else status if status in {"CANCELLED", "REJECTED"}
                      else "PARTIAL" if filled_quantity else "SUBMITTED")
        benign = {"accepted", "older_cumulative_observation", "terminal_duplicate_or_older_status"}
        conflict = reason not in benign
        now = int(time.time() * 1000)
        conn.execute("""INSERT INTO kite_order_observations
            (intent_key,fingerprint,order_id,broker_status,filled_quantity,filled_value,
             disposition,received_ts_ms,raw_json) VALUES (?,?,?,?,?,?,?,?,?)""",
            (intent_key, fingerprint, order_id, status, filled_quantity, value, reason, now, encoded_raw))
        if reason == "accepted":
            conn.execute("""UPDATE kite_order_intents SET state=?,order_id=?,observed_quantity=?,
                observed_value=?,updated_ms=?,projection_pending=1,
                projection_version=projection_version+1 WHERE intent_key=?""",
                (target, order_id, filled_quantity, value, now, intent_key))
        elif conflict:
            conn.execute("""UPDATE kite_order_intents SET reconciliation_required=1,error=?,
                order_id=?,updated_ms=?,projection_pending=1,
                projection_version=projection_version+1 WHERE intent_key=?""", (reason, order_id, now, intent_key))
        return Observation(_get(conn, intent_key), reason == "accepted",
            delta_qty if reason == "accepted" else 0, delta_value if reason == "accepted" else 0, reason)


def clear_for_tests(uid: str) -> None:
    with _transaction() as conn:
        conn.execute("DELETE FROM kite_order_observations WHERE intent_key IN (SELECT intent_key FROM kite_order_intents WHERE uid=?)", (uid,))
        conn.execute("DELETE FROM kite_fill_ledger WHERE uid=?",(uid,))
        conn.execute("DELETE FROM kite_order_intents WHERE uid=?",(uid,))


def record_fill(*, account_id: str, order_id: str, trade_id: str, uid: str,
                symbol: str, side: str, quantity: int, price: float, fees: float=0,
                exchange_ts_ms: int=0, raw: Optional[Dict[str, Any]]=None) -> bool:
    """Insert one immutable fill. False means exact broker execution already consumed."""
    _ready(); now=int(time.time()*1000)
    with db._conn() as conn:
        before=conn.total_changes
        conn.execute("""INSERT OR IGNORE INTO kite_fill_ledger
          (account_id,order_id,trade_id,uid,symbol,side,quantity,price,fees,
           exchange_ts_ms,received_ts_ms,raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
          (account_id,order_id,trade_id,uid,symbol,side,int(quantity),float(price),float(fees),
           int(exchange_ts_ms),now,json.dumps(raw or {},sort_keys=True)))
        return conn.total_changes > before
