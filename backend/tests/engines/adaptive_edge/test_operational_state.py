import pytest

from app.engines.adaptive_edge.operational_state import (
    OperationalState,
    OperationalStateError,
    OperationalTradingState,
    TradingPermissions,
)


def permissions(**overrides):
    values = dict(
        allow_signal_generation=True,
        allow_new_entries=True,
        allow_existing_position_management=True,
        allow_exit_submission=True,
    )
    values.update(overrides)
    return TradingPermissions(**values)


def state(state=OperationalState.NORMAL, **permission_overrides):
    return OperationalTradingState(
        state_id="state-1",
        operational_state=state,
        permissions=permissions(**permission_overrides),
        observation_id="obs-1",
        policy_id="policy-1",
        policy_version="1",
    )


def test_normal_state_can_allow_all_permissions():
    assert state().permissions.allow_new_entries is True


def test_block_new_cannot_allow_new_entries():
    with pytest.raises(OperationalStateError):
        state(OperationalState.BLOCK_NEW)


def test_halted_cannot_generate_signals():
    with pytest.raises(OperationalStateError):
        state(OperationalState.HALTED, allow_signal_generation=True, allow_new_entries=False)


def test_halted_can_retain_exit_submission():
    value = state(
        OperationalState.HALTED,
        allow_signal_generation=False,
        allow_new_entries=False,
        allow_exit_submission=True,
    )
    assert value.permissions.allow_exit_submission is True
