# NIFTY ORB + VWAP Options Strategy

## 1. Strategy contract

NIFTY ORB is an independent directional options-buying strategy. It does not consume signals from Adaptive Edge, SuperTrend, or Flow Navigator. Shared infrastructure may be reused, but signal generation and strategy decisions remain isolated.

The strategy is **long options only**:

```text
NIFTY underlying
    |
    v
5-minute completed bars
    |
    +-- 09:15-09:30 opening range
    +-- VWAP
    +-- VWAP slope
    +-- ATR-normalized breakout
    +-- volume confirmation
    +-- TREND / EXPANSION regime
    |
    v
LONG / SHORT / NONE
    |
    +-- LONG  -> BUY CE
    +-- SHORT -> BUY PE
    +-- NONE  -> NO ORDER
```

No option selling is part of this strategy.

## 2. Current implementation

The core engine is implemented in `backend/app/engines/nifty_orb_options.py`.

### Signal layer

Implemented:

- 5-minute bar model.
- IST normalization through `Asia/Kolkata`.
- Optional `as_of` processing that excludes bars whose 5-minute candle has not completed.
- 15-minute opening range anchored to 09:15 IST.
- VWAP using volume-weighted typical price.
- ATR calculation with configurable period; default 14.
- VWAP slope using configurable lookback; default 3 bars.
- ATR-normalized breakout threshold; default 0.15 ATR.
- Volume ratio against the recent baseline; default confirmation threshold 1.15x.
- Regime classification into `EXPANSION`, `TREND`, `RANGE`, or `UNKNOWN`.
- Directional filter requiring VWAP alignment and VWAP slope alignment.
- Entry-window enforcement; default 09:30-12:00 IST.
- Neutral result when filters are not aligned.
- Signal confidence derived from breakout distance, volume ratio, and a 0.99 ceiling.

### Option-selection layer

Implemented:

- LONG maps only to CE.
- SHORT maps only to PE.
- ATM, ITM, and OTM selection modes.
- Configurable ITM/OTM strike steps.
- Expiry DTE minimum/maximum filters.
- Optional expiry-day avoidance.
- `nearest` / `weekly` / `monthly` / `any` selection, separated by an explicit expiry-calendar rule.
- Minimum lot-size and positive-premium checks.
- Bid/ask validation when enabled.
- Maximum spread percentage gate.
- Minimum option volume.
- Minimum open interest.
- Optional quote-freshness gate.
- Deterministic tie-breaking by expiry, strike distance, volume, OI, and spread.

### Risk and trade-plan layer

Implemented:

- Underlying-based directional risk levels.
- Premium-domain entry/stop/target fields.
- Premium risk per share.
- Whole-lot quantity sizing.
- INR maximum-risk constraint; default ₹3,000 per trade.
- Maximum trades per day; default 2.
- Direction/option-type consistency validation.

### Execution/data boundary

Implemented in the surrounding ORB/TrueData services:

- Canonical ORB provider representation.
- TrueData tick/quote integration controls.
- OI validation controls.
- Bid/ask validation controls.
- Quote freshness controls.
- Liquidity filtering before option selection.
- Existing universal execution ownership: strategy does not define its own Paper/Live or Manual/Auto mode.
- Execution remains separated from the signal engine.

## 3. Default strategy parameters

| Parameter | Default |
|---|---:|
| Bar interval | 5 min |
| Opening range | 15 min |
| Opening range | 09:15-09:30 IST |
| Entry window | 09:30-12:00 IST |
| Breakout threshold | 0.15 ATR |
| Volume multiplier | 1.15x |
| VWAP slope lookback | 3 bars |
| ATR period | 14 |
| Initial stop buffer | 0.10 ATR |
| Trail | none (Trading Mode owns trailing once a position is open) |
| Target | 2R |
| Option moneyness | ATM |
| ITM/OTM steps | 1 |
| Max risk | ₹3,000/trade |
| Max trades | 2/day |
| Max spread | 1.5% of mid |
| Minimum option volume | 1,000 |
| Minimum OI | 10,000 |
| Quote freshness | 15 sec |
| Expiry DTE | 0-7 |
| Fresh-install enabled | No |

## 4. Data policy

TrueData advanced data is intended to improve the **quality of the execution vehicle and validation boundary**, not to replace the underlying ORB signal with a second strategy.

The separation is deliberate:

```text
Underlying price structure
    -> ORB/VWAP/ATR signal

TrueData advanced option data
    -> quote validity
    -> spread
    -> OI
    -> volume
    -> freshness
    -> contract quality

Both
    -> risk sizing
    -> execution admission
```

This prevents the ORB strategy from becoming an accidental Adaptive Edge clone while still using advanced market data where it has direct causal value.

## 5. Execution ownership

