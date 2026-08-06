"""Turning a just-placed order into a PROTECTED position.

Everything a position needs the moment it is opened — registry entry, tick
subscription, broker-side stop (and target, when the signal has one) — happens
here, in one function, for every order path.

It lives in its own module because it previously lived inline in the auto-exec
callback, which is why `positions.register` had exactly ONE call site: an order
you placed by hand from the signal board got no registry entry, no stop, no
monitor and no expiry square-off, while the board went on displaying an SL, a
TSL and a Target beside it. The display was the dangerous part — an unguarded
position that looks guarded.

Two rules the callers depend on:

* **The plan comes from the server, not the client.** `plan_for_symbol` reads the
  levels the board is already showing for that exact contract out of the live
  scanner/Navigator snapshots. A stop supplied by the browser would be a number
  the server cannot verify but would act on.
* **No plan means no protection, said out loud.** `arm_position` reports what it
  actually armed. A caller that gets `stop_premium == 0` must tell the user the
  position is unprotected instead of letting the board imply otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger
from app.services.kite_engine import positions, protective_stop, state

log = get_logger(__name__)


@dataclass(frozen=True)
class LegPlan:
    """The board's own plan for one option contract, as the server computed it."""

    symbol: str
    exchange: str
    token: int
    lot_size: int
    entry_premium: float
    stop_premium: float
    target_premium: float
    strike: float
    expiry: str
    underlying: str
    direction: str
    source: str
    #: Underlying spot and SIGNED delta at the signal, needed to re-translate the
    #: underlying trail into a premium stop on later scans.
    entry_spot: float
    entry_delta: float
    #: False when the leg's SuperTrend is no longer aligned — the plan is a snapshot of
    #: a signal that has already ended, so its trail is frozen wherever it died.
    live: bool = True

    @property
    def protectable(self) -> bool:
        return self.stop_premium > 0


def _rows_for(uid: str) -> list:
    """Every row on the user's board right now, from both engines.

    Order matters only for duplicate contracts; the scanner's rows come first
    because a leg that both engines resolved is the same contract with the same
    premium plan either way.
    """
    rows: list = []
    try:
        from app.services.kite_engine.scanner import scanner
        rows.extend(scanner.snapshot(uid).rows or [])
    except Exception as exc:  # noqa: BLE001 — a missing snapshot is not an error here
        log.debug("protection: scanner snapshot unavailable for %s: %s", uid, exc)
    try:
        from app.services.navigator import runtime as navigator_runtime
        rows.extend(navigator_runtime.snapshot(uid).rows or [])
    except Exception as exc:  # noqa: BLE001
        log.debug("protection: navigator snapshot unavailable for %s: %s", uid, exc)
    return rows


#: Fixed BS IV for the spot→premium delta translation. Must match
#: ``service._IV_ASSUMPTION``, which the auto-exec path uses for the same purpose —
#: two entries into the same contract should not trail at different levels.
_IV_ASSUMPTION = 0.18


def _signed_delta(option_type: str, spot: float, strike: float, expiry: str) -> float:
    """SIGNED BS delta (+ for a CE, − for a PE) for the trail translation.

    ``OptionLeg`` carries no delta of its own, and this used to read a field that does
    not exist and then take ``abs()`` of it — so it was always 0.0, and 0.0 makes
    ``_new_trail_for_open`` bail, which is why a hand-placed position's stop never
    ratcheted while the board showed its TSL moving. The sign matters as much as the
    value: ``premium_stop_from_move`` needs − for a PE or the stop lands on the wrong
    side of the premium.
    """
    is_call = str(option_type or "").upper().startswith("C")
    try:
        from app.services.kite_engine.greeks import black_scholes_greeks
        from app.services.kite_engine.service import _dte_from_expiry  # lazy: cycle
        g = black_scholes_greeks(spot=float(spot), strike=float(strike),
                                 dte_days=_dte_from_expiry(expiry), iv=_IV_ASSUMPTION,
                                 option_type="CE" if is_call else "PE")
        delta = float(g.delta)
    except Exception as exc:  # noqa: BLE001
        log.debug("protection: delta translation unavailable for %s: %s", option_type, exc)
        delta = 0.0
    # A signed ±0.5 fallback keeps the translation producing a stop on the correct side
    # rather than switching it off entirely (which 0.0 does).
    return delta if delta != 0.0 else (0.5 if is_call else -0.5)


