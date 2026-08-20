"""Normalize broker option-chain quotes for ORB option buying."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any, Awaitable, Callable, Sequence
from app.engines.nifty_orb_options import OptionContract, StrategyConfig

@dataclass(frozen=True)
class ChainQuote:
    symbol: str; strike: float; expiry: str; option_type: str; ltp: float; bid: float; ask: float; lot_size: int; volume: float; open_interest: float; delta: float | None = None
    def to_contract(self) -> OptionContract:
        return OptionContract(self.symbol, self.strike, self.expiry, self.option_type, self.ltp, self.bid, self.ask, self.lot_size, self.delta, self.volume, self.open_interest)

def normalize_chain(rows: Sequence[dict[str, Any]] | dict[str, Any], *, default_lot_size: int = 1) -> list[OptionContract]:
    if isinstance(rows, dict):
        rows = rows.get("data") or rows.get("records") or rows.get("Records") or rows.get("options") or []
    result = []
    for row in rows:
        if not isinstance(row, dict): continue
        raw_type = str(row.get("option_type") or row.get("instrument_type") or row.get("type") or row.get("opttype") or "").upper()
        typ = {"CALL": "CE", "C": "CE", "PUT": "PE", "P": "PE"}.get(raw_type, raw_type)
        if typ not in {"CE", "PE"}: continue
        try:
            strike = float(row.get("strike") or row.get("strike_price")); expiry = str(row.get("expiry") or row.get("expiry_date") or "")[:10]
        except (TypeError, ValueError): continue
        if strike <= 0 or not expiry: continue
        result.append(ChainQuote(str(row.get("symbol") or row.get("tradingsymbol") or row.get("instrument") or ""), strike, expiry, typ, float(row.get("ltp") or row.get("last_price") or row.get("close") or 0), float(row.get("bid") or row.get("bid_price") or 0), float(row.get("ask") or row.get("ask_price") or 0), int(row.get("lot_size") or row.get("lotsize") or default_lot_size), float(row.get("volume") or 0), float(row.get("open_interest") or row.get("oi") or 0), float(row["delta"]) if row.get("delta") not in (None, "") else None).to_contract())
    return result

def filter_chain(contracts: Sequence[OptionContract], cfg: StrategyConfig, *, today: date | None = None) -> list[OptionContract]:
    """Drop every contract that fails an eligibility gate.

    The gates mirror :func:`app.engines.nifty_orb_options.select_option` exactly
    so a contract can never pass the chain boundary and then be rejected (or
    worse, accepted) on a different rule at selection time.
    """
    cfg.validate(); today = today or date.today(); result = []
    for c in contracts:
        if not c.symbol or c.lot_size <= 0 or c.ltp <= 0: continue
        if cfg.truedata_use_bid_ask and (c.bid <= 0 or c.ask < c.bid or c.spread_pct > cfg.max_spread_pct): continue
        if cfg.truedata_use_oi and c.open_interest < cfg.min_open_interest: continue
        if c.volume < cfg.min_option_volume: continue
        dte = c.dte_on(today)
        if dte is None or dte < cfg.expiry_dte_min or dte > cfg.expiry_dte_max: continue
        if cfg.avoid_expiry_day and dte == 0: continue
        result.append(c)
    return result

QuoteFetcher = Callable[[str, str], Awaitable[Sequence[dict[str, Any]]]]

async def hydrate(symbol: str, direction: str, cfg: StrategyConfig, fetch_quotes: QuoteFetcher) -> list[OptionContract]:
    return filter_chain(normalize_chain(await fetch_quotes(symbol, "CE" if direction == "LONG" else "PE")), cfg)
