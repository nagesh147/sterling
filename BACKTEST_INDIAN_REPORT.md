# Sterling Indian Market Backtest Report
_Generated 2026-08-25 19:04 IST_  _Capital: ₹100,000  Fees: 0.05% round-trip  Max hold: 200 bars  Data: SterlingLake Pendrive (Feb→Aug 2026)_

## Methodology
- **Data**: 1-minute OHLCV from SterlingLake pendrive (NSE indices + stocks), resampled to 5m / 15m / 1h.
- **Strategies**: SuperTrend (Triple), ORB+VWAP, Adaptive Edge (Volume Profile + IB), Flow Navigator (Volatility Regime), ATM Premium Imbalance (Session-Open).
- **Profiles**: Scalping (SL 1×ATR / TP 2×ATR), Intraday (SL 2× / TP 3.5×), Aggressive (SL 1.5× / TP 4.5×).
- **Exits**: Bar-by-bar first-touch SL/TP. Time-stop after 200 bars. Fee 0.05% round-trip.
- **Capital**: ₹1,00,000 per trade, sequential (no overlapping). PnL compounds.

## 🏆 Top 25 by Net Return (Compounded ₹1,00,000)

| # | Strategy | Symbol | TF | Profile | Trades | Win% | PF | Expect% | Sharpe | MaxDD% | Net Ret% | HODL% |
|---|----------|--------|----|---------|--------|------|-----|---------|--------|--------|----------|-------|
| 1 | SuperTrend (Triple) | INDIGO | 15min | Intraday | 89 | 51.7 | 1.98 | 0.469 | 4.68 | 5.2 | +49.9 | +7.3 |
| 2 | ORB + VWAP | THANGAMAYL | 5min | Intraday | 95 | 47.4 | 1.71 | 0.427 | 3.77 | 8.9 | +47.7 | +46.6 |
| 3 | ORB + VWAP | ACUTAAS | 5min | Aggressive | 69 | 42.0 | 2.23 | 0.561 | 5.04 | 4.6 | +45.6 | +51.2 |
| 4 | Flow Navigator (Vol) | THANGAMAYL | 1h | Aggressive | 15 | 46.7 | 2.84 | 2.701 | 6.79 | 20.0 | +45.3 | +46.6 |
| 5 | SuperTrend (Triple) | KAYNES | 15min | Intraday | 86 | 51.2 | 1.62 | 0.444 | 3.43 | 7.6 | +43.8 | -6.7 |
| 6 | SuperTrend (Triple) | NETWEB | 1h | Aggressive | 26 | 38.5 | 1.98 | 1.452 | 4.46 | 12.5 | +40.9 | +65.6 |
| 7 | ORB + VWAP | THANGAMAYL | 5min | Aggressive | 87 | 35.6 | 1.70 | 0.406 | 3.37 | 6.2 | +40.1 | +46.6 |
| 8 | SuperTrend (Triple) | NETWEB | 1h | Scalping | 37 | 54.1 | 2.31 | 0.930 | 6.12 | 5.3 | +39.4 | +65.6 |
| 9 | SuperTrend (Triple) | INDIGO | 15min | Aggressive | 82 | 36.6 | 1.77 | 0.382 | 3.51 | 6.2 | +35.1 | +7.3 |
| 10 | SuperTrend (Triple) | KAYNES | 1h | Aggressive | 25 | 44.0 | 1.97 | 1.156 | 4.75 | 12.0 | +31.0 | -6.7 |
| 11 | Flow Navigator (Vol) | ACUTAAS | 1h | Aggressive | 16 | 50.0 | 2.44 | 1.765 | 6.33 | 6.0 | +30.4 | +51.2 |
| 12 | Adaptive Edge (Vol+IB) | NETWEB | 15min | Aggressive | 103 | 32.0 | 1.31 | 0.281 | 1.73 | 12.3 | +29.2 | +65.6 |
| 13 | ORB + VWAP | DATAPATTNS | 5min | Aggressive | 84 | 33.3 | 1.49 | 0.315 | 2.54 | 11.1 | +28.2 | +63.8 |
| 14 | SuperTrend (Triple) | DATAPATTNS | 1h | Aggressive | 22 | 40.9 | 1.72 | 1.246 | 3.74 | 16.6 | +27.7 | +63.8 |
| 15 | SuperTrend (Triple) | MCX | 1h | Intraday | 25 | 52.0 | 1.96 | 1.022 | 4.93 | 6.0 | +27.3 | +23.9 |
| 16 | ATM Premium (Open) | GVT&D | 5min | Intraday | 103 | 41.7 | 1.35 | 0.251 | 2.15 | 9.8 | +27.2 | +19.3 |
| 17 | SuperTrend (Triple) | KAYNES | 1h | Scalping | 41 | 51.2 | 1.88 | 0.601 | 4.65 | 4.8 | +26.8 | -6.7 |
| 18 | Flow Navigator (Vol) | KAYNES | 1h | Scalping | 22 | 63.6 | 3.00 | 1.056 | 8.45 | 3.5 | +25.5 | -6.7 |
| 19 | ORB + VWAP | MCX | 5min | Aggressive | 96 | 36.5 | 1.57 | 0.241 | 2.98 | 9.3 | +25.1 | +23.9 |
| 20 | SuperTrend (Triple) | KAYNES | 1h | Intraday | 26 | 50.0 | 1.67 | 0.908 | 3.77 | 14.6 | +24.3 | -6.7 |
| 21 | Flow Navigator (Vol) | NETWEB | 1h | Scalping | 21 | 57.1 | 2.54 | 1.010 | 6.83 | 3.1 | +22.8 | +65.6 |
| 22 | ORB + VWAP | ACUTAAS | 5min | Intraday | 71 | 45.1 | 1.51 | 0.301 | 2.90 | 7.8 | +22.6 | +51.2 |
| 23 | Flow Navigator (Vol) | PERSISTENT | 1h | Intraday | 10 | 60.0 | 3.88 | 2.095 | 9.25 | 7.1 | +22.4 | +4.0 |
| 24 | ORB + VWAP | DATAPATTNS | 5min | Intraday | 81 | 44.4 | 1.38 | 0.265 | 2.29 | 8.7 | +22.3 | +63.8 |
| 25 | Adaptive Edge (Vol+IB) | MCX | 15min | Aggressive | 104 | 31.7 | 1.31 | 0.212 | 1.75 | 11.8 | +22.3 | +23.9 |

