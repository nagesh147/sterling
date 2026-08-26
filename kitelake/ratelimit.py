"""Shared rate limiting for the historical endpoint's 3 requests/second ceiling.

**Why pacing and not a token bucket.** The obvious implementation is a token bucket with
capacity 1. It is wrong here. After any idle period the bucket holds a full token, so a
burst of work gets that token *plus* everything it earns during the next second — at
rate 2.5 that is 3.5 requests inside one second, over Kite's limit of 3. Measured: 20
requests at "rate 2.5" completed in 7.62 s, i.e. 2.62 rq/s observed, precisely because of
that free head-start token.

:class:`PacedRateLimiter` instead guarantees a **minimum spacing** of ``1/rate`` between
consecutive grants. Grants land at ``t0, t0+0.4, t0+0.8, …``, so no one-second window can
ever contain more than 3 at the default 2.5 rq/s, idle or not. It also cannot accumulate
credit, which is the property we actually want against a per-second server counter.

Fairness comes from :class:`asyncio.Lock`, which queues waiters FIFO — without it one
coroutine can monopolise slots and starve another instrument's chunks for minutes.

:class:`AdaptiveLimiter` layers AIMD on top: halve on 429, creep back on sustained
success, never above the configured ceiling.
"""

from __future__ import annotations

import asyncio

__all__ = ["PacedRateLimiter", "AdaptiveLimiter"]


class PacedRateLimiter:
    """Grants at most one acquisition every ``1/rate`` seconds, FIFO, monotonic clock."""

    def __init__(self, rate: float) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = float(rate)
        self._next_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def interval(self) -> float:
        return 1.0 / self._rate

    def set_rate(self, rate: float) -> None:
        """Change the pace. Already-scheduled slots keep their times."""
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rate = float(rate)

    async def acquire(self) -> None:
        """Wait for this caller's slot. Slot assignment is serialised; the wait is not."""
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()  # monotonic: an NTP step cannot stall or burst the run
            slot = now if self._next_at is None else max(now, self._next_at)
            self._next_at = slot + self.interval
            delay = slot - now
        # Sleep outside the lock so the next caller can claim its slot immediately;
        # holding it would serialise the *waits* and halve throughput.
        if delay > 0:
            await asyncio.sleep(delay)


class AdaptiveLimiter:
    """Paced limiter that backs off on 429 and recovers (additive-increase/multiplicative-decrease).

    Never exceeds ``hard_max`` nor the initially requested rate — recovery restores the
    configured speed, it does not go hunting for a faster one.
    """

    #: Consecutive successes before nudging the rate back up.
    REWARD_AFTER = 40
    #: Floor. Below this a large download would never finish; better to surface the
    #: problem than to crawl silently.
    MIN_RATE = 0.5

    def __init__(self, rate: float, *, hard_max: float | None = None) -> None:
        from .config import HIST_RATE_LIMIT_HARD

        ceiling = HIST_RATE_LIMIT_HARD if hard_max is None else float(hard_max)
        self._ceiling = min(float(rate), ceiling)
        self._limiter = PacedRateLimiter(self._ceiling)
        self._successes = 0
        self.penalties = 0

    @property
    def current_rate(self) -> float:
        return self._limiter.rate

    @property
    def ceiling(self) -> float:
        return self._ceiling

    async def acquire(self) -> None:
        await self._limiter.acquire()

    def penalize(self) -> float:
        """Call on a 429. Halves the rate, down to :attr:`MIN_RATE`."""
        self.penalties += 1
        self._successes = 0
        self._limiter.set_rate(max(self.MIN_RATE, self._limiter.rate / 2.0))
        return self._limiter.rate

    def reward(self) -> float:
        """Call on each success. Creeps the rate back toward the ceiling."""
        if self._limiter.rate >= self._ceiling:
            self._successes = 0
            return self._limiter.rate
        self._successes += 1
        if self._successes >= self.REWARD_AFTER:
            self._successes = 0
            self._limiter.set_rate(min(self._ceiling, self._limiter.rate + 0.25))
        return self._limiter.rate
