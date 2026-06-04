"""DOMAIN — canonical contracts surface (additive; no I/O)."""
from app.domain.models import Signal, TradeEvent
from app.domain.interfaces import BrokerProtocol
from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter


def test_signal_constructs_market_agnostic():
    sig = Signal(
        underlying="BTC", direction="long", instrument_type="futures",
        score=82.5, strength="STRONG", stop_loss=49000.0, take_profit=53000.0,
        source="sterling_engine",
    )
    assert sig.underlying == "BTC"
    assert sig.direction == "long"
    assert sig.score == 82.5


def test_trade_event_has_type_and_timestamp():
    ev = TradeEvent(event_type="SignalRaised", payload={"underlying": "BTC"})
    assert ev.event_type == "SignalRaised"
    assert ev.timestamp_ms > 0
    assert ev.payload["underlying"] == "BTC"


def test_canonical_schema_reexports_are_importable():
    from app.domain.models import Candle, InstrumentMeta, AccountPosition  # noqa: F401


def test_delta_adapter_satisfies_broker_protocol():
    adapter = DeltaIndiaAdapter(api_key="k", api_secret="s", is_paper=True)
    assert isinstance(adapter, BrokerProtocol)
