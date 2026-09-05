# 31 — Verification

Evidence before assertions. Every phase ends by running its block here and pasting the
real output into the PR. "It should work" is not a result.

---

## 1. Frontend

```bash
cd frontend && npx tsc --noEmit
```

```bash
cd frontend && npx vitest run src/components/kite/replay src/hooks/__tests__
```

Full suite:

```bash
cd frontend && npx vitest run
```

> **Run the full frontend suite twice before blaming your branch.**
> `SterlingKiteEnginePane.*` is intermittently flaky on `main`, and adding any new test
> file perturbs vitest's scheduling, which makes it more likely. Compare the **failing
> set**, not the count. A branch that adds ten test files will look like it broke the
> suite if you compare counts from a single control run.

---

## 2. Backend

```bash
cd backend && PYTHONWARNINGS=ignore .venv/bin/pytest tests/api/test_simulation.py -q -p no:cacheprovider
```

Full suite (the default invocation is a trap — it captures millions of deprecation
warnings and can hang):

```bash
cd backend && PYTHONWARNINGS=ignore .venv/bin/pytest tests/ -q \
  --deselect "tests/test_delta_iv_socket.py::test_lifespan_starts_iv_stream_only_when_env_set" \
  -p no:cacheprovider
```

Import health:

```bash
cd backend && .venv/bin/python -c "import main; print(len(main.app.routes))"
```

Regression gate (diffs the failing **set** against the merge base — the only reliable
signal, since ~36–64 tests fail on a clean tree):

```bash
bash backend/scripts/regression_gate.sh main
```

Never edit tracked files while a suite run is in flight, and never `pkill -f pytest` —
the pattern matches your own run.

---

## 3. Per-phase blocks

### Phase 0 — backend

```bash
grep -rn "friction_mode" backend/app/services/simulation.py     # implemented, or gone
grep -n "contract\|spot" backend/app/services/simulation.py | head
cd backend && PYTHONWARNINGS=ignore .venv/bin/pytest tests/api/test_simulation.py -q
```

Manual: `curl -s localhost:8000/api/v1/simulation/status | jq .capabilities`

### Phase 1 — summary modal

```bash
grep -rn "sim-summary" frontend/src            # must be empty
grep -rn "exportTradesToCSV\|exportSignalsToCSV" frontend/src   # exactly one definition
cd frontend && npx vitest run src/components/kite/replay/__tests__/ReplaySummaryModal.test.tsx
```

Visual: finish a replay with ≥ 1 signal, in **fullscreen** dock mode. The modal must be
centred over the dock, not behind it and not in the page flow.

### Phase 2 — store

```bash
cd frontend && npx vitest run src/hooks/__tests__
cd frontend && npx tsc --noEmit
```

Manual: open the dock, start a replay, switch browser tabs for 30 s, come back. The
network panel must show **no** `/status` requests while hidden.

### Phase 3 — shell

```bash
grep -n "#[0-9a-fA-F]\{3,6\}" frontend/src/components/kite/replay/*.tsx   # must be empty
cd frontend && npx vitest run src/components/kite/replay/__tests__/ReplayDock.test.tsx
```

Manual, both themes: all four modes; keyboard-resize the dock; confirm the border and
shadow are visible in dark mode.

### Phase 4 — the deck

```bash
grep -rn "5000" frontend/src/components/kite/replay | grep -v replaySpeeds.ts   # must be empty
cd frontend && npx vitest run src/components/kite/replay
```

Manual:
- Press `+` six times from 1×. Every intermediate speed must highlight a pill.
- Drag the timeline across the whole session. The network panel must show **one** seek
  request, not one per pointermove.
- Click a timeline dot. The matching signals row must scroll into view and flash.
- With no friction data, the trades table must have **no** Slippage column and the
  metric strip must read `—`, not `₹0.00`.

### Phase 5 — removal

```bash
grep -rn "SimulationBar\|SimulationSummary\|useSimulation\|sim-dock\|sim-toolbar" frontend/src   # must be empty
cd frontend && npx tsc --noEmit && npx vitest run
```

### Phase 6 — streaming

```bash
curl -N localhost:8000/api/v1/simulation/stream | head -20
cd backend && PYTHONWARNINGS=ignore .venv/bin/pytest tests/api/test_simulation.py -q -k stream
```

Manual: start a replay at MAX speed and watch the network panel. One open EventSource,
no repeated `/status` requests.

---

## 4. Performance measurement

This is a required artifact of Phases 4 and 6, not an optional nicety.

1. Start a replay that produces **≥ 300 signals** (a full session at `all` strategies).
2. React DevTools Profiler → record 10 s at speed 50×.
3. Record, and paste into the PR:
   - components re-rendering per status frame (target: ≤ 3, and **not** the tables)
   - the tables' commit duration at 400 rows (target: < 4 ms)
   - dropped frames in the Performance panel (target: 0 at 50×)

Baseline for comparison, measured the same way on the current dock, so the improvement
is a number rather than a claim.

---

## 5. Accessibility

Cannot be automated away. Do all six:

1. **Keyboard only, no mouse:** open the dock, configure a session, start it, scrub the
   timeline, switch tabs, export a CSV, open and close the summary. Every step must be
   reachable and every focused element must be visibly focused.
2. **Screen reader** (NVDA or VoiceOver): confirm the live region announces new signals
   at most once per 2 s and never announces progress. Run it at 50× — if it is
   unusable, the throttle is wrong.
3. **Contrast:** sample every text/background pair in both themes; all ≥ 4.5:1.
4. **`prefers-reduced-motion: reduce`** (DevTools → Rendering → Emulate CSS media):
   nothing animates except the playhead and progress fill, which still move.
5. **200 % browser zoom:** no horizontal page scroll; the dock's own tables may scroll
   inside their container.
6. **Focus return:** each popover, sheet and modal returns focus to the control that
   opened it.

---

## 6. Visual verification

Take screenshots and attach them. Minimum matrix:

| | light | dark |
|---|---|---|
| docked, idle | ☐ | ☐ |
| docked, running with data | ☐ | ☐ |
| overlay, running | ☐ | ☐ |
| fullscreen + toast + summary | ☐ | ☐ |
| config sheet open | ☐ | ☐ |
| narrow (`data-width="sm"`) | ☐ | ☐ |

The fullscreen + toast + summary cell is the one that proves D4 is fixed — both
overlays must be visible above the dock.

---

## 7. What "done" is not

- A green test run alone. The suite was green while the friction toggle did nothing and
  the summary modal had no CSS. Tests assert what someone thought to assert.
- A screenshot of the happy path. Photograph the empty, loading and error states too.
- "No console errors." The current dock logs a start failure to the console and shows
  the user nothing; that is the defect, not the evidence of health.
