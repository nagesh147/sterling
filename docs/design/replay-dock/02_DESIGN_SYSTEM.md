# 02 — Design System for the Replay Dock

This is the shared vocabulary. Every artifact doc assumes it. Nothing here invents a
new palette: it selects from `frontend/src/styles/theme.ts`, which already holds a
light and dark value for every token, and pins the subset the dock is allowed to use.

---

## 1. Design principle

> **The dock is a transport deck, not a settings panel.**

Three consequences that decide every ambiguous call later:

1. **Time is the primary object.** The timeline is the largest, highest-contrast,
   most-interactive element. Everything else is a readout of where the cursor is.
2. **Configuration is a destination, not a frame.** You go to it before you press play.
   It does not occupy chrome while the replay runs.
3. **Results are payload.** Tables get the remaining space, uninterrupted, and are the
   only thing that scrolls.

---

## 2. Colour

### 2.1 The allowed token set

Use these and nothing else. `k.*` from `frontend/src/styles/kiteUI.tsx` resolves to the
same variables and is the preferred form in TSX; raw `var(--k-*)` is preferred in CSS.

**Surfaces**

| Role | Token | Used for |
|---|---|---|
| Dock ground | `--k-bg` | the dock body, table rows, panel background |
| Chrome | `--k-surface` | shell bar, toolbar, table headers, metric strip |
| Row hover | `--k-surface-hover` | table row hover, segment active |
| Sunken | `--k-surface-sunken` | timeline track, empty-state wells |
| Hairline | `--k-border` | table row rules, internal dividers |
| Structural | `--k-border-strong-4` | the dock's own top edge against the workspace |
| Emphasis edge | `--k-border-strong` | dropdown / modal outer border |

**Ink**

| Role | Token |
|---|---|
| Primary value | `--k-text` |
| Secondary / label | `--k-dim` |
| Tertiary / hint | `--k-faint` |
| Disabled | `--k-faint-2` |

**Semantics — fixed, never re-mapped**

| Meaning | Token | Notes |
|---|---|---|
| Bullish / long / win / profit | `--k-green` | |
| Bearish / short / loss | `--k-red-brick` | the muted brick, not `--k-red`; `--k-red` is reserved for *errors* |
| Error / fault | `--k-red` | connection lost, start failed |
| Target / take-profit | `--k-amber` | |
| Replay identity | `--k-cyan` | the "this is simulated time, not live" colour. Used by the footer chip today (`KiteFooterStatus.tsx`) — adopt it as the dock's identity accent. |
| Selected / active control | `--k-brand` | matches `kw-pane-control[aria-pressed]` |
| Foreground on any filled accent | `--k-on-accent` | **mandatory**; it inverts between themes. `#ffffff` on an accent fill fails contrast in dark mode. |

### 2.2 Tinting

Never hand-write `rgba()`. Use the existing helper:

```ts
import { tint } from '../../styles/kiteUI';
tint(k.green, 10)   // → color-mix(in srgb, var(--k-green) 10%, transparent)
```

Fixed tint ladder — use only these five steps:

| Step | Use |
|---|---|
| 8 % | resting fill of a subtle chip |
| 12 % | hover fill |
| 18 % | active / selected fill (unfilled variant) |
| 28 % | border of a tinted chip |
| 45 % | border of a selected control |

### 2.3 Replay identity

The single most important colour decision: **a replaying dock must never be mistakable
for live trading.** Encode it three ways, redundantly:

1. A 2 px `--k-cyan` top rule on the dock whenever `state !== 'idle'`.
2. The `REPLAY` state pill in the shell bar, cyan-tinted.
3. The footer badge (already cyan). Keep it.

Do **not** encode it by tinting the whole dock — the tables must stay legible and their
green/red must stay unambiguous.

---

## 3. Typography

### 3.1 The ramp

Eleven ad-hoc sizes (D9) collapse to **five**. Every text node in the dock picks one.

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `--rd-fs-micro` | 9 px / 12 | 700 | state pills, status chips, badges. Uppercase, `letter-spacing: .06em`. |
| `--rd-fs-label` | 10 px / 14 | 600 | column headers, field labels, metric labels. Uppercase, `letter-spacing: .05em`. |
| `--rd-fs-body` | 11 px / 16 | 500 | control text, button labels, secondary prose |
| `--rd-fs-data` | 12 px / 16 | 500 | **table cells and all numerics** |
| `--rd-fs-value` | 15 px / 20 | 700 | metric-strip values, summary stat boxes |

