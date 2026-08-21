"""Broker-side protection for an open position.

The source bot had none: it held the position in process memory and exited when
it personally saw the target. These tests pin the two things that matter --
that fidelity mode still reproduces that exactly, and that a protected run can
never end up with two live sells against one long position.
"""
import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, LegQuote, OrderReport, OrderStatus,
)
from app.engines.atm_premium_imbalance.protection import (
    ProtectionState, describe_divergence, plan_protection, reconcile,
    requires_cancel_before_exit,
)

from .test_golden_trades import ScriptedBroker, drive, make_pair


def cfg(**kw):
    base = dict(enabled=True, quantity=20)
    base.update(kw)
    return ATMPremiumImbalanceConfig(**base).validate()


# ------------------------------------------------------------- planning

def test_no_protection_by_default_reproducing_the_observed_bot():
    assert plan_protection(cfg(), instrument_id="I", option_type="CE", quantity=20,
                           entry_fill=133.40, target_price=148.40) is None
    assert "nothing exits the position" in describe_divergence(cfg())


def test_resting_limit_sits_at_the_target_tick_aligned_down():
    p = plan_protection(cfg(protection_mode="RESTING_TARGET_LIMIT"),
                        instrument_id="I", option_type="CE", quantity=20,
                        entry_fill=133.40, target_price=148.40, tick_size=0.05)
    assert p is not None
    assert (p.side, p.quantity, p.limit_price) == ("SELL", 20, 148.40)
    assert p.trigger_price is None
    # an off-grid target rounds down, never up past the target
    p2 = plan_protection(cfg(protection_mode="RESTING_TARGET_LIMIT"),
                         instrument_id="I", option_type="CE", quantity=20,
                         entry_fill=133.42, target_price=148.42, tick_size=0.05)
    assert p2.limit_price == 148.40


def test_gtt_trigger_sits_below_its_limit():
    p = plan_protection(cfg(protection_mode="GTT"), instrument_id="I", option_type="PE",
                        quantity=80, entry_fill=340.10, target_price=355.10, tick_size=0.05)
    assert p.kind == "GTT"
    assert p.limit_price == 355.10
    assert p.trigger_price is not None and p.trigger_price < p.limit_price


def test_divergence_from_the_recordings_is_stated_not_hidden():
    text = describe_divergence(cfg(protection_mode="RESTING_TARGET_LIMIT"))
    assert "NOT byte-comparable to the recordings" in text


def test_live_mode_refuses_to_run_unprotected():
    with pytest.raises(ValueError, match="requires broker-side protection"):
        ATMPremiumImbalanceConfig(execution_mode="live", quote_mode="EXECUTABLE",
                                  quantity=20, protection_mode="NONE").validate()
    # ...and accepts a protected live config
    ATMPremiumImbalanceConfig(execution_mode="live", quote_mode="EXECUTABLE", quantity=20,
                              protection_mode="RESTING_TARGET_LIMIT").validate()


# ------------------------------------------------------------ reconcile

def test_reconcile_resolves_disagreement_to_failed():
    p = plan_protection(cfg(protection_mode="RESTING_TARGET_LIMIT"), instrument_id="I",
                        option_type="CE", quantity=20, entry_fill=100.0, target_price=115.0)
    assert reconcile(p, broker_says_filled=True, broker_says_open=False) is ProtectionState.FILLED
    assert reconcile(p, broker_says_filled=False, broker_says_open=True) is ProtectionState.ACTIVE
    # both true is incoherent -> a resting sell of unknown status
    assert reconcile(p, broker_says_filled=True, broker_says_open=True) is ProtectionState.FAILED
    assert reconcile(None, broker_says_filled=False, broker_says_open=False) is ProtectionState.ABSENT


def test_requires_cancel_only_while_live():
    p = plan_protection(cfg(protection_mode="RESTING_TARGET_LIMIT"), instrument_id="I",
                        option_type="CE", quantity=20, entry_fill=100.0, target_price=115.0)
    assert requires_cancel_before_exit(p) is True
    assert requires_cancel_before_exit(None) is False


# ----------------------------------------------------- lifecycle wiring

