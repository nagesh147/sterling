import sys

filepath = "backend/main.py"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace(
    'configure_daily_loss(parsed.get("soft_warn_usd", -500.0), parsed.get("hard_halt_usd", -1500.0))',
    'from app.services.live_safety import DailyLossConfig\n            configure_daily_loss(DailyLossConfig(soft_warn_usd=parsed.get("soft_warn_usd", -500.0), hard_halt_usd=parsed.get("hard_halt_usd", -1500.0)))'
)

with open(filepath, "w") as f:
    f.write(content)
print("Fixed main.py configure_daily_loss call")
