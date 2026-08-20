"""Bounded multi-underlying scanner for the NIFTY ORB options strategy.

This module deliberately contains no exchange I/O. The runtime supplies a
bar-fetching callable, while this engine owns universe normalization, ranking,
and concurrency limits. That separation keeps exchange concerns out of the
signal engine and makes the scanner deterministic in tests.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Awaitable, Callable, Iterable, Sequence
from zoneinfo import ZoneInfo

from app.engines.nifty_orb_options import Bar, Signal, StrategyConfig, generate_signal

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class UniverseInstrument:
    symbol: str
    kind: str = "stock"  # index | stock
    tradable: bool = True


@dataclass(frozen=True)
class UniverseScanConfig:
    max_candidates: int = 30
    concurrency: int = 6
    min_confidence: float = 0.55
    include_indices: bool = True

    def validate(self) -> None:
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be >= 1")
        if self.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must be between 0 and 1")


@dataclass(frozen=True)
class UniverseSignal:
    instrument: UniverseInstrument
    signal: Signal

    @property
    def rank_key(self) -> tuple[float, float, float, str]:
        # Confidence first; normalized breakout and volume are tie-breakers.
        return (
            self.signal.confidence,
            abs(self.signal.breakout_distance) / max(self.signal.atr, 1e-9),
            self.signal.volume_ratio,
            self.instrument.symbol,
        )


BarFetcher = Callable[[UniverseInstrument, StrategyConfig], Awaitable[Sequence[Bar]]]


def normalize_universe(
    instruments: Iterable[UniverseInstrument],
    *,
    config: UniverseScanConfig = UniverseScanConfig(),
) -> list[UniverseInstrument]:
    """Deduplicate and deterministically bound a scan universe."""
    config.validate()
    seen: set[str] = set()
    out: list[UniverseInstrument] = []
    for item in instruments:
        symbol = item.symbol.strip().upper()
        if not symbol or symbol in seen or not item.tradable:
            continue
        if item.kind == "index" and not config.include_indices:
            continue
        seen.add(symbol)
        out.append(replace(item, symbol=symbol))
        if len(out) >= config.max_candidates:
            break
    return out


async def scan_universe(
    instruments: Iterable[UniverseInstrument],
    *,
    strategy_config: StrategyConfig,
    scan_config: UniverseScanConfig = UniverseScanConfig(),
    fetch_bars: BarFetcher,
    as_of: datetime | None = None,
) -> list[UniverseSignal]:
    """Fetch bounded candidates concurrently and return actionable signals.

    ``as_of`` is the realtime clock. It is passed to every ``generate_signal``
    call so the currently-forming candle cannot become a signal -- a bar
    adapter that forgets to drop it can no longer cause a repaint here. It
    defaults to now in IST; replay and tests pass a fixed value.

    A failed or insufficient *instrument* is skipped rather than failing the whole
    scan, but a bad strategy configuration is not: it is validated once up front,
    because swallowing it per-instrument would turn a misconfiguration into a
    silent "no signals today". Results are sorted strongest-first and are
    deterministic for equal scores because symbol is the final tie-breaker.
    """
    strategy_config.validate()
    now = as_of or datetime.now(IST)
    candidates = normalize_universe(instruments, config=scan_config)
    semaphore = asyncio.Semaphore(scan_config.concurrency)

    async def scan_one(item: UniverseInstrument) -> UniverseSignal | None:
        async with semaphore:
            try:
                bars = await fetch_bars(item, strategy_config)
                if not bars:
                    return None
                signal = generate_signal(bars, strategy_config, as_of=now)
                if signal.direction == "NONE" or signal.confidence < scan_config.min_confidence:
                    return None
                return UniverseSignal(item, signal)
            except (ValueError, KeyError, RuntimeError):
                return None

    results = await asyncio.gather(*(scan_one(item) for item in candidates))
    actionable = [item for item in results if item is not None]
    actionable.sort(key=lambda item: item.rank_key, reverse=True)
    return actionable
