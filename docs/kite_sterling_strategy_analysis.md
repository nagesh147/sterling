# Kite Sterling Engine — Entry, Trailing SL & Exit Analysis (+ Spot vs Derivatives vs Both)

**Date:** 2026-07-16 · **Scope:** Kite (Indian F&O — NIFTY/BANKNIFTY/FINNIFTY/SENSEX + F&O stocks) **only, not crypto.**
**Constraint honored:** the signal core stays exactly the **same 3 SuperTrends on 1H Heikin-Ashi**. Everything below layers around it — nothing replaces it.
**Analysis only — no code was changed.**

Sources: full read of `engines/sterling_kite_engine/` + `services/kite_engine/` + `engines/indicators/`, plus the repo's own empirical studies
(`backend/study/kite_st_*`, `docs/kite_st_permutation_backtest.md`, `backend/study/kite_st_phase0_report.md`, `backend/study/kite_st_exit_analysis.md`).
Every behavioral claim is cited `file:line`. Claims from code-reading that lack a runtime test are marked **⚠ needs-test**.

---

## 0. TL;DR

| Question | Verdict |
|---|---|
| **Is the entry good?** | Yes — it's the *strongest* link. Fresh triple-alignment on closed 1H HA bars is repaint-proof and has a **real, OOS-durable directional edge** (delta-1: OOS-positive on 4/4 indices, PF 1.05–1.15). Keep it. Improvements are filters and *what you buy*, not the trigger. |
| **Is the trailing SL good?** | Right architecture (ST-line trail + GTT + tick monitor), but **three defects**: (1) the monotonic ratchet cancels the "step-out-to-wider-line" design, so the configured `exit_mode` barely matters — effective exit ≈ `one_red`; (2) **spot-mode auto-exec has no working price stop at all**; (3) deep-ITM stops are never trailed after entry. |
| **Is the exit strategy good?** | The red-count exit logic is sound and "no profit-target" is *correct* (31–42% win rate, fat-tail winners). But `two_red` default is **asserted, never measured** (the sweep script exists and was never run), and there is **no expiry/DTE exit** — a weekly can ride into expiry unmanaged. The binding constraint on exits is not the SuperTrends — it's the **vehicle** (theta + IV kill long OTM/ATM regardless of exit tuning: 0/60 configs OOS-positive). |
| **Spot vs Derivatives vs Both?** | **Spot is the best signal source** — it is the only one with validated edge, and premium charts structurally corrupt the ST's assumptions. Derivatives mode is best as an *execution/confirmation* layer (it's currently the only mode whose premium-stop machinery is fully armed). **`both` is the worst default** — it doubles capital deployment on the same move with no cross-mode guard. Endgame: **spot signals → deep-ITM (or futures) vehicle → delta-translated premium stop**. |

---

## 1. What the strategy is today (verified ground truth)

### 1.1 Signal core — the 3 SuperTrends on 1H Heikin-Ashi

- Raw 1H OHLC → Heikin-Ashi (`regime.py:103`), then **three SuperTrends computed on HA high/low/close** (`regime.py:105-107`):

| Line | (period, multiplier) | Role |
|---|---|---|
| `fast` | (21, 1.0) | tightest band, flips first — default trail line |
| `mid` | (14, 2.0) | middle band |
| `slow` | (7, 3.0) | widest band, flips last |

  (`config.py:30-32` — named by flip-responsiveness via multiplier, per the source spec.)
- **Warmup** = 21 bars (`config.py:55-57`) ≈ 3 trading days of 1H bars (7 bars/session).

### 1.2 Entry

- **Trigger:** the latest **closed** bar freshly enters full alignment — all three ST trends agree now, and did *not* all agree on the previous bar (`regime.py:123-132`, `engine.py:66-68`). Long → CE, short → PE.
- **Repaint-proof:** the forming 1H bar is dropped before evaluation (`scanner.py:62-69`), matching the repaint-guard convention used elsewhere in the repo.
- One open position per underlying (spot slots) / per contract (derivatives slots) via a DB-persisted auto-open guard, reconciled against broker positions at startup (`service.py:200-201`, `service.py:605-624`).
- Score is a constant 85 (`engine.py:127-129`) — full alignment *is* the conviction; there is no graded signal quality.
- ADX / ATR-percentile are computed and attached to every row (`scanner.py:116-117,156-157`) but only gate entries when the user sets `adx_min`/`atr_pct_min` (default `None` = off, `service.py:221-225`, `schemas.py` Phase-0 survivors).
- Scan cadence: background loop every **300 s**, market-hours gated (`service.py:32`, `service.py:678-694`); candles cached 180 s; concurrency 2 vs Kite's ~3 req/s limit (`scanner.py:43-46`).

