import sys
import pandas as pd
import numpy as np
import time
from app.api.v1.endpoints.vectorized_backtest import apply_strategy

symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]
strategies = [
    ('mean_reversion', 'Mean Reversion (RSI)'),
    ('ma_crossover', 'MA Crossover (9/21)'),
    ('breakout', '20-Period Breakout'),
    ('price_action', 'Price Action (Engulfing)'),
    ('smc', 'Smart Money Concepts (FVG)'),
    ('supertrend', 'SuperTrend Scalp'),
    ('bollinger', 'Bollinger Bands Breakout'),
    ('ict', 'ICT Silver Bullet'),
    ('supply_demand', '1H Supply/Demand'),
]
timeframes = ['1m', '5m', '15m', '30m', '45m', '1h', '2h', '4h']
tf_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "45m": "45min", "1h": "1h", "2h": "2h", "4h": "4h"}

capital = 500.0

results = []

for sym in symbols:
    file_path = f"vector_store_1m_{sym}.parquet"
    print(f"Loading {file_path}...")
    try:
        df_raw = pd.read_parquet(file_path)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        continue
        
    if 'timestamp' in df_raw.columns:
        df_raw['timestamp'] = pd.to_datetime(df_raw['timestamp'])
        df_raw.set_index('timestamp', inplace=True)
    elif not isinstance(df_raw.index, pd.DatetimeIndex):
        df_raw.index = pd.date_range(end=pd.Timestamp.now(), periods=len(df_raw), freq='1min')

    for tf in timeframes:
        pd_tf = tf_map.get(tf, "1min")
        if pd_tf != "1min":
            df_tf = df_raw.resample(pd_tf).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()
        else:
            df_tf = df_raw.copy()
            
        for strat_id, strat_name in strategies:
            df_curr = df_tf.copy()
            returns_series = apply_strategy(df_curr, strat_id)
            
            if len(returns_series) == 0:
                continue
                
            returns_series = returns_series.replace([np.inf, -np.inf], 0).fillna(0)
            wins = returns_series[returns_series > 0]
            losses = returns_series[returns_series < 0]
            
            win_rate = len(wins) / len(returns_series) if len(returns_series) > 0 else 0
            
            # Gross profit/loss in absolute terms (not just percentages)
            # The strategy logic in vectorized_backtest.py does: returns_series = df['next_return']
            # So the series is percentage returns.
            # To get USD, we apply it to a fixed size or compounding. The UI endpoint does:
            # end_capital = body.starting_capital * (1 + returns_series).prod()
            # To get gross profit and loss properly compounding, we can track equity over time.
            cumulative = (1 + returns_series).cumprod()
            equity_series = capital * cumulative
            
            # Dollar profit/loss per trade (approximate compounding)
            # Actually, standard gross profit is sum of winning trades in $.
            # Let's compute dollar returns per trade.
            eq_shifted = equity_series.shift(1).fillna(capital)
            dollar_returns = eq_shifted * returns_series
            
            dollar_wins = dollar_returns[dollar_returns > 0].sum()
            dollar_losses = abs(dollar_returns[dollar_returns < 0].sum())
            
            pf = dollar_wins / dollar_losses if dollar_losses > 0 else (99.9 if dollar_wins > 0 else 0.0)
            
            end_capital = equity_series.iloc[-1] if len(equity_series) > 0 else capital
            net_profit_usd = end_capital - capital
            net_return_pct = (net_profit_usd / capital) * 100
            
            # Expectancy: (WinRate * AvgWin) - (LossRate * AvgLoss) in percentage terms, or USD terms. Let's do USD terms.
            avg_win = dollar_returns[dollar_returns > 0].mean() if len(dollar_returns[dollar_returns > 0]) > 0 else 0
            avg_loss = abs(dollar_returns[dollar_returns < 0].mean()) if len(dollar_returns[dollar_returns < 0]) > 0 else 0
            expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
            
            sharpe = 0.0
            if len(returns_series) > 1 and returns_series.std() > 0:
                sharpe = np.sqrt(252) * returns_series.mean() / returns_series.std()
                
            results.append({
                'Symbol': sym.replace("USD", ""),
                'Timeframe': tf,
                'Strategy': strat_name,
                'Trades': len(returns_series),
                'Win Rate': win_rate,
                'Profit Factor': pf,
                'Expectancy': expectancy,
                'Gross Profit': dollar_wins,
                'Gross Loss': dollar_losses,
                'Net Return %': net_return_pct,
                'Net Profit $': net_profit_usd,
                'Sharpe': sharpe
            })

df_res = pd.DataFrame(results)
if len(df_res) == 0:
    print("No results.")
    sys.exit(0)
df_res = df_res.sort_values(by='Net Profit $', ascending=False)
top = df_res.head(20)

print("\n--- TOP 20 CONFIGS ---")
for idx, row in top.iterrows():
    print(f"{row['Strategy']} ({row['Symbol']} {row['Timeframe']}) | "
          f"WinRate: {row['Win Rate']*100:.1f}% | PF: {row['Profit Factor']:.2f} | "
          f"Exp: ${row['Expectancy']:.2f} | "
          f"Gross P: ${row['Gross Profit']:.2f} | Gross L: -${row['Gross Loss']:.2f} | "
          f"Net: {row['Net Return %']:.1f}% (${row['Net Profit $']:.2f})")