ORB does not own the account's Paper/Live switch or Manual/Auto switch.

```text
ORB enabled        -> whether ORB may generate signals
Paper / Live       -> universal account mode
Manual / Auto      -> universal execution mode
```

A strategy-local `paper_only` control is not permitted.

## 6. Backtest integrity

The underlying ORB backtest is a **signal-validation layer**. It is not historical option P&L.

Option-level performance requires actual historical option contracts and premiums and must model:

- contract availability;
- expiry selection;
- bid/ask spread;
- slippage;
- brokerage and statutory charges;
- option liquidity;
- lot size;
- partial fills;
- quote availability/freshness;
- expiry-day behavior;
- entry and exit execution timing.

No fabricated option P&L is acceptable when those observations are unavailable.

## 7. Current verification state

As of the same-ticket live-ready path:

- ORB targeted backend suite: **358 passed**.
- Frontend feed/adapter: green. Fresh-install `enabled=false`. Auto-off is `status: manual`.
- Historical option corpus, walk-forward, and OOS remain **OPEN** — not unattended-live eligible.

The strategy is **implemented for supervised Paper/Live Manual then Auto**, not yet production-trustworthy for unattended automated options trading.

## 8. Exact next implementation sequence

Same-ticket Manual/Auto path, restart recovery, and default-off are **done** on
`feature/orb-live-ready`. Remaining for unattended live is **P8**: historical
option corpus + walk-forward / OOS (see IMPLEMENTATION_STATUS.md). The items
below are the original engine-hardening sequence and are already closed.

### P0 — make the signal contract mathematically testable

1. Repair `bars_for_breakout()` fixtures so they genuinely satisfy all canonical signal conditions: OR breakout, VWAP alignment, positive/negative VWAP slope, ATR threshold, volume confirmation, and valid regime.
2. Add explicit tests for each individual gate, not only an all-filters-positive fixture.
3. Add tests proving that removing each gate produces `NONE`.
4. Keep the 09:15 opening-range anchor independent from the entry window.
5. Keep completed-bar semantics explicit in realtime tests.
6. Commit the zero-volume-threshold division guard only if zero is an intentionally supported configuration; otherwise reject zero during configuration validation. Prefer rejecting invalid zero thresholds over silently changing strategy semantics.

### P1 — finish option-selection semantics

7. ~~Define `expiry_selection` precisely.~~ Done: `nearest`/`weekly`/`monthly`/`any`, resolved against an explicit calendar rule, tested on fixed dates.
8. Test expiry selection using fixed dates rather than `datetime.now()` so tests are deterministic.
9. Test ATM/ITM/OTM strike selection across asymmetric strike availability.
10. Test missing bid/ask, crossed markets, stale quotes, low volume, low OI, excessive spread, invalid DTE, and zero/invalid lot sizes independently.

### P1 — complete TrueData advanced-data contract

11. Define one canonical TrueData quote snapshot contract containing timestamp, LTP, bid, ask, volume, and OI.
12. Enforce quote freshness at the provider boundary when freshness is enabled.
13. Enforce OI and bid/ask gates only when their corresponding configuration controls are enabled.
14. Add deterministic tests for stale, missing, crossed, zero, and delayed quotes.
15. Verify that advanced data improves contract admission without entering the underlying directional signal calculation.

### P1 — risk and execution truth

16. Verify premium-domain stop/target translation against actual option price behavior.
17. Verify lot-based sizing against worst-case configured premium risk and actual lot size.
18. Add partial-fill and rejection tests through the universal execution path.
19. Verify duplicate-signal/idempotency behavior across restart/retry.
20. Verify position lifecycle, expiry square-off, and protection arming/disarming end to end.

### P2 — research validation

21. Build historical option replay from real contracts/premiums instead of synthetic option P&L.
22. Include spread, slippage, charges, liquidity, expiry, and partial-fill assumptions from observed data.
23. Run walk-forward and out-of-sample evaluation by regime.
24. Measure expectancy, profit factor, drawdown, win/loss distribution, adverse excursion, favorable excursion, and trade frequency.
25. Test parameter sensitivity; reject parameter sets that only work in narrow historical regions.
26. Test multiple NIFTY market regimes and expiry contexts.

### P2 — production graduation gate

27. Keep strategy disabled until the complete signal, option, risk, execution, and replay suites are green.
28. Require stable out-of-sample option-level performance after realistic costs and slippage.
29. Require deterministic replay of accepted/rejected orders.
30. Require no unresolved safety or causal-data gaps before unattended automation.

## 9. Explicit non-goals

The following are not part of ORB:

- option selling;
- using option premium to generate the primary directional signal;
- importing Adaptive Edge signals;
- strategy-local Paper/Live switching;
- fabricated historical option P&L;
- weakening liquidity/freshness gates merely to increase backtest sample size.
