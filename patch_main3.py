import sys

filepath = "backend/main.py"
with open(filepath, "r") as f:
    content = f.read()

old_str = """from app.services.live_safety import DailyLossConfig
            configure_daily_loss(DailyLossConfig(soft_warn_usd=parsed.get("soft_warn_usd", -500.0), hard_halt_usd=parsed.get("hard_halt_usd", -1500.0)))"""

new_str = """from app.services.live_safety import DailyLossConfig
            configure_daily_loss(DailyLossConfig(enabled=parsed.get("enabled", True), soft_warn_usd=parsed.get("soft_warn_usd", -500.0), hard_halt_usd=parsed.get("hard_halt_usd", -1500.0)))"""

if old_str in content:
    content = content.replace(old_str, new_str)
    with open(filepath, "w") as f:
        f.write(content)
    print("Patched main.py")
else:
    print("Could not find string in main.py")
