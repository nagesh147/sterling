"""API surface for the independent ORB Momentum Options strategy."""
from fastapi import APIRouter, HTTPException
from app.engines.orb_momentum_options import ORBMomentumConfig
from app.services.orb_momentum_scanner import ORBMomentumScanner

router = APIRouter(prefix="/orb-momentum-options", tags=["orb-momentum-options"])
_scanner = ORBMomentumScanner()

@router.get("/config")
async def get_config() -> dict:
    return {"config": _scanner.config.__dict__, "strategy": _scanner.STRATEGY, "option_entry": "BUY_ONLY", "execution_broker": "kite"}

@router.put("/config")
async def update_config(body: dict) -> dict:
    global _scanner
    current = _scanner.config.__dict__.copy()
    unknown = sorted(set(body) - set(current))
    if unknown:
        raise HTTPException(422, f"Unknown fields: {', '.join(unknown)}")
    if body.get("execution_broker", current["execution_broker"]) != "kite":
        raise HTTPException(422, "ORB Momentum Options execution broker must be Kite")
    if body.get("option_entry_side", "BUY") != "BUY":
        raise HTTPException(422, "ORB Momentum Options is option-buying only")
    current.update(body)
    try:
        _scanner = ORBMomentumScanner(ORBMomentumConfig(**current))
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"config": _scanner.config.__dict__, "strategy": _scanner.STRATEGY, "option_entry": "BUY_ONLY", "execution_broker": "kite"}

@router.get("/signals")
async def signals() -> dict:
    return {"strategy": _scanner.STRATEGY, "signals": _scanner.signals()}

@router.post("/reset")
async def reset() -> dict:
    _scanner.reset()
    return {"strategy": _scanner.STRATEGY, "reset": True}
