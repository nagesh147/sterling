# A310 — Gamma Move, end to end

**Strategy ID** `gamma_move` · **Name** "Gamma Move" · **Contract version** A310.2
**Status** BUILT and CALIBRATED, 2026-08-26. Disabled, paper-only, behind the live gate.
**Sits beside** ATM Premium Imbalance — same engine/service/API/board/settings shape,
a peer entry in every registry, never a fork of it.

> ### Superseded in part — read [VALIDATION_REPORT.md](VALIDATION_REPORT.md) first
>
> This document was written as the build plan, before any code or data. It is
> kept because the architecture, the artifact manifest and the funnel argument
> in §3.1 all held up. Three things in it did not, and the report is the
> authority wherever they disagree:
>
> 1. **The three "UNSPECIFIED" gaps (U1/U2/U3) are now measured**, not guessed.
>    The values in §1's gap table and §2's rule text are the original guesses;
>    the shipped values are in `engines/gamma_move/config.py` and the report.
> 2. **The headline result is negative.** The entry triple on its own did not
>    separate from an unconditional baseline (24.7% [20.9,28.9] vs 21.7%
>    [21.5,21.9]). The measured edge is the level filter alone: 46.2%
>    [31.6,61.4]. §2.5 presents the trigger as the strategy's core; it is a
>    necessary condition at best.
> 3. **The regime multiplier default of 3.0 in §2.7 was actively harmful** —
>    measured at −3.3pp, i.e. the gate pointed the wrong way. Shipped at 2.0.

---

## 0. What this document is

A complete, artifact-by-artifact implementation plan: every file to create, every
existing file to edit, every contract (dataclass fields, function signatures,
JSON shapes, TypeScript types), the data path each rule depends on, the tests
that prove it, and the order to build it in.

It is written the way `A280_END_TO_END.md` is written for ATM Premium Imbalance,
because that engine is the template this one copies. Where this strategy needs
something ATM did not — a multi-symbol scanner, an open-interest time series, a
regime gate — the difference is called out and justified rather than smuggled in.

**Read §1 before anything else.** The single largest risk in this build is
that the source is a discretionary strategy from a podcast, and three of its
rules were never stated numerically. Those three are marked **UNSPECIFIED** and
default to *refuse to trade* rather than to a guessed number.

---

## 1. Provenance

### The source

| Field | Value |
|---|---|
| URL | `https://youtube.com/watch?v=W88GygpXZWI` |
| Title | *Ex-SEBI Officer + SEBI Registered Analyst: The Truth About IPOs, Options & Market Operators* |
| Channel | TradeAlphaGuru |
| Uploaded | 2026-06-27 |
| Duration | 76m 32s (4592 s) |
| Language | Hindi. Auto-captions in `hi` (original) and machine-translated `en`. |
| Strategy segment | roughly 27:00 – 43:00, the on-screen walkthrough |
| Presenter | referred to as "Vivek bhai" / "Abhineet bhai" by turns — the captions swap the two names repeatedly, so **no rule in this document is attributed to a named person.** |

The strategy is called **"Gamma Move"** (also "Gamma Blast") in the source. It is
described conversationally over a screen-share of Obstra and TradingView charts.
Worked examples shown on screen: **Biocon 400 CE (May)**, **Power India 35000 CE
(19th)**, **Fortis** (level marking only), and one more small-cap ("Sam Cap") entered
at ~75 and exited "around 11[0]".

Both caption tracks were pulled with `yt-dlp` and de-duplicated. Every numeric
claim below was **cross-checked against the Hindi original**, because the English
track mistranslates freely (it renders the presenter's name four different ways
and turns "VIX" into "Vicks", "Wicks" and "bix"). Where the two tracks disagree,
the Hindi wins and the discrepancy is noted.

### The thesis, in one paragraph

Option **sellers** write heavy open interest at a strike that sits on a spot
support or resistance level. When spot breaks through that level, those shorts
are being carried toward their stop. They cover. Short-covering removes open
interest and simultaneously bids the premium, and because the strike is now
going in-the-money its delta is also rising — so the premium accelerates far
faster than a delta-only model predicts. That acceleration *is* gamma. The trade
is to buy that option and hold for the acceleration, which the source says
arrives **in a single day, two at most**.

### The rules as stated

| # | Rule | Evidence | Status |
|---|---|---|---|
| R1 | Universe is **NSE F&O single stocks**, not indices. | Every worked example is a stock (Biocon, Power India, Fortis, Sun/"Sam Cap"). Screener described as "200 stocks". | STATED |
| R2 | Mark **support / resistance on the SPOT chart** by repeated rejection ("its top will be visible, then from here rejection… then here too stock came in and then down rejection"). | Hindi 1200–1230 | STATED, method qualitative |
| R3 | Spot must be trading **at or near** that level. "If he is somewhere in the middle then it will be of no use to me." | Hindi ~1128 | STATED, no distance given → **UNSPECIFIED (U1)** |
| R4 | At that level, select the strike with the **highest open interest**. May be "a couple of strikes up or down" from the exact level. | Hindi 1146, 1196, 1247, 1298 | STATED |
| R5 | **Resistance → CALL. Support → PUT.** "You will work on the support side there… and then I trade the put at that time." | Hindi 1467–1474 | STATED |
| R6 | Watch that option contract on a **15-minute chart**. | Hindi 1340: `ये मैं 15 मिनट के टाइम` | STATED |
| R7 | Entry needs **three simultaneous conditions**: (a) OI declining — "rapid decline or a decent percentage"; (b) volume **abnormal** versus its own normal; (c) the option's **price rising**. | Hindi 1313–1320, 1346–1348, 1441–1463 | STATED, thresholds **UNSPECIFIED (U2)** |
| R8 | Confirmation forms **within ~45 minutes** of the alert = 3 × 15-min bars. | Hindi 1476: `तो 45 मिनट में कंफर्म हो जाता` | STATED |
| R9 | Stop loss = the **swing low of the option's own premium** immediately before entry — explicitly *not* a spot level. "This is in that particular strike… I am not talking about that particular strike [spot]". | Hindi 1325–1331, 1403–1411 | STATED |
| R10 | **Expiry window**: do not trade at the start of the monthly contract. Only once "roughly 15 days have passed" — the last one or two weeks. Otherwise "OI won't behave that way". | Hindi 1508–1518 | STATED |
| R11 | **Hold 1 day, 2 maximum.** "If it's a gamma move it should come in a single day. One or two days max." Theta is accepted as the price of being near expiry. | Hindi 1520–1528 | STATED |
| R12 | **Regime filter** — the acknowledged flaw. In a corrective / downtrend market cycle the long-side trades stop working. Fix offered: "apply SuperTrend" so you trade with the market cycle. | Hindi 1556–1566 | STATED, parameters **UNSPECIFIED (U3)** |
| R13 | **Risk de-scaling**: after two or three consecutive losers, cut position sizing (1% → 0.5%) and scale back up only once consistency returns. | Hindi 1590–1615 | STATED |
| R14 | Setups are **rare**. `ट्रेड इसके बहुत कम मिलते हैं` — "you get very few trades in this". | Hindi 1507 | STATED |
| R15 | Screening shortcut: NSE publishes a runtime "declining in OI + increasing in price" list; start there, then chart the survivors. | Hindi 1480–1500 | STATED |

### The three gaps — and why they default to "refuse"

> **Superseded.** Every value in this table was replaced by a measured one on
> 2026-08-26. The shipped defaults are `level_proximity_pct = 1.0`,
> `min_oi_drop_pct = 3.0`, `volume_spike_mult = 2.5`, `min_price_gain_pct = 2.0`,
> `regime_period = 10`, `regime_multiplier = 2.0`. The reasoning below about
> *why each one is dangerous to guess* is what survived, and it is why they were
> measured rather than shipped as written.

