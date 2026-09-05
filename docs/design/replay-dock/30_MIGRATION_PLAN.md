# 30 — Migration plan

Seven phases. Each is a separate commit (or PR) that leaves the app working. **Nothing
here is a big-bang rewrite** — the old `SimulationBar` keeps rendering until Phase 5
removes it.

---

## Phase 0 — Backend honesty  *(prerequisite for 4 and 6)*

**Doc:** `23_A14_backend_contract.md`

1. Decide friction: implement (§2.1) or remove (§2.2). **Write the decision in the PR.**
2. Add `SimStatus.capabilities` (§6).
3. Add `contract`/`spot`/`strike`/`opt_type` to `SimSignalEvent` (§3), or record that
   the frontend branch will be deleted instead.
4. Add `bar_index` / `to_pct` / `to_time` to `/seek` (§4).
5. `/available-dates`: add `source`, `resolution`, `earliest`, `latest` (§5).
6. Populate `status_message` for the empty-session case (§7 B3).
7. `/start` while running → `409 {"code": "already_running"}` (§7 B2).
8. Decide and enforce multi-day behaviour (§7 B5).

Ship without the streaming endpoint if you like — it is Phase 6.

**Done when:** `backend/tests/api/test_simulation.py` covers §9.1–11 minus the stream
tests, and the regression gate is clean.

---

## Phase 1 — Fix the summary modal  *(smallest, highest-visibility fix)*

**Doc:** `19_A10_summary_modal.md`

`.sim-summary-overlay` / `.sim-summary-card` are undefined (D3), so the end-of-replay
summary currently renders as an unstyled block in the workspace column. Fix it first,
standalone, before any restructuring.

1. Create `frontend/src/components/kite/replay/` and `replay.css` with the token block
   from `02_DESIGN_SYSTEM.md` §6.1 and §7.
2. Build `ReplaySummaryModal` per A10; body-portal at `--rd-z-modal`.
3. Create `replayCsv.ts` with the single RFC-4180-escaping exporter; point both the
   modal and the existing `SimulationBar` at it; delete the four duplicated functions.
4. Swap `<SimulationSummary/>` for `<ReplaySummaryModal/>` at `KiteLayout.tsx:738`.
5. Delete `SimulationSummary.tsx`.

**Done when:** the modal is centred, scrimmed, focus-trapped, escapable, and renders
above a fullscreen dock. `grep -rn "sim-summary" frontend/src` is empty.

---

## Phase 2 — Extract the store  *(no visual change)*

**Doc:** `22_A13_store_and_stream.md`

1. Move the session-date functions to `frontend/src/lib/replay/marketSessions.ts`
   **verbatim**; strip emoji from the preset labels only.
2. Create `useReplayStore.ts` with the shape in A13 §2 and the named selectors in §3.
3. Create `useReplayTransport.ts` and `useReplayStream.ts` (polling only for now, with
   the visibility/idle/interval fixes from §4.2).
4. Make `useSimulation.ts` a thin re-export shim so `SimulationBar`, `KiteFooterStatus`
   and every `useEffectiveNowMs` consumer keep working untouched.
5. Add the versioned prefs key with migration from `sterling:replay-dock:height`.

**Done when:** all existing tests pass against the shim; the poller stops when idle and
when the tab is hidden; `useEffectiveNowMs` behaviour is unchanged.

---

## Phase 3 — Primitives and the shell

**Docs:** `10_A01`, `11_A02`, `02_DESIGN_SYSTEM.md`

1. `ReplayIcons.tsx` — the full SVG set.
2. `primitives/` — `Segmented`, `Pill`, `StatChip`, `EmptyState`, `Skeleton`,
   `Sparkline`, `ReplayPopover`, `ReplaySheet`.
3. `replayFormat.ts`.
4. `ReplayDock.tsx` + `ReplayShellBar.tsx`, rendering the **old** body via a temporary
   `<LegacySimulationBody/>` extracted from `SimulationBar`. Mount `ReplayDock` behind a
   flag.

**Flag:** `localStorage['sterling:replay-dock:v2'] === '1'`, read once at module load.
`KiteLayout` renders `<ReplayDock/>` or `<SimulationBar/>` accordingly. Keep the flag
until Phase 5.

**Done when:** with the flag on, the dock opens in all four modes, resizes by keyboard,
persists prefs, and the legacy body renders inside it.

---

