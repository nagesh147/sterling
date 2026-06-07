"""Edge sleeves — strategy candidates that are validated but NOT yet live.

A sleeve lives here once research shows real promise but it has not cleared the
deployment bar (deflated Sharpe >= 0.5 on an honest, multiple-testing-corrected
validation). Modules here are intentionally NOT registered in
`edge.strategies.SIGNAL_FNS` and NOT loaded by the live registry. Promotion is a
deliberate, documented act — never automatic.
"""
