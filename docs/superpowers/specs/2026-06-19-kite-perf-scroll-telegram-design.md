# Kite elite perf pass + Mac scroll + Telegram Kite control

**Date:** 2026-06-19
**Branch:** KiteEngine
**Status:** Design — awaiting approval

Three independent phases, built and verified in order. Each is shippable alone.

---

## Phase A — Elite performance pass (frontend + backend)

Builds on the prior round (warm client cache, search debounce, WS prices). Goal:
remove the remaining hot-path cost and render churn the audits surfaced, plus a
fresh sweep.

### Backend
1. **`detail.py` O(N) signal lookup → O(1) index.** `build_detail` linearly scans
   all scan rows (incl. every leg) per detail open. Add a `token → row` index on
   the scanner `UserScan` snapshot, populated when rows are set; detail does a dict
   lookup. (scanner.py, detail.py)
2. **`state.save_signal_cache` double JSON encode.** It does
   `json.dumps({"rows": json.loads(rows_json), ...})` — parse-then-reencode of a
   ~50KB blob on every scan flush. Pass the already-encoded rows through without the
   round-trip. (state.py)
3. **Greeks IV solve: bisection (64 iters) → Newton-Raphson w/ bisection fallback.**
   `greeks.implied_vol` runs 64 Black-Scholes evals per leg on the after-hours path.
   Newton converges in ~5–8 iters; keep bisection as the safety net. (greeks.py)
4. **Offload large `model_dump`.** Serializing 500+ signal rows on the scan-flush
   path blocks the loop; wrap in `asyncio.to_thread` above a row threshold.
   (scanner.py flush)
5. **Sweep:** verify response payloads aren't over-fetching (trim unused fields in
   signals/detail responses where safe); confirm no other per-request full-dump or
   sequential-await patterns remain.

### Frontend
6. **Zero-dep virtualization via `content-visibility`.** Add a `.kv-rows` utility
   (`content-visibility: auto; contain-intrinsic-size: <row-h>`) applied to the
   long lists: SterlingKiteEnginePane signal rows, InstrumentPane option chain,
   instrument search results. Skips layout/paint for off-screen rows — near-virtual
   perf, no library. (No `react-window` dep added.)
7. **Per-row Greeks + sort memoization.** Memoize `computeGreeksFromSymbol` per row
   (`useMemo` keyed on symbol + that symbol's quote/ltp), and ensure `sortedWatch` /
   `groupedRows` only resort when the sort-relevant values change, not on every tick
   object-identity churn. (SterlingWatchList, SterlingKiteEnginePane)
8. **Stabilize tick-derived references.** `useKiteLive` returns a fresh object each
   tick; downstream sorts/filters key off it. Where a consumer only needs prices for
   display (not reorder), avoid putting the whole map in a memo dep — derive a
   compact signature instead.
9. **React Query hygiene:** confirm `staleTime` set on static-ish queries
   (instruments/lots already 1h), structural sharing on, no array/object literals in
   query keys.

**Verification:** `tsc` + `npm run build` clean; backend `pytest` kite suite green;
add a focused unit test for the scanner token-index and the IV solver.

---

## Phase B — Mac-style scrolling (app-wide)

macOS feel on Linux/Windows: overlay scrollbars that are invisible at rest, fade in
thin + rounded on hover/scroll, with contained overscroll and smooth behavior.

- **Global CSS** (globals.css + terminal.css): replace the always-on 4–6px bars with
  an overlay style — transparent thumb at rest, revealed on container `:hover` and
  while scrolling; thin (8px), fully rounded, semi-transparent neutral that tints to
  brand on hover. Firefox: `scrollbar-width: thin; scrollbar-color`.
- **`overscroll-behavior: contain`** on the main scroll containers (panes, feeds,
  tables) so wheel scroll doesn't chain to the page/body (a key part of the native
  feel and prevents the whole terminal bouncing).
- **`scroll-behavior: smooth`** applied to programmatic-scroll containers only (not
  globally — it interferes with virtualization and instant jumps).