## Phase 4 — The deck: rail, timeline, metrics, tables

**Docs:** `12_A03`, `13_A04`, `14_A05`, `15_A06`, `16_A07`, `17_A08`, `18_A09`

Order within the phase (each is independently reviewable):

1. `ReplayTransport` + `replaySpeeds.ts` — the shared ladder (D13).
2. `ReplayMetricsStrip` — including the `—` rule for unmeasured metrics (D1).
3. `ReplaySignalsTable`, then `ReplayTradesTable` — memoised, virtualised, one CSV path.
4. `ReplayTimeline` — the scrubber. Do this **after** the tables so the dot↔row
   cross-link has something to link to.
5. `ReplaySessionPicker` + `ReplayFilters` on the shared popover primitive; wire
   `/available-dates`.
6. `ReplayConfigSheet` — Version A or B per the Phase 0 decision.
7. `ReplayToastHost` — replaces both inline toasts; adds the live region and error toasts.
8. Delete `<LegacySimulationBody/>`.

**Done when:** with the flag on, nothing from `SimulationBar.tsx` renders.

---

## Phase 5 — Remove the old surface

1. Delete `SimulationBar.tsx` and `SimulationBar.css`.
2. `ReplayFooterChip` replaces `SimulationFooterButton` + `SimulationFooterBadge`;
   remove the `simActive` branch from `KiteFooterStatus.tsx` (A12).
3. `KiteLayout`: subscribe to `hostContentHidden` instead of deriving
   `isSimFullHeight` from the dock's mode vocabulary (D17); move `FOOTER_H` into
   `layoutConstants.ts`.
4. Delete `useSimulation.ts`; update every import (search for `useSimulation`,
   `useSimActive`, `useSimBarOpen`, `useEffectiveNowMs`, `getSimNowMs`).
5. Remove the v2 flag.
6. Port the 11 tests in `__tests__/SimulationBar.test.tsx` to the new component tests —
   **port, do not delete**; each one encodes a behaviour someone wanted.

**Done when:** `grep -rn "SimulationBar\|sim-dock\|sim-toolbar" frontend/src` is empty
and the full frontend suite is green (run it twice — see `31_VERIFICATION.md` §4).

---

## Phase 6 — Streaming

**Doc:** `23_A14` §1

1. Backend `GET /simulation/stream` with the four event kinds and the frame throttle.
2. Delta `/status?since_events&since_trades`.
3. Client `useReplayStream` prefers SSE, falls back to delta polling, falls back to full
   polling.
4. Verify referential identity: a `frame` that adds no rows must not change
   `stats.events`' identity.

**Done when:** at 400 signals a frame causes ≤ 3 component re-renders and the tables are
not among them.

---

## Phase 7 — Polish

1. Row virtualisation above 200 rows.
2. Group-by in the trades table.
3. Shortcut sheet (`?`).
4. Equity-curve drawdown shading and crosshair.
5. Dead-CSS sweep: confirm none of the 17 classes in D7 survive.
6. A11y pass with a screen reader; fix whatever the live region actually sounds like at
   speed.

---

## File-level summary

**Created**

```
frontend/src/components/kite/replay/*            (18 files, per 02 §10)
frontend/src/lib/replay/marketSessions.ts
frontend/src/hooks/useReplayStore.ts
frontend/src/hooks/useReplayTransport.ts
frontend/src/hooks/useReplayStream.ts
frontend/src/components/kite/layoutConstants.ts
```

**Deleted**

```
frontend/src/components/kite/SimulationBar.tsx        (1231 lines)
frontend/src/components/kite/SimulationBar.css        (1147 lines)
frontend/src/components/kite/SimulationSummary.tsx    (321 lines)
frontend/src/hooks/useSimulation.ts                   (531 lines)
```

**Modified**

```
frontend/src/components/kite/KiteLayout.tsx           (mount + host coupling)
frontend/src/components/kite/KiteFooterStatus.tsx     (remove sim chip)
backend/app/services/simulation.py                    (friction, contract, capabilities, stream)
backend/app/api/v1/endpoints/simulation.py            (stream, seek, available-dates)
```

---

## Rollback

Phases 1, 2 and 6 are independently revertable. Phases 3–5 are gated by the v2 flag: if
something is wrong after Phase 4, set the flag off and the legacy dock returns. Do not
remove the flag until the new dock has run through a full trading session.
