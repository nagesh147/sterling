# 01 — Ground Truth: what the Replay Dock actually is today

Everything here was read out of the source on `main @ 7ff055e1e`. Line numbers are from
that commit. Where a claim is about absence ("nothing defines this"), the search that
established it is given so it can be re-run.

---

## 1. Artifact inventory

| Artifact | Path | Lines | Role |
|---|---|---|---|
| Dock component | `frontend/src/components/kite/SimulationBar.tsx` | 1231 | The entire dock: shell, toolbar, transport, timeline, 4 tabs, 2 tables, config pane, toast, footer chip, CSV export. |
| Dock stylesheet | `frontend/src/components/kite/SimulationBar.css` | 1147 | All dock styling. |
| Store + API client | `frontend/src/hooks/useSimulation.ts` | 531 | Zustand store, session-date maths, REST client, 150 ms poller. |
| Summary modal | `frontend/src/components/kite/SimulationSummary.tsx` | 321 | End-of-session modal, its own duplicated CSV exporters. |
| Footer status chip | `frontend/src/components/kite/KiteFooterStatus.tsx` | 144 | Renders a `▶ SIMULATION` chip when active. |
| Workspace mount | `frontend/src/components/kite/KiteLayout.tsx` | 827 | Mounts the dock twice (`:316` classic, `:700` Mac stage), the summary at `:738`, footer chip + badge at `:756–757`. |
| Design tokens | `frontend/src/styles/kiteUI.tsx` / `theme.ts` | 194 / ~190 | `k.*` → `var(--k-*)`; 3-column light/dark token table. |
| Component tests | `frontend/src/components/kite/__tests__/SimulationBar.test.tsx` | 445 | 11 tests. |
| Store tests | `frontend/src/hooks/__tests__/useSimulation.test.ts` | — | 4 tests. |
| Backend service | `backend/app/services/simulation.py` | 1261 | `SimulationRunner` singleton + Pydantic models. |
| Backend endpoints | `backend/app/api/v1/endpoints/simulation.py` | 109 | 7 routes under `/api/v1/simulation`. |
| Backend tests | `backend/tests/api/test_simulation.py` | — | API-level tests. |

`SimulationBar.tsx` is a **1231-line single file** that renders eleven distinct UI
concerns. This is the root structural problem; everything below is downstream of it.

---

## 2. Verified defects

These are ordered by whether they mislead the user, then by severity.

### D1 — The friction / slippage system is entirely fictional  ▲ misleads

`SimConfig.friction_mode` is declared at `backend/app/services/simulation.py:37` and
**read nowhere**:

```
grep -rn "friction_mode" backend/ --include='*.py' | grep -v test
→ backend/app/services/simulation.py:37   (the declaration only)
```

Nothing in the runner computes slippage, and `SimTradeEvent`
(`simulation.py:52–72`) declares no `slippage`, no `raw_entry`, no `raw_exit`.

The frontend nevertheless ships all of this:

- `SimulationBar.tsx:1033–1071` — an "Execution Friction & Realism (Advanced)" config
  section with a Realistic/Ideal toggle and prose describing spread of "0.5% index,
  1.5% stock". None of that exists in the backend.
- `SimulationBar.tsx:181–187` — a **SLIPPAGE DRAG** KPI card.
- `SimulationBar.tsx:486–494` — a **Slippage** column in the trades table (its `else` branch hardcodes `₹0.00`).
- `SimulationBar.tsx:466–482` — `raw ₹` sub-lines under entry and exit.
- `useSimulation.ts:37–39` — `slippage?`, `raw_entry?`, `raw_exit?` on the TS type.

Because the routes declare `response_model=SimStatus`, FastAPI strips undeclared keys,
so these fields could not arrive even if the runner produced them. **Net effect:
SLIPPAGE DRAG always prints `₹0.00`, and the toggle changes nothing.** A user reading
that strip concludes their strategy has no execution cost.

### D2 — The contract / spot chip is dead  ▲ misleads

