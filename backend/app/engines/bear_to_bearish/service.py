"""Service & Auto-Execution Manager for Bear to Bearish Strategy Engine."""
from __future__ import annotations

import asyncio
import time
from typing import Dict, List, Optional
from app.core.logging import get_logger
from app.engines.bear_to_bearish.models import (
    BearToBearishConfig,
    BearToBearishSignal,
    BearToBearishSnapshot,
    PcrPoint,
)
from app.engines.bear_to_bearish.strategy import evaluate_bear_to_bearish

log = get_logger(__name__)

# Global runtime state for Bear to Bearish engine
_CONFIG = BearToBearishConfig()
_PCR_HISTORY: Dict[str, List[PcrPoint]] = {}
_LAST_SNAPSHOT: Optional[BearToBearishSnapshot] = None
_EXECUTED_SIGNALS: set[str] = set()


def get_config() -> BearToBearishConfig:
    return _CONFIG


def update_config(new_cfg: Dict[str, float | str | bool | List[str]]) -> BearToBearishConfig:
    global _CONFIG
    _CONFIG = BearToBearishConfig(**{**_CONFIG.model_dump(), **new_cfg})
    return _CONFIG


def add_pcr_point(underlying: str, point: PcrPoint) -> None:
    if underlying not in _PCR_HISTORY:
        _PCR_HISTORY[underlying] = []
    _PCR_HISTORY[underlying].append(point)
    # Retain latest 100 PCR prints per underlying
    if len(_PCR_HISTORY[underlying]) > 100:
        _PCR_HISTORY[underlying] = _PCR_HISTORY[underlying][-100:]


def get_pcr_history(underlying: str) -> List[PcrPoint]:
    return _PCR_HISTORY.get(underlying, [])


async def auto_execute_signal_if_enabled(signal: BearToBearishSignal) -> Optional[str]:
    """Auto-submit signal to OrderRouter if auto_execute is enabled and signal is ARMED."""
    if not _CONFIG.auto_execute:
        return None
    if signal.status != "armed":
        return None
    if signal.id in _EXECUTED_SIGNALS:
        return None

    try:
        from app.services.execution.order_router import OrderRouter, OrderRouterRequest

        # Default order router instance
        router = OrderRouter()
        req = OrderRouterRequest(
            underlying=signal.underlying,
            direction="short",
            instrument_type="option",
            option_type=signal.option_type,
            strike=signal.strike,
            expiry=signal.expiry,
            size=1.0,
            stop_loss=signal.stop_loss,
            target=signal.target_price,
            client_order_id=f"btb-{signal.id}",
            source_engine="bear_to_bearish",
        )

        log.info("Auto-executing Bear to Bearish signal for %s: %s", signal.underlying, req)
        resp = await router.submit(req)
        _EXECUTED_SIGNALS.add(signal.id)
        return resp.broker_order_id or resp.code
    except Exception as exc:
        log.warning("Bear to Bearish auto-execution failed for %s: %s", signal.underlying, exc)
        return None


async def run_scan() -> BearToBearishSnapshot:
    """Scan configured indices/stocks for Bear to Bearish signals."""
    global _LAST_SNAPSHOT
    now_ms = int(time.time() * 1000)
    cfg = get_config()

    rows: List[BearToBearishSignal] = []
    pcr_dict: Dict[str, List[Dict[str, float]]] = {}

    if not cfg.enabled:
        _LAST_SNAPSHOT = BearToBearishSnapshot(
            generated_ms=now_ms,
            scanning=False,
            scanning_label="",
            rows=[],
            pcr_history={},
            config=cfg.model_dump(),
            market_open=True,
            auto_execute=cfg.auto_execute,
        )
        return _LAST_SNAPSHOT

    # Sample candle data & PCR for scan target underlyings
    sample_spots = {
        "NIFTY": 24350.0,
        "BANKNIFTY": 52100.0,
        "FINNIFTY": 23400.0,
        "SENSEX": 80100.0,
    }

    for index_sym in cfg.scan_indices:
        pts = get_pcr_history(index_sym)
        if not pts:
            # Seed default PCR trajectory (opening 0.80 -> 0.58) for active engine demo
            pts = [
                PcrPoint(timestamp_ms=now_ms - 1800000, pcr=0.80),
                PcrPoint(timestamp_ms=now_ms - 1200000, pcr=0.72),
                PcrPoint(timestamp_ms=now_ms - 600000, pcr=0.64),
                PcrPoint(timestamp_ms=now_ms - 300000, pcr=0.58),
            ]
            _PCR_HISTORY[index_sym] = pts

        pcr_dict[index_sym] = [
            {
                "hhmm": time.strftime("%H:%M", time.localtime(p.timestamp_ms / 1000)),
                "pcr": p.pcr,
            }
            for p in pts
        ]

        spot = sample_spots.get(index_sym, 24000.0)
        # Sample Lower-High candle sequence
        candles = [
            {"open": spot, "high": spot + 80, "low": spot - 30, "close": spot + 50},
            {"open": spot + 50, "high": spot + 95, "low": spot + 10, "close": spot + 20},
            {"open": spot + 20, "high": spot + 60, "low": spot - 40, "close": spot - 20},
            {"open": spot - 20, "high": spot + 30, "low": spot - 70, "close": spot - 50},
        ]

        sig = evaluate_bear_to_bearish(
            underlying=index_sym,
            candles=candles,
            pcr_points=pts,
            config=cfg,
            current_spot=spot,
            now_ms=now_ms,
        )

        rows.append(sig)

        # Trigger auto execution if armed and auto_execute enabled
        if sig.status == "armed" and cfg.auto_execute:
            asyncio.create_task(auto_execute_signal_if_enabled(sig))

    _LAST_SNAPSHOT = BearToBearishSnapshot(
        generated_ms=now_ms,
        scanning=False,
        scanning_label="Scan complete",
        rows=rows,
        pcr_history=pcr_dict,
        config=cfg.model_dump(),
        next_scan_ms=now_ms + 60000,
        auto_scan=True,
        market_open=True,
        is_paper=True,
        auto_execute=cfg.auto_execute,
    )
    return _LAST_SNAPSHOT


def get_snapshot() -> BearToBearishSnapshot:
    if _LAST_SNAPSHOT is None:
        now_ms = int(time.time() * 1000)
        return BearToBearishSnapshot(
            generated_ms=now_ms,
            scanning=False,
            scanning_label="",
            rows=[],
            pcr_history={},
            config=_CONFIG.model_dump(),
            auto_execute=_CONFIG.auto_execute,
        )
    return _LAST_SNAPSHOT
