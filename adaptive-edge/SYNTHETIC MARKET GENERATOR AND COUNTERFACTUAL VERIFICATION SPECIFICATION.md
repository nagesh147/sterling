# SYNTHETIC MARKET GENERATOR AND COUNTERFACTUAL VERIFICATION SPECIFICATION

## Canonical Verification Contract — Version 1.0

## 1. Objective

The purpose of this stage is not to prove that the strategy makes money.

The purpose is to prove that the strategy behaves correctly when the mathematical truth is known.

We create controlled event streams in which we know:

`true direction`

`true volatility`

`true liquidity`

`true execution cost`

`true opportunity duration`

`true adverse excursion`

and, most importantly:

`whether predictive edge actually exists`.

The strategy must recover those properties without inventing an edge.

---

# 2. Fundamental Verification Principle

We define:

```text
Synthetic Truth
      |
      v
Synthetic Event Stream
      |
      v
Strategy
      |
      v
Observed Output
```

Then compare:

```text
Observed Output
        vs
Synthetic Truth
```

The strategy passes only when its behavior is consistent with the known truth.

---

# 3. Two Fundamental Test Classes

There are two fundamentally different tests.

`IDENTIFICATION`

Can the strategy detect a deliberately injected edge?

and:

`REJECTION`

Can the strategy correctly reject a market containing no exploitable edge?

The second test is just as important as the first.

---

# 4. Null Market

The first environment is:

`NO_EDGE`.

The market must contain no information that predicts future direction beyond statistical noise.

Conceptually:

```text
P(UP | State_t) = P(DOWN | State_t)
```

after accounting for the defined noise process.

---

# 5. Null Market Requirement

The strategy must converge toward:

`NO_TRADE`

or:

`EV_net <= 0`.

It must not systematically discover profitable directional trading.

---

# 6. Null Market Success Criterion

The exact statistical tolerance will be determined by the verification framework, but the principle is:

```text
ObservedEdge
≈
0
```

within expected sampling uncertainty and after execution costs.

---

# 7. Why This Test Is Critical

Suppose the strategy produces:

`positive P&L`

in a true no-edge environment.

That is a serious failure.

Possible causes include:

`lookahead`

`label leakage`

`execution bias`

`incorrect option pricing`

`state contamination`

`selection bias`

or:

`bug in the validation framework`.

---

# 8. Synthetic Market A — Pure Random Walk

Construct:

```text
P_(t+1)
=
P_t + ε_t
```

where:

`ε_t`

has zero conditional expected value.

The random process must be generated independently of the strategy.

---

# 9. Random-Walk Property

The strategy receives:

`price`

`volume`

`quotes`

and other synthetic fields.

But none of these fields contain future directional information.

Therefore:

```text
E[FutureReturn | CurrentState]
≈
0
```

---

# 10. Synthetic Market B — Known Momentum

Now deliberately inject:

```text
FutureDirection
=
function(PastMomentum)
```

For example, the generator defines:

`positive recent directional pressure`

as a genuine predictor of future movement.

The exact injected relationship is known to the generator.

---

# 11. Expected Result

The strategy should detect:

`positive conditional probability`

when the injected momentum condition is active.

Outside that condition:

`NO_TRADE`.

---

# 12. Important Test

The strategy should not merely make money.

It should identify:

`WHEN`

the synthetic edge exists.

If the generator switches the edge on and off:

the strategy should adapt according to its validated learning mechanism.

---

# 13. Synthetic Market C — Known Mean Reversion

Construct:

```text
FutureReturn
=
-f(CurrentDeviation)
+
Noise
```

where deviation from a synthetic equilibrium level genuinely predicts reversal.

The strategy should detect:

`mean-reversion probability`.

---

# 14. Synthetic Market D — Regime Switching

Construct:

```text
REGIME_A:
momentum

REGIME_B:
mean reversion
```

and switch between them.

The regime transition timestamps are known exactly.

---

# 15. Expected Result

The strategy should not assume:

`one universal relationship`.

It should estimate:

```text
P(outcome | state, regime)
```

and adapt only when the available information supports that adaptation.

