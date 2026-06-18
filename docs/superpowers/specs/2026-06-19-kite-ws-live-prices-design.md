# Kite live prices over WebSocket (kill the REST polling storm)

**Date:** 2026-06-19
**Branch:** KiteEngine
**Status:** Design — awaiting approval

## Problem

The kite terminal runs several always-mounted panes that each poll REST for live
prices: `KiteTicker` (`useKiteLtp`, 5s), `MarketWatchPane` (`useKiteLtp` 5s +
`useKiteQuote` 15s), `TripleSupertrendPane` (`useKiteQuote` 15s), plus transient
consumers (`MarketDataPane`, `SignalDetailPane`, `OrderWindow`). These loops are
independent of the scan and never stop, producing a continuous stream of
`/api/v1/kite/ltp` and `/quote` calls (the network "storm").

A previous fix deduped symbols and collapsed the two LTP loops into one shared
poll. This spec eliminates the hot polling entirely by sourcing live prices from
the **already-existing tick WebSocket**, keeping REST only as a slow
cold-start/fallback path.

## What already exists (no backend work needed)

- `ticker_manager` runs one `KiteTicker` per user and broadcasts decoded ticks to
  the `kite_ticks:{user_id}` channel over `/api/v1/stream/ws`.
- Each tick carries `instrument_token`, `last_price`, `ohlc`, `change`, and
  (full mode) `oi`/`depth`.
- `POST /ticker/subscribe` (auto-starts the ticker via `ensure()`),
  `/ticker/unsubscribe`, `/ticker/status` already exist and take
  `instrument_tokens: number[]`.
- The frontend already consumes a sibling channel this exact way:
  `useKiteOrderUpdates` opens the WS and subscribes to `kite_orders:{userId}`.
- REST `ltp`/`quote` responses include `instrument_token` per symbol, so the
  fallback call doubles as the symbol→token resolver.
- `WatchItem.token` exists; the app uses `'default'` as the channel user-id.

## Design

Two new pieces, and the existing price hooks become tick-backed. **Pane
components do not change** — they keep calling `useKiteLtp` / `useKiteQuote`.

### 1. `useKiteLiveTicks.ts` — module-level singleton tick store

Mirrors the `useAppStream` singleton pattern.

- Opens **one** WebSocket to `/api/v1/stream/ws`; on open, subscribes the
  `kite_ticks:{userId}` channel (userId defaults to `'default'`).
- On each `{type: "kite_ticks", ticks: [...]}` frame, upserts a module-level
  `Map<number /*token*/, Tick>` and notifies React subscribers (via
  `useSyncExternalStore`).
- Reconnect with exponential backoff (2s→30s), same as `useKiteOrderUpdates`.
  Re-subscribes the channel and re-POSTs the desired token set on every
  (re)connect (idempotent server-side).
- **Subscription reconciler** (ref-counted union):
  - `registerTokens(tokens: number[]): () => void` adds to a desired-set with
    per-token refcounts; the returned cleanup decrements.
  - A debounced (~250ms) reconciler diffs desired vs currently-subscribed tokens
    and calls `POST /ticker/subscribe` (added) / `/ticker/unsubscribe` (removed),
    mode `quote`.
- Exposes: `registerTokens`, `getTick(token)`, and a `useTick(token)` /
  `useTicks(tokens)` read hook backed by `useSyncExternalStore`.

### 2. `useKiteLive(symbols, opts)` — shared internal hook

Backs both `useKiteLtp` and `useKiteQuote`. Returns
`Record<symbol, { last_price?, ohlc?, change?, oi?, instrument_token? }>`.

1. Runs the existing REST query at a **slow heartbeat** (default 30s) — purpose:
   (a) cold-start values before ticks arrive, (b) symbol→token resolution,
   (c) fallback when the socket is down or off-hours, (d) `oi`/`depth` refresh
   (quote-mode ticks omit them).
2. Maintains a persistent module-level `symbol→token` cache, populated from the
   `instrument_token` in REST responses **and** from `WatchItem.token` when
   available (so the watchlist resolves instantly without waiting for REST).
