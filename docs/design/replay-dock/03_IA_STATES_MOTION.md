# 03 — Information Architecture, States, Transitions, Keyboard

---

## 1. The problem with the current IA

Today the dock stacks: shell bar → toolbar (tabs + transport + presets + filters, all in
one 32 px row that horizontally scrolls) → conditional progress row → tab panel. The
toolbar carries four unrelated jobs, so at any realistic width it scrolls and the
transport — the control you need most — slides out of view.

Configuration is also a *tab*, which means the surface you use once per session has
equal billing with the surface you watch for an hour.

---

## 2. New layout

```
┌─ SHELL BAR ─────────────────────────────────────────────── 32px ──┐
│ ⠿  Replay   [REPLAY ▸ RUNNING]   10:47:05 IST · 50×   68%        │
│                                        [restore][min][□][⤢][⛶]   │
├─ COMMAND RAIL ──────────────────────────────────────────── 44px ──┤
│ ⏮ ◀◀ ⏵ ▶▶ ⏭ ⏹ │ 1× 5× 10× 50× 100× MAX │ ═══════▓░░░░░░░░░░░░░ │
│                                          └── TIMELINE (flex) ──┘  │
├─ METRIC STRIP ──────────────────────────────────────────── 30px ──┤
│ P&L +₹4,120  ·  WIN 62%  ·  TRADES 21  ·  SIGNALS 47  ·  DRAG —  │
├─ VIEW BAR ──────────────────────────────────────────────── 30px ──┤
│ [ Split │ Signals 47 │ Trades 21 ]        2026-09-04 ▾  Filters ▾ │
├─ CONTENT ────────────────────────────────────────────── flex:1 ───┤
│                                                                   │
│   signals table        │        trades table                      │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

Four changes of substance:

1. **The transport is pinned left in its own rail** and never scrolls away. The timeline
   takes all remaining width in the same row, so play/pause and the scrubber are on one
   horizontal axis — the arrangement of every media player a trader has ever used.
2. **The metric strip is always visible**, not only inside two of four tabs. P&L is why
   the dock exists.
3. **Configuration leaves the tab set.** It becomes a right-side sheet (or, in `half`
   mode, a full-panel overlay) opened by a `Configure` button that is **only enabled
   while `state === 'idle'`** — which is already the truth, since every config control
   is `disabled={simActive}` today. Making the entry point disabled instead of every
   control inside it is one disabled state instead of nineteen.
4. **Session date and filters move to the view bar, right-aligned**, as two dropdown
   buttons rather than a scrolling pill farm.

### 2.1 Responsive behaviour

The dock's width equals its host pane's, which the user can resize freely.

| Width | Adaptation |
|---|---|
| ≥ 1100 px | as drawn |
| 900–1100 px | speed pills collapse to a `50× ▾` select; date button shows `Sep 4` not `2026-09-04` |
| 700–900 px | metric strip drops `SIGNALS` and `DRAG`, keeping P&L / WIN / TRADES; `Split` tab hidden (it is unreadable below ~700 px) and forced to `Signals` |
| < 700 px | command rail wraps to two lines (transport, then timeline); view bar becomes icon-only |

Implement with a `ResizeObserver` on the dock root writing `data-width="xl|lg|md|sm"`,
**not** with media queries. The dock is a pane inside a resizable workspace; viewport
width tells you nothing about it. (This is also why the app's viewport-scale layer must
not be relied on here — see `reference_viewport_scale_traps`.)

---

## 3. Dock modes

Five modes collapse to **four**, because `full` and `maximized` differ only by whether
they reach the top of the viewport, and `fullheight` is the same idea inside the pane.

| Mode | Geometry | When |
|---|---|---|
| `docked` | in-pane, bottom of the dashboard column, user-resizable height (220 px – 80 % of pane) | default |
| `expanded` | in-pane, fills the dashboard column; host hides its own content | the old `fullheight` |
| `overlay` | `position: fixed`, spans the workspace above the footer, resizable height | the old `full` + `maximized` |
| `fullscreen` | body portal, `inset: 0` | unchanged |

`docked` ↔ `expanded` is a **pane-local** change. `overlay` and `fullscreen` are
**app-level**. The shell bar groups its controls accordingly (see `11_A02`).

Persist `mode` and `dockHeight` together under one key (fixes D20):

```ts
const REPLAY_UI_KEY = 'sterling:replay-dock:ui';
type ReplayUiPrefs = {
  v: 1;
  mode: 'docked' | 'expanded' | 'overlay';   // fullscreen intentionally NOT persisted
  height: number;
  tab: 'split' | 'signals' | 'trades';
  open: boolean;
};
```

`fullscreen` is excluded deliberately: reopening the app into a fullscreen takeover the
user does not remember choosing is hostile. Reading a stored `fullscreen` maps to
`overlay`.

---

## 4. State machine

### 4.1 Session state (owned by the backend)

```
        ┌──────────────── stop ─────────────────┐
        │                                        │
     ┌──▼──┐   start   ┌─────────┐   ready   ┌───┴─────┐  pause  ┌────────┐
     │idle │ ────────► │ loading │ ────────► │ running │ ──────► │ paused │
     └──▲──┘           └────┬────┘           └────┬────┘ ◄────── └───┬────┘
        │                   │ fail                │ end of data resume    │
        │                   ▼                     │                       │
        │              ┌────────┐                 │                       │
        └───────────── │ error  │ ◄───────────────┴───────────────────────┘
           dismiss     └────────┘        stream lost
