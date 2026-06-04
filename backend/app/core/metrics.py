"""
Metrics (Phase 2) — lightweight in-process counters & summaries.

No external exporter (Prometheus etc.) is required; this is a thread-safe
in-memory registry with a snapshot() that a future /metrics endpoint or
exporter can read. Deliberately tiny — counters and value-summaries only.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Dict, Iterator

_lock = threading.Lock()
_counters: Dict[str, float] = {}
_summaries: Dict[str, Dict[str, float]] = {}


def incr(name: str, n: float = 1.0) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0.0) + n


def observe(name: str, value: float) -> None:
    """Record a value into a named summary (count/sum/min/max/avg)."""
    with _lock:
        s = _summaries.get(name)
        if s is None:
            _summaries[name] = {"count": 1.0, "sum": value, "min": value, "max": value}
        else:
            s["count"] += 1.0
            s["sum"] += value
            s["min"] = min(s["min"], value)
            s["max"] = max(s["max"], value)


def timing(name: str, ms: float) -> None:
    """Convenience alias for observe() of a millisecond duration."""
    observe(name, ms)


@contextmanager
def timer(name: str) -> Iterator[None]:
    """Time a block and record its duration (ms) into the `name` summary."""
    start = time.perf_counter()
    try:
        yield
    finally:
        observe(name, (time.perf_counter() - start) * 1000.0)


def snapshot() -> Dict[str, Dict]:
    """Return a point-in-time copy: counters + summaries (with computed avg)."""
    with _lock:
        summaries = {}
        for name, s in _summaries.items():
            avg = s["sum"] / s["count"] if s["count"] else 0.0
            summaries[name] = {**s, "avg": avg}
        return {"counters": dict(_counters), "summaries": summaries}


def reset() -> None:
    with _lock:
        _counters.clear()
        _summaries.clear()
