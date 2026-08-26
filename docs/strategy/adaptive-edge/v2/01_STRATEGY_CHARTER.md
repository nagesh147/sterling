# Adaptive Edge V2 — Strategy Charter

**Version:** 2.0.0-draft
**Status:** ARTIFACT-1 / SPECIFICATION-DRAFT
**Scope:** Strategy definition only; no implementation authorization

## 1. Purpose

Adaptive Edge V2 is a causal, execution-aware opportunity-selection strategy.

Its purpose is to identify a tradable opportunity from information available at a defined decision time, estimate the opportunity's economic value, determine whether the opportunity satisfies the strategy's eligibility conditions, obtain an explicit risk authorization, and produce an execution intent only when all required gates pass.

The strategy is designed as a versioned state machine. Prediction, economics, risk authorization, execution, position accounting, and learning are separate causal stages.

## 2. Problem definition

The system must answer, in order:

```text
1. What was knowable at decision time?
2. Does that information define a valid opportunity?
3. What outcome distribution does the strategy estimate from that opportunity?
4. What is the expected economic value after execution costs?
5. Is the opportunity eligible under the current strategy mode?
6. What loss budget is explicitly authorized?
7. What quantity is permitted under the authorized risk and instrument constraints?
8. What execution intent follows?
9. What actually happened at the fill/position level?
10. What outcome becomes the mature historical label?
```

No later stage may modify the semantics of an earlier stage.

## 3. Strategy boundary

V2 owns:

- feature definitions
- opportunity definition
- prediction/edge definition
- economic eligibility
- dynamic operating mode
- risk authorization policy
- position sizing semantics
- strategy entry/exit semantics
- protection semantics
- re-entry semantics
- multi-position interaction semantics
- learning/label definitions

The Sterling platform owns:

- raw market-data transport
- timestamp transport and normalization
- broker/exchange connectivity
- order submission
- authoritative order/fill state
- persistence
- reconciliation
- operational safety
- adapter-specific execution behavior

Platform behavior cannot silently redefine V2 strategy semantics.

## 4. Causal contract

For every decision at time `t_d`, every consumed input `x` must satisfy:

```text
availability_time(x) <= t_d
```

The timestamp at which information becomes available is distinct from the timestamp represented by that information.

A bar ending at `t` is not necessarily available at every instant inside that bar. V2 must use the actual observation-availability timestamp supplied by the canonical data contract.

## 5. Decision unit

The canonical decision unit is an **Opportunity Evaluation**.

An Opportunity Evaluation is immutable once created and contains:

```text
opportunity_id
strategy_version
instrument_context
observation_cutoff_time
decision_time
feature_snapshot_reference
edge_assessment_reference
economic_assessment_reference
mode_state
risk_authorization_reference
eligibility_result
rejection/approval reason codes
```

An Opportunity Evaluation is not an order, fill, position, or outcome.

## 6. Core dependency direction

```text
Raw Observations
      |
      v
Causal Feature Snapshot
      |
      v
Opportunity / Edge Assessment
      |
      v
Economic Assessment
      |
      v
Mode Eligibility
      |
      v
Risk Authorization
      |
      v
Sizing
      |
      v
Execution Intent
      |
      v
Order / Fill
      |
      v
Position State
      |
      v
Outcome / Label
      |
      v
Learning Dataset
```

Forbidden dependencies include:

```text
future outcome -> current decision
current P&L -> historical feature
execution result -> prediction that created the execution
future label -> contemporaneous eligibility
risk authorization -> prediction score
UI calculation -> strategy truth
```

## 7. Architecture frozen by this artifact

The following are architectural commitments of V2:

1. The strategy is versioned.
2. Every strategy formula receives an immutable formula identifier and version.
3. Every decision records strategy version and formula provenance.
4. Causal availability is a hard invariant.
5. Prediction, economics, risk authorization, sizing, and execution remain separate stages.
6. Execution truth comes from authoritative order/fill state, not strategy intent.
7. Risk authorization is explicit state and is not inferred from P&L.
8. Backtest and production use identical strategy mathematics; only adapters differ.
9. Unknown external dependencies remain explicit `UNKNOWN`/`TODO` dependencies.
10. No numerical parameter is production-authorized merely because it appears reasonable.
11. Every learned quantity must have a defined training/validation/test protocol before promotion.
12. A blocked upstream artifact prevents dependent implementation and execution authorization.

