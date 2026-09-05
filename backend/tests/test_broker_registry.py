"""BROKER REGISTRY — metadata + class resolution + parity with the factory."""
import importlib

import pytest

from app.schemas.exchange_config import ExchangeConfig
from app.services.exchanges import registry
from app.services.exchanges.adapter_factory import create_account_adapter
from app.services.exchanges.adapters.zerodha import ZerodhaAdapter


def test_registry_lists_all_supported_brokers():
    reg = registry.load_registry()
    assert set(reg["brokers"]).issuperset({"zerodha"})


def test_every_adapter_path_imports():
    reg = registry.load_registry()
    for name, meta in reg["brokers"].items():
        module_path, cls_name = meta["adapter"].split(":")
        mod = importlib.import_module(module_path)
        assert hasattr(mod, cls_name), f"{name}: {cls_name} missing in {module_path}"


def test_resolve_adapter_class_returns_zerodha():
    assert registry.resolve_adapter_class("zerodha") is ZerodhaAdapter


def test_broker_meta_exposes_markets():
    meta = registry.broker_meta("zerodha")
    assert "equities" in meta["markets"]


def test_load_account_adapter_parity_with_factory():
    cfg = ExchangeConfig(id="r", name="zerodha", api_key="k", api_secret="s", is_paper=True)
    via_registry = registry.load_account_adapter(cfg)
    via_factory = create_account_adapter(cfg)
    assert type(via_registry) is type(via_factory) is ZerodhaAdapter


def test_unknown_broker_raises():
    cfg = ExchangeConfig(id="r", name="nope", api_key="", api_secret="", is_paper=True)
    with pytest.raises(ValueError):
        registry.load_account_adapter(cfg)
