"""
Strategy tracks beyond the directional default.

Each track is a candidate-event generator that emits to the
`app.engines.backtest.event_ledger.EventLedger` under a distinct `track`
string. Tracks do NOT execute trades themselves until their acceptance gates
in `docs/TTACE_NEXT_STEPS.md` pass (≥200 trade sample, deflated_sharpe
≥ 0.95 on walk-forward).
"""
