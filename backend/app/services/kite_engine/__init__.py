"""Kite-exclusive wiring for the Sterling Kite Engine.

Universe building, ATM/ITM strike selection, throttled scanning and the candle
cache live here. This package may touch Kite types; the engine package
(``app.engines.sterling_kite_engine``) stays broker-agnostic. Nothing here imports
strategy/signal/options/derivative logic from any other engine.
"""
