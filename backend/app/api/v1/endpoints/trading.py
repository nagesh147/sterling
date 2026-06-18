"""
Live order execution endpoint.
Places real orders on Delta Exchange India when active exchange config has credentials.
Falls back to paper position creation when credentials are absent.
"""
import json
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.services.exchanges import instrument_registry as registry
from app.services import paper_store
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])


class LiveOrderRequest(BaseModel):
    underlying: str
    direction: str              # "long" or "short"
    instrument_type: str        # "futures" or "options"
    size: float = 1.0           # number of contracts (integer exchange lots)
    contract_value: float = 1.0 # size of one lot in the underlying (Delta perps:
                                # BTC=0.001, ETH=0.01, SOL=1). Coin qty = size*cv.
                                # Defaults to 1.0 → legacy coin-based behavior.
    leverage: float = 5.0       # set via separate leverage API before order
    order_type: str = "market"  # "market" | "limit" | "maker" (limit+post_only)
    limit_price: Optional[float] = None
    time_in_force: str = "gtc"  # "gtc" (good-till-cancel) | "ioc" (immediate-or-cancel)
    post_only: bool = False      # maker-only order (limit orders only)
    reduce_only: bool = False    # close-only, never open new position
    # Bracket fields
    stop_loss: Optional[float] = None
    stop_loss_order_type: str = "market_order"
    stop_loss_limit_price: Optional[float] = None
    trail_amount: Optional[float] = None
    take_profit: Optional[float] = None
    take_profit_order_type: str = "market_order"
    take_profit_limit_price: Optional[float] = None
    bracket_trigger_method: str = "mark_price"
    # For options
    option_symbol: Optional[str] = None
    option_premium: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    projected_theta_burn_usd: Optional[float] = None
    liquidity: Optional[float] = None
    expected_r: Optional[float] = None
    dte: Optional[int] = None
    notes: str = ""
    # Account NAV used to report capital-at-risk as a real %. When omitted the
    # reporter falls back to the legacy $100k denominator (see _capital_at_risk_pct).
    account_equity: Optional[float] = None
    # Idempotency: caller supplies a stable key per logical order. Duplicate
    # submissions within the live_safety TTL window are rejected and the
    # prior order_id is returned. Optional — auto-generated when omitted.
    client_order_id: Optional[str] = None


class LiveOrderResponse(BaseModel):
    mode: str              # "live" or "paper"
    order_id: Optional[str] = None
    paper_position_id: Optional[str] = None
    symbol: str
    side: str
    size: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: Optional[float] = None
    status: str
    message: str
    timestamp_ms: int


class AlgoModeRequest(BaseModel):
    enabled: bool


class AlgoModeResponse(BaseModel):
    enabled: bool


class AlgoRouterModeRequest(BaseModel):
    mode: str   # "paper" | "shadow" | "live"


class AlgoRouterModeResponse(BaseModel):
    mode: str


class VCPModeRequest(BaseModel):
    enabled: bool


class VCPModeResponse(BaseModel):
    enabled: bool
    feed_count: int
    active_profiles: list[str]


@router.get("/algo-mode", response_model=AlgoModeResponse)
async def get_algo_mode(request: Request) -> AlgoModeResponse:
    return AlgoModeResponse(enabled=getattr(request.app.state, "algo_mode", False))


@router.post("/algo-mode", response_model=AlgoModeResponse)
async def set_algo_mode(body: AlgoModeRequest, request: Request) -> AlgoModeResponse:
    from app.services.db import set_config
    request.app.state.algo_mode = body.enabled
    set_config("algo_mode", "true" if body.enabled else "false")
    return AlgoModeResponse(enabled=body.enabled)


class ScalpModeRequest(BaseModel):
    enabled: bool


class ScalpModeResponse(BaseModel):
    enabled: bool


@router.get("/scalp-mode", response_model=ScalpModeResponse)
async def get_scalp_mode(request: Request) -> ScalpModeResponse:
    return ScalpModeResponse(enabled=getattr(request.app.state, "scalp_mode", False))


@router.post("/scalp-mode", response_model=ScalpModeResponse)
async def set_scalp_mode(body: ScalpModeRequest, request: Request) -> ScalpModeResponse:
    from app.services.db import set_config
    request.app.state.scalp_mode = body.enabled
    set_config("scalp_mode", "true" if body.enabled else "false")
    return ScalpModeResponse(enabled=body.enabled)


class ScoringStrategyRequest(BaseModel):
    strategy: str  # "by_edge_max_linear_agree" | "unweighted_mean"


class ScoringStrategyResponse(BaseModel):
    strategy: str


@router.get("/scoring-strategy", response_model=ScoringStrategyResponse)
async def get_scoring_strategy(request: Request) -> ScoringStrategyResponse:
    """
    Get the current ensemble scoring strategy used by the directional engine.

    Available strategies:
      - by_edge_max_linear_agree  (default, best from exhaustive search)
      - unweighted_mean           (legacy, pre-search)
    """
    from app.engines.directional.track_scoring import get_active_strategy
    return ScoringStrategyResponse(strategy=get_active_strategy())


