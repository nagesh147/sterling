"""STRATEGY STUB — track routing removed in the strategy reset.

The prior router mapped (asset, profile) → active strategy tracks (e.g. "vcp",
"trend_following"). It was stripped (preserved in git history on the
`strategy-v2` branch). `select_tracks` now returns an empty list so no tracks
(and therefore no VCP live feeds) activate while the strategy is absent.

Implement the new track routing here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


def select_tracks(asset: Optional[str] = None, profile_key: Optional[str] = None) -> List[str]:
    """Neutral: no active tracks (no strategy loaded)."""
    return []


def populate_from_config(path: Optional[Path] = None) -> bool:
    return False


def set_routes(routes: Dict[str, Dict[str, List[str]]]) -> None:
    return None


def reset_routes() -> None:
    return None


def current_routes() -> Dict[str, Dict[str, List[str]]]:
    return {}


def loaded_from() -> Optional[str]:
    return None