`useSimulation.ts:15–16` declares `contract?: string; spot?: number` on
`SimSignalEvent`, and `SimulationBar.tsx:403–412` renders a contract name plus a
`Spot ₹…` badge when present. The backend `SimSignalEvent`
(`simulation.py:40–49`) has neither field, and the construction site
(`simulation.py:983–993`) sets neither. The chip never renders; the table silently
falls back to `ev.instrument`. Dead branch, and the reason the signals table shows an
index name where a trader expects an option contract.

### D3 — The summary modal has no stylesheet  ▲ visible breakage

`SimulationSummary.tsx:22–23` uses `.sim-summary-overlay` and `.sim-summary-card`.

```
grep -rn "sim-summary" frontend/ --exclude-dir=node_modules
→ only the two TSX references. Zero CSS definitions.
```

So neither class is a modal. The component is mounted at `KiteLayout.tsx:738`, inside
the workspace's flex column, immediately above the `<footer>`. When a replay finishes
with at least one signal (`useSimulation.ts:497–501`), it renders as an **unstyled
block that pushes the layout around** — no overlay, no centring, no scrim, no
elevation, no focus trap, no Escape handling.

### D4 — The signal toast is invisible in fullscreen mode

`.sim-toast-popup` is `position: fixed; z-index: 1000` (`SimulationBar.css` — the `.sim-toast-popup` rule).
The fullscreen dock renders through a body portal at `z-index: 12000`
(`SimulationBar.tsx:1091`). The toast is rendered as a *sibling of* that portal
(`:1119` in fullscreen, `:1186` otherwise) at 1000, so in fullscreen mode it is painted underneath the dock. It is
the mode in which a trader is most likely to be watching for signals.

### D5 — 150 ms full-payload polling

`useSimulation.ts:481–507`: `setInterval` at **150 ms**, each tick `GET /status`,
each response containing the **entire** `stats.events` and `stats.trades` arrays and
replacing the whole store object. Consequences, all real:

- Bandwidth and JSON parse cost grow linearly with session length. A day of replay
  producing 400 signals means re-parsing 400 objects ~6.7×/second.
- Every tick writes a new `status` object into Zustand, so **every** subscriber
  re-renders — including both tables in split view, at 6.7 Hz, unmemoised.
- The poller is a module-level singleton (`let pollInterval`) with no visibility gate,
  so it keeps running when the dock is closed and when the tab is hidden.
- `syncStatus` (`:497`) can start a second poller; `startPolling` calls `stopPolling`
  first, which saves it, but the ownership is implicit and fragile.

### D6 — `SimulationBar.tsx` is one 1231-line component

Eleven concerns in one file, one `useState` cluster, and two large `render*` closures
(`renderSignalsTable`, `renderTradesTable`) recreated on every render. No `React.memo`
anywhere. Combined with D5 this is the performance story in full.

### D7 — Dead and duplicated CSS

14 classes are defined in `SimulationBar.css` and used nowhere in the TSX:

`sim-win-btn`, `sim-btn-config`, `sim-input`, `sim-tab-strip`, `sim-tab-btn`,
`sim-close-btn`, `sim-tab-content`, `sim-config-grid`, `sim-config-header`,
`sim-stats-cells`, `sim-stat-cell`, `sim-date-range-inputs`, `sim-input-label`,
`sim-input-sep`, `sim-tab-split-wrapper`, `sim-toolbar-left`, `sim-tab-actions`.

`.sim-speed-pill` is defined **twice** with conflicting values — once at
`SimulationBar.css:309` (transparent, blue active) and again at `:907` (bordered,
orange active). The second wins; the first is ~30 lines of misleading dead code.

### D8 — Hardcoded hex defeats the dark theme

- `SimulationBar.tsx:23` — `color: '#c2c2c2'` on the drag dots.
- `SimulationBar.tsx:1093` — `background: '#efefef'` on the fullscreen backdrop.
- `SimulationBar.tsx:1101` / `:1104` — `border: '1px solid #e4e4e4'`,
  `boxShadow: 'rgba(0,0,0,.09)'`.
