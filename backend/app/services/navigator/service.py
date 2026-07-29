"""Navigator runtime service: per-user decision cache, the one safe
join point the scanner calls, the central-gate eligibility recheck, and
the price-feature-only evaluation pipeline (spec §16, §18).

This module owns ALL Navigator in-process mutable runtime state — nothing
else keeps its own copy. All state here is a CACHE: it is always safe to
drop and rebuild (e.g. on process restart), and restart never marks old
evidence as current (spec §18.3).

**Price-only mode.** Building live option-chain capture against a real
Kite account is the next integration step outside this session (it needs
a funded/authenticated account to exercise end-to-end). Per the spec's own
validation sequence (§19.3, step 1: "Run price-only walk-forward tests...
before enabling raw chain capture"), `evaluate_signal` runs correctly today
with `chain_history=None` / `gamma_context=None` — flow and gamma simply
report `quality="unavailable"` with `CHAIN_UNAVAILABLE`, exactly the state
the spec expects before chain capture is turned on.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Optional

from app.core.logging import get_logger
from app.engines.navigator import avwap, projected_ranges, volatility
from app.engines.navigator.fusion import FusionInputs, fuse
from app.engines.navigator.gamma_activity import GammaContractInput, evaluate_gamma_activity
from app.engines.navigator.option_flow import ChainFlowSample, evaluate_option_flow
from app.engines.navigator.quality import CandleValidationError, ValidatedCandles, validate_candles
from app.engines.navigator.schemas import (
    BaseSignalEvidence,
    DirectionalEvidence,
    NavigatorConfigModel,
    NavigatorDecision,
)
from app.engines.sterling_kite_engine.schemas import AlignmentChip, EngineSignalRow
from app.schemas.market import Candle
from app.services import db
from app.services.navigator import config_store, repository
from app.services.navigator.adapters import (
    AdapterError,
    KiteTripleSupertrendAdapter,
    is_origination_decision,
    kite_config_revision,
    synthetic_origination_base,
)
from app.services.navigator.calendar import IST
from app.services.navigator.status import ComponentStatus, NavigatorStatusSnapshot, build_status_snapshot

log = get_logger(__name__)

MODEL_VERSIONS = {
    "avwap": avwap.MODEL_VERSION,
    "ranges": projected_ranges.MODEL_VERSION,
    "volatility": volatility.MODEL_VERSION,
}

# uid -> {(underlying, token, direction): NavigatorDecision}
_decision_cache: dict[str, dict[tuple, NavigatorDecision]] = {}
# uid -> {component: ComponentStatus}
_component_status: dict[str, dict[str, ComponentStatus]] = {}
# uid -> bool — set True once a sampler/evaluation pass has actually run for this user
_sampler_running: dict[str, bool] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


# ─────────────────────────────────────────────────────────────────────────
# Decision cache + the scanner join point
# ─────────────────────────────────────────────────────────────────────────

def cache_decision(uid: str, *, underlying: str, token: int, direction: str, decision: NavigatorDecision) -> None:
    _decision_cache.setdefault(uid, {})[(underlying, token, direction)] = decision
    _sampler_running[uid] = True


def get_cached_decision(uid: str, *, underlying: str, token: int, direction: str) -> Optional[NavigatorDecision]:
    return _decision_cache.get(uid, {}).get((underlying, token, direction))


def get_cached_decisions_for_underlying(uid: str, underlying: str) -> list[NavigatorDecision]:
    return [d for (u, _tok, _dir), d in _decision_cache.get(uid, {}).items() if u == underlying]


def clear_cache(uid: str) -> None:
    """Test/reset hook — never called from production request paths."""
    _decision_cache.pop(uid, None)
    _component_status.pop(uid, None)
    _sampler_running.pop(uid, None)


def attach_to_rows(uid: str, rows: list[EngineSignalRow], *, default_underlyings: list[str]) -> list[EngineSignalRow]:
    """Synchronous, cache-only join — NEVER fetches live data or makes a
    broker call. Safe to call from the scanner's hot path once per scan.
    A disabled config makes this an exact no-op (`row.navigator` stays
    `None`, matching the field's default for every existing cached row)."""
    record = config_store.get(uid, default_underlyings=default_underlyings)
    if not record.config.enabled:
        return rows
    for row in rows:
        if not (row.is_fresh or row.is_active):
            continue
        decision = get_cached_decision(uid, underlying=row.underlying, token=row.token, direction=row.direction)
        if decision is not None and decision.config_revision == record.revision:
            row.navigator = decision
    return rows


async def _fetch_candles_for_navigator(client, token: int, lookback_bars: int = 320) -> list[Candle]:
    """A fresh, independent 1H candle fetch for Navigator's price-only
    pipeline — deliberately NOT reusing the scanner's internal cache, so
    this stays a separate, isolated evaluator (matching the "separate,
    independent" design already used for chain sampling). Uses the same
    raw `get_historical` primitive and timestamp parsing the scanner itself
    relies on, and applies the same "drop the still-forming bar" rule."""
    from app.services.exchanges.kite.client import _parse_kite_ts
    from app.services.kite_engine.scanner import drop_forming

    now = datetime.now(IST)
    days_needed = max(2, int(lookback_bars / 6) + 5)
    from_str = (now - timedelta(days=days_needed)).strftime("%Y-%m-%d %H:%M:%S")
    to_str = now.strftime("%Y-%m-%d %H:%M:%S")
    data = await client.get_historical(token, "60minute", from_str, to_str)
    raw = data.get("candles", []) if data else []
    candles: list[Candle] = []
    for row in raw:
        try:
            candles.append(Candle(
                timestamp_ms=_parse_kite_ts(str(row[0])), open=float(row[1]), high=float(row[2]),
                low=float(row[3]), close=float(row[4]), volume=float(row[5]) if len(row) > 5 else 0.0,
            ))
        except (IndexError, ValueError, TypeError):
            continue
    candles.sort(key=lambda c: c.timestamp_ms)
    return drop_forming(candles[-lookback_bars:])


async def run_navigator_pass(
    client, uid: str, rows: list[EngineSignalRow], *, engine_config_payload: dict, default_underlyings: list[str],
    underlying_tokens: Optional[dict[str, int]] = None,
    universe: Optional[list] = None,
    nfo_rows: Optional[list] = None,
    bfo_rows: Optional[list] = None,
    moneyness: Optional[list[str]] = None,
    expiry_types: Optional[list[str]] = None,
    expiry_types_indices: Optional[list[str]] = None,
    expiry_types_stocks: Optional[list[str]] = None,
) -> list[EngineSignalRow]:
    """Live per-scan Navigator evaluation glue — the price-only pipeline
    (spec §19.3 step 1) run against a fresh, independent candle fetch.
    Complete no-op (zero candle fetches, zero overhead) unless the calling
    user has explicitly enabled Navigator; flow/gamma report
    `CHAIN_UNAVAILABLE` until live option-chain capture is wired in a future
    change.

    `underlying_tokens` maps each underlying name to ITS OWN spot/index
    instrument token (the same universe token the base engine already
    resolves) — AVWAP/Volatility read PRICE STRUCTURE, which only means
    something on the underlying's own continuous history. For `source="spot"`/
    `"confluence"` rows `row.token` already IS that token, but a pure
    `"derivatives"` row's `token` is the option CONTRACT's own instrument
    token, which is only ever a few weeks old (a fresh weekly/monthly listing)
    and may never accumulate enough bars to leave warm-up. Falls back to
    `row.token` when the map is omitted or the underlying isn't in it, so
    existing callers/tests are unaffected.

    `universe`/`nfo_rows`/`bfo_rows`/`moneyness`/`expiry_types*` are ONLY used
    by Signal Origination's `"full"` mode, to resolve a real ATM leg for a
    Navigator-originated row (see `_run_structure_and_origination`) — every
    existing caller/test that omits them is unaffected (origination simply
    can't resolve a leg without them, same as it can't run at all without
    `structure_radar_enabled`/`signal_origination` turned on).

    **Navigator's universe is `underlying_tokens`.** The caller resolves it
    (shared with the Kite engine, or Navigator's own — see
    `NavigatorConfigModel.scan_scope_mode`) and passes it in; this function
    covers exactly those names and nothing else. A SuperTrend row for an
    instrument outside Navigator's universe is skipped, because Navigator
    genuinely has no coverage there to form an opinion from. When the map is
    omitted entirely we fall back to the legacy `config.underlyings` list so
    older callers keep working unchanged.

    Returns `rows`, possibly extended with new Navigator-originated rows
    (`source="navigator"`) appended in place — callers that only cared about
    the previous `None` return are unaffected (the input list is still
    mutated the same way for existing rows)."""
    record = config_store.get(uid, default_underlyings=default_underlyings)
    if not record.config.enabled:
        return rows
    config_revision = kite_config_revision(engine_config_payload)
    underlying_tokens = underlying_tokens or {}
    covered = set(underlying_tokens) or set(record.config.underlyings)

    seen: set[tuple] = set()
    seen_directions: set[tuple[str, str]] = set()
    for row in rows:
        if not (row.is_fresh or row.is_active):
            continue
        if row.underlying not in covered:
            continue
        seen_directions.add((row.underlying, row.direction))
        key = (row.underlying, row.token, row.direction)
        if key in seen:
            continue
        seen.add(key)
        try:
            fetch_token = underlying_tokens.get(row.underlying, row.token)
            raw_candles = await _fetch_candles_for_navigator(client, fetch_token)
            if len(raw_candles) < 60:
                continue  # not enough bars yet for a meaningful warmup — skip quietly
            candles = validate_candles(raw_candles)
            base = KiteTripleSupertrendAdapter.adapt(
                row, user_id=uid, observed_at_ms=_now_ms(), config_revision=config_revision,
            )
            evaluate_and_cache(
                uid, row, base=base, candles=candles, config=record.config,
                activation_watermark_ms=record.activation_watermark_ms, config_revision=record.revision,
            )
        except AdapterError as exc:
            log.debug("navigator pass: adapt skipped for %s/%s: %s", uid, row.underlying, exc)
        except CandleValidationError as exc:
            log.debug("navigator pass: candle validation skipped for %s/%s: %s", uid, row.underlying, exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("navigator pass: evaluation failed for %s/%s: %s", uid, row.underlying, exc)

    if record.config.structure_radar_enabled or record.config.signal_origination != "off":
        try:
            await _run_structure_and_origination(
                client, uid, rows, config=record.config, config_revision=config_revision,
                activation_watermark_ms=record.activation_watermark_ms, record_revision=record.revision,
                default_underlyings=default_underlyings, underlying_tokens=underlying_tokens,
                covered=covered,
                seen_directions=seen_directions, universe=universe, nfo_rows=nfo_rows, bfo_rows=bfo_rows,
                moneyness=moneyness, expiry_types=expiry_types,
                expiry_types_indices=expiry_types_indices, expiry_types_stocks=expiry_types_stocks,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("navigator structure radar / origination pass failed for %s: %s", uid, exc)
    return rows


def _option_exchange_for(underlying: str, universe: Optional[list]) -> str:
    if universe:
        for item in universe:
            if getattr(item, "name", None) == underlying:
                return getattr(item, "option_exchange", "NFO")
    return "BFO" if underlying in ("SENSEX", "BANKEX") else "NFO"


async def _run_structure_and_origination(
    client, uid: str, rows: list[EngineSignalRow], *, config: NavigatorConfigModel, config_revision: str,
    activation_watermark_ms: int, record_revision: int, default_underlyings: list[str],
    underlying_tokens: dict[str, int], covered: set[str], seen_directions: set[tuple[str, str]],
    universe: Optional[list], nfo_rows: Optional[list], bfo_rows: Optional[list],
    moneyness: Optional[list[str]], expiry_types: Optional[list[str]],
    expiry_types_indices: Optional[list[str]], expiry_types_stocks: Optional[list[str]],
) -> None:
    """Structure Radar + Signal Origination (2026-07-28 design doc): for every
    underlying+direction in Navigator's own coverage with NO live real
    SuperTrend row this scan, independently compute AVWAP+Volatility via a
    neutral synthetic base fed through the exact same `evaluate_signal`/
    `fuse()` pipeline real rows use. `structure_radar_enabled` alone just
    keeps this cached for `/snapshot`/`/series`/`/status`;
    `signal_origination != "off"` additionally appends a new
    `source="navigator"` row to `rows` when the resulting decision reaches
    CONFIRMED/HIGH_CONVICTION.

    Deliberately SERIAL. The Kite engine's own scanner runs its candle fetches
    behind a `_CONCURRENCY = 2` semaphore chosen to stay under Kite's ~3 req/s
    historical cap, and that semaphore is per-scan rather than process-wide —
    so fanning this loop out in parallel would silently double the effective
    concurrency and start earning 429s. This runs after the engine's scan has
    finished, one instrument at a time, which keeps the combined rate safe
    however large Navigator's universe gets."""
    for underlying in sorted(covered):
        fetch_token = underlying_tokens.get(underlying)
        if fetch_token is None:
            continue  # can't read price structure without the underlying's own token
        try:
            raw_candles = await _fetch_candles_for_navigator(client, fetch_token)
            if len(raw_candles) < 60:
                continue
            candles = validate_candles(raw_candles)
        except CandleValidationError as exc:
            log.debug("structure radar: candle validation skipped for %s/%s: %s", uid, underlying, exc)
            continue

        for direction in ("long", "short"):
            if (underlying, direction) in seen_directions:
                continue  # a real SuperTrend row already covers this underlying+direction
            prior = get_cached_decision(uid, underlying=underlying, token=fetch_token, direction=direction)
            state = "fresh" if prior is None or not is_origination_decision(prior.base_signal_id) else "active"
            try:
                base = synthetic_origination_base(
                    underlying=underlying, token=fetch_token, direction=direction,
                    bar_close_ms=int(candles.timestamp_ms[-1]), user_id=uid, observed_at_ms=_now_ms(),
                    config_revision=config_revision, state=state,
                    exchange=_option_exchange_for(underlying, universe),
                )
                placeholder = EngineSignalRow(
                    underlying=underlying, token=fetch_token, exchange=_option_exchange_for(underlying, universe),
                    regime="BULL" if direction == "long" else "BEAR",
                    alignment=AlignmentChip(fast=0, mid=0, slow=0),
                    direction=direction, option_type="CE" if direction == "long" else "PE",
                    spot=float(candles.close[-1]), stop_loss=float(candles.close[-1]),
                    score=50.0, timestamp_ms=int(candles.timestamp_ms[-1]),
                    is_active=(state == "active"), is_fresh=(state == "fresh"), source="navigator",
                )
                decision = evaluate_and_cache(
                    uid, placeholder, base=base, candles=candles, config=config,
                    activation_watermark_ms=activation_watermark_ms, config_revision=record_revision,
                )
            except AdapterError as exc:
                log.debug("structure radar: synthesis skipped for %s/%s/%s: %s", uid, underlying, direction, exc)
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("structure radar: evaluation failed for %s/%s/%s: %s", uid, underlying, direction, exc)
                continue

            if config.signal_origination == "off" or decision.status not in ("CONFIRMED", "HIGH_CONVICTION"):
                continue
            origin_row = _build_origination_row(
                placeholder, candles=candles, config=config, decision=decision,
                universe=universe, nfo_rows=nfo_rows, bfo_rows=bfo_rows, moneyness=moneyness,
                expiry_types=expiry_types, expiry_types_indices=expiry_types_indices,
                expiry_types_stocks=expiry_types_stocks,
            )
            if origin_row is not None:
                origin_row.navigator = decision
                rows.append(origin_row)


def _build_origination_row(
    placeholder: EngineSignalRow, *, candles: ValidatedCandles, config: NavigatorConfigModel,
    decision: NavigatorDecision, universe: Optional[list], nfo_rows: Optional[list], bfo_rows: Optional[list],
    moneyness: Optional[list[str]], expiry_types: Optional[list[str]],
    expiry_types_indices: Optional[list[str]], expiry_types_stocks: Optional[list[str]],
) -> Optional[EngineSignalRow]:
    """Build the actual signal-table row for a Navigator-originated decision.
    Requires an ACCEPTED AVWAP stop/target proposal — a Navigator-originated
    row with no honest risk-managed stop is not surfaced at all, in either
    `"heads_up"` or `"full"` mode (never a degenerate/fabricated stop)."""
    structure, avwap_eval = avwap.evaluate_avwap(candles, config.avwap, range_supports=None)
    proposal = avwap_eval.stop_target
    if proposal is None or not proposal.accepted or proposal.stop is None:
        return None

    row = placeholder.model_copy(deep=True)
    row.stop_loss = float(proposal.stop)
    row.entry_sl = float(proposal.stop)

    if config.signal_origination == "full" and universe is not None and (nfo_rows is not None or bfo_rows is not None):
        item = next((u for u in universe if getattr(u, "name", None) == row.underlying), None)
        if item is not None:
            from app.services.kite_engine.scanner import attach_strikes

            option_rows = nfo_rows if getattr(item, "option_exchange", "NFO") == "NFO" else bfo_rows
            _expiry = (
                expiry_types_indices if (expiry_types_indices is not None and getattr(item, "is_index", False))
                else expiry_types_stocks if (expiry_types_stocks is not None and not getattr(item, "is_index", False))
                else (expiry_types or ["weekly", "monthly"])
            )
            try:
                attach_strikes(
                    row, option_rows or [], option_name=item.tradingsymbol,
                    moneynesses=moneyness or ["ATM"], expiry_types=_expiry,
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("origination: leg resolution failed for %s: %s", row.underlying, exc)
    return row


def _check_execution_eligible_inner(uid: str, row: EngineSignalRow, *, default_underlyings: list[str]) -> tuple[bool, str]:
    record = config_store.get(uid, default_underlyings=default_underlyings)
    if not record.config.enabled or record.config.operating_mode != "gate":
        return True, "navigator_not_gating"
    if record.calibration_readiness != "ready":
        return False, "GATE_NOT_CALIBRATED"
    decision = get_cached_decision(uid, underlying=row.underlying, token=row.token, direction=row.direction)
    if decision is None:
        return False, "NO_DATA"
    if decision.config_revision != record.revision:
        return False, "CONFIG_REVISION_STALE"
    if decision.bar_close_ms < record.activation_watermark_ms:
        return False, "ACTIVATION_WATERMARK"
    if not decision.execution_eligible:
        return False, "NOT_ELIGIBLE"
    if not (row.is_fresh or row.is_active):
        return False, "BASE_SIGNAL_STALE"
    return True, "OK"


def check_execution_eligible(uid: str, row: EngineSignalRow, *, default_underlyings: list[str]) -> tuple[bool, str]:
    """Re-derives eligibility FRESH against CURRENT config — never trusts a
    cached decision's own `execution_eligible` flag for order submission.
    Returns `(True, "navigator_not_gating")` whenever Navigator isn't
    enabled in `gate` mode, which is a complete pass-through for every
    existing user (spec §16.3: the config revision must be re-read
    immediately before order submission; a disable/config change between
    scan and order blocks the order)."""
    eligible, reason = _check_execution_eligible_inner(uid, row, default_underlyings=default_underlyings)
    if not eligible:
        log.info("navigator.decision.blocked user=%s underlying=%s reason=%s", uid, row.underlying, reason)
    return eligible, reason


# ─────────────────────────────────────────────────────────────────────────
# Price-feature-only evaluation pipeline
# ─────────────────────────────────────────────────────────────────────────

def _placeholder_evidence(component: str, as_of_bar_close_ms: int, observed_at_ms: int) -> DirectionalEvidence:
    return DirectionalEvidence(
        component=component, as_of_bar_close_ms=as_of_bar_close_ms, observed_at_ms=observed_at_ms,
        direction=0, confidence_100=0.0, quality="unavailable", reason_codes=["CHAIN_UNAVAILABLE"], diagnostics={},
    )


def evaluate_signal(
    *,
    base: BaseSignalEvidence,
    candles: ValidatedCandles,
    config: NavigatorConfigModel,
    activation_watermark_ms: int,
    config_revision: int,
    generated_at_ms: Optional[int] = None,
    tick_size: float = 0.05,
    flow_sample: Optional[ChainFlowSample] = None,
    flow_history: Optional[list[ChainFlowSample]] = None,
    gamma_contracts: Optional[list[GammaContractInput]] = None,
    gamma_context: Optional[dict] = None,
    flow_required: bool = False,
    flow_not_applicable: bool = True,
    gamma_required: bool = False,
) -> NavigatorDecision:
    """Pure orchestration: base + candles (+ optional chain evidence) ->
    one immutable `NavigatorDecision`. No I/O — callers gather candles/chain
    data and pass them in, keeping this fully deterministic and testable."""
    generated_at_ms = generated_at_ms if generated_at_ms is not None else base.observed_at_ms
    bar_close_ms = int(candles.timestamp_ms[-1])

    range_eval = projected_ranges.evaluate_ranges(candles, config.ranges)
    atr_for_context = None  # avwap's own ATR isn't known yet at this point; range context falls back to its band-relative proxy

    def _range_supports(direction: str) -> Optional[bool]:
        ctx = range_eval.daily_context
        if ctx == "UNAVAILABLE":
            return None
        favorable = {"long": ("NEAR_UPPER", "BREAK_ABOVE", "REENTERED_FROM_ABOVE"), "short": ("NEAR_LOWER", "BREAK_BELOW", "REENTERED_FROM_BELOW")}
        return ctx in favorable[direction]

    structure, avwap_eval = avwap.evaluate_avwap(candles, config.avwap, range_supports=_range_supports(base.direction), tick_size=tick_size)
    avwap_evidence = _wrap_avwap(avwap_eval, bar_close_ms, generated_at_ms)

    mid_avwap = None if structure.warming_up[-1] else float(structure.mid[-1])
    volatility_eval = volatility.evaluate_volatility(candles, config.volatility, mid_avwap=mid_avwap, base_direction=base.direction)
    volatility_evidence = _wrap_volatility(volatility_eval, bar_close_ms, generated_at_ms)

    if flow_history:
        flow_eval = evaluate_option_flow(flow_history, config.flow)
        flow_evidence = _wrap_flow(flow_eval, bar_close_ms, generated_at_ms)
    else:
        flow_evidence = _placeholder_evidence("option_flow", bar_close_ms, generated_at_ms)

    if gamma_contracts is not None and gamma_context is not None:
        gamma_eval = evaluate_gamma_activity(
            contracts=gamma_contracts,
            flow_direction=flow_evidence.direction, flow_quality=flow_evidence.quality,
            config=config.gamma, **gamma_context,
        )
        gamma_evidence = _wrap_gamma(gamma_eval, bar_close_ms, generated_at_ms)
    else:
        gamma_evidence = _placeholder_evidence("gamma", bar_close_ms, generated_at_ms)

    range_impulse_supported = range_eval.daily_context in ("BREAK_ABOVE", "BREAK_BELOW") or range_eval.weekly_context in ("BREAK_ABOVE", "BREAK_BELOW")

    inputs = FusionInputs(
        base=base, avwap=avwap_evidence, avwap_grade=avwap_eval.grade.grade, avwap_is_fresh_signal=avwap_eval.family is not None,
        volatility=volatility_evidence, volatility_regime=volatility_eval.regime,
        flow=flow_evidence, flow_required=flow_required, flow_not_applicable=flow_not_applicable,
        gamma=gamma_evidence, gamma_required=gamma_required,
        range_impulse_supported=range_impulse_supported,
    )
    return fuse(
        inputs, config=config, activation_watermark_ms=activation_watermark_ms,
        generated_at_ms=generated_at_ms, config_revision=config_revision, model_versions=MODEL_VERSIONS,
    )


def _wrap_avwap(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import avwap_to_evidence
    return avwap_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def _wrap_volatility(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import volatility_to_evidence
    return volatility_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def _wrap_flow(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import option_flow_to_evidence
    return option_flow_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def _wrap_gamma(evaluation, bar_close_ms, observed_at_ms) -> DirectionalEvidence:
    from app.engines.navigator.fusion import gamma_to_evidence
    return gamma_to_evidence(evaluation, as_of_bar_close_ms=bar_close_ms, observed_at_ms=observed_at_ms)


def evaluate_and_cache(
    uid: str, row: EngineSignalRow, *, base: BaseSignalEvidence, candles: ValidatedCandles,
    config, activation_watermark_ms: int, config_revision: int, **kwargs,
) -> NavigatorDecision:
    """Evaluate one row and persist the resulting decision + feature
    snapshot, then cache it for `attach_to_rows`/`check_execution_eligible`
    — the one place a fresh decision enters the runtime."""
    decision = evaluate_signal(
        base=base, candles=candles, config=config, activation_watermark_ms=activation_watermark_ms,
        config_revision=config_revision, **kwargs,
    )
    cache_decision(uid, underlying=row.underlying, token=row.token, direction=row.direction, decision=decision)

    worst_quality = "ok"
    for evidence in (decision.avwap, decision.volatility, decision.option_flow, decision.gamma):
        if evidence is not None and evidence.quality == "unavailable":
            worst_quality = "degraded" if worst_quality == "ok" else worst_quality

    try:
        repository.insert_feature_snapshot({
            "user_id": uid, "underlying": row.underlying, "timeframe": base.timeframe,
            "bar_close_ms": decision.bar_close_ms, "observed_at_ms": decision.generated_at_ms,
            "config_revision": decision.config_revision, "model_versions_json": json.dumps(decision.model_versions),
            "quality": worst_quality,
            "avwap_json": decision.avwap.model_dump_json() if decision.avwap else None,
            "range_json": None,
            "volatility_json": decision.volatility.model_dump_json() if decision.volatility else None,
            "flow_json": decision.option_flow.model_dump_json() if decision.option_flow else None,
            "gamma_json": decision.gamma.model_dump_json() if decision.gamma else None,
            "input_hash": base.raw_payload_hash,
        })
        log.info(
            "navigator.feature.computed user=%s underlying=%s bar_close_ms=%s quality=%s",
            uid, row.underlying, decision.bar_close_ms, worst_quality,
        )
    except repository.NavigatorStorageError as exc:
        log.warning("Navigator feature snapshot persist failed for %s/%s: %s", uid, row.underlying, exc)

    try:
        repository.insert_signal_event({
            "decision_id": decision.decision_id, "user_id": uid, "underlying": row.underlying,
            "bar_close_ms": decision.bar_close_ms, "generated_at_ms": decision.generated_at_ms,
            "direction": decision.direction, "status": decision.status,
            "effective_score": decision.effective_score, "execution_eligible": int(decision.execution_eligible),
            "config_revision": decision.config_revision, "payload_json": decision.model_dump_json(),
        })
        log.info(
            "navigator.decision.emitted user=%s underlying=%s decision_id=%s status=%s effective_score=%s",
            uid, row.underlying, decision.decision_id, decision.status, decision.effective_score,
        )
    except repository.NavigatorStorageError as exc:
        log.warning("Navigator decision persist failed for %s/%s: %s", uid, row.underlying, exc)
    return decision


def get_feature_series(uid: str, underlying: str, *, timeframe: str = "60minute", since_bar_close_ms: int = 0, limit: int = 500) -> list[dict]:
    if not db.is_available():
        return []
    try:
        with db.connection() as c:
            rows = c.execute(
                "SELECT * FROM navigator_feature_snapshots WHERE user_id=? AND underlying=? AND timeframe=? "
                "AND bar_close_ms>=? ORDER BY bar_close_ms ASC LIMIT ?",
                (uid, underlying, timeframe, since_bar_close_ms, limit),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception as exc:
        log.warning("Navigator feature series read failed for %s/%s: %s", uid, underlying, exc)
        return []


# ─────────────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────────────

def get_status(uid: str, *, default_underlyings: list[str]) -> NavigatorStatusSnapshot:
    record = config_store.get(uid, default_underlyings=default_underlyings)
    components = list(_component_status.get(uid, {}).values())
    last_decisions = [d.generated_at_ms for d in _decision_cache.get(uid, {}).values()]
    return build_status_snapshot(
        enabled=record.config.enabled, operating_mode=record.config.operating_mode,
        calibration_readiness=record.calibration_readiness, config_revision=record.revision,
        activation_watermark_ms=record.activation_watermark_ms, components=components,
        last_decision_at_ms=max(last_decisions) if last_decisions else None,
        sampler_running=_sampler_running.get(uid, False),
        now_ms=_now_ms(), max_feature_age_seconds=record.config.max_feature_age_seconds,
    )
