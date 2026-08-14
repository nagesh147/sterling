"""TrueData Provider Configuration.

Source Document Constraints (V2.6):
- Auth URL: https://auth.truedata.in/token
- History Base URL: https://history.truedata.in
- Market API Base URL: https://api.truedata.in
- Realtime Push URL: wss://push.truedata.in
- Replay URL: wss://replay.truedata.in
- Documented Grant Type: "passoword" (exact spec string)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class TrueDataProviderConfig:
    auth_url: str = os.environ.get("TRUEDATA_AUTH_URL", "https://auth.truedata.in/token")
    history_base_url: str = os.environ.get(
        "TRUEDATA_HISTORY_BASE_URL", "https://history.truedata.in"
    )
    market_api_base_url: str = os.environ.get(
        "TRUEDATA_MARKET_API_BASE_URL", "https://api.truedata.in"
    )
    realtime_push_url: str = os.environ.get(
        "TRUEDATA_REALTIME_PUSH_URL", "wss://push.truedata.in"
    )
    replay_url: str = os.environ.get("TRUEDATA_REPLAY_URL", "wss://replay.truedata.in")
    default_realtime_port: int = int(os.environ.get("TRUEDATA_REALTIME_PORT", "8082"))
    timeout_seconds: float = float(os.environ.get("TRUEDATA_TIMEOUT_SECONDS", "30.0"))

    # TrueData V2.6 document literal
    grant_type: str = "passoword"

    @property
    def env_username(self) -> str:
        return os.environ.get("TRUEDATA_USERNAME", "")

    @property
    def env_password(self) -> str:
        return os.environ.get("TRUEDATA_PASSWORD", "")


DEFAULT_CONFIG = TrueDataProviderConfig()
