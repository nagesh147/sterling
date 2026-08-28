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

`app/engines/` — current packages: `sterling_engine` (price-action /
MA-crossover crypto scalper + backtest), `sterling_kite_engine` (Zerodha/Indian
equities & derivatives engine), `directional` (multi-track regime/signal/setup/
sizing/execution pipeline, aka "Grok"), `derivatives` (Greeks-aware strike/
expiry/leverage selection) and its smaller sibling `derivatives_native`, `edge`
(backtest-validated 4h signal generator), `sterling_v2`, `hybrid_vcp`,
`analytics` (walk-forward, sensitivity, correlation, CPCV, Monte Carlo — pure
functions, no I/O), `risk` (drawdown circuit breaker, greeks budget, slippage,
microstructure veto — stateful singletons via DI), `indicators`, `ml`,
`backtest`, `arbitration`, `common`, and `atm_premium_imbalance`
(reverse-engineered — see below), and `oi_wall_flow`
(chain OI walls + short-covering / put-writing flow — see below). Each is self-contained. `scalping/` and
`triple_supertrend/` are legacy dirs, now empty — their logic was consolidated
into `sterling_engine`/`directional`; do not add new code there.

Styles already represented: trend-following (MA crossover), mean-reversion,
volatility/breakout, and derivatives selection, across both crypto (Delta
Exchange India) and Indian equities/derivatives (Zerodha Kite). The
architecture supports statistical-arbitrage and others as new engines.

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

## Reverse-engineered strategies

One strategy in this repo was not designed here. `atm_premium_imbalance`
(`app/engines/atm_premium_imbalance/`) was reconstructed from screen recordings
of a third-party bot, so it carries a documentation obligation the others do
not: every rule traces to the frame it came from, and every default records its
provenance. See `docs/strategy/atm-premium-imbalance/` — the contract (A230),
the evidence matrix (A231), what was rejected (A232) and the conformance report.

If you add another of these, keep the three-way separation that made this one
reviewable:

- **compatibility** behaviour — reproduces the source system, even where that
  is not what you would build;
- **validated** behaviour — what a replay actually proves;
- **research** behaviour — hypotheses, reachable but never a default, and
  refused outright in live mode by `config.validate()`.

A parameter reconstructed from a recording is not a discovered rule. Encode the
provenance and do not call it canonical until a replay proves it — the spec for
this strategy proposed an `entry_buffer_points = 10.25` that a second recording
falsified outright, because the number was measured slippage, not a setting.

## Why isolation matters

Because strategies only speak `Signal` and consume normalized data, the same
strategy runs unchanged across Delta crypto, Zerodha equities, or any future
broker/market — the adapters and the router absorb all the differences.

## OI Wall Flow

`oi_wall_flow` (`app/engines/oi_wall_flow/`) reads an Indian F&O chain the way
a desk does: classify each strike's OI+premium change, locate the put wall
(support) and call wall (resistance), score near-ATM flow, then **buy the
first-resistance CE** (or first-support PE) when the flow agrees.

It does not place orders. It emits `Signal`s (`instrument_type="options"`)
with premium stop/target. Motivating fixture: BSE Ltd 29-Sep-2026, which must
arm **3500 CE** and never a PE. Spec: `docs/strategy/oi-wall-flow/`.

