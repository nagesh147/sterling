# Adaptive Edge — inherited failures

`strategy/adaptive-edge` is the six archived adaptive-edge branches merged back
onto `main`. They were cut as tags (`archive/2026-08-27/adaptive-edge-*`) before
the 2026-08-27 branch cleanup and merged here on 2026-08-27.

**This branch is red, and it was red before the merge.** The merge added nothing:
the failing set on this branch is exactly the union of the failing sets of the
six tags, measured test-id by test-id (42 = 42, zero new). Nothing here is a
semantic conflict between branches — every item below was pushed broken.

Do not "fix" these by deleting the tests. They describe work that was specified
and never finished; the tests are the surviving specification.

## 1. Six files that cannot even be collected

Each imports a name that exists in **no commit on any of the six tags** — checked
symbol by symbol, not inferred. The tests were written against an API that was
never committed.

| Test file | Needs | From |
|---|---|---|
| `engines/test_adaptive_edge_backtest.py` | `ReplayBar` | `adaptive_edge.backtest` |
| `engines/adaptive_edge/test_replay.py` | `ReplayError` | `adaptive_edge.replay` |
| `engines/test_adaptive_edge_research.py` | `build_folds` | `adaptive_edge.walk_forward` |
| `engines/test_adaptive_edge_accounting.py` | `snapshot` | `adaptive_edge.accounting` |
| `engines/test_adaptive_edge_state_machine.py` | the whole module | `adaptive_edge.state_machine` |
| `engines/test_adaptive_edge_kite_adapter.py` | (collect error) | — |

A collection error aborts the whole pytest run, so until these are resolved the
backend suite only runs with all six `--ignore`d:

```
pytest backend/tests -q \
  --deselect backend/tests/test_delta_iv_socket.py \
  --ignore=backend/tests/engines/adaptive_edge/test_replay.py \
  --ignore=backend/tests/engines/test_adaptive_edge_accounting.py \
  --ignore=backend/tests/engines/test_adaptive_edge_backtest.py \
  --ignore=backend/tests/engines/test_adaptive_edge_kite_adapter.py \
  --ignore=backend/tests/engines/test_adaptive_edge_research.py \
  --ignore=backend/tests/engines/test_adaptive_edge_state_machine.py
```

## 2. Forty-two failures once those six are ignored

`42 failed, 4217 passed, 11 skipped, 1 xfailed`, in two clusters:

- **24 in the adaptive_edge engine** — decision pipeline, probability model,
  reconstructed edge, economic spec alignment, e2e gate.
- **18 in TrueData replay provenance** — `backend/tests/services/providers/truedata/`.
  All 18 fail identically at `archive/2026-08-27/adaptive-edge-truedata-replay-gate`.

## Green on this branch

Frontend is clean: 953 tests / 98 files pass and `tsc --noEmit` exits 0. The one
thing the merge did break was `zzScratchClaim.test.tsx`, a throwaway swept in by
commit `0f9327c8` ("xx") that never reached main; it is removed here.

The merge touches only `backend/app/engines/adaptive_edge/`, its tests, and docs
— no other backend code and no frontend.
