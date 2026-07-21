"""Signal-board integrity fixes for the Kite scanner.

The confluence scanner intentionally requires a fresh underlying transition and a
currently-confirming option premium. Two integration boundaries still need protection:

* instrument endpoints can return different amounts of 1H history; an option response
  that contains bars newer than the underlying response must be evaluated only through
  the underlying's latest closed bar;
* confluence is an event, not something that can be reconstructed on every later bar.
  A scan with no new confluence event must not erase the most recent retained setup.

No timestamp or expiry is manufactured here. Existing broker candle timestamps are
only trimmed to the latest closed underlying timestamp already present in that scan.
The most recent option close is retained separately as the current execution/display
premium; it is never used to prove the earlier same-bar signal.
"""
from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Dict, List, Optional, Sequence

from app.engines.sterling_kite_engine.schemas import EngineSignalRow
from app.services.kite_engine import scanner as scanner_mod
from app.services.kite_engine import state

_INSTALLED_ATTR = "_signal_board_runtime_installed"
_RETENTION_MS = scanner_mod._SIGNAL_RETENTION_MS


@dataclass
class _SignalScanContext:
    uid: str
    latest_underlying_bar: Dict[str, int] = field(default_factory=dict)
    latest_option_close: Dict[str, float] = field(default_factory=dict)


_SCAN_CONTEXT: ContextVar[Optional[_SignalScanContext]] = ContextVar(
    "kite_signal_board_context", default=None
)


def _normalise_key(value: object) -> str:
    return str(value or "").strip().upper()


def _option_anchor(name: str, anchors: Dict[str, int]) -> Optional[int]:
    """Return the latest underlying bar for an option symbol, if known.

    The longest matching underlying wins, preventing ``NIFTY`` from matching a
    ``NIFTYNXT50`` contract. A valid option symbol continues with a digit after the
    underlying name; the exact underlying fetch itself is therefore never trimmed.
    """
    symbol = _normalise_key(name)
    matches = [
        (key, ts)
        for key, ts in anchors.items()
        if symbol.startswith(key)
        and len(symbol) > len(key)
        and symbol[len(key)].isdigit()
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: len(item[0]))[1]


def _trim_to_anchor(candles: Sequence, anchor_ms: Optional[int]) -> List:
    """Keep only broker bars at or before an already-observed underlying bar."""
    if anchor_ms is None:
        return list(candles)
    return [candle for candle in candles if int(candle.timestamp_ms) <= int(anchor_ms)]


def _retention_key(row: EngineSignalRow) -> tuple[str, str]:
    return (_normalise_key(row.underlying), _normalise_key(row.option_type))


def _ended_copy(row: EngineSignalRow) -> EngineSignalRow:
    copied = row.model_copy(deep=True, update={"is_fresh": False, "is_active": False})
    copied.legs = [leg.model_copy(update={"is_active": False}) for leg in copied.legs]
    return copied


def merge_retained_confluence(
    current_rows: Sequence[EngineSignalRow],
    previous_rows: Sequence[EngineSignalRow],
    *,
    now_ms: Optional[int] = None,
) -> List[EngineSignalRow]:
    """Merge the latest confluence event per underlying/type into a new snapshot.

    Current scan rows always win. If no current event exists for an underlying/type,
    its most recent prior confluence row remains visible as ended for the standard
    15-day board window. Rows from other scan sources are never carried across a
    source change.
    """
    now = int(now_ms if now_ms is not None else time.time() * 1000)
    merged = list(current_rows)
    newest_current: Dict[tuple[str, str], int] = {}
    for row in current_rows:
        if row.source == "confluence":
            key = _retention_key(row)
            newest_current[key] = max(newest_current.get(key, 0), int(row.timestamp_ms))

    prior_latest: Dict[tuple[str, str], EngineSignalRow] = {}
    for row in previous_rows:
        if row.source != "confluence":
            continue
        timestamp = int(row.timestamp_ms)
        if timestamp <= 0 or now - timestamp > _RETENTION_MS:
            continue
        key = _retention_key(row)
        existing = prior_latest.get(key)
        if existing is None or timestamp > int(existing.timestamp_ms):
            prior_latest[key] = row

    for key, row in prior_latest.items():
        if newest_current.get(key, 0) >= int(row.timestamp_ms):
            continue
        merged.append(_ended_copy(row))

    merged.sort(key=lambda row: int(row.timestamp_ms), reverse=True)
    return merged


def _apply_current_premiums(rows: Sequence[EngineSignalRow], closes: Dict[str, float]) -> None:
    """Stamp current option close after shared-bar confirmation has completed."""
    for row in rows:
        if row.source != "confluence":
            continue
        for leg in row.legs:
            current = closes.get(_normalise_key(leg.option_symbol))
            if current is not None and current > 0:
                leg.premium_spot = float(current)


def _install() -> None:
    scanner_cls = scanner_mod.KiteEngineScanner
    if getattr(scanner_cls, _INSTALLED_ATTR, False):
        return

    original_scan = scanner_cls.scan
    original_fetch_candles = scanner_cls._fetch_candles
    original_evaluate_item = scanner_mod.evaluate_item

    @wraps(original_evaluate_item)
    def evaluate_item(engine, item, candles, cfg):
        ctx = _SCAN_CONTEXT.get()
        if ctx is not None and candles:
            latest_ts = int(candles[-1].timestamp_ms)
            for value in (getattr(item, "name", ""), getattr(item, "tradingsymbol", "")):
                key = _normalise_key(value)
                if key:
                    ctx.latest_underlying_bar[key] = latest_ts
        return original_evaluate_item(engine, item, candles, cfg)

    @wraps(original_fetch_candles)
    async def fetch_candles(self, client, us, token: int, name: str):
        candles = await original_fetch_candles(self, client, us, token, name)
        ctx = _SCAN_CONTEXT.get()
        if ctx is None or not candles:
            return candles
        anchor = _option_anchor(name, ctx.latest_underlying_bar)
        if anchor is None:
            return candles
        ctx.latest_option_close[_normalise_key(name)] = float(candles[-1].close)
        return _trim_to_anchor(candles, anchor)

    @wraps(original_scan)
    async def scan(self, *args, **kwargs):
        uid = str(kwargs.get("uid") or "")
        previous = list(self.snapshot(uid).rows) if uid else []
        confluence_mode = kwargs.get("confluence_universe") is not None
        ctx = _SignalScanContext(uid=uid)
        token = _SCAN_CONTEXT.set(ctx)
        try:
            result = await original_scan(self, *args, **kwargs)
            if confluence_mode and uid:
                snapshot = self.snapshot(uid)
                _apply_current_premiums(snapshot.rows, ctx.latest_option_close)
                snapshot.rows = merge_retained_confluence(snapshot.rows, previous)
                state.save_signal_cache(
                    uid,
                    [row.model_dump() for row in snapshot.rows],
                    snapshot.generated_ms,
                )
            return result
        finally:
            _SCAN_CONTEXT.reset(token)

    scanner_mod.evaluate_item = evaluate_item
    scanner_cls._fetch_candles = fetch_candles
    scanner_cls.scan = scan
    setattr(scanner_cls, _INSTALLED_ATTR, True)


def install() -> None:
    """Install once; kept public for package startup and focused tests."""
    _install()
