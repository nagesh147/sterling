<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

## New modules (v3)

`analytics/`: walk-forward, sensitivity, correlation, performance — no exchange calls
`risk/`: slippage, greeks_budget, circuit_breaker — stateful singletons on SterlingEngine
`services/calibration.py`: persisted adaptive state — always access via dependency injection

### Key invariants
- CorrelationTracker is fed 1H close prices on EVERY evaluate() call
- CircuitBreaker (DrawdownCircuitBreaker).update() is called BEFORE any trade logic in evaluate()
- CalibrationService.record_trade() is called on EVERY position close in paper_store
- Walk-forward results are cached in DB; re-run only when >7 days stale or user forces
- Parameter sensitivity sweep runs on first startup and weekly via background task
- `app.state.dd_circuit_breaker` — DrawdownCircuitBreaker (v3, portfolio drawdown)
- `app.state.circuit_breaker` — existing execution-level CircuitBreaker (DO NOT confuse them)
- `app.state.correlation_tracker` — CorrelationTracker singleton
- `app.state.calibration_service` — CalibrationService singleton

## v3 modules (do not Grep these — use graph)

`engines/analytics/`: walk-forward, sensitivity, correlation, performance — pure functions, no I/O
`engines/risk/`: slippage, greeks_budget, circuit_breaker — stateful singletons via DI
`services/calibration.py`: adaptive state — always inject via Depends, never import directly

### Wire invariants
- CorrelationTracker.update() called on EVERY evaluate() with 1H close
- CircuitBreaker.update() called FIRST in evaluate() before any strategy logic
- CalibrationService.record_trade() called on EVERY paper_store position close
- Sensitivity sweep runs as startup background task; cached 7 days
- Walk-forward: NEVER use test window data to select threshold (lookahead veto)
- `CircuitBreaker` is an alias for `DrawdownCircuitBreaker` — both names valid