- **Auto-hide while idle:** a tiny shared hook/util toggles a `scrolling` class on
  scroll, removed ~800ms after the last scroll event, so the bar fades out like
  macOS. Applied via a `.mac-scroll` class on scroll containers; opt-in, not forced
  on every element, to avoid surprising fixed/overflow-hidden regions.

**Verification:** visual QA via gstack screenshots (per the project's headless QA
pattern) at desktop widths; confirm bars hide at rest, reveal on scroll/hover, and
overscroll doesn't chain.

---

## Phase C — Telegram Kite control (separate from crypto)

Extend the existing single bot (long-poll, single configured chat) with a **separate
Kite command tree + menu**, keeping the crypto bot untouched. Full control incl.
**place/close orders**, gated by **two-tap confirm**.

### Module boundary
- **New `app/services/notifications/telegram_kite.py`** owns all Kite text builders,
  inline keyboards, callback handlers, the alert push, and the order/confirm flow.
- **`telegram_bot.py`** stays the crypto bot; its dispatcher gains a thin delegation:
  Kite commands (`/kite`, `/k*`) and Kite callbacks (namespace prefix `k`) route to
  `telegram_kite`. Shared low-level `_send/_edit/_answer_cb/_api` are reused (moved to
  a small shared `telegram_tx.py` if cleaner, else imported).
- **Top menu:** `/start` shows two buttons — **📈 Crypto** and **🇮🇳 Kite** — each
  opening its own menu. This is the crypto/Kite separation in the UI.

### Kite menu (read + control)
- **Signals** — live ready signals from `scanner.snapshot('default')`, with a refresh
  button and a per-signal "view" that expands legs.
- **Positions** / **P&L** — via the warm Kite client (`acquire_client`) for the active
  account.
- **Scan now** — triggers `service.scan_user` for `default`.
- **Auto-trade** — toggles `state` engine `auto_execute` ON/OFF (two-tap confirm).
- **Order actions** — from a signal's leg or a position: **Buy / Sell / Square-off**.

### Order flow (two-tap confirm)
1. Tap Buy/Sell on a leg → bot replies with the exact order (symbol, side, qty=lot,
   market) and **[✅ Confirm] [✖ Cancel]**. The confirm callback encodes the order
   params (compact; long symbols looked up from a short-lived in-memory map keyed by a
   token to stay within Telegram's 64-byte callback limit).
2. Confirm → places via a **shared order service** extracted from the existing
   `kite_engine.place_order` endpoint (same `live_safety.assert_safe_to_trade` gate +
   idempotency), so REST and Telegram share one code path. Result/errors surface back
   in the chat and to the engine activity log.
3. Auto-trade toggle uses the same confirm step.

### Alerts (separate channel)
- **`push_kite_alerts()`** scans `scanner.snapshot('default')` for NEW ready signals,
  dedupes per `token|timestamp`, and pushes a formatted card with **[View] [Buy]
  [Sell]** buttons. Gated on a `kite_alerts_enabled` flag + market-open.
- Scheduled as its own background task in `main.py` (mirrors
  `_background_scalping_alerts`), independent of the crypto push so the two streams
  never mix.

### Safety / boundaries
- Single configured chat (existing `TELEGRAM_CHAT_ID` check) is the auth boundary.
- Two-tap confirm on every state-changing action (orders, auto-trade).
- Live-order safety reuses the existing gate; PAPER vs LIVE follows the active
  account's `is_paper`. The confirm card states PAPER/LIVE explicitly.
- Bot acts as uid `default` (the local single user / active Kite account).

**Verification:** unit tests for the Kite text builders, callback routing
(crypto vs kite separation), and the confirm→place path with a mocked client +
safety gate; `pytest` telegram suite green. Manual: drive `/kite` against a paper
account.

---

## Out of scope
- A second Telegram bot/token (one bot, two menus).
- Webhook-mode Telegram (keep long-poll).
- New frontend virtualization dependency (use `content-visibility`).
- Multi-tenant Telegram (single local user `default`).

## Sequencing
A → B → C. Each phase verified and (optionally) committed before the next, so a
regression in one doesn't block the others.
