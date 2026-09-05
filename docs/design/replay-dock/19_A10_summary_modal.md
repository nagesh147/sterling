# A10 — `ReplaySummaryModal`

**File:** `frontend/src/components/kite/replay/ReplaySummaryModal.tsx`
**Replaces:** `SimulationSummary.tsx` (321 lines)
**Fixes:** D3 (**no stylesheet at all — this is currently broken, not merely dated**),
D16 (duplicate CSV exporters), D11

---

## 1. The defect, restated

`SimulationSummary.tsx:22–23` uses `.sim-summary-overlay` and `.sim-summary-card`.
Neither class exists in any stylesheet. The component is mounted at
`KiteLayout.tsx:738` inside the workspace flex column. So when a replay ends with at
least one signal, this renders as an **unstyled block in the page flow** — no scrim, no
centring, no elevation, no scroll containment, no Escape, no focus trap. It pushes the
footer and squeezes the workspace.

Fixing this is Phase 1 of the migration precisely because it is a live visual bug, not a
polish item.

## 2. Structure

Body-portalled at `--rd-z-modal` (12300 — above the fullscreen dock and above toasts).

```tsx
createPortal(
  <div className="rd-scrim" data-open onMouseDown={onScrimClose}>
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="rd-summary-title"
      className="rd-summary"
      ref={cardRef}
    >
      <header>…</header>
      <div className="rd-summary-body">…</div>
      <footer>…</footer>
    </div>
  </div>,
  document.body,
)
```

```css
.rd-scrim {
  position: fixed; inset: 0; z-index: var(--rd-z-modal);
  display: grid; place-items: center; padding: 24px;
  background: color-mix(in srgb, var(--k-text) 40%, transparent);
  backdrop-filter: blur(2px);
  animation: rd-fade var(--rd-dur-fast) var(--rd-ease-out);
}
.rd-summary {
  width: min(920px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  display: flex; flex-direction: column;
  background: var(--k-bg);
  border: 1px solid var(--k-border-strong);
  border-radius: 10px;
  box-shadow: 0 24px 64px color-mix(in srgb, var(--k-text) 24%, transparent);
  animation: rd-modal-in var(--rd-dur-base) var(--rd-ease-out);
}
```

Width grows from the current implicit size to 920 px because the body now holds a real
equity curve and two tables.

## 3. Content

### 3.1 Header

```
Replay complete                                    Thu 4 Sep 2026 · 09:00–15:30 · 50×
                                                                              [×]
```

Plus a one-line verdict under the title, in the P&L tone:
`+₹4,120 across 21 trades · 62% win rate · 3h 12m of session in 41s of real time`.
That last clause uses `elapsed_real_s` (D15).

### 3.2 Stat grid — 8 boxes, 4 columns

`SIGNALS` · `TRADES` · `WIN RATE` · `NET P&L` · `WINS` · `LOSSES` · `AVG TRADE` ·
`BEST / WORST`. The current grid is 6 boxes in 3 columns and its `Win Rate` divides by
`trades_entered` rather than by closed trades, which understates the rate whenever a
position is still open at session end. Divide by `wins + losses`.

### 3.3 Equity curve — upgrade the sparkline

The current `EquityCurveSparkline` is a bare `<polyline>` at a fixed 430×44 viewBox with
`preserveAspectRatio="none"` — so the line is horizontally stretched and the aspect is
wrong at any real width. Rebuild as a `Sparkline` primitive:

- Responsive `viewBox` from a `ResizeObserver`, `preserveAspectRatio="xMidYMid meet"`.
- Zero baseline drawn as a 1 px dashed `--k-border` rule, so profit and loss are visually
  separated.
- Area fill under the curve, `tint(tone, 12)`.
- **Max drawdown shaded** — a translucent `--k-red-brick` band from peak to trough. This
  is the single most informative addition and is pure client-side arithmetic over the
  cumulative series.
- Hover shows a crosshair with `trade #n · +₹x · cum ₹y`.
- Points are cumulative **realised** P&L in trade order; state that in the caption, since
  trade order is not necessarily time order for overlapping positions.

Height 120 px, not 44.

### 3.4 Strategy breakdown

Keep the table, add columns: `Signals`, `Trades`, `Wins`, `Losses`, `Win %`,
`Net P&L`, and a `%` share-of-P&L bar. Sort by `Net P&L` descending. Colour the
strategy name's dot from `REPLAY_STRATEGIES`.

Note a real bug to fix while porting: the current `StrategyTable` builds its map from
`events` first, then from `trades`, so a strategy that traded but whose signal rows were
filtered out gets `count: 0` — and a strategy keyed differently between the two arrays
appears twice. Key on a normalised `strategy.toLowerCase()`.

### 3.5 Trades log

Reuse `ReplayTradesTable` in a compact variant rather than the current bespoke 9-column
table. One table implementation, two densities.

### 3.6 Footer

```
[ Export signals ] [ Export trades ]        [ Close ]  [ Replay again ▸ ]
```

`Replay again` closes, opens the dock, and re-runs the same config — the current version
only opens the dock, which leaves the user to press play themselves.

## 4. Behaviour

| Concern | Requirement |
|---|---|
| Open trigger | `showSummary`, set on stop and on natural completion when `signals_fired > 0` (`useSimulation.ts:497–501`, `:411`). Preserve both. |
| Close | `×`, `Close`, `Escape`, scrim `mousedown` **on the scrim itself** (guard `e.target === e.currentTarget`, as today) |
| Focus | trap; initial focus on `×`; return focus to the transport Play button |
| Scroll | body of the card scrolls; `overscroll-behavior: contain`; background page scroll locked while open |
| Stacking | above fullscreen dock and toasts |
| Reduced motion | scrim and card appear without animation |

## 5. Delete the duplicated exporters

`SimulationSummary.tsx:110–161` duplicates the dock's CSV functions and has **diverged**
(17 columns vs 20). Delete both and import from `replayCsv.ts` (A07 §6).

## 6. Acceptance criteria

- [ ] The modal is a real modal: fixed, centred, scrimmed, elevated, focus-trapped.
- [ ] It renders **above** the dock in fullscreen mode.
- [ ] `grep -rn "sim-summary" frontend/src` returns nothing.
- [ ] Win rate divides by `wins + losses`.
- [ ] Equity curve is responsive, has a zero baseline, and shades max drawdown.
- [ ] Strategy breakdown keys case-insensitively and shows no duplicate rows.
- [ ] Exactly one CSV implementation exists in the repo.
- [ ] `Replay again` restarts the replay, not just the dock.
- [ ] Background page does not scroll while the modal is open.

## 7. Tests

1. renders nothing when `showSummary === false`
2. Escape, `×`, `Close`, and scrim-click all close; a click on the *card* does not
3. focus is trapped and returns to the Play button on close
4. win rate with 3W/1L/2 open → `75%`
5. strategy breakdown merges `SuperTrend` and `supertrend` into one row
6. max-drawdown band spans the correct peak→trough indices for a known series
7. `Replay again` calls `start()`
