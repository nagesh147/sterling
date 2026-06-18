# Mac Kite — Apple-grade motion layer for the Kite app

**Date:** 2026-06-19
**Branch:** KiteEngine
**Status:** Approved — implementing in one pass

## Goal

Add a **Mac Kite** mode to the Kite (Zerodha) app: extreme-fluid, physics-driven,
spatially-aware motion in the spirit of macOS — gated behind a single Settings
toggle. When the toggle is **OFF the app is byte-identical to today's Kite** (the
motion library is never even imported). When **ON**, the four motion surfaces from
the brief plus a polish layer come alive while the app still *looks* like Zerodha
Kite (light theme, orange `#f06428`, same layout, same density).

## Hard contract (non-negotiable)

1. `macKite === false` ⇒ every surface renders the **existing markup verbatim**.
   No new wrappers in the off path, no behavioural change, no perf cost.
2. `framer-motion` is **lazy-loaded** — `import()`ed only when `macKite` turns on.
   The default Kite bundle path does not include it.
3. **Data integrity over motion.** The displayed value / order math always reads the
   raw prop synchronously (0 ms). Animation is decorative and must never gate,
   delay, or alter a number a trader acts on.
4. Respect `prefers-reduced-motion`: when set, springs collapse to instant even with
   Mac Kite on (motion-sensitive users still get the layout, not the bounce).

## Architecture

### The seam
- `store/useKiteSettings.ts` — add `macKite: boolean` (default `false`) + `setMacKite`.
  Persisted (already `persist`-wrapped under `kite-settings`).
- `components/kite/mac/MacMotionProvider.tsx` — wraps the Kite root (mounted in
  `KiteTab`). When `macKite` is on: (a) lazy `import('framer-motion')`, (b) adds
  `mac-kite` class to root, (c) injects the scoped token `<style>`, (d) provides a
  React context with the loaded `motion`/`AnimatePresence`/`LayoutGroup` handles and
  the resolved spring configs (or instant configs under reduced-motion). When off it
  renders `children` untouched and imports nothing.
- `hooks/useMacKite.ts` — `useMacKite()` returns `{ on, motion, AnimatePresence,
  LayoutGroup, springs, reduced }`. While the library is still loading (first frame
  after toggle-on) it returns `on:false` so callers render the static path — no flash,
  no suspense boundary required.

### Motion tokens — `styles/macMotion.ts` (single source of truth)
- CSS custom props (injected scoped under `.mac-kite`):
  - `--mac-ease: cubic-bezier(0.25, 1, 0.5, 1)` (standard crisp settle)
  - `--mac-ease-pop: cubic-bezier(0.16, 1, 0.3, 1)` (fluid pop-up)
  - `--mac-hover: background-color 0.1s linear` (ultra-low-latency tint)
  - `--mac-dur-ticker: 150ms`, `--mac-dur-std: 300ms`, `--mac-dur-pop: 500ms`
- JS springs (objects, read by every Framer consumer — no scattered magic numbers):
  - `springs.standard = { type:'spring', stiffness:400, damping:30, mass:0.8 }`
  - `springs.ticker   = { type:'spring', stiffness:450, damping:35 }`
  - `springs.stage    = { type:'spring', stiffness:350, damping:32, mass:0.9 }`
  - `instant = { duration: 0 }` (reduced-motion substitute)

### Gating pattern used everywhere
```tsx
const { on, motion, AnimatePresence, springs } = useMacKite();
if (!on) return <ExistingMarkup/>;   // verbatim off-path
return <motion.div .../>;            // Mac path
```

## The four motion surfaces (from the brief)

### 1. Price tickers — `mac/MacPriceTicker.tsx` + shared `PriceCell.tsx`
- Masked `overflow-hidden` container, fixed height. `AnimatePresence mode="popLayout"`,
  `initial={false}`. Digit column slides **up for green / down for red**; `ticker`
  spring (450/35). **No abrupt color flash** — the colour rides in with the new value,
  the old value exits in its own colour.
- **My enhancement — per-digit odometer:** only the digits that actually changed roll;
  unchanged leading digits stay put. Cheaper and reads as true Mac odometer polish.
- `PriceCell` is a thin shared component: `macKite ? <MacPriceTicker/> : <span>` so we
  don't touch every LTP call site. Wired first into `MarketWatchPane` LTP + change cells.
- Watchlist rows: hover tint via `--mac-hover` (`background-color 0.1s linear`).

### 2. Order ticket — Mac App Store card morph (`OrderWindow.tsx`, `KiteTab.tsx`)
- The Buy/Sell trigger and the OrderWindow execution panel share a `layoutId`; opening
  morphs the pill into the full card (`--mac-ease-pop`, `springs.standard`).
