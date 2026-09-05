# A07 — `ReplaySignalsTable`

**File:** `frontend/src/components/kite/replay/ReplaySignalsTable.tsx`
**Replaces:** `renderSignalsTable` (`SimulationBar.tsx:381–421`)
**Fixes:** D2 (dead contract chip), D5/D6 (re-render cost), D9, D11

---

## 1. Columns

| # | Header | Width | Content | Align |
|---|---|---|---|---|
| 1 | `TIME` | 72 | `HH:MM:SS` mono | left |
| 2 | `STRATEGY` | 120 | colour dot + name (from `REPLAY_STRATEGIES`) | left |
| 3 | `INSTRUMENT` | 1fr | see §2 | left |
| 4 | `DIR` | 68 | `LONG` / `SHORT` chip | left |
| 5 | `STRENGTH` | 72 | `STRONG` / `MODERATE` chip | left |
| 6 | `ENTRY` | 88 | ₹ mono | right |
| 7 | `SL` | 88 | ₹ mono, `--k-red-brick` | right |
| 8 | `TARGET` | 88 | ₹ mono, `--k-amber` | right |
| 9 | `R:R` | 60 | computed `|target−entry| / |entry−stop|`, 1 dp | right |

`STRENGTH` and `R:R` are new. `strength` is already on the wire
(`simulation.py:46`) and never shown; R:R is the number that tells you whether a signal
was worth taking, and it is pure arithmetic on fields you already have. Guard the
division: `entry === stop` → `—`.

Numeric columns right-align. The current table left-aligns prices, which defeats
tabular figures.

## 2. The instrument column and D2

```tsx
{ev.contract ? (
  <span className="rd-contract">
    <strong>{ev.contract}</strong>
    {ev.spot != null && <span className="rd-spot">Spot {fmtInr(ev.spot)}</span>}
  </span>
) : (
  <span className="rd-underlying">{ev.instrument}</span>
)}
```

Keep the branch — but understand that **today it always takes the `else` path**, because
the backend never sends `contract`/`spot` (D2). Two acceptable outcomes:

- **Preferred:** implement `23_A14` §3 so the backend emits `contract` and `spot`. Then
  the column shows `NIFTY26SEP24500CE` with a `Spot ₹24,512` badge, which is what a
  trader needs to know which leg fired.
- **If §3 is deferred:** delete the branch and the `contract?`/`spot?` type fields, and
  rename the column to `UNDERLYING`. Do not ship a branch that documents a capability
  the system does not have.

Whichever you choose, say so in the PR. Silently keeping dead code is what produced D2.

## 3. Ordering and virtualisation

- Newest first. The current code does `events.slice().reverse()` **inside render**, on
  every frame — an O(n) copy at 6.7 Hz. Instead keep the store's array append-only and
  render with `flex-direction: column-reverse` on the body, or memoise the reversed
  array keyed on `events.length`.
- Above 200 rows, virtualise. Fixed 28 px rows make this trivial — a windowing slice of
  `[start, start+visibleCount+overscan]` driven by `scrollTop` is ~30 lines and needs no
  dependency. Do not add `react-window`; the app does not have it and the row height is
  fixed.
- **Auto-scroll:** while `state === 'running'` and the user is within 40 px of the top
  (newest end), keep pinned to newest. If the user scrolls away, stop pinning and show a
  `↑ 12 new signals` button that scrolls back and clears. Silently yanking a trader's
  scroll position mid-read is the single most irritating behaviour a streaming table can
  have.

## 4. Row

```tsx
<div
  className="rd-row"
  data-dir={isBull ? 'long' : 'short'}
  data-new={isNew || undefined}
  data-selected={selectedKey === key || undefined}
  role="row"
  tabIndex={0}
  onClick={() => onSelect(key)}
/>
```

- 28 px, `border-bottom: 1px solid var(--k-border)`.
- Hover `--k-surface-hover`.
- A 2 px left rule in the direction colour: green for long, red-brick for short. This is
  the cheapest way to make direction scannable down a column.
- `data-new` triggers M9: enter animation plus a 600 ms cyan background decay. Compute
  "new" as `time_iso > lastSeenTime` captured when the pane mounts or the user last
  scrolled to top — not as "index 0", which would flash the same row repeatedly.
- Selecting a row highlights it and highlights its dot in the timeline (the reverse of
  the A04 link).

## 5. Empty and loading states

Use the `EmptyState` primitive with the copy from `03_IA_STATES_MOTION.md §4.3`. The
current single string ("Replay stepping through bars... No signals triggered yet.") is
wrong in the idle case, which is the case a first-time user sees.

## 6. Export

One button in the pane header, `Export` icon + label, calling the **single** exporter
from `replayCsv.ts` (fixes D16):

```ts
export function toCsv(rows: Record<string, unknown>[], columns: CsvColumn[]): string;
export function downloadCsv(filename: string, csv: string): void;
```

`toCsv` **must** RFC-4180 escape: wrap any field containing `,`, `"` or a newline in
quotes and double internal quotes. Neither current exporter does, so a symbol or strategy
name with a comma corrupts the file today.

Filename: `sterling_replay_signals_{date}_{startTime}-{endTime}.csv`.

## 7. Performance contract

- `React.memo` on the table and on the row.
- Row key is `${time_iso}|${strategy}|${instrument}` — stable across frames. Index keys
  (used today) make React re-mount rows whenever the array grows, which is why the
  enter animation currently retriggers on unrelated rows.
- Subscribe with `useReplayStore(s => s.status.stats.events)` only; never the whole
  `status`.
- Target: at 400 signals and speed MAX, the table costs < 4 ms per frame. Measure with
  the React Profiler and put the number in the PR.

## 8. Acceptance criteria

- [ ] Nine columns as specified; numerics right-aligned and tabular.
- [ ] R:R computed, `—` when undefined.
- [ ] Contract branch is either backed by real backend data or removed — not left dead.
- [ ] Auto-scroll pins only when already at top; `↑ n new` appears otherwise.
- [ ] CSV export escapes commas and quotes (test with a symbol containing both).
- [ ] 400 rows render without dropping frames at MAX speed.
- [ ] Row selection cross-highlights the timeline dot.

## 9. Tests

1. R:R arithmetic including the `entry === stop` guard
2. reverse ordering without an in-render `.slice().reverse()` (assert the memo is hit)
3. auto-scroll pins at top, releases after a user scroll, `↑ n new` counts correctly
4. `toCsv` escaping: `a,b`, `he said "hi"`, embedded newline
5. row key stability across an append (rows do not remount)
6. empty state copy differs between idle and running-with-no-signals