Nothing else. No 8.5, no 9.5, no 10.5, no 11.5.

### 3.2 Families

```css
--rd-font-ui:   "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--rd-font-mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
```

`--rd-font-ui` is `k.fontFamily`, unchanged. Mono is for, and only for:
times, prices, quantities, percentages, P&L, trade IDs, progress readouts.

**Every numeric cell must carry `font-variant-numeric: tabular-nums`.** Columns of
prices that jitter horizontally as digits change are the single most common density
failure in this codebase.

### 3.3 Number formatting

Centralise in `replayFormat.ts`; do not `.toFixed()` inline.

| Kind | Rule | Example |
|---|---|---|
| Price | `₹` + 2 dp, grouped | `₹1,248.50` |
| P&L | signed, `₹`, 2 dp, grouped | `+₹1,248.50` / `−₹312.00` (U+2212 minus, not hyphen) |
| Percent | signed, 1 dp | `+2.4%` |
| Quantity | grouped integer | `1,250` |
| Lots | integer + `L` | `5L` |
| Time | `HH:MM:SS`, IST, mono | `10:47:05` |
| Duration | compact | `1h 12m` / `47m` / `< 1m` |
| Absent value | `—` (em dash), `--k-faint` | never `0.00` |

The last row is the rule that D1 violates. A metric the backend does not send renders
as `—`, and the metric's tooltip says why.

---

## 4. Space and density

### 4.1 Grid

4 px base. Allowed gaps: **4, 6, 8, 12, 16, 24**.

### 4.2 Fixed heights

| Element | Height |
|---|---|
| Shell bar | 32 px |
| Command rail (transport + timeline row) | 44 px |
| Metric strip | 30 px |
| Filter / segment bar | 30 px |
| Table header row | 28 px |
| Table body row | 28 px |
| Control (button, pill, input) | 24 px |
| Small control (chip, export) | 20 px |
| Resizer grip | 6 px hit area, 2 px visual |

Total persistent chrome: 32 + 44 + 30 = **106 px**. The current dock's minimum height
is 160 px (`SimulationBar.tsx:224`), which leaves 54 px for content. Raise the minimum
to **220 px** so at least three table rows are always visible; a dock that can be
dragged to show zero rows is a dock that will be.

### 4.3 Padding

Horizontal padding is `12px` for all chrome rows and `8px` for table cells. One value
each. The current file uses 10, 12, 14, 16 interchangeably.

---

## 5. Iconography

**Remove every emoji from dock chrome** (D10). Replace with 14×14 inline SVG,
`stroke="currentColor"`, `stroke-width="1.75"`, `fill="none"`, `stroke-linecap="round"`.

Create `frontend/src/components/kite/replay/ReplayIcons.tsx` exporting:

| Name | Replaces | Glyph |
|---|---|---|
| `Play` | `⏵` | right triangle |
| `Pause` | `⏸` | two bars |
| `Stop` | `⏹` | square |
| `SkipStart` | `⏮` | bar + left triangle |
| `SkipEnd` | `⏭` | right triangle + bar |
| `StepBack` | `◀◀` | double left chevron |
| `StepFwd` | `▶▶` | double right chevron |
| `Signal` | `⚡` | lightning polyline |
| `Trades` | `💼` | briefcase |
| `Split` | `🔀` | two-column rect |
| `Config` | `⚙` | gear |
| `Export` | `📥` | tray + down arrow |
| `Calendar` | `📅` | calendar |
| `Target` | `🎯` | concentric circles |

Emoji **may remain** in one place only: user-facing prose inside the config pane's
descriptions, where it is decorative and not load-bearing. Even there, prefer none.

Strategy identity in filter lists becomes a 6 px colour dot plus the name, not an emoji
— that also gives strategies a consistent colour across the signals table, the timeline
heatmap, and the summary breakdown, which they currently lack.

---

## 6. Motion

### 6.1 Tokens

Put these on `.replay-dock` in `replay.css`:

```css
.replay-dock {
  --rd-dur-instant: 90ms;
  --rd-dur-fast:   140ms;
  --rd-dur-base:   200ms;
  --rd-dur-slow:   280ms;

  --rd-ease-out:  cubic-bezier(.2, .8, .2, 1);    /* entry, expand — matches kw-pane-in */
  --rd-ease-in:   cubic-bezier(.4, 0, 1, 1);      /* exit, collapse */
  --rd-ease-move: cubic-bezier(.4, 0, .2, 1);     /* position/size changes */
}
```

