from test_smc import load_candles
from pathlib import Path
import pandas as pd
from smartmoneyconcepts import smc

candles = load_candles("BTCUSD", "1h", Path("sterling_paper.db"))
df = pd.DataFrame({
    "Date": [pd.to_datetime(c.timestamp_ms, unit="ms") for c in candles[-200:]],
    "Open": [c.open for c in candles[-200:]],
    "High": [c.high for c in candles[-200:]],
    "Low": [c.low for c in candles[-200:]],
    "Close": [c.close for c in candles[-200:]],
    "Volume": [c.volume for c in candles[-200:]],
})

df = smc.fvg(df)
df = smc.ob(df)
df = smc.bos_choch(df)
print(df.columns)
print(df.tail(2))
