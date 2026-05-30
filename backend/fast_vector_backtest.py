import pandas as pd
import numpy as np
import time

STORE_PATH = 'vector_store_1m.parquet'

def main():
    print("="*80)
    print(" VECTORIZED ULTRA-FAST BACKTESTER ")
    print("="*80)
    
    start_time = time.time()
    
    try:
        # Loading millions of rows takes < 1 second with Parquet
        print(f"[i] Loading 5-year dataset from {STORE_PATH}...")
        df = pd.read_parquet(STORE_PATH)
    except FileNotFoundError:
        print(f"[!] File not found. Please run build_vector_store.py first.")
        return
        
    print(f"[i] Loaded {len(df):,} rows in {time.time() - start_time:.2f} seconds.")
    
    # -----------------------------------------------------------------------
    # STRATEGY 1: MA CROSSOVER
    # Logic: Go Long when EMA Fast crosses above EMA Slow
    # -----------------------------------------------------------------------
    calc_start = time.time()
    
    # Vectorized condition evaluation (Millions of rows evaluated in milliseconds)
    # df['trend_ema_fast'] > df['trend_ema_slow'] yields a True/False boolean array.
    df['is_bullish'] = df['trend_ema_fast'] > df['trend_ema_slow']
    
    # Detect the exact moment of the crossover (True this candle, False last candle)
    df['crossover_long'] = df['is_bullish'] & (~df['is_bullish'].shift(1).fillna(False))
    
    # Calculate returns. 
    # If we buy at the close of the crossover candle, our return is the difference 
    # between the next candle's close and this candle's close.
    # Note: A real strategy would use ATR for stop loss, which we also have pre-calculated!
    df['next_candle_return'] = df['close'].shift(-1) - df['close']
    
    # Mask out the returns where we didn't have a signal
    df['strategy_returns'] = np.where(df['crossover_long'], df['next_candle_return'], 0)
    
    # Count trades and calculate metrics
    total_trades = df['crossover_long'].sum()
    winning_trades = (df['strategy_returns'] > 0).sum()
    losing_trades = (df['strategy_returns'] < 0).sum()
    
    gross_profit = df[df['strategy_returns'] > 0]['strategy_returns'].sum()
    gross_loss = abs(df[df['strategy_returns'] < 0]['strategy_returns'].sum())
    
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else 0
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    calc_end = time.time()
    
    print("\n[i] STRATEGY RESULTS: MA Crossover")
    print("-" * 40)
    print(f"Total Trades Evaluated : {total_trades:,}")
    print(f"Win Rate               : {win_rate*100:.2f}%")
    print(f"Profit Factor          : {profit_factor:.2f}")
    print(f"Calculation Time       : {calc_end - calc_start:.4f} seconds")
    print("="*80)
    print("Notice how a multi-year backtest executed in fractions of a second!")

if __name__ == "__main__":
    main()
