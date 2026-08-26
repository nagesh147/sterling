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
| `entry_price_source` | two real paths: `MANUAL_FILE` and `FIRST_TICK_PERCENT` | OBSERVED | V17 `Using manual strike price from strike_prices.txt : 288.75 (strike 77600CE)`, `MPP (Upper Circuit) : 1745.45`, `Calculated Order Price (before cap) : 288.75` |
| `entry_through_pct` (first-tick path) | **`0.10`** (10.0%) | **OBSERVED** | Both sessions print `Buffer : 10.0%`; `102.85 × 1.10 → 113.1` and `379.0 × 1.10 → 416.9`. See below — this was recorded two other ways first |
| ~~`entry_buffer_points` as a points buffer~~ | ~~`10.25`~~ | **REJECTED** | Arithmetically impossible across both sessions (needs 10.25 and 37.90) |
| `stop_enabled` | `false` | OBSERVED-DERIVED | no stop line, no stop field, in any recording |
| `max_hold_seconds` | `0` (disabled) | OBSERVED-DERIVED | no time-stop observed |
| `max_quote_age_ms` | `2000` | SterlingDEFAULT | the source bot has no freshness gate; we will not ship without one |
| `max_ce_pe_skew_ms` | `1000` | SterlingDEFAULT | needed for the SYNCHRONIZED research view only |
| `daily_loss_limit` | required | SterlingDEFAULT | Sterling risk invariant; absent from the source bot |

## The entry buffer is `10.0%`, not `10.25` points — and I got here the long way

This parameter has been recorded three different ways. The final answer is a
**percentage of the selected leg's first price**, and the evidence is an exact
arithmetic identity that holds in both decoded sessions.

```
2026-08-20                        2026-08-21
STRIKE SELECTED                   STRIKE SELECTED
Strike      : 77500               Strike      : 77700
Option Type : CE                  Option Type : PE
Premium     : 102.85              Premium     : 379.0
FIRST-TICK ENTRY ATTEMPT 1/3      FIRST-TICK ENTRY ATTEMPT 1/3
First Tick Price : 102.85         First Tick Price : 379.0
Buffer           : 10.0%          Buffer           : 10.0%
Order Price      : 113.1          Order Price      : 416.9
```

* `102.85 × 1.10 = 113.135` → printed **113.1**
* `379.00 × 1.10 = 416.90`  → printed **416.9**

Both to one decimal place. The bot rounds to 1 dp, not to the 0.05 tick grid —
harmless, because one-decimal prices are multiples of 0.10 and so always
tick-valid.

### A points buffer is arithmetically impossible

| Session | first tick | printed order price | points needed |
|---|---|---|---|
| 2026-08-20 | 102.85 | 113.1 | **10.25** |
| 2026-08-21 | 379.00 | 416.9 | **37.90** |

No single points value fits both. `10.25` fits 2026-08-20 *by coincidence*,
because at that price level `+10.25` and `×1.10` differ by only 0.035. At 379.0
they differ by 27.65, and the printed value picks the percentage decisively.

`FIRST_TICK_PLUS_BUFFER` is therefore research-only. `FIRST_TICK_PERCENT` with
`entry_through_pct = 0.10` is the observed rule.

### The reference is the SELECTED leg, not the first tick of either leg

`Premium` in `STRIKE SELECTED` and `First Tick Price` in the entry block are the
same number, and it is the chosen leg's price: 102.85 was the CE it bought,
379.0 the PE. Pricing off whichever leg ticked first would have produced 540.3
on 2026-08-21 instead of 416.9 — a test asserts this.

### The three readings, in order

1. **Rejected as slippage.** Reasoning wrong (the buffer is real), conclusion
   accidentally right (10.25 points is not the parameter).
2. **Accepted as 10.25 points.** A misread of `10.0%` at low resolution, made
   credible by the coincidence above. I reported this to the user as a
   correction of (1); it was itself wrong.
3. **`10.0%` of the selected leg's first price.** Fits both sessions exactly.

The lesson is the same one this document keeps recording: an arithmetic identity
that holds at *one* price level proves very little. It took a session at a
four-times-higher premium to separate the two hypotheses.

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