def plan_for_symbol(uid: str, option_symbol: str) -> Optional[LegPlan]:
    """The plan the board is displaying for ``option_symbol``, or None.

    The stop is the leg's CURRENT trail (`premium_sl`) — the number under the
    board's TSL column — falling back to the stop it was armed with at the signal
    (`entry_sl`). Using the current trail means a hand-placed entry is protected at
    the same level the engine would be enforcing for its own position in that
    contract, which is the only level that is defensible to the user: it is the one
    they were looking at when they pressed Buy.

    A LIVE leg wins over a stale one. The same contract can appear on several rows —
    both engines, both scan sources, and rows whose signal has already ENDED (most of
    the board, most of the time). The first match was whichever row happened to be
    ordered first, so a hand-placed entry could be armed at a trail frozen days ago.
    """
    want = (option_symbol or "").strip().upper()
    if not want:
        return None
    fallback: Optional[LegPlan] = None
    for row in _rows_for(uid):
        for leg in (row.legs or []):
            if str(getattr(leg, "option_symbol", "")).upper() != want:
                continue
            stop = float(getattr(leg, "premium_sl", 0.0) or 0.0) or float(getattr(leg, "entry_sl", 0.0) or 0.0)
            spot = float(getattr(row, "underlying_spot", 0.0) or getattr(row, "spot", 0.0) or 0.0)
            plan = LegPlan(
                symbol=str(leg.option_symbol),
                exchange=str(row.exchange or "NFO"),
                token=int(getattr(leg, "token", 0) or 0),
                lot_size=int(getattr(leg, "lot_size", 0) or 0),
                entry_premium=float(getattr(leg, "premium_spot", 0.0) or 0.0),
                stop_premium=stop,
                target_premium=float(getattr(leg, "premium_target", 0.0) or 0.0),
                strike=float(getattr(leg, "strike", 0.0) or 0.0),
                expiry=str(getattr(leg, "expiry", "") or ""),
                underlying=str(row.underlying or ""),
                # A long option is a long option whichever way the underlying signal
                # points: a PE bought on a bearish signal is still long premium, so
                # its stop is on the DOWNSIDE of the premium.
                direction="long",
                source=str(getattr(row, "source", "") or "spot"),
                entry_spot=spot,
                entry_delta=_signed_delta(
                    str(getattr(leg, "option_type", "") or getattr(row, "option_type", "") or "CE"),
                    spot, float(getattr(leg, "strike", 0.0) or 0.0),
                    str(getattr(leg, "expiry", "") or "")),
                live=bool(getattr(leg, "is_active", False)),
            )
            if plan.live:
                return plan
            fallback = fallback or plan
    return fallback


async def stale_stop_reason(client, plan: LegPlan) -> str:
    """"" when ``plan``'s stop is safe to arm, else why it is not.

    A long option's protective stop has to sit BELOW the premium. A plan taken from a
    signal that has already ended carries a trail frozen where the signal died, and the
    premium may have fallen through it since — arming that as a GTT triggers on
    acceptance and market-sells the position the user has just bought. Fails OPEN on a
    missing quote: no answer is not evidence against the board's own number.
    """
    if plan.stop_premium <= 0:
        return ""
    try:
        key = f"{plan.exchange}:{plan.symbol}"
        q = await client.get_ltp([key])
        ltp = float((q or {}).get(key, {}).get("last_price") or 0.0)
    except Exception as exc:  # noqa: BLE001
        log.debug("protection: stop sanity quote unavailable for %s: %s", plan.symbol, exc)
        return ""
    if ltp <= 0 or plan.stop_premium < ltp:
        return ""
    return (f"the board's stop ₹{plan.stop_premium:.2f} is at or above the live premium "
            f"₹{ltp:.2f}"
            + ("" if plan.live else " (that signal has already ended, so its trail is stale)")
            + " — arming it would have sold the position immediately")


