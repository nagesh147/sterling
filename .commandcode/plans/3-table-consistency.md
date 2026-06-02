# 3-Table Consistency — Spot + Futures + Options

## Current State

| Property | Spot (ScalpingTab) | Futures | Options |
|---|---|---|---|
| Table layout | `tableLayout: fixed, minWidth: 920` | none | none |
| Cell padding | `4px 6px` | `6px 8px` | `6px 8px` |
| Header padding | `4px 6px` | `6px 8px` | `6px 8px` |
| Strategy fontSize | 10, fw 700 | 9, fw normal | 9, fw normal |
| Execute btn fontSize | 11, fw 800 | 10, fw 800 | 10, fw 800 |
| Row bottom border | always present | hidden when expanded | hidden when expanded |
| Header border color | `var(--t-border)` | `c.border` | `c.border` |
| Row border color | `var(--t-br2, ...)` | `c.border2` | `c.border2` |
| Color source | inline `var(--t-*)` | `c.*` tokens | `c.*` tokens |

## Target (all three)

| Property | Value |
|---|---|
| Table | `width: 100%, tableLayout: fixed, borderCollapse: collapse, fontSize: 11` |
| Cell padding | `5px 8px` |
| Header padding | `5px 8px` |
| Header style | `background: c.surface, color: c.muted, fontSize: 9, fontWeight: 600, letterSpacing: 0.06em, textTransform: uppercase` |
| Row data color | `c.text` |
| Row fontWeight (standard) | 600 |
| Row fontWeight (highlighted: symbol, R, P&L) | 700 |
| Strategy column | `fontSize: 10, fontWeight: 600, color: c.muted` |
| Execute button | `fontSize: 11, fontWeight: 700, padding: 4px 12px, borderRadius: 5` |
| All borders | `c.border` / `c.border2` |
| Expanded row bg | `alpha(c.blue, 0.06)` |

## Files

1. `frontend/src/components/scalping/ScalpingTab.tsx` — spot/index table
2. `frontend/src/components/derivatives/FuturesCandidatesTable.tsx` — futures table
3. `frontend/src/components/derivatives/OptionsCandidatesTable.tsx` — options table

## Changes — ScalpingTab.tsx

- Import `c` from terminalUI (check if already imported)
- Table `<thead>`: fontWeight 700→600, letterSpacing 0.08em→0.06em, color var(--t-dim)→c.muted
- `<th>` padding: 4px 6px→5px 8px
- `<td>` padding: 4px 6px→5px 8px
- Strategy cell: fontWeight 700→600, color var(--t-dim)→c.muted
- Status cell: fontWeight 700→600
- Direction cell: fontWeight 700→600
- Symbol cell: fontWeight 700→600
- Executed pill: fontWeight 800→700
- Execute button: fontWeight 800→700

## Changes — FuturesCandidatesTable.tsx & OptionsCandidatesTable.tsx

- Add `tableLayout: fixed` and `minWidth: 920` to table
- Cell padding: 6px 8px→5px 8px (match spot)
- Header fontWeight: 700→600, letterSpacing: 0.08em→0.06em, color: c.dim→c.muted
- Strategy cell: fontSize 9→10, add fontWeight 600
- Execute button: fontSize 10→11 (match spot), fontWeight 800→700
- AUTO pill: fontWeight 800→700
- Consolidation footer rows: align fontSize with rest
