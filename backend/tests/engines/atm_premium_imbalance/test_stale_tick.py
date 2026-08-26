"""The stale-tick defect, and the gate that closes it.

Real values, from Kite historical for SENSEX 77700 PE (token 212614405):

    2026-08-21 09:15 bar   open 356.70  high 356.70  low 318.00  close 334.25
    2026-08-20 15:32-15:33 range        373.90 .. 379.90
    2026-08-21 first trade of the day   09:15 (Kite reports none earlier)

The recorded bot priced its entry from ``First Tick Used : 379.0``, which cannot
be a 2026-08-21 session trade: 379.0 is unreachable until 09:19, and the log
records the fill (340.10, only reachable 09:15-09:16) arriving 680 ms after the
order. It then multiplied that stale value by 1.10 and sent 416.90 into a market
whose open was 356.70.

Our own implementation was vulnerable to exactly the same thing, for two reasons
these tests pin down: the runner discarded the exchange timestamp, and the
freshness gate measured *receipt* age, which a stale-content tick passes trivially.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, InstrumentRef, LegQuote, OptionPairRef,
    PremiumQuoteCache, evaluate, price_entry,
)

IST = timezone(timedelta(hours=5, minutes=30))

#: 2026-08-21 09:15:00 IST, the session open, in epoch ms.
SESSION_OPEN_MS = int(datetime(2026, 8, 21, 9, 15, tzinfo=IST).timestamp() * 1000)
#: A trade from the previous session's close-out, 2026-08-20 15:33 IST.
PRIOR_TRADE_MS = int(datetime(2026, 8, 20, 15, 33, tzinfo=IST).timestamp() * 1000)

REAL_OPEN_PE = 356.70          # the exchange's official open
STALE_LTP_PE = 379.00          # what the bot priced from
REAL_OPEN_CE = 500.00


def leg(ot, token):
    return InstrumentRef(instrument_id=token, tradingsymbol=f"SENSEX26AUG77700{ot}",
                         option_type=ot, strike=77700.0, expiry="2026-08-27",
                         lot_size=20, tick_size=0.05, upper_circuit=3000.0)


@pytest.fixture
def pair():
    return OptionPairRef(underlying="SENSEX", expiry="2026-08-27", strike=77700.0,
                         ce=leg("CE", "212046597"), pe=leg("PE", "212614405"))


def stale(instrument_id, ltp):
    """A tick received now whose trade happened in the previous session."""
    return LegQuote(
        instrument_id=instrument_id, ltp=ltp, bid=ltp - 0.5, ask=ltp + 0.5,
        exchange_ts_ms=PRIOR_TRADE_MS, received_ts_ms=SESSION_OPEN_MS,
        last_trade_ts_ms=PRIOR_TRADE_MS, volume_traded=0, official_open=None,
        prev_close=366.60, sequence=1,
    )


def live(instrument_id, ltp, *, ts_ms=None, official_open=None):
    ts = ts_ms if ts_ms is not None else SESSION_OPEN_MS + 900
    return LegQuote(
        instrument_id=instrument_id, ltp=ltp, bid=ltp - 0.5, ask=ltp + 0.5,
        exchange_ts_ms=ts, received_ts_ms=ts, last_trade_ts_ms=ts,
        volume_traded=222120, official_open=official_open, prev_close=366.60, sequence=2,
    )


# ------------------------------------------------- the defect, characterised

def test_receipt_age_cannot_detect_a_stale_tick():
    """Why the existing freshness gate structurally misses this class of fault.

    The tick's *content* is a day old; its *receipt* is instantaneous. Any gate
    built on receipt time passes it.
    """
    q = stale("212614405", STALE_LTP_PE)
    assert q.age_ms(SESSION_OPEN_MS) == 0          # perfectly "fresh" by receipt
    assert q.last_trade_ts_ms < SESSION_OPEN_MS    # but the trade is from yesterday


def test_a_stale_tick_is_recognised_as_not_session_origin():
    assert stale("212614405", STALE_LTP_PE).is_session_origin(SESSION_OPEN_MS) is False
    assert live("212614405", REAL_OPEN_PE).is_session_origin(SESSION_OPEN_MS) is True


def test_an_undatable_tick_is_unknown_not_assumed_good():
    """A quote-mode tick carries no last_trade_time. That is not evidence of
    freshness, so it must report unknown rather than True."""
    q = LegQuote(instrument_id="212614405", ltp=REAL_OPEN_PE, received_ts_ms=SESSION_OPEN_MS)
    assert q.is_session_origin(SESSION_OPEN_MS) is None


# ------------------------------------------------------------ the signal gate

def test_a_proven_stale_pair_produces_no_signal(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(stale(pair.ce.instrument_id, REAL_OPEN_CE))
    cache.on_option_tick(stale(pair.pe.instrument_id, STALE_LTP_PE))
    cfg = ATMPremiumImbalanceConfig().validate()
    sig = evaluate(cache.view("COMPATIBILITY", SESSION_OPEN_MS), cfg,
                   session_open_ms=SESSION_OPEN_MS)
    assert sig.action == "NO_TRADE"
    assert sig.reason == "stale_session_quote"


def test_a_live_pair_signals_normally(pair):
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(live(pair.ce.instrument_id, REAL_OPEN_CE))
    cache.on_option_tick(live(pair.pe.instrument_id, REAL_OPEN_PE))
    cfg = ATMPremiumImbalanceConfig().validate()
    sig = evaluate(cache.view("COMPATIBILITY", SESSION_OPEN_MS), cfg,
                   session_open_ms=SESSION_OPEN_MS)
    assert sig.action == "BUY_PE"                  # 356.70 < 500.00


def test_the_gate_can_be_switched_off_only_for_replay(pair):
    """Reproducing a defective system is legitimate; trading it is not."""
    cfg = ATMPremiumImbalanceConfig(require_session_origin_tick=False).validate()
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(stale(pair.ce.instrument_id, REAL_OPEN_CE))
    cache.on_option_tick(stale(pair.pe.instrument_id, STALE_LTP_PE))
    sig = evaluate(cache.view("COMPATIBILITY", SESSION_OPEN_MS), cfg,
                   session_open_ms=SESSION_OPEN_MS)
    assert sig.action == "BUY_PE"                  # the bug, deliberately reproduced

    with pytest.raises(ValueError, match="require_session_origin_tick"):
        ATMPremiumImbalanceConfig(
            require_session_origin_tick=False, execution_mode="live",
            quote_mode="EXECUTABLE", quantity=80,
            protection_mode="RESTING_TARGET_LIMIT",
        ).validate()


# ----------------------------------------------------- the pricing reference

def test_the_cache_only_offers_a_session_origin_first_price(pair):
    """The stale tick arrives first; the pricing reference must skip it."""
    cache = PremiumQuoteCache(pair)
    cache.on_option_tick(stale(pair.pe.instrument_id, STALE_LTP_PE))
    assert cache.first_price_for("PE") == STALE_LTP_PE                       # raw history
    assert cache.first_session_price_for("PE", SESSION_OPEN_MS) is None      # nothing valid yet

    cache.on_option_tick(live(pair.pe.instrument_id, REAL_OPEN_PE))
    assert cache.first_session_price_for("PE", SESSION_OPEN_MS) == REAL_OPEN_PE


def test_pricing_from_the_real_open_gives_the_corrected_order_price():
    """356.70 x 1.10 = 392.37 -> 392.4, against the bot's 416.90."""
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10).validate()
    priced = price_entry(cfg, leg("PE", "212614405"), best_ask=None,
                        first_tick_price=REAL_OPEN_PE)
    assert priced.limit_price == 392.40


def test_pricing_from_the_stale_tick_reproduces_the_bot_exactly():
    """Kept as the forensic baseline: the rule is right, the input was not."""
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10).validate()
    priced = price_entry(cfg, leg("PE", "212614405"), best_ask=None,
                        first_tick_price=STALE_LTP_PE)
    assert priced.limit_price == 416.90
    assert round(416.90 - 392.40, 2) == 24.50


def test_official_open_source_uses_the_exchanges_own_answer():
    """`first_tick_source=OFFICIAL_OPEN` prices off ohlc.open, which is
    definitionally a session price and needs no dating."""
    cfg = ATMPremiumImbalanceConfig(
        entry_price_policy="FIRST_TICK_PERCENT", entry_through_pct=0.10,
        first_tick_source="OFFICIAL_OPEN").validate()
    priced = price_entry(cfg, leg("PE", "212614405"), best_ask=None,
                        first_tick_price=STALE_LTP_PE, official_open=REAL_OPEN_PE)
    assert priced.limit_price == 392.40            # the stale tick is ignored
    assert priced.reference_kind == "official_open"
