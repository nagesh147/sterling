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
| Entry *price rule* | **PASS** | two observed paths: an operator price file (V17) and `first_tick + 10.25` (V1, printed verbatim). An earlier version of this report called the buffer falsified — that was wrong (A232) |
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
| `entry_buffer_points` | **REJECTED** | **`10.25`, OBSERVED** | A higher-quality copy of the 2026-08-20 recording made the entry block legible: `First Tick Price : 102.85`, `Buffer : 10.25`, `Order Price : 113.1`. I had inferred from two sessions that no such buffer existed; they were exercising different code paths, and V17 says so itself ("Using **manual** strike price…"). |

One gap also **closed**: a put-side entry, previously `UNRESOLVED`, is now
observed — the Upstox notification reports `Order for 80/80 was traded at the
price of Rs. 340.10`, against the ~337 put rather than the ~491 call.

None of the three was a misreading — every number was read correctly. The
inferences drawn from them were over-general: rules declared from two or four
samples that happened to agree, or that happened to exercise different code
paths. That is worth stating plainly, because it is the same criticism this
report makes of the strategy's own track record, and it applies to my analysis as
readily as to its.

## What is still not done

**No walk-forward or deflated-Sharpe evaluation.** Three sessions with a
decodable outcome, all winners, all chosen by whoever decided what to record. On
a sample of three with selection bias, an expectancy claim is not available at
any confidence.

**V1's entry block is now fully decoded** — from a 720×1280 copy of the same
recording, not from image processing. Strike 77500, option CE, first tick 102.85,
buffer 10.25, order price 113.10, order id 260820000004685. Every field the
supplied specification asserted about that session turned out to be correct.

The remaining unresolved item is the **2026-08-21 strike**, which its Upstox
notification truncates (`SENSEX26AUG7…`).

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
