# Synthetic Event-by-Event Verification Specification
## Canonical State-Machine Test Suite — Version 1.0

## 1. Objective

The purpose of this specification is to verify that the mathematical strategy behaves correctly under controlled event sequences before implementation or live trading.

For every synthetic event sequence:

`E_1, E_2, ..., E_n`

the expected state must be deterministically defined:

`Ω_(t+1) = T(Ω_t, E_(t+1))`.

We are not asking whether the strategy makes money in these scenarios.

We are asking:

`Does the system behave exactly as specified?`

---

# 2. Verification Categories

The synthetic test suite covers:

`A. Normal operation`

`B. Entry`

`C. Profit expansion`

`D. Profit reversal`

`E. Regime transitions`

`F. Execution failures`

`G. Data failures`

`H. Portfolio risk`

`I. Statistical failures`

`J. State-machine failures`

`K. Extreme market conditions`

`L. Impossible-state attacks`.

Every test must specify:

`InitialState`

`Event`

`ExpectedFeatureChange`

`ExpectedProbabilityChange`

`ExpectedRiskChange`

`ExpectedState`

`ExpectedDecision`

`ExpectedInvariant`.

---

# 3. Canonical Event Representation

Each synthetic event contains:

`ExchangeTimestamp`

`ReceiveTimestamp`

`Instrument`

`Bid`

`Ask`

`LTP`

`BidQuantity`

`AskQuantity`

`TradeQuantity`

`TradeClassification`

`Volume`

`OpenInterest`

`OptionIV`

`UnderlyingPrice`

`SequenceID`.

Additional fields may be included when required.

An event with missing mandatory information is not silently repaired.

---

# 4. Test 001 — Idle Market

Initial state:

`NO_TRADE`

Event:

valid market update.

Suppose:

`P_up = 0.34`

`P_down = 0.31`

`P_neutral = 0.35`.

No candidate passes.

Expected:

`State = NO_TRADE`

`Position = NULL`

`Order = NULL`.

Invariant:

`No capital committed`.

---

# 5. Test 002 — Candidate Appears

Initial:

`NO_TRADE`.

New event causes:

`P_up ↑`

`P_neutral ↓`

`ExecutionQuality = VALID`.

Suppose:

`CandidateScore > CandidateThreshold`.

Expected:

`NO_TRADE → CANDIDATE`.

Still:

`Position = NULL`.

No order is submitted.

This verifies that candidate generation is not equivalent to entry.

---

# 6. Test 003 — Candidate Fails

Initial:

`CANDIDATE`.

New event causes:

`P_up ↓`.

Now:

`CandidateScore < cancellation boundary`.

Expected:

`CANDIDATE → NO_TRADE`.

No order.

No risk.

No trade record.

---

# 7. Test 004 — Candidate Becomes Signal

Initial:

`CANDIDATE`.

Conditions:

`Probability valid`

`ConservativeEV > 0`

`Execution valid`

`Risk capacity > 0`

`Data valid`

`Model valid`.

Expected:

`CANDIDATE → SIGNAL`.

Still:

`Position = NULL`.

---

# 8. Test 005 — Signal but No Valid Option

Suppose the underlying signal is strong.

But every option candidate fails:

`Spread`

or:

`Liquidity`

or:

`ExpectedNetEV`.

Expected:

`SIGNAL → NO_TRADE`.

This proves that:

`DirectionalEdge != automatic option trade`.

---

# 9. Test 006 — Valid CE Selection

Suppose:

`CE_1 OptionScore = 0.21`

`CE_2 OptionScore = 0.17`

`CE_3 OptionScore = invalid`.

Then:

`CE_1 = selected option`.

Expected:

`SIGNAL → ENTRY_PENDING`.

---

# 10. Test 007 — Entry Fill

Initial:

`ENTRY_PENDING`.

Event:

valid execution fill.

Suppose:

`RequestedQuantity = 10`

`FilledQuantity = 10`

`EntryPrice = 100`.

Expected:

`ENTRY_PENDING → OPEN`.

Immutable:

`ActualEntryPrice = 100`.

Initial stop and risk are calculated from the actual fill.

---

# 11. Test 008 — Partial Fill

Requested:

`10`.

Filled:

`3`.

Expected:

`PositionQuantity = 3`

`RemainingQuantity = 7`.

The system must not calculate risk as if ten contracts were filled.

If conditions deteriorate:

`RemainingQuantity → cancelled`.

The resulting position remains:

`3 contracts`.

---

# 12. Test 009 — Stale Entry

Suppose a signal occurs at:

`t`.

Price then moves significantly before the order fills.

The candidate's executable EV becomes:

`<= 0`.

Expected:

`ENTRY_PENDING → NO_TRADE`.

The system must not enter merely because:

"the original signal was valid."

---

# 13. Test 010 — Normal Profit

Suppose:

`Entry = 100`.

Price:

`100 → 102 → 105 → 108`.

Net P&L rises.

Expected:

`PeakNetPnL`

updates monotonically.

For example:

`0 → 2 → 5 → 8`.

`ProfitGiveback = 0`.

Stop may increase.

Stop must never decrease.

---

# 14. Test 011 — Profit Reversal

Sequence:

`100 → 110 → 125 → 145 → 140 → 136`.

Suppose:

`PeakNetPnL = +45`.

At:

`136`

the system calculates:

`Giveback = 9`.

If the learned allowed giveback is:

`< 9`

then:

`ProfitFloor violated`.

Expected:

`EXIT_PENDING`.

This verifies the backward protection system.

---

# 15. Test 012 — Continuation Despite Pullback

Sequence:

`100 → 120 → 115 → 118 → 125`.

Suppose the pullback does not exceed the conditional giveback boundary.

Expected:

`HOLD`.

The system must not exit simply because:

`Price < PeakPrice`.

This prevents naive trailing-stop behavior.

---

# 16. Test 013 — Stop Monotonicity

Suppose:

`CurrentStop = 110`.

Candidate calculations produce:

`CandidateStop = 108`.

Expected:

`NewStop = 110`.

Next:

`CandidateStop = 114`.

Expected:

`NewStop = 114`.

Next:

`CandidateStop = 112`.

Expected:

`NewStop = 114`.

Invariant:

`Stop_t >= Stop_(t-1)`.

---

# 17. Test 014 — Horizon Expansion

Initial state:

`SCALP`.

Suppose:

`P(H > 45m)` rises significantly.

Continuation value remains positive.

Expected:

`SCALP → EXTENDED_SCALP`

then potentially:

`EXTENDED_SCALP → INTRADAY`.

No increase in maximum downside risk.

---

# 18. Test 015 — Horizon Contraction

Initial:

`INTRADAY`.

Suppose:

`P(H <= 15m)` rises.

Continuation value decreases.

Expected:

`INTRADAY → EXTENDED_SCALP`.

The position is not automatically closed.

Management becomes more defensive.

---

# 19. Test 016 — Regime Chatter

Synthetic probabilities:

`t1: P_trend = 0.61`

`t2: P_trend = 0.54`

`t3: P_trend = 0.62`

`t4: P_trend = 0.55`.

The system must not repeatedly transition:

`TREND → NON-TREND → TREND → NON-TREND`.

Hysteresis prevents this.

The state remains unchanged unless:

`EntryTransitionEvidence > θ_enter`

or:

`ExitTransitionEvidence < θ_exit`.

---

# 20. Test 017 — Shock Event

Normal state:

`VolatilityPercentile = 0.60`.

New event causes:

`ShockScore >> normal distribution`.

Expected:

`ManagementSeverity ↑`.

If the shock exceeds the validated emergency boundary:

`EmergencyRiskState = TRUE`.

New entries:

`DISABLED`.

Existing position follows emergency protection.

---

# 21. Test 018 — Volatility Explosion

Sequence:

`σ = normal`

then:

`σ = extreme`.

The model's historical domain is exceeded.

Expected:

`ModelDomain = OUT_OF_DOMAIN`.

Therefore:

`NewEntry = FALSE`.

The system must not extrapolate indefinitely from historical distributions.

---

# 22. Test 019 — Liquidity Collapse

Before:

`Spread = normal`.

Then:

`Spread → extreme`.

Expected:

`ExecutionQuality ↓`.

If below the validated execution boundary:

`NewEntry = FALSE`.

Existing positions receive increased execution-risk weighting.