@router.post("/scoring-strategy", response_model=ScoringStrategyResponse)
async def set_scoring_strategy(
    body: ScoringStrategyRequest, request: Request,
) -> ScoringStrategyResponse:
    from app.engines.directional.track_scoring import set_strategy, AVAILABLE_STRATEGIES
    if body.strategy not in AVAILABLE_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid strategy {body.strategy!r}. "
                   f"Must be one of: {list(AVAILABLE_STRATEGIES)}",
        )
    set_strategy(body.strategy)
    from app.services.db import set_config
    set_config("scoring_strategy", body.strategy)
    log.info("Scoring strategy set to %s", body.strategy)
    return ScoringStrategyResponse(strategy=body.strategy)


@router.get("/algo-router-mode", response_model=AlgoRouterModeResponse)
async def get_algo_router_mode(request: Request) -> AlgoRouterModeResponse:
    """
    Phase F: paper / shadow / live dispatch mode for the auto-trader.

      paper  — never call the exchange; always create a paper position
      shadow — call the exchange AND create a paper twin for audit/diff
      live   — call the exchange; no paper record (default for back-compat)
    """
    return AlgoRouterModeResponse(
        mode=getattr(request.app.state, "algo_router_mode", "live") or "live",
    )


@router.post("/algo-router-mode", response_model=AlgoRouterModeResponse)
async def set_algo_router_mode(
    body: AlgoRouterModeRequest, request: Request,
) -> AlgoRouterModeResponse:
    if body.mode not in ("paper", "shadow", "live"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid router mode {body.mode!r}. Must be paper|shadow|live.",
        )
    from app.services.db import set_config
    request.app.state.algo_router_mode = body.mode
    set_config("algo_router_mode", body.mode)
    return AlgoRouterModeResponse(mode=body.mode)


@router.get("/vcp-mode", response_model=VCPModeResponse)
async def get_vcp_mode(request: Request) -> VCPModeResponse:
    """
    Get current VCP live-feed state.
    Returns enabled flag, number of active feeds, and profile keys.
    """
    feed_count = getattr(request.app.state, "vcp_feed_count", 0)
    active = getattr(request.app.state, "vcp_active_profiles", [])
    return VCPModeResponse(
        enabled=getattr(request.app.state, "vcp_mode_enabled", False),
        feed_count=feed_count,
        active_profiles=active,
    )


@router.post("/vcp-mode", response_model=VCPModeResponse)
async def set_vcp_mode(body: VCPModeRequest, request: Request) -> VCPModeResponse:
    """
    Start or stop the VCP live-feed independently of algo_mode.

    Unlike algo_mode (which controls ALL auto-trading including directional
    signal generation), vcp_mode targets only the Hybrid VCP live feed.
    When vcp_mode=True, the _background_vcp_live_feed task will spawn
    VCPLiveFeed instances for all active VCP profiles.
    """
    profiles_by_asset = {
        "BTC": [
            "btc_scalping_5m", "btc_scalping_15m", "btc_scalping_30m",
            "btc_intraday_1h", "btc_intraday_4h",
        ],
        "ETH": [
            "eth_scalping_5m", "eth_scalping_15m", "eth_scalping_30m",
            "eth_intraday_1h",
        ],
    }

    request.app.state.vcp_mode_enabled = body.enabled

    if body.enabled:
        from app.engines.directional.track_selector import select_tracks
        active_profiles: list[str] = []
        for asset, profile_keys in profiles_by_asset.items():
            for pk in profile_keys:
                tracks = select_tracks(asset, pk)
                if "vcp" in tracks:
                    active_profiles.append(pk)

        request.app.state.vcp_active_profiles = active_profiles
        request.app.state.vcp_feed_count = len(active_profiles)
        log = get_logger("vcp-mode")
        log.info("VCP mode enabled: %d profiles active (%s)",
                 len(active_profiles), active_profiles)
    else:
        request.app.state.vcp_active_profiles = []
        request.app.state.vcp_feed_count = 0

    from app.services.db import set_config
    set_config("vcp_mode", "true" if body.enabled else "false")

    return VCPModeResponse(
        enabled=body.enabled,
        feed_count=getattr(request.app.state, "vcp_feed_count", 0),
        active_profiles=getattr(request.app.state, "vcp_active_profiles", []),
    )


