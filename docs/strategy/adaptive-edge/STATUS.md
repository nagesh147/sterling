# Adaptive Edge — Current Status

## Done

- Canonical strategy folder established.
- Strategy semantics separated from SuperTrend and Value Flow Navigator.
- Formula registry established.
- Causal feature layer implemented.
- Edge formula interface implemented with a hard lock against unregistered formulas.
- Economic evaluation implemented using F-004.
- DynamicMode/RiskState separation preserved in contracts.
- Immutable RiskAuthorization contract preserved.
- Causal/economic/risk invariant tests added.
- Dedicated Adaptive Edge UI implemented.
- UI occupies the same right-sidebar location as the shared signal surface through a strategy switcher.
- Shared Signals surface remains intact.

## Not claimed as complete

The exact strategy-specific mathematical definitions F-101..F-114 have not been recovered with sufficient evidence from the repository/context available to this implementation session.

Therefore Adaptive Edge is deliberately not emitting live strategy candidates yet.

## Next gates

```text
1. Recover exact F-101..F-114 definitions
2. Promote each formula into FORMULAS.md
3. Add formula-specific unit + adversarial tests
4. Implement concrete EdgeFormula
5. Implement eligibility/mode/risk/sizing policies
6. Add authoritative backend candidate endpoint/stream
7. Bind AdaptiveEdgePanel to authoritative data
8. Run backtest/live parity validation
9. Paper/shadow validation
10. Only then enable execution
```

The UI being visible does not mean the strategy is executable. The formula lock is intentional.
