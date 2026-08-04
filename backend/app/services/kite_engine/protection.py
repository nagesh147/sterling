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
    #: Underlying spot and |delta| at the signal, needed to re-translate the
    #: underlying trail into a premium stop on later scans.
    entry_spot: float
    entry_delta: float

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


def plan_for_symbol(uid: str, option_symbol: str) -> Optional[LegPlan]:
    """The plan the board is displaying for ``option_symbol``, or None.

    The stop is the leg's CURRENT trail (`premium_sl`) — the number under the
    board's TSL column — falling back to the stop it was armed with at the signal
    (`entry_sl`). Using the current trail means a hand-placed entry is protected at
    the same level the engine would be enforcing for its own position in that
    contract, which is the only level that is defensible to the user: it is the one
    they were looking at when they pressed Buy.
    """
    want = (option_symbol or "").strip().upper()
    if not want:
        return None
    for row in _rows_for(uid):
        for leg in (row.legs or []):
            if str(getattr(leg, "option_symbol", "")).upper() != want:
                continue
            stop = float(getattr(leg, "premium_sl", 0.0) or 0.0) or float(getattr(leg, "entry_sl", 0.0) or 0.0)
            return LegPlan(
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
                entry_spot=float(getattr(row, "underlying_spot", 0.0) or getattr(row, "spot", 0.0) or 0.0),
                entry_delta=abs(float(getattr(leg, "delta", 0.0) or 0.0)),
            )
    return None


@dataclass(frozen=True)
class ArmResult:
    position: positions.OpenPosition
    stop_premium: float
    target_premium: float
    gtt_id: int
    subscribed: bool

    @property
    def protected(self) -> bool:
        """True when SOMETHING will exit this position without the user acting.

        A broker GTT counts; a live tick subscription counts. Neither means the
        board must not display a stop for it.
        """
        return bool(self.gtt_id) or (self.subscribed and self.stop_premium > 0)

    def describe(self) -> str:
        if not self.stop_premium:
            return "no stop — the signal has no premium stop for this contract"
        bits = []
        if self.gtt_id:
            bits.append(f"broker GTT #{self.gtt_id} @ ₹{self.stop_premium:.2f}")
        if self.target_premium and self.gtt_id:
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

    Never raises: an order is already live at this point, so a failure here must be
    logged and reported, not thrown at a caller that can no longer undo the trade.
    """
    # ── never leave a previous GTT for this symbol armed ──────────────────────
    # `positions.register` overwrites by symbol, so re-entering a contract we already
    # have a registry row for would drop the old `gtt_id` and arm a SECOND trigger for
    # the same position. Both would eventually fire against one long — two SELLs, net
    # short. Cancel the old one first; this is the only place positions are created,
    # so this is the only place that can happen.
    prior = positions.get(uid, symbol)
    if prior is not None and prior.gtt_id:
        outcome = await protective_stop.cancel_stop_result(client, prior.gtt_id)
        state.log(uid, "info",
                  f"{symbol}: previous protective GTT #{prior.gtt_id} {outcome} before re-arming")

    p = positions.register(positions.OpenPosition(
        uid=uid, symbol=symbol, exchange=exchange, token=token, qty=qty, lot_size=lot_size,
        entry_premium=entry_premium, stop_premium=stop_premium, order_id=order_id,
        status=positions.PENDING, stop_mode=stop_mode, guard_key=guard_key,
        direction=direction, vehicle=vehicle, underlying=underlying, exit_mode=exit_mode,
        entry_spot=entry_spot, entry_delta=entry_delta, strike=strike, expiry=expiry,
        initial_stop_premium=stop_premium, target_premium=target_premium))

    subscribed = False
    if token and stop_mode in ("monitor", "both"):
        try:
            from app.services.exchanges.kite import constants as K, ticker_manager
            await ticker_manager.subscribe(uid, [token], mode=K.MODE_LTP)
            subscribed = True
            state.log(uid, "info", f"Subscribed token {token} ({symbol}) to tick monitor")
        except Exception as exc:  # noqa: BLE001
            log.debug("kite monitor auto-subscribe failed for %s: %s", uid, exc)

    gtt_id = 0
    if stop_mode in ("broker", "both") and stop_premium > 0:
        gtt_id = await protective_stop.place_stop(
            client, tradingsymbol=symbol, exchange=exchange, qty=qty,
            trigger_premium=stop_premium, last_price=entry_premium,
            direction=direction, target_premium=target_premium) or 0
        if gtt_id:
            positions.update_stop(uid, symbol, stop_premium, gtt_id=gtt_id)
            target_note = f" / target ₹{target_premium:.2f}" if target_premium else ""
            state.log(uid, "info",
                      f"Protective GTT #{gtt_id} placed for {symbol} @ ₹{stop_premium:.2f}{target_note}")
        elif stop_mode == "broker":
            state.log(uid, "info",
                      f"⚠ Protective GTT failed for {symbol}; no broker stop "
                      f"(enable monitor mode for a server-side backstop)")

    return ArmResult(position=p, stop_premium=stop_premium,
                     target_premium=target_premium if gtt_id else 0.0,
                     gtt_id=gtt_id, subscribed=subscribed)


__all__ = ["LegPlan", "ArmResult", "arm_position", "plan_for_symbol"]