@router.post("/place-order", response_model=LiveOrderResponse)
async def place_live_order(body: LiveOrderRequest, request: Request) -> LiveOrderResponse:
    """
    Place a live order on Delta Exchange India (or paper if not configured).
    Automatically sets bracket SL/TP when provided.

    Pre-flight safety checks (in order, fail-closed):
      1. kill_switch_state.enabled       → 423 Locked
      2. daily_loss_state.level == halt  → 423 Locked
      3. idempotency cache hit           → returns prior order_id (200)
    """
    from app.services import adapter_manager as _adm
    from app.services import exchange_account_store
    from app.services import live_safety, paper_store

    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    # ── Safety gate (composite): kill switch + daily-loss + idempotency ──
    idem_key = body.client_order_id or live_safety.make_idempotency_key(
        sym, body.direction, body.instrument_type, body.size,
        # Bucket to the current minute so back-to-back identical clicks dedupe
        int(time.time() // 60),
    )
    decision = live_safety.assert_safe_to_trade(
        positions=paper_store.list_positions(),
        idempotency_key=idem_key,
    )
    if not decision.allowed:
        if decision.code == "duplicate_order":
            # Surface the existing order_id with HTTP 200 — the client retried
            # but should treat the prior order as authoritative.
            return LiveOrderResponse(
                mode="live",
                order_id=live_safety.check_idempotency(idem_key),
                symbol=inst.delta_perp_symbol or f"{sym}USD",
                side="buy" if body.direction == "long" else "sell",
                size=body.size,
                status="duplicate",
                message=decision.reason,
                timestamp_ms=int(time.time() * 1000),
            )
        # Kill switch / daily-loss → 423 Locked (semantic: resource locked)
        raise HTTPException(status_code=423, detail={
            "error": decision.reason,
            "code": decision.code,
        })

    # Options: always BUY — direction is encoded in CE/PE symbol, not in the order side.
    if body.instrument_type == "options":
        side = "buy"
    else:
        side = "buy" if body.direction == "long" else "sell"
    now_ms = int(time.time() * 1000)

    # Check if Delta Exchange India is active with credentials
    algo_mode = getattr(request.app.state, "algo_mode", False)
    # Router mode is the authoritative paper/shadow/live switch. Real orders are
    # placed ONLY in "live" mode — "shadow" runs with keys present but simulates
    # the fill as a paper position (so it never touches real funds), and "paper"
    # is pure simulation. This gate is what stops shadow from placing live orders.
    router_mode = (getattr(request.app.state, "algo_router_mode", "live") or "live").lower()
    active = exchange_account_store.get_active()
    has_live_creds = (
        router_mode == "live"
        and active is not None
        and active.name in ("delta_india", "delta")
        and bool(active.api_key)
        and bool(active.api_secret)
        and not active.api_key.startswith("DUMMY")
        and not active.is_paper
    )

    if has_live_creds:
        # ── LIVE ORDER ────────────────────────────────────────────────────
        try:
            from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
            # Use the API base URL auto-detected during test-credentials (India vs Global).
            # Falls back to global if not yet tested.
            api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
            adapter = DeltaIndiaAdapter(
                api_key=active.api_key,
                api_secret=active.api_secret,
                is_paper=False,
                base_url=api_base,
            )
            if not hasattr(adapter, "place_order"):
                raise RuntimeError("Active adapter does not support live order placement")

            bracket = dict(
                stop_loss=body.stop_loss,
                stop_loss_order_type=body.stop_loss_order_type,
                stop_loss_limit_price=body.stop_loss_limit_price,
                trail_amount=body.trail_amount,
                take_profit=body.take_profit,
                take_profit_order_type=body.take_profit_order_type,
                take_profit_limit_price=body.take_profit_limit_price,
                bracket_trigger_method=body.bracket_trigger_method,
            )

            # "maker" order_type = limit + post_only
            is_maker = body.order_type == "maker"
            api_order_type = "limit_order" if body.order_type in ("limit", "maker") else "market_order"

            if body.instrument_type == "options" and body.option_symbol:
                order = await adapter.place_order_option(
                    option_symbol=body.option_symbol,
                    side=side,
                    size=body.size,
                    order_type=api_order_type,
                    limit_price=body.limit_price,
                    **bracket,
                )
                delta_symbol = body.option_symbol
            else:
                delta_symbol = inst.delta_perp_symbol or f"{sym}USD"
                product_id   = await adapter.get_product_id(delta_symbol)

                # Step 1: Set leverage BEFORE placing order (API contract requirement)
                try:
                    await adapter.set_leverage(product_id, body.leverage)
                except Exception as lev_exc:
                    log.warning("Leverage pre-set failed for %s: %s (continuing)", delta_symbol, lev_exc)

                # Step 2: Place order
                order = await adapter.place_order(
                    symbol=delta_symbol,
                    side=side,
                    size=body.size,
                    order_type=api_order_type,
                    limit_price=body.limit_price,
                    time_in_force=body.time_in_force,
                    post_only=is_maker,
                    reduce_only=body.reduce_only,
                    **bracket,
                )

            order_id = str(order.get("id") or order.get("order_id") or "")
            entry_price = float(order.get("average_fill_price") or order.get("limit_price") or 0.0)

            # Record success in idempotency cache so duplicate submits within
            # the TTL window short-circuit and reuse this order_id.
            live_safety.record_idempotency(idem_key, order_id)

            # Also create a paper tracking entry for P&L monitoring
            _create_paper_tracking(body, sym, entry_price, order_id)

            # Telegram alert
            _send_order_telegram(body, sym, side, entry_price, order_id, "LIVE")

            return LiveOrderResponse(
                mode="live", order_id=order_id,
                symbol=delta_symbol, side=side, size=body.size,
                entry_price=entry_price or None,
                stop_loss=body.stop_loss, take_profit=body.take_profit,
                leverage=body.leverage if body.instrument_type == "futures" else None,
                status="filled" if not body.limit_price else "pending",
                message=f"Live {side.upper()} order placed on Delta Exchange India",
                timestamp_ms=now_ms,
            )

        except Exception as exc:
            log.error("Live order failed: %s", exc)
            failed_pos_id = _create_failed_algo_tracking(body, sym, str(exc))
            # Enqueue for operator-driven retry. The retry endpoint at the
            # bottom of this file picks items off this queue.
            try:
                live_safety.enqueue_retry(
                    payload={
                        "underlying": sym,
                        "direction": body.direction,
                        "instrument_type": body.instrument_type,
                        "size": body.size,
                        "leverage": body.leverage,
                        "client_order_id": idem_key,
                        "failed_position_id": failed_pos_id,
                    },
                    error=str(exc),
                )
            except Exception:
                pass
            error_detail = {"error": f"Order failed: {exc}", "failed_position_id": failed_pos_id}
            if "ip_not_whitelisted" in str(exc).lower() or "whitelist" in str(exc).lower():
                from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter as _DIA
                server_ip = await _DIA._get_public_ip()
                error_detail["server_ip"] = server_ip
                error_detail["error"] = f"Order failed: ip_not_whitelisted — add server IP {server_ip} to your Delta API key whitelist"
            raise HTTPException(
                status_code=502,
                detail=json.dumps(error_detail),
            )

    elif router_mode == "live":
        # ── LIVE REQUESTED BUT NO USABLE CREDENTIALS ──────────────────────
        # Don't silently fall back to a paper trade — that mislabels the order
        # and confuses "what mode am I in?". Reject with a clear next step so a
        # live execution stays tied to live mode.
        active_has_keys = bool(
            active and active.api_key and active.api_secret
            and not active.api_key.startswith("DUMMY")
        )
        reason = (
            "Exchange is in Paper — flip the Paper/Live toggle to Live to place real orders."
            if active_has_keys else
            "No live credentials — add Delta Exchange API keys, then switch the Paper/Live toggle to Live."
        )
        return LiveOrderResponse(
            mode="live",
            symbol=inst.delta_perp_symbol or f"{sym}USD",
            side=side, size=body.size,
            status="rejected",
            message=reason,
            timestamp_ms=now_ms,
        )

    else:
        # ── PAPER / SHADOW ORDER ──────────────────────────────────────────
        # Both create a simulated paper position; "shadow" just means keys are
        # present and we're deliberately simulating instead of going live.
        is_shadow = router_mode == "shadow"
        resp_mode = "shadow" if is_shadow else "paper"
        adapter = _adm.get_adapter() or request.app.state.adapter
        try:
            entry_price = float(await adapter.get_index_price(inst))
        except Exception:
            entry_price = 0.0

        pos_id = _create_paper_tracking(body, sym, entry_price)
        _send_order_telegram(body, sym, side, entry_price, pos_id, resp_mode.upper())

        if is_shadow:
            msg = f"Shadow {side.upper()} position created (simulated — keys present, no live order placed)"
        else:
            msg = f"Paper {side.upper()} position created (no live credentials configured)"

        return LiveOrderResponse(
            mode=resp_mode, paper_position_id=pos_id,
            symbol=inst.delta_perp_symbol or f"{sym}USD",
            side=side, size=body.size,
            entry_price=entry_price,
            stop_loss=body.stop_loss, take_profit=body.take_profit,
            leverage=body.leverage if body.instrument_type == "futures" else None,
            status="open",
            message=msg,
            timestamp_ms=now_ms,
        )


def _capital_at_risk_pct(
    *, entry_price: float, stop_loss: Optional[float], qty: float,
    position_value: float, instrument_type: str, account_equity: Optional[float],
) -> tuple[float, float]:
    """Return (max_risk_usd, capital_at_risk_pct).

    Real risk = stop distance × coin qty — what you actually lose if stopped out —
    expressed as a % of the REAL account NAV. The old formula divided by a
    hardcoded $100k, so a correct 0.25%-risk scalp on a $500 book reported 0.00%.
    Falls back to a notional estimate when no stop is set, and to the legacy $100k
    NAV when the caller doesn't supply equity (keeps older callers unchanged).
    """
    if stop_loss and entry_price > 0:
        max_risk = abs(entry_price - stop_loss) * qty
    else:
        max_risk = position_value * (0.02 if instrument_type == "futures" else 0.05)
    nav = account_equity if (account_equity and account_equity > 0) else 100_000.0
    pct = (max_risk / nav) * 100.0 if entry_price > 0 else 0.0
    return max_risk, pct


def _create_paper_tracking(
    body: LiveOrderRequest, sym: str, entry_price: float,
    order_id: str = "", order_status: str = "filled",
) -> str:
    """Create a tracking entry in paper_store for P&L monitoring."""
    try:
        from app.schemas.execution import Direction as ExecDir
        from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract

        is_live_order = bool(order_id)
        direction = ExecDir.LONG if body.direction == "long" else ExecDir.SHORT
        contracts = max(1, int(body.size))
        cv = body.contract_value or 1.0
        qty = contracts * cv              # coin quantity (lots × lot size)
        position_value = qty * entry_price
        # Real risk = distance to the stop × size — what you actually lose if
        # stopped out — as a % of the REAL account NAV (body.account_equity).
        # The old formula divided by a hardcoded $100k, so a correct 0.25%-risk
        # scalp on a $500 book reported 0.00%. `qty` (not raw lots) moves with price.
        max_risk, capital_at_risk = _capital_at_risk_pct(
            entry_price=entry_price, stop_loss=body.stop_loss, qty=qty,
            position_value=position_value, instrument_type=body.instrument_type,
            account_equity=body.account_equity,
        )
        leg = CandidateContract(
            instrument_name=body.option_symbol or f"{sym}-PERP",
            underlying=sym,
            strike=entry_price, expiry_date="", dte=body.dte or 0,
            option_type=body.instrument_type,
            bid=0.0, ask=0.0,
            mark_price=entry_price, mid_price=entry_price,
            mark_iv=0.0,
            delta=body.delta if body.delta is not None else (1.0 if body.direction == "long" else -1.0),
            gamma=body.gamma, theta=body.theta, vega=body.vega,
            open_interest=0.0, volume_24h=0.0,
            spread_pct=0.0, health_score=body.liquidity or 0.0, healthy=True,
        )
        rr = body.expected_r
        if not rr:
            rr = 2.0
            if body.stop_loss and body.take_profit:
                risk = abs(entry_price - body.stop_loss)
                reward = abs(body.take_profit - entry_price)
                if risk > 0:
                    rr = round(reward / risk, 2)
        structure = TradeStructure(
            structure_type=body.instrument_type,
            direction=direction, legs=[leg],
            net_premium=entry_price, max_loss=entry_price * 0.03,
            max_gain=None, risk_reward=rr,
            score=0.0, score_breakdown={},
            leverage=int(body.leverage),
        )
        sized = SizedTrade(
            structure=structure,
            contracts=contracts,
            contract_value=cv,
            position_value=round(position_value, 2),
            max_risk_usd=round(max_risk, 2),
            capital_at_risk_pct=round(capital_at_risk, 2),
        )
        from app.schemas.greeks import GreeksSnapshot
        import time
        greeks = None
        if body.instrument_type == "options":
            greeks = GreeksSnapshot(
                delta=body.delta if body.delta is not None else (1.0 if body.direction == "long" else -1.0),
                gamma=body.gamma or 0.0,
                theta=body.theta or 0.0,
                vega=body.vega or 0.0,
                spot=entry_price,
                dte=body.dte or 0,
                timestamp_ms=int(time.time() * 1000)
            )

        mode_tag = body.notes.split(" ")[0] if body.notes else ""
        is_scalp = mode_tag.startswith("[SCALP-")
        pos = paper_store.add_position(
            underlying=sym, sized_trade=sized,
            entry_spot_price=entry_price,
            notes=f"{'[LIVE]' if is_live_order else '[PAPER]'} {body.notes} order_id={order_id}",
            is_paper=not is_live_order,
            trail_mode_name="scalping" if is_scalp else None,
            order_id=order_id or None,
            order_status=order_status,
            initial_sl=body.stop_loss,
            initial_tp=body.take_profit,
            entry_greeks_snapshot=greeks,
            expected_theta_burn_usd=body.projected_theta_burn_usd,
        )
        return pos.id
    except Exception as exc:
        log.warning("Paper tracking creation failed: %s", exc)
        return ""


def _send_order_telegram(body: LiveOrderRequest, sym: str, side: str, entry: float, ref_id: str, mode: str):
    """Send Telegram notification for order placement."""
    try:
        from app.services.notifications import telegram as _tg
        import asyncio as _aio
        dir_emoji = "🟢 BUY" if side == "buy" else "🔴 SELL"
        sl_str = f"${body.stop_loss:,.2f}" if body.stop_loss else "—"
        tp_str = f"${body.take_profit:,.2f}" if body.take_profit else "—"
        lev_str = f"{int(body.leverage)}×" if body.instrument_type == "futures" else "options"
        msg = (
            f"<b>{'[LIVE]' if mode=='LIVE' else '[PAPER]'} ORDER PLACED</b>\n"
            f"<b>{sym}</b>  {dir_emoji}  {body.instrument_type.upper()}\n"
            f"Entry: <b>${entry:,.2f}</b>  ·  {lev_str}\n"
            f"Stop Loss: <b>{sl_str}</b>\n"
            f"Take Profit: <b>{tp_str}</b>\n"
            f"Ref: {ref_id}"
        )
        _aio.create_task(_tg.send(msg))
    except Exception:
        pass


def _create_failed_algo_tracking(body: LiveOrderRequest, sym: str, error: str) -> str:
    """
    Track a failed algo order in paper_store so it appears in positions with FAILED badge.
    Position stays OPEN so the user can retry from the positions tab.
    """
    try:
        from app.schemas.execution import Direction as ExecDir
        from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract

        # Best-effort spot price: limit_price from request → stream cache → 0
        spot_price: float = 0.0
        if body.limit_price and body.limit_price > 0:
            spot_price = float(body.limit_price)
        else:
            try:
                from app.api.v1.endpoints.directional import _stream_last_prices
                spot_price = float(_stream_last_prices.get(sym, 0.0))
            except Exception:
                pass

        direction = ExecDir.LONG if body.direction == "long" else ExecDir.SHORT
        contracts = max(1, int(body.size))
        cv = body.contract_value or 1.0
        qty = contracts * cv              # coin quantity (lots × lot size)
        position_value = qty * spot_price if spot_price > 0 else 0.0
        # Real risk = stop distance × size as a % of the real NAV (see
        # _capital_at_risk_pct). Fall back to notional estimate only without a stop.
        max_risk, capital_at_risk = _capital_at_risk_pct(
            entry_price=spot_price, stop_loss=body.stop_loss, qty=qty,
            position_value=position_value, instrument_type=body.instrument_type,
            account_equity=body.account_equity,
        )
        leg = CandidateContract(
            instrument_name=body.option_symbol or f"{sym}-PERP",
            underlying=sym,
            strike=spot_price, expiry_date="", dte=0,
            option_type=body.instrument_type,
            bid=spot_price, ask=spot_price,
            mark_price=spot_price, mid_price=spot_price, mark_iv=0.0,
            delta=1.0 if body.direction == "long" else -1.0,
            open_interest=0.0, volume_24h=0.0,
            spread_pct=0.0, health_score=0.0, healthy=True,
        )
        structure = TradeStructure(
            structure_type=body.instrument_type,
            direction=direction, legs=[leg],
            net_premium=spot_price, max_loss=0.0,
            max_gain=None, risk_reward=2.0,
            score=0.0, score_breakdown={},
            leverage=int(body.leverage),
        )
        sized = SizedTrade(
            structure=structure,
            contracts=contracts,
            contract_value=cv,
            position_value=round(position_value, 2),
            max_risk_usd=round(max_risk, 2),
            capital_at_risk_pct=round(capital_at_risk, 2),
        )
        pos = paper_store.add_position(
            underlying=sym, sized_trade=sized,
            entry_spot_price=spot_price,
            notes=f"[ALGO-FAILED] {error}",
            is_paper=False,
            order_status="failed",
        )
        return pos.id
    except Exception as e:
        log.warning("Failed algo tracking creation error: %s", e)
        return ""


@router.post("/retry-order/{position_id}")
async def retry_failed_order(position_id: str, request: Request) -> dict:
    """
    Retry a failed algo order. Looks up the failed position by ID, re-attempts
    order placement with the original parameters reconstructed from the position,
    and updates order_status accordingly.
    """
    from app.services import adapter_manager as _adm
    from app.services import exchange_account_store

    pos = paper_store.get_position(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
    if pos.order_status not in ("failed", "retry"):
        raise HTTPException(status_code=400, detail=f"Position order_status is '{pos.order_status}', not retryable")

    # Mark as retrying
    paper_store.update_position(position_id, order_status="retry", notes=f"[ALGO-RETRY] {pos.notes}")

    sym = pos.underlying
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    active = exchange_account_store.get_active()
    if not active or not active.api_key or active.api_key.startswith("DUMMY"):
        paper_store.update_position(position_id, order_status="failed",
                                     notes=f"[ALGO-FAILED] No live credentials")
        raise HTTPException(status_code=400, detail="Live credentials required for retry")

    s = pos.sized_trade.structure
    direction = "long" if s.direction.value == "long" else "short"
    side = "buy" if direction == "long" else "sell"
    instrument_type = s.structure_type
    now_ms = int(time.time() * 1000)

    try:
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
        api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
        adapter = DeltaIndiaAdapter(api_key=active.api_key, api_secret=active.api_secret,
                                     is_paper=False, base_url=api_base)

        delta_symbol = inst.delta_perp_symbol or f"{sym}USD"
        product_id   = await adapter.get_product_id(delta_symbol)
        leverage     = pos.sized_trade.leverage if hasattr(pos.sized_trade, 'leverage') else 5
        try:
            await adapter.set_leverage(product_id, leverage)
        except Exception:
            pass

        order = await adapter.place_order(
            symbol=delta_symbol, side=side,
            size=pos.sized_trade.contracts,
            order_type="market_order",
        )
        order_id  = str(order.get("id") or order.get("order_id") or "")
        fill_price = float(order.get("average_fill_price") or order.get("limit_price") or 0.0)

        paper_store.update_position(
            position_id,
            order_id=order_id,
            order_status="filled",
            entry_spot_price=fill_price or pos.entry_spot_price,
            notes=f"[LIVE-RETRY] {pos.underlying} {direction.upper()} order_id={order_id}",
        )
        log.info("Retry succeeded for %s: order_id=%s", position_id, order_id)
        return {"ok": True, "order_id": order_id, "fill_price": fill_price, "timestamp_ms": now_ms}

    except Exception as exc:
        paper_store.update_position(position_id, order_status="failed",
                                     notes=f"[ALGO-FAILED] Retry error: {exc}")
        log.error("Retry failed for %s: %s", position_id, exc)
        raise HTTPException(status_code=502, detail=f"Retry failed: {exc}")


@router.post("/update-order-status/{position_id}")
async def update_order_status(position_id: str, order_id: str, request: Request) -> dict:
    """
    Poll Delta Exchange for a specific order's status and update the position.
    Called by the frontend after placing an order to confirm fill.
    """
    from app.services import exchange_account_store
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter

    pos = paper_store.get_position(position_id)
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    active = exchange_account_store.get_active()
    if not active or active.is_paper:
        raise HTTPException(status_code=400, detail="Live credentials required")

    api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
    adapter  = DeltaIndiaAdapter(api_key=active.api_key, api_secret=active.api_secret,
                                  is_paper=False, base_url=api_base)
    try:
        result = await adapter._auth_get(f"/v2/orders/{order_id}")
        order  = result.get("result", {})
        status = order.get("state", "unknown")    # open, filled, cancelled, rejected
        fill_price = float(order.get("average_fill_price") or 0.0)
        order_status = "filled" if status == "filled" else ("cancelled" if status == "cancelled" else "pending")
        paper_store.update_position(position_id, order_status=order_status,
                                     entry_spot_price=fill_price or pos.entry_spot_price)
        return {"position_id": position_id, "order_id": order_id, "order_status": order_status,
                "fill_price": fill_price, "raw_status": status}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Status check failed: {exc}")


@router.get("/test-credentials")
async def test_credentials(request: Request) -> dict:
    """
    Verify live credentials against both Delta Exchange endpoints (global + India).
    Calls GET /v2/wallet/balances (read-only, no order placed).
    """
    from app.services import exchange_account_store
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter

    active = exchange_account_store.get_active()
    if not active or not active.api_key or not active.api_secret:
        return {"ok": False, "reason": "No credentials configured", "hint": "Enter API key and secret in Settings."}
    if active.api_key.startswith("DUMMY") or active.api_secret.startswith("DUMMY"):
        return {"ok": False, "reason": "Placeholder credentials detected", "hint": "Replace the default DUMMY key/secret with real Delta Exchange credentials."}

    errors = {}
    for label, base_url in [("India (india.delta.exchange)", "https://api.india.delta.exchange"),
                             ("Global (delta.exchange)", "https://api.delta.exchange")]:
        # Short per-call timeout so the overall test stays well under the client's
        # 25s guard even when both India and Global have to be tried.
        adapter = DeltaIndiaAdapter(api_key=active.api_key, api_secret=active.api_secret,
                                    is_paper=False, base_url=base_url, timeout=6.0)
        try:
            data = await adapter._auth_get("/v2/wallet/balances")
            balances = (data.get("result") or [])
            usd = next((b for b in balances if b.get("asset_symbol") in ("USDT", "USD")), None)
            avail = float(usd.get("available_balance", 0) if usd else 0)

            # Check if this platform has the products Sterling trades (BTCUSD etc.)
            # page_size=500 needed — Delta India has 189 perps, BTCUSD is at position 189
            try:
                prod_data = await adapter._public_get("/v2/products",
                    params={"contract_types": "perpetual_futures", "page_size": 500})
                symbols = {p.get("symbol") for p in (prod_data.get("result") or [])}
                has_btc = "BTCUSD" in symbols
            except Exception:
                has_btc = True  # assume ok if check fails

            # Persist the working URL
            updated_extra = dict(active.extra or {})
            updated_extra["api_base_url"] = base_url
            exchange_account_store.update_exchange(active.id, extra=updated_extra)

            if not has_btc:
                return {
                    "ok": False,
                    "account": label,
                    "base_url": base_url,
                    "reason": f"Connected to {label} (${avail:,.2f} available) but BTCUSD/ETHUSD are not listed here.",
                    "hint": "Sterling trades BTCUSD perpetuals which are on the Global platform (delta.exchange). "
                            "Go to delta.exchange → Settings → API Keys, generate new keys there, and re-enter them in Settings.",
                }

            return {
                "ok": True,
                "account": label,
                "balance": f"${avail:,.2f} available",
                "message": f"Connected · ${avail:,.2f} margin available",
                "base_url": base_url,
            }
        except Exception as exc:
            errors[label] = str(exc)

    # Both failed — give a consolidated error
    india_err = errors.get("India (india.delta.exchange)", "")
    global_err = errors.get("Global (delta.exchange)", "")
    primary_err = india_err or global_err
    hint = ""

    if "ip_not_whitelisted" in primary_err.lower() or "whitelist" in primary_err.lower():
        from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter as _DIA
        server_ip = await _DIA._get_public_ip()
        hint = (
            f"Your API key has IP whitelisting enabled. "
            f"Add this server's IP ({server_ip}) to the whitelist at "
            f"india.delta.exchange → Profile → API Keys → Edit Key → Allowed IPs. "
            f"Alternatively, remove all IPs from the whitelist to allow access from any IP."
        )
        label = "India" if india_err else "Global"
        return {"ok": False, "reason": f"IP not whitelisted for this API key", "hint": hint, "server_ip": server_ip}
    elif "invalid_api_key" in primary_err or "Invalid API key" in primary_err:
        hint = ("Key not recognised on either endpoint. Ensure it was generated at "
                "delta.exchange/app/account/manageapikeys (not testnet) and has Read + Trading permissions.")
    elif "403" in primary_err or "Forbidden" in primary_err:
        hint = "Key exists but lacks required permissions. Enable Read + Order Management at delta.exchange/app/account/manageapikeys."
    elif "signature" in primary_err.lower():
        hint = "Signature mismatch — ensure the API Secret is copied exactly (no extra spaces or line breaks)."
    else:
        hint = "Ensure the key is from delta.exchange (not testnet) with Read + Order Management permissions."
    label = "India" if india_err else "Global"
    return {"ok": False, "reason": f"{label}: {primary_err}", "hint": hint}


@router.get("/order-status/{order_id}")
async def get_order_status(order_id: str, request: Request) -> dict:
    """Check status of a live order."""
    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        orders = await adapter.get_open_orders()
        for o in orders:
            if o.order_id == order_id:
                return {"order_id": order_id, "status": o.status, "filled": o.filled_size, "size": o.size}
        return {"order_id": order_id, "status": "filled_or_cancelled"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.delete("/cancel-order/{order_id}")
async def cancel_order(order_id: str, product_id: int, request: Request) -> dict:
    """Cancel a single live open order. DELETE /v2/orders with {id, product_id}."""
    from app.services import exchange_account_store
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
    active = exchange_account_store.get_active()
    if not active or active.is_paper:
        raise HTTPException(status_code=400, detail="Live credentials required")
    api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
    adapter  = DeltaIndiaAdapter(api_key=active.api_key, api_secret=active.api_secret,
                                  is_paper=False, base_url=api_base)
    try:
        result = await adapter.cancel_order(order_id, product_id)
        return {"cancelled": True, "order_id": order_id, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.delete("/cancel-all")
async def cancel_all_orders(product_symbol: str, request: Request) -> dict:
    """Cancel all open orders for a product. DELETE /v2/orders/all"""
    from app.services import exchange_account_store
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
    from app.services.exchanges import instrument_registry as registry
    active = exchange_account_store.get_active()
    if not active or active.is_paper:
        raise HTTPException(status_code=400, detail="Live credentials required")
    inst = registry.get_instrument(product_symbol.upper())
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {product_symbol}")
    api_base = (active.extra or {}).get("api_base_url", "https://api.india.delta.exchange")
    adapter  = DeltaIndiaAdapter(api_key=active.api_key, api_secret=active.api_secret,
                                  is_paper=False, base_url=api_base)
    try:
        delta_symbol = inst.delta_perp_symbol or f"{product_symbol.upper()}USD"
        product_id   = await adapter.get_product_id(delta_symbol)
        result       = await adapter.cancel_all_orders(product_id)
        return {"cancelled_all": True, "product": delta_symbol, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ─── Live execution safety endpoints ────────────────────────────────────────


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str = ""


@router.get("/kill-switch")
async def get_kill_switch() -> dict:
    """Current kill-switch state. When enabled, all live orders are rejected."""
    from app.services import live_safety
    return live_safety.kill_switch_state()


@router.post("/kill-switch")
async def set_kill_switch_state(body: KillSwitchRequest) -> dict:
    """Toggle the live-order kill switch. Operator emergency halt."""
    from app.services import live_safety
    return live_safety.set_kill_switch(body.enabled, reason=body.reason)


@router.get("/daily-loss")
async def get_daily_loss() -> dict:
    """Realised PnL for the current UTC day plus circuit-breaker level."""
    from app.services import live_safety, paper_store
    return live_safety.daily_loss_state(paper_store.list_positions())


@router.get("/retry-queue")
async def get_retry_queue(include_poison: bool = True) -> dict:
    """List failed-order retry queue items. Items reaching max_attempts
    are flagged poison=True and require operator intervention."""
    from app.services import live_safety
    items = live_safety.list_retries(include_poison=include_poison)
    return {
        "items": [
            {
                "id": i.id, "payload": i.payload, "attempt": i.attempt,
                "max_attempts": i.max_attempts, "last_error": i.last_error,
                "enqueued_ms": i.enqueued_ms,
                "last_attempt_ms": i.last_attempt_ms, "poison": i.poison,
            }
            for i in items
        ],
        "count": len(items),
    }


@router.delete("/retry-queue/{rid}")
async def remove_retry_item(rid: str) -> dict:
    """Remove a retry item. Use after manual reconciliation or to drop poison."""
    from app.services import live_safety
    removed = live_safety.remove_retry(rid)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Retry item {rid} not found")
    return {"ok": True, "id": rid}
