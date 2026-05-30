# Vectorized Backtesting Pipeline

This document details the high-performance, Pandas-driven vectorized backtesting architecture built for the Sterling Trading Engine. The purpose of this pipeline is to evaluate multi-year datasets (e.g., 5 years of 1-minute candles) across various timeframes, trading profiles, and strategies in a matter of seconds, avoiding the extreme slowness of traditional event-driven loops.

The pipeline is split into three distinct, decoupled stages:
1. **Data Harvesting** (The Scraper)
2. **Vector Store Compilation** (The Compiler)
3. **Massive Grid Backtesting** (The Engine)

---

## Step 1: Data Harvesting (The Scraper)
**Script:** `data_pipeline/fetch_delta_1m.py`

### What it does
This script acts as the entry point for raw market data. It connects directly to the Delta Exchange API to fetch historical 1-minute OHLCV (Open, High, Low, Close, Volume) data. 

### Key Features:
- **Pagination & Rate Limiting:** Because Delta Exchange limits requests to 2,000 candles per API call, this script automatically chunks the 5-year date ranges into smaller windows. It handles HTTP 429 (Rate Limit Exceeded) errors by implementing exponential backoffs and sleeps.
- **Normalization:** It normalises timestamp boundaries and strictly ensures no mixed-timeframe pollution occurs inside the database.
- **Storage:** Saves the raw, unadulterated candles into the master `sqlite3` database (`sterling_paper.db`) under the `ohlcv` table with the `resolution='1m'` tag.

**Execution Command:**
```bash
cd backend
.venv/bin/python data_pipeline/fetch_delta_1m.py
```

---

## Step 2: Vector Store Compilation (The Compiler)
**Script:** `build_vector_store.py`

### What it does
Querying SQLite databases row-by-row during a backtest is a major bottleneck. To achieve sub-second evaluation speeds, the system must hold data in contiguous memory structures. This script extracts the raw database rows and transforms them into highly compressed "Parquet" files, saving massive amounts of compute time during the actual backtests.

### Key Features:
- **Resumable Architecture:** The compiler automatically detects which symbols (`BTCUSD`, `ETHUSD`, `SOLUSD`) have already been processed. If the script is interrupted (e.g., OOM kill, manual termination), it will skip completed symbols and resume exactly where it left off on the next run.
- **Heavy Lifting (Technical Analysis):** It utilizes the `ta` library to pre-compute over 86 advanced technical indicators (MACD, RSI, ADX, Bollinger Bands, CMF, etc.) on the 1-minute data natively. This means 350+ million data points are calculated *once* and stored.
- **Parquet Format:** Saves output to `vector_store_1m_{symbol}.parquet`. The Parquet format uses columnar storage and Snappy compression, making it up to 50x faster to read into Pandas than standard CSVs or SQLite tables.

**Execution Command:**
```bash
cd backend
.venv/bin/python build_vector_store.py
```

---

## Step 3: Massive Grid Backtesting (The Engine)
**Script:** `run_massive_backtest.py`

### What it does
This is the analytical core. It bypasses event-driven `for-loops` and exclusively uses NumPy/Pandas C-backed matrix math to evaluate thousands of simulated trading years in seconds.

### Key Features:
- **Multi-File Aggregation:** Automatically searches for all `vector_store_1m_*.parquet` files and concatenates them into a master DataFrame.
- **Instantaneous Resampling:** The Parquet file acts as the 1-minute "Source of Truth." To test higher timeframes (5m, 15m, 1h, 4h), the script utilizes Pandas `.resample()` to squeeze the 1-minute candles into the requested timeframe in milliseconds.
- **Dynamic Indicator Calculation:** While the 1-minute data has 86 pre-computed indicators, resampling destroys them (an EMA of 1-minute data is not the same as an EMA of 1-hour data). Thus, the script dynamically recalculates specific required indicators on the fly for the resampled timeframes.
- **Vectorized Strategy Math:** Evaluates complex conditional logic without Python loops. For example, a Breakout strategy is evaluated using boolean matrix masking (`df['close'] > df['highest_high']`).
- **Comprehensive Matrix Output:** Iterates through Trading Profiles (Intraday, Scalping, Aggressive), Timeframes, and Strategies to print a massive grid containing Total Trades, Profit Factor, Win Rate, Sharpe Ratio, and Final Capital.

**Execution Command:**
```bash
cd backend
.venv/bin/python run_massive_backtest.py
```

---

### How to use this going forward
Whenever a user wants to test new logic on the most up-to-date data:
1. Run Step 1 to download the latest missing candles into SQLite.
2. Delete the old `.parquet` files and run Step 2 to re-compile the technical indicators.
3. Rapidly tweak and execute Step 3 to find optimal parameters instantly.
