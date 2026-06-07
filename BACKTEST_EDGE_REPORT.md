# Sterling Edge-Discovery Backtest
_Generated 2026-06-07 07:12 UTC_  _Capital: $500  Fees: 0.10% round-trip  Max hold: 200 bars  Data: 2023-12-29 → 2026-05-30_

## Methodology
- **Data**: 1-minute OHLCV from `backend/vector_store_1m_{BTC,ETH,SOL}USD.parquet`, resampled to 1m / 5m / 15m / 30m / 1h / 4h.
- **Strategies (long-only)**: MA Crossover (EMA 9/21), Mean Reversion (RSI(14) cross up from <30), Breakout (20-bar Donchian high), Price Action (bullish engulfing), SMC FVG (bullish fair-value gap).
- **Profiles**: SL/TP risk style applied as ATR multiples — **Scalping** SL 1.0 × ATR / TP 2.0 × ATR · **Intraday** SL 2.0 / TP 3.5 · **Aggressive** SL 1.5 / TP 4.5.
- **Exits**: bar-by-bar first-touch SL/TP simulation; time-stop after 200 bars if neither hit. Fee 0.10% round-trip.
- **Capital**: $500 nominal per trade, single-shot sequential (no overlapping positions). PnL compounds. Sharpe uses √252 scaling on per-trade returns.
- **Configs evaluated**: 630 (630 with ≥30 trades). Results CSV: `backtest_edge_results.csv`.

---

## 🏆 Top 20 by Bottom-Line PnL (Compounded $500)

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | 91 | 31.9% | 1.53 | 0.897% | 2.63 | 0.02 | 84.4% | 49.1% | 0.09 | -18.8% | $1173.08 | $764.75 | +99.1% | $+495.49 |
| 2 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -0.10 | 97.5% | 50.4% | 0.06 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 3 | BB RSI Mean Reversion (4h) | BTCUSD | Intraday | 92 | 43.5% | 1.40 | 0.742% | 2.31 | 0.02 | 87.6% | 48.4% | 0.05 | -23.7% | $1199.47 | $858.11 | +76.1% | $+380.57 |
| 4 | VWAP Cross (4h) | BTCUSD | Intraday | 94 | 42.6% | 1.30 | 0.512% | 1.82 | -0.08 | 85.0% | 51.0% | 0.02 | -24.5% | $1049.05 | $808.57 | +47.6% | $+238.21 |
| 5 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -0.07 | 96.1% | 51.9% | 0.01 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 6 | Price Action (1h) | BTCUSD | Intraday | 433 | 41.6% | 1.10 | 0.104% | 0.68 | -0.05 | 97.9% | 49.9% | 0.01 | -38.5% | $2386.05 | $2161.43 | +38.5% | $+192.59 |
| 7 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -0.28 | 86.1% | 51.3% | 0.01 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 8 | Breakout (4h) | BTCUSD | Scale_Out_2R | 98 | 60.2% | 1.25 | 0.285% | 1.51 | -0.26 | 60.0% | 48.7% | 0.01 | -21.9% | $703.10 | $563.30 | +26.6% | $+132.94 |
| 9 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -0.23 | 98.3% | 48.3% | 0.01 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 10 | MA Crossover (4h) | BTCUSD | Scale_Out_2R | 181 | 54.7% | 1.13 | 0.176% | 0.83 | -0.09 | 94.5% | 52.0% | 0.01 | -35.8% | $1386.46 | $1227.40 | +24.4% | $+121.89 |
| 11 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -0.11 | 100.0% | 47.4% | 0.01 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 12 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -0.17 | 99.2% | 48.8% | 0.01 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 13 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | 108 | 35.2% | 1.14 | 0.223% | 0.88 | -0.04 | 91.7% | 51.3% | 0.01 | -24.6% | $988.83 | $868.20 | +17.1% | $+85.28 |
| 14 | Price Action (1h) | BTCUSD | Aggressive | 430 | 28.8% | 1.06 | 0.059% | 0.38 | -0.14 | 99.2% | 48.1% | 0.00 | -39.9% | $2128.55 | $2002.22 | +13.8% | $+68.84 |
| 15 | BB RSI Mean Reversion (4h) | BTCUSD | Scalping | 115 | 35.7% | 1.12 | 0.124% | 0.74 | -0.04 | 67.4% | 48.5% | 0.00 | -16.0% | $689.45 | $618.00 | +10.9% | $+54.48 |
| 16 | VWAP Cross (4h) | BTCUSD | Scale_Out_2R | 102 | 51.0% | 1.09 | 0.129% | 0.58 | -0.14 | 87.3% | 50.1% | 0.00 | -25.4% | $807.30 | $741.57 | +7.2% | $+35.79 |
| 17 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -0.24 | 99.7% | 50.5% | 0.00 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 18 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -0.12 | 98.1% | 47.5% | 0.00 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 19 | VWAP Cross (4h) | BTCUSD | Scalping | 143 | 38.5% | 1.06 | 0.062% | 0.44 | -0.05 | 70.9% | 50.4% | 0.00 | -16.4% | $733.40 | $689.40 | +5.4% | $+27.20 |
| 20 | BB RSI Mean Reversion (4h) | BTCUSD | Scale_Out_2R | 99 | 53.5% | 1.08 | 0.123% | 0.52 | -0.10 | 89.8% | 46.7% | 0.00 | -26.4% | $818.04 | $757.08 | +5.4% | $+27.15 |

