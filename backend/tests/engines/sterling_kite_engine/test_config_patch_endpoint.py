"""PATCH /kite/engine/config — a partial write must not revert untouched fields.

``POST /config`` replaces the whole model, so every UI write was a
read-modify-write off a cached copy of all 38 fields. If anything had moved
since that copy was fetched — a second browser tab, another surface in the same
tab — those fields were silently reverted, with no error and nothing on screen.
These are real-money settings, so the guarantee that a write cannot touch what
it does not name is worth pinning down.
"""
import pytest

from app.api.v1.endpoints.kite_engine import patch_config
from app.engines.sterling_kite_engine.schemas import EngineConfigModel
from app.services.kite_engine import state
from fastapi import HTTPException


class _User:
    def __init__(self, uid):
        self.user_id = uid


@pytest.mark.asyncio
async def test_patch_changes_only_the_named_field():
    uid = "patch_one"
    state.reset(uid)
    state.set_config(uid, EngineConfigModel(
        stop_mode="broker", max_lots=7, risk_pct=2.5, auto_execute=True))

    got = await patch_config({"stop_mode": "monitor"}, user=_User(uid))

    assert got.stop_mode == "monitor"
    # Everything else survives untouched.
    assert got.max_lots == 7
    assert got.risk_pct == 2.5
    assert got.auto_execute is True


@pytest.mark.asyncio
async def test_patch_cannot_revert_a_concurrent_change():
    """The exact failure the whole-object POST allowed.

    Two surfaces hold the same snapshot. One changes the daily-loss breaker; the
    other then changes an unrelated toggle. With a whole-object write the second
    surface re-asserts its stale snapshot and the breaker goes back to off.
    """
    uid = "patch_concurrent"
    state.reset(uid)
    state.set_config(uid, EngineConfigModel())

    # Surface A arms the daily-loss breaker.
    await patch_config({"max_daily_loss_pct": 2.0}, user=_User(uid))
    # Surface B, still holding the pre-A snapshot, changes something unrelated.
    got = await patch_config({"max_lots": 3}, user=_User(uid))

    assert got.max_lots == 3
    assert got.max_daily_loss_pct == 2.0, "surface B silently disarmed the loss breaker"


@pytest.mark.asyncio
async def test_patch_rejects_an_unknown_field():
    """A typo must fail loudly, not be dropped on the floor."""
    uid = "patch_unknown"
    state.reset(uid)
    state.set_config(uid, EngineConfigModel())

    with pytest.raises(HTTPException) as err:
        await patch_config({"stop_moed": "broker"}, user=_User(uid))

    assert err.value.status_code == 422
    assert "stop_moed" in str(err.value.detail)


@pytest.mark.asyncio
async def test_patch_still_runs_field_validators():
    """Merging must go back through the model, not straight into storage."""
    uid = "patch_validated"
    state.reset(uid)
    state.set_config(uid, EngineConfigModel())

    # The stock-expiry validator discards whatever it is sent and returns monthly.
    got = await patch_config({"scan_expiries_stocks": ["weekly"]}, user=_User(uid))

    assert got.scan_expiries_stocks == ["monthly"]


@pytest.mark.asyncio
async def test_empty_patch_is_a_no_op():
    uid = "patch_empty"
    state.reset(uid)
    state.set_config(uid, EngineConfigModel(max_lots=5))

    got = await patch_config({}, user=_User(uid))

    assert got.max_lots == 5
