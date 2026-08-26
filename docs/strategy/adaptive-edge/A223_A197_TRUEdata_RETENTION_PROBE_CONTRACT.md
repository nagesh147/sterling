# A223 — A197 TrueData Retention Probe Contract

**Status:** `[IMPLEMENTED / READ-ONLY / FAIL-CLOSED]`

## Purpose

Establish an objective machine-readable retention probe before declaring the A197 LiquidityImbalance calibration corpus unavailable.

## Probe

For each weekday in the requested date interval, request a deterministic one-minute opening window:

```text
09:15:00 -> 09:16:00 Asia/Kolkata
```

using the provider's documented `yymmddTHH:mm:ss` timestamp format.

The probe records exactly one of:

```text
rows > 0  -> historical evidence found
rows = 0  -> empty provider response
exception -> probe inconclusive
```

No data is mutated and no formula is promoted.

## Interpretation

```text
provider error present
    -> A197_RETENTION_PROBE_INCONCLUSIVE

no successful historical sessions
    -> A197_NO_HISTORICAL_TICK_EVIDENCE

one or more successful sessions
    -> A197_HISTORICAL_TICK_EVIDENCE_FOUND
```

A positive probe result is **not** sufficient for A197 calibration. It only establishes that historical tick evidence exists. The existing A197 calibration gate still requires the full coverage, quality, provenance, and hash conditions.

## Why this matters

The existing acquisition path already uses NSE session chunking and the provider's required timestamp representation. fileciteturn72file0L2-L2 The prior live audit found approximately 6–7 usable `NIFTY-I` trading days while the required A197 corpus is substantially larger. fileciteturn74file0L2-L2

This probe prevents an implementation gap from being confused with a provider-retention limitation.

## Safety

The probe:

- does not alter credentials;
- does not persist raw provider data;
- does not create calibration parameters;
- does not alter formula registry state;
- does not unlock the ExecutionGate;
- treats provider errors as inconclusive rather than unavailable.

## Next action

Run this probe against the active TrueData entitlement across the required historical window. If the result demonstrates insufficient coverage without provider errors, record the measured retention boundary and stop attempting to manufacture A197 data from the current entitlement.
