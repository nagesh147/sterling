# A275 — Strategy Conformance & Validation Report

Generated from the replay harness, not hand-written. Regenerate with:

```bash
cd backend && PYTHONWARNINGS=ignore python3 -m pytest tests/engines/atm_premium_imbalance/ -q
```

The tables below come from `conformance.build_report`, comparing the **live**
strategy object's own `summary()` against the values decoded from the
recordings. `UNVERIFIED` means the recording never established that field — it
is not a pass, and it is not omitted.

## Conformance

### V17 — SENSEX 77600 CE, 2026-07-30

11 match · 0 mismatch · 1 unverified · conformant: yes

| Field | Observed | Replayed | Verdict | Evidence |
|---|---|---|---|---|
| strike | 77600.0 | 77600.0 | MATCH | A231/M4 |
| option | CE | CE | MATCH | A231/M4 |
| quantity | 20 | 20 | MATCH | A231/X6 |
| entry_order_price | 288.75 | 288.75 | MATCH | A231/E2 |
| entry | 133.4 | 133.4 | MATCH | A231/E6 |
| target | — | 148.4 | UNVERIFIED | A231/X1 |
| trigger | 149.1 | 149.1 | MATCH | A231/X4 |
| exit_order_price | 148.7 | 148.7 | MATCH | A231/X3 |
| exit | 156.85 | 156.85 | MATCH | A231/X4 |
| points | 23.45 | 23.45 | MATCH | A231/X5 |
| pnl | 469.0 | 469.0 | MATCH | A231/X6 |
| attempts | 1 | 1 | MATCH | A231/E1 |

### V1 — 2026-08-20 (canonical)

7 match · 0 mismatch · 5 unverified · conformant: yes

| Field | Observed | Replayed | Verdict | Evidence |
|---|---|---|---|---|
| strike | — | 77500.0 | UNVERIFIED | A231/M4 |
| option | — | CE | UNVERIFIED | A231/M4 |
| quantity | 100 | 100 | MATCH | A231/X6 |
| entry_order_price | — | 103.8 | UNVERIFIED | A231/E2 |
| entry | 113.1 | 113.1 | MATCH | A231/E6 |
| target | — | 128.1 | UNVERIFIED | A231/X1 |
| trigger | — | 128.1 | UNVERIFIED | A231/X4 |
| exit_order_price | 126.6 | 126.6 | MATCH | A231/X3 |
| exit | 126.6 | 126.6 | MATCH | A231/X4 |
| points | 13.5 | 13.5 | MATCH | A231/X5 |
| pnl | 1350.0 | 1350.0 | MATCH | A231/X6 |
| attempts | 1 | 1 | MATCH | A231/E1 |

## Reading the V1 row set

The table above was generated before the higher-quality copy of the 2026-08-20
recording arrived. Its five `UNVERIFIED` rows — strike, option, entry order
price, target and trigger — are now established (A231, V1 table), and the golden
test asserts the order price of 113.10 directly. Regenerating the table will move
them to `MATCH`.

The note below is kept because the reasoning still holds for the one field that
remains inferred:

- `entry` (113.10) is not read off a frame. It is forced three ways: the log's
  own exit fill of 126.60, the broker UI's `Day P&L 1,350.00` **and**
  `Overall P&L 1,350.00`, and `points × quantity` with quantity 100 printed at
  startup. Any two of those pin the third.
- `strike`, `option` and `entry_order_price` are **no longer** placeholders:
  77500, CE and 113.10 are printed in the recording and asserted by the golden
  test.
- `target` is unverified in **both** cases because neither build printed the
  target as a number. It is evidenced instead by the literal
  `Target Hit (+15)` line and by V17's trigger firing at 149.10 against a
  133.40 fill.

## Fidelity by dimension

