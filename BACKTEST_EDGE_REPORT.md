# Sterling Edge-Discovery Backtest
_Generated 2026-05-30 11:21 UTC_  _Capital: $500  Fees: 0.10% round-trip  Max hold: 200 bars  Data: 2023-12-29 → 2026-05-30_

## Methodology
- **Data**: 1-minute OHLCV from `backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet`, resampled to 1m / 5m / 15m / 30m / 1h / 4h.
- **Strategies (long-only)**: MA Crossover (EMA 9/21), Mean Reversion (RSI(14) cross up from <30), Breakout (20-bar Donchian high), Price Action (bullish engulfing), SMC FVG (bullish fair-value gap).
- **Profiles**: SL/TP risk style applied as ATR multiples — **Scalping** SL 1.0 × ATR / TP 2.0 × ATR · **Intraday** SL 2.0 / TP 3.5 · **Aggressive** SL 1.5 / TP 4.5.
- **Exits**: bar-by-bar first-touch SL/TP simulation; time-stop after 200 bars if neither hit. Fee 0.10% round-trip.
- **Capital**: $500 nominal per trade, single-shot sequential (no overlapping positions). PnL compounds. Sharpe uses √252 scaling on per-trade returns.
- **Configs evaluated**: 270 (270 with ≥30 trades). Results CSV: `backtest_edge_results.csv`.

---

## 🏆 Top 20 by Bottom-Line PnL (Compounded $500)

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 2 | Price Action (1h) | BTCUSD | Intraday | 434 | 41.7% | 1.11 | 0.105% | 0.69 | -38.5% | $2388.67 | $2161.43 | +39.2% | $+196.22 |
| 3 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 4 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 5 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 6 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 7 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 8 | Price Action (1h) | BTCUSD | Aggressive | 431 | 29.0% | 1.06 | 0.060% | 0.39 | -39.9% | $2131.18 | $2002.22 | +14.4% | $+71.82 |
| 9 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 10 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 11 | Price Action (4h) | ETHUSD | Scalping | 161 | 35.4% | 1.04 | 0.060% | 0.27 | -34.6% | $1280.61 | $1232.30 | -0.2% | $-1.09 |
| 12 | Mean Reversion (4h) | BTCUSD | Intraday | 104 | 38.5% | 1.04 | 0.079% | 0.26 | -41.2% | $1113.32 | $1072.12 | -3.7% | $-18.43 |
| 13 | Price Action (4h) | BTCUSD | Intraday | 121 | 38.8% | 1.03 | 0.062% | 0.21 | -31.4% | $1268.70 | $1231.47 | -4.8% | $-24.24 |
| 14 | SMC FVG (4h) | BTCUSD | Scalping | 221 | 38.5% | 1.00 | 0.000% | 0.00 | -28.6% | $1122.99 | $1122.73 | -5.5% | $-27.46 |
| 15 | MA Crossover (1h) | BTCUSD | Intraday | 547 | 39.5% | 1.01 | 0.011% | 0.08 | -47.7% | $2631.03 | $2600.10 | -6.4% | $-32.13 |
| 16 | Breakout (4h) | BTCUSD | Scalping | 148 | 36.5% | 0.95 | -0.047% | -0.38 | -28.7% | $645.23 | $680.11 | -9.3% | $-46.63 |
| 17 | MA Crossover (1h) | BTCUSD | Aggressive | 590 | 28.1% | 1.01 | 0.005% | 0.04 | -47.2% | $2497.34 | $2483.46 | -9.4% | $-46.80 |
| 18 | SMC FVG (4h) | ETHUSD | Aggressive | 128 | 28.1% | 1.03 | 0.071% | 0.18 | -57.2% | $1732.75 | $1687.35 | -14.3% | $-71.65 |
| 19 | Mean Reversion (4h) | SOLUSD | Scalping | 133 | 35.3% | 0.98 | -0.046% | -0.18 | -42.6% | $1200.03 | $1230.79 | -16.0% | $-80.02 |
| 20 | Price Action (30m) | SOLUSD | Aggressive | 861 | 26.4% | 1.01 | 0.012% | 0.07 | -61.6% | $4551.89 | $4499.16 | -18.5% | $-92.69 |

