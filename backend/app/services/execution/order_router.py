"""
Sterling v4 — OrderRouter

Single integration point for emitting orders. Wraps every safety primitive,
selects between paper / shadow / live modes, and produces a structured
response that the FastAPI endpoint converts to HTTP.

Design goals
------------
1. **Pure orchestration**.  No FastAPI dependency — fully unit-testable.
2. **Deterministic dispatch**.  Same pipeline for backtest, paper, shadow,
   and live so behavior matches.
3. **Fail-closed**.  Any uncaught exception in a safety guard rejects the
   order; the guard never silently fails-open.
4. **Idempotent**.  Identical (underlying, direction, instrument_type, size,
   minute-bucket) submissions return the prior order_id within the safety
   TTL window. Callers may also supply an explicit `client_order_id`.

Non-goals
---------
* No retry orchestration on the calling thread — failed orders are enqueued
  into `live_safety.RetryItem` and consumed by an out-of-band worker.
* No backtest hooks — the backtest engine instantiates this class with a
  mock adapter when it wants to test live-router code paths.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.services import live_safety


# ─── Modes ────────────────────────────────────────────────────────────────


class RouterMode(str, Enum):
    PAPER = "paper"      # never call exchange; record paper position only
    SHADOW = "shadow"    # call exchange AND record paper for audit/diff
    LIVE = "live"        # call exchange; no paper record


# ─── Request / Response shapes ────────────────────────────────────────────


@dataclass
class OrderRouterRequest:
    underlying: str
    direction: str               # "long" | "short"
    instrument_type: str         # "futures" | "options"
    size: float = 1.0
    leverage: float = 1.0
    order_type: str = "market"   # "market" | "limit" | "maker"
    limit_price: Optional[float] = None
    time_in_force: str = "gtc"
    post_only: bool = False
    reduce_only: bool = False
    # Bracket
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trail_amount: Optional[float] = None
    # Options-only
    option_symbol: Optional[str] = None
    # Idempotency / observability
    client_order_id: Optional[str] = None
    notes: str = ""
    # Carryover for sizing decisions made upstream
    score: float = 0.0
    signal_strength: str = "SIGNAL"
    mode_name: str = "swing"     # for cooldown keying


@dataclass
class OrderRouterResponse:
    accepted: bool
    mode: str                    # "paper" | "shadow" | "live"
    order_id: Optional[str] = None
    paper_position_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    size: float = 0.0
    entry_price: Optional[float] = None
    status: str = "unknown"      # "filled" | "pending" | "duplicate" | "rejected"
    code: str = ""               # machine-readable when rejected
    reason: str = ""             # human-readable
    timestamp_ms: int = 0
    retry_id: Optional[str] = None    # set when failure was enqueued


# ─── Hooks (dependency injection points) ──────────────────────────────────


@dataclass
class RouterDeps:
    """All external dependencies pinned at construction time. Caller passes
    these explicitly so unit tests can swap each independently."""
    list_open_positions: Callable[[], List[Any]]
    create_paper_position: Callable[[OrderRouterRequest, str, float, Optional[str]], str]
    cooldown_blocked: Callable[[str, str, str, int], bool] = lambda *a, **k: False
    correlation_penalty: Callable[[str, List[Any]], float] = lambda *a, **k: 1.0
    portfolio_cap_breach: Callable[[OrderRouterRequest, List[Any]], Optional[str]] = lambda *a, **k: None
    microstructure_veto: Callable[[OrderRouterRequest], Optional[str]] = lambda *a, **k: None


# ─── Adapter shim ─────────────────────────────────────────────────────────


class _AsyncAdapterShim:
    """Minimal protocol the OrderRouter needs from an exchange adapter.
    Lets us pass a `MagicMock(spec=...)` in tests without dragging the full
    DeltaIndiaAdapter import chain."""
    async def get_index_price(self, instrument: Any) -> float: ...
    async def place_order(self, **kwargs) -> Dict[str, Any]: ...
    async def place_order_option(self, **kwargs) -> Dict[str, Any]: ...
    async def set_leverage(self, product_id: int, leverage: float) -> None: ...
    async def get_product_id(self, symbol: str) -> int: ...


# ─── Main router ──────────────────────────────────────────────────────────


class OrderRouter:
    """
    Stateless orchestrator. Every call to `submit()` runs the full safety
    pipeline and dispatches based on `self.mode`. Mutating `self.mode`
    between calls is supported (for hot-swapping paper↔live).
    """

    def __init__(
        self,
        mode: RouterMode | str,
        adapter: Optional[Any],
        deps: RouterDeps,
        instrument_resolver: Callable[[str], Any],
    ) -> None:
        self.mode = RouterMode(mode) if isinstance(mode, str) else mode
        self.adapter = adapter
        self.deps = deps
        self._resolve = instrument_resolver

    # ── public ──────────────────────────────────────────────────────────

    async def submit(self, req: OrderRouterRequest) -> OrderRouterResponse:
        now_ms = int(time.time() * 1000)
        sym = req.underlying.upper()

        inst = self._resolve(sym)
        if inst is None:
            return self._reject(req, "unknown_underlying", f"Unknown underlying: {sym}", now_ms)

        # 1. Composite safety gate (kill switch / daily loss / idempotency)
        idem_key = req.client_order_id or live_safety.make_idempotency_key(
            sym, req.direction, req.instrument_type, req.size,
            int(now_ms // 60_000),       # minute bucket
        )
        decision = live_safety.assert_safe_to_trade(
            positions=self.deps.list_open_positions(),
            idempotency_key=idem_key,
        )
        if not decision.allowed:
            if decision.code == "duplicate_order":
                prior = live_safety.check_idempotency(idem_key)
                return OrderRouterResponse(
                    accepted=True,
                    mode=self.mode.value,
                    order_id=prior,
                    symbol=self._symbol_for(req, inst),
                    side=self._side(req),
                    size=req.size,
                    status="duplicate",
                    code=decision.code,
                    reason=decision.reason,
                    timestamp_ms=now_ms,
                )
            return self._reject(req, decision.code, decision.reason, now_ms)

        # 2. Cooldown
        if self.deps.cooldown_blocked(sym, req.mode_name, req.direction, now_ms):
            return self._reject(req, "cooldown_active",
                                f"Cooldown active for {sym}/{req.mode_name}/{req.direction}", now_ms)

        # 3. Portfolio bucket caps
        cap_breach = self.deps.portfolio_cap_breach(req, self.deps.list_open_positions())
        if cap_breach:
            return self._reject(req, "portfolio_cap_breach", cap_breach, now_ms)

        # 4. Microstructure veto (cheap, runs late)
        micro = self.deps.microstructure_veto(req)
        if micro:
            return self._reject(req, "microstructure_veto", micro, now_ms)

        # 5. Correlation penalty applies as a *size* multiplier (not a veto)
        penalty = self.deps.correlation_penalty(sym, self.deps.list_open_positions())
        if penalty < 1.0 and req.size * penalty < 1:
            # Cannot scale below 1 contract — reject explicitly.
            return self._reject(req, "correlation_size_zero",
                                f"Correlation penalty {penalty:.2f} would size below 1 contract", now_ms)
        adjusted = OrderRouterRequest(**{**req.__dict__, "size": max(1, round(req.size * penalty))})

        # ── dispatch ───────────────────────────────────────────────────
        if self.mode == RouterMode.PAPER:
            return await self._submit_paper(adjusted, inst, idem_key, now_ms)
        if self.mode == RouterMode.SHADOW:
            return await self._submit_shadow(adjusted, inst, idem_key, now_ms)
        return await self._submit_live(adjusted, inst, idem_key, now_ms)

    # ── dispatchers ─────────────────────────────────────────────────────

    async def _submit_paper(
        self, req: OrderRouterRequest, inst: Any, idem_key: str, now_ms: int,
    ) -> OrderRouterResponse:
        entry = await self._fetch_entry_price(inst)
        pid = self.deps.create_paper_position(req, self._symbol_for(req, inst), entry, None)
        live_safety.record_idempotency(idem_key, f"paper:{pid}")
        return OrderRouterResponse(
            accepted=True, mode="paper",
            paper_position_id=pid,
            symbol=self._symbol_for(req, inst),
            side=self._side(req),
            size=req.size,
            entry_price=entry,
            status="filled",
            timestamp_ms=now_ms,
        )

    async def _submit_shadow(
        self, req: OrderRouterRequest, inst: Any, idem_key: str, now_ms: int,
    ) -> OrderRouterResponse:
        live_resp = await self._submit_live(req, inst, idem_key, now_ms)
        if live_resp.accepted and live_resp.order_id:
            try:
                pid = self.deps.create_paper_position(
                    req, live_resp.symbol, live_resp.entry_price or 0.0, live_resp.order_id
                )
                live_resp.paper_position_id = pid
                live_resp.mode = "shadow"
            except Exception as exc:    # paper failure must not affect live
                live_resp.reason = f"shadow paper-record failed: {exc}"
        return live_resp

    async def _submit_live(
        self, req: OrderRouterRequest, inst: Any, idem_key: str, now_ms: int,
    ) -> OrderRouterResponse:
        if self.adapter is None:
            return self._reject(req, "no_adapter", "Live mode requires an adapter", now_ms)

        side = self._side(req)
        symbol = self._symbol_for(req, inst)

        try:
            if req.instrument_type == "options":
                if not req.option_symbol:
                    return self._reject(req, "missing_option_symbol",
                                        "Options orders require option_symbol", now_ms)
                order = await self.adapter.place_order_option(
                    option_symbol=req.option_symbol,
                    side="buy",                     # always buy for options
                    size=req.size,
                    order_type=self._api_order_type(req.order_type),
                    limit_price=req.limit_price,
                    stop_loss=req.stop_loss,
                    take_profit=req.take_profit,
                )
                symbol = req.option_symbol
            else:
                product_id = await self.adapter.get_product_id(symbol)
                try:
                    await self.adapter.set_leverage(product_id, req.leverage)
                except Exception:
                    pass        # leverage failures are non-fatal — see runbook
                order = await self.adapter.place_order(
                    symbol=symbol,
                    side=side,
                    size=req.size,
                    order_type=self._api_order_type(req.order_type),
                    limit_price=req.limit_price,
                    time_in_force=req.time_in_force,
                    post_only=(req.order_type == "maker"),
                    reduce_only=req.reduce_only,
                    stop_loss=req.stop_loss,
                    take_profit=req.take_profit,
                    trail_amount=req.trail_amount,
                )
        except Exception as exc:
            retry = live_safety.enqueue_retry(
                payload={
                    "underlying": req.underlying,
                    "direction": req.direction,
                    "instrument_type": req.instrument_type,
                    "size": req.size,
                    "leverage": req.leverage,
                    "client_order_id": idem_key,
                },
                error=str(exc),
            )
            return OrderRouterResponse(
                accepted=False, mode=self.mode.value,
                symbol=symbol, side=side, size=req.size,
                status="rejected", code="exchange_error",
                reason=f"Order failed: {exc}",
                timestamp_ms=now_ms, retry_id=retry.id,
            )

        order_id = str(order.get("id") or order.get("order_id") or "")
        entry_price = float(
            order.get("average_fill_price") or order.get("limit_price") or 0.0
        ) or None
        live_safety.record_idempotency(idem_key, order_id)

        return OrderRouterResponse(
            accepted=True, mode=self.mode.value,
            order_id=order_id,
            symbol=symbol, side=side, size=req.size,
            entry_price=entry_price,
            status="filled" if not req.limit_price else "pending",
            timestamp_ms=now_ms,
        )

    # ── helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _side(req: OrderRouterRequest) -> str:
        if req.instrument_type == "options":
            return "buy"
        return "buy" if req.direction == "long" else "sell"

    @staticmethod
    def _api_order_type(order_type: str) -> str:
        return "limit_order" if order_type in ("limit", "maker") else "market_order"

    @staticmethod
    def _symbol_for(req: OrderRouterRequest, inst: Any) -> str:
        if req.instrument_type == "options" and req.option_symbol:
            return req.option_symbol
        return getattr(inst, "delta_perp_symbol", None) or f"{req.underlying.upper()}USD"

    async def _fetch_entry_price(self, inst: Any) -> float:
        if self.adapter is None:
            return 0.0
        try:
            return float(await self.adapter.get_index_price(inst))
        except Exception:
            return 0.0

    @staticmethod
    def _reject(req: OrderRouterRequest, code: str, reason: str, now_ms: int) -> OrderRouterResponse:
        return OrderRouterResponse(
            accepted=False, mode="rejected",
            symbol=req.underlying, side="", size=req.size,
            status="rejected", code=code, reason=reason,
            timestamp_ms=now_ms,
        )
