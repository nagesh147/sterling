import sys
import re

filepath = "backend/main.py"
with open(filepath, "r") as f:
    content = f.read()

new_dl_load = """    # Phase: derivatives_profiles and DailyLossConfig persistence loading
    try:
        from app.services.db import get_config
        import json
        
        dl_str = get_config("daily_loss_config")
        if dl_str:
            from app.services.live_safety import configure_daily_loss
            parsed = json.loads(dl_str)
            configure_daily_loss(parsed.get("soft_warn_usd", -500.0), parsed.get("hard_halt_usd", -1500.0))
            
        dp_str = get_config("derivatives_profiles")
        if dp_str:
            from app.schemas.derivatives import StrategyDerivativesProfile
            parsed = json.loads(dp_str)
            restored = {}
            for k, v in parsed.items():
                restored[k] = StrategyDerivativesProfile(**v)
            app.state.derivatives_profiles = restored
            log.info(f"Restored derivatives_profiles from DB for {list(restored.keys())}")
    except Exception as e:
        log.warning(f"Failed to restore configs from DB: {e}")

    # Restore persisted Telegram credentials."""

content = content.replace("    # Restore persisted Telegram credentials.", new_dl_load)

with open(filepath, "w") as f:
    f.write(content)
print("Patched main.py")
