"""TrueData Realtime & Replay WebSocket client connection managers.

Enforces TrueData V2.6 single active streaming session constraint per user credential.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set

from app.core.logging import get_logger
from .config import DEFAULT_CONFIG

log = get_logger(__name__)


class SingleStreamConflictError(RuntimeError):
    """Raised when an active TrueData WebSocket stream is already running for the credential."""


@dataclass
class ConnectionState:
    url: str
    username: str
    active: bool = False
    subscribed_symbols: Set[str] = None


class TrueDataStreamManager:
    """Manages TrueData Realtime & Replay WebSocket connection lifecycles.

    TrueData V2.6 enforces a single login session per account for realtime data.
    This manager strictly guarantees at most one active connection exists per user credential.
    """

    def __init__(self, config=DEFAULT_CONFIG) -> None:
        self.config = config
        self._active_connections: Dict[str, ConnectionState] = {}
        self._lock = asyncio.Lock()

    async def connect_realtime(
        self,
        user_id: str,
        username: str,
        port: int | None = None,
    ) -> ConnectionState:
        """Initiate realtime WebSocket streaming session."""
        async with self._lock:
            existing = self._active_connections.get(user_id)
            if existing and existing.active:
                raise SingleStreamConflictError(
                    f"TrueData active streaming connection already exists for user '{user_id}'. "
                    "Only one active connection is permitted per account."
                )

            port = port or self.config.default_realtime_port
            ws_url = f"{self.config.realtime_push_url}:{port}"

            state = ConnectionState(
                url=ws_url,
                username=username,
                active=True,
                subscribed_symbols=set(),
            )
            self._active_connections[user_id] = state
            log.info("Established TrueData realtime WebSocket connection for %s at %s", user_id, ws_url)
            return state

    async def connect_replay(
        self,
        user_id: str,
        username: str,
        port: int | None = None,
    ) -> ConnectionState:
        """Initiate replay WebSocket streaming session."""
        async with self._lock:
            existing = self._active_connections.get(user_id)
            if existing and existing.active:
                raise SingleStreamConflictError(
                    f"TrueData active connection already exists for user '{user_id}'."
                )

            port = port or self.config.default_realtime_port
            ws_url = f"{self.config.replay_url}:{port}"

            state = ConnectionState(
                url=ws_url,
                username=username,
                active=True,
                subscribed_symbols=set(),
            )
            self._active_connections[user_id] = state
            log.info("Established TrueData replay WebSocket connection for %s at %s", user_id, ws_url)
            return state

    async def disconnect(self, user_id: str) -> None:
        """Disconnect and release active WebSocket stream."""
        async with self._lock:
            state = self._active_connections.pop(user_id, None)
            if state:
                state.active = False
                log.info("Disconnected TrueData stream for %s", user_id)


STREAM_MANAGER = TrueDataStreamManager()