## 📈 Top 15 by Sharpe (Risk-Adjusted Edge)

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | 91 | 31.9% | 1.53 | 0.897% | 2.63 | 0.02 | 84.4% | 49.1% | 0.09 | -18.8% | $1173.08 | $764.75 | +99.1% | $+495.49 |
| 2 | BB RSI Mean Reversion (4h) | BTCUSD | Intraday | 92 | 43.5% | 1.40 | 0.742% | 2.31 | 0.02 | 87.6% | 48.4% | 0.05 | -23.7% | $1199.47 | $858.11 | +76.1% | $+380.57 |
| 3 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -0.10 | 97.5% | 50.4% | 0.06 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 4 | VWAP Cross (4h) | BTCUSD | Intraday | 94 | 42.6% | 1.30 | 0.512% | 1.82 | -0.08 | 85.0% | 51.0% | 0.02 | -24.5% | $1049.05 | $808.57 | +47.6% | $+238.21 |
| 5 | Breakout (4h) | BTCUSD | Scale_Out_2R | 98 | 60.2% | 1.25 | 0.285% | 1.51 | -0.26 | 60.0% | 48.7% | 0.01 | -21.9% | $703.10 | $563.30 | +26.6% | $+132.94 |
| 6 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -0.28 | 86.1% | 51.3% | 0.01 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 7 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -0.07 | 96.1% | 51.9% | 0.01 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 8 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -0.11 | 100.0% | 47.4% | 0.01 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 9 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -0.23 | 98.3% | 48.3% | 0.01 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 10 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | 108 | 35.2% | 1.14 | 0.223% | 0.88 | -0.04 | 91.7% | 51.3% | 0.01 | -24.6% | $988.83 | $868.20 | +17.1% | $+85.28 |
| 11 | MA Crossover (4h) | BTCUSD | Scale_Out_2R | 181 | 54.7% | 1.13 | 0.176% | 0.83 | -0.09 | 94.5% | 52.0% | 0.01 | -35.8% | $1386.46 | $1227.40 | +24.4% | $+121.89 |
| 12 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -0.17 | 99.2% | 48.8% | 0.01 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 13 | BB RSI Mean Reversion (4h) | BTCUSD | Scalping | 115 | 35.7% | 1.12 | 0.124% | 0.74 | -0.04 | 67.4% | 48.5% | 0.00 | -16.0% | $689.45 | $618.00 | +10.9% | $+54.48 |
| 14 | Price Action (1h) | BTCUSD | Intraday | 433 | 41.6% | 1.10 | 0.104% | 0.68 | -0.05 | 97.9% | 49.9% | 0.01 | -38.5% | $2386.05 | $2161.43 | +38.5% | $+192.59 |
| 15 | VWAP Cross (4h) | BTCUSD | Scale_Out_2R | 102 | 51.0% | 1.09 | 0.129% | 0.58 | -0.14 | 87.3% | 50.1% | 0.00 | -25.4% | $807.30 | $741.57 | +7.2% | $+35.79 |

