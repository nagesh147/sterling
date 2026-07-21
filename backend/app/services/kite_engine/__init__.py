"""Kite-exclusive wiring for the Sterling Kite Engine.

Universe building, ATM/ITM strike selection, throttled scanning and the candle
cache live here. This package may touch Kite types; the engine package
(``app.engines.sterling_kite_engine``) stays broker-agnostic. Nothing here imports
strategy/signal/options/derivative logic from any other engine.
"""

# Install exact listed-expiry handling before the held-contract extension wraps the
# scanner. The held-contract wrapper then remains the outermost layer and continues
# evaluating exact broker-held symbols after the configured scan completes.
from app.services.kite_engine.expiry_series_runtime import install as _install_expiry_series
from app.services.kite_engine.held_contract_scan import install as _install_held_contract_scan

_install_expiry_series()
_install_held_contract_scan()
