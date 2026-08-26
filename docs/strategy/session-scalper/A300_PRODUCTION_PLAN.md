# A300 — Session Scalper: audit and production plan

**What this is.** An end-to-end audit of the ATM Premium Imbalance build and a
specification for the production-grade intraday option scalper that should
replace it, artifact by artifact.

**How to read it.** Every artifact below carries an **Attack** — the strongest
objection I can make to my own specification — and its resolution. An artifact
without a surviving attack is not confirmed. Three artifacts are attacked
successfully and are *not* confirmed; they are named as such in §9.

Provenance markers continue the A230 convention and add two:

| Marker | Meaning |
|---|---|
| **OBSERVED** | Read off a source recording, arithmetically self-consistent |
| **OURS** | Designed here. The recordings show no such thing |
| **UNPROVEN** | Neither observed nor verifiable |
| **MEASURED** | To be fixed by data we do not yet have. Not a config default |
| **GATED** | Exists in code but cannot run live until a named gate passes |

---

## 0. Amendment A300.1 — 2026-08-22, same day

**Raised by the user:** *"why are we using the nifty_orb_*? our atm imbalance
strategy is not independent?"*

The premise was right and it exposed two errors in the first draft.

**The ATM engine is independent, by design.** Verified: every module in
`engines/atm_premium_imbalance/` imports **stdlib only**, and there is no import
in either direction between it and `nifty_orb_*`. It is a sealed conformance
artifact -- that is *why* it carries its own private `protection.py` instead of
using the shared one. Nothing in this plan makes it dependent, and A340 below is
now withdrawn so that stays true.

**Error 1 -- I audited a module instead of the caller path.** Section 3.3 and A343
stated that "there is no downside protection in the build at all". That is true of
`engines/atm_premium_imbalance/protection.py` and **false of Sterling**. The
shared Kite position layer already has it:

| Module | Lines | What it already does |
|---|---|---|
| `services/kite_engine/protective_stop.py` | 343 | Broker-side **two-leg OCO GTT** -- stop *and* target in one trigger, so "both fire and we sell twice" is impossible **by construction**. `place_stop`, `move_stop` (ratchets the GTT up as the stop tightens), `cancel_stop`, `stop_status` |
| `services/kite_engine/protection.py` | 390 | `arm_position` with `stop_mode` = `broker` / `monitor` / `both`; registry entry, tick subscription, expiry square-off. Rule: *no plan means no protection, said out loud* |
| `services/kite_engine/monitor.py` | 500+ | Tick monitor for **intrabar** exits; trails the GTT via `move_stop` |
| `services/kite_engine/positions.py` | 337 | The position registry every order path writes to |

This is the exact mistake this project's own notes warn about: *test the caller
path, not just the function.* The correction matters because it changes A343 from
"build the missing primitive" to "adopt the existing one and add the missing
*structure*" -- a much smaller and safer job.

**Error 2 -- A340 would have built a second position layer.** ORB, Navigator,
auto-exec and hand-placed board orders **all already feed the shared layer
above**. Extracting the ATM engine's private lifecycle into `common/` would have
created a rival position layer beside it: two registries, two protection paths,
two places a stop can be wrong. Withdrawn.

**Revised architecture -- two engines, not three:**

- **`atm_premium_imbalance`** -- frozen, independent, **zero changes**. The
  evidence artifact.
- **The scalper extends the ORB engine** rather than being a new third engine.
  ORB is chosen for one reason only: it is *already wired into the shared position
  layer* and already owns the universe, opening-range and liquidity half.
  `enabled` defaults to `False` and it lives on this feature branch, so reshaping
  it breaks nothing in use.
- **The three-clock model lands in the shared layer** (`protective_stop` +
  `monitor` + a new shared exits module), not in a per-engine file, so every
  engine gains the structural stop and the time stops.
- The good ideas from the ATM engine -- Intents, the phase machine,
  `UNKNOWN -> RECONCILE`, fill-not-limit accounting, session-origin gating -- are
  **ported into the shared layer where they are missing**, as ideas rather than as
  an extraction.

Everything else in this plan stands: the artifacts were mostly new code either
way, and only their *home* changed.

---

## 0.2 Amendment A300.2 — the ORB question

**Raised by the user:** *"in the source video of this, didn't have anything about
ORB? why did we?"*

Correct. The recordings contain **no ORB, no VWAP, no ATR, no momentum, no
time-of-day logic and no multi-underlying scanning.** They show one thing: at the
open, buy the cheaper ATM leg, exit at fill + 15 points.

**Where ORB actually came from — and it was not the video.** It came from the
request itself, ideas 4, 6, 7 and 8: *"making use of the window of first
40min-1hour momentum"*, *"based on the time of the day — this should have
profile"*, *"sometimes we need to make use of momentum"*, plus the slot table.
Those are momentum concepts, and `nifty_orb_*` is this repo's existing
implementation of exactly them. If momentum were not wanted, ORB would have no
business in this plan at all.

So the *presence* of ORB is legitimate. **What is not legitimate is what I did
with it.**

### The overreach

§1.1 did not add momentum alongside the source strategy. It **demoted the source
strategy to nothing** and made momentum the entire thesis. That is backwards, for
one reason that outweighs the rest:

> The recordings are the only **evidence** in this entire project. Replacing the
> one evidenced thing with an unevidenced thing, on the strength of an algebraic
> argument, is the wrong direction of travel.

**The parity argument is sound; the conclusion hung on it was too strong.**
`CE − PE ≈ F − K` is real, and it does establish something useful: the signal is a
near-deterministic function of where spot sits in the strike ladder, so computing
it from two independently-stale premiums is the wrong *implementation*. That part
stands (A322).

What it does **not** establish is that the underlying quantity has no edge. A
signal being a simple function of observable state does not make it edgeless —
most real edges are simple functions of state. The honest statement is *"nobody
has measured whether this pays"*, and that is a reason to **measure it**, not to
discard it.

### A better reading of what the source strategy is

I characterised it as "a coin flip on a round number". That undersells it. At the
open the ATM strike sits near wherever the overnight gap left spot, so *which side
of the strike spot is on* substantially encodes **the gap**. Buying the cheaper —
therefore out-of-the-money — leg is buying **against the gap**, cheaply, with more
contracts per rupee of premium than the dear leg gives.

That is a **gap-fade with convexity**. Partial gap reversion is a documented
intraday effect, and the +15-point target is consistent with taking a small,
early piece of it. It is a real hypothesis that deserves testing on its own terms.

### And my own bias, named

I found a mature momentum engine already in the repo and that made "use ORB"
attractive for reasons of **engineering convenience**. Convenience is not a reason
to change somebody's strategy, and it should not have shaped the recommendation.

### The correction: two signals, not one

Almost none of this plan is about the signal. **23 of the 27 artifacts are
signal-agnostic** — capture, universe, bars, capacity, selector, sizing,
portfolio, the three clocks, the ladder, protection, the governor, the supervisor,
reconciliation, all five validation artifacts, and all four surfaces. Only A320,
A321, A323 and A322 touch the signal at all.

So hosting two signals costs almost nothing structurally:

| | Signal | From | Slot | Status |
|---|---|---|---|---|
| **1** | **Open imbalance** — buy the cheaper ATM leg | **the recordings**, ideas 1-3 | 09:15-09:20 | Evidenced, unmeasured. **A325** |
| **2** | **Opening-range momentum** | ideas 4-8 | 09:45 onward | Hypothesised, unmeasured. **A321** |

They do not even compete for a window: signal 1 is an open-auction strategy that
needs no prior range, signal 2 structurally cannot fire until a range has formed
(Amendment A300.1's slot correction). Both run through the same universe, the same
costs, the same exits, the same portfolio risk and the same validation gate, and
A362 compares them per slot on net-of-cost trades.

**What changes in the plan:** §1.1's conclusion is withdrawn; A325 (the imbalance
signal, restored and properly computed) and A324 (a signal registry) are added.
A322 stays rejected — but only as originally scoped, which was using `|CE − PE|`
as a *contract-selection* input, where parity really does make it redundant.

---

## 1. Verdict

Six findings, in the order that matters.

### 1.1 The signal you want to scale is not the signal you have

`CHEAPER_LEG` buys whichever ATM leg is cheaper. At a fixed strike, put-call
parity fixes the sign of `CE − PE` almost entirely:

```
CE − PE  ≈  F − K        (F = forward ≈ spot + carry, K = strike)
```

With `strike_policy = ATM_NEAREST` on a 100-point ladder, spot is within ±50
points of `K`. So "the cheaper leg" is, to first order, **a statement about
which side of the nearest round number spot is sitting on** — and buying the
cheaper leg means buying the leg that is *out of the money from there*. Net of
skew, the strategy is:

> Spot is above the round number → buy the put. Spot is below → buy the call.

> **The conclusion this section originally drew is WITHDRAWN by Amendment
> A300.2.** It read the algebra above as proof the signal has no edge, and
> demoted it. That was wrong. Read A300.2 before continuing.

**What the algebra does establish**, and this part stands: the signal is a
near-deterministic function of where spot sits in the strike ladder, so computing
it by subtracting two independently-stale premiums is the wrong *implementation*
— compute `F − K` directly and read the skew separately (A322, A325).

**What it does not establish** is that the quantity has no edge. At the open the
ATM strike sits near wherever the overnight gap left spot, so which side of the
strike spot is on substantially encodes **the gap** — and buying the cheaper,
out-of-the-money leg is buying *against* the gap, cheaply, with more contracts per
rupee than the dear leg gives. That is a **gap-fade with convexity**, a real
hypothesis, unmeasured. Three decodable sessions, all winners, all selected by
whoever chose what to record, support nothing either way.

**Where momentum comes in.** Not from the recordings — they contain none of it.
From ideas 4, 6, 7 and 8, which ask for it explicitly. `nifty_orb_options.py` is
this repo's existing implementation of exactly that, so it is reused rather than
rewritten. It becomes the **second** signal, not the replacement for the first.

So the plan hosts both, over one shared substrate:

| Layer | Comes from | Why |
|---|---|---|
| Universe, bars, regime, liquidity gates | `nifty_orb_*` | Signal-agnostic infrastructure both signals use |
| Position, protection, broker OCO GTT, registry | `services/kite_engine/*` — already shared | ORB, Navigator and auto-exec already use it. See Amendment A300.1 |
| Lifecycle *ideas* — Intents, reconcile, fill accounting | `atm_premium_imbalance`, **ported not extracted** | It has the most careful order logic; the engine itself is not touched |
| Signal 1 — open imbalance | **the recordings** | The only evidenced strategy here. Restored by A300.2; owns 09:15-09:20. See A325 |
| Signal 2 — opening-range momentum | ideas 4-8, via `nifty_orb_*` | Hypothesised, not evidenced. Owns 09:45 onward. See A321 |

`atm_premium_imbalance` is **frozen**, not deleted. It is the only artifact in
the repo with external provenance and a conformance test against real
recordings. Mutating it to add momentum destroys that evidence for nothing.

### 1.2 The cost model understates friction, probably by 2–3×

`backend/app/engines/nifty_orb_validation.py:11` is the only cost model in the
option path. Three of its constants look stale or wrong, and one is
catastrophically defaulted:

| Constant | In code | Concern |
|---|---|---|
| `stt_rate` | `0.000625` (0.0625%) | STT on option *sale premium* was raised to 0.1% effective 1 Oct 2024. If so this understates STT by 60% |
| `exchange_rate` | `0.0000297` (0.00297%) | NSE **options** transaction charge is on premium and is roughly 0.05%, not 0.003%. This looks like a futures-notional rate applied to premium — a ~17× understatement |
| `slippage_per_share` | `0.0` | **A scalping cost model with zero slippage.** For ATM options at the open, half-spread is the single largest cost term |

Worked example, the trade the recording actually took (SENSEX ATM PE, ₹338.10,
80 units, ₹27,048 outlay), with a realistic ₹1.50 half-spread at the open:

```
brokerage        ₹20 x 2                        =  ₹40
STT              0.10% x 27,048 (sell premium)  =  ₹27
exchange txn     0.05% x 54,096 (both sides)    =  ₹27
GST              18% x (40 + 27)                =  ₹12
stamp            0.003% x 27,048                =   ₹1
---------------------------------------------------------
fixed                                              ₹107
slippage         ₹1.50 x 80 x 2                 = ₹240
=========================================================
total                                              ₹347   =  ₹4.34 per unit
```

The observed target is **+15.0 points**. Friction is **4.34 points — 29% of the
gross target** — and on a loser it adds to the loss instead of subtracting from
the win. The `+15` target is +4.4% on a ₹338 premium; friction is ~1.3% of
premium. A strategy with a thin raw edge does not survive that, and the current
cost model would not have shown it.

**For a stock option this is fatal.** Typical ATM stock-option spreads run 2–5%
of premium. Half-spread both ways is 2–5% of premium in slippage *alone*
against a scalp targeting 5%. This is the decisive constraint on your idea 3, and
it is not solved by trying harder — it is solved by refusing the illiquid names
(§4, A311).

### 1.3 The entry price policy has no slippage ceiling

`entry_price_policy = FIRST_TICK_PERCENT` with `entry_through_pct = 0.10` prices
the entry at **10% through the first tick**. The dossier defends this as "a limit
deliberately through the market so it fills like a market order". At the open,
in a thin book, it is a limit that *will* fill up to 10% above where you meant
to buy. On a scalp whose gross target is 4–5%, a 10% entry tolerance means the
worst-case entry alone is twice the target.

`MARKETABLE_ASK` with `entry_buffer_points = 0.50` has the opposite defect: a
fixed 0.50 is 1% of a ₹50 premium and 0.1% of a ₹500 one — the same
points-vs-percent error the dossier already identified for stops, still present
on the entry.

**Fix (A340).** Both policies become one: price through the ask by
`min(k x spread, slippage_budget_points)`, where the budget is an explicit
rupee ceiling per trade, and the order is **refused** rather than repriced when
the ask is further than the budget from the decision price. A missed entry is
free; a bad entry is not.

### 1.4 Single-position architecture, portfolio-scale ambition

`atm_premium_imbalance_runner.py` keys its session registry
`_sessions[user_id]` — **one session per user, one option pair, one trade**.
`Session` holds exactly `ce_token` and `pe_token`.

Everything about ideas 1–3 requires N concurrent positions across M underlyings.
That is not a config change; it is a new supervisor layer (A332, A350) and it
brings four constraints the single-position design never had to face:

- **Feed capacity.** Kite's WebSocket caps instruments per connection (3,000 on
  current documentation) with a small number of connections per API key.
  `ticker_manager.py` enforces **no cap at all** — it will happily accept a
  subscribe that the socket silently truncates. Must be verified and enforced
  (A313).
