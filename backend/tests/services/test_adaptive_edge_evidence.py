"""The live evidence record, and the gate that reads it.

Every offline conclusion about this strategy failed for one reason: option
prices exist in no store here. The engine measures them live. This is the
plumbing that makes that measurement survive a restart, so a gate needing weeks
of readings can actually get them.
"""
from __future__ import annotations

import re

import pytest

from app.services import adaptive_edge_evidence as evidence
from app.services import adaptive_edge_runner as runner


@pytest.fixture
def store(monkeypatch):
    data: dict[str, str] = {}
    import app.services.db as db
    monkeypatch.setattr(db, "get_config", lambda key, default="": data.get(key, default))
    monkeypatch.setattr(db, "set_config", lambda key, value: data.__setitem__(key, value))
    return data


def _reading(session="2026-08-27", ms=1, underlying="NIFTY", strike=24_800.0, **over):
    kwargs = dict(session=session, decided_ms=ms, underlying=underlying, strike=strike,
                  implied_ratio=1.2, implied_vol=0.12, realised_vol=0.10,
                  credit_bps=28.0, max_loss_bps=28.8, forecast_bps=40.0)
    kwargs.update(over)
    return evidence.PendingReading(**kwargs)


# --------------------------------------------------------------- recording

def test_a_reading_is_recorded(store):
    assert evidence.record("u1", _reading()) is True
    assert evidence.summary("u1")["pending"] == 1


def test_the_same_decision_is_not_recorded_twice(store):
    """Scans repeat and re-surface the same contract. A duplicated reading
    quietly doubles its own weight in the interval the gate computes."""
    evidence.record("u1", _reading())
    assert evidence.record("u1", _reading()) is False
    assert evidence.summary("u1")["pending"] == 1


def test_the_same_contract_at_a_later_scan_is_a_new_reading(store):
    evidence.record("u1", _reading(ms=1))
    evidence.record("u1", _reading(ms=2))
    assert evidence.summary("u1")["pending"] == 2


def test_an_unresolved_reading_is_not_evidence(store):
    """None is not zero. A zero move is a real outcome; None means unknown."""
    evidence.record("u1", _reading())
    assert evidence.readings("u1") == []
    assert evidence.verdict("u1").observations == 0


# --------------------------------------------------------------- resolving

def test_an_outcome_updates_the_reading_it_belongs_to(store):
    evidence.record("u1", _reading())
    assert evidence.resolve("u1", "2026-08-27", "NIFTY:24800:1", 12.0) is True
    got = evidence.readings("u1")
    assert len(got) == 1
    assert got[0].realised_move_bps == pytest.approx(12.0)
    assert evidence.summary("u1")["pending"] == 0


def test_resolving_an_unknown_reading_is_refused(store):
    assert evidence.resolve("u1", "2026-08-27", "NOPE:0:0", 5.0) is False


def test_a_resolved_reading_carries_the_capped_payoff(store):
    """A huge move must cost exactly the defined risk, never more."""
    evidence.record("u1", _reading())
    evidence.resolve("u1", "2026-08-27", "NIFTY:24800:1", 5_000.0)
    assert evidence.readings("u1")[0].would_have == pytest.approx(-28.8)


# ------------------------------------------------------------- the verdict

def test_a_fresh_account_has_not_earned_the_right_to_trade(store):
    v = evidence.verdict("u1")
    assert v.ready is False
    assert "has not run" in v.reason


def test_the_summary_says_what_is_still_outstanding(store):
    evidence.record("u1", _reading())
    evidence.resolve("u1", "2026-08-27", "NIFTY:24800:1", 10.0)
    assert "more observations" in evidence.summary("u1")["shortfall"]


def test_the_summary_reports_the_measured_premium_level(store):
    for i in range(5):
        evidence.record("u1", _reading(ms=i, implied_ratio=1.3))
        evidence.resolve("u1", "2026-08-27", f"NIFTY:24800:{i}", 10.0)
    assert evidence.summary("u1")["median_implied_ratio"] == pytest.approx(1.3)


# ------------------------------------------------------- the runner's gate

def test_the_runner_refuses_to_arm_without_evidence(store):
    permitted, reason = runner.evidence_permits_arming("u1")
    assert permitted is False
    assert "has not run" in reason


def test_an_unreadable_store_fails_closed(monkeypatch):
    """"Cannot tell" must never resolve to "go ahead"."""
    import app.services.adaptive_edge_evidence as module

    def boom(uid):
        raise RuntimeError("store down")

    monkeypatch.setattr(module, "verdict", boom)
    permitted, reason = runner.evidence_permits_arming("u1")
    assert permitted is False
    assert "unavailable" in reason


def test_arming_is_blocked_by_the_gate(store, monkeypatch):
    import asyncio
    monkeypatch.setattr(runner, "is_paper", lambda uid: True)
    runner._scan_states["u1"] = {"candidates": [], "signals": [
        {"signal_id": "S", "symbol": "X", "token": 1, "underlying": "NIFTY",
         "option_type": "CE", "lot_size": 50, "last_price": 120.0}]}
    result = asyncio.run(runner.arm("u1", "S"))
    assert result["ok"] is False
    assert "evidence gate" in result["reason"]
    runner.clear("u1")


# ------------------------------------------- the client API these paths use

def test_the_scanner_and_runner_call_methods_the_client_actually_has():
    """Both bugs found the moment a live Kite session existed.

    The scanner called `client.quote(...)`, which does not exist — the method is
    `get_quote`. Every call sat inside a try/except, so a real scan reported
    "quotes unavailable" and carried on: the engine could never have worked, and
    nothing failed loudly enough to say so.

    A name checked against the real class is worth more than a mock that agrees
    with whatever it is told.
    """
    import inspect
    from app.services.exchanges.kite.client import KiteClient
    from app.services import adaptive_edge_runner, adaptive_edge_scanner

    available = {n for n in dir(KiteClient) if not n.startswith("_")}
    for module in (adaptive_edge_scanner, adaptive_edge_runner):
        source = inspect.getsource(module)
        for call in re.findall(r"\bclient\.(\w+)\s*\(", source):
            assert call in available, (
                f"{module.__name__} calls client.{call}(), which KiteClient does "
                f"not have — this fails only at runtime, inside an except")


def test_account_enumeration_uses_the_real_accounts_api():
    """`_kite_user_ids` called `accounts.active_user_ids()`, which does not
    exist, inside a bare except returning []. The 60-second scan loop therefore
    enumerated nobody and logged nothing — a no-op reporting success."""
    import inspect
    from app.services.exchanges.kite import accounts
    from app.services import adaptive_edge_runner

    source = inspect.getsource(adaptive_edge_runner._kite_user_ids)
    available = {n for n in dir(accounts) if not n.startswith("_")}
    for call in re.findall(r"\baccounts\.(\w+)\s*\(", source):
        assert call in available, f"accounts.{call}() does not exist"
