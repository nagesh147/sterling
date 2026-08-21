"""
Runtime risk config — adjust sizing params without restart.
Data source switching — hot-swap market data adapter.
"""
import time
from fastapi import APIRouter, Body, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.schemas.risk import RiskParams, ScoringWeights
from app.core.config import settings
from app.core.auth import UserContext, get_current_user
from app.services.exchanges import instrument_registry as registry
from app.services import adapter_manager as _adm

router = APIRouter(prefix="/config", tags=["config"])

_risk = RiskParams(
    capital=settings.default_capital,
    max_position_pct=settings.max_position_pct,
    max_contracts=settings.max_contracts,
)

def get_runtime_risk() -> RiskParams:
    return _risk

_scoring_weights = ScoringWeights()

def get_scoring_weights() -> ScoringWeights:
    return _scoring_weights

@router.get("/risk")
async def get_risk_config() -> RiskParams:
    return _risk

@router.put("/risk")
async def update_risk_config(params: RiskParams) -> RiskParams:
    global _risk
    _risk = params
    return _risk

@router.post("/risk/reset")
async def reset_risk_config() -> RiskParams:
    global _risk
    _risk = RiskParams(
        capital=settings.default_capital,
        max_position_pct=settings.max_position_pct,
        max_contracts=settings.max_contracts,
        hybrid_st_weight=0.5,
    )
    return _risk

class DataSourceRequest(BaseModel):
    exchange: str
    api_key: str = ""
    api_secret: str = ""

class DataSourceResponse(BaseModel):
    exchange: str
    display_name: str
    reachable: bool
    adapter_stack: str
    timestamp_ms: int

@router.get("/data-source")
async def get_data_source() -> DataSourceResponse:
    name = _adm.get_data_source()
    ad = _adm.get_adapter()
    reachable = False
    if ad:
        try:
            reachable = await ad.ping()
        except Exception:
            pass
    return DataSourceResponse(
        exchange=name,
        display_name=_adm.SUPPORTED_DATA_SOURCES.get(name, name),
        reachable=reachable,
        adapter_stack=f"CachingAdapter > RetryingAdapter > {name.title().replace('_', '')}Adapter",
        timestamp_ms=int(time.time() * 1000),
    )

@router.post("/data-source")
async def set_data_source(body: DataSourceRequest, request: Request) -> DataSourceResponse:
    exchange = body.exchange.lower()
    if exchange not in _adm.SUPPORTED_DATA_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unsupported exchange: {exchange!r}. Supported: {list(_adm.SUPPORTED_DATA_SOURCES)}")
    try:
        new_adapter = await _adm.switch(exchange, body.api_key, body.api_secret)
        request.app.state.adapter = new_adapter
        reachable = await new_adapter.ping()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to connect to {exchange}: {exc}") from exc
    return DataSourceResponse(
        exchange=exchange,
        display_name=_adm.SUPPORTED_DATA_SOURCES.get(exchange, exchange),
        reachable=reachable,
        adapter_stack=f"CachingAdapter > RetryingAdapter > {exchange.title().replace('_', '')}Adapter",
        timestamp_ms=int(time.time() * 1000),
    )

@router.post("/data-source/invalidate-cache")
async def invalidate_cache() -> dict:
    ad = _adm.get_adapter()
    if ad and hasattr(ad, "invalidate"):
        ad.invalidate()
    return {"cleared": True, "timestamp_ms": int(time.time() * 1000)}

class SystemInfo(BaseModel):
    version: str
    environment: str
    exchange_adapter: str
    active_data_source: str
    data_source_display: str
    paper_trading: bool
    real_public_data: bool
    default_underlying: str
    supported_underlyings: List[str]
    underlyings_with_options: List[str]
    adapter_stack: str
    db_path: str
    supported_data_sources: dict
    timestamp_ms: int