## 💰 Top 15 by Profit Factor

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | 91 | 31.9% | 1.53 | 0.897% | 2.63 | 0.02 | 84.4% | 49.1% | 0.09 | -18.8% | $1173.08 | $764.75 | +99.1% | $+495.49 |
| 2 | BB RSI Mean Reversion (4h) | BTCUSD | Intraday | 92 | 43.5% | 1.40 | 0.742% | 2.31 | 0.02 | 87.6% | 48.4% | 0.05 | -23.7% | $1199.47 | $858.11 | +76.1% | $+380.57 |
| 3 | VWAP Cross (4h) | BTCUSD | Intraday | 94 | 42.6% | 1.30 | 0.512% | 1.82 | -0.08 | 85.0% | 51.0% | 0.02 | -24.5% | $1049.05 | $808.57 | +47.6% | $+238.21 |
| 4 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -0.10 | 97.5% | 50.4% | 0.06 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 5 | Breakout (4h) | BTCUSD | Scale_Out_2R | 98 | 60.2% | 1.25 | 0.285% | 1.51 | -0.26 | 60.0% | 48.7% | 0.01 | -21.9% | $703.10 | $563.30 | +26.6% | $+132.94 |
| 6 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -0.28 | 86.1% | 51.3% | 0.01 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 7 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -0.11 | 100.0% | 47.4% | 0.01 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 8 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -0.07 | 96.1% | 51.9% | 0.01 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 9 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | 108 | 35.2% | 1.14 | 0.223% | 0.88 | -0.04 | 91.7% | 51.3% | 0.01 | -24.6% | $988.83 | $868.20 | +17.1% | $+85.28 |
| 10 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -0.23 | 98.3% | 48.3% | 0.01 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 11 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -0.17 | 99.2% | 48.8% | 0.01 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 12 | MA Crossover (4h) | BTCUSD | Scale_Out_2R | 181 | 54.7% | 1.13 | 0.176% | 0.83 | -0.09 | 94.5% | 52.0% | 0.01 | -35.8% | $1386.46 | $1227.40 | +24.4% | $+121.89 |
| 13 | BB RSI Mean Reversion (4h) | BTCUSD | Scalping | 115 | 35.7% | 1.12 | 0.124% | 0.74 | -0.04 | 67.4% | 48.5% | 0.00 | -16.0% | $689.45 | $618.00 | +10.9% | $+54.48 |
| 14 | Price Action (1h) | BTCUSD | Intraday | 433 | 41.6% | 1.10 | 0.104% | 0.68 | -0.05 | 97.9% | 49.9% | 0.01 | -38.5% | $2386.05 | $2161.43 | +38.5% | $+192.59 |
| 15 | VWAP Cross (4h) | BTCUSD | Scale_Out_2R | 102 | 51.0% | 1.09 | 0.129% | 0.58 | -0.14 | 87.3% | 50.1% | 0.00 | -25.4% | $807.30 | $741.57 | +7.2% | $+35.79 |

