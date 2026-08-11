# Adaptive Edge — Current Status

## Done

- Canonical strategy folder established.
- Strategy semantics separated from SuperTrend and Value Flow Navigator.
- Machine-readable formula registry established.
- F-001..F-008 anchored; F-004 implemented.
- F-101..F-114 explicitly locked in both documentation and code.
- Causal feature layer implemented and now carries formula provenance.
- Edge formula interface enforced against the registry.
- Economic evaluation implemented from registry formula F-004.
- DynamicMode/RiskState separation preserved in contracts.
- Immutable RiskAuthorization contract preserved.
- Causal/economic/risk invariant tests added.
- Formula-registry lock tests added.
- Dedicated Adaptive Edge UI implemented.
- UI occupies the same right-sidebar location as the shared signal surface through a strategy switcher.
- Shared Signals surface remains intact.
- Repository recovery audit completed: no exact F-101..F-114 definitions were found in existing Sterling artifacts.

## Not claimed as complete

The exact strategy-specific mathematical definitions F-101..F-114 have not been recovered with sufficient evidence from the repository/context available to this implementation session.

Therefore Adaptive Edge is deliberately not emitting live strategy candidates yet.

## Next gates

```text
1. Recover exact F-101..F-114 definitions
2. Promote each recovered formula into FORMULAS.md + formula_registry.py
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