@router.get("/info")
async def system_info() -> SystemInfo:
    import os
    instruments = registry.list_instruments()
    ds = _adm.get_data_source()
    return SystemInfo(
        version="0.4.0",
        environment=settings.environment,
        exchange_adapter=settings.exchange_adapter,
        active_data_source=ds,
        data_source_display=_adm.SUPPORTED_DATA_SOURCES.get(ds, ds),
        paper_trading=settings.paper_trading,
        real_public_data=settings.real_public_data,
        default_underlying=settings.default_underlying,
        supported_underlyings=[i.underlying for i in instruments],
        underlyings_with_options=[i.underlying for i in instruments if i.has_options],
        adapter_stack=f"CachingAdapter > RetryingAdapter > {ds.title().replace('_', '')}Adapter",
        db_path=os.environ.get("STERLING_DB_PATH", "sterling_paper.db"),
        supported_data_sources=_adm.SUPPORTED_DATA_SOURCES,
        timestamp_ms=int(time.time() * 1000),
    )

@router.get("/scoring-weights")
async def get_scoring_weights_endpoint() -> ScoringWeights:
    return _scoring_weights

@router.put("/scoring-weights")
async def update_scoring_weights(body: ScoringWeights) -> ScoringWeights:
    global _scoring_weights
    _scoring_weights = body
    return _scoring_weights

@router.post("/scoring-weights/reset")
async def reset_scoring_weights() -> ScoringWeights:
    global _scoring_weights
    _scoring_weights = ScoringWeights()
    return _scoring_weights

class TelegramConfigRequest(BaseModel):
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True

class TelegramConfigResponse(BaseModel):
    bot_token_set: bool
    bot_token_hint: str
    chat_id: str
    enabled: bool
    reachable: bool = False

@router.get("/telegram")
async def get_telegram_config() -> TelegramConfigResponse:
    import app.services.notifications.telegram as _tg
    from app.services import db as _db
    token = _tg.TELEGRAM_TOKEN
    chat = _tg.TELEGRAM_CHAT_ID
    if not _tg.TELEGRAM_REACHABLE and token and chat and _db.get_config("telegram_verified") == "1":
        _tg.TELEGRAM_REACHABLE = True
    return TelegramConfigResponse(
        bot_token_set=bool(token),
        bot_token_hint=f"…{token[-6:]}" if len(token) >= 6 else ("set" if token else ""),
        chat_id=chat,
        enabled=bool(token and chat),
        reachable=_tg.TELEGRAM_REACHABLE,
    )

@router.put("/telegram")
async def set_telegram_config(body: TelegramConfigRequest) -> TelegramConfigResponse:
    import app.services.notifications.telegram as _tg
    from app.services import db as _db
    new_token = body.bot_token.strip()
    new_chat = body.chat_id.strip()
    if new_token:
        _tg.TELEGRAM_TOKEN = new_token
    if new_chat or not _tg.TELEGRAM_CHAT_ID:
        _tg.TELEGRAM_CHAT_ID = new_chat
    _db.set_config("telegram_bot_token", _tg.TELEGRAM_TOKEN)
    _db.set_config("telegram_chat_id", _tg.TELEGRAM_CHAT_ID)
    reachable = False
    if _tg.TELEGRAM_TOKEN and _tg.TELEGRAM_CHAT_ID:
        try:
            reachable = await _tg.send("✓ Sterling Telegram connected", parse_mode="HTML")
        except Exception:
            pass
    _db.set_config("telegram_verified", "1" if reachable else "0")
    _tg.TELEGRAM_REACHABLE = reachable
    token = _tg.TELEGRAM_TOKEN
    return TelegramConfigResponse(
        bot_token_set=bool(token),
        bot_token_hint=f"…{token[-6:]}" if len(token) >= 6 else ("set" if token else ""),
        chat_id=_tg.TELEGRAM_CHAT_ID,
        enabled=bool(token and _tg.TELEGRAM_CHAT_ID),
        reachable=reachable,
    )

@router.post("/telegram/test")
async def test_telegram() -> TelegramConfigResponse:
    import app.services.notifications.telegram as _tg
    from app.services import db as _db
    reachable = False
    if _tg.TELEGRAM_TOKEN and _tg.TELEGRAM_CHAT_ID:
        reachable = await _tg.send("<b>Sterling test message</b>\nTelegram notifications are working.", parse_mode="HTML")
    if reachable:
        _db.set_config("telegram_verified", "1")
    token = _tg.TELEGRAM_TOKEN
    return TelegramConfigResponse(
        bot_token_set=bool(token),
        bot_token_hint=f"…{token[-6:]}" if len(token) >= 6 else ("set" if token else ""),
        chat_id=_tg.TELEGRAM_CHAT_ID,
        enabled=bool(token and _tg.TELEGRAM_CHAT_ID),
        reachable=reachable,
    )

