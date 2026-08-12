# A52 — Claim-Level Statistical Validity / Multiple-Testing Contract

**Status:** FRAMEWORK IMPLEMENTED / METHOD UNRESOLVED

## Purpose

A52 establishes the boundary between preserved research-selection history (A50), dependence/uncertainty evidence (A49), final-holdout evidence (A51), and a statistically adjusted claim.

## Required inputs

```text
A49 dependence / uncertainty evidence
A50 research-selection registry
A51 final-holdout evidence
        |
        v
A52 statistical-validity contract
```

The contract records the research-registry fingerprint and the full candidate-population size. A claim cannot be represented as statistically adjusted while the correction policy remains unresolved.

## Multiple-testing boundary

A50 preserves how many candidates entered the research population and which candidate was selected. A52 is the point where a source-defined multiple-testing or selection-adjustment method may be attached to that research history.

The implementation therefore requires method identity before an adjusted claim can be marked eligible.

## Deliberately unresolved

A52 does not invent:

- Bonferroni, Holm, Benjamini-Hochberg, Westfall-Young, or any other correction
- family-wise error versus false-discovery objective
- significance level
- p-value threshold
- confidence-interval construction
- dependence-adjusted resampling method
- effective sample-size formula
- economic significance threshold
- promotion threshold

Those values must come from authoritative strategy/statistical specifications or an explicitly approved research-method artifact.

## Claim invariant

```text
correction unresolved
    => adjusted claim ineligible

correction specified/applied
    => method identity required

correction applied + adjusted claim
    => statistical-validity boundary satisfied
```

Passing A52 does not establish profitability, production readiness, or safety. It establishes only that the statistical correction state is explicit and traceable rather than silently assumed.
