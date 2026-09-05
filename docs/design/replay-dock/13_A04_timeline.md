# A04 — `ReplayTimeline` (the new centrepiece)

**File:** `frontend/src/components/kite/replay/ReplayTimeline.tsx`
**Replaces:** `SimulationBar.tsx:805–816` (the 3 px progress bar) and the
`heatmapDots` memo (`:334–360`)
**Fixes:** D11 (no `role="progressbar"`), and the core UX gap — **there is currently no
way to scrub**

---

## 1. Why this is the biggest change

Today the only way to move through a session is `stepBars(±5)`, `jumpStart`, `jumpEnd`.
The 3 px bar is a readout, not a control. A replay tool whose timeline cannot be clicked
is a tape player without a shuttle. This artifact makes the timeline the primary
interactive object and gives the session an at-a-glance shape.

## 2. Anatomy (40 px tall, fills the command rail's remaining width)

```
09:00                     11:30                     14:00        15:30
├─────────────────────────┼─────────────────────────┼──────────────┤   ← tick rail (10px)
│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓┃░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│   ← track (12px)
│   ●    ● ●        ●  ●    ●     ┃      ● ●                      │   ← event lane (12px)
                                  ↑ playhead
```

Three stacked lanes inside one `position: relative` container:

| Lane | Height | Content |
|---|---|---|
| Tick rail | 10 px | hour labels at 09:00/10:00/…/15:30, `--rd-fs-micro`, `--k-faint`; at `data-width="sm"` only 09:00 / 12:00 / 15:30 |
| Track | 12 px | sunken groove `--k-surface-sunken`, played portion filled `--k-cyan` at 55 % opacity, pre-open/post-close regions hatched |
| Event lane | 12 px | one 5 px dot per signal, coloured by direction, positioned by time |

## 3. Coordinate model

The current implementation derives position from `parseTimeToMinutes` on a
`HH:MM:SS` string against `config.start_time`/`end_time`. Keep that model — it is
correct and cheap — but hoist it into a single memo that produces a **pure function**:

```ts
type SessionScale = {
  startMin: number;
  endMin: number;
  span: number;                 // max(1, endMin - startMin)
  pctFor(timeIso: string): number;   // 0..100, clamped
  timeForPct(pct: number): string;   // inverse, "HH:MM:SS"
};
```

`timeForPct` is new and is what makes scrubbing possible. Both directions must round to
the nearest bar boundary using `config.resolution` (`'5m'` today), so a scrub lands on a
bar, not between two.

Multi-day ranges (`config.end_date !== config.date`) are **out of scope for v1** of this
artifact — the current UI already mis-renders them, since `parseTimeToMinutes` ignores
the date part entirely. Document the limitation in the component header and render a
`Multi-day range — timeline shows session times only` note above the track when
`end_date !== date`. Do not silently draw a wrong picture.

## 4. Scrubbing

```tsx
<div
  role="slider"
  aria-label="Replay position"
  aria-valuemin={0}
  aria-valuemax={100}
  aria-valuenow={Math.round(progressPct)}
  aria-valuetext={`${currentTime} IST, ${barsPlayed} of ${barsTotal} bars`}
  aria-disabled={state === 'idle'}
  tabIndex={state === 'idle' ? -1 : 0}
  className="rd-timeline"
  onPointerDown={beginScrub}
  onKeyDown={onScrubKey}
/>
```

Behaviour:

| Interaction | Result |
|---|---|
| Click anywhere on the track | seek to that bar |
| Press and drag | **preview** scrub: playhead follows, tooltip shows target time, **no request is sent** until pointerup |
| Pointerup | one `seek` request to the final position |
| `←` `→` | ±1 bar (`Shift` 5, `Alt` 30) — same ladder as the transport |
| `Home` / `End` | jump start / end |
| `PageUp` / `PageDown` | ±30 bars |

**Drag must not fire a request per pointermove.** The current backend exposes only
`POST /seek` with `bars_offset`; a drag across a session would issue hundreds. Preview
locally, commit once. This requires an absolute seek — see `23_A14_backend_contract.md`
§4, which adds `{ action: "seek_pct" | "seek_time" }`. Until that lands, convert the
final position to a relative `bars_offset` from the current bar and send that; it is
exact because you know `bars_played`.