## 📈 Top 25 by Sharpe (Risk-Adjusted)

| # | Strategy | Symbol | TF | Profile | Trades | Win% | PF | Expect% | Sharpe | MaxDD% | Net Ret% | HODL% |
|---|----------|--------|----|---------|--------|------|-----|---------|--------|--------|----------|-------|
| 1 | Flow Navigator (Vol) | PERSISTENT | 1h | Intraday | 10 | 60.0 | 3.88 | 2.095 | 9.25 | 7.1 | +22.4 | +4.0 |
| 2 | Flow Navigator (Vol) | KAYNES | 1h | Scalping | 22 | 63.6 | 3.00 | 1.056 | 8.45 | 3.5 | +25.5 | -6.7 |
| 3 | Flow Navigator (Vol) | NETWEB | 1h | Scalping | 21 | 57.1 | 2.54 | 1.010 | 6.83 | 3.1 | +22.8 | +65.6 |
| 4 | Flow Navigator (Vol) | THANGAMAYL | 1h | Aggressive | 15 | 46.7 | 2.84 | 2.701 | 6.79 | 20.0 | +45.3 | +46.6 |
| 5 | Flow Navigator (Vol) | ACUTAAS | 1h | Aggressive | 16 | 50.0 | 2.44 | 1.765 | 6.33 | 6.0 | +30.4 | +51.2 |
| 6 | Flow Navigator (Vol) | ACUTAAS | 1h | Scalping | 19 | 57.9 | 2.28 | 0.870 | 6.22 | 4.1 | +17.4 | +51.2 |
| 7 | SuperTrend (Triple) | NETWEB | 1h | Scalping | 37 | 54.1 | 2.31 | 0.930 | 6.12 | 5.3 | +39.4 | +65.6 |
| 8 | Flow Navigator (Vol) | INDIGO | 1h | Scalping | 25 | 56.0 | 2.22 | 0.684 | 5.82 | 3.8 | +18.1 | +7.3 |
| 9 | Flow Navigator (Vol) | LTM | 1h | Intraday | 15 | 53.3 | 2.10 | 1.118 | 5.39 | 7.8 | +17.3 | -4.9 |
| 10 | ORB + VWAP | ACUTAAS | 5min | Aggressive | 69 | 42.0 | 2.23 | 0.561 | 5.04 | 4.6 | +45.6 | +51.2 |
| 11 | SuperTrend (Triple) | MCX | 1h | Intraday | 25 | 52.0 | 1.96 | 1.022 | 4.93 | 6.0 | +27.3 | +23.9 |
| 12 | SuperTrend (Triple) | KAYNES | 1h | Aggressive | 25 | 44.0 | 1.97 | 1.156 | 4.75 | 12.0 | +31.0 | -6.7 |
| 13 | SuperTrend (Triple) | INDIGO | 15min | Intraday | 89 | 51.7 | 1.98 | 0.469 | 4.68 | 5.2 | +49.9 | +7.3 |
| 14 | SuperTrend (Triple) | KAYNES | 1h | Scalping | 41 | 51.2 | 1.88 | 0.601 | 4.65 | 4.8 | +26.8 | -6.7 |
| 15 | SuperTrend (Triple) | NETWEB | 1h | Aggressive | 26 | 38.5 | 1.98 | 1.452 | 4.46 | 12.5 | +40.9 | +65.6 |
| 16 | Flow Navigator (Vol) | THANGAMAYL | 1h | Intraday | 14 | 50.0 | 1.85 | 1.593 | 4.37 | 23.5 | +22.2 | +46.6 |
| 17 | Flow Navigator (Vol) | TATAELXSI | 1h | Aggressive | 17 | 41.2 | 1.89 | 0.930 | 4.26 | 5.9 | +16.0 | -21.6 |
| 18 | SuperTrend (Triple) | NIFTY_50 | 15min | Intraday | 73 | 53.4 | 1.76 | 0.163 | 4.13 | 3.2 | +12.5 | -4.7 |
| 19 | Flow Navigator (Vol) | MUTHOOTFIN | 1h | Intraday | 17 | 52.9 | 1.75 | 0.867 | 3.94 | 6.2 | +14.7 | -24.3 |
| 20 | Flow Navigator (Vol) | KAYNES | 1h | Intraday | 19 | 52.6 | 1.68 | 0.917 | 3.90 | 12.6 | +17.5 | -6.7 |
| 21 | SuperTrend (Triple) | KAYNES | 1h | Intraday | 26 | 50.0 | 1.67 | 0.908 | 3.77 | 14.6 | +24.3 | -6.7 |
| 22 | ORB + VWAP | THANGAMAYL | 5min | Intraday | 95 | 47.4 | 1.71 | 0.427 | 3.77 | 8.9 | +47.7 | +46.6 |
| 23 | Flow Navigator (Vol) | SIEMENS | 1h | Scalping | 19 | 42.1 | 1.73 | 0.479 | 3.76 | 4.4 | +9.1 | +28.1 |
| 24 | SuperTrend (Triple) | DATAPATTNS | 1h | Aggressive | 22 | 40.9 | 1.72 | 1.246 | 3.74 | 16.6 | +27.7 | +63.8 |
| 25 | SuperTrend (Triple) | BSE | 1h | Scalping | 36 | 50.0 | 1.67 | 0.385 | 3.72 | 7.9 | +14.3 | +12.3 |

