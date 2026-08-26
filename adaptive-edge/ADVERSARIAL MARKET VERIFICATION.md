# ADVERSARIAL MARKET VERIFICATION
## Formal Attack Against the Complete Strategy
### Version 1.0

## 1. Verification Objective

We do not ask:

"Does the strategy work?"

We ask:

"Can the specification produce an impossible, non-causal, unsafe, or economically irrational state?"

The verification target is:

`Event -> State -> Feature -> Probability -> Evidence -> Economics -> Risk -> Decision -> Position -> Protection`

Every transition must satisfy the canonical invariants.

---

# 2. Verification Categories

We attack the system using:

`Temporal attacks`

`Data attacks`

`Market attacks`

`Execution attacks`

`Probability attacks`

`Risk attacks`

`State-machine attacks`

`Learning attacks`

`Profit-protection attacks`.

A scenario passes only if:

`No invariant is violated`.

---

# 3. Attack 001 — Duplicate Tick

Initial:

`LTP = 100`

`Volume = 1000`

Incoming event:

`E1 = LTP 101, Volume 100`

Then the exact same event arrives again.

Required:

`State(E1)`

is unchanged by the duplicate.

Therefore:

`ΔVolume = 0`

on the second occurrence.

`ΔDelta = 0`

`FeatureState = unchanged`.

Result:

`PASS`.

---

# 4. Attack 002 — Out-of-Order Tick

Events:

`10:00:01 -> Price 101`

`10:00:03 -> Price 103`

`10:00:02 -> Price 102`.

The third event arrives late.

The system must NOT simply process:

`102`

as the newest state.

It must enter:

`OUT_OF_ORDER`.

If replay/reordering is supported:

the event enters the ordering buffer.

Otherwise:

`DATA_UNSAFE`.

Result:

`PASS` only if no false chronological state is produced.

---

# 5. Attack 003 — Future Timestamp

Current information time:

`10:00:00`.

Incoming event:

`MarketTimestamp = 10:01:00`.

The system cannot use this event.

Required:

`Event = FUTURE_EVENT`.

It must not influence:

`Feature`

`Probability`

or:

`Decision`.

Result:

`PASS`.

---

# 6. Attack 004 — Historical Lookahead

At:

`10:00`

the day's eventual high is:

`150`.

But at ten o'clock the current high is:

`110`.

The state must contain:

`SessionHigh = 110`

not:

`150`.

If the backtest reports:

`SessionHigh = 150`

at ten o'clock:

`FAIL`.

---

# 7. Attack 005 — Future Volatility

Suppose:

`10:00 volatility = 0.4%`

and later:

`10:30 volatility explodes to 2%`.

The ten-o'clock volatility distribution must not contain the ten-thirty information unless that information was already legally available.

Result:

`PASS`.

---

# 8. Attack 006 — Opening Range Leak

Opening interval:

`09:15 -> 09:30`.

At:

`09:20`

the current range is:

`High = 101`

`Low = 99`.

The eventual range becomes:

`High = 105`

`Low = 98`.

At nine-twenty:

`OR_HIGH = 101`

`OR_LOW = 99`.

If the system knows:

`105`

or:

`98`

before nine-thirty:

`FAIL`.

---

# 9. Attack 007 — Label Leakage

Prediction:

`10:00`.

Label horizon:

`30 minutes`.

Outcome ends:

`10:30`.

The label is:

`IMMATURE`

until the outcome is fully observable.

The model used at ten o'clock cannot consume the ten-thirty result.

Result:

`PASS`.

---

# 10. Attack 008 — Overlapping Labels

Prediction A:

`10:00 -> 10:30`.

Prediction B:

`10:05 -> 10:35`.

The labels overlap.

The system must not treat them as fully independent observations.

Required:

`DependencyAwareEvidence`.

If the effective sample size assumes:

`N = number_of_labels`

without accounting for dependence:

`FAIL`.

---

# 11. Attack 009 — Duplicate Evidence

Suppose one underlying market event generates:

`PriceMomentum`

`PriceVelocity`

`PriceAcceleration`.

The model cannot count these as three independent confirmations merely because they have three names.

They share a common source.

The evidence model must account for feature dependence.

Result:

`PASS` only if correlation/dependence is controlled.

---

# 12. Attack 010 — Fake Order Flow

Suppose:

`Price ↑`

but:

`AggressorSide = UNKNOWN`.

The system must NOT infer:

`BUY_VOLUME ↑`.

Therefore:

`Delta`

remains unavailable.

Result:

`PASS`.

---

# 13. Attack 011 — Fake Balanced Order Book

Suppose depth feed disappears.

The system must not set:

`BidDepth = AskDepth = 0`.

That would create:

`OBI = 0`.

But zero means:

"balanced."

Missing means:

"unknown."

Required:

`OBI = UNAVAILABLE`.

Result:

`PASS`.

---

# 14. Attack 012 — Spread Explosion

Normal:

`Bid = 100`

`Ask = 100.10`.

Suddenly:

`Bid = 98`

`Ask = 103`.

The spread becomes:

`5`.

The system must recognize:

`ExecutionRisk ↑`.

It must not interpret the price discontinuity automatically as:

`strong directional signal`.

Result:

`PASS`.

---

# 15. Attack 013 — Liquidity Collapse

Before:

`BidDepth = 10000`

`AskDepth = 12000`.

Then:

`BidDepth = 100`

`AskDepth = 150`.

Price has not moved much.

The liquidity state changes drastically.

The model must detect:

`LIQUIDITY_SHOCK`.

A high-confidence directional signal cannot override an execution-safety failure.

Result:

`PASS`.

---

# 16. Attack 014 — Feed Freeze

Last valid option quote:

`100`.

No new quote arrives for an extended period.

Underlying continues:

`100 -> 102 -> 104`.

The option price must not remain treated as current.

It becomes:

`STALE`.

The system cannot calculate valid option economics from the frozen quote.

Result:

`NEW_ENTRY = NO_TRADE`.

---

# 17. Attack 015 — Underlying Live, Option Feed Dead

Underlying:

`AVAILABLE`.

Option:

`UNAVAILABLE`.

The directional model may still calculate:

`P_UP`.

But:

`BUY_CE`

cannot be executed reliably.

Therefore:

`FINAL_DECISION = NO_TRADE`.

This proves:

`Probability != Eligibility`.

---

# 18. Attack 016 — Option Live, Underlying Dead

Option quote continues arriving.

Underlying feed stops.

The system must not assume the underlying state is unchanged.

Any feature requiring current underlying state becomes:

`STALE`.

Result:

`NO_TRADE`.

---

# 19. Attack 017 — Delayed Option Quote

Underlying arrives at:

`10:00:00.500`.

Option quote timestamp:

`09:59:59.100`.

If the option quote exceeds the validated freshness condition:

`OPTION_STATE = STALE`.

The system must not calculate:

`current option execution economics`

from it.

---

# 20. Attack 018 — Latency Spike

Normal:

`FeedLatency = 30 ms`.

Suddenly:

`FeedLatency = 1500 ms`.

For a micro trade, the information is potentially obsolete before execution.

The system must transition:

`MICRO_ELIGIBLE -> MICRO_DISABLED`.

It may potentially remain eligible for a slower validated mode.

But that transition itself must be validated.

---

# 21. Attack 019 — Latency Cannot Improve Prediction

Suppose latency increases.

The system must not somehow increase:

`P_UP`.

Latency can affect:

`execution probability`

and:

`trade eligibility`.

It must not directly become bullish or bearish evidence.

---

# 22. Attack 020 — Flash Spike

Price:

`100`

then:

`110`

then:

`100`

within a very short interval.

The system must record all valid events.

It must not assume:

`110`

was the beginning of a trend.

