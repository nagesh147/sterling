# A280 — ATM Premium Imbalance, end to end

The complete reference: every document, module, setting, route, surface and test
that makes up this strategy, and an honest ledger of what is proved and what is
not.

**One thing governs how to read all of it.** This strategy was *reverse
engineered from screen recordings of somebody else's bot*. It was not designed
here. So every rule below carries a provenance:

| Marker | Meaning |
|---|---|
| **OBSERVED** | Read off a recording and arithmetically self-consistent. The source bot did this. |
| **OURS** | Added here. The recordings show no such thing. Defaults keep it off or inert unless stated. |
| **UNPROVEN** | Neither observed nor verifiable. Named so it cannot be mistaken for either of the above. |

Where a default would change what the recordings proved, the observed behaviour
stays the default and the addition is opt-in. That is why `FIXED_POINT_TARGET`
is still the default exit policy even though a trailing stop is safer.

---

## 1. The documents

| Artifact | Lines | What it is |
|---|---|---|
| `README.md` | 104 | Entry point and provenance statement |
| `A230_STRATEGY_CONTRACT.md` | 210 | The rules the code must honour. Contract version **A230.4** |
| `A231_FORENSIC_EVIDENCE_MATRIX.md` | 188 | Every rule traced to the frame it came from, with a confidence grade |
| `A232_PARAMETER_PROVENANCE.md` | 124 | Where each default came from, and what was rejected |
| `A265_ARCHITECTURE.md` | 149 | Modules, data flow, state machines, failure paths |
| `A266_RUNBOOK.md` | 148 | Operating it, and the live-readiness gate |
| `VALIDATION_REPORT.md` | 461 | What was checked against real data; what is still unproven |
| `A280_END_TO_END.md` | this file | Complete reference |

### The source recordings

Five recordings of `SENSEX_MEETING_POINT_BOT` / "SENSEX LIVE BOT", on **Upstox**
— not Kite. Version discipline: **V0821 is the latest build and wins every
conflict.**

| Tag | Resolution | Session | Role |
|---|---|---|---|
| **V0821** | 1440×2560 @60 | 2026-08-21 | **Authoritative.** Terminal directly legible |
| V1 | 720×1280 @30 | 2026-08-20 | Prior session; the HQ copy overturned two findings |
| V17 | 720×1280 @60 | 2026-07-30 | Prior version — uses a different entry branch |
| V21 | 720×1280 @60 | ≥2026-07-30 | Prior version (backup dir) |
| V04 | 720×1280 @30 | earlier | Local dev build |

### Four rules that were wrong before they were right

Every one had the same cause — a rule declared from samples that happened to
agree. This is the single most important lesson in the whole artifact set.

| Rule | First stated | Actual | Why it changed |
|---|---|---|---|
| `difference` | signed `PE − CE` | **`\|PE − CE\|`** | Four recordings had the put dearer, making signed and absolute identical. V0821 has the **call** dearer and still prints a positive number. |
| `expiry_policy` | `SAME_DAY` | **`NEAREST`** | V0821 traded a *monthly* contract on a non-expiry day. `SAME_DAY` would have refused to arm. |
| entry buffer | rejected → `10.25` points → | **`10.0%` of the selected leg's first price** | Recorded three ways. `102.85 × 1.10 → 113.1` and `379.0 × 1.10 → 416.9`. No points value fits both. `+10.25` matches the low-premium session to within 0.04 — a coincidence that only breaks at 4× the premium. |
| pricing reference | first tick of either leg | **the selected leg's** first price | A test caught 540.3 where the bot printed 416.9. |

**The transferable lesson:** an arithmetic identity that holds at one price level
proves very little. Check it at a very different magnitude before believing it.

---

## 2. The contract (A230.4)

### Universe — OBSERVED

