import time
import os
import numpy as np
import pandas as pd
import ta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/vectorized", tags=["vectorized_backtest"])

class VectorizedBacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    strategy: str
    profile: str
    starting_capital: float = 500.0

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

@router.post("/run")
async def run_vectorized_endpoint(body: VectorizedBacktestRequest, request: Request):
    t0 = time.time()
    sym = body.symbol.upper()
    if not sym.endswith("USD"):
        sym += "USD"
    file_path = f"vector_store_1m_{sym}.parquet"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"Parquet file {file_path} not found.")
        
    df = pd.read_parquet(file_path)
    
    # Resample if not 1m
    tf_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "45m": "45min", "1h": "1h", "2h": "2h", "4h": "4h"}
    pd_tf = tf_map.get(body.timeframe, "1min")
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
        # Fallback to dummy DatetimeIndex
        df.index = pd.date_range(end=pd.Timestamp.now(), periods=len(df), freq='1min')

    if pd_tf != "1min":
        df = df.resample(pd_tf).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
    returns_series = apply_strategy(df, body.strategy)
    
    # Calculate metrics
    if len(returns_series) == 0:
        return {"metrics": {"Trades": 0, "PF": 0.0, "Win Rate": 0.0, "Sharpe": 0.0, "End Capital": body.starting_capital}, "equity_curve": [], "time_taken": time.time() - t0}
        
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
    
    # Build equity curve
    cumulative = (1 + returns_series).cumprod()
    equity_series = body.starting_capital * cumulative
    
    # Downsample equity curve for UI performance (max 500 points)
    if len(equity_series) > 500:
        step = len(equity_series) // 500
        equity_series = equity_series.iloc[::step]
        
    curve_data = [{"time": str(idx), "value": val} for idx, val in equity_series.items()]
    end_capital = body.starting_capital * (1 + returns_series).prod()
    
    metrics = {
        "Trades": len(returns_series),
        "PF": pf,
        "Win Rate": win_rate,
        "Sharpe": sharpe,
        "End Capital": end_capital
    }
    
    return {
        "metrics": metrics,
        "equity_curve": curve_data,
        "time_taken": time.time() - t0
    }
