# A232 — Parameter Provenance

Every tunable in `ATMPremiumImbalanceConfig`, with where its value came from.
No value in this table is "optimized" — none has been through a walk-forward or
a deflated-Sharpe gate. Provenance vocabulary:

- `OBSERVED` — printed verbatim in a recording.
- `OBSERVED-DERIVED` — not printed, but forced by printed values via an identity.
- `RECONSTRUCTED` — inferred from a single arithmetic coincidence. Weak.
- `REJECTED` — was proposed, evidence contradicts it.
- `SterlingDEFAULT` — our own safety default; no counterpart in the source bot.

| Parameter | Value | Provenance | Basis |
|---|---|---|---|
| `underlying` | `SENSEX` | OBSERVED | every recording |
| `strike_policy` | `ATM_NEAREST` | OBSERVED-DERIVED | V17 printed `Strike : 77600` with `SENSEX LTP : 77638.86`; 77600 is the nearest 100-pt strike (A231/M5) |
| `expiry_policy` | **`NEAREST`** | OBSERVED-DERIVED | Was `SAME_DAY` (RECONSTRUCTED). Corrected 2026-08-21: V0821 ran on a **non-expiry day** and traded the *monthly* `SENSEX26AUG7…` symbol, which a same-day policy would have refused. Also explains V04's parity anomaly (A231/M7, M8) |
| `signal_rule` | buy cheaper leg | OBSERVED | V17: CE 167.50 < PE 214.85 → bought CE |
| `difference_definition` | **`\|PE − CE\|`** (absolute) | OBSERVED | Was recorded as signed `PE − CE`; the first four recordings all had the put dearer, which makes the two identical. V0821 has the **call** dearer and still prints a positive `154.00` (A231/Q2). Direction comes from which leg is cheaper, never from a sign |
| `minimum_difference` | `0.0` (disabled) | OBSERVED-DERIVED | V17 entered on 47.35 with no threshold line printed |
| `target_points` | **`15.0`** | OBSERVED | literal `Target Hit (+15)` in V17 **and** V1; and V17's trigger fired at 149.10 vs entry 133.40 + 15 = 148.40 |
| `target_basis` | broker average fill | OBSERVED | V17 `Average Price 133.4` = `Entry : 133.4`, while the requested limit was 288.75 |
| `exit_buffer_points` | **`0.50`** | OBSERVED | V17 `149.2 → 148.7`; V1 `127.1 → 126.6`. Identical across two builds |
| `exit_reference` | `BEST_BID` (live L1 depth) | OBSERVED | V17/V1 `EXIT — LIMIT SELL AT BEST BID − BUFFER` |
| `max_entry_attempts` | `3` | OBSERVED | V17 `ENTRY ATTEMPT 1/3 — LIMIT BUY` |
| `max_trades_per_session` | `1` | OBSERVED | all recordings shut the process down after one round trip |
| `session_start` | `09:15 IST` | OBSERVED | `Waiting for Market Open (09:15 IST)...` |
| `quantity` | operator-entered | OBSERVED | `Enter Quantity : 100` (V1); 20 (V17, from `PnL 469.0 / 23.45`); 80 (V0821, from the Upstox notification `80/80`). All multiples of the **externally confirmed** SENSEX lot size of 20 |
| `tick_size` | `0.05` | OBSERVED (external) | Kite instrument master: uniform 0.05 across all 2,396 SENSEX option contracts. Makes the observed `148.70` and `126.60` valid tick-aligned prices |
| `lot_size` | `20` | OBSERVED (external) | Kite instrument master, uniform across the expiry. Confirms `PnL 469.0 = 23.45 × 20` |
| `entry_price_source` | two real paths: `MANUAL_FILE` and `FIRST_TICK_PLUS_BUFFER` | OBSERVED | V17 `Using manual strike price from strike_prices.txt : 288.75 (strike 77600CE)`, `MPP (Upper Circuit) : 1745.45`, `Calculated Order Price (before cap) : 288.75` |
| `entry_buffer_points` (first-tick path) | **`10.25`** | **OBSERVED** | 2026-08-20 prints `Buffer : 10.25` under `FIRST-TICK ENTRY ATTEMPT 1/3`, giving `Order Price : 113.1` from `First Tick Price : 102.85`. This document previously rejected it — see below |
| `stop_enabled` | `false` | OBSERVED-DERIVED | no stop line, no stop field, in any recording |
| `max_hold_seconds` | `0` (disabled) | OBSERVED-DERIVED | no time-stop observed |
| `max_quote_age_ms` | `2000` | SterlingDEFAULT | the source bot has no freshness gate; we will not ship without one |
| `max_ce_pe_skew_ms` | `1000` | SterlingDEFAULT | needed for the SYNCHRONIZED research view only |
| `daily_loss_limit` | required | SterlingDEFAULT | Sterling risk invariant; absent from the source bot |