The probability engine determines whether such patterns historically predict continuation or reversal.

---

# 23. Attack 021 — False Breakout

Opening range:

`99 - 101`.

Price:

`100 -> 102 -> 103 -> 100`.

A naive breakout system buys at:

`102`.

Our system must ask:

`P(continuation | current state)`

versus:

`P(reversal | current state)`.

If continuation does not produce sufficient conservative economic value:

`NO_TRADE`.

---

# 24. Attack 022 — Breakout With Strong Flow

Price:

`100 -> 102`.

Aggressive flow:

`strong`.

Depth:

`supportive`.

Volatility:

`normal`.

Execution:

`good`.

Probability:

`P_UP = high`.

This is a valid candidate.

But the system still requires:

`ExpectedNetPnL > required economic threshold`.

A high probability with poor payoff is not sufficient.

---

# 25. Attack 023 — High Probability, Negative EV

Suppose:

`P(win) = 0.80`.

But:

`Expected win = +₹100`

`Expected loss = -₹500`.

Expected value:

`EV = 0.80(100) + 0.20(-500)`

`EV = -₹20`.

Therefore:

`NO_TRADE`.

This formally prevents:

"high probability = trade."

---

# 26. Attack 024 — Positive EV, Excessive Tail Risk

Suppose:

`ExpectedNetPnL > 0`.

But the adverse tail is sufficiently severe that:

`RiskLimitExceeded = TRUE`.

Then:

`NO_TRADE`.

Expected value cannot override hard risk limits.

---

# 27. Attack 025 — Positive EV, Terrible Liquidity

Suppose model predicts:

`ExpectedNetPnL = +₹1000`.

But:

`Spread`

and:

`SlippageDistribution`

make the conservative net value:

`negative`.

Then:

`NO_TRADE`.

The strategy trades:

`net economics`

not theoretical price movement.

---

# 28. Attack 026 — Micro Trade Becomes Scalp

Initial:

`ExpectedHorizon = 3 minutes`.

System enters:

`MICRO`.

Price moves favorably.

New evidence shifts horizon:

`ExpectedHorizon = 18 minutes`.

The trade transitions:

`MICRO -> SCALP`.

This does NOT automatically reset:

`EntryPrice`.

It does NOT reset:

`MFE`.

It does NOT reset:

`MAE`.

It does NOT reset:

`PeakNetPnL`.

It does NOT loosen protection.

Only the mode-dependent continuation/risk calculations change.

---

# 29. Attack 027 — Scalp Becomes Intraday

Expected horizon changes:

`20 min -> 90 min`.

State:

`SCALP -> INTRADAY`.

The system may alter:

`continuation model`

`expected horizon distribution`

`profit-management logic`.

But:

`CURRENT_STOP`

must obey the protection invariant.

It cannot simply move farther from the market because the expected horizon increased.

---

# 30. Attack 028 — Intraday Suddenly Reverses

Suppose:

`Entry = 100`.

Price:

`100 -> 120 -> 135 -> 145`.

Trade has become:

`INTRADAY`.

Then:

`145 -> 138 -> 130`.

The system must calculate:

`PeakNetPnL`

and:

`Giveback`.

If the validated profit-protection condition triggers:

`EXIT`.

It must not say:

"Because this is an intraday trade, keep holding."

---

# 31. Attack 029 — Profit Giveback

Suppose:

`Entry = 100`.

Peak:

`145`.

Current:

`135`.

Ignoring option-specific economics for this synthetic example:

`PeakGain = 45`

`CurrentGain = 35`

`Giveback = 10`.

The protection system evaluates:

`Giveback / PeakGain`.

The exact threshold comes from the learned distribution.

If the threshold is crossed:

`CURRENT_STOP`

tightens or:

`EXIT`.

---

# 32. Attack 030 — Profit Never Goes Negative

Suppose the position reaches:

`+₹1000`.

The protection mechanism moves the stop to guarantee a validated retained profit floor.

Price then reverses.

The system exits:

`>= retained floor`

after costs, subject to execution uncertainty.

The important invariant is:

the strategy cannot voluntarily transform a protected profitable position into an unbounded loss merely because the predicted horizon changes.

---

# 33. Attack 031 — Stop Widening Request

Suppose:

`CURRENT_STOP = ₹120`

and:

`CandidateStop = ₹110`.

The system cannot simply apply:

`110`.

For a long-premium protection boundary:

`CurrentStop_new >= CurrentStop_old`

unless an explicit risk-transition rule allows otherwise.

Therefore:

`120`

remains.

This attacks our earlier idea of careless dynamic stop widening.

---

# 34. Attack 032 — Backward Mode Transition

Suppose:

`INTRADAY -> SCALP -> MICRO`.

The system does not recalculate the trade as though it had always been a micro trade.

Historical state remains immutable.

Only current management parameters are recalculated.

This prevents:

`mode-transition hindsight`.

---

# 35. Attack 033 — Probability Reversal

Current:

`P_UP = 0.82`.

Later:

`P_UP = 0.35`

and:

`P_DOWN = 0.55`.

The probability state changes.

The system must evaluate:

`ContinuationValue`

and:

`ExitValue`.

If exiting is economically superior:

`EXIT`.

It must not remain long merely because:

"the original signal was bullish."

---

# 36. Attack 034 — Probability Reversal Without P&L

A trade may be:

`+₹10`

but the probability of continuation collapses.

The system can exit even with small profit.

Profit alone does not determine continuation.

---

# 37. Attack 035 — Strong Continuation Probability With Existing Profit

Trade:

`+₹1000`.

Continuation probability remains high.

Expected incremental value:

`positive`.

The system may continue.

But:

`CURRENT_STOP`

must continue protecting the accumulated profit.

Therefore:

`Continuation != unprotected holding`.

---

# 38. Attack 036 — Data Failure During Maximum Profit

Trade:

`Entry = 100`

`Peak = 150`.

At exactly the peak:

`Flow feed fails`.

The system cannot calculate new flow evidence.

Required behavior:

`Do not loosen protection`.

Existing protection remains valid.

If executable option pricing remains available:

position management continues conservatively.

If executable pricing also fails:

emergency policy activates.

---

# 39. Attack 037 — Recovery After Data Failure

Data:

`VALID -> DEGRADED -> VALID`.

The system must not instantly re-enable aggressive trading merely because the feed recovered.

It must verify:

`freshness`

`sequence continuity`

`state synchronization`.

Only after successful resynchronization:

`CAPABILITY -> VALID`.

---

# 40. Attack 038 — Data Recovery With Gap

Suppose feed resumes after:

`20 seconds`.

But twenty seconds of events are missing.

The feed is technically connected.

Yet:

`HistoricalState != complete`.

Therefore:

`DATA_GAP = TRUE`.

Recovery is not equivalent to:

`fully synchronized`.

---

# 41. Attack 039 — Duplicate Recovery Burst

After reconnect:

the provider resends several recent events.

The state engine must recognize duplicates.

Otherwise:

`Volume`

`Delta`

and:

`VWAP`

may double-count.

Result:

`PASS` only if event identity/reconciliation prevents duplication.

---

# 42. Attack 040 — Impossible Price

Incoming:

`Price = -100`.

For an option price:

impossible.

The event becomes:

`INVALID`.

It must not mutate state.

---

# 43. Attack 041 — Zero Option Price

Option:

`LTP = 0`.

This requires special handling.

It cannot automatically be treated as:

`free option`.

The system must distinguish:

`valid zero`

from:

`missing/invalid`.

For traded option contracts, the semantic validity must come from source rules.

---

# 44. Attack 042 — Negative Spread

Suppose:

`Bid = 105`

`Ask = 100`.

If the source does not explicitly permit this state:

`QUOTE_INVALID`.