| Dimension | Verdict | Basis |
|---|---|---|
| Video fidelity | **PASS** | V17 reproduces all 11 established fields; V1 all 7; V0821's put-side entry all 3 |
| Signal fidelity | **PASS** | `Difference = \|PE − CE\|` verified on every legible line across all five recordings; cheaper-leg rule reproduced in **both** directions |
| Quote-model fidelity | **PASS** | independent per-leg caching reproduces the observed one-leg-moved sequences |
| Entry mechanics | **PASS** | 3-attempt limit-buy, upper-circuit cap, fill-not-limit accounting |
| Entry *price rule* | **PASS** | two observed paths: an operator price file (V17) and `first_tick × 1.10` to 1 dp (V1 and V0821, both reproduced exactly). Earlier versions of this report called the buffer falsified, then called it 10.25 points; both were wrong (A232) |
| Exit fidelity | **PASS** | `+15` off the fill and `bid − 0.50` reproduced in both builds |
| Execution fidelity | **PARTIAL** | order lifecycle, reconciliation and broker-side protection modelled and driven end-to-end against a fake broker; not yet exercised against a live Kite session |
| Risk fidelity | **N/A** | the source bot had no risk controls; ours are additions, not reproductions |
| Market-data fidelity | **PARTIAL PASS** | index level, ATM strike, lot size, tick, ladder and expiry listing all MATCH against Kite's own data; option premiums and ticks unavailable |

## Independent market-data cross-check

Run by `tests/engines/atm_premium_imbalance/test_market_crosscheck.py` against
Kite's own data from the offline lake. Skipped, loudly, when the lake is not
attached — never silently reported as covered.

| Field | From the recording | From market data | Verdict |
|---|---|---|---|
| SENSEX at the open, 2026-07-30 | 77638.86 | 77638.86 | **MATCH** |
| ATM strike implied by that open | 77600 | 77600 | **MATCH** |
| Expiry 2026-08-20 listed | yes | yes | **MATCH** |
| Lot size | 20 | 20 | **MATCH** |
| Tick size | 0.05 | 0.05 | **MATCH** |
| Strike ladder spacing | 100 | 100 | **MATCH** |
| 77500 has both legs listed | yes | yes | **MATCH** |

The first row is the strongest single piece of evidence in this whole exercise.
V17's bot printed `SENSEX LTP : 77638.86` at its first post-open tick; Kite's
09:15 IST minute bar for that session opens at exactly 77638.86. Two independent
systems, the same paisa. It simultaneously confirms the decoding, the timing, and
— via the nearest-listed-strike rule — the printed strike of 77600.

Sources: `bars/interval=minute/exchange=BSE/segment=INDICES/265__SENSEX.parquet`
and `instruments/latest.parquet` (114,851 rows, 2,396 SENSEX option contracts).
Prices are stored as `int64 = round(rupees × 10_000)` per `kitelake/config.py`.

### Bar-level replay against Kite — RUN, and it found a defect

Run 2026-08-21 against real Kite minute bars for the traded contract
(`SENSEX26AUG77700PE`, token 212614405):

| Check | Recording | Real Kite bars | Verdict |
|---|---|---|---|
| ATM strike | 77700 | 77700 (index 09:15 open **77701.07**) | **MATCH** |
| Which leg was cheaper | PE | PE — CE open 500.00 vs PE open 356.70 | **MATCH** |
| Entry fill possible in its minute | 340.10 | within [318.00, 356.70] | **MATCH** |
| Target reached | 355.10 | yes, in the 09:16 minute (high 360.00) | **MATCH** |
| First tick | 379.0 | **356.70** | **MISMATCH** |
| Order price | 416.9 | **392.40** | **MISMATCH** |

**All three mismatches are one root cause, and it is a defect in the source
strategy rather than in this implementation.**

The bot priced its entry from a **stale tick**. It used 379.0 when the exchange's
official open was 356.70 — 22.3 points, 6.3% high. 379.0 does not occur anywhere
in the 09:15 bar (318.00–356.70); it sits inside the *previous* session's closing
minutes (373.90–379.90). The `×1.10` rule then amplified the error: 416.90 sent,
against the 392.40 the true open implies.

