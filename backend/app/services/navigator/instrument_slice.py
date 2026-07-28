"""Indexed option-instrument slice over `InstrumentCache` (spec §10.1).

`InstrumentCache` (`app.services.exchanges.kite.instruments`) only exposes a
linear `search()`/`resolve_token()` over the full ~80k-row dump — this
module adds a lazy secondary index keyed by `(exchange, underlying, expiry)`
so Navigator's chain sampler never re-scans the full dump on every poll. The
index is rebuilt only when the underlying cache's own row list actually
changes (i.e. when its TTL refreshes) — checked via object identity, so a
TTL-fresh cache costs nothing beyond the identity comparison.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Literal, Optional

from app.services.exchanges.kite.instruments import InstrumentCache

OptionType = Literal["CE", "PE"]


@dataclass(frozen=True)
class OptionInstrument:
    tradingsymbol: str
    exchange: str
    strike: float
    option_type: OptionType
    expiry: str  # YYYY-MM-DD, exactly as listed — never derived from a weekday rule
    token: int
    lot_size: int
    tick_size: float


@dataclass(frozen=True)
class OptionInstrumentSlice:
    underlying: str
    exchange: str
    expiry: str
    atm_strike: float
    strike_step: float
    contracts: list[OptionInstrument]  # CE+PE pairs for the selected strike window
    expected_contract_count: int
    found_contract_count: int


def _infer_strike_step(strikes: list[float]) -> float:
    """Modal spacing between adjacent listed strikes — robust to an
    occasional illiquid/missing strike in the dump (a single outlier gap
    doesn't skew a mode the way it would skew a mean)."""
    if len(strikes) < 2:
        return 0.0
    diffs = [round(b - a, 4) for a, b in zip(strikes, strikes[1:]) if b > a]
    if not diffs:
        return 0.0
    return Counter(diffs).most_common(1)[0][0]


class InstrumentSliceIndex:
    """Wraps one `InstrumentCache`, maintaining a lazily-rebuilt secondary
    index: `(exchange, underlying, expiry) -> {strike: {"CE": .., "PE": ..}}`."""

    def __init__(self, cache: InstrumentCache):
        self._cache = cache
        self._index: dict[tuple[str, str, str], dict[float, dict[str, OptionInstrument]]] = {}
        self._indexed_rows_id: dict[str, int] = {}

    async def _ensure_index(self, exchange: str) -> None:
        exchange = exchange.upper()
        rows = await self._cache.load(exchange)
        if self._indexed_rows_id.get(exchange) == id(rows):
            return
        # Rebuild only this exchange's slice of the index — other exchanges'
        # entries (e.g. BFO while refreshing NFO) are left untouched.
        for key in [k for k in self._index if k[0] == exchange]:
            del self._index[key]
        for r in rows:
            itype = str(r.get("instrument_type", "")).upper()
            if itype not in ("CE", "PE"):
                continue
            name = str(r.get("name", "")).upper()
            expiry = str(r.get("expiry") or "")[:10]
            if not name or not expiry:
                continue
            try:
                strike = float(r.get("strike") or 0)
            except (TypeError, ValueError):
                continue
            if strike <= 0:
                continue
            key = (exchange, name, expiry)
            bucket = self._index.setdefault(key, {})
            strike_bucket = bucket.setdefault(strike, {})
            strike_bucket[itype] = OptionInstrument(
                tradingsymbol=str(r.get("tradingsymbol", "")),
                exchange=exchange,
                strike=strike,
                option_type=itype,
                expiry=expiry,
                token=int(r.get("instrument_token") or 0),
                lot_size=int(r.get("lot_size") or 0),
                tick_size=float(r.get("tick_size") or 0.0),
            )
        self._indexed_rows_id[exchange] = id(rows)

    async def listed_expiries(self, exchange: str, underlying: str) -> list[str]:
        await self._ensure_index(exchange)
        name = underlying.upper()
        ex = exchange.upper()
        return sorted({exp for (e, nm, exp) in self._index if e == ex and nm == name})

    async def option_slice(
        self,
        *,
        exchange: str,
        underlying: str,
        expiry: str,
        spot: float,
        strike_radius: int,
        strike_step_override: Optional[float] = None,
    ) -> OptionInstrumentSlice:
        await self._ensure_index(exchange)
        key = (exchange.upper(), underlying.upper(), expiry)
        bucket = self._index.get(key, {})
        strikes = sorted(bucket.keys())
        if not strikes:
            return OptionInstrumentSlice(
                underlying=underlying, exchange=exchange.upper(), expiry=expiry,
                atm_strike=0.0, strike_step=0.0, contracts=[],
                expected_contract_count=0, found_contract_count=0,
            )
        strike_step = strike_step_override if strike_step_override else _infer_strike_step(strikes)
        atm_strike = min(strikes, key=lambda s: abs(s - spot))
        atm_index = strikes.index(atm_strike)
        lo = max(0, atm_index - strike_radius)
        hi = min(len(strikes), atm_index + strike_radius + 1)
        selected_strikes = strikes[lo:hi]

        contracts: list[OptionInstrument] = []
        for s in selected_strikes:
            for side in ("CE", "PE"):
                inst = bucket[s].get(side)
                if inst is not None:
                    contracts.append(inst)

        return OptionInstrumentSlice(
            underlying=underlying, exchange=exchange.upper(), expiry=expiry,
            atm_strike=atm_strike, strike_step=strike_step, contracts=contracts,
            expected_contract_count=len(selected_strikes) * 2, found_contract_count=len(contracts),
        )
