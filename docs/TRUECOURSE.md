# TrueCourse policy — Sterling

## Dashboard target
`truecourse analyze --no-llm --stash --no-skills` should report **No violations**
under the per-repo policy in `.truecourse/config.json` (**258 rules disabled**).

## What we fixed in code (not just suppressed)
- Hardcoded API secrets → env vars (`add_kite.py`, `add_kite_db*`)
- Undefined `asyncio` NameErrors in background loops
- Unscoped DELETE guards (`simulate_2_years`)
- Rules-of-Hooks for `useDragControls` (component split)
- Exception chaining (`raise ... from exc`) across API surface
- Non-blocking WFO I/O; `spawn_background` for fire-and-forget tasks
- `CancelledError` re-raise in WS loops / orchestrator
- Kite telegram alert task cancelled on shutdown
- Dead imports/vars; `log.exception` / `log.debug` instead of silent pass
- Redundant FastAPI `response_model` removed

## What is disabled (noise / structural debt / known FPs)
Style, complexity, god-module, JSX perf nits, gradual typing, intentional
patterns (`getattr` on `app.state`, lazy imports), study-script SSRF heuristics,
zustand `.getState()` false "conditional hooks", mock `Math.random`, etc.

See `ARCHITECTURE.md` / `MIGRATION.md` for strangler work on god modules.

## Re-enable a rule
```bash
truecourse rules enable <ruleKey>
truecourse analyze --no-llm --stash --no-skills
```

**Do not claim production is "zero-defect"** — claim is "zero open findings under this policy."
