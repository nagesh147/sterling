from test_smc import load_candles
from pathlib import Path
import pandas as pd
from smartmoneyconcepts import smc

candles = load_candles("BTCUSD", "1h", Path("sterling_paper.db"))
df = pd.DataFrame({
    "open": [c.open for c in candles[-200:]],
    "high": [c.high for c in candles[-200:]],
    "low": [c.low for c in candles[-200:]],
    "close": [c.close for c in candles[-200:]],
    "volume": [c.volume for c in candles[-200:]],
})

df_fvg = smc.fvg(df)
df_ob = smc.ob(df)
df_bos = smc.bos_choch(df)

print("FVG columns:", df_fvg.columns.tolist() if hasattr(df_fvg, 'columns') else type(df_fvg))
print("OB columns:", df_ob.columns.tolist() if hasattr(df_ob, 'columns') else type(df_ob))
print("BOS columns:", df_bos.columns.tolist() if hasattr(df_bos, 'columns') else type(df_bos))
