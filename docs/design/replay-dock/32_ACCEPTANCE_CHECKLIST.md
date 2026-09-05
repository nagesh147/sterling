# 32 — Acceptance checklist

One list. The redesign is done when every box is ticked with evidence, not intent.

---

## Honesty — the defects that mislead

- [ ] **D1** Friction is either implemented end-to-end (backend computes it, the trades
      table shows it, the metric strip totals it) **or** every trace of it is deleted
      from both sides. No enabled control changes a value the backend ignores.
- [ ] Unmeasured metrics render `—` with an explanatory `title`. No `?? 0` anywhere.
- [ ] **D2** `contract`/`spot` are emitted by the backend and rendered, **or** the
      frontend branch and type fields are deleted.
- [ ] **D14** `/available-dates` is consumed, and its `source` distinguishes real stored
      dates from the synthetic fallback.
- [ ] **D18** Every failed transport command produces a visible error. None is only
      `console.error`ed.
- [ ] **D15** `bars_played`, `bars_total`, `elapsed_real_s` and `status_message` are all
      surfaced somewhere.
- [ ] `SimStatus.capabilities` exists and the UI branches on it, not on sampled values.

## Correctness

- [ ] **D3** The summary modal is a real modal: portalled, scrimmed, centred, focus
      trapped, escapable, above the fullscreen dock.
- [ ] **D4** Toasts render above the fullscreen dock.
- [ ] **D13** One speed ladder shared by the pills and the keyboard; `+` never lands on
      an unrepresented speed.
- [ ] **D16** Exactly one CSV implementation, RFC-4180 escaped, its columns generated
      from the same array that drives the table.
- [ ] **D19** Toast identity is stable; the effect does not re-run per status frame.
- [ ] **D20** Mode, height, tab and open-state persist under one versioned key; the old
      height key is migrated; `fullscreen` is not persisted.
- [ ] Win rate divides by `wins + losses`, not `trades_entered`.
- [ ] Strategy breakdown keys case-insensitively; no duplicate rows.

## Structure

- [ ] **D6** `SimulationBar.tsx` and `SimulationBar.css` are deleted. No file in
      `replay/` exceeds ~300 lines.
- [ ] **D7** No dead CSS: every class in `replay.css` is used; `.rd-speed-pill` (or any
      class) is defined once.
- [ ] **D17** `KiteLayout` subscribes to one boolean (`hostContentHidden`) and does not
      know the dock's mode vocabulary. `FOOTER_H` is one shared constant.
- [ ] `useSimulation.ts` is deleted; `useEffectiveNowMs` / `getSimNowMs` keep their
      signatures.
- [ ] Exactly one replay surface in the footer.

## Design

- [ ] **D8** No hex literal in any `replay/` file
      (`grep -n "#[0-9a-fA-F]\{3,6\}"` is empty). Filled accents use `--k-on-accent`.
- [ ] **D9** Only the five type-ramp sizes are used.
- [ ] **D10** No emoji in dock chrome; all icons are SVG inheriting `currentColor`.
- [ ] Both themes verified visually in all four modes.
- [ ] Every numeric column is mono + `tabular-nums`; no horizontal jitter as digits change.
- [ ] Density held: chrome rows 30–44 px, table rows 28 px.
- [ ] Replay identity (cyan rule + `REPLAY ▸` pill + footer chip) is present whenever
      `state !== 'idle'`.

## Motion

- [ ] Every animation is in the M1–M22 table; nothing else animates.
- [ ] Only `transform` and `opacity` animate during playback.
- [ ] `transition: all` appears nowhere.
- [ ] `prefers-reduced-motion` is honoured; the playhead and progress fill still move.
- [ ] Metric flash suppressed at `speed >= 100`.
- [ ] At most three elements animate simultaneously in steady-state playback.

## Interaction

- [ ] **The timeline is scrubbable** by pointer and keyboard, and a drag issues exactly
      one seek request.
- [ ] Timeline dots cluster and cross-link to table rows in both directions.
- [ ] Auto-scroll pins only when the user is already at the newest end; otherwise a
      `↑ n new` affordance appears.
- [ ] **D12** Shortcuts fire only when the dock owns focus, plus the single documented
      global toggle. Space in another pane's input does nothing to the replay.
- [ ] `?` opens a shortcut sheet; every control's `title` names its shortcut.
- [ ] `Apply & start` exists in the config sheet.
- [ ] Market-hours quick ranges (full / regular / first hour / last hour) work.

## Accessibility

- [ ] **D11** Tabs have `role="tabpanel"` + `aria-controls` + `id` linkage; the inactive
      panel is unmounted, not `display:none`.
- [ ] The resizer is a keyboard-operable `role="separator"` with `aria-valuenow`.
- [ ] The timeline is a `role="slider"` with `aria-valuetext`.
- [ ] Every icon-only control has an `aria-label` naming its shortcut.
- [ ] Popovers: `aria-expanded`, focus trap, Escape, focus return, arrow-key navigation.
- [ ] One `aria-live="polite"` region, throttled to ≤ 1 message per 2 s, never
      announcing progress.
- [ ] Colour is never the only channel for direction or win/loss.
- [ ] All six manual a11y checks in `31_VERIFICATION.md` §5 completed and reported.

## Performance

- [ ] **D5** Polling replaced by SSE with a fixed fallback; polling stops when idle and
      when the tab is hidden.
- [ ] No component subscribes to the whole `status` object.
- [ ] `stats.events` / `stats.trades` keep referential identity across frames that add
      nothing.
- [ ] Measured: ≤ 3 components re-render per status frame; the tables are not among them.
- [ ] Measured: tables commit in < 4 ms at 400 rows.
- [ ] Measured: 0 dropped frames at 50× with 300+ signals.
- [ ] Before/after numbers are in the PR.

## Verification

- [ ] `npx tsc --noEmit` clean.
- [ ] Frontend suite run **twice**; failing set compared, not counts.
- [ ] Backend suite run with `PYTHONWARNINGS=ignore` and the socket test deselected;
      regression gate clean against the merge base.
- [ ] Screenshot matrix from `31_VERIFICATION.md` §6 attached.
- [ ] All 11 tests from `__tests__/SimulationBar.test.tsx` ported, not deleted.