Our engine reproduces the bot's arithmetic exactly — given 379.0 it produces
416.9, asserted by test. Fed the exchange's real open it produces 392.40. So the
**rule is confirmed and the input is not.**

The build is aware: it prints both numbers under `OPEN PRICE CHECK (reference
only)`. It surfaces the discrepancy and then trades on the stale value anyway.

Consequence for viability: a limit 16.9% through the true open is not a price
opinion, it is "take whatever the book has". That is how the fill landed at
340.10 — *below* the official open. The `+15` target is then measured from a fill
the strategy never controlled, which is a materially weaker claim than "enter at
the open and take 15 points".

### Replay re-run with the fix in place

Same real bars, the carried-over 379.0 fed in first exactly as the feed delivered
it (stamped in the session it actually came from, 2026-08-20 15:33):

| Check | Recording | Real Kite bars | Verdict |
|---|---|---|---|
| ATM strike | 77700 | 77700 | MATCH |
| Which leg | PE | PE | MATCH |
| Entry fill possible | 340.10 | in [318.00, 356.70] | MATCH |
| Target reached | 355.10 | 09:16 minute | MATCH |
| **`stale_price_rejected`** | fed 379.0 | **priced from 356.70** | **MATCH** |
| **`engine_vs_market`** | 392.40 | **392.40** | **MATCH** |
| `first_tick_price` | 379.0 | 356.70 | MISMATCH |
| `entry_order_price` | 416.9 | 392.40 | MISMATCH |
| `engine_vs_recording` | 416.9 | 392.40 | MISMATCH |

7 match · 3 mismatch · 1 unverified.

The three mismatches are the *point*, not a regression: they are the recording
disagreeing with the exchange. `engine_vs_recording` and `engine_vs_market` are
reported as separate rows for exactly this reason — a single "does the engine
match" row would hide which of the two we are matching. Where the source bot was
wrong those answers must differ, and here they do: we side with the market.

Two things had to be fixed in the harness before this re-run meant anything.
The bar-derived quotes were previously **undated**, so the session-origin gate
treated them as unknowable and skipped — the replay would have reported success
while testing nothing. Each quote is now stamped from its own bar. And
`summary()` did not expose the pricing reference, so the rejection could not be
observed; `first_tick_price` is now part of the summary, since an order price
alone cannot show whether it came from a session price.

### The same fault was present in this implementation, and is now closed

Two defects, both found by reading our own code rather than inferred:

1. **The runner discarded the trade clock.** `_tick_to_quote` tested
   `isinstance(ts, datetime)`, but Kite's binary ticker emits `last_trade_time`
   and `exchange_timestamp` as u32 **epoch seconds**. The check therefore always
   failed and the receipt time was written into the exchange stamp — destroying
   the only field that can date a price, and silently breaking SYNCHRONIZED
   mode's skew calculation as well.
2. **Nothing gated on session origin.** The freshness gate measured *receipt*
   age, which a stale-content tick passes trivially: a day-old price received a
   millisecond ago has an age of zero.

The fix is the session-origin invariant in A230 §5, applied identically by the
signal gate and the pricing path. `last_trade_time` alone is consulted — using
`exchange_timestamp` as a fallback would have masked the fault, since a
carried-over price arrives in a packet with a current exchange timestamp. That
mistake was made and then removed during this work; the reasoning is recorded in
`LegQuote.is_session_origin`.

Proven end-to-end in `tests/services/test_atm_premium_imbalance_runner.py`, using
the real prices from this session:

| Feed | Our behaviour |
|---|---|
| CE 500.00 / PE 379.00, both stamped 2026-08-20 15:33 | **no order placed** |
| CE 500.00 / PE 356.70, stamped 2026-08-21 09:15:00.9 | BUY at **392.40** |

and in `tests/engines/atm_premium_imbalance/test_stale_tick.py`, which also keeps
the defective behaviour reachable (`require_session_origin_tick=False`) so the
recordings stay reproducible — and asserts that live mode refuses that setting.

