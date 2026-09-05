# A13 — Store, transport, and streaming

**Files:**
`frontend/src/hooks/useReplayStore.ts`
`frontend/src/hooks/useReplayTransport.ts`
`frontend/src/hooks/useReplayStream.ts`
**Replaces:** `frontend/src/hooks/useSimulation.ts` (531 lines)
**Fixes:** D5 (150 ms full-payload polling), D18 (swallowed errors), D20 (persistence)

---

## 1. Split one hook into three

`useSimulation.ts` is a store, a date library, a REST client, and a poller. Split:

| Module | Owns |
|---|---|
| `lib/replay/marketSessions.ts` | `getIstDateParts`, `formatYmd`, `getLastMarketWorkingDay`, `getTodayMarketDate`, `getYesterdayMarketDate`, `getDynamicMarketPresets` — **moved verbatim**, emoji stripped from labels |
| `useReplayStore.ts` | Zustand state + setters only. No fetch. |
| `useReplayTransport.ts` | `start/stop/pause/resume/setSpeed/step/seek/jump`, error handling, toasts |
| `useReplayStream.ts` | the connection: SSE with a polling fallback, lifecycle-managed |

`useSimulation.ts` becomes a thin re-export shim for one release so nothing outside the
dock breaks, then is deleted. **`useEffectiveNowMs()` and `getSimNowMs()` must keep
their exact signatures and module path for the whole migration** — other panes depend on
them for replay-aware "now".

## 2. Store shape

```ts
type ReplayStore = {
  // ── UI (persisted under sterling:replay-dock:ui) ──
  open: boolean;
  mode: 'docked' | 'expanded' | 'overlay' | 'fullscreen';
  prevMode: 'docked' | 'expanded' | 'overlay';
  height: number;
  tab: 'split' | 'signals' | 'trades';
  configOpen: boolean;
  hostContentHidden: boolean;        // what KiteLayout subscribes to (fixes D17)

  // ── Session config (form state before start) ──
  draft: ReplayDraft;
  setDraft(patch: Partial<ReplayDraft>): void;
  resetDraft(): void;

  // ── Live status (from the backend) ──
  status: ReplayStatus;
  applyFrame(frame: ReplayFrame): void;    // see §4 — incremental, not wholesale

  // ── Error ──
  error: { code: string; message: string; at: number } | null;
  setError(e: ReplayStore['error']): void;

  // ── Derived, memoised in selectors, never stored ──
};
```

`ReplayDraft` holds `date, endDate, startTime, endTime, speed, resolution,
strategies, moneyness, lots, frictionMode, instruments`.

**Rule: nothing derived is stored.** Win rate, average trade, exposure, and the reversed
row arrays are all selectors. The current store stores `selectedStrategy` *and*
`selectedStrategies`, and `moneyness` *and* `selectedMoneyness`, keeping them in sync by
hand in every setter (`useSimulation.ts:298–349`). Keep only the arrays; derive the
scalar in the request builder.

## 3. Selectors — the performance contract

Export named selectors and forbid whole-object subscription:

```ts
export const useReplayState    = () => useReplayStore(s => s.status.state);
export const useReplayPct      = () => useReplayStore(s => s.status.progress_pct);
export const useReplayClock    = () => useReplayStore(s => s.status.current_time_iso);
export const useReplayEvents   = () => useReplayStore(s => s.status.stats.events);
export const useReplayTrades   = () => useReplayStore(s => s.status.stats.trades);
export const useReplayPnl      = () => useReplayStore(s => s.status.stats.pnl);
```

Add a lint rule or a review checklist item: **no component may call
`useReplayStore(s => s.status)`.** That single pattern is why the current dock
re-renders everything 6.7×/s (D5).

## 4. Streaming replaces polling

### 4.1 Target: server-sent events

`23_A14` §1 adds `GET /api/v1/simulation/stream` (SSE). The client:

```ts
const es = new EventSource('/api/v1/simulation/stream');
es.addEventListener('frame',  e => applyFrame(JSON.parse(e.data)));
es.addEventListener('signal', e => appendSignal(JSON.parse(e.data)));
es.addEventListener('trade',  e => upsertTrade(JSON.parse(e.data)));
es.addEventListener('state',  e => setState(JSON.parse(e.data)));
es.onerror = () => scheduleReconnect();     // exponential backoff, 500ms → 8s, then fall back to polling
```

