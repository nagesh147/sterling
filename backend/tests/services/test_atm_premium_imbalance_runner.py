"""Tick-driven runner: intent execution, gating and the no-double-order lock."""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, InstrumentRef, OptionPairRef,
    OrderReport, OrderStatus,
)
import app.services.atm_premium_imbalance_runner as R

IST = timezone(timedelta(hours=5, minutes=30))


class FakeBroker(R.BrokerPort):
    def __init__(self, entry_fill=133.40, exit_fill=156.85, fail_place=False, fail_cancel=False):
        self.entry_fill, self.exit_fill = entry_fill, exit_fill
        self.fail_place, self.fail_cancel = fail_place, fail_cancel
        self.placed, self.cancelled = [], []
        self._n = 0

    async def place(self, *, instrument_id, side, quantity, limit_price, tag):
        if self.fail_place:
            return None, "broker down"
        self._n += 1
        oid = f"O{self._n}"
        self.placed.append({"id": oid, "side": side, "qty": quantity,
                            "price": limit_price, "tag": tag})
        return oid, None

    async def status(self, order_id):
        rec = next((p for p in self.placed if p["id"] == order_id), None)
        if rec is None:
            return None
        px = self.entry_fill if rec["side"] == "BUY" else self.exit_fill
        return OrderReport(order_id=order_id, status=OrderStatus.COMPLETE,
                           transaction=rec["side"], average_price=px,
                           filled_quantity=rec["qty"])

    async def cancel(self, order_id):
        if self.fail_cancel:
            return False
        self.cancelled.append(order_id)
        return True


def _pair():
    def leg(ot, token):
        return InstrumentRef(instrument_id=token, tradingsymbol=f"SENSEX77600{ot}",
                             option_type=ot, strike=77600.0, expiry="2026-07-30",
                             lot_size=20, tick_size=0.05, upper_circuit=1745.45)
    return OptionPairRef(underlying="SENSEX", expiry="2026-07-30", strike=77600.0,
                         ce=leg("CE", "111"), pe=leg("PE", "222"))


def _session(protection_mode="NONE", quantity=20):
    pair = _pair()
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=quantity,
                                    protection_mode=protection_mode).validate()
    strat = ATMPremiumImbalanceStrategy(cfg=cfg, pair=pair, quantity=quantity, trade_id="t")
    return R.Session(user_id="u1", cfg=cfg, pair=pair, strategy=strat,
                     session_date=datetime.now(IST).date(), ce_token=111, pe_token=222)


def tick(token, ltp, bid, ask):
    return {"instrument_token": token, "last_price": ltp,
            "depth": {"buy": [{"price": bid, "quantity": 100}],
                      "sell": [{"price": ask, "quantity": 100}]}}


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    R.clear()
    monkeypatch.setattr(R, "_is_market_open", lambda: True)
    yield
    R.clear()


# ------------------------------------------------------------- gating

@pytest.mark.asyncio
async def test_no_session_is_inactive():
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "inactive"


@pytest.mark.asyncio
async def test_market_closed_is_refused(monkeypatch):
    R.register(_session())
    monkeypatch.setattr(R, "_is_market_open", lambda: False)
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "market_closed"


@pytest.mark.asyncio
async def test_a_stale_session_date_is_dropped():
    s = _session()
    s.session_date = datetime.now(IST).date() - timedelta(days=1)
    R.register(s)
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], FakeBroker()) == "session_rolled"
    assert R.active_session("u1") is None


@pytest.mark.asyncio
async def test_no_broker_means_no_orders():
    R.register(_session())
    assert await R.on_ticks("u1", [tick(111, 100.0, 99.5, 100.5)], None) == "no_broker"


@pytest.mark.asyncio
async def test_foreign_tokens_are_ignored():
    s = _session(); R.register(s)
    b = FakeBroker()
    await R.on_ticks("u1", [tick(999, 50.0, 49.5, 50.5)], b)
    assert b.placed == []
    assert s.strategy.phase.value == "idle"


# ------------------------------------------------------- full lifecycle

