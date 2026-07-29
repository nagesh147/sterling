"""Exact listed-expiry integration for the Sterling Kite scanner.

This module follows the same idempotent install-time extension pattern as
``held_contract_scan``. It keeps the established scanner implementation intact while
making expiry-series selection consistent across spot, derivative, confluence and
deep-ITM execution paths.

Important invariant: no expiry date is calculated from a weekday. Contract dates are
always the exact ``expiry`` values present in Kite's instrument dump. Weekly/monthly
classification and W1-W4/M1-M2 ranks are applied only to those listed dates.
"""
from __future__ import annotations

import copy
import importlib
import sys
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import wraps
from typing import Dict, List, Optional, Sequence

from pydantic.fields import FieldInfo

from app.engines.sterling_kite_engine.schemas import (
    EngineConfigModel,
    EngineSignalRow,
    OptionLeg,
)
from app.services.kite_engine import state
from app.services.kite_engine import scanner as scanner_mod
from app.services.kite_engine import strikes as strikes_mod

_INSTALLED_ATTR = "_expiry_series_runtime_installed"
_STATE_PATCHED_ATTR = "_expiry_series_state_patched"
_SERVICE_PATCHED_ATTR = "_expiry_series_service_patched"

_FULL_MONEYNESS = [
    "ITM5", "ITM4", "ITM3", "ITM2", "ITM1",
    "ATM",
    "OTM1", "OTM2", "OTM3", "OTM4", "OTM5",
]
_INDEX_OPTION_NAMES = {
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
    "SENSEX", "BANKEX", "BSX", "BKX",
}
_INDEX_SYMBOL_PREFIXES = (
    "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
    "SENSEX", "BANKEX", "NIFTY",
)


@dataclass
class _ScanContext:
    uid: str
    index_series: Dict[str, List[int]]
    stock_series: Dict[str, List[int]]
    latest_spot: Dict[str, float] = field(default_factory=dict)


_SCAN_CONTEXT: ContextVar[Optional[_ScanContext]] = ContextVar(
    "kite_expiry_series_context", default=None
)


def _ensure_model_field(model_cls, name: str, annotation, default) -> None:
    """Add a Pydantic v2 field before config JSON is loaded, if it is absent."""
    fields = model_cls.__pydantic_fields__
    if name in fields:
        return
    info = FieldInfo.from_annotation(annotation)
    info.default = copy.deepcopy(default)
    fields[name] = info


def _install_model_fields() -> None:
    _ensure_model_field(EngineConfigModel, "scan_weekly_series_indices", List[int], [0, 1, 2, 3])
    _ensure_model_field(EngineConfigModel, "scan_monthly_series_indices", List[int], [0, 1])
    _ensure_model_field(EngineConfigModel, "scan_monthly_series_stocks", List[int], [0, 1])
    _ensure_model_field(OptionLeg, "resolution_note", Optional[str], None)
    _ensure_model_field(EngineSignalRow, "resolution_reason", Optional[str], None)

    # Correct category defaults for newly-created configurations. Existing saved
    # configurations are normalised by the state wrappers below.
    EngineConfigModel.__pydantic_fields__["scan_expiries_indices"].default = ["weekly", "monthly"]
    EngineConfigModel.__pydantic_fields__["scan_expiries_stocks"].default = ["monthly"]
    EngineConfigModel.__pydantic_fields__["strike_moneyness"].default = list(_FULL_MONEYNESS)

    OptionLeg.model_rebuild(force=True)
    EngineSignalRow.model_rebuild(force=True)
    EngineConfigModel.model_rebuild(force=True)


def _clean_ranks(value, *, maximum: int, default: Sequence[int], allow_empty: bool = False) -> List[int]:
    if value is None:
        raw = list(default)
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = [value]
    cleaned: List[int] = []
    for item in raw:
        try:
            rank = min(maximum, max(0, int(item)))
        except (TypeError, ValueError):
            continue
        if rank not in cleaned:
            cleaned.append(rank)
    cleaned.sort()
    if not cleaned and not allow_empty:
        return list(default)
    return cleaned