- `SimulationBar.css:939` / `:944` — `color: #ffffff` on active pills, which is correct
  *only* in light mode; dark mode needs `var(--k-on-accent)` (that token exists
  precisely for this, and inverts — see `theme.ts` comment at the `on-accent` entry).

### D9 — Eleven font sizes, no ramp

`8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 14, 16` px all appear. Six of them
differ by 0.5 px, which is below the perceptual threshold at these sizes and simply
reads as misalignment. There is no scale; each value was chosen locally.

### D10 — Emoji as iconography

`🎯 📈 ⚡ 📉 ⚖️ 🧭 🔔 🔀 💼 ⚙ 📥 📅 ✨ 🟢 🔴 ⏮ ◀◀ ⏵ ⏸ ▶▶ ⏭ ⏹` are used as UI icons
throughout. They do not inherit `currentColor`, do not respond to the theme, render
with platform-specific metrics that break the tabular alignment the tables depend on,
and are announced verbatim by screen readers ("chart increasing button").

### D11 — Accessibility gaps

- The four dock tabs have `role="tab"` / `aria-selected` (`:665–701`) but there is no
  `role="tabpanel"`, no `aria-controls`, no `id` linkage, and the panels are toggled
  with `display:none` rather than `hidden` (the four `display: activeDockTab === … ? … : 'none'` panels).
- The resizer (the `.sim-dock-resizer` div; handler at `:316`) is a bare `div` with a mouse handler: no `role="separator"`,
  no `tabIndex`, no `aria-valuenow`, no keyboard resize. `KiteLayout.tsx:726–732`
  already does this correctly for workspace resizers — the pattern exists and was not
  reused.
- The transport buttons carry `title` but no `aria-label`; a `title` alone is not a
  reliable accessible name.
- Dropdowns (the two `sim-dropdown-container` blocks) are `div`s with click-outside handling: no
  `aria-expanded`, no `role="menu"`, no Escape-to-close, no focus return, no arrow-key
  navigation.
- The progress bar (`.sim-progress-fill`) has no `role="progressbar"` / `aria-valuenow`.
- Live signal arrival is not announced — no `aria-live` region anywhere.

### D12 — Keyboard handling is global and unscoped

`SimulationBar.tsx:270–313` binds `keydown` on `window` whenever `barOpen` is true. It
guards only against `HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement`. So
Space, arrows, Home/End and `+`/`-` are captured **anywhere in the app** while the dock
is merely *open* — including inside `contenteditable`, inside other panes' custom
widgets, and while a different pane has focus. `Home`/`End` are also stolen from every
scrollable region in the workspace.

### D13 — Speed control is inconsistent between surfaces

Keyboard `+`/`-` step through `[1, 5, 10, 50, 100, 250, 500, 1000, 5000]`
(the two `speeds` arrays inside `handleKeyDown`), but the toolbar renders only `[1, 5, 10, 50, 100, 5000]`
(the `sim-speed-group` map in the toolbar). Pressing `+` can therefore land on `250` — a speed with no button, which
leaves every pill unhighlighted and looks like a broken control.

### D14 — `/available-dates` is dead backend surface

`simulation.py:73–108` builds a 90-day list of valid session dates (including a
synthetic fallback). Nothing in the frontend calls it:

```
grep -rn "available-dates" frontend/src   → no matches
```

Meanwhile the date inputs are free `<input type="date">` (the two `<input type="date">` in the config pane), so a user
can pick a Sunday, or a date with no stored candles, and only find out by pressing
play. The data to prevent that already exists and is unused.

### D15 — Backend `SimStatus` fields the UI never surfaces

`bars_played`, `bars_total`, `elapsed_real_s`, `status_message` are all populated
(`simulation.py:85–95`) and never rendered. `status_message` in particular is the
only channel the backend has for telling the user why a replay produced nothing.

### D16 — Duplicated CSV exporters

