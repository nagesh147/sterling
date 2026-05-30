import sys
import time
import numpy as np
import pandas as pd
import ta
import warnings
import glob

warnings.filterwarnings('ignore')

def calculate_metrics(returns_series, starting_capital=500):
    if len(returns_series) == 0:
        return {"Trades": 0, "PF": 0.0, "Win Rate": 0.0, "Sharpe": 0.0, "End Capital": starting_capital}
    
    returns_series = returns_series.replace([np.inf, -np.inf], 0).fillna(0)
    wins = returns_series[returns_series > 0]
    losses = returns_series[returns_series < 0]
    
    gross_profit = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 0
    
    pf = gross_profit / gross_loss if gross_loss > 0 else (99.9 if gross_profit > 0 else 0.0)
    win_rate = len(wins) / len(returns_series)
    
    sharpe = 0.0
    if len(returns_series) > 1 and returns_series.std() > 0:
        # Annualized Sharpe (assuming roughly 252*24 trading periods depending on TF, simplified to standard generic)
        sharpe = np.sqrt(252) * returns_series.mean() / returns_series.std()
    
    # Capital calculation assuming fractional returns
    # e.g., trade yields 0.01 = 1% return. 
    cumulative = (1 + returns_series).prod()
    end_capital = starting_capital * cumulative
        
    return {
        "Trades": len(returns_series),
        "PF": pf,
        "Win Rate": win_rate,
        "Sharpe": sharpe,
        "End Capital": end_capital
    }

def apply_strategy(df, strategy_name):
    """
    Applies pure Pandas/NumPy vectorized logic for millions of rows instantly.
    Returns the dataframe with a 'strategy_returns' column.
    """
    # Base return of the asset for the next candle
    df['next_return'] = df['close'].shift(-1) / df['close'] - 1
    
    if strategy_name == "ma_crossover":
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=9)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=21)
        is_bullish = df['ema_fast'] > df['ema_slow']
        signal = is_bullish & (~is_bullish.shift(1).fillna(False))
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "mean_reversion":
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        signal = (df['rsi'] < 30) & (df['rsi'].shift(1) >= 30)
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "breakout":
        df['highest_high'] = df['high'].rolling(20).max().shift(1)
        signal = df['close'] > df['highest_high']
        # Only take the initial breakout, not every bar it's higher
        signal = signal & (~signal.shift(1).fillna(False))
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "price_action":
        # Bullish Engulfing proxy
        prev_bearish = df['close'].shift(1) < df['open'].shift(1)
        curr_bullish = df['close'] > df['open']
        engulfs_body = (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))
        signal = prev_bearish & curr_bullish & engulfs_body
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "smc":
        # Fair Value Gap (Bullish) - Gap between previous high and next low
        gap = df['low'] - df['high'].shift(2)
        curr_bullish = df['close'] > df['open']
        signal = (gap > 0) & curr_bullish
        # Buy on the candle that confirms the FVG creation
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    else:
        df['strategy_returns'] = 0
        
    # Return just the valid trades (non-zero returns)
    return df[df['strategy_returns'] != 0]['strategy_returns']

def main():
    print("="*100)
    print(" MASSIVE VECTORIZED BACKTEST: 5 Years | 8 Timeframes | 5 Strategies | 3 Profiles")
    print("="*100)
    
    start_time = time.time()
    
    files = glob.glob('vector_store_1m_*.parquet')
    if not files:
        print(f"[!] No Parquet files found. Please run build_vector_store.py first.")
        return
        
    print(f"[i] Loading 5-year Parquet dataset from {len(files)} files...")
    df_raw = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        
    print(f"[i] Loaded {len(df_raw):,} raw 1m rows in {time.time() - start_time:.2f} seconds.")
    
    # We must ensure 'time' is a datetime index for fast pandas resampling
    df_raw['time'] = pd.to_datetime(df_raw['time'], unit='s')
    df_raw.set_index('time', inplace=True)
    
    # Define parameters
    timeframes = ["1min", "5min", "15min", "30min", "45min", "1h", "2h", "4h"]
    tf_labels = ["1m", "5m", "15m", "30m", "45m", "1h", "2h", "4h"]
    strategies = ["price_action", "smc", "ma_crossover", "mean_reversion", "breakout"]
    
    profiles = {
        "Intraday": ["price_action", "smc"],
        "Scalping": ["price_action", "breakout"],
        "Aggressive": ["mean_reversion", "ma_crossover"]
    }

    print("\n" + "-"*100)
    print(f"{'Profile':<12} | {'Timeframe':<5} | {'Strategy':<15} | {'Trades':<6} | {'PF':<6} | {'Win %':<6} | {'Sharpe':<6} | {'Final $':<8}")
    print("-" * 100)

    # To avoid recalculating the same timeframe multiple times, we cache resampled dataframes
    resampled_dfs = {}
    for tf_key, tf_label in zip(timeframes, tf_labels):
        if tf_key == "1min":
            resampled_dfs[tf_label] = df_raw.copy()
        else:
            # Vectorized OHLVC resampling is extremely fast
            resampled_dfs[tf_label] = df_raw.groupby('symbol').resample(tf_key).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).reset_index(level=0, drop=True) # Drop symbol from multi-index temporarily for ta calcs

    for profile_name, active_strats in profiles.items():
        for tf_label in tf_labels:
            df_tf = resampled_dfs[tf_label]
            
            for strat in strategies:
                if strat not in active_strats:
                    continue
                    
                # Apply strategy and get trades array
                trades = apply_strategy(df_tf.copy(), strat)
                metrics = calculate_metrics(trades, starting_capital=500)
                
                print(f"{profile_name:<12} | {tf_label:<5} | {strat:<15} | {metrics['Trades']:<6} | {metrics['PF']:<6.2f} | {metrics['Win Rate']*100:<5.1f}% | {metrics['Sharpe']:<6.2f} | ${metrics['End Capital']:<7.2f}")

    total_time = time.time() - start_time
    print("-" * 100)
    print(f"BACKTEST BATCH COMPLETE IN {total_time:.2f} SECONDS.")
    print("="*100)

if __name__ == "__main__":
    main()