3. Registers resolved tokens with the tick store (ref-counted) → drives
   subscription.
4. Reads live ticks by token via `useSyncExternalStore` and **overlays** them on
   the REST snapshot per symbol (tick wins when present). Re-renders on tick.

### Reimplemented public hooks (signatures unchanged)

- `useKiteLtp(symbols, enabled)` → `useKiteLive(symbols, { rest: ltpQuery })`,
  returns the `{ last_price, instrument_token }` shape it returns today.
- `useKiteQuote(symbols, enabled)` → `useKiteLive(symbols, { rest: quoteQuery })`,
  returns the fuller `{ last_price, ohlc, change, oi, depth, ... }` shape.
- `useKiteOhlc` — left as REST (not in the hot path; OHLC is slow-moving).

`canonSyms` dedupe/sort (from the prior fix) is retained.

## Data flow

```
KiteTicker / MarketWatchPane / TripleSupertrendPane
        │  useKiteLtp / useKiteQuote  (unchanged call sites)
        ▼
   useKiteLive(symbols)
        ├── REST query @30s ──► symbol→token + cold-start/fallback/oi/depth
        ├── registerTokens ──► reconciler ──► POST /ticker/subscribe
        └── useSyncExternalStore(tick store) ──► overlay live last_price/ohlc/change
                                   ▲
        kite_ticks WS frame ──► tick store Map<token,Tick>
```

## Edge cases & decisions

- **Off-hours / ticker not running / socket down:** no ticks arrive; panes show
  the REST snapshot (30s heartbeat). No "no data" regression vs today.
- **Cold start:** REST resolves on mount (~1s), so tokens + first prices appear
  immediately; ticks take over once subscribed.
- **OrderWindow depth ladder:** quote-mode ticks omit `depth`. OrderWindow stays
  on a faster REST poll for its single, transient instrument via an explicit
  `heartbeatMs` override (e.g. 5s while the depth panel is open). It is not part
  of the always-on storm, so this is acceptable.
- **OI for options:** quote-mode ticks omit `oi`; it comes from the 30s REST
  heartbeat. Acceptable (OI is slow-moving). Subscribing options in `full` mode
  is a future option, not in scope.
- **Multi-tenant:** userId is `'default'` to match `useKiteOrderUpdates`. If/when
  a real per-user id is wired, both consumers should read it from one place.
- **Unsubscribe churn:** reconciler is debounced and ref-counted so rapid
  pane mounts/unmounts and watchlist edits don't thrash subscribe/unsubscribe.

## Out of scope

- Backend changes (the tick fan-out and subscribe endpoints already exist).
- Migrating OrderWindow depth or `useKiteOhlc` off REST.
- A second public WebSocket (we reuse `/api/v1/stream/ws`).

## Testing

- Unit: tick-store reducer (upsert by token, refcount add/remove, debounced diff
  produces correct subscribe/unsubscribe token deltas).
- Unit: `useKiteLive` overlay (tick overrides REST per symbol; missing tick falls
  back to REST; token resolved from `WatchItem.token` and from REST response).
- `npx tsc --noEmit` clean.
- Manual (DevTools): with the kite terminal open during market hours, confirm
  `/ltp` and `/quote` calls drop to the 30s heartbeat (no 5s loop), one
  `/ticker/subscribe` fires for the displayed token union, and prices still tick
  live in the ticker + market watch + triple-supertrend panes.

## Files

- **New:** `frontend/src/hooks/useKiteLiveTicks.ts` (tick store + subscription
  reconciler + read hooks).
- **Edit:** `frontend/src/hooks/useKite.ts` — add `useKiteLive`; reimplement
  `useKiteLtp`/`useKiteQuote` on top of it; slow REST heartbeat to 30s.
- **Edit (minimal):** `OrderWindow.tsx` — pass a faster `heartbeatMs` for depth.
- Pane components (`KiteTicker`, `MarketWatchPane`, `TripleSupertrendPane`,
  `MarketDataPane`, `SignalDetailPane`) — unchanged.
