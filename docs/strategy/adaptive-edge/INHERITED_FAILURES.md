# Adaptive Edge — what the archive merge inherited, and how it was resolved

`strategy/adaptive-edge` is the six archived adaptive-edge branches merged back
onto `main` on 2026-08-27. They were cut as tags
(`archive/2026-08-27/adaptive-edge-*`) before the branch cleanup.

The merge itself was clean: measured test-id by test-id, the failing set after
merging was exactly the union of the six tags' own failing sets — 42 = 42, zero
new. Nothing below was caused by combining the branches. They were pushed
broken, and six test files could not even be imported.

**The suite is now green: 4290 backend passed / 0 failed, 953 frontend, `tsc`
clean.** This records what the failures actually were, because several were not
what they looked like.

## The engine is still not executable

That property was never traded away to get a green suite, and it is now
asserted from both sides:

```
formula gate authorized  : False | required_strategy_formula_not_implemented
promotion gate authorized: False | strategy_promotion_required
strategy executable      : False | required_strategy_formulas_unresolved
```

## What the failures were

**One import spelling, two module identities.** Twenty-two tests imported
`backend.app.engines...` while the other 387 files use `app.engines...`.
`backend/pytest.ini` sets `testpaths = tests`, so the suite runs from
`backend/`, where those 22 could not be collected at all. Run from the repo root
instead, where both spellings resolve, the same module is imported twice and
every class exists as two unrelated objects — so `pytest.raises` did not catch
exceptions the code raised correctly, and reported `DID NOT RAISE`. Several
"failures" were only ever that.

**Five APIs that existed only as tests.** `ReplayBar`, `ReplayError`,
`build_folds`, module-level `snapshot`/`update_peak_pnl`, and the whole
`state_machine` module were imported by tests but defined in no commit on any
branch. `kite_adapter.py` imported `ReplayBar` too, so it was production code
that could not import. They are implemented now.

**Two generations of the canonical formulas.** `expected_net_value` took
`(profit, loss, cost)` — EV(s,m) with probabilities applied, which is what
`target_stop_ev` beside it already computed — while every caller passed a single
gross value, as F-004 is specified in two separate contract documents. Same for
`risk_per_unit` and `position_size`, whose callers passed arguments the
signatures did not have.

**Three generations of the execution-authorization model**, disagreeing about
the single most safety-critical question in the engine — what makes a strategy
executable:

| date | model | F-101..F-114 status |
|---|---|---|
| 2026-08-11 | deprecated reconstruction | `DEPRECATED` |
| 2026-08-12 | implemented + promotion gate | `IMPLEMENTED` @ 2.1.0 |
| 2026-08-17/18 | governance conformance | `LOCKED` |

One registry entry cannot hold three statuses, so these could not all pass. The
2026-08-17/18 governance model is authoritative here: it is newest, it was the
one already green, and it blocks on the formulas themselves rather than on a
promotion record a single constant could flip. The two older files were rewritten
to assert the same safety property under it.

## Two things deliberately not made green by implementation

**The feature-driven backtester.** `test_adaptive_edge_backtest.py` drove a
`run_replay` that derived a direction from `MarketFeatures` itself. That needs
the F-101..F-114 formulas, which `model.py` removed as invented and says "must
not execute". Writing them back to earn a green tick is the one thing that
removal exists to prevent. The file now tests that the boundary holds: bars
carry data, callers supply decisions, the deprecated model still refuses to run.

**Three asserted values were wrong, not stale.** EV(s,m) for the documented
inputs is `0.6*10 - 0.3*8 - 1.0 = 2.6`, not the asserted 3.2. A valuation
fixture named "availability before observation" passed `T0.replace(minute=9)`,
which is nine minutes *after*. A `links or [default]` helper meant an explicitly
empty list became the default, so the one case that file needed to test never
occurred. In each case the implementation was right.

## Defects found and fixed along the way

- `TrueDataMarketDataAdapter` stamped its own provenance unconditionally, so a
  record arriving labelled `synthetic` was relabelled `truedata` — laundering
  fabricated data into a sequence the replay contract then accepts as real.
- `BarStore`/`TickStore` never persisted or returned `source`/`source_version`.
- `evaluate_economics` treated `net >= minimum` as eligible, so with the default
  threshold of zero an opportunity with no expected profit and real risk was
  eligible. The source rule is `EV_conservative <= 0 -> NO_TRADE`.
- `evaluate_economics` accepted a negative execution cost, which inflates net
  value and turns unviable opportunities eligible.
- `dispatch_order`'s `formula_ids` *replaced* the required formula scope instead
  of widening it, so naming one already-implemented formula authorized a
  dispatch and skipped the fourteen that govern whether the strategy may trade.
