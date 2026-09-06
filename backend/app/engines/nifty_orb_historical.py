"""Fail-closed historical option walk-forward for ORB.

A corpus must already contain option bars *and* labeled signals. This module
will not invent option trades from underlying points, and it will not report
edge from an empty or incomplete file.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.engines.nifty_orb_option_replay import (
    OptionBar,
    ReplayAdmission,
    ReplayCostConfig,
    ReplayRejection,
    ReplayTrade,
    replay_signal,
    summarize_replay,
)
from app.engines.nifty_orb_validation import require_historical_option_fields, walk_forward


def _bar(row: dict[str, Any]) -> OptionBar:
    ts = row["timestamp"]
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return OptionBar(
        timestamp=dt,
        symbol=str(row["symbol"]),
        option_type=str(row["option_type"]),
        strike=float(row["strike"]),
        expiry=str(row["expiry"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        bid=float(row.get("bid") or 0),
        ask=float(row.get("ask") or 0),
        volume=float(row.get("volume") or 0),
        open_interest=float(row.get("open_interest") or 0),
        lot_size=int(row["lot_size"]),
    )


def evaluate_historical_corpus(
    payload: dict[str, Any],
    *,
    train_size: int = 4,
    test_size: int = 2,
    step: int | None = None,
) -> dict[str, Any]:
    """Replay labeled option signals across walk-forward folds.

    ``payload.bars`` must satisfy ``require_historical_option_fields``.
    ``payload.signals`` must be a non-empty list of
    ``{entry_index, risk_points, target_r, lots?}``. Missing signals is a
    refusal, not a cue to synthesise trades.
    """
    bars_raw = payload.get("bars")
    if not isinstance(bars_raw, list):
        raise ValueError("corpus.bars must be a list of option OHLC rows")
    require_historical_option_fields(bars_raw)
    signals = payload.get("signals")
    if not isinstance(signals, list) or not signals:
        raise ValueError(
            "corpus has option bars but no labeled signals; refusing to invent option trades"
        )
    bars = [_bar(row) for row in bars_raw]
    costs = ReplayCostConfig()
    admission = ReplayAdmission()

    def evaluator(train: list, test: list) -> dict[str, Any]:
        trades: list[ReplayTrade] = []
        rejections: list[dict[str, Any]] = []
        for item in test:
            outcome = replay_signal(
                bars,
                int(item["entry_index"]),
                float(item["risk_points"]),
                float(item.get("target_r") or 2),
                costs,
                lots=int(item.get("lots") or 1),
                admission=admission,
            )
            if isinstance(outcome, ReplayRejection):
                rejections.append({"entry_index": outcome.signal_index, "reason": outcome.reason})
            else:
                trades.append(outcome)
        return {
            "metrics": summarize_replay(trades),
            "rejections": rejections,
            "train_signals": len(train),
            "test_signals": len(test),
            "option_pnl": True,
        }

    folds = walk_forward(signals, evaluator, train_size=train_size, test_size=test_size, step=step)
    oos_trades = sum(int(f["metrics"]["trades"]) for f in folds)
    oos_net = sum(float(f["metrics"]["net_pnl"]) for f in folds)
    return {
        "folds": folds,
        "fold_count": len(folds),
        "oos_trades": oos_trades,
        "oos_net_pnl": oos_net,
        "option_pnl": True,
        "unattended_live_eligible": False,
        "note": "Walk-forward of labeled option signals. Not evidence of edge until a real multi-month corpus is green out of sample.",
    }