Also confirmed from the real index, for the canonical session: SENSEX opened
2026-08-20 at **77468.45**, whose nearest listed strike is **77500** — the strike
video 1 printed (31.55 away, against 68.45 for 77400).

**2026-08-20's option premiums are not replayable.** That expiry lapsed the day
before this run, so the contract has been removed from Kite's instrument dump and
historical rejects its token. The index check above is the most that session
supports.

Frozen bar values and these conclusions live in
`tests/engines/atm_premium_imbalance/test_real_data_replay.py`, so they survive
the contracts being delisted.

### Harness provenance

`app/services/atm_premium_imbalance_replay.py` fetches the bars and
`engines/atm_premium_imbalance/replay.py` does the comparison. The harness is
proven by 11 fixture tests with a negative case for every positive one — a
disagreeing first tick, a target never reached, a fill outside its bar, the wrong
leg cheaper — because a replay that cannot contradict the recording is not a
check. Entry decisions come from the real strategy engine, not from arithmetic
repeated in the harness.

Its ceiling, stated so the result is not oversold: minute bars can confirm the
first tick, the ATM strike, which leg was cheaper, the computed order price and
whether the target was reached. They cannot confirm the fills or the bid-derived
exit price — those are *bracketed*, and a fill outside its bar is a mismatch,
which is the strongest statement bars support. Tick ordering is untestable at
this granularity.

Sessions: `2026-08-21` replayed in full (above). `2026-08-20` index-only, its
option contract delisted. `2026-07-30` not replayable at all — that expiry had
lapsed before the instrument snapshot was taken, so its token cannot be
recovered.

### What this cross-check still cannot reach

- **Option premiums.** The lake holds no BFO/NFO bars — only `BSE`, `NSE` and
  `INDICES` segments. So CE/PE levels, the entry fill and the exit fill remain
  checkable only against the recording's own internal arithmetic.
- **Asynchronous leg behaviour.** There are no tick files at all. A one-minute
  bar is a four-way summary of sixty seconds; it cannot evidence the order in
  which two legs updated. This is asserted as a boundary by
  `test_lake_has_no_option_bars_so_premiums_stay_unverified`, which will fail if
  option or tick data ever appears — so the claim cannot silently go stale.
- **2026-08-20 and 2026-08-21.** The lake ends 2026-08-13, so the two most
  recent sessions have no external check at all.

## Corrections made after the first report

Both from the 2026-08-21 recording, and both the same failure mode — four
samples agreeing by coincidence, generalised into a rule:

| Rule | Was | Now | Why it changed |
|---|---|---|---|
| `difference` | signed `PE − CE` | **`\|PE − CE\|`** | V1/V17/V21/V04 all had the put dearer, making signed and absolute identical. V0821 has the **call** dearer (`CE 491.15 \| PE 337.15`) and still prints `154.00`. |
| `expiry_policy` | `SAME_DAY` | **`NEAREST`** | V0821 ran on a non-expiry day and traded the *monthly* `SENSEX26AUG7…`. `SAME_DAY` would have refused to arm. |
| entry buffer | **REJECTED**, then **`10.25` points** | **`10.0%` of the selected leg's first price** | Recorded three ways. Higher-quality copies made both entry blocks legible: `102.85 × 1.10 → 113.1` and `379.0 × 1.10 → 416.9`, both printed to one decimal. No single *points* value fits both (needs 10.25 and 37.90); `+10.25` matches the lower-premium session to within 0.04, which is why the points reading survived one session. |

One gap also **closed**: a put-side entry, previously `UNRESOLVED`, is now
observed — the Upstox notification reports `Order for 80/80 was traded at the
price of Rs. 340.10`, against the ~337 put rather than the ~491 call.

Two of the three were over-general inferences from samples that happened to
agree; the third (`10.25` points) was a genuine misreading of `10.0%` at low
resolution, made credible by an arithmetic coincidence that only breaks at a
higher premium.

