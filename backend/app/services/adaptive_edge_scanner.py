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

            for row in tradeable:
                candidates.append({
                    **row,
                    "underlying": name,
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
