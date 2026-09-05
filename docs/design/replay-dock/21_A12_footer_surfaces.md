# A12 — Footer surfaces

**Files:**
`frontend/src/components/kite/replay/ReplayFooterChip.tsx` (replaces
`SimulationFooterButton` + `SimulationFooterBadge`, `SimulationBar.tsx:1198–1231`)
`frontend/src/components/kite/KiteFooterStatus.tsx` (the `▶ SIMULATION` chip, `:79–96`)

---

## 1. Today there are three footer surfaces for one thing

| Surface | Where | Shows |
|---|---|---|
| `SimulationFooterButton` | `KiteLayout.tsx:756` | `REPLAY DOCK (10:47:05)` toggle chip |
| `SimulationFooterBadge` | `KiteLayout.tsx:757` | a pulsing `REPLAYING` badge, right next to it |
|  `KiteFooterStatus` sim chip | `:79–96` inside the status cluster | `▶ SIMULATION (10:47:05)` |

Two of these render the same clock at the same moment, 40 px apart, in two different
colours. Collapse to **one**.

## 2. The single chip

```tsx
<button
  type="button"
  className="kw-dock-chip rd-footer-chip"
  data-active={open || active}
  data-state={state}
  aria-pressed={open}
  aria-label={open ? 'Minimise replay dock' : 'Open replay dock'}
  title={hint}
  onClick={() => setOpen(!open)}
>
  <span className="rd-footer-glyph">{active ? <Icons.Signal/> : <Icons.Play/>}</span>
  REPLAY
  {active && <span className="rd-footer-clock">{currentTime}</span>}
  {active && <span className="rd-footer-dot" data-pulse />}
</button>
```

- Keeps `kw-dock-chip` so it matches every other footer chip's height, radius, hover
  lift and shadow (`KiteLayout.tsx` `WORKSPACE_CSS`).
- `--k-cyan` accent when active, matching the dock's replay identity.
- The clock is mono + tabular so the chip does not resize each second. The current
  version interpolates `${status.current_time_iso || 'RUNNING'}` into a proportional
  font, so the chip's width oscillates — a small thing that is very visible in a footer.
- The pulsing dot replaces the separate `REPLAYING` badge.
- `title` carries the detail the badge used to imply:
  `Replaying 2026-09-04 · 10:47:05 IST · 50× · 47 signals`.

**Delete** `SimulationFooterBadge` and remove the `simActive` branch from
`KiteFooterStatus.tsx:79–96` entirely.

## 3. Why remove it from `KiteFooterStatus`

That component's own docstring explains its discipline: each chip shows only what its
engine actually publishes, and it deliberately refuses to invent a plausible dash. The
simulation chip is not an engine — it is a mode. Putting a mode chip in the engine
cluster implies replay is a seventh strategy. Move it out; the engine cluster becomes
uniformly "engines", which is what its comment already claims.

The one thing worth keeping from that chip is the idea that **replay state belongs next
to broker state**, because both answer "is what I am looking at real?". So place the
single replay chip immediately *left* of the `KITE` broker button, before the divider,
rather than in the centre cluster where the dock toggle lives today.

## 4. Behaviour

| State | Chip |
|---|---|
| `idle`, dock closed | `REPLAY`, dim, play glyph |
| `idle`, dock open | `REPLAY`, `--k-brand` (matches `aria-pressed`), play glyph |
| `loading` | `REPLAY · starting…`, dim, spinner glyph |
| `running` | `REPLAY 10:47:05` + pulsing cyan dot |
| `paused` | `REPLAY 10:47:05 ‖` amber dot, not pulsing |
| `error` | `REPLAY · failed`, `--k-red`, click opens the dock **and** the error detail |

Clicking always toggles the dock. It never starts or stops a replay — a footer chip that
can start a simulation is a footer chip that will start one by accident.

## 5. Motion

- M20 pulse on the dot while running; `data-pulse` so reduced motion pins it.
- The chip's hover lift comes from `.kw-dock-chip:hover { transform: translateY(-1px) }`
  already in `WORKSPACE_CSS`. Nothing to add.
- State colour changes cross-fade over `--rd-dur-fast`.

## 6. Acceptance criteria

- [ ] Exactly one replay surface in the footer.
- [ ] `SimulationFooterBadge` deleted; `KiteFooterStatus`'s sim branch deleted.
- [ ] Chip width does not change as the clock ticks (mono + tabular).
- [ ] `aria-pressed` reflects dock openness; `aria-label` changes with it.
- [ ] Clicking never mutates replay state.
- [ ] Error state is reachable and opens the detail.

## 7. Tests

1. one chip renders for each of the six states with the right label and tone
2. click toggles `open` and does not call any transport command
3. `aria-pressed` / `aria-label` track `open`
4.  `KiteFooterStatus` renders no simulation chip (regression guard)
