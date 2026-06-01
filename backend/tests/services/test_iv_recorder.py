import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services import db
from app.services.delta_iv_socket import IVTick
from app.services.delta_iv_recorder import _flush_ticks, start_recorder, stop_recorder

# Use an in-memory db for testing
pytestmark = pytest.mark.asyncio


import os
import tempfile

@pytest.fixture(autouse=True)
def setup_db():
    fd, path = tempfile.mkstemp()
    os.close(fd)
    db._DB_PATH = path
    db.init()
    yield
    os.unlink(path)


def test_db_schema_created():
    """Verify table option_iv_ticks is created and writable."""
    ts = 1680000000.0
    data = [
        ("BTC", "270625", 100000.0, "call", 0.65, 0.64, 0.66, 0.5, 0.01, -10.0, 5.0, 2.0, ts)
    ]
    db.record_option_ticks(data)

    with db._conn() as c:
        row = c.execute("SELECT * FROM option_iv_ticks WHERE underlying='BTC'").fetchone()

    assert row is not None
    assert row["underlying"] == "BTC"
    assert row["expiry"] == "270625"
    assert row["strike"] == 100000.0
    assert row["opt_type"] == "call"
    assert row["mark_iv"] == 0.65


@patch("app.services.delta_iv_recorder.iv_manager")
def test_recorder_downsamples_and_flushes(mock_iv_manager):
    """Verify the downsampling flush routine pushes correct tuples."""
    mock_tick = IVTick(
        option_symbol="C-BTC-100000-270625",
        underlying="BTC",
        option_type="call",
        strike=100000.0,
        expiry="270625",
        dte=30,
        mark_iv=0.65, bid_iv=0.64, ask_iv=0.66,
        mark_price=1000.0, best_bid=990.0, best_ask=1010.0,
        delta=0.5, gamma=0.01, theta=-10.0, vega=5.0, rho=2.0,
        ts_exchange=1680000000.0, ts_local=1680000001.0
    )

    mock_iv_manager.chain.return_value = [mock_tick]
    mock_iv_manager.atm_iv.return_value = 0.65

    _flush_ticks("BTC")

    with db._conn() as c:
        row = c.execute("SELECT * FROM option_iv_ticks WHERE underlying='BTC'").fetchone()
        iv_row = c.execute("SELECT * FROM iv_history WHERE underlying='BTC'").fetchone()

    assert row is not None
    assert row["mark_iv"] == 0.65
    assert row["delta"] == 0.5

    assert iv_row is not None
    assert iv_row["ivr"] == 0.65


@patch("app.services.delta_iv_recorder.iv_manager")
async def test_atm_iv_bridge(mock_iv_manager):
    """Verify atm_iv bridge handles None values safely."""
    mock_iv_manager.chain.return_value = []
    mock_iv_manager.atm_iv.return_value = None

    _flush_ticks("ETH")

    with db._conn() as c:
        iv_row = c.execute("SELECT * FROM iv_history WHERE underlying='ETH'").fetchone()
    
    # If atm_iv is None, it shouldn't record to iv_history
    assert iv_row is None

