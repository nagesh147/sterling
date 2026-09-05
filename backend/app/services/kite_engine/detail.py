"""Compose the click-through detail for a ready signal: trigger context, live
underlying price, and per-leg option quote + market depth + Black-Scholes greeks.

Kite-only; reads live quotes via the user's client. No other-engine imports.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.logging import get_logger
from app.engines.sterling_kite_engine.schemas import (
    DepthLevel, EngineDetailResponse, OptionDetail,
)
from app.services.kite_engine.greeks import black_scholes_greeks, implied_vol
from app.services.kite_engine.scanner import scanner
from app.services.kite_engine.market_hours import continuous_close

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))


#: Indian equity/index options stop trading at 15:30 IST on their expiry day.
_EXPIRY_CLOSE_IST = (15, 30)


def intraday_dte_days(expiry: str, now: Optional[datetime] = None, *, exchange: str = "NFO") -> float:
    """Fractional days left until the 15:30 IST expiry close.

    Whole-day arithmetic returns 0 for the entire expiry session, which drives
    ``black_scholes_greeks`` and ``implied_vol`` into their degenerate branch:
    delta hardcoded to ±1.00 or 0.00, gamma/theta/vega zeroed, IV unsolvable.
    On the highest-volume day of the option's life the panel would then show a
    fabricated delta of 1.00 for a contract that is very much still moving —
    and the badges built on that delta would follow it.

    The scanner already floors its own DTE at 1 day (``_dte_from_expiry``), so
    before this the stop shown for a leg and the delta shown for the same leg
    came from two different models. This is the display path's answer, and it
    is the more precise one: hours, not days.
    """
    now = now or datetime.now(_IST)
    try:
        day = datetime.strptime(str(expiry)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 0.0
    close = datetime.combine(day, continuous_close(day, exchange), tzinfo=_IST)
    return max(0.0, (close - now).total_seconds() / 86_400.0)


def _spot_symbol(underlying: str, option_exchange: str) -> str:
    # SENSEX/BSE names quote on BSE; everything else on NSE. Display name == LTP
    # symbol for indices ("NIFTY 50") and stocks ("RELIANCE") alike.
    return ("BSE:" if option_exchange == "BFO" else "NSE:") + underlying


def _levels(side: list) -> List[DepthLevel]:
    out: List[DepthLevel] = []
    for lv in (side or []):
        try:
            out.append(DepthLevel(price=float(lv.get("price") or 0.0),
                                  quantity=int(lv.get("quantity") or 0),
                                  orders=int(lv.get("orders") or 0)))
        except (TypeError, ValueError):
            continue
    return out


def _navigator_row_for_token(uid: str, token: int, timestamp_ms: int, *, exact: bool = False):
    """Find a Navigator-owned row by token in Navigator's own snapshot.

    Navigator-originated rows never pass through the Kite engine's scanner, and
    when the SuperTrend engine is switched off that scanner has no rows at all —
    so the board the user clicked may be entirely Navigator's. Same
    token-or-leg-token matching the scanner does, with the timestamp preferred
    but not required (a background scan can regroup the row between the click
    and this request)."""
    try:
        from app.services.navigator import runtime as navigator_runtime
        rows = navigator_runtime.snapshot(uid).rows
    except Exception as exc:  # noqa: BLE001
        log.debug("navigator detail lookup unavailable for %s: %s", uid, exc)
        return None

    def _token_matches(row) -> bool:
        return row.token == token or any(getattr(leg, "token", None) == token for leg in row.legs)

    candidates = [row for row in rows if _token_matches(row)]
    if not candidates:
        return None
    if timestamp_ms > 0:
        hit = next((row for row in candidates if row.timestamp_ms == timestamp_ms), None)
        if hit is not None:
            return hit
    if exact:
        return None  # caller wants certainty, not the nearest thing
    return max(candidates, key=lambda row: row.timestamp_ms)


async def build_detail(
    client, uid: str, token: int, timestamp_ms: int = 0, source: Optional[str] = None,
) -> Optional[EngineDetailResponse]:
    """Build detail for the selected signal row.

    Resolution order matters. A Navigator origination is keyed on the SAME
    underlying token as the SuperTrend rows for that instrument, so a loose
    token match in the engine's snapshot will happily answer a click on a
    Navigator row with a different signal's plan — different entry, different
    stop, different legs. Two rules keep that from happening:

    * `source` (sent by the board) picks which snapshot owns the row;
    * failing that, an EXACT timestamp match in either snapshot always beats a
      loose same-token match in the other.

    The loose fallback still exists, and still comes last: a background scan can
    regroup a row between the click and this request, and answering with the
    current row for that instrument beats a misleading 404.
    """
    snapshot = scanner.snapshot(uid)
    engine_exact = snapshot.row_for_token(token, timestamp_ms) if timestamp_ms > 0 else None
    navigator_exact = _navigator_row_for_token(uid, token, timestamp_ms, exact=True) if timestamp_ms > 0 else None

    if source == "navigator":
        row = navigator_exact or _navigator_row_for_token(uid, token, timestamp_ms) or engine_exact
    elif source:
        row = engine_exact or snapshot.row_for_token(token) or navigator_exact
    else:
        row = engine_exact or navigator_exact
    if row is None:
        row = snapshot.row_for_token(token) or _navigator_row_for_token(uid, token, timestamp_ms)
    if row is None:
        return None

    spot_sym = _spot_symbol(row.underlying, row.exchange)
    spot_now = 0.0
    try:
        d = await client.get_ltp([spot_sym])
        spot_now = float((d.get(spot_sym) or {}).get("last_price") or 0.0)
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine detail LTP failed %s: %s", spot_sym, exc)
    spot_ref = spot_now or row.spot

    qsyms = [f"{row.exchange}:{leg.option_symbol}" for leg in row.legs]
    quotes = {}
    if qsyms:
        try:
            quotes = await client.get_quote(qsyms)
        except Exception as exc:  # noqa: BLE001
            log.warning("kite-engine detail quote failed: %s", exc)

    now_ist = datetime.now(_IST)
    options: List[OptionDetail] = []
    for leg in row.legs:
        q = quotes.get(f"{row.exchange}:{leg.option_symbol}", {}) or {}
        depth = q.get("depth", {}) or {}
        buy, sell = _levels(depth.get("buy", [])), _levels(depth.get("sell", []))
        bid = buy[0].price if buy else 0.0
        ask = sell[0].price if sell else 0.0
        ltp = float(q.get("last_price") or 0.0)
        iv = float(q.get("implied_volatility") or 0.0) / 100.0
        dte_exact = intraday_dte_days(leg.expiry, now=now_ist, exchange=row.exchange)
        dte = int(dte_exact)  # whole days, for display only
        # Live IV is absent after hours — back it out of the last traded premium so
        # greeks stay meaningful (the user often looks when the market is closed).
        if iv <= 0 and ltp > 0:
            iv = implied_vol(price=ltp, spot=spot_ref, strike=leg.strike,
                             dte_days=dte_exact, option_type=leg.option_type)
        g = black_scholes_greeks(spot=spot_ref, strike=leg.strike, dte_days=dte_exact,
                                 iv=iv, option_type=leg.option_type)
        options.append(OptionDetail(
            moneyness=leg.moneyness, option_type=leg.option_type,
            option_symbol=leg.option_symbol, strike=leg.strike, expiry=leg.expiry,
            lot_size=leg.lot_size, dte=dte, last_price=ltp, bid=bid, ask=ask, iv=iv,
            delta=g.delta, gamma=g.gamma, theta=g.theta, vega=g.vega,
            greeks_solved=g.solved, depth_buy=buy, depth_sell=sell,
            entry_premium=leg.premium_spot, initial_stop_premium=leg.entry_sl,
            trail_stop_premium=leg.premium_sl, target_premium=leg.premium_target,
            is_active=bool(leg.is_active),
        ))

    return EngineDetailResponse(
        underlying=row.underlying, token=row.token, exchange=row.exchange,
        direction=row.direction, regime=row.regime, alignment=row.alignment, option_type=row.option_type,
        triggered_ms=row.timestamp_ms,
        # For "spot" signals row.spot is the underlying at trigger; for "derivatives"
        # row.spot is the premium (zeroed after grouping), so use the separately
        # captured underlying_spot.
        spot_at_trigger=(row.underlying_spot if (row.underlying_spot or 0) > 0 else row.spot),
        spot_now=spot_now,
        stop_loss=row.stop_loss, options=options,
        resolution_reason=getattr(row, "resolution_reason", None),
        source=row.source, score=row.score,
        entry_sl=row.entry_sl, target=row.target, exit_state=row.exit_state,
        exit_reason=row.exit_reason,
        is_active=bool(row.is_active), is_fresh=bool(row.is_fresh),
        adx=row.adx, atr_pct=row.atr_pct,
        navigator=row.navigator,
    )
