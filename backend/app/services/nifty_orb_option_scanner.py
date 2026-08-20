"""Realtime ORB scanner -> option candidate orchestration.

No order placement occurs here. This service produces the exact candidates that
can be rendered in Signals and later passed to universal execution.
"""
from __future__ import annotations
import asyncio
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Awaitable, Callable, Sequence
from app.engines.nifty_orb_options import OptionContract, StrategyConfig
from app.engines.nifty_orb_universe import IST, UniverseInstrument, UniverseScanConfig, UniverseSignal, scan_universe
from app.services.nifty_orb_option_chain import filter_chain
from app.services.nifty_orb_trade_planner import PlannedSignal, plan_signal

OptionFetcher=Callable[[UniverseInstrument,str,StrategyConfig],Awaitable[Sequence[OptionContract]]]
BarFetcher=Callable[[UniverseInstrument,StrategyConfig],Awaitable[Sequence[Any]]]

@dataclass(frozen=True)
class OptionSignalCandidate:
    planned: PlannedSignal
    rank: tuple[float,float,float,str]
    status: str="actionable"

    def to_dict(self)->dict[str,Any]:
        p=self.planned
        return {"symbol":p.symbol,"kind":p.kind,"status":self.status,"rank":self.rank,"signal":p.signal.to_dict(),"option":asdict(p.option),"trade_plan":p.trade_plan.to_dict()}

async def scan_option_candidates(
    instruments: Sequence[UniverseInstrument], *, strategy_config: StrategyConfig,
    scan_config: UniverseScanConfig=UniverseScanConfig(), fetch_bars: BarFetcher,
    fetch_options: OptionFetcher, max_option_concurrency: int=4,
    as_of: datetime|None=None,
) -> list[OptionSignalCandidate]:
    """Scan underlyings, hydrate only actionable signals, and build option plans.

    One session date anchors both the chain filter and option selection. They
    previously disagreed: ``filter_chain`` defaulted to the machine's local date
    while ``select_option`` used IST, so on a UTC host they resolved to different
    days for five and a half hours every night.
    """
    strategy_config.validate()
    now=(as_of or datetime.now(IST)).astimezone(IST); session=now.date()
    signals=await scan_universe(instruments,strategy_config=strategy_config,scan_config=scan_config,fetch_bars=fetch_bars,as_of=now)
    semaphore=asyncio.Semaphore(max(1,max_option_concurrency))
    async def resolve(candidate: UniverseSignal)->OptionSignalCandidate|None:
        async with semaphore:
            try:
                contracts=await fetch_options(candidate.instrument,candidate.signal.direction,strategy_config)
                contracts=filter_chain(contracts,strategy_config,today=session)
                if not contracts:return None
                planned=plan_signal(candidate,contracts,strategy_config,today=session)
                return OptionSignalCandidate(planned,candidate.rank_key)
            except (ValueError,KeyError,RuntimeError):
                return None
    resolved=await asyncio.gather(*(resolve(s) for s in signals))
    out=[x for x in resolved if x is not None]
    out.sort(key=lambda x:x.rank,reverse=True)
    return out