## 🎯 Top 15 by Expectancy per Trade

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | 91 | 31.9% | 1.53 | 0.897% | 2.63 | 0.02 | 84.4% | 49.1% | 0.09 | -18.8% | $1173.08 | $764.75 | +99.1% | $+495.49 |
| 2 | BB RSI Mean Reversion (4h) | BTCUSD | Intraday | 92 | 43.5% | 1.40 | 0.742% | 2.31 | 0.02 | 87.6% | 48.4% | 0.05 | -23.7% | $1199.47 | $858.11 | +76.1% | $+380.57 |
| 3 | VWAP Cross (4h) | BTCUSD | Intraday | 94 | 42.6% | 1.30 | 0.512% | 1.82 | -0.08 | 85.0% | 51.0% | 0.02 | -24.5% | $1049.05 | $808.57 | +47.6% | $+238.21 |
| 4 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -0.10 | 97.5% | 50.4% | 0.06 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 5 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -0.11 | 100.0% | 47.4% | 0.01 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 6 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -0.28 | 86.1% | 51.3% | 0.01 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 7 | Breakout (4h) | BTCUSD | Scale_Out_2R | 98 | 60.2% | 1.25 | 0.285% | 1.51 | -0.26 | 60.0% | 48.7% | 0.01 | -21.9% | $703.10 | $563.30 | +26.6% | $+132.94 |
| 8 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -0.23 | 98.3% | 48.3% | 0.01 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 9 | MA Crossover (4h) | BTCUSD | Aggressive | 156 | 28.2% | 1.14 | 0.234% | 0.83 | -0.17 | 99.2% | 48.8% | 0.01 | -43.5% | $1524.60 | $1342.31 | +23.9% | $+119.29 |
| 10 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | 108 | 35.2% | 1.14 | 0.223% | 0.88 | -0.04 | 91.7% | 51.3% | 0.01 | -24.6% | $988.83 | $868.20 | +17.1% | $+85.28 |
| 11 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -0.07 | 96.1% | 51.9% | 0.01 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 12 | MA Crossover (4h) | BTCUSD | Scale_Out_2R | 181 | 54.7% | 1.13 | 0.176% | 0.83 | -0.09 | 94.5% | 52.0% | 0.01 | -35.8% | $1386.46 | $1227.40 | +24.4% | $+121.89 |
| 13 | VWAP Cross (4h) | BTCUSD | Scale_Out_2R | 102 | 51.0% | 1.09 | 0.129% | 0.58 | -0.14 | 87.3% | 50.1% | 0.00 | -25.4% | $807.30 | $741.57 | +7.2% | $+35.79 |
| 14 | SMC FVG (4h) | BTCUSD | Aggressive | 135 | 30.4% | 1.07 | 0.128% | 0.48 | -0.12 | 98.1% | 47.5% | 0.00 | -39.8% | $1255.52 | $1168.84 | +5.7% | $+28.49 |
| 15 | BB RSI Mean Reversion (4h) | BTCUSD | Scalping | 115 | 35.7% | 1.12 | 0.124% | 0.74 | -0.04 | 67.4% | 48.5% | 0.00 | -16.0% | $689.45 | $618.00 | +10.9% | $+54.48 |

## 🥇 Composite Winner (avg rank of PnL + Sharpe + PF)

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | 91 | 31.9% | 1.53 | 0.897% | 2.63 | 0.02 | 84.4% | 49.1% | 0.09 | -18.8% | $1173.08 | $764.75 | +99.1% | $+495.49 |
| 2 | BB RSI Mean Reversion (4h) | BTCUSD | Intraday | 92 | 43.5% | 1.40 | 0.742% | 2.31 | 0.02 | 87.6% | 48.4% | 0.05 | -23.7% | $1199.47 | $858.11 | +76.1% | $+380.57 |
| 3 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -0.10 | 97.5% | 50.4% | 0.06 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 4 | VWAP Cross (4h) | BTCUSD | Intraday | 94 | 42.6% | 1.30 | 0.512% | 1.82 | -0.08 | 85.0% | 51.0% | 0.02 | -24.5% | $1049.05 | $808.57 | +47.6% | $+238.21 |
| 5 | Breakout (4h) | BTCUSD | Scale_Out_2R | 98 | 60.2% | 1.25 | 0.285% | 1.51 | -0.26 | 60.0% | 48.7% | 0.01 | -21.9% | $703.10 | $563.30 | +26.6% | $+132.94 |
| 6 | Breakout (4h) | BTCUSD | Intraday | 100 | 42.0% | 1.20 | 0.317% | 1.31 | -0.28 | 86.1% | 51.3% | 0.01 | -28.1% | $962.56 | $803.85 | +27.7% | $+138.49 |
| 7 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -0.07 | 96.1% | 51.9% | 0.01 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 8 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -0.11 | 100.0% | 47.4% | 0.01 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 9 | SMC FVG (4h) | BTCUSD | Intraday | 149 | 40.9% | 1.14 | 0.257% | 0.90 | -0.23 | 98.3% | 48.3% | 0.01 | -44.4% | $1589.80 | $1398.45 | +26.3% | $+131.31 |
| 10 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | 108 | 35.2% | 1.14 | 0.223% | 0.88 | -0.04 | 91.7% | 51.3% | 0.01 | -24.6% | $988.83 | $868.20 | +17.1% | $+85.28 |

