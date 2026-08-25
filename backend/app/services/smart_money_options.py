"""Runtime service for the Smart Money Multi-X Options strategy."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.smart_money_options import (
    STRATEGY_ID,
    STRATEGY_NAME,
    CONTRACT_VERSION,
    SmartMoneyOptionsConfig,
)

log = get_logger(__name__)

_CONFIG_KEY = "smart_money_options_config"


def get_config() -> SmartMoneyOptionsConfig:
    """Load persisted config, falling back to safe disabled defaults."""
    default = SmartMoneyOptionsConfig(enabled=False)
    try:
        from app.services import db
        raw = db.get_config(_CONFIG_KEY)
    except Exception:
        return default
    if not raw:
        return default
    try:
        stored = json.loads(raw) if isinstance(raw, str) else raw
        known = SmartMoneyOptionsConfig.field_names()
        merged = {**default.as_dict(), **{k: v for k, v in dict(stored).items() if k in known}}
        return SmartMoneyOptionsConfig(**merged).validate()
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        log.error(
            "Stored %s config is invalid (%s); falling back to disabled defaults",
            STRATEGY_ID, exc,
        )
        return default


def set_config(values: dict[str, Any]) -> SmartMoneyOptionsConfig:
    """Persist a config change."""
    current = get_config().as_dict()
    unknown = sorted(set(values) - set(current))
    if unknown:
        raise ValueError(f"Unknown {STRATEGY_ID} config fields: {', '.join(unknown)}")
    current.update(values)
    cfg = SmartMoneyOptionsConfig(**current).validate()
    from app.services import db
    db.set_config(_CONFIG_KEY, json.dumps(cfg.as_dict(), separators=(",", ":")))
    return cfg


def descriptor() -> dict[str, Any]:
    """Identity and configuration schema published to the UI."""
    cfg = get_config()
    return {
        "strategy": {
            "id": STRATEGY_ID,
            "name": STRATEGY_NAME,
            "contract_version": CONTRACT_VERSION,
            "enabled": cfg.enabled,
            "live_ready": True,
        },
        "config": cfg.as_dict(),
        "defaults": SmartMoneyOptionsConfig(enabled=False).as_dict(),
        "vocabularies": SmartMoneyOptionsConfig.VOCABULARIES,
    }


async def snapshot() -> dict[str, Any]:
    """Live snapshot of the Smart Money Multi-X Options engine."""
    from app.services.smart_money_options_runner import get_latest_signals, get_active_positions
    cfg = get_config()
    signals = await get_latest_signals()
    positions = await get_active_positions()

    return {
        "strategy_id": STRATEGY_ID,
        "strategy_name": STRATEGY_NAME,
        "enabled": cfg.enabled,
        "execution_mode": cfg.execution_mode,
        "universe": cfg.universe,
        "signals": [s.as_dict() for s in signals],
        "positions": positions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
