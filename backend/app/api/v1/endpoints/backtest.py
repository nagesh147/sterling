import time
from fastapi import APIRouter, HTTPException, Request
from app.schemas.backtest import (
    BacktestRequest, BacktestResult,
    MTFBacktestRequest, MTFBacktestResult,
    HybridVCPBacktestRequest, HybridVCPBacktestResult, HybridVCPProfileResult,
)
from app.services.exchanges import instrument_registry as registry
from app.engines.backtest.backtest_engine import run_backtest
from app.engines.backtest.backtest_mtf import run_mtf_backtest

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run")
async def run_backtest_endpoint(
    body: BacktestRequest,
    request: Request,
) -> dict:
    from app.core.rate_limit import check_backtest
    check_backtest(request)
    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    from app.services import adapter_manager as _adm
    from app.api.v1.endpoints.directional import _adapter_can_serve
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )
    adapter = _adm.get_adapter() or request.app.state.adapter

    # Fetch enough historical candles — extra 100 bars for EMA50 warmup
    # 1H: Deribit typically returns up to 5000 bars per request
    limit_1h = min(body.lookback_days * 24 + 100, 5000)
    limit_4h = min(body.lookback_days * 6 + 100, 1000)

    try:
        candles_4h = await adapter.get_candles(inst, "4H", limit=limit_4h)
        candles_1h = await adapter.get_candles(inst, "1H", limit=limit_1h)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}") from exc

    result = run_backtest(
        underlying=sym,
        candles_4h=candles_4h,
        candles_1h=candles_1h,
        lookback_days=body.lookback_days,
        sample_every_n_bars=body.sample_every_n_bars,
        atm_iv=body.atm_iv,
        option_dte=body.option_dte,
    )

    result_dict = result.model_dump()

    # Attach performance metrics
    try:
        import numpy as np
        from app.engines.analytics.performance import full_report
        bars = result.bars
        trades = []
        for bar in bars:
            if bar.fwd_return_4h is not None and (bar.green_arrow or bar.red_arrow):
                direction = 1 if bar.green_arrow else -1
                pnl_pct = direction * (bar.fwd_return_4h or 0.0) / 100
                trades.append({'pnl_pct': pnl_pct, 'regime': bar.macro_regime})
        if len(trades) >= 2:
            v = 1.0
            curve = [1.0]
            for t in trades:
                v *= (1 + t['pnl_pct'])
                curve.append(v)
            rpt = full_report(np.array(curve), trades)
            result_dict['performance'] = {
                'sharpe': round(rpt.sharpe, 4),
                'max_drawdown': round(rpt.max_drawdown, 4),
                'win_rate': round(rpt.win_rate, 4),
                'total_trades': rpt.total_trades,
                'regime_breakdown': rpt.regime_breakdown,
            }
            result_dict['slippage_adjusted'] = True
    except Exception:
        pass

    return result_dict


@router.post("/mtf")
async def run_mtf_backtest_endpoint(
    body: MTFBacktestRequest,
    request: Request,
) -> MTFBacktestResult:
    from app.core.rate_limit import check_backtest
    check_backtest(request)

    sym  = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    from app.services import adapter_manager as _adm
    from app.api.v1.endpoints.directional import _adapter_can_serve
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )
    adapter = _adm.get_adapter() or request.app.state.adapter

    needs_15m = "scalping_15m" in body.profiles
    needs_1h  = "scalping_15m" in body.profiles or "intraday_1h" in body.profiles
    needs_4h  = "intraday_1h"  in body.profiles or "intraday_4h" in body.profiles
    needs_1d  = "intraday_4h"  in body.profiles  # 1D regime for intraday_4h profile

    limit_15m = min(body.lookback_days * 96 + 100, 4000)
    limit_1h  = min(body.lookback_days * 24 + 100, 5000)
    limit_4h  = min(body.lookback_days * 6  + 100, 1000)
    limit_1d  = body.lookback_days + 30

    try:
        candles_15m = (
            await adapter.get_candles(inst, "15m", limit=limit_15m)
            if needs_15m else []
        )
        candles_1h = (
            await adapter.get_candles(inst, "1H",  limit=limit_1h)
            if needs_1h else []
        )
        candles_4h = (
            await adapter.get_candles(inst, "4H",  limit=limit_4h)
            if needs_4h else []
        )
        candles_1d = (
            await adapter.get_candles(inst, "1D",  limit=limit_1d)
            if needs_1d else []
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}") from exc

    # Issue 11 — apply per-underlying funding default when caller omits the field.
    from app.services.funding import resolve_funding_8h_pct
    funding = resolve_funding_8h_pct(sym, body.funding_8h_pct)

    raw = run_mtf_backtest(
        underlying=sym,
        candles_15m=candles_15m,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
        c_1d=candles_1d,
        profiles=body.profiles,
        score_min=body.score_min,
        funding_8h_pct=funding,
        exit_atr_tf=body.exit_atr_tf,
        payoff_mode=body.payoff_mode,
    )

    best_key    = None
    best_sharpe = -999.0
    for key, r in raw.items():
        s = r.get("sharpe")
        if s is not None and r.get("total_trades", 0) >= 5 and s > best_sharpe:
            best_sharpe = s
            best_key    = key

    return {
        "underlying":   sym,
        "profiles":     raw,
        "timestamp_ms": int(time.time() * 1000),
        "recommended":  best_key,
    }