---

# 16. Synthetic Market E — Volatility Switching

Create:

```text
LOW_VOL
NORMAL_VOL
HIGH_VOL
EXTREME_VOL
```

with known volatility distributions.

The strategy must correctly estimate changing:

`range`

`MAE`

`MFE`

`execution cost`

and:

`opportunity persistence`.

---

# 17. Volatility Shock

Inject sudden transitions:

```text
LOW -> EXTREME
```

and:

```text
EXTREME -> LOW
```

The purpose is to test whether:

`state`

updates immediately while:

`model parameters`

remain frozen.

---

# 18. Critical Runtime Test

At a volatility shock:

```text
CurrentVolatility
        |
        v
STATE CHANGES
```

but:

```text
ValidatedParameter
```

must not spontaneously change.

This verifies:

`runtime adaptation != parameter adaptation`.

---

# 19. Synthetic Market F — False Breakout

Construct an environment where:

`breakout`

is visually strong but statistically followed by reversal.

The strategy must learn:

`breakout continuation probability`

and:

`breakout failure probability`.

---

# 20. Synthetic Market G — True Breakout

Reverse the relationship.

Now:

`breakout`

genuinely predicts continuation.

The strategy should distinguish this environment from the false-breakout environment.

---

# 21. Synthetic Market H — Liquidity Collapse

Construct:

```text
Normal liquidity
       |
       v
Liquidity collapse
       |
       v
Normal liquidity
```

During collapse:

`spread widens`

`depth decreases`

`slippage increases`.

---

# 22. Expected Result

Even if directional probability remains attractive:

the economic decision may become:

`NO_TRADE`.

This verifies that:

`prediction`

and:

`tradability`

are separate concepts.

---

# 23. Synthetic Market I — Latency Attack

Create a known edge that decays with execution delay.

For example:

```text
Edge(t + Δ)
```

decreases monotonically as:

`Δ`

increases.

---

# 24. Expected Result

The strategy should estimate:

`EV_after_latency`.

When:

`execution_delay`

makes the opportunity uneconomic:

`NO_TRADE`.

---

# 25. Synthetic Market J — Option Theta

Construct option prices where:

`underlying`

may remain approximately unchanged while:

`option value`

declines due to time decay.

This tests whether the system mistakenly treats:

`correct directional prediction`

as:

`profitable option trade`.

---

# 26. Expected Result

A directional forecast can be correct while:

`option_net_return < 0`.

The strategy must therefore reject the trade when:

`option economics`

do not support it.

---

# 27. Synthetic Market K — IV Shock

Create:

```text
IV_normal
      |
      v
IV_shock
      |
      v
IV_normal
```

while controlling underlying price movement.

The system must distinguish:

`directional edge`

from:

`option-pricing effects`.

---

# 28. Synthetic Market L — Profit Reversal

This directly tests our dynamic protection architecture.

Create:

```text
Entry
  |
  v
Profit increases
  |
  v
PeakProfit
  |
  v
Reversal
```

with known:

`giveback distribution`.

---

# 29. Expected Protection Behavior

As profit increases:

`protection boundary`

must move in the profitable direction.

It must not loosen simply because:

`expected horizon`

changes.

---

# 30. Protection Monotonicity Test

For a long position:

if:

`Price_high > Price_previous_high`

then the protected boundary must satisfy:

```text
Stop_new >= Stop_previous
```

unless an explicitly defined emergency state transition supersedes the normal rule.

---

# 31. Reverse Direction

For a short position:

if:

`Price_low < Price_previous_low`

then:

```text
Stop_new <= Stop_previous
```

Again:

`profit protection cannot move backward`.

---

# 32. Synthetic Market M — Mode Transition

Construct a trade whose future opportunity evolves:

```text
MICRO
   ->
SCALP
   ->
EXTENDED_SCALP
   ->
INTRADAY
```

The underlying process is controlled by the generator.

---

# 33. Expected Result

The runtime should reclassify:

`mode`

without modifying:

`risk protection backward`.

---

# 34. Reverse Mode Transition

Now construct:

```text
INTRADAY
   ->
EXTENDED_SCALP
   ->
SCALP
   ->
MICRO
```

The system must allow the expected horizon to shorten.

But:

`profit protection`

must not be reset.

---

# 35. Critical Invariant

Mode is:

`descriptive`.

Risk is:

`protective`.

Therefore:

```text
Mode transition
-X->
Protection reset
```

---

# 36. Synthetic Market N — Noisy Mode Classification

Construct an environment where predicted horizon oscillates:

```text
29 min
31 min
28 min
32 min
30 min
```

The mode should not continuously flip:

```text
SCALP
INTRADAY
SCALP
INTRADAY
```

unless the validated transition mechanism explicitly permits it.

---

# 37. Hysteresis Test

The state machine must have validated transition stability.

Conceptually:

```text
Current Mode
      |
      v
Evidence
      |
      v
Transition confidence
      |
      +--> insufficient -> stay
      |
      +--> sufficient -> transition
```

The exact transition sensitivity is learned.

---

# 38. Synthetic Market O — Emergency Reversal

Construct:

```text
Entry
  ->
Profit
  ->
Protection
  ->
Strong opposite signal
```

The system must determine whether:

`continuation value`

still exceeds:

`exit value`.

If not:

`EXIT`.

---

# 39. Emergency Reversal Must Not Mean Stop Widening

An opposite signal cannot justify:

```text
loss tolerance increases
```

simply because:

`model confidence changed`.

Protection and directional conviction remain separate.

---

# 40. Synthetic Market P — Stop Attack

Construct a price path that repeatedly approaches the protection boundary but does not cross it.

The purpose is to test:

`stop stability`.

---

# 41. Synthetic Market Q — Gap Through Stop

Construct:

```text
Stop = 100
PreviousPrice = 101
NextTradablePrice = 95
```

The system must not claim:

`ExitPrice = 100`.

Actual executable outcome must reflect:

`95`

or the appropriate simulated execution rule.

---

# 42. This Is Essential

Otherwise backtests systematically underestimate:

`gap risk`

and:

`slippage`.

---

# 43. Synthetic Market R — Spread Explosion

Construct:

```text
Normal spread
       |
       v
Extreme spread
```

while directional prediction remains unchanged.

The strategy should potentially move:

`TRADE`

to:

`NO_TRADE`

because:

`economic EV`

has deteriorated.

---

# 44. Synthetic Market S — Data Loss

Remove:

`depth`

or:

`trade events`

or:

`quotes`

for controlled intervals.

The system must transition into:

`CAPABILITY_DEGRADED`.

It must never silently replace missing values with fabricated information.

---

# 45. Missing Data Invariant

These are distinct:

```text
Observed zero
```

and:

```text
Missing
```

The system must preserve that distinction.

---

# 46. Synthetic Market T — Timestamp Disorder

Deliberately reorder events.

Example:

```text
10:00:01
10:00:03
10:00:02
```

The data validation layer must detect the violation.

The strategy must not silently process:

`10:00:03`

before:

`10:00:02`.

---

# 47. Synthetic Market U — Duplicate Events

Duplicate identical events.

The canonical event identity system must determine whether the duplicate is:

`retransmission`

or:

`new event`.

No double counting is allowed.

---

# 48. Synthetic Market V — Lookahead Attack

This is one of the most important tests.

Inject a feature containing:

`future return`.

For example:

```text
FutureReturn_1min
```

The feature must be explicitly marked:

`UNAVAILABLE_AT_t`.

The production feature generator must reject it.

---

# 49. Historical Replay Attack

Another version:

Allow the research system to accidentally access:

`future labels`.

The verification harness must detect:

```text
Decision_t
depends_on
Label_>t
```

and fail.

---

# 50. Lookahead Failure Is Fatal

Unlike weak performance:

`lookahead leakage`

is not a parameter problem.

It invalidates the experiment.

The entire affected experiment must be discarded.

---

# 51. Synthetic Market W — Calibration Test

Construct a synthetic process where the true probability is known.

For example:

```text
State A -> P(UP) = 0.60

State B -> P(UP) = 0.80

State C -> P(UP) = 0.30
```

The statistical model should converge toward those probabilities as sample size increases.

---

# 52. Calibration Convergence

As:

`N -> large`

we expect:

```text
EstimatedProbability
        ->
TrueProbability
```

within sampling error.

---

# 53. Synthetic Market X — Sparse Evidence

Create a state occurring only a small number of times.

The system must not output:

`P = 0.97`

with unjustified confidence.

Instead:

`EvidenceStrength`

must remain low.

---

# 54. Synthetic Market Y — Distribution Shift

Train under:

`Distribution A`.

Test under:

`Distribution B`.

The strategy must detect degradation rather than pretending the original probability remains valid.

---

# 55. Distribution Shift Detection

Possible signals:

`feature distribution drift`

`probability calibration drift`

`execution-cost drift`

`regime-frequency drift`.

The detection mechanism itself must remain auditable.

---

# 56. Synthetic Market Z — Adversarial Noise

Construct features that appear predictive in training purely by chance.

For example:

`random feature X`.

By design:

```text
P(FutureReturn | X)
=
P(FutureReturn)
```

out of sample.

---

# 57. Expected Result

The system may find apparent training correlation.

But validation/test performance must collapse toward:

`NO_EDGE`.

This tests overfitting resistance.

---

# 58. Multiple-Testing Attack

Generate:

`1,000`

independent random features.

Search for the "best."

A naive optimizer will almost certainly find apparent predictive relationships.

Our research framework must identify this as:

`multiple-testing risk`.

---

# 59. Expected Result

The selected random feature should fail on untouched out-of-sample data.

If it does not:

the validation framework is suspect.

---

# 60. Parameter Overfitting Attack

Generate a parameter family:

```text
θ1
θ2
...
θN
```

with no true relationship between parameter and future outcome.

The optimization engine must not reliably produce positive out-of-sample edge.

---

# 61. Stop Optimization Attack

Create random price paths with no edge.

Allow the optimizer to select the best stop.

The result may look profitable due to random selection.

The untouched test must expose this.

---

# 62. Target Optimization Attack

Do the same for:

`target`

`profit floor`

`trailing sensitivity`

`mode thresholds`.

Each must survive unseen data.

---

# 63. Synthetic Edge Recovery

The opposite experiment injects:

`known edge strength`.

For example:

```text
TrueEdge = +X basis points
```

The system should estimate:

`positive EV`

within expected statistical uncertainty.

---

# 64. Edge Strength Sweep

Repeat with:

```text
Very small edge
Small edge
Medium edge
Large edge
```

The strategy should become progressively more confident as evidence increases.

---

# 65. Cost Sweep

Take the same synthetic edge and increase:

`spread`

`slippage`

`fees`

`latency`.

Expected behavior:

```text
NetEV
  |
  v
positive
  |
  v
zero
  |
  v
negative
```

The system should eventually transition to:

`NO_TRADE`.

---

# 66. Risk Sweep

Increase:

`MAE`

while keeping expected gross return constant.

The strategy should reduce:

`position size`

or:

`trade eligibility`

according to the risk architecture.

---

# 67. Liquidity Sweep

Increase:

`execution uncertainty`.

Expected:

`trade frequency decreases`.

This is preferable to maintaining identical trading frequency regardless of execution conditions.

---

# 68. Probability Sweep

Increase true:

`P(UP)`.

Expected:

`CE eligibility`

should increase when economic conditions remain favorable.

Decrease it:

`CE eligibility`

should decrease.

---

# 69. Direction Symmetry Test

Create identical environments with opposite direction.

If:

`UP environment`

produces one behavior,

then the mathematically mirrored:

`DOWN environment`

should produce the corresponding opposite behavior.

This catches directional implementation asymmetry.

---

# 70. Long/Short Symmetry

For mirrored price paths:

```text
Long scenario
vs
Short scenario
```

the state machine should behave symmetrically except where real option-market mechanics legitimately break symmetry.

---

# 71. Option Symmetry Caveat

CE and PE economics are not guaranteed to be perfectly symmetric because of:

`IV skew`

`liquidity`

`spread`

`contract structure`.

Therefore:

`directional symmetry`

must not be confused with:

`economic identity`.

---

# 72. Event-Ordering Attack

Construct two event streams containing exactly the same events but different ordering.

If the ordering changes causal information:

the outputs may legitimately differ.

If ordering differs only by equivalent event representation:

the outputs should remain equivalent.

---

# 73. State Replay Test

Run:

`event stream A`

twice.

The final:

`state`

`decisions`

`positions`

must be identical.

This establishes deterministic replay.

---

# 74. Interrupted Replay

Stop the engine at event:

`t`.

Save state.

Resume from:

`t+1`.

Compare against uninterrupted replay.

Expected:

`identical final state`.

---

# 75. Restart Determinism

This is crucial for eventual production.

The system cannot depend on hidden runtime state.

Everything required to reconstruct behavior must be explicitly represented.

---

# 76. Protection-State Replay

Repeat restart testing while a position is active and:

`profit protection`

is moving.

The restored system must produce the same:

`stop boundary`

and:

`exit decision`.

---

# 77. Mode-State Replay

Repeat while the position transitions:

```text
MICRO
-> SCALP
-> EXTENDED
-> INTRADAY
-> SCALP
```

The result must remain deterministic.

---

# 78. Impossible-State Tests

The state machine must reject states such as:

```text
NO_POSITION + TRAILING_STOP_ACTIVE
```

or:

```text
POSITION_CLOSED + PROFIT_PROTECTION_ACTIVE
```

or:

```text
SHORT_POSITION + LONG_STOP_DIRECTION
```

unless explicitly represented by a valid transitional state.

---

# 79. State Invariant Test

Every state transition must satisfy:

```text
CurrentState
+
ValidEvent
=
ValidNextState
```

If:

`InvalidNextState`

occurs:

`FAIL`.

---

# 80. Protection Invariant

For long positions:

```text
ProtectedStop_(t+1)
>=
ProtectedStop_t
```

after the protection mechanism has activated.

For short:

```text
ProtectedStop_(t+1)
<=
ProtectedStop_t
```

---

# 81. Profit Giveback Invariant

If:

`PeakProfit`

increases,

the system must not erase historical:

`PeakProfit`.

Peak state is monotonic.

---

# 82. Realized P&L Invariant

Once a trade exits:

`RealizedPnL`

becomes immutable.

It cannot subsequently be altered by:

`mode changes`

or:

`new market data`.

---

# 83. Position Invariant

At any timestamp:

```text
PositionState
∈
{
FLAT,
LONG,
SHORT
}
```

unless a transitional state is explicitly defined.

---

# 84. Order Invariant

Every generated order must have:

`timestamp`

`side`

`quantity`

`instrument`

`price assumption`

`execution status`.

No anonymous order may exist.

---

# 85. Quantity Invariant

Position size cannot exceed:

`validated risk capacity`.

This must remain true regardless of:

`probability`

`mode`

or:

`profit`.

---

# 86. Profit Cannot Increase Risk

This is one of our strongest principles.

Once a trade becomes profitable:

the strategy may:

`protect`

or:

`reduce`

risk.

It cannot increase maximum loss merely because confidence increases.

---

# 87. Mode Cannot Increase Historical Risk

Transition:

`SCALP -> INTRADAY`

may change:

`continuation expectations`.

It cannot:

`restore a previously removed risk allowance`.

---

# 88. Reverse Mode Cannot Erase Protection

Transition:

`INTRADAY -> SCALP`

may tighten protection.

It cannot reset the stop to the original entry risk.

---

# 89. No Edge + Positive P&L

A no-edge environment can occasionally produce profitable trades.

That is expected.

The requirement is not:

`every trade loses`.

The requirement is:

`aggregate behavior is statistically consistent with no edge`.

---

# 90. Known Edge + Negative Individual Trades

Likewise:

a true edge does not mean every trade wins.

The system must evaluate:

`distribution`.

Not individual outcomes.

---

# 91. Monte Carlo Repetition

