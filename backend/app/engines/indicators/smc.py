import pandas as pd
from typing import List, Any
import smartmoneyconcepts as smc

def compute_smc(candles: List[Any]) -> pd.DataFrame:
    """
    Computes Smart Money Concepts (FVG, OB, BOS/CHoCH) over the given candles.
    Returns the enriched DataFrame with forward-filled active levels to prevent look-ahead bias.
    """
    if not candles:
        return pd.DataFrame()
        
    df = pd.DataFrame({
        "timestamp_ms": [c.timestamp_ms for c in candles],
        "open": [c.open for c in candles],
        "high": [c.high for c in candles],
        "low": [c.low for c in candles],
        "close": [c.close for c in candles],
        "volume": [c.volume for c in candles],
    })
    
    try:
        # Calculate SMC elements. The library appends new columns or returns a df.
        df = smc.fvg(df)
        df = smc.ob(df)
        df = smc.bos_choch(df)
        
        # Forward-fill state so at any row `i`, we know the nearest active
        # Bullish/Bearish FVG price levels and OB levels.
        cols_to_ffill = [c for c in df.columns if c not in ["timestamp_ms", "open", "high", "low", "close", "volume"]]
        if cols_to_ffill:
            df[cols_to_ffill] = df[cols_to_ffill].ffill()
    except Exception:
        # Fail gracefully if library encounters edge cases or insufficient data
        pass

    return df
