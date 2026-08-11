"""Research-only Adaptive Edge endpoints.

This router never places orders. It fetches historical Kite candles, builds the
causal feature stream, and runs the deterministic replay engine.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import UserContext, get_current_user
from app.services.exchanges.kite import accounts as kite_accounts
from app.services.kite_engine.backtest_service import _resolve_underlying_token, _inst
from app.services.kite_engine.universe import build_universe
from app.engines.adaptive_edge.backtest import ReplayConfig, run_replay
from app.engines.adaptive_edge.kite_adapter import build_replay_bars

router = APIRouter(prefix="/kite/adaptive-edge", tags=["adaptive-edge"])


class AdaptiveEdgeBacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=80)
    lookback_bars: int = Field(default=1000, ge=100, le=5000)
    initial_capital: float = Field(default=100_000.0, gt=0)
    risk_fraction: float = Field(default=0.01, gt=0, le=0.05)
    fee_rate: float = Field(default=0.001, ge=0, le=0.02)
    slippage_bps: float = Field(default=5.0, ge=0, le=100)
    max_holding_bars: int = Field(default=24, ge=1, le=500)
    cooldown_bars: int = Field(default=2, ge=0, le=100)


async def _client(user: UserContext):
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active Kite account — add credentials and log in first.")
    return await kite_accounts.acquire_client(acct)


@router.post("/backtest")
async def adaptive_edge_backtest(
    body: AdaptiveEdgeBacktestRequest,
    user: UserContext = Depends(get_current_user),
) -> dict:
    client = await _client(user)
    resolved = await _resolve_underlying_token(client, body.symbol)
    if resolved is None:
        raise HTTPException(404, f"Could not resolve Kite underlying '{body.symbol}'")

    token, name = resolved
    candles = await client.get_candles(_inst(token, name), "1H", body.lookback_bars)
    if len(candles) < 30:
        raise HTTPException(422, f"Only {len(candles)} candles returned; at least 30 are required")

    bars = build_replay_bars(candles)
    result = run_replay(
        bars,
        ReplayConfig(
            initial_capital=body.initial_capital,
            risk_fraction=body.risk_fraction,
            fee_rate=body.fee_rate,
            slippage_bps=body.slippage_bps,
            max_holding_bars=body.max_holding_bars,
            cooldown_bars=body.cooldown_bars,
        ),
    )
    return {
        "strategy": "adaptive-edge",
        "version": "0.1.0",
        "mode": "research_backtest",
        "underlying": name,
        "candles": len(candles),
        "bars": len(bars),
        "initial_capital": result.initial_capital,
        "final_capital": result.final_capital,
        "total_return": result.total_return,
        "max_drawdown": result.max_drawdown,
        "trade_count": len(result.trades),
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "formula_versions": {f"F-{n}": "0.1.0" for n in range(101, 115)},
        "live_execution_enabled": False,
    }
