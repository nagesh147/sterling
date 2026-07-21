"""Signal-board integrity fixes for the Kite scanner.

The confluence scanner is an intersection of two retained entry states:

* the underlying has a retained triple-SuperTrend entry; and
* the selected option premium has a retained BUY entry.

Two integration boundaries need protection:

* instrument endpoints can return different amounts of 1H history, so option bars are
  evaluated only through the latest closed underlying bar already observed; and
* clearing the persisted board must not make an active/recent confluence setup
  impossible to reconstruct. The base scanner accidentally narrowed the approved
  retained-entry design to a fresh transition on the latest bar only.

No timestamp or expiry is manufactured here. Every timestamp comes from a broker
candle. Fresh auto-execution remains limited to the bar on which the second side of
the confluence becomes active; historical reconstruction never replays an old order.
"""
from __future__ import annotations

import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
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
    """Stamp the latest close on same-bar, newly-fired confluence rows only.

    Reconstructed retained rows keep their actual confluence-entry premium. Live LTP
    is supplied separately by the quote stream in the UI.
    """
    for row in rows:
        if row.source != "confluence" or not row.is_fresh:
            continue
        for leg in row.legs:
            current = closes.get(_normalise_key(leg.option_symbol))
            if current is not None and current > 0:
                leg.premium_spot = float(current)


def _latest_per_key(rows: Sequence[EngineSignalRow]) -> List[EngineSignalRow]:
    """Keep the newest row for each underlying/direction board slot."""
    latest: Dict[tuple[str, str], EngineSignalRow] = {}
    passthrough: List[EngineSignalRow] = []
    for row in rows:
        if row.source != "confluence":
            passthrough.append(row)
            continue
        key = _retention_key(row)
        old = latest.get(key)
        if old is None or int(row.timestamp_ms) > int(old.timestamp_ms):
            latest[key] = row
    return passthrough + list(latest.values())


