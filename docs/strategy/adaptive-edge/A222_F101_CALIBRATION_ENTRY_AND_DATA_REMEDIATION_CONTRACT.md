# A222 — F-101 Calibration Entry and Data Remediation Contract

**Status:** `[CANONICAL / RESEARCH GATE]`
**Formula:** `F-101`
**Production:** `LOCKED`
**ExecutionGate:** `BLOCKED`
**Date:** 2026-08-18

## 1. Purpose

A222 defines what must be true before the F-101 A197 calibration process may begin and what actions are permitted when the current market-data corpus fails that gate.

This artifact does not select parameters, alter the F-101 formula, authorize a provider substitution, or unlock execution.

## 2. Current evidence

The current Sterling evidence establishes:

```text
1-minute NIFTY 50 bars        -> sufficient historical depth
NIFTY-I tick history          -> only recent entitled window
NIFTY 50 tick bid/ask qty     -> present but zero in sampled windows
NIFTY-I bid/ask qty           -> non-zero in sampled windows
A197 LI calibration corpus    -> unavailable
```

Therefore the blocker is historical LiquidityImbalance evidence, not calibration compute capacity.

## 3. Calibration entry invariant

F-101 calibration may enter the A197 protocol only when all conditions hold:

```text
bar_count >= 45,000
AND trading_days >= 120
AND LI-valid observations >= 45,000
AND missing_score_rate <= 0.1%
AND no observations outside the authorized session
AND no observations beyond the A126 lifecycle cutoff
AND dataset_sha256 is present and valid
AND canonical_sequence_hash is present and valid
```

A dataset satisfying only the bar-history requirement is insufficient.

## 4. Permitted remediation paths

Only the following remediation paths are valid:

### R1 — Obtain sufficient TrueData historical tick entitlement

Request/enable a TrueData entitlement that demonstrably exposes the required historical `NIFTY-I` bid/ask quantity data for at least the A197 coverage window.

Validation must be performed by probing multiple non-adjacent historical dates before attempting full acquisition.

```text
recent control
oldest expected date
middle date
several boundary dates
        |
        v
non-empty LI-capable tick responses
        |
        v
full acquisition
```

### R2 — Acquire an independently authorized historical dataset

If TrueData cannot supply the required historical depth, a different market-data source may be evaluated only through an explicit strategy/data-governance decision.

The substitute must preserve the canonical LI semantics and provide sufficient provenance, timestamp integrity, and bid/ask quantity fields.

No silent provider substitution is permitted.

### R3 — Revisit the F-101 feature contract

If historical LI cannot be obtained from any authorized source, the F-101 feature subset may be reconsidered only through a new strategy decision artifact.

This is a strategy-definition change, not a calibration workaround.

A proxy for LiquidityImbalance is prohibited unless explicitly authorized as a new feature definition.

## 5. Prohibited remediation

The following do **not** satisfy A197:

- inventing or interpolating historical ticks;
- treating NIFTY 50 zero-quantity quotes as valid LI;
- extending seven days into six months through synthetic data;
- replacing LI with another feature without a strategy decision;
- using current-window parameters as production parameters;
- declaring A197 satisfied because 45,000 bars exist;
- fitting parameters on validation or test observations;
- unlocking execution because a short-window backtest is profitable.

## 6. Acquisition acceptance test

Before full acquisition, the operator must produce a retention probe report containing:

| Evidence | Required |
|---|---:|
| provider account/entitlement identity | YES |
| symbol used for LI | YES |
| request format | YES |
| historical probe dates | >= 5 |
| non-adjacent historical dates | YES |
| returned bidqty/askqty | YES |
| non-zero LQ evidence | YES |
| empty-range interpretation | RECORDED |
| dataset provenance | YES |

A successful recent-day request alone is not evidence of A197-scale retention.

## 7. Calibration sequence after remediation

Once the corpus passes the entry gate:

```text
RAW PROVIDER DATA
      |
      v
CANONICAL EVENT SEQUENCE
      |
      v
DATASET + SEQUENCE HASH
      |
      v
A197 ENTRY GATE
      |
      v
FEATURE CONSTRUCTION
      |
      v
TRAIN
      |
      v
PARAMETER ESTIMATION
      |
      v
FREEZE FOR FOLD
      |
      v
VALIDATE
      |
      v
TEST
      |
      v
OUT-OF-SAMPLE REPORT
```

Every fold remains temporally causal and test-isolated.

## 8. Decision

As of 2026-08-18:

```text
A197 calibration entry: BLOCKED
Reason: insufficient historical LI evidence
Permitted next action: data entitlement / authorized data-source remediation
Production authorization: BLOCKED
```

No mathematical shortcut exists around this gate.
