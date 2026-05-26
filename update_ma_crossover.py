import re

file_path = "/home/nageshmadaram/Sterling/backend/app/engines/scalping/ma_crossover.py"
with open(file_path, "r") as f:
    content = f.read()

content = content.replace("fast = cfg.ma_fast_period", "fast = cfg.ma_fast_sma")
content = content.replace("slow = cfg.ma_slow_period", "slow = cfg.ma_slow_ema")

content = content.replace("cross_bars = min(3, i)", "cross_bars = min(cfg.ma_cross_window, i)")
content = content.replace("swing_lookback=10", "swing_lookback=cfg.ma_risk_lookback")
content = content.replace("lows_15m[-10:]", "lows_15m[-cfg.ma_risk_lookback:]")
content = content.replace("highs_15m[-10:]", "highs_15m[-cfg.ma_risk_lookback:]")

content = content.replace("last 10 candles", "last cfg.ma_risk_lookback candles")

with open(file_path, "w") as f:
    f.write(content)
