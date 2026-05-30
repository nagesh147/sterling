# High-Speed Vectorized Backtesting Architecture

## What is it?
This architecture replaces the traditional "Event-Driven" backtesting loop (where Python evaluates every single candle one by one) with a **Vectorized Analytical Data Store**. By pre-computing all heavy mathematical indicators across the entire dataset exactly *once*, and saving them in an ultra-fast column-oriented format (Parquet), we eliminate computational bottlenecks. 

With this system, testing a new strategy over 5 years of 1-minute data (2.6+ million rows) takes less than 2 seconds, compared to the hours it would take in a standard Python loop.

## Are the indicators limited to our App?
**No.** Currently, the compiler script calculates a robust baseline (EMAs, SMAs, ATR, RSI, Bollinger Bands). However, it is fundamentally unrestricted. You can attach any popular trading community indicator to the build process (e.g., using the `pandas_ta` library, which generates over 100+ standard indicators like MACD, Ichimoku, Stochastic, ADX, etc., automatically). Once compiled, *every* indicator you choose to include is permanently baked into the Parquet file as a fast-read column, instantly ready for your backtests.

## Architecture Flow
The system is divided into two distinct phases:

### 1. The Compiler (`build_vector_store.py`)
This is the heavy lifting step. You run this exactly once (or whenever you download new OHLCV data).
* **Input:** Raw historical data from `sterling_paper.db` (SQLite).
* **Process:** Extracts millions of rows, groups by symbol, and calculates all configured technical indicators via vector math.
* **Output:** `vector_store_1m.parquet` - A highly compressed, ultra-fast data store.

### 2. The Backtester (`fast_vector_backtest.py`)
This is what you run whenever you want to test a new trading idea or strategy.
* **Input:** `vector_store_1m.parquet`
* **Process:** Loads millions of rows into memory instantly. Uses matrix math (Pandas/NumPy boolean arrays) to find all crossover/breakout/SMC conditions simultaneously.
* **Output:** Instant metrics (Profit Factor, Win Rate, Trades, Calculation Time).

## How to Use

### Step 1: Build the Data Store
Run this command in an external Ubuntu terminal so you can watch its live progress. Depending on your data size, it may take a minute or two.
```bash
cd /home/nageshmadaram/Sterling/backend
.venv/bin/python build_vector_store.py
```

### Step 2: Run a Lightning-Fast Backtest
Once the parquet file exists, you can test strategies instantly.
```bash
.venv/bin/python fast_vector_backtest.py
```

### Extending Indicators
If you want to add every standard indicator used in the trading community (MACD, ADX, VWAP, etc.), you can easily expand `build_vector_store.py`. For example, installing `pandas_ta` and calling `df.ta.strategy("all")` will append every known indicator to your DataFrame before saving it to the Parquet file.