The system must not calculate:

`Spread = -5`

and continue.

---

# 45. Attack 043 — Probability Sum Violation

Suppose:

`P_UP = 0.7`

`P_DOWN = 0.5`

`P_NEUTRAL = 0.1`.

Sum:

`1.3`.

This is invalid.

Required:

`ProbabilityState = INVALID`.

Therefore:

`NO_TRADE`.

---

# 46. Attack 044 — Probability Outside [0,1]

Suppose:

`P_UP = 1.03`.

Impossible.

Required:

`MODEL_ERROR`.

No decision may be generated.

---

# 47. Attack 045 — Model Out of Domain

Current state is statistically far outside validated historical support.

All raw fields are available.

Nevertheless:

`DOMAIN_STATUS = OUT_OF_DOMAIN`.

The system must reduce confidence or disable trading according to the validated policy.

This demonstrates:

`DataAvailable != ModelValid`.

---

# 48. Attack 046 — Novel Volatility Regime

Historical training:

`volatility <= 1%`.

Current:

`volatility = 4%`.

The data is perfectly valid.

But the model has insufficient comparable historical evidence.

Therefore:

`DOMAIN_RISK ↑`.

The system must not extrapolate blindly.

---

# 49. Attack 047 — Extreme Positive Historical Backtest

Suppose one model produces:

`+500%`

during backtest.

That is not automatically evidence of superiority.

The system must test:

`multiple testing`

`parameter search`

`walk-forward stability`

`out-of-sample performance`

`transaction costs`

`regime stability`.

A spectacular backtest is treated as:

`candidate`

not:

`truth`.

---

# 50. Attack 048 — Parameter Overfitting

Suppose changing a parameter from:

`0.41 -> 0.42`

dramatically changes profitability.

This indicates possible:

`parameter sensitivity`.

The system should measure:

`performance surface`

rather than select the single maximum.

A robust strategy should generally have:

`stable performance region`

rather than one isolated optimum.

---

# 51. Attack 049 — Future Parameter Promotion

A parameter set is optimized on:

`January -> December`.

It cannot then be claimed to have predicted:

`January`.

The parameter version must be frozen during the evaluation period.

---

# 52. Attack 050 — Adaptive Intraday Learning

Suppose today's first ten trades are profitable.

The system must not automatically alter:

`ProbabilityModel`

mid-session based on those ten outcomes unless such online adaptation was explicitly designed, separately validated, and causally permissible.

Default:

`No online parameter mutation`.

---

# 53. Attack 051 — Losing Streak

Suppose:

`10 consecutive losses`.

The strategy must not automatically:

`double position size`.

Nor should it loosen risk because:

"the next trade is due."

Position sizing remains governed by:

`current risk`

`capital`

`economic distribution`

`validated sizing rule`.

---

# 54. Attack 052 — Winning Streak

Similarly:

`10 consecutive wins`

must not automatically increase risk.

Winning streaks can be statistically correlated.

They do not create permission to violate risk constraints.

---

# 55. Attack 053 — Simultaneous CE and PE Signals

Suppose:

`P_UP`

and:

`P_DOWN`

are both high relative to historical uncertainty.

This may represent:

`high volatility`

rather than directional certainty.

For our directional buyer strategy:

if neither direction has sufficient conservative EV:

`NO_TRADE`.

The system does not buy both simply because both probabilities are elevated.

---

# 56. Attack 054 — CE Cheaper Than PE

Suppose:

`CE EV = +₹300`

`PE EV = +₹250`.

Choose:

`CE`

only if:

`CE`

also passes:

`risk`

`execution`

`evidence`

`portfolio`

constraints.

Price alone does not determine option selection.

---

# 57. Attack 055 — Cheap Option Trap

Suppose:

`CE price = ₹10`

and:

`PE price = ₹100`.

The cheap CE may appear attractive.

But if:

`Probability`

and:

`expected payoff`

do not compensate for its low absolute sensitivity and execution characteristics:

`NO_TRADE`.

Cheap premium is not inherently favorable.

---

# 58. Attack 056 — High Delta Option Trap

Suppose one option has high delta but extremely poor:

`spread`

`liquidity`

or:

`execution cost`.

The system may prefer another contract or:

`NO_TRADE`.

Option selection is an optimization problem, not:

"choose ATM."

---

# 59. Attack 057 — Option Quote Manipulation

Suppose:

`Bid = 100`

`Ask = 101`.

Then:

`Ask = 120`

for one event.

If this quote is anomalous relative to the validated distribution:

`ExecutionQuality ↓`.

The model must not automatically treat:

`120`

as a real executable opportunity.

---

# 60. Attack 058 — LTP/Quote Inconsistency

Suppose:

`LTP = 100`

`Bid = 120`

`Ask = 121`.

This requires source-consistency validation.

If inconsistent:

`QUOTE_STATE = INVALID`.

No trade.

---

# 61. Attack 059 — Own Order Creates False Signal

We submit:

`BUY CE 100 contracts`.

Our fills increase observed volume.

The strategy must not interpret its own activity as:

`100 contracts of independent market demand`.

This prevents self-induced signal contamination.

---

# 62. Attack 060 — Partial Fill

Requested:

`100`.

Filled:

`30`.

Remaining:

`70`.

Position quantity:

`30`.

Not:

`100`.

Entry price:

actual weighted fill price.

Risk:

based on actual exposure.

---

# 63. Attack 061 — Partial Fill Then Price Collapse

Requested:

`100`.

Filled:

`30`.

Price immediately collapses.

Risk must be calculated on:

`30`.

The system must not assume the remaining seventy contracts are exposed.

---

# 64. Attack 062 — Cancel After Partial Fill

`100 requested`

`30 filled`

`70 cancelled`.

Final position:

`30`.

The cancellation cannot erase the thirty filled contracts.

---

# 65. Attack 063 — Exit Order Partial Fill

Position:

`100`.

Exit:

`100`.

Only:

`40`

fill.

Remaining position:

`60`.

The state must remain:

`OPEN`.

Risk management continues on the sixty.

---

# 66. Attack 064 — Position Already Closed

Suppose an exit completes.

A delayed duplicate exit event arrives.

The system must not create:

`negative position`.

The position state remains:

`CLOSED`.

---

# 67. Attack 065 — Emergency Exit With Stale Price

Suppose the system detects a serious risk condition.

But current quote is stale.

It must distinguish:

`decision to exit`

from:

`ability to execute exit`.

Execution safety handles the latter.

The system must not claim:

"position exited"

until actual execution confirms it.

---

# 68. Attack 066 — Broker Rejection

The system decides:

`EXIT`.

Broker rejects.

Position remains:

`OPEN`.

The state machine must immediately represent:

`EXIT_REJECTED`.

It cannot transition to:

`CLOSED`.

---

# 69. Attack 067 — Data Says Flat, Broker Says Long

Market feed indicates no position information.

Broker reports:

`LONG 100`.

Broker/account state must dominate internal assumptions for actual exposure.

This is a reconciliation failure.

Trading should be disabled until:

`PositionState`

is reconciled.

---

# 70. Attack 068 — Capital Mismatch

Internal state:

`AvailableCapital = ₹100,000`.

Broker:

`AvailableCapital = ₹20,000`.

The strategy must not use its stale internal value.

Actual broker/account state is required for execution.

---

# 71. Attack 069 — Risk Limit Race

Two candidate trades arrive almost simultaneously.

Before the first order's execution is confirmed, the second decision sees:

`AvailableRisk`.

The system must account for:

`reserved/pending risk`.

Otherwise two individually valid trades can collectively violate the portfolio limit.

---

# 72. Attack 070 — Correlated CE/PE Exposure

Suppose two candidate signals are generated on the same underlying within milliseconds.

