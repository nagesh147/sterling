"""Derivative-scan extension for exact broker-held option contracts.

The normal premium-chart scan deliberately resolves only the configured moneyness
ladder around the *current* underlying spot. That keeps the request count bounded,
but it leaves a blind spot after a contract moves away from that ladder: the exact
held contract is no longer evaluated even though its own 1H Heikin-Ashi chart can
produce a valid three-green confirmation.

This module installs a small, idempotent extension around ``KiteEngineScanner.scan``.
After the configured derivative pass completes it evaluates every non-zero NFO/BFO
option position by exact tradingsymbol, de-duplicates contracts already covered by
the ladder, and merges any running/fresh signal into the normal scanner snapshot.
It never places a second order for an already-held contract.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from typing import Iterable, List, Mapping, Optional, Sequence

from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.services.kite_engine import state
from app.services.kite_engine.strikes import OptionPick
from app.services.kite_engine.universe import UniverseItem

_IST = timezone(timedelta(hours=5, minutes=30))
_INSTALLED_ATTR = "_held_contract_scan_installed"


@dataclass(frozen=True)
class HeldContractSpec:
    """Exact broker-held option contract plus the minimal scanner context."""

    item: UniverseItem
    pick: OptionPick
    moneyness: str = "HELD"


def _position_qty(row: Mapping) -> int:
    for key in ("quantity", "qty", "net_quantity"):
        try:
            value = int(float(row.get(key, 0) or 0))
        except (TypeError, ValueError):
            continue
        if value:
            return value
    return 0


def held_contract_specs(
    positions_raw: Optional[Mapping],
    nfo_rows: Sequence[Mapping],
    bfo_rows: Sequence[Mapping],
    *,
    today: Optional[date] = None,
) -> List[HeldContractSpec]:
    """Resolve non-zero broker option positions to exact instrument metadata.

    Only the ``net`` book is used; Kite's ``day`` book overlaps it and would double
    scan the same contract. Rows absent from the current instrument dump are ignored
    rather than guessed, because a guessed token cannot fetch historical candles.
    """

    today = today or datetime.now(_IST).date()
    by_key = {}
    for exchange, rows in (("NFO", nfo_rows), ("BFO", bfo_rows)):
        for row in rows:
            symbol = str(row.get("tradingsymbol", "") or "").strip().upper()
            if symbol:
                by_key[(exchange, symbol)] = row

    out: List[HeldContractSpec] = []
    seen = set()
    net_rows: Iterable[Mapping] = (positions_raw or {}).get("net", []) or []
    for position in net_rows:
        if _position_qty(position) == 0:
            continue
        exchange = str(position.get("exchange", "") or "").strip().upper()
        if exchange not in ("NFO", "BFO"):
            continue
        symbol = str(
            position.get("tradingsymbol")
            or position.get("trading_symbol")
            or position.get("symbol")
            or ""
        ).strip().upper()
        key = (exchange, symbol)
        if not symbol or key in seen:
            continue
        meta = by_key.get(key)
        if not meta:
            continue
        option_type = str(meta.get("instrument_type", "") or "").upper()
        if option_type not in ("CE", "PE"):
            continue
        try:
            token = int(meta.get("instrument_token") or position.get("instrument_token") or 0)
            strike = float(meta.get("strike") or 0.0)
            lot_size = int(meta.get("lot_size") or 0)
        except (TypeError, ValueError):
            continue
        if token <= 0 or strike <= 0:
            continue
        expiry = str(meta.get("expiry", "") or "")[:10]
        try:
            dte = (date.fromisoformat(expiry) - today).days
        except (TypeError, ValueError):
            dte = 0
        underlying = str(meta.get("name", "") or "").strip().upper()
        if not underlying:
            continue

        seen.add(key)
        out.append(HeldContractSpec(
            item=UniverseItem(
                name=underlying,
                tradingsymbol=underlying,
                token=0,
                exchange="BSE" if exchange == "BFO" else "NSE",
                option_exchange=exchange,
                is_index=False,
            ),
            pick=OptionPick(
                option_symbol=symbol,
                strike=strike,
                option_type=option_type,
                expiry=expiry,
                dte=dte,
                lot_size=lot_size,
                token=token,
            ),
        ))
    return out


async def _append_held_contract_signals(
    scanner_obj,
    *,
    uid: str,
    client,
    cfg: SterlingKiteEngineConfig,
    nfo_rows: Sequence[Mapping],
    bfo_rows: Sequence[Mapping],
    log_cb=None,
) -> None:
    """Evaluate exact held contracts and merge them into the completed snapshot."""

    try:
        positions_raw = await client.get_positions_raw()
    except Exception:
        return

    specs = held_contract_specs(positions_raw, nfo_rows, bfo_rows)
    if not specs:
        return

    # Local import avoids a scanner<->extension import cycle during package startup.
    from app.services.kite_engine.scanner import (
        _compile_rows,
        _retain_signals,
        drop_forming,
        evaluate_derivative_contract,
    )

    us = scanner_obj.snapshot(uid)
    existing = {
        leg.option_symbol
        for row in us.rows
        for leg in getattr(row, "legs", [])
        if getattr(leg, "option_symbol", "")
    }
    existing.update(us.scanned_contract_symbols)
    pending = [spec for spec in specs if spec.pick.option_symbol not in existing]
    if not pending:
        return

    us.scanning = True
    appended = []
    now_ms = int(time.time() * 1000)
    try:
        for spec in pending:
            if us.cancelled:
                break
            pick = spec.pick
            us.scanning_label = f"Held: {pick.option_symbol}"
            if log_cb:
                log_cb(f"Scanning held derivative: {pick.option_symbol}")
            us.scanned_contract_symbols.add(pick.option_symbol)
            us.diag.deriv_resolved += 1
            try:
                candles = drop_forming(await scanner_obj._fetch_candles(
                    client, us, pick.token, pick.option_symbol))
            except Exception:  # noqa: BLE001
                us.diag.deriv_no_data += 1
                continue

            if not candles:
                us.diag.deriv_no_data += 1
                continue

            bars = len(candles)
            us.diag.deriv_charts += 1
            us.diag.deriv_min_bars = bars if us.diag.deriv_min_bars == 0 else min(us.diag.deriv_min_bars, bars)
            us.diag.deriv_max_bars = max(us.diag.deriv_max_bars, bars)
            rows = evaluate_derivative_contract(spec.item, spec.moneyness, pick, candles, cfg)
            latest_ts = int(candles[-1].timestamp_ms)
            fired = any(int(row.timestamp_ms) == latest_ts for row in rows)
            if fired:
                us.diag.deriv_fired += 1
            appended.extend(_retain_signals(rows, now_ms))

        if appended:
            us.rows = _compile_rows([*us.rows, *appended])
            us.generated_ms = int(time.time() * 1000)
            state.save_signal_cache(uid, [row.model_dump() for row in us.rows], us.generated_ms)
    finally:
        us.scanning = False
        us.scanning_label = ""


def install() -> None:
    """Install the held-contract extension once for every scanner instance."""

    from app.services.kite_engine.scanner import KiteEngineScanner

    if getattr(KiteEngineScanner, _INSTALLED_ATTR, False):
        return
    original_scan = KiteEngineScanner.scan

    @wraps(original_scan)
    async def scan_with_held_contracts(self, *args, **kwargs):
        await original_scan(self, *args, **kwargs)
        # ``None`` means the configured source is spot/confluence, where premium-only
        # derivative rows would violate the selected mode. An empty list still means
        # derivative mode and should scan broker-held contracts.
        if kwargs.get("deriv_universe") is None:
            return
        await _append_held_contract_signals(
            self,
            uid=kwargs["uid"],
            client=kwargs["client"],
            cfg=kwargs["cfg"],
            nfo_rows=kwargs.get("nfo_rows", ()),
            bfo_rows=kwargs.get("bfo_rows", ()),
            log_cb=kwargs.get("log_cb"),
        )

    KiteEngineScanner.scan = scan_with_held_contracts
    setattr(KiteEngineScanner, _INSTALLED_ATTR, True)