---

# 23. Test 020 — Feed Delay

Suppose:

`ExchangeTimestamp = 10:00:00.000`

`ReceiveTimestamp = 10:00:00.800`.

If the validated latency domain is exceeded:

`DataQuality = UNSAFE`.

Expected:

`NewEntry = FALSE`.

The signal itself may remain statistically attractive.

It is irrelevant because it cannot be reliably executed.

---

# 24. Test 021 — Duplicate Event

Sequence IDs:

`100`

`101`

`101`.

The second `101` is a duplicate.

Expected:

The duplicate event produces:

`NO STATE CHANGE`.

It must not modify:

`Volume`

`Delta`

`PriceVelocity`

`Profile`

`Probability`.

---

# 25. Test 022 — Out-of-Order Event

Sequence:

`100`

`102`

`101`.

If ordering cannot be reconstructed safely:

`DATA_UNSAFE`.

Expected:

`NewEntry = FALSE`.

The system must never calculate a false chronological state.

---

# 26. Test 023 — Missing Event

Suppose the feed reports:

`T1`

then:

`T2`

followed by an unexplained large timestamp gap.

Expected:

`FeedIntegrity ↓`.

If the gap exceeds the validated boundary:

`DATA_UNSAFE`.

---

# 27. Test 024 — Option IV Shock

Underlying:

`+0.3%`.

IV:

`normal → sharply lower`.

The underlying directional model remains positive.

But:

`OptionEV_CE ↓`.

Expected:

The system may transition from:

`BUY_CE`

to:

`NO_TRADE`.

This verifies that underlying direction does not override option economics.

---

# 28. Test 025 — Correct Direction, Negative Option EV

Suppose:

`P_up = 0.85`.

But selected CE has:

`large spread`

`poor liquidity`

`negative ConservativeEV`.

Expected:

`NO_TRADE`.

This is mandatory.

---

# 29. Test 026 — Stop Slippage

Suppose:

`Stop = 90`.

Market jumps:

`95 → 80`.

Actual execution:

`79`.

Expected:

`RealizedLoss`

reflects:

`79`.

The system must not record:

`Loss = 10`

simply because the theoretical stop was `90`.

This verifies execution reality.

---

# 30. Test 027 — Stop Cannot Guarantee Maximum Loss

Initial intended risk:

`₹1,000`.

Synthetic gap causes:

`RealizedLoss = ₹1,700`.

Expected:

The risk model records:

`IntendedRisk = ₹1,000`

`RealizedRisk = ₹1,700`.

It must not falsely report:

`MaximumLoss = ₹1,000`.

This distinction must propagate into the statistical risk model.

---

# 31. Test 028 — Portfolio Correlation

Positions:

`NIFTY CE`

`BANKNIFTY CE`

`Stock CE`.

Each individually passes its risk test.

But aggregate directional exposure is excessive.

Expected:

`PortfolioRisk > AllowedPortfolioRisk`.

The system rejects the new position.

This fixes the major weakness discovered in the adversarial attack.

---

# 32. Test 029 — Independent-Looking Positions

Suppose:

`NIFTY CE`

is already open.

A new:

`RELIANCE CE`

signal appears.

If the historical covariance model indicates sufficiently low incremental exposure:

the trade may proceed.

Therefore correlation does not automatically prohibit multiple positions.

It evaluates:

`IncrementalPortfolioRisk`.

---

# 33. Test 030 — Duplicate Signal

The exact same signal persists for many events.

Expected:

Only one trade may be created.

Once:

`ENTRY_PENDING`

or:

`OPEN`

exists:

`DuplicateCandidate = TRUE`.

No second order.

---

# 34. Test 031 — Algorithmic Revenge Trading

Suppose:

Trade 1:

`-₹1,000`.

Trade 2:

`-₹1,500`.

Trade 3:

signal appears.

The system must not increase position size merely because of previous losses.

Position sizing depends on:

`CurrentCapital`

`CurrentRiskState`

`CurrentExpectedValue`

`ExecutionRisk`.

Not:

`NeedToRecoverLoss`.

---

# 35. Test 032 — Martingale Attack

Loss sequence:

`L`

`L`

`L`

`L`.

The system must not produce:

`Q`