@router.get("/circuit-breaker")
async def get_circuit_breaker(request: Request) -> dict:
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is None:
        return {"state": "ok", "halted": False, "size_multiplier": 1.0}
    return {"state": "halted" if cb.halted else "ok", "halted": cb.halted, "size_multiplier": cb.size_multiplier}

@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(request: Request) -> dict:
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is not None:
        cb.reset()
    return {"state": "ok", "halted": False, "size_multiplier": 1.0}

class EvalHistoryCapResponse(BaseModel):
    cap: int

@router.get("/eval-history-cap")
async def get_eval_history_cap() -> EvalHistoryCapResponse:
    from app.services import eval_history
    return EvalHistoryCapResponse(cap=eval_history.get_cap())

@router.put("/eval-history-cap")
async def set_eval_history_cap(cap: int = 50) -> EvalHistoryCapResponse:
    from app.services import eval_history
    eval_history.set_cap(cap)
    return EvalHistoryCapResponse(cap=eval_history.get_cap())


# NIFTY ORB configuration is deliberately kept in this endpoint alongside the
# existing runtime configuration surface. Trading mode remains universal: there is
# no strategy-local paper/live switch.
class NiftyOrbConfigRequest(BaseModel):
    enabled: bool | None = None
    underlying: str | None = None
    scan_indices: list[str] | None = None
    scan_stocks: list[str] | None = None
    scan_all_stocks: bool | None = None
    scan_stock_contracts: bool | None = None
    interval_minutes: int | None = None
    opening_range_minutes: int | None = None
    entry_start: str | None = None
    entry_end: str | None = None
    min_breakout_atr: float | None = None
    volume_multiplier: float | None = None
    vwap_slope_lookback: int | None = None
    trend_lookback: int | None = None
    atr_period: int | None = None
    stop_buffer_atr: float | None = None
    target_r: float | None = None
    option_moneyness: str | None = None
    option_steps_itm: int | None = None
    max_risk_inr: float | None = None
    max_trades_per_day: int | None = None
    avoid_expiry_day: bool | None = None
    expiry_selection: str | None = None
    expiry_dte_min: int | None = None
    expiry_dte_max: int | None = None
    execution_broker: str | None = None
    data_source: str | None = None
    max_spread_pct: float | None = None
    min_option_volume: float | None = None
    min_open_interest: float | None = None
    max_quote_staleness_s: int | None = None
    truedata_use_ticks: bool | None = None
    truedata_use_oi: bool | None = None
    truedata_use_bid_ask: bool | None = None
    truedata_use_quote_freshness: bool | None = None

@router.get("/nifty-orb-options")
async def get_nifty_orb_options_config() -> dict:
    """Current ORB config, plus the engine's own defaults.

    The defaults are published rather than mirrored in the client so the UI can
    mark which fields are still at default without keeping a second copy that
    could drift from the engine — the failure mode this codebase keeps hitting.
    """
    from app.engines.nifty_orb_options import StrategyConfig
    from app.services.nifty_orb_options import get_config
    cfg = get_config()
    return {
        "config": cfg.__dict__,
        "defaults": StrategyConfig().__dict__,
        "supported_data_sources": ["kite", "truedata"],
        "execution_brokers": ["kite"],
    }

@router.put("/nifty-orb-options")
async def update_nifty_orb_options_config(body: NiftyOrbConfigRequest) -> dict:
    from app.services.nifty_orb_options import set_config
    try:
        cfg = set_config({k: v for k, v in body.model_dump().items() if v is not None})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"config": cfg.__dict__}

@router.post("/nifty-orb-options/snapshot")
async def nifty_orb_options_snapshot(user: UserContext = Depends(get_current_user)) -> dict:
    from app.services.nifty_orb_options import snapshot
    try:
        return await snapshot(user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"NIFTY ORB snapshot failed: {exc}") from exc

@router.post("/nifty-orb-options/scan")
async def nifty_orb_options_scan(user: UserContext = Depends(get_current_user)) -> dict:
    from app.services.nifty_orb_scanner import scan_user
    try:
        return await scan_user(user.user_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"NIFTY ORB scan failed: {exc}") from exc

