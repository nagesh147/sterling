# Adaptive Edge — User Guide

**Who this is for:** anyone who needs to understand how Adaptive Edge decides, enters, protects, and exits — in plain language.

**What this is not:** a license to go live. Live orders stay off until TrueData premium tick history is available, F-101 is calibrated on that history, and the execution gate is unlocked. The software path described here is already built and tested.

---

## 1. In one paragraph

Adaptive Edge watches NIFTY (and later options on it) every minute. It builds three numbers from the tape — how price just moved, who is leaning in the quote, and how wild the last few minutes were versus the last longer stretch. Those three numbers become one score between −1 and +1. If the recovered checks pass, it may take **one** position. While that position is open it can flatten because of a **stop**, a **trail**, a **profit lock**, or the **hard 14:45 IST cutoff**. It never pyramids. After it is flat it may enter again the next day, still only one position at a time.

TrueData’s current login only keeps about a week of bid/ask history. Premium tick history is the missing piece for a 120-day calibration. Everything else below is implemented.

---

## 2. What is ready vs what waits for premium login

| Piece | Status |
|---|---|
| Read the tape (bars + last quote) | Ready on the entitled window |
| Three-feature analysis | Ready |
| Score | Ready as a **trial** evaluator (not the frozen production file) |
| Entry checks that we actually recovered | Ready |
| Simulated fill (ask for buys, bid for sells) | Ready |
| One position only | Ready |
| Stop / trail / profit-lock **machinery** | Ready — distances are a **policy you supply**, not a secret default |
| 14:45 IST flatten | Ready |
| Next-day re-entry when flat | Ready |
| P&L peak and giveback | Ready |
| Walk-forward (fit on train, score test) | Ready as research, not a freeze |
| MICRO / SCALP / EXTENDED_SCALP / INTRADAY | Ready as **mode machinery**; numeric rungs are an explicit policy, not frozen F-104 |
| 120-day calibration file `f101_parameters_v1.json` | **Waiting on TrueData premium history** |
| Live Kite orders | **Blocked on purpose** until formulas are unlocked |

---

## 2.1 Micro, scalp, and intradayer — what those words mean here

These are **how long the current opportunity still looks useful**, not four separate strategies and not a timer.

| Mode | Plain meaning | After-entry management name |
|---|---|---|
| MICRO | Usefulness is still short | H0 Impulse |
| SCALP | Continuation beyond the shortest burst | H1 Tactical |
| EXTENDED_SCALP | Still supported, not yet a session hold | H2 Intraday swing |
| INTRADAY | Broader session continuation still justified | H3 Session trend |

A trade **starts MICRO**. It can step up or jump (MICRO can go straight to INTRADAY if the evidence is strong enough and stays strong for several bars). It can step back down. It does **not** become SCALP just because five minutes passed, and it does **not** become INTRADAY just because price went up.

The engine requires **several things at once** before it will change mode:

```text
score still agrees with the side we entered
AND the three features are still valid
AND open profit is at least the policy rung (example: 5 / 15 / 25 points)
AND we have not given back more than 60% of the best open profit
AND (for INTRADAY only) at least 45 minutes remain before 14:45 IST
AND that picture holds for 3 bars in a row   ← stops flicker
```

Those 5 / 15 / 25 / 3-bar numbers are the **research policy** shipped in the runner. They are not the missing F-104 learned thresholds. Changing them does not unlock live trading.

Mode **cannot** raise your authorized risk and **cannot** loosen a stop or trail.

### Thesis, protection stages, overlays, H4

These run beside mode. They are also explicit research policy, not recovered F-105/F-106.

**Thesis** (is the original idea still true?)

| State | Meaning |
|---|---|
| STRONG | Score still agrees, profit open, little giveback |
| VALID | Score still agrees |
| WEAKENING | Score flipped this bar, or giveback is large |
| INVALID | Score flipped (or data missing) for 15 bars → flatten |

**Protection stages**

| Stage | Meaning |
|---|---|
| P0 risk-controlled | Just in; hard stop only |
| P1 breakeven-protected | Trade is in profit; trail may sit at/above entry |
| P2 profit-protected | Profit-lock has armed |
| P3 aggressive trail | Lock + trail both working after a larger move |

**Overlays** (side conditions, can stack)

- DATA_UNCERTAINTY — features missing this bar; do not promote
- LIQUIDITY_STRESS — no valid LI quote
- ECONOMIC_COLLAPSE — gave back more than 80% of peak open profit → flatten
- BURST — volatility ratio ≥ 2 (research rung)
- EMERGENCY — only if explicitly flagged; not invented from price

