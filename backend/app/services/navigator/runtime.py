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
from app.engines.navigator.gamma_activity import (
    GammaContractInput,
    classify_expiry_profile,
    compute_gamma_sample,
    fractional_time_to_expiry,
)
from app.engines.navigator.option_flow import ChainFlowSample, ContractFlowInput
from app.engines.navigator.schemas import NavigatorConfigModel
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
from app.services.navigator.calendar import IST, expiry_close_ist
from app.services.navigator.chain_sampler import ChainSamplerCoordinator
from app.services.navigator.instrument_slice import InstrumentSliceIndex, OptionInstrumentSlice

log = get_logger(__name__)

SCAN_INTERVAL_S = 300
#: Retention windows are days wide, so trimming them on every 5-minute scan
#: would be pure churn. Once an hour is plenty.
RETENTION_INTERVAL_MS = 60 * 60 * 1000


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
_user_sampler_keys: dict[str, set[tuple[str, str, str]]] = {}
_sampler_users: dict[tuple[str, str, str], set[str]] = {}
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
            nav_service.hydrate_decision_cache_from_rows(uid, snap.rows)
        except Exception as exc:  # noqa: BLE001
            log.debug("navigator runtime cache hydrate failed for %s: %s", uid, exc)
    _snapshots[uid] = snap
    return snap


def is_auto_running() -> bool:
    return _auto_running


def cancel(uid: str) -> bool:
    """Ask the running scan to stop at its next instrument boundary.

    Only raises the flag — it must NOT clear `scanning`. The scan loop owns
    that (in its `finally`), and clearing it here while the loop is still
    winding down would let a concurrent `scan_user` walk straight past the
    "already scanning" guard, leaving two scans writing one user's board."""
    st = status(uid)
    if not st.scanning:
        return False
    st.cancelled = True
    st.scanning_label = "Cancelling…"
    _log(uid, "info", "Navigator scan cancelled by user.")
    return True


def _save_snapshot(uid: str, rows: list[EngineSignalRow], *, persist: bool = True) -> None:
    """Publish `rows` as the user's current board.

    The in-memory update is always immediate so the UI sees a scan progress.
    `persist=False` skips the DB write: persisting is a full re-serialization of
    every row so far, so doing it per instrument makes a scan quadratic in the
    universe size (a full F&O scan is ~200 instruments). Mid-scan durability
    buys nothing anyway — a scan that dies part-way is re-run from scratch, and
    the surviving prior rows are preserved by `_merge_with_lifecycle`."""
    snap = snapshot(uid)
    snap.rows = rows
    snap.generated_ms = _now_ms()
    if not persist or not db.is_available():
        return
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


def _row_key(row: EngineSignalRow) -> tuple[str, str, int, str, int]:
    return (
        row.source or "spot",
        row.underlying,
        int(row.token),
        row.direction,
        int(row.timestamp_ms),
    )


def _row_lifecycle_key(row: EngineSignalRow) -> tuple[str, int, str]:
    return (row.underlying, int(row.token), row.direction)


def _merge_unique_rows(rows: list[EngineSignalRow]) -> list[EngineSignalRow]:
    merged: dict[tuple[str, str, int, str, int], EngineSignalRow] = {}
    for row in rows:
        key = _row_key(row)
        existing = merged.get(key)
        if existing is None:
            merged[key] = row
            continue
        existing_rank = (1 if existing.is_fresh else 0, 1 if existing.is_active else 0)
        row_rank = (1 if row.is_fresh else 0, 1 if row.is_active else 0)
        if row_rank >= existing_rank:
            merged[key] = row
    return sorted(merged.values(), key=lambda r: (r.is_fresh or r.is_active, r.timestamp_ms), reverse=True)


def _merge_with_lifecycle(
    uid: str, previous_rows: list[EngineSignalRow], current_rows: list[EngineSignalRow],
    completed_underlyings: set[str],
) -> list[EngineSignalRow]:
    """fresh/active rows from this scan plus ended rows from prior scans.

    Only underlyings that completed successfully are allowed to end prior
    Navigator setups. Cancelled or failed instruments keep their previous row
    state so a partial scan cannot accidentally erase the board.
    """
    merged = {_row_key(row): row for row in _merge_unique_rows(current_rows)}
    live_current = {
        _row_lifecycle_key(row)
        for row in current_rows
        if row.source == "navigator" and (row.is_fresh or row.is_active)
    }
    for prev in previous_rows:
        if prev.source != "navigator":
            continue
        key = _row_lifecycle_key(prev)
        if key in live_current:
            continue
        if prev.underlying in completed_underlyings:
            ended = prev.model_copy(deep=True, update={"is_fresh": False, "is_active": False})
            nav_service.forget_decision(
                uid, underlying=ended.underlying, token=ended.token, direction=ended.direction,
            )
            merged[_row_key(ended)] = ended
        else:
            merged.setdefault(_row_key(prev), prev)
    return _merge_unique_rows(list(merged.values()))


