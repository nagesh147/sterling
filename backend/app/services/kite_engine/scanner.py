"""Throttled background scanner for the Kite Sterling Kite Engine.

Per active Kite user: fetch 1H candles for each universe item (cached, rate
throttled), drop the forming bar, run the broker-agnostic engine, and collect the
"ready" rows (fresh full-alignment transition on the latest closed bar). Strike
selection is done from the already-loaded option dumps — no extra quote calls.

Kite types are touched only here and in the endpoints; the engine package stays
broker-agnostic. Nothing here imports another engine's strategy logic.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

import numpy as np

from app.core.logging import get_logger
from app.domain.models import Candle
from app.engines.indicators.adx import adx as _adx
from app.engines.indicators.atr import atr_percentile as _atr_pct, compute_atr as _compute_atr
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.common.exit_counter import get_exit_threshold, exit_needs_counter_signal
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.engine import SterlingKiteEngine
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions
from app.engines.sterling_kite_engine.schemas import (
    AlignmentChip, EngineSignalRow, OptionLeg, SetupChart, SetupLine, SetupPoint,
)
from app.schemas.instruments import InstrumentMeta
from app.services.kite_engine.strikes import (
    ExpiryType, OptionPick, chain_rows_for, pick_contracts, pick_strikes,
)
from app.services.kite_engine.universe import UniverseItem
from app.services.kite_engine import state

log = get_logger(__name__)

_CANDLE_TTL_S = 180          # re-use cached 1H candles for ~3 min
_CONCURRENCY = 2             # stay UNDER Kite historical ~3 req/s (3 concurrent → 429s)
_TF_MS = 3_600_000           # 1H bar in ms
_LOOKBACK_BARS = 320

# Signals linger on the board for a couple of weeks after they fire — even once
# their SuperTrend de-aligns (the UI renders these struck-through as "ended") — so a
# setup entered before a weekend is still visible the following Monday instead of
# vanishing the instant the trend breaks. The UI buckets ended entries up to 15 days
# old ("Today / Yesterday / Last week / Last 15 days"), so the retention matches.
_SIGNAL_RETENTION_MS = 15 * 24 * 60 * 60 * 1000

_IST = timezone(timedelta(hours=5, minutes=30))

# place_cb(row, item) -> Awaitable: optional auto-exec hook injected by the endpoint.
PlaceCb = Callable[[EngineSignalRow, UniverseItem], Awaitable[None]]


# ── pure helpers (unit-tested) ──────────────────────────────────────────────
def drop_forming(candles: List[Candle], now_ms: Optional[int] = None) -> List[Candle]:
    """Drop the last bar if its 1H period has not closed yet."""
    if not candles:
        return candles
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    if candles[-1].timestamp_ms + _TF_MS > now_ms:
        return candles[:-1]
    return candles


def _trail_stop_value(r, direction: str, i: int, last_idx: int,
                      cfg: SterlingKiteEngineConfig) -> float:
    """The stop level to attach to a signal row.

    Default: the tightest still-green line at the latest bar (the validated fast
    trail). When ``exit_aligned_trail`` is on: the line whose flip is the
    ``exit_mode``-th red (one_red→fast, two_red→mid, three_red→slow), so the stop
    breach coincides with the red-count exit instead of the tightest line pre-empting
    it. Falls back to the entry-bar ``trail_target`` line when no green line remains.
    """
    if getattr(cfg, "exit_aligned_trail", False):
        trail_val = r.trail_value_for_threshold(last_idx, get_exit_threshold(cfg.exit_mode))
    else:
        trail_val = r.best_trail_line_value(direction, last_idx)
    return trail_val if trail_val > 0 else float(r.line(cfg.trail_target)[i])


def _exit_state_str(r, direction: str, last_idx: int, cfg: SterlingKiteEngineConfig) -> str:
    """Red-counter progress at the latest bar as ``"<reds>/<threshold> red"``.

    ``reds`` = how many of the three ST lines are against the position now; threshold =
    the count that triggers the exit under ``exit_mode`` (one_red→1, two_red→2,
    three_red[_signal]→3). This is the live Exit-column readout.
    """
    reds = r.red_line_count(direction, last_idx)
    return f"{reds}/{get_exit_threshold(cfg.exit_mode)} red"


def _entry_sl_value(r, i: int, cfg: SterlingKiteEngineConfig) -> float:
    """Initial hard stop at the entry bar = the ``trail_target`` (validated fast) ST
    line at the trigger index. Static reference for the SL column (vs. the live TSL)."""
    return float(r.line(cfg.trail_target)[i])


def _retain_signals(eval_rows: List[EngineSignalRow], now_ms: int) -> List[EngineSignalRow]:
    """Filter one instrument's transitions to the rows worth showing.

    Keeps every still-running or just-fired entry, PLUS the single most-recent
    now-ended entry while it is still within the retention window. This replaces the
    old ``is_active or is_fresh`` drop so a recent setup doesn't disappear the moment
    its trend ends — it stays on the board (rendered struck-through as "ended") until
    it ages out or a newer transition on the same instrument supersedes it. Older
    de-aligned wiggles are dropped, keeping the board bounded and the cache stable
    across re-scans (each scan replays the same history deterministically).

    Auto-exec is unaffected: callers still fire only on the fresh (latest-bar) row.
    """
    if not eval_rows:
        return []
    latest_ts = max(int(r.timestamp_ms) for r in eval_rows)
    out: List[EngineSignalRow] = []
    for r in eval_rows:
        if r.is_active or r.is_fresh:
            out.append(r)
        elif int(r.timestamp_ms) == latest_ts and (now_ms - int(r.timestamp_ms)) <= _SIGNAL_RETENTION_MS:
            out.append(r)
    return out


def evaluate_item(
    engine: SterlingKiteEngine, item: UniverseItem,
    candles: Sequence[Candle], cfg: SterlingKiteEngineConfig,
) -> List[EngineSignalRow]:
    """Run the engine on closed candles; return all historical fresh transitions."""
    if len(candles) <= cfg.warmup + 1:
        return []
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)

    rows = []
    indices = np.where(longs | shorts)[0]
    latest_ts = int(candles[-1].timestamp_ms)
    # Trend-quality readings for the optional directional-mode entry filters
    # (computed once over the raw OHLC; never gate anything on their own).
    adx_arr = _adx(h, l, c, 14)
    atr_arr = _compute_atr(h, l, c, 14)
    for i in indices:
        direction = "long" if longs[i] else "short"
        ts = int(candles[i].timestamp_ms)
        # A trade is "running" until enough ST lines turn red (per exit_mode).
        # For one_red: ANY one line flipping against the entry exits.
        # For two_red/three_red: two/three lines must be red simultaneously.
        # For three_red_signal: all three red AND a fresh counter-arrow.
        # Check every bar from entry to latest — once the exit condition fires,
        # the trade is dead even if conditions reverse later (that's a new entry).
        active = True
        for j in range(i, len(c)):
            reds = r.red_line_count(direction, j)
            if reds >= get_exit_threshold(cfg.exit_mode):
                if exit_needs_counter_signal(cfg.exit_mode):
                    # Also need a fresh counter-entry arrow at this bar
                    if direction == "long" and shorts[j]:
                        active = False
                        break
                    elif direction == "short" and longs[j]:
                        active = False
                        break
                    # Not enough — reds hit threshold but no counter-arrow yet
                else:
                    active = False
                    break
        # Adaptive stop: tightest still-green line, or the exit_mode-aligned line.
        last_idx = len(c) - 1
        stop_loss = _trail_stop_value(r, direction, i, last_idx, cfg)
        rows.append(EngineSignalRow(
            underlying=item.name, token=item.token, exchange=item.option_exchange,
            regime="BULL" if direction == "long" else "BEAR",
            alignment=AlignmentChip(fast=int(r.t_fast[i]), mid=int(r.t_mid[i]), slow=int(r.t_slow[i])),
            direction=direction, option_type="CE" if direction == "long" else "PE",
            spot=float(c[i]), stop_loss=stop_loss,
            entry_sl=_entry_sl_value(r, i, cfg),
            exit_state=_exit_state_str(r, direction, last_idx, cfg),
            score=85.0, timestamp_ms=ts,
            is_active=active,
            is_fresh=(ts == latest_ts),
            adx=float(adx_arr[i]) if i < len(adx_arr) else None,
            atr_pct=float(_atr_pct(atr_arr[: i + 1])) if i >= 14 else None,
        ))
    return rows


# Fixed display/priority order: ATM first (the auto-exec primary), then ITM
# inwards, then OTM outwards — independent of the order the UI sends them in.
_MONEYNESS_ORDER = {"ATM": 0, "ITM1": 1, "ITM2": 2, "ITM3": 3, "ITM4": 4, "ITM5": 5,
                    "ITM10": 5.3, "ITM15": 5.6, "ITM20": 5.9,
                    "OTM1": 6, "OTM2": 7, "OTM3": 8, "OTM4": 9, "OTM5": 10}


def _compile_rows(rows: List[EngineSignalRow]) -> List[EngineSignalRow]:
    """Group derivative legs and de-duplicate into final display rows."""
    grouped_derivs: Dict[tuple, EngineSignalRow] = {}
    leg_ts: Dict[tuple, int] = {}
    final_rows: List[EngineSignalRow] = []
    for r in rows:
        if r.source != "derivatives":
            final_rows.append(r)
            continue
        key = (r.underlying, r.option_type)
        leg = r.legs[0]
        leg.premium_spot = r.spot
        leg.premium_sl = r.stop_loss
        leg.token = r.token
        sym_key = (*key, leg.option_symbol)
        if key not in grouped_derivs:
            r.spot = 0
            r.stop_loss = 0
            r.entry_sl = None   # per-leg (leg.entry_sl) is authoritative for grouped deriv rows
            r.legs = [leg]
            grouped_derivs[key] = r
            leg_ts[sym_key] = r.timestamp_ms
            continue
        parent = grouped_derivs[key]
        if sym_key not in leg_ts:
            parent.legs.append(leg)
            leg_ts[sym_key] = r.timestamp_ms
        elif r.timestamp_ms > leg_ts[sym_key]:
            for i, existing in enumerate(parent.legs):
                if existing.option_symbol == leg.option_symbol:
                    parent.legs[i] = leg
                    break
            leg_ts[sym_key] = r.timestamp_ms
        parent.is_active = parent.is_active or leg.is_active
        parent.is_fresh = parent.is_fresh or r.is_fresh
        if r.timestamp_ms > parent.timestamp_ms:
            parent.timestamp_ms = r.timestamp_ms
            # keep the underlying-spot aligned with the displayed (latest) trigger bar
            if (r.underlying_spot or 0) > 0:
                parent.underlying_spot = r.underlying_spot
    final_rows.extend(grouped_derivs.values())
    for r in final_rows:
        if r.source == "derivatives" and len(r.legs) > 1:
            r.legs.sort(key=lambda leg: _MONEYNESS_ORDER.get(leg.moneyness, 99))
    return final_rows


def evaluate_derivative_contract(
    item: UniverseItem, moneyness: str, pick: OptionPick,
    candles: Sequence[Candle], cfg: SterlingKiteEngineConfig,
) -> List[EngineSignalRow]:
    """Run the Sterling Kite Engine on an option CONTRACT's own premium series.

    Options-buying only: emit a BUY signal on a fresh *uptrend* transition of the
    premium (a fresh downtrend is a holder's exit, not an entry, so it's ignored).
    A rising CE = bullish underlying (BULL); a rising PE = bearish underlying (BEAR).
    ``spot`` carries the premium last close and ``stop_loss`` the premium ST trail;
    ``token`` is the option's own instrument_token so a click opens its premium chart.

    Short-dated weeklies are NOT skipped — they're evaluated like everything else; the
    SuperTrend simply returns no signal until the contract has ~``warmup`` 1H bars (so a
    young weekly produces no signal, never a fabricated one).
    """
    if len(candles) <= 1:
        return []
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)

    rows = []
    is_ce = pick.option_type == "CE"
    indices = np.where(longs)[0]
    latest_ts = int(candles[-1].timestamp_ms)
    for i in indices:
        ts = int(candles[i].timestamp_ms)
        # "running" until enough ST lines turn red (per exit_mode). For derivatives
        # all entries are long (BUY), so red = trend == -1.
        active = True
        for j in range(i, len(c)):
            reds = r.red_line_count("long", j)
            if reds >= get_exit_threshold(cfg.exit_mode):
                if exit_needs_counter_signal(cfg.exit_mode):
                    if shorts[j]:
                        active = False
                        break
                else:
                    active = False
                    break
        # Adaptive stop: tightest still-green line, or the exit_mode-aligned line.
        last_idx = len(c) - 1
        stop_loss = _trail_stop_value(r, "long", i, last_idx, cfg)
        entry_sl = _entry_sl_value(r, i, cfg)
        rows.append(EngineSignalRow(
            underlying=item.name, token=pick.token, exchange=item.option_exchange,
            regime="BULL" if is_ce else "BEAR",
            alignment=AlignmentChip(fast=int(r.t_fast[i]), mid=int(r.t_mid[i]), slow=int(r.t_slow[i])),
            direction="long", option_type=pick.option_type,
            legs=[OptionLeg(moneyness=moneyness, option_type=pick.option_type,
                            option_symbol=pick.option_symbol, strike=pick.strike,
                            expiry=pick.expiry, lot_size=pick.lot_size or None,
                            entry_sl=entry_sl, is_active=active)],
            spot=float(c[i]), stop_loss=stop_loss, entry_sl=entry_sl,
            exit_state=_exit_state_str(r, "long", last_idx, cfg),
            score=85.0, timestamp_ms=ts, source="derivatives",
            is_active=active, is_fresh=(ts == latest_ts),
        ))
    return rows


def attach_strikes(
    row: EngineSignalRow, option_rows: Sequence[dict], *, option_name: str,
    moneynesses: Sequence[str] = ("ATM",), today: Optional[date] = None,
    expiry_types: Sequence[ExpiryType] = (),
) -> EngineSignalRow:
    """Resolve and attach an option leg per selected moneyness from a raw dump.

    ``option_name`` is the option-chain underlying ("NIFTY"), which differs from
    ``row.underlying`` (the display name, e.g. "NIFTY 50") for indices. Legs are
    emitted in a fixed canonical order (ATM, ITM…, OTM…) regardless of request order.
    """
    today = today or datetime.now(_IST).date()
    chain = chain_rows_for(option_rows, option_name, today)
    ordered = sorted(moneynesses, key=lambda m: _MONEYNESS_ORDER.get(m, 99))
    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,
                         moneynesses=ordered, expiry_types=expiry_types, today=today)
    row.legs = [
        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None)
        for m, p in picks
    ]
    return row


def option_order_args(row: EngineSignalRow, leg: Optional[OptionLeg] = None) -> Optional[dict]:
    """Pure mapping: a ready row (+ chosen leg) → Kite option-BUY order args.

    Options buying is always a BUY (a call for bull, a put for bear); quantity is
    one lot (``lot_size``). For auto-exec the primary leg is the one *nearest spot*
    (i.e. ATM when selected) — never a deep OTM contract just because it sorts
    first. The advisory ST trailing stop rides along as the SL trigger.
    """
    if leg is None and row.legs:
        leg = min(row.legs, key=lambda l: abs(l.strike - row.spot))
    if leg is None:
        return None
    return {
        "option_symbol": leg.option_symbol,
        "side": "buy",
        "size": int(leg.lot_size or 0),
        "lot_size": int(leg.lot_size or 0),
        "token": int(leg.token or 0),
        "exchange": row.exchange,
        "stop_loss": float(row.stop_loss),
        # Premium basis for risk sizing (workstream F). Derivatives legs carry the
        # option's own premium (premium_spot) + its ST trail (premium_sl); for spot
        # signals these may be None → risk-sizing degrades to a single lot.
        "entry_premium": float(leg.premium_spot) if leg.premium_spot is not None else None,
        "stop_premium": float(leg.premium_sl) if leg.premium_sl is not None else None,
    }


# ── per-user scan state ─────────────────────────────────────────────────────
@dataclass
class ContractScanDiag:
    """Per-contract trace: one entry for every option contract the scan attempted."""
    underlying: str = ""
    symbol: str = ""       # option tradingsymbol
    strike: float = 0.0
    option_type: str = ""  # "CE" | "PE"
    expiry: str = ""
    moneyness: str = ""
    bars: int = 0
    premium_close: float = 0.0
    fired: bool = False
    fired_at_ms: int = 0
    reason: str = ""


@dataclass
class ScanDiag:
    """Per-scan breakdown — surfaced to the activity log so a silently-empty index
    candle fetch (the classic 'no index signals' symptom) is visible, not guessed."""
    universe: int = 0          # instruments in the scan universe
    indices: int = 0           # of those, how many are indices
    evaluated: int = 0         # had enough candles to run the engine
    no_data: int = 0           # skipped: no token / no or too-few candles (silent drops)
    index_evaluated: int = 0   # indices that had usable candles
    index_no_data: int = 0     # indices dropped for missing data
    index_fired: int = 0       # indices that produced a ready signal
    deriv_resolved: int = 0    # contracts resolved from option chains (pre-fetch)
    deriv_no_spot: int = 0     # underlyings skipped: spot price unresolved (candles+quote empty)
    deriv_charts: int = 0      # option contracts charted (had premium candles)
    deriv_no_data: int = 0     # contracts skipped: no token / empty premium fetch
    deriv_fired: int = 0       # contracts that produced a BUY signal
    deriv_min_bars: int = 0    # premium-chart bar depth of charted contracts (history)
    deriv_max_bars: int = 0
    confluence_fired: int = 0  # merged rows where the underlying AND a leg's premium both fired
    contracts: List[ContractScanDiag] = field(default_factory=list)


@dataclass
class UserScan:
    engine: SterlingKiteEngine
    rows: List[EngineSignalRow] = field(default_factory=list)
    candle_cache: Dict[int, tuple] = field(default_factory=dict)  # token -> (mono_ts, candles)
    generated_ms: int = 0
    scanning: bool = False
    scanning_label: str = ""
    cancelled: bool = False
    diag: ScanDiag = field(default_factory=ScanDiag)
    # token → row index, lazily built and invalidated when a new scan lands
    # (keyed by generated_ms + row count). Turns detail lookup O(n)→O(1).
    _idx_key: tuple = (-1, -1)
    _row_by_token: Dict[int, "EngineSignalRow"] = field(default_factory=dict)

    def row_for_token(self, token: int, timestamp_ms: int = 0):
        """Return the scan row whose own token or one of whose leg tokens matches
        ``token`` (optionally also matching ``timestamp_ms``). O(1) via a cached
        index; falls back to a scan only on the rare token/timestamp-collision case."""
        key = (self.generated_ms, len(self.rows))
        if self._idx_key != key:
            idx: Dict[int, "EngineSignalRow"] = {}
            for r in self.rows:
                rt = getattr(r, "token", None)
                if rt is not None:
                    idx.setdefault(rt, r)
                for leg in r.legs:
                    lt = getattr(leg, "token", None)
                    if lt is not None:
                        idx.setdefault(lt, r)
            self._row_by_token = idx
            self._idx_key = key
        r = self._row_by_token.get(token)
        if timestamp_ms > 0 and r is not None and r.timestamp_ms != timestamp_ms:
            # token reused across snapshots at different timestamps — exact-match scan
            return next((x for x in self.rows
                         if (getattr(x, "token", None) == token
                             or any(getattr(l, "token", None) == token for l in x.legs))
                         and x.timestamp_ms == timestamp_ms), None)
        return r


def _inst(item: UniverseItem) -> InstrumentMeta:
    """Minimal InstrumentMeta for 1H candle fetch (only zerodha_token is read)."""
    return InstrumentMeta(
        underlying=item.tradingsymbol,
        tick_size=0.05, strike_step=1.0, exchange_currency="INR",
        perp_symbol="", index_name=item.name,
        has_options=True, exchange="zerodha",
        zerodha_token=item.token,
    )


class KiteEngineScanner:
    def __init__(self) -> None:
        self._users: Dict[str, UserScan] = {}

    def _user(self, uid: str, cfg: SterlingKiteEngineConfig) -> UserScan:
        us = self._users.get(uid)
        if us is None:
            us = UserScan(engine=SterlingKiteEngine(cfg))
            self._users[uid] = us
        return us

    def snapshot(self, uid: str) -> UserScan:
        us = self._users.get(uid)
        if us is not None:
            return us
        us = UserScan(engine=SterlingKiteEngine())
        cached = state.load_signal_cache(uid)
        if cached:
            rows_data, gen_ms = cached
            try:
                us.rows = [EngineSignalRow(**r) for r in rows_data]
                us.generated_ms = gen_ms
            except Exception as _exc:
                log.debug("suppressed: %s", _exc)
        self._users[uid] = us
        return us

    def cancel(self, uid: str) -> bool:
        """Signal a running scan to stop. Returns True if a scan was running."""
        us = self._users.get(uid)
        if us and us.scanning:
            us.cancelled = True
            us.scanning = False
            us.scanning_label = "Cancelled"
            return True
        return False

    async def _fetch_candles(self, client, us: UserScan, token: int, name: str) -> List[Candle]:
        """Fetch + cache 1H candles by instrument_token. Works for underlyings AND
        option contracts (distinct token spaces, so the cache never collides)."""
        hit = us.candle_cache.get(token)
        if hit and (time.monotonic() - hit[0]) < _CANDLE_TTL_S:
            return hit[1]
        inst = InstrumentMeta(
            underlying=name, tick_size=0.05, strike_step=1.0, exchange_currency="INR",
            perp_symbol="", index_name=name, has_options=True, exchange="zerodha",
            zerodha_token=token,
        )
        candles = await client.get_candles(inst, "1H", _LOOKBACK_BARS)
        us.candle_cache[token] = (time.monotonic(), candles)
        return candles

    async def _fetch_1h(self, client, us: UserScan, item: UniverseItem) -> List[Candle]:
        return await self._fetch_candles(client, us, item.token, item.tradingsymbol)

    async def scan(
        self, *, uid: str, client, universe: List[UniverseItem],
        nfo_rows: Sequence[dict], bfo_rows: Sequence[dict],
        cfg: SterlingKiteEngineConfig, moneyness: Sequence[str] = ("ATM",),
        expiry_types: Sequence[ExpiryType] = (),
        expiry_types_indices: Optional[Sequence[ExpiryType]] = None,
        expiry_types_stocks: Optional[Sequence[ExpiryType]] = None,
        place_cb: Optional[PlaceCb] = None,
        deriv_universe: Optional[List[UniverseItem]] = None,
        confluence_universe: Optional[List[UniverseItem]] = None,
        log_cb: Optional[Callable[[str], None]] = None,
        close_feed: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        us = self._user(uid, cfg)
        us.engine.cfg = cfg
        us.scanning = True
        us.cancelled = False
        us.scanning_label = "Loading instruments…"
        try:
            sem = asyncio.Semaphore(_CONCURRENCY)
            today = datetime.now(_IST).date()
            now_ms = int(time.time() * 1000)  # retention cutoff for ended signals
            rows: List[EngineSignalRow] = []
            diag = ScanDiag(universe=len(universe),
                            indices=sum(1 for i in universe if i.is_index))

            def _no_data(item: UniverseItem) -> None:
                diag.no_data += 1
                if item.is_index:
                    diag.index_no_data += 1

            async def _one(item: UniverseItem) -> None:
                if us.cancelled:
                    return
                if not item.token:
                    _no_data(item)
                    return
                us.scanning_label = item.name
                if log_cb:
                    log_cb(f"Scanning spot: {item.name} ({item.exchange})")
                async with sem:
                    try:
                        candles = drop_forming(await self._fetch_1h(client, us, item))
                    except Exception as exc:  # noqa: BLE001
                        log.warning("kite-engine scan candle fail %s: %s", item.name, exc)
                        _no_data(item)
                        return
                # Feed the correlation tracker the latest underlying close (opt-in).
                if close_feed and candles:
                    close_feed(item.name, float(candles[-1].close))
                # Too few bars to run the engine → a silent drop unless we record it.
                if len(candles) <= cfg.warmup + 1:
                    _no_data(item)
                    return
                diag.evaluated += 1
                if item.is_index:
                    diag.index_evaluated += 1
                eval_rows = evaluate_item(us.engine, item, candles, cfg)
                if not eval_rows:
                    return
                option_rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                
                latest_ts = candles[-1].timestamp_ms
                # Surface running/just-fired setups PLUS the most-recent recently-ended
                # one, so signals don't vanish the instant a trend breaks (they show as
                # "ended" until they age out — see _retain_signals).
                for row in _retain_signals(eval_rows, now_ms):
                    attach_strikes(row, option_rows, option_name=item.tradingsymbol,
                                   moneynesses=moneyness, today=today,
                                   expiry_types=_expiry)
                    rows.append(row)

                    is_fresh = (row.timestamp_ms == latest_ts)
                    if is_fresh:
                        if item.is_index:
                            diag.index_fired += 1
                        if place_cb is not None and row.legs:
                            try:
                                await place_cb(row, item)
                            except Exception as exc:  # noqa: BLE001
                                log.warning("kite-engine auto-exec fail %s: %s", item.name, exc)

            await asyncio.gather(*[_one(i) for i in universe])

            # ── flush spot results immediately so the frontend shows them while
            # derivatives are still scanning ──
            def _flush() -> None:
                us.rows = _compile_rows(rows)
                us.generated_ms = int(time.time() * 1000)
                model_rows = [r.model_dump() for r in us.rows]
                state.save_signal_cache(uid, model_rows, us.generated_ms)
            _flush()

            # ── derivatives scan: triple-ST on each contract's OWN premium chart ──
            async def _deriv_one(item: UniverseItem) -> None:
                if us.cancelled:
                    return
                if not item.token:
                    return
                async with sem:
                    try:
                        under = drop_forming(await self._fetch_candles(
                            client, us, item.token, item.tradingsymbol))
                    except Exception as exc:  # noqa: BLE001
                        log.warning("kite-engine deriv spot-anchor fail %s: %s", item.name, exc)
                        under = []
                
                spot = float(under[-1].close) if under else 0.0
                # Underlying spot at each 1H bar, so a derivative signal can report the
                # spot at its trigger timestamp (the premium chart alone never carries it).
                under_close_by_ts = {int(c.timestamp_ms): float(c.close) for c in under}
                if spot <= 0:
                    try:
                        # Quote by DISPLAY name (mirrors detail._spot_symbol): the LTP
                        # symbol is "NSE:NIFTY 50" / "BSE:SENSEX", NOT the option name
                        # ("NIFTY"), which is not a valid quote symbol and returns nothing.
                        qsym = f"BSE:{item.name}" if item.option_exchange == "BFO" else f"NSE:{item.name}"
                        q = await client.get_quote([qsym])
                        if q and qsym in q:
                            spot = float(q[qsym].get("last_price") or 0.0)
                    except Exception as exc:  # noqa: BLE001
                        log.warning("kite-engine deriv spot fallback fail %s: %s", item.name, exc)

                if spot <= 0:
                    # Don't fail silently — a zero spot drops the whole chain (the classic
                    # "no derivative signals" symptom), so make it visible in the log + diag.
                    diag.deriv_no_spot += 1
                    if log_cb:
                        log_cb(f"⚠ {item.name}: spot unavailable (candles + quote both empty) — derivatives skipped")
                    return
                if close_feed:
                    close_feed(item.name, spot)
                option_rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
                chain = chain_rows_for(option_rows, item.tradingsymbol, today)
                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                contracts = pick_contracts(chain, spot=spot, moneynesses=moneyness,
                                           expiry_types=_expiry, today=today)
                diag.deriv_resolved += len(contracts)

                async def _contract(m: str, pick) -> None:
                    if us.cancelled:
                        return
                    if not pick.token:
                        diag.deriv_no_data += 1
                        diag.contracts.append(ContractScanDiag(
                            underlying=item.name, symbol=pick.option_symbol,
                            strike=pick.strike, option_type=pick.option_type,
                            expiry=pick.expiry[:10], moneyness=m,
                            bars=0, premium_close=0.0, fired=False,
                            reason="no instrument token"))
                        return
                    if log_cb:
                        try:
                            ed = datetime.strptime(pick.expiry[:10], "%Y-%m-%d")
                            day = ed.day
                            sfx = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
                            readable = f"{item.name} {day}{sfx} w {ed.strftime('%b').upper()} {int(pick.strike)} {pick.option_type}"
                        except Exception:
                            readable = pick.option_symbol
                        us.scanning_label = readable
                        log_cb(f"Scanning derivative: {readable} ({m})")
                    async with sem:
                        try:
                            oc = drop_forming(await self._fetch_candles(
                                client, us, pick.token, pick.option_symbol))
                        except Exception as exc:  # noqa: BLE001
                            log.warning("kite-engine deriv chart fail %s: %s", pick.option_symbol, exc)
                            diag.deriv_no_data += 1
                            diag.contracts.append(ContractScanDiag(
                                underlying=item.name, symbol=pick.option_symbol,
                                strike=pick.strike, option_type=pick.option_type,
                                expiry=pick.expiry[:10], moneyness=m,
                                bars=0, premium_close=0.0, fired=False,
                                reason=f"candle fetch failed: {exc}"))
                            return
                    if not oc:
                        diag.deriv_no_data += 1  # nothing returned (a short-but-present
                        diag.contracts.append(ContractScanDiag(     # weekly is still charted below, never skipped)
                            underlying=item.name, symbol=pick.option_symbol,
                            strike=pick.strike, option_type=pick.option_type,
                            expiry=pick.expiry[:10], moneyness=m,
                            bars=0, premium_close=0.0, fired=False,
                            reason="no candle data returned"))
                        return
                    diag.deriv_charts += 1
                    bars = len(oc)               # premium-history depth, to expose short weeklies
                    diag.deriv_min_bars = bars if diag.deriv_min_bars == 0 else min(diag.deriv_min_bars, bars)
                    diag.deriv_max_bars = max(diag.deriv_max_bars, bars)
                    premium_close = float(oc[-1].close) if oc else 0.0
                    drows = evaluate_derivative_contract(item, m, pick, oc, cfg)
                    latest_ts = oc[-1].timestamp_ms
                    fired = any(drow.timestamp_ms == latest_ts for drow in drows)
                    fired_at = next((drow.timestamp_ms for drow in drows if drow.timestamp_ms == latest_ts), 0)
                    
                    if not drows:
                        reason = f"no fresh up-transition ({bars} bars, warmup={cfg.warmup})" if bars > cfg.warmup else f"too few bars ({bars} < {cfg.warmup+1} warmup)"
                    elif fired:
                        reason = "fresh BUY signal"
                    else:
                        reason = "historical entry only (not fresh)"
                    
                    diag.contracts.append(ContractScanDiag(
                        underlying=item.name, symbol=pick.option_symbol,
                        strike=pick.strike, option_type=pick.option_type,
                        expiry=pick.expiry[:10], moneyness=m,
                        bars=bars, premium_close=premium_close, fired=fired,
                        fired_at_ms=fired_at, reason=reason))
                    
                    latest_ts = oc[-1].timestamp_ms
                    # Keep running/just-fired entries plus the most-recent recently-ended
                    # one (the diag trace above still records every historical entry).
                    for drow in _retain_signals(drows, now_ms):
                        # Stamp the underlying spot at this signal's trigger bar (1H bars
                        # of premium and underlying share timestamps; fall back to the
                        # last bar at/before the trigger if there's no exact match).
                        drow.underlying_spot = under_close_by_ts.get(int(drow.timestamp_ms))
                        if drow.underlying_spot is None and under_close_by_ts:
                            prior = [ts for ts in under_close_by_ts if ts <= drow.timestamp_ms]
                            if prior:
                                drow.underlying_spot = under_close_by_ts[max(prior)]
                        rows.append(drow)
                        is_fresh = (drow.timestamp_ms == latest_ts)
                        if is_fresh:
                            diag.deriv_fired += 1
                            if place_cb is not None:  # auto-exec is universal (spot + derivatives)
                                try:
                                    await place_cb(drow, item)
                                except Exception as exc:  # noqa: BLE001
                                    log.warning("kite-engine deriv auto-exec fail %s: %s", pick.option_symbol, exc)

                await asyncio.gather(*[_contract(m, p) for m, p in contracts])

                # Flush after this underlying's derivatives finish so signals
                # from already-scanned symbols appear immediately in the table.
                _flush()

            await asyncio.gather(*[_deriv_one(i) for i in (deriv_universe or [])])

            # ── confluence scan: underlying regime AND the leg's own premium ──────
            # A candidate strike is emitted only when the UNDERLYING fires a fresh
            # entry (spot regime, direction → CE/PE) AND that option's OWN premium
            # triple-ST also confirms (a running/fresh BUY). One merged row per
            # underlying signal, carrying only the confirmed legs — the highest-
            # conviction filter ("the index turned AND the option is actually moving").
            async def _confluence_one(item: UniverseItem) -> None:
                if us.cancelled:
                    return
                if not item.token:
                    _no_data(item)
                    return
                us.scanning_label = item.name
                if log_cb:
                    log_cb(f"Scanning confluence: {item.name} ({item.exchange})")
                async with sem:
                    try:
                        candles = drop_forming(await self._fetch_1h(client, us, item))
                    except Exception as exc:  # noqa: BLE001
                        log.warning("kite-engine confluence candle fail %s: %s", item.name, exc)
                        _no_data(item)
                        return
                if close_feed and candles:
                    close_feed(item.name, float(candles[-1].close))
                if len(candles) <= cfg.warmup + 1:
                    _no_data(item)
                    return
                diag.evaluated += 1
                if item.is_index:
                    diag.index_evaluated += 1
                eval_rows = evaluate_item(us.engine, item, candles, cfg)
                if not eval_rows:
                    return
                option_rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
                _expiry = expiry_types_indices if (expiry_types_indices is not None and item.is_index) else expiry_types_stocks if (expiry_types_stocks is not None and not item.is_index) else expiry_types
                chain = chain_rows_for(option_rows, item.tradingsymbol, today)
                ordered = sorted(moneyness, key=lambda m: _MONEYNESS_ORDER.get(m, 99))
                latest_ts = candles[-1].timestamp_ms

                for row in _retain_signals(eval_rows, now_ms):
                    # Candidate strikes for this signal's direction — the SAME picks
                    # attach_strikes resolves — then confirm each on its own premium.
                    picks = pick_strikes(chain, spot=row.spot, direction=row.direction,
                                         moneynesses=ordered, expiry_types=_expiry, today=today)
                    confirmed: List[OptionLeg] = []
                    for m, pick in picks:
                        if us.cancelled:
                            return
                        if not pick.token:
                            continue  # no premium series to confirm against
                        async with sem:
                            try:
                                oc = drop_forming(await self._fetch_candles(
                                    client, us, pick.token, pick.option_symbol))
                            except Exception as exc:  # noqa: BLE001
                                log.warning("kite-engine confluence chart fail %s: %s",
                                            pick.option_symbol, exc)
                                continue
                        if len(oc) <= 1:
                            continue
                        diag.deriv_charts += 1
                        bars = len(oc)
                        diag.deriv_min_bars = bars if diag.deriv_min_bars == 0 else min(diag.deriv_min_bars, bars)
                        diag.deriv_max_bars = max(diag.deriv_max_bars, bars)
                        drows = evaluate_derivative_contract(item, m, pick, oc, cfg)
                        # Confirmed = the premium is CURRENTLY trending up (running/fresh
                        # BUY), not merely a stale historical entry.
                        live = [d for d in drows if d.is_active or d.is_fresh]
                        if not live:
                            continue
                        d = max(live, key=lambda x: x.timestamp_ms)
                        leg = d.legs[0]
                        leg.premium_spot = d.spot
                        leg.premium_sl = d.stop_loss
                        leg.entry_sl = d.entry_sl
                        leg.token = pick.token
                        leg.is_active = d.is_active
                        confirmed.append(leg)
                    if not confirmed:
                        continue
                    confirmed.sort(key=lambda l: _MONEYNESS_ORDER.get(l.moneyness, 99))
                    row.source = "confluence"
                    row.legs = confirmed
                    row.underlying_spot = row.spot  # spot mode: `spot` IS the underlying
                    rows.append(row)
                    if row.timestamp_ms == latest_ts:
                        diag.confluence_fired += 1
                        if place_cb is not None:
                            try:
                                await place_cb(row, item)
                            except Exception as exc:  # noqa: BLE001
                                log.warning("kite-engine confluence auto-exec fail %s: %s",
                                            item.name, exc)
                _flush()

            await asyncio.gather(*[_confluence_one(i) for i in (confluence_universe or [])])

            us.diag = diag
            us.generated_ms = int(time.time() * 1000)
            model_rows = [r.model_dump() for r in us.rows]
            state.save_signal_cache(uid, model_rows, us.generated_ms)
        finally:
            us.scanning = False
            us.scanning_label = ""


scanner = KiteEngineScanner()


# ── setup chart (click-to-visualize) ────────────────────────────────────────
async def build_setup_chart(
    client, token: int, underlying: str, cfg: SterlingKiteEngineConfig,
) -> SetupChart:
    item = UniverseItem(name=underlying or str(token), tradingsymbol=underlying or str(token),
                        token=token, exchange="", option_exchange="NFO")
    candles = drop_forming(await client.get_candles(_inst(item), "1H", _LOOKBACK_BARS))
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    ha_o, ha_h, ha_l, ha_c = compute_heikin_ashi(o, h, l, c)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)

    secs = [int(cd.timestamp_ms // 1000) for cd in candles]
    points = [SetupPoint(time=secs[i], open=float(ha_o[i]), high=float(ha_h[i]),
                         low=float(ha_l[i]), close=float(ha_c[i])) for i in range(len(candles))]

    def _line(arr) -> List[SetupLine]:
        out: List[SetupLine] = []
        for i in range(cfg.warmup, len(candles)):
            v = float(arr[i])
            if v > 0:
                out.append(SetupLine(time=secs[i], value=v))
        return out

    fresh = np.where(longs | shorts)[0]
    entry_index = int(fresh[-1]) if len(fresh) else None
    return SetupChart(
        underlying=underlying or str(token), candles=points,
        st_fast=_line(r.l_fast), st_mid=_line(r.l_mid), st_slow=_line(r.l_slow),
        entry_index=entry_index, trail_target=cfg.trail_target,
        exit_mode=cfg.exit_mode,
    )