**H4 session extension** — if mode is already INTRADAY, there are ≤ 90 minutes to 14:45, and the trade is still aligned and in profit, A126 may promote H3 → H4. It still flattens at 14:45.

### Market profile, volume profile, TBT order flow

These now run from the same TrueData ticks used for liquidity imbalance. They are **session-to-date** and causal (only prints that had already arrived).

**Market profile** — each 1-minute bar stamps every price it traded through (TPO). POC is the price with the most stamps. Value area is the 70% of stamps around POC (research convention). Close can be above, inside, or below value.

**Volume profile** — each tick’s volume is added to its last-price bin. VPOC is the heaviest price. Same 70% area.

**Order flow** — TrueData does **not** say who hit whom. We classify each print with a labeled research rule:

```text
if last price >= ask  → buy aggressor
if last price <= bid  → sell aggressor
else                  → uptick = buy, downtick = sell
```

That is **not** the missing canonical DeltaVelocity. Bar delta = buy volume − sell volume. CVD is the running sum. Last quote still gives liquidity imbalance.

If you are long and the bar’s flow is selling, overlay **FLOW_AGAINST**. If price is below value while long, overlay **OUTSIDE_VALUE**. Either one puts posture to DEFENSIVE. They do not invent an F-101 feature.

**VWAP** — session typical price, volume-weighted from TBT. Resets each IST day. Long below VWAP → **AGAINST_VWAP**. After the 15-minute initial balance, we also keep an **anchored VWAP** from IB end.

**Opening structure** — session open, prior close (gap), and initial balance high/low (first 15 minutes, research convention). After IB completes: above / inside / below the opening range. Long below IB low → **OUTSIDE_OR**.

**HVN / LVN** — local peaks and troughs on the volume histogram. Sitting on an LVN (within 1 point) → **AT_LVN**.

**Value migration** — POC compared with the previous bar’s POC. Long while POC is walking down → **VALUE_MIGRATION_AGAINST**.

---

**Operating posture** (engine stance, not MICRO/SCALP)

OBSERVE when flat → ACTIVE in a short mode → INTRADAY in the long mode → DEFENSIVE if thesis is weakening or an overlay is stressing → EXIT_ONLY at cutoff or invalid thesis → HALTED only on emergency.

### Worked mode path

```text
09:30 IST   BUY, mode = MICRO
09:33 IST   +6 points, score still buy, 3 bars in a row → SCALP
09:41 IST   +16 points, still aligned → EXTENDED_SCALP
09:50 IST   +28 points, 2 hours to cutoff → INTRADAY
11:10 IST   giveback 70% of the peak → back to MICRO
14:45 IST   cutoff flattens regardless of mode
```

---

## 3. How the analysis works

Every 1-minute bar close, the engine looks only at information that was already available at that close. It does not peek into the next bar.

### 3.1 Three ingredients

**Log return** — how much the last close moved versus the close before it.

```text
If last close was 24,700 and this close is 24,720
log return ≈ ln(24720 / 24700) ≈ +0.00081
```

The first bar of a series has no previous close, so this ingredient is missing for that one bar.

**Liquidity imbalance** — who is showing more size on the quote, using the last bid/ask that had arrived **at or before** this minute.

```text
LI = (bid qty − ask qty) / (bid qty + ask qty)
```

Example: bid qty 80, ask qty 20 → LI = (80−20)/(80+20) = **+0.60** (more size on the bid).  
If both sides are zero, LI is **missing**, not zero. We do not invent a quote from the bar.

**Volatility ratio** — short-window wiggle versus long-window wiggle of those log returns.

The research runner currently uses windows **5 and 15** minutes. Those windows are a **placeholder**. They are not the frozen production pair. The first 15 bars of a day-session warmup cannot make this ratio, so the score is missing there.

Delta velocity (aggressor / uptick-downtick) is **not** used. Strategy Lead removed it from this score.

### 3.2 Turning three numbers into one score

For each ingredient the engine asks: “is this unusual compared with the typical level we estimated?”

```text
z = clip( (value − median) / scale , −4, +4 )
score = tanh( w1·z_return + w2·z_liquidity + w3·z_vol )
```

- Median and scale are supposed to be **learned on training data only**.
- Until premium history exists, the entitled-window runner uses a **unit-scale trial** (median 0, scale ~1, equal weights). That is a harness, not the live brain.
- `tanh` keeps the score between **−1 and +1**.
- Positive score → research path leans **buy**. Negative → **sell**.

On the last entitled cache (NIFTY-I, 6–14 Aug 2026) this produced **2,562 valid scores** and **15 missing** (almost all volatility warmup).

---

## 4. How an entry is decided

