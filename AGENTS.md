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
# Memory Context — Sterling v4 Hybrid VCP-Momentum Scalper

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE

### Session Context (2026-05-22)

Key work done today — all on the Sterling live trading engine:

**PaperLiveToggle fix** 🔴
- SHADOW button in LIVE mode was opening "go-live-confirm" modal (wrong action)
- PAPER button onClick guarded by `!isLive` so clicking it in SHADOW did nothing
- Fixed: LIVE→SHADOW now directly calls `update({is_paper:true})`, SHADOW/PAPER→PAPER works, PAPER button onClick properly fires regardless of current mode

**Track filter in SignalsTable** 🟣
- Backend: `DirectionalOrchestrator` picks winning track (highest score: vcp/trend_following/mean_reversion)
- `track` field now exposed in `snapshot_cache.SnapshotEntry` + `/signals` response
- Frontend: new pill-row in signal table — ALL / VCP (amber) / TREND (green) / REVERSION (purple)
- Each pill shows live count of signals matching that track
- Count queried from REST signals data, independent of mode filter

**algo_router_mode persistence** ✅
- Mode now survives restarts via `db.set_config("algo_router_mode", body.mode)`
- On startup: `get_config("algo_router_mode") or "live"` → `app.state.algo_router_mode`

**V4AnalyticsDashboard badge fix** ✅
- Was hardcoded "SHADOW TRADING"
- Now polls `http://localhost:8000/api/v1/trading/algo-router-mode` every 3s directly

**Realized PnL in V4 Analytics** 🟣
- `_build_pnl_event` emits `total_realized_pnl_usd` (aggregated from closed positions) + `realized_pnl_usd` per entry
- Frontend `LivePnlEntry` updated with `realized_pnl_usd: number | null` + `total_realized_pnl_usd: number`
- Shows realized below the Open P&L card

**Shadow mode sync** ✅
- `LiveControlPanel.changeMode()` writes to `algo_router_mode` via `POST /api/v1/trading/algo-router-mode`
- `PaperLiveToggle` writes to `is_paper` via `PUT /api/v1/exchanges/{id}` (for paper/shadow switching)
- Custom `sterling-router-mode-change` event broadcasts mode to V4AnalyticsDashboard

**9 active VCP feeds** 🟣
- BTC × 5m/15m/30m/1h/4h + ETH × 5m/15m/30m/1h
- All routed via `config/tracks.yaml` to `[vcp, trend_following]`
- VCP live feeds connect to Delta India WebSocket

### Architecture Notes

`algo_mode` (on/off) — master switch for ALL auto-trading (directional + VCP)  
`algo_router_mode` (paper/shadow/live) — execution dispatcher  
Both enabled → full auto-trading. `signal_strength == "STRONG"` gates every order.

Auto-order path: `_auto_place_algo_order` (main.py) → `OrderRouter.submit()`
VCP auto-trade path: `VCPExecutor.on_bar()` → `OrderRouter.submit()`

### Servers

- Backend: `http://localhost:8000` (uvicorn, port 8000)
- Frontend: `http://localhost:5173` (Vite dev, port 5173)

### Relevant Files

- `backend/app/api/v1/endpoints/directional.py` — signals endpoint, track exposure
- `backend/app/services/snapshot_cache.py` — SnapshotEntry with track field
- `backend/app/engines/directional/orchestrator.py` — best_track.name propagated
- `frontend/src/components/SignalsTable.tsx` — track filter pills + SignalsFeedBody
- `frontend/src/components/PaperLiveToggle.tsx` — 3-way toggle, correct onClick logic
- `frontend/src/hooks/useSignals.ts` — SignalItem with track field

### Out of scope

- Live order routing (paper-only, shadow audit available)
- Multi-exchange routing (single Delta India account)
- WebSocket fill streaming (REST polling sufficient)
</claude-mem-context>