@router.post("/vcp")
async def run_vcp_backtest_endpoint(
    body: HybridVCPBacktestRequest,
    request: Request,
) -> HybridVCPBacktestResult:
    """
    Hybrid VCP-Momentum Scalper backtest — single or multi-profile run.

    Fetches 15m/30m signal candles + 1h/2h regime candles from the exchange
    adapter and runs the bar-by-bar replay engine.
    """
    from app.core.rate_limit import check_backtest
    check_backtest(request)

    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    from app.services import adapter_manager as _adm
    from app.api.v1.endpoints.directional import _adapter_can_serve
    src = _adm.get_data_source()
    if not _adapter_can_serve(inst, src):
        raise HTTPException(
            status_code=400,
            detail=f"{sym} is not available on {src} data source",
        )
    adapter = _adm.get_adapter() or request.app.state.adapter

    from app.engines.hybrid_vcp import PROFILES

    has_15m = any("15m" in p for p in body.profiles)
    has_30m = any("30m" in p for p in body.profiles)
    needs_1h = has_15m
    needs_2h = has_30m

    limit_signal = max(
        (15 if has_15m else 30) * 96 + 200,   # enough bars for EMA21 warmup + regime
        4000,
    )
    limit_regime = max(
        (60 if needs_1h else 120) * 24 + 200,
        2000,
    )

    try:
        candles_by_tf = {}
        if has_15m:
            candles_by_tf["15m"] = await adapter.get_candles(inst, "15m", limit=limit_signal)
        if has_30m:
            candles_by_tf["30m"] = await adapter.get_candles(inst, "30m", limit=limit_signal)
        if needs_1h:
            candles_by_tf["1h"] = await adapter.get_candles(inst, "1H", limit=limit_regime)
        if needs_2h:
            candles_by_tf["2h"] = await adapter.get_candles(inst, "2h", limit=limit_regime)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Candle fetch failed: {exc}") from exc

    from app.services.funding import resolve_funding_8h_pct
    from app.engines.hybrid_vcp.backtest import run_all_profiles
    from app.schemas.backtest import HybridVCPProfileResult

    funding = resolve_funding_8h_pct(sym, body.funding_8h_pct)

    active_profiles = {k: v for k, v in PROFILES.items() if k in body.profiles}
    if not active_profiles:
        raise HTTPException(
            status_code=400,
            detail=f"No valid profiles. Available: {list(PROFILES.keys())}",
        )

    raw_results = run_all_profiles(candles_by_tf, active_profiles)

    profile_results = {}
    best_key = None
    best_sharpe = -999.0

    for key, rpt in raw_results.items():
        profile_results[key] = HybridVCPProfileResult(
            label=rpt.profile,
            signal_tf=active_profiles[key].signal_tf,
            regime_tf=active_profiles[key].regime_tf,
            trade_count=rpt.trade_count,
            win_rate=rpt.win_rate if rpt.trade_count >= 3 else None,
            sharpe=rpt.sharpe if rpt.trade_count >= 5 else None,
            sortino=rpt.sortino if rpt.trade_count >= 5 else None,
            profit_factor=rpt.profit_factor if rpt.trade_count >= 3 else None,
            max_drawdown=rpt.max_drawdown,
            cagr=rpt.cagr if rpt.trade_count >= 10 else None,
            equity_curve=rpt.equity_curve,
            trades=[
                {
                    "entry_bar":     t.entry_bar,
                    "exit_bar":      t.exit_bar,
                    "direction":     t.direction,
                    "entry_price":   t.entry_price,
                    "exit_price":    t.exit_price,
                    "pnl_pct":       t.pnl_pct,
                    "gross_pnl":     t.gross_pnl,
                    "cost_pct":      t.cost_pct,
                    "net_pnl":       t.net_pnl,
                    "hold_bars":     t.hold_bars,
                    "exit_reason":   t.exit_reason,
                }
                for t in rpt.trades
            ],
        )
        if rpt.trade_count >= 5 and (rpt.sharpe or -999) > best_sharpe:
            best_sharpe = rpt.sharpe or -999
            best_key = key

    return HybridVCPBacktestResult(
        underlying=sym,
        profiles=profile_results,
        timestamp_ms=int(time.time() * 1000),
        recommended=best_key,
    )