## 📈 Top 15 by Sharpe (Risk-Adjusted Edge)

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 2 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 3 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 4 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 5 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 6 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 7 | Price Action (1h) | BTCUSD | Intraday | 434 | 41.7% | 1.11 | 0.105% | 0.69 | -38.5% | $2388.67 | $2161.43 | +39.2% | $+196.22 |
| 8 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 9 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 10 | Price Action (1h) | BTCUSD | Aggressive | 431 | 29.0% | 1.06 | 0.060% | 0.39 | -39.9% | $2131.18 | $2002.22 | +14.4% | $+71.82 |
| 11 | Price Action (4h) | ETHUSD | Scalping | 161 | 35.4% | 1.04 | 0.060% | 0.27 | -34.6% | $1280.61 | $1232.30 | -0.2% | $-1.09 |
| 12 | Mean Reversion (4h) | BTCUSD | Intraday | 104 | 38.5% | 1.04 | 0.079% | 0.26 | -41.2% | $1113.32 | $1072.12 | -3.7% | $-18.43 |
| 13 | Price Action (4h) | BTCUSD | Intraday | 121 | 38.8% | 1.03 | 0.062% | 0.21 | -31.4% | $1268.70 | $1231.47 | -4.8% | $-24.24 |
| 14 | SMC FVG (4h) | ETHUSD | Aggressive | 128 | 28.1% | 1.03 | 0.071% | 0.18 | -57.2% | $1732.75 | $1687.35 | -14.3% | $-71.65 |
| 15 | SMC FVG (4h) | SOLUSD | Intraday | 124 | 38.7% | 1.01 | 0.043% | 0.09 | -56.4% | $2110.40 | $2083.45 | -24.4% | $-121.80 |

## 💰 Top 15 by Profit Factor

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 2 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 3 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 4 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 5 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 6 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 7 | Price Action (1h) | BTCUSD | Intraday | 434 | 41.7% | 1.11 | 0.105% | 0.69 | -38.5% | $2388.67 | $2161.43 | +39.2% | $+196.22 |
| 8 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 9 | Price Action (1h) | BTCUSD | Aggressive | 431 | 29.0% | 1.06 | 0.060% | 0.39 | -39.9% | $2131.18 | $2002.22 | +14.4% | $+71.82 |
| 10 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 11 | Price Action (4h) | ETHUSD | Scalping | 161 | 35.4% | 1.04 | 0.060% | 0.27 | -34.6% | $1280.61 | $1232.30 | -0.2% | $-1.09 |
| 12 | Mean Reversion (4h) | BTCUSD | Intraday | 104 | 38.5% | 1.04 | 0.079% | 0.26 | -41.2% | $1113.32 | $1072.12 | -3.7% | $-18.43 |
| 13 | Price Action (4h) | BTCUSD | Intraday | 121 | 38.8% | 1.03 | 0.062% | 0.21 | -31.4% | $1268.70 | $1231.47 | -4.8% | $-24.24 |
| 14 | SMC FVG (4h) | ETHUSD | Aggressive | 128 | 28.1% | 1.03 | 0.071% | 0.18 | -57.2% | $1732.75 | $1687.35 | -14.3% | $-71.65 |
| 15 | SMC FVG (4h) | SOLUSD | Intraday | 124 | 38.7% | 1.01 | 0.043% | 0.09 | -56.4% | $2110.40 | $2083.45 | -24.4% | $-121.80 |

## 🎯 Top 15 by Expectancy per Trade

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 2 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 3 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 4 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 5 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 6 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 7 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 8 | Price Action (1h) | BTCUSD | Intraday | 434 | 41.7% | 1.11 | 0.105% | 0.69 | -38.5% | $2388.67 | $2161.43 | +39.2% | $+196.22 |
| 9 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 10 | Mean Reversion (4h) | BTCUSD | Intraday | 104 | 38.5% | 1.04 | 0.079% | 0.26 | -41.2% | $1113.32 | $1072.12 | -3.7% | $-18.43 |
| 11 | SMC FVG (4h) | ETHUSD | Aggressive | 128 | 28.1% | 1.03 | 0.071% | 0.18 | -57.2% | $1732.75 | $1687.35 | -14.3% | $-71.65 |
| 12 | Price Action (4h) | BTCUSD | Intraday | 121 | 38.8% | 1.03 | 0.062% | 0.21 | -31.4% | $1268.70 | $1231.47 | -4.8% | $-24.24 |
| 13 | Price Action (4h) | ETHUSD | Scalping | 161 | 35.4% | 1.04 | 0.060% | 0.27 | -34.6% | $1280.61 | $1232.30 | -0.2% | $-1.09 |
| 14 | Price Action (1h) | BTCUSD | Aggressive | 431 | 29.0% | 1.06 | 0.060% | 0.39 | -39.9% | $2131.18 | $2002.22 | +14.4% | $+71.82 |
| 15 | SMC FVG (4h) | SOLUSD | Intraday | 124 | 38.7% | 1.01 | 0.043% | 0.09 | -56.4% | $2110.40 | $2083.45 | -24.4% | $-121.80 |

## 🥇 Composite Winner (avg rank of PnL + Sharpe + PF)

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 2 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 3 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 4 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 5 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 6 | Price Action (1h) | BTCUSD | Intraday | 434 | 41.7% | 1.11 | 0.105% | 0.69 | -38.5% | $2388.67 | $2161.43 | +39.2% | $+196.22 |
| 7 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 8 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 9 | Price Action (1h) | BTCUSD | Aggressive | 431 | 29.0% | 1.06 | 0.060% | 0.39 | -39.9% | $2131.18 | $2002.22 | +14.4% | $+71.82 |
| 10 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |

## Best by BTCUSD

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 2 | Price Action (1h) | BTCUSD | Intraday | 434 | 41.7% | 1.11 | 0.105% | 0.69 | -38.5% | $2388.67 | $2161.43 | +39.2% | $+196.22 |
| 3 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 4 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 5 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |

## Best by ETHUSD

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 2 | Price Action (4h) | ETHUSD | Scalping | 161 | 35.4% | 1.04 | 0.060% | 0.27 | -34.6% | $1280.61 | $1232.30 | -0.2% | $-1.09 |
| 3 | SMC FVG (4h) | ETHUSD | Aggressive | 128 | 28.1% | 1.03 | 0.071% | 0.18 | -57.2% | $1732.75 | $1687.35 | -14.3% | $-71.65 |
| 4 | Breakout (4h) | ETHUSD | Scalping | 151 | 31.8% | 0.91 | -0.121% | -0.71 | -34.3% | $873.71 | $965.07 | -21.1% | $-105.59 |
| 5 | Breakout (1h) | ETHUSD | Scalping | 522 | 35.4% | 0.95 | -0.035% | -0.38 | -28.2% | $1666.79 | $1758.82 | -21.4% | $-106.76 |

## Best by SOLUSD

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | Max DD | Gross Profit | Gross Loss | Net Return | Bottom-Line Portfolio Impact (USD Value) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 2 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 3 | Mean Reversion (4h) | SOLUSD | Scalping | 133 | 35.3% | 0.98 | -0.046% | -0.18 | -42.6% | $1200.03 | $1230.79 | -16.0% | $-80.02 |
| 4 | Price Action (30m) | SOLUSD | Aggressive | 861 | 26.4% | 1.01 | 0.012% | 0.07 | -61.6% | $4551.89 | $4499.16 | -18.5% | $-92.69 |
| 5 | Price Action (4h) | SOLUSD | Scalping | 163 | 33.7% | 0.97 | -0.059% | -0.24 | -40.6% | $1350.94 | $1399.40 | -19.7% | $-98.49 |

## Profile Roll-Up (median across configs with ≥30 trades)

| profile | trades | win_rate | pf | sharpe | expectancy | net_return | pnl_usd | max_dd |
|---|---|---|---|---|---|---|---|---|
| Aggressive | 1285.5000 | 0.2552 | 0.8487 | -1.0496 | -0.0010 | -0.7367 | -368.3358 | -0.7960 |
| Intraday | 1257.5000 | 0.3612 | 0.8591 | -1.0476 | -0.0010 | -0.7807 | -390.3375 | -0.8023 |
| Scalping | 2027.0000 | 0.3280 | 0.7529 | -1.9294 | -0.0010 | -0.9050 | -452.4770 | -0.9110 |

## Strategy Roll-Up (median across configs with ≥30 trades)

| strategy | trades | win_rate | pf | sharpe | expectancy | net_return | pnl_usd | max_dd |
|---|---|---|---|---|---|---|---|---|
| Breakout | 1277.0000 | 0.3186 | 0.7748 | -1.7455 | -0.0010 | -0.7503 | -375.1644 | -0.7629 |
| MA Crossover | 2291.0000 | 0.3337 | 0.8582 | -1.0379 | -0.0009 | -0.8491 | -424.5717 | -0.8636 |
| Mean Reversion | 1190.5000 | 0.3165 | 0.8004 | -1.4462 | -0.0010 | -0.7906 | -395.2936 | -0.8336 |
| Price Action | 1513.0000 | 0.3303 | 0.8257 | -1.2496 | -0.0010 | -0.7791 | -389.5314 | -0.8024 |
| SMC FVG | 1841.0000 | 0.3273 | 0.8346 | -1.2398 | -0.0010 | -0.8346 | -417.2796 | -0.8566 |

## Timeframe Roll-Up (median across configs with ≥30 trades)

| tf | trades | win_rate | pf | sharpe | expectancy | net_return | pnl_usd | max_dd |
|---|---|---|---|---|---|---|---|---|
| 15m | 1933.0000 | 0.3313 | 0.8352 | -1.2130 | -0.0009 | -0.8683 | -434.1344 | -0.8888 |
| 1h | 507.0000 | 0.3280 | 0.9080 | -0.6705 | -0.0010 | -0.5317 | -265.8646 | -0.6235 |
| 1m | 33824.0000 | 0.2779 | 0.3792 | -6.2846 | -0.0010 | -1.0000 | -500.0000 | -1.0000 |
| 30m | 987.0000 | 0.3289 | 0.8718 | -0.9238 | -0.0008 | -0.6453 | -322.6302 | -0.7284 |
| 4h | 128.0000 | 0.3357 | 0.9197 | -0.5879 | -0.0012 | -0.2640 | -131.9762 | -0.5222 |
| 5m | 6802.0000 | 0.3286 | 0.6850 | -2.4396 | -0.0010 | -0.9989 | -499.4299 | -0.9989 |