Each synthetic environment should be generated repeatedly with different random seeds.

A single synthetic run is insufficient.

---

# 92. Seed Independence

Results must remain qualitatively consistent across independent random seeds.

If success depends on:

`seed = 42`,

the strategy is not validated.

---

# 93. Synthetic Sample Scaling

Run experiments at increasing sample sizes:

`N_small`

`N_medium`

`N_large`.

Observe convergence.

---

# 94. Expected Convergence

For a true edge:

```text
Sample Size
   ->
uncertainty decreases
   ->
estimated probability stabilizes
   ->
economic estimate stabilizes
```

For a false edge:

```text
Sample Size
   ->
spurious signal disappears
```

---

# 95. Verification Report

Every synthetic experiment produces:

`TEST_ID`

`GENERATOR_VERSION`

`SEED`

`TRUE_PARAMETERS`

`INPUT_STREAM`

`MODEL_VERSION`

`OBSERVED_OUTPUT`

`EXPECTED_OUTPUT`

`PASS/FAIL`.

---

# 96. No Hidden Truth Access

The production strategy must never receive:

`TRUE_EDGE`

`TRUE_REGIME`

`TRUE_FUTURE_RETURN`

or:

`TRUE_GENERATOR_STATE`.

These are available only to the verification harness.

---

# 97. Oracle Separation

The synthetic test harness may know the truth.

The strategy may not.

Therefore:

```text
Generator
   |
   +--> Events -> Strategy
   |
   +--> Truth -> Verification Harness
```

The two information paths remain separate.

---

# 98. Counterfactual Verification

We can also take the same historical/synthetic event sequence and ask:

"What would have happened under another protection policy?"

"What would have happened under another execution latency?"

"What would have happened under another option?"

This is useful for validating economic operators.

---

# 99. Counterfactual Causality Rule

Counterfactual evaluation may use future events because it is evaluating:

`what would have happened`.

But the counterfactual result cannot alter:

`the historical decision`.

---

# 100. Counterfactual Example

Historical path:

```text
Entry = 100
Peak = 145
Final = 110
```

Candidate protection policies:

`Policy A`

`Policy B`

`Policy C`.

We can calculate their realized outcomes.

But the historical model can only select the policy using:

`training/validation evidence`.

---

# 101. Counterfactual Execution

Likewise:

```text
Signal at 100
```

can be evaluated under:

`10 ms`

`50 ms`

`100 ms`

`500 ms`

latency.

This reveals the edge-decay curve.

---

# 102. Counterfactual Option Selection

At a historical signal:

evaluate the actual available option universe as it existed at that timestamp.

Then compare:

`CE candidates`

`PE candidates`

and:

`NO_TRADE`.

This validates the option-selection mechanism.

---

# 103. Synthetic Verification Gate

The strategy cannot proceed to historical optimization unless:

```text
ALL CRITICAL INVARIANTS = PASS
```

and:

```text
NO-EDGE TEST = PASS
```

and:

```text
KNOWN-EDGE RECOVERY = PASS
```

and:

```text
LOOKAHEAD TEST = PASS
```

---

# 104. Critical Failures

Any of these immediately invalidates the research pipeline:

`future information leakage`

`non-deterministic replay`

`impossible state`

`profit-protection regression`

`position-size violation`

`no-edge systematic profitability`

`known-edge systematic rejection`

`incorrect execution accounting`.

---

# 105. Non-Critical Failures

Some failures may be implementation-quality rather than architectural.

For example:

`minor numerical approximation error`.

These can be logged separately if they do not affect causal correctness.

---

# 106. Synthetic Verification Hierarchy

```text
DATA
  |
  v
EVENT ORDER
  |
  v
STATE MACHINE
  |
  v
FEATURES
  |
  v
PROBABILITY
  |
  v
ECONOMICS
  |
  v
PROTECTION
  |
  v
EXECUTION
  |
  v
FULL STRATEGY
```

Each layer must pass before the next is trusted.

---

# 107. The Most Important Experiment

The single most important synthetic experiment is:

