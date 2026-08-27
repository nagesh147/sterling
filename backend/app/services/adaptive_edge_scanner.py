"""Candidate discovery for Adaptive Edge.

A three-stage funnel, for the same reason the Gamma Move scanner has one: the
historical endpoint is rate-limited to roughly three requests a second, so the
expensive per-contract work has to run on a list that liquidity and the expiry
window have already cut down.

    underlyings  ->  eligible contracts  ->  scored candidates

Stage 1 and 2 cost one chain read per underlying. Only stage 3 pulls candles,
and only for contracts that survived.

Everything here is causal: at bar *i* a feature may use bars at or before *i*
and nothing after. That is §3 of the Master Specification, and it is the one
property that cannot be recovered by testing later — a lookahead feature
produces a backtest that is simply a different, better strategy than the one
that would have traded.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.adaptive_edge import AdaptiveEdgeConfig
from app.engines.adaptive_edge.f103_opportunity import (
    OpportunityAction,
    OpportunityCandidate,
    evaluate_opportunity,
)
from app.engines.adaptive_edge.f109_option_selection import F109Candidate, select_f109
from app.engines.adaptive_edge.implied_vol import read as read_implied
from app.engines.adaptive_edge.volatility_forecast import evaluate_straddle, forecast
from app.engines.adaptive_edge.volatility_harvest import evaluate as price_harvest
from app.services.adaptive_edge import ist_today, nfo_dump, underlyings
from app.services.adaptive_edge_strategy import (
    MIN_BARS,
    decide_from_candles,
    fetch_bars,
)
from app.services.kite_engine.strikes import (
    chain_rows_for,
    expiry_window_of,
    in_expiry_window,
)

log = get_logger(__name__)

#: Minimum spacing between historical requests. A token bucket cannot hold a
#: 3 rq/s limit — it lets a burst through and then the API rejects the tail —
#: so pace on minimum spacing instead. This repository has already learned that
#: once, in the kitelake acquisition path.
_MIN_REQUEST_SPACING_S = 0.34


class Pacer:
    """Minimum-spacing pacer. Not a token bucket, deliberately."""

    def __init__(self, spacing: float = _MIN_REQUEST_SPACING_S) -> None:
        self._spacing = spacing
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._spacing - (now - self._last)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def listed_contracts(
    chain: list[dict],
    cfg: AdaptiveEdgeConfig,
    *,
    spot: float,
) -> list[dict]:
    """Stage 2a: which *listed* contracts this config would consider.

    Structural only — expiry window and strike window. These come from the
    instrument dump, so they cost nothing per contract and cut the list before
    anything has to be quoted.

    ``chain_rows_for`` supplies ``dte``; a row without it is rejected rather
    than defaulted. Defaulting a missing ``dte`` to 0 combines with
    ``avoid_expiry_day`` to drop every contract, which looks exactly like a
    strategy that found no setup — the failure this codebase keeps rediscovering.
    """
    if spot <= 0:
        return []
    window = expiry_window_of(cfg)
    lo = spot * (1.0 - cfg.strike_window_pct / 100.0)
    hi = spot * (1.0 + cfg.strike_window_pct / 100.0)

    out: list[dict] = []
    for row in chain:
        if "dte" not in row:
            continue
        if not in_expiry_window(row, **window):
            continue
        strike = _num(row.get("strike"))
        if not (lo <= strike <= hi):
            continue
        out.append(row)

    out.sort(key=lambda r: (abs(_num(r.get("strike")) - spot), int(r.get("dte", 0))))
    return out[: cfg.max_candidates]


def tradeable_contracts(
    rows: list[dict],
    quotes: dict[str, dict],
    cfg: AdaptiveEdgeConfig,
    *,
    spot: float,
) -> tuple[list[dict], dict[str, int]]:
    """Stage 2b: of those, which can actually be traded right now.

    Needs live quotes, so it runs only on what stage 2a left. Returns the
    survivors and a tally of why the rest were dropped — an operator looking at
    an empty board needs to tell "all too wide" from "all too illiquid".
    """
    kept: list[dict] = []
    dropped: dict[str, int] = {}

    def drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    for row in rows:
        symbol = str(row.get("instrument_name") or "")
        quote = quotes.get(f"NFO:{symbol}") or quotes.get(symbol) or {}
        if not quote:
            drop("no quote")
            continue
        last = _num(quote.get("last_price"))
        oi = _num(quote.get("oi"))
        volume = _num(quote.get("volume"))
        depth = quote.get("depth") or {}
        bids = depth.get("buy") or []
        asks = depth.get("sell") or []
        bid = _num(bids[0].get("price")) if bids else 0.0
        ask = _num(asks[0].get("price")) if asks else 0.0

        if oi < cfg.min_option_oi:
            drop("open interest below floor")
            continue
        if volume < cfg.min_option_volume:
            drop("volume below floor")
            continue
        # Below this the tick is a large fraction of the premium, so any
        # premium-change feature measures the tick grid, not the market.
        if last < cfg.min_option_premium:
            drop("premium below floor")
            continue
        if bid > 0 and ask > 0:
            mid = (bid + ask) / 2.0
            if mid > 0 and ((ask - bid) / mid) * 100.0 > cfg.max_spread_pct:
                drop("spread too wide")
                continue

        kept.append(
            {
                "symbol": symbol,
                "token": int(_num(row.get("token"))),
                "strike": _num(row.get("strike")),
                "option_type": "CE" if str(row.get("option_type")) == "call" else "PE",
                "expiry": str(row.get("expiry_date") or ""),
                "dte": int(row.get("dte", 0)),
                "lot_size": int(_num(row.get("lot_size"))),
                "last_price": last,
                "oi": oi,
                "volume": volume,
                "bid": bid,
                "ask": ask,
                "spot": spot,
            }
        )
    return kept, dropped




def _f103_eligibility(row: dict, decision_direction: str, expected_ev: float | None,
                      conservative_ev: float | None):
    """F-103, the candidate eligibility boundary, run for real.

    The same conjunction F-110 applies at entry, applied here at the candidate
    stage — §30 rather than §35. Both belong: a candidate that cannot clear the
    boundary should not become a trade candidate at all, and the final gate is
    still checked before anything is armed.

    It refuses on the same term F-110 does. `conservative_expected_value` is
    LowerConfidenceBound(EV) and the model that would bound it has no
    directional signal (see docs/strategy/adaptive-edge/F102_CALIBRATION_RESULT.md),
    so it is passed absent and the reason comes from the formula rather than
    from prose written here.
    """
    action = (OpportunityAction.BUY_CE if decision_direction == "BULLISH"
              else OpportunityAction.BUY_PE if decision_direction == "BEARISH"
              else OpportunityAction.NO_TRADE)
    return evaluate_opportunity(OpportunityCandidate(
        action=action,
        data_ok=True,
        directional_edge_ok=action is not OpportunityAction.NO_TRADE,
        expected_value=expected_ev,
        conservative_expected_value=conservative_ev,
        # Already applied in reaching this list: OI and volume floors, the spread
        # ceiling, the strike and expiry windows.
        liquidity_ok=True,
        slippage_ok=True,
        risk_ok=True,
    ))


def rank_contracts(rows: list[dict], cfg: AdaptiveEdgeConfig,
                   *, expected_ev: float | None) -> list[dict]:
    """Order contracts by F-109, the canonical selector, when it can decide.

    F-109 picks the eligible candidate with maximum ExpectedNetEV under
    liquidity, slippage, risk and data-quality constraints, and fails closed on
    a missing input. Expected value per contract needs the probability model, so
    today it returns nothing and the fallback ordering applies — open interest
    first, then distance from spot, which is a liquidity heuristic and is
    labelled as one rather than dressed up as the formula.

    Contracts are still returned when F-109 declines, because they are what the
    observation recorder needs. Being surfaced is not being armable; the entry
    gate decides that.
    """
    if expected_ev is not None:
        candidates = [
            F109Candidate(
                option_symbol=str(r.get("symbol") or ""),
                option_type=str(r.get("option_type") or ""),
                strike=_num(r.get("strike")),
                moneyness="ATM",
                expected_gross_ev=expected_ev,
                execution_cost=max(0.0, (_num(r.get("ask")) - _num(r.get("bid"))) / 2.0),
                risk=_num(r.get("last_price")) * max(1, int(_num(r.get("lot_size")))),
                liquidity=_num(r.get("oi")),
                expected_slippage=max(0.0, (_num(r.get("ask")) - _num(r.get("bid"))) / 2.0),
                data_quality=1.0,
                required_liquidity=float(cfg.min_option_oi),
                allowable_slippage=_num(r.get("last_price")) * cfg.max_spread_pct / 100.0,
                max_risk=float(cfg.max_daily_loss) if cfg.max_daily_loss > 0 else float("inf"),
                required_data_quality=cfg.min_chain_completeness,
            )
            for r in rows
        ]
        chosen = select_f109(candidates)
        if chosen is not None:
            head = [r for r in rows if str(r.get("symbol")) == chosen.option_symbol]
            return head + [r for r in rows if str(r.get("symbol")) != chosen.option_symbol]

    # Liquidity heuristic, not F-109. Named so nobody reads it as the formula.
    return sorted(rows, key=lambda r: (-_num(r.get("oi")), abs(_num(r.get("strike")) - _num(r.get("spot")))))




def atm_pair(rows: list[dict], spot: float) -> tuple[dict | None, dict | None]:
    """The call and put nearest the money, at a single shared strike.

    A straddle whose legs sit at different strikes is a strangle with different
    economics, so the strike is chosen once and both legs are taken from it or
    neither is.
    """
    if spot <= 0 or not rows:
        return None, None
    by_strike: dict[float, dict[str, dict]] = {}
    for row in rows:
        by_strike.setdefault(_num(row.get("strike")), {})[str(row.get("option_type"))] = row
    for strike in sorted(by_strike, key=lambda s: abs(s - spot)):
        legs = by_strike[strike]
        if "CE" in legs and "PE" in legs:
            return legs["CE"], legs["PE"]
    return None, None


def minutes_to_expiry(row: dict, now: datetime) -> float:
    """Trading minutes left in a contract.

    Days-to-expiry alone is too coarse: an option expiring today has between 375
    and zero minutes left depending on the clock, and implied volatility read off
    the wrong figure is wrong by the square root of the error.
    """
    dte = int(_num(row.get("dte")))
    minutes_left_today = max(0.0, (15 * 60 + 30) - (now.hour * 60 + now.minute))
    return max(1.0, dte * 375.0 + min(minutes_left_today, 375.0))


def volatility_reading(name: str, rows: list[dict], closes: list[float],
                       cfg: AdaptiveEdgeConfig, *, spot: float,
                       now: Optional[datetime] = None) -> dict | None:
    """What the market charges for movement, against what the tape delivers.

    This is the fact every offline study of this strategy was missing. It is not
    derivable from any store here — no option price history exists — and it is
    trivially available live, which is why the engine measures it every scan
    whether or not it intends to trade.

    Returns both sides plus a defined-risk structure priced at the *measured*
    ratio rather than an assumed one. Whether that structure may be armed is not
    decided here; the evidence gate decides it from the accumulated record.
    """
    now = now or datetime.now(_IST)
    view = forecast(closes, horizon_bars=cfg.horizon_bars)
    if view is None:
        return None
    call, put = atm_pair(rows, spot)
    if call is None or put is None:
        return None

    expiry_minutes = minutes_to_expiry(call, now)
    reading = read_implied(
        call_premium=_num(call.get("last_price")),
        put_premium=_num(put.get("last_price")),
        spot=spot,
        strike=_num(call.get("strike")),
        minutes_to_expiry=expiry_minutes,
        realised_vol_bps_per_minute=view.realised_vol_bps,
    )
    if reading is None:
        return None

    structure = price_harvest(closes, implied_vol_ratio=reading.ratio,
                              horizon_bars=cfg.horizon_bars)
    return {
        "underlying": name,
        "strike": _num(call.get("strike")),
        "expiry": str(call.get("expiry") or ""),
        "call": call.get("symbol"),
        "put": put.get("symbol"),
        "lot_size": int(_num(call.get("lot_size"))),
        "spot": spot,
        "minutes_to_expiry": round(expiry_minutes, 1),
        # The measurement, which is the point of running at all.
        "implied_vol": round(reading.implied_vol, 5),
        "realised_vol": round(reading.realised_vol, 5),
        "implied_ratio": round(reading.ratio, 4),
        "premium_rich": reading.premium_rich,
        "straddle_bps": round(reading.straddle_bps, 2),
        "forecast_bps": round(view.excursion_bps, 2),
        "vol_percentile": view.percentile,
        # The structure, priced at the measured ratio. Arming is the gate's call.
        "credit_bps": round(structure.net_credit_bps, 2) if structure else None,
        "max_loss_bps": round(structure.max_loss_bps, 2) if structure else None,
        "structure_eligible": bool(structure and structure.eligible),
        "structure_reason": structure.reason if structure else "not priceable",
    }


def straddle_signal(name: str, rows: list[dict], closes: list[float], cfg: AdaptiveEdgeConfig,
                    *, spot: float) -> dict | None:
    """The engine's actual trade decision: is movement cheaper than it is likely?

    Long gamma, no direction. Direction was measured and abandoned — momentum,
    mean reversion and opening-range breakout all failed to hold out of sample
    once fills moved to the next bar's open. Magnitude survived, so this trades
    magnitude.

    Returns None rather than an ineligible signal when the straddle cannot be
    priced or the tape is too short to forecast, because those are the engine
    being unable to ask rather than the answer being no.
    """
    view = forecast(closes, horizon_bars=cfg.horizon_bars)
    if view is None:
        return None
    call, put = atm_pair(rows, spot)
    if call is None or put is None:
        return None

    gate = evaluate_straddle(
        forecast_bps=view.excursion_bps,
        call_premium=_num(call.get("last_price")),
        put_premium=_num(put.get("last_price")),
        spot=spot,
        round_trip_cost_pct=cfg.fee_rate * 100.0 + cfg.slippage_bps / 100.0,
    )
    premium = _num(call.get("last_price")) + _num(put.get("last_price"))
    return {
        "underlying": name,
        "structure": "STRADDLE",
        "strike": _num(call.get("strike")),
        "expiry": str(call.get("expiry") or ""),
        "call": call.get("symbol"),
        "put": put.get("symbol"),
        "call_token": call.get("token"),
        "put_token": put.get("token"),
        "lot_size": int(_num(call.get("lot_size"))),
        "spot": spot,
        "premium": premium,
        "forecast_bps": round(view.excursion_bps, 2),
        "breakeven_bps": round(gate.breakeven_bps, 2),
        "edge_ratio": round(gate.edge_ratio, 3),
        "realised_vol_bps": round(view.realised_vol_bps, 3),
        "vol_percentile": view.percentile,
        "entry_ok": gate.eligible,
        "reason": gate.reason,
    }


async def scan(uid: str, cfg: AdaptiveEdgeConfig) -> dict[str, Any]:
    """Run the funnel and return what each stage produced.

    Counts as well as candidates, so an empty board distinguishes "nothing
    passed the trigger" from "the universe was empty" from "every contract was
    outside the expiry window" — three different problems that all render as no
    rows.
    """
    started = time.monotonic()
    names = underlyings(cfg)
    today = ist_today()

    state: dict[str, Any] = {
        "underlyings": len(names),
        "chains_read": 0,
        "listed": 0,
        "tradeable": 0,
        "candidates": [],
        "decisions": [],
        "volatility": [],
        "skipped": {},
        "dropped": {},
        "errors": [],
    }
    if not names:
        state["errors"].append("no underlyings selected")
        return state

    try:
        dump = await nfo_dump(uid)
    except Exception as exc:                                       # noqa: BLE001
        state["errors"].append(f"instrument dump unavailable: {exc}")
        return state

    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if acct is None:
        state["errors"].append("no active Kite account")
        return state
    client = await accounts.acquire_client(acct)

    pacer = Pacer()
    candidates: list[dict] = []

    for name in names:
        try:
            rows = chain_rows_for(dump, name, today)
            if not rows:
                state["skipped"][name] = "no listed contracts"
                continue
            state["chains_read"] += 1

            await pacer.wait()
            spot_key = f"NSE:{name} 50" if name == "NIFTY" else f"NSE:{name}"
            spot = 0.0
            spot_token = 0
            try:
                quotes = await client.quote([spot_key])
                spot = _num((quotes or {}).get(spot_key, {}).get("last_price"))
                spot_token = int(_num((quotes or {}).get(spot_key, {}).get("instrument_token")))
            except Exception as exc:                               # noqa: BLE001
                state["skipped"][name] = f"spot unavailable: {exc}"
                continue
            if spot <= 0:
                state["skipped"][name] = "spot unavailable"
                continue

            listed = listed_contracts(rows, cfg, spot=spot)
            state["listed"] += len(listed)
            if not listed:
                state["skipped"][name] = "no contract inside the expiry and strike windows"
                continue

            # The canonical pipeline decides direction and economics. Ask it
            # before quoting a chain: a NEUTRAL underlying needs no quotes, and
            # a direction halves the contracts worth pricing.
            expiry = str(listed[0].get("expiry_date") or "")
            token = int(_num(next((r.get("token") for r in rows if r.get("token")), 0)))
            decision = None
            try:
                await pacer.wait()
                candles = await fetch_bars(client, spot_token or token,
                                           interval=cfg.decision_timeframe,
                                           lookback_bars=cfg.feature_lookback_bars)
                if len(candles) < MIN_BARS:
                    state["skipped"][name] = (
                        f"only {len(candles)} bars of history; the pipeline needs "
                        f"{MIN_BARS} before a decision means anything")
                    continue
                decision = decide_from_candles(name, candles, cfg, expiry=expiry, spot=spot)
                candles_closes = [float(c.get("close") or 0.0) for c in candles]
            except Exception as exc:                               # noqa: BLE001
                state["errors"].append(f"{name}: history unavailable: {exc}")
                continue

            if decision is None:
                state["skipped"][name] = "pipeline returned no decision"
                continue

            state["decisions"].append({
                "underlying": name, "direction": decision.direction,
                "horizon": decision.horizon, "reason": decision.reason,
                "eligible": decision.eligible,
                "expected_net_value": decision.expected_net_value,
                "uncertainty": decision.uncertainty, "bars": decision.bars,
                "trace_hash": decision.trace_hash,
            })

            if not decision.actionable:
                state["skipped"][name] = (
                    f"{decision.direction.lower()}: {decision.reason}"
                    if decision.direction == "NEUTRAL"
                    else f"expected value not positive: {decision.reason}")
                continue

            # Only the side the strategy actually called. Surfacing both CE and
            # PE would mean the board showing two contradictory trades for one
            # decision.
            wanted = decision.option_type
            listed = [r for r in listed
                      if ("call" if wanted == "CE" else "put") == str(r.get("option_type"))]
            if not listed:
                state["skipped"][name] = f"no listed {wanted} inside the windows"
                continue

            await pacer.wait()
            keys = [f"NFO:{r.get('instrument_name')}" for r in listed if r.get("instrument_name")]
            try:
                chain_quotes = await client.quote(keys) or {}
            except Exception as exc:                               # noqa: BLE001
                state["skipped"][name] = f"chain quotes unavailable: {exc}"
                continue

            tradeable, dropped = tradeable_contracts(listed, chain_quotes, cfg, spot=spot)
            for reason, count in dropped.items():
                state["dropped"][reason] = state["dropped"].get(reason, 0) + count
            state["tradeable"] += len(tradeable)
            if not tradeable:
                state["skipped"][name] = "no contract passed the liquidity filters"
                continue

            # Measure implied against realised before anything else. This runs
            # whether or not a trade follows, because it is the record the
            # evidence gate opens on and it exists nowhere but live quotes.
            try:
                reading = volatility_reading(name, tradeable, candles_closes, cfg, spot=spot)
                if reading is not None:
                    state["volatility"].append(reading)
            except Exception as exc:                               # noqa: BLE001
                state["errors"].append(f"{name}: volatility reading failed: {exc}")

            ranked = rank_contracts(tradeable, cfg, expected_ev=decision.expected_net_value)
            for row in ranked:
                eligibility = _f103_eligibility(
                    row, decision.direction, decision.expected_net_value,
                    None)   # conservative EV: see F102_CALIBRATION_RESULT.md
                candidates.append({
                    **row,
                    "underlying": name,
                    "f103_eligible": eligibility.eligible,
                    "f103_action": eligibility.action.value,
                    "f103_reason": eligibility.reason,
                    "direction": decision.direction,
                    "horizon": decision.horizon,
                    "reason": decision.reason,
                    "expected_net_value": decision.expected_net_value,
                    "uncertainty": decision.uncertainty,
                    "trace_hash": decision.trace_hash,
                    "actionable": True,
                })
        except Exception as exc:                                   # noqa: BLE001
            state["errors"].append(f"{name}: {exc}")

    state["candidates"] = candidates
    state["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    return state
