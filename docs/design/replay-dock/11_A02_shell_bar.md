# A02 — `ReplayShellBar`

**File:** `frontend/src/components/kite/replay/ReplayShellBar.tsx`
**Replaces:** `SimulationBar.tsx:539–657`
**Fixes:** D8 (hex drag dots), D10 (emoji), D11 (control labels), D15 (unused status),
D17 (five near-identical modes)

---

## 1. Layout (32 px, `--k-surface`, 1 px bottom `--k-border-2`)

```
⠿  Replay  ·  [REPLAY ▸ RUNNING ●]     10:47:05 IST · 50×     ▓▓▓▓░░ 68%   1 284 / 1 890 bars
                                                          [⤢ restore][— min][□ expand][▣ overlay][⛶ full]
```

| Slot | Content | Type token |
|---|---|---|
| grip | 6-dot drag handle, `currentColor` inherited from `--k-faint` | — |
| title | `Replay` | `--rd-fs-body`, 700 |
| state | `<ReplayStatePill/>` | `--rd-fs-micro` |
| clock | `HH:MM:SS IST · {speed}×` | `--rd-fs-body`, mono, tabular |
| progress | a 40 px mini-track + `68%` | `--rd-fs-body`, mono |
| bars | `1,284 / 1,890 bars` — **new**, surfaces `bars_played`/`bars_total` (D15) | `--rd-fs-micro`, `--k-dim` |
| controls | window controls, `margin-left:auto` | 24×24 each |

At `data-width="md"` drop the bar counter; at `"sm"` drop the clock's `IST ·` prefix and
the progress percentage (the mini-track remains).

## 2. The drag grip (fixes D8)

```tsx
function DragGrip() {
  return (
    <span aria-hidden="true" className="rd-grip">
      {Array.from({ length: 6 }, (_, i) => <span key={i} />)}
    </span>
  );
}
```

```css
.rd-grip { width: 10px; display: grid; grid-template-columns: repeat(2, 3px); gap: 2px; color: var(--k-faint); flex-shrink: 0; }
.rd-grip > span { width: 2.5px; height: 2.5px; border-radius: 50%; background: currentColor; }
```

The colour moves out of the inline style and onto a token. That is the entire fix; the
current `#c2c2c2` is invisible on `--k-bg: #0f1115`.

## 3. State pill

```tsx
<span className="rd-state-pill" data-state={state} role="status">
  {state === 'running' && <span className="rd-pulse" data-pulse />}
  {LABEL[state]}
</span>
```

| state | label | colour | extra |
|---|---|---|---|
| `idle` | `IDLE` | `--k-dim` | — |
| `loading` | `LOADING` | `--k-dim` | 12 px spinner |
| `running` | `RUNNING` | `--k-green` | pulsing dot (M20) |
| `paused` | `PAUSED` | `--k-amber` | — |
| `error` | `ERROR` | `--k-red` | click opens the error detail |

Prefixed by a static `REPLAY ▸` in `--k-cyan` whenever `state !== 'idle'`, so the pill
reads `REPLAY ▸ RUNNING`. That is the "this is not live" signal from
`02_DESIGN_SYSTEM.md §2.3`.

`role="status"` (implicit `aria-live="polite"`) is correct here **only because state
changes are rare**. Do not add `role="status"` to the clock.

## 4. `status_message` — surface it (D15)

When `status.status_message` is non-empty, render it as an inline note after the state
pill, truncated with `text-overflow: ellipsis` and the full text in `title`. This is the
backend's only channel for "no candles stored for this date", which currently reaches
the user as an inexplicably empty session.

## 5. Window controls

Reduce from five to four, grouped by scope with a hairline divider:

| Control | Icon | `aria-label` | `aria-pressed` | Action |
|---|---|---|---|---|
| Minimise | `—` | `Minimise replay dock` | — | `setOpen(false)` |
| Expand | `▣` | `Expand replay to fill pane` | `mode === 'expanded'` | toggle docked ↔ expanded |
| Overlay | `▭` | `Float replay over workspace` | `mode === 'overlay'` | toggle docked ↔ overlay |
| Fullscreen | `⛶` | `Replay full screen` | `mode === 'fullscreen'` | toggle |

Every one keeps `className="kw-pane-control"` so it inherits the workspace's hover,
active-scale and `aria-pressed` styling (`KiteLayout.tsx` `WORKSPACE_CSS`). Each gets a
real SVG from `ReplayIcons.tsx`; none gets an emoji.

Double-click on the bar toggles docked ↔ expanded. Keep this; it is discoverable and
already implemented. Add `onDoubleClick` guard so it does not fire when the target is a
control.

## 6. Motion

- M19: the state pill cross-fades `background`/`color` over `--rd-dur-fast` on change.
- M20: the pulse dot, `opacity 1↔.35` over 1.6 s, `data-pulse` so reduced-motion pins it.
- M17: `:active { transform: scale(.94) }` on the controls — inherited from
  `.kw-pane-control:active`, so nothing to write.
- The progress percentage uses `M7`'s linear timing so it does not lag the fill.

## 7. Acceptance criteria

- [ ] No emoji in the shell bar.
- [ ] No hex literal in the file.
- [ ] Every control has an `aria-label`; `aria-pressed` reflects the current mode.
- [ ] `bars_played` / `bars_total` render and are tabular-aligned.
- [ ] A non-empty `status_message` is visible and its full text is in `title`.
- [ ] In dark mode the grip is visible.
- [ ] `role="status"` announces each state change exactly once (not per frame).

## 8. Tests

1. state pill renders the right label and `data-state` for all five states
2. `REPLAY ▸` prefix present iff `state !== 'idle'`
3. window controls set `aria-pressed` correctly per mode
4. `status_message` renders when present, absent when `''`
5. double-click toggles docked ↔ expanded, but not when the click target is a button
6. bar counter formats with grouping (`1,284 / 1,890`)
