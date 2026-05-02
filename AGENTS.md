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


<claude-mem-context>
# Memory Context

# [Sterling] recent context, 2026-04-27 5:29pm GMT+5:30

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 19 obs (7,269t read) | 76,818t work | 91% savings

### Apr 24, 2026
S37 Caveman mode switched to ultra intensity (Apr 24, 11:33 PM)
S26 Caveman mode switched to ultra intensity (Apr 24, 11:33 PM)
45 11:36p 🟣 Sterling Project Directory Structure Created
46 11:37p 🟣 Sterling Backend Core Config and Logging Implemented
47 " 🟣 Sterling Pydantic Schemas: Instruments and Market
48 " 🟣 Sterling Directional Engine Schemas: Full State Machine and Signal Types
49 " 🟣 Sterling Execution and Risk Schemas Defined
50 11:38p 🟣 Sterling Indicator Engine: ATR, EMA, Heikin-Ashi, SuperTrend Implemented
51 " 🟣 Sterling Instrument Registry and Exchange Adapter Base Class
52 11:39p 🟣 Sterling DeribitAdapter: Full Public-Data Exchange Client Implemented
53 " 🟣 Sterling Directional Engines: Regime and Signal Computation Implemented
54 " 🟣 Sterling Setup and Policy Engines Implemented
55 11:40p 🟣 Sterling Contract Health and Option Translation Engines Implemented
56 " 🟣 Sterling Structure Scoring and Sizing Engines Implemented
57 11:41p 🟣 Sterling DirectionalOrchestrator: Full Trade Cycle Pipeline Assembled
58 " 🟣 Sterling Health Endpoint Implemented
59 11:42p 🟣 Sterling API Endpoints: Instruments and Directional Routes Implemented
60 " 🟣 Sterling FastAPI App Entry Point and Test Fixtures Implemented
### Apr 26, 2026
S38 Caveman mode switched to ultra intensity (Apr 26, 3:27 PM)
S39 User queried available slash commands/skills — checking what exists (Apr 26, 3:44 PM)
S40 Caveman mode switched to ultra level (Apr 26, 3:44 PM)
S50 Caveman mode switched to ultra level (Apr 26, 3:47 PM)
S51 Caveman mode switched to ultra intensity (Apr 26, 4:24 PM)
S52 Memory search for Sterling project — retrieving prior session observations (Apr 26, 10:29 PM)
90 10:40p 🔵 Shell Claude+Graphify Integration in ~/.bashrc
91 " 🔵 ~/.claude/settings.json Full Global Config Structure
92 " 🔵 caveman-statusline.sh — Security-Hardened Status Badge Script

Access 77k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>