"""Independent CE/PE quote caching, and the three views built over it.

The source bot's observable behaviour comes from this file's central choice:
each leg is cached on its own, and the premium difference is recomputed from
whatever pair happens to be cached when either leg ticks. The recordings show
ticks moving one leg, the other, or both -- so forcing CE and PE into a single
synchronised snapshot would quietly replace the strategy with a different one.

``SYNCHRONIZED`` and ``EXECUTABLE`` exist so we can *measure* whether that
asynchrony is load-bearing, without ever changing what ``COMPATIBILITY``
produces.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional

from .models import (
    LegQuote,
    OptionPairRef,
    OptionType,
    PremiumPairView,
    QuoteMode,
)

#: Per-leg history depth for SYNCHRONIZED alignment. Small on purpose: this is a
#: timestamp-matching window, not a bar store.
_HISTORY = 64


class PremiumQuoteCache:
    """Latest-known CE and PE state for one option pair.

    Not thread-safe by design: it is driven from a single feed callback, and
    adding a lock would hide a wiring mistake rather than fix one.
    """

    def __init__(self, pair: OptionPairRef, *, history: int = _HISTORY) -> None:
        self._pair = pair
        self._ce: Optional[LegQuote] = None
        self._pe: Optional[LegQuote] = None
        self._underlying_ltp: Optional[float] = None
        self._underlying_ts_ms: int = 0
        self._ce_hist: Deque[LegQuote] = deque(maxlen=history)
        self._pe_hist: Deque[LegQuote] = deque(maxlen=history)
        self._ce_updates = 0
        self._pe_updates = 0
        self._first_option_tick: Optional[tuple[OptionType, LegQuote]] = None
        self._first_by_leg: dict[str, LegQuote] = {}

    # ------------------------------------------------------------------ ingest

    @property
    def pair(self) -> OptionPairRef:
        return self._pair

    def on_option_tick(self, quote: LegQuote) -> Optional[OptionType]:
        """Apply one option tick. Returns which leg moved, or ``None`` if foreign.

        Out-of-order ticks are dropped rather than applied: a feed that replays
        an older sequence must not walk the cache backwards.
        """
        if quote.instrument_id == self._pair.ce.instrument_id:
            leg: OptionType = "CE"
            current = self._ce
        elif quote.instrument_id == self._pair.pe.instrument_id:
            leg = "PE"
            current = self._pe
        else:
            return None

        if current is not None and quote.sequence and current.sequence:
            if quote.sequence < current.sequence:
                return None

        if leg == "CE":
            self._ce = quote
            self._ce_hist.append(quote)
            self._ce_updates += 1
        else:
            self._pe = quote
            self._pe_hist.append(quote)
            self._pe_updates += 1

        if self._first_option_tick is None:
            self._first_option_tick = (leg, quote)
        self._first_by_leg.setdefault(leg, quote)
        return leg

    def on_underlying_tick(self, ltp: float, ts_ms: int = 0) -> None:
        self._underlying_ltp = float(ltp)
        self._underlying_ts_ms = int(ts_ms)

    # ------------------------------------------------------------------- state

    @property
    def ce(self) -> Optional[LegQuote]:
        return self._ce

    @property
    def pe(self) -> Optional[LegQuote]:
        return self._pe

    @property
    def underlying_ltp(self) -> Optional[float]:
        return self._underlying_ltp

    @property
    def update_counts(self) -> tuple[int, int]:
        """``(ce_updates, pe_updates)`` -- asserted on by the async-cache tests."""
        return self._ce_updates, self._pe_updates

    @property
    def first_option_tick(self) -> Optional[tuple[OptionType, LegQuote]]:
        """The first option tick ever seen, whichever leg it belonged to.

        Recorded because the rejected ``FIRST_TICK_PLUS_BUFFER`` policy needs it
        for replay, and because the forensic report compares it against the fill.
        """
        return self._first_option_tick

    def first_price_for(self, option_type: OptionType) -> Optional[float]:
        """The first price ever seen for one leg.

        This -- not the first tick of *either* leg -- is what the source bot
        prices its entry from. Its ``STRIKE SELECTED`` block prints the selected
        leg's price as ``Premium`` and the entry block repeats it as
        ``First Tick Price``: 102.85 for the CE it chose on 2026-08-20, 379.0 for
        the PE it chose on 2026-08-21.
        """
        q = self._first_by_leg.get(option_type)
        return None if q is None else float(q.ltp)

    def both_legs_present(self) -> bool:
        return self._ce is not None and self._pe is not None

    # ------------------------------------------------------------------- views

    def view(self, mode: QuoteMode, now_ms: int, *, max_skew_ms: int = 1000) -> Optional[PremiumPairView]:
        """Build the requested view, or ``None`` if it cannot be built.

        ``None`` is a real answer -- 'no executable pair right now' -- and the
        caller must treat it as no-signal rather than substituting another mode.
        """
        if mode == "COMPATIBILITY":
            return self._compatibility_view(now_ms)
        if mode == "SYNCHRONIZED":
            return self._synchronized_view(now_ms, max_skew_ms)
        if mode == "EXECUTABLE":
            return self._executable_view(now_ms)
        raise ValueError(f"unknown quote mode: {mode}")

    def _compatibility_view(self, now_ms: int) -> Optional[PremiumPairView]:
        ce, pe = self._ce, self._pe
        if ce is None or pe is None:
            return None
        return PremiumPairView(
            mode="COMPATIBILITY",
            ce_price=float(ce.ltp),
            pe_price=float(pe.ltp),
            ce_ts_ms=ce.exchange_ts_ms,
            pe_ts_ms=pe.exchange_ts_ms,
            ce_age_ms=ce.age_ms(now_ms),
            pe_age_ms=pe.age_ms(now_ms),
            ce_sequence=ce.sequence,
            pe_sequence=pe.sequence,
        )

    def _synchronized_view(self, now_ms: int, max_skew_ms: int) -> Optional[PremiumPairView]:
        """Best timestamp-aligned CE/PE pair within ``max_skew_ms``.

        Chooses the closest-in-exchange-time pair, then breaks ties toward the
        most recent, so the view is deterministic for a given history.
        """
        if not self._ce_hist or not self._pe_hist:
            return None
        best: Optional[tuple[int, int, LegQuote, LegQuote]] = None
        for c in self._ce_hist:
            for p in self._pe_hist:
                skew = abs(int(c.exchange_ts_ms) - int(p.exchange_ts_ms))
                if skew > max_skew_ms:
                    continue
                recency = min(int(c.exchange_ts_ms), int(p.exchange_ts_ms))
                key = (skew, -recency)
                if best is None or key < (best[0], -best[1]):
                    best = (skew, recency, c, p)
        if best is None:
            return None
        _, _, ce, pe = best
        return PremiumPairView(
            mode="SYNCHRONIZED",
            ce_price=float(ce.ltp),
            pe_price=float(pe.ltp),
            ce_ts_ms=ce.exchange_ts_ms,
            pe_ts_ms=pe.exchange_ts_ms,
            ce_age_ms=ce.age_ms(now_ms),
            pe_age_ms=pe.age_ms(now_ms),
            ce_sequence=ce.sequence,
            pe_sequence=pe.sequence,
        )

    def _executable_view(self, now_ms: int) -> Optional[PremiumPairView]:
        """Compare what could actually be *bought*: the two asks.

        If either leg has no ask, there is no executable comparison. Falling back
        to LTP here would silently turn production into COMPATIBILITY mode.
        """
        ce, pe = self._ce, self._pe
        if ce is None or pe is None:
            return None
        ce_ask = ce.executable_buy_price()
        pe_ask = pe.executable_buy_price()
        if ce_ask is None or pe_ask is None:
            return None
        return PremiumPairView(
            mode="EXECUTABLE",
            ce_price=ce_ask,
            pe_price=pe_ask,
            ce_ts_ms=ce.exchange_ts_ms,
            pe_ts_ms=pe.exchange_ts_ms,
            ce_age_ms=ce.age_ms(now_ms),
            pe_age_ms=pe.age_ms(now_ms),
            ce_sequence=ce.sequence,
            pe_sequence=pe.sequence,
        )

    def all_views(self, now_ms: int, *, max_skew_ms: int = 1000) -> dict[str, Optional[PremiumPairView]]:
        """All three views at once, for the forensic alignment report."""
        return {
            "COMPATIBILITY": self._compatibility_view(now_ms),
            "SYNCHRONIZED": self._synchronized_view(now_ms, max_skew_ms),
            "EXECUTABLE": self._executable_view(now_ms),
        }