def _entry_delay_satisfied(cfg, now: Optional[datetime] = None) -> bool:
    delay = int(getattr(cfg, "entry_delay_after_open_minutes", 0) or 0)
    if delay <= 0:
        return True
    now = now or datetime.now(IST)
    session_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    return now >= session_open + timedelta(minutes=delay)


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
            stock_contracts=getattr(nav_cfg, "scan_stock_contracts", True),
        )
    return select_scan_universe(
        full_universe, indices=engine_cfg.scan_indices,
        stocks=engine_cfg.scan_stocks, all_stocks=engine_cfg.scan_all_stocks,
        stock_contracts=getattr(engine_cfg, "scan_stock_contracts", True),
    )


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


def _flow_history(account_scope: str, underlying: str, cfg) -> tuple[list[ChainFlowSample], list[GammaContractInput], Optional[dict], str]:
    since = _now_ms() - int(max(cfg.flow.robust_window_samples, cfg.gamma.robust_window_samples) * cfg.flow_sample_seconds * 1000 * 2)
    rows = repository.fetch_latest_option_snapshots(account_scope, underlying, since_bucket_ms=since)
    if not rows:
        return [], [], None, "unavailable"
    by_bucket: dict[int, list[dict]] = {}
    for r in rows:
        by_bucket.setdefault(int(r["sample_bucket_ms"]), []).append(r)
    history: list[ChainFlowSample] = []
    prev_by_token: dict[int, dict] = {}
    latest_contracts: list[GammaContractInput] = []
    latest_expiry: Optional[str] = None
    latest_bucket = max(by_bucket)
    latest_rows = by_bucket[latest_bucket]
    chain_quality = "ok"
    if (_now_ms() - latest_bucket) / 1000.0 > cfg.flow.max_quote_age_seconds:
        chain_quality = "unavailable"
    strike_radius = cfg.flow.dynamic_strike_radius if cfg.flow.mode == "dynamic" else cfg.flow.broad_strike_radius
    min_expected_contracts = max(1, (2 * int(strike_radius) + 1) * 2)
    if len(latest_rows) / min_expected_contracts < cfg.flow.min_chain_completeness:
        chain_quality = "degraded" if chain_quality == "ok" else chain_quality
    if any(str(r.get("quote_quality") or "ok") != "ok" for r in latest_rows):
        chain_quality = "degraded" if chain_quality == "ok" else chain_quality
    gamma_history: list[tuple[int, float, list[GammaContractInput]]] = []
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
            comparable = False
            if prev is not None:
                gap_s = (int(r["sample_bucket_ms"]) - int(prev["sample_bucket_ms"])) / 1000.0
                curr_day = datetime.fromtimestamp(int(r["sample_bucket_ms"]) / 1000.0, tz=IST).date()
                prev_day = datetime.fromtimestamp(int(prev["sample_bucket_ms"]) / 1000.0, tz=IST).date()
                comparable = gap_s <= cfg.flow.max_sample_gap_seconds and curr_day == prev_day
                if not comparable:
                    chain_quality = "degraded" if chain_quality == "ok" else chain_quality
            delta_volume = None
            if comparable and r.get("cumulative_volume") is not None and prev.get("cumulative_volume") is not None:
                dv = int(r["cumulative_volume"]) - int(prev["cumulative_volume"])
                delta_volume = dv if dv >= 0 else None
                if dv < 0:
                    chain_quality = "degraded" if chain_quality == "ok" else chain_quality
            delta_oi = None
            if comparable and r.get("open_interest") is not None and prev.get("open_interest") is not None:
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
        gamma_history.append((bucket, atm, gamma_contracts))
    gamma_context = None
    if latest_expiry and history:
        try:
            expiry_date = datetime.strptime(latest_expiry, "%Y-%m-%d").date()
            latest_profile = classify_expiry_profile(
                int(history[-1].sample_ms), expiry_date, cfg.gamma.expiry_profile_start_ist,
            )
            profile_history: list[float] = []
            for bucket, spot, contracts in gamma_history[:-1]:
                if classify_expiry_profile(int(bucket), expiry_date, cfg.gamma.expiry_profile_start_ist) != latest_profile:
                    continue
                expiry_close_ts_ms = int(expiry_close_ist(expiry_date).timestamp() * 1000)
                T = fractional_time_to_expiry(int(bucket), expiry_close_ts_ms)
                sample = compute_gamma_sample(
                    contracts, spot=spot, T=T, risk_free_rate=cfg.gamma.risk_free_rate,
                    dividend_yield=cfg.gamma.dividend_yield, min_iv=cfg.gamma.min_iv,
                    max_iv=cfg.gamma.max_iv,
                )
                if sample.valid_contracts > 0:
                    profile_history.append(sample.gross_gamma_activity)
            gamma_context = {
                "spot": float(history[-1].atm_strike),
                "quote_ts_ms": int(history[-1].sample_ms),
                "expiry_date": expiry_date,
                "risk_free_rate": cfg.gamma.risk_free_rate,
                "dividend_yield": cfg.gamma.dividend_yield,
                "profile_history": profile_history[-cfg.gamma.robust_window_samples:],
            }
        except ValueError:
            gamma_context = None
    return history, latest_contracts, gamma_context, chain_quality


