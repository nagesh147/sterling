# Probability Baseline Resolution

## Result

The canonical source supports implementation of the baseline empirical probability layer, but it does not authorize freezing the research parameters needed to turn it into a production strategy configuration.

## Source-supported implementation

```text
eligible historical population
        |
        v
outcome counts / explicit observation weights
        |
        v
empirical conditional probability
        |
        v
sample sufficiency
        |
        v
ProbabilityState
```

For the three-state directional model:

```text
UP / DOWN / NEUTRAL
```

The resulting probabilities must sum to one.

The statistical specification explicitly defines the baseline empirical estimator and gives equal observation weighting as the default baseline. It also defines effective sample size for weighted observations.

## Evidence boundary

The minimum effective sample threshold remains `UNFROZEN`. Therefore it is passed as an explicit research/configuration input rather than hard-coded.

When the evidence requirement is not met, the implementation returns:

```text
INSUFFICIENT_DATA
```

and does not manufacture a probability.

## Bayesian candidate

The source also defines Beta-Binomial smoothing as a candidate statistical method. Its prior parameters remain explicitly unresolved and are therefore inputs rather than constants.

## What remains blocked

The following are not resolved by this implementation:

- exact outcome horizon
- exact UP/DOWN/NEUTRAL classification boundary
- final conditioning/binning scheme
- minimum effective sample threshold
- dependence-adjusted effective sample methodology
- hierarchical prior construction
- calibration method
- uncertainty interval convention
- selection between empirical and Bayesian candidates
- learned feature weights

Those require the declared label, research, and walk-forward protocols.

## Consequence

Probability status changes from a generic `PARTIAL` operator to:

```text
BASELINE EMPIRICAL ESTIMATOR       IMPLEMENTED
PRODUCTION PROBABILITY CONTRACT    PARTIAL / PARAMETERS UNFROZEN
CALIBRATION                         BLOCKED / METHOD UNFROZEN
UNCERTAINTY                         PARTIAL / INTERVAL UNFROZEN
```

No numerical strategy threshold has been invented.
