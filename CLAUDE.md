# Use the optimized version we already prepared
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
- Walk-forward: **no lookahead**
- Sensitivity sweep: startup + weekly, cached 7 days
- Singletons: `dd_circuit_breaker`, `circuit_breaker`, `correlation_tracker`, `calibration_service`
- Always inject CalibrationService via Depends
- Do not Grep v3 modules — use graph

## 3. Preferred Tools
- `rg` (not grep) | `fd` (not find) | `sg` | `jq` | `yq` | `gh` | `tsc --noEmit`

## 4. Skill Usage Strategy (Token Efficient)
Use skills selectively (1–3 max per task). Prefer good skills over long free-form reasoning.
Preferred: investigate-bug, systematic-debugging, implement-feature, writing-plans, architecture-review, verification-before-completion, test-driven-development, smart-explore

## Style
Be precise. Always re-check invariants when touching evaluate(), risk, or paper_store.
EOF