## 🪙 Strategy vs. Buy-and-Hold (the missing benchmark)

**44 of 630** configs (≥30 trades) beat buy-and-hold on BOTH return and drawdown. Everything else is a worse way to hold the asset.

| # | Strategy (TF) | Symbol | Profile | Strat Net | HODL Net | Excess | Strat MaxDD | HODL MaxDD |
|---|---|---|---|---|---|---|---|---|
| 1 | SMC FVG (4h) | SOLUSD | Aggressive | +24.4% | -54.6% | +78.9% | -50.5% | -73.2% |
| 2 | SMC FVG (4h) | SOLUSD | Scalping | +6.4% | -54.6% | +61.0% | -52.9% | -73.2% |
| 3 | BB RSI Mean Reversion (4h) | SOLUSD | Scalping | -1.1% | -54.6% | +53.4% | -33.6% | -73.2% |
| 4 | SMC FVG (4h) | ETHUSD | Scalping | +38.6% | -13.6% | +52.2% | -33.1% | -65.2% |
| 5 | Mean Reversion (4h) | SOLUSD | Scalping | -17.5% | -54.6% | +37.1% | -42.6% | -73.2% |
| 6 | Price Action (30m) | SOLUSD | Aggressive | -18.5% | -54.6% | +36.0% | -61.6% | -75.6% |
| 7 | Price Action (4h) | SOLUSD | Scalping | -19.4% | -54.6% | +35.1% | -40.6% | -73.2% |
| 8 | Breakout (4h) | SOLUSD | Intraday | -21.3% | -54.6% | +33.3% | -53.1% | -73.2% |
| 9 | VWAP Cross (30m) | SOLUSD | Scalping | -21.7% | -54.6% | +32.9% | -37.0% | -75.6% |
| 10 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | +17.1% | -13.6% | +30.7% | -24.6% | -65.2% |
| 11 | SMC FVG (4h) | SOLUSD | Intraday | -24.4% | -54.6% | +30.2% | -56.4% | -73.2% |
| 12 | Mean Reversion (4h) | SOLUSD | Aggressive | -26.2% | -54.6% | +28.4% | -53.5% | -73.2% |
| 13 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | +99.1% | +72.1% | +27.0% | -18.8% | -49.8% |
| 14 | VWAP Cross (30m) | SOLUSD | Scale_Out_2R | -28.2% | -54.6% | +26.3% | -42.0% | -75.6% |
| 15 | VWAP Cross (4h) | SOLUSD | Scalping | -29.6% | -54.6% | +24.9% | -47.5% | -73.2% |
| 16 | Breakout (4h) | SOLUSD | Scalping | -30.1% | -54.6% | +24.4% | -43.9% | -73.2% |
| 17 | MA Crossover (4h) | BTCUSD | Intraday | +95.3% | +72.1% | +23.2% | -27.2% | -49.8% |
| 18 | MA Crossover (1h) | SOLUSD | Aggressive | -31.4% | -54.6% | +23.1% | -68.6% | -73.6% |
| 19 | BB RSI Mean Reversion (1h) | SOLUSD | Scale_Out_2R | -32.6% | -54.6% | +21.9% | -56.9% | -73.6% |
| 20 | VWAP Cross (30m) | SOLUSD | Aggressive | -36.2% | -54.6% | +18.4% | -52.8% | -75.6% |