def _normalise_engine_config(cfg: EngineConfigModel) -> EngineConfigModel:
    """Apply safe defaults and the stock-monthly-only exchange constraint."""
    updates = {
        "scan_expiries_indices": list(
            cfg.scan_expiries_indices or cfg.scan_expiries or ["weekly", "monthly"]
        ),
        "scan_expiries_stocks": ["monthly"],
        "scan_weekly_series_indices": _clean_ranks(
            getattr(cfg, "scan_weekly_series_indices", None),
            maximum=3,
            default=[0, 1, 2, 3],
        ),
        "scan_monthly_series_indices": _clean_ranks(
            getattr(cfg, "scan_monthly_series_indices", None),
            maximum=1,
            default=[0, 1],
        ),
        "scan_monthly_series_stocks": _clean_ranks(
            getattr(cfg, "scan_monthly_series_stocks", None),
            maximum=1,
            default=[0, 1],
        ),
    }
    if list(cfg.strike_moneyness or []) == ["ITM1", "ATM", "OTM1"]:
        updates["strike_moneyness"] = list(_FULL_MONEYNESS)
    return cfg.model_copy(update=updates)


def _persist_normalised(uid: str, cfg: EngineConfigModel) -> None:
    state._config[uid] = cfg
    try:
        state.db.set_config(f"kite_engine_config_{uid}", cfg.model_dump_json())
    except Exception:
        pass


def _install_state_wrappers() -> None:
    if getattr(state, _STATE_PATCHED_ATTR, False):
        return
    original_get = state.get_config
    original_set = state.set_config

    @wraps(original_get)
    def get_config(uid: str) -> EngineConfigModel:
        original = original_get(uid)
        normalised = _normalise_engine_config(original)
        if normalised.model_dump() != original.model_dump():
            _persist_normalised(uid, normalised)
        return normalised

    @wraps(original_set)
    def set_config(uid: str, cfg: EngineConfigModel) -> EngineConfigModel:
        return original_set(uid, _normalise_engine_config(cfg))

    state.get_config = get_config
    state.set_config = set_config
    setattr(state, _STATE_PATCHED_ATTR, True)


def _series_maps(cfg: EngineConfigModel) -> tuple[Dict[str, List[int]], Dict[str, List[int]]]:
    cfg = _normalise_engine_config(cfg)
    return (
        {
            "weekly": list(cfg.scan_weekly_series_indices),
            "monthly": list(cfg.scan_monthly_series_indices),
        },
        {
            "weekly": [],
            "monthly": list(cfg.scan_monthly_series_stocks),
        },
    )


def _name_is_index(option_name: str) -> bool:
    return str(option_name or "").strip().upper() in _INDEX_OPTION_NAMES


def _chain_is_index(chain: Sequence[dict]) -> bool:
    for row in chain:
        symbol = str(row.get("instrument_name") or row.get("tradingsymbol") or "").upper()
        if symbol.startswith(_INDEX_SYMBOL_PREFIXES):
            return True
    return False


def _series_for_chain(chain: Sequence[dict]) -> Optional[Dict[str, List[int]]]:
    ctx = _SCAN_CONTEXT.get()
    if ctx is None:
        return None
    return ctx.index_series if _chain_is_index(chain) else ctx.stock_series


def _available_expiries(chain: Sequence[dict]) -> List[str]:
    return sorted({
        str(row.get("expiry_date") or row.get("expiry") or "")[:10]
        for row in chain
        if row.get("expiry_date") or row.get("expiry")
    })


