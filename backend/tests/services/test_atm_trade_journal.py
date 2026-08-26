"""The journal is the only thing that survives a restart, so it is tested for the
two ways it could quietly ruin the measurement: losing a real trade, or counting a
simulated one.
"""
import pytest

from app.services import atm_trade_journal as journal
from app.services import db


class _Exit:
    def __init__(self, reason):
        self.reason = reason


class _Trade:
    """Enough of a TradeRecord for the journal, which reads by attribute."""

    def __init__(self, entry, exit_price, points, pnl, reason="target_hit",
                 option_type="PE", quantity=80):
        self.option_type, self.quantity = option_type, quantity
        self.strike, self.expiry = 77700.0, "2026-08-27"
        self.entry_price, self.exit_price = entry, exit_price
        self.points, self.pnl = points, pnl
        self.exit = _Exit(reason)


@pytest.fixture(autouse=True)
def _clean_db():
    db.init()
    with db.connection() as conn:
        conn.execute("DELETE FROM atm_trades")
    yield
    with db.connection() as conn:
        conn.execute("DELETE FROM atm_trades")


def _rec(trade, **kw):
    kw.setdefault("underlying", "SENSEX")
    kw.setdefault("mode", "paper")
    kw.setdefault("is_sim", False)
    return journal.record(trade, **kw)


def test_a_closed_trade_survives_and_is_counted():
    assert _rec(_Trade(338.10, 353.10, 15.0, 1200.0))
    s = journal.summary()
    assert s["trades"] == 1 and s["wins"] == 1 and s["losses"] == 0


def test_a_simulated_trade_is_recorded_but_never_counted():
    """A sim fill is modelled at a price nobody paid.

    Letting it into the win rate would corrupt the one statistic that decides
    whether this strategy is viable, so it is stored and excluded.
    """
    assert _rec(_Trade(338.10, 353.10, 15.0, 1200.0), is_sim=True)
    assert journal.summary()["trades"] == 0
    assert journal.summary(include_sim=True)["trades"] == 1


def test_a_trade_with_no_fill_is_not_recorded():
    """A session can complete without ever filling. That is not a trade."""
    assert not _rec(_Trade(338.10, None, 0.0, 0.0))
    assert journal.summary()["trades"] == 0


def test_the_break_even_win_rate_is_reported_beside_the_actual_one():
    """A win rate alone says nothing without the threshold it must clear.

    Three wins of +3% and one loss of -30% is a 75% win rate and a losing
    strategy: break-even needs 30/(3+30) = 90.9%.
    """
    for _ in range(3):
        _rec(_Trade(100.0, 103.0, 3.0, 300.0))
    _rec(_Trade(100.0, 70.0, -30.0, -3000.0, reason="stop_hit"))
    s = journal.summary()
    assert s["win_rate_pct"] == 75.0
    assert s["break_even_win_rate_pct"] == pytest.approx(90.91, abs=0.05)
    assert s["expectancy_pct"] < 0


def test_percentages_not_points_so_the_statistic_generalises():
    """+15 points is 15% of a 100 premium and 4.4% of a 338 one.

    The whole reason a fixed point target is suspect is that the same points mean
    different risk at different premiums, so the summary must be scale-free.
    """
    _rec(_Trade(100.0, 115.0, 15.0, 1125.0))
    _rec(_Trade(338.10, 353.10, 15.0, 1200.0))
    s = journal.summary()
    assert s["best_pct"] == pytest.approx(15.0, abs=0.01)
    assert s["worst_pct"] == pytest.approx(4.44, abs=0.01)


def test_no_verdict_is_offered_on_too_small_a_sample():
    _rec(_Trade(100.0, 103.0, 3.0, 300.0))
    s = journal.summary()
    assert "not enough trades" in s["verdict"]
    assert s["min_sample"] >= 30


def test_exit_reasons_are_counted_so_a_stop_that_never_fires_is_visible():
    _rec(_Trade(100.0, 103.0, 3.0, 300.0, reason="target_hit"))
    _rec(_Trade(100.0, 90.0, -10.0, -750.0, reason="stop_hit"))
    _rec(_Trade(100.0, 90.0, -10.0, -750.0, reason="stop_hit"))
    assert journal.summary()["exit_reasons"] == {"target_hit": 1, "stop_hit": 2}


def test_a_journal_failure_never_raises_into_the_trading_path():
    """A write problem must not be able to kill a live trade."""
    class Broken:
        entry_price = 100.0
        exit_price = 110.0
        def __getattr__(self, name):
            raise RuntimeError("boom")
    assert journal.record(Broken(), underlying="X", mode="paper", is_sim=False) is False
