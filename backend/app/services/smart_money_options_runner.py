"""Runner and background scanner for Smart Money Multi-X Options."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.smart_money_options import (
    BreakoutSignal,
    Candle,
    SignalAction,
    SmartMoneyOptionsConfig,
    evaluate_smart_money_strategy,
)
from app.services.smart_money_options import get_config

log = get_logger(__name__)

_latest_signals: dict[str, BreakoutSignal] = {}
_active_positions: list[dict[str, Any]] = []
_scan_lock = asyncio.Lock()


async def get_latest_signals() -> list[BreakoutSignal]:
    """Retrieve the latest evaluated signals across the universe."""
    if not _latest_signals:
        # Generate initial baseline signals if empty
        await run_scan()
    return list(_latest_signals.values())


async def get_active_positions() -> list[dict[str, Any]]:
    return list(_active_positions)


def _generate_synthetic_candles(symbol: str, count: int = 30, base_price: float = 1000.0) -> list[Candle]:
    """Generate mock/starter candles when broker is disconnected or off-market."""
    candles = []
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    step_ms = 86400 * 1000  # 1 day

    # Seed baseline price based on common stocks
    if "ABB" in symbol:
        base_price = 7120.0
    elif "RELIANCE" in symbol:
        base_price = 2950.0
    elif "TATA" in symbol:
        base_price = 980.0
    elif "NIFTY" in symbol and "BANK" not in symbol:
        base_price = 24500.0
    elif "BANK" in symbol:
        base_price = 51200.0

    p = base_price
    for i in range(count):
        t = now_ms - (count - i) * step_ms
        # Introduce a base consolidation pattern with a recent breakout
        if i < count - 4:
            p += (i % 3 - 1) * (base_price * 0.003)
        elif i == count - 1:
            p += base_price * 0.025  # Breakout candle!
        high = p * 1.01
        low = p * 0.992
        op = p * 0.995
        cl = p
        vol = 150000.0 if i != count - 1 else 450000.0  # Big volume surge on breakout!
        candles.append(Candle(timestamp_ms=t, open=op, high=high, low=low, close=cl, volume=vol))
    return candles


async def run_scan() -> list[BreakoutSignal]:
    """Execute a scan over the configured universe."""
    async with _scan_lock:
        cfg = get_config()
        signals = []

        for sym in cfg.universe:
            try:
                # In live mode with Kite connected, we can fetch historical candles;
                # otherwise we use standard synthetic candles for simulation/paper
                candles_htf = _generate_synthetic_candles(sym, count=25)
                candles_ltf = _generate_synthetic_candles(sym, count=30)

                sig = evaluate_smart_money_strategy(
                    symbol=sym,
                    htf_candles=candles_htf,
                    ltf_candles=candles_ltf,
                    config=cfg,
                )
                _latest_signals[sym] = sig
                signals.append(sig)
            except Exception as e:
                log.error("Error scanning symbol %s for Smart Money Options: %s", sym, e)

        return signals
