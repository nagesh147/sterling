cat > /home/nageshmadaram/Sterling/CLAUDE.md << 'EOF'
# Sterling - Project Instructions

## 1. Graph Tools First (Highest Priority)
ALWAYS use code-review-graph MCP tools before Grep/Glob/Read.

- Exploring → `semantic_search_nodes` or `query_graph`
- Impact → `get_impact_radius` or `get_affected_flows`
- Review → `detect_changes` + `get_review_context`
- Architecture → `get_architecture_overview` + `list_communities`
- Relationships → `query_graph` (callers_of / callees_of / tests_for / imports_of)

Only fall back to `rg` / `fd` / `sg` when the graph cannot answer.

## 2. Critical Invariants (Never Violate)
- `CorrelationTracker.update()` with 1H closes on **every** `evaluate()`
- `DrawdownCircuitBreaker.update()` (alias `CircuitBreaker`) called **FIRST** in `evaluate()`
- `CalibrationService.record_trade()` on **every** paper_store position close
- Walk-forward: **no lookahead** (never use test window data for threshold selection)
- Sensitivity sweep: startup + weekly, cached 7 days
- Singletons: `dd_circuit_breaker`, `circuit_breaker`, `correlation_tracker`, `calibration_service`
- Always inject `CalibrationService` via Depends — never import directly
- Do **not** Grep v3 modules (`engines/analytics/`, `engines/risk/`, `services/calibration.py`) — use graph

## 3. Preferred Tools
- Search: `rg` (not grep)
- Find: `fd` (not find)
- AST: `sg` (ast-grep)
- JSON: `jq` | YAML/TOML: `yq` | GitHub: `gh`
- Typecheck: `tsc --noEmit`
- Avoid `find -exec` / complex xargs — prefer `fd -x` or `rg -l | xargs`

## 4. Skill Usage Strategy (Token Efficient)
Use skills **selectively** and **on-demand** only. Never load many skills at once.

### Preferred Skills by Task
- Debugging / Bugs → `investigate-bug` + `systematic-debugging`
- New Features → `implement-feature` + `writing-plans` + `executing-plans`
- Planning → `make-plan` / `writing-plans` + `brainstorming`
- Code Review → `requesting-code-review` + `architecture-review`
- Verification → `verification-before-completion` + `test-driven-development`
- Architecture / Big changes → `architecture-review` + `pathfinder` + `smart-explore`
- Exploration → `smart-explore` + `learn-codebase`
- Context issues → `context-optimization`

### Rules
- Prefer 1–3 focused skills maximum per task
- Prefer using a good skill over long free-form reasoning
- After using skills, continue with graph tools when exploring code
- Keep full skill content loading only when needed

## Style
- Be precise and concise
- Prefer small verifiable steps
- Always re-check the critical invariants when touching evaluate(), risk, or paper_store logic
EOF