`--rd-ease-out` is deliberately the same curve `KiteLayout.tsx` already uses for
`kw-pane-in`, so the dock enters like every other pane.

### 6.2 The motion table

Every animation in the dock, exhaustively. If it is not in this table, do not animate it.

| # | What | Property | Duration | Easing | Trigger |
|---|---|---|---|---|---|
| M1 | Dock opens | `transform: translateY(8px)→0`, `opacity .6→1` | `--rd-dur-base` | out | `barOpen` false→true |
| M2 | Dock closes | same, reversed | `--rd-dur-fast` | in | `barOpen` true→false |
| M3 | Mode change (half↔full↔maximized) | `height`, `inset` | `--rd-dur-base` | move | `viewMode` change |
| M4 | Fullscreen enter | `opacity 0→1`, `scale .985→1` | `--rd-dur-base` | out | portal mount |
| M5 | Tab panel swap | `opacity 0→1`, `translateY(4px)→0` | `--rd-dur-fast` | out | active tab change |
| M6 | Segment indicator slides | `transform: translateX` on a single pill | `--rd-dur-fast` | move | tab change |
| M7 | Progress fill | `width` | `--rd-dur-instant` **linear** | — | every status frame |
| M8 | Playhead marker | `transform: translateX` | `--rd-dur-instant` **linear** | every status frame |
| M9 | New signal row enters | `opacity 0→1`, `translateY(-4px)→0`, plus a 600 ms cyan `background` flash decaying to transparent | `--rd-dur-base` / 600 ms | out | row keyed new |
| M10 | Heatmap dot appears | `scale 0→1` | `--rd-dur-fast` | out (slight overshoot) | new event |
| M11 | Toast in | `opacity 0→1`, `translateY(10px)→0` | `--rd-dur-base` | out | new `last_signal` |
| M12 | Toast out | `opacity 1→0`, `translateY(0→-6px)` | `--rd-dur-fast` | in | 4 s timer or dismiss |
| M13 | Summary scrim | `opacity 0→1` | `--rd-dur-fast` | out | `showSummary` |
| M14 | Summary card | `opacity 0→1`, `scale .97→1`, `translateY(8px)→0` | `--rd-dur-base` | out | `showSummary` |
| M15 | Config accordion | `grid-template-rows: 0fr→1fr` | `--rd-dur-base` | move | `<details>` toggle |
| M16 | Caret rotate | `transform: rotate(0→90deg)` | `--rd-dur-fast` | move | same |
| M17 | Control press | `transform: scale(.94)` | `--rd-dur-instant` | out | `:active` |
| M18 | Value change flash | `color` pulse on the changed metric | 400 ms | out | metric value delta |
| M19 | State pill change | `background`/`color` cross-fade | `--rd-dur-fast` | move | `state` change |
| M20 | Live pulse dot | `opacity 1↔.35` | 1.6 s | `ease-in-out` infinite | `state === 'running'` |
| M21 | Resizer engage | `background` + `height 2px→4px` | `--rd-dur-instant` | out | hover / drag |
| M22 | Skeleton shimmer | `background-position` sweep | 1.2 s linear infinite | — | `state === 'loading'` |

### 6.3 Rules

- **Never animate `height`/`width` on a scrolling container while data streams in.** M3
  is the one exception and it only runs on an explicit user mode change, never during a
  status frame.
- **Never animate `top`/`left`.** Use `transform`.
- Anything running while the replay plays (M7, M8, M9, M10, M20) must be
  `transform`/`opacity` only, so it stays on the compositor.
- Only two properties may be in a `transition` shorthand per rule. `transition: all` is
  banned.

### 6.4 Reduced motion — mandatory

```css
@media (prefers-reduced-motion: reduce) {
  .replay-dock,
  .replay-dock *,
  .replay-overlay,
  .replay-overlay * {
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
    scroll-behavior: auto !important;
  }
  .replay-dock [data-pulse] { opacity: 1 !important; }
}
```

M7 and M8 keep working (they are functional position updates, not decoration) but land
instantly. M9's flash becomes a static 600 ms background that then clears — no fade.

### 6.5 Motion budget

