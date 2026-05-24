"""STRATEGY STUB — directional orchestrator removed in the strategy reset.

The orchestrator previously wired regime → signal → setup → structures → sizing
into a single evaluation. It was stripped so a new strategy can be built on a
clean seam (preserved in git history on the `strategy-v2` branch).

`run_once` / `preview` return empty, valid responses and `compute_ivr` returns
None so endpoints, the watchlist, and the UI render neutral/empty states.

Implement the new orchestration here.
"""
from __future__ import annotations

from typing import List, Optional

from app.schemas.market import Candle
from app.schemas.instruments import InstrumentMeta
from app.schemas.risk import RiskParams
from app.schemas.directional import TradeState, Direction
from app.schemas.execution import RunOnceResponse, PreviewResponse


async def compute_ivr(
    adapter,
    instrument: InstrumentMeta,
    candles_1h: Optional[List[Candle]] = None,
) -> Optional[float]:
    """No IV-rank without a strategy/options model."""
    return None


async def run_once(
    instrument: InstrumentMeta,
    adapter,
    risk_params: Optional[RiskParams] = None,
    macro_filter: str = "adx_4h",
    mode: str = "swing",
) -> RunOnceResponse:
    """Neutral evaluation: IDLE / NEUTRAL with no ranked structures."""
    underlying = getattr(instrument, "underlying", "") or ""
    return RunOnceResponse(
        underlying=underlying,
        paper_mode=True,
        state=TradeState.IDLE,
        direction=Direction.NEUTRAL,
        recommendation="no strategy loaded",
        reason="strategy removed in reset — implement orchestrator",
        ranked_structures=[],
        no_trade_score=0.0,
    )


async def preview(
    instrument: InstrumentMeta,
    adapter,
    macro_filter: str = "adx_4h",
    mode: Optional[str] = None,
) -> PreviewResponse:
    """Neutral preview: no candidates, no structures."""
    underlying = getattr(instrument, "underlying", "") or ""
    return PreviewResponse(
        underlying=underlying,
        state=TradeState.IDLE,
        direction=Direction.NEUTRAL,
        candidates=[],
        ranked_structures=[],
        reason="strategy removed in reset — implement orchestrator",
    )
