# Testing

## Running the suite

```bash
make verify    # backend pytest + frontend `tsc --noEmit`  (the regression gate)
make test      # backend pytest only
```

**Fast full run** (recommended locally) — the suite emits millions of
third-party `DeprecationWarning`s; capturing them is slow and memory-heavy.
Suppress them:

```bash
cd backend
PYTHONWARNINGS=ignore .venv/bin/pytest tests/ -q -p no:cacheprovider
```

This runs the full ~1250-test suite in well under a minute (vs many minutes with
warning capture).

## Known suite characteristics

- **Order-dependent tests.** A handful of tests (e.g. parts of
  `test_exchanges_account.py`, `test_phase2_selector.py`) pass in isolation but
  fail in the full run due to shared module-level state. `tests/conftest.py`
  resets a lot of global state between tests, but not all. Treat the **failure
  set diff vs `main`** (not the absolute count) as the regression signal.
- **One live-socket test** (`test_delta_iv_socket.py::test_lifespan_starts_iv_stream_only_when_env_set`)
  can hang on a real socket; deselect it for unattended runs:
  `--deselect "tests/test_delta_iv_socket.py::test_lifespan_starts_iv_stream_only_when_env_set"`.

## Test types in this codebase

| Type | Example | Guards |
|---|---|---|
| Unit | `test_order_router.py` | each safety reject path, DI |
| Contract | `test_broker_contract.py` | every order broker satisfies `TradingExchangeAdapter` |
| Registry | `test_broker_registry.py` | every `registry.json` adapter path imports |
| Golden smoke | `test_golden_smoke_delta.py` | Delta factory + paper router response shape (offline) |
| Event/agents | `test_event_bus.py`, `test_agents.py`, `test_orchestrator.py` | bus + facades + reference flow |
| Risk | `test_risk_engine.py` | fail-closed, first-breach-wins, shadow-compare |
| Observability | `test_observability.py` | JSON shape, correlation ids, metrics |

## Zero-regression workflow (for refactors)

1. Capture the baseline failure set at `main` (fast flags above).
2. Make additive changes.
3. Re-run and **diff failure sets**: any test that fails now but passed at
   baseline is a regression — fix or revert. New green tests are fine.
4. Confirm `import main` loads (whole-app import health) and the **golden smoke**
   passes.

## Frontend

`cd frontend && npx tsc --noEmit` (type-check) is part of `make verify`.