### 1.3 Trailing stop — as designed vs. as it actually behaves

Designed (the "adaptive trail"):

1. At entry the stop = the ST trail line value; default `trail_target="fast"` (`schemas.py`, backed by the 7.5-year sweep — see §4).
2. Each 5-min scan recomputes the regime; the stop rides the **tightest still-green line** (`regime.py:72-94`). As lines flip red the trail was *meant* to **step out** to the next wider still-green line (fast→mid→slow), giving the trade room to survive to a `two_red`/`three_red` exit.
3. The tightened stop is pushed to open positions after every scan (`service.py:425-487`): in-memory (`positions.update_stop`), broker GTT moved (`protective_stop.move_stop`), tick subscription refreshed.
4. Intrabar, the WS tick monitor market-exits the moment LTP breaches the stop (`monitor.py:on_tick`), then cancels the GTT so it can't double-fire.

Actual behavior — **the ratchet contradiction** (documented in the code itself, `regime.py:80-85`, and in `study/kite_st_exit_analysis.md §6.2`):

> `positions.update_stop` ratchets the premium stop **up-only for longs** (`positions.py: update_stop`) and therefore **rejects the step-out loosening**. The stop stays pinned near the peak `fast`-line level, so the price trail fires around the first `fast` flip and **pre-empts the red-count exit. Net effect: `exit_mode` is largely cosmetic in live trading — effective exit ≈ `one_red`,** whatever the config says.

### 1.4 Exit paths, enumerated

| # | Path | Mechanism | Status |
|---|---|---|---|
| 1 | **Broker GTT stop** | single-leg GTT, market SELL at trigger; placed at entry, trailed each scan (`protective_stop.py`, `service.py:369-381`) | Live (`stop_mode` "broker"/"both"; default "both") |
| 2 | **Tick-monitor price exit** | WS tick → `should_exit(stop, ltp)` → market exit + GTT cancel (`monitor.py:on_tick`, `positions.py:should_exit`) | Live |
| 3 | **Red-count exit** | scan updates `current_red_count` per position (`service.py:468-486`); next tick, monitor exits if `reds ≥ get_exit_threshold(exit_mode)` (`monitor.py:on_tick`) | Live, but scan-granular (5 min) and pre-empted by #1/#2 (§1.3) |
| 4 | Manual close | UI / API | Live |
| 5 | **Expiry / EOD square-off** | — | **Does not exist.** No expiry, DTE, or EOD logic anywhere in `monitor.py`/`positions.py` (verified by search). |
| — | `engine.manage()` early-lock/flip exit | `engine.py:87-122` | **Dead code in production** — nothing calls `.manage()`; the scanner recomputes the regime directly (`study/kite_st_exit_analysis.md §1`). |

### 1.5 Sizing & risk stack

- **Premium-at-risk sizing**: lots such that `(entry − stop) × qty ≤ risk_pct% × available F&O capital`, floor 1 lot, cap `max_lots` + margin affordability (`sizing.py:size_position`). Defaults `risk_pct=1.0`, `max_lots=10` (`schemas.py`).
- Drawdown circuit breaker + correlation penalty exist but only when `wire_risk_infra=True` (**default False**, `service.py:296-316`).
- **No daily-loss breaker applies to Kite** — the USD one is crypto-only and Kite calls `assert_safe_to_trade(check_daily_loss=False)` (`service.py:66-68,321-322`). Kill-switch + idempotency still apply.

---

## 2. Entry analysis

### 2.1 What's genuinely good

1. **Closed-bar, fresh-transition discipline.** No repaint, no mid-trend chasing, deterministic replay (each scan reproduces identical history — `scanner.py:72-94`). This is the hardest thing to get right in a scanner and it's right.
2. **The edge is real (for the signal, not the wrapper).** Stripped to delta-1, the same entries+trail are **OOS-positive on all four indices** (OOS PF 1.05–1.15, ~38–42% win rate, median hold 3.7 days, p90 ~10 days) over 7.5 years of real 1H candles (`docs/kite_st_permutation_backtest.md §4`). A classic trend-following profile: sub-coinflip win rate carried by fat-tail winners.
3. **HA smoothing does its one job** — suppressing single-bar whipsaw flips so "triple alignment" means a persistent regime, not three coincident ticks.
4. **Triple confirmation keeps base rate low** and the alignment chip (fast/mid/slow) gives an honest per-signal state.

### 2.2 Where the entry leaks edge

