import pytest

from app.engines.adaptive_edge.execution_dispatch import OrderIntent, dispatch_order
from app.engines.adaptive_edge.execution_gate import ExecutionBlockedError


class RecordingDispatcher:
    def __init__(self) -> None:
        self.intents = []

    def dispatch(self, intent: OrderIntent) -> object:
        self.intents.append(intent)
        return {"accepted": True, "intent_id": intent.intent_id}


def test_unresolved_strategy_cannot_reach_dispatcher():
    dispatcher = RecordingDispatcher()
    intent = OrderIntent("i1", "NIFTY-CE", "BUY", 50)

    with pytest.raises(ExecutionBlockedError):
        dispatch_order(intent, dispatcher)

    assert dispatcher.intents == []


def test_dispatcher_is_called_only_after_explicitly_satisfied_gate():
    dispatcher = RecordingDispatcher()
    intent = OrderIntent("i2", "NIFTY-CE", "BUY", 50)

    result = dispatch_order(intent, dispatcher, formula_ids=("F-004",))

    assert result == {"accepted": True, "intent_id": "i2"}
    assert dispatcher.intents == [intent]