While `state === 'running'`, a scrub implicitly pauses, seeks, then resumes — mirroring
every video player. Show this: the play button flips to Pause during the drag.

## 5. Event lane

```ts
const dots = useMemo(() => events.map(ev => ({
  key: ev.time_iso + ev.instrument + ev.strategy,
  left: scale.pctFor(ev.time_iso),
  tone: isBull(ev.direction) ? 'bull' : 'bear',
  strategy: ev.strategy,
  label: `${fmtTime(ev.time_iso)} · ${ev.strategy.toUpperCase()} · ${ev.instrument} ${ev.direction}`,
})), [events, scale]);
```

- Dot is 5 px, `border-radius: 50%`, `background` = `--k-green` / `--k-red-brick`,
  `box-shadow: 0 0 4px currentColor` for the glow the current version has and should keep.
- **Clustering:** when two dots land within 4 px, merge into one dot with a
  `data-count` and a slightly larger radius (7 px). Without this, a busy session renders
  a solid bar and conveys nothing. Compute clusters in the same memo, bucketing by
  `Math.round(left * trackWidthPx / 100 / 4)`.
- Hover a dot → a tooltip with the signal detail. Click a dot → seek to that bar **and**
  select the corresponding row in the signals table (scroll it into view, flash it).
  That link is the feature that makes the timeline worth building.
- Dots enter with M10 (`scale 0→1`, 140 ms, slight overshoot).

Cap the rendered dot count at 600; beyond that, cluster more aggressively. A 5000×
replay of a full day can emit thousands and each is a DOM node.

## 6. Playhead

```css
.rd-playhead {
  position: absolute; top: 0; bottom: 0; width: 2px;
  background: var(--k-cyan);
  transform: translateX(var(--rd-playhead-x));
  transition: transform var(--rd-dur-instant) linear;
  will-change: transform;
}
.rd-playhead::after {           /* grab handle */
  content: ''; position: absolute; top: -3px; left: -4px;
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--k-cyan);
  box-shadow: 0 0 0 2px var(--k-bg);
}
```

Position via a CSS custom property written from JS, **not** `left`. That keeps it on the
compositor at 6.7 updates/s (or higher once SSE lands).

## 7. Pre-open / post-close regions

`config.start_time` defaults to `09:00:00` but NSE opens at `09:15`. Hatch `09:00–09:15`
and anything after `15:30` so the user can see that the flat stretch at the start is
pre-open, not a dead strategy. Use a 45° `repeating-linear-gradient` in
`--k-border` at 4 px pitch.

## 8. Idle / loading

- `idle`: track at 40 % opacity, no playhead, no dots, tick labels dimmed, `aria-disabled`.
- `loading`: M22 shimmer sweeping the track.

## 9. Acceptance criteria

- [ ] Clicking the track seeks; the resulting `current_time_iso` matches the clicked
      position to within one bar.
- [ ] Dragging issues exactly **one** seek request (assert on the fetch spy call count).
- [ ] `role="slider"` with correct `aria-valuenow` / `aria-valuetext`; keyboard-operable.
- [ ] Dots cluster: 200 signals in a 1 px-per-2-minutes track render ≤ 600 nodes.
- [ ] Clicking a dot scrolls and flashes the matching signals row.
- [ ] Playhead uses `transform`; no layout thrash (verified in a profile, or at minimum
      by asserting the inline style writes a custom property, not `left`).
- [ ] Multi-day range shows the limitation note.
- [ ] Reduced motion: playhead still moves, dots appear without scaling.

## 10. Tests

1. `pctFor`/`timeForPct` round-trip within one bar for 20 sample times
2. clamping: times before `start_time` → 0, after `end_time` → 100
3. drag → single seek call with the correct final offset
4. keyboard: ←/→/Shift/Alt/Home/End produce the right offsets
5. clustering merges dots within 4 px and sets `data-count`
6. `aria-valuetext` includes the current time and bar counts
7. idle renders no playhead and `aria-disabled="true"`
