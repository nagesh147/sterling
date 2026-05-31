"""Strategy catalog — plain-English descriptors + live performance.

The candidate tables show terse strategy ids ("ma_crossover", "smc", …) with no
explanation of what they actually do, on what timeframe, long or short, or which
engine produced them. Worse, the SAME id means different things in different
engines (the edge feed's `ma_crossover` is EMA9/21 long-only on 4H; the scalping
scanner's was a near-level bidirectional thing). This module is the single place
that explains each strategy in plain language and joins it to the live, validated
combos from the robustness-gated registry so a user can see exactly what is
running and how it has performed.

Pure data + a join function. No I/O — the endpoint passes in the loaded registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class StrategyDescriptor:
    id: str
    name: str               # human display name
    tagline: str            # one line: what it does
    how_it_works: str       # plain-English of the ACTUAL signal logic
    direction: str          # "Long only" | "Long & Short"
    engine: str             # which engine emits it
    instrument: str         # how it routes to futures/options
    note: str = ""          # disambiguation / caveats


# The descriptors mirror app/engines/edge/strategies.py EXACTLY (the validated,
# long-only functions the edge feed trades). Keep them in sync with that file.
DESCRIPTORS: dict[str, StrategyDescriptor] = {
    "ma_crossover": StrategyDescriptor(
        id="ma_crossover",
        name="EMA Crossover (Trend)",
        tagline="Buys the moment a fast trend line crosses above a slow one.",
        how_it_works=(
            "On each bar it computes a fast EMA(9) and a slow EMA(21) of the close. "
            "It fires a LONG the instant EMA9 crosses from below to above EMA21 — a "
            "fresh trend-onset signal. It does NOT fire while they stay crossed; only "
            "on the flip. Exit is a fixed ATR bracket (stop = 2.0×ATR below entry, "
            "target = 3.5×ATR above ⇒ ~1.75 reward:risk)."
        ),
        direction="Long only",
        engine="Edge feed (backtest-validated). The live scalping scanner now "
               "delegates to this exact EMA9/21 logic too, so both paths agree.",
        instrument="The derivatives selector routes each signal to a future or an "
                   "option (Greeks-aware), so it can appear in either candidate table.",
        note="This is NOT the old 'SMA(5)/EMA(9) near a 4H level, both directions' "
             "strategy that shared the name — that was a separate, BTC-losing "
             "implementation, replaced 2026-05-31.",
    ),
    "mean_reversion": StrategyDescriptor(
        id="mean_reversion",
        name="RSI Mean Reversion",
        tagline="Buys oversold bounces as momentum turns back up.",
        how_it_works=(
            "Computes RSI(14) on the close. Fires a LONG when RSI crosses up through "
            "30 — i.e. the bar that exits 'oversold'. The idea is to catch the bounce "
            "after a flush, not to short strength. Exit is the profile's ATR bracket."
        ),
        direction="Long only",
        engine="Edge feed (backtest-validated).",
        instrument="Routed to a future or option by the selector.",
        note="Different from the SCALPING-scanner 'mean_reversion', which is a "
             "z-score overbought/oversold FADE near 4H levels and trades BOTH "
             "directions — that intraday version is the engine's strongest performer.",
    ),
    "breakout": StrategyDescriptor(
        id="breakout",
        name="Channel Breakout",
        tagline="Buys a fresh break above the recent high.",
        how_it_works=(
            "Tracks the rolling 20-bar high. Fires a LONG the first bar the close "
            "pushes above that high (a breakout). Long-only, ATR bracket exit."
        ),
        direction="Long only",
        engine="Edge feed (backtest-validated).",
        instrument="Routed to a future or option by the selector.",
        note="THIS edge-feed breakout (4h channel, long-only) works and is live. "
             "The separate SCALPING-scanner breakout is DISABLED: both its original "
             "chase entry (44/44 stop-outs) and a rebuilt retest entry (4-7% win, "
             "-90%) were validated as losers — breakout doesn't work in the intraday "
             "near-level framework, only as this 4h channel version.",
    ),
    "price_action": StrategyDescriptor(
        id="price_action",
        name="Bullish Engulfing",
        tagline="Buys a bullish engulfing candle after a down bar.",
        how_it_works=(
            "Fires a LONG when the current bar is bullish (close > open) AND it "
            "engulfs the prior bearish bar — it opens below the prior close and "
            "closes above the prior open. A classic reversal candle. ATR bracket exit."
        ),
        direction="Long only",
        engine="Edge feed (backtest-validated).",
        instrument="Routed to a future or option by the selector.",
        note="The SCALPING-scanner 'price_action' is a different double-bottom / "
             "neckline-break pattern near 4H levels.",
    ),
    "smc": StrategyDescriptor(
        id="smc",
        name="Smart-Money FVG",
        tagline="Buys a bullish fair-value-gap imbalance.",
        how_it_works=(
            "Detects a bullish Fair Value Gap: the current bar's LOW sits above the "
            "HIGH of two bars back, leaving an unfilled price gap (an institutional "
            "imbalance), confirmed by a bullish close. Fires LONG. ATR bracket exit."
        ),
        direction="Long only",
        engine="Edge feed (backtest-validated).",
        instrument="Routed to a future or option by the selector.",
        note="The SCALPING-scanner 'smc' is a liquidity-sweep + order-block variant "
             "near 4H levels.",
    ),
}

# Profile → the ATR SL/TP bracket each one applies (so the user sees the actual risk shape).
PROFILE_BRACKET = {
    "Scalping": "tight (SL 1.0×ATR / TP 2.0×ATR)",
    "Intraday": "balanced (SL 2.0×ATR / TP 3.5×ATR)",
    "Aggressive": "let-it-run (SL 1.5×ATR / TP 4.5×ATR)",
}


def _pct(x: float) -> float:
    return round(x * 100.0, 1)


def build_catalog(registry) -> List[dict]:
    """Merge the static descriptors with the live, validated combos from the
    robustness-gated registry. Returns one entry per strategy, each carrying the
    explanation plus the exact (symbol, tf, profile) configs that are live and
    how each has performed (OOS Sharpe, Monte-Carlo P(loss), return, drawdown)."""
    by_strategy: dict[str, list] = {}
    for combo in registry.all():
        by_strategy.setdefault(combo.strategy, []).append(combo)

    out: List[dict] = []
    for sid, d in DESCRIPTORS.items():
        combos = sorted(by_strategy.get(sid, []), key=lambda c: -c.signal_score)
        out.append({
            "id": d.id,
            "name": d.name,
            "tagline": d.tagline,
            "how_it_works": d.how_it_works,
            "direction": d.direction,
            "engine": d.engine,
            "instrument": d.instrument,
            "note": d.note,
            "live": len(combos) > 0,
            "live_combo_count": len(combos),
            "combos": [{
                "symbol": c.symbol.replace("USD", ""),
                "tf": c.tf,
                "profile": c.profile,
                "bracket": PROFILE_BRACKET.get(c.profile, ""),
                "trades": c.trades,
                "win_rate_pct": _pct(c.win_rate),
                "net_return_pct": _pct(c.net_return),
                "sharpe": round(c.sharpe, 2),
                "oos_sharpe": (None if c.oos_sharpe == float("inf") else round(c.oos_sharpe, 2)),
                "p_loss_pct": _pct(c.p_loss),
                "max_dd_pct": _pct(c.max_dd),
                "signal_score": round(c.signal_score, 0),
            } for c in combos],
        })
    # Strategies with live combos first, then by best conviction.
    out.sort(key=lambda e: (not e["live"],
                            -max([c["signal_score"] for c in e["combos"]], default=0)))
    return out
