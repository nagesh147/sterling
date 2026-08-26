# A46 — Historical Replay / Deterministic State Reconstruction Contract

**Version:** 2.0.0-draft  
**Artifact:** A46  
**Status:** FRAMEWORK IMPLEMENTED  
**Depends on:** A38, A40, A41, A42, A43, A44, A45

## 1. Purpose

A46 defines how an Adaptive Edge historical observation sequence is reconstructed into state without consulting future observations, mutable live state, or undocumented provider semantics.

The contract is deterministic. Given the same replay manifest, event identities, source versions, feature snapshot identities, model-state identity, and reducer semantics, replay must produce the same reconstructed state fingerprint.

## 2. Replay inputs

A replay manifest identifies:

- specification versions;
- feature snapshot identities;
- model-state identity when applicable; and
- the ordered event identities to replay.

Every replay event carries:

- stable event identity;
- observation timestamp;
- deterministic sequence number;
- event type;
- immutable payload fingerprint; and
- source version.

## 3. Ordering

Events are canonically ordered by:

1. observed timestamp;
2. sequence number; and
3. event identity as the deterministic tie-breaker.

Two different events may not claim the same sequence number. Ambiguous ordering is therefore a hard replay error.

## 4. Determinism

The replay engine does not retrieve current provider values during reconstruction. TrueData may provide the historical source observations, but provider retrieval is outside the replay reducer.

The replay fingerprint incorporates the manifest identity, specification versions, feature snapshot identities, model-state identity, and each selected event identity/payload fingerprint.

## 5. No leakage

A replay implementation must not:

- access observations after the replay cutoff;
- replace historical observations with current values;
- mutate previously observed events;
- silently substitute missing events; or
- infer unavailable strategy parameters.

## 6. Missing and duplicate data

Missing manifest events are fatal because silently dropping an event changes the reconstructed state.

Duplicate event identities are fatal because two different payloads cannot safely represent one immutable observation.

## 7. Provider boundary

TrueData documentation remains the authority for TrueData transport and response semantics. A46 does not reinterpret TrueData documentation into strategy semantics.

The provider boundary is:

```text
TrueData historical source
        |
        v
immutable observation/event
        |
        v
A46 replay manifest
        |
        v
historical state reconstruction
```

## 8. Explicit non-goals

A46 does not define:

- target or horizon semantics;
- model coefficients;
- calibration parameters;
- option selection;
- risk allocation;
- position sizing;
- execution prices;
- fees or slippage;
- live order submission; or
- out-of-sample performance claims.

Those remain governed by their respective contracts and source evidence.
