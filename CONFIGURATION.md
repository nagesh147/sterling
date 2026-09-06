# Configuration

Sterling is configured for Indian markets.

| Setting | Environment variable | Default |
|---|---|---|
| default underlying | `DEFAULT_UNDERLYING` | `NIFTY` |
| database path | `DB_PATH` | `./sterling.db` |
| log level | `LOG_LEVEL` | `INFO` |
| real public data | `REAL_PUBLIC_DATA` | `true` |

Zerodha and TrueData credentials are managed from the Connect page and must not be committed to source control.