@dataclass(frozen=True)
class ArmResult:
    position: positions.OpenPosition
    stop_premium: float
    target_premium: float
    gtt_id: int
    subscribed: bool
    #: True when the trigger at the broker is the PREVIOUS one — it could be neither
    #: cancelled nor retargeted, so it guards the earlier quantity at the earlier
    #: level. It is a real exit, but it is not the stop this call was asked to arm,
    #: and saying "protected" for it would be the display lying again.
    stale_gtt: bool = False

    @property
    def protected(self) -> bool:
        """True when SOMETHING will exit this position AT THIS STOP without the user
        acting. A broker GTT counts; a live tick subscription counts. A stale trigger
        does not — it is armed at a level we did not choose and a quantity that may be
        short of what we hold.
        """
        monitored = self.subscribed and self.stop_premium > 0
        if self.stale_gtt:
            return monitored
        return bool(self.gtt_id) or monitored

    def describe(self) -> str:
        if not self.stop_premium:
            return "no stop — the signal has no premium stop for this contract"
        bits = []
        if self.gtt_id and self.stale_gtt:
            bits.append(f"⚠ broker still holds the EARLIER GTT #{self.gtt_id}, not this stop")
        elif self.gtt_id:
            bits.append(f"broker GTT #{self.gtt_id} @ ₹{self.stop_premium:.2f}")
        if self.target_premium and self.gtt_id and not self.stale_gtt:
            bits.append(f"target ₹{self.target_premium:.2f} (OCO)")
        if self.subscribed:
            bits.append("tick monitor")
        return " + ".join(bits) if bits else f"stop ₹{self.stop_premium:.2f} armed nowhere — check the log"