At most **three** elements animate simultaneously during steady-state playback: the
progress fill, the playhead, and at most one entering row. Everything else is static
until the user acts.

---

## 7. Elevation and stacking

One ladder. Every `z-index` in the dock comes from here — no ad-hoc numbers.

```css
--rd-z-dock:        140;   /* docked modes, below the 150 footer */
--rd-z-maximized:   145;
--rd-z-dropdown:    12100; /* body-portalled */
--rd-z-fullscreen:  12000;
--rd-z-toast:       12200; /* MUST exceed fullscreen — fixes D4 */
--rd-z-modal:       12300; /* summary; exceeds toast */
```

| Level | Shadow |
|---|---|
| Flat (dock in half mode) | none; a `1px --k-border-strong-4` top edge only |
| Raised (full / maximized) | `0 -8px 24px color-mix(in srgb, var(--k-text) 10%, transparent)` |
| Floating (dropdown, toast) | `0 10px 26px color-mix(in srgb, var(--k-text) 18%, transparent)` |
| Modal | `0 24px 64px color-mix(in srgb, var(--k-text) 24%, transparent)` |

Shadows are tinted with `--k-text`, not `rgba(0,0,0,…)` — a black shadow on a
`#0f1115` dark ground is invisible, which is why the current dock loses its elevation
entirely in dark mode (D8).

---

## 8. Focus and accessibility baseline

- **Visible focus, always:**
  `outline: 2px solid var(--k-brand); outline-offset: 1px;` on `:focus-visible`. Never
  `outline: none` without a replacement.
- **Hit target ≥ 24×24 px** even where the visual is smaller — pad, don't grow.
- **Contrast:** every text/background pair ≥ 4.5:1 in both themes. The theme tokens are
  documented as clearing AA on dark; the pairings you invent are your responsibility.
- **Accessible names:** every icon-only control needs `aria-label`. `title` is a
  supplement, never the name.
- **Live regions:** exactly one `aria-live="polite"` region in the dock, announcing new
  signals. It must be throttled (see `20_A11_toasts.md`) — an unthrottled live region at
  replay speed 5000× makes a screen reader unusable.
- **Colour is never the only channel.** Direction is green/red *and* the words
  `LONG`/`SHORT`. Win/loss is a tinted chip *and* the words `WIN`/`LOSS`.

---

## 9. Naming conventions

| Thing | Convention | Example |
|---|---|---|
| CSS class | `rd-` prefix, kebab | `.rd-transport-btn` |
| CSS custom property | `--rd-` prefix | `--rd-dur-fast` |
| State on an element | `data-*` attribute | `data-state="running"` |
| Component file | PascalCase under `replay/` | `ReplayTimeline.tsx` |
| Test id | `data-testid="replay-…"` | `replay-timeline` |

The old `sim-` prefix is retired wholesale in Phase 4 (see `30_MIGRATION_PLAN.md`).
Do not mix prefixes inside one component.

---

## 10. File layout the redesign creates

```
frontend/src/components/kite/replay/
├─ ReplayDock.tsx               A01  shell, modes, mount contract
├─ ReplayShellBar.tsx           A02  identity, state, window controls
├─ ReplayTransport.tsx          A03  transport + speed
├─ ReplayTimeline.tsx           A04  scrubber + heatmap
├─ ReplaySessionPicker.tsx      A05  dates
├─ ReplayFilters.tsx            A05  strategies + legs
├─ ReplayMetricsStrip.tsx       A06
├─ ReplaySignalsTable.tsx       A07
├─ ReplayTradesTable.tsx        A08
├─ ReplayConfigPanel.tsx        A09
├─ ReplaySummaryModal.tsx       A10
├─ ReplayToastHost.tsx          A11
├─ ReplayFooterChip.tsx         A12
├─ ReplayIcons.tsx              shared SVG set
├─ replayFormat.ts              number/time formatting
├─ replayCsv.ts                 the ONE CSV exporter (fixes D16)
├─ replay.css                   tokens + all dock styling
└─ primitives/
   ├─ Segmented.tsx
   ├─ Pill.tsx
   ├─ StatChip.tsx
   ├─ EmptyState.tsx
   ├─ Skeleton.tsx
   └─ Sparkline.tsx

frontend/src/hooks/
├─ useReplayStore.ts            A13  store only
├─ useReplayTransport.ts        A13  commands
└─ useReplayStream.ts           A13  SSE + fallback poller
```