## 💰 Top 25 by Profit Factor

| # | Strategy | Symbol | TF | Profile | Trades | Win% | PF | Expect% | Sharpe | MaxDD% | Net Ret% | HODL% |
|---|----------|--------|----|---------|--------|------|-----|---------|--------|--------|----------|-------|
| 1 | Flow Navigator (Vol) | PERSISTENT | 1h | Intraday | 10 | 60.0 | 3.88 | 2.095 | 9.25 | 7.1 | +22.4 | +4.0 |
| 2 | Flow Navigator (Vol) | KAYNES | 1h | Scalping | 22 | 63.6 | 3.00 | 1.056 | 8.45 | 3.5 | +25.5 | -6.7 |
| 3 | Flow Navigator (Vol) | THANGAMAYL | 1h | Aggressive | 15 | 46.7 | 2.84 | 2.701 | 6.79 | 20.0 | +45.3 | +46.6 |
| 4 | Flow Navigator (Vol) | NETWEB | 1h | Scalping | 21 | 57.1 | 2.54 | 1.010 | 6.83 | 3.1 | +22.8 | +65.6 |
| 5 | Flow Navigator (Vol) | ACUTAAS | 1h | Aggressive | 16 | 50.0 | 2.44 | 1.765 | 6.33 | 6.0 | +30.4 | +51.2 |
| 6 | SuperTrend (Triple) | NETWEB | 1h | Scalping | 37 | 54.1 | 2.31 | 0.930 | 6.12 | 5.3 | +39.4 | +65.6 |
| 7 | Flow Navigator (Vol) | ACUTAAS | 1h | Scalping | 19 | 57.9 | 2.28 | 0.870 | 6.22 | 4.1 | +17.4 | +51.2 |
| 8 | ORB + VWAP | ACUTAAS | 5min | Aggressive | 69 | 42.0 | 2.23 | 0.561 | 5.04 | 4.6 | +45.6 | +51.2 |
| 9 | Flow Navigator (Vol) | INDIGO | 1h | Scalping | 25 | 56.0 | 2.22 | 0.684 | 5.82 | 3.8 | +18.1 | +7.3 |
| 10 | Flow Navigator (Vol) | LTM | 1h | Intraday | 15 | 53.3 | 2.10 | 1.118 | 5.39 | 7.8 | +17.3 | -4.9 |
| 11 | SuperTrend (Triple) | NETWEB | 1h | Aggressive | 26 | 38.5 | 1.98 | 1.452 | 4.46 | 12.5 | +40.9 | +65.6 |
| 12 | SuperTrend (Triple) | INDIGO | 15min | Intraday | 89 | 51.7 | 1.98 | 0.469 | 4.68 | 5.2 | +49.9 | +7.3 |
| 13 | SuperTrend (Triple) | KAYNES | 1h | Aggressive | 25 | 44.0 | 1.97 | 1.156 | 4.75 | 12.0 | +31.0 | -6.7 |
| 14 | SuperTrend (Triple) | MCX | 1h | Intraday | 25 | 52.0 | 1.96 | 1.022 | 4.93 | 6.0 | +27.3 | +23.9 |
| 15 | Flow Navigator (Vol) | TATAELXSI | 1h | Aggressive | 17 | 41.2 | 1.89 | 0.930 | 4.26 | 5.9 | +16.0 | -21.6 |
| 16 | SuperTrend (Triple) | KAYNES | 1h | Scalping | 41 | 51.2 | 1.88 | 0.601 | 4.65 | 4.8 | +26.8 | -6.7 |
| 17 | Flow Navigator (Vol) | THANGAMAYL | 1h | Intraday | 14 | 50.0 | 1.85 | 1.593 | 4.37 | 23.5 | +22.2 | +46.6 |
| 18 | SuperTrend (Triple) | INDIGO | 15min | Aggressive | 82 | 36.6 | 1.77 | 0.382 | 3.51 | 6.2 | +35.1 | +7.3 |
| 19 | SuperTrend (Triple) | NIFTY_50 | 15min | Intraday | 73 | 53.4 | 1.76 | 0.163 | 4.13 | 3.2 | +12.5 | -4.7 |
| 20 | Flow Navigator (Vol) | MUTHOOTFIN | 1h | Intraday | 17 | 52.9 | 1.75 | 0.867 | 3.94 | 6.2 | +14.7 | -24.3 |
| 21 | Flow Navigator (Vol) | SIEMENS | 1h | Scalping | 19 | 42.1 | 1.73 | 0.479 | 3.76 | 4.4 | +9.1 | +28.1 |
| 22 | SuperTrend (Triple) | DATAPATTNS | 1h | Aggressive | 22 | 40.9 | 1.72 | 1.246 | 3.74 | 16.6 | +27.7 | +63.8 |
| 23 | SuperTrend (Triple) | MCX | 1h | Aggressive | 26 | 34.6 | 1.72 | 0.756 | 3.48 | 8.9 | +19.9 | +23.9 |
| 24 | ORB + VWAP | THANGAMAYL | 5min | Intraday | 95 | 47.4 | 1.71 | 0.427 | 3.77 | 8.9 | +47.7 | +46.6 |
| 25 | ORB + VWAP | THANGAMAYL | 5min | Aggressive | 87 | 35.6 | 1.70 | 0.406 | 3.37 | 6.2 | +40.1 | +46.6 |

## 📊 Strategy Comparison (Averaged Across All Instruments)

| Strategy | Configs | Avg Trades | Avg Win% | Avg PF | Avg Sharpe | Avg Net Ret% | Best Net Ret% |
|----------|---------|------------|----------|--------|------------|-------------|---------------|
| ATM Premium (Open) | 66 | 104 | 31.1 | 0.87 | -1.19 | -6.6 | +27.2 |
| Adaptive Edge (Vol+IB) | 66 | 152 | 26.5 | 0.72 | -2.72 | -23.1 | +29.2 |
| Flow Navigator (Vol) | 66 | 18 | 36.8 | 1.31 | 0.24 | +5.0 | +45.3 |
| ORB + VWAP | 60 | 91 | 35.2 | 1.05 | -0.08 | +2.6 | +47.7 |
| SuperTrend (Triple) | 198 | 133 | 33.8 | 1.02 | -0.18 | -1.1 | +49.9 |

## 📌 Beat Buy-and-Hold: **104** of **456** configurations
