# Adaptive Edge — Recovery Ledger

## Recovered from Sterling artifacts

1. Adaptive Edge has a dedicated engine namespace: `backend/app/engines/adaptive_edge/`.
2. `DynamicMode` and `RiskState` are separate axes.
3. `RiskAuthorization` is immutable and attached to an opportunity.
4. Mode transitions preserve the existing authorization.
5. Causal feature availability is a hard invariant.
6. Economic evaluation is separate from prediction and risk.
7. Expected net value is gross value less execution cost.
8. The dedicated UI must not reuse the SuperTrend/Navigator signal table semantics.
9. The UI must display authoritative backend values and formula IDs rather than recomputing strategy mathematics.

## Existing related Sterling work that is NOT automatically part of Adaptive Edge

The repository contains a separate derivatives-edge study and routing design. It describes an older derivatives-native research track, including calibrated options modelling and routing-gate concepts. It is explicitly not adopted as Adaptive Edge unless the Adaptive Edge specification says so.

Likewise, the existing Navigator and SuperTrend signal surfaces are shared platform/engine surfaces, not Adaptive Edge strategy definitions.

## Unresolved exact definitions

The following are not present in a form strong enough to safely claim they are the exact previously agreed Adaptive Edge formulas:

- F-101 feature normalization/score
- F-102 edge/prediction equation
- F-103 opportunity eligibility
- F-104 dynamic-mode transition thresholds
- F-105 predictive-profit protection threshold
- F-106 dynamic-risk schedule
- F-107 risk-per-unit
- F-108 position sizing beyond generic platform constraints
- F-109 instrument/option selection score
- F-110 entry trigger
- F-111 exit trigger
- F-112 trailing/profit-protection parameterization
- F-113 re-entry
- F-114 multi-position interaction

## Recovery rule

Do not infer these from SuperTrend, Navigator, old derivatives studies, or generic trading conventions.

When the exact definitions are recovered, add them here first, then promote them into `FORMULAS.md`, tests, implementation, and traceability.