def _armed(protection_mode="RESTING_TARGET_LIMIT"):
    pair = make_pair(77600.0, "A", "B", "2026-07-30")
    c = cfg(protection_mode=protection_mode)
    s = ATMPremiumImbalanceStrategy(cfg=c, pair=pair, quantity=20)
    b = ScriptedBroker(entry_fill=133.40, exit_fill=156.85)
    # get to a filled entry without letting drive() service protection intents
    now = 0
    for leg, ltp, bid, ask in [("CE", 167.50, 167.0, 167.5), ("PE", 214.85, 214.4, 215.3)]:
        now += 50
        iid = pair.ce.instrument_id if leg == "CE" else pair.pe.instrument_id
        intent = s.on_option_tick(LegQuote(instrument_id=iid, ltp=ltp, bid=bid, ask=ask,
                                           exchange_ts_ms=now, received_ts_ms=now, sequence=now), now)
    intent = s.record_entry_submit(intent.priced, order_id="E1")
    intent = s.record_entry_status(OrderReport(order_id="E1", status=OrderStatus.COMPLETE,
                                               transaction="BUY", average_price=133.40,
                                               filled_quantity=20))
    return s, pair, intent, now


def test_protection_is_placed_immediately_after_the_entry_fills():
    s, _, intent, _ = _armed()
    assert intent.kind == "place_protection"
    assert intent.limit_price == 148.40          # the target
    assert intent.side == "SELL" and intent.quantity == 20
    assert s.protection.state is ProtectionState.PENDING


def test_unacknowledged_protection_halts_rather_than_pretending_to_be_protected():
    s, _, intent, _ = _armed()
    out = s.record_protection_submit(order_id=None, error="broker timeout")
    assert out.kind == "halt"
    assert s.protection.state is ProtectionState.FAILED
    assert s.trade.state.value == "reconciliation_required"


def test_exit_cancels_the_resting_sell_before_sending_its_own():
    s, pair, intent, now = _armed()
    s.record_protection_submit(order_id="P1")
    assert s.protection.state is ProtectionState.ACTIVE

    now += 50
    out = s.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=149.10,
                                    bid=149.2, ask=149.6, exchange_ts_ms=now,
                                    received_ts_ms=now, sequence=now), now)
    # target hit -> cancel first, do NOT send a second sell yet
    assert out.kind == "cancel_protection"
    assert out.order_id == "P1"
    assert s.protection.state is ProtectionState.CANCEL_PENDING

    out = s.record_protection_cancelled(ok=True)
    assert out.kind == "submit_exit"
    assert out.limit_price == 148.70             # best bid 149.2 - 0.50


def test_a_failed_cancel_halts_instead_of_stacking_two_sells():
    s, pair, intent, now = _armed()
    s.record_protection_submit(order_id="P1")
    now += 50
    s.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=149.10, bid=149.2,
                              ask=149.6, exchange_ts_ms=now, received_ts_ms=now,
                              sequence=now), now)
    out = s.record_protection_cancelled(ok=False)
    assert out.kind == "halt"
    assert out.reason == "protection_cancel_failed"
    assert s.trade.state.value == "reconciliation_required"


def test_protection_filling_closes_the_trade_as_a_normal_exit():
    """This is protection working, not protection failing."""
    s, _, intent, _ = _armed()
    s.record_protection_submit(order_id="P1")
    out = s.record_protection_filled(148.40)
    assert out.kind == "complete"
    assert s.trade.state.value == "closed"
    assert s.trade.exit_price == 148.40
    assert s.trade.points == 15.00               # exactly the target
    assert s.trade.pnl == 300.0                  # 15.00 x 20
    assert s.summary()["protection"]["state"] == "filled"
    assert s.trades_taken == 1


def test_fidelity_mode_places_no_protection_and_exits_exactly_as_observed():
    s, pair, intent, now = _armed(protection_mode="NONE")
    assert intent.kind == "none" and s.protection is None
    now += 50
    out = s.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=149.10, bid=149.2,
                                    ask=149.6, exchange_ts_ms=now, received_ts_ms=now,
                                    sequence=now), now)
    assert out.kind == "submit_exit"             # straight to the observed exit
    assert out.limit_price == 148.70