The second cannot ignore:

`existing/pending exposure`.

Portfolio risk must be recalculated before acceptance.

---

# 73. Attack 071 — No Trade During Data Transition

Capability:

`FULL -> PARTIAL`.

At the exact transition timestamp, a signal appears.

The system must use the capability state actually valid at the decision timestamp.

No retroactive classification.

---

# 74. Attack 072 — Model Version Transition

Suppose:

`Model v1`

is active until:

`10:00`.

`Model v2`

becomes active at:

`10:00`.

A decision at:

`09:59:59.900`

uses:

`v1`.

A decision at:

`10:00:00.100`

uses:

`v2`.

Historical audit must preserve the version used.

---

# 75. Attack 073 — Model Version Rollback

Suppose v2 is later found defective.

We may roll back for future decisions.

But historical decisions made under v2 remain:

`ModelVersion = v2`.

We do not rewrite history.

---

# 76. Attack 074 — Label Revision

Suppose an outcome is initially:

`MATURED`.

Later data correction changes the underlying source.

The system must version the correction.

It must not silently rewrite previously trained datasets.

---

# 77. Attack 075 — Survivorship Bias

Suppose the model is trained only on currently active option contracts.

Expired options disappear.

This can create severe survivorship bias.

The research dataset must include the historically valid contract universe.

If unavailable:

the relevant historical claim must be marked:

`LIMITED`.

---

# 78. Attack 076 — Expired Option Selection Bias

The backtest must not select options using information such as:

"which strike eventually became profitable."

Strike selection must use only:

`information available at entry`.

---

# 79. Attack 077 — Future Expiry Knowledge

At a historical timestamp, the system may know:

`contract expiry`

because it was already published.

That is legitimate.

But it must not use future:

`option performance`

to select the contract.

---

# 80. Attack 078 — Future Liquidity Selection

We must not select:

"the option that had the best liquidity over the next hour."

Liquidity used for selection must be:

`available at decision time`.

Future liquidity belongs only to outcome analysis.

---

# 81. Attack 079 — Transaction Cost Leakage

Suppose the backtest uses the eventual average spread during the trade to calculate entry cost.

That is invalid.

Entry cost must be based on:

`entry-time executable conditions`.

Future spread affects:

`future exit economics`.

---

# 82. Attack 080 — Perfect Fill

The system must never assume:

`Buy at Bid`.

For an immediate long option purchase:

the executable reference is:

`Ask`.

Actual fill may be worse.

Therefore:

`ExpectedExecutionCost`

must include slippage uncertainty.

---

# 83. Attack 081 — Zero Slippage Assumption

If historical execution data shows:

`slippage > 0`

but backtest assumes:

`slippage = 0`.

The backtest is invalid.

---

# 84. Attack 082 — Unrealistic Stop Fill

A stop is triggered at:

`100`.

The market gaps:

`100 -> 90`.

The backtest cannot assume execution at exactly:

`100`.

Execution simulation must model:

`gap/slippage`.

---

# 85. Attack 083 — Trailing Stop Tick Ordering

Price events:

`100`

`110`

`105`

Suppose the stop should update at:

`110`.

The system must process:

`110`

first:

update stop,

then:

`105`

may trigger the updated stop.

If the simulator processes the whole candle as:

`high = 110`

and:

`low = 105`

without event ordering, it may produce an impossible result.

This is one reason tick/replay validation matters.

---

# 86. Attack 084 — Same-Timestamp Events

Two events share identical timestamps.

The system must use:

`sequence`

or another deterministic ordering mechanism.

If ordering cannot be established:

the affected state becomes:

`AMBIGUOUS`.

The backtest must not invent an ordering.

---

# 87. Attack 085 — Event Clock Resolution

If source timestamps have only:

`second precision`

then the strategy cannot legitimately claim:

`millisecond-level causal ordering`.

The precision of the strategy cannot exceed the precision of the source.

---

# 88. Attack 086 — Micro Trade Reality Check

Suppose expected trade duration:

`2 minutes`.

But:

`feed latency = 500 ms`

and:

`option spread = large`.

The statistical price signal may be correct.

The economic trade may still be invalid.

Therefore:

`Prediction accuracy`

and:

`Trade profitability`

remain separate.

---

# 89. Attack 087 — Three-Minute Trade

Suppose:

`ExpectedHorizon = 3 minutes`.

This is valid.

The system does not impose:

`minimum duration = 5 minutes`.

Our horizon model is continuous.

The trade is classified according to:

`ExpectedHorizonDistribution`.

---

# 90. Attack 088 — Thirty-Five-Minute Trade

Expected horizon:

`35 minutes`.

This can remain within the scalp regime if the learned horizon classification says so.

There is no arbitrary requirement that:

`35 minutes = intraday`.

---

# 91. Attack 089 — Forty-Four-Minute Trade

Similarly:

`44 minutes`.

It remains whatever mode the learned distribution maps it to.

The old conceptual boundary:

`<45 minutes`

is not hardcoded.

---

# 92. Attack 090 — Horizon Changes Without Price Change

Suppose price remains nearly unchanged.

But:

`flow`

`volatility`

`liquidity`

change significantly.

The expected horizon may change.

This is legitimate.

Horizon is a prediction of future behavior, not simply elapsed time.

---

# 93. Attack 091 — Elapsed Time Exceeds Expected Horizon

Expected:

`5 minutes`.

Actual:

`8 minutes`.

The trade does not automatically exit.

Instead:

`TIME_IN_TRADE`

is compared with the conditional continuation distribution.

The system asks:

"Does remaining continuation value justify continued exposure?"

---

# 94. Attack 092 — Expected Horizon Becomes Shorter

Trade has been open:

`20 minutes`.

Expected remaining horizon collapses.

The system can exit if:

`ContinuationValue < ExitValue`.

It does not need to wait for an arbitrary time limit.

---

# 95. Attack 093 — Expected Horizon Becomes Longer

Trade open:

`10 minutes`.

Expected horizon expands.

The system may continue.

But:

`risk`

and:

`profit protection`

remain independently enforced.

---

# 96. Attack 094 — Sudden Reversal After Large Profit

Synthetic sequence:

`100 -> 105 -> 115 -> 130 -> 150 -> 140 -> 125`.

The system must record:

`PeakNetPnL`

at the 150 state.

The subsequent decline generates:

`Giveback`.

Protection must react to:

`giveback`

not merely:

`current profit`.

---

# 97. Attack 095 — Reversal Before Profit

Sequence:

`100 -> 102 -> 99 -> 96`.

There is no large profit to protect.

The system uses:

`InitialStop`

and:

`CurrentRisk`.

Profit-locking logic must not pretend a profit exists.

---

# 98. Attack 096 — Whipsaw

Sequence:

`100 -> 103 -> 99 -> 104 -> 98 -> 105`.

A naive system could repeatedly enter and exit.

Our economic gate must account for:

`transaction costs`

`spread`

`execution`

`expected value`.

If repeated small movements cannot overcome costs:

`NO_TRADE`.

---

# 99. Attack 097 — High Win Rate Whipsaw

Suppose:

`WinRate = 70%`

but:

average win:

`₹50`

average loss:

`₹150`.

Then:

`EV = 0.7(50) - 0.3(150)`

`= -₹10`.

The strategy must reject the apparent high win rate.

---

# 100. Attack 098 — Low Win Rate, Positive EV

Suppose:

`WinRate = 35%`

average win:

`₹500`

average loss:

`₹100`.

Then:

`EV = 0.35(500) - 0.65(100)`

`= ₹110`.

This can be economically valid.

Therefore:

`WinRate`

is not the objective.

---

# 101. Attack 099 — Profit Factor Manipulation

A model may show high profit factor because of one enormous outlier.

