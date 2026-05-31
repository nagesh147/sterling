import sys

filepath = "backend/main.py"
with open(filepath, "r") as f:
    content = f.read()

new_block = """
    _router_mode = (get_config("algo_router_mode") or "live").lower()
    if _router_mode in ("paper", "shadow", "live"):
        app.state.algo_router_mode = _router_mode
    else:
        app.state.algo_router_mode = "live"

    # Daily Loss Circuit Breaker
    dl_cfg_str = get_config("daily_loss_config")
    if dl_cfg_str:
        import json
        try:
            dl_dict = json.loads(dl_cfg_str)
            from app.services.live_safety import configure_daily_loss, DailyLossConfig
            configure_daily_loss(DailyLossConfig(
                soft_warn_usd=float(dl_dict.get("soft_warn_usd", -1000.0)),
                hard_halt_usd=float(dl_dict.get("hard_halt_usd", -1500.0))
            ))
        except Exception:
            pass
"""

content = content.replace("""    _router_mode = (get_config("algo_router_mode") or "live").lower()
    if _router_mode in ("paper", "shadow", "live"):
        app.state.algo_router_mode = _router_mode
    else:
        app.state.algo_router_mode = "live"
""", new_block)

with open(filepath, "w") as f:
    f.write(content)
print("Patched main.py")
