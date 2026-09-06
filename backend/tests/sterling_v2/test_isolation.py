"""SterlingV2 must be additive: importing it must not import or mutate the
existing engines, and existing modules must be importable unchanged."""
import importlib


def test_v2_package_imports_clean():
    mod = importlib.import_module("app.engines.sterling_v2.config")
    assert mod.SimConfig().fee_round_trip == 0.001
    assert mod.V2_ENABLED_DEFAULT is False


def test_existing_engines_still_import():
    # Untouched engines must still load.
    importlib.import_module("app.engines.edge.strategies")
    importlib.import_module("app.engines.directional.orchestrator")