We therefore require:

`distribution`

not merely:

`aggregate profit factor`.

Tail dependence must be visible.

---

# 102. Attack 100 — Single Regime Dominance

Suppose:

`90% of total profits`

come from one month.

The strategy must not be considered robust.

Performance must be decomposed by:

`month`

`volatility regime`

`session phase`

`market direction`

`capability state`.

---

# 103. Attack 101 — One Trade Dominance

Suppose:

`one trade = 60% of total profits`.

The model requires robustness analysis.

Removing that trade should not transform:

`profitable`

into:

`catastrophic`.

If it does:

`FRAGILE_EDGE`.

---

# 104. Attack 102 — Multiple Testing

Suppose we test:

`10,000`

parameter combinations.

One produces spectacular performance.

The correct question becomes:

"What was the probability of finding a spectacular result somewhere among 10,000 attempts?"

The validation layer must account for the search process.

---

# 105. Attack 103 — Feature Selection Leakage

Suppose we inspect the full test period and discover:

"Order-flow imbalance is extremely predictive."

Then we include it in the model and report test performance.

Invalid.

Feature selection must occur using:

`training/validation`

only.

---

# 106. Attack 104 — Test Set Contamination

Once the final test set is inspected repeatedly:

it is no longer a genuine untouched test.

Therefore:

`FINAL_TEST`

must remain sealed until the model is frozen.

---

# 107. Attack 105 — Regime-Specific Overfitting

Suppose the model is optimized specifically for:

`high volatility`.

It performs badly during:

`normal volatility`.

The production system must know:

`regime applicability`.

It must not claim universal validity.

---

# 108. Attack 106 — Synthetic Extreme Gap

Price:

`100`.

Next event:

`70`.

No intermediate observations.

The state engine must process:

`gap`.

The stop cannot assume it was filled at an intermediate theoretical value.

---

# 109. Attack 107 — Exchange Halt / Data Pause

No trades occur for an extended interval.

The system must distinguish:

`market inactivity`

from:

`feed failure`.

This requires session/exchange-state information.

If the distinction cannot be established:

`CAPABILITY = UNCERTAIN`.

---

# 110. Attack 108 — Market Close

At the operational cutoff:

`NewEntry = FALSE`.

Existing position:

must follow the canonical exit policy.

No new prediction may override the close constraint.

---

# 111. Attack 109 — Signal Exactly at Cutoff

Signal arrives exactly at the boundary.

The system requires deterministic timestamp comparison.

For example:

`DecisionTimestamp < Cutoff`

may be eligible.

`DecisionTimestamp >= Cutoff`

is not.

The exact inequality will be frozen in the operational contract.

---

# 112. Attack 110 — Model Wants Trade, Risk Says No

Suppose:

`P_UP = 0.90`

`EV = positive`.

But:

`PortfolioRiskCapacity = 0`.

Result:

`NO_TRADE`.

Risk has precedence.

---

# 113. Attack 111 — Model Wants Exit, Execution Says Wait

Suppose:

`EXIT`.

But:

`broker connectivity unavailable`.

The system cannot claim:

`position closed`.

It transitions into:

`EXIT_PENDING / EXECUTION_FAILURE`.

Emergency handling begins.

---

# 114. Attack 112 — Strategy Wants Hold, Hard Stop Says Exit

Suppose:

`ContinuationValue = high`.

But:

`CurrentPrice <= CurrentStop`.

Hard protection dominates.

Result:

`EXIT`.

---

# 115. Attack 113 — Strategy Wants Hold, Profit Floor Says Exit

Suppose:

`ContinuationValue > 0`.

But:

`Giveback`

crosses the validated profit-protection boundary.

Result:

`EXIT`.

This proves:

`Continuation != unlimited holding`.

---

# 116. Attack 114 — Stop and Target Trigger Same Event

Suppose one event creates a state where both:

`profit boundary`

and:

`stop`

appear relevant.

The state machine requires a deterministic precedence rule.

For a long position:

`hard adverse protection`

must not be ignored merely because a profit target was theoretically reachable.

The exact event ordering must determine which condition actually occurred first.

---

# 117. Attack 115 — Intrabar Ambiguity

If only OHLC bars are available:

`High`

and:

`Low`

do not tell us whether:

`High occurred before Low`

or:

`Low occurred before High`.

Therefore a bar-only simulator cannot truthfully resolve certain stop/target sequences.

Such trades must be:

`ambiguous`

rather than assigned a favorable order.

---

# 118. Attack 116 — Tick Replay Resolution

Where tick/replay data exists, the ambiguity can be resolved by actual event order.

This is one of the strongest reasons to use replay rather than purely candle-based backtesting.

TrueData currently documents a full-market replay facility for active Market Data API subscribers.

---

# 119. Attack 117 — Backtest Perfect Knowledge

The simulator must not know:

`future high`

`future low`

`future spread`

`future liquidity`

or:

`future option movement`

when calculating a current stop or entry.

Any such access is:

`LOOKAHEAD_FAILURE`.

---

# 120. Attack 118 — Replay Speed

Replay may be processed faster than real time.

That is acceptable.

But the logical information sequence must remain:

`event order`

and:

`information availability`.

Speed of simulation must not change causality.

---

# 121. Attack 119 — Model Uses Future Replay

The replay engine may possess the entire historical session.

The model being evaluated must not.

The replay infrastructure can know the future.

The strategy process cannot.

This distinction must be enforced architecturally.

---

# 122. Attack 120 — Oracle Contamination

If the backtest engine calculates:

`future outcome`

and accidentally exposes it to:

`state`

the entire experiment becomes invalid.

Therefore labels and future outcomes must reside in a separate research layer inaccessible to the live-state process.

---

# 123. Attack 121 — Profit Protection Creates Lookahead

Suppose the stop is calculated from:

`future maximum favorable excursion`.

Invalid.

The stop may use only:

`MFE observed so far`.

Therefore:

`MFE_t = max(P_<=t since entry)`.

---

# 124. Attack 122 — Reversal Probability Leakage

Reversal probability at:

`10:15`

must be estimated from historical situations available at that point.

It cannot be estimated from:

"what happened later in today's trade."

---

# 125. Attack 123 — Adaptive Stop Leakage

Suppose we retrospectively discover:

"the trade reversed at 145."

Then we cannot design the historical stop to trigger precisely at:

`144`.

That would be outcome-conditioned hindsight.

The stop parameters must originate from the model version active at the time.

---

# 126. Attack 124 — Learning From Open Trade

An open trade has:

`unrealized P&L`.

That outcome is not yet a matured training label.

It must not update:

`historical probability estimates`

during the trade.

---

# 127. Attack 125 — Learning From Current Session

Default production rule:

`Today's incomplete outcomes`

do not modify:

`Today's model`.

This creates a clean temporal boundary.

---

# 128. Attack 126 — Self-Reinforcing Model

Suppose the model predicts:

`UP`.

It enters.

The resulting price move increases:

`UP evidence`.

The model then becomes more bullish because of its own trade.

This is prohibited unless the observed market move independently satisfies the market-data definition.

The strategy cannot treat:

`its own position`

as evidence.

---

# 129. Attack 127 — Execution Feedback Contamination

Our fill may move the option price slightly.

That price movement is technically observable.

But the strategy must not automatically interpret its own execution as independent evidence.

A robust implementation should tag internally generated execution events.

---

# 130. Attack 128 — State Reset Error

Position closes.

Required reset:

`EntryPrice`

`MFE`

`MAE`

`PeakNetPnL`

`CurrentStop`

`PositionTime`.

Historical market state remains.

The system must not reset:

`VWAP`

or:

`SessionHigh`

because a trade closed.

---

# 131. Attack 129 — Session Reset Error

New trading day.

