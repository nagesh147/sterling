# A03 — `ReplayTransport`

**File:** `frontend/src/components/kite/replay/ReplayTransport.tsx`
**Replaces:** `SimulationBar.tsx:704–745`
**Fixes:** D10 (emoji glyphs), D11 (labels), D13 (speed ladder mismatch)

---

## 1. Layout

Left third of the 44 px command rail:

```
[⏮] [◀◀] [ ⏵ ] [▶▶] [⏭] [⏹] │ 1× 5× 10× 50× 100× MAX
```

- Seek buttons: 28×28, `--k-text`, transparent, hover `tint(--k-text, 8)`.
- **Play/pause is the primary control**: 32×32, filled `--k-green` (play) /
  `--k-amber` (pause) with `--k-on-accent` glyph, `border-radius: 6px`. It is the only
  filled control in the rail; that is what makes it findable at a glance.
- Stop: 28×28, `--k-red-brick` glyph, transparent ground. Destructive, so it sits at the
  end past a 1 px hairline.
- All glyphs are SVG from `ReplayIcons.tsx`. No `⏮ ◀◀ ⏵` characters.

## 2. Button matrix

| Button | Icon | `aria-label` | Enabled when | Action |
|---|---|---|---|---|
| Jump start | `SkipStart` | `Jump to session start (Home)` | `state ≠ idle` | `transport.jumpStart()` |
| Step back | `StepBack` | `Step back 5 bars (Shift+Left)` | `state ≠ idle` | `transport.stepBars(-5)` |
| Play / Pause / Resume | `Play`/`Pause` | see below | always | see below |
| Step forward | `StepFwd` | `Step forward 5 bars (Shift+Right)` | `state ≠ idle` | `transport.stepBars(5)` |
| Jump end | `SkipEnd` | `Jump to session end (End)` | `state ≠ idle` | `transport.jumpEnd()` |
| Stop | `Stop` | `Stop replay` | `state ≠ idle` | `transport.stop()` |

Primary button by state:

| state | icon | label | action |
|---|---|---|---|
| `idle` | Play | `Start replay (Space)` | `setTab('split'); transport.start()` |
| `loading` | spinner | `Starting replay` | disabled |
| `running` | Pause | `Pause replay (Space)` | `transport.pause()` |
| `paused` | Play | `Resume replay (Space)` | `transport.resume()` |
| `error` | Play | `Retry replay (Space)` | `transport.start()` |

Note the `idle` case also switches the tab away from config — preserve that behaviour
from `SimulationBar.tsx:722–729`; it is why pressing play doesn't leave you staring at a
form.

## 3. Step sizes

The current UI hardcodes ±5 in the buttons and ±5 in the keyboard handler. Make step
size a modifier, consistently across both:

| Input | Bars |
|---|---|
| click / `←` `→` | 1 |
| `Shift` + click / `Shift+←→` | 5 |
| `Alt` + click / `Alt+←→` | 30 |

Show the effective size in the `title` as the modifier changes, or simply document all
three in the label: `Step back (← 1 bar · Shift 5 · Alt 30)`.

## 4. Speed control — one ladder (fixes D13)

```ts
// frontend/src/components/kite/replay/replaySpeeds.ts
export const REPLAY_SPEEDS = [1, 5, 10, 50, 100, 5000] as const;
export type ReplaySpeed = typeof REPLAY_SPEEDS[number];
export const speedLabel = (s: number) => (s >= 5000 ? 'MAX' : `${s}×`);
export function stepSpeed(current: number, dir: 1 | -1): number {
  const i = REPLAY_SPEEDS.indexOf(current as ReplaySpeed);
  const j = Math.min(REPLAY_SPEEDS.length - 1, Math.max(0, (i < 0 ? 0 : i) + dir));
  return REPLAY_SPEEDS[j];
}
```

Both the pill row **and** the `+`/`-` keyboard handler import this. `stepSpeed` is
defensive about a speed that is not on the ladder (which the backend can set via
`/speed`), snapping to index 0 rather than leaving every pill unselected.

Pills: 22 px tall, mono, `--rd-fs-micro`. Active pill uses `--k-brand` fill with
`--k-on-accent` text (**not** `#ffffff` — D8). `MAX` gets a subtle
`background-image` diagonal hatch so it reads as "not a real multiple".

At `data-width="lg"` and below the pill row collapses to a single `<select>`-styled
button showing the current speed with a dropdown of the same six values.

## 5. Disabled treatment

`opacity: .35; cursor: not-allowed; pointer-events: none` — but keep the element
focusable-skipped via `disabled`, not `aria-disabled`, so it leaves the tab order. Six
dimmed buttons in `idle` is a lot of grey; soften by rendering the seek group at
`opacity .5` as a *group* rather than each button individually, which reads as "not yet"
rather than "broken".

## 6. Motion

- M17 press scale on every button.
- The primary button cross-fades its fill colour on state change over `--rd-dur-fast`;
  the icon swap is a 90 ms `opacity` cross-fade, not a hard cut.
- Speed pill selection: the active fill slides between pills (M6 pattern, same
  measured-offset implementation as the segmented control).

## 7. Acceptance criteria

- [ ] `REPLAY_SPEEDS` is the only speed list in the codebase (`grep -rn "5000" frontend/src/components/kite/replay` finds it once).
- [ ] `+` pressed six times from 1× lands on MAX and the MAX pill is highlighted at every step.
- [ ] A backend-set speed of `250` highlights no pill but does not break `+`/`-`.
- [ ] Every button has an `aria-label` containing its shortcut.
- [ ] No emoji.
- [ ] Play button is visually the largest control in the rail.

## 8. Tests

1. primary button label/icon/action for each of the five states
2. `stepSpeed` ladder walk, both directions, both ends, and from an off-ladder value
3. Shift/Alt modifiers change the step size passed to `stepBars`
4. seek buttons disabled in `idle`, enabled in `running` and `paused`
5. starting from `idle` also switches the active tab to `split`
