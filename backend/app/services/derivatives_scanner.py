"""Derivatives scanner + auto-executor — extracted from main.py so the
unit tests can drive the auto-exec path without booting the full ASGI
lifespan (which transitively imports asyncpg, telegram bot, etc.).

Two public surfaces:

  • `auto_execute_derivative(app, *, freeze_token, row_strategy,
     row_underlying, leg)` — consume one freeze_token and submit it via
     `place_live_order`. Single-fire by construction (consume is one-shot).
  • `run_scanner_tick(app)` — the body of one scanner pulse: collect
     armed signals, run `_decide_both` per signal, cache rows, and
     auto-fire when `algo_mode` + per-strategy `auto_execute_<leg>` are
     both ON.

The main.py background task is a thin loop around `run_scanner_tick`.
This separation lets the tests assert against the contracts here
without dragging in DB / network plumbing.
"""
from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)


# Per-(strategy, sym, instrument_type) cooldown tracker — keyed
# "{strategy}|{sym}|{inst}" → ts_ms; prevents back-to-back auto-fires on
# the same selector pulse for the same instrument leg.
_deriv_last_ordered: dict[str, int] = {}


def deriv_cooldown_ms() -> int:
    """Derivatives auto-execute cooldown. Independent of the per-symbol
    futures cooldown so derivatives auto-fires don't share a token with
    the legacy ALGO path. 15 min default."""
    return 15 * 60 * 1000


def clear_cooldowns_for_tests() -> None:
    """Wipe the cooldown tracker — for test fixtures only."""
    _deriv_last_ordered.clear()


class _ReqProxy:
    """Minimal Starlette-Request-like wrapper. The selector signal
    collector + place_live_order only read .app and .state, so this is
    sufficient."""

    def __init__(self, app: Any):
        self.app = app
        self.state = app.state


async def auto_execute_derivative(
    app: Any, *, freeze_token: str, row_strategy: str,
    row_underlying: str, leg: str,
) -> bool:
    """Consume the freeze_token and submit via place_live_order.

    Returns True iff the order was accepted (status not in
    {"rejected","error"}). Returns False on stale token, missing
    candidate, or place_live_order raising / returning a rejection.

    The freeze_token is single-fire: a second call with the same token
    will return False even if the first call succeeded.
    """
    # The Delta order path went with the crypto product surface, and this
    # function is only reached when scalp_mode is on — the crypto kill
    # switch, which no longer has a control. Refuse rather than raise
    # ImportError from a module that is gone.
    log.warning(
        "DERIV auto-exec %s/%s/%s: no broker order path in this build; skipping.",
        row_strategy, row_underlying, leg,
    )
    return False
    from app.engines.derivatives.freeze_token import get_store

    store = get_store()
    decision = store.consume(freeze_token)
    if decision is None:
        log.debug(
            "DERIV auto-exec %s/%s/%s: token stale/already consumed",
            row_strategy, row_underlying, leg,
        )
        return False
    cand = decision.chosen
    if cand is None:
        return False

    order = LiveOrderRequest(
        underlying=cand.underlying, direction=cand.direction,
        instrument_type=cand.instrument_type,
        size=float(cand.contracts), leverage=float(cand.leverage),
        order_type="market",
        stop_loss=cand.stop_loss, take_profit=cand.take_profit,
        option_symbol=cand.option_symbol,
        delta=cand.delta,
        gamma=cand.gamma,
        theta=cand.theta,
        vega=cand.vega,
        projected_theta_burn_usd=cand.projected_theta_burn_usd,
        liquidity=cand.liquidity.composite if cand.liquidity else None,
        expected_r=cand.expected_r,
        dte=cand.dte,
        notes=(
            f"[AUTO][DERIV-{leg.upper()}] {row_strategy} "
            f"freeze={freeze_token[:8]} R={cand.expected_r:.2f}"
        ),
    )

    try:
        resp = await place_live_order(order, _ReqProxy(app))
    except Exception as exc:
        log.warning(
            "DERIV auto-exec %s/%s/%s: place_live_order raised: %s",
            row_strategy, row_underlying, leg, exc,
        )
        return False

    accepted = resp.status not in ("rejected", "error")
    log.info(
        "DERIV AUTO-EXEC %s [%s] %s/%s/%s lev=%s size=%s → %s (%s)",
        "OK" if accepted else "REJ",
        resp.mode, row_strategy, row_underlying, leg,
        cand.leverage, cand.contracts, resp.status, resp.message,
    )
    return accepted


