"""Golden-trade replays.

Each case drives the *live* strategy object with the tick sequence read off the
recordings and asserts the numbers the recordings printed. There is no separate
backtest implementation: if these pass, live and replay agree by construction.

Every expected value cites its A231 row. Anything the recordings did not
establish is asserted as UNRESOLVED rather than invented -- see
``test_v1_entry_block_is_unresolved``.
"""
import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig,
    ATMPremiumImbalanceStrategy,
    InstrumentRef,
    LegQuote,
    ManualPriceTable,
    OptionPairRef,
    OrderReport,
    OrderStatus,
)


# --------------------------------------------------------------------- harness

class ScriptedBroker:
    """Minimal broker that fills at a scripted average price.

    Deliberately fills *away* from the requested limit, because that is what
    happened in the observed trades and it is the behaviour that catches any code
    that quietly uses the requested price as the fill.
    """

    def __init__(self, entry_fill, exit_fill, entry_order_id="E1", exit_order_id="X1"):
        self.entry_fill = entry_fill
        self.exit_fill = exit_fill
        self.entry_order_id = entry_order_id
        self.exit_order_id = exit_order_id
        self.submitted = []

    def run(self, strategy, intent):
        """Service intents until the strategy needs another tick."""
        guard = 0
        while intent.kind not in ("none", "complete", "halt"):
            guard += 1
            assert guard < 50, f"intent loop did not settle: {intent}"
            if intent.kind == "submit_entry":
                self.submitted.append(("BUY", intent.limit_price, intent.quantity))
                intent = strategy.record_entry_submit(
                    intent.priced, order_id=self.entry_order_id, api_time_ms=170.80
                )
            elif intent.kind == "poll_entry":
                intent = strategy.record_entry_status(
                    OrderReport(
                        order_id=self.entry_order_id, status=OrderStatus.COMPLETE,
                        transaction="BUY", average_price=self.entry_fill,
                        filled_quantity=intent.quantity or strategy.quantity,
                    )
                )
            elif intent.kind == "submit_exit":
                self.submitted.append(("SELL", intent.limit_price, intent.quantity))
                intent = strategy.record_exit_submit(order_id=self.exit_order_id)
            elif intent.kind == "poll_exit":
                intent = strategy.record_exit_status(
                    OrderReport(
                        order_id=self.exit_order_id, status=OrderStatus.COMPLETE,
                        transaction="SELL", average_price=self.exit_fill,
                        filled_quantity=strategy.quantity,
                    )
                )
            else:
                raise AssertionError(f"unexpected intent {intent.kind}")
        return intent


def make_pair(strike, ce_token, pe_token, expiry, upper=1745.45):
    def leg(ot, token):
        return InstrumentRef(
            instrument_id=f"BSE_FO|{token}",
            tradingsymbol=f"SENSEX{int(strike)}{ot}",
            option_type=ot, strike=strike, expiry=expiry,
            lot_size=20, tick_size=0.05, upper_circuit=upper,
        )
    return OptionPairRef(
        underlying="SENSEX", expiry=expiry, strike=strike,
        ce=leg("CE", ce_token), pe=leg("PE", pe_token),
        underlying_instrument_id="BSE_INDEX|SENSEX",
    )


def drive(strategy, broker, ticks, *, start_ms=0, step_ms=50):
    """Feed (leg, ltp, bid, ask) tuples; service intents after each."""
    now = start_ms
    for leg, ltp, bid, ask in ticks:
        now += step_ms
        inst_id = strategy.pair.ce.instrument_id if leg == "CE" else strategy.pair.pe.instrument_id
        quote = LegQuote(
            instrument_id=inst_id, ltp=ltp, bid=bid, ask=ask,
            exchange_ts_ms=now, received_ts_ms=now, sequence=now,
        )
        intent = strategy.on_option_tick(quote, now)
        intent = broker.run(strategy, intent)
        if intent.kind in ("complete", "halt"):
            return intent
    return intent


# ------------------------------------------------------- V17 -- 2026-07-30

