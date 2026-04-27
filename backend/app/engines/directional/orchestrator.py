import time
from typing import Optional, List

import numpy as np

from app.schemas.market import Candle
from app.schemas.instruments import InstrumentMeta
from app.schemas.directional import TradeState, Direction, ExecMode, IVRBand
from app.schemas.execution import RunOnceResponse, PreviewResponse, SizedTrade
from app.schemas.risk import RiskParams

from app.services.exchanges.base import BaseExchangeAdapter
from app.engines.directional.regime_engine import compute_regime
from app.engines.directional.signal_engine import compute_signal
from app.engines.directional.setup_engine import evaluate_setup
from app.engines.directional.policy_engine import apply_policy
from app.engines.directional.execution_engine import assess_timing
from app.engines.directional.option_translation_engine import translate_options
from app.engines.directional.structure_selector import build_structures
from app.engines.directional.sizing_engine import size_trade
from app.engines.directional.scoring import rank_structures, score_no_trade
from app.core.logging import get_logger

log = get_logger(__name__)


def _compute_hv_ivr(candles_1h: List[Candle]) -> Optional[float]:
    """
    Realized-volatility IVR fallback for instruments without a DVOL index.
    Computes annualized HV over 24-hour windows for 30 days,
    then returns the percentile rank of the latest window (0-100).
    """
    if len(candles_1h) < 50:
        return None
    closes = np.array([c.close for c in candles_1h], dtype=np.float64)
    log_rets = np.diff(np.log(closes + 1e-10))
    window = 24  # bars per day (1H resolution)
    hvs: List[float] = []
    for end in range(window, len(log_rets) + 1, window):
        seg = log_rets[max(0, end - window): end]
        if len(seg) >= 12:
            hv = float(np.std(seg) * np.sqrt(252 * 24) * 100)
            hvs.append(hv)
    if len(hvs) < 3:
        return None
    lo, hi = min(hvs), max(hvs)
    if hi <= lo:
        return None
    return round((hvs[-1] - lo) / (hi - lo) * 100.0, 2)


async def compute_ivr(
    adapter: BaseExchangeAdapter,
    instrument: InstrumentMeta,
    candles_1h: Optional[List[Candle]] = None,
) -> Optional[float]:
    """
    Compute IVR from DVOL if available, falling back to realized-vol percentile.
    Pass candles_1h to enable the HV fallback for non-DVOL instruments.
    """
    history = await adapter.get_dvol_history(instrument, days=30)
    current = await adapter.get_dvol(instrument)
    if history and current is not None:
        lo, hi = min(history), max(history)
        if hi > lo:
            raw = (current - lo) / (hi - lo) * 100.0
            return round(max(0.0, min(100.0, raw)), 2)  # clamp [0,100]
    # Fallback: realized vol from 1H candles
    if candles_1h:
        return _compute_hv_ivr(candles_1h)
    return None


