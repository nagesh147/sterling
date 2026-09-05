# A05 — `ReplaySessionPicker` + `ReplayFilters`

**Files:**
`frontend/src/components/kite/replay/ReplaySessionPicker.tsx`
`frontend/src/components/kite/replay/ReplayFilters.tsx`
**Replaces:** `SimulationBar.tsx:748–802` (the two dropdowns) and `:750–762` (preset pills)
**Fixes:** D10 (emoji), D11 (dropdown a11y), D14 (unused `/available-dates`)

---

## 1. Session picker

### 1.1 Trigger

A single button in the view bar, right-aligned:

```
[ 📅 → Calendar icon ]  Thu 4 Sep 2026  ·  09:00–15:30  ▾
```

At `data-width="lg"` → `Thu 4 Sep ▾`. At `"sm"` → `4 Sep ▾`.

`aria-haspopup="dialog"`, `aria-expanded`, disabled while `state !== 'idle'` with
`title="Stop the replay to change the session"` — one disabled control instead of the
six the current UI disables individually.

### 1.2 Popover contents

Body-portalled at `--rd-z-dropdown`, anchored to the trigger, `role="dialog"`,
`aria-label="Choose replay session"`, focus-trapped, `Escape` closes and returns focus.

```
┌──────────────────────────────────────────┐
│ QUICK                                    │
│  ● Last working day     Thu 4 Sep 2026   │
│  ○ Previous session     Wed 3 Sep 2026   │
├──────────────────────────────────────────┤
│ SESSION DATE                             │
│  [ 2026-09-04 ]   →   [ 2026-09-04 ]     │
│   start date          end date (range)   │
├──────────────────────────────────────────┤
│ MARKET HOURS                             │
│  [ 09:00:00 ]  to  [ 15:30:00 ]          │
│  ⤷ Full session   Regular (09:15–15:30)  │
│    First hour     Last hour              │
├──────────────────────────────────────────┤
│  ⚠ No stored candles for 2026-09-06.     │
│                        [Cancel] [Apply]  │
└──────────────────────────────────────────┘
```

### 1.3 Quick presets — preserve the logic exactly

`getDynamicMarketPresets()` (`useSimulation.ts:162–216`) filters against real NSE
holidays and the 09:00 IST open. **Move it unchanged** into
`frontend/src/lib/replay/marketSessions.ts`; do not reimplement. Its emoji (`📅`) is
part of the returned `label` string — strip emoji from the labels in that module and
render the icon in the component.

Presets become radio options, not pills. They are mutually exclusive with the date
inputs and there are only 2–4 of them; a radio group is honest about that and is
keyboard-navigable for free.

### 1.4 Wire up `/available-dates` (fixes D14)

```ts
const { data: availableDates } = useQuery({
  queryKey: ['replay', 'available-dates', instrument, resolution],
  queryFn: () => fetch(`/api/v1/simulation/available-dates?instrument=${instrument}&resolution=${resolution}`).then(r => r.json()),
  staleTime: 15 * 60_000,
});
```

Use it for three things:

1. `min` / `max` on the date inputs.
2. A validation note (the `⚠` line) when the chosen date is not in the set. Warn, do not
   block — the endpoint has a synthetic 90-business-day fallback when the OHLCV store is
   empty (`simulation.py:88–103`), so a hard block would be wrong whenever that fallback
   is in play. Say which case you are in: `"No stored candles"` vs
   `"Candle store is empty; dates unverified"`.
3. Disable `Apply` only when the date is syntactically invalid or `end < start`.

**Honesty note for the implementer:** that endpoint's fallback invents dates. Do not
present its output as "sessions with data" without checking whether the fallback fired.
Add `source: "store" | "fallback"` to the response — see `23_A14` §5.

### 1.5 Market-hours quick ranges

Four buttons that set both time fields at once. `Full session` = `09:00–15:30` (today's
default, which includes pre-open), `Regular` = `09:15–15:30`, `First hour` =
`09:15–10:15`, `Last hour` = `14:30–15:30`. This is the single most requested shortcut
for anyone studying an opening-range strategy, and it costs eight lines.

## 2. Filters

### 2.1 Trigger

```
[ Filters · 3 ▾ ]
```

Shows the count of active narrowings (strategies + legs). Zero narrowings renders
`Filters ▾` with no badge. Disabled while `state !== 'idle'`.

### 2.2 Popover