@pytest.mark.asyncio
async def test_end_to_end_entry_and_exit_without_protection():
    s = _session(); R.register(s)
    b = FakeBroker(entry_fill=133.40, exit_fill=156.85)

    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    assert s.strategy.trade.entry_price == 133.40
    assert s.strategy.trade.target_price == 148.40
    buys = [p for p in b.placed if p["side"] == "BUY"]
    assert len(buys) == 1 and buys[0]["price"] == 168.00     # ask 167.50 + 0.50

    out = await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    assert out == "complete"
    sells = [p for p in b.placed if p["side"] == "SELL"]
    assert len(sells) == 1 and sells[0]["price"] == 148.70   # bid 149.2 - 0.50
    assert s.strategy.trade.points == 23.45
    assert s.strategy.trade.pnl == 469.0
    assert s.finished is True


@pytest.mark.asyncio
async def test_protection_is_placed_then_cancelled_before_the_exit():
    s = _session(protection_mode="RESTING_TARGET_LIMIT"); R.register(s)
    b = FakeBroker()

    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    protect = [p for p in b.placed if p["tag"] == "api-protect"]
    assert len(protect) == 1
    assert protect[0]["price"] == 148.40 and protect[0]["side"] == "SELL"

    await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    # the resting sell was cancelled before our own sell went out
    assert b.cancelled == [protect[0]["id"]]
    exits = [p for p in b.placed if p["tag"] == "api-exit"]
    assert len(exits) == 1
    assert s.strategy.trade.points == 23.45


@pytest.mark.asyncio
async def test_a_failed_protection_cancel_halts_before_sending_a_second_sell():
    s = _session(protection_mode="RESTING_TARGET_LIMIT"); R.register(s)
    b = FakeBroker(fail_cancel=True)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    out = await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    assert out.startswith("halt:")
    assert [p for p in b.placed if p["tag"] == "api-exit"] == []


@pytest.mark.asyncio
async def test_one_trade_per_session_then_inactive():
    s = _session(); R.register(s)
    b = FakeBroker()
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    await R.on_ticks("u1", [tick(111, 149.10, 149.2, 149.6)], b)
    n = len(b.placed)
    assert await R.on_ticks("u1", [tick(111, 200.0, 199.5, 200.5)], b) == "inactive"
    assert len(b.placed) == n


@pytest.mark.asyncio
async def test_a_dead_broker_does_not_open_a_position():
    s = _session(); R.register(s)
    b = FakeBroker(fail_place=True)
    await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50),
                            tick(222, 214.85, 214.4, 215.3)], b)
    assert s.strategy.trade.entry_price is None
    assert b.placed == []


@pytest.mark.asyncio
async def test_concurrent_ticks_cannot_start_a_second_order():
    """The lock is the guard against a tick arriving mid-order."""
    import asyncio
    s = _session(); R.register(s)
    b = FakeBroker()
    lock = R._lock_for("u1")
    await lock.acquire()
    try:
        assert await R.on_ticks("u1", [tick(111, 167.50, 167.0, 167.50)], b) == "busy"
        assert b.placed == []
    finally:
        lock.release()


# ------------------------------------------------------ tick normalisation

def test_tick_normalisation_keeps_depth_and_both_timestamps():
    q = R._tick_to_quote("BSE_FO|1", tick(111, 167.50, 167.0, 167.9), now_ms=1234)
    assert (q.ltp, q.bid, q.ask) == (167.50, 167.0, 167.9)
    assert q.received_ts_ms == 1234
    assert q.source == "kite_ticker"


def test_missing_depth_yields_no_bid_or_ask_rather_than_ltp():
    """Synthesising depth from the last trade would change entry and exit prices."""
    q = R._tick_to_quote("BSE_FO|1", {"instrument_token": 111, "last_price": 167.5}, now_ms=1)
    assert q.ltp == 167.5
    assert q.bid is None and q.ask is None


# --------------------------------------------- timestamp handling (defect 1)

SESSION_OPEN = datetime(2026, 8, 21, 9, 15, tzinfo=IST)
SESSION_OPEN_MS = int(SESSION_OPEN.timestamp() * 1000)
PRIOR_TRADE = datetime(2026, 8, 20, 15, 33, tzinfo=IST)
PRIOR_TRADE_MS = int(PRIOR_TRADE.timestamp() * 1000)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        (0, None),
        (SESSION_OPEN, SESSION_OPEN_MS),                       # datetime
        (int(SESSION_OPEN.timestamp()), SESSION_OPEN_MS),      # epoch SECONDS (Kite binary)
        (SESSION_OPEN_MS, SESSION_OPEN_MS),                    # already ms
        ("nonsense", None),
    ],
)
def test_epoch_normalisation_accepts_every_form_kite_sends(raw, expected):
    assert R._epoch_ms(raw) == expected


