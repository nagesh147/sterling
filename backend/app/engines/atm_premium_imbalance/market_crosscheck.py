"""Cross-check decoded video observations against independent market data.

The forensic evidence in A231 was self-verified: every reading had to satisfy an
identity the source bot itself computed. That catches transcription errors but
cannot catch a *shared* misreading. This module supplies the external check --
comparing what the recording printed against real exchange data the recording
had no part in producing.

Pure functions only. The caller supplies bars and instrument rows, so the same
comparison runs against the offline lake, a live broker, or a fixture.

What can and cannot be checked is deliberately explicit:

* The **index level** at the session open, and therefore the **ATM strike** the
  strategy should have chosen, can be checked from index minute bars.
* **Contract metadata** -- lot size, tick size, strike ladder, whether an expiry
  was listed -- can be checked from an instrument master.
* **Option premiums** cannot be checked without option bars, and *asynchronous
  tick behaviour* cannot be checked without ticks. A one-minute bar is a
  four-way summary of sixty seconds; it cannot evidence the order two legs
  updated in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional, Sequence

from .models import q2

IST = timezone(timedelta(hours=5, minutes=30))

#: Indian market open. The source bot idled until this and traded the first tick.
MARKET_OPEN_IST = time(9, 15)

VERDICT_MATCH = "MATCH"
VERDICT_MISMATCH = "MISMATCH"
VERDICT_UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class IndexBar:
    """One index minute bar, already in real price units."""

    ts_utc: datetime
    open: float
    high: float
    low: float
    close: float

    @property
    def ts_ist(self) -> datetime:
        return self.ts_utc.astimezone(IST)


@dataclass(frozen=True)
class CrossCheck:
    field: str
    observed: Optional[float | int | str]
    external: Optional[float | int | str]
    verdict: str
    source: str = ""
    note: str = ""


def _cmp(field, observed, external, source, *, tol=0.0, note="") -> CrossCheck:
    if external is None:
        return CrossCheck(field, observed, None, VERDICT_UNAVAILABLE, source, note)
    if observed is None:
        return CrossCheck(field, None, external, VERDICT_UNAVAILABLE, source,
                          note or "nothing decoded to compare against")
    if isinstance(observed, (int, float)) and isinstance(external, (int, float)):
        ok = abs(float(observed) - float(external)) <= tol
    else:
        ok = observed == external
    return CrossCheck(field, observed, external, VERDICT_MATCH if ok else VERDICT_MISMATCH, source, note)


def open_bar(bars: Sequence[IndexBar], session: date) -> Optional[IndexBar]:
    """The 09:15 IST bar for ``session``, i.e. the one the open tick falls in.

    Matched on IST wall time rather than by position, so a partial day or a feed
    that starts late cannot silently hand back the wrong minute.
    """
    for bar in bars:
        ist = bar.ts_ist
        if ist.date() == session and ist.hour == MARKET_OPEN_IST.hour and ist.minute == MARKET_OPEN_IST.minute:
            return bar
    return None


def nearest_listed_strike(spot: float, strikes: Iterable[float]) -> Optional[float]:
    """Same rule the strategy uses, applied to the externally observed spot.

    Deliberately re-implemented against `selection.select_atm_strike`'s contract
    rather than importing it: the point is to check the *rule* reproduces the
    printed strike, and a shared helper would make the check circular only if it
    disagreed -- which the test asserts it does not.
    """
    candidates = sorted({float(s) for s in strikes if float(s) > 0})
    if not candidates or spot <= 0:
        return None
    return min(candidates, key=lambda k: (abs(k - spot), k))


def check_session_open(
    *,
    session: date,
    observed_index_ltp: Optional[float],
    observed_strike: Optional[float],
    bars: Sequence[IndexBar],
    listed_strikes: Sequence[float],
) -> list[CrossCheck]:
    """Compare the recording's index level and chosen strike against real bars.

    The index value the bot printed at its first post-open tick should equal the
    *open* of the 09:15 bar: both are the first trade of the session.
    """
    bar = open_bar(bars, session)
    src = f"index minute bars {session.isoformat()} 09:15 IST"
    if bar is None:
        return [
            CrossCheck("index_ltp_at_open", observed_index_ltp, None, VERDICT_UNAVAILABLE, src,
                       "no 09:15 IST bar for this session in the supplied data"),
            CrossCheck("atm_strike", observed_strike, None, VERDICT_UNAVAILABLE, src,
                       "cannot derive the strike without the spot"),
        ]
    out = [_cmp("index_ltp_at_open", observed_index_ltp, q2(bar.open), src, tol=0.005)]
    atm = nearest_listed_strike(bar.open, listed_strikes)
    out.append(_cmp("atm_strike", observed_strike, atm, src,
                    note="nearest listed strike to the externally observed open"))
    return out


def check_contract_metadata(
    *,
    observed_lot_size: Optional[int],
    observed_tick_size: Optional[float],
    expiry: str,
    strike: Optional[float],
    instrument_rows: Sequence[dict],
) -> list[CrossCheck]:
    """Compare lot size, tick size, ladder spacing and listing against the master.

    ``instrument_rows`` are dicts with at least ``expiry``, ``strike``,
    ``option_type``, ``lot_size``, ``tick_size``.
    """
    src = f"instrument master, expiry {expiry}"
    rows = [r for r in instrument_rows if str(r.get("expiry"))[:10] == expiry]
    if not rows:
        return [CrossCheck("expiry_listed", expiry, None, VERDICT_UNAVAILABLE, src,
                           "expiry absent from the supplied instrument master")]

    lots = {int(r["lot_size"]) for r in rows if r.get("lot_size")}
    ticks = {float(r["tick_size"]) for r in rows if r.get("tick_size")}
    ce = {float(r["strike"]) for r in rows if r.get("option_type") == "CE"}
    pe = {float(r["strike"]) for r in rows if r.get("option_type") == "PE"}
    both = sorted(ce & pe)
    spacings = {round(both[i + 1] - both[i]) for i in range(len(both) - 1)}

    # Resolve each value to a local *before* building the CrossCheck. Popping a
    # set inside an argument list mutates it, and a later argument that re-reads
    # its length then sees the wrong size -- which silently downgraded a uniform
    # ladder to UNAVAILABLE.
    lot = lots.pop() if len(lots) == 1 else None
    tick = ticks.pop() if len(ticks) == 1 else None
    spacing = spacings.pop() if len(spacings) == 1 else None

    out = [
        CrossCheck("expiry_listed", expiry, expiry, VERDICT_MATCH, src),
        _cmp("lot_size", observed_lot_size, lot, src,
             note="uniform across the expiry" if lot is not None else "not uniform"),
        _cmp("tick_size", observed_tick_size, tick, src, tol=1e-9),
        CrossCheck("strike_ladder_uniform", spacing, spacing,
                   VERDICT_MATCH if spacing is not None else VERDICT_UNAVAILABLE, src,
                   f"{len(both)} strikes with both legs listed"),
    ]
    if strike is not None:
        listed = strike in ce and strike in pe
        out.append(CrossCheck("strike_has_both_legs", strike, strike if listed else None,
                              VERDICT_MATCH if listed else VERDICT_MISMATCH, src))
    return out


def summarise(checks: Sequence[CrossCheck]) -> dict:
    return {
        "match": sum(1 for c in checks if c.verdict == VERDICT_MATCH),
        "mismatch": sum(1 for c in checks if c.verdict == VERDICT_MISMATCH),
        "unavailable": sum(1 for c in checks if c.verdict == VERDICT_UNAVAILABLE),
        # A cross-check with nothing to compare against is not a pass, but it is
        # also not a contradiction. Only a real disagreement fails.
        "contradicted": any(c.verdict == VERDICT_MISMATCH for c in checks),
        "checks": [
            {"field": c.field, "observed": c.observed, "external": c.external,
             "verdict": c.verdict, "source": c.source, "note": c.note}
            for c in checks
        ],
    }


def format_table(checks: Sequence[CrossCheck]) -> str:
    lines = ["| Field | From the recording | From market data | Verdict | Source |",
             "|---|---|---|---|---|"]
    for c in checks:
        o = "—" if c.observed is None else c.observed
        e = "—" if c.external is None else c.external
        lines.append(f"| {c.field} | {o} | {e} | {c.verdict} | {c.source} |")
    return "\n".join(lines)
