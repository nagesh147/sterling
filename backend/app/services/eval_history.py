"""
In-memory rolling evaluation history per underlying.
Stores last MAX_HISTORY run-once snapshots for signal trend analysis.
"""
from collections import deque
from typing import Dict, Deque, List, Any

MAX_HISTORY = 50

_history: Dict[str, Deque[dict]] = {}


def record(underlying: str, result_dict: dict) -> None:
    if underlying not in _history:
        _history[underlying] = deque(maxlen=MAX_HISTORY)
    _history[underlying].append(result_dict)


def get_history(underlying: str) -> List[dict]:
    return list(_history.get(underlying, []))


def clear(underlying: str | None = None) -> None:
    if underlying:
        _history.pop(underlying, None)
    else:
        _history.clear()