## `entry_buffer_points = 10.25` — OBSERVED (this document previously rejected it)

**I got this wrong, and the correction matters more than the original claim.**

The 2026-08-20 session's entry block became legible from a higher-quality copy of
the recording, and it prints the buffer as a named parameter:

```
=========================================
STRIKE SELECTED
=========================================
Strike       : 77500
Option Type  : CE
Premium      : 102.85
=========================================
FIRST-TICK ENTRY ATTEMPT 1/3
=========================================
First Tick Price : 102.85
Buffer           : 10.25
Order Price      : 113.1
API Time : 98.19 ms
Order ID : 260820000004685
```

`102.85 + 10.25 = 113.10`. The block is *titled* `FIRST-TICK ENTRY ATTEMPT`, the
buffer is *labelled* `Buffer`, and the resulting `Order Price` is printed. This is
a rule, not a residual.

### Why it was rejected, and why that was wrong

The earlier argument was: V17 prints `First Tick 167.50`, `Order Price 288.75`,
`fill 133.40`, so no `+10.25` exists anywhere, therefore V1's
`113.10 − 102.85 = 10.25` must be open-auction slippage.

The flaw was treating the two sessions as evidence about **one** mechanism. They
are two different code paths, and V17 says so in its own output: *"Using
**manual** strike price from strike_prices.txt"*. The word "manual" implies an
automatic alternative, and V1 is that alternative. Both are real:

| Session | Path taken | Order price |
|---|---|---|
| V17, 2026-07-30 | `MANUAL_FILE` — `strike_prices.txt` had an entry for 77600CE | 288.75 (from the file) |
| V1, 2026-08-20 | `FIRST_TICK_PLUS_BUFFER` — automatic | 113.10 = 102.85 + 10.25 |
| V0821, 2026-08-21 | first tick 379.0 printed; fill 340.10 | consistent with a marketable limit at 389.25 filling better |

`FIRST_TICK_PLUS_BUFFER` is therefore no longer research-only, and
`entry_buffer_points = 10.25` is `OBSERVED`.

### The `OPEN PRICE CHECK (reference only)` block does not contradict this

The newest build prints `First Tick Used` beside `Official Open` under a heading
that says *reference only*. That block is a **diagnostic comparing the tick the
bot used against the exchange's official open** — it is not a statement that the
first tick is unused for pricing. Reading it as the latter was part of the same
mistake.

### What this says about the method

The self-consistency checks that caught genuine transcription errors could not
catch this, because nothing here was misread. The error was inferential: a rule
was declared from two sessions that happened to exercise different branches.
That is the third such correction in this document — see below — and all three
share one cause: **too few samples, too much confidence.**

## Consequence for the strategy's identity

Three numbers are now observed as named parameters: `target_points = 15.0`,
`exit_buffer_points = 0.50` and `entry_buffer_points = 10.25`. The entry price
has two real paths — an operator price file, and `first_tick + buffer` when the
file has no entry for the strike.

The alpha claim is still: *buy the cheaper ATM leg at the open and take +15
points.* Entry-price mechanics affect the fill, not the hypothesis, so that
sentence remains the thing needing validation.