@router.post("/nifty-orb-options/backtest")
async def nifty_orb_options_backtest(body: dict) -> dict:
    from app.services.nifty_orb_options import backtest_from_bars
    rows = body.get("bars") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="bars must be a list of OHLCV rows")
    return backtest_from_bars(rows)

@router.post("/nifty-orb-options/execute")
async def nifty_orb_options_execute(user: UserContext = Depends(get_current_user)) -> dict:
    from app.services.nifty_orb_options import execute_manual
    try:
        return await execute_manual(user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"NIFTY ORB execution failed: {exc}") from exc

@router.on_event("startup")
async def _start_nifty_orb_runner() -> None:
    from app.services.nifty_orb_options_runner import start
    start()

# --------------------------------------------------------------------------
# ATM Premium Imbalance
#
# Registered exactly the way NIFTY ORB is: engine package + service config
# store + these endpoints. The repository has no central strategy registry to
# add to -- app/engines/edge/catalog.py catalogues backtest-validated
# (symbol, tf, profile) combos for the edge feed, which is a different concept
# -- so inventing a second registry here would create the parallel
# infrastructure the strategy contract forbids. The strategy publishes its own
# identity on GET instead.
# --------------------------------------------------------------------------

class ATMPremiumImbalanceConfigRequest(BaseModel):
    enabled: bool | None = None
    underlying: str | None = None
    expiry_policy: str | None = None
    explicit_expiry: str | None = None
    strike_policy: str | None = None
    session_start: str | None = None
    session_end: str | None = None
    quote_mode: str | None = None
    max_quote_age_ms: int | None = None
    max_ce_pe_skew_ms: int | None = None
    signal_mode: str | None = None
    minimum_difference: float | None = None
    minimum_difference_percent: float | None = None
    entry_price_policy: str | None = None
    require_session_origin_tick: bool | None = None
    first_tick_source: str | None = None
    entry_buffer_points: float | None = None
    entry_through_pct: float | None = None
    manual_price_file: str | None = None
    max_entry_attempts: int | None = None
    entry_attempt_timeout_ms: int | None = None
    exit_policy: str | None = None
    protection_mode: str | None = None
    target_points: float | None = None
    exit_buffer_points: float | None = None
    stop_enabled: bool | None = None
    stop_points: float | None = None
    max_hold_seconds: int | None = None
    max_trades_per_session: int | None = None
    quantity: int | None = None
    max_quantity: int | None = None
    max_premium_at_risk_inr: float | None = None
    daily_loss_limit_inr: float | None = None
    data_source: str | None = None
    execution_mode: str | None = None


@router.get("/atm-premium-imbalance")
async def get_atm_premium_imbalance_config() -> dict:
    """Current config plus the engine's own defaults and vocabularies.

    Defaults and enums are published rather than mirrored in the client, so the
    UI cannot drift from the engine -- the recurring bug class in this codebase
    is a UI that claims backend behaviour the backend does not honour.
    """
    from app.engines.atm_premium_imbalance.config import (
        ENTRY_PRICE_POLICIES, EXIT_POLICIES, EXPIRY_POLICIES, FIRST_TICK_SOURCES,
        PROTECTION_MODES, QUOTE_MODES, RESEARCH_ONLY_ENTRY_POLICIES, SIZING_MODES,
        RESEARCH_ONLY_EXIT_POLICIES, STRIKE_POLICIES, ATMPremiumImbalanceConfig,
    )
    from app.services.atm_premium_imbalance import descriptor, get_config
    cfg = get_config()
    return {
        "strategy": {**descriptor(), "enabled": cfg.enabled},
        "config": cfg.as_dict(),
        "defaults": ATMPremiumImbalanceConfig().as_dict(),
        "vocabularies": {
            "expiry_policy": sorted(EXPIRY_POLICIES),
            "strike_policy": sorted(STRIKE_POLICIES),
            "quote_mode": sorted(QUOTE_MODES),
            "entry_price_policy": sorted(ENTRY_PRICE_POLICIES),
            "exit_policy": sorted(EXIT_POLICIES),
            "protection_mode": sorted(PROTECTION_MODES),
            "sizing_mode": sorted(SIZING_MODES),
            "first_tick_source": sorted(FIRST_TICK_SOURCES),
            "data_source": ["kite", "truedata"],
            "execution_mode": ["paper", "live"],
        },
        # The UI must be able to grey these out rather than offer a switch that
        # validate() will refuse.
        "research_only": {
            "entry_price_policy": sorted(RESEARCH_ONLY_ENTRY_POLICIES),
            "exit_policy": sorted(RESEARCH_ONLY_EXIT_POLICIES),
        },
        # Live refuses NONE: a crash while long would leave the position with
        # nothing watching it. Published so the UI can say so up front.
        "live_requires": {"protection_mode": sorted(PROTECTION_MODES - {"NONE"}),
                          "quote_mode": ["EXECUTABLE"],
                          "require_session_origin_tick": [True]},
    }


