# Sterling - Project Instructions

## Core Rule: Use Graph First
ALWAYS use code-review-graph MCP tools BEFORE Grep/Glob/Read.

- Exploring → `semantic_search_nodes` or `query_graph`
- Impact → `get_impact_radius` or `get_affected_flows`
- Review → `detect_changes` + `get_review_context`
- Architecture → `get_architecture_overview` + `list_communities`
- Relationships → `query_graph` (callers_of / callees_of / tests_for)

Only fall back to rg/fd/sg when the graph cannot answer.

## Critical Invariants (Never Violate)
- `CorrelationTracker.update()` with 1H closes on EVERY evaluate()
- `DrawdownCircuitBreaker.update()` (or CircuitBreaker) called FIRST in evaluate()
- `CalibrationService.record_trade()` on EVERY paper_store position close
- No lookahead in walk-forward (never use test window for threshold selection)
- Sensitivity sweep cached 7 days
- Do NOT confuse `dd_circuit_breaker` (portfolio) vs `circuit_breaker` (execution)

## Preferred Tools
- Search: `rg` (not grep)
- Find: `fd` (not find)
- AST: `sg` (ast-grep)
- JSON: `jq` | YAML/TOML: `yq`
- GitHub: `gh`
- Typecheck: `tsc --noEmit`

## Skill Usage Strategy (Token Efficient)
Do NOT load many skills by default.  
Only invoke skills when the task clearly benefits from them.

### Recommended Skills by Situation
- Debugging / bugs → `systematic-debugging` + `investigate-bug`
- New features → `implement-feature` + `writing-plans` + `executing-plans`
- Code quality / review → `requesting-code-review` + `architecture-review`
- Planning / complex work → `brainstorming` + `writing-plans` + `make-plan`
- Verification → `verification-before-completion` + `test-driven-development`
- Architecture / big changes → `architecture-review` + `pathfinder`
- Exploration → `smart-explore` + `learn-codebase`
- Context / memory issues → `context-optimization` + `memory-systems`

### Rule of Thumb
- Prefer 1–3 focused skills over many
- Always prefer skills over long free-form reasoning when a good skill exists
- After using a skill, continue with graph tools when exploring code

## Style
- Be precise and concise
- Prefer small, verifiable steps
- Always check invariants when touching risk / evaluate / paper_store logic