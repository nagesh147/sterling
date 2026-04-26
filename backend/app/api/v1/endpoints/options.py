"""
Option chain browser — returns full chain with per-contract health assessment.

GET /options/chain?underlying=BTC&type=all&min_dte=5&max_dte=45
"""
import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request

from app.services.exchanges import instrument_registry as registry
from app.engines.directional.contract_health_engine import assess_contract_health

router = APIRouter(prefix="/options", tags=["options"])


@router.get("/chain")
async def option_chain(
    underlying: str = Query(...),
    type: str = Query(default="all", pattern="^(call|put|all)$"),
    min_dte: int = Query(default=5, ge=0, le=365),
    max_dte: int = Query(default=45, ge=0, le=365),
    request: Request = None,
):
    sym = underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")
    if not inst.has_options:
        raise HTTPException(status_code=400, detail=f"{sym} has no options on {inst.exchange}")

    adapter = request.app.state.adapter
    try:
        spot = await adapter.get_index_price(inst)
        raw_chain = await adapter.get_option_chain(inst)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Option chain fetch failed: {exc}")

    # Filter by DTE and type
    filtered = [o for o in raw_chain if min_dte <= o.dte <= max_dte]
    if type != "all":
        filtered = [o for o in filtered if o.option_type == type]

    # Assess health
    assessed = [assess_contract_health(o, min_dte=inst.min_dte) for o in filtered]

    # Group by expiry date, sort strikes within each expiry
    by_expiry: dict = {}
    for c in assessed:
        by_expiry.setdefault(c.expiry_date, []).append(c.model_dump())

    for expiry in by_expiry:
        by_expiry[expiry].sort(key=lambda x: x["strike"])

    healthy_count = sum(1 for c in assessed if c.healthy)

    # IV distribution stats from healthy contracts
    ivs = sorted(c.mark_iv for c in assessed if c.healthy and c.mark_iv > 0)
    atm = min(assessed, key=lambda x: abs(x.strike - float(spot)), default=None) if assessed else None
    iv_stats = {}
    if ivs:
        iv_stats = {
            "atm_iv": round(atm.mark_iv, 2) if atm and atm.mark_iv > 0 else None,
            "min_iv": round(ivs[0], 2),
            "max_iv": round(ivs[-1], 2),
            "avg_iv": round(sum(ivs) / len(ivs), 2),
            "iv_skew": round(ivs[-1] - ivs[0], 2),
            "sample_count": len(ivs),
        }

    return {
        "underlying": sym,
        "spot_price": float(spot),
        "exchange": inst.exchange,
        "total_contracts": len(assessed),
        "healthy_contracts": healthy_count,
        "expiry_count": len(by_expiry),
        "filter": {"type": type, "min_dte": min_dte, "max_dte": max_dte},
        "iv_stats": iv_stats,
        "by_expiry": by_expiry,
        "timestamp_ms": int(time.time() * 1000),
    }
