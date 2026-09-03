"""Kite runtime adapter for the advisory opening-volume leader engine."""

from __future__ import annotations

import asyncio
import time as monotonic_time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.engines.nifty_orb_options import Bar
from app.engines.opening_volume_leaders import (
    IST,
    STRATEGY_CONTRACT,
    LeaderSignal,
    LeaderTier,
    OpeningVolumeConfig,
    evaluate_leader,
    rank_leaders,
)
from app.services.kite_engine.stock_registry import CURATED_STOCK_NAMES

_HISTORY_CACHE_TTL_SECONDS = 45.0
_HISTORY_CALL_SPACING_SECONDS = 0.36
_history_cache: dict[tuple[str, str, int, int, datetime], tuple[float, list[Bar]]] = {}


class _HistoricalPacer:
    """Space Kite historical requests so a concurrent scan cannot burst 429s."""

    def __init__(self, spacing_seconds: float) -> None:
        self._spacing_seconds = spacing_seconds
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = monotonic_time.monotonic()
            if now < self._next_at:
                await asyncio.sleep(self._next_at - now)
                now = monotonic_time.monotonic()
            self._next_at = now + self._spacing_seconds


_historical_pacer = _HistoricalPacer(_HISTORY_CALL_SPACING_SECONDS)


def _as_ist(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


@dataclass(frozen=True)
class LiveLeaderScanConfig:
    symbols: tuple[str, ...] = ()
    scan_all_stocks: bool = True
    include_watch: bool = False
    max_candidates: int = 40
    concurrency: int = 3
    history_calendar_days: int = 45

    def validate(self) -> LiveLeaderScanConfig:
        if self.max_candidates < 1 or self.max_candidates > 100:
            raise ValueError("max_candidates must be between 1 and 100")
        if self.concurrency < 1 or self.concurrency > 8:
            raise ValueError("concurrency must be between 1 and 8")
        if self.history_calendar_days < 30 or self.history_calendar_days > 60:
            raise ValueError("history_calendar_days must be between 30 and 60")
        if not self.scan_all_stocks and not self.symbols:
            raise ValueError("select symbols or enable scan_all_stocks")
        return self


def _normalize_universe(config: LiveLeaderScanConfig) -> list[str]:
    allowed = tuple(dict.fromkeys(symbol.upper() for symbol in CURATED_STOCK_NAMES))
    allowed_set = set(allowed)
    if config.scan_all_stocks:
        return list(allowed[: config.max_candidates])
    requested = list(
        dict.fromkeys(
            symbol.strip().upper() for symbol in config.symbols if symbol.strip()
        )
    )
    unsupported = [symbol for symbol in requested if symbol not in allowed_set]
    if unsupported:
        raise ValueError(
            "symbols outside Sterling's curated high-liquidity universe: "
            + ", ".join(sorted(unsupported))
        )
    return requested[: config.max_candidates]


def _bar_from_kite(row: Sequence[Any]) -> Bar:
    from app.services.exchanges.kite.client import _parse_kite_ts

    if len(row) < 5:
        raise ValueError("Kite historical row has fewer than five OHLC fields")
    timestamp_ms = _parse_kite_ts(str(row[0]))
    timestamp = datetime.fromtimestamp(
        timestamp_ms / 1000.0, tz=timezone.utc
    ).astimezone(IST)
    return Bar(
        timestamp=timestamp,
        open=float(row[1]),
        high=float(row[2]),
        low=float(row[3]),
        close=float(row[4]),
        volume=float(row[5]) if len(row) > 5 else 0.0,
    )


async def _history(
    client,
    *,
    uid: str,
    symbol: str,
    token: int,
    as_of: datetime,
    history_calendar_days: int,
) -> list[Bar]:
    observed_at = _as_ist(as_of)
    # A new minute makes one more candle causally available.  Including the
    # completion boundary prevents a cache hit at 09:17 from reusing a 09:16
    # snapshot that could not yet contain the completed 09:16 bar.
    completed_through = observed_at.replace(second=0, microsecond=0)
    key = (uid, symbol, token, history_calendar_days, completed_through)
    cached = _history_cache.get(key)
    now_mono = monotonic_time.monotonic()
    if cached and now_mono - cached[0] < _HISTORY_CACHE_TTL_SECONDS:
        return cached[1]

    start = observed_at - timedelta(days=history_calendar_days)
    await _historical_pacer.wait()
    payload = await client.get_historical(
        token,
        "minute",
        start.strftime("%Y-%m-%d 09:00:00"),
        observed_at.strftime("%Y-%m-%d %H:%M:%S"),
    )
    bars: list[Bar] = []
    for row in (payload or {}).get("candles", []) or []:
        try:
            bars.append(_bar_from_kite(row))
        except (IndexError, TypeError, ValueError):
            continue
    bars.sort(key=lambda bar: bar.timestamp)
    _history_cache[key] = (monotonic_time.monotonic(), bars)
    expired = [
        cache_key
        for cache_key, (created_at, _) in _history_cache.items()
        if monotonic_time.monotonic() - created_at >= _HISTORY_CACHE_TTL_SECONDS
    ]
    for cache_key in expired:
        _history_cache.pop(cache_key, None)
    return bars


def _breadth(signals: Sequence[LeaderSignal]) -> dict[str, float | int | None]:
    advances = sum(
        1
        for signal in signals
        if signal.day_change_pct is not None and signal.day_change_pct > 0
    )
    declines = sum(
        1
        for signal in signals
        if signal.day_change_pct is not None and signal.day_change_pct < 0
    )
    unchanged = sum(1 for signal in signals if signal.day_change_pct == 0)
    return {
        "advances": advances,
        "declines": declines,
        "unchanged": unchanged,
        "observed": advances + declines + unchanged,
        "advance_decline_ratio": advances / declines if declines else None,
    }


async def scan_kite_leaders(
    uid: str,
    *,
    as_of: datetime | None = None,
    scan_config: LiveLeaderScanConfig | None = None,
    signal_config: OpeningVolumeConfig | None = None,
) -> dict:
    """Scan Sterling's safe F&O-equity universe without placing any orders."""

    scan_config = (scan_config or LiveLeaderScanConfig()).validate()
    signal_config = (signal_config or OpeningVolumeConfig()).validate()
    normalized_uid = str(uid or "").strip()
    if not normalized_uid:
        raise ValueError("authenticated user is required")
    observed_at = _as_ist(as_of or datetime.now(IST))
    symbols = _normalize_universe(scan_config)

    from app.services.exchanges.kite import accounts
    from app.services.nifty_orb_scanner import _kite_instrument

    account = accounts.get_active(normalized_uid)
    if not account:
        raise RuntimeError("no active Kite account")
    client = await accounts.acquire_client(account)
    semaphore = asyncio.Semaphore(scan_config.concurrency)

    async def evaluate(symbol: str) -> tuple[LeaderSignal | None, str | None]:
        async with semaphore:
            try:
                instrument = await _kite_instrument(client, symbol)
                token = int(instrument.zerodha_token or 0)
                if token <= 0:
                    raise RuntimeError(f"no Kite cash token for {symbol}")
                bars = await _history(
                    client,
                    uid=normalized_uid,
                    symbol=symbol,
                    token=token,
                    as_of=observed_at,
                    history_calendar_days=scan_config.history_calendar_days,
                )
                return (
                    evaluate_leader(
                        symbol,
                        bars,
                        as_of=observed_at,
                        config=signal_config,
                    ),
                    None,
                )
            # A single broker/instrument failure must stay isolated so the
            # advisory universe scan can report all other symbols.
            except Exception as exc:  # noqa: BLE001
                return None, str(exc)

    outcomes = await asyncio.gather(*(evaluate(symbol) for symbol in symbols))
    evaluated: list[LeaderSignal] = []
    failures: list[dict[str, str]] = []
    for symbol, (signal, error) in zip(symbols, outcomes):
        if signal is not None:
            evaluated.append(signal)
        else:
            failures.append(
                {"symbol": symbol, "error": error or "unknown evaluation failure"}
            )

    ranked = rank_leaders(evaluated)
    leaders = [signal for signal in ranked if signal.is_leader]
    watch = [signal for signal in ranked if signal.tier is LeaderTier.WATCH]
    return {
        "strategy": STRATEGY_CONTRACT,
        "as_of": observed_at.isoformat(),
        "universe_count": len(symbols),
        "evaluated_count": len(evaluated),
        "leader_count": len(leaders),
        "watch_count": len(watch),
        "breadth": _breadth(evaluated),
        "leaders": [signal.to_dict() for signal in leaders],
        "watch": [signal.to_dict() for signal in watch]
        if scan_config.include_watch
        else [],
        "failures": failures,
    }
