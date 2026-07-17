# Kite: global chart config + OI Change / Open Interest tabs

**Date:** 2026-07-18 · **Branch:** kite-mobile · **File(s):** `frontend/src/components/kite/InstrumentPane.tsx`, `frontend/src/components/kite/OIView.tsx` (new), `frontend/src/hooks/useKiteOptionChain.ts`, `backend/app/api/v1/endpoints/kite.py`

Two deliverables in one pass: (1) a **bug** — the chart config resets when you switch symbols; (2) a **feature** — two new OI tabs.

---

## 1. Bug: chart config must be "same throughout" (global, not per-symbol)

**Current behaviour.** `ChartView` persists chart state under a **per-symbol** KV key (`kite_chart_state_{user}_{symbol}`). The `[symbol]` effect *resets* tf / indicators / params / zoom / drawings to defaults and reloads that symbol's blob. So switching symbols wipes the view you had set up.

**Desired behaviour (user).** "The chart config including zoom … should be same throughout." Config is **global** across all symbols.

**What is global vs per-symbol.**
- **Global:** `tf`, active indicators, indicator `params`, `isHA`, `isLogScale`, `showVP`, and **zoom** (a visible *time* window is calendar-based, so it applies to any symbol).
- **Per-symbol:** `drawings` only. A trendline drawn at NIFTY 23900 is meaningless on BANKNIFTY 51000, so drawing geometry stays keyed by symbol.

**Storage.** One global KV blob under symbol key `__global__`:
```
{ tf, active, isHA, isLogScale, showVP, params, zoom,
  drawingsBySymbol: { "NSE:NIFTY 50": [...], "NSE:BANKNIFTY": [...] } }
```
Keeps a **single** save path / debounce / flush / keepalive machinery (unchanged), and keeps drawings per-symbol *inside* the blob. Backend change is minimal: add `drawingsBySymbol` (default `{}`) to the GET defaults and the POST whitelist in `save_chart_state`/`get_chart_state`.

**Frontend flow.**
- **Mount (once):** GET `__global__` → set config state, seed `drawingsBySymbolRef`, set `drawings = map[symbol] || []`, set `persistedZoom`.
- **Symbol change:** *no* config reset, *no* GET. Only `setDrawings(map[symbol] || [])` and carry zoom forward: `setPersistedZoom(lastZoomRef.current)` so the same time window is applied to the new symbol.
- **Save (debounced):** POST the full global blob to `__global__`, with `drawingsBySymbol[symbol]` updated to the current drawings and `zoom = lastZoomRef.current`.

**Why zoom carries correctly.** `TradingViewKiteChart` already re-applies a non-null `persistedZoom` on an instrument switch (apply-view block, `isNewInstrument` branch). By no longer nulling zoom on switch and seeding `persistedZoom` from the live `lastZoomRef`, the same visible range is re-applied to the new symbol.

**Tests.** Rewrite `InstrumentPane.persist.test.tsx` to lock the **global** behaviour: config set on A is retained after switching to B (no reset); drawings remain per-symbol; zoom carries; flush-on-unmount / pagehide-keepalive still POST to `__global__`.

**Caveats.** Old per-symbol saved blobs are orphaned (dev branch, not committed) — user reconfigures once; previously-saved per-symbol drawings are not migrated into the new map.

---

## 2. Feature: OI Change / Open Interest tabs

Two new tabs next to **Fundamentals**, each with a small **NEW** badge: `Chart | Option chain | Fundamentals | OI Change | Open Interest`.

**UI.** Sensibull-style horizontal bars by strike, CE vs PE:
- **Open Interest:** *total* OI per strike (CE left/red, PE right/green), diverging from the strike axis. Summary row: total CE OI, total PE OI, PCR, Max Pain, ATM.
- **OI Change:** *change* in OI per strike (positive = build-up, negative = unwind), same diverging layout. Same summary but on ΔOI (change-PCR).
- Expiry pills reuse the existing option-chain expiry selector shape.

**Data.** Both consume the existing `useKiteOptionChain(symbol)` (already polls every 15 s). Total OI is `leg.oi` — real, no new plumbing.

**OI-change source (the one real constraint).** Kite's quote has **no** change-in-OI field, and there is no intraday OI history API. MVP computes ΔOI on the **frontend** against a **day baseline**: the first OI snapshot observed today per `(underlying, expiry, IST-date)`, cached in `localStorage`, diffed on every refetch. Honest label: *"OI change since first snapshot today."* Zero backend change, survives reloads, shared within the browser.
- Not a true "since previous close" figure (would need historical OI per instrument — future enhancement). Clearly labelled.

**No backend change for OI** (the `drawingsBySymbol` change above is the only backend edit).

---

## Verification
- `tsc --noEmit` clean; `InstrumentPane.persist.test.tsx` rewritten + green; new `OIView` unit test (bar math + baseline diff).
- Browser: attempt screenshot of the OI tabs; the Kite tab's motion layer may time out the renderer (known) — fall back to unit tests + honest caveat if so.