`2Q`

`4Q`

`8Q`.

Any position-sizing function that produces this without explicit validated justification fails the test.

---

# 36. Test 033 — Trade-Frequency Explosion

Synthetic market produces thousands of micro-signals.

Every signal individually has:

`GrossEV > 0`.

But:

`NetEV_after_cost < 0`.

Expected:

`NO_TRADE`.

This validates economic filtering.

---

# 37. Test 034 — Probability Overconfidence

Model outputs:

`P_up = 0.95`.

But:

`EffectiveSampleSize = low`.

Expected:

`Confidence ↓`.

The probability cannot be treated as equivalent to:

`95% high-confidence prediction`.

---

# 38. Test 035 — Calibration Failure

Suppose the model predicts:

`P_up ≈ 0.80`

for one thousand historical observations.

Actual success:

`0.56`.

Expected:

`CalibrationFailure = TRUE`.

The model becomes:

`CHALLENGER_REJECTED`

or:

`ENTRY_DISABLED`

depending on the production policy.

---

# 39. Test 036 — Distribution Drift

Historical state:

`FeatureDistribution = normal`.

Current state:

`FeatureDistribution = radically different`.

Suppose:

`DriftScore > θ_drift`.

Expected:

`ModelDomain = OUT_OF_DOMAIN`.

New entries disabled.

---

# 40. Test 037 — Whipsaw Market

Price sequence:

`100`

`103`

`99`

`104`

`98`

`105`

`97`.

Directional efficiency:

`↓`.

Regime transition frequency:

`↑`.

Expected:

`ConservativeEV ↓`.

Eventually:

`NO_TRADE`.

The strategy must recognize an unproductive market instead of increasing trade frequency.

---

# 41. Test 038 — Entry Pending Deadlock

Order submitted.

No fill.

No market improvement.

No cancellation event.

The pending-order timeout is reached.

Expected:

`ENTRY_PENDING → NO_TRADE`.

The system must never remain indefinitely in:

`ENTRY_PENDING`.

---

# 42. Test 039 — Exit Pending Failure

Exit decision occurs.

Order does not fill.

Expected:

`EXIT_PENDING → OPEN`.

But:

`ExecutionEmergency = TRUE`.

The system continues risk management.

It must never mark the position:

`CLOSED`

without an actual fill.

---

# 43. Test 040 — Simultaneous Target and Stop

Within one high-speed interval:

`Target`

and:

`Stop`

are both crossed.

If tick-level order exists:

the earliest event wins.

If event ordering is unavailable:

`AMBIGUOUS`.

The backtest must not choose whichever produces the better P&L.

This is a critical anti-optimism rule.

---

# 44. Test 041 — Impossible Position State

Attempt:

`Position = NULL`

while:

`Quantity = 5`.

Expected:

`STATE_VALIDATION_FAILURE`.

The system must not continue with an impossible state.

---

# 45. Test 042 — Impossible Closed State

Attempt:

`State = CLOSED`

while:

`LivePosition = TRUE`.

Expected:

`STATE_VALIDATION_FAILURE`.

---

# 46. Test 043 — Impossible Entry State

Attempt:

`ENTRY_PENDING`

while:

`SelectedOption = NULL`.

Expected:

`STATE_VALIDATION_FAILURE`.

---

# 47. Test 044 — Impossible Stop Movement

Attempt:

`Stop = 120`

then:

`Stop = 110`.

Expected:

`STATE_VALIDATION_FAILURE`.

The system must never silently accept a risk-increasing stop.

---

# 48. Test 045 — Learning Leakage

Historical decision:

`t = 10:00`.

Outcome becomes known:

`t = 10:30`.

Attempt to modify:

`ModelVersion`

at:

`10:05`

using the eventual outcome.

Expected:

`LEARNING_VIOLATION`.

The model remains unchanged.

---

# 49. Test 046 — Normalization Leakage

Attempt to calculate:

`VolumeZScore_10:00`

using the entire day's volume distribution.

Expected:

`LOOKAHEAD_VIOLATION`.

The feature is invalid.

---

# 50. Test 047 — Profile Leakage

Attempt to calculate:

`10:00 Profile`

using:

`10:00–15:30 completed profile`.

Expected:

