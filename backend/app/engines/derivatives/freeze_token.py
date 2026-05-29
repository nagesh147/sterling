"""Freeze-token store for preview→execute idempotency.

The selector returns a token bound to the chosen candidate(s). The
execute endpoint requires the token to still be valid (within TTL) AND
to match the candidate the user clicked — protects against the user
clicking "EXECUTE" on the candidate they saw while the table refreshed
to a different ranking underneath.

Mounted on app.state.derivatives_freeze_cache as a singleton dict
{token: (DerivativesDecision, expires_at_ms)}. Stale entries are
GC'd lazily on each get/put.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Optional


FREEZE_TTL_MS = 30_000


@dataclass
class FreezeEntry:
    decision: object         # avoid circular import — typed as object
    expires_at_ms: int


class FreezeTokenStore:
    def __init__(self) -> None:
        self._store: dict[str, FreezeEntry] = {}

    def _gc(self, now_ms: int) -> None:
        expired = [k for k, e in self._store.items() if e.expires_at_ms <= now_ms]
        for k in expired:
            self._store.pop(k, None)

    def freeze(self, decision: object) -> tuple[str, int]:
        """Store `decision` and return (token, ttl_ms)."""
        now = int(time.time() * 1000)
        self._gc(now)
        token = uuid.uuid4().hex
        self._store[token] = FreezeEntry(
            decision=decision, expires_at_ms=now + FREEZE_TTL_MS,
        )
        return token, FREEZE_TTL_MS

    def get(self, token: str) -> Optional[object]:
        """Return the stored decision if the token is still valid; else None.
        Does NOT consume — execute endpoint pops separately to allow
        idempotent re-checks within TTL."""
        now = int(time.time() * 1000)
        entry = self._store.get(token)
        if entry is None:
            return None
        if entry.expires_at_ms <= now:
            self._store.pop(token, None)
            return None
        return entry.decision

    def consume(self, token: str) -> Optional[object]:
        """Validate AND remove the token. Used by /execute to prevent
        a single freeze_token firing more than once."""
        now = int(time.time() * 1000)
        entry = self._store.pop(token, None)
        if entry is None or entry.expires_at_ms <= now:
            return None
        return entry.decision

    def clear(self) -> None:
        self._store.clear()


# Module-level singleton — main.py sets app.state.derivatives_freeze_cache
# to point at this; the /execute endpoint reads it via the request app.
_GLOBAL_STORE = FreezeTokenStore()


def get_store() -> FreezeTokenStore:
    return _GLOBAL_STORE
