cat > /home/nageshmadaram/Sterling/CLAUDE.md << 'EOF'
# Sterling - Project Instructions

## 1. Graph Tools First (Highest Priority)
ALWAYS use **code-review-graph** MCP tools before Grep/Glob/Read.

- Exploring → `semantic_search_nodes` or `query_graph`
- Impact → `get_impact_radius` or `get_affected_flows`
- Review → `detect_changes` + `get_review_context`
- Architecture overview → `get_architecture_overview` + `list_communities`
- Relationships → `query_graph` (callers_of / callees_of / tests_for / imports_of)

Only fall back to `rg` / `fd` / `sg` when the graph cannot answer.

## 2. Architecture Quality → Use TrueCourse
For deeper architecture analysis use **TrueCourse**:

- Circular dependencies
- Layer violations
- God modules / dead modules
- Cross-service flows (frontend ↔ backend)
- Architecture health / coupling
- Spec / intent drift

Commands:
- `truecourse analyze` — full analysis
- `truecourse list` — show violations
- `truecourse dashboard` — interactive UI

**Rule:** Use code-review-graph for daily coding & impact.  
Use TrueCourse for architecture quality, circular deps, and structural health.

## 3. Critical Invariants (Never Violate)
- `CorrelationTracker.update()` with 1H closes on **every** `evaluate()`
- `DrawdownCircuitBreaker.update()` (alias `CircuitBreaker`) called **FIRST** in `evaluate()`
- `CalibrationService.record_trade()` on **every** paper_store position close
- Walk-forward: **no lookahead**
- Sensitivity sweep: startup + weekly, cached 7 days
- Singletons: `dd_circuit_breaker`, `circuit_breaker`, `correlation_tracker`, `calibration_service`
- Always inject `CalibrationService` via Depends
- Do **not** Grep v3 modules — use graph

## 4. Preferred Tools
- Search: `rg` | Find: `fd` | AST: `sg` (ast-grep)
- JSON: `jq` | YAML: `yq` | GitHub: `gh`
- Typecheck: `tsc --noEmit`

## 5. Skill Usage Strategy (Token Efficient)
Use skills **selectively** (1–3 max per task). Prefer good skills over long free-form reasoning.

### Preferred Skills
- Debugging → `investigate-bug` + `systematic-debugging`
- Features → `implement-feature` + `writing-plans` + `executing-plans`
- Review → `requesting-code-review` + `architecture-review`
- Verification → `verification-before-completion` + `test-driven-development`
- Architecture → `architecture-review` + `pathfinder` + `smart-explore`
- Exploration → `smart-explore` + `learn-codebase`

## Style
- Be precise and concise
- Prefer small verifiable steps
- Always re-check critical invariants when touching evaluate(), risk, or paper_store
EOF