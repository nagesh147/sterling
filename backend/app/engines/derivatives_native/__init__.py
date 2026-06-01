"""Native derivatives engine — generates its own futures + option legs,
bypassing the routing-gate instrument veto. Returns the existing
DualDerivativesDecision contract so downstream (FE, /execute) is unchanged."""
