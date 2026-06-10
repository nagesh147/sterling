# Paper-Book Demo Dashboard (Pro + Guided) — Design

**Date:** 2026-06-10
**Branch:** `feat/dsr-deflation-gate`
**Status:** approved (design); spec under review
**Scope:** Phase 2, Slice 1. Read-only. Touches the live app only by ADDING an
isolated read-only endpoint + a new frontend tab — no live-engine logic changes,
no `study.*` imports from `app/`.

## Problem / goal

The conviction regime book is the project's strongest result — a real
out-of-sample edge (OOS +75.8% / Sharpe 1.57 / **DSR 0.327**, paper-trading
+71.6% / Sharpe 2.35 live since 2025-09-07) — but it is **not deflation-provable
(DSR < 0.5) and is paper-only**. There is currently no way to *see* it. This slice
builds a judge-ready dashboard that surfaces the genuine paper book honestly, in
two layouts (the brief's "Pro" + "Guided"), without fabricating anything and
without implying live-money trading.

## Honesty framing (drives every design choice)

- **NOT-LIVE guardrail:** a persistent `RESEARCH · PAPER · NOT LIVE MONEY` banner
  above both views.
- **Two real, separated stat sources — never conflated:**
  1. **Backtest validation** (static constants w/ provenance): OOS +75.8% /
     Sharpe 1.57 / **DSR 0.327** / IS→OOS corr +0.38, "as validated 2026-06-10,
     see `docs/funding_sleeve_result.md` + `docs/regime_book_before_after.md`."
     Served as labeled constants — **never presented as a live recompute.**
  2. **Live paper-forward** (read from `state.json` `realized`): ret +71.6% /
     Sharpe 2.35 / maxDD −29.9% / n 146 since inception 2025-09-07.
- **The DSR-0.327 "real but not provable → paper-only" verdict is shown front and
  center**, not buried.
- **No fabricated chrome:** the validated book is futures-direction only (no
  options legs), so there are **no Greeks / vol-curve / options panels.** Showing
  them would be fiction — explicitly excluded.

## Architecture — three thin, single-responsibility units

### 1. Backend: `app/api/v1/endpoints/paper.py`
`router = APIRouter(prefix="/paper", tags=["paper"])`, wired in `main.py` as
`app.include_router(paper_router, prefix="/api/v1")` alongside the others.
**Reads `data/paper/{state.json,trades.csv}` as FILES — imports no `study.*`
module** (the isolation invariant; asserted by a test). Demo-safe: missing or
malformed files return `200 {"available": false}`, never a 500.

Routes:
- `GET /api/v1/paper/state` → parsed `state.json` plus derived fields:
  - `return_pct` = `total_equity / capital − 1`
  - `equity_curve` = `cumprod(1 + realized.weighted_pnls) * capital` (list of
    floats — the curve comes straight from the persisted weighted pnls, no
    recompute). This is **realized** (closed-trade) equity; it ends at
    `realized.end` ($857.76), which is **below** `total_equity` ($889) by the
    open-position unrealized PnL. The Pro view labels the curve "realized
    (closed) equity" and annotates the final `total_equity` (incl. open) as a
    separate marker, so the curve-end vs hero-number gap is explained, not hidden.
  - `buffer_to_trip` = `breaker.threshold − breaker.drawdown` (drawdown headroom
    before the kill-switch trips) and `tripped` passthrough
  - passthrough: `total_equity, realized{ret,sharpe,max_dd,n}, open_positions,
    breaker, asof, inception, n_closed, capital`
- `GET /api/v1/paper/trades` → `trades.csv` parsed to a list of row dicts (the
  closed-trade ledger for the Pro table).
- `GET /api/v1/paper/summary` → static backtest-validation block:
  `{dsr: 0.327, oos_sharpe: 1.57, oos_return_pct: 75.8, is_oos_corr: 0.38,
  provable: false, verdict: "<the paper-only caveat string>",
  provenance: "validated 2026-06-10; docs/funding_sleeve_result.md"}`.

### 2. Frontend hook: `src/hooks/usePaperBook.ts`
React Query hooks `usePaperState() / usePaperTrades() / usePaperSummary()` over
the existing `api` wrapper (`src/utils/api.ts`), with typed interfaces mirroring
the endpoint shapes. Manual refresh via `refetch` (no websockets — book updates
every 4h).

### 3. Frontend tab: `src/components/paper/PaperResearchTab.tsx` (+ subcomponents)
Registered in `src/pages/Dashboard.tsx`: add `'paper'` to the `Tab` union, an
entry to `TABS` (label `PAPER RESEARCH`, a free shortcut key), `TAB_KEYS`, and one
`{activeTab === 'paper' && <PaperResearchTab/>}` render branch. A `mode`
toggle ('guided' | 'pro') switches layout over the **same** hook data.

- **Guided (judge view):** hero `$500 → $889 (+77.8%)`; the one-line verdict
  ("real OOS edge, Sharpe 1.57; **DSR 0.327 < 0.5 → not deflation-provable →
  paper-only**"); current positions (short BTC/ETH/SOL) with unrealized PnL;
  kill-switch `ARMED · {buffer_to_trip}% buffer`; one-line "how it works."
- **Pro:** equity curve (reusing `src/components/EquityCurve.tsx` /
  `lightweight-charts`) fed by `equity_curve`; closed-trade ledger table (from
  `/trades`); per-position detail (entry / SL / TP / weight / unrealized);
  drawdown-vs-kill-switch gauge (`breaker.drawdown` vs `threshold`); regime/sleeve
  state per position; validation-stats panel (`/summary` + the caveat).

## Data flow

existing 4h cron → `study.paper_trader` writes `data/paper/{state.json,trades.csv}`
→ `/api/v1/paper/*` reads files → React Query hooks → `PaperResearchTab`
(Guided | Pro). One direction, read-only.

## Error handling

- Backend: file-missing / JSON-or-CSV-parse-error → `200 {"available": false,
  "reason": "<msg>"}`. No path raises a 500 for a demo.
- Frontend: `available === false` → a friendly "paper book not yet generated — run
  `python -m study.paper_trader`" empty state, not a crash.

## Testing

- **Backend** (`backend/tests/test_paper_endpoint.py`, pytest): with a fixture
  `data/paper` (monkeypatched dir): `/state` returns derived `return_pct` +
  `equity_curve` + `buffer_to_trip`; `/trades` returns ledger rows; `/summary`
  returns the static block with `provable=false`; missing files → `available:false`
  (status 200, not 500); **isolation assert** — `import app.api.v1.endpoints.paper`
  pulls in no module under the `study` package (inspect `sys.modules`).
- **Frontend:** `tsc` clean (the project's FE gate; no test runner present). The
  new hook + components fully typed; `Dashboard.tsx` compiles with the new tab.

## Non-goals (deferred or excluded)

- **No shadow-OrderRouter, no live-trade controls, no promotion-to-live** — the
  book is DSR < 0.5; live execution stays out (a later slice only if ever
  warranted).
- **No options / Greeks / vol-curve panels** — the book has no options legs;
  fabricated chrome is the anti-pattern this project exists to avoid.
- **No websockets / real-time push** — 4h cadence → fetch-on-load + refresh.
- **No live-engine logic changes** — only an additive read-only endpoint + tab.