Required reset:

session-specific quantities.

But historical model distributions remain.

The system must not erase:

`training history`.

---

# 132. Attack 130 — Symbol Reuse

A new option contract has a similar symbol representation.

The system must use:

`canonical instrument identity`

including expiry/strike/contract properties.

It must not accidentally merge two contracts.

---

# 133. Attack 131 — Contract Expiry Transition

An option reaches expiry.

The system must not continue treating it as:

`tradable`.

The instrument state becomes:

`EXPIRED`.

---

# 134. Attack 132 — Option Chain Changes

New strikes become available.

The candidate universe changes.

The model must not use future-added strikes in historical periods where they did not exist.

This is another potential historical universe leak.

---

# 135. Attack 133 — Historical Universe Reconstruction

For each historical timestamp:

`CandidateOptions_t`

must represent the contracts actually available at that time.

Not:

`all contracts that exist today`.

---

# 136. Attack 134 — Selection After Outcome

The system must not select:

"the option with maximum future return."

Candidate selection uses only:

`information at t`.

Future performance is only:

`label`.

---

# 137. Attack 135 — Dynamic Position Size

Suppose:

`RiskCapacity`

falls after another position is opened.

The new trade's size must be calculated from:

`current`

risk capacity.

It cannot use the earlier capacity snapshot.

---

# 138. Attack 136 — Size Explosion Under Low Stop Distance

Suppose estimated stop distance becomes extremely small.

Naive formula:

`PositionSize = Risk / StopDistance`.

As:

`StopDistance -> 0`

position size approaches infinity.

Therefore the sizing system requires:

`minimum executable risk distance`

or:

`maximum position constraint`.

Otherwise:

`FAIL`.

---

# 139. Attack 137 — Option Premium Collapse

Option price:

`100 -> 1`.

Even if theoretical underlying prediction remains correct, option economics may become nonlinear.

The strategy must recalculate:

`option response`

`execution`

`risk`.

It cannot assume fixed delta.

---

# 140. Attack 138 — IV Shock

Underlying barely moves.

IV suddenly increases dramatically.

Option price rises.

The system must distinguish:

`underlying directional movement`

from:

`volatility repricing`.

This prevents false attribution of the profit to directional prediction.

---

# 141. Attack 139 — Theta Decay

Underlying remains approximately unchanged.

Option price decreases.

The model's economic distribution must include:

`time decay`.

Therefore:

`P(correct direction)`

does not imply:

`positive option P&L`.

---

# 142. Attack 140 — Correct Direction, Losing Option Trade

Underlying:

`UP`.

Model:

`correct`.

Option:

`loses money`

because of:

`theta`

`IV contraction`

`spread`

or:

`insufficient magnitude`.

The system must classify this correctly.

This is one of the most important validation tests.

---

# 143. Attack 141 — Wrong Direction, Profitable Option

The option may temporarily gain because of:

`IV expansion`

despite an incorrect directional forecast.

The model must not conclude:

"direction prediction was correct."

The label definitions must distinguish:

`underlying outcome`

from:

`option economic outcome`.

---

# 144. Attack 142 — Directional Label Mismatch

We therefore require separate historical labels:

`UNDERLYING_DIRECTION_OUTCOME`

and:

`OPTION_NET_RETURN_OUTCOME`.

The trading decision ultimately cares about:

`OPTION_NET_RETURN`

after costs.

The underlying directional probability remains useful as a causal explanatory component.

---

# 145. Attack 143 — Probability Correct, Economic Model Wrong

Suppose:

`P_UP = 0.75`.

But:

`OptionSelection`

chooses an instrument whose expected net return is negative.

The final decision must be:

`NO_TRADE`.

---

# 146. Attack 144 — Economic Model Correct, Execution Model Wrong

Suppose:

`ExpectedNetPnL = +₹500`

under theoretical mid-price.

Actual:

`spread + slippage = ₹700`.

Actual expected net:

`-₹200`.

Decision:

`NO_TRADE`.

---

# 147. Attack 145 — Strategy Profitable Only at Mid

If the backtest is profitable at:

`MID`

but unprofitable at:

`ASK entry`

and:

`BID exit`

the strategy fails realistic execution validation.

---

# 148. Attack 146 — Latency-Sensitive Edge

Suppose:

`ExpectedEdge = ₹100`.

Expected latency cost:

`₹120`.

Then:

`ConservativeNetEV < 0`.

Result:

`NO_TRADE`.

This is especially important for our shortest-duration trades.

---

# 149. Attack 147 — Edge Disappears After Delay

The system can test:

`0 ms`

`50 ms`

`100 ms`

`250 ms`

`500 ms`

`1000 ms`

and beyond, depending on measured conditions.

If profitability collapses rapidly with latency:

the strategy is:

`latency-sensitive`.

That becomes a production constraint.

---

# 150. Attack 148 — Tick Advantage Is Illusory

Suppose tick-level model produces:

`+₹1000`.

But minute-level model produces:

`+₹900`.

After realistic execution:

tick model:

`-₹100`.

minute model:

`+₹500`.

The tick model is rejected.

Higher resolution is not automatically superior.

---

# 151. Attack 149 — Tick Data Overfitting

Suppose tick model performs exceptionally well in:

`five available historical days`.

This is insufficient evidence of long-term robustness.

The model requires:

`walk-forward`

`out-of-sample`

`multiple regimes`

and:

`independent validation`.

---

# 152. Attack 150 — Replay/Data Mismatch

Historical replay and REST history may produce different representations.

The research pipeline must identify:

`source`

`version`

`timestamp`

`field semantics`.

A model trained on one representation and evaluated on another without reconciliation is invalid.

---

# 153. Attack 151 — Model Degradation

Full model:

`Price + Flow + Depth + Option + IV`.

Depth disappears.

The fallback:

`Price + Flow + Option + IV`.

This fallback is allowed only if:

`MODEL_NO_DEPTH = VALIDATED`.

Otherwise:

`NO_TRADE`.

---

# 154. Attack 152 — Multiple Missing Domains

Suppose:

`Depth = missing`

`Flow = missing`

`IV = stale`.

The model cannot simply remove all three and continue unless:

`MODEL_PRICE_OPTION`

has independent validation.

Otherwise:

`NO_TRADE`.

---

# 155. Attack 153 — Capability Oscillation

Data alternates:

`FULL`

`PARTIAL`

`FULL`

`PARTIAL`

every few milliseconds.

The strategy must not repeatedly switch models without stabilization.

Otherwise model-selection noise itself becomes a source of instability.

A capability transition mechanism must therefore require:

`validated state confirmation`.

Exact confirmation rules remain to be empirically determined.

---

# 156. Attack 154 — Model Churn

Similarly:

`MICRO -> SCALP -> MICRO -> SCALP`

every few events.

The system must not repeatedly change protection parameters in a way that causes pathological stop movement.

Mode transitions require:

`state-transition hysteresis`

or another validated stability mechanism.

The exact sensitivity is learned.

---

# 157. Attack 155 — Stop Churn

Candidate stops:

`120`

`121`

`120.5`

`121.2`

`120.8`.

The stop should not oscillate backward and forward.

For long protection:

`CURRENT_STOP`

must satisfy its monotonic protection invariant.

---

# 158. Attack 156 — Profit-Lock Churn

Similarly, profit-protection boundaries must not repeatedly unlock and relock profit based on tiny fluctuations.

Once a protection level becomes established:

it must remain valid unless an explicitly authorized state transition occurs.

---

# 159. Attack 157 — Reversal Probability Noise

Suppose:

`ReversalProbability`

changes:

`0.30 -> 0.52 -> 0.48 -> 0.55`.

The system must not treat every small change as a decisive reversal.

The transition mechanism requires:

`statistical significance`

or:

`validated hysteresis`.

---

# 160. Attack 158 — Confidence Explosion

A model receives one unusual but highly predictive event.

It must not immediately assign:

`P_UP = 0.999`.

Evidence must incorporate:

`sample support`

`uncertainty`

`calibration`

`domain distance`.

---

# 161. Attack 159 — Confidence Collapse From One Event

Conversely:

one contradictory event must not instantly reduce:

`P_UP`

to zero.

The probability mechanism must update according to the validated statistical model.

---

# 162. Attack 160 — Zero Effective Sample Size

If a condition has almost no historical observations:

`N_eff ≈ 0`.

The model cannot claim high-confidence probability.

Required:

`EVIDENCE = INSUFFICIENT`.

---

# 163. Attack 161 — Historical Regime Contamination

Suppose historical data contains:

`COVID crash`

and:

`normal market`

and:

`low-volatility regime`.

The model cannot assume all observations are identically distributed.

Regime conditioning must be part of the statistical framework.

---

# 164. Attack 162 — Regime Transition

Suppose volatility changes from:

`LOW -> EXTREME`.

The model must not continue applying the low-volatility conditional distribution without validation.

---

# 165. Attack 163 — Time-of-Day Dependence

A signal at:

`09:20`

and identical feature values at:

`14:20`

may have different conditional outcomes.

The model must preserve:

`time-of-session`.

---

# 166. Attack 164 — Session Boundary

A trade initiated near the operational cutoff cannot be treated as equivalent to one initiated at market open.

Expected horizon and execution opportunity shrink as the available session time shrinks.

The model must incorporate:

`TIME_TO_CLOSE`.

---

# 167. Attack 165 — Impossible Horizon

Suppose:

`ExpectedHorizon = 90 minutes`

but:

`TimeToClose = 20 minutes`.

The model cannot assume the full ninety-minute opportunity exists.

The horizon distribution must be conditioned on:

`remaining session`.

---

# 168. Attack 166 — Horizon Censoring

A trade cannot remain open past the operational cutoff.

Therefore historical horizon labels must account for:

`session truncation`.

Otherwise duration distributions become biased.

---

# 169. Attack 167 — Censored Outcome

If the trade would theoretically continue but the system is required to close at the cutoff:

the label must distinguish:

`natural exit`

from:

`forced session exit`.

---

# 170. Attack 168 — Forced Exit Misclassified

A trade closed at:

`15:00`

because of the operational policy must not automatically be labeled:

`prediction failed`.

The outcome type must record:

`EXIT_REASON = SESSION_CUTOFF`.

---

# 171. Attack 169 — Strategy Changes Its Own Label

The strategy cannot choose the label definition after observing outcomes.

Historical labels are fixed by the canonical label specification.

---

# 172. Attack 170 — Training/Test Boundary Contamination

If training ends:

`June 30`

then:

`July 1`

must not influence:

`June 30 model parameters`.

No exceptions.

---

# 173. Attack 171 — Walk-Forward Boundary

For a walk-forward cycle:

```text id="jzq0xk"
TRAIN -> VALIDATE -> TEST
                |
                v
          PROMOTE MODEL
                |
                v
             NEXT WINDOW
```

The test interval remains unseen during model selection.

---

# 174. Attack 172 — Repeated Test Peeking

If the test set is repeatedly inspected to improve the model:

it ceases to be a true test.

The process must preserve:

`TEST_LOCK`.

---

# 175. Attack 173 — Data Snooping

If we test hundreds of features and keep the best ones based on test performance:

the reported edge is biased upward.

Feature selection must be performed within the training/validation process.

---

# 176. Attack 174 — Parameter Stability

A valid parameter should not require:

`exactly 0.731`

when:

`0.730`

and:

`0.732`

fail catastrophically.

If it does:

`PARAMETER_FRAGILITY = HIGH`.

The model requires further investigation.

---

# 177. Attack 175 — Strategy Collapse After Cost Increase

Suppose transaction costs increase by:

`10%`.

The strategy should be stress-tested.

Then:

`25%`

`50%`

and larger adverse execution assumptions.

If profitability disappears immediately:

the edge is economically fragile.

---

# 178. Attack 176 — Slippage Stress

The same strategy must be evaluated under:

`P50 slippage`

`P75`

`P90`

`P95`

and adverse tail conditions.

The production strategy must use an appropriately conservative estimate.

---

# 179. Attack 177 — Spread Stress

Likewise:

`normal spread`

`2x`

`3x`

`5x`.

The system should know at which point:

`NO_TRADE`

becomes mandatory.

---

# 180. Attack 178 — Latency Stress

Similarly:

`normal latency`

`2x`

`5x`

`10x`.

The strategy's edge should be characterized as a function:

`EV(latency)`.

---

# 181. Attack 179 — Volatility Stress

Evaluate:

`normal`

`2x`

`3x`

`5x`.

The model must not assume that increasing volatility simply increases opportunity.

It can simultaneously increase:

`slippage`

`spread`

`option pricing uncertainty`

`tail risk`.

---

# 182. Attack 180 — Liquidity Stress

Reduce available liquidity progressively.

The system should determine:

`minimum viable liquidity`.

This becomes a learned execution boundary.

---

# 183. Attack 181 — Profit Target Maximization

Suppose a fixed target produces:

`₹500`.

But a continuation model suggests:

`₹700 expected incremental value`.

The system should not exit merely because:

`₹500`

was reached.

However, profit protection must remain active.

This verifies:

`continuation-value architecture`.

---

# 184. Attack 182 — Infinite Holding

Suppose continuation probability remains positive forever.

The system cannot hold indefinitely.

Eventually:

`time decay`

`session cutoff`

`risk`

`economic deterioration`

or:

`execution conditions`

must constrain the position.

---

# 185. Attack 183 — Theta Dominance

If:

`expected directional gain`

is smaller than:

`expected theta + spread + slippage`

then:

`NO_TRADE`.

---

# 186. Attack 184 — Correct Direction Too Late

Suppose:

`P_UP = high`.

But the predicted move requires:

`30 minutes`.

Remaining session:

`5 minutes`.

The economic opportunity may be insufficient.

Therefore:

`NO_TRADE`.

---

# 187. Attack 185 — Correct Direction, Wrong Magnitude

Underlying moves:

`+20 points`.

Model direction:

`correct`.

But the selected option requires:

`+50 points`

to overcome costs.

Result:

`negative option EV`.

Trade should not have been entered.

---

# 188. Attack 186 — Correct Direction, IV Collapse

Underlying:

`+1%`.

IV:

`-30%`.

Option:

`negative net return`.

The economic model must capture this.

---

# 189. Attack 187 — Correct Direction, Spread Explosion

Underlying moves correctly.

Option spread expands dramatically during exit.

Realized P&L falls.

Execution model must account for this.

---

# 190. Attack 188 — Wrong Direction, Tight Protection

Trade moves against us immediately.

The stop is reached.

The loss remains bounded by:

`validated execution assumptions`.

The strategy does not widen the stop simply because:

"the signal might recover."

---

# 191. Attack 189 — Stop Hunt Hypothesis

Price briefly crosses the stop and immediately reverses.

The system must still respect the stop.

We cannot retrospectively decide:

"the stop was wrong."

The distribution determines whether the stop methodology has positive expectancy over many trades.

---

# 192. Attack 190 — Repeated Stop-Outs

If many trades repeatedly hit stops and reverse:

the research system must record:

`MAE`

`MFE`

and:

`post-stop continuation`.

The strategy may eventually learn a better protection model.

But runtime cannot ignore current protection because of a historical hypothesis.

---

# 193. Attack 191 — Emergency Reversal

Suppose an open long position has:

`P_UP = 0.70`.