`SimulationBar.tsx:65–125` and `SimulationSummary.tsx:110–161` each define
`exportSignalsToCSV` / `exportTradesToCSV`. They have **diverged**: the dock's trade
export has 20 columns including the (never-populated) slippage and raw columns; the
summary's has 17. Neither escapes commas or quotes in field values, so a strategy name
or symbol containing a comma corrupts the file.

### D17 — Layout coupling via a boolean

`KiteLayout.tsx:297` computes `isSimFullHeight` and uses it at `:306` and `:311` to
hide the workspace content and the top bar. The dock's `viewMode` therefore reaches
into and rewrites its host's layout. Five modes exist (`half`, `full`, `fullheight`,
`maximized`, `fullscreen`), the shell bar labels them with five different words
("Dashboard dock", "Bottom dock", "Full height", "Maximized", "Full screen"), and
three of them look nearly identical to a user.

### D18 — Start-failure handling is a blind retry

`useSimulation.ts:396–414`: on any `/start` failure it POSTs `/stop` and retries once,
then `console.error`s. The user sees **nothing**. A replay that fails to start is
indistinguishable from one the user forgot to start.

### D19 — Toast effect keys on object identity

`SimulationBar.tsx:261–268` depends on
`[sim.status.last_signal?.time_iso, …instrument, …strategy]`. Two signals from the same
strategy on the same instrument in the same second are one toast. More importantly,
because the poller replaces `status` wholesale every 150 ms, this effect re-evaluates
6.7×/s for the life of the session.

### D20 — `viewMode` and dock height persist inconsistently

`dockHeight` persists to `localStorage` under `sterling:replay-dock:height`
(`:19`, `:221`, `:327` in `SimulationBar.tsx`). `viewMode`, `activeDockTab` and `barOpen` do not persist at
all — they reset to `half` / `split` / `false` on reload (the `useSimulationStore` initialiser).
So the dock reopens at the remembered *height* but the wrong *mode*.

---

## 3. What is genuinely good and must be preserved

Do not regress these while rebuilding.

1. **`getDynamicMarketPresets()`** (`useSimulation.ts:162–216`) — presets are filtered
   against real NSE holidays and the 09:00 IST open, so "Today" never appears on a
   Sunday. This logic is correct and well-commented. Keep it verbatim; only its
   *presentation* changes.
2. **IST date maths via `Intl.DateTimeFormat`** (`useSimulation.ts:70–96`) rather than local-time
   arithmetic. Correct, and matches the timezone pinning the rest of the suite relies on.
3. **The `k` token indirection** — components already read `var(--k-*)` in most places.
4. **`useEffectiveNowMs()`** (`useSimulation.ts:526–531`) — lets the rest of the app treat replay time
   as "now". This is the dock's most valuable export and the redesign must not break
   its signature.
5. **The `sterling-simulation-start` CustomEvent** (`useSimulation.ts:390`, dispatched on start) and the
   session-storage feed-cache clear (`clearLocalFeedCache`, `useSimulation.ts:365–371`). Other panes depend on these.
6. **`kw-pane` / `kw-pane-control` / `kw-dock-chip`** — the dock already borrows the
   workspace's own chrome classes (`WORKSPACE_CSS` in `KiteLayout.tsx`, lines 88–101). Keep that borrowing; it is
   why the dock looks like it belongs.
7. **The five-mode ambition.** Traders do want a bottom strip *and* a full-screen study
   view. The modes are over-enumerated (D17), not wrong.

---

## 4. Re-running these checks

```bash
# D1
grep -rn "friction_mode\|slippage\|raw_entry\|raw_exit" backend/app/services/simulation.py
# D2
sed -n '40,50p' backend/app/services/simulation.py
# D3
grep -rn "sim-summary" frontend/ --exclude-dir=node_modules
# D7
grep -n "^\.sim-speed-pill {" frontend/src/components/kite/SimulationBar.css
# D14
grep -rn "available-dates" frontend/src
```
