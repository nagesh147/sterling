"""BROKER REGISTRY — metadata + class resolution + parity with the factory."""
import importlib

import pytest

from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges import registry
from app.services.exchanges.adapter_factory import create_account_adapter
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter


def test_registry_lists_all_supported_brokers():
    reg = registry.load_registry()
    assert set(reg["brokers"]).issuperset({"delta_india", "zerodha", "binance", "deribit", "okx"})


def test_every_adapter_path_imports():
    reg = registry.load_registry()
    for name, meta in reg["brokers"].items():
        module_path, cls_name = meta["adapter"].split(":")
        mod = importlib.import_module(module_path)
        assert hasattr(mod, cls_name), f"{name}: {cls_name} missing in {module_path}"


def test_resolve_adapter_class_returns_delta():
    assert registry.resolve_adapter_class("delta_india") is DeltaIndiaAdapter


def test_broker_meta_exposes_markets():
    meta = registry.broker_meta("delta_india")
    assert "crypto" in meta["markets"]


def test_load_account_adapter_parity_with_factory():
    cfg = ExchangeConfig(id="r", name="delta_india", api_key="k", api_secret="s", is_paper=True)
    via_registry = registry.load_account_adapter(cfg)
    via_factory = create_account_adapter(cfg)
    assert type(via_registry) is type(via_factory) is DeltaIndiaAdapter


def test_unknown_broker_raises():
    cfg = ExchangeConfig(id="r", name="nope", api_key="", api_secret="", is_paper=True)
    with pytest.raises(ValueError):
        registry.load_account_adapter(cfg)
