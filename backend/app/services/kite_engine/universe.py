"""Build the Kite scan universe from the instruments dump.

The universe is every underlying with listed options (NFO + BFO equity options)
plus the four index underlyings (NIFTY / BANKNIFTY / FINNIFTY / SENSEX), backed
by an editable ``universe.json``. No hardcoded constituent lists — membership is
derived from what actually has options, so it tracks F&O eligibility.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.services.kite_engine.stock_registry import CURATED_STOCK_NAMES, LIQUIDITY_ORDER, STOCKS_BY_LIQUIDITY

_CFG_PATH = Path(__file__).with_name("universe.json")

# High-liquidity F&O stocks for the "indices + liquid stocks" derivatives bucket.
# Names match the option-chain `name` / equity tradingsymbol. Edit freely.
CURATED_STOCKS = tuple(CURATED_STOCK_NAMES)


@dataclass(frozen=True)
class UniverseItem:
    name: str            # display name ("RELIANCE", "NIFTY 50")
    tradingsymbol: str   # option-chain underlying filter ("RELIANCE", "NIFTY")
    token: int           # spot/index instrument_token for 1H candle fetch
    exchange: str        # spot exchange ("NSE" / "BSE" / "INDICES")
    option_exchange: str  # "NFO" / "BFO"
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
    # Build the spot lookup so the FIRST listing wins on a tradingsymbol collision.
    # Callers pass equities as NSE + BSE, so an F&O name that lists on both venues
    # (RELIANCE, TCS, …) keeps its NSE spot token — NSE is where the options trade
    # and where 1H history is deepest; a BSE token would chart a thinner series.
    by_symbol: Dict[str, dict] = {}
    for e in equities:
        ts = str(e.get("tradingsymbol", ""))
        if ts and ts not in by_symbol:
            by_symbol[ts] = e
    out: List[UniverseItem] = []

    # Indices first. Prefer the well-known stable spot_token from config; fall
    # back to resolving the spot_symbol from the dump. This guarantees indices
    # always carry a candle-fetch token (they were being dropped for token==0).
    for ix in cfg.get("indices", []):
        spot = by_symbol.get(ix["spot_symbol"], {})
        token = int(ix.get("spot_token", 0) or 0) or int(spot.get("instrument_token", 0) or 0)
        out.append(UniverseItem(
            name=ix["name"],
            tradingsymbol=ix["option_name"],
            token=token,
            exchange="INDICES",
            option_exchange=ix["option_exchange"],
            is_index=True,
        ))

    if cfg.get("include_fno_equities", True):
        seen = set()
        for rows, opt_exch in ((nfo_instruments, "NFO"), (bfo_instruments, "BFO")):
            for row in rows:
                name = row.get("name")
                if not name or name in seen:
                    continue
                if row.get("instrument_type") not in ("CE", "PE"):
                    continue
                eq = by_symbol.get(name)
                if not eq:
                    continue  # no spot listing → can't fetch candles → skip
                seen.add(name)
                out.append(UniverseItem(
                    name=name,
                    tradingsymbol=name,
                    token=int(eq.get("instrument_token", 0) or 0),
                    exchange=str(eq.get("exchange", "NSE")),
                    option_exchange=opt_exch,
                ))
    return out


def select_scan_universe(
    universe: List[UniverseItem], *,
    indices: Sequence[str], stocks: Sequence[str], all_stocks: bool,
) -> List[UniverseItem]:
    """Filter the universe to the user's granular selection, preserving order.

    An index is kept iff its display name is in ``indices``. A stock is kept iff
    ``all_stocks`` is set OR its name is in ``stocks``. Applied to BOTH the spot and
    the derivatives scan, so the user controls exactly what each scan covers.
    """
    idx = set(indices)
    stk = set(stocks)
    out: List[UniverseItem] = []
    for u in universe:
        if u.is_index:
            if u.name in idx:
                out.append(u)
        elif all_stocks or u.name in stk:
            out.append(u)
    return out
