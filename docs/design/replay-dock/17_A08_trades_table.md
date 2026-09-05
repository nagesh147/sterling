# A08 — `ReplayTradesTable`

**File:** `frontend/src/components/kite/replay/ReplayTradesTable.tsx`
**Replaces:** `renderTradesTable` (`SimulationBar.tsx:423–526`)
**Fixes:** D1 (fabricated slippage column and `raw ₹` lines), D5/D6, D9, D11

---

## 1. Columns

| # | Header | Width | Content | Align |
|---|---|---|---|---|
| 1 | `ID` | 64 | `trade_id`, mono, `--k-blue` | left |
| 2 | `IN` | 76 | entry `HH:MM:SS` | left |
| 3 | `OUT` | 76 | exit time, or `OPEN` chip | left |
| 4 | `HELD` | 60 | duration, compact (`47m`) | right |
| 5 | `STRATEGY` | 110 | dot + name | left |
| 6 | `CONTRACT` | 1fr | `symbol`, with `strike`+`opt_type` as a sub-line | left |
| 7 | `SIZE` | 88 | `5L` with `(1,250)` sub | right |
| 8 | `ENTRY` | 88 | ₹ | right |
| 9 | `EXIT` | 88 | ₹ or `—` | right |
| 10 | `SL / TGT` | 110 | `₹x / ₹y`, red-brick / amber | right |
| 11 | `STATUS` | 72 | `WIN` / `LOSS` / `OPEN` chip | center |
| 12 | `P&L` | 120 | signed ₹ + `(%)` | right |

`HELD` and `SL / TGT` are new; `stop_loss` and `target_price` are on the wire
(`simulation.py:66–67`) and never shown, which makes it impossible to tell whether a
loss hit its stop or was closed at session end.

**The `SLIPPAGE` column is removed**, and the `raw ₹` sub-lines under entry/exit are
removed, unless `23_A14` §2 lands first. See §2.

## 2. Friction columns — conditional on real data (D1)

```tsx
const hasFriction = trades.some(t => t.slippage != null);
```

- `hasFriction === false` → the column is **not rendered at all**, and the pane header
  shows a one-line note: *"Execution friction not modelled — fills are at signal price."*
  linking to the config sheet.
- `hasFriction === true` → render the `SLIPPAGE` column and the `raw ₹` sub-lines, both
  exactly as the current implementation draws them (that part is good work; it just has
  no data).

This is a conditional-column pattern, not a `?? 0`. It is the difference between "we did
not measure this" and "we measured zero".

## 3. Totals row

Sticky footer, `--k-surface`, `border-top: 2px solid var(--k-border)`. Keep the current
footer's content and add:

| Cell | Value |
|---|---|
| label | `Total · {n} trades ({closed} closed, {open} open)` |
| SIZE | total lots + total quantity |
| SL/TGT | `—` |
| STATUS | `{wins}W / {losses}L` |
| P&L | total, `--rd-fs-value` weight 800 |

Also add a **`GROSS` vs `NET`** distinction *only when* `hasFriction` — `GROSS` is
`sum(pnl)` before drag, `NET` after. Without friction data there is only one number and
labelling it `NET` would be a claim.

## 4. Grouping

Add an optional group-by control in the pane header: `None | Strategy | Contract`.
When grouped, insert a 24 px group header row with the group's trade count and subtotal
P&L, and make it collapsible. A day with 40 trades across 6 strategies is unreadable
flat, and the summary modal's strategy breakdown is currently the only place this exists
— it should be here, live, while the replay runs.

Group state lives in component state, not the store; it is a view preference.

## 5. Open-position treatment

Rows with `status === 'OPEN'`:

- `OUT` shows an `OPEN` chip in `--k-cyan`, not the string `'OPEN'` in a time column.
- `EXIT` shows the **current mark** if the backend can provide it, else `—`. Do not show
  the entry price there.
- `P&L` shows unrealised, in italic or with a `~` prefix, so it is not confused with
  realised. The metric strip's `REALIZED P&L` must exclude these — verify against
  `simulation.py`'s accounting before assuming it does.

## 6. Row and performance

Identical contract to A07 §4 and §7: 28 px rows, `React.memo`, stable key on
`trade_id`, narrow selector `s => s.status.stats.trades`, virtualise above 200 rows,
no in-render `.slice().reverse()`.

Row left rule: green for `WIN`, red-brick for `LOSS`, cyan for `OPEN`.

## 7. Export

Same single `replayCsv.ts` exporter. Column set must **match what is rendered** — the
current dock exports 20 columns including 4 that are always empty (D16). Build the
export column list from the same array that drives the table, so they cannot diverge:

```ts
const COLUMNS: TradeColumn[] = [...];         // drives <thead>, <tbody>, and CSV
```

## 8. Acceptance criteria

- [ ] `SLIPPAGE` and `raw ₹` appear **only** when at least one trade carries `slippage`.
- [ ] When absent, the explanatory note is shown instead.
- [ ] `HELD` and `SL / TGT` columns render from existing backend fields.
- [ ] Open rows are visually distinct and their unrealised P&L is marked as such.
- [ ] Totals row separates gross/net only when friction data exists.
- [ ] Group-by strategy produces correct subtotals.
- [ ] Export columns are generated from the same `COLUMNS` array as the table.

## 9. Tests

1. friction columns hidden with `slippage: undefined`, shown with a value present
2. `HELD` formatting: 0 → `< 1m`, 47 → `47m`, 72 → `1h 12m`
3. open row shows `~` unrealised and is excluded from the realized total
4. group-by subtotals equal the sum of their rows
5. CSV column headers equal the rendered column headers
6. totals row lots/qty match the sum of rows
