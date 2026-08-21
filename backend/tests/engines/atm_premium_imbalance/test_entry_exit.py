"""Entry pricing, the retry state machine, and exit pricing."""
import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig,
    InstrumentRef,
    ManualPriceTable,
    OrderReport,
    OrderStatus,
    ReconcileState,
    exit_order_price,
    price_entry,
    should_exit,
    stop_price,
    target_price,
)
from app.engines.atm_premium_imbalance.entry import ActionKind, EntryEngine, EntryPhase


def inst(strike=77600.0, option_type="CE", upper=1745.45, tick=0.05):
    return InstrumentRef(
        instrument_id="BSE_FO|1141595", tradingsymbol="SENSEX77600CE",
        option_type=option_type, strike=strike, expiry="2026-07-30",
        lot_size=20, tick_size=tick, upper_circuit=upper,
    )


def report(status=OrderStatus.COMPLETE, avg=133.40, qty=20, oid="260730000006021"):
    return OrderReport(
        order_id=oid, status=status, transaction="BUY",
        average_price=avg, filled_quantity=qty,
    )


# ----------------------------------------------------------- entry pricing

def test_marketable_ask_is_the_default_policy():
    cfg = ATMPremiumImbalanceConfig()
    assert cfg.entry_price_policy == "MARKETABLE_ASK"
    priced = price_entry(cfg, inst(), best_ask=167.50)
    assert priced.limit_price == 168.00        # 167.50 + 0.50
    assert priced.reference_kind == "best_ask"
    assert not priced.capped_by_upper_circuit


def test_manual_file_reproduces_the_observed_order_price():
    """V17: strike_prices.txt gave 288.75 for 77600CE. A231/E2."""
    table = ManualPriceTable.parse("# comment\n77600CE 288.75\n77600PE=301.10\n")
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="MANUAL_FILE", manual_price_file="strike_prices.txt"
    ).validate()
    priced = price_entry(cfg, inst(), best_ask=167.50, manual_table=table)
    assert priced.limit_price == 288.75
    assert priced.reference_kind == "manual_file"
    assert not priced.capped_by_upper_circuit   # 288.75 < MPP 1745.45


def test_entry_limit_is_capped_at_the_upper_circuit():
    table = ManualPriceTable.parse("77600CE 5000.00")
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="MANUAL_FILE", manual_price_file="f.txt"
    ).validate()
    priced = price_entry(cfg, inst(upper=1745.45), best_ask=167.5, manual_table=table)
    assert priced.capped_by_upper_circuit
    assert priced.limit_price <= 1745.45
    assert priced.raw_price == 5000.00          # provenance preserved


def test_percent_through_policy():
    cfg = ATMPremiumImbalanceConfig(entry_price_policy="PERCENT_THROUGH", entry_through_pct=0.72)
    priced = price_entry(cfg.validate(), inst(), best_ask=167.50)
    # 167.50 x 1.72 = 288.10, already on the 0.05 grid. Chosen because it lands
    # near the 288.75 the observed bot actually sent against a 167.50 ask.
    assert priced.limit_price == 288.10


def test_buy_limit_rounds_up_to_the_tick_grid():
    cfg = ATMPremiumImbalanceConfig(entry_buffer_points=0.52)
    priced = price_entry(cfg, inst(), best_ask=167.50)
    assert priced.limit_price == 168.05         # 168.02 -> up to 168.05


def test_policies_do_not_silently_fall_back():
    cfg = ATMPremiumImbalanceConfig()           # MARKETABLE_ASK
    with pytest.raises(ValueError, match="requires a live ask"):
        price_entry(cfg, inst(), best_ask=None, last_price=167.5)

    manual_cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="MANUAL_FILE", manual_price_file="f.txt"
    ).validate()
    with pytest.raises(ValueError, match="no manual price"):
        price_entry(manual_cfg, inst(strike=77500.0), best_ask=1.0,
                    manual_table=ManualPriceTable.parse("77600CE 288.75"))


def test_manual_table_rejects_malformed_lines():
    with pytest.raises(ValueError, match="line 2"):
        ManualPriceTable.parse("77600CE 288.75\nbroken line here now\n")


def test_rejected_first_tick_policy_is_blocked_in_live():
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PLUS_BUFFER", execution_mode="live",
        quote_mode="EXECUTABLE", quantity=20,
    )
    with pytest.raises(ValueError, match="research-only"):
        cfg.validate()


