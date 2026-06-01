"""Phase 2a — native derivatives engine: config, engine, producer swap."""
from __future__ import annotations

import time
import pytest

from app.engines.derivatives_native.config import (
    ALPHA_SOURCES, DerivativesEngineConfig, EngineMode, RiskPosture,
)


class TestEngineConfig:
    def test_defaults(self):
        c = DerivativesEngineConfig()
        assert c.engine_mode == EngineMode.ROUTING_GATE
        assert c.active_alpha_sources == ["directional_futures"]
        assert c.risk_posture == RiskPosture.LONG_ONLY
        assert c.validation_method == 1

    def test_rejects_unknown_alpha_source(self):
        with pytest.raises(ValueError):
            DerivativesEngineConfig(active_alpha_sources=["directional_futures", "bogus"])

    def test_rejects_bad_validation_method(self):
        with pytest.raises(ValueError):
            DerivativesEngineConfig(validation_method=4)

    def test_alpha_sources_constant(self):
        assert ALPHA_SOURCES == {
            "directional_futures", "vrp_voltiming", "skew_put", "gex_pinning"}
