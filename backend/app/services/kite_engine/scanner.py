"""Throttled background scanner for the Kite triple-SuperTrend engine.

Per active Kite user: fetch 1H candles for each universe item (cached, rate
throttled), drop the forming bar, run the broker-agnostic engine, and collect the
"ready" rows (fresh full-alignment transition on the latest closed bar). Strike
selection is done from the already-loaded option dumps — no extra quote calls.

Kite types are touched only here and in the endpoints; the engine package stays
broker-agnostic. Nothing here imports another engine's strategy logic.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

import numpy as np

from app.core.logging import get_logger
from app.domain.models import Candle
from app.engines.indicators.heikin_ashi import compute_heikin_ashi
from app.engines.triple_supertrend.config import TripleSupertrendConfig
from app.engines.triple_supertrend.engine import TripleSupertrendEngine
from app.engines.triple_supertrend.regime import compute_regime, entry_transitions
from app.engines.triple_supertrend.schemas import (
    AlignmentChip, EngineSignalRow, OptionLeg, SetupChart, SetupLine, SetupPoint,
)
from app.schemas.instruments import InstrumentMeta
from app.services.kite_engine.strikes import chain_rows_for, pick_strikes
from app.services.kite_engine.universe import UniverseItem

log = get_logger(__name__)

_CANDLE_TTL_S = 180          # re-use cached 1H candles for ~3 min
_CONCURRENCY = 3             # Kite historical ~3 req/s
_TF_MS = 3_600_000           # 1H bar in ms
_LOOKBACK_BARS = 320

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


def evaluate_item(
    engine: TripleSupertrendEngine, item: UniverseItem,
    candles: Sequence[Candle], cfg: TripleSupertrendConfig,
) -> Optional[EngineSignalRow]:
    """Run the engine on closed candles; return a row only on a fresh transition."""
    if len(candles) <= cfg.warmup + 1:
        return None
    o = np.array([c.open for c in candles], float)
    h = np.array([c.high for c in candles], float)
    l = np.array([c.low for c in candles], float)
    c = np.array([c.close for c in candles], float)
    r = compute_regime(o, h, l, c, cfg)
    longs, shorts = entry_transitions(r)
    i = len(c) - 1
    if not (longs[i] or shorts[i]):
        return None
    direction = "long" if longs[i] else "short"
    return EngineSignalRow(
        underlying=item.name, token=item.token, exchange=item.option_exchange,
        regime="BULL" if direction == "long" else "BEAR",
        alignment=AlignmentChip(fast=int(r.t_fast[i]), mid=int(r.t_mid[i]), slow=int(r.t_slow[i])),
        direction=direction, option_type="CE" if direction == "long" else "PE",
        spot=float(c[i]), stop_loss=float(r.line(cfg.trail_target)[i]),
        score=85.0, timestamp_ms=int(candles[i].timestamp_ms),
    )


def attach_strikes(
    row: EngineSignalRow, option_rows: Sequence[dict], *, option_name: str,
    moneynesses: Sequence[str] = ("ATM",), today: Optional[date] = None,
) -> EngineSignalRow:
    """Resolve and attach an option leg per selected moneyness from a raw dump.

    ``option_name`` is the option-chain underlying ("NIFTY"), which differs from
    ``row.underlying`` (the display name, e.g. "NIFTY 50") for indices.
    """
    today = today or datetime.now(_IST).date()
    chain = chain_rows_for(option_rows, option_name, today)
    picks = pick_strikes(chain, spot=row.spot, direction=row.direction, moneynesses=moneynesses)
    row.legs = [
        OptionLeg(moneyness=m, option_type=p.option_type, option_symbol=p.option_symbol,
                  strike=p.strike, expiry=p.expiry, lot_size=p.lot_size or None)
        for m, p in picks
    ]
    return row


def option_order_args(row: EngineSignalRow, leg: Optional[OptionLeg] = None) -> Optional[dict]:
    """Pure mapping: a ready row (+ chosen leg) → Kite option-BUY order args.

    Options buying is always a BUY (a call for bull, a put for bear); quantity is
    one lot (``lot_size``). Defaults to the first/primary leg for auto-exec.
    The advisory ST trailing stop rides along as the SL trigger.
    """
    leg = leg or (row.legs[0] if row.legs else None)
    if leg is None:
        return None
    return {
        "option_symbol": leg.option_symbol,
        "side": "buy",
        "size": int(leg.lot_size or 0),
        "exchange": row.exchange,
        "stop_loss": float(row.stop_loss),
    }


# ── per-user scan state ─────────────────────────────────────────────────────
@dataclass
class UserScan:
    engine: TripleSupertrendEngine
    rows: List[EngineSignalRow] = field(default_factory=list)
    candle_cache: Dict[int, tuple] = field(default_factory=dict)  # token -> (mono_ts, candles)
    generated_ms: int = 0
    scanning: bool = False


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

    def _user(self, uid: str, cfg: TripleSupertrendConfig) -> UserScan:
        us = self._users.get(uid)
        if us is None:
            us = UserScan(engine=TripleSupertrendEngine(cfg))
            self._users[uid] = us
        return us

    def snapshot(self, uid: str) -> UserScan:
        return self._users.get(uid) or UserScan(engine=TripleSupertrendEngine())

    async def _fetch_1h(self, client, us: UserScan, item: UniverseItem) -> List[Candle]:
        hit = us.candle_cache.get(item.token)
        if hit and (time.monotonic() - hit[0]) < _CANDLE_TTL_S:
            return hit[1]
        candles = await client.get_candles(_inst(item), "1H", _LOOKBACK_BARS)
        us.candle_cache[item.token] = (time.monotonic(), candles)
        return candles

    async def scan(
        self, *, uid: str, client, universe: List[UniverseItem],
        nfo_rows: Sequence[dict], bfo_rows: Sequence[dict],
        cfg: TripleSupertrendConfig, moneyness: Sequence[str] = ("ATM",),
        place_cb: Optional[PlaceCb] = None,
    ) -> None:
        us = self._user(uid, cfg)
        us.engine.cfg = cfg
        us.scanning = True
        sem = asyncio.Semaphore(_CONCURRENCY)
        today = datetime.now(_IST).date()
        rows: List[EngineSignalRow] = []

        async def _one(item: UniverseItem) -> None:
            if not item.token:
                return
            async with sem:
                try:
                    candles = drop_forming(await self._fetch_1h(client, us, item))
                except Exception as exc:  # noqa: BLE001
                    log.warning("kite-engine scan candle fail %s: %s", item.name, exc)
                    return
            row = evaluate_item(us.engine, item, candles, cfg)
            if row is None:
                return
            option_rows = nfo_rows if item.option_exchange == "NFO" else bfo_rows
            attach_strikes(row, option_rows, option_name=item.tradingsymbol,
                           moneynesses=moneyness, today=today)
            rows.append(row)
            if place_cb is not None and row.legs:
                try:
                    await place_cb(row, item)
                except Exception as exc:  # noqa: BLE001
                    log.warning("kite-engine auto-exec fail %s: %s", item.name, exc)

        await asyncio.gather(*[_one(i) for i in universe])
        us.rows = rows
        us.generated_ms = int(time.time() * 1000)
        us.scanning = False


scanner = KiteEngineScanner()


# ── setup chart (click-to-visualize) ────────────────────────────────────────
async def build_setup_chart(
    client, token: int, underlying: str, cfg: TripleSupertrendConfig,
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
    )
