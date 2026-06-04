# Markets

Markets are normalized so strategies are **market-agnostic**. A strategy emits a
`Signal` for an `underlying`; the broker + market adapters translate that into a
concrete instrument and order.

## Supported market taxonomy

Declared in `config/registry.json` under `markets`, and each broker lists the
markets it serves:

| Market | Description | Broker(s) today |
|---|---|---|
| `crypto` | perps & options | delta_india, binance, deribit, okx |
| `equities` | Indian equities | zerodha |
| `commodities` | commodity futures (incl. natural gas) | zerodha |
| `forex` | FX pairs | — (planned) |
| `metals` | gold / silver | — (planned) |
| `energy` | natural gas / crude | — (planned) |

## Normalized data models

Strategies and agents consume canonical models from `app/domain/models.py`
(re-exported from `app/schemas/`):

- `Candle` — OHLCV bar
- `OptionSummary` — option chain row (strike, greeks, IV)
- `InstrumentMeta` — normalized instrument identity
- `Signal` — strategy output (underlying, direction, instrument_type, score, …)

Each adapter maps exchange-specific shapes into these. Lot sizes / contract
values are handled inside the adapter (e.g. Delta ETH = 0.01 coins/lot) — see
the `contract_value` notes in the codebase.

## Adding a market

1. Add the market key under `markets` in `config/registry.json`.
2. List it in the serving broker's `markets` array.
3. Ensure the broker adapter returns normalized `Candle`/`InstrumentMeta`/
   `OptionSummary` for that market (the anti-corruption layer).
4. Strategies need **no change** — they already operate on normalized models.

## Worked example: Zerodha → Indian equities

`zerodha` is registered with `"markets": ["equities", "commodities"]`. To take an
equities strategy live: implement the order methods on `ZerodhaAdapter`
(subclass `TradingExchangeAdapter`), confirm the contract test passes, and route
signals through the `OrderRouter` exactly as for crypto. The strategy that
produced the `Signal` is unchanged. See [BROKERS.md](BROKERS.md).
