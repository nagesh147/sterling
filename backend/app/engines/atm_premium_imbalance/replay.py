"""Bar-level replay of a recorded session against real exchange data.

**What this can and cannot establish.** The strategy is tick-driven: it enters on
the first usable tick and exits on the first tick at or beyond the target. Kite's
finest historical granularity is a one-minute bar, which is a four-way summary of
sixty seconds. So a bar replay can check *prices and decisions*, never the tick
sequence:

===========================  ==================================================
Checkable from bars          Not checkable from bars
===========================  ==================================================
first tick (= 09:15 open)    the order two legs updated in
ATM strike (from the index)  the exact fill price
which leg was cheaper        the bid/ask the exit was priced off
the computed order price     sub-minute timing
whether the target was hit   whether it was hit before or after some other tick
===========================  ==================================================

The exit *order* price cannot be reproduced at all: it is `best_bid − 0.50`, and
bars carry no depth. What a bar can do is **bracket** it — if the recorded fill
lies outside the containing minute's [low, high], the recording and the exchange
disagree and something is wrong.

No synthetic intra-bar path is invented. Where a tick stream is needed to drive
the engine, only prices the bar actually evidences are emitted (open, and the
high once it is relevant), and the result is labelled as such.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Sequence

from .config import ATMPremiumImbalanceConfig
from .conformance import MATCH, MISMATCH, UNVERIFIED, FieldComparison
from .models import LegQuote, OptionPairRef, OrderReport, OrderStatus, q2
from .selection import select_atm_strike
from .strategy import ATMPremiumImbalanceStrategy

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_OPEN = time(9, 15)


@dataclass(frozen=True)
class Bar:
    """One minute bar, in real price units, stamped in IST."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def ist(self) -> datetime:
        return self.ts.astimezone(IST)

    def contains(self, price: float) -> bool:
        return self.low - 1e-9 <= price <= self.high + 1e-9


@dataclass(frozen=True)
class ObservedSession:
    """What the recording said, so the replay has something to disagree with.

    Every field is optional: a session where a value was never printed must
    produce `UNVERIFIED`, not a fabricated comparison.
    """

    label: str
    session: date
    expiry: str
    strike: Optional[float] = None
    option_type: Optional[str] = None
    first_tick_price: Optional[float] = None
    entry_order_price: Optional[float] = None
    entry_fill: Optional[float] = None
    exit_order_price: Optional[float] = None
    exit_fill: Optional[float] = None
    quantity: Optional[int] = None
    index_at_open: Optional[float] = None
    #: A price the recording used that did NOT come from this session, with the
    #: session it did come from. Supplying it makes the replay feed that value in
    #: first, exactly as the feed delivered it, and check that the engine refuses
    #: to price from it. Leave unset for sessions with no such fault.
    stale_price: Optional[float] = None
    stale_traded_at_ms: Optional[int] = None


def open_bar(bars: Sequence[Bar], session: date) -> Optional[Bar]:
    """The 09:15 IST bar — the one the session's first trade falls in."""
    for b in bars:
        i = b.ist
        if i.date() == session and i.hour == MARKET_OPEN.hour and i.minute == MARKET_OPEN.minute:
            return b
    return None


def session_bars(bars: Sequence[Bar], session: date) -> list[Bar]:
    out = [b for b in bars if b.ist.date() == session]
    return sorted(out, key=lambda b: b.ts)


def first_bar_reaching(bars: Sequence[Bar], target: float, *, after: datetime) -> Optional[Bar]:
    """Earliest bar strictly after ``after`` whose high reaches ``target``.

    'The target was hit somewhere in this minute' is the strongest claim a bar
    supports; it does not say when within the minute.
    """
    for b in bars:
        if b.ts <= after:
            continue
        if b.high + 1e-9 >= target:
            return b
    return None


def _cmp(field: str, observed, replayed, note: str = "", tol: float = 0.0) -> FieldComparison:
    if observed is None or replayed is None:
        return FieldComparison(field, observed, replayed, UNVERIFIED, note)
    if isinstance(observed, (int, float)) and isinstance(replayed, (int, float)):
        ok = abs(float(observed) - float(replayed)) <= tol
    else:
        ok = observed == replayed
    return FieldComparison(field, observed, replayed, MATCH if ok else MISMATCH, note)