- **Historical rate limit.** `nifty_orb_universe.scan_universe` calls
  `fetch_bars` per instrument. Kite's historical endpoint is 3 requests/second
  (kitelake's own cost model is built on that constant). Scanning 200 underlyings
  every 5 minutes is ~67s of solid rate-limited fetching per scan. **This is a
  latent bomb at scale** and the fix is to build bars from the tick stream
  in-process (A312), not to poll history.
- **Order rate limit.** A trailing stop that re-arms the broker-side order on
  every ratchet, times 40 positions, will breach Kite's per-minute order cap.
  Needs an explicit governor (A344).
- **Correlation.** Forty long calls on forty NIFTY constituents on a momentum
  morning is not forty ₹25,000 risks. It is one ₹1,000,000 directional beta bet
  wearing forty names. This is the **largest hidden risk in the whole expansion**
  and the reason naive multi-underlying rollouts blow up (A332).

### 1.5 There is no option premium history to validate any of this against

The dossier is straight about it: the lake holds no BFO/NFO option bars, and
`test_lake_has_no_option_bars_so_premiums_stay_unverified` exists to fail if that
ever changes. Kite historical serves option bars only for **currently listed**
contracts; expired weeklies are delisted and gone.

This is the binding constraint on the entire programme. Every feature you asked
for — momentum thresholds, time-of-day profiles, T1/T2/T3 levels, trail
distances — is a *parameter*, and parameters chosen without data are chosen by
taste. Multi-target ladders are especially dangerous here: they add 4–6 free
parameters to a strategy with zero validated ones.

**So A310 (option data capture) is the first thing built, before any strategy
work.** It is cheap, it is the only artifact whose value compounds daily, and
nothing downstream can be honestly decided without it. Six months from now you
either have six months of ATM option history or you have the same problem.

### 1.6 The performance module annualises for crypto

`backend/app/engines/analytics/performance.py:29` — `_DAYS_PER_YEAR = 365.0`,
commented "Sterling trades crypto perpetuals 24/7". Indian equity derivatives
trade ~252 days. Every Sharpe, Sortino, Calmar and **deflated Sharpe** computed
for this strategy through that module is inflated by `sqrt(365/252) = 1.20`.

Given that the project's own gate is DSR ≥ 0.5 and memory records that *no*
Sterling config clears it after the last DSR fix, a 20% inflation is the
difference between a pass and a fail. Must be parameterised per asset class
before any go/no-go number is quoted (A362).

---

## 2. What survives the audit

Not everything needs replacing. These are good and are kept as-is:

| Kept | Why |
|---|---|
| The **Intent** pattern (`strategy.py`) | Engine returns descriptions, caller performs them. This is what makes replay a real test of the live path. The best design decision in the repo |
| **Session-origin gating** (`is_session_origin`) | A stale-LTP tick arrives instantly and is "fresh" by age. Consulting only `last_trade_ts_ms`, refusing `exchange_timestamp` as a fallback, and treating undatable as three-valued — all correct, all found from a real fault |
| **Fill-not-limit accounting** | Target computed from the broker average fill. Observed 288.75 requested / 133.40 filled. Any other choice is broken |
| **Ratchet monotonicity** + property test | Correct invariant, correctly tested |
| **Protection cancel-before-exit halts on failure** | Two live sells on one long is a short. Halting is right |
| **Adoption honesty** (high-water seeded from entry) | Refusing to invent an unknowable peak is exactly right |
| **Trigger / order price / fill kept separate** | Three different numbers in the evidence. Conflating them is the classic backtest lie |
| **`test_every_config_field_is_settable`** | Guards a real bug class that already bit once |
| **Lot-space sizing + `sizing_blocker`** | One function answers both the board and `arm()`. Correct |
| **`TradingCosts` separating gross from net** | The *structure* is right even though the constants are wrong (§1.2) |
| **CPCV / PBO / walk-forward / deflated Sharpe** | The institutional validation kit already exists. Rare and valuable |
| **ORB's cost-capped premium risk** | `premium_risk_per_share = min(max(...), entry_premium)` — a bought option cannot lose more than it cost. Already fixed once, stays |

---

## 3. The strategy design

This section decides the three questions your ideas raise, before any artifact
specifies how to build them.

### 3.1 The signal: opening-range momentum, with a session-relative definition

**Hypothesis, stated so it can be falsified.** Overnight information is absorbed
in the first minutes of the session. When price then leaves the opening range on
expanding volume and holds the break, the move continues for long enough to pay
for the option's spread and theta.

That is a real, documented family of intraday effects, and it is what you
described in ideas 4–8. The existing `generate_signal` already implements the
core of it: opening range, breakout distance measured in ATR, VWAP side, VWAP
slope, volume ratio versus lookback, and a `Regime` classification of
EXPANSION / TREND / RANGE.

Four changes, all **OURS**:

1. **Opening range becomes a profile parameter, not a constant.** Your instinct
   for "first 40 min–1 hour" is right in spirit and wrong as a fixed number: the
   right window is the one after which the range stops expanding, and that
   differs by underlying and by day. Specify `opening_range_minutes` per
   *underlying class* and per *volatility regime*, **MEASURED**, with your
   15/30/45/60 as the candidate set. Not hand-picked.

2. **Breakout must be confirmed by a close, not a touch.** A touch of the OR
   high is a wick. This is the same discipline as §3.3 and for the same reason.

3. **Anti-signal: opening range too wide.** If the OR is already >1.5× the
   20-day average OR, the day's move may be spent. Gate, not invert.

4. **Premium imbalance survives here, demoted.** `|CE − PE|` at the ATM strike
   is a cheap read on where spot sits inside the strike ladder and on skew. That
   is genuinely useful for **choosing which contract to buy** once direction is
   decided by momentum — never for choosing direction. See A322.

### 3.2 Time-of-day: your table becomes a prior, not a rule

Your table is broadly consistent with known intraday microstructure, so it is
adopted **as the prior** and then overwritten by measurement. The expert
difference is in four places:

**Do not hardcode clock times as policy.** A slot's behaviour is a *measured*
property — realised vol, spread, hit-rate, follow-through — and it drifts. Store
per-slot multipliers, calibrate them by walk-forward, version them, and never
hand-edit them in production (A320).

**Intraday volatility is U-shaped, so a fixed stop is wrong at every hour.**
This is the strongest technical argument for a time-of-day profile and it is not
in your list. A 15-point stop at 09:20 and a 15-point stop at 13:00 are
different trades because σ differs by 2–3×. Every distance in the system is
therefore expressed in **σ_slot units** — ATR of the underlying, scaled by the
slot's own volatility ratio.

**"Avoid the midday lull" becomes a higher bar, not a ban.** A blanket 11:00–13:30
ban discards the rare news-driven midday expansion, which is among the cleanest
setups of the day. Correct form: raise `min_confidence`, widen the required
expansion, tighten the spread ceiling, cut position size. If the measured
expectancy in that slot is still negative after those, *then* the calibrator sets
size to zero — as an output, not as your opinion or mine.

**Add the term your table is missing: theta, and expiry.** The same clock slot is
a completely different trade at 0-DTE versus 4-DTE. On expiry day after ~14:00
an ATM option is almost pure gamma and theta, and premium decay is non-linear.
The profile must be keyed on **(slot × DTE bucket)**, not slot alone. This is
the single most valuable improvement to your idea 5.

Resulting default profile — **all MEASURED, these are starting priors only**:

| Slot (IST) | Regime | min_conf | stop (σ) | target | size | Notes |
|---|---|---|---|---|---|---|
| 09:15–09:20 | no ORB signal | — | — | — | 0 | **Structural, not a preference:** the opening range does not exist yet. Belongs to the open-auction class — see below |
| 09:20–09:45 | gap absorption | 0.70 | 1.5 | trail only | 0.5× | High vol, high slippage. Small and wide |
| 09:45–11:00 | **prime** | 0.55 | 1.0 | ladder on | 1.0× | Your best window. Agreed |
| 11:00–13:30 | lull | 0.75 | 0.8 | 1.5R fixed | 0.4× | Higher bar, not a ban |
| 13:30–14:00 | Europe open | 0.65 | 1.0 | ladder on | 0.7× | |
| 14:00–15:00 | **prime** | 0.55 | 1.0 | ladder on | 1.0× | Institutional positioning. Agreed |
| 15:00–15:15 | close | 0.80 | 0.8 | 1R fixed | 0.3× | Exit-only bias |
| 15:15–15:30 | no entry | — | — | — | 0 | Square-off window |

`0-DTE` overrides the whole table after 13:00: no new entries, exit-only.

> **Does this not contradict the ATM evidence? — raised by the user.**
>
> It would, if the table were a global session policy. It is not, and the first
> draft failed to say so. **This table governs the momentum engine only.** For an
> opening-range strategy the 09:15–09:20 row is not a judgement at all — it is
> arithmetic: the opening range has not formed, so there is nothing to break out
> of. An ORB signal in that window is *undefined*, not discouraged.
>
> The ATM strategy lives in exactly that window — `entry_window_seconds = 300` is
> 09:15 to 09:20 — and it belongs to a *different class*: open-auction imbalance,
> which needs no prior range because it trades the dislocation itself. So the slot
> is **reserved, not banned**, and if the ATM strategy is ever validated it is the
> thing that owns it.
>
> What does carry over from §1.2 is the cost argument, and it is *about* that
> strategy rather than against it: the open is where spreads are widest, which is
> why the worked example used a ₹1.50 half-spread and why friction ate 29% of a
> +15 target. That says the open is **expensive**, not that it is forbidden.
>
> **The honest state:** whether the open is tradable at all is unresolved, and the
> two strategies disagree about it. That is a reason to keep both and measure them,
> not to settle it by assertion in a table.

### 3.3 The exit model: three clocks

This answers your question 12 directly. Your objection to a trailing stop is
exactly right, and it is the right objection:

> price goes 15 up, dips −20 for a second, then runs 50 up — we lose

That is **wick risk**, and it has five distinct causes. A single trailing stop
cannot fix them because they are not one problem.

| Cause | Why the naive TSL loses | Fix |
|---|---|---|
| **A. Trailing on the premium** | Option LTP is noisy and the spread can widen momentarily. A single air-pocket print takes you out at a price no size was available at | **Trail in underlying space.** The thesis is about the underlying; the option is the vehicle. Translate to premium only for the broker order |
| **B. Trailing on ticks** | A wick is a tick. Your −20 dip is precisely this | **Close-confirmed ratchet.** The stop only moves, and only fires, on a *completed bar close*. A wick does not close |
| **C. Distance in points or percent** | Points ignore volatility; percent-of-premium conflates IV level with expected move | **σ_slot units** (§3.2) |
| **D. Giving back the excursion** | Full-position trail returns the whole retracement | **Partial ladder** — but see the attack below, it is not free |
| **E. Theta** | A trade that is not working still costs money every minute | **Time stops.** The highest-value addition for option scalping, and absent from every version of this build |

**The design.** Three independent monotonic clocks. Whichever fires first wins.
Each is owned by a different layer, so a bug in one cannot disable another.

```
CLOCK 1 — STRUCTURE          (underlying space, close-confirmed, ratcheting)
   rung 0  initial      OR level, or entry − k·σ_slot, whichever is nearer
   rung 1  break-even   after MFE ≥ 1R  → stop to entry
   rung 2  chandelier   after MFE ≥ 1.5R → highest close − k·σ_slot
   monotonic: each rung takes max() against the rung below

CLOCK 2 — TIME               (bars, not prices)
   hard        exit at max_hold_bars regardless
   no-progress exit if MFE < 0.5R by bar N — theta is certain, the edge is not
   session     square-off at the session-end window, wins over everything

CLOCK 3 — CATASTROPHE        (premium space, resting AT THE BROKER)
   SL-M sell at ~2x the structural distance, in premium terms
   premium floor at −X% of entry
   dead-man: if our process dies, clock 3 is the only thing left alive
   never expected to fire in normal operation
```

Clock 3 answers: **what protects the position when our process is gone?**
Sterling already has this — see Amendment A300.1. `services/kite_engine/` places
a broker-side **two-leg OCO GTT** (stop *and* target in one trigger, so a double
sell is impossible by construction), ratchets it with `move_stop`, and backs it
with a tick monitor for intrabar exits.

The ATM engine's own `protection_mode` is the exception: `RESTING_TARGET_LIMIT`
rests a sell at the *target* and its `GTT` triggers just below that same target,
so both are take-profits. That is correct **for a sealed conformance artifact**
and wrong as a description of the platform. What clock 3 needs from the shared
layer is not a new primitive but the missing *structure*: a stop derived from
underlying-space structure rather than a premium level. See A343.

**Targets: a ladder, defaulting off.** Your T1/T2/T3 idea, with the honest
caveat that most systems get wrong:

```
T1 at 1R    exit 1/3   → stop to break-even
T2 at 2R    exit 1/3   → stop to T1
runner      no target  → chandelier trail until stopped
```

**Scaling out lowers expectancy in a positively-skewed momentum strategy.** The
edge in momentum lives in the right tail; cutting two-thirds of the position at
1R and 2R caps exactly the tail that pays for all the losers. Scale-out is a
**variance-reduction tool, not a return-enhancement tool** — it raises win rate
and cuts drawdown while lowering mean P&L. Which side of that trade you want is
a real decision, and it must be made from a measured payoff distribution, per
slot, not from preference. So: **implemented, per-slot selectable, defaulting
OFF** (full position on trail), because that is the higher-expectancy prior.

And a hard practical constraint that is easy to miss: **you cannot scale out of
one lot.** Thirds need ≥3 lots. Lot size is a property of the contract and must
be read from the instrument master, never assumed — but at index lot sizes and a
₹25,000 premium ceiling, many contracts admit only one or two lots, and some
admit one lot only. The ladder must **degrade explicitly** — 3 lots → thirds,
2 lots → halves at T1 and runner, 1 lot → single target, no ladder — and the
board must say which mode a row is in. Silently ignoring a configured ladder
because the size cannot express it is the same class of bug as the pydantic
mirror that dropped nine settings.

---

## 3.5 How it actually works — a day, in plain language

No specifications in this section. Just what happens, in order, with numbers you
can check.

> **Every number here is illustrative.** Lot sizes, sigma values and deltas are
> plausible stand-ins so the arithmetic is followable. In the real system all
> three are **read**, never assumed: lot size from the instrument master, sigma
> from measured bars, delta solved from the traded premium.

### The one idea that makes the rest simple

There are only **three numbers** the whole system cares about once you are in a
trade:

```
1R          the money you agreed to risk, fixed at entry
MFE         the best this trade has been, measured in R
the stop    which only ever moves UP, never down
```

Everything — targets, trailing, partial exits, time stops — is expressed in R.
That is why one rule works on a ₹40 stock option and a ₹500 index option without
changing a number.

---

### 08:45 — before the bell

Nothing is decided by you at the open. It is all decided now.

**A nightly job has already produced the eligible list.** It measured spread,
depth, volume and open interest at the ATM strike for every F&O underlying over
the last N sessions, and published something like:

```
ELIGIBLE 2026-08-25    18 of 186 underlyings

  indices   NIFTY  BANKNIFTY  SENSEX  FINNIFTY
  stocks    RELIANCE  HDFCBANK  ICICIBANK  INFY  TCS  SBIN
            AXISBANK  LT  BAJFINANCE  ITC  TATAMOTORS  MARUTI
            KOTAKBANK  ADANIENT

REJECTED  168
  165 on spread      median ATM spread above the 1.50% ceiling
    2 on depth       fewer than 3 lots at top of book
    1 on OI          below the open-interest floor
```

That list is the answer to *"trade all F&O stocks"*. It is not a refusal — it is
the measurement. If 165 names carry 3%+ spreads, trading them loses money with
near-certainty, and the ledger shows which floor each one failed so you can argue
with the floor rather than with the concept.

**You then set four things**, once:

| Setting | Example | What it does |
|---|---|---|
| Mode | `paper` | `live` is refused until the promotion gate passes |
| Outlay cap | ₹25,000 | The most one position may **spend** |
| Risk cap | ₹5,000 | The most one position may **lose at its stop** |
| Signals on | both | Open imbalance, momentum, or both |

The system then tells you, before you arm, whether it *can* run: how many
subscription tokens it needs against what the socket allows, and whether any
position would be blocked.

---

### Manual or automatic — the four ways to run it

This is the part that usually gets muddled, so it is worth being blunt.

| | Finding the trade | Placing the order | Who manages the exit |
|---|---|---|---|
| **A** | automatic | automatic | the system |
| **B** | automatic | **you click Buy** | the system |
| **C** | **you pick the underlying** | automatic | the system |
| **D** | **you place it by hand** | **you** | **the system, still** |

**Row D is the important one.** If you buy an option by hand off the board, it
still gets a registry entry, a tick subscription, a broker-side stop, the three
clocks and the end-of-day square-off. It is *adopted*.

That is not a nice-to-have. This platform has already been bitten by its absence:
a hand-placed order once got no registry entry, no stop and no monitor **while the
board went on displaying an SL, a TSL and a target beside it**. An unguarded
position that looks guarded is worse than one that looks unguarded.

In all four rows the exit logic is identical. The only thing that changes is who
decides to enter.

---

### 09:15:00 — the bell. Signal 1 fires.

NIFTY opens at **24,518**. The strike ladder is 50 points wide, so the ATM strike
is **24,500**.

**Step 1 — which leg?** Spot is 18 points above the strike, so the call is dearer
and the put is cheaper. Buy the **put** — a cheap bet against the gap up.

We do *not* work this out by subtracting two premiums. We compute `F − K = +18`
straight from spot, strike, expiry and rate. Two premiums give the same answer
more noisily, and either of them could be carrying yesterday's price.

**Step 2 — is this tick real?** The 24,500 PE's last *trade* stamp must be from
today's session. If it is stamped yesterday we refuse and wait, no matter how
attractive the price looks. This gate caught a real fault: a carried-over tick
once produced an order price of 416.90 where the genuine session price gave
392.40.

**Step 3 — is it tradable?**

```
PE  bid 141.10   ask 142.30   spread 1.20 on a mid of 141.70  =  0.85%
ceiling 1.50%  ->  PASS
```

**Step 4 — how much?** Both caps are applied and the smaller one wins.

```
lot size 75 (illustrative)      1 lot costs 142.30 x 75  =  ₹10,672
outlay cap ₹25,000              ->  2 lots  =  ₹21,345      <- binds
risk cap   ₹5,000               ->  1R is ₹4,556 (below it)  <- passes

QUANTITY = 2 lots = 150 units       LADDER MODE = HALVES
```

`HALVES` because two lots split once but not into thirds. The board says so on the
row. A ladder the size cannot express is never silently ignored.

**Step 5 — the entry price.** Price *through* the ask so it fills like a market
order, but never further than an explicit rupee budget:

```
through-ask = min( 0.5 x spread , budget ₹2.00 )  =  min(0.60, 2.00)  =  0.60
limit = 142.30 + 0.60 = 142.90
```

If the ask runs more than ₹2.00 away from the price we decided on, the order is
**refused, not repriced**. A missed entry costs nothing. This replaces the recorded
bot's "10% through the first tick" — which, on a trade targeting 4–5%, means the
worst-case entry alone is twice the target.

**Step 6 — the fill.** Broker average fill: **142.75**.

> Everything downstream uses **142.75**, never 142.90. In the recordings the bot
> requested 288.75 and filled at 133.40; a target computed off the request would
> never have fired.

---

### 09:15:02 — the stop is set, three ways at once

```
sigma for this 5-minute slot        45 index points   (measured)
stop multiple                       1.5
initial risk                        67.5 index points

we are long a PUT, so we lose if spot RISES
        stop spot  =  24,518 + 67.5  =  24,585.5

|delta| of the 24,500 PE             0.45   (solved from the premium)
        1R  =  67.5 x 0.45  =  30.4 premium points  =  ₹4,556 on 150 units
```

Three protections now exist, each owned by a different part of the system so a bug
in one cannot switch off another:

| | What | Where it lives | Level here |
|---|---|---|---|
| **Clock 1** | Structural stop, **fires only on a bar close** | our process | premium ~112.38 |
| **Clock 2** | Hard time stop + "no progress" stop | our process | bars, not price |
| **Clock 3** | Catastrophe stop, ~2x wider | **at the broker**, an OCO GTT | premium ~82.00 |

Clock 3 is placed **before anything else happens**. If our process dies a second
later, the exchange still closes the position. Clock 1 does the day-to-day work;
clock 3 exists so that clock 1 is *allowed* to be slow.

---

### Scenario A — it works

The gap starts fading. Spot falls, the put gains.

```
spot 24,470.0   premium 164.35   +21.60  = 0.71R
spot 24,450.5   premium 173.12   +30.38  = 1.00R   <- T1
spot 24,420.0   premium 186.85   +44.10  = 1.45R
spot 24,410.0   premium 191.35   +48.60  = 1.60R   <- trail engages
```

**At 1R, T1 fires.** Sell 1 lot (75 units) at bid − 0.50, filled 172.50.

```
tranche 1   +29.75 x 75  =  ₹2,231
the stop moves to BREAK-EVEN at 142.75  ->  the rest of this trade cannot lose
```

That is the most useful thing partial exits do. Not the profit — the fact that the
remaining position is now free.

**Past 1.5R the trail engages.** It follows the *underlying*, not the premium, and
it only moves on *closed* bars:

```
lowest 1-minute CLOSE so far   24,415
trail  =  24,415 + (0.8 x 45)  =  24,451
```

**A 1-minute bar later closes at 24,455**, above the trail. Exit the remaining 75
at bid − 0.50, filled 170.80.

```
tranche 2   +28.05 x 75  =  ₹2,104

gross                          ₹4,335
charges and slippage           ₹  125
NET                            ₹4,210   on ₹21,412 deployed   =  +19.7%
```

---

### Scenario B — the wick. Your original objection.

You said: *price goes 15 up, dips −20 for a second, then runs 50 up — we lose.*

Here is that exact case. The trade is at +1.2R when one print takes the premium
down 20 points — an air pocket with no size behind it — and the bar then closes
higher.

| | A naive trailing stop | This design |
|---|---|---|
| What it watches | the option premium | **the underlying** — an option print cannot move it |
| When it moves | every tick | **only on a closed bar** — a wick never closes |
| What fires here | the wick | nothing |
| Result | stopped out at the worst price of the move | **still in**, and it runs to +2.5R |

Three independent reasons the wick cannot touch us, and clock 3 sits 60 points
below, untouched.

**Being slower is not free** — see scenario C.

---

### Scenario C — it fails, and the cost of being slow

The gap does not fade. It continues. We faded the wrong way.

```
09:19  a 1-minute bar CLOSES at 24,590   (our stop level was 24,585.5)
       overshoot 4.5 index points
       premium ~110.35, exit at bid - 0.50, filled 109.80

loss  =  (142.75 - 109.80) x 150  =  ₹4,942
```

Modelled 1R was ₹4,556. **The realised loss is 1.08R.**

That extra 8% is the honest price of waiting for a close, and it should be said out
loud rather than buried: a close-confirmed stop **always loses slightly more than
its nominal risk**, because price is already through the level by the time the bar
closes. On a violent bar it can be much more. That is exactly why clock 3 exists,
and why the outlay cap binds independently — a stop can fail to fill where you
wanted it.

**If it keeps happening:** at ₹10,000 of realised loss for the day the supervisor
**HALTs**. No new entries; positions already open keep being managed on their
normal exits. This is checked *before* any quote arithmetic, so a breached limit
cannot be argued with by an attractive-looking price.

---

### Scenario D — nothing happens, and you can see why

Most of the time the answer is no. The board says *which* no:

```
NIFTY       watching   no signal - spread 2.10% over the 1.50% ceiling
BANKNIFTY   watching   refused - a quote traded before today's open
INFY        watching   refused - expected net edge -₹140, below the floor
SBIN        watching   no signal - the opening range has not formed yet
TATAMOTORS  watching   refused - portfolio net delta budget
```

A refusal is said **once**, and again only when the *reason* changes. A condition
that stays true for four thousand ticks produces one line, not four thousand.

---

### 09:52 — Signal 2 fires. A completely different trade.

RELIANCE. The opening range from 09:15 to 09:45 was **2,930 to 2,952**.

```
09:52  a 5-minute bar CLOSES at 2,958      above the range high
       volume 1.8x the 20-bar average       expansion confirmed
       price above VWAP, VWAP slope up      direction confirmed
       -> LONG
```

Note **closes**, not touches. A touch of 2,952 is a wick. Same discipline as the
exit side, same reason.

```
structural stop   2,948   (the 1-minute swing low under the break)
risk              10 index points

vehicle: the CE with delta 0.55-0.65 and the tightest MEASURED spread
         -> 2,940 CE, delta 0.60, ask 42.00

premium risk = 10 x 0.60 = 6 premium points
lot 250 (illustrative)  ->  1 lot costs ₹10,500,  risk ₹1,500
outlay cap ₹25,000      ->  2 lots = ₹21,000,     risk ₹3,000
```

From here it is **identical** to signal 1 — same three clocks, same ladder, same
broker GTT, same square-off. The signal is the only thing that differed.

---

### 09:52:01 — eleven candidates fire at once. The catch.

A market-wide push. Eleven eligible stocks all break their opening range LONG in
the same minute.

**The naive outcome:** 11 positions, ₹231,000 deployed, every one long. That is
not eleven diversified ₹21,000 risks. It is **one ₹231,000 bet that the market goes
up**, taken without anybody deciding to take it.

**What actually happens:**

```
candidate  1  RELIANCE     ADMITTED
candidate  2  ICICIBANK    ADMITTED
candidate  3  LT           ADMITTED
candidate  4  HDFCBANK     REFUSED - portfolio net delta budget
...
candidate 11  ITC          REFUSED - portfolio net delta budget

terminal:  8 candidates refused - portfolio net delta budget
```

The budget assumes **everything in a class moves together** (correlation 1.0)
rather than trusting an estimate. If the book is unacceptable when everything moves
together, it is unacceptable — because that is what a crisis morning delivers, and
it is exactly when an estimate would have told you 0.4.

Eight refusals collapse to **one** terminal line with a count. The individual
events are all in the audit log.

---

### 15:15 — the end, whatever the clocks say

The square-off window beats every exit policy. A target not reached by now is not
going to be, and a bought option held past the close — held to expiry, on expiry
day — can settle worthless.

Anything still open is closed. Then the journal is written: every signal, refusal,
ratchet and tranche, with the inputs that produced it, so any single decision can
be replayed later and produce the same answer.

---

### When things break

| What breaks | What happens |
|---|---|
| Our process dies mid-trade | The broker GTT is still there. The position closes at its stop or target without us |
| We restart | Every broker position is matched against our state. An unexplained position **blocks arming** and is adopted by name. State says long but the broker says flat -> **HALT**, because "we missed a fill" and "someone closed it by hand" need opposite responses |
| A tick stream silently drops one contract | The subscription audit notices that token never ticked, marks it **not subscribed**, and blocks the position that needed it. A silent feed gap must not look like a quiet market |
| The broker returns an unclear order status | Never a retry — always reconcile. A retry that double-fills turns one position into two |
| A fill is worse than modelled | Logged against the model's prediction. A persistent bias becomes a finding, not a mystery |
| Too many orders too fast | A pacer holds the rate. Exits are never queued behind a trailing update, and a modification that **tightens** a stop is never dropped |

---

---

## 3.6 Before and after — the recorded strategy vs this one

The left column is what the recordings actually show. The right column is what
this plan builds. Nothing in the left column is criticism of the source bot: it
was doing one thing on one index and it did not claim to do more.

### The trade itself

| | Recorded strategy | This plan | Why it matters |
|---|---|---|---|
| **Universe** | SENSEX only | Every underlying that clears a **measured** liquidity floor — typically ~18 of 186 | Ideas 1–3. And the rejection ledger tells you *why* each name failed |
| **Signals** | One | **Two**, slot-scoped: open imbalance (09:15–09:20) and opening-range momentum (09:45 on) | Ideas 4–8. Neither is measured yet; both face the same gate |
| **How the signal is computed** | Subtract two independently-cached LTPs | `F − K` direct from spot, strike, expiry, rate — plus skew read separately | Put-call parity makes the subtraction a noisier route to the same number, and either premium can be stale |
| **Quote trust** | None. Whatever the cache holds | Three-valued session-origin gate. Proven-stale **always** refused; undatable refused in live | A carried-over tick produced 416.90 where the session price gave 392.40 |
| **Entry timing** | First valid tick pair after arming | Slot-eligible windows only | Arm at 14:00 and the recorded logic traded at 14:00 — a different strategy wearing the same name |
| **Entry price** | Limit **10% through** the first tick | Through-ask, capped by an explicit rupee **slippage budget**; refuse rather than reprice | On a trade targeting 4–5%, a 10% tolerance means the worst case entry alone is twice the target |
| **Entry accounting** | — (already correct) | Broker **average fill**, never the requested limit | Requested 288.75, filled 133.40. Kept, not changed |
| **Spread / depth gate** | None | Hard ceiling on measured spread; depth floor in lots | At the open, half-spread is the largest single cost term |

### Getting out

| | Recorded strategy | This plan | Why it matters |
|---|---|---|---|
| **Target** | **+15 points, fixed** | R-multiples off measured risk. +15 becomes *one candidate* the walk-forward tests | 15 points is a 30% move on a ₹50 premium and 3% on a ₹500 one — the same number meaning two different trades |
| **Stop loss** | **None at all** | Clock 1: structural, in **underlying** space, **close-confirmed**, ratcheting | The premium can halve in seconds. In the recorded V17 session the bought leg fell 133 → 86 before reaching target |
| **Trailing** | None | Chandelier off the highest **close**, in underlying space, monotonic | This is the fix for the wick problem — see scenario B |
| **Time stop** | None | Clock 2: hard hold limit **plus** a no-progress exit if MFE < 0.5R by bar N | Theta is a certainty; the edge is not. Absent from every prior version |
| **Partial exits** | None | T1 / T2 / runner, degrading by lot count, **default OFF** | Scaling out cuts variance, not mean. It must be chosen from a measured payoff distribution |
| **Broker-side protection** | **None.** Position held in process memory only | OCO GTT (stop *and* target in one trigger) + tick monitor + heartbeat | If the process died, the recorded bot's position simply sat there unguarded |
| **End of day** | Not addressed | Square-off window beats every clock | Held to expiry, a bought option can settle worthless |
| **Exit order price** | `best_bid − 0.50`, tick-aligned down | Same, unchanged | Directly evidenced across two builds. Kept |

### Money and survival

| | Recorded strategy | This plan | Why it matters |
|---|---|---|---|
| **Sizing** | Operator types a quantity | `min(outlay cap, stop-risk cap)`, whole lots read from the instrument master | Sizing by the stop alone once produced 2,400 units of an ₹18 option — ₹43,200 — while reporting "risk 3,000" |
| **Daily loss limit** | None | Enforced **before any quote arithmetic**, currency-explicit, cannot be set to zero | A limit that only stops tomorrow is not a limit |
| **Concurrency** | One trade, one day | Explicit cap, plus gross outlay and per-underlying limits | |
| **Correlation** | Not applicable | Portfolio net delta budgeted at **correlation 1.0** within a class | 40 long calls on 40 constituents is one bet, not 40 |
| **Crash recovery** | None | matched / orphan / **ghost**; adoption by name; a ghost HALTs | State is gone after a restart; the position is not |
| **Feed integrity** | Assumed | Subscription acknowledgement audit; a token that never ticks is *not subscribed* | Silent partial delivery looks exactly like a quiet market |
| **Order rate** | Not a concern at one trade | Minimum-spacing pacer with priority classes | A trailing stop across 40 positions will breach a per-minute cap |

### Knowing whether it works

| | Recorded strategy | This plan | Why it matters |
|---|---|---|---|
| **Cost model** | None | Re-derived from a real contract note; slippage **measured, never zero**; realised-vs-modelled reconciliation | Friction was **29% of the +15 target** on the one trade we can price |
| **Evidence** | 3 decodable sessions, all winners, selected by whoever chose to record | Walk-forward + CPCV/PBO + deflated Sharpe, on net-of-cost trades, **pre-committed thresholds** | Nobody films their losses |
| **Data retained** | None | Daily option capture, forever, from day one | Expired weeklies are delisted. What is not captured today is gone |
| **Observability** | Terminal prints | Decision audit log; any single decision replayable | |
| **Live gate** | None | Ten coded conditions plus a staged rollout enforced by persisted state | Code, not discipline |

---

### What the recorded strategy does *better*

This matters, and a comparison table that only runs one way is marketing.

| | Recorded strategy | This plan |
|---|---|---|
| **Simplicity** | ~10 real decisions | ~90 settings across two signals |
| **Overfit surface** | Almost none — there is nearly nothing to tune | Large. Every parameter added is a parameter that can be fitted to noise |
| **Evidence for its target** | `+15` is **directly observed**, in two independent builds of the bot | R-multiples are a design choice with no observation behind them |
| **Evidence it ever traded** | Yes — five recordings of it running | Signal 2 has never traded anywhere |
| **Time to first trade** | It works today | Phase 0 is data capture with no trading at all |

**The honest summary:** this plan is **not strictly better**. It is better at
*surviving* — it cannot lose the premium to a dead process, it cannot silently
size to ₹43,000, it cannot trade a 4%-spread contract, it cannot keep trading
after a bad morning. It is **worse at being simple**, and it replaces two
observed constants with a dozen unobserved ones.

That trade is worth making only if the parameters are chosen by measurement. If
they end up chosen by taste, this plan is a more elaborate way to lose money than
the thing it replaced — which is exactly why A310 (capture) comes first and A362
(the gate) decides, and why **both** signals are held to the same threshold with
no credit for provenance.

---

---

## 4. The artifacts

Twenty-nine artifacts in seven layers. Each has a purpose, a contract, an
**Attack**, tests, and a done-when. Numbering continues the A-series.

The engine is the **renamed ORB engine** (`nifty_orb_*` → `orb_scalper`), not a
new one — see Amendment A300.1. Board `EngineId` stays `'orb'`; only its label
changes, from "ORB + VWAP" to "ORB Scalper". Nothing new is registered, so the
board, the config registry and the five-engine `BoardSignal` contract all keep
working as they are.

---

### Layer A — Data and universe

#### A310 — Option premium capture service · **BUILD FIRST**

**Purpose.** Record what nothing else can recover later. Every trading day,
capture 1-minute bars and (where the socket allows) raw ticks for the ATM ±N
strikes of every eligible underlying, both legs, into the kitelake, keyed by
`(underlying, expiry, strike, option_type, date)`.

**Why first.** Kite serves option history only for *listed* contracts. Expired
weeklies are delisted and gone forever. Everything downstream — momentum
thresholds, slot profiles, ladder levels, trail distances — is a parameter, and
the difference between choosing them from data and choosing them from taste is
this one job existing today rather than in six months.

**Contract.**
- `kitelake/option_capture.py` — a daily job, writes Parquet under
  `options/{underlying}/{expiry}/{yyyy-mm-dd}.parquet`
- Captures: LTP, bid, ask, bid_qty, ask_qty, volume, OI, exchange timestamp,
  last-trade timestamp — **per leg, timestamps preserved separately** (the
  asynchronous CE/PE behaviour is data, not noise)
- Also captures the **underlying** bar series for the same session, so premium
  and spot are aligned in one file and no later join can misalign them
- Roll: N strikes each side of ATM at 09:15, re-centred if spot moves ≥ N/2
  strikes intraday, with the re-centring logged as an event in the file
- Idempotent per day; a partial day is marked partial, never silently completed
- Retention: forever. This is the asset.

**Attack.** *"This is 40 underlyings × 2 legs × 7 strikes = 560 instruments of
tick capture on top of live trading, on the same API key. It will starve the
trading feed and it will breach the socket cap."*

**Resolution — attack lands, spec changes.** Capture and trading must not share
a socket budget. Three changes: (1) capture runs on a **separate API key /
connection**, treated as a hard prerequisite, not an optimisation; (2) capture
defaults to **1-minute bars pulled post-session** from the historical endpoint
for the contracts that were listed that day — no live socket cost at all — with
tick capture as an opt-in extra for a small watchlist; (3) the eligible universe
(A311) bounds the count, and A313 owns the budget arithmetic for both. Post-hoc
bar capture is strictly weaker evidence than ticks (no intrabar order, §A360's
limitation) but it is *available*, it is free of feed contention, and it is
infinitely better than nothing.

**Tests.** Round-trip a synthetic day and assert per-leg timestamps survive.
Assert a partial day cannot be read as complete. Assert re-centring is recorded.
Assert the job is idempotent. Assert `test_lake_has_no_option_bars...` is
**replaced** by its inverse, so the lake's new capability is asserted rather than
its old absence.

**Done when** one full trading day of the eligible universe is on disk, and
A360 can replay it.

---

#### A311 — Liquidity-earned universe

**Purpose.** Decide which underlyings are eligible, from measurement, nightly.
This is where ideas 1–3 are honoured and bounded.

**Contract.**
- `backend/app/engines/orb_scalper/universe.py`
- Inputs: NFO/BFO instrument master (already cached — `nifty_orb_universe_runtime.discover_universe`
  already discovers F&O stock underlyings from it), plus the previous N sessions'
  captured option data (A310)
- Per candidate underlying, measure at the ATM strike over the last N sessions:
  median spread as % of premium, median top-of-book depth in lots, median option
  volume, OI, and the **realised slot-by-slot σ** of the underlying
- Eligibility is a hard floor on all of: `spread_pct ≤ ceiling`,
  `depth_lots ≥ floor`, `volume ≥ floor`, `oi ≥ floor`
- Output: a **versioned, dated eligibility list** with the measured numbers
  attached, plus every rejection and its reason
- Indices are candidates on the same terms as stocks. No hardcoded allowlist.

**Attack.** *"After a real spread floor, the eligible stock list may be almost
empty — so this artifact quietly kills idea 3 while appearing to deliver it."*

**Resolution — attack lands, and the outcome is the point.** That is the correct
behaviour and it must be *visible*, not quiet. The artifact therefore publishes
the full rejection ledger, not just the survivors: "182 F&O underlyings
considered, 31 eligible, 151 rejected — 148 on spread, 3 on depth", with the
distribution. If the honest answer is "indices plus a dozen names", the operator
sees exactly why and can argue with the floor rather than with the concept. A
universe that shrinks under measurement is a working measurement.

**Tests.** A candidate failing any single floor is rejected and names that floor.
The list is deterministic for a fixed input. Floors cannot be set to zero (same
principle as the money limits — a disabled floor must be spelled, and here it
cannot be). Rejections are complete: every input appears in exactly one of the
two lists.

**Done when** a dated eligibility list exists with measured numbers and a
rejection ledger, and A323 reads it rather than a config array.

---

#### A312 — In-process bar factory

**Purpose.** Build the underlying bar series from the live tick stream, so the
scanner never touches the historical endpoint during a session.

**Why.** `nifty_orb_universe.scan_universe` fetches bars per instrument through a
supplied `fetch_bars`. Against Kite's 3 requests/second historical limit, a
200-underlying scan is ~67 seconds of rate-limited fetching — per scan. At scale
this is not slow, it is broken: the scan cannot complete inside its own interval.

**Contract.**
- `backend/app/engines/orb_scalper/bars.py` — pure aggregation, no I/O
- Ingests ticks, emits **closed** bars only, at the configured interval, IST-aligned
- A partially formed bar is never emitted. `as_of` already exists in
  `generate_signal` for exactly this reason; the factory makes it structural
  rather than a caller's discipline
- Seeds from history **once**, at arm time, for the ATR/volume lookback window,
  then runs entirely off ticks
- Gap handling: a missing minute is a missing bar, explicitly, never a
  forward-filled one — a synthetic bar in an ATR window silently narrows the
  measured volatility

**Attack.** *"Ticks are lossy. A dropped socket means bars with holes, and an ATR
computed over holes is wrong in the dangerous direction — it under-measures
volatility, which tightens every stop."*

**Resolution — attack lands, spec changes.** The factory tracks **coverage** per
bar (ticks seen, seconds covered) and marks a bar `degraded` below a threshold.
A σ computed from any degraded bar is flagged, and the signal layer treats a
flagged σ as a **refusal**, not as a number. Plus a post-session reconciliation
job that re-fetches the day's real bars from history and asserts the in-process
series matched — a drift report, run daily, so the assumption is audited rather
than trusted. This is the same pattern as `market_crosscheck.py` and for the
same reason.

**Tests.** Partially-formed bar is never emitted. A gap produces a gap, not a
fill. Coverage marking triggers at the threshold. Reconciliation against a known
real series passes at zero drift and fails at injected drift.

**Done when** a full session's in-process bars reconcile against Kite history at
zero drift for every eligible underlying.

---

#### A313 — Feed capacity planner

**Purpose.** Make subscription capacity an arithmetic fact that is checked before
arming, instead of a limit discovered by silent truncation.

**Contract.**
- Extends `backend/app/services/exchanges/kite/ticker_manager.py`, which today
  enforces **no cap whatsoever**
- A declared capacity model: instruments per connection, connections per key
  (current Kite documentation says 3,000 and a small connection count —
  **the exact figures must be verified against live docs at build time and
  recorded with their source, not copied from here**)
- `plan(underlyings, strikes_per_side)` returns the token count and either fits
  or names the overflow
- `arm()` refuses on overflow with the arithmetic in the message, and the board
  shows headroom before the operator arms

**Attack.** *"A cap read from documentation is a guess. The real behaviour of an
over-subscribed socket is silent partial delivery, which looks identical to a
quiet market."*

**Resolution — attack lands, and it changes the design from a cap to a probe.**
A declared cap is necessary but not sufficient. Add a **subscription
acknowledgement audit**: after subscribing, assert that every requested token
produces a tick within a bounded window, and treat any token that does not as
**not subscribed** — surfaced, and blocking for the position that needed it. This
detects truncation empirically rather than trusting a constant, and it also
catches the unrelated case of a genuinely untraded contract. Silent partial
delivery is exactly the failure class the session-origin gate was built for; it
deserves the same treatment.

**Tests.** Overflow refuses and names the numbers. A token that never ticks is
reported as unsubscribed, not as stale. Refcounted release
(`test_ticker_subscription_ownership.py`) continues to pass unchanged — the
existing owner-tagged refcount is correct and must not regress.

**Done when** an over-subscription is refused before arming, and a
non-delivering token is surfaced within its window.

---

### Layer B — Signal and regime

#### A320 — Session profile calibrator

**Purpose.** Turn your time-of-day table (§3.2) from an opinion into a measured,
versioned artifact keyed on **(slot × DTE bucket × underlying class)**.

**Contract.**
- `backend/app/engines/orb_scalper/profile.py` — pure; a calibrator plus an
  immutable `SessionProfile` value object
- Per key, calibrates: `min_confidence`, `stop_sigma_mult`, `target_mode`,
  `size_scale`, `spread_ceiling_pct`, `max_concurrent`, `ladder_mode`
- Calibrated by walk-forward on captured data (A310) through A362's harness —
  **never fitted on the whole history**
- `slot × DTE` is the key, not `slot`: 0-DTE after 13:00 is a different trade
  from 4-DTE at the same clock time (§3.2)
- Ships with the §3.2 table as the **prior**, every value marked MEASURED and
  every uncalibrated cell explicitly `prior`, never silently a fitted number
- Versioned and dated. Production reads a pinned version; a recalibration is a
  new version, reviewed, never an in-place edit

**Attack.** *"Seven slots × four DTE buckets × two classes × seven parameters is
392 free parameters fitted on — at best — a few months of data. This is not
calibration, it is a machine for manufacturing overfit."*

**Resolution — attack lands hard, spec changes materially.** 392 parameters is
indefensible and the artifact as first specified is wrong. Three changes:

1. **Parametric, not per-cell.** Fit a small number of *global* coefficients and
   let the slot enter through a measured **volatility ratio** `σ_slot / σ_day`
   and a measured **follow-through ratio**. `stop_sigma_mult` becomes one global
   constant times the slot's own σ — not a per-slot free parameter. This collapses
   the count from hundreds to under ten.
2. **Pooled across underlyings.** Class-level, not name-level. A per-name profile
   is unfittable at this sample size.
3. **A cell with fewer than a stated minimum of observations stays at its prior
   and is labelled `prior`.** It never receives a fitted value. The board and the
   report show which cells are fitted and which are inherited.

The slot structure survives because it is a real microstructure effect. The
*free parameters per slot* do not.

**Tests.** Parameter count is asserted under a ceiling — a test that fails if
someone adds a per-slot free parameter. A low-sample cell keeps its prior and is
labelled. A profile is immutable once versioned. Walk-forward calibration never
sees its own test window (the standing no-lookahead invariant).

**Done when** a dated profile version exists, with under ten fitted parameters,
each cell labelled fitted or prior.

---

#### A321 — Momentum signal core

**Purpose.** One signal function, generalised from `generate_signal`, that turns
a closed-bar series plus a session profile into a direction, a regime, a
confidence and an initial structural stop level.

**Contract.**
- `backend/app/engines/orb_scalper/signal.py`
- Reuses ORB's existing vocabulary: opening range, `breakout_distance` in ATR,
  VWAP side and slope, `volume_ratio`, `Regime`
- **Changes from ORB:**
  - Breakout requires a **bar close** beyond the OR, not a touch (§3.3 cause B)
  - `opening_range_minutes` comes from the profile, per class and regime (§3.1)
  - New gate: **OR too wide** — reject when the OR exceeds a measured multiple of
    its own recent average; the day's range may already be spent
  - Emits the **structural stop level in underlying space** — the OR level or
    `entry − k·σ_slot`, whichever is nearer — so the exit engine never has to
    invent one
  - Emits `sigma_slot` alongside ATR, so every downstream distance is in σ units
  - Refuses on a degraded σ (A312) instead of returning a number
- **Gates reject; they never invert.** This invariant is inherited from
  `atm_premium_imbalance/signal.py` and is non-negotiable: a filter that flips a
  long into a short is a second, unvalidated strategy hiding inside the first

**Attack.** *"Close-confirmation costs you the move. On a 5-minute bar you enter
up to 5 minutes and several σ after the break — on a scalp, that is the entire
edge given away to avoid a wick."*

**Resolution — attack lands, and it forces an explicit trade-off rather than a
default.** Both horns are real: touch-entry buys wicks, close-entry buys
late. So the confirmation interval becomes a **profile-owned parameter with its
own measurement**, and the candidate set is small and explicit — confirm on the
1-minute close inside a 5-minute signal bar, or on a *price-and-time* condition
(price holds beyond the level for K seconds), which is cheaper than a full bar.
Which one wins is measured (A362) on the captured data, per slot. Shipping
either as a hardcoded default would be exactly the "declared a rule from samples
that happened to agree" error the dossier's four corrections warn about.

**Tests.** A wick that does not close produces no signal. A close beyond the OR
does. A gate never inverts a direction (property test over generated inputs). A
degraded σ refuses. The currently-forming bar can never produce a signal —
`as_of` discipline, already tested in `test_nifty_orb_universe_repaint.py`, is
carried over.

**Done when** the signal reproduces ORB's decisions on ORB's fixtures where the
rules agree, and every divergence is explained by a named new gate.

---

#### A322 — Premium imbalance as a *vehicle-selection* input · **REJECTED, as scoped**

**Purpose as specified.** Feed `|CE − PE|` at the ATM strike into contract
selection, as a read on which leg is better value.

> **Scope note, per Amendment A300.2.** This artifact is about using the imbalance
> to pick a *contract*, and in that role parity really does make it redundant. It
> is **not** a judgement on the imbalance as a **signal** — that was the overreach
> A300.2 withdraws, and it is restored as **A325**.

**Attack.** *"By put-call parity, `CE − PE ≈ F − K`. The selector already knows
spot, the strike, the expiry and the rate — so it can compute `F − K` directly
and to better precision. The premium difference therefore carries **no
information the selector does not already have**, except the part attributable to
skew — and that part is contaminated by two independent stale quotes, which is
the exact fault the session-origin gate exists to catch."*

**Resolution — attack succeeds. The artifact is rejected and replaced.**

The useful signal in "which leg is cheaper" is not the premium difference; it is
the **implied-volatility difference at equal moneyness** — the skew. That is a
real, tradable observable, and it is not recoverable from a raw premium
subtraction. So:

- **Rejected:** `|CE − PE|` as a selector input. It is a redundant, noisier
  restatement of `F − K`.
- **Replacing artifact — A322b, IV-and-skew read.** Solve IV per leg from the
  traded premium (`nifty_orb_greeks.py` already implies delta this way, and the
  `TradePlan.delta_source` vocabulary of `broker` / `implied` / `assumed` is the
  right honesty model to extend). Feed **IV level** and **skew** to the selector:
  IV level scales expected move and therefore the target; skew says which leg is
  richly priced. Both are labelled by source, and `assumed` never reaches a live
  sizing decision.
- The demotion of premium imbalance from *signal* (§1.1) to *nothing* is
  complete. This is the right outcome: it was never carrying information.

**Note for the record.** This does not invalidate the ATM Premium Imbalance
dossier. That artifact set documents what a third-party bot *did*, with
provenance, and remains correct as forensics. This finding is about whether the
rule carries edge, which the dossier already declines to claim.

---

#### A323 — Candidate admission and ranking

**Purpose.** Turn N signals into at most K positions, deterministically.

**Contract.**
- `backend/app/engines/orb_scalper/admission.py`
- Reuses `nifty_orb_universe.scan_universe`'s structure — bounded concurrency,
  per-instrument failure isolation, deterministic sort with symbol as final
  tie-break. That design is correct and is kept
- **Changes:** reads the A311 eligibility list rather than a config array; reads
  the A320 profile for `min_confidence` and `max_concurrent` per slot; ranks on
  **expected net edge**, not raw confidence
- `expected_net_edge = confidence × expected_move_in_premium − modelled_round_trip_cost`
  where the cost term is A363's, per contract, including the measured spread.
  A high-confidence signal on a wide-spread contract must lose to a
  medium-confidence signal on a tight one — ranking on confidence alone is how a
  scanner fills the book with the least tradable names
- Admission is subject to A332's portfolio and correlation budget, which can
  refuse a candidate that ranks well

**Attack.** *"Ranking by expected net edge multiplies a calibrated-ish confidence
by a modelled move and subtracts a modelled cost. Three models compounding —
the ranking is more likely to reflect model error than signal quality."*

**Resolution — attack lands, spec narrows.** It is used as a **filter and a
tie-break, not a score**. Concretely: a hard admission floor
(`expected_net_edge > 0` with a stated margin — refuse anything whose modelled
edge does not clear its modelled cost) and then rank by the *measured* quantities
only — spread, depth, σ-normalised breakout — with confidence as one term. The
compounded model decides *whether*, never *how much*. And every refusal on the
edge floor is logged with its three terms, so model error is visible in the
ledger rather than buried in an ordering.

**Tests.** Deterministic for fixed input. A wide-spread high-confidence candidate
loses to a tight-spread lower-confidence one. `max_concurrent` is honoured. A
per-instrument failure does not fail the scan; a bad config does. The edge floor
refuses and reports all three terms.

**Done when** a scan over the full eligible universe completes inside its
interval and every refusal names its reason.

#### A324 — Signal registry

**Purpose.** Let the engine host more than one signal without either of them
knowing about the other. Added by Amendment A300.2.

**Contract.**
- `backend/app/engines/orb_scalper/signals/__init__.py` — a registry; one module
  per signal, each conforming to one protocol
- The protocol is deliberately narrow: `evaluate(state) -> Signal | None`, where
  `Signal` carries direction, confidence, the **structural stop in underlying
  space**, `sigma_slot`, and a `signal_id`. Everything downstream — selector,
  sizer, portfolio, the three clocks, the audit log — is keyed on `signal_id` and
  otherwise indifferent to which signal fired
- Each signal declares the **slots it is eligible for**, so the 09:15-09:20 window
  is claimed by the imbalance signal and the momentum signal simply never offers a
  candidate there (Amendment A300.1)
- **Gates reject, never invert** — inherited, and now enforced at the registry
  boundary so a signal module cannot flip another's direction
- Per-signal risk budget: a signal cannot consume the whole portfolio allocation.
  A322/A325's unmeasured status must not be able to spend the book

**Attack.** *"A registry is premature abstraction. Two signals do not need a
plugin system, and the protocol will be wrong because it is being designed from
one and a half examples."*

**Resolution — attack lands, and the spec shrinks to match.** No plugin system, no
dynamic loading, no configuration-driven dispatch. It is a `dict` of two entries
and one dataclass, and the protocol contains only the fields the *existing*
downstream artifacts already consume — which is why it can be gotten right: it is
derived from consumers that are already specified, not from imagined future
signals. If a third signal ever needs a field this protocol lacks, the protocol
changes then. What the registry buys today is the thing that matters: **neither
signal can special-case the other**, and the audit log can attribute every trade
to one of them, which is the precondition for A362 comparing them.

**Tests.** A signal offering a candidate outside its declared slots is refused.
Direction cannot be inverted across the boundary. Per-signal budget binds. Every
trade record carries a `signal_id`.

---

#### A325 — The open-imbalance signal, restored

**Purpose.** The source strategy, as a first-class signal, tested on its own
terms. Added by Amendment A300.2, which withdrew its demotion.

**What it is.** At the open, buy the cheaper ATM leg — read as a **gap-fade with
convexity**: the ATM strike sits near wherever the overnight gap left spot, so the
cheaper (out-of-the-money) leg is a cheap, high-convexity bet against the gap.

**Contract.**
- `backend/app/engines/orb_scalper/signals/open_imbalance.py`
- **Computed correctly, which is A322's surviving lesson.** The decision quantity
  is `F − K` — computed from spot, strike, expiry and rate — **not** a subtraction
  of two independently-stale premiums. The premiums are then used for what they
  are good for: the executable price, and the skew (A322b)
- Scaled per ideas 1-3: every underlying on A311's eligibility list, not SENSEX
  only. The signal is underlying-agnostic; only the strike ladder differs
- Eligible slot: **09:15-09:20** only, by default. It is an open-auction strategy
- Exits through the three clocks like everything else. **The observed
  `+15 points` becomes one candidate target among those A362 tests** — it is a
  SENSEX-specific constant and cannot be right for every underlying at every
  premium level, which is the same points-versus-percent error the dossier already
  identified for stops
- **Not** a copy of `atm_premium_imbalance`. That engine stays frozen; this is a
  fresh signal module expressing the same idea over the shared substrate, so the
  conformance artifact keeps its evidence and this one is free to be scaled and
  measured

**Attack.** *"This is the unmeasured strategy the plan spent §1.1 arguing against,
readmitted because the user pushed back. Either the parity argument mattered or it
did not — reinstating the signal one turn after rejecting it is deference, not
analysis."*

**Resolution — attack lands on the process, and the distinction has to be made
precisely.** Both positions cannot be right, so here is which part of the original
argument survives and which does not:

- **Survives:** the imbalance is a redundant and noisier way to compute `F − K`.
  Consequence — the *implementation* changes, and this artifact computes `F − K`
  directly. That is a real correction and it is kept.
- **Does not survive:** "therefore the quantity has no edge." That never followed.
  The algebra identifies *what* is being bet on; it says nothing about whether the
  bet pays. Nobody has measured it.

So the reinstatement is not deference — it is the removal of a conclusion the
evidence never supported. And the test is symmetric: A325 faces **exactly** the
gate A321 faces, on net-of-cost trades, with no allowance for having been the
original idea. If it fails A362 it does not trade, and the recordings' three
winning sessions will not save it.

**Tests.** The decision quantity is `F − K`, asserted never to be derived by
subtracting two premiums. Refuses outside its declared slot. Refuses on a stale or
undatable quote (session-origin gate). Reproduces the recordings' *direction* on
the decoded sessions — the one conformance claim available, and it is about
direction only, never P&L. Scales to a non-SENSEX underlying with no code change.

**Done when** it emits directionally-correct signals for every decoded session and
runs over the full eligibility list.


---

### Layer C — Vehicle and sizing

#### A330 — Contract selector

**Purpose.** Given a direction and an underlying, choose the contract to buy.

**Contract.**
- `backend/app/engines/orb_scalper/selector.py`
- Reuses `select_option`'s existing gate set — expiry preference and DTE window,
  `max_spread_pct`, `min_option_volume`, `min_open_interest`,
  `max_quote_staleness_s` — all of which are correct and stay
- Reuses `selection.resolve_pair`'s discipline: contracts come from the listed
  master, **never synthesised by string formatting**. A fabricated instrument key
  is an order that rejects or, worse, hits a contract nobody chose
- **Moneyness defaults to slightly ITM, delta 0.55–0.65**, not ATM. For a
  scalp, ITM gives a tighter relative spread and higher delta — more premium
  movement per underlying point and less of the position in extrinsic value
  that theta will take. The repo already reached this conclusion once
  (`option_moneyness: ITM`, `option_steps_itm`), and the ST strategy audit
  recorded the same verdict: spot signals, deep-ITM vehicle
- Requires the session-origin gate (`is_session_origin`, three-valued) on both
  legs before any pricing. Inherited from ATM PI unchanged — proven-stale refused
  always, undatable refused in live
- Emits IV and skew from A322b, labelled by source

**Attack.** *"ITM contracts on stock options are frequently the *least* liquid
line in the chain — retail flow concentrates at ATM and OTM. Preferring ITM for
tighter spreads may select strictly worse fills on exactly the names idea 3 is
about."*

**Resolution — attack lands, spec changes.** Moneyness stops being a preference
and becomes a **measured choice per underlying**: the selector scores the
candidate strikes on their *own measured* spread and depth (A310/A311 data) and
picks the best executable delta inside the 0.45–0.75 band, rather than stepping a
fixed number of strikes ITM. The ITM bias survives as a tie-break, not a rule.
This also removes `option_steps_itm` as a free parameter, which is the right
direction (§A320's attack).

**Tests.** A contract failing any gate is rejected and names the gate. No
instrument key is ever constructed. Delta band is honoured. A stale leg refuses.
Selection is deterministic for fixed inputs. `assumed` delta never reaches a live
sizing path.

---

#### A331 — Position sizer and ladder feasibility

**Purpose.** Convert a risk budget into a whole number of lots, and state
plainly what exit structures that number can express.

**Contract.**
- `backend/app/engines/orb_scalper/sizing.py`
- Sizing is on the **full premium outlay**, not the modelled stop distance. This
  is already fixed in ORB's `build_trade_plan` and the reason is recorded there:
  sizing by the stop produced 2,400 units of an 18-rupee option — ₹43,200 of
  premium — while reporting "risk 3,000". Keep it fixed
- Lot size is read from the instrument master, **never assumed**. It changes by
  contract and over time; a hardcoded number is a wrong order
- Reuses `config.sizing_blocker`'s pattern: one function answers both the board
  and the arm path, and names the two nearest workable sizes
- **New: ladder feasibility.** Returns an explicit `ladder_mode`:

  | Lots | Mode | Behaviour |
  |---|---|---|
  | ≥ 3 | `THIRDS` | T1 ⅓, T2 ⅓, runner ⅓ |
  | 2 | `HALVES` | T1 ½, runner ½ |
  | 1 | `SINGLE` | No ladder. One target or pure trail |

  The mode is **published on the board row and in the trade record**. A
  configured ladder that the size cannot express must degrade *visibly* — silently
  ignoring it is the same bug class as the pydantic mirror that dropped nine
  settings while the UI looked like it had saved

**Attack.** *"Sizing on full premium outlay is far too conservative for a
strategy with a real stop. A ₹25,000 cap on outlay against a stop that risks 20%
of premium means the actual risk per trade is ₹5,000 — so the operator is capped
at a fifth of the risk they authorised, and the strategy is starved."*

**Resolution — attack lands, and it exposes a genuine ambiguity in the current
config.** Both quantities are real and they are not the same thing, so both must
be stated and both must bind:

- `max_premium_outlay_inr` — the most that can be *spent*. Binds because an
  option can go to zero (gap, halt, expiry) and then the outlay *is* the loss.
- `max_risk_per_trade_inr` — the most that can be *lost at the structural stop*.
  Binds normally.

Size is `min()` of the two. Naming only one is what created the objection: the
existing `max_premium_at_risk_inr` conflates them, and its own docstring argues
both sides ("the outlay *is* the risk"). It is the outlay in the tail and the
stop distance in the body, and a scalping strategy lives in the body. Splitting
the two is the fix, and it must be a **rename with a migration**, not a silent
reinterpretation of a persisted field.

**Tests.** Quantity is always whole lots. Both caps bind independently and the
binding one is named. Ladder mode matches lot count at every boundary (1, 2, 3).
A configured ladder with 1 lot reports `SINGLE` and says so. Migration of a
persisted `max_premium_at_risk_inr` is asserted.

---

#### A332 — Portfolio allocator and correlation budget

**Purpose.** Stop N independent good decisions from adding up to one bad one.
**This is the highest-value new artifact in the whole plan.**

**Why.** Forty long calls across forty NIFTY constituents on a momentum morning
is not forty diversified ₹25,000 risks. It is a single ₹1,000,000 long-beta bet
wearing forty names, taken without anyone deciding to take it. This is how
multi-underlying rollouts fail, and it is invisible to every per-trade limit in
the current build.

**Contract.**
- `backend/app/engines/orb_scalper/portfolio.py`
- Wires the existing `correlation_tracker` singleton (`CorrelationTracker.update()`
  on every evaluate is a standing project invariant — it must be honoured here,
  not reimplemented)
- Budgets, all binding at admission time:
  - `max_concurrent_positions` — absolute
  - `max_gross_outlay_inr` — total premium deployed
  - `max_net_delta_inr_per_underlying` and **`max_portfolio_net_delta`**, the
    latter expressed against a benchmark (NIFTY) using each name's beta, so
    forty correlated longs register as one large delta rather than forty small ones
  - `max_positions_per_sector` and `max_correlation_cluster_exposure`, computed
    from the correlation matrix rather than from a static sector map
- `admit(candidate) -> Decision` returns admitted or refused **with the binding
  budget named**
- Wires the existing `dd_circuit_breaker` / `DrawdownCircuitBreaker` — and the
  standing invariant that it runs **first** in the evaluate path applies here too

**Attack.** *"Correlation estimated intraday on a handful of bars is noise.
Budgeting against a noisy matrix will refuse good trades in a pattern that looks
like a rule but is arbitrary — and worse, it will fail to refuse on the day that
matters, because a correlation spike is exactly what a crisis morning does to the
estimate."*

**Resolution — attack lands, spec changes to a floor rather than an estimate.**
An intraday-estimated correlation matrix is the wrong instrument. Instead:

1. **Beta to the benchmark, estimated on daily data over a long window** — stable,
   well-conditioned, and the quantity that actually matters for "am I just long
   the index".
2. **A stress assumption, not an estimate, for the tail:** budget as if
   correlation were **1.0** within an asset class. If the portfolio is
   unacceptable under `ρ = 1`, it is unacceptable — because that is what a
   crisis morning delivers, and it is precisely when the estimate would have said
   0.4. This turns the budget from a forecast into a floor, which is what a risk
   limit should be.
3. Intraday correlation is still *tracked and displayed* (the singleton's job),
   because a spike is information for the operator. It just does not size
   anything.

**Tests.** Forty correlated candidates admit far fewer than forty. The binding
budget is named on every refusal. `ρ = 1` stress is applied within class. The
drawdown breaker runs before any quote arithmetic. Correlation tracker is
updated on every evaluate (the standing invariant, asserted).

**Done when** a scripted forty-correlated-candidate morning admits a bounded,
explained subset.

---

### Layer D — Execution and exits

#### A340 — Adopt the shared position layer · **EXTRACTION WITHDRAWN**

**Superseded by Amendment A300.1.** The first draft specified extracting the ATM
engine's order machinery into `engines/common/option_position/`. Withdrawn: ORB,
Navigator, auto-exec and hand-placed board orders already feed
`services/kite_engine/{positions, protection, protective_stop, monitor}`, so the
extraction would have created a **second** position layer beside the one in use —
two registries, two protection paths, two places a stop can be wrong.

**What replaces it.** The scalper is a consumer of the existing shared layer, and
the ideas worth keeping from the ATM engine are *ported into* that layer where it
lacks them:

| Idea | Where it lives now | Port to shared? |
|---|---|---|
| **Intent** pattern — engine describes, caller performs | ATM engine only | Yes. It is what makes replay a real test of the live path |
| Phase machine, exhaustive by phase | ATM engine only | Yes — `execute_scan` is a 120-line fire-and-forget with JSON-blob state |
| `UNKNOWN → RECONCILE`, never a retry that could double | ATM engine only | **Yes, highest priority.** A real-money invariant |
| Fill-not-limit accounting | ATM engine only | Yes |
| Session-origin gating, three-valued | ATM engine only | Yes |
| Broker-side OCO GTT + `move_stop` trailing | **shared, already** | Already there — use it |
| Registry, tick subscription, expiry square-off | **shared, already** | Already there — use it |

The ATM engine itself takes **zero changes**, which is the point: its conformance
evidence survives because nothing touches it.

**Attack.** *"Porting five ideas into a shared layer that four engines already
depend on is more dangerous than the extraction was. A regression in `kite_engine`
breaks Navigator and auto-exec — live paths with real money — where a regression
in a fresh `common/` module could only break the new engine."*

**Resolution — attack lands, and it sets the order of work.** The risk is real and
it decides sequencing rather than direction: a second position layer is the worse
end state, so the shared layer is still the right home, but each port lands as
**one commit, behind the existing tests of every consumer**, in ascending order of
risk — session-origin gating first (purely additive, a new refusal), then
fill-not-limit, then `UNKNOWN → RECONCILE`, then the phase machine, and the Intent
refactor last or not at all. **Any port that cannot be made additive is not made.**
`live_safety.assert_safe_to_trade` already guards the consumers and its tests are
the regression net.

**One behaviour change, and it is a fix (§1.3):** entry pricing gains an explicit
slippage budget — price through the ask by `min(k × spread, budget_points)` and
**refuse** when the ask is further than the budget from the decision price. A
missed entry is free; a bad entry is not. Lands separately, after every port, so a
failure has exactly one possible cause.

**Done when** the scalper opens, manages and closes a position entirely through the
shared layer, and no second registry exists.

#### A341 — Three-clock exit engine

**Purpose.** Implement §3.3. This is the direct answer to your question 12.

**Contract.**
- `backend/app/services/kite_engine/exits.py` — pure, no I/O, no clock. **Shared,
  per A300.1**, so every engine gains the structural stop and the time stops
- Three independent evaluators. Whichever fires first wins. Each returns a
  distinct named reason, because "stopped out", "gave back a win", "ran out of
  time" and "the exchange closed us" are four different outcomes and the log must
  not blur them (a discipline ATM PI already gets right with `stop_hit` /
  `breakeven_stop_hit` / `trailing_stop_hit`)

**Clock 1 — structure.** Underlying space, close-confirmed, ratcheting:

```
rung 0   initial      min(OR level, entry − k·σ_slot)
rung 1   break-even   MFE ≥ 1R          → stop to entry
rung 2   chandelier   MFE ≥ 1.5R        → highest_close − k·σ_slot
result = max(rung 0, rung 1, rung 2)      # monotonic, never moves down
```

- Ratchets and fires **only on completed bar closes**. This is what defeats your
  −20 wick: a wick has no close
- The high-water mark is the highest **close**, and it lives on the position, not
  in the policy — ATM PI's reasoning holds and its trap is inherited: default it
  to the entry, never to `last_price`, or every price becomes its own peak
- Distances in σ_slot units (§3.2), so the same rule breathes correctly at 09:30
  and at 13:00

**Clock 2 — time.**
- `max_hold_bars` — hard
- **`no_progress_bars`** — exit if MFE < 0.5R by bar N. Theta is certain; the
  edge is not. This is the highest-value single addition to the exit model and it
  is absent from every version of this build
- Session-end square-off wins over everything (ATM PI's `close_at_session_end`
  is correct and is inherited)

**Clock 3 — catastrophe.** Premium space, resting at the broker (A343).

**Attack.** *"Close-confirmation is exactly the flaw you fixed in the simulator.
Between two closes the price can travel far past the stop, and on a 0-DTE option
a 5-minute unconfirmed excursion can be 40% of premium. You have replaced a stop
that fires too early with one that fires too late — and the dossier already
records that minute bars have no intrabar order, so you cannot even measure which
is worse."*

**Resolution — attack lands, and it is the reason clock 3 is not optional.**
Close-confirmation is *deliberately* the slower stop; it exists to not be
whipsawed, and its cost is exactly the excursion described. That cost is bounded
by clock 3, which is intrabar, broker-side, and set at roughly twice the
structural distance. So the two are a matched pair and neither is complete alone:
clock 1 decides *when the thesis is wrong*, clock 3 decides *how much this trade
may cost while clock 1 makes up its mind*. Naming clock 3 "optional protection",
as `protection_mode = NONE` does today, is therefore wrong — with
close-confirmed structural stops it is **load-bearing**, and the live gate must
require it (it already does; the reasoning is now stronger).

On the measurement objection: it is correct and it is honest. The confirmation
interval cannot be chosen from minute bars. It is therefore listed in §9 as
requiring **tick** capture (A310's opt-in path) before any value is trusted, and
until then the default is the *tighter* of the candidates, because being early is
recoverable and being late is not.

**Tests.** Property: the structural stop is monotonic in the highest close.
A wick below the stop with a close above does not exit. A close below does. The
no-progress stop fires at exactly bar N. Session-end beats every other clock.
Each clock produces its own distinct reason. High-water defaults to entry.

---

#### A342 — Target ladder · **NOT CONFIRMED AS POLICY**

**Purpose.** Implement T1/T2/runner with partial exits (§3.3).

**Contract.**
- Part of `exits.py`. R-multiples relative to the initial structural risk
- `THIRDS` / `HALVES` / `SINGLE` from A331, chosen by lot count
- On T1: exit the tranche, **ratchet the stop to break-even**. On T2: ratchet to
  T1. The ratchet is monotonic and shares clock 1's `max()` discipline
- Each tranche is a separate broker order with its own id, its own fill and its
  own record. A partial fill on a tranche must not be double-counted, and the
  remaining quantity is recomputed from **confirmed fills**, never from intent
- Broker-side protection quantity is **reduced** as tranches close, and the
  reduction is confirmed before the next tranche is sent — the same
  cancel-and-confirm discipline as ATM PI's exit path, for the same reason

**Attack.** *"Scaling out reduces expectancy in a positively-skewed strategy. You
say so yourself in §3.3. So this artifact ships a mechanism whose expected effect
on returns is negative, with four new free parameters (T1, T2, split ratios), for
a strategy with zero validated parameters — chosen from data that does not exist
yet."*

**Resolution — attack succeeds on the policy, fails on the mechanism.**

- **The mechanism is confirmed.** It is needed regardless: partial exits, tranche
  accounting and protection-quantity reduction are hard to retrofit safely, and
  getting the order lifecycle right is independent of whether the ladder is used.
- **The policy is NOT confirmed.** No T1, T2 or split ratio is specified in this
  document, and none may be set by hand. `ladder_mode` defaults to **OFF** (full
  position on the clock-1 trail) because that is the higher-expectancy prior for
  momentum, and it may be switched on only per-slot by A362 with the payoff
  distribution attached.
- Ships with an explicit statement on the board and in the config: *scale-out is
  a variance-reduction tool, not a return-enhancement tool.* An operator turning
  it on should know they are buying a smoother equity curve with mean P&L.

**Tests.** Remaining quantity always derives from confirmed fills. A tranche
partial fill is not double-counted. Protection quantity reduces and is confirmed
before the next tranche. Stop ratchet on T1 is monotonic. With `ladder_mode` off,
behaviour is byte-identical to the pure-trail path.

---

#### A343 — Structural stop and dead-man switch · **CORRECTED**

**Corrected by Amendment A300.1.** The first draft claimed no downside protection
existed and specified building a `STOP_LOSS_ORDER` mode. Both wrong: the shared
layer already places a broker-side **two-leg OCO GTT** carrying stop *and* target,
ratchets it with `move_stop`, and backs it with a tick monitor for intrabar exits.
The GTT is a *better* primitive than the SL-M I proposed — it lives at Zerodha,
survives disconnects, needs no resting margin, and OCO makes a double sell
impossible by construction rather than by careful coding on our side.

**What is actually missing** is not the primitive but the structure feeding it:

| Missing | Why it matters |
|---|---|
| A stop derived from **underlying-space structure** | Today's `stop_premium` is a premium level. §3.3 cause A — a premium-space stop is taken out by an air-pocket print |
| **Close-confirmed** ratcheting | `move_stop` ratchets on ticks. §3.3 cause B — a wick is a tick |
| Distances in **σ_slot** | §3.3 cause C |
| **Time stops**, hard and no-progress | §3.3 cause E. Absent everywhere in the platform |
| A **heartbeat** dead-man check | The GTT survives our death; nothing reports that we died |

So the artifact becomes: compute the three clocks in the shared exits module, and
express clock 1's result to the broker through the **existing** `place_stop` /
`move_stop` OCO surface. `move_stop` already carries a recorded fix worth
preserving — it once dropped the target and degraded OCO to a bare stop the first
time the trail ratcheted.

**Attack.** *"A GTT is triggered by Zerodha on LTP and fires a market sell. On a
0-DTE ATM contract in a spike that fills at a fraction of the trigger. You are
calling a market order a stop and budgeting risk against a number it will not
achieve."*

**Resolution — attack lands, and it changes what the artifact may claim.** A GTT
market sell is not a guaranteed price and must never be represented as one. The
catastrophe level is set with **explicit slippage assumed**, budgeted at the
measured depth-weighted price rather than at the trigger; the board and the trade
record show it as a *trigger*, never as a risk figure, and any risk figure carries
its assumption; and `max_premium_outlay_inr` (A331) exists precisely because
clock 3 can fail — it is the bound that survives when the stop does not fill where
it should. This is why both caps must bind and neither can be dropped.

**Tests.** Clock 1's structural stop reaches the broker through `move_stop` with
the target leg **intact after a ratchet**. Re-arm throttling holds under a rapid
ratchet. A tightening modification is never dropped (A344). The catastrophe level
is reported as a trigger, never as guaranteed risk. The heartbeat gap arms nothing
new but is surfaced.

#### A344 — Order rate governor

**Purpose.** Keep the system inside the broker's order limits, by construction.

**Contract.**
- `backend/app/services/kite_engine/rate_governor.py` — shared, per A300.1
- A single token-bucket-free **minimum-spacing pacer** in front of every order
  call. Minimum spacing, not a bucket — kitelake learned this the hard way: a
  token bucket cannot hold a sustained rate, and the burst it permits is exactly
  what breaches a per-minute cap
- Declared limits per second, per minute and per day, **verified against live
  Kite documentation at build time and recorded with their source** (current
  documentation indicates 10/second and 200/minute for orders; do not copy these
  figures from here)
- Priority classes, because not all orders are equal:
  `EXIT > PROTECTION > ENTRY > TRAIL_MODIFY`. Under pressure, trail modifications
  are dropped first and entries second; an exit is never queued behind a trail
  update
- A dropped trail modification is **logged**, not silent — the structural stop
  and the broker stop then disagree, and the operator must be able to see that

**Attack.** *"Deprioritising trail modifications means the broker-side stop
lags the real one during exactly the fast market where it matters. The governor
protects the API budget by degrading the safety layer."*

**Resolution — attack lands, and it inverts part of the priority.** The failure
mode described is real: dropping trail updates when the stop is *tightening* is
backwards. Refined rule — a trail modification that **tightens** the broker stop
is promoted to `PROTECTION` priority; only a modification that loosens or
merely tracks a rising stop at unchanged risk is droppable. Combined with
throttling on movement threshold (A343), the number of tightening modifications
is small, so this costs little budget. The general principle: rate limiting may
degrade throughput, never protection.

**Tests.** Sustained rate never exceeds the declared limits. An exit is never
queued behind a trail modify. A tightening modify is not dropped. A dropped
modify is logged. Spacing holds under a burst.

---

### Layer E — Risk and control

#### A350 — Portfolio risk supervisor

**Purpose.** One place that can stop everything, and one place that decides
whether trading may continue at all.

**Contract.**
- `backend/app/services/orb_scalper/supervisor.py`
- Runs **before** any signal work on every cycle. The standing project invariant
  is that `DrawdownCircuitBreaker.update()` is first in `evaluate()`; the same
  ordering applies here and for the same reason — a breached limit must not be
  arguable with by an attractive price
- Enforces, in order: drawdown breaker → daily realised loss → open-risk ceiling
  → concurrency → correlation budget (A332) → per-underlying limits
- **All money limits are currency-explicit.** Memory records that the daily-loss
  breaker previously read 0.00 for USD-denominated positions and never halted; a
  currency-ambiguous threshold is still an open item in that note. Every limit in
  this artifact carries its currency in the field name (`_inr`) and the reader
  asserts the position's currency matches, refusing rather than defaulting
- Zero is never "unlimited". A limit is refused at zero (ATM PI's convention,
  which is correct — an "0 means unlimited" rule is one typo from no limit)
- A **kill switch**: one call that cancels every working order, squares off every
  open position at market, and refuses to arm again without an explicit reset

**Attack.** *"'Square off everything at market' on forty illiquid option
positions simultaneously is itself a large loss event — the kill switch is a
button that guarantees the worst fills of the day, so nobody will press it, so it
is not a control."*

**Resolution — attack lands, spec changes.** Two-stage: **HALT** (stop all new
entries, keep managing existing positions on their normal exits) and **FLATTEN**
(square off now, accepting the fills). HALT is the automatic response to every
breached limit, and it is safe to trigger — so it will actually be used. FLATTEN
is manual-only, or automatic on a narrow set of genuine emergencies (feed dead
beyond a bound, broker rejecting, authentication lost), because in those cases
managing positions is not on offer anyway. Conflating the two is what makes a
kill switch unpressable.

**Tests.** The breaker runs before quote arithmetic. A breached limit HALTs and
names itself. A currency mismatch refuses rather than reading zero. Zero is
refused at config. FLATTEN requires an explicit reset to resume. HALT preserves
exit management for open positions.

---

#### A351 — Reconciliation at portfolio scale

**Purpose.** Restart mid-session with forty positions and end up in a correct
state, or refuse.

**Contract.**
- Generalises ATM PI's `orphan_positions` / `adopt`
- On start: read every open position from the broker, match against persisted
  session state, and classify each as `matched`, `orphan` (no session explains it)
  or `ghost` (a session expects it, the broker does not have it)
- **Orphans block arming and are adopted by symbol, on request, never
  automatically.** Inherited, and the reasoning is unchanged and correct: a long
  option might be a hand-placed trade, and quietly taking control of someone
  else's position is worse than telling them about it
- An adopted position is honest about what it cannot know: high-water seeded from
  the **entry**, not the current price, so a trail resumes from scratch rather
  than from an invented peak. `TradeRecord.adopted` marks it. All inherited
- **New at scale:** a `ghost` — state says we are long, the broker says we are
  flat — is at least as dangerous as an orphan and has no handling today. It must
  **HALT**, not resolve itself, because the two most likely causes are a fill we
  missed and a position someone closed by hand, and those need opposite responses
- Persisted state must be written before an order is sent, not after, or a crash
  between send and write produces an orphan that looks like a hand trade

**Attack.** *"Adoption refuses when the resolved ATM has moved on — correct for
one pair, unworkable for forty. By 11:00, spot has moved and most adopted
positions will be at strikes the selector would no longer choose, so a restart
mid-session will refuse to adopt nearly everything and leave forty positions
unmanaged. The safe-looking rule produces the least safe outcome."*

**Resolution — attack lands, and it is a real design error in the inherited
rule.** The current check exists to prevent watching one option's price in order
to sell a different one — a real hazard. But it conflates *selection* with
*management*. Adoption does not re-select; it manages an existing contract by its
own instrument key. So the rule is corrected: adoption binds to the **position's
own contract**, resolved from the broker's own symbol, and the ATM check is
dropped from the adopt path entirely. What replaces it is stricter and actually
targets the hazard: adoption refuses if the symbol cannot be resolved to a listed
contract, and every price used thereafter must carry that contract's own
instrument key — which the session-origin gate already enforces per leg. An
unmanaged position is the worst outcome available, and the old rule maximised it.

**Tests.** Orphan blocks arming and is reported. Ghost HALTs. Adoption binds to
the position's own contract regardless of where ATM has moved. An unresolvable
symbol refuses. State is written before the order is sent (asserted by a crash
injection between the two).

---

### Layer F — Validation

#### A360 — Replay harness on captured data

**Purpose.** Replay a real session, bar by bar or tick by tick, through the
**live** code path.

**Contract.**
- Generalises `atm_premium_imbalance_sim.py`, whose safety design is correct and
  is inherited wholesale: the session is marked `sim` and `on_ticks()` returns
  early for one; it refuses to start over a live armed session; it uses its own
  broker and `forget()`s its session so it can never hand back subscriptions a
  live session holds; and **`illustrative_only` rides in every payload**, so a
  client cannot render replayed numbers as live ones by forgetting a flag in one
  place. All of that is kept
- Extended to N concurrent positions and the full candidate scan
- Reads A310's captured data. Where only bars exist, the limitation is stated in
  the output, not in a footnote: minute bars have no intrabar order, so ticks are
  modelled walking O→H→L→C, which lets a peak set the trail before the low tests
  it — and a trailing stop's result depends on exactly that ordering
- Fills modelled at the **measured depth-weighted price**, not at the limit.
  ATM PI's simulator models fills at the limit and says so; that is optimistic
  and must not carry into a number anyone decides on
- **Inherits the fidelity discipline** ATM PI records: the replay must reach the
  same "no" by the same route as live. Its bug was refusing at 09:14 on the
  stale-quote gate when live refuses on market hours — teaching the wrong lesson
  about which gate protects you

**Attack.** *"A replay through the live path with modelled fills is still a
backtest wearing a costume. The shared code path proves the *logic* agrees; it
proves nothing about the *fills*, and for a scalping strategy the fills are the
entire result."*

**Resolution — attack lands and is accepted as a permanent limitation, not
solved.** The harness's claim is narrowed to what it can support: it validates
**decisions**, not P&L. Every output is labelled with its fill model, and a
P&L figure from a modelled fill may not be quoted as a result — only as a
ranking between policies evaluated under the *same* model. The thing that
validates fills is A363, against real fills from paper and then small live
trading. This is the same discipline the dossier applies to the existing
simulator and it is the correct one.

**Tests.** Sim ticks never reach a live session and vice versa. `illustrative_only`
is present in every payload shape (asserted structurally, not per-field). Refuses
over a live armed session. Live and replay refuse at 09:14 for the same reason.

---

#### A361 — Synthetic premium model · **NOT CONFIRMED FOR VALIDATION**

**Purpose as specified.** Reconstruct historical option premiums from underlying
bars plus a fitted IV surface, to get a longer history than A310 can accumulate.

**Attack.** *"The strategy's entire net result lives in the spread, the skew and
the depth. A Black-Scholes reconstruction from underlying bars produces none of
those — it produces a smooth mid-price with no bid/ask, no depth, and an IV that
was fitted from today's surface rather than measured on the day. Validating a
scalping strategy on it would measure the model's smoothness, not the strategy's
edge. Worse, it would produce *better* results than reality by construction,
because every friction that kills the strategy is absent."*

**Resolution — attack succeeds. Rejected for validation.**

Retained only as a **pre-screen** for the parameter search — a cheap way to
discard policies that fail even in a frictionless world — and explicitly barred
from producing any number quoted as a result or fed to A362's gate. It is
labelled `MODELLED` at every boundary, in the same spirit as
`TradePlan.delta_source`'s `assumed`.

**Consequence, stated plainly:** there is no shortcut around A310. The validation
timeline is bounded by how long the capture has been running, and the only way to
shorten it is to start capturing now.

---

#### A362 — Walk-forward, CPCV and the deflation gate

**Purpose.** Decide, with a pre-committed rule, whether this strategy has an edge.

**Contract.**
- Reuses the existing suite — `walk_forward.run_real`, `cpcv.run_cpcv` and
  `calculate_pbo`, `performance.deflated_sharpe`, `monte_carlo`. This kit already
  exists and is good; it does not need rebuilding
- **Fix first: `_DAYS_PER_YEAR = 365.0`** in `performance.py` is a crypto
  constant (its own comment says so). It must become a per-asset-class parameter
  at 252 for Indian equity derivatives. Every Sharpe and every deflated Sharpe
  computed through it today is inflated by `sqrt(365/252) = 1.20` — which is the
  width of the gate itself (§1.6)
- **Every metric is computed net of A363's costs.** ORB's validation module
  already separates gross from net and computes every decision metric from the
  net series, with the reasoning recorded: a trade green before charges and red
  after is a loss. Keep that, correct the constants
- No lookahead. The standing project invariant — never use the test window for
  threshold selection — applies to profile calibration (A320) as much as to
  thresholds
- The number of trials must be **counted and passed to `deflated_sharpe`**
  honestly, including every parameter variant tried across the whole programme.
  Under-reporting trials is how a deflated Sharpe stops deflating

**Pre-committed gate.** Written before the numbers are seen:

| Criterion | Threshold |
|---|---|
| Deflated Sharpe | ≥ 0.50 |
| PBO | ≤ 0.50 |
| Net profit factor | ≥ 1.25 |
| Out-of-sample net expectancy | > 0 |
| Result holds across ≥ 2 distinct volatility regimes | required |
| Sample | ≥ 100 net trades OOS |

**Attack.** *"Memory already records that after the DSR fix, no Sterling config
clears 0.5 — and the regime-book rework's best was 0.394 with a full cycle of
data. Setting the gate at 0.5 for a strategy with months of data and hundreds of
candidate parameters means the gate is a formality that will never pass, so it
will be argued down when the time comes."*

**Resolution — attack lands on the politics, not the statistics.** The threshold
is correct and is kept; what changes is that the *consequence of failing* is
specified now, in advance, so failing is a normal outcome rather than a crisis:

- **Fails the gate → the strategy runs in paper indefinitely and continues
  capturing.** That is a legitimate, useful state, not a defeat. Paper trading a
  strategy that has not proven edge costs nothing and accumulates the exact data
  the gate needs.
- The gate may be **lowered only by a written amendment to this document, dated,
  with the reasoning**, before the run that it applies to. Never after seeing a
  number.
- Trials are counted cumulatively across the programme in a checked-in ledger, so
  the deflation cannot be reset by starting a "new" search.

**Done when** the gate has been run once, and the result — pass or fail — is
recorded with its trial count.

---

#### A363 — Cost model re-derivation

**Purpose.** Replace the current cost constants with numbers derived from a real
contract note. **§1.2 makes this a blocker, not a nicety.**

**Contract.**
- Rewrite `TradingCosts`, keeping its structure (which is right) and replacing
  its constants
- Every rate carries its **source and effective date** in a comment, and a test
  fails when a rate is older than a stated age — so staleness becomes visible
  rather than permanent. The three suspected defects in §1.2 are all staleness,
  and none of them announced itself
- Derive from an actual contract note for an option round trip, and assert the
  model reproduces it to the rupee
- **Slippage stops defaulting to zero.** It becomes a required, measured input:
  per underlying, per slot, the median realised half-spread from A310 data. A
  scalping cost model with zero slippage is not conservative, it is wrong
- Model **depth-weighted** slippage, not half-spread, for sizes above top-of-book

**Attack.** *"Modelled slippage from historical spreads systematically
understates realised slippage, because the act of trading moves the price and
because the worst fills happen in exactly the fast conditions where quotes are
least representative."*

**Resolution — attack lands, and it defines the artifact's real end state.**
Modelled slippage is a starting estimate, not an answer. The artifact therefore
includes a **realised-versus-modelled reconciliation**, run continuously in paper
and live: every fill's actual price against the model's prediction, reported as a
distribution. The model is then corrected from *its own errors* rather than from
historical quotes, and a persistent bias is a finding, not a mystery. This is the
same pattern as `market_crosscheck.py` and A312's drift report — an assumption
that audits itself. Until the reconciliation has run, every net number carries a
stated slippage assumption.

**Done when** the model reproduces a real contract note to the rupee, slippage is
non-zero and measured, and the reconciliation report exists.

---

#### A364 — Promotion gate

**Purpose.** One coded gate between paper and real money. Code, not discipline.

**Contract.**
- Extends `config.validate()`'s existing live-mode refusal, which is already the
  right pattern: `execution_mode = "live"` raises unless every condition holds
- Live requires **all** of:
  - A362's gate passed, with the result and trial count recorded
  - A363's reconciliation run, with realised slippage inside a stated tolerance
  - `protection_mode = STOP_LOSS_ORDER` (never `NONE` — with close-confirmed
    structural stops, clock 3 is load-bearing, §A341)
  - `require_session_origin_tick = True`
  - Both money caps set and positive (A331)
  - A311 eligibility list dated within a stated window
  - A320 profile version pinned, with fitted cells identified
  - No research-only policy anywhere in the config
  - A313 capacity plan fits, with the subscription audit passing
  - Correlation budget configured (A332)
- Plus a **staged rollout**: one underlying, one lot, for a stated number of
  sessions, before the universe or the size may grow. Each stage has its own
  recorded result

**Attack.** *"A ten-condition gate will be satisfied mechanically. Someone will
set the two money caps to large numbers, pin a profile version whose cells are
all priors, and pass — every condition true, nothing actually validated."*

**Resolution — attack lands, spec changes.** Conditions that can be satisfied
vacuously are the weak ones, so they gain substance: the money caps must be
consistent with the validated size (the gate compares them against A362's tested
sizing and refuses a live size larger than the one that was validated); the
profile must have a stated minimum fraction of **fitted** cells for the slots
being traded, not merely be pinned; and the staged rollout is enforced by state,
not by intention — the config physically cannot express a wider universe until
the prior stage's sessions are recorded. A gate that can be passed by filling in
fields is a form, not a gate.

**Done when** live mode is unreachable without every condition, and the staged
rollout is enforced by persisted state.

---

### Layer G — Surfaces

#### A370 — Config registry and API

**Purpose.** One schema, one validator, no mirrors.

**Contract.**
- Backend: the engine dataclass is the **single validator**. No hand-written
  pydantic mirror at the API boundary — that exact pattern silently dropped nine
  settings while the UI looked like it had saved, because pydantic discards
  unknown keys. `test_every_config_field_is_settable` compares the served payload
  against the dataclass fields and must be carried over unchanged
- Unknown keys on PUT are **refused, not ignored**
- Frontend: settings live in `frontend/src/components/kite/config/registry.ts`,
  which is already the single source of truth per setting. Rescan is a property
  of the field; manual/auto is a tag, never duplicated storage
- Every setting carries its **provenance marker** (§ header) in the registry, so
  the panel can show OBSERVED / OURS / MEASURED / GATED — a MEASURED value that
  an operator hand-edits should look wrong on screen
- Config is **versioned**, and a config that fails today's validation cannot be
  loaded as a trading config. Validation lives in the engine, not the API, so a
  config persisted by an older build or edited in the database cannot become a
  trading config the engine rejects mid-session. Inherited, correct

**Attack.** *"Provenance markers in the UI are decoration. Nobody reads a badge,
and a MEASURED field that is hand-editable will be hand-edited."*

**Resolution — attack lands, spec changes from a label to a lock.** A MEASURED
field is **not editable in the panel at all** — it is displayed with its
calibration version and date, and changing it requires a recalibration or an
explicit, logged override that marks the config as `overridden` and **fails
A364's gate**. A badge that only informs is worth little; a badge that names a
state the gate can refuse is worth having.

**Tests.** No config field can be dropped by the API (carried over). Unknown keys
refused. A MEASURED field cannot be set through the normal path. An override
marks the config and fails the live gate.

---

#### A371 — Board

**Purpose.** Forty positions, readable.

**Contract.**
- **No new `EngineId`.** `'orb'` already exists and is already rendered; only its
  label changes. This is the simplification A300.1 bought — a third engine would
  have needed a new id, a new adapter and a new registry entry
- Uses the existing **parent/children** grouping, which already exists for
  exactly this: the parent holds what belongs to the idea (the underlying, where
  the signal came from, when it fired) and each child holds what belongs to one
  contract. The parent deliberately leaves price columns empty rather than
  borrowing a leg's numbers — a thesis has no premium
- `running` means **armed or in position**, never merely enabled. An
  enabled-but-unarmed row must not claim to be running. Inherited
- Every level nullable; a missing number renders `—`, never `0`. On a stop
  column a fabricated zero is a trade-destroying lie. Inherited
- **`BoardLevels` needs extending:** it has one `target`. The ladder needs
  `targets: (number | null)[]` plus the active `ladderMode` from A331, so a row
  can show which tranches are still open. This is a contract change affecting all
  five existing engines and must be additive — `target` stays as the first target
  for engines that publish one
- Sections carry what this engine knows that others do not: the slot and its
  profile version, σ_slot, the three clock states, the correlation budget's
  headroom, quote provenance (its own block — "refusing a carried-over price" and
  "no signal yet" are different situations and an operator must tell them apart
  without reading logs)

**Attack.** *"Forty rows with three clocks and a tranche ladder each is not a
board, it is a spreadsheet. The operator's actual job during a fast session is to
notice the one thing that is wrong, and this design buries it in forty rows of
correct information."*

**Resolution — attack lands, and it reorders the design.** The board is **not**
the primary surface during a session. Primary is a small **exception panel**:
positions that HALTed, ghosts, unsubscribed tokens, dropped trail modifications,
budget refusals, protection disagreements — anything where the system wants a
human. It is empty on a normal day, and an empty exception panel is the signal
that everything is fine. The forty-row board is the *reference* view behind it.
This inverts what the current single-position board does, correctly: with one
position, the position is the exception panel; with forty, it is not.

**Tests.** Parent rows publish no premium. Nulls render as `—`. `running`
requires armed. Ladder mode is visible per row. The exception panel is empty
when nothing is wrong and shows each exception class when it is.

---

#### A372 — Terminal log at portfolio scale

**Purpose.** Keep the log readable when forty positions are talking.

**Contract.**
- Inherits ATM PI's discipline, which is right: **transitions, not ticks**; a
  refusal is said once and again only when the *reason* changes; reasons are
  translated into words ("a quote traded before today's open", not
  `stale_session_quote`); an unmapped reason falls through as-is so a new gate is
  visible the day it is added; a rising peak that leaves the stop where it was is
  context, not an event
- **New at scale:** per-underlying dedup keys, and a **rollup** — forty
  simultaneous refusals for the same reason become one line with a count, not
  forty lines. The individual events remain in the audit log (A373)

**Attack.** *"Rolling up forty refusals into one line hides the case where
thirty-nine are routine and one is a genuinely new fault."*

**Resolution — attack lands, spec changes.** Rollup is **by reason**, so a new
reason can never be absorbed into an existing rollup — it gets its own line the
first time it occurs, which is precisely the "a new gate is visible the day it is
added" property, preserved at scale. Counts roll up; reasons never do.

---

#### A373 — Decision audit log

**Purpose.** Explain any trade, or any refusal, after the fact.

**Contract.**
- Every admission decision, refusal, entry, ratchet, tranche and exit persisted
  with its full input snapshot: quote, σ_slot, profile version, budget state,
  cost model version, and every term of the ranking
- Append-only, queryable by underlying and by session
- Sufficient to **replay a single decision** in isolation and get the same answer
  — which is the actual test of whether the log is complete

**Attack.** *"An audit log written on every tick-driven decision across forty
underlyings is a write-amplification problem that will become the system's
latency bottleneck, in the fast market where latency matters most."*

**Resolution — attack lands, spec changes.** Decisions are logged, ticks are not:
the log records **state transitions and refusal-reason changes**, which is the
same dedup rule as A372, so volume is bounded by events rather than by tick rate.
Writes are buffered and flushed off the decision path, and a flush failure is
surfaced rather than blocking a trade. The completeness test — replay one decision
from the log alone — is what keeps the dedup honest, because a decision that
cannot be replayed proves a field was dropped.

**Done when** an arbitrary past decision can be replayed from the log alone and
reproduces its original outcome.

---

## 5. Sequencing

The order matters more than the content. Three principles decide it:

1. **Data before decisions.** Every parameter in this plan is chosen from data
   that does not exist yet. The capture job is therefore first, and its value
   compounds from the day it starts.
2. **Never refactor what you cannot yet verify.** A340 extracts the one piece of
   code with real provenance. It happens *after* the replay harness can detect a
   behaviour change on real data — not before, and not in the same commit as any
   feature.
3. **Every phase ends at a gate that can fail.** A phase whose gate cannot fail
   is not a gate, it is a milestone with a ceremony.

### Phase 0 — Capture and correct · *no strategy work*

| Artifact | Why now |
|---|---|
| **A310** Option data capture | Nothing downstream is honest without it. Start today |
| **A363** Cost model re-derivation | §1.2. Every net number quoted before this is wrong, probably by 2–3× |
| **A362 (partial)** `_DAYS_PER_YEAR` fix | §1.6. A one-line fix that moves every Sharpe by 20% |
| **A311** Liquidity-earned universe | Bounds A310's cost and answers idea 3 on measurement |
| **A313** Feed capacity planner | Must exist before anything subscribes at scale |

**Gate 0.** One full trading day of the eligible universe on disk and readable.
The cost model reproduces a real contract note to the rupee. The eligibility
ledger states how many F&O names survived a real spread floor.

**This gate can fail interestingly.** If the eligible stock list is near-empty,
idea 3 is answered — by measurement, not by opinion — and the programme narrows
to indices before any code is written for it. That is the cheapest possible place
to learn it.

### Phase 1 — Signal, on paper, single position

| Artifact | |
|---|---|
| **A312** In-process bar factory | Removes the historical rate-limit bomb |
| **A324** Signal registry | Two entries and one dataclass, per A300.2 |
| **A325** Open-imbalance signal | The recorded strategy, restored and scaled |
| **A321** Momentum signal core | Generalised from ORB's `generate_signal` |
| **A322b** IV and skew read | Replaces the rejected A322 |
| **A330** Contract selector | |
| **A331** Sizer and ladder feasibility | Including the two-cap split |
| **A360** Replay harness | On A310's captured data |

**Gate 1.** The replay reproduces ORB's decisions on ORB's fixtures wherever the
rules agree, and every divergence is explained by a named new gate. In-process
bars reconcile against Kite history at zero drift for a full session. **A325
reproduces the recorded sessions' direction** — direction only, never P&L — and
neither signal can offer a candidate outside its declared slot.

### Phase 2 — Exits and protection

| Artifact | |
|---|---|
| **A340** Shared position lifecycle | The extraction. One commit, no features |
| — | *ATM PI golden trades must pass byte-identically before continuing* |
| **A340b** Slippage-budget entry | §1.3. Separate commit, after conformance |
| **A341** Three-clock exit engine | The answer to question 12 |
| **A342** Target ladder | Mechanism only. Policy stays OFF |
| **A343** Protection and dead-man switch | `STOP_LOSS_ORDER`, the missing mode |
| **A344** Order rate governor | |

**Gate 2.** ATM PI's conformance suite passes unchanged. The wick test passes: a
bar whose low breaches the stop but whose close does not produces no exit. The
no-progress stop fires at exactly bar N. Protection is armed before any other
post-fill intent.

### Phase 3 — Portfolio

| Artifact | |
|---|---|
| **A332** Allocator and correlation budget | The highest-value new artifact |
| **A350** Supervisor, HALT and FLATTEN | |
| **A351** Reconciliation at scale | Including the corrected adopt rule and ghosts |
| **A323** Admission and ranking | |
| **A320** Session profile calibrator | Under ten fitted parameters |

**Gate 3.** A scripted forty-correlated-candidate morning admits a bounded,
explained subset. A restart mid-session with N open positions ends in a correct
state or refuses. A ghost HALTs.

### Phase 4 — Surfaces

| Artifact | |
|---|---|
| **A370** Config registry and API | |
| **A371** Board and exception panel | Exception panel first, board second |
| **A372** Terminal log with reason-keyed rollup | |
| **A373** Decision audit log | |

**Gate 4.** An arbitrary past decision replays from the log alone and reproduces
its outcome. The exception panel is empty on a clean session.

### Phase 5 — The decision

| Artifact | |
|---|---|
| **A362** Walk-forward, CPCV, deflation gate | With the cumulative trial ledger |
| **A364** Promotion gate | Coded, with the staged rollout enforced by state |

**Gate 5 — the only gate that decides anything.** §A362's pre-committed
thresholds, on net-of-cost trades, with trials counted cumulatively.

**Expected outcome: it fails.** Memory records that no Sterling config clears
DSR 0.5, and the regime-book rework's best was 0.394 with a full cycle of data.
A strategy with a few months of capture and a large parameter search should be
expected to fail a deflation gate. That is why §A362 specifies the consequence in
advance: **paper indefinitely, capture continues**. Failing is the normal,
useful outcome — it costs nothing and it accumulates exactly the data the gate
needs. Passing on the first attempt would be the surprising result, and the
appropriate response to it would be suspicion.

---

## 6. Change map

What actually gets touched, so the blast radius is visible before work starts.
**Revised by Amendment A300.1** — there is no third engine and no extracted
`common/option_position`.

### The engine is renamed, as its own mechanical commit

`nifty_orb_*` becomes `orb_scalper` — flat modules promoted to a package. The
name is not cosmetic: an engine that scans every eligible index and F&O stock is
not "NIFTY ORB", and a misleading module name is how the wrong config gets
edited. But it touches every import and ~15 test files, so it lands **alone**,
mechanically, before any behaviour change.

### New — inside the existing engine

```
backend/app/engines/orb_scalper/          (was nifty_orb_*, promoted to a package)
    signal.py          A321   momentum core, generalised from generate_signal
    profile.py         A320   session profile + calibrator  (<10 fitted params)
    universe.py        A311   liquidity-earned eligibility  (absorbs nifty_orb_universe)
    bars.py            A312   in-process bar factory
    selector.py        A330   contract choice               (absorbs select_option)
    sizing.py          A331   two caps, ladder feasibility
    portfolio.py       A332   allocator + correlation budget
    admission.py       A323   ranking                       (absorbs scan_universe)
    config.py          A370   the single validator          (extends StrategyConfig)
backend/app/services/orb_scalper/
    supervisor.py      A350   HALT / FLATTEN
    reconcile.py       A351   orphans, ghosts, adoption at scale
    audit.py           A373   decision log
kitelake/option_capture.py    A310   the Phase-0 job
docs/strategy/session-scalper/       this plan
```

### New — inside the SHARED layer

This is where A300.1 moved the exit work, so every engine gains it rather than
one:

```
backend/app/services/kite_engine/
    exits.py           A341   the three clocks. Computes the structural stop;
                              expresses it through the EXISTING place_stop/move_stop
    tranches.py         A342   partial-exit accounting, protection qty reduction
    rate_governor.py   A344   minimum-spacing pacer, priority classes
```

### Modified

| File | Change | Risk |
|---|---|---|
| `analytics/performance.py` | `_DAYS_PER_YEAR` → per-asset-class | **Changes every historical metric in the repo.** Must be a parameter with an explicit default per class, never a global edit |
| `nifty_orb_validation.py` | Cost constants, non-zero slippage | Changes every ORB net number. Same care |
| `kite_engine/protective_stop.py` | Accept a structural stop; keep the OCO target leg through a ratchet | **Live money.** Four consumers. The `move_stop` fix that stopped it degrading OCO to a bare stop must not regress |
| `kite_engine/protection.py` | Heartbeat / dead-man reporting | **Live money.** Additive only |
| `kite_engine/monitor.py` | Close-confirmation, time stops | **Live money.** Today it ratchets on ticks; the new path must be opt-in per engine so Navigator and auto-exec keep today's behaviour until they choose otherwise |
| `kite_engine/positions.py` | Ghost classification | Additive |
| `exchanges/kite/ticker_manager.py` | Capacity + subscription audit | Shared with charts and the protection monitor. The refcount design is correct — extend, do not touch |
| `board/boardTypes.ts` | `targets[]`, `ladderMode` | Shared by five engines. **Additive only.** No new `EngineId` — `'orb'` already exists, only its label changes |
| `config/registry.ts` | New settings + provenance markers | |

### Frozen — do not modify

**The whole of `atm_premium_imbalance`** — engine, services, tests and documents
(A230, A231, A232, A280). Zero changes, which is the point: it imports stdlib
only, it is the only artifact with external provenance and a conformance test
against real recordings, and nothing in this plan needs it to change. A322's
rejection does not touch it either — the dossier never claimed the rule had edge,
and this plan's finding is about edge, not about what was observed.

The one thing that would justify reopening it: if a port into the shared layer
(A340) turns out to need a behaviour the ATM engine defines, take the *idea*, not
the file.

---

## 7. What this plan does not do

Named so the scope is honest.

**It does not add an indicator to `atm_premium_imbalance`.** That engine's value
is that it reproduces something with evidence. Adding momentum to it would make
the thing being validated a different strategy from the thing reconstructed —
which its own signal module already says, and which is correct.

**It does not promise the strategy works.** Every number in §3 is a prior. The
plan builds the machinery to find out, and the gate that decides. It is entirely
possible that the honest end state is: indices only, one slot, no ladder, paper.

**It does not trade stock options until they earn it.** Idea 3 is implemented as
a measurement (A311), not as a feature. If the spreads say no, the answer is no.

**It does not use synthetic premiums to shorten the timeline.** A361 is rejected
for validation (§4). There is no shortcut around capture.

**It does not touch the v3 risk singletons' invariants.** `dd_circuit_breaker`,
`correlation_tracker`, `calibration_service` are wired in as-is, honouring the
standing ordering rules, not reimplemented.

---

## 8. Answers to the twelve ideas

Direct, so nothing is lost in the specification.

| # | Your idea | Verdict |
|---|---|---|
| 1 | Not just SENSEX | **Yes.** A311 treats every index as a candidate on measured terms |
| 2 | All indices | **Yes, if they clear the floors.** No hardcoded allowlist |
| 3 | All F&O stock options | **Only what earns it.** A311. Expect a small survivor set; expect the spread floor to reject most. This is measurement, not refusal |
| 4 | First 40–60 min momentum window | **Yes, but not as a fixed number.** A320/A321: the window is the one after which the range stops expanding, per class and regime |
| 5 | Time-of-day profile | **Yes, and keyed on slot × DTE.** Your table becomes the prior (§3.2). The missing term was expiry: 0-DTE at 14:00 is a different trade from 4-DTE at 14:00 |
| 6 | Use momentum | **Yes — as the *second* signal, not the only one.** The recordings contain no momentum; it comes from this idea. Corrected in A300.2: the imbalance signal is **restored** (A325), not demoted. Both run over one substrate and are measured against the same gate |
| 7 | Your slot table | Adopted as prior, then measured. Midday becomes a higher bar, not a ban (§3.2) |
| 8 | Why those times work | Agreed on the mechanism. Added: intraday σ is U-shaped, so a fixed stop is wrong at every hour — which is the strongest argument for the profile and was not in the list |
| 9 | Improve freely | Done, and twice corrected by you: A300.1 (the ATM engine is independent; no third engine, no second position layer) and A300.2 (ORB came from your ideas, not the video — and I wrongly demoted your signal). Of my own artifacts: A322 rejected as scoped, A361 rejected, A342 held, A340 withdrawn, A343 corrected |
| 10 | Scalping focus | **The binding constraint, not a flavour.** §1.2: friction is ~29% of the observed +15 target on an index option and larger than the target on a wide-spread stock option |
| 11 | Algo, maximise | Intent pattern kept, rate governor added, capacity made arithmetic, every decision replayable (A373) |
| 12 | T1/T2/T3 vs TSL | **Answered in §3.3 — three clocks.** Your whipsaw objection is right and has five distinct causes; the fixes are: trail in *underlying* space, ratchet on *closes* not ticks, distances in σ not points, time stops because theta is certain, and a broker-side catastrophe stop so close-confirmation's slowness is bounded. The ladder ships as a mechanism with its **policy off**, because scaling out lowers expectancy in a positively-skewed strategy — it buys a smoother curve with mean P&L, and that trade must be chosen from a measured payoff distribution, not from preference |

---

## 9. Not confirmed

Three artifacts did not survive their attack, and two facts in this document are
unverified. Named here so they cannot be mistaken for settled.

### Rejected

**A322 — premium imbalance as a vehicle input.** Put-call parity makes `CE − PE`
a noisier restatement of `F − K`, which the selector already knows exactly. It
carries no information beyond skew, and the skew component is contaminated by two
independent stale quotes. **Replaced by A322b**, an IV-and-skew read, which
measures the thing that was actually wanted.

**A361 — synthetic premium model, for validation.** Reconstructed premiums have
no bid, no ask, no depth and a fitted IV. Every friction that determines whether
this strategy works is absent from them, so a validation run would flatter the
strategy by construction. **Retained only as a pre-screen**, barred from any
quoted number and from A362's gate. The consequence — that the validation
timeline is bounded by capture — is real and has no workaround.

### Confirmed as mechanism, not as policy

**A342 — the target ladder.** The mechanism is confirmed and must be built early,
because tranche accounting and protection-quantity reduction are hard to retrofit
safely. **No T1, T2 or split ratio is specified in this document and none may be
set by hand.** Default OFF. Turned on only per-slot, by A362, with the payoff
distribution attached.

### Facts to verify before they are relied on

**Broker limits.** The WebSocket instrument cap (documentation indicates 3,000
per connection, with a small connection count per key) and the order rate limits
(indicated 10/second, 200/minute) are quoted from memory of Kite's documentation.
**Verify against live documentation at build time and record the figures with
their source.** A313 and A344 are built around them; a wrong constant makes both
artifacts wrong in the silent direction. A313's subscription-acknowledgement
audit exists specifically because a documented cap is not evidence.

**Tax and charge rates.** §1.2 asserts that `stt_rate = 0.000625` and
`exchange_rate = 0.0000297` are stale or misapplied, on the basis that STT on
option sale premium was raised to 0.1% and that NSE's options transaction charge
is levied on premium at roughly 0.05%. **I have not verified either against a
current contract note, and A363 exists to do exactly that.** The direction of the
error is what matters and is not in doubt — the current model understates
friction, and it understates it before slippage, which defaults to zero. But the
magnitude in §1.2's worked example should be treated as an estimate until a real
contract note confirms it.

**The confirmation interval.** §A341's close-confirmation cannot be chosen from
minute bars, because minute bars have no intrabar order. Until A310's opt-in tick
capture has run, the default is the *tighter* candidate — being early is
recoverable, being late is not — and no measured claim about the interval may be
made.

---

## 10. The one-line summary

Freeze the reverse-engineered engine as evidence and keep its *idea* as a
first-class signal computed properly; add opening-range momentum as a second
signal because that is what was asked for, not because the recordings implied it;
run both over one shared substrate — universe, costs, portfolio risk, and three
independent exit clocks instead of one trailing stop — on the existing Kite
position layer rather than a second one; and start capturing option data today,
because every parameter here is currently chosen by taste and neither signal has
been measured.
