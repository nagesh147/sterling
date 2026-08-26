"""TrueData Historical Corpus Ingestion and Observational Replay Engine.

Preserves raw TrueData provider payloads alongside canonicalized representations
and computes observational telemetry baselines without parameter overfitting:
- Raw & Canonical Data Hashing
- Multi-regime Observational Telemetry (Signals, Trades, Horizon, MAE, MFE, PnL, TraceHash)
- Deterministic Replay Invariant
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from app.engines.adaptive_edge.e2e import ReplayContext
from app.engines.adaptive_edge.event_boundary import CanonicalMarketEvent
from app.engines.adaptive_edge.opportunity_mode import OpportunityMode
from app.engines.adaptive_edge.strategy_pipeline import (
    StrategyConfig,
    StrategyExecutionResult,
    run_strategy_semantics_pipeline,
)
from app.services.providers.truedata.adapter import TrueDataMarketDataAdapter


@dataclass(frozen=True)
class CorpusSessionMetadata:
    session_date: str
    instrument: str
    timeframe: str
    provider_source: str
    regime_label: str
    session_start: str
    session_end: str
    bar_count: int
    raw_data_hash: str
    canonical_data_hash: str


@dataclass(frozen=True)
class CorpusSession:
    metadata: CorpusSessionMetadata
    raw_bars: tuple[dict[str, Any], ...]
    raw_ticks: tuple[dict[str, Any], ...]
    canonical_events: tuple[CanonicalMarketEvent, ...]


@dataclass(frozen=True)
class ObservationalTelemetry:
    session_date: str
    instrument: str
    regime_label: str
    bar_count: int
    signals_detected: int
    traded: bool
    trade_direction: str | None
    horizon: OpportunityMode | None
    selected_instrument: str | None
    authorized_risk: float
    authorized_quantity: int
    entry_fill_price: float | None
    exit_fill_price: float | None
    exit_reason: str | None
    gross_pnl: float
    net_pnl: float
    mae_points: float
    mfe_points: float
    trace_hash: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.horizon is not None:
            d["horizon"] = self.horizon.value
        return d


def load_corpus_session(filepath: str | Path) -> CorpusSession:
    """Load a versioned TrueData historical session from JSON."""
    path = Path(filepath)
    raw_bytes = path.read_bytes()
    raw_hash = hashlib.sha256(raw_bytes).hexdigest()

    data = json.loads(raw_bytes.decode("utf-8"))
    meta_dict = data.get("metadata", {})
    raw_bars = tuple(data.get("raw_bars", []))
    raw_ticks = tuple(data.get("raw_ticks", []))

    symbol = meta_dict.get("instrument", "NIFTY-I")

    # Canonicalize bars and ticks using TrueDataMarketDataAdapter
    canonical_list: list[CanonicalMarketEvent] = []
    for i, bar in enumerate(raw_bars):
        canonical_list.append(
            TrueDataMarketDataAdapter.create_bar_event(symbol, bar, sequence=i)
        )
    for j, tick in enumerate(raw_ticks):
        canonical_list.append(
            TrueDataMarketDataAdapter.create_tick_event(symbol, tick, sequence=j)
        )

    # Compute canonical hash
    hasher = hashlib.sha256()
    for ev in canonical_list:
        hasher.update(f"{ev.record_id}|{ev.event_time}|{ev.event_type}\n".encode("utf-8"))
    canonical_hash = hasher.hexdigest()

    metadata = CorpusSessionMetadata(
        session_date=str(meta_dict.get("session_date", "")),
        instrument=symbol,
        timeframe=str(meta_dict.get("timeframe", "1min")),
        provider_source=str(meta_dict.get("provider_source", "truedata")),
        regime_label=str(meta_dict.get("regime_label", "unknown")),
        session_start=str(meta_dict.get("session_start", "")),
        session_end=str(meta_dict.get("session_end", "")),
        bar_count=len(raw_bars),
        raw_data_hash=raw_hash,
        canonical_data_hash=canonical_hash,
    )

    return CorpusSession(
        metadata=metadata,
        raw_bars=raw_bars,
        raw_ticks=raw_ticks,
        canonical_events=tuple(canonical_list),
    )


def list_corpus_sessions(corpus_dir: str | Path) -> list[CorpusSession]:
    """List and load all corpus sessions in the given directory sorted by date."""
    p = Path(corpus_dir)
    sessions: list[CorpusSession] = []
    for file in sorted(p.glob("*.json")):
        sessions.append(load_corpus_session(file))
    return sessions


def evaluate_corpus_session(
    session: CorpusSession,
    *,
    config: StrategyConfig | None = None,
    replay_context: ReplayContext | None = None,
) -> ObservationalTelemetry:
    """Execute strategy pipeline on historical corpus session and record observational baseline."""
    effective_config = config or StrategyConfig(symbol=session.metadata.instrument)
    effective_replay = replay_context or ReplayContext(
        decision_time=session.metadata.session_start,
        event_time=session.metadata.session_start,
        deterministic_id_namespace=f"corpus-{session.metadata.session_date}",
        sequence_seed=100,
    )

    bar_events = [ev for ev in session.canonical_events if ev.event_type == "bar"]
    tick_events = [ev for ev in session.canonical_events if ev.event_type == "tick"]

    result: StrategyExecutionResult = run_strategy_semantics_pipeline(
        bar_events=bar_events,
        tick_events=tick_events,
        config=effective_config,
        replay_context=effective_replay,
    )

    # Compute MAE and MFE across the traded sequence
    mae = 0.0
    mfe = 0.0
    entry_fill = None
    exit_fill = None

    if result.traded and result.initial_position is not None:
        entry_fill = result.initial_position.average_price
        exit_fill = (
            result.final_position.average_price
            if result.final_position is not None
            else None
        )
        is_call = "CE" in (result.selected_instrument or "")
        multiplier = 1.0 if is_call else -1.0

        for bar in bar_events:
            close_px = float(bar.payload.get("close", entry_fill))
            high_px = float(bar.payload.get("high", close_px))
            low_px = float(bar.payload.get("low", close_px))

            fav_spot = high_px if is_call else low_px
            adv_spot = low_px if is_call else high_px

            fav_move = (fav_spot - entry_fill) * multiplier
            adv_move = (entry_fill - adv_spot) * multiplier

            if fav_move > mfe:
                mfe = fav_move
            if adv_move > mae:
                mae = adv_move

    trade_direction = result.market_decision.direction if result.market_decision else None
    horizon = result.market_decision.horizon if result.market_decision else None
    qty = result.sizing_assessment.final_quantity if result.sizing_assessment else 0

    return ObservationalTelemetry(
        session_date=session.metadata.session_date,
        instrument=session.metadata.instrument,
        regime_label=session.metadata.regime_label,
        bar_count=session.metadata.bar_count,
        signals_detected=1 if result.market_decision is not None else 0,
        traded=result.traded,
        trade_direction=trade_direction,
        horizon=horizon,
        selected_instrument=result.selected_instrument,
        authorized_risk=effective_config.authorized_risk,
        authorized_quantity=qty,
        entry_fill_price=entry_fill,
        exit_fill_price=exit_fill,
        exit_reason=result.exit_reason,
        gross_pnl=result.realized_pnl + (effective_config.execution_cost if result.traded else 0.0),
        net_pnl=result.realized_pnl,
        mae_points=round(mae, 2),
        mfe_points=round(mfe, 2),
        trace_hash=result.trace_hash,
    )
