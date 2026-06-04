# Contributing

## Golden rule

**Zero regression.** No change may break existing functionality. Prove it with
the failure-set diff in [TESTING.md](TESTING.md), not by eyeballing.

## Workflow

1. Branch off `main` (`feat/...`, `fix/...`). Never commit straight to `main`.
2. **TDD:** write a failing test, see it fail, implement the minimum to pass,
   see it pass, commit. Keep commits small and task-aligned.
3. Run `make verify` before every commit; run the fast full-suite diff before
   merging.
4. Open a PR; merge only when the diff gate is clean.

## Code standards

- **Additive over invasive.** Prefer new modules + facades over rewriting
  working code. Follow existing patterns in the area you touch.
- **DRY / YAGNI.** One construction path, one source of truth (e.g. the broker
  registry delegates construction to the factory). Don't add abstractions
  nothing uses.
- **Small, focused files**, one responsibility each. If a file you touch has
  grown unwieldy, a targeted split is fair game — unrelated refactors are not.
- **Inject dependencies** (see `OrderRouter` / agents) — avoid new global state
  so the system stays horizontally scalable.
- **Pydantic at the boundary.** External inputs are schemas, not raw dicts.
- **Fail-closed** in any safety/risk path.

## Where things go

- Pure contracts → `app/domain/` (no I/O).
- Broker integrations → `app/services/exchanges/adapters/` + `registry.json`
  ([BROKERS.md](BROKERS.md)).
- Strategies → `app/engines/` ([STRATEGIES.md](STRATEGIES.md)); they emit
  `Signal`s and never import an adapter.
- Risk rules → `app/engines/risk/engine.py` ([RISK_MANAGEMENT.md](RISK_MANAGEMENT.md)).
- Agents/bus → `app/agents/`, `app/bus/` ([docs/AGENTS.md](docs/AGENTS.md)).

## Commits

- Conventional prefixes (`feat:`, `fix:`, `chore:`, `docs:`, `test:`), optionally
  phase-scoped (`feat(phase3a): ...`).
- Reference the spec/plan under `docs/superpowers/` for architecture work.

## Knowledge graph

This repo has a `code-review-graph` MCP; prefer it over raw grep for exploring
(see root `CLAUDE.md`). It is a dev aid, not a runtime dependency.
