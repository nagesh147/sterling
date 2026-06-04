"""Diagnostic: why do scalping setups rarely arm?

Replicates the engine's own 4H/1H level gate (engines/scalping/levels.detect_levels)
against the SAME stored candles the live scanner uses, and reports, per symbol+TF:
  - current price
  - how many qualifying levels were detected (>= level_touches, clustered within tol%)
  - distance to the NEAREST level (%) vs the proximity gate the strategies use
    (price_action/smc/mean_reversion use tol*3 ; breakout uses tol*4)
  - macro trend regime (the macro_trend_filter direction gate)
"""
import numpy as np
from app.services import ohlcv_store
from app.schemas.market import Candle
from app.engines.sterling_engine.config import ScalpingProfile
from app.engines.sterling_engine.levels import detect_levels, price_near_level


def load(sym, res, n=400):
    # store rows are dicts: {time, open, high, low, close, volume}; time is epoch ms
    rows = ohlcv_store.get_candles(f"{sym}USD", res, limit=n)
    out = []
    for r in rows:
        out.append(Candle(
            timestamp_ms=int(r['time']),
            open=float(r['open']), high=float(r['high']),
            low=float(r['low']), close=float(r['close']),
            volume=float(r.get('volume') or 0.0),
        ))
    out.sort(key=lambda c: c.timestamp_ms)
    return out


def ema_last(arr, period):
    if len(arr) < period:
        return float(arr[-1])
    k = 2 / (period + 1)
    e = float(arr[0])
    for x in arr[1:]:
        e = x * k + e * (1 - k)
    return e


cfg = ScalpingProfile()  # defaults: touches=2, tol=0.5, trend EMA 50/100, flat band 0.5%
PROX = {"price_action/smc/mean_rev (tol*3)": cfg.level_tolerance_pct * 3,
        "breakout (tol*4)": cfg.level_tolerance_pct * 4}

for sym in ["BTC", "ETH"]:
    print(f"\n================  {sym}  ================")
    for res in ["1h", "4h", "1d"]:
        candles = load(sym, res)
        if len(candles) < 30:
            print(f"  [{res}] only {len(candles)} candles in store — profile can't run")
            continue
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        closes = np.array([c.close for c in candles])
        ts = np.array([c.timestamp_ms for c in candles], dtype=np.int64)
        price = float(closes[-1])
        levels = detect_levels(highs, lows, closes, ts, cfg)
        # nearest level (any), regardless of tolerance
        if levels:
            nearest = min(levels, key=lambda l: abs(l.price - price))
            dist_pct = abs(nearest.price - price) / price * 100
            near_str = f"nearest level {nearest.price:.2f} ({nearest.level_type}, {nearest.touches} touches) = {dist_pct:.2f}% away"
        else:
            near_str = "NO qualifying levels detected"
        # trend regime
        fast = ema_last(closes, cfg.macro_trend_ema_fast)
        slow = ema_last(closes, cfg.macro_trend_ema_slow)
        band = abs(fast - slow) / price * 100
        regime = "CHOP" if band < cfg.macro_trend_flat_band_pct else ("UP" if fast > slow else "DOWN")
        # does it pass each proximity gate?
        gates = []
        for label, tol in PROX.items():
            hit = price_near_level(price, levels, tolerance_pct=tol)
            gates.append(f"{label}: gate=±{tol:.1f}% -> {'ARM-ELIGIBLE' if hit else 'no'}")
        print(f"  [{res}] price={price:.2f} | {len(levels)} levels | {near_str}")
        print(f"        regime={regime} (EMA{cfg.macro_trend_ema_fast}/{cfg.macro_trend_ema_slow} gap {band:.2f}%, trendFilter blocks {'shorts' if regime=='UP' else 'longs' if regime=='DOWN' else 'nothing'})")
        for g in gates:
            print(f"        {g}")
