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


# ---------------------------------------------------------------------------
# The four bugs a live Kite session exposed that no mock had caught. Every one
# was a mismatch between what the code assumed a value looked like and what the
# broker actually sends, and every one failed SILENTLY — the scan reported
# "not enough history" or "spot unavailable" rather than an error, so the
# engine looked like it was running while it made no decision at all.
# ---------------------------------------------------------------------------

def test_fetch_bars_reads_the_shape_kite_actually_returns():
    """get_historical() returns {"candles": [...]} at the TOP level.

    Reading only the nested data.candles returned zero rows every time, so the
    strategy never saw a bar and every scan skipped with "only 0 bars of
    history" — indistinguishable from a genuinely short history.
    """
    import asyncio
    from app.services.adaptive_edge_strategy import fetch_bars

    candles = [[f"2026-08-27T09:{m:02d}:00+0530", 100.0, 101.0, 99.0, 100.5, 0]
               for m in range(15, 45)]

    class TopLevel:
        async def get_historical(self, *a, **k):
            return {"candles": candles}

    class Nested:
        async def get_historical(self, *a, **k):
            return {"data": {"candles": candles}}

    for client in (TopLevel(), Nested()):
        bars = asyncio.run(fetch_bars(client, 256265, interval="minute", lookback_bars=30))
        assert len(bars) == 30, f"{type(client).__name__} returned {len(bars)} bars"


def test_index_spot_keys_come_from_the_engine_map_not_string_formatting():
    """BANKNIFTY options track an index named "NIFTY BANK".

    "NSE:BANKNIFTY" does not resolve, so the underlying was dropped from every
    scan with nothing but "spot unavailable" to show for it.
    """
    from app.services.adaptive_edge_scanner import spot_quote_key

    assert spot_quote_key("NIFTY") == "NSE:NIFTY 50"
    assert spot_quote_key("BANKNIFTY") == "NSE:NIFTY BANK"
    assert spot_quote_key("FINNIFTY") == "NSE:NIFTY FIN SERVICE"
    # A single stock is named after itself and must pass through untouched.
    assert spot_quote_key("RELIANCE") == "NSE:RELIANCE"


def test_the_liquidity_filter_normalises_option_type_to_the_traded_spelling():
    """tradeable_contracts() emits CE/PE, not the chain's call/put.

    The scan narrows the chain to the side the strategy called. Comparing that
    against "call"/"put" after the filter had already normalised matched
    nothing, so every contract was discarded after passing every check.
    """
    from app.services.adaptive_edge_scanner import tradeable_contracts
    from app.engines.adaptive_edge.config import AdaptiveEdgeConfig

    rows = [{"instrument_name": f"NIFTY{k}{s}", "strike": 24000.0,
             "option_type": k, "lot_size": 75, "expiry": "2026-08-27"}
            for k, s in (("call", "CE"), ("put", "PE"))]
    quotes = {f"NFO:{r['instrument_name']}": {
        "last_price": 100.0, "volume": 500000, "oi": 100000,
        "depth": {"buy": [{"price": 99.5, "quantity": 1000}],
                  "sell": [{"price": 100.5, "quantity": 1000}]},
    } for r in rows}

    kept, _ = tradeable_contracts(rows, quotes, AdaptiveEdgeConfig(), spot=24000.0)
    assert kept, "fixture should survive the liquidity filter"
    assert {str(r["option_type"]) for r in kept} <= {"CE", "PE"}
    for side in ("CE", "PE"):
        assert [r for r in kept if str(r.get("option_type")) == side], \
            f"narrowing the chain to {side} must keep rows"


def test_the_volatility_reading_sees_both_legs_of_the_straddle():
    """The implied-vol reading prices an ATM straddle: it needs the CE AND the
    PE at one strike. Quoting only the side the strategy called left one leg
    missing, so the reading returned None on every scan and the evidence gate
    could never open."""
    import inspect
    from app.services import adaptive_edge_scanner as scanner

    src = inspect.getsource(scanner.scan)
    reading_at = src.index("volatility_reading(")
    narrow_at = src.index("wanted = decision.option_type")
    assert reading_at < narrow_at, (
        "the volatility reading must be taken from the full chain, before the "
        "scan narrows to one side — otherwise the straddle has only one leg")


def test_a_measurement_without_a_tradeable_structure_is_archived_but_not_evidence(store):
    """The implied-versus-realised ratio is observable on every scan; a priced
    structure almost never is (a 30-bar hold only fits inside the last half hour
    of a weekly expiry). Discarding the unpriced rows kept the store empty and
    threw away the one fact no offline study of this strategy had."""
    from app.services import adaptive_edge_evidence as ev

    bare = ev.PendingReading(
        session="2026-08-27", decided_ms=1, underlying="NIFTY", strike=24100.0,
        implied_ratio=1.9, implied_vol=0.12, realised_vol=0.06,
        credit_bps=None, max_loss_bps=None, forecast_bps=40.0)
    priced = ev.PendingReading(
        session="2026-08-27", decided_ms=2, underlying="NIFTY", strike=24100.0,
        implied_ratio=1.8, implied_vol=0.12, realised_vol=0.07,
        credit_bps=55.0, max_loss_bps=200.0, forecast_bps=40.0)
    assert ev.record("meas", bare)
    assert ev.record("meas", priced)

    # Both resolve — but only the priced one can speak to expectancy.
    ev.resolve("meas", "2026-08-27", bare.key, 30.0)
    ev.resolve("meas", "2026-08-27", priced.key, 30.0)

    assert len(ev.readings("meas")) == 1, "an unpriced row is not gate evidence"
    s = ev.summary("meas")
    assert s["measurements"] == 2, "both measurements must be archived"
    assert s["observations"] == 1
    assert s["median_measured_ratio"] > 1.0


def test_an_underlying_with_no_reachable_expiry_says_so():
    """BANKNIFTY has no weekly expiry, so its nearest contract sits ~33 days out
    while this strategy holds for minutes. Reporting that as "no contract inside
    the expiry and strike windows" made a permanent mismatch look like a quiet
    day, and it went unnoticed across every scan."""
    import inspect
    from app.services import adaptive_edge_scanner as scanner

    src = inspect.getsource(scanner.scan)
    assert "no expiry this strategy can hold" in src
    assert "nearest expiry is" in src


def test_the_default_universe_only_holds_what_the_horizon_can_trade():
    from app.engines.adaptive_edge.config import AdaptiveEdgeConfig

    cfg = AdaptiveEdgeConfig()
    assert "BANKNIFTY" not in cfg.scan_indices, (
        "BANKNIFTY cannot produce a candidate at this horizon — carrying it in "
        "the default universe only manufactures a skip on every scan")
    assert cfg.scan_indices, "the universe must not be empty"