| ID | What is missing | Why guessing is dangerous | Original guess |
|---|---|---|---|
| **U1** | How near is "near the level". | Too wide and every stock qualifies, which turns R3 off entirely and makes the whole funnel noise. | `level_proximity_pct = 1.0` (%), and the field **cannot be 0** — 0 would mean "exactly on the level", which never happens on a tick basis, so it would silently pass nothing. Validation refuses `<= 0`. |
| **U2** | The numeric thresholds for OI drop, volume spike and price gain. | This *is* the entry. A too-loose triple fires on ordinary noise; a too-tight one never fires and the engine looks broken rather than selective. | `min_oi_drop_pct = 5.0`, `volume_spike_mult = 2.0`, `min_price_gain_pct = 2.0`. All three **must be > 0**. These are *starting points for calibration, not observed values* — the doc says so, the config docstring says so, and the board shows a `UNCALIBRATED` badge until a replay run has been recorded. |
| **U3** | SuperTrend period and multiplier, and which timeframe it runs on. | A regime filter with the wrong period inverts: it will confirm exactly the trades it was added to block. | `regime_timeframe = "day"`, `regime_period = 10`, `regime_multiplier = 3.0` — the platform's existing SuperTrend defaults, so the number is at least sourced from something rather than invented here. |

> **The recurring failure mode this table exists to prevent.** In this codebase a
> filter has twice been disabled by an out-of-range config value that *also*
> broke the arithmetic downstream of it (see the NIFTY ORB notes). Every
> threshold above is validated with an explicit lower bound, and `0` never means
> "off" for any of them. Where a rule genuinely can be switched off, it gets its
> own boolean.

### What the source never specifies at all