`frame` is **small**: `{ t, pct, bars_played, bars_total, elapsed_real_s, pnl, wins,
losses, signals_fired, trades_open }` — scalars only, no arrays. Signals and trades
arrive once each, as they happen, and are appended client-side. That is the whole fix:
the payload stops being O(session) per tick and becomes O(1).

### 4.2 Fallback poller

If SSE fails (proxy, older backend), fall back to `GET /status`, but fixed:

| Fix | Detail |
|---|---|
| Interval | 500 ms while `running`, 2000 ms while `paused`, **stopped** while `idle` |
| Visibility | pause entirely on `document.visibilitychange` → hidden; resume with an immediate fetch |
| Dock closed | keep polling only if `state !== 'idle'` (the footer chip shows the clock), at 2000 ms |
| Delta | request `?since={lastEventCount}&since_trades={lastTradeCount}` and append (`23_A14` §1.3); if unsupported, replace but **reuse row identity** so React does not remount every row |
| Ownership | the interval lives in a hook with a proper cleanup, not a module-level `let` |

### 4.3 `applyFrame` must be incremental

```ts
applyFrame(frame) {
  set(s => {
    const st = s.status;
    // Mutate only what changed; keep array identity when the arrays did not change,
    // so `useReplayEvents()` subscribers do not re-render.
    return { status: { ...st, ...frame, stats: { ...st.stats, ...frameStats } } };
  });
}
```

`stats.events` and `stats.trades` must keep **referential identity** across frames in
which they did not change. The current `setStatus(status)` replaces everything every
150 ms, which is why memoising the tables today would not help.

## 5. Transport commands

```ts
type ReplayTransport = {
  start(): Promise<void>;
  stop(): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  setSpeed(s: number): Promise<void>;
  stepBars(n: number): Promise<void>;
  seekToPct(pct: number): Promise<void>;     // new — powers the timeline scrub
  jumpStart(): Promise<void>;
  jumpEnd(): Promise<void>;
};
```

Every command:

1. Applies an **optimistic** state change where it is safe (`pause` → `paused`
   immediately), so the UI does not wait a round trip at 60 fps.
2. `await`s the response and reconciles.
3. On failure: `setError`, push an error toast (A11 §6), and revert the optimistic
   change. **Never `console.error` and return** — that is D18.

`start()` keeps the existing retry-after-stop behaviour (`useSimulation.ts:396–414`)
because a stale runner is a real and common cause, but the retry becomes visible: the
first failure pushes a transient `Restarting…` toast, and only a second failure becomes
a sticky error.

`start()` also keeps `clearLocalFeedCache()` and the
`window.dispatchEvent(new CustomEvent('sterling-simulation-start'))` dispatch — other
panes listen for it. Add a matching `sterling-simulation-stop` on stop; its absence is
why some panes never clear their replay-derived state.

## 6. Persistence

```ts
const REPLAY_UI_KEY = 'sterling:replay-dock:ui';   // versioned, see 03 §3
```

- Write on change, debounced 250 ms, wrapped in `try/catch` (quota).
- Read once at store creation with a version check; unknown `v` → defaults.
- Migrate the existing `sterling:replay-dock:height` value on first read, then remove it.
- `mode: 'fullscreen'` is never written; if read, map to `'overlay'`.

## 7. Acceptance criteria

- [ ] No component subscribes to the whole `status` object.
- [ ] `stats.events` keeps referential identity across frames that add no events.
- [ ] Polling stops when `state === 'idle'` and when the tab is hidden.
- [ ] SSE connects when available and falls back cleanly when it does not.
- [ ] Every failed command produces a visible error; none is only logged.
- [ ] `useEffectiveNowMs()` keeps its signature and behaviour.
- [ ] `sterling-simulation-start` still fires; `…-stop` is added.
- [ ] UI prefs round-trip through one versioned key; the old height key is migrated.
- [ ] Measured: at 400 signals, a status frame causes ≤ 3 component re-renders (metric
      strip, timeline, shell bar) — **not** the tables.

## 8. Tests

1. selector isolation: writing a frame with unchanged arrays does not re-render a
   component subscribed to `useReplayEvents`
2. poller: stops on `idle`; stops on `visibilitychange` hidden; resumes on visible
3. SSE `signal` event appends without replacing the array reference of `trades`
4. failed `start` sets `error`, pushes a toast, and leaves `state === 'idle'`
5. optimistic `pause` flips state before the promise resolves and reverts on rejection
6. prefs migration: legacy `sterling:replay-dock:height` is read once then removed
7. stored `fullscreen` loads as `overlay`
8. `useEffectiveNowMs` returns replay time while running and wall time when idle
