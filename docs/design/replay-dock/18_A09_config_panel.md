# A09 — `ReplayConfigSheet`

**File:** `frontend/src/components/kite/replay/ReplayConfigPanel.tsx`
**Replaces:** the Configuration tab (`SimulationBar.tsx:888–1073`)
**Fixes:** D1 (fictional friction section), D10, D11

---

## 1. From tab to sheet

Configuration stops being a peer of Signals/Trades. It becomes a **sheet** that slides
in from the right edge of the dock, 420 px wide (full width below `data-width="md"`),
over a 40 % scrim, opened by a `Configure` button in the view bar.

Why: it is used once per session, and as a tab it forced every one of its nineteen
controls to carry its own `disabled={simActive}`. As a sheet, the *entry point* is
disabled while a replay runs and the controls inside can be simple.

```tsx
<ReplaySheet open={configOpen} onClose={…} label="Replay configuration" side="end">
```

Focus trapped, `Escape` closes, focus returns to the `Configure` button. Slide is
`transform: translateX(100%)→0` over `--rd-dur-base` with `--rd-ease-out`; the scrim
fades (M13).

## 2. Sections

Keep the `<details>` accordion pattern — it works, it is keyboard-accessible for free,
and the existing `.sim-settings-*` visual treatment is one of the better parts of the
current CSS. Port it to `rd-`, replace emoji titles with icons, and add M15/M16
(`grid-template-rows: 0fr→1fr` expand, caret rotate).

### 2.1 Session (open by default)

Moves out. It now lives in the session picker (A05). The sheet's Session section becomes
a **read-only summary** of what the picker holds, with an `Edit` button that opens the
picker. One source of truth for the session; two editors is how they drift.

### 2.2 Strategies

Same as the filters popover (A05 §2.2), rendered inline. The popover and the sheet share
one `<ReplayStrategyPicker>` component so they cannot disagree.

### 2.3 Position sizing

| Field | Control | Notes |
|---|---|---|
| Moneyness | multi-select chips `ATM / ITM1 / ITM2 / OTM1 / OTM2 / ALL` | shared with A05 |
| Lots | segmented `1 · 2 · 5 · 10 · 25 · 50` + a free numeric input | the current UI offers only the six presets; a numeric input costs nothing and 3 lots is a normal size |

Add a derived read-out under the control: `5 lots ≈ 375 contracts (NIFTY, 75/lot)`.
Only render it when the lot size for the instrument is actually known — otherwise omit
the line. Do not guess 75.

### 2.4 Execution model — rebuild honestly (D1)

The current section (`SimulationBar.tsx:1033–1071`) claims a spread model of
"0.5% index, 1.5% stock" and a Realistic/Ideal toggle. **None of it exists in the
backend.** Two permitted versions:

**Version A — after `23_A14` §2 lands (preferred).** Render the toggle plus the actual
parameters the backend accepts, and echo the values the backend confirms:

```
EXECUTION MODEL
 ( ) Ideal        fills at the exact signal price
 (•) Realistic    buy at ask, sell at bid, plus slippage
     Index spread   [ 0.50 ] %      Stock spread [ 1.50 ] %
     Slippage       [ 0.25 ] %      applied on both legs
     ⓘ These values are sent to the replay engine and echoed back in
       `config.friction`. If the echo differs, the engine's values win.
```

The echo requirement is not decoration — it is the check that catches the next D1.

**Version B — if §2 is deferred.** Render the section as **disabled with an explicit
reason**:

```
EXECUTION MODEL                                    NOT AVAILABLE
Replay fills at the exact signal price. Spread and slippage
modelling is not implemented in the replay engine yet.
```

Do **not** render an enabled toggle that changes nothing. That is the defect, not the
styling of it.

### 2.5 Advanced (collapsed)

New section, all optional, each field hidden unless the backend advertises support (see
`23_A14` §6 `capabilities`):

- Bar resolution (`1m` / `5m` / `15m`) — `SimConfig.resolution` exists and is hardcoded
  to `'5m'` by the frontend (`useSimulation.ts:381`). Expose it.
- Instruments (`SimConfig.instruments`, currently always `[]` = all watchlist). A
  multi-select would let a user replay one symbol.
- Auto-open summary on completion (client-side preference).
- Clear results on start (mirrors the existing `clearLocalFeedCache` behaviour, made
  visible).

## 3. Validation

Validate on change, show inline, and gate `Start`:

| Rule | Message |
|---|---|
| `end_date < date` | `End date is before the start date.` |
| `end_time <= start_time` | `End time must be after the start time.` |
| date not in `availableDates` (store-backed) | `No stored candles for this date.` (warn) |
| no strategy selected | cannot happen — the store falls back to `all` |
| lots < 1 or > 500 | `Lots must be between 1 and 500.` |

Errors render under the field in `--k-red`, with `aria-describedby` linkage and
`aria-invalid` on the input.

## 4. Footer

Sticky at the bottom of the sheet:

```
[ Reset to defaults ]                    [ Cancel ]  [ Apply & start ▸ ]
```

`Apply & start` closes the sheet, applies, and calls `transport.start()`. This is the
flow the dock is missing: today you configure in a tab, then hunt for the play button in
a scrolling toolbar.

`Reset to defaults` restores the store's initial values (`useSimulation.ts` initialiser),
including `date = getLastMarketWorkingDay()`.

## 5. Acceptance criteria

- [ ] Config is a sheet, not a tab; `Configure` is disabled while `state !== 'idle'`.
- [ ] No enabled control changes a value the backend ignores.
- [ ] The execution-model section is either fully wired (Version A, with echo) or
      explicitly disabled with a reason (Version B).
- [ ] `resolution` is exposed and reaches `SimConfig`.
- [ ] Validation messages are linked by `aria-describedby`; `Apply` is gated.
- [ ] Escape closes and returns focus to the trigger.
- [ ] Accordion animates with M15/M16 and is inert under reduced motion.

## 6. Tests

1. `Configure` disabled while running; enabled when idle
2. Version B renders the section disabled and the reason text
3. `end_time <= start_time` blocks `Apply` and shows the message
4. `Apply & start` applies the config **then** calls start (assert order)
5. `Reset to defaults` restores `date` to `getLastMarketWorkingDay()`
6. `resolution` selection reaches the `/start` body