- **No exit rule.** The examples say "2x here", "goes back to 1800, around 2x-3x",
  "I enter at 75… went around 11[0]" — realised multiples, never a rule that
  produced them. The exit is discretionary in the source.
  **Implementation:** the engine ships a `TIME_STOP` exit (R11's 1–2 days) as the
  only exit that is actually sourced, plus optional `PERCENT_TARGET` and
  `TRAILING_STOP` policies that are clearly labelled **OURS**, not observed.
- **No win rate, no sample size, no losing example.** Four winners were shown.
  Four winners establish nothing: a coin-flip strategy shows four straight
  winners about one time in sixteen.
- **No slippage or cost model.** Stock-option spreads at these premiums are wide;
  a 2x on the mid is not a 2x on the fill.

---

## 2. The contract (A310.1)

Written as the engine will implement it. **OBSERVED** = stated in the source.
**OURS** = added by this build, with the reason.

### 2.1 Universe — OBSERVED (R1)

Scan NSE F&O **single-stock** underlyings. Indices are excluded by default
(`include_indices = False`): every worked example is a stock, and the mechanism —
identifiable sellers pinned at one strike on a level — is weaker on an index where
OI is spread across many strikes and participants.

Liquidity floor (**OURS**): a candidate contract must clear
`min_option_oi`, `min_option_volume` and `max_spread_pct` before it can be
watched. The source scanned "200 stocks" with no liquidity qualification; a
2x on a contract you cannot exit is not a 2x.

### 2.2 Level identification — OBSERVED (R2, R3)

On the underlying's spot series at `level_timeframe` (default `day`), find swing
pivots: a bar whose high is the highest of the `pivot_lookback` bars either side
is a **resistance pivot**; the mirror is a **support pivot**. Cluster pivots whose
prices are within `level_cluster_pct` of each other into one level, and score the
level by how many pivots it contains (the source's "rejection… then rejection
again" is a touch count).

A level is **live** for today if `abs(spot - level) / level * 100 <= level_proximity_pct` (U1).

> This is the one place the source is qualitative and the implementation is
> mechanical. The doc-string on `levels.py` must say so: the engine is asserting
> a *specific* definition of "resistance" that the source only gestured at.

### 2.3 Strike selection — OBSERVED (R4, R5)

For each live level, take the option chain for the selected expiry and choose the
**highest-OI strike** among strikes within `strike_window_pct` of the level price.
Direction follows the level kind:

| Level | Option | Thesis |
|---|---|---|
| resistance | **CE** | spot breaks up; call writers cover |
| support | **PE** | spot breaks down; put writers cover |

Ties on OI break toward the strike nearest the level.

### 2.4 Expiry window — OBSERVED (R10)

`days_to_expiry` must satisfy `min_days_to_expiry <= dte <= max_days_to_expiry`,
default `1` and `14`. The lower bound is **OURS**: on expiry day itself the OI
signal degenerates into settlement mechanics and the premium is nearly all gamma
already, which is a different trade. The upper bound is the source's "roughly 15
days have passed".

`max_days_to_expiry = 0` is **rejected by validation**, not treated as "no limit".

### 2.5 Entry trigger — OBSERVED shape (R6, R7, R8), thresholds now MEASURED (U2)

> **Read this first.** On 167,253 real bars this triple, evaluated on its own,
> did **not** separate from the unconditional population. It is a necessary
> condition, not a sufficient one, and the caller must apply 2.2's level filter
> before treating a trigger as a setup. See the validation report §2.1.

Evaluated on the **option contract's own** 15-minute series
`(close, volume, oi)`, indexed `t` = the most recently closed bar:

```
oi_drop_pct     = (oi[t-1] - oi[t]) / oi[t-1] * 100
volume_ratio    = volume[t] / mean(volume[t-volume_lookback .. t-1])
price_gain_pct  = (close[t] - close[t-1]) / close[t-1] * 100

unwinding = oi_drop_pct    >= min_oi_drop_pct        # (a)
abnormal  = volume_ratio   >= volume_spike_mult      # (b)
rising    = price_gain_pct >= min_price_gain_pct     # (c)

triggered = unwinding and abnormal and rising
```

`confirm_bars` (default `1`, max `3`) consecutive triggered bars are required.
R8's "confirms in 45 minutes" is 3 bars — available as `confirm_bars = 3` for the
stricter reading, but 1 is the default because the worked examples all enter on
the bar where the three conditions first coincide.

Guards that must also hold at the moment of entry (**OURS**):
- `oi[t-1] > 0` — a zero prior OI makes `oi_drop_pct` undefined, not infinite.
- at least `volume_lookback + 2` bars of history exist.
- every bar in the window is from **today's session** — a series stitched across
  a session boundary produces a fake OI collapse at the seam every single day.
- the regime gate (2.7) agrees with the direction.

### 2.6 Stop — OBSERVED (R9)

`stop = min(low[t-swing_lookback .. t])` on the **option's own** premium series,
default `swing_lookback = 6` bars (90 minutes). Explicitly the option chart, not
spot. If that low is `>= entry`, the setup is rejected rather than entered with an
inverted stop.

Percent basis is also offered (`stop_basis = PERCENT`) and is **required in live
mode**, for the same reason ATM Premium Imbalance requires it: these premiums run
from ₹5 to ₹600, so a points stop is a 4% risk at one end and a 100% risk at the
other.

### 2.7 Regime gate — OBSERVED intent (R12), OURS parameters (U3)

> **Superseded default.** `regime_multiplier` shipped at **2.0**, not the 3.0
> below. At 3.0 the gate measured *inverted* at three of four periods — agreeing
> with it was worse than fighting it. See the validation report §2.4.

SuperTrend on the **underlying spot** at `regime_timeframe`, using the existing
`app.engines.indicators.supertrend`. CE trades require SuperTrend **up**; PE
trades require SuperTrend **down**. `regime_enabled = True` by default — the
source names this as the flaw that broke the strategy, so shipping with it off
would be shipping the known bug.

### 2.8 Exit — MOSTLY OURS

| Policy | Rule | Source |
|---|---|---|
| `TIME_STOP` *(default)* | Exit at `max_hold_days` (default `2`) trading days after entry, or at `session_end` on the final day. | OBSERVED (R11) |
| `PERCENT_TARGET` | Exit at `entry * (1 + target_pct/100)`. | **OURS.** The 2x/3x figures in the source are outcomes, not a rule. |
| `TRAILING_STOP` | Ratchet a stop `trail_pct` below the running high, arming after `trail_start_pct` of profit. | **OURS.** |

All policies additionally honour the R9 stop and, if `close_at_session_end`, flatten
at `session_end`.

### 2.9 Risk — OURS, except R13

- `risk_per_trade_pct` of deployable capital, sized to the distance between entry
  and the R9 stop.
- **De-scaling (R13, OBSERVED):** after `descale_after_losses` consecutive losing
  trades (default `3`), multiply risk by `descale_factor` (default `0.5`). Restore
  full size after `rescale_after_wins` consecutive winners (default `2`).
- `max_concurrent_positions` (default `3`), `max_new_trades_per_day` (default `2`),
  `max_premium_at_risk_inr`, `daily_loss_limit_inr`.
- `enabled = False` and `execution_mode = "paper"` by default. Nothing here has
  been through a walk-forward.

---

## 3. Feasibility — can this platform actually see open interest?

This is the question the whole build turns on, and the answer was not obvious.
The project's own working notes record that **Kite's option-chain quote path has
no `change_in_oi` and no intraday OI history**, and that the existing OI Change
tab therefore computes ΔOI on the frontend against a `localStorage` day-baseline.
If that were the only OI available, R7 would be unimplementable and this document
would end here.

It is not the only path. Three distinct OI sources exist in the codebase today:

| # | Source | Where | Gives | Verified at |
|---|---|---|---|---|
| 1 | **Historical candles with OI** | `KiteClient.get_historical(token, interval, frm, to, continuous, oi)` sends `oi=1` to `/instruments/historical/{token}/{interval}`. Kite returns `[ts, o, h, l, c, volume, oi]` per candle for F&O instruments. | The **15-minute (close, volume, oi) series on an option contract** — exactly R6+R7. | `backend/app/services/exchanges/kite/client.py:545-552` |
| 2 | **Live tick OI** | The binary KiteTicker parser reads `oi`, `oi_day_high`, `oi_day_low` out of MODE_FULL packets. | Live OI per tick, for the currently-forming bar and for the exit monitor. | `backend/app/services/exchanges/kite/ticker.py:99-101` |
| 3 | **Bulk quote OI** | `/quote` returns `oi` per instrument; already mapped in the client. | A **chain-wide OI snapshot in one call**, up to 500 instruments — exactly R4's "which strike has the most OI". | `backend/app/services/exchanges/kite/client.py:934` |

Source 1 is already plumbed through to an HTTP endpoint that forwards the flag
(`backend/app/api/v1/endpoints/kite.py:760`), so nothing new is needed at the
transport layer. **The strategy is implementable as specified.**

> Correction worth recording: the "Kite has no intraday OI" note is true of the
> *option-chain view* and the bulk-quote path used by the OI tabs. It is not true
> of the historical-candles API. Both statements need to coexist or this gets
> re-litigated on the next engine.

### 3.1 The rate-limit problem, and the funnel that solves it

Kite's historical API allows roughly **3 requests/second**. A naive design —
"pull 15-min OI candles for every strike of every F&O stock" — is ~180 stocks ×
~10 strikes = 1,800 requests = **10 minutes per scan cycle**, which cannot run on
a 15-minute cadence and would starve every other consumer of the same budget.

The fix is that R3, R4 and R10 are all *filters that run on cheaper data*. Apply
them first and the expensive call happens a few dozen times, not 1,800:

```
STAGE A — Levels                       cost: ~180 daily-candle requests, ONCE per day
  for each F&O underlying:
    daily spot candles (cached; the data lake already holds these)
    -> swing pivots -> clustered levels
    -> keep only names where spot is within level_proximity_pct of a level   (R3)
  typical survivors: 10-25 names

STAGE B — Strikes                      cost: 1-2 bulk /quote calls TOTAL
  for the survivors:
    NFO instrument dump (already cached, 15-min TTL, shared with ATM's BFO path)
    -> strikes within strike_window_pct of the level, expiry passing R10
    -> ONE bulk /quote over all of them (<=500 instruments per call) -> oi per strike
    -> highest-OI strike per name                                          (R4, R5)
  typical survivors: 10-25 contracts

STAGE C — Trigger watch                cost: ~25 historical requests per 15-min bar
  for each selected contract:
    get_historical(token, "15minute", today, oi=True)
    -> evaluate the R7 triple on the last closed bar
    -> subscribe MODE_FULL ticks for the forming bar and for exits
```

Stage C at 25 contracts is **~9 seconds** of the historical budget per 15-minute
bar. That is the whole reason the funnel is ordered this way, and reordering it
is a performance regression that will not look like one in review.

**Pacing:** use **minimum-spacing pacing** (a monotonic "not before
`last_call + 1/rate`" gate), *not* a token bucket. A bucket with a burst
allowance will empty itself into Kite in the first second of every cycle and eat
429s for the rest of it — this has already been learned once, in the kitelake
downloader, whose `kitelake/ratelimit.py::PacedRateLimiter` says so in its own
module docstring. Reuse it rather than writing a second one.

### 3.2 Session-boundary correctness

Open interest resets its *meaning* daily: it is a cumulative outstanding figure
that is republished each session, and Kite's own candle series carries the value
at the close of each bar. Two failure modes must be closed explicitly:

1. **Do not stitch across sessions.** Computing `oi[t-1] - oi[t]` across a
   session boundary compares yesterday's last bar with today's first and produces
   a large phantom "unwind" at 09:15 **every single day**. The engine must slice
   the series to today's session before evaluating, and refuse if fewer than
   `volume_lookback + 2` of today's bars exist.
2. **Volume is per-bar in candles, cumulative in ticks.** Candle `volume` is the
   bar's own traded quantity; a tick's `volume_traded` is the day's running total.
   The forming-bar builder must difference the tick figure against the day total
   at the bar's open. Mixing the two makes `volume_ratio` enormous and constant,
   which turns condition (b) permanently true — i.e. silently removes one third
   of the entry rule.

### 3.3 What this does *not* give us

- **No historical OI before the data lake's coverage.** Kite's historical window
  for expired option contracts is limited, and expired contracts drop out of the
  instrument dump entirely. A backtest across many expiries therefore needs the
  contracts captured *while they were live* — see §8's replay note. The honest
  statement is: **this engine can be forward-tested from the day it ships, and
  back-tested only over whatever the data lake already holds.**
- **No bid/ask depth in the candle path.** `max_spread_pct` can only be evaluated
  from a live quote, so it is an entry-time guard, never a backtest filter.

---

## 4. Artifact manifest

Every file, in dependency order. **NEW** = create. **EDIT** = a named change to an
existing file. Line counts are estimates for planning, not targets.

### Backend — engine (pure strategy mathematics, no broker, no socket, no clock)

| # | Artifact | Kind | ~LoC | Purpose |
|---|---|---|---|---|
| B1 | `backend/app/engines/gamma_move/__init__.py` | NEW | 60 | Package exports, `STRATEGY_ID`, `STRATEGY_NAME`, `CONTRACT_VERSION = "A310.1"` |
| B2 | `backend/app/engines/gamma_move/config.py` | NEW | 420 | `GammaMoveConfig` frozen dataclass + vocabularies + `validate()` |
| B3 | `backend/app/engines/gamma_move/models.py` | NEW | 340 | `Candle`, `OICandle`, `SpotLevel`, `StrikeCandidate`, `GammaSignal`, `TriggerMetrics`, `PositionState`, `TradeRecord`, `ExitEvent` |
| B4 | `backend/app/engines/gamma_move/levels.py` | NEW | 170 | Swing-pivot detection, clustering, proximity test (2.2) |
| B5 | `backend/app/engines/gamma_move/selection.py` | NEW | 190 | Expiry choice (R10), strike window, highest-OI pick, direction from level kind (2.3, 2.4) |
| B6 | `backend/app/engines/gamma_move/trigger.py` | NEW | 200 | The R7 triple, `confirm_bars`, session-slice guard, `TriggerMetrics` (2.5) |
| B7 | `backend/app/engines/gamma_move/regime.py` | NEW | 90 | SuperTrend gate, wrapping `app.engines.indicators.supertrend` (2.7) |
| B8 | `backend/app/engines/gamma_move/exit.py` | NEW | 230 | Swing-low stop, time stop, percent target, trailing ladder (2.6, 2.8) |
| B9 | `backend/app/engines/gamma_move/sizing.py` | NEW | 160 | Risk-per-trade sizing in lots, the R13 de-scaling ladder (2.9) |
| B10 | `backend/app/engines/gamma_move/strategy.py` | NEW | 520 | `GammaMoveStrategy` state machine: `Phase`, `Intent`, `evaluate()`, `on_bar()`, `on_tick()` |
| B11 | `backend/app/engines/gamma_move/replay.py` | NEW | 300 | Bar-by-bar replay over stored OI candles; no broker |

### Backend — services (plumbing: broker, persistence, scheduling)

| # | Artifact | Kind | ~LoC | Purpose |
|---|---|---|---|---|
| B12 | `backend/app/services/gamma_move.py` | NEW | 380 | Config load/persist, `descriptor()`, `snapshot(uid)`, NFO dump cache, instrument resolution |
| B13 | `backend/app/services/gamma_move_scanner.py` | NEW | 420 | Stages A/B/C of §3.1, the minimum-spacing pacer, candidate cache |
| B14 | `backend/app/services/gamma_move_runner.py` | NEW | 520 | Per-user session, `scan_once()`, `auto_scan_loop()`, tick handling, arm/adopt, orphan detection, subscription ownership |
| B15 | `backend/app/services/gamma_move_replay.py` | NEW | 220 | Fetches historical OI candles and drives B11 |
| B16 | `backend/app/services/gamma_move_sim.py` | NEW | 180 | Operator-facing simulation, mirroring `atm_premium_imbalance_sim` |

### Backend — API

| # | Artifact | Kind | Change |
|---|---|---|---|
| B17 | `backend/app/api/v1/endpoints/config.py` | **EDIT** | Append the `/gamma-move*` route block (§6.1) |
| B18 | `backend/main.py` | **EDIT** | Register `gamma_move_runner.auto_scan_loop` in startup and cancel it in shutdown (§6.2) |

### Frontend

| # | Artifact | Kind | ~LoC | Purpose |
|---|---|---|---|---|
| F1 | `frontend/src/hooks/useGammaMove.ts` | NEW | 260 | Config + snapshot queries, mutations, all TS types |
| F2 | `frontend/src/components/GammaMoveSettings.tsx` | NEW | 420 | The settings form itself |
| F3 | `frontend/src/components/kite/GammaMoveSettingsPanel.tsx` | NEW | 12 | Kite-shell wrapper, exactly as `AtmPremiumImbalanceSettingsPanel` |
| F4 | `frontend/src/components/kite/board/gammaMoveAdapter.ts` | NEW | 300 | `snapshot -> BoardSignal[]` |
| F5 | `frontend/src/components/kite/board/GammaMoveBoard.tsx` | NEW | 180 | The signal table |
| F6 | `frontend/src/components/kite/board/boardTypes.ts` | **EDIT** | +6 | `EngineId`, `ENGINE_LABEL`, `ENGINE_TAG` |
| F7 | `frontend/src/components/kite/config/registry.ts` | **EDIT** | +90 | `SectionId`, `SECTION_IDS`, field definitions |
| F8 | `frontend/src/components/kite/ConnectPane.tsx` | **EDIT** | +8 | Icon, section entry, panel render |
| F9 | `frontend/src/components/kite/AdaptiveEdgeRightSidebar.tsx` | **EDIT** | +8 | `NAV_TARGET`, snapshot hook, tab, board render |

### Tests

| # | Artifact | Kind | Covers |
|---|---|---|---|
| T1 | `backend/tests/engines/gamma_move/__init__.py` | NEW | — |
| T2 | `…/test_config.py` | NEW | Every `validate()` branch; U1/U2/U3 lower bounds; live-mode gate |
| T3 | `…/test_levels.py` | NEW | Pivot detection, clustering, proximity |
| T4 | `…/test_selection.py` | NEW | Expiry window (R10), strike window, OI tie-break, direction mapping |
| T5 | `…/test_trigger.py` | NEW | The R7 triple; each condition failing alone; `confirm_bars`; **session-boundary phantom unwind**; `oi[t-1] == 0` |
| T6 | `…/test_regime.py` | NEW | CE blocked in downtrend, PE blocked in uptrend, gate disabled |
| T7 | `…/test_exit.py` | NEW | Swing-low stop, inverted-stop rejection, time stop across days, trailing ladder |
| T8 | `…/test_sizing.py` | NEW | Lot rounding, caps, de-scale/rescale ladder (R13) |
| T9 | `…/test_strategy.py` | NEW | Full state machine, one trade end to end |
| T10 | `…/test_replay.py` | NEW | Replay reproduces the same decisions as live evaluation |
| T11 | `…/test_properties.py` | NEW | Property tests: no signal without all three conditions; stop always below entry |
| T12 | `backend/tests/services/test_gamma_move_scanner.py` | NEW | Funnel ordering, pacer spacing, request-count ceiling |
| T13 | `backend/tests/services/test_gamma_move_runner.py` | NEW | Arm, orphan detection, subscription release, daily caps |
| T14 | `backend/tests/api/test_gamma_move_api.py` | NEW | All six routes, 422 on unknown key, defaults/vocabularies published |
| T15 | `frontend/…/board/__tests__/GammaMoveBoard.test.tsx` | NEW | Rows, empty state, statuses |
| T16 | `frontend/…/board/__tests__/gammaMove.test.ts` | NEW | Adapter mapping, null levels render as "—" |
| T17 | `frontend/…/__tests__/GammaMoveSettings.test.tsx` | NEW | Form renders, mutation payloads, research-only greying |
| T18 | `frontend/…/kite/__tests__/registry.sections.test.ts` | **EDIT** | Add `gammaMove` to the expected section list |

### Docs

| # | Artifact | Kind |
|---|---|---|
| D1 | `docs/strategy/gamma-move/A310_END_TO_END.md` | this document |
| D2 | `docs/strategy/gamma-move/README.md` | NEW — index + one-paragraph summary |
| D3 | `docs/strategy/gamma-move/A311_RUNBOOK.md` | NEW — arm, monitor, recover, kill |
| D4 | `docs/strategy/gamma-move/VALIDATION_REPORT.md` | NEW — written *after* the first replay run, never before |

**Totals: 33 new files, 6 edited files.**

---

## 5. Backend contracts, artifact by artifact

### B2 — `engines/gamma_move/config.py`

```python
STRATEGY_ID       = "gamma_move"
LEVEL_TIMEFRAMES  = frozenset({"day", "60minute", "15minute"})
TRIGGER_TIMEFRAMES= frozenset({"15minute", "5minute", "30minute"})
EXIT_POLICIES     = frozenset({"TIME_STOP", "PERCENT_TARGET", "TRAILING_STOP"})
STOP_BASES        = frozenset({"POINTS", "PERCENT"})
SIZING_MODES      = frozenset({"LOTS", "RISK_PCT"})
PROTECTION_MODES  = frozenset({"NONE", "GTT", "RESTING_STOP_LIMIT"})
DATA_SOURCES      = frozenset({"kite"})
EXECUTION_MODES   = frozenset({"paper", "live"})

#: Thresholds with no observed value. Published so the API can badge them and the
#: board can show UNCALIBRATED until a replay run exists.
UNCALIBRATED_FIELDS = frozenset({
    "level_proximity_pct", "min_oi_drop_pct", "volume_spike_mult",
    "min_price_gain_pct", "regime_period", "regime_multiplier",
})

@dataclass(frozen=True)
class GammaMoveConfig:
    enabled: bool = False

    # --- universe (2.1) ----------------------------------------------------
    include_indices: bool = False
    max_universe: int = 200
    explicit_symbols: tuple[str, ...] = ()      # empty = whole F&O stock list
    min_option_oi: int = 50_000
    min_option_volume: int = 1_000
    max_spread_pct: float = 3.0

    # --- levels (2.2) ------------------------------------------------------
    level_timeframe: str = "day"
    level_lookback_days: int = 120
    pivot_lookback: int = 5
    level_cluster_pct: float = 0.75
    min_level_touches: int = 2
    level_proximity_pct: float = 1.0            # U1 — must be > 0

    # --- strike (2.3) ------------------------------------------------------
    strike_window_pct: float = 2.0
    max_candidates: int = 25

    # --- expiry (2.4) ------------------------------------------------------
    min_days_to_expiry: int = 1
    max_days_to_expiry: int = 14                # must be > 0; not "0 = off"

    # --- trigger (2.5) -----------------------------------------------------
    trigger_timeframe: str = "15minute"
    volume_lookback: int = 20
    min_oi_drop_pct: float = 5.0                # U2 — must be > 0
    volume_spike_mult: float = 2.0              # U2 — must be > 0
    min_price_gain_pct: float = 2.0             # U2 — must be > 0
    confirm_bars: int = 1                       # 1..3

    # --- regime (2.7) ------------------------------------------------------
    regime_enabled: bool = True
    regime_timeframe: str = "day"
    regime_period: int = 10                     # U3
    regime_multiplier: float = 3.0              # U3

    # --- stop (2.6) --------------------------------------------------------
    stop_basis: str = "PERCENT"
    swing_lookback: int = 6
    stop_percent: float = 30.0
    stop_points: float = 0.0

    # --- exit (2.8) --------------------------------------------------------
    exit_policy: str = "TIME_STOP"
    max_hold_days: int = 2                      # R11; must be >= 1
    target_pct: float = 0.0                     # OURS; 0 = no target
    trail_pct: float = 0.0
    trail_start_pct: float = 0.0
    close_at_session_end: bool = False
    protection_mode: str = "NONE"

    # --- session -----------------------------------------------------------
    session_start: str = "09:30"                # after the opening auction
    session_end: str = "15:15"
    scan_interval_seconds: int = 300

    # --- risk (2.9) --------------------------------------------------------
    sizing_mode: str = "RISK_PCT"
    risk_per_trade_pct: float = 1.0
    lots: int = 0
    max_concurrent_positions: int = 3
    max_new_trades_per_day: int = 2
    max_premium_at_risk_inr: float = 25_000.0
    daily_loss_limit_inr: float = 10_000.0
    descale_after_losses: int = 3               # R13
    descale_factor: float = 0.5                 # R13
    rescale_after_wins: int = 2                 # R13

    # --- plumbing ----------------------------------------------------------
    data_source: str = "kite"
    execution_mode: str = "paper"
```

**`validate()` must enforce, at minimum:**

- every vocabulary membership;
- `level_proximity_pct > 0`, `min_oi_drop_pct > 0`, `volume_spike_mult > 1.0`,
  `min_price_gain_pct > 0` — **U2's whole point: none of these may be zero**;
- `0 <= min_days_to_expiry < max_days_to_expiry`, and `max_days_to_expiry > 0`;
- `1 <= confirm_bars <= 3`; `volume_lookback >= 5`; `pivot_lookback >= 2`;
- `swing_lookback >= 2`; `max_hold_days >= 1`;
- `0 < descale_factor <= 1`; `descale_after_losses >= 1`;
- `session_start < session_end`;
- `stop_percent < 100` — a 100% stop *is* the premium;
- **live-mode gate**, mirroring ATM's:
  - `stop_basis == "PERCENT"` (premium range argument, 2.6);
  - `protection_mode != "NONE"` — a dropped socket must not leave a long naked;
  - a size must actually be set;
  - `execution_mode == "live"` is refused entirely while
    `live_ready is False` in the descriptor (§8).

Helpers: `as_dict()`, `field_names()`, `stop_distance_inr(reference)`,
`effective_lots(...)`, `sizing_blocker(lot_size)` — one function both the board
and `arm()` call, so they cannot disagree.

### B3 — `engines/gamma_move/models.py`

```python
@dataclass(frozen=True)
class OICandle:
    ts_ms: int; open: float; high: float; low: float
    close: float; volume: int; oi: int

@dataclass(frozen=True)
class SpotLevel:
    price: float
    kind: Literal["support", "resistance"]
    touches: int
    last_touch_ms: int
    distance_pct: float          # signed: spot vs level

@dataclass(frozen=True)
class StrikeCandidate:
    underlying: str
    level: SpotLevel
    instrument: InstrumentRef    # token, tradingsymbol, strike, expiry, lot_size, tick_size
    option_type: Literal["CE", "PE"]
    oi: int
    days_to_expiry: int

@dataclass(frozen=True)
class TriggerMetrics:
    oi_drop_pct: float; volume_ratio: float; price_gain_pct: float
    unwinding: bool; abnormal: bool; rising: bool
    bars_confirmed: int
    def triggered(self) -> bool: ...

@dataclass(frozen=True)
class GammaSignal:
    id: str
    candidate: StrikeCandidate
    metrics: TriggerMetrics
    state: Literal["watching", "armed", "running", "weakening", "ended", "error"]
    entry: float | None; stop: float | None; target: float | None
    trail: float | None; ltp: float | None; exit_price: float | None
    lots: int | None; quantity: int | None
    at_ms: int
    reason: str | None           # never None for watching/error
    regime: Literal["up", "down", "unknown"]
    uncalibrated: bool           # true while no VALIDATION_REPORT exists
    def as_dict(self) -> dict: ...
```

> `reason` being mandatory for `watching` and `error` is not decoration. A board
> row that declines to trade and will not say why is the single most-repeated
> defect in this codebase's engines.

### B6 — `engines/gamma_move/trigger.py`

```python
def slice_session(candles: Sequence[OICandle], session_day_ms: int) -> list[OICandle]:
    """Today's bars only. Guards the phantom-unwind-at-09:15 bug (§3.2)."""

def evaluate_trigger(
    candles: Sequence[OICandle], cfg: GammaMoveConfig,
) -> TriggerMetrics | None:
    """None when there is not enough of today's history to judge — never a
    fabricated zero-metrics 'no signal', which reads identically to a real one."""
```

### B7 — `engines/gamma_move/regime.py`

```python
def regime_of(spot: Sequence[Candle], cfg: GammaMoveConfig) -> Literal["up","down","unknown"]:
    """SuperTrend direction on the underlying. `unknown` when there are fewer
    than regime_period + 1 bars — and `unknown` BLOCKS, it does not pass."""

def regime_allows(regime, option_type, cfg) -> bool: ...
```

### B10 — `engines/gamma_move/strategy.py`

`Phase`: `idle → scanning → watching → armed → entering → in_position → exiting →
done | halted`.
`Intent`: `NONE | ENTER | EXIT | HALT`.

`GammaMoveStrategy.evaluate(now_ms, candidates, bars, spot, positions) -> Intent`
is pure: it takes data and returns an intent, and never touches a broker. The
runner (B14) is the only thing that turns an intent into an order. This is what
makes B11's replay exercise the same code the live path uses.

### B12 — `services/gamma_move.py`

Mirrors `services/atm_premium_imbalance.py` one-for-one:

```python
_CONFIG_KEY = "gamma_move_config"
_DUMP_TTL_S = 900.0                      # NFO dump, same TTL as ATM's BFO dump

def get_config() -> GammaMoveConfig          # invalid stored row -> disabled defaults, logged
def set_config(values: dict) -> GammaMoveConfig   # unknown key -> ValueError, never ignored
async def _nfo_dump(uid) -> list[dict]       # cached; client.search_instruments("", "NFO", ...)
async def resolve_contract(uid, underlying, strike, expiry, option_type) -> InstrumentRef
def descriptor() -> dict
async def snapshot(uid) -> dict
```

`descriptor()`:

```python
{
  "id": "gamma_move",
  "name": "Gamma Move",
  "contract_version": "A310.1",
  "tagline": "Buys the option that short-sellers are covering at a level.",
  "how_it_works": (
    "Finds F&O stocks trading at a support or resistance level, picks the strike "
    "carrying the most open interest there, and buys it when open interest falls, "
    "volume spikes and the premium rises together on the same 15-minute bar — the "
    "signature of option writers covering. Holds one to two days."
  ),
  "provenance": "Transcribed from a public podcast walkthrough; see docs/strategy/gamma-move/",
  "live_ready": False,
  "uncalibrated": ["level_proximity_pct", "min_oi_drop_pct", "volume_spike_mult",
                   "min_price_gain_pct", "regime_period", "regime_multiplier"],
}
```

**`snapshot(uid)` returns** — the shape F4 adapts:

```jsonc
{
  "strategy": { ...descriptor, "enabled": bool },
  "config":   { ...GammaMoveConfig },
  "scan": {
    "last_run_ms": 1756... , "next_run_ms": 1756...,
    "stage_a": { "scanned": 187, "near_level": 19, "cached": true },
    "stage_b": { "chains_quoted": 19, "candidates": 14 },
    "stage_c": { "watched": 14, "triggered": 1,
                 "historical_requests": 14, "budget_seconds": 4.7 }
  },
  "candidates": [ { ...GammaSignal.as_dict() } ],
  "positions":  [ { ...GammaSignal.as_dict() } ],
  "record": { "trades": 0, "verdict": "no realised trades yet" },
  "orphan_positions": [],
  "blockers": [ "strategy disabled", "no VALIDATION_REPORT — thresholds uncalibrated" ]
}
```

`blockers` is a list of plain sentences, exactly as ATM's is, because that list is
what the board renders when nothing is happening.

### B13 — `services/gamma_move_scanner.py`

Implements §3.1 verbatim. Public surface:

```python
async def scan_levels(uid, cfg) -> dict[str, list[SpotLevel]]   # Stage A, cached per day
async def scan_strikes(uid, cfg, levels) -> list[StrikeCandidate]  # Stage B, bulk /quote
async def scan_triggers(uid, cfg, candidates) -> list[GammaSignal] # Stage C, paced historical
async def scan_once(uid, cfg) -> list[GammaSignal]              # A -> B -> C
```

Non-negotiables in this file:

- **Minimum-spacing pacer, not a token bucket** (§3.1). Reuse
  `kitelake/ratelimit.py::PacedRateLimiter`, which already guarantees a minimum
  spacing of `1/rate` between calls and exists because a bucket did not.
- **Never call `build_client()` on this path.** Use
  `kite_accounts.acquire_client(acct)` — the client cache exists precisely because
  a per-scan client build was a measured hot-path regression.
- Stage A results are cached per `(uid, trading-day)`; Stage B per
  `(uid, trading-day, hour)`; Stage C is never cached.
- Every truncation (`max_universe`, `max_candidates`) must `log.info` what was
  dropped. Silent truncation reads as "covered everything" when it did not.

### B14 — `services/gamma_move_runner.py`

Mirrors `atm_premium_imbalance_runner.py`, with a multi-position session instead
of a single-pair one:

```python
async def scan_once(uid) -> dict
async def auto_scan_loop(interval: int = 300) -> None
async def on_ticks(uid, ticks, broker=None) -> str
async def arm(uid, signal_id) -> dict
async def adopt(uid, symbol, quantity, entry_price) -> dict
async def orphan_positions(uid, cfg) -> list[dict]
def session_status(uid) -> dict | None
async def release_subscriptions(session) -> None
def clear(uid=None) -> None
```

Two invariants carried over from earlier engines and easy to lose here:

1. **Subscription ownership is tagged and refcounted.** Claim tick subscriptions
   under this strategy's owner tag and release only that tag. An untagged release
   will pull ticks out from under the protection monitor for an unrelated engine.
2. **One `_exiting` claim per position.** Every exit path — target, stop, time
   stop, session end, manual — must take the same claim before sending an order,
   or two paths will both exit the same position.

### B15/B16 — replay and simulation

`gamma_move_replay.py` fetches `get_historical(..., oi=True)` for a chosen
contract and date range and drives `engines/gamma_move/replay.py`. It writes
nothing to the trade journal. `gamma_move_sim.py` exposes the operator-facing
run/stop pair, and its output is stamped `simulation` so the board can never
render replayed numbers as live ones — the same rule ATM's board follows.

---

## 6. API and wiring

### 6.1 `backend/app/api/v1/endpoints/config.py` — **EDIT**, append

Six routes, matching the ATM block's structure and docstring style:

| Method | Path | Returns |
|---|---|---|
| `GET` | `/config/gamma-move` | `{strategy, config, defaults, vocabularies, research_only, live_requires, uncalibrated}` |
| `PUT` | `/config/gamma-move` | `{config}` — partial update; **unknown key → 422**, never a silent drop |
| `GET` | `/config/gamma-move/snapshot` | B12's `snapshot(uid)` |
| `POST` | `/config/gamma-move/scan` | `{scanned, candidates:[…]}` — on-demand scan |
| `POST` | `/config/gamma-move/arm` | arms one candidate by id |
| `POST` | `/config/gamma-move/adopt` | adopts an orphan position |
| `POST` | `/config/gamma-move/simulate` · `/simulate/stop` | replay control |

`GET` publishes **defaults and vocabularies from the engine**, never a second copy
in the client. This is the codebase's most-repeated bug class — a UI claiming
backend behaviour the backend does not honour — and publishing is the fix that
already works for ATM.

Snapshot/scan/arm/adopt take `user: UserContext = Depends(get_current_user)` and
raise 401 without a uid. **Do not skip the `uid=`**: the daily-loss breaker has
previously failed open for engines that did not pass one.

### 6.2 `backend/main.py` — **EDIT**

Beside the existing ATM registration (~line 1540):

```python
from app.services.gamma_move_runner import auto_scan_loop as _gamma_move_scan
gamma_move_task = asyncio.create_task(_gamma_move_scan(interval=300))
```

…and cancel `gamma_move_task` in the shutdown block with the others.

---

## 7. Frontend contracts, artifact by artifact

### F1 — `hooks/useGammaMove.ts`

```ts
const KEY          = ['gamma-move-config'];
const SNAPSHOT_KEY = ['gamma-move-snapshot'];

export type LevelTimeframe   = 'day' | '60minute' | '15minute';
export type TriggerTimeframe = '15minute' | '5minute' | '30minute';
export type ExitPolicy       = 'TIME_STOP' | 'PERCENT_TARGET' | 'TRAILING_STOP';
export type StopBasis        = 'POINTS' | 'PERCENT';
export type SizingMode       = 'LOTS' | 'RISK_PCT';
export type ProtectionMode   = 'NONE' | 'GTT' | 'RESTING_STOP_LIMIT';

export interface GammaMoveConfig { /* one field per B2 field, same names */ }

export interface GammaMoveResponse {
  strategy: { id; name; contract_version; tagline; how_it_works;
              provenance; live_ready: boolean; enabled: boolean;
              uncalibrated: string[] };
  config: GammaMoveConfig;
  defaults: GammaMoveConfig;
  vocabularies: Record<string, string[]>;
  research_only: { exit_policy: string[] };
  live_requires: { protection_mode: string[]; stop_basis: string[] };
}

export interface GammaMoveSnapshot { strategy; config; scan; candidates;
                                     positions; record; orphan_positions;
                                     blockers: string[] }

export function useGammaMoveConfig()
export function useGammaMoveSnapshot()
export function useUpdateGammaMove()      // PUT, invalidates both keys
export function useGammaMoveScan()        // POST /scan
export function useGammaMoveArm()         // POST /arm
```

Field names are **identical** to B2's Python names. The ATM hook does this and it
is why a config field can be added in one place and read in the other without a
translation table to keep in sync.

### F4 — `board/gammaMoveAdapter.ts`

`gammaMoveToBoard(snapshot?) => BoardSignal[]`. One row per candidate/position.

| `BoardSignal` slot | Filled with |
|---|---|
| `engine` | `'gamma_move'` |
| `underlying` | the stock, e.g. `BIOCON` |
| `instrument` | `{ symbol, exchange:'NFO', kind:'option', optionType, strike, expiry, lotSize, quoteKey:'NFO:<symbol>' }` |
| `direction` | always `'long'` — this strategy only ever **buys** options |
| `status` | `armed` / `running` / `weakening` / `ended` / `watching` / `error` from `GammaSignal.state` |
| `levels` | `{ ltp, entry, stop, trail, target, exit }` — **null, never 0**, when unknown |
| `sizing` | `{ lots, quantity, atRiskInr, deployedInr }` |
| `score` | `null` — this engine publishes no score, and inventing one is a lie |
| `reason` | `GammaSignal.reason`, mandatory for `watching`/`error` |
| `underlyingPrice` | spot |
| `origin` | see below |
| `flags` | `UNCALIBRATED` (amber) while thresholds are unvalidated; `DTE n` (dim); `REGIME UP/DOWN` (green/amber) |

**`origin`** — this engine's own answer to "where did this come from" is
**which of the three conditions is carrying the signal**, because that is the rule
the whole strategy turns on:

```ts
{ label: 'OI UNWIND', tone: 'green',
  hint: 'Open interest fell 7.4% on the last 15-minute bar while volume ran 3.1x
         its recent average and the premium rose 4.2% — writers covering.' }
```

**Detail `sections`** — three blocks:

1. **Trigger** — `oi_drop_pct`, `volume_ratio`, `price_gain_pct`, each shown against
   its configured threshold and marked pass/fail. A trader must be able to see
   *which* leg of the triple is short.
2. **Level** — level price, kind, touch count, distance in %, and the timeframe it
   was found on.
3. **Contract** — strike, expiry, days to expiry, OI, the strike's share of chain
   OI, and lot size.

`direction` is hardcoded `'long'` deliberately. `OpenPosition.direction` has
previously reported `"long"` for every option and a counter that inferred sell
intent from it sold every PE at entry. Here the strategy genuinely never sells,
so the constant is correct — and the comment in the file must say *why* it is
correct rather than leaving the next reader to re-derive it.

### F5 — `board/GammaMoveBoard.tsx`

Renders `BoardSignal[]` through the shared board components. Columns:
`Status · Instrument · Origin · LTP · Entry · Stop · Target · Qty · At-risk · Reason`.
Empty state reads out `snapshot.blockers` verbatim; a quiet engine that will not
say why is the thing this table exists to prevent.

### F6–F9 — the four wiring edits, exactly

**F6 `board/boardTypes.ts`**
```ts
export type EngineId = … | 'atm_premium_imbalance' | 'gamma_move';
ENGINE_LABEL: { …, gamma_move: 'Gamma Move' }
ENGINE_TAG:   { …, gamma_move: 'GM' }
```
Update the `BoardOrigin` doc-comment, which enumerates what each engine's origin
badge means, to include this one. It is a comment that has stayed accurate by
being edited every time; keep that streak.

**F7 `config/registry.ts`**
```ts
export type SectionId = … | 'atmPremiumImbalance' | 'gammaMove' | 'markets' | …
export const SECTION_IDS: SectionId[] = [ …, 'atmPremiumImbalance', 'gammaMove', 'markets', … ]
```
Plus one `FieldDef` per user-visible setting, each with `label`, `help`, `owner`,
`applies`, `stage`, `rescan`, `home: 'gammaMove'`, and — required — `evidence`
naming the backend code that honours it. `rescan: true` on every field that
invalidates the candidate cache: `level_*`, `pivot_lookback`, `strike_window_pct`,
`min_days_to_expiry`, `max_days_to_expiry`, `include_indices`, `explicit_symbols`.

**F8 `ConnectPane.tsx`** — three edits:
```ts
import { GammaMoveSettingsPanel } from './GammaMoveSettingsPanel';      // ~line 25
gammaMove: <Icons.Pulse />,                                          // ~line 842
{ id: 'gammaMove', label: 'Gamma Move',
  eyebrow: 'OI unwind at a level, buy the gamma',
  group: 'Signal engines',
  pageDescription: 'Buys the option that writers are covering: an F&O stock at a '
    + 'support or resistance level, the highest-OI strike there, entered when open '
    + 'interest falls while volume and premium rise together. Held one to two days. '
    + 'Transcribed from a public walkthrough and not yet validated, so it stays '
    + 'paper-only until the readiness gate passes.' },                  // after the atm entry
{section === 'gammaMove' && (<><GammaMoveSettingsPanel /></>)}          // ~line 1107
```

**F9 `AdaptiveEdgeRightSidebar.tsx`** — four edits: `NAV_TARGET.gammaMove =
'gamma_move'`; `const gmSnapshot = useGammaMoveSnapshot()`; a `tabs` entry
`{ id:'gamma_move', running: gmCfg?.enabled !== false, live: live(gm), scanned: gm.length }`;
and `{engine === 'gamma_move' && <GammaMoveBoard nowMs={nowMs} onOpenDetail={onOpenBoardDetail} />}`.

---

## 8. Build order

**All nine phases are complete** as of 2026-08-26, plus two fixes the tests
surfaced (a swing-pivot plateau bug and a de-scale ladder that un-latched on a
single winner) and one artifact the plan did not anticipate: the calibration
harness under `backend/study/gamma_move/`, without which the three gaps would
still be guesses.

Nine phases. Each ends with a green test run; none leaves the tree in a state
where the engine is reachable but half-wired.

| Phase | Artifacts | Done when |
|---|---|---|
| **P0** Scaffolding | B1, B2, B3, T1, T2 | `GammaMoveConfig().validate()` passes; every U1/U2/U3 lower bound has a failing-case test |
| **P1** Levels | B4, T3 | Pivots and clusters computed from a fixture series; proximity test exact at the boundary |
| **P2** Selection | B5, T4 | Expiry window, strike window, OI tie-break, CE/PE direction all proved |
| **P3** Trigger | B6, B7, T5, T6 | The R7 triple, each condition failing alone, `confirm_bars`, **the session-boundary phantom unwind**, `oi[t-1] == 0`, and the regime gate blocking both ways |
| **P4** Lifecycle | B8, B9, B10, T7, T8, T9, T11 | One trade runs end to end in-process; property tests hold |
| **P5** Data path | B12, B13, T12 | A real `scan_once` against a live Kite session returns candidates, and the request count and pacing are asserted |
| **P6** Runtime | B14, B17, B18, T13, T14 | Routes answer; the loop runs; orphan detection and subscription release proved |
| **P7** Replay | B11, B15, B16, T10 | A stored contract replays and the replay's decisions match the live evaluator's |
| **P8** Frontend | F1–F9, T15–T18 | The tab renders, settings round-trip, `registry.sections` test updated |
| **P9** Validation | D4 | `VALIDATION_REPORT.md` written from an actual replay run — **and not before** |

**Suggested commits:** one per phase, staged **by explicit path**. This worktree is
shared; other sessions leave uncommitted work in it and can switch `HEAD`
mid-turn. Never `git add -A`, and re-check `git branch --show-current`
immediately before each commit.

**Running the tests:** `PYTHONWARNINGS=ignore` is required, and
`test_delta_iv_socket` must be deselected. Suite ordering is flaky here — compare
the failing **set**, not the failing count.

---

## 9. Test plan — the cases that actually matter

Beyond ordinary coverage, these are the ones that catch the bugs this design can
plausibly ship:

| Case | Why |
|---|---|
| **Session-boundary phantom unwind** | Feed two sessions of candles unsliced; assert **no** signal at the first bar of day two. Without `slice_session` this fires every trading morning at 09:15 — a bug that looks like a working strategy. |
| **Cumulative vs per-bar volume** | Build a forming bar from ticks whose `volume_traded` is a running day total; assert `volume_ratio` is comparable to the candle-derived one. Mixing them makes condition (b) permanently true and silently deletes a third of the entry rule. |
| **`oi[t-1] == 0`** | Assert refusal, not `inf`, not a divide-by-zero traceback. |
| **Each condition failing alone** | Three tests: OI drops but volume is normal; volume spikes but OI is flat; both fire but the premium falls. All three must produce **no signal**, each with a distinct `reason`. |
| **Inverted stop** | Swing low above the entry ⇒ candidate rejected, not entered with `stop > entry`. |
| **Regime `unknown` blocks** | Too few bars for SuperTrend must block, not pass. A gate that fails open is not a gate. |
| **De-scale ladder** | 3 losses ⇒ half size; 2 wins ⇒ full size; a win mid-streak resets the loss counter. |
| **Zero-threshold refusal** | `min_oi_drop_pct = 0` ⇒ `validate()` raises. This is U2's guard rail and the one thing standing between "selective" and "fires on every bar". |
| **Unknown config key** | `PUT` with a typo'd field ⇒ 422, not a 200 that silently ignored it. |
| **Request-count ceiling** | `scan_once` over a 200-name universe issues ≤ `max_candidates` historical requests. Asserts the funnel ordering has not been quietly inverted. |
| **Pacer spacing** | Consecutive historical calls are ≥ `1/rate` apart. Guards against someone swapping in a token bucket. |
| **Board null levels** | A signal with `entry: null` renders `—`, never `0`. A fabricated `0` in a stop column is a trade-destroying lie. |

---

## 10. What is proved, and what is not

### Proved before a line is written

- **The data exists.** All three OI paths were located in the codebase and cited
  by file and line (§3). This is not an assumption.
- **The rate limit is survivable**, given the funnel in §3.1 — ~25 historical
  requests per 15-minute bar against a 3 rq/s budget.
- **The pattern is proved.** ATM Premium Imbalance is a working engine with the
  same engine/service/API/board/settings shape, 19 backend test files, and a
  live-readiness gate. This build copies it rather than inventing a shape.

### Not proved, and no amount of code will fix these

1. **The strategy has no established edge.** Four winning examples were shown in
   the source. Four winners establish nothing — a coin flip produces four
   straight winners about one time in sixteen. No losing trade, no win rate, no
   sample size, and no drawdown was disclosed.
2. **Three of its rules were never given numbers** (U1, U2, U3). The defaults in
   §5 are calibration starting points chosen to be plausible, not observed
   values. Until a replay run says otherwise, they are guesses wearing a config
   field's clothing — which is exactly why the board badges them `UNCALIBRATED`.
3. **There is no exit rule at all** (§1). The 2x/3x figures are outcomes. The
   shipped `TIME_STOP` default is the only exit the source actually supports, and
   "hold two days and see" is not a validated exit.
4. **Costs are unmodelled.** Stock-option spreads at these premiums are wide and
   the source shows mid-to-mid multiples. Every backtest number this engine
   produces must carry a structure-aware cost model or it is fiction — this
   codebase has already had to kill one engine's numbers for exactly this.
5. **Backtest depth is limited by the data lake.** Expired contracts leave the
   instrument dump, so history exists only where it was captured while live.
   Honest framing: **forward-testable from day one, back-testable only over
   whatever is already stored.**
6. **Selection bias in the source.** The presenter is selling a mentorship
   programme and a screener in the same video. The examples are the ones chosen
   to be shown.

### The live gate

`live_ready` stays `False` and `execution_mode: "live"` is refused by
`validate()` until **all** of the following are true:

- [ ] `VALIDATION_REPORT.md` exists, written from a replay over ≥ 3 expiry cycles
- [ ] The report states a win rate **and** its break-even threshold — a win rate
      without one is not an answer
- [ ] U1/U2/U3 thresholds are calibrated from that run, not from this document
- [ ] A structure-aware cost model is applied, and the edge survives it
- [ ] The regime gate is shown to help rather than merely to have been added
- [ ] `protection_mode != NONE` and `stop_basis == PERCENT` are enforced
- [ ] The daily-loss breaker is proved to receive this engine's `uid=`
- [ ] Paper-traded for a full expiry cycle with the record reconciling

Six of the eight are process, not code. That is the point.

---

## 11. Open questions for the operator

1. **Universe size.** `max_universe = 200` covers the whole F&O stock list. A
   tighter, curated high-liquidity list already exists in
   `services/kite_engine/universe.py` and would cut Stage A cost and improve
   fill quality. Prefer it?
2. **`confirm_bars`.** Default `1` matches the worked examples; `3` matches the
   source's "confirms in 45 minutes". `1` is shipped; `3` is one setting away.
3. **Indices.** Excluded by default (§2.1). The mechanism is weaker there, but
   NIFTY/BANKNIFTY have the deepest OI on the exchange. Worth a separate
   calibration rather than a shared one.
4. **Exit.** `TIME_STOP` is the only sourced exit. If a target is wanted,
   `PERCENT_TARGET` needs a number, and that number has to come from a replay.

---

*Sources: the podcast captions (Hindi original, cross-checked against the machine
translation); the Sterling codebase at `beaef03f`; and the ATM Premium Imbalance
documents `A230`, `A265`, `A280`, which this document deliberately parallels.*
