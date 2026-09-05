# 40 — Implementation notes

What actually landed against the specification, where it deviated, what the
browser caught that the tests did not, and what is still open.

Branch `design/replay-dock-redesign`, three commits off `main @ 7ff055e1e`.

---

## 1. Phase status

| Phase | Doc | Status |
|---|---|---|
| 0 — backend honesty | `23_A14` | Done. Friction **implemented** (Option A). |
| 1 — summary modal | `19_A10` | Done. |
| 2 — store extraction | `22_A13` | Done. |
| 3 — primitives + shell | `10_A01`, `11_A02` | Done. |
| 4 — the deck | `12`–`18` | Done. |
| 5 — remove old surface | `30 §Phase 5` | Done. |
| 6 — streaming | `23_A14 §1` | Done. |
| 7 — polish | `30 §Phase 7` | Done, except the palette item in §5. |

---

## 2. Deviations from the spec, and why

**Phase order.** Phase 2 (store) was done before Phase 1 (modal). The spec put
the modal first because it is the standalone visible bug; but every component
would then have been written against `useSimulationStore` and rewritten against
`useReplayStore` an hour later. Landing the store first cost nothing and avoided
writing every component twice.

**No v2 feature flag.** `30_MIGRATION_PLAN` gated phases 3–5 behind
`sterling:replay-dock:v2`. Since all phases landed in one branch with the old
surface deleted in the same change, a flag would have guarded a code path that
no longer exists. The rollback is `git revert` of the two feature commits.

**Friction: Option A, not B.** `SimConfig.friction_mode` is now read.
`_apply_friction` fills buys at the ask and sells at the bid plus a
configurable per-leg slippage, and P&L is computed from the fills. One
consequence worth knowing: **WIN/LOSS now follows the money actually made, not
the predicted spot move**, so friction can flip a marginal winner. That is
correct — a win rate and a P&L that disagree is worse than either alone — but it
does mean win rates will read slightly lower than the previous engine's.

**`_option_contract` fixed a latent sign error.** An OTM call is a *higher*
strike and an OTM put a *lower* one. Applying one signed offset to both would
have made one of them ITM. This code did not exist before (the old runner only
ever used ATM), so nothing regressed — but the test is there because it is the
kind of thing that looks right and is not.

**CSV: reused, not written.** The spec called for a new `replayCsv.ts` with its
own escaping. `frontend/src/utils/csvExport.ts` already existed, already escaped
correctly, and was already used by the positions and portfolio panes. Writing a
third implementation would have been the exact mistake the spec was complaining
about. `replayCsv.ts` is now a thin layer for replay-specific naming; the shared
utility was widened to accept a nullable cell (so an absent value is an empty
field, never `"null"`) and its download was guarded.

---

## 3. Two bugs the browser caught that the tests did not

Both were found by rendering the dock with realistic data, not by the suite.
Both now have regression tests.

**Duplicate React keys.** `signalKey` was `time|strategy|instrument`, which is
not unique — one strategy can fire twice on one symbol inside the same second,
and React then drops or duplicates rows. It now includes the row's index in the
append-only events array.

**The trades totals row was one cell short** whenever the friction column was
present: the blank span was 2 wide when it should always be 3 (Entry, Exit,
SL/Target). Every footer cell after Size sat under the wrong header. The
regression test sums the footer's colspans and compares against the header
count, so it cannot drift again.

The lesson worth keeping: a table can be fully green in jsdom and still be
visibly wrong, because jsdom does not lay anything out. Render it.

---

## 4. Verification actually performed

**Frontend.** `tsc --noEmit` clean. 1432 tests, 136 new. Two failures —
`AdaptiveEdgeSettingsPanel` and `NavigatorSettingsPanel` — reproduce identically
on `origin/main` in a detached control worktree, so the failing set is
unchanged. Suite run twice; same set both times, as
`31_VERIFICATION.md §1` requires.

**Backend.** 4801 passed, 11 skipped, 1 xfailed, **0 failed**, with
`PYTHONWARNINGS=ignore` and the socket test deselected. 73 replay tests, 57 of
them new.

**Browser** (headless harness at 1400px, both themes, real fixture data):

- Zero console errors on a clean load.
- Stacking measured, not assumed: dock `z-index: 12000` in fullscreen, toast
  host `12200`, summary overlay `12300`, and `elementFromPoint` at the viewport
  centre resolves to the modal. **This is the proof for D3 and D4** — the
  modal that had no stylesheet at all, and the toast that was painted under
  the fullscreen dock.
- Config sheet, summary modal, equity curve with drawdown band, error toast
  with Retry, and the split tables all render correctly in light and dark.

**Not performed:** no screen-reader pass, and no React Profiler measurement of
the re-render counts. The performance work is structurally in place (scalar
selectors, preserved array identity, single mounted panel, memoised rows,
virtualisation above 200 rows) and is covered by store-level identity tests, but
the numbers `31_VERIFICATION.md §4` asks for have not been taken. Treat the
performance claims as reasoned, not measured.

---

## 5. Open, and deliberately not fixed

**Light-mode contrast is below AA for secondary and accent text.** Measured in
the browser:

| Pair | Dark | Light |
|---|---|---|
| `--k-text` on `--k-bg` | 15.4 | 9.7 |
| `--k-dim` on `--k-surface` | 5.6 | **2.6** |
| `--k-green` on `--k-bg` | 8.9 | **2.8** |
| `--k-amber` on `--k-bg` | 10.8 | **2.0** |
| `--k-cyan` on `--k-bg` | 10.5 | **2.3** |
| `--k-on-accent` on `--k-brand` | 7.3 | **3.2** |

This is **inherited, not introduced**: the palette is untouched by this branch,
and the previous dock used the same tokens for the same roles. `theme.ts` states
that every light value is byte-identical to the hex it replaced, and only the
dark values were chosen to clear AA — so this is an app-wide property of light
mode, not a replay-dock defect. Fixing it means changing the terminal's light
palette, which is a separate decision affecting every pane and would break the
"light mode is provably unchanged" invariant that file is built on.

Recorded here rather than silently ticked in `32_ACCEPTANCE_CHECKLIST.md`.

**Multi-day ranges are refused, not supported.** The runner only ever built one
session's bounds. It now says so — in `capabilities.multi_day`, in
`status_message`, and in the config sheet — instead of silently replaying a
single day. Implementing them means teaching `_run_loop` to span dates and
putting the date into `current_time_iso`, without which the timeline cannot
place a bar.

**`/available-dates` does not filter exchange holidays.** It skips weekends
only, while the preset logic checks `isNseClosed`. The response now declares
`holidays_filtered: false` so the client does not over-claim, but the two
definitions of "trading day" still differ.

**Lot sizes are the engine's originals** (25 index / 15 stock). These are not
current NSE contract sizes, but changing them changes every historical P&L
number this engine produces, which is a trading decision rather than a UI one.

**Expiry is hardcoded `26AUG`** in the contract name, inherited from the
previous runner. The contract string is therefore illustrative, not tradeable.
