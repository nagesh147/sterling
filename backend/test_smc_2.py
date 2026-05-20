from test_smc import load_candles
from pathlib import Path
import pandas as pd
from smartmoneyconcepts import smc

candles = load_candles("BTCUSD", "1h", Path("sterling_paper.db"))
df = pd.DataFrame({
    "timestamp_ms": [c.timestamp_ms for c in candles[-200:]],
    "open": [c.open for c in candles[-200:]],
    "high": [c.high for c in candles[-200:]],
    "low": [c.low for c in candles[-200:]],
    "close": [c.close for c in candles[-200:]],
    "volume": [c.volume for c in candles[-200:]],
})

df = smc.fvg(df)
df = smc.ob(df)
df = smc.bos_choch(df)
print(df.columns)
print(df.tail(2))
