# A06 — `ReplayMetricsStrip`

**File:** `frontend/src/components/kite/replay/ReplayMetricsStrip.tsx`
**Replaces:** `ConsolidationPnLBar` (`SimulationBar.tsx:127–205`)
**Fixes:** D1 (fabricated slippage), D9 (font sizes), D18 (value-change feedback)

---

## 1. Why it changes

The current strip is rendered inside two of four tabs, so P&L disappears when you are
on Signals or Config. It also prints a **SLIPPAGE DRAG of `₹0.00`** that is not a
measurement — the backend never computes it (D1). A number that is always zero and looks
like a measurement is worse than no number.

## 2. Placement

Always visible, directly under the command rail, 30 px, `--k-surface`,
1 px bottom `--k-border`.

## 3. Metrics

| # | Label | Value | Sub | Source | Tone |
|---|---|---|---|---|---|
| 1 | `REALIZED P&L` | signed ₹, 2 dp | `(n closed)` | `stats.pnl`, closed trades | green/red-brick |
| 2 | `WIN RATE` | `n%` | `(wW · lL)` | `stats.wins`/`losses` | green ≥50 %, red-brick <50 %, dim when 0 trades |
| 3 | `TRADES` | integer | `(n open)` or `all settled` | `stats.trades` | text |
| 4 | `SIGNALS` | integer | `(n filtered)` when filters narrow | `stats.signals_fired` | text |
| 5 | `AVG TRADE` | signed ₹ | — | `pnl / closedCount` | green/red-brick |
| 6 | `EXPOSURE` | integer lots | `(n contracts)` | sum of open `lots`/`quantity` | text |
| 7 | `SLIPPAGE` | see §4 | — | `stats.slippage_total` | red-brick or `—` |
| 8 | `ELAPSED` | `m:ss` | `n bars/s` | `elapsed_real_s`, `bars_played` | dim |

Metrics 6 and 8 are new. `EXPOSURE` is the one number a trader checks before deciding
whether a P&L figure is impressive; `ELAPSED` surfaces `elapsed_real_s` (D15) and gives
the user a reason to trust or distrust a very fast replay.

Order matters: P&L first, always. At `data-width="md"` drop 5–8; at `"sm"` keep only
1–3.

## 4. The slippage rule — the honesty fix

```tsx
const drag = stats.slippage_total;      // number | null | undefined

{drag == null ? (
  <Metric
    label="SLIPPAGE"
    value="—"
    tone="absent"
    title="This replay did not model execution friction. Enable it in configuration to measure spread and slippage drag."
  />
) : (
  <Metric label="SLIPPAGE" value={fmtSignedInr(-drag)} tone="loss" />
)}
```

**Until `23_A14` §2 lands, `slippage_total` is always `undefined`, so this metric
always renders `—`.** That is correct and intended: the em dash says "not measured",
the `₹0.00` it replaces said "measured, and it was free."

Apply the same rule to any other metric whose backing field is optional. Never
`?? 0`.

## 5. Anatomy of one metric

```tsx
<div className="rd-metric" data-tone={tone} title={title}>
  <span className="rd-metric-label">{label}</span>
  <span className="rd-metric-value" data-flash={flashKey}>{value}</span>
  {sub && <span className="rd-metric-sub">{sub}</span>}
</div>
```

Single row, `gap: 5px`, separated by a 1 px `--k-border` vertical rule (not the `|`
character the current version uses — a glyph separator inherits font metrics and shifts
when values change width).

Typography: label `--rd-fs-label`, value `--rd-fs-value` mono tabular, sub
`--rd-fs-micro` `--k-dim`.

## 6. Value-change flash (M18)

```ts
const flashKey = useValueFlash(value);   // increments on change, resets after 400ms
```

```css
.rd-metric-value[data-flash="1"] { animation: rd-flash var(--rd-dur-slow) var(--rd-ease-out); }
@keyframes rd-flash {
  0%   { background: color-mix(in srgb, var(--k-cyan) 22%, transparent); }
  100% { background: transparent; }
}
```

Gated: **do not flash while `speed >= 100`**. At MAX speed every metric changes every
frame and the strip becomes a strobe. Read `speed` from the store and pass
`enabled={speed < 100}` to `useValueFlash`.

## 7. Memoisation

The strip re-renders on every status frame today. Wrap in `React.memo` and select
narrowly:

```ts
const pnl      = useReplayStore(s => s.status.stats.pnl);
const wins     = useReplayStore(s => s.status.stats.wins);
const losses   = useReplayStore(s => s.status.stats.losses);
const tradeN   = useReplayStore(s => s.status.stats.trades.length);
const signalN  = useReplayStore(s => s.status.stats.signals_fired);
```

Never `useReplayStore(s => s.status)` — that is the pattern that makes every subscriber
re-render on every frame (D5).

## 8. Acceptance criteria

- [ ] Strip is visible in every tab and every mode.
- [ ] `SLIPPAGE` renders `—` when the backend sends no value, with an explanatory `title`.
- [ ] No metric renders a `0` derived from a missing field.
- [ ] Flash is suppressed at `speed >= 100` and under reduced motion.
- [ ] Values are mono + `tabular-nums`; the strip does not reflow as digits change.
- [ ] `data-width` responsive drops match §3.

## 9. Tests

1. `slippage_total: undefined` → `—`; `12.5` → `−₹12.50`
2. win rate: 0 trades → `0%` with dim tone; 3W/1L → `75%` green
3. avg trade divides by **closed** trades, not all trades
4. flash does not fire when `speed >= 100`
5. strip subscribes to scalar selectors (assert render count under repeated status writes)