- Background **Kite canvas dims + `scale(0.98)`** (the spec's "2%") while open, via a
  class/transform on the Kite root; restores on close. `prefers-reduced-transparency`
  ⇒ dim only, no scale.
- Off path = today's popover + centered-modal OrderWindow, unchanged.

### 3. Contextual chart switching — `mac/MacChartSwitch.tsx`
- `AnimatePresence` keyed on symbol. Outgoing chart `scaleX→0.96 + fade`; incoming
  draws in from the **right canvas edge** (`x: 24→0 + fade`), `--mac-ease`.
- Wraps the container *around* `lightweight-charts` (canvas internals untouched).
- Wired into `SetupChart` / `MarketDataPane` chart host.

### 4. Workspace — full free-drag Stage Manager — `mac/MacStageLayout.tsx`
- Selected at the `KiteLayout` level: `macKite ? <MacStageLayout/> : <existing layout>`.
  The existing fixed-sidebar + resizer `KiteLayout` is **left fully intact** as the
  off-path and the fallback.
- The same children (watchlist / content / right / terminal) become **draggable,
  reorderable widgets**. Dragging a panel makes neighbours **part ways and resize**
  with `springs.stage` via Framer layout animation (FLIP). Drop snaps to slots
  (left | center | right | bottom dock); a ghost placeholder shows the target slot.
- Layout arrangement persists to `localStorage` (`kite_stage_layout`). A reset returns
  to the canonical Kite arrangement. Lock (existing footer lock) freezes dragging.
- `will-change: transform` is applied **only during drag**, removed on drop (no
  permanent layer explosion).

## Polish layer (my own additions — "best to the core")

These are gated by the same flag and reduced-motion guard; each is small and high-value:

- **Mode-engage settle:** toggling Mac Kite on plays a one-time, subtle whole-canvas
  spring settle so the mode *feels* like it engaged. Once per activation.
- **Button press physics:** `whileTap={{ scale:0.97 }}` + spring on Mac-mode buttons
  (a shared `MacButton`/style), giving tactile, lightweight-object feedback.
- **Notification spring entrance:** `KiteNotifications` toasts slide+spring in/out
  instead of appearing flatly.
- **Nav-section Magic Move:** crossfade + slight slide between Kite nav sections
  (dashboard/orders/holdings/…) so navigation has spatial continuity.
- **Proximity hover on watchlist:** hovered row lifts subtly (`scale` + shadow); honours
  the brief's "proximity scales and smooth tracking" without a heavy library.
- **GPU hygiene:** `translate3d(0,0,0)` / `contain: layout paint` on hot animated
  layers; `will-change` toggled around interactions only.
- **Mac scrollbars:** reuse the app's existing Mac-scroll autohide styling inside
  `.mac-kite` for consistency (already shipped in this branch).

## Performance guardrails (brief §3)
- Data layer 0 ms — see hard contract #3. Tick value updates are synchronous; the roll
  is the only animated thing and runs on the compositor.
- Hardware acceleration via `translate3d` + scoped `will-change`.
- Watchlist hover `background-color 0.1s linear` (no lag behind eye tracking).
- Animation loops (150–250 ms) never block React render or the WS tick store.

## File inventory
**New:** `styles/macMotion.ts`, `hooks/useMacKite.ts`,
`components/kite/mac/{MacMotionProvider,MacPriceTicker,MacStageLayout,MacChartSwitch,MacKiteToggle,MacButton}.tsx`,
`components/kite/PriceCell.tsx`.
**Edited (additively, off-path preserved):** `store/useKiteSettings.ts`,
`components/kite/{KiteTab,KiteLayout,OrderWindow,MarketWatchPane,KiteNotifications,SetupChart}.tsx`.
**Dependency:** `framer-motion@12` (installed; React 19 peer OK).

## Settings entry point
A Kite-styled **Mac Kite** toggle in the footer control bar (`KiteLayout` footer, beside
lock/reset — it is a view/layout preference, and keeps the Kite navbar pixel-faithful).
Persisted via `useKiteSettings`.

## Build phases
1. Seam + tokens + provider + footer toggle — prove off = identical, on adds `mac-kite`.
2. Tickers + watchlist hover.
3. Order-ticket morph + canvas dim.
4. Chart Magic Move.
5. Stage Manager free-drag (structural; last).
6. Polish layer.

## Verification
- `tsc --noEmit` clean (baseline already clean).
- gstack visual QA via `vite preview`: screenshot Mac Kite **OFF** (must match current
  Kite exactly) and **ON** for each surface. Confirm off = existing behaviour.
- Manual `prefers-reduced-motion` check.

## Risks
- **Stage Manager** is the only structural rebuild and the main Kite-parity risk — it is
  fully isolated behind `MacStageLayout`; the off-path `KiteLayout` is never modified in
  its layout logic, only the footer gains a toggle.
- Lazy-load race: `useMacKite` returns `on:false` until the chunk resolves, so the static
  path renders for ~1 frame on first activation — acceptable, no flash.