def resolve_option_legs(
    row: EngineSignalRow,
    option_rows: Sequence[dict],
    *,
    option_name: str,
    moneynesses: Sequence[str],
    today: date,
    expiry_types: Sequence[str],
    expiry_ranks_by_type: Dict[str, List[int]],
    latest_spot: Optional[float] = None,
) -> tuple[List[OptionLeg], Optional[str]]:
    """Pure resolution helper used by the scanner wrapper and regression tests."""
    chain = strikes_mod.chain_rows_for(option_rows, option_name, today)
    ordered = sorted(
        moneynesses,
        key=lambda value: scanner_mod._MONEYNESS_ORDER.get(value, 99),
    )
    spot = float(latest_spot if latest_spot is not None and latest_spot > 0 else row.spot)
    picks = strikes_mod.pick_strikes(
        chain,
        spot=spot,
        direction=row.direction,
        moneynesses=ordered,
        expiry_types=tuple(expiry_types or ()),
        expiry_ranks_by_type=expiry_ranks_by_type,
        today=today,
    )
    legs = [
        OptionLeg(
            moneyness=moneyness,
            option_type=pick.option_type,
            option_symbol=pick.option_symbol,
            strike=pick.strike,
            expiry=pick.expiry,
            lot_size=pick.lot_size or None,
            is_active=bool(row.is_active),
            signal_timestamp_ms=row.timestamp_ms,
            entry_timestamp_ms=row.timestamp_ms,
            resolution_note=None,
        )
        for moneyness, pick in picks
    ]
    if legs:
        return legs, None
    if not chain:
        return [], f"No listed option-chain rows were found for {option_name}."
    selected = {
        kind: list(expiry_ranks_by_type.get(kind, []))
        for kind in expiry_types
    }
    expiries = _available_expiries(chain)
    return [], (
        "No listed contract matched the selected strike and expiry series. "
        f"Selected series: {selected}; available listed expiries: "
        f"{', '.join(expiries[:8]) or 'none'}."
    )


def _install_scanner_wrappers() -> None:
    scanner_cls = scanner_mod.KiteEngineScanner
    if getattr(scanner_cls, _INSTALLED_ATTR, False):
        return

    original_scan = scanner_cls.scan
    original_evaluate_item = scanner_mod.evaluate_item
    original_pick_strikes = scanner_mod.pick_strikes
    original_pick_contracts = scanner_mod.pick_contracts

    @wraps(original_evaluate_item)
    def evaluate_item(engine, item, candles, cfg):
        ctx = _SCAN_CONTEXT.get()
        if ctx is not None and candles:
            latest = float(candles[-1].close)
            ctx.latest_spot[item.name.upper()] = latest
            ctx.latest_spot[item.tradingsymbol.upper()] = latest
        return original_evaluate_item(engine, item, candles, cfg)

    @wraps(original_pick_strikes)
    def pick_strikes(chain, *args, **kwargs):
        if kwargs.get("expiry_ranks_by_type") is None:
            series = _series_for_chain(chain)
            if series is not None:
                kwargs["expiry_ranks_by_type"] = series
        return original_pick_strikes(chain, *args, **kwargs)

    @wraps(original_pick_contracts)
    def pick_contracts(chain, *args, **kwargs):
        if kwargs.get("expiry_ranks_by_type") is None:
            series = _series_for_chain(chain)
            if series is not None:
                kwargs["expiry_ranks_by_type"] = series
        return original_pick_contracts(chain, *args, **kwargs)

    def attach_strikes(
        row: EngineSignalRow,
        option_rows: Sequence[dict],
        *,
        option_name: str,
        moneynesses: Sequence[str] = ("ATM",),
        today: Optional[date] = None,
        expiry_types: Sequence[str] = (),
    ) -> EngineSignalRow:
        ctx = _SCAN_CONTEXT.get()
        series = (
            ctx.index_series if ctx is not None and _name_is_index(option_name)
            else ctx.stock_series if ctx is not None
            else {kind: [0] for kind in expiry_types}
        )
        current_spot = None
        if ctx is not None:
            current_spot = ctx.latest_spot.get(option_name.upper())
        legs, reason = resolve_option_legs(
            row,
            option_rows,
            option_name=option_name,
            moneynesses=moneynesses,
            today=today or datetime.now(scanner_mod._IST).date(),
            expiry_types=expiry_types,
            expiry_ranks_by_type=series,
            latest_spot=current_spot,
        )
        row.legs = legs
        row.resolution_reason = reason
        return row

    @wraps(original_scan)
    async def scan(self, *args, **kwargs):
        uid = kwargs.get("uid")
        cfg_model = state.get_config(uid) if uid else EngineConfigModel()
        index_series, stock_series = _series_maps(cfg_model)
        # Enforce truthful category support at the scanner boundary, regardless of
        # stale clients or legacy persisted settings.
        kwargs["expiry_types_indices"] = tuple(
            cfg_model.scan_expiries_indices or cfg_model.scan_expiries or ["weekly", "monthly"]
        )
        kwargs["expiry_types_stocks"] = ("monthly",)
        token = _SCAN_CONTEXT.set(_ScanContext(
            uid=str(uid or ""),
            index_series=index_series,
            stock_series=stock_series,
        ))
        try:
            return await original_scan(self, *args, **kwargs)
        finally:
            _SCAN_CONTEXT.reset(token)

    scanner_mod.evaluate_item = evaluate_item
    scanner_mod.pick_strikes = pick_strikes
    scanner_mod.pick_contracts = pick_contracts
    scanner_mod.attach_strikes = attach_strikes
    scanner_cls.scan = scan
    setattr(scanner_cls, _INSTALLED_ATTR, True)