#: CE/PE stream decoded from V17 frames 0025, 0032, 0056, 0084. Every triple in
#: the source satisfied ``Difference = PE - CE``; see A231/Q2.
V17_STREAM = [
    ("CE", 121.45, 121.0, 121.9), ("PE", 245.70, 245.0, 246.4),
    ("CE", 106.80, 106.3, 107.2), ("PE", 245.15, 244.7, 245.6),
    ("CE", 103.80, 103.3, 104.2), ("PE", 246.40, 246.0, 246.9),
    ("CE", 103.70, 103.2, 104.1), ("PE", 249.15, 248.7, 249.6),
    ("CE", 96.30, 95.8, 96.7),    ("PE", 264.85, 264.4, 265.3),
    ("CE", 94.95, 94.5, 95.4),    ("PE", 252.50, 252.0, 252.9),
    ("CE", 86.30, 85.8, 86.7),    ("PE", 243.95, 243.5, 244.4),
    ("CE", 90.15, 89.7, 90.6),    ("CE", 91.50, 91.0, 91.9),
    ("PE", 240.00, 239.6, 240.4), ("CE", 96.25, 95.8, 96.7),
    ("CE", 97.20, 96.7, 97.6),    ("PE", 241.80, 241.3, 242.2),
    ("CE", 94.30, 93.8, 94.7),    ("CE", 94.55, 94.1, 95.0),
    ("CE", 140.20, 139.7, 140.6), ("PE", 196.95, 196.5, 197.4),
    ("CE", 141.00, 140.5, 141.4), ("PE", 199.30, 198.8, 199.7),
    ("CE", 138.10, 137.6, 138.5), ("CE", 139.50, 139.0, 139.9),
    ("PE", 192.60, 192.1, 193.0),
    # The tick that crossed the 148.40 target. Best bid 149.2 -> exit at 148.7.
    ("CE", 149.10, 149.2, 149.6),
]


@pytest.fixture
def v17():
    pair = make_pair(77600.0, "1141595", "1145203", "2026-07-30")
    cfg = ATMPremiumImbalanceConfig(
        enabled=True,
        entry_price_policy="MANUAL_FILE",
        manual_price_file="strike_prices.txt",
        quantity=20,
    ).validate()
    strategy = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=pair, quantity=20, trade_id="v17",
        manual_table=ManualPriceTable.parse("77600CE 288.75\n77600PE 301.10\n"),
    )
    broker = ScriptedBroker(entry_fill=133.40, exit_fill=156.85,
                            entry_order_id="260730000006021",
                            exit_order_id="260730000008605")
    return strategy, broker, pair


def test_v17_golden_trade_reproduces_every_printed_number(v17):
    strategy, broker, _ = v17
    first = [("CE", 167.50, 167.0, 167.50), ("PE", 214.85, 214.4, 215.3)]
    intent = drive(strategy, broker, first + V17_STREAM)

    assert intent.kind == "complete"
    s = strategy.summary()

    # --- signal (A231/S1, Q2)
    assert strategy.signal.action == "BUY_CE"
    assert strategy.signal.difference == 47.35        # 214.85 - 167.50
    # --- instrument (A231/M4)
    assert (s["strike"], s["option"]) == (77600.0, "CE")
    assert strategy.trade.instrument_id == "BSE_FO|1141595"
    # --- entry (A231/E2, E6)
    assert s["entry_order_price"] == 288.75           # from strike_prices.txt
    assert s["entry"] == 133.40                       # broker average fill
    assert s["attempts"] == 1
    # --- exit (A231/X1, X3, X4)
    assert s["target"] == 148.40                      # 133.40 + 15
    assert s["trigger"] == 149.10
    assert s["exit_order_price"] == 148.70            # best bid 149.2 - 0.50
    assert s["exit"] == 156.85
    # --- result (A231/X5, X6)
    assert s["points"] == 23.45
    assert s["pnl"] == 469.0
    assert s["slippage_vs_target"] == 8.45            # filled above target
    assert s["state"] == "closed"


def test_v17_does_not_exit_before_the_target(v17):
    """CE reached 141.00 mid-stream; the target was 148.40."""
    strategy, broker, _ = v17
    first = [("CE", 167.50, 167.0, 167.50), ("PE", 214.85, 214.4, 215.3)]
    drive(strategy, broker, first + V17_STREAM[:-1])
    assert strategy.trade.exit is None
    assert strategy.phase.value == "in_position"
    assert strategy.trade.target_price == 148.40


def test_v17_target_would_be_wrong_if_built_on_the_requested_limit(v17):
    """Guards the accounting invariant: 288.75 + 15 = 303.75 never fires."""
    strategy, broker, _ = v17
    first = [("CE", 167.50, 167.0, 167.50), ("PE", 214.85, 214.4, 215.3)]
    drive(strategy, broker, first + V17_STREAM)
    assert strategy.trade.target_price == 148.40
    assert strategy.trade.entry_order_price == 288.75
    assert strategy.trade.target_price != 303.75


