"""
Hybrid VCP-Momentum Scalper — Strategy V2
Live execution engine. Consumes bar updates from the exchange WebSocket and
feeds them through the VCP entry/exit state machine. Emits fills via
OrderRouter — same deterministic pipeline used for backtest/paper/shadow.

Usage
-----
    exec = VCPExecutor(
        profile=PROFILES["btc_scalping_15m"],
        router=router,           # OrderRouter instance
        adapter=adapter,         # exchange adapter (DeribitAdapter etc.)
        microstate_callback=None,# optional(LiveMicroState -> None) called each bar
    )
    await exec.start()

The executor runs indefinitely, rebalancing on each signal bar and managing
open positions until exit conditions fire.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional

from app.engines.hybrid_vcp.profiles import VCPProfile, exit_config_from_profile
from app.engines.hybrid_vcp.indicators import compute_bundle, IndicatorBundle
from app.engines.hybrid_vcp.microstructure import (
    obi_proxy, cvd_proxy, cvd_proxy_bar, flow_score, detect_divergence,
)
from app.engines.hybrid_vcp.signals import (
    detect_mode, signal_compression, signal_breakout,
    Direction, VolMode,
)
from app.engines.hybrid_vcp.entries import EntryConfig, evaluate_gate, EntryGate
from app.engines.hybrid_vcp.exits import ExitConfig, ExitResult, ExitReason, PositionState, check_exits
from app.engines.hybrid_vcp.live_filters import (
    LiveMicroState, LiveFilterConfig, LiveFilterDecision,
    evaluate_live_filters,
)
from app.services.execution.order_router import OrderRouter, OrderRouterRequest, RouterMode

log = logging.getLogger(__name__)


@dataclass
class VCPExecutorConfig:
    vol_filter_pct:  float = 35.0
    flow_threshold:  float = 0.35
    max_ibs_long:    float = 0.35
    min_ibs_short:   float = 0.65
    max_rsi_long:    float = 40.0
    min_rsi_short:   float = 60.0
    stop_mult:       float = 0.9
    tp1_mult:        float = 1.5
    trail_mult:      float = 0.5
    live_filter_cfg: Optional[LiveFilterConfig] = None
    # Bar processing throttle (seconds). Set > 0 to avoid double-processing
    # on high-frequency updates.
    min_bar_interval: float = 0.0


@dataclass
class VCPExecutorState:
    in_position:    bool = False
    entry_price:   float = 0.0
    entry_bar:     int   = 0
    direction:     int   = 0
    stop_price:    float = 0.0
    tp_price:      float = 0.0
    trail_active:  bool  = False
    trail_extreme: float = 0.0
    tp1_fired:     bool  = False
    order_id:      Optional[str] = None
    profile_key:   str   = ""


class VCPExecutor:
    """
    Live bar-by-bar VCP-Momentum executor.

    Thread-safety note: this class is designed to run on a single asyncio
    task. The `on_bar` method is NOT re-entrant — call it from one consumer only.
    """

    def __init__(
        self,
        profile: VCPProfile,
        router: OrderRouter,
        adapter: Any,          # exchange adapter with get_candles + get_index_price
        config: Optional[VCPExecutorConfig] = None,
        microstate_callback: Optional[Callable[[LiveMicroState], None]] = None,
    ):
        self.profile = profile
        self.router  = router
        self.adapter = adapter
        self.cfg     = config or VCPExecutorConfig(
            vol_filter_pct=profile.vol_filter_pct,
            flow_threshold=profile.flow_threshold,
            max_ibs_long=profile.max_ibs_long,
            min_ibs_short=profile.min_ibs_short,
            max_rsi_long=profile.max_rsi_long,
            min_rsi_short=profile.min_rsi_short,
            live_filter_cfg=LiveFilterConfig() if profile.vol_filter_pct > 0 else None,
        )
        self._cb = microstate_callback

        self._state: VCPExecutorState = VCPExecutorState(profile_key=profile.label)
        self._entry_cfg = EntryConfig(
            vol_filter_pct=self.cfg.vol_filter_pct,
            flow_threshold=self.cfg.flow_threshold,
            max_ibs_long=self.cfg.max_ibs_long,
            min_ibs_short=self.cfg.min_ibs_short,
            max_rsi_long=self.cfg.max_rsi_long,
            min_rsi_short=self.cfg.min_rsi_long,
        )
        self._exit_cfg  = exit_config_from_profile(profile)
        self._last_bar_ms: int = 0
        self._bar_count:  int = 0
        self._running:    bool = False
        self._lock = asyncio.Lock()

    # ── Public API ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Begin the executor loop. Call once, then await."""
        self._running = True
        log.info(f"[VCP] Starting executor for {self.profile.label}")

    async def stop(self) -> None:
        self._running = False
        log.info(f"[VCP] Stopped executor for {self.profile.label}")

    async def on_bar(
        self,
        bar_ts_ms: int,
        open_: float, high: float, low: float, close: float, volume: float,
        live_micro: Optional[LiveMicroState] = None,
    ) -> Optional[str]:
        """
        Process a new bar. Call from your WebSocket bar consumer.

        Returns order_id if an order was placed, else None.
        Throttles if bar arrives faster than min_bar_interval.
        """
        async with self._lock:
            if not self._running:
                return None

            now = time.time() * 1000
            if self.cfg.min_bar_interval > 0:
                if now - self._last_bar_ms < self.cfg.min_bar_interval * 1000:
                    return None
            self._last_bar_ms = now
            self._bar_count  += 1

            self._bar_ts_ms = bar_ts_ms

            result = await self._process_bar(
                bar_ts_ms, open_, high, low, close, volume, live_micro,
            )
            return result

    async def _process_bar(
        self, bar_ts_ms: int,
        open_: float, high: float, low: float, close: float, volume: float,
        live_micro: Optional[LiveMicroState],
    ) -> Optional[str]:
        """Inner bar processor — called under lock."""
        pos = self._read_pos()

        # ── Pre-compute indicators ────────────────────────────────────────
        bundle, obi_val, cvd_bar, mode, comp, brk, flow, div = self._compute_indicators(
            open_, high, low, close, volume,
        )

        # ── Live microstructure filters ──────────────────────────────────
        if live_micro is not None and self.cfg.live_filter_cfg is not None:
            direction_hint = 1 if (comp.long_score > comp.short_score) else -1
            lf_decision = evaluate_live_filters(
                live_micro, direction_hint, self.cfg.live_filter_cfg,
            )
            if not lf_decision.passed:
                log.debug(f"[VCP] Live filter veto: {lf_decision.reason}")
                return None
            if self._cb:
                self._cb(live_micro)

        # ── Entry logic ──────────────────────────────────────────────────
        if not pos.in_position:
            gate = evaluate_gate(
                self._bar_count,
                close, high, low, open_, volume, bundle,
                config=self._entry_cfg,
            )
            if gate.triggered and gate.direction != Direction.NONE:
                order_id = await self._enter_position(gate.direction, close, bundle)
                return order_id

        # ── Exit logic ────────────────────────────────────────────────────
        if pos.in_position:
            trend = int(brk[self._bar_count]) if self._bar_count < len(brk) else 0
            exits = check_exits(
                self._to_position_state(pos),
                self._bar_count,
                self._closes_for_check(bundle),
                self._highs_for_check(bundle),
                self._lows_for_check(bundle),
                bundle.atr,
                trend,
                self._exit_cfg,
            )
            for ex in exits:
                await self._exit_position(ex, close)

        return None

    async def _enter_position(self, direction: Direction, close: float, bundle: IndicatorBundle) -> str:
        """Place market entry order and update state."""
        atr_val = float(bundle.atr[self._bar_count]) if self._bar_count < len(bundle.atr) else 1.0
        entry_price = float(await self.adapter.get_index_price(None)) or close

        stop_price = (
            entry_price - self.cfg.stop_mult * atr_val
            if direction == Direction.LONG
            else entry_price + self.cfg.stop_mult * atr_val
        )
        tp_price = (
            entry_price + self.cfg.tp1_mult * atr_val
            if direction == Direction.LONG
            else entry_price - self.cfg.tp1_mult * atr_val
        )

        req = OrderRouterRequest(
            underlying=self.profile.label.split()[0].lower(),
            direction="long" if direction == Direction.LONG else "short",
            instrument_type="futures",
            size=1.0,
            stop_loss=stop_price,
            take_profit=tp_price,
            mode_name=f"vcp_{self.profile.signal_tf}",
            score=0.0,
            signal_strength="VCP",
        )
        resp = await self.router.route(req)

        # Update state
        self._state = VCPExecutorState(
            in_position=True,
            entry_price=entry_price,
            entry_bar=self._bar_count,
            direction=(+1 if direction == Direction.LONG else -1),
            stop_price=stop_price,
            tp_price=tp_price,
            trail_active=False,
            trail_extreme=entry_price,
            tp1_fired=False,
            order_id=resp.order_id,
            profile_key=self.profile.label,
        )
        log.info(
            f"[VCP] Enter {direction.value} @ {entry_price:.4f} "
            f"SL={stop_price:.4f} TP={tp_price:.4f}"
        )
        return resp.order_id or ""

    async def _exit_position(self, exit_: ExitResult, close: float) -> None:
        """Close position via market order."""
        direction_str = "long" if self._state.direction == 1 else "short"
        req = OrderRouterRequest(
            underlying=self.profile.label.split()[0].lower(),
            direction=direction_str,
            instrument_type="futures",
            size=1.0,
            reduce_only=True,
            mode_name=f"vcp_{self.profile.signal_tf}",
        )
        resp = await self.router.route(req)

        entry_price = self._state.entry_price
        pnl_pct = self._state.direction * (close - entry_price) / entry_price
        log.info(
            f"[VCP] Exit {exit_.reason.value} @ {close:.4f} "
            f"PnL={pnl_pct:.4f} ({exit_.partial_pct:.0%} partial)"
        )

        self._state = VCPExecutorState(profile_key=self.profile.label)

    # ── Indicator helpers ──────────────────────────────────────────────────

    def _compute_indicators(self, open_: float, high: float, low: float, close: float, volume: float):
        o = self._bar_history_open
        h = self._bar_history_high
        l = self._bar_history_low
        c = self._bar_history_close
        v = self._bar_history_vol

        idx = self._bar_count

        # Add current bar
        o[idx] = open_; h[idx] = high; l[idx] = low; c[idx] = close; v[idx] = volume

        bundle = compute_bundle(o[:idx+1], h[:idx+1], l[:idx+1], c[:idx+1], v[:idx+1])
        obi_val   = float(obi_proxy(h[:idx+1], l[:idx+1], c[:idx+1], v[:idx+1], bundle.vol_sma20))
        cvd_bar   = float(cvd_proxy_bar(o[:idx+1], h[:idx+1], l[:idx+1], c[:idx+1], v[:idx+1]))
        mode      = detect_mode(c[:idx+1], h[:idx+1], l[:idx+1], bundle.atr, VCPConfig())
        comp      = signal_compression(bundle.ibs, bundle.rsi, VCPConfig())
        brk       = signal_breakout(c[:idx+1], h[:idx+1], l[:idx+1], bundle.rsi,
                                    bundle.ema8, bundle.ema21,
                                    bundle.pivot_high, bundle.pivot_low,
                                    v[:idx+1], bundle.vol_sma20, MomentumConfig())
        flow      = float(flow_score(obi_val, cvd_bar, bundle.rsi[-1] if len(bundle.rsi) else 50.0))
        div       = detect_divergence(c[:idx+1], bundle.rsi)

        return bundle, obi_val, cvd_bar, mode, comp, brk, flow, div

    def _read_pos(self) -> VCPExecutorState:
        return self._state

    def _to_position_state(self, pos: VCPExecutorState) -> PositionState:
        return PositionState(
            entry_price=pos.entry_price,
            direction=pos.direction,
            entry_bar=pos.entry_bar,
            stop_price=pos.stop_price,
            tp_price=pos.tp_price,
            trail_active=pos.trail_active,
            trail_extreme=pos.trail_extreme,
        )

    def _closes_for_check(self, bundle: IndicatorBundle) -> "np.ndarray":
        return bundle.close

    def _highs_for_check(self, bundle: IndicatorBundle) -> "np.ndarray":
        return bundle.high

    def _lows_for_check(self, bundle: IndicatorBundle) -> "np.ndarray":
        return bundle.low

    # Rolling history buffers (pre-allocated)
    _bar_history_open:  any = field(default=None, init=False, repr=False)
    _bar_history_high:  any = field(default=None, init=False, repr=False)
    _bar_history_low:   any = field(default=None, init=False, repr=False)
    _bar_history_close: any = field(default=None, init=False, repr=False)
    _bar_history_vol:   any = field(default=None, init=False, repr=False)
    _bar_ts_ms: int = field(default=0, init=False)

    def __post_init__(self):
        n = 5000   # max bars to keep in memory
        import numpy as np
        self._bar_history_open  = np.zeros(n, dtype=np.float64)
        self._bar_history_high = np.zeros(n, dtype=np.float64)
        self._bar_history_low  = np.zeros(n, dtype=np.float64)
        self._bar_history_close= np.zeros(n, dtype=np.float64)
        self._bar_history_vol  = np.zeros(n, dtype=np.float64)