import numpy as np
import pandas as pd
from typing import Dict, Any

def run_bias_diagnostic(df_4h: pd.DataFrame, trade_log: pd.DataFrame) -> Dict[str, Any]:
    """
    Compares macro regime distribution against engine trade execution distribution
    to detect mechanical code asymmetry vs. natural market trend following.
    
    df_4h: DataFrame with columns ['open', 'high', 'low', 'close']
    trade_log: DataFrame of executed trades with columns ['side', 'timestamp']
    """
    # 1. Establish the Macro Benchmark (Using a standard 50 EMA on 4H data)
    df_4h['ema50'] = df_4h['close'].ewm(span=50, adjust=False).mean()
    
    total_bars = len(df_4h)
    bullish_bars = np.sum(df_4h['close'] > df_4h['ema50'])
    bearish_bars = np.sum(df_4h['close'] <= df_4h['ema50'])
    
    macro_bull_pct = (bullish_bars / total_bars) * 100
    macro_bear_pct = (bearish_bars / total_bars) * 100
    
    # 2. Calculate Engine Execution Distribution
    total_trades = len(trade_log)
    long_trades = np.sum(trade_log['side'] == 'long')
    short_trades = np.sum(trade_log['side'] == 'short')
    
    engine_long_pct = (long_trades / total_trades) * 100 if total_trades > 0 else 0
    engine_short_pct = (short_trades / total_trades) * 100 if total_trades > 0 else 0
    
    # 3. Analyze the Divergence Delta
    long_delta = engine_long_pct - macro_bull_pct
    
    print("=== STERLING SCALPING ENGINE BIAS DIAGNOSTIC ===")
    print(f"Macro Market Environment:  {macro_bull_pct:.1f}% Bullish | {macro_bear_pct:.1f}% Bearish")
    print(f"Engine Trade Allocation:   {engine_long_pct:.1f}% Longs   | {engine_short_pct:.1f}% Shorts")
    print("-" * 48)
    
    if abs(long_delta) <= 15:
        print("✅ DIAGNOSTIC: PASS (Market Driven)")
        print("The short/long bias is legitimate. Your engine is correctly reflecting the macro regime.")
    else:
        print("❌ DIAGNOSTIC: FAIL (Mechanical Asymmetry Detected)")
        print(f"WARNING: Engine is heavily skewed by an extra {abs(long_delta):.1f}% relative to the market trend.")
        print("Check your horizontal zone detection logic for mathematical inequalities or hardcoded defaults.")
        
    return {
        "macro_bull_pct": macro_bull_pct,
        "engine_long_pct": engine_long_pct,
        "divergence_delta": long_delta
    }