`LOOKAHEAD_VIOLATION`.

---

# 51. Test 048 — Label Leakage

A forty-five-minute outcome begins:

`10:00`.

Attempt to use its partial outcome at:

`10:20`

as a completed training label.

Expected:

`LABEL_NOT_MATURE`.

Observation excluded.

---

# 52. Test 049 — Model Version Determinism

Replay identical events twice.

Inputs:

`same DataVersion`

`same ModelVersion`

`same ParameterVersion`.

Expected:

`StateSequence_A = StateSequence_B`.

Any difference indicates nondeterminism.

---

# 53. Test 050 — Champion/Challenger Isolation

Suppose:

`Champion = M1`.

`Challenger = M2`.

M2 performs extremely well on today's data.

Expected:

Production decisions continue using:

`M1`.

M2 cannot influence today's production state until the formal promotion process occurs.

---

# 54. Test 051 — Profit Floor Versus Continuation

Suppose:

`PeakPnL = +₹10,000`.

Continuation model:

`strong`.

Profit-giveback model:

`high reversal probability`.

Expected:

Continuation may remain positive, but:

`ProfitProtection`

still tightens.

The forward model cannot disable backward protection.

---

# 55. Test 052 — Hard Risk Versus Probability

Suppose:

`P_continuation = 0.95`.

But:

`HardRiskBoundary = breached`.

Expected:

`EXIT`.

Probability cannot override hard risk.

---

# 56. Test 053 — Data Safety Versus Entry

Suppose:

`ConservativeEV = strongly positive`.

But:

`DataQuality = UNSAFE`.

Expected:

`NO_TRADE`.

Safety takes precedence.

---

# 57. Test 054 — Execution Safety Versus Signal

Suppose:

`DirectionalProbability = high`.

But:

`Spread = extreme`.

Expected:

`NO_TRADE`.

---

# 58. Test 055 — Decision Precedence

We now formalize precedence.

For an existing position:

`DATA SAFETY`

does not necessarily force immediate liquidation, but disables unreliable new decisions.

For risk:

`HARD RISK`

has highest economic priority.

Then:

`EXIT`

then:

`STOP UPDATE`

then:

`HOLD`.

For a new position:

`DATA SAFETY`

`MODEL SAFETY`

`PORTFOLIO RISK`

`EXECUTION`

`ECONOMIC VALUE`

`SIGNAL`.

A lower-priority condition cannot override a higher-priority safety condition.

---

# 59. Test 056 — No Trade Is Valid

The system repeatedly receives mediocre signals.

Expected output:

`NO_TRADE`

for all events.

This is not a failure.

It proves the strategy does not need to manufacture trades.

---

# 60. Test 057 — Perfect Directional Prediction but No Economic Edge

Suppose:

`P_up = extremely high`.

But option economics produce:

`ExpectedNetEV <= 0`.

Expected:

`NO_TRADE`.

This is one of the most important tests in the entire suite.

---

# 61. Test 058 — Strong Economic Edge but Insufficient Risk Capacity

Suppose:

`ConservativeEV > 0`.

But:

`AvailableRiskCapacity < RequiredRisk`.

Expected:

`NO_TRADE`.

The strategy must not borrow risk from the future.

---

# 62. Test 059 — Strong Signal During Portfolio Stress

Existing positions consume most portfolio risk.

New signal:

`excellent`.

But:

`IncrementalPortfolioRisk`

would exceed the portfolio boundary.

Expected:

`NO_TRADE`.

---

# 63. Test 060 — Complete Catastrophic Sequence

We now combine everything.

Initial:

`NO_TRADE`.

Then:

strong signal.

Then:

CE entry.

Then:

partial fill.

Then:

trend.

Then:

large profit.

Then:

regime reversal.

Then:

volatility explosion.

Then:

liquidity collapse.

Then:

feed delay.

Then:

stop breach.

Then:

slippage.

Then:

exit failure.

The system must maintain:

`State consistency`

`Risk accounting`

`Position accounting`

`Execution accounting`

through the entire sequence.

It must never:

`double-count quantity`

`lose track of exposure`

`widen the stop`

`use future information`

`declare an unfilled exit as completed`

or:

`enter another position because the original signal remains cached`.

