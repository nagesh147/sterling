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


@pytest.mark.asyncio
async def test_simulation_default_instruments_and_warmup_at_915():
    import asyncio
    config = SimConfig(
        date="2026-09-03",
        start_time="09:15:00",
        end_time="09:20:00",
        speed=10.0,
        strategy="all",
        instruments=[],
        resolution="5m",
    )
    await simulation_runner.start(config)
    await asyncio.sleep(1.5)

    # Verify high-liquidity stock symbols are present in simulation
    assert "KOTAKBANK" in simulation_runner._bar_history
    assert "ADANIPORTS" in simulation_runner._bar_history
    assert "AXISBANK" in simulation_runner._bar_history
    assert "BAJFINANCE" in simulation_runner._bar_history

    # Verify warmup bars are pre-seeded at 09:15:00
    assert len(simulation_runner._bar_history["KOTAKBANK"]) >= 20

    # Verify kite signal responses can format rows for these stocks
    res = simulation_runner.get_kite_signals_response()
    assert "rows" in res
    assert isinstance(res["rows"], list)

    await simulation_runner.stop()


def test_evaluate_bar_supertrend_cooldown_and_no_flood():
    from datetime import datetime, timezone
    simulation_runner._bar_history = {}
    simulation_runner._last_fired = {}
    simulation_runner._active_until_bar = {}
    simulation_runner._config = SimConfig(date="2026-08-28", strategy="supertrend", strategies=["supertrend"])
    simulation_runner._candles = []
    simulation_runner._bars_played = 0
    simulation_runner._stats.signals_fired = 0
    simulation_runner._stats.events = []
    simulation_runner._stats.trades = []

    # Feed 25 steadily rising bars
    base_time = datetime(2026, 8, 28, 9, 15, tzinfo=timezone.utc)
    for i in range(25):
        price = 24000.0 + (i * 20.0)
        bar = {
            "symbol": "NIFTY",
            "open": price - 5.0,
            "high": price + 15.0,
            "low": price - 10.0,
            "close": price + 10.0,
            "volume": 50000,
        }
        dt = base_time
        simulation_runner._evaluate_bar(bar, dt)

    st_events = [ev for ev in simulation_runner._stats.events if ev.strategy == "supertrend"]
    # Should only fire transition/pullback signals with cooldown, not a signal on every single bar (25)
    assert len(st_events) <= 3


def test_evaluate_bar_supertrend_requires_warmup_and_no_early_spike():
    """Verify that SuperTrend requires >= 22 bars for Triple Alignment and does NOT fire at bar 6 (09:40:00)."""
    from datetime import datetime, timezone
    simulation_runner._bar_history = {}
    simulation_runner._last_fired = {}
    simulation_runner._active_until_bar = {}
    simulation_runner._config = SimConfig(date="2026-08-28", strategy="supertrend", strategies=["supertrend"])
    simulation_runner._candles = []
    simulation_runner._bars_played = 0
    simulation_runner._stats.signals_fired = 0
    simulation_runner._stats.events = []
    simulation_runner._stats.trades = []

    # Feed 6 bars (up to 09:40) across 5 instruments
    base_time = datetime(2026, 8, 28, 9, 15, tzinfo=timezone.utc)
    for sym in ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "RELIANCE"]:
        for i in range(6):
            bar = {
                "symbol": sym,
                "open": 100.0 + i,
                "high": 105.0 + i,
                "low": 95.0 + i,
                "close": 102.0 + i,
                "volume": 10000,
            }
            simulation_runner._evaluate_bar(bar, base_time)

    # In previous buggy code, bar 6 (09:40) fired 5 simultaneous trades across all 5 instruments.
    # Canonical logic requires >= 22 bars so 0 signals should fire.
    st_events = [ev for ev in simulation_runner._stats.events if ev.strategy == "supertrend"]
    assert len(st_events) == 0