# --------------------------------------------------------- V1 -- 2026-08-20

def test_v1_golden_trade_reproduces_the_broker_pnl():
    """The canonical case, now fully decoded from the 720x1280 copy.

    The entry block reads verbatim::

        STRIKE SELECTED
        Strike       : 77500
        Option Type  : CE
        Premium      : 102.85
        FIRST-TICK ENTRY ATTEMPT 1/3
        First Tick Price : 102.85
        Buffer           : 10.25
        Order Price      : 113.1
        Order ID : 260820000004685

    So this case pins the *order price* as well as the P&L, using the observed
    automatic entry policy rather than a placeholder.
    """
    pair = make_pair(77500.0, "V1CE", "V1PE", "2026-08-20", upper=2000.0)
    cfg = ATMPremiumImbalanceConfig(
        enabled=True, quantity=100,
        entry_price_policy="FIRST_TICK_PLUS_BUFFER", entry_buffer_points=10.25,
    ).validate()
    strategy = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=100, trade_id="v1")
    broker = ScriptedBroker(entry_fill=113.10, exit_fill=126.60,
                            entry_order_id="260820000004685",
                            exit_order_id="260820000007450")

    ticks = [
        ("CE", 102.85, 102.4, 103.3), ("PE", 168.25, 167.8, 168.7),
        ("CE", 126.90, 126.4, 127.3),
        ("CE", 128.10, 127.10, 128.5),   # crosses 113.10 + 15; bid 127.1
    ]
    intent = drive(strategy, broker, ticks)
    assert intent.kind == "complete"

    s = strategy.summary()
    assert strategy.signal.action == "BUY_CE"          # 102.85 < 168.25
    assert (s["strike"], s["option"]) == (77500.0, "CE")
    assert strategy.trade.first_tick_price == 102.85   # "First Tick Price : 102.85"
    assert s["entry_order_price"] == 113.10            # 102.85 + 10.25, as printed
    assert s["entry"] == 113.10                        # broker fill
    assert s["target"] == 128.10                       # 113.10 + 15
    assert s["exit_order_price"] == 126.60             # best bid 127.1 - 0.50
    assert s["exit"] == 126.60
    assert s["points"] == 13.50
    assert s["pnl"] == 1350.0                          # matches the Upstox UI
    assert strategy.trade.entry_order_id == "260820000004685"


def test_the_evidence_record_documents_the_buffer_as_observed():
    """The 10.25 buffer is a printed parameter, and the record must say so.

    It was previously recorded as REJECTED on the reading that it was measured
    slippage. Guarding the corrected wording so the reversal cannot silently be
    undone by a later edit.
    """
    from app.engines.atm_premium_imbalance import CONTRACT_VERSION
    assert CONTRACT_VERSION == "A230.3"
    prov = open("../docs/strategy/atm-premium-imbalance/A232_PARAMETER_PROVENANCE.md").read()
    assert "10.25" in prov
    assert "OBSERVED" in prov
    # and the un-rejection is explained rather than just swapped
    assert "Buffer : 10.25" in prov


# ------------------------------------------------------ lifecycle guarantees

def test_one_trade_then_no_more():
    pair = make_pair(77600.0, "A", "B", "2026-07-30")
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=20).validate()
    strategy = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=20)
    broker = ScriptedBroker(entry_fill=100.0, exit_fill=116.0)

    drive(strategy, broker, [
        ("CE", 100.0, 99.5, 100.5), ("PE", 200.0, 199.5, 200.5),
        ("CE", 115.0, 114.5, 115.5),      # 100 + 15 -> exit
    ])
    assert strategy.trades_taken == 1
    assert strategy.phase.value == "done"

    # Further ticks must not open anything.
    before = strategy.summary()
    drive(strategy, broker, [("CE", 50.0, 49.5, 50.5), ("PE", 300.0, 299.5, 300.5)])
    assert strategy.summary() == before
    assert strategy.trades_taken == 1


def test_duplicate_ticks_do_not_create_a_second_entry():
    pair = make_pair(77600.0, "A", "B", "2026-07-30")
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=20).validate()
    strategy = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=20)
    broker = ScriptedBroker(entry_fill=133.40, exit_fill=156.85)
    ticks = [("CE", 167.50, 167.0, 167.5), ("PE", 214.85, 214.4, 215.3)]
    drive(strategy, broker, ticks * 6)
    buys = [s for s in broker.submitted if s[0] == "BUY"]
    assert len(buys) == 1
    assert strategy.trade.entry_price == 133.40


