"""Kite-exclusive wiring for the Sterling Kite Engine.

Universe building, ATM/ITM strike selection, throttled scanning and the candle
cache live here. This package may touch Kite types; the engine package
(``app.engines.sterling_kite_engine``) stays broker-agnostic. Nothing here imports
strategy/signal/options/derivative logic from any other engine.
"""

# Install once at package import so both manual and background scans evaluate exact
# broker-held option contracts in addition to the current moneyness ladder.
from app.services.kite_engine.held_contract_scan import install as _install_held_contract_scan

_install_held_contract_scan()
