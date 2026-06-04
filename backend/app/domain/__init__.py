"""
domain — the canonical contracts surface (pure; no I/O, no FastAPI).

Everything here is broker- and market-agnostic. Infrastructure (adapters,
persistence) and application (agents, router) depend INWARD on this package;
this package depends on nothing else in app/ except the existing schemas it
blesses as canonical.
"""
