"""Bar-by-bar replay of the Gamma Move engine over stored history.

It drives ``GammaMoveStrategy`` -- the same object the live runner drives -- so a
replay result is evidence about the shipped code rather than about a second
implementation that happens to agree today.

No broker, no clock, no network. Fills are the bar's own close, which is
optimistic and is stated as such in the result: a real fill crosses a spread
that on these contracts is wide, and no replay number here is net of cost.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

from .config import GammaMoveConfig
from .models import Candle, OICandle, SpotLevel, StrikeCandidate, q2
from .strategy import GammaMoveStrategy, Intent
from .trigger import session_day

_IST = timezone(timedelta(hours=5, minutes=30))


def replay_contract(candidate: StrikeCandidate, bars: Sequence[OICandle],
                    cfg: GammaMoveConfig, *, regime_by_day: Optional[dict] = None,
                    spot_candles: Optional[Sequence[Candle]] = None) -> dict:
    """Walk one contract's history and report every decision the engine made."""
    strat = GammaMoveStrategy(cfg)
    regime_by_day = regime_by_day or {}
    events: list[dict] = []
    series = list(bars)

    for i in range(2, len(series)):
        window = series[:i + 1]
        bar = series[i]
        day = session_day(bar.ts_ms)
        today = datetime.fromtimestamp(bar.ts_ms / 1000, _IST).date()
        strat.state.roll(day)
        regime = regime_by_day.get(day, "unknown")

        # Manage what is open before looking for anything new: a replay that
        # enters again while still holding overstates the strategy's capacity.
        for pos in list(strat.state.positions.values()):
            decision = strat.on_price(pos, bar.close, bar.ts_ms, day)
            if decision.intent is Intent.EXIT and decision.exit_position:
                pnl = strat.on_exit(decision.exit_position, bar.close, day)
                events.append({"kind": "exit", "ts_ms": bar.ts_ms, "day": day,
                               "price": q2(bar.close), "reason": decision.exit_reason,
                               "pnl_inr": pnl})

        signal = strat.evaluate(candidate, window, now_ms=bar.ts_ms, today=today,
                                regime=regime)
        if signal.state != "armed":
            continue
        blocker = strat.admit(signal, day)
        if blocker:
            events.append({"kind": "refused", "ts_ms": bar.ts_ms, "day": day,
                           "reason": blocker})
            continue
        strat.on_entry(signal, signal.entry or bar.close, bar.ts_ms, day)
        events.append({"kind": "entry", "ts_ms": bar.ts_ms, "day": day,
                       "price": signal.entry, "stop": signal.stop,
                       "lots": signal.lots, "quantity": signal.quantity,
                       "metrics": signal.metrics.as_dict() if signal.metrics else None})

    # Anything still open at the end of the record is marked, not silently
    # closed at the last price -- an unresolved trade is not a winner.
    open_positions = [{"symbol": sym, "entry": p.entry, "stop": p.stop}
                      for sym, p in strat.state.positions.items()]
    return {
        "tradingsymbol": candidate.instrument.tradingsymbol,
        "underlying": candidate.underlying,
        "bars": len(series), "events": events,
        "record": strat.state.record.as_dict(),
        "open_at_end": open_positions,
        "caveats": [
            "fills are the bar close; no spread, no slippage, no brokerage",
            "the level is held fixed for the whole replay, so it does not "
            "reproduce a level being discovered mid-window",
        ],
    }


def summarise(results: Sequence[dict]) -> dict:
    """Aggregate several contract replays into one honest verdict."""
    entries = sum(1 for r in results for e in r["events"] if e["kind"] == "entry")
    closed = [e for r in results for e in r["events"] if e["kind"] == "exit"]
    wins = [e for e in closed if (e.get("pnl_inr") or 0) > 0]
    pnl = sum(e.get("pnl_inr") or 0 for e in closed)
    unresolved = sum(len(r["open_at_end"]) for r in results)
    return {
        "contracts": len(results), "entries": entries, "closed": len(closed),
        "unresolved": unresolved, "wins": len(wins),
        "win_rate": q2(100.0 * len(wins) / len(closed)) if closed else None,
        "gross_pnl_inr": q2(pnl),
        # A win rate without its break-even threshold is not an answer, so the
        # caller is handed both or neither.
        "break_even_win_rate": _break_even(closed),
        "verdict": ("no closed trades" if not closed
                    else f"{len(wins)}/{len(closed)} winners, gross Rs {pnl:,.0f}"),
    }


def _break_even(closed: Sequence[dict]) -> Optional[float]:
    """The win rate this average win/loss pair would need just to break even."""
    wins = [e["pnl_inr"] for e in closed if (e.get("pnl_inr") or 0) > 0]
    losses = [-e["pnl_inr"] for e in closed if (e.get("pnl_inr") or 0) <= 0]
    if not wins or not losses:
        return None
    avg_w, avg_l = sum(wins) / len(wins), sum(losses) / len(losses)
    if avg_w + avg_l <= 0:
        return None
    return q2(100.0 * avg_l / (avg_w + avg_l))