Both failure modes are the same criticism this report makes of the strategy's own
track record — too few samples, too much confidence — and it applies to the
analysis as readily as to the strategy. The practical lesson: an identity that
holds at one price level proves very little. It took a session at four times the
premium to separate `+10.25` from `×1.10`.

## What is still not done

**No walk-forward or deflated-Sharpe evaluation.** Every session with a decodable
outcome was a winner, and all were chosen by whoever decided what to record. On a
sample this small with selection bias, an expectancy claim is not available at any
confidence.

**Two items remain genuinely open**, both by absence of evidence rather than
illegibility: no recording shows a minimum-difference threshold (A231/S3) or any
stop-loss or time-stop (A231/X7). Absence cannot be upgraded by better video;
only source access would settle them.

**V1's entry block is now fully decoded** — from a 720×1280 copy of the same
recording, not from image processing. Strike 77500, option CE, first tick 102.85,
buffer 10.25, order price 113.10, order id 260820000004685. Every field the
supplied specification asserted about that session turned out to be correct.

**The 2026-08-21 entry block is also decoded**: `Strike : 77700`,
`Option Type : PE`, `Premium : 379.0`, `Buffer : 10.0%`, `Order Price : 416.9`,
`Order ID : 260821000004158`. Its Upstox notification truncates the symbol, but
the terminal prints the strike outright.

**V1's entry fill is no longer inferred.** The Upstox notification states it:
`Order for 100/100 was traded at the price of Rs. 113.10`. It had been derived
from `126.60 − 1350.00/100`; the broker now confirms the same number directly.

**The live path is now partly built.** Broker-side protection exists
(`protection_mode` parks a sell at the target on the exchange, so a dead process
still closes the position) and so does a tick-driven runner that hangs off the
Kite tick fan-out rather than polling — because entry happens 1 ms after the
first tick and a 1-second poll cannot express that.

Still missing before live: the daily-loss breaker and premium-at-risk ceiling are
config fields but are **not yet enforced by the runner**, and there is no
position reconciliation on startup. `config.validate()` refuses live without both
broker-side protection and executable quotes, so the gate is code, not
discipline — but the gate is not yet complete.

## Promotion decision

**BLOCKED.**

The mechanics are proven to reproduce. The edge is entirely unevidenced. The
remaining gate items are listed in [A266_RUNBOOK.md](A266_RUNBOOK.md); the
blocking ones are broker-side protection for an open position, a runner with
market-hours gating, risk integration, multi-session tick replay, and a
walk-forward evaluation.

## Test inventory

| Suite | Count | Covers |
|---|---|---|
| `test_signal_and_quotes.py` | 32 | difference identity, independent leg caching, three quote modes, liveness gates, ATM/expiry selection |
| `test_entry_exit.py` | 30 | entry price policies, upper-circuit cap, tick alignment, retry/reconciliation state machine, target and exit pricing |
| `test_golden_trades.py` | 8 | V17 and V1 end-to-end replays, one-trade lifecycle, duplicate-tick protection, halt-on-diverged |
| `test_properties.py` | 9 | seeded invariants over thousands of samples |
| `test_conformance.py` | 6 | report generation, UNVERIFIED handling, parity caveat |
| `tests/api/test_atm_premium_imbalance_api.py` | 6 | published defaults/vocabularies, live-mode refusals, tenant scoping |
| `test_protection.py` | 13 | protective order planning, the cancel-before-exit ordering, halt-on-failed-cancel |
| `test_market_crosscheck.py` | 10 | external comparison logic, plus the real cross-check against Kite data when the lake is attached |
| `tests/services/test_atm_premium_imbalance_runner.py` | 13 | tick normalisation, market/session gating, intent execution, the no-double-order lock |
| frontend `AtmPremiumImbalanceSettings.test.tsx` | 9 | provenance disclosure, research-only marking, conditional fields |

Full suites at time of writing: backend **3340 passed**, frontend **549 passed**,
TypeScript **0 errors**.