def test_unresolved_reconciliation_halts_instead_of_retrying():
    from app.engines.atm_premium_imbalance import ReconcileState
    pair = make_pair(77600.0, "A", "B", "2026-07-30")
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=20).validate()
    strategy = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=20)

    intent = strategy.on_option_tick(
        LegQuote(instrument_id=pair.ce.instrument_id, ltp=167.50, bid=167.0, ask=167.5,
                 exchange_ts_ms=1, received_ts_ms=1, sequence=1), 1)
    intent = strategy.on_option_tick(
        LegQuote(instrument_id=pair.pe.instrument_id, ltp=214.85, bid=214.4, ask=215.3,
                 exchange_ts_ms=2, received_ts_ms=2, sequence=2), 2)
    assert intent.kind == "submit_entry"

    intent = strategy.record_entry_submit(intent.priced, order_id="A1")
    assert intent.kind == "poll_entry"
    intent = strategy.record_entry_status(None)            # status unknown
    assert intent.kind == "reconcile_entry"
    intent = strategy.record_entry_reconciliation(ReconcileState.DIVERGED)
    assert intent.kind == "halt"
    assert strategy.trade.state.value == "reconciliation_required"

# ------------------------------------------------- 2026-08-21 -- the put side

def test_2026_08_21_put_side_trade():
    """The first observed put-side entry, and the case that corrected two rules.

    Established by the recording:
      * ``CE : 491.15 | PE : 337.15 | Difference : 154.00`` -- a *positive*
        difference with the call dearer, which is what proves the printed value
        is absolute rather than signed ``PE - CE``.
      * The Upstox notification: ``Order for 80/80 was traded at the price of
        Rs. 340.10. Order #260821000004158``.
      * The contract is ``SENSEX26AUG7...`` -- the *monthly* August symbol, on a
        day that is not an expiry day, so the expiry policy is NEAREST.

    Not established: the strike (the notification truncates it), and the exit.
    The exit fill below is therefore scripted only to drive the lifecycle; the
    assertions cover the entry side and the target, nothing more.
    """
    pair = make_pair(81000.0, "A21CE", "A21PE", "2026-08-27", upper=3000.0)
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=80, expiry_policy="NEAREST").validate()
    strategy = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=80, trade_id="v0821")
    broker = ScriptedBroker(entry_fill=340.10, exit_fill=356.00,
                            entry_order_id="260821000004158")

    intent = drive(strategy, broker, [
        ("CE", 491.15, 490.5, 491.6), ("PE", 337.15, 336.6, 337.6),
        ("PE", 350.00, 349.5, 350.5),
        ("PE", 355.10, 355.20, 355.6),      # crosses 340.10 + 15
    ])
    assert intent.kind == "complete"
    s = strategy.summary()

    # --- signal: the cheaper leg is the PUT here
    assert strategy.signal.action == "BUY_PE"
    assert strategy.signal.option_type == "PE"
    assert strategy.signal.difference == 154.00      # absolute, not -154.00
    assert strategy.trade.instrument_id == "BSE_FO|A21PE"
    # --- entry accounting uses the broker fill from the notification
    assert s["entry"] == 340.10
    assert s["quantity"] == 80                        # 4 SENSEX lots of 20
    # --- target is the same +15 rule, on the put
    assert s["target"] == 355.10
    assert s["option"] == "PE"


def test_put_side_conformance_marks_the_unknown_fields_unverified():
    """The 2026-08-21 strike and exit were not legible; they must not be faked."""
    from app.engines.atm_premium_imbalance.conformance import build_report
    pair = make_pair(81000.0, "A21CE", "A21PE", "2026-08-27", upper=3000.0)
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=80, expiry_policy="NEAREST").validate()
    strategy = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=80, trade_id="v0821")
    broker = ScriptedBroker(entry_fill=340.10, exit_fill=356.00)
    drive(strategy, broker, [
        ("CE", 491.15, 490.5, 491.6), ("PE", 337.15, 336.6, 337.6),
        ("PE", 355.10, 355.20, 355.6),
    ])
    observed = {"option": "PE", "quantity": 80, "entry": 340.10}   # all we actually have
    report = build_report(case="2026-08-21 put side", observed=observed, summary=strategy.summary())
    assert report["mismatch"] == 0
    assert report["match"] == 3
    assert report["unverified"] >= 8          # strike, exit, points, pnl, ...

