"""Track fire-and-forget asyncio tasks so they are not GC'd mid-flight.

TrueCourse / CPython: a Task with no strong reference may be garbage-collected
before it finishes. Keep a module-level set of strong refs and discard on done.
"""
from __future__ import annotations

import asyncio
from typing import Coroutine, Optional, Set, TypeVar

T = TypeVar("T")

_background_tasks: Set[asyncio.Task] = set()


def spawn_background(
    coro: Coroutine[object, object, T],
    *,
    name: Optional[str] = None,
) -> asyncio.Task:
    """Create a task, retain a strong reference until it completes, return it."""
    task = asyncio.create_task(coro, name=name) if name else asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