async def arm_position(
    client, uid: str, *, symbol: str, exchange: str, token: int, qty: int, lot_size: int,
    entry_premium: float, stop_premium: float, order_id: str, stop_mode: str,
    direction: str = "long", vehicle: str = "otm_options", underlying: str = "",
    exit_mode: str = "one_red", guard_key: str = "", entry_spot: float = 0.0,
    entry_delta: float = 0.0, strike: float = 0.0, expiry: str = "",
    target_premium: float = 0.0,
) -> ArmResult:
    """Register a freshly-placed position and arm whatever protection is configured.

    ``stop_mode`` decides where the stop lives: ``broker`` (GTT only), ``monitor``
    (server-side tick exit only), ``both``. A GTT failure under ``both`` is
    survivable because the monitor remains; under ``broker`` it is reported, since
    nothing else is watching.

    ``qty`` is THIS order's quantity. If the symbol is already held, the position is
    treated as a scale-in: the registry row carries the total, the broker stop is
    armed for the total, and the hold clock keeps running from the first entry.

    Never raises: an order is already live at this point, so a failure here must be
    logged and reported, not thrown at a caller that can no longer undo the trade.
    """
    # ── never leave a previous GTT for this symbol armed ──────────────────────
    # `positions.register` overwrites by symbol, so re-entering a contract we already
    # have a registry row for would drop the old `gtt_id` and arm a SECOND trigger for
    # the same position. Both would eventually fire against one long — two SELLs, net
    # short. Cancel the old one first; this is the only place positions are created,
    # so this is the only place that can happen.
    #
    # Cancelling is not the same as having cancelled, though: when it cannot be
    # confirmed, the old trigger may still be resting, and placing a new one anyway is
    # exactly the double-SELL this block exists to prevent. So ask the broker, and when
    # the old trigger is (or may be) still there, RETARGET it instead of adding a rival.
    prior = positions.get(uid, symbol)
    prior_live = prior is not None and prior.status in (positions.PENDING, positions.OPEN)
    prior_gtt = int(getattr(prior, "gtt_id", 0) or 0) if prior is not None else 0
    carry_gtt = 0
    if prior_gtt:
        outcome = await protective_stop.cancel_stop_result(client, prior_gtt)
        if outcome != protective_stop.CANCELLED:
            status = await protective_stop.stop_status(
                client, prior_gtt, tradingsymbol=symbol,
                direction=getattr(prior, "direction", "long"))
            if status in (protective_stop.STOP_ACTIVE, protective_stop.STOP_UNVERIFIED):
                carry_gtt = prior_gtt
        state.log(uid, "info",
                  f"{symbol}: previous protective GTT #{prior_gtt} {outcome} before re-arming")

    # ── a second buy of a contract we already hold is a SCALE-IN ───────────────
    # We end up holding the SUM, and `qty` is what the broker stop, the monitor's exit
    # SELL and the realized PnL are all computed from. Registering only this order's
    # quantity would leave the earlier lot with nothing on it.
    prior_qty = int(prior.qty or 0) if prior_live and prior is not None else 0
    total_qty = int(qty) + prior_qty
    qty_by_order = dict(getattr(prior, "qty_by_order", {}) or {}) if prior_live else {}
    if prior_qty and not qty_by_order and prior is not None:
        # The prior row carries no per-order breakdown (it predates this field, or came
        # from the auto-exec path). Seed it with the lot it represents — otherwise the
        # next fill postback would re-total from a map holding only the NEW order and
        # silently forget the earlier lot, which is the very loss this is preventing.
        qty_by_order[str(prior.order_id or f"prior:{symbol}")] = prior_qty
    if order_id:
        qty_by_order[str(order_id)] = int(qty)
    if prior_qty and prior is not None:
        prior_px = float(prior.fill_price or prior.entry_premium or 0.0)
        if prior_px > 0 and entry_premium > 0 and total_qty > 0:
            # Weighted average, so realized PnL is booked against what the holding
            # actually cost rather than against the latest lot's price.
            entry_premium = (prior_px * prior_qty + float(entry_premium) * int(qty)) / total_qty

    p = positions.register(positions.OpenPosition(
        uid=uid, symbol=symbol, exchange=exchange, token=token, qty=total_qty, lot_size=lot_size,
        entry_premium=entry_premium, stop_premium=stop_premium, order_id=order_id,
        status=positions.PENDING, stop_mode=stop_mode, guard_key=guard_key,
        direction=direction, vehicle=vehicle, underlying=underlying, exit_mode=exit_mode,
        entry_spot=entry_spot, entry_delta=entry_delta, strike=strike, expiry=expiry,
        initial_stop_premium=stop_premium, target_premium=target_premium,
        qty_by_order=qty_by_order,
        # Adding a lot must not restart the hold clock — the time stop and the expiry
        # square-off have to keep counting from the FIRST entry.
        **({"opened_ms": int(prior.opened_ms)} if prior_live and prior is not None
           and prior.opened_ms else {})))

    subscribed = False
    if token and stop_mode in ("monitor", "both"):
        try:
            from app.services.exchanges.kite import constants as K, ticker_manager
            await ticker_manager.subscribe(uid, [token], mode=K.MODE_LTP)
            subscribed = True
            state.log(uid, "info", f"Subscribed token {token} ({symbol}) to tick monitor")
        except Exception as exc:  # noqa: BLE001
            log.debug("kite monitor auto-subscribe failed for %s: %s", uid, exc)

    gtt_id, stale_gtt = 0, False
    if stop_mode in ("broker", "both") and stop_premium > 0:
        target_note = f" / target ₹{target_premium:.2f}" if target_premium else ""
        if carry_gtt:
            # The old trigger is, or may still be, the live one at the broker. A MODIFY
            # rewrites it whole — new stop, new total quantity, target and all — so one
            # resting SELL covers the whole holding and there is never a moment with two.
            moved = await protective_stop.move_stop(
                client, trigger_id=carry_gtt, tradingsymbol=symbol, exchange=exchange,
                qty=total_qty, trigger_premium=stop_premium, last_price=entry_premium,
                direction=direction, target_premium=target_premium)
            gtt_id, stale_gtt = carry_gtt, not moved  # the trigger of record either way
            positions.update_stop(uid, symbol, stop_premium, gtt_id=gtt_id)
            if moved:
                state.log(uid, "info",
                          f"Protective GTT #{gtt_id} retargeted for {symbol}: {total_qty} qty "
                          f"@ ₹{stop_premium:.2f}{target_note}")
            else:
                state.log(uid, "order_failed",
                          f"⚠ {symbol}: GTT #{gtt_id} could be neither cancelled nor retargeted. "
                          f"NOT arming a second trigger (two would both sell and leave you "
                          f"short) — the stop at Zerodha is the OLD one"
                          + (" and the tick monitor guards the rest." if subscribed
                             else ", and nothing else is guarding this position. Check Zerodha now."))
        else:
            gtt_id = await protective_stop.place_stop(
                client, tradingsymbol=symbol, exchange=exchange, qty=total_qty,
                trigger_premium=stop_premium, last_price=entry_premium,
                direction=direction, target_premium=target_premium) or 0
            if gtt_id:
                positions.update_stop(uid, symbol, stop_premium, gtt_id=gtt_id)
                state.log(uid, "info",
                          f"Protective GTT #{gtt_id} placed for {symbol} @ ₹{stop_premium:.2f}{target_note}")
            elif stop_mode == "broker":
                state.log(uid, "info",
                          f"⚠ Protective GTT failed for {symbol}; no broker stop "
                          f"(enable monitor mode for a server-side backstop)")

    return ArmResult(position=p, stop_premium=stop_premium,
                     target_premium=target_premium if gtt_id else 0.0,
                     gtt_id=gtt_id, subscribed=subscribed, stale_gtt=stale_gtt)


__all__ = ["LegPlan", "ArmResult", "arm_position", "plan_for_symbol", "stale_stop_reason"]