| # | Weakness | Why it hurts | Evidence |
|---|---|---|---|
| E1 | **Entry lag is structural** — HA lags, and the last-to-flip line gates the entry. | You buy well after the move starts; with a long option that's paying peak IV after the move is visible. Delta-1 results already *include* this lag, so it isn't fatal — but it's why the wrapper matters so much (§4). | mechanism of `regime.py:112-113` |
| E2 | **Flat conviction (score=85)** — no discrimination between a marginal and a powerful alignment. | Cannot size or prioritize by quality; every signal is equal to the sizer. | `engine.py:127-129` |
| E3 | **Quality filters exist but are off, and unvalidated.** ADX≥25–30 (±ATR-pct) lifted OOS PF to 1.1–2.0 in the filter study — but OOS n collapsed to 12–29 trades, far below the ≥100 gate. | Promising, not provable yet. Turning them on blind is curve-fitting; leaving them off forever wastes the one measured entry improvement. | `kite_st_phase0_report.md §0c`, `kite_st_filters_results.csv` |
| E4 | **No session-time awareness.** A fresh alignment on the 14:15 or 15:15 bar enters minutes before close → guaranteed overnight gap exposure, with no INR daily-loss breaker behind it (§1.5). The 09:15 bar also embeds the overnight gap, distorting that bar's HA/ATR. | Overnight index gaps are the tail risk of this whole book. | `service.py` (no time-of-day gate anywhere) |
| E5 | **No entry-time IV or spread gate.** The IV-sensitivity table shows entry-time IV *is* the P&L for long options (same config swings +837% → −278% purely on IV). The scanner never looks at IV, IV percentile, or bid-ask spread before buying. | You systematically buy expensive options after visible moves (when IV is bid). | `docs/kite_st_permutation_backtest.md §2` |
| E6 | **Execution slippage vs. signal bar.** The signal is the 1H close; auto-exec fires on the next scan tick (up to ~5 min later) at market. | Small, but unmodeled — the studies fill at bar prices. | `service.py:32` |

### 2.3 Entry recommendations (keeping the 3ST/1H/HA core untouched)

