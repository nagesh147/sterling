"""TBT order-flow research classifier.

TrueData ticks have ltp/volume/bid/ask/bidqty/askqty and no aggressor flag.
This is NOT canonical DeltaVelocity (C-DV). Classifier label is explicit.
"""
from __future__ import annotations

from dataclasses import dataclass

from .feature_engine import FeatureStatus
from .liquidity_imbalance import compute_liquidity_imbalance

CLASSIFIER = "RESEARCH_TBT_QUOTE_THEN_TICK"
NOT_CANONICAL_DV = True


def classify_print(
    *,
    ltp: float,
    bid: float | None,
    ask: float | None,
    prev_ltp: float | None,
    last_side: str | None,
) -> str | None:
    """Quote rule first; tick rule if the print is inside the spread."""
    if bid is not None and ask is not None and ask >= bid:
        if ltp >= ask:
            return "BUY"
        if ltp <= bid:
            return "SELL"
    if prev_ltp is not None:
        if ltp > prev_ltp:
            return "BUY"
        if ltp < prev_ltp:
            return "SELL"
        return last_side
    return None


@dataclass
class OrderFlowBuilder:
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    unclassified_volume: float = 0.0
    cvd: float = 0.0
    bar_buy: float = 0.0
    bar_sell: float = 0.0
    prev_ltp: float | None = None
    last_side: str | None = None
    last_li: float | None = None
    last_spread: float | None = None

    def add_tick(
        self,
        *,
        ltp: float,
        volume: float,
        bid: float | None,
        ask: float | None,
        bidqty: float | None,
        askqty: float | None,
    ) -> None:
        size = max(0.0, float(volume))
        side = classify_print(
            ltp=ltp,
            bid=bid,
            ask=ask,
            prev_ltp=self.prev_ltp,
            last_side=self.last_side,
        )
        if side == "BUY":
            self.buy_volume += size
            self.bar_buy += size
            self.cvd += size
        elif side == "SELL":
            self.sell_volume += size
            self.bar_sell += size
            self.cvd -= size
        else:
            self.unclassified_volume += size
        if side is not None:
            self.last_side = side
        self.prev_ltp = ltp
        li, status = compute_liquidity_imbalance(bidqty, askqty)
        if status is FeatureStatus.VALID:
            self.last_li = li
        if bid is not None and ask is not None and ask >= bid:
            self.last_spread = ask - bid

    def roll_bar(self) -> tuple[float, float, float]:
        delta = self.bar_buy - self.bar_sell
        buy, sell = self.bar_buy, self.bar_sell
        self.bar_buy = 0.0
        self.bar_sell = 0.0
        return delta, buy, sell
