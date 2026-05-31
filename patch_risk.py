import os
import sys

filepath = "backend/app/api/v1/endpoints/risk_dashboard.py"
with open(filepath, "r") as f:
    content = f.read()

new_endpoints = """

class DailyLossRequest(BaseModel):
    soft_warn_usd: float
    hard_halt_usd: float

@router.get("/daily-loss")
async def get_daily_loss(request: Request) -> dict:
    from app.services.live_safety import daily_loss_state, _DAILY_LOSS_CFG
    from app.services.paper_store import list_positions
    state = daily_loss_state(list_positions())
    return {
        "pnl_usd": state["pnl_usd"],
        "level": state["level"],
        "soft_warn_usd": _DAILY_LOSS_CFG.soft_warn_usd,
        "hard_halt_usd": _DAILY_LOSS_CFG.hard_halt_usd,
        "timestamp_ms": int(time.time() * 1000)
    }

@router.post("/daily-loss")
async def set_daily_loss(body: DailyLossRequest, request: Request) -> dict:
    from app.services.live_safety import configure_daily_loss, DailyLossConfig
    from app.services.db import set_config
    
    cfg = DailyLossConfig(
        soft_warn_usd=body.soft_warn_usd,
        hard_halt_usd=body.hard_halt_usd
    )
    configure_daily_loss(cfg)
    
    # Persist
    import json
    set_config("daily_loss_config", json.dumps({"soft_warn_usd": body.soft_warn_usd, "hard_halt_usd": body.hard_halt_usd}))
    
    from app.services.paper_store import list_positions
    from app.services.live_safety import daily_loss_state
    state = daily_loss_state(list_positions())
    return {
        "pnl_usd": state["pnl_usd"],
        "level": state["level"],
        "soft_warn_usd": cfg.soft_warn_usd,
        "hard_halt_usd": cfg.hard_halt_usd,
        "timestamp_ms": int(time.time() * 1000)
    }
"""

if "get_daily_loss" not in content:
    content += new_endpoints
    with open(filepath, "w") as f:
        f.write(content)
    print("Patched risk_dashboard.py")
else:
    print("Already patched")
