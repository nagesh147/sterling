# Context & token playbook (Sterling)

## Tool ownership
| Need | Tool |
|------|------|
| Callers, impact, PR risk, MCP token savings | code-review-graph |
| Cycles, layers, god modules, violation UI | TrueCourse |
| Code + docs knowledge graph | Graphify |
| Plan / debug / implement / verify | Skills (1–3) |

## Session recipe
1. State goal in one sentence.
2. Plan (if non-trivial) → approve.
3. New Claude session for implementation when plan is large.
4. Use graph tools before Grep/Read.
5. Touch only files in scope; small commits.
6. Stop and re-session if answers get vague or context feels full.

## Avoid
- Dumping whole repo into chat
- Enabling many MCP servers
- Loading many skills at once
- Using strongest model for docs-only work
- Re-explaining CLAUDE.md / invariants every time (point at files instead)

## TrueCourse
- Default: `truecourse analyze --no-llm`
- LLM analyze only when explicitly needed (costly)