def test_rejected_first_tick_policy_still_replays():
    """The spec's 10.25 model must remain reproducible, just not tradable."""
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PLUS_BUFFER", entry_buffer_points=10.25,
    ).validate()
    priced = price_entry(cfg, inst(), best_ask=None, first_tick_price=102.85)
    assert priced.limit_price == 113.10          # the supplied spec's arithmetic
    assert priced.reference_kind == "first_tick"


def test_live_mode_requires_executable_quotes():
    cfg = ATMPremiumImbalanceConfig(execution_mode="live", quantity=20)
    with pytest.raises(ValueError, match="quote_mode=EXECUTABLE"):
        cfg.validate()


# ------------------------------------------------- entry retry state machine

def test_happy_path_fills_on_first_attempt():
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    priced = price_entry(eng.cfg, inst(), best_ask=167.50)
    assert eng.next_action().kind is ActionKind.SUBMIT
    eng.record_submit(priced, order_id="A1")
    assert eng.next_action().kind is ActionKind.AWAIT_STATUS
    eng.record_status(report())
    assert eng.next_action().kind is ActionKind.DONE_FILLED
    assert eng.fill_price == 133.40 and eng.attempt_count == 1


def test_unknown_status_demands_reconciliation_never_a_resubmit():
    """The invariant this class exists for. A230 section 5."""
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    priced = price_entry(eng.cfg, inst(), best_ask=167.50)
    eng.record_submit(priced, order_id="A1")
    eng.record_status(None)                      # status poll failed
    action = eng.next_action()
    assert action.kind is ActionKind.RECONCILE
    assert action.order_id == "A1"
    # Repeated asking must not degrade into a submit.
    for _ in range(5):
        assert eng.next_action().kind is ActionKind.RECONCILE


def test_timeout_demands_reconciliation():
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id="A1")
    eng.record_timeout()
    assert eng.next_action().kind is ActionKind.RECONCILE


def test_submit_without_order_id_or_error_demands_reconciliation():
    """No ack and no error is the dangerous case: it may still be live."""
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id=None)
    assert eng.next_action().kind is ActionKind.RECONCILE


def test_reconciliation_finding_a_fill_uses_that_fill():
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id="A1")
    eng.record_status(None)
    eng.record_reconciliation(ReconcileState.MATCHED, report(avg=133.40))
    assert eng.next_action().kind is ActionKind.DONE_FILLED
    assert eng.fill_price == 133.40
    assert eng.attempt_count == 1                # no duplicate attempt created


def test_reconciliation_confirming_absence_allows_one_more_attempt():
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id="A1")
    eng.record_status(None)
    eng.record_reconciliation(ReconcileState.MATCHED, report(status=OrderStatus.CANCELLED, avg=None, qty=0))
    action = eng.next_action()
    assert action.kind is ActionKind.SUBMIT and action.attempt == 2


@pytest.mark.parametrize("state", [ReconcileState.UNKNOWN, ReconcileState.DIVERGED])
def test_unresolved_reconciliation_blocks_the_strategy(state):
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id="A1")
    eng.record_status(None)
    eng.record_reconciliation(state)
    assert eng.next_action().kind is ActionKind.BLOCKED
    assert eng.phase is EntryPhase.BLOCKED


def test_three_rejections_exhaust_the_sequence():
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    for n in (1, 2, 3):
        action = eng.next_action()
        assert action.kind is ActionKind.SUBMIT and action.attempt == n
        eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id=f"A{n}")
        eng.record_status(report(status=OrderStatus.REJECTED, avg=None, qty=0))
    assert eng.next_action().kind is ActionKind.DONE_EXHAUSTED
    assert eng.attempt_count == 3


def test_complete_without_average_price_is_treated_as_unknown():
    """A 'complete' with no price must never reach the target calculation."""
    eng = EntryEngine(cfg=ATMPremiumImbalanceConfig())
    eng.record_submit(price_entry(eng.cfg, inst(), best_ask=167.5), order_id="A1")
    eng.record_status(OrderReport(order_id="A1", status=OrderStatus.COMPLETE,
                                  transaction="BUY", average_price=None, filled_quantity=20))
    assert eng.next_action().kind is ActionKind.RECONCILE


# ------------------------------------------------------------ exit mechanics

def test_target_is_entry_fill_plus_fifteen():
    cfg = ATMPremiumImbalanceConfig()
    assert target_price(133.40, cfg) == 148.40     # V17
    assert target_price(113.10, cfg) == 128.10     # V1


