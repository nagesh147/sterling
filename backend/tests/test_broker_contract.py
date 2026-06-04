"""
BROKER CONTRACT — every adapter that supports order placement must expose the
TradingExchangeAdapter surface, so a new broker that forgets cancel_order fails
CI instead of production.
"""
import inspect

from app.services.exchanges.trading_base import TradingExchangeAdapter
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter

REQUIRED_ABSTRACT = {"place_order", "place_order_option", "cancel_order", "get_product_id"}


def test_trading_base_declares_required_order_methods():
    assert REQUIRED_ABSTRACT.issubset(TradingExchangeAdapter.__abstractmethods__)


def test_delta_is_a_trading_adapter():
    assert issubclass(DeltaIndiaAdapter, TradingExchangeAdapter)


def test_delta_can_instantiate_with_contract_satisfied():
    # All abstract methods implemented → construction must succeed offline.
    adapter = DeltaIndiaAdapter(api_key="k", api_secret="s", is_paper=True)
    for name in REQUIRED_ABSTRACT:
        assert inspect.iscoroutinefunction(getattr(adapter, name))
