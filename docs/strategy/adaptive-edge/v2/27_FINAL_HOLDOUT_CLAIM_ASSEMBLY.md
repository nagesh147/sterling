# A51 — Final Holdout / Claim Assembly Contract

**Status:** FRAMEWORK IMPLEMENTED

## Purpose

A51 defines the boundary between research evaluation and a final untouched holdout claim. A final holdout may only be used after candidate selection and research activity have ceased for the evaluated candidate/evaluation identity.

## Required lineage

```text
candidate population
  -> A50 research selection registry
  -> frozen selected candidate
  -> untouched final holdout
  -> claim evidence
```

## Holdout eligibility

A candidate is ineligible for final-holdout evaluation when prior test observation or selection influence is recorded for that candidate/evaluation identity.

## Evidence identity

A final claim record must retain:

- holdout identity
- evaluation identity
- candidate identity
- result fingerprint
- dataset fingerprint
- claim fingerprint

## Prohibited behavior

A51 does not invent or select:

- return thresholds
- Sharpe thresholds
- confidence levels
- statistical tests
- multiple-testing corrections
- economic significance thresholds
- promotion criteria
- target or horizon semantics

Those remain governed by their respective source-defined artifacts.

## Claim boundary

A successful A51 assembly means only that the evidence satisfies the repository's final-holdout lineage and contamination invariants. It does not establish that the strategy is profitable, statistically significant, production-ready, or safe to trade.
