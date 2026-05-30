import time
import numpy as np
import pandas as pd
import ta
import warnings
import glob

warnings.filterwarnings('ignore')

def calculate_metrics(returns_series, starting_capital=500):
    if len(returns_series) == 0:
        return {"Trades": 0, "PF": 0.0, "Win Rate": 0.0, "Sharpe": 0.0, "End Capital": starting_capital,
                "Gross Profit": 0.0, "Gross Loss": 0.0, "Net Return": 0.0, "Expectancy": 0.0}
    
    returns_series = returns_series.replace([np.inf, -np.inf], 0).fillna(0)
    wins = returns_series[returns_series > 0]
    losses = returns_series[returns_series < 0]
    
    gross_profit_pct = wins.sum() if len(wins) > 0 else 0
    gross_loss_pct = abs(losses.sum()) if len(losses) > 0 else 0
    
    pf = gross_profit_pct / gross_loss_pct if gross_loss_pct > 0 else (99.9 if gross_profit_pct > 0 else 0.0)
    win_rate = len(wins) / len(returns_series)
    
    sharpe = 0.0
    if len(returns_series) > 1 and returns_series.std() > 0:
        sharpe = np.sqrt(252) * returns_series.mean() / returns_series.std()
    
    cumulative = (1 + returns_series).prod()
    end_capital = starting_capital * cumulative
    
    net_return_pct = cumulative - 1
    gross_profit_usd = starting_capital * gross_profit_pct
    gross_loss_usd = starting_capital * gross_loss_pct
    
    # Expectancy = (Win % * Average Win) - (Loss % * Average Loss)
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        
    return {
        "Trades": len(returns_series),
        "PF": pf,
        "Win Rate": win_rate,
        "Sharpe": sharpe,
        "End Capital": end_capital,
        "Gross Profit": gross_profit_usd,
        "Gross Loss": gross_loss_usd,
        "Net Return": net_return_pct,
        "Expectancy": expectancy
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
    files = glob.glob('backend/vector_store_1m_*.parquet')
    if not files:
        print("No Parquet files found.")
        return
        
    df_raw = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df_raw['time'] = pd.to_datetime(df_raw['time'], unit='s')
    df_raw.set_index('time', inplace=True)
    
    timeframes = ["1min", "5min", "15min", "30min", "1h", "4h"]
    tf_labels = ["1m", "5m", "15m", "30m", "1h", "4h"]
    
    profiles = {
        "Intraday": ["price_action", "smc"],
        "Scalping": ["price_action", "breakout"],
        "Aggressive": ["mean_reversion", "ma_crossover"]
    }

    results = []

    resampled_dfs = {}
    for tf_key, tf_label in zip(timeframes, tf_labels):
        if tf_key == "1min":
            resampled_dfs[tf_label] = df_raw.copy()
        else:
            resampled_dfs[tf_label] = df_raw.groupby('symbol').resample(tf_key).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).reset_index(level=0, drop=True)

    for profile_name, active_strats in profiles.items():
        for tf_label in tf_labels:
            df_tf = resampled_dfs[tf_label]
            
            for strat in active_strats:
                trades = apply_strategy(df_tf.copy(), strat)
                m = calculate_metrics(trades, starting_capital=500)
                
                results.append({
                    "Strategy": f"{strat.replace('_', ' ').title()} ({tf_label})",
                    "Profile": profile_name,
                    "Win Rate": f"{m['Win Rate']*100:.1f}%",
                    "Profit Fac": f"{m['PF']:.2f}",
                    "Expectancy": f"{m['Expectancy']:.4f}",
                    "Gross Profit": f"${m['Gross Profit']:.2f}",
                    "Gross Loss": f"${m['Gross Loss']:.2f}",
                    "Net Return": f"{m['Net Return']*100:.1f}%",
                    "Simulated PnL": f"${m['End Capital'] - 500:.2f}",
                    "End Capital": m['End Capital']
                })

    # Sort by End Capital
    results = sorted(results, key=lambda x: x["End Capital"], reverse=True)

    print("| Strategy (Timeframe Configuration) | Profile | Win Rate | Profit Fac | Expectancy | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in results[:15]:
        print(f"| {r['Strategy']} | {r['Profile']} | {r['Win Rate']} | {r['Profit Fac']} | {r['Expectancy']} | {r['Gross Profit']} | {r['Gross Loss']} | {r['Net Return']} | {r['Simulated PnL']} |")

if __name__ == "__main__":
    main()