def test_the_trade_clock_is_never_substituted_with_receipt_time():
    """The defect: epoch-seconds ints failed an isinstance(datetime) check and the
    receipt time was written into the exchange stamp, destroying the evidence."""
    tick = {"instrument_token": 111, "last_price": 379.0,
            "last_trade_time": int(PRIOR_TRADE.timestamp()),
            "exchange_timestamp": int(SESSION_OPEN.timestamp()),
            "ohlc": {"open": 356.7, "high": 356.7, "low": 318.0, "close": 366.6},
            "volume_traded": 0}
    q = R._tick_to_quote("212614405", tick, now_ms=SESSION_OPEN_MS)
    assert q.last_trade_ts_ms == PRIOR_TRADE_MS        # preserved, not overwritten
    assert q.exchange_ts_ms == SESSION_OPEN_MS
    assert q.received_ts_ms == SESSION_OPEN_MS
    assert q.official_open == 356.7
    assert q.prev_close == 366.6
    # and the quote dates itself correctly
    assert q.is_session_origin(SESSION_OPEN_MS) is False


def test_a_tick_with_no_trade_stamp_reports_unknown_not_fresh():
    q = R._tick_to_quote("212614405", {"instrument_token": 111, "last_price": 356.7},
                         now_ms=SESSION_OPEN_MS)
    assert q.last_trade_ts_ms is None
    assert q.is_session_origin(SESSION_OPEN_MS) is None


# ------------------------------------- end to end: the stale tick is refused

def _pin_clock(monkeypatch, at_ms):
    monkeypatch.setattr(R, "_now_ms", lambda: at_ms)


def full_tick(token, ltp, bid, ask, *, traded_at, official_open=356.7, volume=222120):
    return {"instrument_token": token, "last_price": ltp,
            "last_trade_time": int(traded_at.timestamp()),
            "exchange_timestamp": int(traded_at.timestamp()),
            "ohlc": {"open": official_open, "high": 545.6, "low": 318.0, "close": 366.6},
            "volume_traded": volume,
            "depth": {"buy": [{"price": bid, "quantity": 100}],
                      "sell": [{"price": ask, "quantity": 100}]}}


@pytest.mark.asyncio
async def test_a_previous_session_price_places_no_order(monkeypatch):
    """The real 2026-08-21 fault, driven through the runner."""
    _pin_clock(monkeypatch, SESSION_OPEN_MS + 1000)
    s = _session(); R.register(s)
    b = FakeBroker()
    out = await R.on_ticks("u1", [
        full_tick(111, 500.00, 499.5, 500.5, traded_at=PRIOR_TRADE),
        full_tick(222, 379.00, 378.5, 379.5, traded_at=PRIOR_TRADE),
    ], b)
    assert out == "idle"
    assert b.placed == []                              # nothing was sent
    assert s.strategy.trade is None


@pytest.mark.asyncio
async def test_a_session_price_prices_off_the_real_open(monkeypatch):
    """Same instant, same legs, but stamped inside the session.

    356.70 x 1.10 = 392.37 -> 392.4, against the 416.90 the stale tick produced.
    """
    _pin_clock(monkeypatch, SESSION_OPEN_MS + 1000)
    s = _session(quantity=80); R.register(s)
    s.strategy.cfg = ATMPremiumImbalanceConfig(
        enabled=True, quantity=80, entry_price_policy="FIRST_TICK_PERCENT",
        entry_through_pct=0.10).validate()
    b = FakeBroker(entry_fill=340.10, exit_fill=400.0)
    traded = SESSION_OPEN + timedelta(milliseconds=900)
    await R.on_ticks("u1", [
        full_tick(111, 500.00, 499.5, 500.5, traded_at=traded),
        full_tick(222, 356.70, 356.2, 357.2, traded_at=traded),
    ], b)
    buys = [p for p in b.placed if p["side"] == "BUY"]
    assert len(buys) == 1
    assert buys[0]["price"] == 392.40
    assert s.strategy.trade.option_type == "PE"        # 356.70 < 500.00
