"""TrueData-native provider for ORB.

TrueData is used as a first-class market-data source. Historical bars build the
ORB; the option-chain endpoint discovers contracts; latest ticks refresh the
actual executable quote before the option is selected. The strategy engine
itself remains broker/data-provider agnostic.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Sequence
from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig
from app.services.market_data.truedata import TrueDataHistoricalClient
from app.services.nifty_orb_option_chain import normalize_chain, filter_chain

class TrueDataOrbProvider:
    def __init__(self, client: TrueDataHistoricalClient) -> None:
        self.client = client

    async def bars(self, symbol: str, cfg: StrategyConfig) -> list[Bar]:
        interval = f"{cfg.interval_minutes}min"
        rows = await self.client.get_last_bars(symbol, 200, interval=interval, bidask=0)
        out: list[Bar] = []
        for r in rows:
            raw = str(r.get("timestamp") or r.get("time") or "")
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00")) if "T" in raw else datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out.append(Bar(dt, float(r.get("open", 0)), float(r.get("high", 0)), float(r.get("low", 0)), float(r.get("close", 0)), float(r.get("volume", 0))))
        return out

    async def latest_tick(self, symbol: str, *, bidask: bool = True) -> dict[str, Any] | None:
        rows = await self.client.get_last_ticks(symbol, 1, bidask=1 if bidask else 0)
        return rows[-1] if rows else None

    @staticmethod
    def _tick_time(tick: dict[str, Any]) -> datetime | None:
        raw = tick.get("timestamp") or tick.get("time")
        if not raw:
            return None
        try:
            if isinstance(raw, (int, float)):
                return datetime.fromtimestamp(float(raw) / 1000, tz=timezone.utc)
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    async def refresh_contracts(self, contracts: Sequence[OptionContract], cfg: StrategyConfig) -> list[OptionContract]:
        """Refresh only the option candidates with TrueData's latest tick API."""
        refreshed: list[OptionContract] = []
        now = datetime.now(timezone.utc)
        for contract in contracts:
            tick = await self.latest_tick(contract.symbol, bidask=cfg.truedata_use_bid_ask if hasattr(cfg, "truedata_use_bid_ask") else True) if getattr(cfg, "truedata_use_ticks", True) else None
            if tick is None and getattr(cfg, "truedata_use_ticks", True):
                continue
            if tick:
                stamp = self._tick_time(tick)
                if getattr(cfg, "truedata_use_quote_freshness", True) and stamp is not None:
                    age = max(0.0, (now - stamp).total_seconds())
                    if age > cfg.max_quote_staleness_s:
                        continue
                ltp = float(tick.get("ltp") or contract.ltp or 0)
                bid = float(tick.get("bid") or contract.bid or 0)
                ask = float(tick.get("ask") or contract.ask or 0)
                volume = float(tick.get("volume") or contract.volume or 0)
                oi = float(tick.get("oi") or contract.open_interest or 0)
                contract = OptionContract(contract.symbol, contract.strike, contract.expiry, contract.option_type, ltp, bid, ask, contract.lot_size, contract.delta, volume, oi)
            if getattr(cfg, "truedata_use_oi", True) and contract.open_interest < cfg.min_open_interest:
                continue
            if getattr(cfg, "truedata_use_bid_ask", True) and contract.spread_pct > cfg.max_spread_pct:
                continue
            refreshed.append(contract)
        return filter_chain(refreshed, cfg)

    async def option_chain(self, symbol: str, expiry: str, cfg: StrategyConfig) -> list[OptionContract]:
        payload = await self.client.get_option_chain(symbol, expiry)
        contracts = filter_chain(normalize_chain(payload), cfg)
        return await self.refresh_contracts(contracts, cfg)

    async def symbols(self, segment: str = "NFO", search: str | None = None) -> Any:
        return await self.client.get_all_symbols(segment, search=search, allexpiry=False)