Entry is not “score crossed zero, fire.” Seven questions are asked. Only three of them have recovered tests today. The others stay **blank (spec gap)** unless you explicitly supply an answer.

```text
May I enter?
  1. Data valid?     three features are present          ← recovered
  2. Model valid?    score itself is present             ← recovered
  3. Execution valid? we have a real bid or ask          ← recovered
  4. Economic?       expected value > cost               ← only if you supply both numbers
  5. Risk?           risk desk authorized this trade     ← only if you supply authorization
  6. Capital?        size came out > 0                   ← only if you supply a size policy
  7. Session?        09:15–15:30 IST weekday             ← operational clock, not F-103
```

**Recovered rule used in software:** 1 AND 2 AND 3 must pass. If any of those three fail, no order.

**Also enforced, even though they are not F-102/F-103 math:**

- No new entry at or after **14:45 IST**.
- No second position while one is open (no pyramid).
- After a flatten, re-entry is allowed only when flat and still before 14:45.

**Buy price** is the executable **ask**. **Sell price** is the executable **bid**. We do not fill at last-traded price.

### 4.1 Worked entry — 6 Aug 2026, NIFTY-I

This is from the research replay on the entitled cache, not a live order.

```text
09:15 IST   first bar of the day. Volatility ratio still warming up. No score.
09:30 IST   first valid score of that day (15 one-minute bars of warmup).
            Research path entered 1 lot, BUY, at the ask then available.
            Audit wrote: opportunity → order intent → simulated fill → accounting mark.
            Position count = 1.
```

From 09:30 until 14:45 the same replay **refused 314 later scores as pyramid**. That is working as designed.

---

## 5. How size is decided

If you do **not** supply a size policy, quantity is the explicit research default of **1**.

If you **do** supply one, two recovered platform formulas run:

```text
risk per unit  = |entry − initial stop| + expected costs     (F-107 machinery)
quantity       = floor( authorized risk / risk per unit )    (F-108 machinery)
                 then clipped to lot size and max contracts
```

Those formulas exist. The **numbers** (authorized risk, stop used for size, max contracts) are yours to pass in. The engine will not invent a live risk budget.

---

## 6. How the position is protected

Once filled, four **authorities** can flatten. They are not the same thing.

```text
14:45 IST cutoff     always wins if the clock is there
hard stop            “price went this many points against me”
trail                “give back this many points from the best price seen”
profit lock          “after I was up X, do not give it all back”
```

Session cutoff **cannot** be turned off by a still-positive score.

Stop / trail / lock **distances are not recovered Adaptive Edge constants**. The machinery is production-grade (causal, monotonic trail, audited). You pass a policy. Example policy used only in tests and in the stories below:

```text
stop   = 25 points from entry
trail  = 15 points behind the best price
lock   = arm after +20 points, then keep 5 points off the best
```

That example is **not** written into a production freeze file.

### 6.1 Hard stop (SL)

Buy at 24,700, stop 25 points → stop price **24,675**.  
If a later minute’s close is 24,675 or lower, flatten at the bid.

Sell at 24,700, stop 25 → stop price **24,725**.  
Close at 24,725 or higher → flatten at the ask.

The stop does **not** move. The trail does.

### 6.2 Trailing stop (TSL)

Trail remembers the **best price so far** (highest close for a buy, lowest for a sell). It only tightens.

```text
Buy 24,700, trail 15
09:40  close 24,730   best = 24,730   trail = 24,715   hold
09:41  close 24,722   best stays 24,730   trail stays 24,715   hold
09:42  close 24,715   close hits trail   flatten at the bid
```

A later lower close cannot push the trail back down. That is the A177 monotonicity rule.

### 6.3 Profit lock

Different from a trail. It stays **off** until the trade has been in profit by the activation distance.

```text
Buy 24,700, arm at +20, keep 5 off the best
09:50  close 24,715   only +15   lock still off
09:51  close 24,725   +25   lock arms   lock price = 24,720
09:52  close 24,740   best 24,740   lock moves up to 24,735
09:53  close 24,735   hits lock   flatten
```

Unrealized profit on the screen is not treated as money in the bank. Flatten still uses the executable bid/ask.

### 6.4 14:45 IST session cutoff

NSE regular session here is 09:15–15:30 IST. Adaptive Edge **must be flat 45 minutes before the close**:

```text
14:45 IST  no new entries
           open position is closed with the opposite executable quote
15:30 IST  session end (we are already flat)
```

This is the only **mandatory** exit that does not need a supplied policy.

### 6.5 Worked day — 6 Aug 2026 (real replay)

