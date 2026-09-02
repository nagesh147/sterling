"""
Tests for Market Replay Simulation endpoints and service.
"""
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from app.services.simulation import simulation_runner, SimState, SimConfig, SimStatus


@pytest.fixture(autouse=True)
async def reset_simulation():
    """Ensure simulation runner is stopped before/after each test."""
    await simulation_runner.stop()
    yield
    await simulation_runner.stop()


def test_simulation_initial_status():
    status = simulation_runner.status
    assert status.state == SimState.IDLE
    assert status.bars_played == 0
    assert status.stats.signals_fired == 0


@pytest.mark.asyncio
async def test_start_and_stop_simulation():
    config = SimConfig(
        date="2026-08-28",
        start_time="09:15:00",
        end_time="15:30:00",
        speed=10.0,
        resolution="5m",
        instruments=["NIFTY"],
    )
    status = await simulation_runner.start(config)
    assert status.state in (SimState.RUNNING, SimState.LOADING)
    assert status.config is not None
    assert status.config.date == "2026-08-28"

    # Stop simulation
    stop_status = await simulation_runner.stop()
    assert stop_status.state == SimState.IDLE


@pytest.mark.asyncio
async def test_pause_and_resume():
    config = SimConfig(
        date="2026-08-28",
        start_time="09:15:00",
        end_time="15:30:00",
        speed=10.0,
        instruments=["NIFTY"],
    )
    await simulation_runner.start(config)
    # Manually transition to running if still loading in test
    simulation_runner._state = SimState.RUNNING

    pause_status = await simulation_runner.pause()
    assert pause_status.state == SimState.PAUSED

    resume_status = await simulation_runner.resume()
    assert resume_status.state == SimState.RUNNING

    await simulation_runner.stop()


def test_set_speed():
    status = simulation_runner.set_speed(15.0)
    assert simulation_runner._speed == 15.0

    # Bounds check
    simulation_runner.set_speed(6000.0)
    assert simulation_runner._speed == 5000.0

    simulation_runner.set_speed(0.1)
    assert simulation_runner._speed == 0.5


@pytest.mark.asyncio
async def test_auto_restart_on_duplicate_start():
    config1 = SimConfig(date="2026-08-28", speed=5.0)
    await simulation_runner.start(config1)
    assert simulation_runner.status.config.date == "2026-08-28"

    config2 = SimConfig(date="2026-08-29", speed=10.0)
    status = await simulation_runner.start(config2)
    assert status.config.date == "2026-08-29"

    await simulation_runner.stop()


@pytest.mark.asyncio
async def test_step_and_seek_controls():
    config = SimConfig(date="2026-08-28", start_time="09:15:00", end_time="15:30:00", speed=10.0, instruments=["NIFTY"])
    await simulation_runner.start(config)
    simulation_runner._state = SimState.RUNNING
    simulation_runner._start_epoch = 1787889000
    simulation_runner._end_epoch = 1787911500
    simulation_runner._current_sim_epoch = 1787889000.0

    status = simulation_runner.step_bars(5)
    assert simulation_runner._seek_requested_epoch == 1787889000.0 + (5 * 300)

    jump_status = simulation_runner.jump_start()
    assert simulation_runner._seek_requested_epoch == 1787889000.0

    await simulation_runner.stop()
