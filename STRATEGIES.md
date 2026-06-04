# Strategies

Strategies are **fully independent of brokers and markets**. They consume
normalized market data and emit standardized `Signal`s. They never import an
adapter and never place orders directly — execution is the `OrderRouter`'s job.

## The contract

A strategy produces `app.domain.models.Signal`:

```python
Signal(
    underlying="BTC",          # symbol, not an exchange-specific instrument
    direction="long",          # "long" | "short"
    instrument_type="futures", # "futures" | "options"
    score=82.5, strength="STRONG",
    stop_loss=49000.0, take_profit=53000.0,
    size_hint=1.0, source="sterling_engine",
)
```

Structurally, a strategy satisfies `StrategyProtocol`
(`app/domain/interfaces.py`): a `generate(...) -> list[Signal]`. The
`StrategyAgent` (`app/agents/strategy_agent.py`) runs a generator and publishes
`SignalRaised` events.

## Where strategies live

`app/engines/` — current engines include `sterling_engine` (price-action /
MA-crossover scalper + backtest), `directional`, `edge` (backtest-validated 4h
combos), `sterling_v2`, `hybrid_vcp`, `analytics`, `indicators`, `risk`. Each is
self-contained.

Styles already represented: trend-following (MA crossover), mean-reversion,
volatility/breakout, and derivatives selection. The architecture supports
statistical-arbitrage and others as new engines.

## Adding a strategy

1. Create a module under `app/engines/<your_strategy>/` that produces `Signal`s
   from normalized `Candle`/`OptionSummary`/`InstrumentMeta` inputs.
2. **Validate before trusting it.** This codebase has hard-won evidence that
   strategies overfit on short windows — use the cross-symbol + out-of-sample
   split harness (see `app/engines/sterling_engine/backtest.py`, the edge
   discovery matrix, and `docs/reports/`). Momentum/IS↔OOS correlation can be
   negative; 4h is where durable edge has been found.
3. Route generated signals through the `OrderRouter` (paper first) — the same
   path for backtest, paper, shadow, and live ([EXECUTION.md](EXECUTION.md)).
4. Keep the strategy broker/market-agnostic: no adapter imports, no order calls.

## Why isolation matters

Because strategies only speak `Signal` and consume normalized data, the same
strategy runs unchanged across Delta crypto, Zerodha equities, or any future
broker/market — the adapters and the router absorb all the differences.
