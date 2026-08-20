# NIFTY ORB Options — Implementation Status and Execution Plan

Last updated: 2026-08-20

## Status

**Unit-green and measurement-honest. Not approved for unattended automated options trading.**

```text
200 passed
0 failed          (backend, -k orb)
```

Verified against a full-suite run on the pre-work commit: **25 failures fixed,
0 newly broken**. The 39 that remain red are pre-existing and outside ORB
(adaptive-edge, live-safety daily-loss, TrueData tick history).

No production filter was weakened to reach green. Where a test and the
implementation disagreed, the stricter side won and the fixture was rebuilt to
satisfy it.

The strategy remains **long-options-only**:

```text
LONG  -> BUY CE
SHORT -> BUY PE
NONE  -> NO ORDER
```

## Branch consolidation

All ORB work lives on a single branch, `feature/nifty-orb-options`.
`feature/nifty-orb-options-scan` and `feature/nifty-orb-options-universe` were
identical to each other and fully contained in it (zero unique commits), so the
consolidation required no merge. The branch is level with `main`.

## What is implemented

### A. Market structure

NIFTY and a bounded stock/index universe. 5-minute bars, IST-normalized.
15-minute opening range anchored to 09:15 IST regardless of the entry window.
Completed-bar protection for realtime callers.

### B. Signal model

ATR-normalized ORB breakout, VWAP level and slope confirmation, volume
confirmation, TREND/EXPANSION regime requirement, entry-window gate.

A rejected bar now names the first unmet gate rather than reporting "filters not
aligned". The order runs from the strategy's defining condition outwards:

```text
structure     -> no opening-range breakout
magnitude     -> breakout below ATR threshold
location      -> close is not above/below VWAP
direction     -> VWAP slope is not positive/negative
participation -> volume below confirmation threshold
context       -> regime is RANGE / UNKNOWN
```

Each gate has one test that leaves it as the *only* unmet prerequisite.

### C. Configuration validation

`StrategyConfig.validate()` rejects every out-of-range value and runs at
`generate_signal`, `select_option`, `build_trade_plan`, `filter_chain` and the
config PUT. `set_config` delegates its shared rules to it, so an operator cannot
persist a configuration the engine will later refuse mid-session.

The rule is that **an invalid value is a configuration error, never an implicit
bypass**. `volume_multiplier=0` used to disable volume confirmation *and* divide
by zero in the confidence term; it is now rejected. Disabling a liquidity floor
is expressed by setting that floor to zero or by the explicit `truedata_use_*`
switches.

### D. Option model and expiry semantics

CE for LONG, PE for SHORT, strictly. ATM/ITM/OTM with configurable strike steps.
Spread, OI, volume and quote-freshness gates.

```text
nearest  = minimum eligible DTE
weekly   = nearest eligible non-monthly expiry
monthly  = nearest eligible monthly expiry
any      = no preference beyond eligibility
```

Monthly is the last occurrence of that expiry's weekday in its calendar month,
overridable by passing the venue's real monthly-expiry set. The rule lives in
`is_monthly_expiry()` and is shared by the engine and the TrueData provider, so
a provider-resolved expiry and an engine-selected contract cannot disagree about
what "weekly" means. **An expiry preference that matches nothing raises** — it no
longer falls back to a different bucket.

Every DTE decision takes an explicit reference date (`dte_on(today)`), so replay
and live classify a contract identically and the test suite is not a time bomb.

### E. Risk model

Whole-lot quantity, INR risk ceiling, underlying stop representation,
premium-domain protection fields, maximum daily trade count.
`_conservative_quantity` sizes against the **full premium outlay**, because a
bought option can go to zero.

### F. Data architecture

Kite (default) and TrueData normalize into one ORB representation. TrueData
advanced observations improve data quality and contract selection; they are not
a second directional engine.

Every required check at the provider boundary **raises**:

```text
missing quote | stale quote | undated quote | crossed market
invalid bid/ask | excessive spread | insufficient OI | insufficient volume
```

Previously a stale quote could return an empty result a caller might mistake for
"valid, nothing to do".

### G. Costed validation

`validate_option_trades` reported net-of-cost figures under `gross_profit` and
built `profit_factor` from them. Gross and net are now strictly separate, and
every decision metric — win rate, expectancy, profit factor, drawdown — is net.
Reporting a pre-cost profit factor as *the* profit factor is how a costed
strategy gets approved on numbers it never earned.

### H. Option replay

The replay engine models the broker, not the chart. Every default is the
pessimistic one:

| Modelled | Behaviour |
| --- | --- |
| Execution timing | Fill lands `entry_delay_bars` (default 1) after the signal bar. A same-bar fill is refused. |
| Spread | Buy pays the open plus half the quoted spread; sell receives the reference less half the spread. |
| Slippage | Applied to both fills; a statutory cost model carrying its own slippage term is rejected as double-counting. |
| Sizing | `lots * lot_size`, not one lot. |
| Liquidity admission | `ReplayAdmission.from_strategy_config()` mirrors the live spread/volume/OI gates. |
| Partial fills | Size capped at a share of the bar's traded volume, lot-aligned. Too thin for one lot is a refusal. |
| Intrabar sequencing | A bar touching both stop and target resolves as a stop. |
| Expiry | Squared off on the expiry date, not carried to the end of data. |
| Charges | Statutory Indian stack (STT, exchange, SEBI, GST, stamp) on turnover. |
| Impossible stops | A stop wider than the premium paid is refused. |

`replay_signal` returns a `ReplayRejection` with the reason, and the endpoint
reports them under `rejections`. **A replay that silently drops untradeable
signals reports a strategy nobody ran.**

Reported per run: net and gross P&L, total costs, net and gross profit factor,
expectancy, drawdown, average R, MAE, MFE, max consecutive losses, partial-fill
count, exit-reason mix.

### I. Execution architecture

ORB owns neither Paper/Live nor Manual/Auto. It uses the universal account and
execution mode and the shared safety, idempotency and protection
infrastructure. A strategy-local `paper_only` control is forbidden, and a test
asserts no such field exists — a UI flag claiming a safety the shared execution
path never reads is the recurring failure mode this guards against.

## Remaining work

### Step 1 — Execution truth (mostly closed)

`execute_scan` is now driven end-to-end against a fake broker in
`tests/services/test_nifty_orb_execution_e2e.py`. Covered:

| Path | Proven behaviour |
| --- | --- |
| Idempotency | The order carries the tag and the tag is recorded against the broker order id. |
| Duplicate submission | An existing broker order on our tag is adopted, not re-submitted. |
| Tag collision | A tag naming a foreign symbol or a SELL trips the kill switch and places nothing. |
| Same-scan duplicate | Two rows on one underlying produce one order. |
| Broker rejection | A raising `place_order` is reported and nothing is counted. |
| Unknown submission | No order id trips the kill switch: the order may have reached the exchange. |
| Terminal status | A REJECTED order is not cancelled again. |
| Unfilled order | A live unfilled order is cancelled and reconciled. |
| Partial fill | Protection is armed for the quantity *held*, the remainder is cancelled, and `requested_quantity` is reported alongside it. |
| Protection failure | An unprotectable position is closed; if it cannot be closed the kill switch trips. |
| Contract authority | A broker strike/expiry/type disagreeing with the plan is refused before any order. |
| Policy re-checks | Expiry policy, stale signal, liquidity floors, premium risk budget and >0.30% underlying drift each refuse. |
| Daily limit | The count persists, and a second scan returns `daily_limit`. |
| Advisory mode | `auto_execute` off places nothing. |

Still uncovered, and still blocking:

- **restart recovery** — re-reading trade state and open positions after a
  process restart;
- **protection disarming** — the teardown side of `arm_position`;
- **broker-side expiry square-off** — modelled in replay, not yet proven on the
  live path.

### Step 2 — Historical option dataset (open)

The replay engine exists; no historical option dataset has been replayed through
it. Required per contract:

```text
timestamp symbol option_type expiry strike open high low close bid ask
volume open_interest lot_size
```

`require_historical_option_fields` enforces the schema. No synthetic option P&L
derived from underlying points.

### Step 3 — Walk-forward and out-of-sample (open)

Evaluate across separate regimes and periods and report expectancy, profit
factor, net P&L after costs, maximum drawdown, win rate, average win/loss, MAE,
MFE, trade frequency, consecutive losses and parameter sensitivity. Reject
configurations that depend on narrow historical parameter choices.

Until this runs there is **no evidence of edge** — only evidence that the
measurement is now sound.

### Step 4 — Production gate (open)

```text
ORB unit tests green                    [DONE]
        |
        v
provider boundary contract green        [DONE]
        |
        v
costed replay model honest              [DONE]
        |
        v
live order path end-to-end              [DONE]
        |
        v
restart recovery + protection teardown  [OPEN]
        |
        v
historical option replay on real data   [OPEN]
        |
        v
walk-forward                            [OPEN]
        |
        v
out-of-sample stable                    [OPEN]
        |
        v
production safety audit                 [OPEN]
        |
        v
UNATTENDED LIVE ELIGIBLE
```

## Explicit design decisions

1. ORB remains independent from Adaptive Edge.
2. TrueData advanced data improves observation quality and contract selection;
   it does not inject Adaptive Edge-style signal intelligence.
3. The underlying generates direction; the option is the execution vehicle.
4. Only option buying is permitted.
5. Shared execution infrastructure owns Paper/Live and Manual/Auto.
6. Backtests must not fabricate option P&L.
7. Safety and causal-data gates are never removed to make tests or backtests
   look better. Where a test and a gate disagreed, the gate won.
8. An invalid configuration value is rejected, never reinterpreted as a bypass.
9. A refusal is data. Anything that declines to trade says why.