---

# 64. Formal Invariants

Every synthetic test must continuously verify:

`I1: Position quantity >= 0`

`I2: Filled quantity <= requested quantity`

`I3: Closed position quantity = 0`

`I4: Stop never moves adversely`

`I5: Risk never increases because of horizon expansion`

`I6: Future events never influence past state`

`I7: Duplicate events produce no additional state mutation`

`I8: Out-of-order unsafe events cannot produce normal trading decisions`

`I9: No position exists without an execution fill`

`I10: No closed position exists without an exit fill`

`I11: No new trade when data safety fails`

`I12: No new trade when model safety fails`

`I13: No new trade when portfolio risk fails`

`I14: No new trade when execution economics fail`

`I15: Probability vectors sum to one`

`I16: State transitions consume exactly one event`

`I17: Learning cannot modify the active historical model retroactively`

`I18: Production model version is immutable during its active interval`

`I19: A pending state has a valid exit path`

`I20: Every realized trade has exactly one entry and one final exit`.

---

# 65. State Coverage Requirement

Before implementation is approved, every state must have at least one test for:

`Normal transition`

`Failure transition`

`Boundary condition`.

For example:

`OPEN`

must be tested under:

`HOLD`

`UPDATE_STOP`

`EXIT`.

`ENTRY_PENDING`

must be tested under:

`FILL`

`CANCEL`

`TIMEOUT`

`PARTIAL_FILL`.

---

# 66. Transition Coverage

Every legal transition in the state graph must have a synthetic test.

Every illegal transition must have a rejection test.

Therefore:

`LegalTransition -> accepted`

`IllegalTransition -> rejected`.

This is effectively a formal transition-contract test.

---

# 67. Numerical Boundary Tests

Every threshold must be tested at:

`just below`

`exactly equal`

`just above`.

For example:

`Score = θ - ε`

`Score = θ`

`Score = θ + ε`.

This prevents ambiguous implementation around equality conditions.

---

# 68. Floating-Point Rule

The mathematical specification uses exact comparisons conceptually.

The eventual implementation must define numerical tolerance:

`ε_numeric`.

Equality-sensitive transitions must use a formally specified tolerance rather than accidental floating-point behavior.

---

# 69. Synthetic Test Result Classification

Each test receives:

`PASS`

`FAIL`

or:

`SPECIFICATION_AMBIGUOUS`.

`SPECIFICATION_AMBIGUOUS` is important.

If two reasonable implementations produce different outcomes because the specification does not define the behavior, that is a specification failure.

We must fix the specification rather than choosing whichever implementation we prefer.

---

# 70. Verification Standard

We should not proceed to production implementation until:

`All mandatory transitions = PASS`

`All invariants = PASS`

`No unresolved impossible states`

`No unresolved temporal ambiguity`

`No unresolved risk precedence`

`No unresolved execution precedence`

`No unresolved learning boundary`.

---

# 71. What This Test Suite Has Revealed

The architecture is now much stronger.

But one major issue remains:

We have specified what the system should do when quantities change, but we have not yet established whether those quantities are **statistically identifiable and estimable with sufficient sample size**.

For example:

`P(reversal | microstructure state)`

may theoretically exist.

But if that state occurs only:

`37 times`

in five years, its empirical estimate may be worthless.

Therefore:

`Mathematical definition`

does not imply:

`Statistical reliability`.

We need an explicit evidence layer.

---

# 72. Next Specification

The next artifact should therefore be:

# Statistical Identifiability and Evidence Specification

This will define:

`Minimum effective sample size`

`Confidence intervals`

`Posterior uncertainty`

`Rare-state handling`

`Sparse-state fallback`

`Distribution stability`

`Calibration requirements`

`Feature redundancy`

`Multicollinearity`

`Parameter identifiability`

`Minimum observations per regime`

`Tail-event estimation`

`Unseen-state behavior`.

Most importantly, it will answer:

> When the system encounters a market state it has insufficient historical evidence for, exactly what does it do?

The answer cannot be:

"guess."

It must mathematically become something such as:

`LOW_EVIDENCE → reduce confidence → reduce EV → NO_TRADE`

or another formally validated fallback.

That is the next major weakness we should attack before touching TrueData or implementation.