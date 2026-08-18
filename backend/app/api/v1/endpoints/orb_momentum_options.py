"""API surface for the independent ORB Momentum Options strategy."""
from fastapi import APIRouter
from app.engines.orb_momentum_options import ORBMomentumConfig
from app.services.orb_momentum_scanner import ORBMomentumScanner

router = APIRouter(prefix="/orb-momentum-options", tags=["orb-momentum-options"])
_scanner = ORBMomentumScanner()

@router.get("/config")
async def get_config() -> dict:
    return {"config": _scanner.config.__dict__, "strategy": _scanner.STRATEGY}

@router.put("/config")
async def update_config(body: dict) -> dict:
    global _scanner
    current = _scanner.config.__dict__.copy(); unknown = sorted(set(body) - set(current))
    if unknown: return {"error": f"Unknown fields: {', '.join(unknown)}"}
    current.update(body)
    _scanner = ORBMomentumScanner(ORBMomentumConfig(**current))
    return {"config": _scanner.config.__dict__, "strategy": _scanner.STRATEGY}

@router.get("/signals")
async def signals() -> dict:
    return {"strategy": _scanner.STRATEGY, "signals": _scanner.signals()}

@router.post("/reset")
async def reset() -> dict:
    _scanner.reset()
    return {"strategy": _scanner.STRATEGY, "reset": True}
