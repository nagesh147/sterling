"""Futures contract picker for the directional-mode Kite engine.

Finds the near-month or next-month index future from the already-loaded NFO/BFO
instrument dumps. No new network calls. Reuses the same UniverseItem / OptionPick
shape so the rest of the engine (sizing, stops, monitor) can handle both
options and futures uniformly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Literal, Optional, Sequence

from app.core.logging import get_logger

log = get_logger(__name__)

FuturesExpiry = Literal["near", "next"]


@dataclass(frozen=True)
class FuturesPick:
    tradingsymbol: str
    exchange: str           # NFO / BFO
    token: int
    expiry: str             # YYYY-MM-DD
    dte: int
    lot_size: int = 0


def pick_futures_contract(
    instruments: Sequence[dict], *, name: str, exchange: str = "NFO",
    expiry_preference: FuturesExpiry = "near",
    today: Optional[date] = None,
) -> Optional[FuturesPick]:
    """Pick the near-month or next-month futures contract for ``name``.

    ``name`` is the tradingsymbol prefix (e.g. "NIFTY", "BANKNIFTY").
    Filters the instrument dump for segment "NFO-FUT" / "BFO-FUT" and
    instrument_type "FUT", then picks by nearest or second-nearest expiry.
    """
    today = today or date.today()
    want = name.upper()
    alias = {"SENSEX": "BSX", "BANKEX": "BKX"}.get(want)
    segment = f"{exchange}-FUT"

    candidates: List[dict] = []
    for r in instruments:
        n = str(r.get("name", "")).upper()
        seg = str(r.get("segment", "")).upper()
        it = str(r.get("instrument_type", "")).upper()
        if it != "FUT" or seg != segment:
            continue
        if n != want and not (alias and n == alias):
            continue
        exp = str(r.get("expiry", ""))[:10]
        try:
            ed = datetime.strptime(exp, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        dte = (ed - today).days
        if dte < 0:
            continue  # expired
        candidates.append({**r, "_dte": dte, "_expiry": exp})

    if not candidates:
        return None

    # Sort by expiry (nearest first)
    candidates.sort(key=lambda x: x["_dte"])

    if expiry_preference == "near":
        pick = candidates[0]
    elif len(candidates) > 1:
        # next-month = second distinct expiry
        first_exp = candidates[0]["_expiry"]
        nexts = [c for c in candidates if c["_expiry"] != first_exp]
        pick = nexts[0] if nexts else candidates[0]
    else:
        pick = candidates[0]

    return FuturesPick(
        tradingsymbol=str(pick.get("tradingsymbol", "")),
        exchange=exchange,
        token=int(pick.get("instrument_token", 0) or 0),
        expiry=pick["_expiry"],
        dte=int(pick["_dte"]),
        lot_size=int(pick.get("lot_size", 0) or 0),
    )
