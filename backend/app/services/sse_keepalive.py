"""
Sterling v4 — SSE keepalive helper

Wraps any async generator that yields SSE-formatted strings (`data: ...\\n\\n`)
with periodic `: keepalive\\n\\n` comment lines. SSE comments are lines that
start with a colon — they're parsed as no-ops by EventSource clients but keep
the TCP connection alive across HTTP load balancers that close idle sockets.

Why a separate helper rather than inlining? Two reasons:
  1. The same logic applies to every SSE endpoint we'll add — DRY.
  2. Keepalive cadence is independent of the data emission cadence. If the
     producer takes 60s to compute the next data frame, we still want a
     comment every 15s so the proxy doesn't time us out.

Pure asyncio. No external dependencies.
"""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator, AsyncIterator


SSE_KEEPALIVE_LINE = ": keepalive\n\n"


async def with_keepalive(
    source: AsyncIterator[str],
    interval_s: float = 15.0,
) -> AsyncGenerator[str, None]:
    """
    Iterate `source` while emitting `: keepalive\\n\\n` every `interval_s`
    seconds whenever the source has not produced a frame in that window.

    Cancellation-safe: when the consumer disconnects, the awaiter on
    `source.__anext__()` raises CancelledError and propagates outward.
    """
    pending: asyncio.Task[str] | None = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(source.__anext__())
            try:
                frame = await asyncio.wait_for(asyncio.shield(pending), timeout=interval_s)
            except asyncio.TimeoutError:
                yield SSE_KEEPALIVE_LINE
                continue
            except StopAsyncIteration:
                return
            pending = None
            yield frame
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, StopAsyncIteration, Exception):
                pass


def is_keepalive(line: str) -> bool:
    """True iff `line` is a valid SSE keepalive comment frame."""
    return line.lstrip().startswith(":")