```text
NO EDGE
+
REALISTIC NOISE
+
REALISTIC COST
+
REALISTIC VOLATILITY
+
REALISTIC LIQUIDITY
```

Then run the complete strategy.

Expected:

```text
No persistent positive net edge.
```

If the strategy still produces strong positive out-of-sample performance:

stop.

Do not proceed to historical optimization.

Investigate the pipeline.

---

# 108. Second Most Important Experiment

Inject a deliberately small edge:

```text
TrueEdge > 0
```

with realistic noise and costs.

The strategy should eventually recover:

`positive net EV`

if the edge is economically large enough to survive costs.

---

# 109. Third Most Important Experiment

Inject an edge smaller than execution costs.

Expected:

`NO_TRADE`.

This tests whether the strategy understands the difference between:

`predictive`

and:

`profitable`.

---

# 110. Fourth Most Important Experiment

Inject a profitable directional edge that disappears after a regime transition.

Expected:

`performance degradation`

followed by:

`validated adaptation`

only when the learning protocol permits it.

Runtime must not secretly retrain itself.

---

# 111. Fifth Most Important Experiment

Inject a profitable trade that evolves:

```text
MICRO
-> SCALP
-> INTRADAY
-> reversal
```

Expected:

```text
Mode:
MICRO -> SCALP -> INTRADAY

Protection:
monotonically tighter

Reversal:
EXIT if continuation value becomes insufficient
```

This directly tests one of the central ideas of our strategy.

---

# 112. Sixth Most Important Experiment

Inject:

```text
INTRADAY
-> SCALP
```

after significant profit.

Expected:

`protection tightens or remains`

never:

`returns to original risk`.

---

# 113. Seventh Most Important Experiment

Inject:

`extreme volatility`

after entry.

Expected:

`state changes immediately`.

But:

`model parameters remain frozen`.

The system may alter:

`risk`

`mode`

`execution eligibility`

according to validated rules.

---

# 114. Eighth Most Important Experiment

Inject:

`liquidity collapse`

without changing directional probability.

Expected:

`NO_TRADE`

or:

`position reduction`

if the economic model determines execution has become unacceptable.

---

# 115. Ninth Most Important Experiment

Inject:

`future-information feature`.

Expected:

`research pipeline rejection`.

Not:

`excellent performance`.

---

# 116. Tenth Most Important Experiment

Run:

`random features + huge parameter search`.

Expected:

`out-of-sample collapse`.

This verifies our multiple-testing defenses.

---

# 117. Final Verification Equation

The complete strategy is accepted only if:

```text
Correctness
AND
Causality
AND
StatisticalValidity
AND
EconomicValidity
AND
RiskValidity
AND
ExecutionValidity
```

are all true.

---

# 118. Current Status

After this artifact, we have verified the conceptual system against:

`null markets`

`known edges`

`regime changes`

`volatility shocks`

`liquidity failures`

`execution latency`

`option decay`

`profit reversals`

`mode transitions`

`data corruption`

`lookahead`

`overfitting`

`multiple testing`

`state-machine invariants`.

---

# 119. What Remains Unfrozen

We still deliberately do not invent:

`synthetic parameter values`

`real-market distribution values`

`actual training window`

`actual embargo`

`actual probability thresholds`

`actual profit quantiles`

`actual risk quantiles`.

Those belong to the real-data research stage.

---

# 120. Next Artifact

The next artifact should now be:

# REAL-DATA RESEARCH DATASET CONTRACT

This is the point where we finally define exactly how the TrueData historical stream becomes the canonical research dataset.

It will specify:

`event schema`

`timestamp normalization`

`instrument identity`

`underlying/option linkage`

`session boundaries`

`corporate actions`

`expiry handling`

`missing data`

`duplicate events`

`quote reconstruction`

`trade reconstruction`

`option-chain reconstruction`

`historical state snapshots`

`data versioning`

`data-quality scores`

and:

`the exact boundary between raw data and derived features`.

Only after this contract is complete should the actual TrueData documentation become a blocker, because that is precisely where we replace our currently abstract source fields with their real API field names, semantics, precision, entitlement, and historical availability.