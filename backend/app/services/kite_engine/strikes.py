"""Kite-only ATM/ITM/OTM option strike and expiry-series resolver.

Expiry classification is derived from the dates actually listed in the instrument
chain. This deliberately avoids weekday assumptions because exchange expiry days
and holiday adjustments can change.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Literal, Optional, Sequence

Moneyness = Literal[
    "ATM", "ITM1", "ITM2", "ITM3", "ITM4", "ITM5",
    "ITM10", "ITM15", "ITM20",
    "OTM1", "OTM2", "OTM3", "OTM4", "OTM5",
]
ExpiryType = Literal["weekly", "monthly"]

_ITM_OFFSET = {
    "ATM": 0,
    "ITM1": 1, "ITM2": 2, "ITM3": 3, "ITM4": 4, "ITM5": 5,
    "ITM10": 10, "ITM15": 15, "ITM20": 20,
    "OTM1": -1, "OTM2": -2, "OTM3": -3, "OTM4": -4, "OTM5": -5,
}


def _parse_expiry(raw: object) -> Optional[date]:
    try:
        return date.fromisoformat(str(raw or "")[:10])
    except (TypeError, ValueError):
        return None


def _expiry_date_set(chain: Sequence[dict], today: date) -> dict[str, set[str]]:
    """Return labels for each listed future expiry.

    For every calendar month represented by the chain, the latest listed expiry is
    the monthly contract. Any earlier listed expiries in that month are weekly
    contracts. A chain containing only one expiry per month is therefore monthly-
    only, which correctly models stock options and monthly-only indices.
    """
    future = sorted({
        d for r in chain
        if (d := _parse_expiry(r.get("expiry_date") or r.get("expiry"))) is not None
        and d >= today
    })
    by_month: dict[tuple[int, int], list[date]] = {}
    for d in future:
        by_month.setdefault((d.year, d.month), []).append(d)

    out: dict[str, set[str]] = {}
    for dates in by_month.values():
        monthly = max(dates)
        for d in dates:
            out[d.isoformat()] = {"monthly"} if d == monthly else {"weekly"}
    return out


def _series_dates(
    chain: Sequence[dict], expiry_type: ExpiryType, today: date
) -> list[date]:
    labels = _expiry_date_set(chain, today)
    return sorted(
        d for key, kinds in labels.items()
        if expiry_type in kinds and (d := _parse_expiry(key)) is not None
    )


def _filter_chain_by_expiry(
    chain: Sequence[dict], expiry_types: Sequence[ExpiryType], today: date
) -> list[dict]:
    if not expiry_types:
        return list(chain)
    labels = _expiry_date_set(chain, today)
    wanted = set(expiry_types)
    return [
        r for r in chain
        if wanted & labels.get(str(r.get("expiry_date") or r.get("expiry") or "")[:10], set())
    ]


def _filter_chain_by_series(
    chain: Sequence[dict], *, expiry_type: ExpiryType, expiry_rank: int, today: date
) -> list[dict]:
    dates = _series_dates(chain, expiry_type, today)
    if expiry_rank < 0 or expiry_rank >= len(dates):
        return []
    selected = dates[expiry_rank].isoformat()
    return [
        r for r in chain
        if str(r.get("expiry_date") or r.get("expiry") or "")[:10] == selected
    ]


def chain_rows_for(option_instruments: Sequence[dict], name: str, today: date) -> List[dict]:
    """Extract strike-picker rows for an underlying from an NFO/BFO dump."""
    want = name.upper()
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
            strike = float(r.get("strike") or 0.0)
        except (ValueError, TypeError):
            continue
        if strike <= 0 or ed < today:
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
    option_type: str
    expiry: str
    dte: int
    lot_size: int = 0
    token: int = 0


def pick_strike(
    chain: Sequence[dict], *, spot: float, direction: str,
    moneyness: Moneyness = "ATM", min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (), expiry_type: Optional[ExpiryType] = None,
    expiry_rank: int = 0, today: Optional[date] = None,
) -> Optional[OptionPick]:
    """Resolve one CE/PE contract for a requested expiry series and moneyness.

    When the requested depth exceeds the listed strike ladder, the deepest listed
    strike on the same ITM/OTM side is selected instead of returning no contract.
    """
    want_call = direction == "long"
    want_type = "call" if want_call else "put"
    rows = [
        r for r in chain
        if str(r.get("option_type", "")).lower() == want_type
        and int(r.get("dte", 0)) >= min_dte
    ]
    current = today or date.today()
    if expiry_type is not None:
        rows = _filter_chain_by_series(rows, expiry_type=expiry_type, expiry_rank=expiry_rank, today=current)
    elif expiry_types:
        rows = _filter_chain_by_expiry(rows, expiry_types, current)
        if rows:
            nearest = min(int(r.get("dte", 0)) for r in rows)
            rows = [r for r in rows if int(r.get("dte", 0)) == nearest]
    else:
        if rows:
            nearest = min(int(r.get("dte", 0)) for r in rows)
            rows = [r for r in rows if int(r.get("dte", 0)) == nearest]
    if not rows:
        return None

    rows = sorted(rows, key=lambda r: float(r["strike"]))
    strikes = [float(r["strike"]) for r in rows]
    atm = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    off = _ITM_OFFSET[moneyness]
    requested_idx = atm - off if want_call else atm + off
    idx = min(max(requested_idx, 0), len(strikes) - 1)

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
    expiry_ranks_by_type: Optional[dict[ExpiryType, Sequence[int]]] = None,
    today: Optional[date] = None,
) -> List[tuple]:
    """Resolve requested strikes across independently selected weekly/monthly ranks."""
    out: List[tuple] = []
    seen: set[str] = set()
    series = expiry_ranks_by_type or {kind: [0] for kind in expiry_types}
    if not series:
        series = {None: [0]}  # type: ignore[dict-item]
    for kind, ranks in series.items():
        for rank in ranks:
            for m in moneynesses:
                pick = pick_strike(
                    chain, spot=spot, direction=direction, moneyness=m,
                    min_dte=min_dte, expiry_types=expiry_types,
                    expiry_type=kind, expiry_rank=int(rank), today=today,
                )
                if pick and pick.option_symbol not in seen:
                    seen.add(pick.option_symbol)
                    out.append((m, pick))
    return out


def pick_contracts(
    chain: Sequence[dict], *, spot: float,
    moneynesses: Sequence[Moneyness], min_dte: int = 0,
    expiry_types: Sequence[ExpiryType] = (),
    expiry_ranks_by_type: Optional[dict[ExpiryType, Sequence[int]]] = None,
    today: Optional[date] = None,
) -> List[tuple]:
    """Resolve both CE and PE across selected strike and expiry series."""
    out: List[tuple] = []
    seen: set[str] = set()
    series = expiry_ranks_by_type or {kind: [0] for kind in expiry_types}
    if not series:
        series = {None: [0]}  # type: ignore[dict-item]
    for kind, ranks in series.items():
        for rank in ranks:
            for m in moneynesses:
                for direction in ("long", "short"):
                    pick = pick_strike(
                        chain, spot=spot, direction=direction, moneyness=m,
                        min_dte=min_dte, expiry_types=expiry_types,
                        expiry_type=kind, expiry_rank=int(rank), today=today,
                    )
                    if pick and pick.option_symbol not in seen:
                        seen.add(pick.option_symbol)
                        out.append((m, pick))
    return out


def pick_by_delta(
    chain: Sequence[dict], *, spot: float, direction: str,
    target_delta: float = 0.90, iv: float = 0.18,
    min_dte: int = 0, expiry_types: Sequence[ExpiryType] = (),
    expiry_type: Optional[ExpiryType] = None, expiry_rank: int = 0,
    today: Optional[date] = None,
) -> Optional[OptionPick]:
    from app.services.kite_engine.greeks import black_scholes_greeks

    want_call = direction == "long"
    want_type = "call" if want_call else "put"
    rows = [r for r in chain if str(r.get("option_type", "")).lower() == want_type and int(r.get("dte", 0)) >= min_dte]
    current = today or date.today()
    if expiry_type is not None:
        rows = _filter_chain_by_series(rows, expiry_type=expiry_type, expiry_rank=expiry_rank, today=current)
    elif expiry_types:
        rows = _filter_chain_by_expiry(rows, expiry_types, current)
    if not rows:
        return None
    nearest = min(int(r.get("dte", 0)) for r in rows)
    rows = [r for r in rows if int(r.get("dte", 0)) == nearest]

    abs_target = abs(target_delta)
    best_row = None
    best_dist = float("inf")
    for r in rows:
        strike = float(r.get("strike", 0))
        dte_d = max(1.0, float(r.get("dte", 1)))
        g = black_scholes_greeks(spot=spot, strike=strike, dte_days=dte_d, iv=iv, option_type="CE" if want_call else "PE")
        dist = abs(abs(g.delta) - abs_target)
        if dist < best_dist:
            best_dist = dist
            best_row = r
    if best_row is None:
        return None
    return OptionPick(
        option_symbol=str(best_row.get("instrument_name", "")),
        strike=float(best_row["strike"]),
        option_type="CE" if want_call else "PE",
        expiry=str(best_row.get("expiry_date", "")),
        dte=int(best_row.get("dte", 0)),
        lot_size=int(best_row.get("lot_size", 0) or 0),
        token=int(best_row.get("token", 0) or 0),
    )
