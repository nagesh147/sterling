"""Statistical Arbitrage (3D Spread) trading engine."""

from app.engines.statarb.config import StatArbConfig, StatArbPairConfig, default_statarb_config
from app.engines.statarb.schemas import StatArbSignal, StatArbScanResponse
from app.engines.statarb.scanner import scan_statarb_universe, scan_pair

__all__ = [
    "StatArbConfig",
    "StatArbPairConfig",
    "default_statarb_config",
    "StatArbSignal",
    "StatArbScanResponse",
    "scan_statarb_universe",
    "scan_pair"
]