def test_target_ignores_the_requested_limit():
    """V17 requested 288.75 and filled 133.40; the target must use 133.40."""
    cfg = ATMPremiumImbalanceConfig()
    assert target_price(133.40, cfg) == 148.40
    assert target_price(288.75, cfg) != 148.40


@pytest.mark.parametrize("bid,expected", [(149.2, 148.7), (127.1, 126.6)])
def test_exit_price_is_best_bid_minus_half_a_point(bid, expected):
    """OBSERVED in both builds. A231/X3."""
    assert exit_order_price(bid, ATMPremiumImbalanceConfig(), tick_size=0.05) == expected


def test_sell_limit_rounds_down_to_the_tick_grid():
    cfg = ATMPremiumImbalanceConfig(exit_buffer_points=0.52)
    assert exit_order_price(149.2, cfg, tick_size=0.05) == 148.65   # 148.68 -> down


def test_exit_price_needs_a_reference():
    assert exit_order_price(None, ATMPremiumImbalanceConfig()) is None
    assert exit_order_price(None, ATMPremiumImbalanceConfig(), fallback_price=149.2) == 148.7


def test_target_trigger_fires_at_or_above_target():
    cfg = ATMPremiumImbalanceConfig()
    assert should_exit(last_price=148.39, entry_fill=133.40, cfg=cfg) == (False, "")
    assert should_exit(last_price=148.40, entry_fill=133.40, cfg=cfg) == (True, "target_hit")
    assert should_exit(last_price=149.10, entry_fill=133.40, cfg=cfg) == (True, "target_hit")


def test_no_stop_and_no_time_stop_by_default():
    cfg = ATMPremiumImbalanceConfig()
    assert stop_price(133.40, cfg) is None
    assert should_exit(last_price=1.0, entry_fill=133.40, cfg=cfg, held_seconds=99999) == (False, "")


def test_stop_and_time_stop_work_when_enabled():
    cfg = ATMPremiumImbalanceConfig(stop_enabled=True, stop_points=10.0, max_hold_seconds=60)
    assert stop_price(133.40, cfg) == 123.40
    assert should_exit(last_price=123.40, entry_fill=133.40, cfg=cfg) == (True, "stop_hit")
    assert should_exit(last_price=130.0, entry_fill=133.40, cfg=cfg, held_seconds=60) == (True, "time_stop")


def test_convergence_exit_is_research_only():
    cfg = ATMPremiumImbalanceConfig(exit_policy="PREMIUM_CONVERGENCE")
    cfg.validate()
    assert should_exit(last_price=140.0, entry_fill=133.40, cfg=cfg,
                       counter_leg_price=139.0) == (True, "premium_convergence")
    live = ATMPremiumImbalanceConfig(
        exit_policy="PREMIUM_CONVERGENCE", execution_mode="live",
        quote_mode="EXECUTABLE", quantity=20,
    )
    with pytest.raises(ValueError, match="research-only"):
        live.validate()

# ------------------------------------------------------ session-time parsing

@pytest.mark.parametrize(
    "start,end",
    [
        ("9:15", "15:25"),      # single-digit hour is normalised, not rejected
        ("09:15", "15:25"),
        ("00:00", "23:59"),
    ],
)
def test_valid_session_times_are_accepted_and_normalised(start, end):
    cfg = ATMPremiumImbalanceConfig(session_start=start, session_end=end).validate()
    assert cfg is not None


@pytest.mark.parametrize(
    "start,end,match",
    [
        ("0915", "15:25", "session_start must be HH:MM"),
        ("09:15:00", "15:25", "session_start must be HH:MM"),
        ("ab:cd", "15:25", "session_start must be HH:MM"),
        ("", "15:25", "session_start must be HH:MM"),
        ("24:00", "15:25", "session_start must be a valid HH:MM time"),
        ("09:60", "15:25", "session_start must be a valid HH:MM time"),
        ("09:15", "9-25", "session_end must be HH:MM"),
        ("09:15", "25:00", "session_end must be a valid HH:MM time"),
    ],
)
def test_malformed_session_times_are_rejected(start, end, match):
    """A bad stored time must fail at load, not mid-session inside the engine."""
    with pytest.raises(ValueError, match=match):
        ATMPremiumImbalanceConfig(session_start=start, session_end=end).validate()


def test_session_must_start_before_it_ends():
    with pytest.raises(ValueError, match="session_start must be before session_end"):
        ATMPremiumImbalanceConfig(session_start="15:25", session_end="09:15").validate()
    with pytest.raises(ValueError, match="session_start must be before session_end"):
        ATMPremiumImbalanceConfig(session_start="09:15", session_end="09:15").validate()
