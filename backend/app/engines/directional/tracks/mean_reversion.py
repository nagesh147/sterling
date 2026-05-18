"""
Issue 2 — Mean-reversion track scaffold (research-only).

Emits `candidate` events to the EventLedger when:
  * BB(20,2) width / Keltner(20,1.5,1.5) width < 1.0   (squeeze)
  * ADX(14) <= 20                                       (no trend)
  * |close - EMA20| / close >= 0.005                    (≥0.5% away from mean)

Direction:
  * close < EMA20 → "long" (expect reversion up)
  * close > EMA20 → "short" (expect reversion down)

Gating: only runs when `STERLING_ENABLE_MR_TRACK=1`. Does NOT call any
exchange adapter, does NOT enter trades, does NOT touch positions. Future
work will plug this into walk-forward and CPCV for edge validation.

Pure module. No I/O.
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.schemas.market import Candle
from app.engines.indicators.bollinger import bollinger_bands
from app.engines.indicators.keltner import keltner
from app.engines.indicators.ema import compute_ema
from app.engines.indicators.adx import adx as compute_adx
from app.engines.backtest.event_ledger import EventLedger


@dataclass(frozen=True)
class MRConfig:
    bb_period: int = 20
    bb_std: float = 2.0
    kc_period: int = 20
    kc_atr_mult: float = 1.5
    adx_period: int = 14
    adx_ceiling: float = 20.0
    ema_period: int = 20
    min_dist_pct: float = 0.005   # 0.5% away from EMA20
    min_warmup_bars: int = 30


@dataclass
class MRCandidate:
    bar_idx: int
    ts_ms: int
    direction: str   # "long" or "short"
    bb_kc_ratio: float
    adx: float
    dist_from_mean_pct: float


def enabled() -> bool:
    return os.environ.get("STERLING_ENABLE_MR_TRACK") == "1"


def compute_mr_candidates(
    candles: Sequence[Candle],
    *,
    config: Optional[MRConfig] = None,
) -> List[MRCandidate]:
    """
    Scan a candle stream and return one MRCandidate per bar that satisfies
    all three filters. Pure; no ledger emission. Use this as a research /
    smoke-test entry point.
    """
    cfg = config or MRConfig()
    if not enabled():
        return []
    if len(candles) < cfg.min_warmup_bars:
        return []
    closes = np.array([c.close for c in candles], dtype=np.float64)
    highs  = np.array([c.high  for c in candles], dtype=np.float64)
    lows   = np.array([c.low   for c in candles], dtype=np.float64)
    bb_lo, bb_mid, bb_up = bollinger_bands(closes, period=cfg.bb_period,
                                           std_mult=cfg.bb_std)
    kc_lo, kc_mid, kc_up = keltner(highs, lows, closes,
                                   period=cfg.kc_period,
                                   atr_mult=cfg.kc_atr_mult)
    bb_width = bb_up - bb_lo
    kc_width = kc_up - kc_lo
    ratio = np.where(kc_width > 0, bb_width / kc_width, np.inf)
    adx_arr = compute_adx(highs, lows, closes, cfg.adx_period)
    ema_arr = compute_ema(closes, cfg.ema_period)

    out: List[MRCandidate] = []
    for i in range(cfg.min_warmup_bars, len(candles)):
        if ratio[i] >= 1.0:
            continue
        ax = float(adx_arr[i]) if not np.isnan(adx_arr[i]) else 0.0
        if ax > cfg.adx_ceiling:
            continue
        if ema_arr[i] <= 0:
            continue
        dist = (closes[i] - ema_arr[i]) / closes[i]
        if abs(dist) < cfg.min_dist_pct:
            continue
        direction = "long" if dist < 0 else "short"
        out.append(MRCandidate(
            bar_idx=i,
            ts_ms=int(candles[i].timestamp_ms),
            direction=direction,
            bb_kc_ratio=float(ratio[i]),
            adx=ax,
            dist_from_mean_pct=float(dist),
        ))
    return out


def emit_to_ledger(
    candidates: Sequence[MRCandidate], ledger: EventLedger,
    *, asset: str, profile: str,
) -> int:
    """Append each candidate as a CANDIDATE event under track=mean_reversion."""
    n = 0
    for c in candidates:
        ledger.record_candidate(
            bar_idx=c.bar_idx, ts_ms=c.ts_ms,
            asset=asset, profile=profile,
            track="mean_reversion",
            features={
                "direction":           c.direction,
                "bb_kc_ratio":         c.bb_kc_ratio,
                "adx":                 c.adx,
                "dist_from_mean_pct":  c.dist_from_mean_pct,
            },
        )
        n += 1
    return n
