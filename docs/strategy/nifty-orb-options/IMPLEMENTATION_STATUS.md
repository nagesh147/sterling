# NIFTY ORB Options — Implementation Status and Execution Plan

Last updated: 2026-08-20

## Status

**Unit-green and measurement-honest. Not approved for unattended automated options trading.**

```text
250 passed
0 failed          (backend, -k orb)
frontend tsc      clean  (0 errors, down from 2 pre-existing)
```

Verified by isolated-worktree full-suite runs at the pre-work commit and at
HEAD, same command:

```text
baseline   64 failing
HEAD       34 failing
fixed      30
newly broken 0
```

The 34 still red are pre-existing and outside ORB: adaptive-edge (32) and
TrueData tick history (2). The five live-safety / order-router / algo-mode
daily-loss failures are now green -- see finding 14, they were reporting a real
hole, not drifting.

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

## Audit findings closed

A pass over the service, scanner, universe and frontend layers after the suite
went green. Everything here was on a live path.

| # | Defect | Consequence |
| --- | --- | --- |
| 1 | `execute_auto` was an unreferenced second auto-execution path | Passed `positions=[], check_daily_loss=False`, bypassing the daily-loss breaker. On a broker read failure it set `filled = qty`, treating an unfilled order as fully filled. Never checked `armed.protected`. No market-hours, entry-window, liquidity, freshness, drift or premium-budget guard. **Deleted**; `execute_scan` is the only auto path. |
| 2 | Four independent implementations of weekly-vs-monthly expiry | The live Kite scan resolved "weekly" to the nearest eligible expiry, which *is* the monthly during the week it expires -- a weekly mandate bought monthly contracts. **All four now use `is_monthly_expiry`**, and an unmatched preference refuses rather than substituting. |
| 3 | `scan_universe` called `generate_signal` with no clock, and `scan_kite_universe` did not drop the forming candle | The universe scan signalled off an **unclosed bar**. The other two bar adapters filtered; this one did not. Fixed at the choke point so no adapter can reintroduce it. |
| 4 | `build_trade_plan` sized by the modelled stop; the executor sized by the full premium | Measured 16x divergence: the board showed 2400 units of an 18-rupee option (Rs 43,200 of premium) labelled "risk Rs 3,000" while the executor would buy 150. Plan and executor quantities are now identical, and `max_loss_inr` reports the premium actually committed. |
| 5 | `get_config()` loaded a stored config without validating it | An invalid persisted row would surface as an exception deep in the engine mid-session. Now validates on load and falls back to disabled. |
| 6 | The scanner duplicated the TrueData provider's gates in a different order | The same bad tick raised a different error depending on the caller, and either copy could be hardened without the other. Now delegates to `refresh_contract`. |
| 7 | `filter_chain` defaulted to the host's local date, `select_option` to IST | On a UTC host they named different sessions for 5.5 hours a day, shifting every DTE. One IST session date now anchors both. |
| 8 | Scan caches were never evicted | The runner ticks every 5s forever and the option key carries the session date: one dead entry per underlying per user per day. Writes now evict. |
| 9 | `NiftyOrbSignalsPanel` read `s.orHigh`, which does not exist | The opening-range column rendered "—" for every row, always. Two pre-existing `tsc` errors; the frontend typecheck is now clean. |
| 10 | A stop wider than the premium produced `stop_premium = 0.05` | Hold-to-zero presented as a stop. `premium_risk_per_share` is capped at the premium paid. |
| 11 | `_selection_config` appeared to relax liquidity before selection but was a no-op | Removed rather than left to mislead. |
| 12 | Refusals consumed the daily trade budget | `len(executed)` counted every blocked row, so with the default cap of 2 a pair of illiquid candidates exhausted the day before a tradable third was examined. Only fills count now. |
| 13 | An unguarded `_save_state` after a filled, protected entry | A database failure raised out of `execute_scan`, so the day's trade count never persisted and the next 5-second tick would read the stale count and trade past `max_trades_per_day`. Now trips the kill switch and reports `executed_count_not_persisted` -- same failure class as the daily-PnL persistence gate. |
| 14 | The daily-loss circuit breaker was inert for USD-denominated positions | See below. Reachable from `trading.py` and `order_router.py`, **not** from ORB. |

### Finding 14 in detail

`daily_realized_pnl_inr` read `realized_pnl_inr`, falling back to
`realized_pnl` -- but paper and crypto positions expose **only**
`realized_pnl_usd`. Every such position therefore contributed 0.00 and the
breaker reported `clear` regardless of the loss:

```text
configured halt threshold : -500
realised P&L in the book  : -600
what the breaker read     :    0.00
assert_safe_to_trade      : allowed=True     <-- order permitted
```

ORB was never exposed: both of its `assert_safe_to_trade` call sites pass
`uid=`, which routes to `state.daily_realized_pnl_strict(uid)` -- the
authoritative account read -- rather than the positions cascade. A regression
test now pins ORB to that path so it cannot silently inherit the other one.

The cascade now ends at `realized_pnl_usd`, so the breaker halts again. Three
`test_live_safety` daily-loss tests plus one each in `test_order_router` and
`test_algo_mode` were failing on this and are now green; they were encoding the
correct behaviour all along.

**Residual, needs a decision:** `DailyLossConfig` holds a single threshold pair
and accepts either `*_inr` or `*_usd`, storing one number. A book must therefore
be configured in its own currency, and a genuinely mixed-currency deployment
needs separate thresholds. That limitation predates this fix and this cascade
cannot resolve it.

Two hazards introduced by the config-validation work were caught in the same
pass: `scan_one` would have swallowed a `ValueError` from an invalid config once
per instrument and reported an empty scan, and `set_config`'s duplicate of the
TrueData tick/freshness coupling would have drifted from `validate()`. Both are
fixed -- the config is validated once before any fan-out, and the coupling lives
on `validate()`.

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

Also covered since: refusals no longer consume the daily budget, and a failed
trade-count write trips the kill switch instead of silently raising the cap.

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
