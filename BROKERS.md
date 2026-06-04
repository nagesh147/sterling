# Brokers — adding & replacing exchanges

Brokers are plug-and-play. The platform ships adapters for **Delta Exchange
India** (primary), **Zerodha**, **Binance**, **Deribit**, and **OKX**.

## The contracts

Adapters inherit one of three bases in `app/services/exchanges/`:

| Base | Use when | Methods |
|---|---|---|
| `BaseExchangeAdapter` (`base.py`) | public market data only | `get_index_price`, `get_spot_price`, `get_perp_price`, `get_candles`, `get_option_chain`, `get_dvol`, `ping`, … |
| `AuthenticatedExchangeAdapter` (`authenticated_base.py`) | + private account data | `test_connection`, `get_balances`, `get_positions`, `get_open_orders`, `get_fills`, `get_portfolio_snapshot` |
| `TradingExchangeAdapter` (`trading_base.py`) | + order placement | `get_product_id`, `place_order`, `place_order_option`, `cancel_order` (required); `set_leverage`, `set_margin_mode`, `cancel_replace_stop`, `market_reduce_close` (optional) |

`TradingExchangeAdapter` is the enforced order contract. A broker that forgets a
required method **fails the contract test** (`tests/test_broker_contract.py`),
not production.

## Adding a new broker (checklist)

1. **Create the adapter** at `app/services/exchanges/adapters/<name>.py`,
   subclassing the right base. Implement the abstract methods. Keep all
   exchange-specific quirks (auth signing, symbol formats, lot sizes) inside the
   adapter — this is the anti-corruption layer.

2. **Register construction** in `app/services/exchanges/adapter_factory.py`
   (`create_account_adapter`) — map the broker key to its constructor with the
   right credential fields.

3. **Declare metadata** in `config/registry.json`:
   ```json
   "<name>": {
     "adapter": "app.services.exchanges.adapters.<name>:<Name>Adapter",
     "markets": ["equities"],
     "capabilities": ["equity", "futures"],
     "auth": "token"
   }
   ```

4. **List it** in `SUPPORTED_EXCHANGES` (`app/schemas/exchange_config.py`).

5. **Add a contract test** — extend `tests/test_broker_contract.py` to assert
   your adapter `issubclass(..., TradingExchangeAdapter)` if it places orders.
   `tests/test_broker_registry.py::test_every_adapter_path_imports` already
   verifies your registry path imports.

6. **Run** `make verify`.

## How adapters are loaded

```python
from app.services.exchanges import registry
adapter = registry.load_account_adapter(cfg)   # validated + delegates to factory
cls     = registry.resolve_adapter_class("zerodha")   # dynamic import
meta    = registry.broker_meta("zerodha")             # markets / capabilities
```

Construction is delegated to the factory so there is exactly one construction
path (registry metadata and factory cannot drift). New code should call
`registry.load_account_adapter`; the legacy `create_account_adapter` remains for
backward compatibility.

## Paper vs live

Every adapter takes `is_paper`. Order *dispatch* mode (paper/shadow/live) is
decided by the `OrderRouter`, not the adapter — see [EXECUTION.md](EXECUTION.md).
Delta India is the reference implementation; study `adapters/delta_india.py`.
