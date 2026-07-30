"""Narrow option-chain capture: quote-slice sampling, snapshot validation,
completeness/staleness, and interval counter rules (spec §10).

The existing scanner's per-row option resolution (`scanner.py`) is
untouched and makes zero extra quote calls — this sampler is a SEPARATE,
independent, account-scoped poller. Its snapshots are joined to scanner
rows later purely by timestamp (Phase 5), never fetched inline per signal
row.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Awaitable, Callable, Optional

from app.core.logging import get_logger
from app.services.navigator.calendar import IST
from app.services.navigator.instrument_slice import InstrumentSliceIndex, OptionInstrument, OptionInstrumentSlice

log = get_logger(__name__)

MODEL_VERSION = "chain_sampler_v1"

QuoteFetcher = Callable[[list[str]], Awaitable[dict]]
SpotProvider = Callable[[], Awaitable[float]]
SampleSink = Callable[[tuple, OptionInstrumentSlice, "ChainSampleResult", int], Awaitable[None]]


# ─────────────────────────────────────────────────────────────────────────
# Per-contract snapshot parsing + quality (pure, testable without asyncio)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class QuoteSnapshot:
    instrument: OptionInstrument
    bid: float
    ask: float
    last_price: float
    mid: float
    implied_volatility: Optional[float]
    open_interest: Optional[int]
    cumulative_volume: Optional[int]
    exchange_timestamp_ms: Optional[int]
    received_at_ms: int
    quote_quality: str  # "ok" | "crossed" | "wide" | "incomplete"


def _mid_from_depth(bid: float, ask: float, last_price: float) -> float:
    if bid > 0 and ask > 0 and ask >= bid:
        return (bid + ask) / 2.0
    return last_price


def _parse_exchange_timestamp(value) -> Optional[int]:
    """Best-effort parse of Kite's `timestamp`/`last_trade_time` quote
    fields. Whether these are true exchange timestamps for every required
    field is an unverified external fact (spec §22 #5) — if the field is
    absent or unparseable, this returns None rather than guessing, and
    callers fall back to `received_at_ms`."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(str(value)[:19], fmt).replace(tzinfo=IST)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


def parse_quote_row(instrument: OptionInstrument, raw: dict, *, received_at_ms: int, max_spread_pct: float) -> QuoteSnapshot:
    depth = raw.get("depth") or {}
    buy = depth.get("buy") or [{}]
    sell = depth.get("sell") or [{}]
    bid = float((buy[0] if buy else {}).get("price") or 0.0)
    ask = float((sell[0] if sell else {}).get("price") or 0.0)
    last_price = float(raw.get("last_price") or 0.0)
    mid = _mid_from_depth(bid, ask, last_price)

    iv_raw = raw.get("implied_volatility")
    iv = float(iv_raw) / 100.0 if iv_raw not in (None, "", 0) else None
    oi = raw.get("oi")
    oi = int(oi) if oi not in (None, "") else None
    volume = raw.get("volume")
    volume = int(volume) if volume not in (None, "") else None

    quality = "ok"
    if bid > 0 and ask > 0 and ask < bid:
        quality = "crossed"
    elif mid <= 0:
        quality = "incomplete"
    elif bid > 0 and ask > 0 and mid > 0 and (ask - bid) / mid > max_spread_pct:
        quality = "wide"

    return QuoteSnapshot(
        instrument=instrument, bid=bid, ask=ask, last_price=last_price, mid=mid,
        implied_volatility=iv, open_interest=oi, cumulative_volume=volume,
        exchange_timestamp_ms=_parse_exchange_timestamp(raw.get("timestamp") or raw.get("last_trade_time")),
        received_at_ms=received_at_ms, quote_quality=quality,
    )


# ─────────────────────────────────────────────────────────────────────────
# Whole-slice completeness/staleness (spec §10.2 step 6)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ChainSampleResult:
    snapshots: list[QuoteSnapshot]
    expected_contract_count: int
    found_contract_count: int
    completeness: float
    stale_count: int
    quality: str  # "ok" | "degraded" | "unavailable"


def evaluate_chain_sample(
    slice_: OptionInstrumentSlice, snapshots: list[QuoteSnapshot], *,
    now_ms: int, max_quote_age_seconds: int, min_chain_completeness: float,
) -> ChainSampleResult:
    stale_count = sum(
        1 for s in snapshots if (now_ms - s.received_at_ms) / 1000.0 > max_quote_age_seconds
    )
    completeness = (
        len(snapshots) / slice_.expected_contract_count if slice_.expected_contract_count > 0 else 0.0
    )
    if slice_.expected_contract_count == 0 or not snapshots:
        quality = "unavailable"
    elif completeness < min_chain_completeness or stale_count > 0:
        quality = "degraded"
    else:
        quality = "ok"
    return ChainSampleResult(
        snapshots=snapshots, expected_contract_count=slice_.expected_contract_count,
        found_contract_count=len(snapshots), completeness=completeness,
        stale_count=stale_count, quality=quality,
    )


# ─────────────────────────────────────────────────────────────────────────
# Interval counter rules (spec §10.4)
# ─────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CounterDelta:
    valid: bool
    delta_volume: Optional[int] = None
    delta_oi: Optional[int] = None
    reset_reason: Optional[str] = None


def compute_counter_delta(
    prev: Optional[dict], curr: QuoteSnapshot, *,
    max_sample_gap_seconds: int, prev_session_date: Optional[date], curr_session_date: date,
) -> CounterDelta:
    """`prev` is the previous sample's stored dict for this exact contract
    (or None on first sight). A session reset, instrument/expiry rollover,
    excessive gap, or negative cumulative-volume delta all start a fresh
    warmup — never clamped to a synthetic zero delta."""
    if prev is None:
        return CounterDelta(valid=False, reset_reason="warmup")
    if prev_session_date != curr_session_date:
        return CounterDelta(valid=False, reset_reason="session_reset")
    if prev.get("instrument_token") != curr.instrument.token or prev.get("expiry") != curr.instrument.expiry:
        return CounterDelta(valid=False, reset_reason="instrument_rollover")
    gap_seconds = (curr.received_at_ms - prev["received_at_ms"]) / 1000.0
    if gap_seconds > max_sample_gap_seconds:
        return CounterDelta(valid=False, reset_reason="sample_gap")
    if curr.cumulative_volume is None or prev.get("cumulative_volume") is None:
        return CounterDelta(valid=False, reset_reason="missing_volume")
    delta_volume = curr.cumulative_volume - prev["cumulative_volume"]
    if delta_volume < 0:
        return CounterDelta(valid=False, reset_reason="negative_volume_delta")
    delta_oi = None
    if curr.open_interest is not None and prev.get("open_interest") is not None:
        delta_oi = curr.open_interest - prev["open_interest"]
    return CounterDelta(valid=True, delta_volume=delta_volume, delta_oi=delta_oi)


# ─────────────────────────────────────────────────────────────────────────
# Backoff (mirrors the existing get_candles 429 pattern in client.py)
# ─────────────────────────────────────────────────────────────────────────

def backoff_seconds(attempt: int, *, is_rate_limited: bool, jitter: Optional[float] = None) -> float:
    if not is_rate_limited:
        return 0.5
    j = random.uniform(0, 0.25) if jitter is None else jitter
    return min(8.0, 0.75 * (2 ** attempt)) + j


# ─────────────────────────────────────────────────────────────────────────
# Account-scoped coordinator (spec §10.2) — one poller per
# (account_scope, underlying, expiry), shared across every enabled user view
# ─────────────────────────────────────────────────────────────────────────

class ChainSamplerCoordinator:
    """Owns at most one running poll loop per `(account_scope, underlying,
    expiry)` key. Multiple enabled Navigator configs pointed at the same
    account/underlying/expiry must never multiply identical broker quote
    requests."""

    def __init__(
        self,
        *,
        quote_fetcher: QuoteFetcher,
        instrument_index: InstrumentSliceIndex,
        on_sample: SampleSink,
        now_ms: Optional[Callable[[], int]] = None,
    ):
        self._quote_fetcher = quote_fetcher
        self._instrument_index = instrument_index
        self._on_sample = on_sample
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))
        self._tasks: dict[tuple, asyncio.Task] = {}
        self._last_by_contract: dict[tuple, dict] = {}  # (account_scope, token) -> last snapshot dict

    def rebind(
        self, *, quote_fetcher: QuoteFetcher, instrument_index: InstrumentSliceIndex,
        on_sample: SampleSink,
    ) -> None:
        """Point the already-running pollers at a fresh broker client / sink.

        A coordinator outlives the client it was built from. When a Kite session
        expires the cached client is closed and rebuilt on re-login, and when
        Navigator's config is saved the revision that stamps each snapshot
        changes — but the poll loops read these off `self` on every cycle, so
        rebinding is enough to bring them along. Without it a coordinator keeps
        calling a closed httpx client forever (flow and gamma go permanently
        `unavailable` with no error the user can see) and keeps stamping
        snapshots with a config revision that is no longer current.

        Deliberately does NOT restart the tasks: the running pollers hold the
        per-contract counter-reset state that OI/volume deltas depend on."""
        self._quote_fetcher = quote_fetcher
        self._instrument_index = instrument_index
        self._on_sample = on_sample

    def is_running(self, account_scope: str, underlying: str, expiry: str) -> bool:
        key = (account_scope, underlying, expiry)
        task = self._tasks.get(key)
        return task is not None and not task.done()

    def ensure_started(
        self, *, account_scope: str, underlying: str, exchange: str, expiry: str,
        spot_provider: SpotProvider, config,
    ) -> None:
        key = (account_scope, underlying, expiry)
        if self.is_running(account_scope, underlying, expiry):
            return
        self._tasks[key] = asyncio.create_task(
            self._run(key, account_scope, underlying, exchange, expiry, spot_provider, config)
        )
        log.info("navigator.sampler.started account=%s underlying=%s expiry=%s", account_scope, underlying, expiry)

    async def stop(self, account_scope: str, underlying: str, expiry: str) -> None:
        key = (account_scope, underlying, expiry)
        task = self._tasks.pop(key, None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
        log.info("navigator.sampler.stopped account=%s underlying=%s expiry=%s", account_scope, underlying, expiry)

    async def stop_all(self) -> None:
        keys = list(self._tasks.keys())
        for key in keys:
            await self.stop(*key)

    async def sample_once(
        self, *, account_scope: str, underlying: str, exchange: str, expiry: str,
        spot_provider: SpotProvider, config,
    ) -> tuple[OptionInstrumentSlice, ChainSampleResult]:
        """One poll cycle, directly callable (used by the loop and by
        tests) — resolves the slice, fetches quotes in one batch, and
        evaluates completeness/staleness."""
        spot = await spot_provider()
        strike_radius = config.dynamic_strike_radius if config.mode == "dynamic" else config.broad_strike_radius
        slice_ = await self._instrument_index.option_slice(
            exchange=exchange, underlying=underlying, expiry=expiry, spot=spot,
            strike_radius=strike_radius, strike_step_override=config.strike_step_override,
        )
        symbols = [f"{c.exchange}:{c.tradingsymbol}" for c in slice_.contracts]
        quotes = await self._quote_fetcher(symbols) if symbols else {}
        now_ms = self._now_ms()
        snapshots = []
        for inst in slice_.contracts:
            raw = quotes.get(f"{inst.exchange}:{inst.tradingsymbol}")
            if raw:
                snapshots.append(
                    parse_quote_row(inst, raw, received_at_ms=now_ms, max_spread_pct=config.max_spread_pct)
                )
        result = evaluate_chain_sample(
            slice_, snapshots, now_ms=now_ms,
            max_quote_age_seconds=config.max_quote_age_seconds,
            min_chain_completeness=config.min_chain_completeness,
        )
        return slice_, result

    async def _run(self, key, account_scope, underlying, exchange, expiry, spot_provider, config) -> None:
        attempt = 0
        while True:
            try:
                slice_, result = await self.sample_once(
                    account_scope=account_scope, underlying=underlying, exchange=exchange,
                    expiry=expiry, spot_provider=spot_provider, config=config,
                )
                if result.quality == "unavailable":
                    log.info(
                        "navigator.chain.rejected account=%s underlying=%s expiry=%s completeness=%.2f",
                        account_scope, underlying, expiry, result.completeness,
                    )
                else:
                    log.info(
                        "navigator.chain.sampled account=%s underlying=%s expiry=%s contracts=%s quality=%s",
                        account_scope, underlying, expiry, result.found_contract_count, result.quality,
                    )
                await self._on_sample(key, slice_, result, self._now_ms())
                attempt = 0
                await asyncio.sleep(config.flow_sample_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                log.warning("navigator.chain.rejected account=%s underlying=%s expiry=%s error=%s", account_scope, underlying, expiry, exc)
                await asyncio.sleep(backoff_seconds(attempt, is_rate_limited="429" in str(exc)))
