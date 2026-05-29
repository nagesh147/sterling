"""Central DerivativesSelector — picks instrument (options vs futures),
strike, expiry, leverage, SL/TP for every strategy signal on Delta
Exchange India. Phase 2 of the derivatives build.

Public entry point: `selector.DerivativesSelector.decide(...)` returns
a `DerivativesDecision` with the chosen contract, sized leverage, BSM-
priced SL/TP, expected R, expected funding/theta drag, a freeze_token
(30s TTL) for preview→execute idempotency, and the top-3 alternatives
the picker considered.

Wiring contract: each strategy's `/execute` endpoint passes a
`SignalContext` (signal payload + strategy profile + market context).
The selector returns a decision the endpoint converts into a
`LiveOrderRequest` for OrderRouter. Strategy code never reaches into
the selector internals — only `decide()` and the resulting decision.
"""
