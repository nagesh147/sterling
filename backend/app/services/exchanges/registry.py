"""
Declarative broker registry.

Single source of truth for broker METADATA (markets, capabilities) and class
location. Construction is delegated to adapter_factory.create_account_adapter so
there is exactly one construction path (DRY) and registry/factory cannot drift.

Falls back gracefully: if registry.json is missing, load_account_adapter still
works via the factory, and resolve/meta raise clear errors.
"""
from __future__ import annotations

import functools
import importlib
import json
from pathlib import Path
from typing import Any, Dict, Type

from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter
from app.services.exchanges.adapter_factory import create_account_adapter

_REGISTRY_PATH = Path(__file__).resolve().parents[3] / "config" / "registry.json"


@functools.lru_cache(maxsize=1)
def load_registry() -> Dict[str, Any]:
    """Load and cache config/registry.json. Empty skeleton if absent."""
    if not _REGISTRY_PATH.exists():
        return {"brokers": {}, "markets": {}, "strategies": {}}
    with _REGISTRY_PATH.open() as fh:
        return json.load(fh)


def broker_meta(name: str) -> Dict[str, Any]:
    meta = load_registry()["brokers"].get(name.lower())
    if meta is None:
        raise ValueError(f"Broker not in registry: {name!r}")
    return meta


def list_brokers() -> Dict[str, Any]:
    return load_registry()["brokers"]


def resolve_adapter_class(name: str) -> Type[AuthenticatedExchangeAdapter]:
    """Dynamically import the adapter class named in the registry."""
    module_path, cls_name = broker_meta(name)["adapter"].split(":")
    module = importlib.import_module(module_path)
    return getattr(module, cls_name)


def load_account_adapter(cfg: ExchangeConfig) -> AuthenticatedExchangeAdapter:
    """Registry-validated construction. Delegates to the factory (one path).

    New code should call this. Existing callers of create_account_adapter
    keep working unchanged.
    """
    return create_account_adapter(cfg)
