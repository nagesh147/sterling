# Sterling — Project Instructions

## A. Tool Priority (All Projects)

### 1) Code exploration & impact → code-review-graph FIRST
ALWAYS use code-review-graph MCP tools before Grep/Glob/Read.

- Exploring → `semantic_search_nodes` or `query_graph`
- Impact → `get_impact_radius` or `get_affected_flows`
- Review → `detect_changes` + `get_review_context`
- Architecture map → `get_architecture_overview` + `list_communities`
- Relationships → `query_graph` (callers_of / callees_of / tests_for / imports_of)

Fall back to `rg` / `fd` / `sg` only when the graph cannot answer.

### 2) Architecture quality → TrueCourse
Use TrueCourse for:
- Circular dependencies, layer violations
- God modules / dead modules / coupling
- Cross-service flows (frontend ↔ backend)
- Spec / intent drift, architecture health

Commands: `truecourse analyze` | `truecourse list` | `truecourse dashboard`

**Rule:** code-review-graph = daily coding & impact. TrueCourse = architecture health.

### 3) Preferred CLI
`rg` (not grep) · `fd` (not find) · `sg` (ast-grep) · `jq` · `yq` · `gh` · `tsc --noEmit`

---

## B. Dynamic Skill Usage (Universal — Token Efficient)

**Rules**
1. Prefer **1–3 skills max** per task. Never load many skills.
2. Match skill to **task type** (table below). If none fit, use tools only.
3. Prefer a good skill over long free-form reasoning.
4. After skills, return to code-review-graph for code exploration.
5. Do **not** use content/social skills (baoyu-post-*, comic, wechat, etc.) unless the user explicitly asks for content/publishing.

### Routing table
| Task type | Tools first | Skills (pick 1–3) |
|-----------|-------------|-------------------|
| Explore / impact / PR review | code-review-graph | `architecture-review`, `requesting-code-review` |
| Architecture (cycles, layers, god modules) | TrueCourse | `architecture-review` |
| Bug / regression | graph if code | `investigate-bug`, `systematic-debugging`, then `verification-before-completion` |
| New feature | graph | `writing-plans` / `make-plan` → `implement-feature` → `test-driven-development` → `verification-before-completion` |
| Planning only | — | `brainstorming`, `writing-plans` |
| Frontend / UI | graph if code | `frontend-design`, `ui-ux-pro-max`, `react-best-practices` (if React) |
| Security-sensitive | graph | `security-review` |
| Docs / slides / sheets | — | `docx` / `pdf` / `pptx` / `xlsx` |
| Context / long session | — | `context-optimization` |
| Unfamiliar area | graph | `smart-explore`, `learn-codebase`, `pathfinder` |

### Core skills (default toolbox)
`systematic-debugging`, `investigate-bug`, `test-driven-development`, `verification-before-completion`, `writing-plans`, `executing-plans`, `implement-feature`, `requesting-code-review`, `architecture-review`, `brainstorming`, `smart-explore`, `learn-codebase`, `context-optimization`, `using-superpowers`, `security-review`

Domain skills (frontend, finance, supabase, baoyu-*, obsidian, etc.) = **on demand only**.

---

## C. Sterling Critical Invariants (Never Violate)

- `CorrelationTracker.update()` with 1H closes on **every** `evaluate()`
- `DrawdownCircuitBreaker.update()` (alias `CircuitBreaker`) **FIRST** in `evaluate()`
- `CalibrationService.record_trade()` on **every** paper_store position close
- Walk-forward: **no lookahead** (never use test window for threshold selection)
- Sensitivity sweep: startup + weekly, cached 7 days
- Singletons: `dd_circuit_breaker`, `circuit_breaker`, `correlation_tracker`, `calibration_service`
- Always inject `CalibrationService` via Depends — never import directly
- Do **not** Grep v3 modules (`engines/analytics/`, `engines/risk/`, `services/calibration.py`) — use graph

---

## D. Style
- Precise and concise
- Small verifiable steps
- Re-check invariants when touching `evaluate()`, risk, or paper_store

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
| ------ | ---------- |
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
