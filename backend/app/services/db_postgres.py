import asyncpg
from typing import Optional

# Setup database connection config
DB_CONFIG = {
    "user": "postgres",
    "password": "password", 
    "database": "sterling",
    "host": "127.0.0.1"
}

_pool: Optional[asyncpg.Pool] = None

async def init_db_schema():
    """
    Initializes the PostgreSQL database schema for the V4 engine.
    This creates the necessary tables including those specific to TimescaleDB.
    """
    global _pool
    try:
        if not _pool:
            _pool = await asyncpg.create_pool(**DB_CONFIG)
            
        async with _pool.acquire() as conn:
            # Create candles table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    resolution TEXT NOT NULL,
                    open DOUBLE PRECISION,
                    high DOUBLE PRECISION,
                    low DOUBLE PRECISION,
                    close DOUBLE PRECISION,
                    volume DOUBLE PRECISION,
                    UNIQUE(symbol, resolution, time)
                );
            """)
            
            # Convert to hypertable if TimescaleDB is installed (ignore error if already hypertable or no extension)
            try:
                await conn.execute("SELECT create_hypertable('candles', 'time', if_not_exists => TRUE);")
            except Exception:
                pass
                
            # Create HMM regimes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS hmm_regimes (
                    time TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    primary_regime INTEGER,
                    confidence DOUBLE PRECISION,
                    UNIQUE(symbol, time)
                );
            """)
            
    except Exception as e:
        print(f"Failed to initialize PostgreSQL schema: {e}")
        raise e

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if not _pool:
         _pool = await asyncpg.create_pool(**DB_CONFIG)
    return _pool