```

`error` is **new**. Today a failed start is swallowed into `console.error` (D18). The
store gains `error: { code, message, at } | null`, and `error` is a first-class render
state everywhere `state` is consumed.

### 4.2 What each state renders

| State | Shell pill | Transport | Timeline | Content | Chrome accent |
|---|---|---|---|---|---|
| `idle` | `IDLE`, `--k-dim` | Play enabled; all others disabled | flat track, no playhead, dimmed | last session's results if any, else empty state with a `Configure` CTA | none |
| `loading` | `LOADING`, `--k-dim`, spinner | all disabled | skeleton shimmer (M22) | table skeletons, 5 rows | none |
| `running` | `RUNNING`, `--k-green`, pulsing dot (M20) | Pause + all seek enabled | live fill + playhead + heatmap | streaming rows | 2 px `--k-cyan` top rule |
| `paused` | `PAUSED`, `--k-amber` | Resume + all seek enabled | static fill, playhead visible, **scrub enabled** | frozen rows | 2 px `--k-cyan` top rule, 60 % opacity |
| `error` | `ERROR`, `--k-red` | Play (retry) enabled, rest disabled | flat, dimmed | error panel: message, `Retry`, `Open configuration` | 2 px `--k-red` top rule |

### 4.3 Content states per pane

Every table pane must handle all five. Today only "empty" exists, and its copy is wrong
for the idle case ("Replay stepping through bars…" while nothing is running).

| Case | Signals pane | Trades pane |
|---|---|---|
| Idle, never run | "No replay loaded. Pick a session and press play." + `Configure` | same |
| Loading | 5 skeleton rows | 5 skeleton rows |
| Running, none yet | "Watching for signals… 47 bars replayed." (uses `bars_played`, fixing D15) | "No entries yet. Strong signals open positions automatically." |
| Populated | rows | rows |
| Error | inline error strip above whatever rows exist | same |

---

## 5. Transitions between panes

- Tab change is `opacity`+`translateY` only (M5), 140 ms, and the **outgoing panel is
  unmounted, not `display:none`d**. Keeping four panels mounted is why the dock
  currently re-renders two tables on every 150 ms status frame.
- The segmented control gets a sliding indicator (M6): one absolutely-positioned pill
  behind the labels, translated to the active segment. It must be driven by measured
  offsets, not by `nth-child` guesses, because label widths change with counts.
- Scroll position per tab is preserved in a ref map keyed by tab id, and restored on
  re-entry. A trader who scrolls up 200 rows and flips tabs should not lose their place.

---

## 6. Keyboard

### 6.1 Scoping — fixes D12

The current handler is on `window` and fires whenever the dock is *open*. Replace with:

- The dock root is `tabIndex={-1}` with `data-replay-root`.
- Shortcuts fire only when `document.activeElement` is inside the dock root **or** the
  dock is in `overlay` / `fullscreen` mode (where it owns the screen).
- The guard extends to `[contenteditable]`, `[role="textbox"]`, and any element with
  `data-swallow-keys`.
- A single global exception: **`Ctrl/⌘ + Shift + R`** toggles the dock open from
  anywhere. Nothing else is global.

### 6.2 Map

| Key | Action | Enabled when |
|---|---|---|
| `Space` | play / pause / resume | always |
| `K` | same as Space (media convention) | always |
| `←` / `→` | step 1 bar back / forward | `state ≠ idle` |
| `Shift + ←/→` | step 5 bars | `state ≠ idle` |
| `Alt + ←/→` | step 30 bars | `state ≠ idle` |
| `Home` / `End` | jump to session start / end | `state ≠ idle` |
| `,` / `.` | frame-step back / forward while paused | `state === 'paused'` |
| `+` / `-` | speed up / down **through the same ladder the UI shows** (fixes D13) | always |
| `1`…`6` | speed presets 1×, 5×, 10×, 50×, 100×, MAX | always |
| `S` | focus Signals tab | always |
| `T` | focus Trades tab | always |
| `D` | focus Split tab | always |
| `C` | open configuration | `state === 'idle'` |
| `E` | export current tab to CSV | rows > 0 |
| `F` | cycle docked → expanded → overlay | always |
| `Escape` | fullscreen→overlay→docked; if already docked, close dock | always |
| `?` | open the shortcut sheet | always |

**The speed ladder is one constant**, exported once and consumed by both the keyboard
handler and the pill row:

```ts
export const REPLAY_SPEEDS = [1, 5, 10, 50, 100, 5000] as const;
export const REPLAY_SPEED_LABEL = (s: number) => (s >= 5000 ? 'MAX' : `${s}×`);
```

If more granularity is wanted, add it to this array — never to the keyboard handler alone.

### 6.3 Discoverability

`?` opens a shortcut sheet (a `ReplaySummaryModal` sibling using the same overlay
primitive). Every button's `title` ends with its shortcut in parentheses, e.g.
`Pause replay (Space)`. That convention already exists in the current file; keep it and
make it complete.

### 6.4 Focus management

| Event | Focus goes to |
|---|---|
| Dock opens | dock root (so shortcuts work immediately), **not** into a control |
| Config sheet opens | its first field; focus trapped; `Escape` closes and returns focus to the `Configure` button |
| Summary modal opens | the modal's close button; focus trapped; returns to the transport Play button |
| Dropdown opens | first item; arrows navigate; `Escape` closes and returns to the trigger |
| Dock closes | the footer replay chip |

---

## 7. Announcements

One polite live region, mounted once in `ReplayDock`:

```tsx
<div aria-live="polite" aria-atomic="true" className="rd-sr-only" data-testid="replay-live">
  {announcement}
</div>
```

`announcement` is written by a **throttled** reducer — at most one message per 2 s,
coalescing: `"3 new signals. Latest: NIFTY long at 10:47."`. Also announce state
transitions once each (`"Replay running at 50 times speed."`, `"Replay complete. 47
signals, 21 trades, profit 4,120 rupees."`).

Never announce per-bar progress.
