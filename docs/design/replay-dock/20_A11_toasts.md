# A11 — `ReplayToastHost`

**File:** `frontend/src/components/kite/replay/ReplayToastHost.tsx`
**Replaces:** the inline toast (`SimulationBar.tsx:1119–1125` and `:1186–1192`)
**Fixes:** D4 (invisible in fullscreen), D19 (identity-keyed effect), plus the missing
live region

---

## 1. The two defects

1. **Stacking (D4).** `.sim-toast-popup` is `z-index: 1000`; the fullscreen dock is a
   body portal at `12000`. The toast is rendered as that portal's sibling, so in
   fullscreen — the mode where a user is most likely watching for signals — it is painted
   underneath. Fix: portal the toast host at `--rd-z-toast` (12200).
2. **Duplication.** The toast is rendered twice in the component tree (once in the
   fullscreen return, once in the docked return), each with its own JSX. One host,
   mounted once by `ReplayDock`, removes the duplication.

## 2. Behaviour

```ts
type ReplayToast = {
  id: string;                       // `${time_iso}|${strategy}|${instrument}|${seq}`
  kind: 'signal' | 'trade' | 'state' | 'error';
  tone: 'bull' | 'bear' | 'info' | 'error';
  title: string;
  detail: string;
  at: number;
};
```

| Rule | Value |
|---|---|
| Max visible | 3, newest at the top of the stack |
| Dwell | 4 s (`signal`/`trade`), 6 s (`state`), **sticky** (`error` — dismiss only) |
| Position | bottom-right, 12 px from the dock's bottom edge in docked modes, 12 px from the viewport in overlay/fullscreen |
| Pause on hover | yes — the dwell timer stops while the pointer is over the stack |
| Dismiss | `×` on each, or click the body to seek to that signal and dismiss |
| Rate limit | **hard cap of 1 toast per 800 ms.** Beyond that, coalesce into one `n new signals` toast that replaces the previous coalesced one. |

That rate limit is not optional. At speed 5000× the current implementation would try to
render a toast for every signal in a day.

**Suppress toasts entirely when `speed >= 100`** and instead surface a single persistent
`n signals so far` counter in the metric strip. Nobody reads a toast at 100×.

## 3. Anatomy

```
┌────────────────────────────────────────────┐
│▌ SIGNAL   10:47:05                      × │
│  SuperTrend · NIFTY26SEP24500CE            │
│  LONG  entry ₹142.50  →  tgt ₹168.00       │
└────────────────────────────────────────────┘
 ▌ = 3px left rule, --k-green (bull) / --k-red-brick (bear)
```

- `--k-surface` ground, `--k-border-strong` border, floating shadow.
- Title row `--rd-fs-micro`; detail rows `--rd-fs-body`, prices mono.
- Clicking the body seeks the timeline to that signal and selects its table row — the
  same cross-link as A04 and A07.

## 4. Motion

- Enter M11 (`opacity`, `translateY(10px)→0`, 200 ms out-ease).
- Exit M12 (140 ms in-ease, `translateY(0→-6px)`).
- Stack reflow when one is removed: the remaining toasts translate up over
  `--rd-dur-fast`. Use a keyed list with `transform` only — never animate `top`.
- Reduced motion: appear and disappear with no transform, `opacity` only, 1 ms.

## 5. Live region (the accessibility half)

The toast host also owns the announcement text written into `ReplayDock`'s
`aria-live="polite"` region. Throttle to **one message per 2 s**, coalescing:

```
"3 new signals. Latest: SuperTrend NIFTY long at 10:47."
```

State transitions announce once each and bypass the coalescer:
`"Replay paused."` / `"Replay complete. 47 signals, 21 trades, profit 4,120 rupees."`

Never announce progress. Never set `aria-live="assertive"` — an assertive region firing
at replay speed interrupts the user's own typing.

## 6. Error toasts

This is where D18's swallowed start failure surfaces. `useReplayTransport` pushes an
`error` toast on any command failure:

```
▌ REPLAY ERROR                                ×
  Could not start replay
  No stored candles for 2026-09-06.        [Retry]
```

Sticky, `--k-red` rule, with the backend's message when there is one and a generic line
when there is not. This single change turns "nothing happened when I pressed play" into
a diagnosable event.

## 7. Acceptance criteria

- [ ] Toasts render above the dock in fullscreen mode.
- [ ] Exactly one toast host in the tree (`grep` finds one `<ReplayToastHost`).
- [ ] Rate limit holds: 50 signals in 1 s produce ≤ 2 toasts.
- [ ] Toasts are suppressed at `speed >= 100`.
- [ ] Hovering pauses the dwell timer.
- [ ] Error toasts are sticky and offer Retry.
- [ ] The live region emits at most one message per 2 s and never announces progress.

## 8. Tests

1. z-index/portal: toast host mounts to `document.body`, not inside the dock
2. rate limiter: 50 rapid pushes → ≤ 2 rendered toasts, coalesced copy correct
3. `speed = 100` → zero signal toasts
4. hover pauses dwell; unhover resumes and it dismisses
5. error toast persists past 10 s and Retry calls `start`
6. live region throttle: 10 signals in 1 s → 1 announcement