## Best by BTCUSD

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | BB RSI Mean Reversion (4h) | BTCUSD | Aggressive | 91 | 31.9% | 1.53 | 0.897% | 2.63 | 0.02 | 84.4% | 49.1% | 0.09 | -18.8% | $1173.08 | $764.75 | +99.1% | $+495.49 |
| 2 | MA Crossover (4h) | BTCUSD | Intraday | 166 | 43.4% | 1.29 | 0.493% | 1.83 | -0.10 | 97.5% | 50.4% | 0.06 | -27.2% | $1807.89 | $1398.80 | +95.3% | $+476.37 |
| 3 | BB RSI Mean Reversion (4h) | BTCUSD | Intraday | 92 | 43.5% | 1.40 | 0.742% | 2.31 | 0.02 | 87.6% | 48.4% | 0.05 | -23.7% | $1199.47 | $858.11 | +76.1% | $+380.57 |
| 4 | VWAP Cross (4h) | BTCUSD | Intraday | 94 | 42.6% | 1.30 | 0.512% | 1.82 | -0.08 | 85.0% | 51.0% | 0.02 | -24.5% | $1049.05 | $808.57 | +47.6% | $+238.21 |
| 5 | Price Action (1h) | BTCUSD | Intraday | 433 | 41.6% | 1.10 | 0.104% | 0.68 | -0.05 | 97.9% | 49.9% | 0.01 | -38.5% | $2386.05 | $2161.43 | +38.5% | $+192.59 |

## Best by ETHUSD

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMC FVG (4h) | ETHUSD | Scalping | 220 | 39.5% | 1.15 | 0.202% | 0.97 | -0.07 | 96.1% | 51.9% | 0.01 | -33.1% | $1757.87 | $1535.19 | +38.6% | $+193.05 |
| 2 | BB RSI Mean Reversion (4h) | ETHUSD | Scalping | 108 | 35.2% | 1.14 | 0.223% | 0.88 | -0.04 | 91.7% | 51.3% | 0.01 | -24.6% | $988.83 | $868.20 | +17.1% | $+85.28 |
| 3 | Price Action (4h) | ETHUSD | Scalping | 161 | 35.4% | 1.04 | 0.060% | 0.27 | -0.18 | 97.8% | 52.8% | 0.00 | -34.6% | $1280.61 | $1232.30 | -0.2% | $-1.09 |
| 4 | VWAP Cross (4h) | ETHUSD | Scalping | 153 | 34.0% | 1.00 | -0.002% | -0.01 | -0.07 | 96.3% | 46.3% | 0.00 | -37.5% | $1043.26 | $1045.13 | -6.9% | $-34.73 |
| 5 | SMC FVG (4h) | ETHUSD | Aggressive | 128 | 28.1% | 1.03 | 0.071% | 0.18 | -0.28 | 100.0% | 50.4% | 0.00 | -57.2% | $1732.75 | $1687.35 | -14.3% | $-71.65 |

## Best by SOLUSD

| # | Strategy (Timeframe Configuration) | Symbol | Strategy Profile | Trades | Win Rate | Profit Factor | Expectancy | Sharpe | OOS Sharpe | P(Loss) | P(Sup) | DSR | Max DD | Gross Profit | Gross Loss | Net Return | Portfolio Impact (USD) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMC FVG (4h) | SOLUSD | Aggressive | 123 | 28.5% | 1.15 | 0.443% | 0.94 | -0.11 | 100.0% | 47.4% | 0.01 | -50.5% | $2050.33 | $1777.59 | +24.4% | $+121.81 |
| 2 | SMC FVG (4h) | SOLUSD | Scalping | 196 | 38.3% | 1.06 | 0.103% | 0.43 | -0.24 | 99.7% | 50.5% | 0.00 | -52.9% | $1736.17 | $1634.99 | +6.4% | $+32.18 |
| 3 | BB RSI Mean Reversion (4h) | SOLUSD | Scalping | 115 | 33.0% | 1.05 | 0.091% | 0.32 | -0.08 | 98.5% | 49.3% | 0.00 | -33.6% | $1167.65 | $1115.33 | -1.1% | $-5.53 |
| 4 | Mean Reversion (4h) | SOLUSD | Scalping | 132 | 34.8% | 0.97 | -0.060% | -0.23 | -0.17 | 99.6% | 46.1% | 0.00 | -42.6% | $1191.19 | $1230.79 | -17.5% | $-87.32 |
| 5 | Price Action (30m) | SOLUSD | Aggressive | 861 | 26.4% | 1.01 | 0.012% | 0.07 | -0.04 | 100.0% | 51.5% | 0.00 | -61.6% | $4551.89 | $4499.16 | -18.5% | $-92.69 |

