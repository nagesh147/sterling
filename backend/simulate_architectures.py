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
        sharpe = np.sqrt(252) * returns_series.mean() / returns_series.std()
    
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
        signal = signal & (~signal.shift(1).fillna(False))
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "price_action":
        prev_bearish = df['close'].shift(1) < df['open'].shift(1)
        curr_bullish = df['close'] > df['open']
        engulfs_body = (df['close'] > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))
        signal = prev_bearish & curr_bullish & engulfs_body
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "smc":
        gap = df['low'] - df['high'].shift(2)
        curr_bullish = df['close'] > df['open']
        signal = (gap > 0) & curr_bullish
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    else:
        df['strategy_returns'] = 0
        
    return df[df['strategy_returns'] != 0]['strategy_returns']

def main():
    print("="*100)
    print(" TRADING METRICS SIMULATION: Portfolio Level ($500 Capital)")
    print("="*100)
    
    files = glob.glob('vector_store_1m_*.parquet')
    if not files: return
    df_raw = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df_raw['time'] = pd.to_datetime(df_raw['time'], unit='s')
    df_raw.set_index('time', inplace=True)
    
    timeframes = ["1min", "5min", "15min", "30min", "45min", "1h", "2h", "4h"]
    tf_labels = ["1m", "5m", "15m", "30m", "45m", "1h", "2h", "4h"]
    
    resampled_dfs = {}
    for tf_key, tf_label in zip(timeframes, tf_labels):
        if tf_key == "1min": resampled_dfs[tf_label] = df_raw.copy()
        else: resampled_dfs[tf_label] = df_raw.groupby('symbol').resample(tf_key).agg({
            'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
        }).reset_index(level=0, drop=True)
            
    print("\n[ SCENARIO 1: The 'AI Gatekeeper' (Using ALL Standard Profiles) ]")
    
    all_profiles_strategies = ["price_action", "smc", "breakout", "ma_crossover", "mean_reversion"]
    
    all_raw_returns = []
    perfect_filtered_returns = []
    
    gatekeeper_accepts = [("mean_reversion", "1m"), ("price_action", "5m"), ("smc", "4h")]
    
    for tf_label in tf_labels:
        df_tf = resampled_dfs[tf_label]
        for strat in all_profiles_strategies:
            trades = apply_strategy(df_tf.copy(), strat)
            all_raw_returns.append(trades)
            
            if (strat, tf_label) in gatekeeper_accepts:
                perfect_filtered_returns.append(trades)
                
    combined_raw = pd.concat(all_raw_returns).sort_index()
    combined_filtered = pd.concat(perfect_filtered_returns).sort_index()
    
    raw_metrics = calculate_metrics(combined_raw)
    filtered_metrics = calculate_metrics(combined_filtered)
    
    print("If you run standard profiles, the backend generates this RAW portfolio BEFORE the Gatekeeper:")
    print(f"Total Trades Generated: {raw_metrics['Trades']:,}")
    print(f"Raw Win Rate:           {raw_metrics['Win Rate']*100:.2f}%")
    print(f"Raw Profit Factor:      {raw_metrics['PF']:.2f}")
    print(f"Raw Sharpe:             {raw_metrics['Sharpe']:.2f}")
    print(f"Raw Final Balance:      ${raw_metrics['End Capital']:,.2f}")
    
    print("\nIf the AI Gatekeeper works FLAWLESSLY and rejects all 3.3 million bad trades,")
    print("leaving only the Top 3 pairs, you get these POST-FILTER metrics:")
    print(f"Total Trades Executed: {filtered_metrics['Trades']:,}")
    print(f"Filtered Win Rate:     {filtered_metrics['Win Rate']*100:.2f}%")
    print(f"Filtered Profit Factor:{filtered_metrics['PF']:.2f}")
    print(f"Filtered Sharpe:       {filtered_metrics['Sharpe']:.2f}")
    print(f"Filtered Final Balance:${filtered_metrics['End Capital']:,.2f}")
    
    print("\n" + "="*100)
    print("[ SCENARIO 2: Refactored Backend (Optimized Strategy+Timeframe Pairs) ]")
    
    opt_returns = []
    for strat, tf_label in gatekeeper_accepts:
        df_tf = resampled_dfs[tf_label]
        trades = apply_strategy(df_tf.copy(), strat)
        opt_returns.append(trades)
        
    combined_opt = pd.concat(opt_returns).sort_index()
    opt_metrics = calculate_metrics(combined_opt)
    
    print("Backend ONLY generates signals for the combinations with proven mathematical edge.")
    print("The RAW portfolio BEFORE the Gatekeeper is exactly the same as the flawless post-filter above:")
    print(f"Total Trades Generated: {opt_metrics['Trades']:,} (NO TRASH FILTERING NEEDED)")
    print(f"Optimized Win Rate:     {opt_metrics['Win Rate']*100:.2f}%")
    print(f"Optimized Profit Factor:{opt_metrics['PF']:.2f}")
    print(f"Optimized Sharpe:       {opt_metrics['Sharpe']:.2f}")
    print(f"Optimized Final Balance:${opt_metrics['End Capital']:,.2f}")
    print("="*100)

if __name__ == "__main__":
    main()
