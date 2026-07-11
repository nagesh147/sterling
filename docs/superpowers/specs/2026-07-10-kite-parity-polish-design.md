# Kite Parity Polish — Design

**Date:** 2026-07-10
**Status:** Approved for implementation

## Context

A deep-dive audit of the Kite (Zerodha-inspired) module found it far more
mature than "work in progress" implied — a near-complete Kite Connect v3
client, a genuinely wired auto-scan/auto-execute engine, and a thorough order
ticket. The real gaps were narrow and specific:

1. Several UI elements in `PortfolioPane.tsx` are decorative (`href="#"`,
   unwired search inputs) — visual parity with real Kite's chrome, zero
   behavior.
2. The order ticket has no path to AMO (after-market orders) despite the
   backend fully supporting the `variety` param.
3. No basket-order flow (stage multiple orders, check combined margin, place
   as a batch) — real Kite Web has this; neither the frontend ticket nor a
   dedicated backend endpoint construct it here (though `margins/basket`
   already exists for the margin-check leg).
4. MCX (commodities) is declared in `constants.py`'s `EXCHANGES` tuple but
   never reaches `universe.py`/`stock_registry.py` — the auto-scan engine
   can't find MCX instruments. Manual MCX order placement already works via
   the generic order route.

This spec covers items 1–3. Item 4 is explicitly deferred (see "Out of
scope").

## Goal

Close the specific parity gaps above without touching the parts of the
module that are already solid (order-type/validity matrix, GTT, positions
math, the Mac motion layer, the auto-engine's core scan/signal/execution
pipeline). No refactor of `SterlingKiteEnginePane.tsx` or test-coverage work
in this pass — that was explicitly deferred by the user in favor of parity
work.

## 1. Wire the dead UI elements (`PortfolioPane.tsx`)

| Element | Where | Treatment |
|---|---|---|
| Search (Positions) | `PortfolioPane.tsx:244` | Client-side filter on `tradingsymbol`/`exchange`, case-insensitive substring match. No backend call. |
| Search (Holdings) | `PortfolioPane.tsx:371` | Same pattern against holdings rows. |
| Download (Positions) | `PortfolioPane.tsx:256` | Export the *currently filtered/sorted* rows to CSV, client-side (`Blob` + `<a download>`), matching real Kite's per-table CSV export. |
| Download (Holdings) | `PortfolioPane.tsx:377` | Same, for holdings rows. |
| Analytics (Positions) | `PortfolioPane.tsx:250` | Modal expanding the existing inline "Breakdown" bar chart: realized vs. unrealized split, per-symbol P&L, and charges pulled from the existing `/charges/orders` backend route (already implemented, just unused by the frontend today). |
| Analytics (Holdings) | `PortfolioPane.tsx:374` | Modal: investment value vs. current value, day P&L vs. overall P&L — all from data already present on holdings rows, no new backend call needed. |
| "Analyze" (Positions) | `PortfolioPane.tsx:247` | Real Kite deep-links this to Sensibull (third-party options-strategy analyzer) — out of scope to build. Repurpose: opens the existing `SignalImpactCalculator.tsx` scoped to the selected position/row instead of a dead link. |
| Settings | `PortfolioPane.tsx:253` | Popover exposing the existing `useKiteSettings` store's display toggles (`showHoldings`, `showNotes`, `showGroupColors`, `showExchange`, `showLeg`, `chgType`, etc.) — this store already exists but isn't surfaced as a dedicated settings UI from Positions/Holdings. No new state needed, just a new small popover component reading/writing the existing store. |

None of this touches the backend.

## 2. AMO order path (`OrderWindow.tsx`)

Real Kite does not expose a manual "AMO" dropdown — it **detects** that the
market is closed and requires an explicit confirmation before placing the
order as AMO. Match that instead of adding a redundant variety selector:

- Add a market-hours check (NSE/BSE/NFO/BFO segment hours; reuse whatever
  exchange-hours knowledge already exists in the codebase, or a small pure
  helper if none does).
- When the order ticket is opened (or the moment it detects closed-market
  state) with the target exchange closed: show an inline notice — "Market is
  closed. This order will be queued as an After Market Order (AMO) for the
  next session." — and require an explicit confirm checkbox before the
  Submit button enables.
- On submit with that state active, send `variety: 'amo'` in the order body
  (currently hardcoded to `'regular'` at `OrderWindow.tsx:123`) instead of
  relying on the backend's silent regular→AMO resubmission fallback.
- `buildOrderBody`/`orderTicket.ts` gets a pure function,
  `resolveVariety(marketOpen: boolean, requestedVariety) -> Variety`, that is
  unit-testable without React.

## 3. Basket orders

Kite Connect has no atomic multi-order placement endpoint — real Kite Web
implements baskets client-side: stage entries, check combined margin via
`margins/basket` (which the backend already exposes), then place each order
individually. This is primarily frontend work.

**State:** new Zustand store `useKiteBasketStore` — array of staged entries
(`{id, symbol, exchange, side, qty, product, orderType, price?, trigger?}`)
plus per-entry placement status once "Place Basket" is fired
(`idle | placing | placed | failed`).

**Entry points to add to basket:**
- `OrderWindow.tsx` — a secondary "Add to Basket" action next to Submit
  (stages the entry instead of placing it immediately).
- Watchlist/positions rows — extend `KiteActionButtons` with a new optional
  `onBasket` callback + icon (the component already has this exact
  add-a-slot pattern via `onAdd`/`onMore`; this keeps existing callers
  unaffected since the prop is optional).

**New `BasketPane.tsx`:** follows the same fixed-position modal-overlay
pattern already used by `OrderWindow.tsx` (backdrop + centered panel) rather
than introducing a new drawer paradigm. Contents:
- List of staged entries: editable qty/price inline, remove-row, BUY/SELL
  color coding (reusing existing pill/color conventions from
  `PortfolioPane.tsx`).
- Aggregate margin summary, fetched from `/margins/basket` on any change to
  the staged list (debounced ~400ms, same debounce pattern as
  `useDebounced.ts`).
- "Place Basket" button — places entries **sequentially** (not
  `Promise.all`) via the existing `usePlaceKiteOrder()` mutation
  (`hooks/useKite.ts:277`), updating each row's status live as its call
  resolves.
- **No automatic rollback on partial failure** — a live order that already
  filled cannot be un-placed. Failed rows stay in the basket, editable, with
  a visible "failed — reason" state so the user can retry or remove them
  individually. This must be explicit in the UI, not silently swallowed.

A basket-open trigger (icon + staged-count badge, matching real Kite's nav
basket icon) goes in `KiteLayout.tsx`'s top bar.

## Out of scope (this pass)

- **MCX auto-engine support** — deferred by user decision, to be picked up
  as a dedicated pass before production rollover. This pass will only add an
  explicit marker: a comment at `constants.py` near `EXCHANGE_MCX` noting
  it's declared but not wired into `universe.py`, and a correction to
  MARKETS.md's "commodities: zerodha" claim to state it's manual-only today.
- Splitting `SterlingKiteEnginePane.tsx` (2159 lines) — explicitly deferred
  in favor of parity work.
- Raising frontend Kite test coverage broadly — deferred; new code written in
  this pass still gets tests (see below), but no retroactive coverage push.

## Testing

- `resolveVariety()` (AMO detection) and any new pure helpers in
  `orderTicket.ts` — unit tests, no React needed.
- `useKiteBasketStore` — unit tests for add/remove/update-status transitions.
- Basket sequential-placement flow — component test mocking
  `usePlaceKiteOrder()`, asserting sequential (not parallel) calls and correct
  per-row status transitions on success/failure/mixed results.
- CSV export and client-side search/filter — light component tests
  (filter narrows visible rows; export triggers a Blob download call).
- Manual verification in a browser (dev server) for all wired UI elements
  and the AMO/basket flows end to end, per this project's UI-change
  verification norm.

## Rollout

All additive — no existing behavior changes except the AMO variety fix,
which only takes effect when the market is actually closed (previously
implicit, backend-only fallback; now explicit and visible). Ship behind no
flag; this is UI-only + one payload field change, low risk, paper/live
distinction is unaffected.
