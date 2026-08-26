import pytest

from app.engines.adaptive_edge.end_to_end_gate import (
    ChainEvent,
    ChainStage,
    EndToEndGateError,
    validate_causal_chain,
    validate_no_execution_without_authorization,
)


def chain():
    events = []
    parent = None
    for index, stage in enumerate(ChainStage):
        event_id = f"{stage.value}-{index}"
        events.append(ChainEvent(stage, event_id, index * 10, parent))
        parent = event_id
    return tuple(events)


def test_complete_chain_is_valid():
    events = chain()
    validate_causal_chain(events)
    validate_no_execution_without_authorization(events)


def test_incomplete_chain_is_rejected():
    with pytest.raises(EndToEndGateError):
        validate_causal_chain(chain()[:-1])


def test_wrong_stage_order_is_rejected():
    events = list(chain())
    events[7], events[8] = events[8], events[7]
    with pytest.raises(EndToEndGateError):
        validate_causal_chain(tuple(events))


def test_broken_causal_parent_is_rejected():
    events = list(chain())
    events[8] = ChainEvent(events[8].stage, events[8].event_id, events[8].occurred_at_ms, "wrong-parent")
    with pytest.raises(EndToEndGateError):
        validate_causal_chain(tuple(events))


def test_backward_causal_time_is_rejected():
    events = list(chain())
    events[9] = ChainEvent(events[9].stage, events[9].event_id, 1, events[8].event_id)
    with pytest.raises(EndToEndGateError):
        validate_causal_chain(tuple(events))
