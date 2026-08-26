"""Fetch real Kite data for a recorded session and replay it through the engine.

Two data sources, tried in order:

1. **The offline lake** — for the index, and for the instrument master (which is
   how the traded contract's token is resolved even after the contract expired).
2. **Kite historical** — for the option minute bars. Kite serves expired F&O
   contracts if you have the token, which is exactly what the lake's snapshot
   supplies.

The recorded sessions and what each printed live in :data:`SESSIONS`, so the
replay has something to disagree with. Run it with::

    python -m app.services.atm_premium_imbalance_replay 2026-08-20
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

from app.core.logging import get_logger
from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, InstrumentRef, OptionPairRef,
)
from app.engines.atm_premium_imbalance.replay import (
    Bar, ObservedSession, ReplayResult, replay_session,
)

log = get_logger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

#: kitelake stores prices as int64 = round(rupees * PRICE_SCALE).
PRICE_SCALE = 10_000

#: What each recording printed. Absent fields were never printed and must stay
#: absent so the replay reports UNVERIFIED rather than inventing a comparison.
SESSIONS: dict[str, dict] = {
    "2026-08-20": {
        "label": "2026-08-20 (V1, canonical)",
        "expiry": "2026-08-20",
        "strike": 77500.0,
        "option_type": "CE",
        "first_tick_price": 102.85,
        "entry_order_price": 113.10,
        "entry_fill": 113.10,
        "exit_order_price": 126.60,
        "exit_fill": 126.60,
        "quantity": 100,
    },
    "2026-08-21": {
        "label": "2026-08-21 (V0821, put side)",
        "expiry": "2026-08-27",
        "strike": 77700.0,
        "option_type": "PE",
        "first_tick_price": 379.00,
        "entry_order_price": 416.90,
        "entry_fill": 340.10,
        "quantity": 80,
    },
    "2026-07-30": {
        "label": "2026-07-30 (V17, manual-price path)",
        "expiry": "2026-07-30",
        "strike": 77600.0,
        "option_type": "CE",
        "first_tick_price": 167.50,
        "entry_order_price": 288.75,   # from strike_prices.txt, not the percent rule
        "entry_fill": 133.40,
        "exit_order_price": 148.70,
        "exit_fill": 156.85,
        "quantity": 20,
        "index_at_open": 77638.86,
    },
}


# ------------------------------------------------------------------- the lake

def lake_root() -> Optional[Path]:
    cfg = Path.home() / ".config" / "kitelake" / "roots.json"
    if not cfg.exists():
        return None
    try:
        known = json.loads(cfg.read_text()).get("known") or []
    except (json.JSONDecodeError, OSError):
        return None
    for entry in known:
        p = entry.get("last_path")
        if p and Path(p).is_dir():
            return Path(p)
    return None


def _to_ist(ts) -> datetime:
    stamp = ts if isinstance(ts, datetime) else datetime.fromisoformat(str(ts))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(IST)


def lake_index_bars(root: Path, session: date) -> list[Bar]:
    """SENSEX index minute bars for one session, from the lake."""
    import pyarrow.parquet as pq
    p = root / "bars" / "interval=minute" / "exchange=BSE" / "segment=INDICES" / "265__SENSEX.parquet"
    if not p.exists():
        return []
    d = pq.read_table(p).to_pydict()
    out: list[Bar] = []
    for i, ts in enumerate(d["ts"]):
        stamp = _to_ist(ts)
        if stamp.date() != session:
            continue
        out.append(Bar(stamp, d["open"][i] / PRICE_SCALE, d["high"][i] / PRICE_SCALE,
                       d["low"][i] / PRICE_SCALE, d["close"][i] / PRICE_SCALE))
    return out


def lake_sensex_options(root: Path, expiry: str) -> list[dict]:
    """SENSEX option rows for one expiry, with Kite tokens, from the lake."""
    import pyarrow.parquet as pq
    p = root / "instruments" / "latest.parquet"
    if not p.exists():
        return []
    d = pq.read_table(p).to_pydict()
    rows = []
    for i in range(len(d["tradingsymbol"])):
        if d["name"][i] != "SENSEX" or d["instrument_type"][i] not in ("CE", "PE"):
            continue
        if str(d["expiry"][i])[:10] != expiry:
            continue
        rows.append({
            "token": int(d["instrument_token"][i]),
            "tradingsymbol": d["tradingsymbol"][i],
            "strike": float(d["strike"][i]),
            "option_type": d["instrument_type"][i],
            "lot_size": int(d["lot_size"][i]),
            "tick_size": float(d["tick_size"][i]),
        })
    return rows


def resolve_pair(rows: Sequence[dict], strike: float, expiry: str) -> Optional[OptionPairRef]:
    ce = next((r for r in rows if r["strike"] == strike and r["option_type"] == "CE"), None)
    pe = next((r for r in rows if r["strike"] == strike and r["option_type"] == "PE"), None)
    if ce is None or pe is None:
        return None

    def ref(r):
        return InstrumentRef(
            instrument_id=str(r["token"]), tradingsymbol=r["tradingsymbol"],
            option_type=r["option_type"], strike=r["strike"], expiry=expiry,
            lot_size=r["lot_size"], tick_size=r["tick_size"], exchange="BFO",
        )
    return OptionPairRef(underlying="SENSEX", expiry=expiry, strike=strike,
                         ce=ref(ce), pe=ref(pe), underlying_instrument_id="265")


# ------------------------------------------------------------------ kite bars

async def kite_minute_bars(uid: str, token: int, session: date) -> list[Bar]:
    """Minute bars for one instrument on one session, from Kite historical.

    Kite serves expired F&O contracts by token, which is why the lake's
    instrument snapshot matters: it preserves tokens for contracts that no longer
    appear in a live dump.
    """
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("no active Kite account — log in first")
    client = await accounts.acquire_client(acct)
    frm = f"{session.isoformat()} 09:00:00"
    to = f"{session.isoformat()} 15:40:00"
    data = await client.get_historical(int(token), "minute", frm, to)
    out: list[Bar] = []
    for row in (data or {}).get("candles", []) or []:
        try:
            out.append(Bar(_to_ist(row[0]), float(row[1]), float(row[2]),
                           float(row[3]), float(row[4]),
                           float(row[5]) if len(row) > 5 else 0.0))
        except (IndexError, TypeError, ValueError):
            continue
    return out


# --------------------------------------------------------------------- driver

async def run(session_key: str, uid: str = "default") -> ReplayResult:
    spec = SESSIONS.get(session_key)
    if spec is None:
        raise ValueError(f"unknown session {session_key}; known: {sorted(SESSIONS)}")
    session = date.fromisoformat(session_key)
    observed = ObservedSession(session=session, **{k: v for k, v in spec.items() if k != "expiry"},
                               expiry=spec["expiry"])

    root = lake_root()
    rows = lake_sensex_options(root, spec["expiry"]) if root else []
    pair = resolve_pair(rows, spec["strike"], spec["expiry"]) if rows else None
    index_bars = lake_index_bars(root, session) if root else []
    listed = sorted({r["strike"] for r in rows})

    if pair is None:
        res = ReplayResult(label=spec["label"])
        res.notes.append(
            f"contract not resolvable: the instrument master has no {spec['expiry']} "
            f"expiry (it had already expired when the snapshot was taken)"
        )
        return res

    ce_bars = await kite_minute_bars(uid, int(pair.ce.instrument_id), session)
    pe_bars = await kite_minute_bars(uid, int(pair.pe.instrument_id), session)

    cfg = ATMPremiumImbalanceConfig(
        enabled=True, quantity=spec.get("quantity") or 0,
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10,
        expiry_policy="NEAREST",
    ).validate()
    return replay_session(observed, cfg=cfg, ce_bars=ce_bars, pe_bars=pe_bars,
                          index_bars=index_bars, listed_strikes=listed, pair=pair)


def main(argv: Sequence[str]) -> int:
    keys = list(argv[1:]) or sorted(SESSIONS)
    rc = 0
    for key in keys:
        try:
            res = asyncio.run(run(key))
        except Exception as exc:
            print(f"\n### {key}\n\nCOULD NOT RUN: {exc}\n")
            rc = 2
            continue
        print(f"\n### {res.label}\n")
        if res.checks:
            print(res.table())
        print(f"\n{res.match} match · {res.mismatch} mismatch · {res.unverified} unverified")
        for n in res.notes:
            print(f"\n> {n}")
        if res.contradicted:
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
