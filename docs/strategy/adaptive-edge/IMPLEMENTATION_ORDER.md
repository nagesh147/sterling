# Adaptive Edge — Implementation Order

This is the active implementation order for `feature/adaptive-edge-formula-recovery`.

## Phase A — Strategy core

1. Market observation contract
2. Causal feature construction
3. Contextual percentile / normalization
4. Price + order-flow + liquidity evidence
5. Probability / similarity / Bayesian evidence aggregation
6. Expected move / outcome distribution

## Phase B — Option economics

7. Candidate option universe
8. Premium / bid / ask / spread
9. Option payoff under target/stop scenarios
10. Execution cost model
11. Expected gross value
12. Expected net value
13. Conservative EV / no-trade gate

## Phase C — Trade construction

14. Target / stop search
15. Risk per unit
16. Effective risk including costs and slippage
17. Lot-size / contract sizing
18. Instrument / strike selection
19. Entry trigger

## Phase D — Position management

20. Continuation value
21. Profit giveback
22. Profit floor
23. Monotonic protection
24. Exit decision
25. Re-entry rules
26. Multi-position interaction

## Phase E — Validation

27. Historical replay using the exact production strategy functions
28. Cost/slippage sensitivity
29. Walk-forward parameter learning where the source specification requires learned parameters
30. Calibration where required
31. Untouched out-of-sample evaluation
32. Robustness decision

## Explicit correction

Walk-forward fitting and calibration are not the first implementation target. They are downstream validation/learning mechanisms. A working strategy core must exist before those mechanisms can meaningfully evaluate it.

No live execution is enabled by this branch.
