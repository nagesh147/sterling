"""Build the production Kite scan universe from listed instruments.

Indices come from ``universe.json``. Equity option underlyings are restricted to the
curated Very High/High liquidity registry so arbitrary or thin F&O names cannot be
included through either explicit selection or the legacy ``all_stocks`` flag.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.services.kite_engine.stock_registry import (
    CURATED_STOCK_NAMES,
    HIGH_LIQUIDITY_STOCK_NAMES,
    LIQUIDITY_ORDER,
    STOCKS_BY_LIQUIDITY,
)

_CFG_PATH = Path(__file__).with_name("universe.json")
CURATED_STOCKS = tuple(CURATED_STOCK_NAMES)
_HIGH_LIQUIDITY = frozenset(HIGH_LIQUIDITY_STOCK_NAMES)


@dataclass(frozen=True)
class UniverseItem:
    name: str
    tradingsymbol: str
    token: int
    exchange: str
    option_exchange: str
    is_index: bool = False


def load_cfg() -> dict:
    return json.loads(_CFG_PATH.read_text())


def build_universe(
    *,
    nfo_instruments: Sequence[dict],
    bfo_instruments: Sequence[dict],
    equities: Sequence[dict],
    cfg: Optional[dict] = None,
) -> List[UniverseItem]:
    cfg = cfg if cfg is not None else load_cfg()
    by_symbol: Dict[str, dict] = {}
    for equity in equities:
        symbol = str(equity.get("tradingsymbol", ""))
        if symbol and symbol not in by_symbol:
            by_symbol[symbol] = equity

    output: List[UniverseItem] = []
    for index in cfg.get("indices", []):
        spot = by_symbol.get(index["spot_symbol"], {})
        token = int(index.get("spot_token", 0) or 0) or int(spot.get("instrument_token", 0) or 0)
        output.append(UniverseItem(
            name=index["name"],
            tradingsymbol=index["option_name"],
            token=token,
            exchange="INDICES",
            option_exchange=index["option_exchange"],
            is_index=True,
        ))

    if cfg.get("include_fno_equities", True):
        seen: set[str] = set()
        for instruments, option_exchange in ((nfo_instruments, "NFO"), (bfo_instruments, "BFO")):
            for instrument in instruments:
                name = str(instrument.get("name") or "")
                if not name or name in seen or name not in _HIGH_LIQUIDITY:
                    continue
                if instrument.get("instrument_type") not in ("CE", "PE"):
                    continue
                equity = by_symbol.get(name)
                if not equity:
                    continue
                seen.add(name)
                output.append(UniverseItem(
                    name=name,
                    tradingsymbol=name,
                    token=int(equity.get("instrument_token", 0) or 0),
                    exchange=str(equity.get("exchange", "NSE")),
                    option_exchange=option_exchange,
                ))
    return output


def select_scan_universe(
    universe: List[UniverseItem], *,
    indices: Sequence[str], stocks: Sequence[str], all_stocks: bool,
) -> List[UniverseItem]:
    """Filter selections while enforcing the high-liquidity stock boundary.

    ``all_stocks`` means all eligible high-liquidity stocks, never all listed F&O.
    Explicit arbitrary stock names are ignored.
    """
    selected_indices = set(indices)
    selected_stocks = set(stocks) & _HIGH_LIQUIDITY
    output: List[UniverseItem] = []
    for item in universe:
        if item.is_index:
            if item.name in selected_indices:
                output.append(item)
        elif item.name in _HIGH_LIQUIDITY and (all_stocks or item.name in selected_stocks):
            output.append(item)
    return output