@dataclass
class ReplayResult:
    label: str
    checks: list[FieldComparison] = field(default_factory=list)
    engine_summary: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def match(self) -> int:
        return sum(1 for c in self.checks if c.verdict == MATCH)

    @property
    def mismatch(self) -> int:
        return sum(1 for c in self.checks if c.verdict == MISMATCH)

    @property
    def unverified(self) -> int:
        return sum(1 for c in self.checks if c.verdict == UNVERIFIED)

    @property
    def contradicted(self) -> bool:
        return self.mismatch > 0

    def table(self) -> str:
        lines = ["| Check | Recording | Kite bars | Verdict | Note |", "|---|---|---|---|---|"]
        for c in self.checks:
            o = "—" if c.observed is None else c.observed
            r = "—" if c.replayed is None else c.replayed
            lines.append(f"| {c.field} | {o} | {r} | {c.verdict} | {c.evidence} |")
        return "\n".join(lines)


def replay_session(
    observed: ObservedSession,
    *,
    cfg: ATMPremiumImbalanceConfig,
    ce_bars: Sequence[Bar],
    pe_bars: Sequence[Bar],
    index_bars: Sequence[Bar] = (),
    listed_strikes: Sequence[float] = (),
    pair: Optional[OptionPairRef] = None,
) -> ReplayResult:
    """Compare a recorded session against real minute bars.

    Runs the checks bars can support, and where a pair is supplied also drives
    the real strategy engine so the *decisions* (which leg, what order price) come
    from production code rather than from arithmetic repeated here.
    """
    res = ReplayResult(label=observed.label)
    ce = session_bars(ce_bars, observed.session)
    pe = session_bars(pe_bars, observed.session)
    idx = session_bars(index_bars, observed.session)

    if not ce or not pe:
        res.notes.append("no option bars for this session — nothing checkable")
        res.checks.append(FieldComparison("option_bars", "required", None, UNVERIFIED,
                                          "Kite returned no minute bars for one or both legs"))
        return res

    ce0, pe0 = open_bar(ce, observed.session), open_bar(pe, observed.session)
    if ce0 is None or pe0 is None:
        res.notes.append("no 09:15 IST bar for one or both legs")
        res.checks.append(FieldComparison("open_bar", "09:15 IST", None, UNVERIFIED,
                                          "session open bar missing"))
        return res

    # --- index open -> the ATM strike the strategy should have chosen
    idx0 = open_bar(idx, observed.session) if idx else None
    if idx0 is not None and listed_strikes:
        res.checks.append(_cmp("index_at_open", observed.index_at_open, q2(idx0.open),
                               "index 09:15 bar open", tol=0.005))
        res.checks.append(_cmp("atm_strike", observed.strike,
                               select_atm_strike(idx0.open, listed_strikes),
                               "nearest listed strike to the index open"))

    # --- which leg was cheaper at the open
    cheaper = "CE" if ce0.open < pe0.open else ("PE" if pe0.open < ce0.open else None)
    res.checks.append(_cmp("option_type", observed.option_type, cheaper,
                           f"CE open {q2(ce0.open)} vs PE open {q2(pe0.open)}"))

    # --- the first tick: the selected leg's 09:15 open
    sel0 = ce0 if cheaper == "CE" else pe0
    res.checks.append(_cmp("first_tick_price", observed.first_tick_price, q2(sel0.open),
                           "selected leg's 09:15 bar open", tol=0.005))

    # --- the order price the policy computes from that first tick
    if cfg.entry_price_policy == "FIRST_TICK_PERCENT":
        computed = round(sel0.open * (1.0 + cfg.entry_through_pct), 1)
        res.checks.append(_cmp("entry_order_price", observed.entry_order_price, q2(computed),
                               f"first tick x (1 + {cfg.entry_through_pct:g}), to 1 dp", tol=0.005))

    # --- the fill must at least lie inside the minute it happened in
    if observed.entry_fill is not None:
        res.checks.append(FieldComparison(
            "entry_fill_within_open_bar", observed.entry_fill,
            f"[{q2(sel0.low)}, {q2(sel0.high)}]",
            MATCH if sel0.contains(observed.entry_fill) else MISMATCH,
            "bars cannot give the fill, only bracket it"))

    # --- was the target reachable, and when
    if observed.entry_fill is not None:
        target = q2(observed.entry_fill + cfg.target_points)
        sel_bars = ce if cheaper == "CE" else pe
        hit = first_bar_reaching(sel_bars, target, after=sel0.ts)
        res.checks.append(FieldComparison(
            "target_reached", f"{target} (fill + {cfg.target_points:g})",
            None if hit is None else hit.ist.strftime("%H:%M IST"),
            MATCH if hit is not None else MISMATCH,
            "first minute whose high reaches the target"))
        if hit is not None and observed.exit_fill is not None:
            res.checks.append(FieldComparison(
                "exit_fill_within_target_bar", observed.exit_fill,
                f"[{q2(hit.low)}, {q2(hit.high)}]",
                MATCH if hit.contains(observed.exit_fill) else MISMATCH,
                "brackets only; the exit price itself needs depth"))

    # --- drive the real engine, so decisions come from production code
    if pair is not None:
        res.engine_summary = _drive_engine(cfg, pair, observed, ce0, pe0, cheaper)
        if res.engine_summary:
            engine_px = res.engine_summary.get("entry_order_price")
            res.checks.append(_cmp("engine_option_type", observed.option_type,
                                   res.engine_summary.get("option"),
                                   "decided by the live strategy engine"))
            # Two different questions, kept apart. Comparing the engine to the
            # recording asks "do we reproduce the bot"; comparing it to the
            # market asks "are we right". When the bot was wrong those answers
            # must differ, and a single row would hide that.
            res.checks.append(_cmp("engine_vs_recording", observed.entry_order_price,
                                   engine_px,
                                   "our order price vs what the bot sent", tol=0.005))
            if cfg.entry_price_policy == "FIRST_TICK_PERCENT":
                market_px = round(sel0.open * (1.0 + cfg.entry_through_pct), 1)
                res.checks.append(_cmp("engine_vs_market", q2(market_px), engine_px,
                                       "our order price vs the exchange open x "
                                       f"(1 + {cfg.entry_through_pct:g})", tol=0.005))
            if observed.stale_price is not None:
                used = res.engine_summary.get("first_tick_price")
                res.checks.append(FieldComparison(
                    "stale_price_rejected", observed.stale_price, used,
                    MATCH if (used is not None and abs(used - observed.stale_price) > 1e-9)
                    else MISMATCH,
                    "the out-of-session price was fed in first; the engine must not price from it"))
    res.notes.append(
        "Minute bars only. Fill prices and the bid-derived exit price are bracketed, "
        "not reproduced; tick ordering is not testable at this granularity."
    )
    return res


