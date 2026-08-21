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

Seven fields match, five are unverified. That split is the honest state of the
evidence, and it matters where the gaps are:

- `entry` (113.10) is not read off a frame. It is forced three ways: the log's
  own exit fill of 126.60, the broker UI's `Day P&L 1,350.00` **and**
  `Overall P&L 1,350.00`, and `points × quantity` with quantity 100 printed at
  startup. Any two of those pin the third.
- `strike`, `option` and `entry_order_price` are **placeholders** in the replay.
  V1's entry block sits inside a burst where the phone terminal repaints at
  30 Hz with roughly five pixels of glyph height, so no static frame stack
  exists to super-resolve. The supplied specification's `77500 CE` and
  `first tick 102.85` were not independently confirmed.
- `target` is unverified in **both** cases because neither build printed the
  target as a number. It is evidenced instead by the literal
  `Target Hit (+15)` line and by V17's trigger firing at 149.10 against a
  133.40 fill.

## Fidelity by dimension

| Dimension | Verdict | Basis |
|---|---|---|
| Video fidelity | **PASS** | V17 reproduces all 11 established fields; V1 reproduces all 7 |
| Signal fidelity | **PASS** | `Difference = PE − CE` verified on every legible line across all four recordings; cheaper-leg rule reproduced |
| Quote-model fidelity | **PASS** | independent per-leg caching reproduces the observed one-leg-moved sequences |
| Entry mechanics | **PASS** | 3-attempt limit-buy, upper-circuit cap, fill-not-limit accounting |
| Entry *price rule* | **NOT ESTABLISHED** | operator-supplied per session; the spec's `+10.25` is falsified (A232) |
| Exit fidelity | **PASS** | `+15` off the fill and `bid − 0.50` reproduced in both builds |
| Execution fidelity | **PARTIAL** | order lifecycle and reconciliation modelled; no broker adapter exercised end-to-end |
| Risk fidelity | **N/A** | the source bot had no risk controls; ours are additions, not reproductions |
| Market-data fidelity | **NOT TESTED** | see below |

## What was not done, and why

**No independent market-data cross-check.** The task asked to verify the decoded
prices against real historical SENSEX option ticks for 2026-07-30 and
2026-08-20. I did not do this. TrueData credentials are not available in this
environment, and Kite's historical API does not serve tick data for expired BSE
F&O contracts. Rather than fabricate an alignment table, the evidence matrix
records what the recordings show and marks the rest unresolved.

What replaced it is *internal* arithmetic verification: every numeric read had to
satisfy an identity that the source bot itself computed —
`Difference = PE − CE`, `Points = exit − entry`, `PnL = Points × qty`,
`elapsed_ms = clock − bot_start`, `order = best_bid − 0.50`. Readings that failed
were discarded rather than rounded, which is how `BSE_FO|1141695` was corrected
to `1141595` and `133.47` to `133.40`. Plus one genuinely external check: the
Upstox Positions page in V1 shows `1,350.00`, which the replay reproduces from
the log-derived fills alone.

**No walk-forward or deflated-Sharpe evaluation.** Two sessions, both winners,
selected by whoever chose what to record. On a sample of two with selection bias,
an expectancy claim is not available at any confidence. Nothing here should be
read as evidence the strategy is profitable.

**No live path.** No background runner, no broker-side protection for an open
position, no risk-breaker integration. Live is blocked in `config.validate()`
rather than left to operator discipline.

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
| frontend `AtmPremiumImbalanceSettings.test.tsx` | 9 | provenance disclosure, research-only marking, conditional fields |

Full suites at time of writing: backend **3340 passed**, frontend **549 passed**,
TypeScript **0 errors**.