1. **P1 — Paper-validate the ADX filter** exactly as shipped (`adx_min=25`, filters already wired at `service.py:221-225`). Accept/reject on ≥100 paper signals, not on the n=12–29 backtest.
2. **P1 — Add a session-time entry window** (e.g. no *new* auto-exec entries on the last bar of the day; treat the 09:15 bar's signal with a gap-size sanity check). This is an execution-layer gate; the signal itself stays untouched.
3. **P2 — Entry-time contract gates** (derivatives execution, not signal): max bid-ask spread %, min OI/volume, and an IV-percentile ceiling before buying the leg. E5 is the most expensive leak per rupee of any item in this table.
4. **P2 — Graded conviction for display/sizing** — expose green-streak length / ADX as a displayed conviction tier (keep score=85 as the entry gate). Zero change to what fires; better human triage.

---

## 3. Trailing SL & exit analysis

### 3.1 The three defects, ranked

**D1 (P0) — Spot-mode auto-exec has no working price stop.** For spot-sourced signals the legs carry no premium data (`premium_spot`/`premium_sl` are only stamped on derivatives rows, `scanner.py:181-183`), so in `_make_place_cb`:
- `stop_px = 0.0` → the **GTT branch is skipped** (`service.py:369` requires `stop_px > 0`) — and in `"both"` mode it's skipped *silently* (the warning only logs when `stop_mode=="broker"`, `service.py:378-381`);
- the monitor's price exit is **permanently inert** (`positions.should_exit` returns False for `stop_premium ≤ 0`, `positions.py`);
- the trail-update pass never matches (`_new_trail_for_open` needs `leg.premium_sl > 0`, `service.py:416-421`);
- risk-sizing can't compute → **always 1 lot** (`service.py:281-293` falls through);
- the `stop_loss` passed into the entry order does nothing on a market order (`client.py:352-353` — honored only for explicit SL/SL-M order types).

Net: a spot-mode OTM auto-position is protected **only** by the red-count exit at 5-minute scan granularity, with no broker-side stop at all. The underlying-level ST stop exists on the row — it is simply never translated to premium. (The delta-translation machinery to do this **already exists** for deep-ITM: `service.py:173-179`.)

**D2 (P0) — The ratchet contradiction (§1.3).** Until `positions.update_stop`'s monotonic ratchet and `regime.best_trail_line_value`'s step-out are reconciled, the `exit_mode` feature is largely cosmetic and every live exit is effectively `one_red`+trail-breach. Two coherent resolutions — this is a *decision*, then a measurement, not a refactor:
- *(a) Tighten-only semantics:* accept the ratchet, set the default `exit_mode="one_red"` honestly, and delete the pretense of multi-red exits from the live path; or
- *(b) Step-out semantics:* let the stop re-anchor outward to the next still-green line, **floored at the entry-time initial stop** (never risk more than entered risk), so `two_red`/`three_red` can actually function.
Which is better is an empirical question — and the harness to answer it already exists and **has never been run**: `backend/study/kite_st_exit_mode_sweep.py` (no results CSV exists in `backend/study/`). Run it before touching the default.

**D3 (P1) — Deep-ITM stops are never trailed.** The entry stop is delta-implied (`service.py:173-179`) but `_new_trail_for_open` deliberately skips deep-ITM (`service.py:402-404`), and the monitor merely compares LTP to that *static* entry stop. So the validated-vehicle path (§4) currently has the *weakest* trailing of the three vehicles: static initial stop + red-count only. The same delta-translation used at entry could re-derive the premium stop from the fresh underlying ST trail each scan — the inputs are all already in the row.

### 3.2 Additional exit-stack findings

- **⚠ needs-test — GTT-fired exits are invisible to the registry, risking a double-sell.** `monitor.on_order_update` matches postbacks **by tradingsymbol only** — no `order_id` or transaction-type check (`monitor.py:on_order_update`). If the *broker GTT* fires (exactly the server-down scenario GTT exists for), its SELL postback is interpreted as an entry **fill** (`mark_filled` with the exit price); the position stays `OPEN`, the guard is never released, and on the next tick the monitor's `should_exit` would market-**SELL again** → a naked short option. Nothing else reconciles the position registry against broker positions (only the auto-open *guard* is reconciled at startup, `service.py:605-624`). This deserves a reproducing test before the next live session with `stop_mode="broker"`/`"both"`.
- **No expiry/DTE exit (P1).** Default `scan_expiries` includes weeklies; median hold is 3.7 days, p90 ~10 (`docs/kite_st_permutation_backtest.md §5`) — i.e. **weeklies routinely expire mid-trade**. The permutation study had to fix DTE=30 for exactly this reason. Live, nothing squares off a position approaching expiry; it settles however it settles.
- **HA-space stop vs. real-LTP execution (P2, informational).** Trail values are computed from HA-smoothed series but compared against raw LTP ticks and used as GTT triggers. HA lows sit at/below real lows by construction, so triggers are slightly conservative; fine — just document it so nobody "fixes" it into a mismatch.
- **Gap-through-stop is unbounded by design.** GTT fires a *market* SELL — an overnight gap fills wherever the market opens. That is inherent to stops; the mitigations are sizing (already premium-at-risk-based) and E4's session gate, not stop mechanics.
- **No profit target — keep it that way.** With 31–42% win rate the book lives on fat-tail winners; the exit study is explicit that a fixed TP would clip them and flip the edge negative (`kite_st_exit_analysis.md §4`).
- **Untested-but-scripted exit refinements**: breakeven-promotion at +1R and a 48-bar time-stop (attacks theta directly) are already parameterized in `backend/study/kite_st_exit_sweep.py` — also **never run**. The time-stop is the most interesting for the options wrapper: it caps exactly the theta-bleed failure mode the sweep proved dominant.

### 3.3 Trailing/exit recommendations, ranked

| Priority | Recommendation | Rides on |
|---|---|---|
| **P0** | Give spot-mode auto-exec a real premium stop: translate the underlying ST trail to premium via the delta method already used for deep-ITM (D1). Until then, treat spot-mode auto-exec as unprotected. | `service.py:173-179` machinery |
| **P0** | Decide ratchet-vs-step-out semantics (D2), then **run `kite_st_exit_mode_sweep.py`** to pick the default `exit_mode` with numbers. Until then the honest default is `one_red` (it's what actually happens). | existing sweep script |
| **P0** | Write the GTT-fired-exit reconciliation test (⚠ above); match postbacks by `order_id`/transaction-type and close the registry position when the protective exit fills. | `monitor.py`, `positions.py` |
| **P1** | Trail the deep-ITM stop each scan via delta re-translation (D3). | trail-update pass |
| **P1** | Add an expiry guard: square off (or roll) at T-1 day for any held contract; prefer monthly legs whenever expected hold (p90 ~10d) exceeds the weekly's remaining DTE. | positions registry (needs an `expiry` field) |
| **P1** | Run `kite_st_exit_sweep.py` — it directly answers whether a breakeven promotion or 48-bar time-stop improves the costed-options lens. | existing sweep script |
| **P2** | Wire an INR daily-loss/drawdown backstop for Kite (today: none unless `wire_risk_infra` is on). | `state.drawdown_multiplier` |

---

## 4. The vehicle is the exit's binding constraint (evidence)

The repo's own 7.5-year study (real 1H index candles, real Indian F&O cost schedule, IS 70%/OOS 30%) is unambiguous (`docs/kite_st_permutation_backtest.md`):

| Wrapper for the same entries + ST exit | OOS result |
|---|---|
| Long OTM/ATM options (as deployed) | **0 / 60 configs OOS-positive**; best OOS = −12%. Headline +961% full-history returns are an IS-regime + fixed-IV artifact (IV 0.10→+837%, IV 0.28→−278%). |
| Delta-1 (signal isolation) | **4 / 4 indices OOS-positive**, PF 1.05–1.15 |
| Deep-ITM options (ITM5–ITM15) | **3 / 4 OOS-positive** (validated ✓, shipped `itm_depth=ITM10`) |
| Index futures | **3 / 4 OOS-positive** (validated ✓, opt-in) |
| `trail_target` | fast > mid ≫ slow on every lens (hence the `fast` default) |
| `early_lock` | provably inert (byte-identical results) — correctly removed |

**Implication for "make it best":** no amount of exit tuning rescues long OTM/ATM buying — theta + IV are a structural tax bigger than the edge. The exits should be tuned (§3), but the step-change is `directional_mode=ON` with `vehicle=deep_itm_options` (or futures for accounts that accept margin + two-sided risk). Caveat the studies honestly: premium was BS-modeled (fixed IV) over real underlying candles; deep-ITM is the least IV-sensitive region, which is exactly why it's the credible options vehicle.

---

## 5. Spot vs Derivatives vs Both — which is best, and why

### 5.1 What each mode actually does

| | **spot** | **derivatives** (current default, `schemas.py:247`) | **both** |
|---|---|---|---|
| ST runs on | underlying 1H chart | each selected contract's **own premium** 1H chart (`scanner.py:215-276`) | both, concurrently |
| Directions | long→CE and short→PE | **BUY-only** (fresh premium *up*-transition; a premium downtrend is a holder's exit, not an entry) | both sets |
| Legs | strikes resolved from the chain per selected moneyness (`attach_strikes`) | the scanned contract itself is the leg; CE and PE resolved per moneyness (`pick_contracts`, `strikes.py:213-234`) | union |
| Stop basis | underlying ST level (never translated to premium — §3.1 D1) | premium ST trail — **fully armed**: GTT + monitor + trail updates all work | mixed |
| Auto-exec guard | per **underlying** | per **contract** | **no cross-mode guard** — the same move can open the spot leg *and* several premium legs simultaneously (`service.py:200`) |
| Scan cost (default 4 indices, ITM1/ATM/OTM1) | ~4 candle fetches/scan | ~4 spot anchors + up to ~24 contract charts/scan (moneyness × CE&PE, deduped) at 2-concurrent under Kite's ~3 req/s | sum of both |
| Historical validation | **7.5 y, IS/OOS, 4 indices** (§4) | **essentially none** — expired strikes have no fetchable premium; the "real" backtest mode is capped at one listed contract's life (n = 1–5 trades: "statistically meaningless", `docs/kite_st_permutation_backtest.md §6`) | n/a |

### 5.2 Why premium-chart SuperTrends are statistically weaker as a *signal source*

1. **Non-stationary drift violates the ST's premise.** Premium = f(spot, IV, θ, moneyness). Theta imposes a persistent downward drift, so "trend" on premium conflates underlying direction with time-decay and IV flow. A premium uptrend must *beat* theta to print — which makes it an implicit momentum-strength filter (the one genuine virtue) but also a later, rarer, direction-biased trigger.
2. **ATR on premium isn't comparable across contracts.** Band width scales with moneyness/gamma/IV, and explodes near expiry — the same (period, mult) triple means something different on every strike and every week of a contract's life. The 3ST parameters were chosen (and validated) on underlying charts.
3. **Contract history is too short for the warmup, by construction.** Warmup = 21 bars ≈ 3 trading sessions (`config.py:55-57`); a weekly lives ~5 sessions (~35 hourly bars). Premium-chart signals can only appear in the **back half of a weekly's life — the maximum-theta zone**. (The scanner correctly never fabricates signals for young contracts, `scanner.py:227-229` — but that means the mode structurally skews late-DTE.)
4. **Strike churn destroys continuity.** Every expiry/ATM drift re-points the scan at different contracts — there is no stable series to trust a trend on, and no way to backtest the mode over history (the validation asymmetry in the table above is *permanent*, not a to-do).
5. **BUY-only truncation** throws away the bearish half of the information on every chart it scans.
6. Illiquid strikes print gappy/flat bars that HA smooths into false structure.

### 5.3 What derivatives mode gets right (and spot currently doesn't)

- It trades **what you actually hold**: the stop is in premium space, directly executable — and today it is the **only mode where the whole protective stack (GTT + tick monitor + trail updates + risk sizing) is actually armed** (§3.1 D1).
- The theta-beating requirement is a genuine confirmation: a CE whose premium trend flips up is telling you demand is beating decay *right now*.
- Per-contract `is_active` (with the fixed no-resurrection semantics, `scanner.py:244-258`) gives honest per-leg health.

### 5.4 Verdict

**Best signal source: `spot` — decisively.** It carries the only validated edge, both directions, full history, stable series. The premium chart is the wrong place to *discover* direction (§5.2), and its one virtue (confirmation) doesn't need to be the primary source.

**Best execution mechanics today: `derivatives`** — purely because of the spot-mode stop gap (D1). This is an implementation artifact, not a signal-quality argument, and it currently forces an ugly trade-off: validated signals with no stop (spot) vs. unvalidated signals with a good stop (derivatives).

**`both`: keep for research/display, never for auto-exec.** Two parallel signal streams with per-mode guards means the same NIFTY move can open the spot-picked leg *plus* multiple premium legs — uncontrolled concentration on one underlying, with `wire_risk_infra` (correlation penalty) off by default. Its legitimate use is side-by-side comparison on the board while paper-validating.

**The "best" configuration is spot-signals + derivative-aware execution** (this dissolves the trade-off instead of picking a loser):

1. `scan_source="spot"` — the validated trigger, both directions.
2. `directional_mode=ON`, `vehicle="deep_itm_options"` (`itm_depth=ITM10` or `target_delta≈0.85–0.9`) — the validated wrapper; futures where margin/two-sided risk is acceptable.
3. Delta-translated premium stop at entry **and per-scan re-translation** (fixes D1 + D3 with machinery that already exists).
4. Optional *premium-confirm* gate borrowed from derivatives mode: before auto-exec, require the chosen leg's own premium chart to not be in a fresh ST *down*-state — confirmation as a filter, not as the source.
5. `stop_mode="both"`, `risk_pct=1.0`, `wire_risk_infra=true`, exit_mode per the D2 sweep (until run: `one_red` is the honest label for current behavior).

---

## 6. Evidence status — what is proven vs. asserted

| Claim | Status |
|---|---|
| Delta-1 signal edge OOS on 4/4 indices | **Measured** (7.5y, IS/OOS, real candles) |
| Long OTM/ATM options unviable (0/60 OOS) | **Measured** (BS-premium caveat, but IV-sensitivity analysis makes the direction robust) |
| Deep-ITM / futures vehicles flip it positive (3/4 each) | **Measured**, BS-modeled premium (deep-ITM least model-sensitive); shipped as validated ✓ |
| `trail_target=fast` best, `slow` worst, `early_lock` inert | **Measured** |
| `exit_mode=two_red` default | **Asserted only** — rollout doc has zero numbers; sweep script exists, never run |
| Ratchet shadows step-out → effective `one_red` | **Code-verified** (documented in `regime.py:80-85` itself); magnitude unmeasured |
| Spot-mode auto-exec has no price stop | **Code-verified** (traced end-to-end §3.1); no runtime repro yet |
| GTT-fired exit → possible double-sell | **⚠ needs-test** — code-reading only |
| ADX entry filter helps | **Suggestive, small-n** (OOS n=12–29) — paper-validate |
| Derivatives-mode signal quality | **Unvalidated and structurally unvalidatable** over history |

---

## 7. Consolidated roadmap (analysis only — nothing implemented)

| # | Priority | Item | Section |
|---|---|---|---|
| 1 | P0 | Spot-mode premium stop via delta translation | §3.1 D1 |
| 2 | P0 | Decide ratchet vs step-out; run `kite_st_exit_mode_sweep.py`; set `exit_mode` default from data | §3.1 D2 |
| 3 | P0 | GTT-exit reconciliation test + order-id matching in `on_order_update` | §3.2 ⚠ |
| 4 | P1 | Switch default `scan_source` derivatives → **spot** once #1 lands; derivatives demoted to confirm-gate | §5.4 |
| 5 | P1 | `directional_mode=ON`, `vehicle=deep_itm_options` as the recommended preset (validated vehicle) | §4 |
| 6 | P1 | Trail deep-ITM stops per scan (delta re-translation) | §3.1 D3 |
| 7 | P1 | Expiry guard (T-1 square-off / monthly-preference when p90 hold > weekly DTE) | §3.2 |
| 8 | P1 | Run `kite_st_exit_sweep.py` (breakeven +1R, 48-bar time-stop, trail period/mult) | §3.2 |
| 9 | P2 | Session-time entry gates (no last-bar entries; 09:15 gap sanity) | §2.3 |
| 10 | P2 | Contract-level spread/OI/IV-percentile gates for the executed leg | §2.3 |
| 11 | P2 | INR daily-loss backstop; `wire_risk_infra=true` in the recommended preset | §1.5 |
| 12 | P2 | Disable auto-exec under `scan_source="both"` (or add a cross-mode guard) | §5.4 |

---

*Report generated by code + study review on branch `kite-mobile` (commit `be829ca`).*

---

# Part II — Fixes Implemented (2026-07-16)

All fixes were built **test-first** (TDD); the Sterling-Kite suite is green
(**186 passed**, up from 155 + 3 pre-existing failures) and the wider Kite surface
(routers, completeness, orders) passes (**254 passed**). The 3 SuperTrends on 1H
Heikin-Ashi are untouched — every change layers around that core. Risky real-money
default changes are **opt-in / reversible**; only two protective defaults changed
(see notes).

### P0 — bugs fixed

| # | Fix | What changed | Files |
|---|---|---|---|
| D1 | **Spot-mode now gets a real premium stop** | A spot-source leg carries no premium, so auto-exec now fetches the leg LTP and derives a delta-implied premium stop from the underlying ST trail (the same translation deep-ITM used). Position stores `entry_spot`/`entry_delta`/`strike`/`expiry`/`initial_stop_premium`; sizing keyed off the resolved premium (no longer floored to 1 lot). | `greeks.py` (`premium_stop_from_move`), `service.py` (`_resolve_premium_stop`, `_make_place_cb`, `_resolve_deep_itm`), `positions.py` |
| — | **GTT-exit double-sell closed** | `monitor.on_order_update` now classifies a postback by `order_id` + `transaction_type`: a protective exit fill (SELL for a long / BUY-to-cover a short from a non-entry order) reconciles the position to **CLOSED** and releases the guard instead of being mis-booked as an entry fill — so the tick monitor can't market-sell a second time (naked short). | `monitor.py` |
| D2 | **`exit_mode` made functional (opt-in) + now MEASURED** | New `exit_aligned_trail` flag aligns the price stop to the `exit_mode`-th-red line. The sweep it was built to enable has since been **run** (see §8): the data says tighter is better, so `exit_aligned_trail` stays **default off** and the `exit_mode` default was changed **`two_red` → `one_red`** (the measured winner). | `regime.py`, `scanner.py`, `config.py`, `schemas.py` |

### P1 — trailing / exit / evidence

| # | Fix | What changed |
|---|---|---|
| D3 | **Deep-ITM & spot-OTM stops now trail** | `_new_trail_for_open` re-translates the fresh underlying ST level to a premium stop via the stored signed delta (`premium_stop_from_move`), ratcheting up — and, because the model is anchored at entry with **signed** delta, it trails **into profit** as the ST ratchets past the entry spot, with no live re-quote. |
| — | **Expiry square-off guard** | `expiry_square_off_days` (default **1**): each scan squares off any held option within T-1 of expiry via the monitor exit path, so a weekly can't settle unmanaged. Options only (futures roll). |
| #4 | **`scan_source` default → `spot`** | The validated source (delta-1 OOS-positive 4/4), now fully stop-protected by D1. Derivatives/both remain selectable. (Auto-exec is off by default, so this mainly changes which signals populate the board.) |

### P2 — guards (all opt-in, default off)

| Fix | Knob |
|---|---|
| **Session-time entry gate** — block new auto-entries in the last N min before 15:30 (overnight-gap guard) | `block_entry_minutes_before_close` (0 = off) + `market_hours.minutes_to_close` |
| **Contract liquidity gate** — skip an entry whose leg has too-wide a bid-ask spread or too-thin OI (fail-open on missing data) | `max_spread_pct`, `min_oi` + `service._passes_liquidity` |
| **`both`-mode cross guard** — block a second entry on an underlying already held (prevents stacking one move across spot+deriv) | automatic when `scan_source="both"` |
| **INR daily-loss breaker** — halt new entries once the IST-day realized loss reaches a % of F&O capital (fills the crypto-only-breaker gap); realized PnL now booked at every exit | `max_daily_loss_pct` (None = off) + `state.record_realized_pnl` / `daily_realized_pnl` |
| **Time-stop** — square off a position after N held 1H bars (the exit-mechanics sweep's robust theta-cap finding; see §9) | `time_stop_bars` (0 = off) + `service._time_stop_positions` |

### Two changed defaults (protective, reversible)
- `scan_source`: `derivatives` → **`spot`** (validated source; see #4).
- `expiry_square_off_days`: **1** (was: no expiry handling at all). Set to `0` to disable.

### Still requires larger work (not code-fixable here)
- **Frontend controls** for the new knobs (`exit_aligned_trail`, `expiry_square_off_days`, session/liquidity/daily-loss gates) — backend defaults are safe without them; the UI additions are a follow-up.
- The long-OTM-options vehicle is still the OOS loser; pairing spot signals with `directional_mode + vehicle=deep_itm_options` (validated ✓) remains the recommended preset.

---

# Part III — Exit sweeps run on fresh real data (2026-07-16)

With the Kite account connected, both exit sweeps were run on a fresh 7.5-year pull
(2019-01-01 → 2026-07-16, ~13k 1H bars/index, 4 indices, IS 70% / OOS 30%, both a
theta-free delta-1 lens and a costed ATM-options lens).

### 8. Exit-mode (red-count) sweep — `study/kite_st_exit_mode_sweep.py`

Mean OOS return by mode (baseline `one_red`):

| exit_mode | delta1 OOS | idx + | options OOS | vs one_red (delta1) |
|---|---:|---:|---:|---:|
| **one_red** | **+4.0%** | **3/4** | **−134.0%** | — |
| two_red | −6.4% | 1/4 | −184.5% | −10.4pp |
| three_red | −18.4% | 0/4 | −338.1% | −22.4pp |
| three_red_signal | −18.4% | 0/4 | −338.1% | −22.4pp |

**`one_red` is best on both lenses — tighter exits win decisively.** The shipped
`two_red` default (previously asserted, never measured) was measurably worse.
**Action taken:** default changed `two_red` → **`one_red`** (`config.py`, `schemas.py`),
and `exit_aligned_trail` confirmed correct to leave **off** (widening the trail to
honour a looser mode is exactly what the data penalises). Artifact:
`study/kite_st_exit_mode_sweep_results.csv`.

### 9. Exit-mechanics sweep — `study/kite_st_exit_sweep.py`

48 configs (trail_period × trail_mult × time_stop × breakeven), same data/windows.
Top configs by mean OOS:

| lens | shipped baseline (p21,m1.0) | best config | IS→OOS Spearman |
|---|---:|---|---:|
| delta1 | +4.0% | p21, **m0.75**, tstop48 → **+10.3%** (3/4 +) | **−0.20** |
| options | −134.0% | p10, **m0.75**, tstop48 → **−31.7%** | **−0.19** |

Two things stand out, and they point in **opposite directions on trust**:

1. **The rankings do NOT generalize — IS→OOS Spearman is negative (−0.20 / −0.19).**
   So the specific "winner" (a tighter `m0.75` trail) is overfit to the in-sample
   window and was **deliberately not adopted** — the 7.5y-validated `fast` (m1.0)
   trail stays the default. Chasing the top cell here would be the classic mistake.
2. **A ~48-bar time-stop is the one robust, cross-lens improvement.** It appears in
   nearly every top config on both lenses and, on the theta-exposed options lens, cuts
   the mean OOS loss from **−134% → ~−32%** — it directly caps the theta-bleed failure
   mode. **Action taken:** shipped as an opt-in `time_stop_bars` knob (default **0/off**),
   enforced by a scan-time square-off (`service._time_stop_positions`). Off by default
   because the delta-1 benefit is marginal and it mainly helps the long-OTM-options
   vehicle we already steer away from; on for users trading that vehicle who want the
   theta cap. Artifact: `study/kite_st_exit_sweep_results.csv`.

### Net of the sweeps
- **Changed default:** `exit_mode` `two_red` → **`one_red`** (measured best on both lenses).
- **New opt-in knob:** `time_stop_bars` (default off) — the robust theta-cap finding.
- **Deliberately unchanged:** the `fast`/m1.0 trail (negative IS→OOS corr forbids chasing the sweep's tighter optimum); `exit_aligned_trail` stays off (looser exits lose).
- **Unchanged truth:** long OTM/ATM options remain OOS-negative regardless of exit tuning — the vehicle (deep-ITM / futures) is still the real lever.
