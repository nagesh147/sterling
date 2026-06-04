# Configuration

## Application settings

`app/core/config.py` (`Settings`, pydantic-settings). Values come from
environment variables / `.env` (see `backend/.env.example`):

| Setting | Env | Default | Purpose |
|---|---|---|---|
| `environment` | `ENVIRONMENT` | `development` | runtime environment |
| `paper_trading` | `PAPER_TRADING` | `true` | global paper default |
| `real_public_data` | `REAL_PUBLIC_DATA` | `true` | use live public market data |
| `default_underlying` | `DEFAULT_UNDERLYING` | `BTC` | default symbol |
| `log_level` | `LOG_LEVEL` | `INFO` | log verbosity |
| `log_json` | `LOG_JSON` | `false` | opt-in structured JSON logging |
| `cors_origins` | `CORS_ORIGINS` | localhost:5173/3000 | allowed origins |
| `exchange_adapter` | `EXCHANGE_ADAPTER` | `delta_india` | active adapter key |
| `max_contracts` | `MAX_CONTRACTS` | `10` | sizing cap |
| `max_position_pct` | `MAX_POSITION_PCT` | `0.05` | per-position cap |
| `default_capital` | `DEFAULT_CAPITAL` | `100000` | NAV default |

Settings are loaded once into the `settings` singleton; unknown env keys are
ignored (`extra: ignore`).

## Broker / market registry

`config/registry.json` is the declarative source of truth for **brokers**
(adapter class path, markets, capabilities, auth) and the **market taxonomy**.
See [BROKERS.md](BROKERS.md) and [MARKETS.md](MARKETS.md). It is loaded and
cached by `app/services/exchanges/registry.py`.

## Exchange credentials

Per-exchange credentials are stored as `ExchangeConfig`
(`app/schemas/exchange_config.py`): `name`, `api_key`, `api_secret`, `is_paper`,
and an `extra` dict (e.g. Zerodha `access_token`). They are managed via the
exchanges API and the account store — never hard-coded. See [SECURITY.md](SECURITY.md).

## Precedence

1. Environment variables / `.env` → `Settings`.
2. `config/registry.json` → broker & market metadata.
3. Stored `ExchangeConfig` → live credentials & active exchange.