async def run_once(
    instrument: InstrumentMeta,
    adapter: BaseExchangeAdapter,
    risk_params: Optional[RiskParams] = None,
) -> RunOnceResponse:
    now_ms = int(time.time() * 1000)
    risk = risk_params or RiskParams()

    if not instrument.has_options:
        return RunOnceResponse(
            underlying=instrument.underlying, paper_mode=True,
            state=TradeState.FILTERED, direction=Direction.NEUTRAL,
            recommendation="no_trade",
            reason=f"{instrument.underlying} has no options on {instrument.exchange}",
            timestamp_ms=now_ms,
        )

    try:
        candles_4h = await adapter.get_candles(instrument, "4H", limit=100)
        candles_1h = await adapter.get_candles(instrument, "1H", limit=200)
        candles_15m = await adapter.get_candles(instrument, "15m", limit=50)
    except Exception as exc:
        log.error("Candle fetch failed for %s: %s", instrument.underlying, exc)
        return RunOnceResponse(
            underlying=instrument.underlying, paper_mode=True,
            state=TradeState.FILTERED, direction=Direction.NEUTRAL,
            recommendation="no_trade",
            reason=f"Market data unavailable: {exc}",
            timestamp_ms=now_ms,
        )

    regime = compute_regime(candles_4h)
    signal = compute_signal(candles_1h)
    setup = evaluate_setup(regime, signal)

    if setup.state in (TradeState.IDLE, TradeState.FILTERED):
        return RunOnceResponse(
            underlying=instrument.underlying, paper_mode=True,
            state=setup.state, direction=setup.direction,
            regime=regime.model_dump(), signal=signal.model_dump(),
            recommendation="no_trade", reason=setup.reason,
            timestamp_ms=now_ms,
        )

    exec_timing = assess_timing(candles_15m, signal)
    ivr = await compute_ivr(adapter, instrument, candles_1h)
    policy = apply_policy(setup.direction, instrument, ivr)

    try:
        option_chain = await adapter.get_option_chain(instrument)
        spot_price = await adapter.get_index_price(instrument)
    except Exception as exc:
        log.error("Option chain fetch failed: %s", exc)
        return RunOnceResponse(
            underlying=instrument.underlying, paper_mode=True,
            state=TradeState.FILTERED, direction=setup.direction,
            regime=regime.model_dump(), signal=signal.model_dump(),
            ivr=ivr, ivr_band=policy.ivr_band,
            recommendation="no_trade",
            reason=f"Option chain unavailable: {exc}",
            timestamp_ms=now_ms,
        )

    calls, puts = translate_options(
        instrument, setup.direction, policy, option_chain, spot_price
    )
    structures = build_structures(calls, puts, setup.direction, policy)

    if not structures:
        return RunOnceResponse(
            underlying=instrument.underlying, paper_mode=True,
            state=TradeState.FILTERED, direction=setup.direction,
            regime=regime.model_dump(), signal=signal.model_dump(),
            ivr=ivr, ivr_band=policy.ivr_band,
            recommendation="no_trade",
            reason="No healthy candidate structures found",
            timestamp_ms=now_ms,
        )

    ranked = rank_structures(structures, regime, signal, exec_timing, policy)
    no_trade_scr = score_no_trade(regime, signal, policy)
    sized_trades = [size_trade(s, risk) for s in ranked[:5]]

    best = ranked[0] if ranked else None
    if best and best.score > no_trade_scr:
        recommendation = best.structure_type
        state_final = (
            TradeState.ENTRY_ARMED_PULLBACK
            if exec_timing.mode == ExecMode.PULLBACK
            else TradeState.ENTRY_ARMED_CONTINUATION
        )
        reason = (
            f"{exec_timing.reason} | "
            f"Score: {best.score:.1f} vs no-trade: {no_trade_scr:.1f}"
        )
    else:
        recommendation = "no_trade"
        state_final = TradeState.FILTERED
        reason = (
            f"Best score {best.score if best else 0:.1f} "
            f"<= no-trade {no_trade_scr:.1f}"
        )

    return RunOnceResponse(
        underlying=instrument.underlying, paper_mode=True,
        state=state_final, direction=setup.direction,
        regime=regime.model_dump(), signal=signal.model_dump(),
        exec_mode=exec_timing.mode,
        ivr=ivr, ivr_band=policy.ivr_band,
        ranked_structures=sized_trades,
        no_trade_score=no_trade_scr,
        recommendation=recommendation, reason=reason,
        timestamp_ms=now_ms,
    )


async def preview(
    instrument: InstrumentMeta,
    adapter: BaseExchangeAdapter,
) -> PreviewResponse:
    now_ms = int(time.time() * 1000)

    if not instrument.has_options:
        return PreviewResponse(
            underlying=instrument.underlying,
            state=TradeState.FILTERED, direction=Direction.NEUTRAL,
            reason=f"{instrument.underlying} has no options on {instrument.exchange}",
            timestamp_ms=now_ms,
        )

    try:
        candles_4h = await adapter.get_candles(instrument, "4H", limit=100)
        candles_1h = await adapter.get_candles(instrument, "1H", limit=200)
    except Exception as exc:
        return PreviewResponse(
            underlying=instrument.underlying,
            state=TradeState.FILTERED, direction=Direction.NEUTRAL,
            reason=f"Market data unavailable: {exc}",
            timestamp_ms=now_ms,
        )

    regime = compute_regime(candles_4h)
    signal = compute_signal(candles_1h)
    setup = evaluate_setup(regime, signal)
    ivr = await compute_ivr(adapter, instrument, candles_1h)
    policy = apply_policy(setup.direction, instrument, ivr)

    if setup.direction == Direction.NEUTRAL:
        return PreviewResponse(
            underlying=instrument.underlying,
            state=setup.state, direction=setup.direction,
            ivr=ivr, ivr_band=policy.ivr_band,
            reason=setup.reason, timestamp_ms=now_ms,
        )

    try:
        option_chain = await adapter.get_option_chain(instrument)
        spot_price = await adapter.get_index_price(instrument)
    except Exception as exc:
        return PreviewResponse(
            underlying=instrument.underlying,
            state=setup.state, direction=setup.direction,
            ivr=ivr, ivr_band=policy.ivr_band,
            reason=f"Option chain unavailable: {exc}",
            timestamp_ms=now_ms,
        )

    calls, puts = translate_options(
        instrument, setup.direction, policy, option_chain, spot_price
    )
    all_candidates = calls + puts
    structures = build_structures(calls, puts, setup.direction, policy)

    candles_15m = []
    try:
        candles_15m = await adapter.get_candles(instrument, "15m", limit=50)
    except Exception:
        pass

    from app.schemas.directional import ExecTimingResult
    exec_timing = (
        assess_timing(candles_15m, signal)
        if candles_15m
        else ExecTimingResult(mode=ExecMode.WAIT, confidence=0.0, reason="No 15m data")
    )

    ranked = rank_structures(structures, regime, signal, exec_timing, policy)

    return PreviewResponse(
        underlying=instrument.underlying,
        state=setup.state, direction=setup.direction,
        candidates=all_candidates[:10],
        ranked_structures=ranked[:5],
        ivr=ivr, ivr_band=policy.ivr_band,
        reason=setup.reason, timestamp_ms=now_ms,
    )
