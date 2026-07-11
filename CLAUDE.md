<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**ALWAYS use graph tools FIRST** before Grep/Glob/Read.  
The graph is faster, cheaper, and provides structural context (callers, dependents, test coverage, impact) that file scanning cannot.

### When to use graph tools
- Exploring code → `semantic_search_nodes` or `query_graph`
- Understanding impact / blast radius → `get_impact_radius` or `get_affected_flows`
- Code review → `detect_changes` + `get_review_context`
- Relationships → `query_graph` (`callers_of`, `callees_of`, `imports_of`, `tests_for`)
- Architecture → `get_architecture_overview` + `list_communities`

Fall back to `rg` / `fd` / `sg` only when the graph does not cover the need.

### Key Tools
| Tool                     | Primary Use                              |
|--------------------------|------------------------------------------|
| `detect_changes`         | Code review + risk scoring               |
| `get_review_context`     | Token-efficient source snippets          |
| `get_impact_radius`      | Change blast radius                      |
| `get_affected_flows`     | Impacted execution paths                 |
| `query_graph`            | Callers / callees / imports / tests / deps |
| `semantic_search_nodes`  | Find by name or keyword                  |
| `get_architecture_overview` | High-level structure                  |
| `refactor_tool`          | Renames, dead code, etc.                 |

### Workflow
1. `detect_changes` for reviews
2. `get_affected_flows` / `get_impact_radius` for scope
3. `query_graph` (especially `tests_for`) for coverage
4. Graph auto-updates on file changes

---

### v3 Modules & Critical Invariants

**Modules**
- `engines/analytics/`: walk-forward, sensitivity, correlation, performance (pure functions, no I/O)
- `engines/risk/`: slippage, greeks_budget, circuit_breaker (stateful singletons via DI)
- `services/calibration.py`: adaptive state — **always** inject via Depends, never import directly

**Key Invariants (never violate)**
- `CorrelationTracker.update()` is called with 1H close prices on **every** `evaluate()`
- `DrawdownCircuitBreaker.update()` (alias: `CircuitBreaker`) is called **FIRST** in `evaluate()` before any strategy logic
- `CalibrationService.record_trade()` is called on **every** paper_store position close
- Walk-forward: never use test-window data to select threshold (no lookahead)
- Sensitivity sweep runs on first startup + weekly (cached 7 days)
- `app.state` singletons:
  - `dd_circuit_breaker` → DrawdownCircuitBreaker (portfolio drawdown)
  - `circuit_breaker` → existing execution-level CircuitBreaker
  - `correlation_tracker`
  - `calibration_service`

**Note**: Do **not** Grep the v3 modules — use the graph.

---

### Preferred Bash Commands
Use these when available (fall back silently if missing):

- Search content: `rg` (over `grep`)
- Find files: `fd` (over `find`)
- Structural / AST search: `sg` (ast-grep) — especially for TS/TSX
- JSON: `jq`
- YAML / TOML: `yq`
- GitHub: `gh` (PRs, issues, reviews, CI, releases)
- Benchmarking: `hyperfine`
- Circular deps (JS/TS): `madge --circular`
- Dead code (JS/TS): `knip`
- Duplication (JS/TS): `jscpd`
- Typecheck only: `tsc --noEmit` (or `tsc -b --noEmit` in monorepos)

**Never** use `find -exec` or complex `xargs` chains when `fd -x` or `rg -l | xargs` is cleaner.