async def _current_client(acct):
    """The account's live client, resolved fresh at call time.

    Never capture a client in a long-lived closure. `acquire_client` rebuilds
    (and closes) the cached client whenever the access token rotates, so a
    captured one goes dead the first time the user re-logs in. Resolving per
    call is a dict lookup on the warm path."""
    return await kite_accounts.acquire_client(acct)


async def _start_samplers(client, uid: str, acct, items, nfo_rows, bfo_rows, record) -> None:
    if record.config.scan_source == "spot" or not (record.config.flow.enabled or record.config.gamma.enabled):
        await stop_user_samplers(uid)
        return
    account_scope = _account_scope(acct)
    revision = record.revision
    coord = _coordinators.get(account_scope)
    sink = lambda key, sl, res, _now: _on_sample(key, sl, res, revision)  # noqa: E731
    index = InstrumentSliceIndex(client._instruments)
    if coord is None:
        coord = ChainSamplerCoordinator(
            quote_fetcher=client.get_quote, instrument_index=index, on_sample=sink,
        )
        _coordinators[account_scope] = coord
    else:
        # A cached coordinator outlives the client and the config revision it
        # was built from — re-point it at the current ones rather than letting
        # its pollers keep calling a closed client and stamping snapshots with
        # a revision that has since moved on.
        coord.rebind(quote_fetcher=client.get_quote, instrument_index=index, on_sample=sink)
    desired: set[tuple[str, str, str]] = set()
    try:
        for item in items:
            rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
            expiry = _nearest_expiry(rows, item.tradingsymbol)
            if not expiry:
                continue
            key = (account_scope, item.name, expiry)
            desired.add(key)
            _sampler_users.setdefault(key, set()).add(uid)

            # `acct` is a stable record; the client behind it is resolved per call
            # so this poller survives a re-login (it outlives any single scan).
            async def spot_provider(token=item.token, account=acct):
                candles = await nav_service._fetch_candles_for_navigator(
                    await _current_client(account), token, 4)
                return float(candles[-1].close) if candles else 0.0

            coord.ensure_started(
                account_scope=account_scope, underlying=item.name, exchange=item.option_exchange,
                expiry=expiry, spot_provider=spot_provider, config=_sampler_config(record.config),
            )
    finally:
        # Record what this user claimed even if a start failed part-way. The
        # claim in `_sampler_users` is what the next pass diffs against to shut
        # pollers down; losing it here would orphan them until process exit.
        _user_sampler_keys[uid] = desired
    for key in _sampler_users_to_release(uid, desired):
        account_scope_, underlying, expiry = key
        old_coord = _coordinators.get(account_scope_)
        if old_coord is not None:
            await old_coord.stop(account_scope_, underlying, expiry)
    nav_service.set_sampler_running(uid, any(coord.is_running(*key) for key in desired))


