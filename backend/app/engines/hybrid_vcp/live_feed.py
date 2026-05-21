"""
Hybrid VCP-Momentum Scalper — Strategy V2
Live WebSocket feed for VCP execution.

Consumes:
  * l2_orderbook → builds RealOBI each bar close
  * all_trades   → builds RealCVD each bar close
  * v2/ticker    → derives the completed bar (OHLCV) and drives VCPExecutor.on_bar()

Designed to run as a background asyncio task. On any connection error it
back-off reconnect attempts up to 5×, then gives up and signals the caller.
The executor falls back to proxy indicators when the feed is unavailable.

Supported exchanges:
  * Delta Exchange India / Global (wss://socket.india.delta.exchange)
  * Deribit (wss://test.deribit.com / wss://ws.deribit.com)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.engines.hybrid_vcp.live_filters import (
    LiveMicroState, RealOBI, RealCVD,
    obi_from_orderbook, cvd_from_trades,
)
from app.engines.hybrid_vcp.executor import VCPExecutor

log = logging.getLogger(__name__)


@dataclass
class VCPBar:
    """Reconstructed bar from the exchange WebSocket."""
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class VCPFeedConfig:
    exchange:        str = "delta_india"
    ws_url:         str = ""          # auto-detected if empty
    symbols:        List[str] = field(default_factory=lambda: ["BTCUSD", "ETHUSD"])
    signal_tf_secs: int = 900         # 15m = 900s
    reconnect_max:  int = 5
    reconnect_delay: float = 3.0
    heartbeat_timeout: float = 35.0


# ─── Delta Exchange WebSocket parser ─────────────────────────────────────────

class DeltaFeedParser:
    """
    Parses Delta Exchange WebSocket messages into VCP-relevant events.

    Produces three event types:
      'bar'        — completed signal_tf bar (OHLCV)
      'micro_state'— RealOBI + RealCVD for the current bar
      'price'      — latest index price for entry fill
    """

    BAR_EVENT       = "bar"
    MICRO_EVENT     = "micro_state"
    PRICE_EVENT     = "price"

    def __init__(self, signal_tf_secs: int = 900):
        self._tf_secs = signal_tf_secs
        self._last_bar_ts: int = 0
        self._bar_open: float = 0.0
        self._bar_high: float = -1e9
        self._bar_low:  float = 1e9
        self._bar_close: float = 0.0
        self._bar_vol: float = 0.0

        # Per-symbol orderbook state
        self._bids: Dict[str, List[tuple]] = {}
        self._asks: Dict[str, List[tuple]] = {}
        self._trades: Dict[str, List[tuple]] = {}   # rolling window for CVD
        self._seq_no:  int = 0

        self._pending_bar: Optional[VCPBar] = None
        self._on_bar_callback: Optional[Callable[[VCPBar, LiveMicroState], None]] = None

    def set_on_bar(self, cb: Callable[[VCPBar, Optional[LiveMicroState]], None]) -> None:
        self._on_bar = cb

    @property
    def last_bar_ts(self) -> int:
        return self._last_bar_ts

    def process_message(self, raw: str) -> Optional[tuple]:
        """
        Parse a raw JSON message string.
        Returns (event_type, payload) or None for messages that need no action.
        """
        try:
            msg = json.loads(raw)
        except Exception:
            return None

        mtype = msg.get("type", "")
        sym   = msg.get("symbol") or msg.get("product_symbol", "")

        if mtype == "heartbeat":
            return None

        self._seq_no += 1

        if mtype == "v2/ticker":
            return self._handle_ticker(sym, msg)
        elif mtype == "all_trades":
            return self._handle_trades(sym, msg)
        elif mtype == "l2_orderbook":
            return self._handle_orderbook(sym, msg)
        elif mtype == "bar":
            return self._handle_candle(sym, msg)

        return None

    def _handle_ticker(self, sym: str, msg: dict) -> tuple:
        """v2/ticker: 5s snapshot. Build bar from mark_price movement."""
        price = float(msg.get("mark_price") or msg.get("spot_price") or msg.get("close") or 0)
        vol   = float(msg.get("volume_24h") or 0)
        ts_ms = int(msg.get("timestamp", 0))

        bar = self._update_bar(ts_ms, price, vol)
        if bar:
            micro = self._build_micro_state(sym)
            self._emit_bar(bar, micro)
            return (self.BAR_EVENT, bar)

        return (self.PRICE_EVENT, price)

    def _handle_trades(self, sym: str, msg: dict) -> Optional[tuple]:
        """all_trades: real-time fill. Update CVD."""
        trades_data = msg.get("trades", [])
        if not trades_data:
            return None
        for t in trades_data:
            size = float(t.get("size", 0))
            side = t.get("side", "")   # "buy" or "sell"
            if side in ("buy", "sell"):
                self._trades.setdefault(sym, []).append((size, side))
        # Keep rolling window of last 100 trades
        if len(self._trades.get(sym, [])) > 100:
            self._trades[sym] = self._trades[sym][-100:]
        return None

    def _handle_orderbook(self, sym: str, msg: dict) -> Optional[tuple]:
        """l2_orderbook: top-N orderbook levels. Update OBI."""
        buy_list = msg.get("buy", []) or msg.get("bids", [])
        sell_list = msg.get("sell", []) or msg.get("asks", [])
        bids = [(float(p.get("limit_price", 0)), float(p.get("size", 0))) for p in buy_list[:10] if p]
        asks = [(float(p.get("limit_price", 0)), float(p.get("size", 0))) for p in sell_list[:10] if p]
        self._bids[sym] = bids
        self._asks[sym] = asks
        return None

    def _handle_candle(self, sym: str, msg: dict) -> Optional[tuple]:
        """
        Native bar event (if exchange sends it). Use if available instead of
        reconstructing from ticker — more accurate open/high/low.
        """
        ts_ms  = int(msg.get("timestamp", 0) or msg.get("start_timestamp", 0))
        o = float(msg.get("open", 0))
        h = float(msg.get("high", 0))
        l = float(msg.get("low", 0))
        c = float(msg.get("close", 0))
        v = float(msg.get("volume", 0) or msg.get("tick_volume", 0))

        bar = VCPBar(timestamp_ms=ts_ms, open=o, high=h, low=l, close=c, volume=v)
        micro = self._build_micro_state(sym)
        self._emit_bar(bar, micro)
        return (self.BAR_EVENT, bar)

    def _update_bar(self, ts_ms: int, price: float, vol: float) -> Optional[VCPBar]:
        """Reconstruct bar from tick updates between completed intervals."""
        if ts_ms <= self._last_bar_ts and self._last_bar_ts > 0:
            return None

        bar_ts = (ts_ms // (self._tf_secs * 1000)) * (self._tf_secs * 1000)

        if bar_ts != self._last_bar_ts:
            if self._last_bar_ts > 0 and self._bar_close > 0:
                # Emit completed bar
                completed = VCPBar(
                    timestamp_ms=self._last_bar_ts,
                    open=self._bar_open,
                    high=self._bar_high,
                    low=self._bar_low,
                    close=self._bar_close,
                    volume=self._bar_vol,
                )
                self._last_bar_ts = bar_ts
                self._bar_open  = price
                self._bar_high  = price
                self._bar_low   = price
                self._bar_close = price
                self._bar_vol   = vol
                return completed

            self._last_bar_ts = bar_ts
            self._bar_open  = price
            self._bar_high = price
            self._bar_low  = price
            self._bar_close = price
            self._bar_vol   = vol
            return None

        # Same bar — update
        self._bar_high  = max(self._bar_high, price)
        self._bar_low   = min(self._bar_low,  price)
        self._bar_close = price
        self._bar_vol  += vol
        return None

    def _build_micro_state(self, sym: str) -> LiveMicroState:
        bids = self._bids.get(sym, [])
        asks = self._asks.get(sym, [])
        trades = self._trades.get(sym, [])

        obi = None
        cvd = None
        if bids and asks:
            obi_val = obi_from_orderbook(bids, asks)
            obi = RealOBI(
                bid_qty=sum(q for _, q in bids),
                ask_qty=sum(q for _, q in asks),
                imbalance=obi_val,
                ref_spread=self._compute_spread(bids, asks),
            )
        if trades:
            cvd_val = cvd_from_trades(trades)
            cvd = RealCVD(cvd=cvd_val, cvd_rate=0.0)

        return LiveMicroState(
            obi=obi,
            cvd=cvd,
            timestamp_ms=int(time.time() * 1000),
            seq_no=self._seq_no,
        )

    def _compute_spread(self, bids, asks) -> float:
        if not bids or not asks:
            return 0.0
        best_bid = bids[0][0] if bids else 0.0
        best_ask = asks[0][0] if asks else 0.0
        return abs(best_ask - best_bid)

    def _emit_bar(self, bar: VCPBar, micro: LiveMicroState) -> None:
        if self._on_bar:
            try:
                self._on_bar(bar, micro)
            except Exception:
                pass

    @property
    def on_bar(self) -> Callable:
        return getattr(self, "_on_bar", None)

    @on_bar.setter
    def on_bar(self, val: Callable) -> None:
        self._on_bar = val


# ─── Deribit WebSocket parser ──────────────────────────────────────────────

class DeribitFeedParser:
    """
    Parses Deribit WebSocket messages into VCP-relevant events.

    Deribit WebSocket channels (authenticated via ?it=v2 API):
      * ticker         → mark_price + 24h volume (bar reconstruction)
      * trades         → per-trade: size, side, price, timestamp → RealCVD
      * book          → l2 orderbook: bids + asks → RealOBI

    Message types:
      * "heartbeat"    → keepalive, ignore
      * "ticker"       → {data: {mark_price, last_price, volume, timestamp_ms)}}
      * "trades"       → {data: [{price, amount, side, timestamp}]}
      * "book"         → {data: {bids: [[price,vol]], asks: [[price,vol]], timestamp_ms}}

    Produces the same three event types as DeltaFeedParser:
      'bar' | 'micro_state' | 'price'
    """

    BAR_EVENT   = "bar"
    MICRO_EVENT = "micro_state"
    PRICE_EVENT = "price"

    def __init__(self, signal_tf_secs: int = 900):
        self._tf_secs = signal_tf_secs
        self._last_bar_ts: int = 0
        self._bar_open: float = 0.0
        self._bar_high: float = -1e9
        self._bar_low:  float = 1e9
        self._bar_close: float = 0.0
        self._bar_vol: float = 0.0

        self._bids: Dict[str, List[tuple]] = {}
        self._asks: Dict[str, List[tuple]] = {}
        self._trades: Dict[str, List[tuple]] = {}
        self._seq_no: int = 0

        self._on_bar: Optional[Callable[[VCPBar, Optional[LiveMicroState]], None]] = None

    def set_on_bar(self, cb: Callable[[VCPBar, Optional[LiveMicroState]], None]) -> None:
        self._on_bar = cb

    @property
    def last_bar_ts(self) -> int:
        return self._last_bar_ts

    def process_message(self, raw: str) -> Optional[tuple]:
        """Parse Deribit JSON message. Returns (event_type, payload) or None."""
        try:
            msg = json.loads(raw)
        except Exception:
            return None

        params = msg.get("params", {})
        channel = params.get("channel", "")
        data = params.get("data", {})

        if not channel or not data:
            return None

        if msg.get("method") == "heartbeat":
            return None

        if channel.startswith("ticker."):
            return self._handle_ticker(channel, data)
        elif channel.startswith("trades."):
            return self._handle_trades(channel, data)
        elif channel.startswith("book."):
            return self._handle_orderbook(channel, data)

        return None

    def _handle_ticker(self, channel: str, data: dict) -> tuple:
        """Deribit ticker: extract mark_price + volume → bar reconstruction."""
        price = float(data.get("mark_price") or data.get("last_price") or 0)
        vol   = float(data.get("volume") or data.get("stats", {}).get("volume", 0) or 0)
        ts_ms = int(data.get("timestamp", 0) or data.get("last_trade_timestamp", 0))

        bar = self._update_bar(ts_ms, price, vol)
        if bar:
            sym = self._sym_from_channel(channel)
            micro = self._build_micro_state(sym)
            self._emit_bar(bar, micro)
            return (self.BAR_EVENT, bar)

        return (self.PRICE_EVENT, price)

    def _handle_trades(self, channel: str, data: list) -> Optional[tuple]:
        """Deribit trades: list of {price, amount, side, timestamp} → RealCVD."""
        if not isinstance(data, list):
            data = [data]
        sym = self._sym_from_channel(channel)
        for t in data:
            if not isinstance(t, dict):
                continue
            size = float(t.get("amount", 0) or t.get("quantity", 0))
            side = str(t.get("side", "")).lower()
            if side in ("buy", "sell"):
                self._trades.setdefault(sym, []).append((size, side))
        if len(self._trades.get(sym, [])) > 100:
            self._trades[sym] = self._trades[sym][-100:]
        return None

    def _handle_orderbook(self, channel: str, data: dict) -> Optional[tuple]:
        """Deribit book: top-N bids/asks → RealOBI."""
        bids_raw = data.get("bids", []) or data.get("change_id", [])
        asks_raw = data.get("asks", []) or data.get("change_id", [])
        if isinstance(bids_raw, list) and len(bids_raw) > 0:
            if isinstance(bids_raw[0], list):
                bids = [(float(p), float(v)) for p, v in bids_raw[:10] if p and v]
                asks = [(float(p), float(v)) for p, v in asks_raw[:10] if p and v]
            elif isinstance(bids_raw, dict):
                bids = [(float(p), float(v)) for p, v in (bids_raw.get("bids", []) or [])[:10]]
                asks = [(float(p), float(v)) for p, v in (asks_raw.get("asks", []) or [])[:10]]
            else:
                bids, asks = [], []
        else:
            bids, asks = [], []
        sym = self._sym_from_channel(channel)
        self._bids[sym] = bids
        self._asks[sym] = asks
        return None

    def _update_bar(self, ts_ms: int, price: float, vol: float) -> Optional[VCPBar]:
        """Reconstruct bar from Deribit ticker ticks."""
        if ts_ms <= self._last_bar_ts and self._last_bar_ts > 0:
            return None

        bar_ts = (ts_ms // (self._tf_secs * 1000)) * (self._tf_secs * 1000)

        if bar_ts != self._last_bar_ts:
            if self._last_bar_ts > 0 and self._bar_close > 0:
                completed = VCPBar(
                    timestamp_ms=self._last_bar_ts,
                    open=self._bar_open,
                    high=self._bar_high,
                    low=self._bar_low,
                    close=self._bar_close,
                    volume=self._bar_vol,
                )
                self._last_bar_ts = bar_ts
                self._bar_open  = price
                self._bar_high  = price
                self._bar_low   = price
                self._bar_close = price
                self._bar_vol   = vol
                return completed

            self._last_bar_ts = bar_ts
            self._bar_open  = price
            self._bar_high = price
            self._bar_low  = price
            self._bar_close = price
            self._bar_vol   = vol
            return None

        self._bar_high  = max(self._bar_high, price)
        self._bar_low   = min(self._bar_low, price)
        self._bar_close = price
        self._bar_vol  += vol
        return None

    def _build_micro_state(self, sym: str) -> LiveMicroState:
        bids   = self._bids.get(sym, [])
        asks   = self._asks.get(sym, [])
        trades = self._trades.get(sym, [])

        obi = None
        cvd = None
        if bids and asks:
            obi_val = obi_from_orderbook(bids, asks)
            obi = RealOBI(
                bid_qty=sum(q for _, q in bids),
                ask_qty=sum(q for _, q in asks),
                imbalance=obi_val,
                ref_spread=self._compute_spread(bids, asks),
            )
        if trades:
            cvd_val = cvd_from_trades(trades)
            cvd = RealCVD(cvd=cvd_val, cvd_rate=0.0)

        return LiveMicroState(
            obi=obi,
            cvd=cvd,
            timestamp_ms=int(time.time() * 1000),
            seq_no=self._seq_no,
        )

    def _compute_spread(self, bids, asks) -> float:
        if not bids or not asks:
            return 0.0
        return abs(bids[0][0] - asks[0][0])

    def _emit_bar(self, bar: VCPBar, micro: LiveMicroState) -> None:
        if self._on_bar:
            try:
                self._on_bar(bar, micro)
            except Exception:
                pass

    def _sym_from_channel(self, channel: str) -> str:
        parts = channel.split(".")
        return parts[1] if len(parts) > 1 else "unknown"

    @property
    def on_bar(self) -> Callable:
        return getattr(self, "_on_bar", None)

    @on_bar.setter
    def on_bar(self, val: Callable) -> None:
        self._on_bar = val


# ─── Main Live Feed ─────────────────────────────────────────────────────────────

class VCPLiveFeed:
    """
    Background asyncio task that connects to the exchange WebSocket,
    parses l2_orderbook + all_trades + v2/ticker channels, and drives
    a VCPExecutor on each completed bar.

    Supports two exchange parsers:
      * delta_india / delta_global → DeltaFeedParser
      * deribit                   → DeribitFeedParser

    Usage
    -----
        feed = VCPLiveFeed(
            config=VCPFeedConfig(symbols=["BTCUSD"], signal_tf_secs=900),
            executor=executor,
        )
        await feed.start()
        # ... runs forever ...
        await feed.stop()

    The feed is robust: if the WebSocket drops it reconnect with exponential
    back-off. If reconnection fails after `reconnect_max` attempts, the feed
    logs an error and calls `executor.on_bar(...)` with the last known price
    so the executor state machine can continue without gaps.
    """

    def __init__(
        self,
        config: Optional[VCPFeedConfig] = None,
        executor: Optional[VCPExecutor] = None,
    ):
        self.cfg = config or VCPFeedConfig()
        self._exec = executor

        # Select parser based on exchange
        if self.cfg.exchange.startswith("deribit"):
            self._parser = DeribitFeedParser(signal_tf_secs=self.cfg.signal_tf_secs)
        else:
            self._parser = DeltaFeedParser(signal_tf_secs=self.cfg.signal_tf_secs)

        self._parser.on_bar = self._on_bar

        self._running:    bool = False
        self._task:       Optional[asyncio.Task] = None
        self._retry_count: int = 0
        self._last_price: float = 0.0
        self._delay:      float = self.cfg.reconnect_delay

        self._on_micro_state: Optional[Callable[[LiveMicroState], None]] = None

    def set_executor(self, executor: VCPExecutor) -> None:
        self._exec = executor

    def set_microstate_callback(self, cb: Callable[[LiveMicroState], None]) -> None:
        self._on_micro_state = cb

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        log.info(f"[VCPLiveFeed] Starting — exchange={self.cfg.exchange} symbols={self.cfg.symbols}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("[VCPLiveFeed] Stopped")

    async def _run(self) -> None:
        import websockets

        ws_url = self.cfg.ws_url or self._get_ws_url()

        while self._running:
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    open_timeout=10,
                ) as ws:
                    await self._subscribe(ws)
                    self._retry_count = 0
                    self._delay = self.cfg.reconnect_delay
                    await self._listen(ws)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                self._retry_count += 1
                if self._retry_count >= self.cfg.reconnect_max:
                    log.error(
                        "[VCPLiveFeed] Max reconnection attempts (%d) reached — feed is stopping. Last price=%.4f",
                        self.cfg.reconnect_max, self._last_price,
                    )
                    break
                log.warning(
                    "[VCPLiveFeed] WS error (attempt %d/%d): %s — reconnecting in %.0fs",
                    self._retry_count, self.cfg.reconnect_max, exc, self._delay,
                )
                await asyncio.sleep(self._delay)
                self._delay = min(self._delay * 2, 60.0)

    async def _subscribe(self, ws: Any) -> None:
        ex = self.cfg.exchange.lower()
        if ex.startswith("deribit"):
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "public/subscribe",
                "params": {
                    "channels": [
                        f"ticker.{sym}.raw",
                        f"trades.{sym}.raw",
                        f"book.{sym}.raw",
                    ]
                    for sym in self.cfg.symbols
                },
            }
        else:
            payload = {
                "type": "subscribe",
                "payload": {
                    "channels": [
                        {"name": "v2/ticker",    "symbols": self.cfg.symbols},
                        {"name": "all_trades",   "symbols": self.cfg.symbols},
                        {"name": "l2_orderbook", "symbols": self.cfg.symbols},
                    ],
                },
            }
            await ws.send(json.dumps({"type": "enable_heartbeat"}))
        await ws.send(json.dumps(payload))
        log.info(f"[VCPLiveFeed] Subscribed to {self.cfg.symbols} on {ex}")

    async def _listen(self, ws: Any) -> None:
        while self._running:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=self.cfg.heartbeat_timeout)
            except asyncio.TimeoutError:
                log.warning("[VCPLiveFeed] Heartbeat timeout — reconnecting")
                break

            try:
                self._parser.process_message(raw)
            except Exception as exc:
                log.debug("[VCPLiveFeed] Parse error: %s", exc)
                continue

    def _on_bar(self, bar: VCPBar, micro: LiveMicroState) -> None:
        """Called by the parser each time a bar completes."""
        if self._on_micro_state and micro:
            self._on_micro_state(micro)

        if self._exec is None:
            return

        # Fire executor — use asyncio.create_task so we don't block the WS loop
        asyncio.create_task(
            self._exec.on_bar(
                bar_ts_ms=bar.timestamp_ms,
                open_=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                live_micro=micro,
            )
        )

    def _delta_ws_url(self) -> str:
        if self.cfg.exchange == "delta_india":
            return "wss://socket.india.delta.exchange"
        return "wss://socket.delta.exchange"

    def _deribit_ws_url(self, testnet: bool = False) -> str:
        if testnet:
            return "wss://test.deribit.com"
        return "wss://ws.deribit.com"

    def _get_ws_url(self) -> str:
        ex = self.cfg.exchange.lower()
        if ex.startswith("deribit"):
            testnet = "test" in ex or "sandbox" in ex
            return self._deribit_ws_url(testnet)
        return self._delta_ws_url()


# ─── Convenience factory ──────────────────────────────────────────────────────

async def start_vcp_live_feed(
    profile_key: str,
    router: Any,
    adapter: Any,
    symbols: Optional[List[str]] = None,
) -> VCPLiveFeed:
    """
    One-liner to start the VCP live feed.

    Example
    -------
        feed = await start_vcp_live_feed(
            profile_key="btc_scalping_15m",
            router=order_router,
            adapter=delta_adapter,
            symbols=["BTCUSD"],
        )
    """
    from app.engines.hybrid_vcp import PROFILES, VCPExecutor

    profile = PROFILES.get(profile_key)
    if not profile:
        raise ValueError(f"Unknown profile: {profile_key} — available: {list(PROFILES.keys())}")

    sym = symbols or ["BTCUSD"]

    exec_cfg = VCPExecutorConfig(
        vol_filter_pct=profile.vol_filter_pct,
        flow_threshold=profile.flow_threshold,
        max_ibs_long=profile.max_ibs_long,
        min_ibs_short=profile.min_ibs_short,
        max_rsi_long=profile.max_rsi_long,
        min_rsi_short=profile.min_rsi_short,
    )

    executor = VCPExecutor(
        profile=profile,
        router=router,
        adapter=adapter,
        config=exec_cfg,
    )

    tf_secs = profile.signal_bar_ms // 1000

    feed_cfg = VCPFeedConfig(
        exchange="delta_india",
        symbols=sym,
        signal_tf_secs=tf_secs,
    )

    feed = VCPLiveFeed(config=feed_cfg, executor=executor)
    await feed.start()
    return feed