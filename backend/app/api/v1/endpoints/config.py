"""
Runtime risk config — adjust sizing params without restart.
Data source switching — hot-swap market data adapter.
"""
import time
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import List
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


# ─── Risk config ──────────────────────────────────────────────────────────────

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


# ─── Data source ──────────────────────────────────────────────────────────────

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
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported exchange: {exchange!r}. Supported: {list(_adm.SUPPORTED_DATA_SOURCES)}",
        )
    try:
        new_adapter = await _adm.switch(exchange, body.api_key, body.api_secret)
        # Keep app.state.adapter in sync for legacy code that reads it directly
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
    """Force-clear the market data cache so the next request fetches live data."""
    ad = _adm.get_adapter()
    if ad and hasattr(ad, "invalidate"):
        ad.invalidate()  # type: ignore[attr-defined]
    return {"cleared": True, "timestamp_ms": int(time.time() * 1000)}


# ─── System info ──────────────────────────────────────────────────────────────

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


# ─── Scoring weights ──────────────────────────────────────────────────────────

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


# ─── Telegram config ─────────────────────────────────────────────────────────

class TelegramConfigRequest(BaseModel):
    bot_token: str = ""
    chat_id: str = ""
    enabled: bool = True


class TelegramConfigResponse(BaseModel):
    bot_token_set: bool
    bot_token_hint: str     # last 6 chars only — never expose full token
    chat_id: str
    enabled: bool
    reachable: bool = False


@router.get("/telegram")
async def get_telegram_config() -> TelegramConfigResponse:
    import app.services.notifications.telegram as _tg
    from app.services import db as _db
    token = _tg.TELEGRAM_TOKEN
    chat  = _tg.TELEGRAM_CHAT_ID
    # Restore in-memory flag from DB when not already set — handles page reloads
    # and any scenario where the module-level bool was reset without a server restart.
    if not _tg.TELEGRAM_REACHABLE and token and chat:
        if _db.get_config("telegram_verified") == "1":
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
    new_chat  = body.chat_id.strip()

    # Empty token = keep existing (don't wipe a saved token when only updating chat_id)
    if new_token:
        _tg.TELEGRAM_TOKEN = new_token
    if new_chat or not _tg.TELEGRAM_CHAT_ID:
        _tg.TELEGRAM_CHAT_ID = new_chat

    # Persist credentials to SQLite
    _db.set_config("telegram_bot_token", _tg.TELEGRAM_TOKEN)
    _db.set_config("telegram_chat_id",   _tg.TELEGRAM_CHAT_ID)

    # Attempt to send a verification message — write DB flag based on actual result
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
        reachable = await _tg.send(
            "<b>Sterling test message</b>\nTelegram notifications are working.",
            parse_mode="HTML",
        )
    # Persist verified status so it survives server restarts
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


# ─── Circuit breaker ─────────────────────────────────────────────────────────

@router.get("/circuit-breaker")
async def get_circuit_breaker(request: Request) -> dict:
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is None:
        return {"state": "ok", "halted": False, "size_multiplier": 1.0}
    state = "halted" if cb.halted else "ok"
    return {"state": state, "halted": cb.halted, "size_multiplier": cb.size_multiplier}


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(request: Request) -> dict:
    cb = getattr(request.app.state, "circuit_breaker", None)
    if cb is not None:
        cb.reset()
    return {"state": "ok", "halted": False, "size_multiplier": 1.0}


# ─── Eval history cap ─────────────────────────────────────────────────────────

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


# ─── NIFTY ORB + VWAP options strategy ───────────────────────────────────────

class NiftyOrbConfigRequest(BaseModel):
    enabled: bool | None = None
    underlying: str | None = None
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
    trail_atr: float | None = None
    target_r: float | None = None
    option_moneyness: str | None = None
    option_steps_itm: int | None = None
    max_risk_inr: float | None = None
    max_trades_per_day: int | None = None
    avoid_expiry_day: bool | None = None
    expiry_selection: str | None = None
    execution_broker: str | None = None
    data_source: str | None = None
    paper_only: bool | None = None


@router.get("/nifty-orb-options")
async def get_nifty_orb_options_config() -> dict:
    from app.services.nifty_orb_options import get_config
    return {"config": get_config().__dict__, "supported_data_sources": ["kite", "truedata"], "execution_brokers": ["kite"]}


@router.put("/nifty-orb-options")
async def update_nifty_orb_options_config(body: NiftyOrbConfigRequest) -> dict:
    from app.services.nifty_orb_options import set_config
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        cfg = set_config(values)
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


@router.post("/nifty-orb-options/backtest")
async def nifty_orb_options_backtest(body: dict) -> dict:
    from app.services.nifty_orb_options import backtest_from_bars
    rows = body.get("bars") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="bars must be a list of OHLCV rows")
    return backtest_from_bars(rows)


@router.post("/nifty-orb-options/execute")
async def nifty_orb_options_execute(user: UserContext = Depends(get_current_user)) -> dict:
    from app.services.nifty_orb_options import get_config, snapshot
    from app.services.kite_engine.service import place_manual_order
    cfg = get_config()
    if cfg.paper_only:
        raise HTTPException(status_code=409, detail="Strategy is paper-only. Disable paper_only after validation.")
    snap = await snapshot(user.user_id)
    plan = snap.get("plan") or {}
    contract = plan.get("contract") or {}
    quantity = int(plan.get("quantity") or 0)
    if not contract.get("symbol") or quantity <= 0:
        raise HTTPException(status_code=409, detail="No executable NIFTY ORB trade plan is active.")
    result = await place_manual_order(user.user_id, contract["symbol"], "BUY", quantity, exchange="NFO")
    return {"plan": plan, "execution": result}
