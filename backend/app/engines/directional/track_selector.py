"""
Sterling v4 — Per-(asset, profile) track router.

Picks which Track(s) the orchestrator dispatches a given (asset, profile) to.
Backed by a YAML config file so non-code routing changes are config-only.

Lookup order:
  1. Exact `(asset, profile)` match in the config dict
  2. Asset-default (`(asset, "_default_")`) match
  3. Global default — always `["trend_following"]`

Multiple tracks can be returned. The orchestrator evaluates each and keeps
the highest-score TrackSignal (per the Phase-4 risk budgeting rules: see
`engines/risk/track_budget.py` once that ships).

Config file (default location: `backend/config/tracks.yaml`):

    routes:
      BTC:
        scalping_5m:  [mean_reversion]
        scalping_15m: [mean_reversion]
        scalping_30m: [mean_reversion]
        _default_:    [trend_following]   # fallback for BTC profiles not listed
      ETH:
        _default_:    [trend_following]   # ETH never touches MR
      _default_:
        _default_:    [trend_following]   # global fallback

Programmatic override:
  set_routes({"SOL": {"scalping_15m": ["mean_reversion"]}}) from a startup
  hook or test fixture.

Falls back to a hard-coded BTC routing dict when the YAML file is absent so
the test suite and fresh checkouts work without a config file.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml as _yaml
    _HAVE_YAML = True
except Exception:
    _HAVE_YAML = False


# ── Hard-coded default routing ───────────────────────────────────────────
#
# Used when the YAML config is missing. ETH NEVER routes to mean_reversion
# (preserves the 1.27-Sharpe winner). BTC short-TF routes exclusively to MR.
# Altcoins fall through to trend_following until calibrated.
_DEFAULT_ROUTES: Dict[str, Dict[str, List[str]]] = {
    "BTC": {
        "scalping_5m":  ["mean_reversion"],
        "scalping_15m": ["mean_reversion"],
        "scalping_30m": ["mean_reversion"],
        "intraday_1h":  ["trend_following"],
        "intraday_4h":  ["trend_following"],
        "_default_":    ["trend_following"],
    },
    "ETH": {
        "_default_":    ["trend_following"],
    },
    "_default_": {
        "_default_":    ["trend_following"],
    },
}

# Hot, mutable copy of the routes dict. populate_from_config() refreshes it
# from disk; set_routes() supports programmatic overrides (tests).
_ROUTES: Dict[str, Dict[str, List[str]]] = {
    asset: dict(profiles) for asset, profiles in _DEFAULT_ROUTES.items()
}

_LOADED_FROM: Optional[str] = None


def _default_config_path() -> Path:
    here = Path(__file__).resolve().parents[3]   # backend/
    return here / "config" / "tracks.yaml"


def populate_from_config(path: Optional[Path] = None) -> bool:
    """Load routes from a YAML file. Returns True on success, False on miss.

    On any I/O or parse error the in-memory routes stay at whatever was loaded
    previously (or the hard-coded default on cold start). Errors log but
    never raise — routing must always succeed.
    """
    global _ROUTES, _LOADED_FROM
    if not _HAVE_YAML:
        return False
    p = path or _default_config_path()
    if not p.exists():
        return False
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = _yaml.safe_load(f) or {}
        routes = data.get("routes")
        if not isinstance(routes, dict):
            return False
        new: Dict[str, Dict[str, List[str]]] = {}
        for asset, profiles in routes.items():
            if not isinstance(profiles, dict):
                continue
            new[asset.upper()] = {
                k: (v if isinstance(v, list) else [v])
                for k, v in profiles.items()
            }
        # Ensure global fallback exists.
        new.setdefault("_default_", {"_default_": ["trend_following"]})
        _ROUTES = new
        _LOADED_FROM = str(p)
        return True
    except Exception:
        return False


def set_routes(routes: Dict[str, Dict[str, List[str]]]) -> None:
    """Programmatic override (test fixtures, startup hooks). Merges into the
    existing route table; existing asset entries are replaced wholesale."""
    global _ROUTES
    for asset, profiles in routes.items():
        _ROUTES[asset.upper()] = dict(profiles)


def reset_routes() -> None:
    """Reset to the hard-coded defaults. Useful for test isolation."""
    global _ROUTES, _LOADED_FROM
    _ROUTES = {asset: dict(profiles) for asset, profiles in _DEFAULT_ROUTES.items()}
    _LOADED_FROM = None


def select_tracks(asset: Optional[str], profile_key: Optional[str]) -> List[str]:
    """Resolve which tracks to evaluate for this (asset, profile).

    Asset is normalised: "BTCUSD" / "btc" / "BTC-USDT" → "BTC". An empty or
    unknown asset routes through "_default_". Profile fallback follows the
    same shape: missing or unknown profile_key uses the asset's `_default_`
    entry, then the global `_default_`.

    Always returns a non-empty list — final fallback is `["trend_following"]`.
    """
    a = _normalize_asset(asset)
    profiles = _ROUTES.get(a) or _ROUTES.get("_default_") or {}
    if profile_key and profile_key in profiles:
        return list(profiles[profile_key])
    if "_default_" in profiles:
        return list(profiles["_default_"])
    # Defensive global fallback.
    return list(_ROUTES.get("_default_", {}).get("_default_", ["trend_following"]))


def _normalize_asset(asset: Optional[str]) -> str:
    if not asset:
        return "_default_"
    s = asset.upper().replace("USDT", "").replace("USD", "").replace("-", "").replace("_", "")
    return s if s else "_default_"


def current_routes() -> Dict[str, Dict[str, List[str]]]:
    """Snapshot of the active route table (for /healthz, logging, debug UI)."""
    return {a: dict(p) for a, p in _ROUTES.items()}


def loaded_from() -> Optional[str]:
    """Path of the YAML loaded by `populate_from_config`, or None."""
    return _LOADED_FROM


# Auto-load at import time so the CLI / FastAPI startup gets the right routes
# without ceremony. STERLING_DISABLE_TRACK_CONFIG=1 disables auto-load
# (used by some test fixtures).
if os.environ.get("STERLING_DISABLE_TRACK_CONFIG") != "1":
    populate_from_config()