@router.put("/atm-premium-imbalance")
async def update_atm_premium_imbalance_config(body: ATMPremiumImbalanceConfigRequest) -> dict:
    from app.services.atm_premium_imbalance import set_config
    try:
        cfg = set_config({k: v for k, v in body.model_dump().items() if v is not None})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"config": cfg.as_dict()}


@router.get("/atm-premium-imbalance/snapshot")
async def atm_premium_imbalance_snapshot(user: UserContext = Depends(get_current_user)) -> dict:
    """Config, the resolved ATM pair, and every reason the strategy is not armed.

    The tenant comes from the authenticated session, never from the request:
    taking it from the body would let any caller resolve instruments against
    another user's broker credentials and rate limit.
    """
    from app.services.atm_premium_imbalance import snapshot
    uid = str(user.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="authenticated user is required")
    try:
        return await snapshot(uid)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"ATM Premium Imbalance snapshot failed: {exc}"
        ) from exc


@router.post("/atm-premium-imbalance/arm")
async def atm_premium_imbalance_arm(user: UserContext = Depends(get_current_user)) -> dict:
    """Resolve the ATM pair, subscribe both legs, and arm the session.

    Idempotent for the day: arming twice returns ``already_armed`` rather than
    creating a second session that could place a second entry. The strategy then
    runs off the Kite tick stream, not off this call.
    """
    from app.services.atm_premium_imbalance_runner import arm
    uid = str(user.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="authenticated user is required")
    try:
        return await arm(uid)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ATM Premium Imbalance arm failed: {exc}") from exc


@router.post("/atm-premium-imbalance/adopt")
async def atm_premium_imbalance_adopt(
    symbol: str, user: UserContext = Depends(get_current_user),
) -> dict:
    """Take charge of an open position the app has no session for.

    Requires the symbol rather than adopting whatever is found: a long option on
    this underlying may be a hand-placed trade, and the operator is the one who
    knows which position is the strategy's.
    """
    from app.services.atm_premium_imbalance_runner import adopt
    uid = str(user.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="authenticated user is required")
    try:
        return await adopt(uid, symbol)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"ATM Premium Imbalance adopt failed: {exc}"
        ) from exc


@router.post("/atm-premium-imbalance/simulate")
async def atm_premium_imbalance_simulate(
    speed: float = 60.0, lots: Optional[int] = None,
    overrides: Optional[dict] = Body(default=None, embed=True),
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Replay the last traded session through the live code path, on a fake clock.

    The clock starts at 09:14 IST so the pre-open refusal is visible, then the
    strategy runs against real minute bars. Nothing reaches a broker: the session
    is marked as a simulation, which is also what stops today's live ticks from
    driving it.

    Results are illustrative, not a backtest — see the module docstring for the
    two structural reasons (minute bars have no intrabar order, and fills are
    modelled at the limit price).
    """
    from app.services.atm_premium_imbalance_sim import start
    uid = str(user.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="authenticated user is required")
    try:
        return await start(uid, speed=speed, lots=lots, overrides=overrides)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"ATM Premium Imbalance simulation failed: {exc}"
        ) from exc


@router.post("/atm-premium-imbalance/simulate/stop")
async def atm_premium_imbalance_simulate_stop(
    user: UserContext = Depends(get_current_user),
) -> dict:
    from app.services.atm_premium_imbalance_sim import stop
    uid = str(user.user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="authenticated user is required")
    return await stop(uid)
