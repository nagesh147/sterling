"""
Sterling v4 — SSE keepalive helper tests.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, List

import pytest

from app.services.sse_keepalive import (
    SSE_KEEPALIVE_LINE, is_keepalive, with_keepalive,
)


# ─── Source generators (test fixtures) ────────────────────────────────────


async def _instant_source(n: int = 3) -> AsyncIterator[str]:
    for i in range(n):
        yield f"data: {{\"i\": {i}}}\n\n"


async def _slow_source(n: int = 3, delay_s: float = 0.05) -> AsyncIterator[str]:
    for i in range(n):
        await asyncio.sleep(delay_s)
        yield f"data: {{\"i\": {i}}}\n\n"


async def _never_source() -> AsyncIterator[str]:
    while True:
        await asyncio.sleep(60)
        yield "should_not_appear"


# ─── Tests ────────────────────────────────────────────────────────────────


class TestSSEKeepalive:

    @pytest.mark.asyncio
    async def test_keepalive_format_is_valid_sse_comment(self) -> None:
        assert SSE_KEEPALIVE_LINE.startswith(":")
        assert SSE_KEEPALIVE_LINE.endswith("\n\n")
        assert is_keepalive(SSE_KEEPALIVE_LINE)
        assert not is_keepalive("data: {}\n\n")

    @pytest.mark.asyncio
    async def test_passes_through_fast_source(self) -> None:
        # When source emits faster than the keepalive cadence, no keepalives.
        out: List[str] = []
        async for frame in with_keepalive(_instant_source(3), interval_s=1.0):
            out.append(frame)
        assert len(out) == 3
        assert all("data:" in f for f in out)
        assert not any(is_keepalive(f) for f in out)

    @pytest.mark.asyncio
    async def test_emits_keepalive_when_source_is_slow(self) -> None:
        # Source emits 3 frames at 0.2s; keepalive every 0.05s ⇒ many keepalives.
        out: List[str] = []
        async for frame in with_keepalive(_slow_source(3, 0.2), interval_s=0.05):
            out.append(frame)
            if len(out) > 50:
                break
        keepalive_count = sum(1 for f in out if is_keepalive(f))
        data_count = sum(1 for f in out if not is_keepalive(f))
        assert data_count == 3
        assert keepalive_count >= 6      # 3 frames * 0.2s / 0.05s ≈ 12 keepalives

    @pytest.mark.asyncio
    async def test_keepalive_continues_on_silent_source(self) -> None:
        # Source never emits — we should see keepalives until cancellation.
        kept: List[str] = []

        async def _consumer():
            async for frame in with_keepalive(_never_source(), interval_s=0.05):
                kept.append(frame)
                if len(kept) >= 3:
                    return

        await asyncio.wait_for(_consumer(), timeout=2.0)
        assert len(kept) == 3
        assert all(is_keepalive(f) for f in kept)

    @pytest.mark.asyncio
    async def test_termination_propagates_when_source_ends(self) -> None:
        out: List[str] = []
        async for frame in with_keepalive(_instant_source(2), interval_s=0.01):
            out.append(frame)
        assert sum(1 for f in out if not is_keepalive(f)) == 2

    @pytest.mark.asyncio
    async def test_no_orphaned_tasks_on_consumer_cancel(self) -> None:
        # Sanity: when the consumer breaks early the helper does not leave a
        # pending task that warns "Task was destroyed but it is pending".
        loop = asyncio.get_event_loop()
        prior_tasks = set(asyncio.all_tasks(loop))

        async for _ in with_keepalive(_never_source(), interval_s=0.01):
            break       # immediate cancellation

        # Allow one event loop tick for any pending cancellations to resolve
        await asyncio.sleep(0.02)
        new_tasks = set(asyncio.all_tasks(loop)) - prior_tasks
        # Filter out the *current* test task itself
        leaked = [t for t in new_tasks if not t.done() and t is not asyncio.current_task()]
        assert leaked == [], f"Leaked tasks: {leaked}"