`role="dialog"`, two sections, both multi-select:

```
STRATEGIES                              [All] [None]
 ☑ ● SuperTrend
 ☑ ● VCP Squeeze
 ☐ ● Adaptive Edge
 ☐ ● Bear to Bearish
 ☐ ● ATM Imbalance
 ☐ ● Navigator
 ☐ ● NIFTY ORB
OPTION LEGS                             [All] [None]
 ☑ ATM     ☐ ITM1   ☐ ITM2   ☐ OTM1   ☐ OTM2
```

- The `●` is the **strategy colour dot** (see `02_DESIGN_SYSTEM.md §5`), from a single
  registry so the same strategy is the same colour in the timeline, the tables and the
  summary. Define it once:

```ts
// replayStrategies.ts
export const REPLAY_STRATEGIES = [
  { id: 'supertrend',      label: 'SuperTrend',      tone: 'var(--k-blue)' },
  { id: 'vcp',             label: 'VCP Squeeze',     tone: 'var(--k-violet)' },
  { id: 'adaptive_edge',   label: 'Adaptive Edge',   tone: 'var(--k-cyan)' },
  { id: 'bear_to_bearish', label: 'Bear to Bearish', tone: 'var(--k-purple)' },
  { id: 'atm_imbalance',   label: 'ATM Imbalance',   tone: 'var(--k-amber)' },
  { id: 'navigator',       label: 'Navigator',       tone: 'var(--k-emerald)' },
  { id: 'nifty_orb',       label: 'NIFTY ORB',       tone: 'var(--k-orange)' },
] as const;
```

  This replaces the emoji-labelled `STRATEGY_OPTIONS` at `SimulationBar.tsx:41–49`.
  **Verify each id against the backend** before shipping — the backend's strategy names
  are produced inside `simulation.py`'s signal generator, and an id mismatch silently
  filters everything out.

- Checkbox rows use real `<input type="checkbox">` inside `<label>`, not `☑`/`☐` text
  in a `<button>`. That gets keyboard, screen-reader, and indeterminate state for free.
- Preserve the store's existing `toggleStrategy` / `toggleMoneyness` semantics
  (`useSimulation.ts:304–349`): deselecting the last item falls back to `all`/`ALL`.
  It is unusual but it prevents an empty replay, and existing tests assert it.

### 2.3 Applied-filter chips

When any filter is narrowed, render dismissible chips in the view bar next to the
trigger:

```
[SuperTrend ×] [VCP ×] [ATM ×]
```

so the user can see what is filtered without opening the popover. This is the fix for
the current `STRAT (2) ▼` label, which tells you a count but not what.

## 3. Shared popover primitive

Both popovers use one component so the a11y is written once:

```tsx
<ReplayPopover
  trigger={…}
  label="Choose replay session"
  align="end"
  open={open}
  onOpenChange={setOpen}
>
  {children}
</ReplayPopover>
```

Requirements: body portal at `--rd-z-dropdown`; positioned by
`getBoundingClientRect()` with viewport flipping; `Escape` closes; click-outside closes;
focus trapped while open; focus returns to the trigger on close; `aria-expanded` on the
trigger; first focusable child focused on open; arrow keys move within the list.

The current implementation (`SimulationBar.tsx:748–802`) is `position: absolute` inside
the toolbar, which is `overflow-x: auto` — so the popover **clips** at the toolbar edge
today. Portalling fixes that too.

## 4. Acceptance criteria

- [ ] `getDynamicMarketPresets` moved, not rewritten; its existing test still passes.
- [ ] Popovers are body-portalled and are not clipped by the toolbar's `overflow`.
- [ ] Escape closes each popover and returns focus to its trigger.
- [ ] `/available-dates` is called and its result bounds the date inputs.
- [ ] Choosing a date outside the available set shows a warning but does not block.
- [ ] Strategy colours are read from `REPLAY_STRATEGIES` and match the timeline dots.
- [ ] No emoji in strategy or leg labels.
- [ ] Applied filters render as dismissible chips.

## 5. Tests

1. presets render only valid sessions (reuse the existing holiday/weekend fixtures)
2. Escape and click-outside close the popover; focus returns to the trigger
3. tab order inside the popover is trapped
4. date outside `availableDates` shows the warning, `Apply` stays enabled
5. `end < start` disables `Apply`
6. deselecting the last strategy falls back to `all`
7. filter chips render one per narrowing and dismiss correctly
