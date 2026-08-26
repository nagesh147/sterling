"""Every closed ATM trade, on disk, and the one number that decides the strategy.

Before this existed the only thing the strategy persisted was its *config*. A
closed trade lived on an in-memory session object and died at restart or at the
end of the day, so running it in paper for fifty sessions produced fifty days of
terminal scrollback and nothing anybody could count.

That is what this fixes, and it is the whole point of it: the strategy wins about
+3% net when it wins and can lose most of the premium when it does not, so its
viability is decided almost entirely by **how often it wins**. That number cannot
be inferred from three recordings -- a strategy that merely breaks even shows
three straight winners four times out of five. It has to be measured forward.

Two rules keep the measurement honest:

* **Simulated trades are recorded but never counted.** A replay writes rows so a
  session can be reviewed, and :func:`summary` excludes them by default. A sim
  fill is modelled at a price nobody paid; letting it into the win rate would
  corrupt the only statistic that matters.
* **The summary reports the break-even win rate next to the actual one.** A win
  rate alone says nothing -- 85% is excellent against a small average loss and
  ruinous against a large one. Reporting the threshold beside the measurement is
  the difference between a number and an answer.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.services import db

log = get_logger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if hasattr(value, "value"):          # Enum
        return value.value
    return value


def record(trade: Any, *, underlying: str, mode: str, is_sim: bool,
           closed_at_ms: Optional[int] = None) -> bool:
    """Persist one closed trade. Never raises into the trading path.

    A journal write must not be able to break a trade, so every failure is logged
    and swallowed -- but it is logged loudly, because a silently empty journal
    looks exactly like a strategy that never traded.
    """
    entry, exit_ = getattr(trade, "entry_price", None), getattr(trade, "exit_price", None)
    if entry is None or exit_ is None or not entry:
        return False
    try:
        ts = closed_at_ms or int(datetime.now(IST).timestamp() * 1000)
        session_date = datetime.fromtimestamp(ts / 1000, tz=IST).date().isoformat()
        with db.connection() as conn:
            conn.execute(
                "INSERT INTO atm_trades (session_date, underlying, option_type, strike,"
                " expiry, quantity, entry_price, exit_price, points, pnl, exit_reason,"
                " mode, is_sim, raw) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_date, underlying, getattr(trade, "option_type", "") or "",
                 getattr(trade, "strike", None), getattr(trade, "expiry", None),
                 int(getattr(trade, "quantity", 0) or 0), float(entry), float(exit_),
                 float(getattr(trade, "points", 0.0) or 0.0),
                 float(getattr(trade, "pnl", 0.0) or 0.0),
                 getattr(getattr(trade, "exit", None), "reason", None),
                 mode, 1 if is_sim else 0,
                 json.dumps(_jsonable(trade), default=str, separators=(",", ":"))),
            )
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("ATM journal could not record a closed trade: %s", exc)
        return False


def summary(*, include_sim: bool = False, underlying: str = "",
            limit: int = 0) -> dict:
    """What the journal knows, and whether it is enough to conclude anything.

    ``break_even_win_rate`` is the number to read first: it is
    ``avg_loss / (avg_win + avg_loss)`` from the *measured* distribution, so
    comparing it against ``win_rate`` says directly whether the strategy is above
    or below water. ``verdict`` refuses to answer below a minimum sample rather
    than reporting a win rate computed from four trades as if it meant something.
    """
    where, args = ["1=1"], []
    if not include_sim:
        where.append("is_sim = 0")
    if underlying:
        where.append("underlying = ?")
        args.append(underlying)
    sql = (f"SELECT entry_price, points, pnl, exit_reason FROM atm_trades "
           f"WHERE {' AND '.join(where)} ORDER BY id DESC")
    if limit > 0:
        sql += f" LIMIT {int(limit)}"
    try:
        with db.connection() as conn:
            rows = list(conn.execute(sql, args))
    except Exception as exc:  # noqa: BLE001
        log.warning("ATM journal could not be read: %s", exc)
        rows = []

    # Percentage of premium, not rupees: the whole reason a fixed +15 target is
    # suspect is that the same points mean different risk at different premiums,
    # so the statistic that generalises has to be scale-free.
    pcts = [(r[1] / r[0]) * 100.0 for r in rows if r[0]]
    wins = [p for p in pcts if p > 0]
    losses = [-p for p in pcts if p < 0]
    n = len(pcts)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    win_rate = (len(wins) / n * 100.0) if n else 0.0
    breakeven = (avg_loss / (avg_win + avg_loss) * 100.0) if (avg_win + avg_loss) else None

    reasons: dict[str, int] = {}
    for r in rows:
        reasons[r[3] or "unknown"] = reasons.get(r[3] or "unknown", 0) + 1

    MIN_SAMPLE = 30
    if n < MIN_SAMPLE:
        verdict = f"not enough trades yet — {n} of {MIN_SAMPLE} before a win rate means anything"
    elif breakeven is None:
        verdict = "no losing trades yet, so no break-even threshold can be computed"
    elif win_rate > breakeven:
        verdict = f"above water: winning {win_rate:.1f}% against a {breakeven:.1f}% break-even"
    else:
        verdict = f"BELOW WATER: winning {win_rate:.1f}% but needs {breakeven:.1f}% to break even"

    return {
        "trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "break_even_win_rate_pct": None if breakeven is None else round(breakeven, 2),
        "expectancy_pct": round(sum(pcts) / n, 3) if n else 0.0,
        "worst_pct": round(min(pcts), 2) if pcts else 0.0,
        "best_pct": round(max(pcts), 2) if pcts else 0.0,
        "total_pnl": round(sum(r[2] for r in rows), 2),
        "exit_reasons": reasons,
        "min_sample": MIN_SAMPLE,
        "verdict": verdict,
    }
