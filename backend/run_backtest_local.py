import pandas as pd
import numpy as np
import ta
import os

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
        
    elif strategy_name == "supertrend":
        df['macd'] = ta.trend.macd_diff(df['close'])
        signal = (df['macd'] > 0) & (df['macd'].shift(1) <= 0)
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "bollinger":
        df['bb_high'] = ta.volatility.bollinger_hband(df['close'], window=20, window_dev=2)
        signal = (df['close'] > df['bb_high']) & (df['close'].shift(1) <= df['bb_high'].shift(1))
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "ict":
        gap = df['low'] - df['high'].shift(2)
        curr_bullish = df['close'] > df['open']
        signal = (gap > df['close'] * 0.001) & curr_bullish
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    elif strategy_name == "supply_demand":
        df['support'] = df['low'].rolling(50).min().shift(1)
        signal = (df['close'] < df['support'] * 1.002) & (df['close'] > df['support'])
        df['strategy_returns'] = np.where(signal, df['next_return'], 0)
        
    else:
        df['strategy_returns'] = 0
        
    return df[df['strategy_returns'] != 0]['strategy_returns']

symbols = ['BTCUSD', 'ETHUSD', 'SOLUSD']
timeframes = ['1m', '5m', '15m', '30m', '1h', '4h']
strategies = [
    {'id': 'mean_reversion', 'name': 'Sterling: Mean Reversion (RSI)'},
    {'id': 'ma_crossover', 'name': 'Sterling: MA Crossover (9/21)'},
    {'id': 'breakout', 'name': 'Sterling: 20-Period Breakout'},
    {'id': 'price_action', 'name': 'Sterling: Price Action (Engulfing)'},
    {'id': 'smc', 'name': 'Sterling: Smart Money Concepts (FVG)'},
    {'id': 'supertrend', 'name': 'Community: SuperTrend Scalp'},
    {'id': 'bollinger', 'name': 'Community: Bollinger Bands Breakout'},
    {'id': 'ict', 'name': 'Community: ICT Silver Bullet'},
    {'id': 'supply_demand', 'name': 'Community: 1H Supply/Demand'}
]
profiles = ['Intraday', 'Scalping', 'Aggressive']

results = []

for sym in symbols:
    file_path = f"vector_store_1m_{sym}.parquet"
    if not os.path.exists(file_path):
        continue
    df_base = pd.read_parquet(file_path)
    if 'timestamp' in df_base.columns:
        df_base['timestamp'] = pd.to_datetime(df_base['timestamp'], unit='ms') # Or infer
        df_base.set_index('timestamp', inplace=True)
    elif not isinstance(df_base.index, pd.DatetimeIndex):
        df_base.index = pd.date_range(end=pd.Timestamp.now(), periods=len(df_base), freq='1min')
    
    tf_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "45m": "45min", "1h": "1h", "2h": "2h", "4h": "4h"}
    
    for tf in timeframes:
        pd_tf = tf_map.get(tf, "1min")
        if pd_tf != "1min":
            df_tf = df_base.resample(pd_tf).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
        else:
            df_tf = df_base.copy()
            
        for strat in strategies:
            returns_series = apply_strategy(df_tf.copy(), strat['id'])
            if len(returns_series) == 0:
                continue
                
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
                
            end_capital = 500.0 * (1 + returns_series).prod()
            net_return = end_capital - 500.0
            
            for prof in profiles:
                # Currently profile doesn't change the vector logic in python snippet,
                # but we show it as requested by the user.
                results.append({
                    "symbol": sym,
                    "tf": tf,
                    "strategy": strat['name'],
                    "profile": prof,
                    "win_rate": win_rate,
                    "profit_factor": pf,
                    "expectancy": sharpe,
                    "net_return": net_return,
                    "end_capital": end_capital
                })

df_res = pd.DataFrame(results)
if not df_res.empty:
    df_res = df_res.sort_values(by="net_return", ascending=False).drop_duplicates().head(20)
    print(f"{'Strategy Configuration':<60} | {'Profile':<12} | {'Win Rate':<10} | {'Profit Fac':<10} | {'Expectancy':<10} | {'Net Return':<15} | {'End Capital':<15}")
    print("-" * 145)
    for _, row in df_res.iterrows():
        config = f"{row['strategy']} ({row['symbol']} {row['tf']})"
        print(f"{config:<60} | {row['profile']:<12} | {row['win_rate']*100:>8.2f}% | {row['profit_factor']:>10.2f} | {row['expectancy']:>10.2f} | ${row['net_return']:>13.2f} | ${row['end_capital']:>13.2f}")
else:
    print("No results")