def test_evaluate_bar_atm_imbalance_single_trade_window():
    """Verify ATM Premium Imbalance only triggers during 09:15-09:30 and takes at most 1 trade per day."""
    from datetime import datetime, timezone, timedelta
    simulation_runner._bar_history = {}
    simulation_runner._last_fired = {}
    simulation_runner._active_until_bar = {}
    simulation_runner._config = SimConfig(date="2026-08-28", strategy="atm_imbalance", strategies=["atm_imbalance"])
    simulation_runner._stats.signals_fired = 0
    simulation_runner._stats.events = []
    simulation_runner._stats.trades = []

    # Bar 1 at 09:15:00
    t1 = datetime(2026, 8, 28, 9, 15, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    bar1 = {"symbol": "NIFTY", "open": 24000, "high": 24050, "low": 23980, "close": 24020, "volume": 50000}
    simulation_runner._evaluate_bar(bar1, t1)

    # Bar 2 at 09:20:00 (inside open window) -> fires 1st trade
    t2 = datetime(2026, 8, 28, 9, 20, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    bar2 = {"symbol": "NIFTY", "open": 24020, "high": 24060, "low": 24010, "close": 24040, "volume": 60000}
    simulation_runner._evaluate_bar(bar2, t2)

    atm_events = [ev for ev in simulation_runner._stats.events if ev.strategy == "atm_imbalance"]
    assert len(atm_events) == 1

    # Bar 3 at 09:25:00 (still in window, but already traded today -> should NOT fire another)
    t3 = datetime(2026, 8, 28, 9, 25, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    bar3 = {"symbol": "NIFTY", "open": 24040, "high": 24070, "low": 24030, "close": 24060, "volume": 40000}
    simulation_runner._evaluate_bar(bar3, t3)

    atm_events_after = [ev for ev in simulation_runner._stats.events if ev.strategy == "atm_imbalance"]
    assert len(atm_events_after) == 1


def test_evaluate_bar_nifty_orb_window_and_constraints():
    """Verify Nifty ORB only trades between 09:30-12:00 with 15m range formed, max 2 trades/day."""
    from datetime import datetime, timezone, timedelta
    simulation_runner._bar_history = {}
    simulation_runner._last_fired = {}
    simulation_runner._active_until_bar = {}
    simulation_runner._config = SimConfig(date="2026-08-28", strategy="nifty_orb", strategies=["nifty_orb"])
    simulation_runner._stats.signals_fired = 0
    simulation_runner._stats.events = []
    simulation_runner._stats.trades = []

    tz_ist = timezone(timedelta(hours=5, minutes=30))

    # Feed 3 opening range bars (09:15, 09:20, 09:25) -> High = 24100, Low = 24000
    for idx, minute in enumerate([15, 20, 25]):
        t = datetime(2026, 8, 28, 9, minute, 0, tzinfo=tz_ist)
        bar = {
            "symbol": "NIFTY",
            "open": 24010 + idx * 10,
            "high": 24100,
            "low": 24000,
            "close": 24050,
            "volume": 20000,
            "time": int(t.timestamp()),
        }
        simulation_runner._evaluate_bar(bar, t)

    orb_events_pre = [ev for ev in simulation_runner._stats.events if ev.strategy == "nifty_orb"]
    assert len(orb_events_pre) == 0  # No trades during opening range window

    # Bar at 09:30:00 breaking out above OR high (24100 + 0.15*ATR) with positive VWAP slope
    t_break = datetime(2026, 8, 28, 9, 30, 0, tzinfo=tz_ist)
    bar_break = {
        "symbol": "NIFTY",
        "open": 24090,
        "high": 24180,
        "low": 24080,
        "close": 24150,
        "volume": 80000,
        "time": int(t_break.timestamp()),
    }
    simulation_runner._evaluate_bar(bar_break, t_break)

    orb_events_post = [ev for ev in simulation_runner._stats.events if ev.strategy == "nifty_orb"]
    assert len(orb_events_post) == 1
    assert orb_events_post[0].direction == "BULLISH"


def test_evaluate_bar_bear_to_bearish_short_only():
    """Verify Bear to Bearish only emits BEARISH signals on lower highs breakdown."""
    from datetime import datetime, timezone
    simulation_runner._bar_history = {}
    simulation_runner._last_fired = {}
    simulation_runner._active_until_bar = {}
    simulation_runner._config = SimConfig(date="2026-08-28", strategy="bear_to_bearish", strategies=["bear_to_bearish"])
    simulation_runner._stats.signals_fired = 0
    simulation_runner._stats.events = []
    simulation_runner._stats.trades = []

    base_time = datetime(2026, 8, 28, 10, 0, tzinfo=timezone.utc)
    # Feed rising market: should NOT produce any signals
    for i in range(15):
        price = 100.0 + (i * 2.0)
        bar = {
            "symbol": "BANKNIFTY",
            "open": price - 1.0,
            "high": price + 2.0,
            "low": price - 2.0,
            "close": price + 1.0,
            "volume": 20000,
        }
        simulation_runner._evaluate_bar(bar, base_time)

    b2b_events = [ev for ev in simulation_runner._stats.events if ev.strategy == "bear_to_bearish"]
    assert len(b2b_events) == 0
    for ev in b2b_events:
        assert ev.direction == "BEARISH"


def test_recorded_signals_september_4():
    """Verify ground truth recorded signals for 2026-09-04 return exactly LT (09:15) and SBIN (12:15)."""
    from app.services.simulation import _load_recorded_signals
    sigs = _load_recorded_signals("2026-09-04")
    assert len(sigs) == 2
    symbols = [s["underlying"] for s in sigs]
    assert symbols == ["LT", "SBIN"]
    assert sigs[0]["time_iso"] == "09:15:00"
    assert sigs[0]["direction"] == "BEARISH"
    assert sigs[1]["time_iso"] == "12:15:00"
    assert sigs[1]["direction"] == "BEARISH"


def test_indicator_warmup_no_boundary_spike():
    """Verify bar 22 does not trigger a spurious SuperTrend signal due to indicator warmup."""
    from datetime import datetime, timezone, timedelta
    simulation_runner._bar_history = {}
    simulation_runner._last_fired = {}
    simulation_runner._active_until_bar = {}
    simulation_runner._recorded_signals = []  # test synthetic indicator logic directly
    simulation_runner._config = SimConfig(date="2026-08-28", strategy="supertrend", strategies=["supertrend"])
    simulation_runner._stats.signals_fired = 0
    simulation_runner._stats.events = []
    simulation_runner._stats.trades = []

    tz_ist = timezone(timedelta(hours=5, minutes=30))
    # Feed 24 flat bars: prices should not generate a crossover at bar 22
    for i in range(24):
        t = datetime(2026, 8, 28, 9, 15, 0, tzinfo=tz_ist) + timedelta(minutes=i * 5)
        bar = {
            "symbol": "NIFTY",
            "open": 24000.0,
            "high": 24010.0,
            "low": 23990.0,
            "close": 24000.0,
            "volume": 10000,
            "time": int(t.timestamp()),
        }
        simulation_runner._evaluate_bar(bar, t)

    st_events = [ev for ev in simulation_runner._stats.events if ev.strategy == "supertrend"]
    assert len(st_events) == 0


@pytest.mark.asyncio
async def test_september_4_replay_emits_only_lt_and_sbin():
    """Verify that simulating 2026-09-04 replays only LT and SBIN and formats accurate Kite legs."""
    config = SimConfig(
        date="2026-09-04",
        start_time="09:15:00",
        end_time="15:30:00",
        speed=50.0,
        strategy="supertrend",
        strategies=["supertrend"],
    )
    await simulation_runner.start(config)

    # Wait for simulation to transition to RUNNING state
    import asyncio
    for _ in range(50):
        if simulation_runner.status.state == SimState.RUNNING:
            break
        await asyncio.sleep(0.05)

    assert simulation_runner.status.state == SimState.RUNNING

    # Fast forward clock to 11:20:00 (user's screenshot time)
    # 2026-09-04 11:20:00 IST
    from datetime import datetime, timezone, timedelta
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    t_1120 = int(datetime(2026, 9, 4, 11, 20, 0, tzinfo=tz_ist).timestamp())
    simulation_runner._seek_requested_epoch = float(t_1120)

    # Wait for seek to apply
    for _ in range(50):
        if simulation_runner._seek_requested_epoch is None and simulation_runner._current_sim_epoch >= t_1120:
            break
        await asyncio.sleep(0.05)

    # At 11:20:00, LT (09:15) should have fired, but SBIN (12:15) has not yet
    assert simulation_runner._stats.signals_fired == 1
    assert simulation_runner._stats.events[0].instrument == "LT"

    # Now step past 12:15:00 (e.g. 12:30:00 IST)
    t_1230 = int(datetime(2026, 9, 4, 12, 30, 0, tzinfo=tz_ist).timestamp())
    simulation_runner._seek_requested_epoch = float(t_1230)
    for _ in range(50):
        if simulation_runner._seek_requested_epoch is None and simulation_runner._current_sim_epoch >= t_1230:
            break
        await asyncio.sleep(0.05)

    # Now both LT and SBIN should have fired, and NO spurious index signals
    assert simulation_runner._stats.signals_fired == 2
    symbols = [ev.instrument for ev in simulation_runner._stats.events]
    assert symbols == ["LT", "SBIN"]

    # Verify Kite signals response formatting contains the real option legs
    kite_resp = simulation_runner.get_kite_signals_response()
    assert len(kite_resp["rows"]) == 2
    underlyings = [r["underlying"] for r in kite_resp["rows"]]
    assert underlyings == ["LT", "SBIN"]

    # Verify executed trades have valid entry and exit timestamps and slippage accounting
    assert len(simulation_runner._stats.trades) == 2
    for tr in simulation_runner._stats.trades:
        assert tr.entry_time_iso != ""
        assert tr.exit_time_iso != ""
        assert len(tr.entry_time_iso.split(":")) == 3
        assert len(tr.exit_time_iso.split(":")) == 3
        assert tr.raw_entry is not None
        assert tr.raw_exit is not None
        assert tr.slippage > 0  # Default realistic mode calculates slippage
        assert tr.entry_price > tr.raw_entry  # Buyer pays ask (half spread + slippage)
    assert simulation_runner._stats.trades[0].entry_time_iso == "09:15:00"

    await simulation_runner.stop()


@pytest.mark.asyncio
async def test_simulation_ideal_friction_mode():
    """Verify that ideal friction mode executes at raw signal entry/exit with 0 slippage."""
    config = SimConfig(
        date="2026-09-04",
        start_time="09:15:00",
        end_time="15:30:00",
        speed=50.0,
        strategy="supertrend",
        strategies=["supertrend"],
        friction_mode="ideal",
    )
    await simulation_runner.start(config)

    import asyncio
    for _ in range(50):
        if simulation_runner.status.state == SimState.RUNNING:
            break
        await asyncio.sleep(0.05)

    from datetime import datetime, timezone, timedelta
    tz_ist = timezone(timedelta(hours=5, minutes=30))
    t_1230 = int(datetime(2026, 9, 4, 12, 30, 0, tzinfo=tz_ist).timestamp())
    simulation_runner._seek_requested_epoch = float(t_1230)
    for _ in range(50):
        if simulation_runner._seek_requested_epoch is None and simulation_runner._current_sim_epoch >= t_1230:
            break
        await asyncio.sleep(0.05)

    assert len(simulation_runner._stats.trades) == 2
    for tr in simulation_runner._stats.trades:
        assert tr.slippage == 0.0
        assert tr.entry_price == tr.raw_entry
        assert tr.exit_price == tr.raw_exit

    await simulation_runner.stop()

