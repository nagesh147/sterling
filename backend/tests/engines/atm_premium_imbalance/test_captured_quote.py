"""Real captured ticks, and what they prove about clock semantics.

Captured 2026-08-21 23:16 IST (Friday, market closed) from the live Kite session
for the two contracts the 2026-08-21 recording traded. Two independent captures
agreeing on every field:

1. ``GET /api/v1/kite/quote`` -- REST, timestamps as strings.
2. A **binary WebSocket tick** pulled off ``kite_ticks:default`` after forcing a
   re-subscribe, i.e. through ``exchanges/kite/ticker.parse_packet`` -- the exact
   path the runner consumes. Timestamps arrive as ``int`` epoch **seconds**::

       token 212614405  mode=full
         last_price         = 358.65
         last_trade_time    = 1787306999   -> 2026-08-21 15:39:59 IST
         exchange_timestamp = 1787309751   -> 2026-08-21 16:25:51 IST
         ohlc               = {open 356.70, high 433.0, low 318.0, close 369.75}
         volume_traded      = 10152900
         L1 bid/ask         = 0.0 / 0.0

The epoch-seconds form is why the previous `isinstance(ts, datetime)` check always
failed, and the 2752-second gap between the two clocks is why
``exchange_timestamp`` may not stand in for ``last_trade_time``.

Values frozen here so the conclusions survive the contract expiring.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import ATMPremiumImbalanceConfig, InstrumentRef, price_entry
from app.engines.atm_premium_imbalance import OptionPairRef, PremiumQuoteCache
import app.services.atm_premium_imbalance_runner as R

IST = timezone(timedelta(hours=5, minutes=30))


def ist(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=IST)


#: Verbatim from the binary tick capture. Epoch SECONDS, as Kite sends them.
LAST_TRADE_EPOCH = 1787306999      # 2026-08-21 15:39:59 IST
EXCHANGE_EPOCH    = 1787309751      # 2026-08-21 16:25:51 IST

CAPTURE = {
    "PE": {"token": 212614405, "timestamp": EXCHANGE_EPOCH,
           "last_trade_time": LAST_TRADE_EPOCH, "last_price": 358.65,
           "ohlc": {"open": 356.70, "high": 433.0, "low": 318.0, "close": 369.75},
           "volume": 10152900},
    "CE": {"token": 212046597, "timestamp": EXCHANGE_EPOCH,
           "last_trade_time": LAST_TRADE_EPOCH, "last_price": 361.85,
           "ohlc": {"open": 500.00, "high": 545.6, "low": 352.75, "close": 444.35},
           "volume": 9054500},
}

#: The next session after the capture. 2026-08-22 is a Saturday.
NEXT_OPEN_MS = int(ist(2026, 8, 24, 9, 15).timestamp() * 1000)
#: Friday's own open, for the cross-check below.
FRIDAY_OPEN_MS = int(ist(2026, 8, 21, 9, 15).timestamp() * 1000)


def as_tick(leg):
    c = CAPTURE[leg]
    return {"instrument_token": c["token"], "last_price": c["last_price"],
            "last_trade_time": c["last_trade_time"], "exchange_timestamp": c["timestamp"],
            "ohlc": c["ohlc"], "volume_traded": c["volume"],
            # market closed -> no live book, exactly as captured
            "depth": {"buy": [{"price": 0, "quantity": 0}],
                      "sell": [{"price": 0, "quantity": 0}]}}


def quote(leg, now_ms):
    return R._tick_to_quote(str(CAPTURE[leg]["token"]), as_tick(leg), now_ms)


def inst(ot):
    return InstrumentRef(instrument_id=str(CAPTURE[ot]["token"]),
                         tradingsymbol=f"SENSEX26AUG77700{ot}", option_type=ot,
                         strike=77700.0, expiry="2026-08-27", lot_size=20,
                         tick_size=0.05, upper_circuit=1696.1)


# ------------------------------------ the two clocks are genuinely different

def test_kite_sends_epoch_seconds_which_is_why_the_old_check_failed():
    """The captured stamps are plain ints, not datetimes.

    `_tick_to_quote` previously tested `isinstance(ts, datetime)`; against this
    real payload that is False, so the receipt time was written into the exchange
    stamp and the trade clock was lost entirely.
    """
    assert isinstance(CAPTURE["PE"]["last_trade_time"], int)
    assert not isinstance(CAPTURE["PE"]["last_trade_time"], datetime)
    q = quote("PE", now_ms=NEXT_OPEN_MS)
    assert q.last_trade_ts_ms == LAST_TRADE_EPOCH * 1000        # preserved
    assert q.exchange_ts_ms == EXCHANGE_EPOCH * 1000


def test_the_packet_clock_runs_ahead_of_the_trade_clock():
    """Why `exchange_timestamp` cannot stand in for `last_trade_time`.

    They are 2752 seconds apart in a single real tick: the exchange kept updating
    until 16:25:51 while the last trade was at 15:39:59. A gate keyed on the
    packet clock would date this price 46 minutes after it actually traded, and
    during a pre-open -- where the packet clock advances but no trade has occurred
    -- it would pass a previous session's price as current.
    """
    q = quote("PE", now_ms=int(ist(2026, 8, 21, 23, 16).timestamp() * 1000))
    assert q.exchange_ts_ms > q.last_trade_ts_ms
    assert (q.exchange_ts_ms - q.last_trade_ts_ms) // 1000 == 2752


def test_the_captured_price_is_stale_for_the_next_session():
    q = quote("PE", now_ms=NEXT_OPEN_MS + 1000)
    assert q.ltp == 358.65
    assert q.is_session_origin(NEXT_OPEN_MS) is False        # Friday's trade
    assert q.is_session_origin(FRIDAY_OPEN_MS) is True       # ...but Friday's own session


def test_the_runner_preserves_every_field_needed_to_judge_this():
    q = quote("PE", now_ms=NEXT_OPEN_MS)
    assert q.last_trade_ts_ms == LAST_TRADE_EPOCH * 1000
    assert q.official_open == 356.70
    assert q.prev_close == 369.75
    assert q.volume_traded == 10152900


# ------------------------------------------- ohlc.open is stale too (the hole)

def test_the_published_open_is_the_previous_sessions_until_today_trades():
    """`ohlc.open` = 356.70 in this capture is FRIDAY's 09:15 open.

    Independently corroborated: the minute bar fetched for 2026-08-21 09:15 opens
    at 356.70. So the field is session-to-date and carries no timestamp, which is
    why it has to be dated by the leg's last trade rather than trusted outright.
    """
    pair = OptionPairRef(underlying="SENSEX", expiry="2026-08-27", strike=77700.0,
                         ce=inst("CE"), pe=inst("PE"))
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(quote("PE", now_ms=NEXT_OPEN_MS))

    # ungated it hands back Friday's open...
    assert cache.official_open_for("PE") == 356.70
    # ...but dated against the next session it is withheld
    assert cache.official_open_for("PE", NEXT_OPEN_MS) is None
    # and against Friday's own session it is legitimately Friday's open
    assert cache.official_open_for("PE", FRIDAY_OPEN_MS) == 356.70


def test_official_open_source_cannot_be_fooled_by_a_previous_sessions_open():
    """The failure this closes: pricing Monday's entry off Friday's open."""
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10,
        first_tick_source="OFFICIAL_OPEN").validate()
    with pytest.raises(ValueError, match="OFFICIAL_OPEN requires"):
        price_entry(cfg, inst("PE"), best_ask=None, first_tick_price=None,
                    official_open=None)          # withheld by the cache


# ------------------------------------------------- the closed book is refused

def test_no_live_book_means_marketable_ask_refuses_rather_than_guessing():
    """Captured depth is 0/0 with the market closed."""
    q = quote("PE", now_ms=NEXT_OPEN_MS)
    assert q.ask is None and q.bid is None
    cfg = ATMPremiumImbalanceConfig().validate()          # MARKETABLE_ASK
    with pytest.raises(ValueError, match="requires a live ask"):
        price_entry(cfg, inst("PE"), best_ask=q.ask)


def test_the_pair_of_captured_quotes_yields_no_signal_for_the_next_session():
    from app.engines.atm_premium_imbalance import evaluate
    pair = OptionPairRef(underlying="SENSEX", expiry="2026-08-27", strike=77700.0,
                         ce=inst("CE"), pe=inst("PE"))
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(quote("CE", now_ms=NEXT_OPEN_MS))
    cache.on_option_tick(quote("PE", now_ms=NEXT_OPEN_MS))
    sig = evaluate(cache.view("COMPATIBILITY", NEXT_OPEN_MS),
                   ATMPremiumImbalanceConfig().validate(),
                   session_open_ms=NEXT_OPEN_MS)
    assert sig.action == "NO_TRADE"
    assert sig.reason == "stale_session_quote"
