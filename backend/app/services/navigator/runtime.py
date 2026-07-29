"""Independent runtime for Sterling Value-Flow Navigator.

This module deliberately does not call ``kite_engine.scanner.scan()``. It
reuses only shared Kite account/client, instrument dumps, universe selection,
strike attachment, and the Navigator evaluator. Supertrend may be disabled and
Navigator still scans, persists evidence, and can surface Navigator-owned rows.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional

from app.core.logging import get_logger
from app.engines.navigator.gamma_activity import GammaContractInput
from app.engines.navigator.option_flow import ChainFlowSample, ContractFlowInput
from app.engines.sterling_kite_engine.schemas import EngineSignalRow
from app.services import db
from app.services.exchanges.kite import accounts as kite_accounts
from app.services.exchanges.kite.errors import KiteTokenError
from app.services.kite_engine import service as kite_service
from app.services.kite_engine import state as kite_state
from app.services.kite_engine.market_hours import is_market_open
from app.services.kite_engine.scanner import scanner
from app.services.kite_engine.universe import build_universe, select_scan_universe
from app.services.navigator import config_store, repository, service as nav_service
from app.services.navigator.calendar import IST
from app.services.navigator.chain_sampler import ChainSamplerCoordinator
from app.services.navigator.instrument_slice import InstrumentSliceIndex, OptionInstrumentSlice

log = get_logger(__name__)

SCAN_INTERVAL_S = 300


@dataclass
class NavigatorRuntimeStatus:
    scanning: bool = False
    scanning_label: str = ""
    cancelled: bool = False
    last_scan_ms: int = 0
    next_scan_ms: int = 0
    signal_count: int = 0
    scan_source: str = "spot"
    failures: list[dict] = field(default_factory=list)


@dataclass
class NavigatorSnapshot:
    rows: list[EngineSignalRow] = field(default_factory=list)
    generated_ms: int = 0


_status: dict[str, NavigatorRuntimeStatus] = {}
_snapshots: dict[str, NavigatorSnapshot] = {}
_activity: dict[str, list[dict]] = {}
_coordinators: dict[str, ChainSamplerCoordinator] = {}
_auto_running = False
_first_scan_done = False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _log(uid: str, kind: str, message: str) -> None:
    _activity.setdefault(uid, []).append({"ts_ms": _now_ms(), "kind": kind, "message": message})
    _activity[uid] = _activity[uid][-2000:]


def activity(uid: str, limit: int = 2000) -> list[dict]:
    return _activity.get(uid, [])[-limit:]


def status(uid: str) -> NavigatorRuntimeStatus:
    return _status.setdefault(uid, NavigatorRuntimeStatus())


def snapshot(uid: str) -> NavigatorSnapshot:
    snap = _snapshots.get(uid)
    if snap is not None:
        return snap
    snap = NavigatorSnapshot()
    raw = db.get_config(f"navigator_runtime_rows_{uid}") if db.is_available() else None
    if raw:
        try:
            data = json.loads(raw)
            snap.rows = [EngineSignalRow(**r) for r in data.get("rows", [])]
            snap.generated_ms = int(data.get("generated_ms") or 0)
        except Exception as exc:  # noqa: BLE001
            log.debug("navigator runtime cache hydrate failed for %s: %s", uid, exc)
    _snapshots[uid] = snap
    return snap


def is_auto_running() -> bool:
    return _auto_running


def cancel(uid: str) -> bool:
    st = status(uid)
    if not st.scanning:
        return False
    st.cancelled = True
    st.scanning = False
    st.scanning_label = "Cancelled"
    _log(uid, "info", "Navigator scan cancelled by user.")
    return True


def _save_snapshot(uid: str, rows: list[EngineSignalRow]) -> None:
    snap = snapshot(uid)
    snap.rows = rows
    snap.generated_ms = _now_ms()
    if db.is_available():
        try:
            db.set_config(
                f"navigator_runtime_rows_{uid}",
                json.dumps({"rows": [r.model_dump() for r in rows], "generated_ms": snap.generated_ms}),
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("navigator runtime cache persist failed for %s: %s", uid, exc)


def _account_scope(acct) -> str:
    return f"kite:{getattr(acct, 'id', '') or getattr(acct, 'user_id', '')}"


def _sampler_config(cfg):
    payload = cfg.flow.model_dump()
    payload["flow_sample_seconds"] = cfg.flow_sample_seconds
    return SimpleNamespace(**payload)


async def _instrument_dumps(client):
    return await asyncio.gather(
        client.search_instruments("", "NFO", limit=1_000_000),
        client.search_instruments("", "BFO", limit=1_000_000),
        client.search_instruments("", "NSE", limit=1_000_000),
        client.search_instruments("", "BSE", limit=1_000_000),
    )


def _resolve_nav_universe(nav_cfg, engine_cfg, full_universe):
    if nav_cfg.scan_scope_mode == "custom":
        return select_scan_universe(
            full_universe, indices=nav_cfg.scan_indices,
            stocks=nav_cfg.scan_stocks, all_stocks=nav_cfg.scan_all_stocks,
        )
    return select_scan_universe(
        full_universe, indices=engine_cfg.scan_indices,
        stocks=engine_cfg.scan_stocks, all_stocks=engine_cfg.scan_all_stocks,
    )


def _source_filter(items, source: str) -> list:
    # Navigator's price structure is always read from the underlying token. The
    # source controls option-chain/sampler coverage and surfaced row ownership.
    return list(items) if source in ("spot", "derivatives", "both", "confluence") else []


def _nearest_expiry(rows: list[dict], option_name: str, today=None) -> Optional[str]:
    today = today or datetime.now(IST).date()
    out = sorted({
        str(r.get("expiry") or "")[:10]
        for r in rows
        if str(r.get("name", "")).upper() == option_name.upper()
        and str(r.get("instrument_type", "")).upper() in ("CE", "PE")
        and str(r.get("expiry") or "")[:10] >= today.isoformat()
    })
    return out[0] if out else None


async def _on_sample(account_key: tuple, slice_: OptionInstrumentSlice, result, config_revision: int) -> None:
    account_scope, underlying, _expiry = account_key
    for s in result.snapshots:
        inst = s.instrument
        repository.insert_option_snapshot({
            "account_scope": account_scope, "underlying": underlying, "spot_token": None,
            "spot": slice_.atm_strike, "exchange": inst.exchange, "expiry": inst.expiry,
            "instrument_token": inst.token, "tradingsymbol": inst.tradingsymbol,
            "option_type": inst.option_type, "strike": inst.strike, "lot_size": inst.lot_size,
            "tick_size": inst.tick_size, "bid": s.bid, "ask": s.ask, "last_price": s.last_price,
            "mid": s.mid, "implied_volatility": s.implied_volatility,
            "open_interest": s.open_interest, "cumulative_volume": s.cumulative_volume,
            "exchange_timestamp_ms": s.exchange_timestamp_ms, "received_at_ms": s.received_at_ms,
            "sample_bucket_ms": s.received_at_ms, "quote_quality": s.quote_quality,
            "config_revision": config_revision,
        })


def _flow_history(account_scope: str, underlying: str, cfg) -> tuple[list[ChainFlowSample], list[GammaContractInput], Optional[dict]]:
    since = _now_ms() - int(max(cfg.flow.robust_window_samples, cfg.gamma.robust_window_samples) * cfg.flow_sample_seconds * 1000 * 2)
    rows = repository.fetch_latest_option_snapshots(account_scope, underlying, since_bucket_ms=since)
    if not rows:
        return [], [], None
    by_bucket: dict[int, list[dict]] = {}
    for r in rows:
        by_bucket.setdefault(int(r["sample_bucket_ms"]), []).append(r)
    history: list[ChainFlowSample] = []
    prev_by_token: dict[int, dict] = {}
    latest_contracts: list[GammaContractInput] = []
    latest_expiry: Optional[str] = None
    for bucket in sorted(by_bucket):
        sample_rows = by_bucket[bucket]
        strikes = sorted({float(r["strike"]) for r in sample_rows if float(r["strike"] or 0) > 0})
        if not strikes:
            continue
        step = min([b - a for a, b in zip(strikes, strikes[1:]) if b > a] or [1.0])
        atm = strikes[len(strikes) // 2]
        contracts: list[ContractFlowInput] = []
        gamma_contracts: list[GammaContractInput] = []
        for r in sample_rows:
            token = int(r["instrument_token"])
            prev = prev_by_token.get(token)
            mid = float(r["mid"] or 0.0)
            prev_mid = float(prev["mid"]) if prev and prev.get("mid") else None
            delta_volume = None
            if prev is not None and r.get("cumulative_volume") is not None and prev.get("cumulative_volume") is not None:
                dv = int(r["cumulative_volume"]) - int(prev["cumulative_volume"])
                delta_volume = dv if dv >= 0 else None
            delta_oi = None
            if prev is not None and r.get("open_interest") is not None and prev.get("open_interest") is not None:
                delta_oi = int(r["open_interest"]) - int(prev["open_interest"])
            spread = None
            if mid > 0 and r.get("bid") and r.get("ask"):
                spread = (float(r["ask"]) - float(r["bid"])) / mid
            contracts.append(ContractFlowInput(
                token=token, option_type=str(r["option_type"]), strike=float(r["strike"]),
                mid=mid, prev_mid=prev_mid, delta_volume=delta_volume,
                delta_oi=delta_oi, spread_pct=spread,
            ))
            sign = 0 if prev_mid is None or mid == prev_mid else (1 if mid > prev_mid else -1)
            gamma_contracts.append(GammaContractInput(
                token=token, strike=float(r["strike"]), lot_size=int(r["lot_size"] or 1),
                iv=r.get("implied_volatility"), delta_volume=delta_volume, price_return_sign=sign,
            ))
            prev_by_token[token] = r
            latest_expiry = str(r.get("expiry") or "")[:10]
        history.append(ChainFlowSample(sample_ms=bucket, atm_strike=atm, strike_step=step, contracts=contracts))
        latest_contracts = gamma_contracts
    gamma_context = None
    if latest_expiry and history:
        try:
            gamma_context = {
                "spot": float(history[-1].atm_strike),
                "quote_ts_ms": int(history[-1].sample_ms),
                "expiry_date": datetime.strptime(latest_expiry, "%Y-%m-%d").date(),
                "risk_free_rate": cfg.gamma.risk_free_rate,
                "dividend_yield": cfg.gamma.dividend_yield,
                "profile_history": [],
                "chain_quality": "ok",
            }
        except ValueError:
            gamma_context = None
    return history, latest_contracts, gamma_context


def _component_status_from_decision(decision):
    out = {}
    for name, ev in (
        ("avwap", decision.avwap),
        ("ranges", None),
        ("volatility", decision.volatility),
        ("option_flow", decision.option_flow),
        ("gamma", decision.gamma),
    ):
        if name == "ranges":
            out[name] = nav_service.ComponentStatus(name=name, quality="ok", last_updated_ms=decision.generated_at_ms, reason_codes=["OK"])
        elif ev is not None:
            out[name] = nav_service.ComponentStatus(name=name, quality=ev.quality, last_updated_ms=ev.observed_at_ms, reason_codes=ev.reason_codes)
    return out


async def _start_samplers(client, uid: str, acct, items, nfo_rows, bfo_rows, record) -> None:
    if not (record.config.flow.enabled or record.config.gamma.enabled):
        return
    account_scope = _account_scope(acct)
    coord = _coordinators.get(account_scope)
    if coord is None:
        coord = ChainSamplerCoordinator(
            quote_fetcher=client.get_quote,
            instrument_index=InstrumentSliceIndex(client._instruments),
            on_sample=lambda key, sl, res, _now: _on_sample(key, sl, res, record.revision),
        )
        _coordinators[account_scope] = coord
    for item in items:
        rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
        expiry = _nearest_expiry(rows, item.tradingsymbol)
        if not expiry:
            continue

        async def spot_provider(token=item.token):
            candles = await nav_service._fetch_candles_for_navigator(client, token, 4)
            return float(candles[-1].close) if candles else 0.0

        coord.ensure_started(
            account_scope=account_scope, underlying=item.name, exchange=item.option_exchange,
            expiry=expiry, spot_provider=spot_provider, config=_sampler_config(record.config),
        )
    nav_service.set_sampler_running(uid, any(
        coord.is_running(account_scope, item.name, _nearest_expiry(nfo_rows if item.option_exchange == "NFO" else bfo_rows, item.tradingsymbol) or "")
        for item in items
    ))


def _source_modes_enabled(source: str) -> tuple[bool, bool]:
    return source in ("spot", "both", "confluence"), source in ("derivatives", "both", "confluence")


async def scan_user(client, uid: str, *, interval_s: float = SCAN_INTERVAL_S, acct=None) -> int:
    record = config_store.get(uid, default_underlyings=kite_state.get_config(uid).scan_indices)
    if not record.config.enabled:
        return 0
    st = status(uid)
    if st.scanning:
        _log(uid, "info", "Navigator scan skipped: another Navigator scan is already running.")
        return st.signal_count
    st.scanning = True
    st.cancelled = False
    st.failures = []
    st.scan_source = record.config.scan_source
    _log(uid, "scan_start", "Navigator scan started.")
    try:
        nfo, bfo, nse, bse = await _instrument_dumps(client)
        full = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
        engine_cfg = kite_state.get_config(uid)
        nav_universe = _source_filter(_resolve_nav_universe(record.config, engine_cfg, full), record.config.scan_source)
        await _start_samplers(client, uid, acct or kite_accounts.get_active(uid), nav_universe, nfo, bfo, record)
        rows: list[EngineSignalRow] = []
        place_cb = kite_service._make_place_cb(client, uid) if (
            engine_cfg.auto_execute and record.config.signal_origination == "full"
            and record.config.auto_execute_originated and record.calibration_readiness == "ready"
        ) else None
        _log(uid, "info", f"Navigator plan: {len(nav_universe)} instruments using {record.config.scan_source}.")
        account_scope = _account_scope(acct or kite_accounts.get_active(uid))
        use_flow, use_gamma = _source_modes_enabled(record.config.scan_source)
        for item in nav_universe:
            if st.cancelled:
                break
            st.scanning_label = item.name
            try:
                chain_history, gamma_contracts, gamma_context = _flow_history(account_scope, item.name, record.config)
                before = len(rows)
                kwargs = {}
                if use_flow and chain_history:
                    kwargs["flow_history"] = chain_history
                    kwargs["flow_not_applicable"] = False
                    kwargs["flow_required"] = item.is_index and record.config.flow.require_for_index_gate
                if use_gamma and gamma_context is not None:
                    kwargs["gamma_contracts"] = gamma_contracts
                    kwargs["gamma_context"] = gamma_context
                    kwargs["gamma_required"] = record.config.gamma.required_for_gate
                await nav_service.run_navigator_pass(
                    client, uid, rows, engine_config_payload=engine_cfg.model_dump(mode="json"),
                    default_underlyings=engine_cfg.scan_indices,
                    underlying_tokens={item.name: item.token},
                    universe=[item], nfo_rows=nfo, bfo_rows=bfo,
                    moneyness=engine_cfg.strike_moneyness,
                    expiry_types=engine_cfg.scan_expiries,
                    expiry_types_indices=engine_cfg.scan_expiries_indices,
                    expiry_types_stocks=engine_cfg.scan_expiries_stocks,
                    evaluation_kwargs=kwargs,
                )
                for row in rows[before:]:
                    if row.navigator is not None:
                        nav_service.note_component_status(uid, _component_status_from_decision(row.navigator))
                    if place_cb and row.source == "navigator" and row.is_fresh and row.legs and row.navigator and row.navigator.execution_eligible:
                        await place_cb(row, item)
                _save_snapshot(uid, rows)
            except Exception as exc:  # noqa: BLE001
                st.failures.append({"underlying": item.name, "error": str(exc)})
                _log(uid, "error", f"{item.name}: {exc}")
                log.warning("navigator independent scan failed for %s/%s: %s", uid, item.name, exc)
        live = sum(1 for r in rows if r.is_active or r.is_fresh)
        st.last_scan_ms = _now_ms()
        st.next_scan_ms = st.last_scan_ms + int(interval_s * 1000)
        st.signal_count = live
        _save_snapshot(uid, rows)
        _log(uid, "scan_done", f"Navigator scan complete: {live} live signal(s), {len(st.failures)} failure(s).")
        return live
    finally:
        st.scanning = False
        st.scanning_label = ""


async def _scan_all_connected_once(interval_s: float) -> None:
    global _first_scan_done
    try:
        accts = [a for a in kite_accounts._load_from_db() if a.connected]
    except Exception as exc:  # noqa: BLE001
        log.warning("navigator auto-scan account load failed: %s", exc)
        return
    scanned = False
    for acct in accts:
        try:
            record = config_store.get(acct.user_id, default_underlyings=kite_state.get_config(acct.user_id).scan_indices)
            if not record.config.enabled:
                continue
            client = await kite_accounts.acquire_client(acct)
            try:
                await client.get_profile()
            except KiteTokenError:
                kite_accounts.clear_session(acct.user_id, acct.id)
                await kite_accounts.release_client(acct.id)
                _log(acct.user_id, "info", "Kite session expired; Navigator auto-scan paused.")
                continue
            await scan_user(client, acct.user_id, interval_s=interval_s, acct=acct)
            scanned = True
        except Exception as exc:  # noqa: BLE001
            log.warning("navigator auto-scan failed for %s: %s", getattr(acct, "user_id", "?"), exc)
    if scanned:
        _first_scan_done = True


async def retention_cleanup_once() -> None:
    now = _now_ms()
    try:
        for row in repository.fetch_config_audit("", limit=0):
            row
    except Exception:
        pass
    # Use the most conservative defaults when no user config is loaded.
    repository.delete_old_option_snapshots(now - 30 * 24 * 60 * 60 * 1000)
    repository.delete_old_feature_snapshots(now - 365 * 24 * 60 * 60 * 1000)


async def auto_scan_loop(interval_s: float = SCAN_INTERVAL_S) -> None:
    global _auto_running
    _auto_running = True
    log.info("navigator auto-scan loop started (every %ss)", interval_s)
    try:
        while True:
            try:
                if _first_scan_done and not is_market_open():
                    await asyncio.sleep(30)
                    continue
                await _scan_all_connected_once(interval_s)
                try:
                    await retention_cleanup_once()
                except Exception as exc:  # noqa: BLE001
                    log.debug("navigator retention cleanup failed: %s", exc)
            except Exception as exc:  # noqa: BLE001
                log.warning("navigator auto-scan iteration error: %s", exc)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        raise
    finally:
        _auto_running = False
        for coord in list(_coordinators.values()):
            await coord.stop_all()
        _coordinators.clear()
