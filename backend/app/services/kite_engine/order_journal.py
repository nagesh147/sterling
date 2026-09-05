"""Durable, fail-closed Kite order intents and immutable broker fill events."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
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
        error=row["error"], created_ms=int(row["created_ms"]), updated_ms=int(row["updated_ms"]))


def make_key(*, uid: str, account_id: str, strategy_id: str, generation_id: str,
             signal_id: str, exchange: str, symbol: str, side: str) -> str:
    raw="|".join((uid,account_id,strategy_id,generation_id,signal_id,exchange,symbol,side))
    return sha256(raw.encode()).hexdigest()


def reserve(*, uid: str, account_id: str, strategy_id: str, generation_id: str,
            signal_id: str, exchange: str, symbol: str, side: str, quantity: int,
            payload: Optional[Dict[str, Any]]=None) -> Intent:
    """Atomically create one intent. Existing key is returned and never overwritten."""
    _ready()
    key=make_key(uid=uid,account_id=account_id,strategy_id=strategy_id,
                 generation_id=generation_id,signal_id=signal_id,exchange=exchange,
                 symbol=symbol,side=side)
    tag="ke"+key[:18]
    now=int(time.time()*1000)
    with db._conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("""INSERT OR IGNORE INTO kite_order_intents
          (intent_key,uid,account_id,strategy_id,generation_id,signal_id,exchange,symbol,
           side,quantity,tag,state,payload_json,created_ms,updated_ms)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (key,uid,account_id,strategy_id,generation_id,signal_id,exchange,symbol,
           side,int(quantity),tag,"RESERVED",json.dumps(payload or {},sort_keys=True),now,now))
        row=conn.execute("SELECT * FROM kite_order_intents WHERE intent_key=?",(key,)).fetchone()
    return _row(row)


def transition(intent_key: str, state: str, *, order_id: str="", error: str="") -> Intent:
    _ready(); state=state.upper()
    allowed={
      "RESERVED":{"SUBMITTING","CANCELLED"}, "SUBMITTING":{"SUBMITTED","UNKNOWN","REJECTED"},
      "UNKNOWN":{"SUBMITTED","PARTIAL","FILLED","REJECTED","CANCELLED"},
      "SUBMITTED":{"PARTIAL","FILLED","REJECTED","CANCELLED","UNKNOWN"},
      "PARTIAL":{"PARTIAL","FILLED","CANCELLED","UNKNOWN"}}
    with db._conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row=conn.execute("SELECT * FROM kite_order_intents WHERE intent_key=?",(intent_key,)).fetchone()
        if row is None: raise KeyError(intent_key)
        current=row["state"]
        if state != current and state not in allowed.get(current,set()):
            raise ValueError(f"invalid_intent_transition:{current}->{state}")
        oid=order_id or row["order_id"]
        conn.execute("UPDATE kite_order_intents SET state=?,order_id=?,error=?,updated_ms=? WHERE intent_key=?",
                     (state,oid,error,int(time.time()*1000),intent_key))
        row=conn.execute("SELECT * FROM kite_order_intents WHERE intent_key=?",(intent_key,)).fetchone()
    return _row(row)


def unresolved(uid: str) -> List[Intent]:
    _ready()
    marks=','.join('?' for _ in UNRESOLVED)
    with db._conn() as conn:
        rows=conn.execute(f"SELECT * FROM kite_order_intents WHERE uid=? AND state IN ({marks}) ORDER BY created_ms",
                          (uid,*sorted(UNRESOLVED))).fetchall()
    return [_row(r) for r in rows]


def find(*, uid: str, order_id: str="", tag: str="") -> Optional[Intent]:
    _ready()
    if not order_id and not tag:
        return None
    field,value=("order_id",order_id) if order_id else ("tag",tag)
    with db._conn() as conn:
        row=conn.execute(f"SELECT * FROM kite_order_intents WHERE uid=? AND {field}=?",
                         (uid,value)).fetchone()
    return _row(row) if row else None


def clear_for_tests(uid: str) -> None:
    _ready()
    with db._conn() as conn:
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