def _sampler_users_to_release(uid: str, keep: set[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Drop `uid`'s claim on every sampler key it no longer wants, and return
    the keys that now have no claimants left — those are the ones safe to stop.

    Samplers are shared per (account, underlying, expiry) across users, so one
    user losing interest must never stop a poller another user is still reading.
    """
    release: list[tuple[str, str, str]] = []
    for key in set(_sampler_users) - keep:
        users = _sampler_users.get(key)
        if users is None:
            continue
        if uid not in users:
            continue
        users.discard(uid)
        if users:
            continue
        _sampler_users.pop(key, None)
        release.append(key)
    return release


async def stop_user_samplers(uid: str) -> None:
    """Release every sampler this user claims, stopping the ones nobody else wants."""
    _user_sampler_keys.pop(uid, None)
    for account_scope, underlying, expiry in _sampler_users_to_release(uid, set()):
        coord = _coordinators.get(account_scope)
        if coord is not None:
            await coord.stop(account_scope, underlying, expiry)
    nav_service.set_sampler_running(uid, False)


def _source_uses_chain(source: str) -> bool:
    """Whether this scan source needs option-chain evidence at all.

    Navigator always reads price structure from the underlying's own token —
    the source only decides whether the option chain is sampled and fed to the
    flow/gamma components on top of that."""
    return source in ("derivatives", "both", "confluence")


async def scan_user(client, uid: str, *, interval_s: float = SCAN_INTERVAL_S, acct=None) -> int:
    record = config_store.get(uid, default_underlyings=kite_state.get_config(uid).scan_indices)
    if not record.config.enabled:
        await stop_user_samplers(uid)
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
    previous_rows = snapshot(uid).rows
    nav_service.hydrate_decision_cache_from_rows(uid, previous_rows)
    completed_underlyings: set[str] = set()
    try:
        nfo, bfo, nse, bse = await _instrument_dumps(client)
        full = build_universe(nfo_instruments=nfo, bfo_instruments=bfo, equities=nse + bse)
        engine_cfg = kite_state.get_config(uid)
        nav_universe = _resolve_nav_universe(record.config, engine_cfg, full)
        await _start_samplers(client, uid, acct or kite_accounts.get_active(uid), nav_universe, nfo, bfo, record)
        rows: list[EngineSignalRow] = []
        # The ONLY place a Navigator-originated order can be submitted (the Kite
        # engine's scan deliberately passes `include_origination=False` and has
        # no auto-exec block of its own). Reuses the base engine's central
        # `_make_place_cb` gate so originated rows go through exactly the same
        # sizing/stop/paper-vs-live path as every other row.
        #
        # `engine_cfg.auto_execute` is the account's master MANUAL/AUTO switch,
        # not a SuperTrend-specific flag — Navigator can scan with the
        # SuperTrend engine off, but it still will not place orders while the
        # account is in MANUAL. Each row is then re-checked individually below
        # via `check_originated_execution_eligible`.
        place_cb = kite_service._make_place_cb(client, uid) if (
            engine_cfg.auto_execute and record.config.signal_origination == "full"
            and record.config.auto_execute_originated and record.calibration_readiness == "ready"
        ) else None
        _log(uid, "info", f"Navigator plan: {len(nav_universe)} instruments using {record.config.scan_source}.")
        account_scope = _account_scope(acct or kite_accounts.get_active(uid))
        uses_chain = _source_uses_chain(record.config.scan_source)
        use_flow = uses_chain and record.config.flow.enabled
        use_gamma = uses_chain and record.config.gamma.enabled
        for item in nav_universe:
            if st.cancelled:
                break
            st.scanning_label = item.name
            try:
                chain_history, gamma_contracts, gamma_context, chain_quality = _flow_history(account_scope, item.name, record.config)
                before = len(rows)
                kwargs = {}
                if use_flow:
                    kwargs["flow_required"] = item.is_index and record.config.flow.require_for_index_gate
                    kwargs["flow_not_applicable"] = False
                    kwargs["chain_quality"] = chain_quality
                if use_flow and chain_history:
                    kwargs["flow_history"] = chain_history
                if use_gamma:
                    kwargs["gamma_required"] = record.config.gamma.required_for_gate
                    kwargs["chain_quality"] = chain_quality
                if use_gamma and gamma_context is not None:
                    kwargs["gamma_contracts"] = gamma_contracts
                    kwargs["gamma_context"] = gamma_context
                await nav_service.run_navigator_pass(
                    client, uid, rows, engine_config_payload=engine_cfg.model_dump(mode="json"),
                    default_underlyings=engine_cfg.scan_indices,
                    underlying_tokens={item.name: item.token},
                    universe=[item], nfo_rows=nfo, bfo_rows=bfo,
                    # Navigator's own contract coverage when it has been given
                    # one, otherwise the Kite engine's. Before these fields
                    # existed the engine's ladder was used unconditionally, so
                    # a user editing strike coverage "for SuperTrend" silently
                    # moved Navigator too, with no way to separate them.
                    moneyness=(record.config.strike_moneyness
                               if record.config.strike_moneyness is not None
                               else engine_cfg.strike_moneyness),
                    expiry_types=engine_cfg.scan_expiries,
                    expiry_types_indices=(record.config.scan_expiries_indices
                                          if record.config.scan_expiries_indices is not None
                                          else engine_cfg.scan_expiries_indices),
                    expiry_types_stocks=(record.config.scan_expiries_stocks
                                         if record.config.scan_expiries_stocks is not None
                                         else engine_cfg.scan_expiries_stocks),
                    evaluation_kwargs=kwargs,
                )
                for row in rows[before:]:
                    if row.navigator is not None:
                        nav_service.note_component_status(uid, nav_service.component_statuses_from_decision(row.navigator))
                    if place_cb and row.source == "navigator" and row.is_fresh and row.legs and row.navigator and row.navigator.execution_eligible:
                        eligible, reason = nav_service.check_originated_execution_eligible(
                            uid, row, default_underlyings=engine_cfg.scan_indices,
                        )
                        if not eligible:
                            _log(uid, "order_blocked", f"{row.underlying}: Navigator auto-entry blocked ({reason}).")
                            continue
                        if not _entry_delay_satisfied(record.config):
                            _log(uid, "order_blocked", f"{row.underlying}: Navigator auto-entry blocked (ENTRY_DELAY).")
                            continue
                        await place_cb(row, item)
                completed_underlyings.add(item.name)
                # In-memory only — the durable write happens once at the end.
                _save_snapshot(
                    uid, _merge_with_lifecycle(uid, previous_rows, rows, completed_underlyings),
                    persist=False,
                )
            except Exception as exc:  # noqa: BLE001
                st.failures.append({"underlying": item.name, "error": str(exc)})
                _log(uid, "error", f"{item.name}: {exc}")
                log.warning("navigator independent scan failed for %s/%s: %s", uid, item.name, exc)
        rows = _merge_with_lifecycle(uid, previous_rows, rows, completed_underlyings)
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


async def _scan_all_connected_once(interval_s: float) -> list[str]:
    """Scan every connected account whose user has Navigator enabled.

    Returns the user ids actually scanned, so the caller can size retention to
    exactly those users' configured windows."""
    global _first_scan_done
    scanned_uids: list[str] = []
    try:
        accts = [a for a in kite_accounts._load_from_db() if a.connected]
    except Exception as exc:  # noqa: BLE001
        log.warning("navigator auto-scan account load failed: %s", exc)
        return scanned_uids
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
            scanned_uids.append(acct.user_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("navigator auto-scan failed for %s: %s", getattr(acct, "user_id", "?"), exc)
    if scanned_uids:
        _first_scan_done = True
    return scanned_uids


async def retention_cleanup_once(*, raw_days: int, feature_days: int) -> None:
    """Trim stored chain/feature history to the configured windows.

    Delegates to `repository.run_retention`, which deletes in bounded batches
    and reports what it removed. Called at most hourly — the windows are days
    wide, so running it on every 5-minute scan would be pure churn."""
    repository.run_retention(raw_days=raw_days, feature_days=feature_days, now_ms=_now_ms())


def _widest_retention(user_ids: list[str]) -> tuple[int, int]:
    """The most generous retention any scanning user asked for.

    Retention is per-user config but the tables are shared, so a single pass
    has to keep whatever the longest-retaining user still needs. Falls back to
    the schema defaults when no user config can be read."""
    defaults = NavigatorConfigModel()
    raw, feature = defaults.retention_raw_days, defaults.retention_features_days
    for uid in user_ids:
        try:
            cfg = config_store.get(
                uid, default_underlyings=kite_state.get_config(uid).scan_indices).config
        except Exception:  # noqa: BLE001
            continue
        raw = max(raw, cfg.retention_raw_days)
        feature = max(feature, cfg.retention_features_days)
    return raw, feature


async def auto_scan_loop(interval_s: float = SCAN_INTERVAL_S) -> None:
    global _auto_running
    _auto_running = True
    last_retention_ms = 0
    log.info("navigator auto-scan loop started (every %ss)", interval_s)
    try:
        while True:
            try:
                if _first_scan_done and not is_market_open():
                    await asyncio.sleep(30)
                    continue
                scanned_uids = await _scan_all_connected_once(interval_s)
                if scanned_uids and _now_ms() - last_retention_ms >= RETENTION_INTERVAL_MS:
                    last_retention_ms = _now_ms()
                    raw_days, feature_days = _widest_retention(scanned_uids)
                    try:
                        await retention_cleanup_once(raw_days=raw_days, feature_days=feature_days)
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
