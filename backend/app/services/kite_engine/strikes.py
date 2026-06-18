"""Kite-only ATM/ITM/OTM option strike picker.

Bull → CE, bear → PE. ATM is the strike nearest spot; ITM steps *into* the money,
OTM steps *out of* the money. Built fresh for Kite option chains; imports no other
engine's selector logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Literal, Optional, Sequence

Moneyness = Literal["ATM", "ITM1", "ITM2", "ITM3", "ITM4", "ITM5", "OTM1", "OTM2", "OTM3", "OTM4", "OTM5"]
ExpiryType = Literal["weekly", "monthly"]
# Signed "into-the-money" offset (in strike steps): positive = ITM, negative = OTM.
_ITM_OFFSET = {"ATM": 0, "ITM1": 1, "ITM2": 2, "ITM3": 3, "ITM4": 4, "ITM5": 5, "OTM1": -1, "OTM2": -2, "OTM3": -3, "OTM4": -4, "OTM5": -5}


def _expiry_date_set(chain: Sequence[dict], today: date) -> dict:
    """Classify each unique expiry date in the chain as weekly or monthly.

    NSE/BFO conventions: weekly contracts expire every Thursday. Monthly contracts
    expire on the last Thursday of the month (which coincides with a weekly).
    Returns {expiry_date_str: {"weekly", ...}} — the last-Thursday expiry gets
    BOTH labels so filtering by either weekly or monthly includes it."""
    from datetime import date as _date, timedelta

    exp_dates: set[_date] = set()
    for r in chain:
        raw = str(r.get("expiry_date", "") or r.get("expiry", ""))[:10]
        try:
            exp_dates.add(_date.fromisoformat(raw))
        except (ValueError, TypeError):
            continue
    if not exp_dates:
        return {}

    # Find the last Thursday of each month present in the chain
    last_thu: set[_date] = set()
    for d in exp_dates:
        last_day = (d.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        while last_day.isoweekday() != 4:
            last_day = last_day - timedelta(days=1)
        last_thu.add(last_day)

    # Every Thursday expiry is "weekly"; last-Thursday is also "monthly"
    out: dict[str, set[str]] = {}
    for d in exp_dates:
        ts = d.isoformat()
        labels: set[str] = set()
        if d.isoweekday() == 4:
            labels.add("weekly")
        if d in last_thu:
            labels.add("monthly")
        out[ts] = labels if labels else {"weekly"}  # fallback
    return out


def _filter_chain_by_expiry(chain: Sequence[dict], expiry_types: Sequence[ExpiryType],
                            today: date) -> list:
    """Return chain rows matching the selected expiry types (weekly/monthly)."""
    if not expiry_types or set(expiry_types) == {"weekly", "monthly"}:
        return list(chain)
    exp_map = _expiry_date_set(chain, today)
    want = set(expiry_types)
    return [r for r in chain
            if want & exp_map.get(str(r.get("expiry_date", "") or r.get("expiry", ""))[:10], set())]


def chain_rows_for(option_instruments: Sequence[dict], name: str, today: date) -> List[dict]:
    """Extract pick_strike-ready rows for ``name`` from a raw NFO/BFO dump.

    Uses only the instrument metadata (strike / expiry / type) — no quote calls —
    which is all the strike picker needs and works for both NFO and BFO (SENSEX).
    """
    want = name.upper()
    # BSE index options carry a SHORT CODE in the `name` field (SENSEX→BSX,
    # BANKEX→BKX) even though their tradingsymbol still starts with the index name.
    # Match on the name, the known alias, OR a tradingsymbol prefix (the index name
    # immediately followed by a digit, e.g. "SENSEX25..."). The prefix net means
    # resolution never silently breaks if Kite's `name` field isn't what we assume.
    alias = {"SENSEX": "BSX", "BANKEX": "BKX"}.get(want)
    out: List[dict] = []
    for r in option_instruments:
        n = str(r.get("name", "")).upper()
        tsym = str(r.get("tradingsymbol", "")).upper()
        prefix_hit = tsym.startswith(want) and len(tsym) > len(want) and tsym[len(want)].isdigit()
        if n != want and not (alias and n == alias) and not prefix_hit:
            continue
        it = r.get("instrument_type")
        if it not in ("CE", "PE"):
            continue
        exp = str(r.get("expiry", ""))[:10]
        try:
            ed = datetime.strptime(exp, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        try:
            strike = float(r.get("strike") or 0.0)
        except (ValueError, TypeError):
            continue
        if strike <= 0:
            continue
        out.append({
            "strike": strike,
            "option_type": "call" if it == "CE" else "put",
            "expiry_date": exp,
            "dte": (ed - today).days,
            "instrument_name": str(r.get("tradingsymbol", "")),
            "lot_size": int(r.get("lot_size") or 0),
            "token": int(r.get("instrument_token") or 0),
        })
    return out


@dataclass(frozen=True)
class OptionPick:
    option_symbol: str
    strike: float
    option_type: str  # "CE" | "PE"
    expiry: str
    dte: int
    lot_size: int = 0
    token: int = 0  # option instrument_token (for fetching the contract's own candles)


def pick_strike(
    chain: Sequence[dict],
    *,
    spot: float,
    direction: str,
    moneyness: Moneyness = "ATM",
    min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    today: Optional[date] = None,
) -> Optional[OptionPick]:
    """Pick the CE (bull) / PE (bear) at the requested moneyness from a Kite
    option chain (list of OptionSummary-like dicts), or ``None`` if unavailable.

    ATM = nearest strike to ``spot``. ITM steps *into* the money (CALL ITM = lower
    strike, PUT ITM = higher strike); OTM steps *out of* the money (CALL OTM =
    higher strike, PUT OTM = lower strike).
    """
    want_call = direction == "long"
    want_type = "call" if want_call else "put"
    rows = [
        r for r in chain
        if str(r.get("option_type", "")).lower() == want_type
        and int(r.get("dte", 0)) >= min_dte
    ]
    if expiry_types and set(expiry_types) != {"weekly", "monthly"}:
        _today = today or date.today()
        rows = _filter_chain_by_expiry(rows, expiry_types, _today)
    if not rows:
        return None

    # nearest expiry only
    near_dte = min(int(r["dte"]) for r in rows)
    rows = sorted((r for r in rows if int(r["dte"]) == near_dte), key=lambda r: float(r["strike"]))
    strikes = [float(r["strike"]) for r in rows]

    atm = min(range(len(strikes)), key=lambda k: abs(strikes[k] - spot))
    off = _ITM_OFFSET[moneyness]
    # CALL ITM = lower strike (atm - off); PUT ITM = higher strike (atm + off).
    # OTM flips the sign (off < 0), so CALL OTM = higher, PUT OTM = lower.
    idx = atm - off if want_call else atm + off
    if idx < 0 or idx >= len(strikes):
        return None

    r = rows[idx]
    return OptionPick(
        option_symbol=str(r.get("instrument_name", "")),
        strike=float(r["strike"]),
        option_type="CE" if want_call else "PE",
        expiry=str(r.get("expiry_date", "")),
        dte=int(r.get("dte", 0)),
        lot_size=int(r.get("lot_size", 0) or 0),
        token=int(r.get("token", 0) or 0),
    )


def pick_strikes(
    chain: Sequence[dict], *, spot: float, direction: str,
    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    today: Optional[date] = None,
) -> List[tuple]:
    """Pick one OptionPick per requested moneyness (skipping any unavailable).

    Returns a list of ``(moneyness, OptionPick)`` tuples, de-duplicated by the
    resolved option_symbol (so e.g. ATM and ITM1 collapsing to the same strike
    when the chain is sparse don't double-list)."""
    out: List[tuple] = []
    seen: set = set()
    for m in moneynesses:
        pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                          min_dte=min_dte, expiry_types=expiry_types, today=today)
        if pick and pick.option_symbol not in seen:
            seen.add(pick.option_symbol)
            out.append((m, pick))
    return out


def pick_contracts(
    chain: Sequence[dict], *, spot: float,
    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    today: Optional[date] = None,
) -> List[tuple]:
    """Resolve BOTH the CE and the PE contract at each requested moneyness — used by
    the derivatives scan, which charts both sides of every selected strike.

    ITM/OTM are relative to each option's own side (CALL ITM is below spot, PUT ITM
    is above), so "ITM1" yields two different strikes. Returns ``(moneyness, OptionPick)``
    tuples de-duplicated by resolved option_symbol."""
    out: List[tuple] = []
    seen: set = set()
    for m in moneynesses:
        for direction in ("long", "short"):  # long → CE, short → PE
            pick = pick_strike(chain, spot=spot, direction=direction, moneyness=m,
                              min_dte=min_dte, expiry_types=expiry_types, today=today)
            if pick and pick.option_symbol not in seen:
                seen.add(pick.option_symbol)
                out.append((m, pick))
    return out