- Underlying **SENSEX**, options on the Kite **BFO** segment
- `expiry_policy = NEAREST` — the nearest listed expiry, not necessarily today's
- `strike_policy = ATM_NEAREST` — nearest strike to spot on the 100-point ladder
- Lot size 20, tick size 0.05 (cross-checked against Kite's instrument master)

### Quote model — three modes

| Mode | Behaviour | Provenance |
|---|---|---|
| `COMPATIBILITY` | Independently cached last-traded price per leg. Reproduces the source bot exactly. **Paper only.** | OBSERVED (default) |
| `SYNCHRONIZED` | CE and PE aligned by exchange timestamp. Tests whether the asynchronous cache is itself doing the work. | OURS — research |
| `EXECUTABLE` | Compares the two **asks** — what could actually be bought. **Required for live.** | OURS |

### Signal — OBSERVED

`CHEAPER_LEG`: buy the cheaper of the two ATM premiums. Equal premiums are
explicitly **no trade** rather than a tie-break — a coin flip at the open is not
a strategy. There is no indicator anywhere in this engine, deliberately: adding
one would make the thing being validated a different strategy from the thing
reconstructed.

### Entry

Five price policies. The default expresses the *mechanism* observed — a limit
deliberately through the market so it fills like a market order — without
hard-coding one morning's numbers.

| Policy | Price | Provenance |
|---|---|---|
| `MARKETABLE_ASK` | `best_ask + entry_buffer_points`, capped at the upper circuit | OURS (default) |
| `PERCENT_THROUGH` | a percentage through the ask | OURS |
| `FIRST_TICK_PERCENT` | `round(selected_leg_first_price × (1 + pct), 1)` | **OBSERVED** — this is the source bot's automatic path |
| `MANUAL_FILE` | read from `strike_prices.txt` | OBSERVED — V17's branch |
| `FIRST_TICK_PLUS_BUFFER` | first price + points | UNPROVEN — research only, refused in live |

**The session-origin invariant — OURS, and the most important safety rule here.**
A quote carrying a *previous session's* last-traded price arrives instantly and
is therefore perfectly "fresh" by age. Only its trade stamp gives it away. So:

- `is_session_origin()` consults **only** `last_trade_ts_ms`. `exchange_timestamp`
  is deliberately *not* a fallback — it stamps when the exchange sent the packet,
  not when the price traded, so a stale-LTP tick has a current one and the
  fallback would mask exactly the fault it was added to catch.
- Three-valued: `True` / `False` / `None` (undatable). Proven-stale is refused
  always; undatable is refused in live and allowed in paper.
- `ohlc.open` is **not** exempt. A real captured tick showed it carrying the
  *previous* day's open, so it is withheld until the leg trades today.

This was a real fault, found in real data: a stale tick produced an order price
of 416.9 where the session price gives 392.4.

**Retry:** up to `max_entry_attempts` (3), `entry_attempt_timeout_ms` (1500).
An `UNKNOWN` order status always goes to RECONCILE — never to a retry that could
double the position.

**Accounting invariant:** the entry price of record is the broker's **average
fill**, never the requested limit. Observed: requested 288.75, filled 133.40. A
target computed from 288.75 would never fire.

### Exit

| Policy | Behaviour | Provenance |
|---|---|---|
| `FIXED_POINT_TARGET` | `entry_fill + target_points` (15.0) | **OBSERVED** (default) |
| `PREMIUM_CONVERGENCE` | exit when the bought leg reaches the other | UNPROVEN — research only |
| `TRAILING_STOP` | ratcheting stop, no ceiling | **OURS** |

**Exit order price — OBSERVED:** `best_bid − 0.50`, tick-aligned **downward**.
Confirmed in two builds: 149.2 → 148.7 and 127.1 → 126.6. Rounding down keeps a
sell marketable.

**Three separate facts, never conflated:** the trigger (149.10), the order price
(148.70) and the fill (156.85).

### The trailing stop ladder — OURS

Three rungs, applied in order, and the result **only ever moves up**:

1. **Initial stop** — `entry − stop_distance`. The most this trade may lose.
2. **Break-even** — once the price has been `breakeven` in front, the stop moves
   to the entry fill. The trade can no longer lose.
3. **Trail** — past `trail_start`, the stop follows the high-water mark at
   `trail_distance` behind it.

The ratchet is the whole point: a stop that can move down is not protection, it
is a way to lose more than was agreed. Each rung takes `max` against the one
below, and a property test asserts the ladder is monotonic in the peak.

**Measured from the entry fill**, not the current price — the risk agreed at
entry must not drift with the market. The trail distance is the deliberate
exception; it follows the peak because that is its job.

**`PERCENT` basis exists because these premiums run ~50 to ~500.** Fifteen points
is a 30% risk on one and 3% on the other — the same number meaning two completely
different trades. One basis governs every distance; a per-field unit, or a
"percent wins over points" precedence rule, is how a config ends up meaning
something nobody intended.

The high-water mark lives on the strategy, not in the exit policy — it is a fact
about this position's history. `should_exit()` defaults it to the **entry fill**,
not `last_price`: defaulting to the last price would make every price its own
peak and fire the trail on the first tick down.

Three rungs report three distinct reasons — `stop_hit`, `breakeven_stop_hit`,
`trailing_stop_hit`. "Stopped out" and "gave back part of a win" are different
outcomes and the log should not blur them.

### Session — OURS

- `entry_window_seconds` (300). Buying at the open is what this strategy *is*;
  without a window it entered on the first valid tick pair after arming, whenever
  that happened to be. Arm at 14:00 and it traded at 14:00.
- `close_at_session_end` (on). A position held past the close — and on expiry
  day, held to expiry — can settle worthless. This wins over every exit policy:
  a target not reached by the close is not going to be.
- A live session is gated by market hours *before* the strategy is asked
  anything, so **there is no signal before 09:15**.

### Risk — OURS

| Limit | Enforcement |
|---|---|
| `max_premium_at_risk_inr` (25,000) | Checked at entry against **limit price × quantity**. A bought option can lose all of its premium, so the outlay *is* the risk. |
| `daily_loss_limit_inr` (10,000) | Checked in the signal gate **before any quote arithmetic**, so a breach cannot be argued with by an attractive price. |
| `max_quantity` (500) | Hard ceiling |
| `max_trades_per_session` (1) | Enforced in the gate *and* in the phase machine |

Neither money limit can be switched off — the config refuses zero, which is
stricter than an "0 means unlimited" convention that is one typo from nothing.

> **Worth knowing:** the ₹25,000 default ceiling would have refused the trade the
> recording took (80 × 338.10 = ₹27,048). The default is deliberately
> conservative. The snapshot publishes `max_affordable_premium` — the dearest
> option the configured size can buy — so this surfaces before arming rather than
> as a halt at the open, which lands milliseconds after the bell.

### Protection — OURS

`protection_mode`: `NONE` (default) · `RESTING_TARGET_LIMIT` · `GTT`. Parks a
sell at the target on the exchange so a dead process still closes the position.
**Required for live.**

Invariant: protection is *cancelled and confirmed cancelled* before our own exit
is sent. A failed cancel **halts** rather than risking two sells.

---

## 3. The code

### Engine — `backend/app/engines/atm_premium_imbalance/` (3,550 lines)

Pure logic. **No I/O anywhere**, which is what lets live, replay and simulation
share one code path.

| Module | Lines | Responsibility |
|---|---|---|
| `strategy.py` | 683 | The orchestrator. Phase machine, emits **Intents** |
| `models.py` | 433 | `LegQuote`, `PremiumPairView`, `TradeRecord`, `ExitEvent`, `q2()`, `align_to_tick()` |
| `config.py` | 416 | 47 settings, every vocabulary, all validation |
| `entry.py` | 380 | Five price policies, the retry state machine |
| `replay.py` | 329 | Bar-driven replay against recorded sessions |
| `quote_cache.py` | 296 | Per-leg caching and the three quote views |
| `exit.py` | 207 | Target, stop, trailing ladder, exit order pricing |
| `market_crosscheck.py` | 208 | Compares observed facts against an instrument master |
| `protection.py` | 152 | Broker-side protection planning |
| `conformance.py` | 139 | Diffs our output against the recordings |
| `selection.py` | 110 | Expiry and strike resolution |
| `signal.py` | 107 | The one `evaluate()`. Gates can reject; never invert |
| `session.py` | 42 | Session open/close arithmetic, IST-anchored |

**Why Intents.** The engine returns a description of what should happen —
`submit_entry`, `poll_exit`, `halt` — and the service layer performs it. Eleven
kinds: `none`, `submit_entry`, `poll_entry`, `reconcile_entry`,
`place_protection`, `cancel_protection`, `submit_exit`, `poll_exit`,
`reconcile_exit`, `complete`, `halt`. This is why a simulation can be driven by a
fake broker on a virtual clock with no special cases in the strategy.

**Phases:** `IDLE → ARMED → ENTERING → IN_POSITION → EXITING → DONE`, plus
`HALTED`. The dispatch is exhaustive by phase, so a tick arriving while `EXITING`
falls through rather than starting a second exit.

### Services — `backend/app/services/` (1,806 lines)

| Module | Lines | Responsibility |
|---|---|---|
| `atm_premium_imbalance_runner.py` | 802 | Tick-driven live runner, session registry, `arm`/`adopt`, terminal log |
| `atm_premium_imbalance_sim.py` | 489 | Virtual-clock replay of the last traded session |
| `atm_premium_imbalance.py` | 268 | Config store, pair resolution, `snapshot()` |
| `atm_premium_imbalance_replay.py` | 247 | Offline replay CLI against the data lake |

**Tick subscriptions are refcounted** (`exchanges/kite/ticker_manager.py`). There
is one subscription set per account, shared with the operator's charts and the
protection tick monitor. `arm()` claims its two legs with an owner tag;
`release()` unsubscribes only when the departing owner was the last claimant. A
token any *untagged* caller subscribed is never auto-released — starving the
protection monitor would leave a real stop unguarded.

Without this, one dead pair leaked per armed day: the session was popped from the
registry first, discarding the only record of which tokens were ours.

### API — `backend/app/api/v1/endpoints/config.py`

| Route | Purpose |
|---|---|
| `GET /config/atm-premium-imbalance` | Config, defaults, vocabularies, `research_only`, `live_requires` |
| `PUT /config/atm-premium-imbalance` | Partial update. **Unknown keys are refused, not ignored** |
| `GET /config/atm-premium-imbalance/snapshot` | Config + resolved pair + sizing + blockers + live session + simulation |
| `POST /config/atm-premium-imbalance/arm` | Resolve the pair, claim both legs, arm |
| `POST /config/atm-premium-imbalance/adopt?symbol=…` | Take charge of an orphaned position |
| `POST /config/atm-premium-imbalance/simulate` | Replay the last traded session |
| `POST /config/atm-premium-imbalance/simulate/stop` | Stop the replay |

> **A bug worth recording.** The PUT used to carry a hand-written pydantic mirror
> of the config, listing every field by name. It fell behind the dataclass, and
> pydantic silently drops unknown keys — so nine newer settings were discarded on
> the way in while the UI looked like it had saved. The mirror is gone; the engine
> is now the single validator, and `test_every_config_field_is_settable` compares
> the served payload against the dataclass fields so they cannot drift again.

### Frontend — `frontend/src/`

| File | Responsibility |
|---|---|
| `hooks/useAtmPremiumImbalance.ts` | Types, config/snapshot queries, arm/simulate mutations |
| `components/AtmPremiumImbalanceSettings.tsx` | The settings panel |
| `components/kite/AtmPremiumImbalanceSettingsPanel.tsx` | Settings-hub wrapper |
| `components/kite/board/atmPremiumImbalanceAdapter.ts` | Snapshot → one `BoardSignal` |
| `components/kite/board/AtmPremiumImbalanceBoard.tsx` | The board panel, arm and replay controls |

The board is the fourth engine tab. `running` means **armed**, not merely
enabled — an enabled-but-unarmed tab must not claim to be running.

`stop` and `trail` were `null` on the row for as long as no stop existed; they
carry real values now that the trailing policy does. The row publishes no score,
because the strategy computes none.

The **Quote provenance** block is its own section on the row, because
"refusing a carried-over price" and "no signal yet" are different situations and
an operator must be able to tell them apart without reading the logs.

---

## 4. Configuration reference

47 settings. Defaults shown; provenance marked.

### Universe
| Setting | Default | |
|---|---|---|
| `enabled` | `False` | OURS |
| `underlying` | `SENSEX` | OBSERVED |
| `expiry_policy` | `NEAREST` | OBSERVED — corrected from `SAME_DAY` |
| `explicit_expiry` | `""` | OURS |
| `strike_policy` | `ATM_NEAREST` | OBSERVED |

### Session
| Setting | Default | |
|---|---|---|
| `session_start` | `09:15` | OBSERVED |
| `session_end` | `15:25` | OURS |
| `entry_window_seconds` | `300` | OURS |
| `close_at_session_end` | `True` | OURS |
| `max_trades_per_session` | `1` | OBSERVED |

### Quotes
| Setting | Default | |
|---|---|---|
| `quote_mode` | `COMPATIBILITY` | OBSERVED |
| `max_quote_age_ms` | `2000` | OURS — the bot had no freshness gate |
| `max_ce_pe_skew_ms` | `1000` | OURS — `SYNCHRONIZED` only |
| `require_session_origin_tick` | `True` | OURS |
| `first_tick_source` | `SESSION_TICK` | OURS |

### Signal
| Setting | Default | |
|---|---|---|
| `signal_mode` | `CHEAPER_LEG` | OBSERVED |
| `minimum_difference` | `0.0` | UNPROVEN — no recording shows a threshold |
| `minimum_difference_percent` | `0.0` | UNPROVEN |

### Entry
| Setting | Default | |
|---|---|---|
| `entry_price_policy` | `MARKETABLE_ASK` | OURS (mechanism OBSERVED) |
| `entry_buffer_points` | `0.5` | OURS |
| `entry_through_pct` | `0.0` | `0.10` reproduces the bot exactly |
| `manual_price_file` | `""` | OBSERVED — V17's branch |
| `max_entry_attempts` | `3` | OBSERVED |
| `entry_attempt_timeout_ms` | `1500` | OURS |

### Exit
| Setting | Default | |
|---|---|---|
| `exit_policy` | `FIXED_POINT_TARGET` | OBSERVED |
| `target_points` | `15.0` | **OBSERVED — directly evidenced, two builds** |
| `exit_buffer_points` | `0.5` | **OBSERVED — directly evidenced, two builds** |
| `max_hold_seconds` | `0` (off) | UNPROVEN |

### Stops and trailing — all OURS
| Setting | Default |
|---|---|
| `stop_enabled` | `False` |
| `stop_basis` | `POINTS` (`PERCENT` recommended) |
| `stop_points` / `stop_percent` | `0.0` / `0.0` |
| `trail_points` / `trail_percent` | `0.0` / `0.0` |
| `trail_start_points` / `trail_start_percent` | `0.0` / `0.0` |
| `breakeven_points` / `breakeven_percent` | `0.0` / `0.0` |

### Size and risk — all OURS
| Setting | Default |
|---|---|
| `sizing_mode` | `QUANTITY` (compatibility; `LOTS` is safer) |
| `lots` / `quantity` | `0` / `0` |
| `max_quantity` | `500` |
| `max_premium_at_risk_inr` | `25000.0` |
| `daily_loss_limit_inr` | `10000.0` |

### Plumbing
| Setting | Default | |
|---|---|---|
| `protection_mode` | `NONE` | OURS — required for live |
| `data_source` | `kite` | OURS |
| `execution_mode` | `paper` | OURS |

**`sizing_mode` defaults to `QUANTITY` purely for compatibility.** A config saved
before `LOTS` existed states a quantity, and defaulting to `LOTS` would have
silently ignored it. `LOTS` is the better way to say it: the exchange only
accepts whole lots and the lot size is a property of the contract, not something
the operator should have to remember.

---

## 5. Operating it

### Arming

`POST …/arm`. Refuses rather than guessing, and every refusal has a name:

| Status | Meaning |
|---|---|
| `disabled` | The strategy is switched off |
| `no_quantity` | No size stated |
| `invalid_size` | Not whole lots, or over the cap — names the two nearest sizes that work |
| `market_closed` | Outside 09:15–15:30 |
| `open_position_unaccounted` | A position exists that no session explains |
| `already_armed` | Idempotent for the day |
| `armed` | Pair resolved, both legs claimed |

### Crash recovery

Restart mid-trade and the strategy's state is gone while the position is not. Any
long option on the underlying with no session behind it is **reported**, **blocks
arming**, and can be **adopted by symbol**.

Adoption is by symbol and on request, never automatic — a long option here might
be a trade the operator placed by hand, and quietly taking control of somebody
else's position is worse than telling them about it. It also refuses when the
resolved ATM has moved on: adopting the wrong contract would watch one option's
price in order to sell a different one.

An adopted trade is honest about what it cannot know. The high-water mark is
seeded from the **entry fill**, not the current price — the peak since entry is
unknowable after the fact, and guessing it would place a trailing stop somewhere
the position never actually reached. `first_tick_price` stays `None` for the same
reason, and `TradeRecord.adopted` marks the trade.

### The simulator

`POST …/simulate` replays the last traded session through the **live** runner,
the **live** strategy object and the **live** board payload. Only the ticks and
the clock differ.

- **Real time by default** — one simulated second per real second, advancing
  second by second so the clock reads like a live one. `speed` scales it.
- **Starts at 09:14:45 AM IST**, so the clock visibly walks up to the bell.
- **Continuous by default** — keeps working after a trade closes. Relaxes exactly
  two settings and names them: the trade limit and the entry window.

Safety is structural, not conventional:

- the session is marked `sim` and `on_ticks()` returns early for one, so today's
  live ticks can never drive a replayed position
- it refuses to start over a live armed session
- it uses its own broker and `forget()`s its session, so it can never hand back
  subscriptions a live session holds
- `illustrative_only` rides in **every** payload, so a client cannot render
  replayed numbers as live ones by forgetting a flag in one place

> **It is illustrative, not evidence**, for two structural reasons. The data is
> minute bars and Kite publishes no historical option ticks, so the intrabar
> order is unknown — ticks walk open, high, low, close, which lets the peak set
> the trail before the low tests it, but that ordering is an assumption and a
> trailing stop's result depends on exactly it. And fills are modelled at the
> limit price, which is optimistic.

**A fidelity bug worth recording.** The replay used to evaluate before 09:15 and
refuse on the *stale-quote* gate. Live never gets that far — the market-hours
check answers first. So the replay was teaching that the stale-quote gate is what
protects you at 09:14, when in live it matters at 09:15:00 on the first tick
carrying yesterday's price. Both paths now reach the same "no" by the same route.

### The terminal log

Transitions, not ticks. The premium comparison updates dozens of times a second;
a log that repeated it would bury the four moments that matter.

```
⏪ ATM REPLAY    replaying 2026-08-21 at 1x — 40 contracts, trailing stop;
                 continuous (trade limit lifted to 50, entry window off).
                 Real prices, simulated fills; not a backtest.
⏸  ATM WAITING   no trade — the exchange is not open
⚖️  ATM SIGNAL   CE 584.90 | PE 267.60 | diff 317.30 → buy the PE
🟢 ATM ENTRY     BUY 40 PE @ limit 268.65 (attempt 1)
✅ ATM FILLED    filled 40 PE @ 268.65 — no fixed target, the stop decides
🪜 ATM STOP      stop 268.65 (peak 287.90, entry 268.65)
🪜 ATM STOP      stop 272.32 (peak 296.00, entry 268.65)
🪜 ATM STOP      stop 293.99 (peak 319.55, entry 268.65)
🔴 ATM EXIT      SELL 40 PE @ limit 290.80 — trailing_stop_hit
🏁 ATM DONE      closed PE 40 @ 290.80 — +22.15 pts, P&L ₹+886.00
🔁 ATM RE-ARMED  trade 1 of 50 done — watching for the next signal
```

A refusal is said once, and again only when the *reason* changes. The stop line
keys on the stop alone — a rising peak that leaves the stop where it was is
context, not an event. Reasons are translated: "a quote traded before today's
open", not `stale_session_quote`. An unmapped reason falls through as-is so a new
gate is visible the day it is added.

---

## 6. Tests — 19 backend files, 4,933 lines (plus 835 frontend)

| File | Lines | What it guards |
|---|---|---|
| `test_golden_trades.py` | 406 | The recorded trades, reproduced end to end |
| `test_entry_exit.py` | 357 | All five entry policies, exit pricing |
| `test_signal_and_quotes.py` | 290 | The gate order, all three quote views |
| `test_market_crosscheck.py` | 233 | Observed facts vs the instrument master |
| `test_replay.py` | 203 | Bar-driven replay |
| `test_trailing_stop.py` | 205 | The ladder, and the **ratchet property** |
| `test_protection.py` | 181 | Cancel-before-exit, halt on failed cancel |
| `test_stale_tick.py` | 178 | The session-origin gate |
| `test_properties.py` | 175 | Invariants across generated inputs |
| `test_session_window.py` | 160 | Entry window, session-end square-off |
| `test_risk_limits.py` | 138 | The two limits that used to be decoration |
| `test_real_data_replay.py` | 117 | Against real Kite bars |
| `test_atm_premium_imbalance_runner.py` | 567 | Intents, the no-double-order lock, release |
| `test_atm_premium_imbalance_sim.py` | 504 | The simulator, and its safety invariants |
| `test_atm_premium_imbalance_reconcile.py` | 251 | Crash recovery, adoption |
| `test_atm_premium_imbalance_terminal.py` | 196 | The log, and its deduping |
| `test_atm_premium_imbalance_api.py` | 198 | Routes; **no config field can be dropped** |
| `test_ticker_subscription_ownership.py` | 173 | Refcounted release |
| `test_atm_premium_imbalance_snapshot.py` | 123 | Blockers |

Suite totals: **3,647 backend**, **724 frontend**, `tsc` clean.

Two tests exist specifically to fail when an assumption stops being true:
`test_lake_has_no_option_bars_so_premiums_stay_unverified` fails if option data
ever appears, and `test_every_config_field_is_settable` fails if the API and the
config drift.

---

## 7. What is proved, and what is not

### Verified against data outside the recordings

Seven external matches from the offline `kitelake` data lake, including V17's
printed `SENSEX LTP : 77638.86` matching the 09:15 IST bar open **exactly** —
which confirms lot size 20, tick 0.05, the 100-point ladder and the ATM rule.

Live behaviour verified on real Kite data for 2026-08-21, watched second by
second, with the ratchet visible:

| Peak | Stop | Rung |
|---|---|---|
| 276.30 | 228.35 | initial 15% risk |
| 287.90 | **268.65** | break-even — the trade can no longer lose |
| 296.00 | 272.32 | trail (296.00 × 0.92) |
| 319.55 | 293.99 | trail (319.55 × 0.92) |

Exit 290.80, **+22.15 points, ₹886** on 40 contracts. The fixed target would have
closed at 283.65 for +15.

### Not proved — and no amount of code will fix these

**No external check on option premiums.** The lake holds no BFO/NFO bars and Kite
publishes no historical option ticks. CE/PE levels, the entry fill and the exit
fill remain verified only against the recording's own arithmetic.

**No expectancy claim is available at any confidence.** Every session with a
decodable outcome was a winner, and every one was chosen by whoever decided what
to record. Nobody films their losses. On a sample this small with that selection
bias, no claim about profitability is available. The simulator does not change
this: one replayed day is one sample and its fills are modelled.

**One day is one sample.** The trailing stop beat the fixed target on 2026-08-21
because the price ran to 319.55. On a day that spikes and reverses, a 15% stop
loses more than a +15 target ever made. Continuous mode compounds that — it
re-enters immediately at the exit price, so each stop sits below a higher entry.

**Two rules remain unknown**, by absence of evidence rather than illegibility: no
recording shows a minimum-difference threshold or any stop or time stop. Both are
now implemented as options defaulting off, so the build no longer lacks the
capability — but what the source bot did is still unknown and only source access
would settle it.

**The broker differs.** The recordings are Upstox. This is Kite.

### The live gate

`config.validate()` refuses `execution_mode = "live"` without **all** of:

- `quote_mode = EXECUTABLE`
- a positive quantity
- `protection_mode != NONE`
- `require_session_origin_tick = True`
- no research-only entry or exit policy

The gate is code, not discipline. **Status: paper only.** Nothing structural
remains on the risk side — the limits are enforced, a stop exists, positions are
reconciled and the session is bounded. What remains missing is evidence.