def _drive_engine(cfg, pair, observed, ce0: Bar, pe0: Bar, cheaper) -> dict:
    """Feed the two 09:15 opens to the real engine and read its decision.

    Only prices the bars actually evidence are emitted, and each is **dated**
    from its bar: a trade inside the 09:15 bar happened at or after the session
    open, so the quote is genuinely session-origin rather than merely undatable.
    Leaving it undated would make the session-origin gate a no-op here and the
    replay would silently stop testing it.

    When ``observed.stale_price`` is set, that value is fed in *first*, stamped in
    the session it really came from -- reproducing the feed order the recording
    saw -- so the replay exercises the rejection path rather than assuming it.
    """
    if observed.quantity is None or observed.quantity <= 0:
        return {}
    strat = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=pair, quantity=observed.quantity, trade_id=f"replay-{observed.label}"
    )
    bar_ms = int(ce0.ts.timestamp() * 1000)
    now = bar_ms
    intent = None

    def emit(inst_id, price, traded_ms, official_open):
        nonlocal now, intent
        now += 50
        intent = strat.on_option_tick(
            LegQuote(instrument_id=inst_id, ltp=float(price), bid=None, ask=None,
                     exchange_ts_ms=now, received_ts_ms=now, sequence=now,
                     last_trade_ts_ms=traded_ms, official_open=official_open,
                     source="kite_minute_bar"),
            now,
        )

    if observed.stale_price is not None and observed.stale_traded_at_ms is not None:
        # The carried-over price, on the leg the recording actually bought.
        stale_leg = pair.leg(observed.option_type or "PE")
        other = pair.pe if stale_leg is pair.ce else pair.ce
        other_bar = pe0 if stale_leg is pair.ce else ce0
        emit(other.instrument_id, other_bar.open, observed.stale_traded_at_ms, None)
        emit(stale_leg.instrument_id, observed.stale_price, observed.stale_traded_at_ms, None)

    for inst_id, bar in ((pair.ce.instrument_id, ce0), (pair.pe.instrument_id, pe0)):
        emit(inst_id, bar.open, bar_ms, bar.open)
    # Acknowledge the entry so the summary carries the computed order price. The
    # fill used is the recording's, because bars cannot supply one.
    if intent.kind == "submit_entry" and observed.entry_fill is not None:
        intent = strat.record_entry_submit(intent.priced, order_id="replay")
        strat.record_entry_status(OrderReport(
            order_id="replay", status=OrderStatus.COMPLETE, transaction="BUY",
            average_price=float(observed.entry_fill), filled_quantity=observed.quantity))
    return strat.summary()
