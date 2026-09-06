/bin/bash: _detect_claude_ctx_mode: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `_detect_claude_ctx_mode'
/bin/bash: _find_skill_entry: line 1: syntax error: unexpected end of file from `for' command on line 0
/bin/bash: error importing function definition for `_find_skill_entry'
/bin/bash: _invoke_claude: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `_invoke_claude'
/bin/bash: _resolve_skill_dir: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `_resolve_skill_dir'
/bin/bash: build_context: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `build_context'
/bin/bash: claude_graphify: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `claude_graphify'
/bin/bash: claude_real: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `claude_real'
/bin/bash: compact_stream: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `compact_stream'
/bin/bash: dedup_lines: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `dedup_lines'
/bin/bash: extract_directives: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `extract_directives'
/bin/bash: get_dynamic_skills: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `get_dynamic_skills'
/bin/bash: get_project_context: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `get_project_context'
/bin/bash: is_new_project: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `is_new_project'
/bin/bash: json_minify: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `json_minify'
/bin/bash: load_claude_mem: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `load_claude_mem'
/bin/bash: read_skill_content: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `read_skill_content'
/bin/bash: strip_markdown: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `strip_markdown'
/bin/bash: sync_graph_cached: line 1: syntax error: unexpected end of file from `{' command on line 0
/bin/bash: error importing function definition for `sync_graph_cached'
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
