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

_CFG_PATH = Path(__file__).with_name("universe.json")


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
    by_symbol: Dict[str, dict] = {
        str(e.get("tradingsymbol", "")): e for e in equities if e.get("tradingsymbol")
    }
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
