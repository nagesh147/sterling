# Adaptive Edge V2 — Evaluation Evidence Aggregation / Cycle-Level Result Contract

**Artifact:** A48  
**Version:** 2.0.0-draft  
**Status:** IMPLEMENTATION-FRAMEWORK  
**Depends on:** A39, A40, A46, A47

## 1. Purpose

A48 defines the evidence boundary between individual walk-forward evaluation cycles and any later statistical or economic interpretation.

A48 preserves every cycle as an auditable result. It does not define profitability, statistical significance, target horizon, promotion thresholds, or a preferred aggregation statistic.

## 2. Core rule

A cycle result is an evidence unit, not merely an input to an aggregate metric.

The evidence set must retain:

```text
cycle identity
candidate identity
code / feature / label / execution versions
train / validation / test boundaries
observation counts
independent-episode counts
exclusions and exclusion reasons
metric payload as supplied
contamination state
result lineage
```

## 3. Cycle preservation

Every completed evaluation cycle must be retained.

Failed, negative, excluded, and contaminated cycles must not be silently removed before downstream analysis.

The evidence set therefore represents the research population rather than only the successful cycles.

## 4. Identity consistency

All cycles in one evidence set must belong to the same evaluation identity.

Cycle identifiers must be unique.

A duplicate cycle identifier is an integrity failure rather than a second observation.

## 5. Boundary preservation

Each cycle retains independent identifiers for:

```text
training boundary
validation boundary
test boundary
```

A48 does not choose their dates or durations.

## 6. Observation versus economic episode

The evidence set preserves both:

```text
observation_count
independent_episode_count
```

These quantities must not be silently conflated. The latter depends on the eventual dependence/episode definition.

## 7. Exclusions

Excluded observations remain represented through:

```text
excluded_observation_count
exclusion_reasons
```

A downstream consumer may apply an exclusion policy only when that policy is explicitly defined elsewhere.

## 8. Contamination

A contaminated cycle remains in the evidence set.

Contamination is metadata about evidence validity; it is not permission to delete the cycle.

A47 remains responsible for determining whether an OOS claim is eligible.

## 9. Metrics

A48 stores metric payloads supplied by the evaluation layer.

It does not define:

```text
Sharpe
return threshold
drawdown threshold
confidence interval
p-value
statistical test
promotion threshold
```

No metric may be invented solely to make the evidence set complete.

## 10. Deterministic evidence identity

The evidence-set fingerprint is derived from a canonical representation of the cycle records.

The fingerprint must be independent of input ordering.

Changing any lineage, boundary, count, metric, exclusion, contamination, or result-fingerprint field changes the evidence identity.

## 11. Aggregation boundary

A48 intentionally stops before statistical aggregation.

```text
cycle results
    |
    v
A48 evidence set
    |
    +--> later statistical evaluation
    +--> later economic evaluation
    +--> later claim evaluation
```

A single aggregate number must never replace the underlying cycle records.

## 12. Reproducibility

An A48 evidence set must be reconstructible from its cycle records and their upstream lineage.

The evidence fingerprint provides integrity detection; it does not constitute a statistical validity claim.

## 13. Negative-result preservation

A cycle with poor performance, missing data, exclusions, or contamination remains part of the evidence population.

This prevents research-result survivorship from being introduced at the aggregation boundary.

## 14. Multiple candidates

Candidate selection remains outside A48.

If different candidates were evaluated, their evidence must remain attributable to their candidate identities. A48 must not silently collapse candidates into one winner.

## 15. Final-test protection

A47 remains authoritative for OOS claim eligibility.

A48 does not turn an evidence set into a final-test claim merely because it contains test cycles.

## 16. Implementation boundary

Implemented primitives provide:

```text
cycle-level result representation
cycle identity validation
evaluation identity consistency
observation / episode counts
exclusion preservation
contamination preservation
deterministic evidence fingerprint
```

Still unresolved:

```text
statistical estimator
uncertainty method
economic aggregation rule
regime aggregation policy
promotion threshold
final performance metric set
```

## 17. Completion criterion

A48 is structurally complete when downstream evaluation can consume an immutable, reproducible collection of all cycle-level evidence without reconstructing missing cycle information or relying on a single aggregate result.

## ARCHITECTURE STATUS

**FROZEN:** cycle preservation; identity consistency; boundary lineage; observation/episode distinction; exclusion preservation; contamination preservation; deterministic evidence identity; separation from statistical/economic interpretation.

**IMPLEMENTED:** cycle-level evidence representation and evidence-set construction primitives.

**UNRESOLVED:** statistical aggregation; uncertainty estimation; economic aggregation; regime policy; promotion thresholds.

**BLOCKERS:** upstream target/horizon and other strategy semantics remain unresolved for final numerical evaluation.

**NEXT ARTIFACT:** A49 — Statistical Dependence / Uncertainty Evaluation Contract.
