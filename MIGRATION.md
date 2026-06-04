# Migration — modular architecture hardening

This platform is being hardened **in place** using a strangler-fig approach:
additive modules alongside the working system, no big-bang rewrite, and a
**zero-regression** gate at every step. The full design rationale is in
`docs/superpowers/specs/2026-06-04-modular-trading-architecture-hardening-design.md`.

## Principles

- **Additive first.** New capabilities ship as new modules; existing files are
  not moved or rewritten without test-proven parity.
- **Shadow before authoritative.** Behavior-changing components (RiskEngine,
  SQLAlchemy) run log-only / parallel before they become the source of truth.
- **The diff is the gate.** Regression = a test that fails now but passed at the
  baseline commit. See [TESTING.md](TESTING.md) for the fast diff workflow.
- **Delta Exchange India behavior never changes.** Pinned by the golden smoke
  (`tests/test_golden_smoke_delta.py`).

## Phases

| Phase | Scope | Status |
|---|---|---|
| **0** | Safety net: cleanup, `make verify`, Delta golden smoke | ✅ done |
| **1** | `TradingExchangeAdapter` contract, `app/domain/` models, `registry.json` + loader | ✅ done |
| **2** | Observability: JSON logging, correlation ids, metrics (opt-in) | ✅ done |
| **3** | Event bus + 8 agent facades + Orchestrator + Fill→PNL reference flow | ✅ done |
| **4** | Separated `RiskEngine` + rule registry (shadow-compare) | ✅ done |
| **5** | SQLAlchemy parallel store (dual-write/verify, flag default-OFF, Postgres-ready) | ⏳ planned |
| **6** | Canonical docs + report archival + market seam | ✅ done |

## Phase 5 plan (SQLAlchemy — not yet implemented)

Persistence today is raw `sqlite3` (`app/services/db.py`, `paper_store`,
`calibration`, `ohlcv_store`, `derivatives_audit`). The migration is **parallel
and reversible**:

1. **5a** — Add `app/persistence/` (SQLAlchemy 2.0 models mirroring the sqlite
   schema, session, repositories). Read-only mirror; verified by dual-read tests.
2. **5b** — Dual-write behind `USE_SQLALCHEMY` (default **OFF**). A reconciliation
   check asserts sqlite and SQLAlchemy agree on every write.
3. **5c** — Flip the flag ON after a verification window. Keep the raw-sqlite path
   as fallback for one release. Engine URL from config → PostgreSQL-ready.

No SQLite-specific SQL leaks into the ORM layer so Postgres is a config change.

## Rollback

Every phase is a self-contained set of commits.
- **Phases 1–4** are additive — disabling is removing the new import/flag; the
  old path is untouched.
- **Phase 2** JSON logging and **Phase 4** RiskEngine are gated OFF / shadow by
  default, so rollback = leave the flag off.
- **Phase 6** archival keeps code-referenced reports (`BACKTEST_EDGE_REPORT.md`,
  `DERIVATIVES_EDGE_STUDY.md`) at repo root; the rest live in `docs/reports/`.
- To revert a phase, `git revert` its commits and run the diff gate.

## Verification at each phase

```bash
cd backend
PYTHONWARNINGS=ignore .venv/bin/pytest tests/ -q \
  --deselect "tests/test_delta_iv_socket.py::test_lifespan_starts_iv_stream_only_when_env_set" \
  -p no:cacheprovider
```
Diff the failure set against `main`; it must contain **no test that newly fails**.
Confirm `python -c "import main"` and the golden smoke pass.