```text
09:30 IST   BUY 1, research fill
14:45 IST   EXIT_SESSION_CUTOFF, opposite fill, quantity → 0
            Audit: session_cutoff_exit
```

The same pattern repeated 7, 10, 11, 12 and 13 Aug. **14 Aug** entered at 09:15 IST and was still open at the last bar **14:42 IST** — the cache simply ended three minutes before cutoff, so that last day correctly stayed qty 1.

---

## 7. Re-entry and “one position”

```text
Open?  → ignore later scores (pyramid blocked)
Flat and before 14:45? → next valid score may enter again
After 14:45? → no entry, even if the score is huge
Next calendar session? → allowed again
```

On the entitled cache: **7 entries, 6 cutoff exits, 6 next-day re-entries, 2,285 blocked pyramids**.

---

## 8. P&L the engine actually computes

```text
current P&L     = signed (mark − entry) × quantity
peak P&L        = best current P&L so far                 (F-002)
profit giveback = peak − current                          (F-003)
```

Giveback is how much of the best open profit has been handed back. It is accounting, not an automatic exit. Profit-lock (section 6.3) is the exit that uses a **price** policy.

---

## 9. Full realtime flow (happy path)

```text
09:14 IST   outside session
09:15 IST   bars start; score still warming up
09:30 IST   score +0.03, LI valid, ask present
            Data + Model + Execution pass
            BUY 1 @ ask 24,710
            stop (example) 24,685   trail 24,695   lock off
10:05 IST   close 24,740
            trail tightens to 24,725   lock arms (if +20 policy)
            later scores ignored (already in)
14:45 IST   clock cutoff
            SELL 1 @ bid 24,755
            flat
            books: peak / giveback updated
```

## 10. Full realtime flow (stop hits before 14:45)

```text
09:30 IST   BUY 1 @ 24,710   stop 24,685
09:47 IST   close 24,680
            protective stop fires
            SELL 1 @ bid
            flat
            a later 10:00 score may enter again (still before 14:45, now flat)
14:45 IST   if still open, cutoff would have flattened anyway
```

## 11. Full realtime flow (premium login arrives — not done yet)

```text
1. TrueData premium retains /getticks?bidask=1 before 6 Aug 2026
2. Re-measure an old date; it must return bidqty and askqty
3. Build ~120 trading days / ~45,000 one-minute bars + matching quotes
4. Walk-forward: estimate median/scale on TRAIN only
5. Confirm TEST does not leak into that estimate
6. Write f101_parameters_v1.json only after that promotion
7. Then — and only then — F-101 can be unlocked and Kite can be connected
```

Until step 2 is true, live Adaptive Edge stays **blocked**. The last remasure (same account): 15 Jul and 1 Aug 2026 returned **no data**; 13 Aug returned **167** ticks with bid/ask size. That is why premium login is the remaining external dependency.

---

## 12. What the engine will not do

- It will not invent a stop distance and call it “the Adaptive Edge stop.”
- It will not treat SuperTrend, Navigator, or old ATR experiments as this strategy.
- It will not enter two positions at once.
- It will not stay in past 14:45 IST.
- It will not write `f101_parameters_v1.json` from a one-week trial.
- It will not send Kite orders while F-101..F-114 are locked.

---

## 13. How to run the software path

From the repo root, with `backend/sterling_paper.db` holding the TrueData credential:

```text
PYTHONPATH=backend python backend/scripts/run_adaptive_edge_research_e2e.py
PYTHONPATH=backend python backend/scripts/remeasure_truedata_li_retention.py
```

You want:

```text
SOFTWARE_COMPLETE: True
PRODUCTION_GATE: False
A197: False
OLD_DATE_HISTORY_PRESENT: False     ← flips only after premium history
```

Tests live under `backend/tests/engines/test_adaptive_edge_*.py` (research path, protection, lifecycle, registry, execution gate).

---

## 14. Formula map (short)

| ID | Plain name | In this guide |
|---|---|---|
| F-001 | Don’t use the future | §3 |
| F-002 / F-003 | Peak P&L / giveback | §8 |
| F-007 / F-008 | Buy at ask / sell at bid | §4 |
| F-101 | The three-feature score | §3 |
| F-102 / F-103 | Edge + eligibility math | **not recovered** — structure only |
| F-107 / F-108 | Risk per unit / size | §5 if you supply numbers |
| F-111 / F-112 | Exit trigger / trail numbers | machinery in §6, numbers not frozen |
| F-113 / F-114 | Re-entry / one position | §7 |

---

*This guide describes the software that exists today. It does not freeze 5/15 windows, equal weights, or example 25/15/20 point protection as production strategy law.*