## 8. Deliberately NOT frozen by this artifact

This charter does **not** choose:

- trading universe
- underlying symbols
- option strikes
- expiries
- contract multipliers
- liquidity thresholds
- spread thresholds
- slippage parameters
- prediction horizons
- feature lookback lengths
- score thresholds
- mode thresholds
- risk budgets
- stop distances
- profit-protection distances
- re-entry limits
- position-count limits
- model coefficients
- training windows

Those values require later artifacts with explicit source definitions or statistically validated parameter-selection procedures.

## 9. External dependencies

### Market-data provider

**Status:** UNKNOWN

The canonical provider and its exact documentation are not assumed by this charter. TrueData remains an external dependency requiring its actual documentation before any TrueData-specific adapter contract is frozen.

### Instrument/exchange specification

**Status:** UNKNOWN

The exact tradable universe, contract metadata, session calendar, tick size, lot/contract multiplier, expiry conventions, and instrument lifecycle must be sourced from authoritative exchange/provider documentation before strategy-specific instrument semantics are frozen.

### Execution venue

**Status:** UNKNOWN

The authoritative order/fill semantics, supported order types, latency behavior, rejection states, and fee model must be sourced from the actual execution adapter documentation.

## 10. V2 objective function boundary

V2 ultimately requires an economic decision criterion of the form:

```text
Opportunity
    -> outcome distribution
    -> expected gross value
    -> expected execution cost
    -> expected net value
    -> eligibility decision
```

The exact mathematical definition of the outcome distribution, gross value, execution-cost model inputs, and eligibility threshold is intentionally deferred to later artifacts.

F-004 remains the currently frozen generic economic relationship:

```text
ExpectedNetValue = ExpectedGrossValue - ExpectedExecutionCost
```

This charter does not redefine F-004.

## 11. Versioning rule

V2 is a new strategy definition. It must never overwrite the semantics of Adaptive Edge V1.

Any semantic change after V2.0.0 is frozen requires a new strategy version and a change record identifying:

```text
old definition
new definition
reason
affected formulas
affected state transitions
affected learned quantities
backtest impact
validation impact
migration/compatibility impact
```

## 12. Artifact attack

### Causal attack

No future information is required by the charter itself. Exact data availability semantics remain an upstream dependency.

### Leakage attack

The architecture prohibits outcome/label information from entering contemporaneous decisions. The exact learning dataset is deferred and must be attacked separately.

### Circularity attack

The dependency direction is acyclic at the conceptual level. Later artifacts must prove that no feature, economics, or risk variable creates a hidden cycle.

### Execution attack

The charter does not assume fills equal intents. Exact fill semantics are deferred to execution artifacts.

### Statistical attack

No parameter or model coefficient is asserted. Therefore no claim of predictive validity is made by this artifact.

### Data-availability attack

TrueData and exact instrument/exchange semantics are explicitly UNKNOWN. No provider-specific implementation is authorized from this charter.

### Scope attack

The charter defines the strategy boundary but intentionally does not define the trading universe or numerical thresholds. Those are dependencies, not omissions to be guessed.

## 13. Completion criterion

Artifact 1 is complete when:

```text
strategy purpose is explicit
+ ownership boundaries are explicit
+ causal dependency direction is explicit
+ versioning semantics are explicit
+ unknown external dependencies are explicit
+ deferred numerical choices are explicit
+ attack results are recorded
```

It is **not** sufficient to authorize implementation.

## ARCHITECTURE STATUS

Frozen by this artifact:

```text
V2 identity and version boundary
causal pipeline
stage ownership
Opportunity Evaluation as decision unit
strategy/platform boundary
formula provenance requirement
unknown-dependency policy
parameter-governance principle
non-executable-until-resolved rule
```

## UNRESOLVED

```text
V2 opportunity definition
V2 target/outcome definition
prediction horizon
feature set
edge equation
eligibility equation
mode state machine details
risk equation
sizing equation
instrument-selection semantics
entry/exit semantics
protection semantics
re-entry semantics
multi-position semantics
learning/label protocol
```

## BLOCKERS

None for completing this charter.

The unresolved items are intentional dependencies for subsequent artifacts, not permission to invent values.

## NEXT ARTIFACT

**A26 — Opportunity and Outcome Definition**

This artifact must define exactly what constitutes an opportunity, what future outcome is being predicted, the observation/decision timestamps, the outcome horizon, label maturity, and the causal boundary between observation and outcome.
