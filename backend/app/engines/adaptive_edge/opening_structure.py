"""Opening structure: session open, prior close, initial balance.

IB length is a research convention (15 minutes from first bar), not F-110.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


IB_MINUTES = 15


@dataclass
class OpeningStructureBuilder:
    session_open: float | None = None
    prior_close: float | None = None
    first_bar_time: datetime | None = None
    ib_high: float | None = None
    ib_low: float | None = None
    ib_complete: bool = False

    def start_day(self, *, prior_close: float | None) -> None:
        self.session_open = None
        self.prior_close = prior_close
        self.first_bar_time = None
        self.ib_high = None
        self.ib_low = None
        self.ib_complete = False

    def add_bar(self, *, available_at: datetime, open_px: float, high: float, low: float) -> None:
        if self.session_open is None:
            self.session_open = open_px
            self.first_bar_time = available_at
        if self.first_bar_time is None:
            return
        if available_at <= self.first_bar_time + timedelta(minutes=IB_MINUTES):
            self.ib_high = high if self.ib_high is None else max(self.ib_high, high)
            self.ib_low = low if self.ib_low is None else min(self.ib_low, low)
        else:
            self.ib_complete = self.ib_high is not None and self.ib_low is not None

    @property
    def gap(self) -> float | None:
        if self.session_open is None or self.prior_close is None:
            return None
        return self.session_open - self.prior_close


def or_location(price: float, ib_high: float | None, ib_low: float | None, *, complete: bool) -> str:
    if not complete or ib_high is None or ib_low is None:
        return "ib_forming"
    if price > ib_high:
        return "above_or"
    if price < ib_low:
        return "below_or"
    return "inside_or"