Then:

`P_UP = 0.20`

`P_DOWN = 0.75`.

If the validated reversal condition is triggered:

`EXIT`.

We do not immediately reverse into PE unless:

`new entry`

independently passes:

`all entry conditions`.

Therefore:

`EXIT`

and:

`NEW_ENTRY`

are separate decisions.

---

# 194. Attack 192 — Same-Tick Reversal

A long exits.

Can the system immediately buy PE on the same event?

Only if:

`new state`

and:

`execution`

permit a fresh decision.

It must not reuse the old signal.

---

# 195. Attack 193 — Position Flip Loop

The system must avoid:

`CE -> PE -> CE -> PE`

because of tiny probability fluctuations.

This requires:

`transition hysteresis`

or:

`minimum evidence advantage`.

The exact threshold is learned.

---

# 196. Attack 194 — No-Trade Stability

Similarly, the system should not oscillate:

`NO_TRADE -> BUY -> NO_TRADE -> BUY`

on tiny feature changes.

Decision transitions require validated stability.

---

# 197. Attack 195 — Capability/Decision Race

Suppose:

`FULL capability`

exists at:

`10:00:00.000`.

It becomes:

`DEGRADED`

at:

`10:00:00.100`.

A decision timestamped:

`10:00:00.050`

is evaluated under:

`FULL`.

A decision at:

`10:00:00.150`

uses:

`DEGRADED`.

This is deterministic.

---

# 198. Attack 196 — Position State Race

Order fill:

`10:00:00.100`.

Exit signal:

`10:00:00.110`.

The exit calculation must know that the position is actually:

`OPEN`.

It cannot operate against a stale:

`FLAT`.

---

# 199. Attack 197 — Fill Arrives After Exit Request

An exit request may be submitted while an entry fill is still being reconciled.

The state machine must support:

`PENDING`

transitions without creating impossible:

`negative quantity`.

---

# 200. Attack 198 — Account Reconciliation Failure

If internal:

`PositionQuantity != broker PositionQuantity`

then:

`TRADING_DISABLED`

until reconciled.

This is a hard operational invariant.

---

# 201. Attack 199 — Capital Reconciliation Failure

If:

`InternalAvailableCapital != BrokerAvailableCapital`

the internal value cannot be used for position sizing.

Trading is paused until reconciliation.

---

# 202. Attack 200 — Catastrophic Feed Failure

All market data stops.

Required:

`No new entries`.

Existing positions enter:

`EMERGENCY_POSITION_MANAGEMENT`.

The system cannot continue making predictive decisions from frozen data.

---

# 203. Formal Verification Summary

The complete attack suite tests:

`Temporal causality`

`State integrity`

`Execution realism`

`Option economics`

`Profit protection`

`Dynamic horizon`

`Model degradation`

`Walk-forward learning`

`Portfolio risk`

`Data recovery`.

---

# 204. Invariants That Must Never Fail

The following are now formal invariants.

`I1`

No future information influences current state.

`I2`

No duplicate event mutates state twice.

`I3`

No out-of-order event silently becomes current.

`I4`

Missing data never becomes zero.

`I5`

Stale data never becomes current without a valid update.

`I6`

Probability must remain mathematically valid.

`I7`

Decision cannot override hard risk limits.

`I8`

Position state reflects actual execution.

`I9`

Current protection cannot casually become less protective.

`I10`

Peak P&L cannot decrease.

`I11`

Future outcomes cannot modify past decisions.

`I12`

Model versions are immutable over their declared evaluation period.

`I13`

Unvalidated fallback models cannot trade.

`I14`

Own orders cannot become independent market-flow evidence.

`I15`

Historical option universe must reflect historically available contracts.

`I16`

Execution costs cannot use future information.

`I17`

A probability signal is not sufficient for trade eligibility.

`I18`

Mode transitions cannot erase trade history.

`I19`

Data recovery does not automatically imply synchronized state.

`I20`

Account/broker state dominates stale internal exposure.

---

# 205. Most Important Discovery

The adversarial attack exposes a critical architectural distinction:

`PREDICTION`

and:

`PROTECTION`

must remain orthogonal.

Prediction asks:

`What is likely to happen next?`

Protection asks:

`What risk are we willing to retain given what has already happened?`

A trade can therefore have:

`high continuation probability`

while simultaneously requiring:

`tighter protection`

because accumulated profit has become significant.

This is exactly what our earlier forward/backward profit idea was attempting to achieve, but now it has a formal separation.

---

# 206. Second Important Discovery

`TRADE_MODE`

must not control:

`RISK_PERMISSION`.

A trade becoming:

`SCALP -> INTRADAY`

does not grant permission to lose more.

Likewise:

`INTRADAY -> SCALP`

does not automatically force an exit.

Mode describes:

`expected opportunity horizon`.

Risk state describes:

`acceptable downside`.

---

# 207. Third Important Discovery

Tick data does not create an edge by itself.

It primarily gives us:

`higher temporal resolution`

`better state reconstruction`

`better execution modeling`

`better event ordering`.

The edge still has to survive:

`costs`

`latency`

`walk-forward testing`

`multiple-testing correction`

`out-of-domain conditions`

`adversarial scenarios`.

This is now formally embedded in the verification framework.

---

# 208. Fourth Important Discovery

The strategy should not have one universal model.

It should have:

`validated conditional models`

for different information-capability states.

Conceptually:

`M_full`

`M_no_depth`

`M_no_flow`

`M_price_option`

and so forth.

But only those that demonstrate independent out-of-sample validity may become production candidates.

---

# 209. Fifth Important Discovery

The strategy's real objective is not:

`maximize prediction accuracy`.

It is:

`maximize risk-adjusted expected net economic value`

subject to:

`execution`

`capital`

`data`

`model validity`

and:

`hard safety constraints`.

That distinction governs the entire architecture.

---

# 210. Verification Verdict

The architecture survives the conceptual adversarial attack.

However, several items cannot yet receive a numerical PASS because numerical parameters are intentionally unfrozen.

Specifically:

`Horizon transition sensitivity`

`Probability thresholds`

`Evidence thresholds`

`Profit-floor quantile`

`Reversal threshold`

`Stop sensitivity`

`Capability degradation penalty`

`Latency tolerance`

`Spread tolerance`

`Slippage quantiles`

`Minimum effective sample size`.

These must be learned through walk-forward research.

We must not invent them now.

---

# 211. What Is Now Frozen

The following are architectural invariants:

`State definitions`

`Temporal causality`

`Variable ownership`

`Dependency direction`

`Capability semantics`

`Position lifecycle`

`Protection monotonicity`

`No-lookahead rules`

`Execution realism`

`Learning boundary`

`Model-version immutability`.

---

# 212. What Remains Unfrozen

Only numerical/statistical quantities remain unfrozen.

That is intentional.

The strategy specification now tells us:

`WHAT`

and:

`WHEN`

and:

`UNDER WHAT CONDITIONS`.

Historical research will determine:

`HOW MUCH`.

---

# 213. Next Artifact

The correct next step is now the:

# PARAMETER LEARNING AND WALK-FORWARD EXPERIMENT SPECIFICATION

This is where we finally define the exact experimental machinery for discovering the numerical values.

For every unfrozen parameter we will specify:

`Parameter`

`Candidate range`

`Training objective`

`Label`

`Validation metric`

`Test metric`

`Walk-forward window`

`Purging`

`Embargo`

`Multiple-testing control`

`Stability criterion`

`Promotion criterion`.

Most importantly, we will define how the system learns values such as:

`profit-floor quantile`

`reversal probability threshold`

`stop sensitivity`

`horizon transition threshold`

`evidence threshold`

without allowing the optimization process itself to overfit the historical data.

That is the next boundary before implementation.