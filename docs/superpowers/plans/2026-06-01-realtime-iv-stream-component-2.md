# Real-Time IV Streaming — Component ② TDD Plan (Forward IV Recorder)

_Date: 2026-06-01 · Status: in-progress_

## Goal
Implement the Forward IV Recorder (Component ②), which subscribes to the IV Stream Manager (Component ①) and persists options Greeks/IV data into SQLite to build a historical surface for future backtests.

## Architecture & Schema Requirements
1. **Database Schema (`app/services/db.py`)**:
   - Create table `option_iv_ticks` with columns: `underlying`, `expiry`, `strike`, `opt_type`, `mark_iv`, `bid_iv`, `ask_iv`, `delta`, `gamma`, `theta`, `vega`, `rho`, `ts`.
   - Ensure indices exist for efficient querying by `underlying, ts` and `expiry`.
2. **ATM-IV Updates**:
   - Persist ATM IV directly into the existing `iv_history` table to feed the legacy/volatility regime systems.
3. **Downsampling Engine**:
   - The stream emits every ~2 seconds. Persisting 2s data per strike per expiry would cause massive DB bloat.
   - Implement a background loop (`app/services/delta_iv_recorder.py`) that polls `iv_manager` once a minute (or detects meaningful change) and flush-inserts the active chains.
4. **Lifespan Integration**:
   - Wire the background loop into the FastAPI lifespan (in `main.py`) gated by the `STERLING_IV_STREAM` environment variable, just like `iv_manager.start()`.

## TDD Steps

### Step 1: Database Schema
- **Test**: `tests/services/test_iv_recorder.py::test_db_schema_created`
- **Action**: Add `CREATE TABLE IF NOT EXISTS option_iv_ticks` to `db._create_tables`. Add `record_option_ticks` and `get_option_ticks` helpers.
- **Verification**: Ensure the table creates cleanly without breaking existing tests.

### Step 2: The Downsampling Recorder
- **Test**: `tests/services/test_iv_recorder.py::test_recorder_downsamples_and_flushes`
- **Action**: Create `app/services/delta_iv_recorder.py`. It reads `iv_manager.chain("BTC")` on a 60s interval.
- **Verification**: Mock `iv_manager` and ensure DB insert is called with the correct `option_iv_ticks` data structure.

### Step 3: ATM-IV Bridge
- **Test**: `tests/services/test_iv_recorder.py::test_atm_iv_bridge`
- **Action**: Ensure the recorder fetches ATM IV (nearest 30 DTE or closest) via `iv_manager.atm_iv()` and calls `db.record_iv(underlying, ivr)`.
- **Verification**: Validate `iv_history` has the correct updates.

### Step 4: Lifespan Wiring & Live Verification
- **Test**: Manual (repo-wide test pass).
- **Action**: Hook `start_recorder()` into `main.py` lifespan (gated by `STERLING_IV_STREAM`).
- **Verification**: Run `STERLING_IV_STREAM=1 python verify_engine.py` or a quick script to ensure it connects, streams, and drops 1-minute rows into the DB.

Let's begin with Step 1 and 2.