async def _configured_resolve_deep_itm(service_mod, client, item, row, cfg):
    """Resolve deep-ITM execution from the same category-specific listed series."""
    exchange = item.option_exchange
    try:
        dump = await client.search_instruments("", exchange, limit=1_000_000)
    except Exception:
        return None

    today = datetime.now(service_mod._IST).date()
    chain = strikes_mod.chain_rows_for(dump, item.tradingsymbol, today)
    if not chain:
        return None

    cfg = _normalise_engine_config(cfg)
    index_series, stock_series = _series_maps(cfg)
    series = index_series if item.is_index else stock_series
    expiry_types = tuple(
        (cfg.scan_expiries_indices if item.is_index else cfg.scan_expiries_stocks)
        or cfg.scan_expiries
        or ()
    )
    spot = float(getattr(row, "underlying_spot", 0) or row.spot)
    direction = "long" if getattr(row, "direction", "long") in ("long", "bull", 1) else "short"
    plans = [
        (kind, rank)
        for kind in expiry_types
        for rank in series.get(kind, [])
    ]

    pick = None
    for kind, rank in plans:
        if cfg.target_delta:
            pick = strikes_mod.pick_by_delta(
                chain,
                spot=spot,
                direction=direction,
                target_delta=float(cfg.target_delta),
                iv=0.18,
                expiry_type=kind,
                expiry_rank=rank,
                today=today,
            )
        else:
            picks = strikes_mod.pick_strikes(
                chain,
                spot=spot,
                direction=direction,
                moneynesses=[cfg.itm_depth or "ITM10"],
                expiry_types=[kind],
                expiry_ranks_by_type={kind: [rank]},
                today=today,
            )
            pick = picks[0][1] if picks else None
        if pick is not None and pick.option_symbol:
            break

    if pick is None or not pick.option_symbol:
        return None

    entry_premium, stop_premium, delta = await service_mod._resolve_premium_stop(
        client,
        exch=exchange,
        symbol=pick.option_symbol,
        strike=float(pick.strike),
        expiry=pick.expiry,
        option_type=pick.option_type,
        spot=spot,
        trail_level=float(row.stop_loss or spot),
        iv=0.18,
    )
    return service_mod._ResolvedTrade(
        symbol=pick.option_symbol,
        exchange=exchange,
        token=int(pick.token or 0),
        lot_size=int(pick.lot_size or 0),
        entry_px=entry_premium,
        stop_px=stop_premium,
        delta=delta,
        strike=float(pick.strike),
        expiry=str(pick.expiry),
    )


def _patch_service_module(service_mod) -> None:
    if getattr(service_mod, _SERVICE_PATCHED_ATTR, False):
        return

    async def resolve_deep_itm(client, item, row, cfg):
        return await _configured_resolve_deep_itm(service_mod, client, item, row, cfg)

    service_mod._resolve_deep_itm = resolve_deep_itm
    setattr(service_mod, _SERVICE_PATCHED_ATTR, True)


def _install_service_patch_later() -> None:
    """Patch service after its current import completes without creating a cycle."""
    def worker() -> None:
        module_name = "app.services.kite_engine.service"
        for _ in range(500):
            service_mod = sys.modules.get(module_name)
            if service_mod is not None and hasattr(service_mod, "_resolve_deep_itm"):
                _patch_service_module(service_mod)
                return
            time.sleep(0.01)
        try:
            _patch_service_module(importlib.import_module(module_name))
        except Exception:
            return

    threading.Thread(
        target=worker,
        name="kite-expiry-series-service-patch",
        daemon=True,
    ).start()


def install() -> None:
    """Install the exact-expiry integration once."""
    _install_model_fields()
    _install_state_wrappers()
    _install_scanner_wrappers()
    _install_service_patch_later()