async def run_scanner_tick(app: Any, interval_s: int = 30) -> dict:
    """Run one scanner pulse: collect → decide_both per signal → cache
    → auto-fire when gated. Returns the cache snapshot for inspection.

    Sets `app.state.derivatives_scan_cache` with the latest snapshot.
    """
    from app.engines.derivatives.profiles import get_profile
    from app.api.v1.endpoints import derivatives as _deriv_ep

    log.info("DERIV scanner tick starting")
    try:
        futures_rows, options_rows, ts_ms = await _deriv_ep._both_rows(
            _ReqProxy(app), strategy_filter=None, underlying_filter=None,
        )
    except Exception as exc:
        import traceback
        log.warning("DERIV scanner _both_rows crashed: %s\n%s", exc, traceback.format_exc())
        futures_rows, options_rows, ts_ms = [], [], 0

    attempts = 0
    accepted = 0
    algo_on = bool(getattr(app.state, "algo_mode", False))
    scalp_on = bool(getattr(app.state, "scalp_mode", False))
    log.info(f"DERIV scanner tick: algo_on={algo_on} scalp_on={scalp_on}")
    if algo_on and scalp_on:
        overrides = _deriv_ep._profile_overrides(app)
        for rows, leg in ((futures_rows, "futures"), (options_rows, "options")):
            for row in rows:
                prof = overrides.get(row.strategy) or get_profile(row.strategy)
                flag_attr = f"auto_execute_{leg}"
                
                # Granular logging for investigation
                auto_exec_flag = getattr(prof, flag_attr, False)
                log.info(f"DERIV scanner checking {row.strategy}/{row.underlying}/{leg}: {flag_attr}={auto_exec_flag}, token={row.freeze_token}")
                
                if not auto_exec_flag:
                    continue
                key = f"{row.strategy}|{row.underlying}|{leg}"
                now_ms = int(time.time() * 1000)
                cooldown_elapsed = now_ms - _deriv_last_ordered.get(key, 0)
                if cooldown_elapsed < deriv_cooldown_ms():
                    log.debug(f"DERIV scanner skipped {key} due to cooldown ({cooldown_elapsed}ms < {deriv_cooldown_ms()}ms)")
                    continue
                _deriv_last_ordered[key] = now_ms
                attempts += 1
                try:
                    ok = await auto_execute_derivative(
                        app, freeze_token=row.freeze_token,
                        row_strategy=row.strategy,
                        row_underlying=row.underlying, leg=leg,
                    )
                    if ok:
                        accepted += 1
                except Exception as exc:
                    log.warning(
                        "DERIV auto-exec crashed %s/%s/%s: %s",
                        row.strategy, row.underlying, leg, exc,
                    )

    cache = {
        "futures": [r.model_dump() for r in futures_rows],
        "options": [r.model_dump() for r in options_rows],
        "last_scan_ms": ts_ms,
        "next_scan_ms": ts_ms + interval_s * 1000,
        "auto_exec_attempts": attempts,
        "auto_exec_accepted": accepted,
    }
    app.state.derivatives_scan_cache = cache
    if attempts:
        log.info(
            "DERIV scanner: %d futures + %d options rows, auto-exec %d/%d accepted",
            len(futures_rows), len(options_rows), accepted, attempts,
        )
    return cache