## Profile Roll-Up (median across configs with ≥30 trades)

| profile | trades | win_rate | pf | sharpe | expectancy | net_return | pnl_usd | max_dd |
|---|---|---|---|---|---|---|---|---|
| Aggressive | 1231.0000 | 0.2560 | 0.8402 | -1.1094 | -0.0009 | -0.7021 | -351.0606 | -0.7659 |
| Intraday | 1188.5000 | 0.3615 | 0.8535 | -1.1019 | -0.0010 | -0.7621 | -381.0582 | -0.7734 |
| Intraday_Trailing | 1936.0000 | 0.2743 | 0.3878 | -5.6181 | -0.0022 | -0.9887 | -494.3599 | -0.9888 |
| Scale_Out_2R | 1298.5000 | 0.4848 | 0.7704 | -1.7320 | -0.0011 | -0.8356 | -417.7778 | -0.8554 |
| Scalping | 1814.5000 | 0.3290 | 0.7553 | -1.9180 | -0.0010 | -0.8640 | -431.9821 | -0.8771 |

## Strategy Roll-Up (median across configs with ≥30 trades)

| strategy | trades | win_rate | pf | sharpe | expectancy | net_return | pnl_usd | max_dd |
|---|---|---|---|---|---|---|---|---|
| BB RSI Mean Reversion | 1062.0000 | 0.3251 | 0.7451 | -2.0300 | -0.0011 | -0.8253 | -412.6329 | -0.8337 |
| Breakout | 1315.0000 | 0.3182 | 0.7083 | -2.3549 | -0.0012 | -0.8457 | -422.8518 | -0.8463 |
| MA Crossover | 2428.5000 | 0.3324 | 0.7901 | -1.6506 | -0.0010 | -0.9597 | -479.8336 | -0.9643 |
| Mean Reversion | 1197.0000 | 0.3183 | 0.7449 | -1.9110 | -0.0011 | -0.8498 | -424.8789 | -0.8682 |
| Price Action | 1583.5000 | 0.3303 | 0.7517 | -1.8339 | -0.0010 | -0.8878 | -443.8768 | -0.8979 |
| SMC FVG | 1925.0000 | 0.3263 | 0.7785 | -1.6159 | -0.0010 | -0.9102 | -455.1043 | -0.9173 |
| VWAP Cross | 1321.5000 | 0.3392 | 0.7810 | -1.6376 | -0.0009 | -0.6547 | -327.3423 | -0.6992 |

## Timeframe Roll-Up (median across configs with ≥30 trades)

| tf | trades | win_rate | pf | sharpe | expectancy | net_return | pnl_usd | max_dd |
|---|---|---|---|---|---|---|---|---|
| 15m | 1873.0000 | 0.3341 | 0.7848 | -1.6032 | -0.0011 | -0.8865 | -443.2483 | -0.8989 |
| 1h | 499.0000 | 0.3280 | 0.8571 | -1.0318 | -0.0014 | -0.5863 | -293.1548 | -0.6553 |
| 1m | 31158.0000 | 0.2659 | 0.3428 | -6.9375 | -0.0010 | -1.0000 | -500.0000 | -1.0000 |
| 30m | 964.0000 | 0.3301 | 0.8453 | -1.1206 | -0.0010 | -0.6953 | -347.6742 | -0.7408 |
| 4h | 124.0000 | 0.3465 | 0.8696 | -0.9836 | -0.0027 | -0.3894 | -194.6773 | -0.5307 |
| 5m | 6004.0000 | 0.3301 | 0.6478 | -2.8221 | -0.0010 | -0.9990 | -499.5052 | -0.9990 |