async def _rebuild_retained_confluence(
    self,
    *,
    uid: str,
    client,
    confluence_universe: Sequence,
    nfo_rows: Sequence[dict],
    bfo_rows: Sequence[dict],
    cfg,
    moneyness: Sequence[str],
    expiry_types: Sequence[str],
    expiry_types_indices: Optional[Sequence[str]],
    expiry_types_stocks: Optional[Sequence[str]],
    existing_rows: Sequence[EngineSignalRow],
) -> List[tuple[EngineSignalRow, object]]:
    """Reconstruct retained confluence from candle history after cache loss.

    This restores the approved scanner design: use ``_retain_signals`` on both the
    underlying and option premium rather than requiring the underlying transition to
    occur on the latest bar. The confluence timestamp is the later of the two retained
    entry timestamps—the first broker bar on which both conditions were active.
    """
    if not uid or not confluence_universe:
        return []

    from app.services.kite_engine import expiry_series_runtime as expiry_runtime

    us = self.snapshot(uid)
    now_ms = int(time.time() * 1000)
    today = datetime.now(scanner_mod._IST).date()
    cfg_model = state.get_config(uid)
    index_series, stock_series = expiry_runtime._series_maps(cfg_model)
    covered = {
        _retention_key(row): int(row.timestamp_ms)
        for row in existing_rows
        if row.source == "confluence"
    }
    sem = asyncio.Semaphore(scanner_mod._CONCURRENCY)
    rebuilt: List[tuple[EngineSignalRow, object]] = []

    for item in confluence_universe:
        if not getattr(item, "token", 0):
            continue
        try:
            underlying = scanner_mod.drop_forming(
                await self._fetch_1h(client, us, item)
            )
        except Exception as exc:  # noqa: BLE001
            scanner_mod.log.warning(
                "kite-engine retained confluence underlying fail %s: %s",
                getattr(item, "name", ""), exc,
            )
            continue
        if len(underlying) <= cfg.warmup + 1:
            continue

        # scanner_mod.evaluate_item is the installed wrapper, so this also establishes
        # the exact latest underlying bar used to trim every option history below.
        eval_rows = scanner_mod.evaluate_item(us.engine, item, underlying, cfg)
        candidates = scanner_mod._retain_signals(eval_rows, now_ms)
        if not candidates:
            continue

        # A board slot needs only its newest retained entry. Older superseded entries
        # remain historical, not simultaneous trade plans.
        newest_candidates: Dict[str, EngineSignalRow] = {}
        for row in candidates:
            key = _normalise_key(row.option_type)
            old = newest_candidates.get(key)
            if old is None or int(row.timestamp_ms) > int(old.timestamp_ms):
                newest_candidates[key] = row

        option_rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
        chain = scanner_mod.chain_rows_for(option_rows, item.tradingsymbol, today)
        if not chain:
            continue
        selected_expiries = (
            expiry_types_indices
            if item.is_index and expiry_types_indices is not None
            else expiry_types_stocks
            if not item.is_index and expiry_types_stocks is not None
            else expiry_types
        )
        series = index_series if item.is_index else stock_series
        ordered = sorted(
            moneyness,
            key=lambda value: scanner_mod._MONEYNESS_ORDER.get(value, 99),
        )
        under_by_ts = {
            int(candle.timestamp_ms): float(candle.close) for candle in underlying
        }
        latest_underlying_ts = int(underlying[-1].timestamp_ms)

        for row in newest_candidates.values():
            board_key = _retention_key(row)
            if covered.get(board_key, 0) >= int(row.timestamp_ms):
                continue
            picks = scanner_mod.pick_strikes(
                chain,
                spot=float(row.spot),
                direction=row.direction,
                moneynesses=ordered,
                expiry_types=tuple(selected_expiries or ()),
                expiry_ranks_by_type=series,
                today=today,
            )
            if not picks:
                continue

            async def confirm(moneyness_value, pick):
                async with sem:
                    try:
                        option_history = scanner_mod.drop_forming(
                            await self._fetch_candles(
                                client, us, pick.token, pick.option_symbol
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        scanner_mod.log.warning(
                            "kite-engine retained confluence option fail %s: %s",
                            pick.option_symbol, exc,
                        )
                        return None
                if len(option_history) <= cfg.warmup + 1:
                    return None

                # Full-history retained premium entry, not only a latest-bar arrow.
                premium_rows = scanner_mod.evaluate_derivative_contract(
                    item, moneyness_value, pick, option_history, cfg
                )
                premium_candidates = scanner_mod._retain_signals(premium_rows, now_ms)
                if not premium_candidates:
                    return None
                premium_row = max(
                    premium_candidates, key=lambda value: int(value.timestamp_ms)
                )
                confluence_ts = max(
                    int(row.timestamp_ms), int(premium_row.timestamp_ms)
                )
                if confluence_ts > latest_underlying_ts:
                    return None

                # Prove both retained entries were active on the exact confluence bar.
                option_at_signal = _trim_to_anchor(option_history, confluence_ts)
                underlying_at_signal = _trim_to_anchor(underlying, confluence_ts)
                if (
                    not option_at_signal
                    or not underlying_at_signal
                    or int(option_at_signal[-1].timestamp_ms) != confluence_ts
                    or int(underlying_at_signal[-1].timestamp_ms) != confluence_ts
                ):
                    return None

                premium_at_signal = scanner_mod.evaluate_derivative_contract(
                    item, moneyness_value, pick, option_at_signal, cfg
                )
                premium_match = next(
                    (
                        value
                        for value in premium_at_signal
                        if int(value.timestamp_ms) == int(premium_row.timestamp_ms)
                        and value.is_active
                    ),
                    None,
                )
                if premium_match is None:
                    return None

                # Use the pre-install evaluator so the historical prefix does not move
                # the option-trimming anchor away from the true latest underlying bar.
                underlying_at_event = self._signal_board_original_evaluate_item(
                    us.engine, item, underlying_at_signal, cfg
                )
                underlying_match = next(
                    (
                        value
                        for value in underlying_at_event
                        if int(value.timestamp_ms) == int(row.timestamp_ms)
                        and value.is_active
                    ),
                    None,
                )
                if underlying_match is None:
                    return None

                leg = premium_row.legs[0].model_copy(deep=True)
                leg.premium_spot = float(option_at_signal[-1].close)
                leg.premium_sl = float(premium_row.stop_loss)
                leg.entry_sl = float(premium_match.stop_loss)
                leg.token = int(pick.token or 0)
                leg.is_active = bool(row.is_active and premium_row.is_active)
                leg.signal_timestamp_ms = int(premium_row.timestamp_ms)
                leg.entry_timestamp_ms = confluence_ts
                leg.alignment = premium_row.alignment
                leg.exit_state = premium_row.exit_state
                return leg, confluence_ts, underlying_match

            confirmed_results = await asyncio.gather(
                *[confirm(m, pick) for m, pick in picks]
            )
            confirmed = [result for result in confirmed_results if result is not None]
            if not confirmed:
                continue

            # All legs belong to the same underlying retained entry, but their premium
            # entries may begin on different bars. The parent starts at the latest leg
            # confirmation so every displayed leg was valid by the parent timestamp.
            parent_ts = max(result[1] for result in confirmed)
            parent_legs = [
                result[0] for result in confirmed if result[1] <= parent_ts
            ]
            parent_legs.sort(
                key=lambda leg: scanner_mod._MONEYNESS_ORDER.get(leg.moneyness, 99)
            )
            parent_under = max(
                (result[2] for result in confirmed),
                key=lambda value: int(value.timestamp_ms),
            )
            parent = row.model_copy(deep=True)
            parent.source = "confluence"
            parent.timestamp_ms = parent_ts
            parent.legs = parent_legs
            parent.spot = under_by_ts.get(parent_ts, float(row.spot))
            parent.underlying_spot = parent.spot
            parent.entry_sl = parent_under.stop_loss
            parent.is_active = bool(row.is_active and any(leg.is_active for leg in parent_legs))
            parent.is_fresh = parent_ts == latest_underlying_ts
            rebuilt.append((parent, item))
            covered[board_key] = parent_ts

    return rebuilt


def _install() -> None:
    scanner_cls = scanner_mod.KiteEngineScanner
    if getattr(scanner_cls, _INSTALLED_ATTR, False):
        return

    original_scan = scanner_cls.scan
    original_fetch_candles = scanner_cls._fetch_candles
    original_evaluate_item = scanner_mod.evaluate_item
    # Exposed only to this runtime's historical-prefix verifier.
    scanner_cls._signal_board_original_evaluate_item = staticmethod(original_evaluate_item)

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
        confluence_universe = kwargs.get("confluence_universe")
        confluence_mode = confluence_universe is not None
        ctx = _SignalScanContext(uid=uid)
        token = _SCAN_CONTEXT.set(ctx)
        try:
            result = await original_scan(self, *args, **kwargs)
            if confluence_mode and uid:
                snapshot = self.snapshot(uid)
                strict_rows = list(snapshot.rows)
                _apply_current_premiums(strict_rows, ctx.latest_option_close)
                rebuilt_pairs = await _rebuild_retained_confluence(
                    self,
                    uid=uid,
                    client=kwargs.get("client"),
                    confluence_universe=confluence_universe or (),
                    nfo_rows=kwargs.get("nfo_rows") or (),
                    bfo_rows=kwargs.get("bfo_rows") or (),
                    cfg=kwargs.get("cfg"),
                    moneyness=kwargs.get("moneyness") or ("ATM",),
                    expiry_types=kwargs.get("expiry_types") or (),
                    expiry_types_indices=kwargs.get("expiry_types_indices"),
                    expiry_types_stocks=kwargs.get("expiry_types_stocks"),
                    # Only rows produced by this scan are authoritative coverage.
                    # Cached rows must be revalidated: treating a warm-cache row as
                    # covered skips reconstruction and then merge_retained_confluence()
                    # downgrades a still-running setup to ended after every restart.
                    existing_rows=strict_rows,
                )
                rebuilt_rows = [row for row, _item in rebuilt_pairs]
                strict_keys = {
                    (_retention_key(row), int(row.timestamp_ms))
                    for row in strict_rows
                    if row.source == "confluence"
                }
                place_cb = kwargs.get("place_cb")
                for row, item in rebuilt_pairs:
                    identity = (_retention_key(row), int(row.timestamp_ms))
                    if row.is_fresh and identity not in strict_keys:
                        snapshot.diag.confluence_fired += 1
                        if place_cb is not None:
                            try:
                                await place_cb(row, item)
                            except Exception as exc:  # noqa: BLE001
                                scanner_mod.log.warning(
                                    "kite-engine retained confluence auto-exec fail %s: %s",
                                    row.underlying, exc,
                                )
                current = _latest_per_key(strict_rows + rebuilt_rows)
                snapshot.rows = merge_retained_confluence(current, previous)
                snapshot.generated_ms = int(time.time() * 1000)
                state.save_signal_cache(
                    uid,
                    [row.model_dump() for row in snapshot.rows],
                    snapshot.generated_ms,
                )
                log_cb = kwargs.get("log_cb")
                if log_cb and rebuilt_rows:
                    live = sum(1 for row in rebuilt_rows if row.is_active or row.is_fresh)
                    log_cb(
                        f"Restored {len(rebuilt_rows)} retained confluence signal(s) "
                        f"from broker candle history ({live} live)."
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
