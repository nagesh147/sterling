# Kite Real-Money Hardening — Design Spec

**Date:** 2026-06-20
**Branch:** KiteEngine
**Status:** Approved (design), implementation in progress

## Motivation

Expert review of the Kite Triple-SuperTrend auto-exec path surfaced several
real-money risks. This spec hardens the live order path and adds an honest
options backtest. Eight workstreams, implemented in five safety-ordered stages.

The headline findings being fixed:

1. **Auto-exec places a naked market BUY with no broker-side stop.**
   `place_order_option(order_type="market_order", stop_loss=…)` drops the trigger
   for market orders (`client.py` `place_order`: `trigger_price` only attached for
   SL/SL-M). The trailing stop existed only as UI reconciliation. → Workstream C/D.
2. **Daily-loss circuit breaker is denominated in USD** (`hard_halt_usd`, reads
   `realized_pnl_usd`) on an INR broker — mis-scaled / inert for Kite. → Workstream A.
3. **Auto-open guard is in-memory only** → double-entry after restart. → Workstream B.
4. **Fixed 1-lot sizing** — no per-trade risk normalization. → Workstream F.
5. **Fills assumed, not confirmed** — order success not verified against fills. → Workstream E.
6. **Paper/live mode not prominently shown.** → Workstream G.
7. **No validated edge** — strategy has never been backtested. → Workstream H.

## Workstreams

### A. Daily-loss breaker → crypto-exclusive
Remove the USD daily-loss gate from the 3 Kite call sites
(`kite_engine/service.py:53` manual, `:97` auto-exec, `kite.py:613` REST).
Kite orders keep kill-switch + idempotency (currency-agnostic). Crypto sites
(`trading.py`, `order_router.py`, `main.py`) untouched.

Implementation: add a `check_daily_loss: bool = True` param to
`assert_safe_to_trade`; Kite call sites pass `check_daily_loss=False`. This keeps
one composite gate (no divergent copies) while making the dollar breaker
crypto-only.

### B. Persist auto-open + startup reconcile
- `state.mark_auto_open` / `clear_auto_open` also persist the per-uid set to DB
  (`kite_engine_auto_open_{uid}`), mirroring `set_config`.
- On load, hydrate `_auto_open[uid]` from DB (lazy, like config).
- On startup (`main.py` lifespan, before auto-scan loop): for each connected
  account, **reconcile against `GET /positions`** — keep flags the broker confirms
  open, clear the rest. Broker is source of truth.

### C/D. Broker stop + tick monitor (user-selectable)
New engine config `stop_mode: "broker" | "monitor" | "both"` (default `both`),
3-way UI toggle.
- **Entry** (mode ∈ {broker, both}): place a GTT/SL-M stop at Zerodha at the ST
  trail price → survives server/WS/laptop death.
- **Tick monitor** (mode ∈ {monitor, both}): `kite_engine/monitor.py`, per-user
  async loop fed by the existing `KiteTicker` WS. On tick for a held contract,
  recompute trail; on breach, market-exit + cancel the stale GTT. As the trail
  tightens, modify the GTT (trail-up).
- The monitor *is* the tick-driven exit engine (intrabar, scan-independent).
- UI reconciliation downgraded to display-only.

### E. WS order-fill tracking
Consume `on_order_update` text-frame postbacks (already decoded in `ticker.py`,
broadcast on `kite_orders:{uid}`). Auto-exec + monitor confirm fills, capture
real fill price (true entry/stop basis), mark COMPLETE/REJECTED from the postback
instead of assuming success.

### F. Per-trade risk sizing
Replace fixed 1-lot: read FO margin via `get_margins()`, read `lot_size`, size so
`(entry_premium − stop_premium) × qty ≤ risk_pct × available_capital`
(default `risk_pct = 1%`, UI-configurable). Floor 1 lot; cap by max-lots guard and
available margin. Premium-at-risk, not notional. Shown in order preview.

### G. PAPER/LIVE header badge
Always-visible badge in `KiteLayout` header (top-right), reading
`useKiteStatus().is_paper`: amber **PAPER** / green **LIVE**, plus a persistent
LIVE tint. Existing ConnectPane banner stays.

### H. Kite options backtest tab (all 3 data modes)
New `'backtest'` pane in `KiteTab.tsx`; endpoint `/api/v1/kite/engine/backtest`
with `data_mode`:
- **synthetic** — ST on real underlying candles, option priced each bar via
  Black-Scholes + theta, real Indian costs (STT/brokerage/GST/slippage). Full
  multi-year history; premium MODELED (honest caveat badge).
- **real** — true fetched premium candles for currently-listed strikes; short
  lookback, small-sample badge.
- **both** (default) — BS history + real-premium calibration overlay showing
  BS-vs-real drift.

Reuse existing `BacktestPanel` rendering (equity curve, histogram, Sharpe/PF/
win-rate/DSR, cost breakdown). Each mode carries an explicit honesty badge.

## Build order (safest first)
1. A (breaker) + B (persist/reconcile) — pure safety.
2. F (sizing) + E (fills) — order-path correctness.
3. C/D (broker stop + tick monitor) — largest, most testing.
4. G (badge) — quick.
5. H (backtest tab) — largest, fully additive, zero live-path risk.

TDD throughout, mirroring existing test patterns. Zero-regression vs the baseline
failing-set (suite has order-dependent flaky tests; compare set-diff, not counts).
Run with `PYTHONWARNINGS=ignore`.

## Key facts (from recon)
- `get_candles(instrument, resolution, limit)` works with NFO option tokens
  (historical premium) — `client.py:700`.
- `get_margins(segment)` → available capital per segment; `instrument_lot_sizes()`
  → lot size per symbol — `client.py:476,257`.
- `on_order_update` text frames wired in `ticker.py:258`, broadcast on
  `kite_orders:{uid}` — `ticker_manager.py`.
- Auto-scan loop starts in `main.py` lifespan (~1560).
- `is_paper` plumbed via `AccountSummaryResponse` + `useKiteStatus()`.
