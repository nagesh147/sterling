"""Property tests over randomised-but-seeded inputs.

Seeded rather than generative so a failure is reproducible from the test name
alone, and so the suite adds no dependency.
"""
import random

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig,
    InstrumentRef,
    LegQuote,
    OptionPairRef,
    PremiumQuoteCache,
    align_to_tick,
    evaluate,
    exit_order_price,
    price_entry,
    q2,
    select_atm_strike,
    target_price,
)

SEED = 20260820
CFG = ATMPremiumImbalanceConfig()


def _pair():
    def leg(ot, token):
        return InstrumentRef(
            instrument_id=f"BSE_FO|{token}", tradingsymbol=f"S{ot}",
            option_type=ot, strike=77600.0, expiry="2026-07-30",
            lot_size=20, tick_size=0.05, upper_circuit=1745.45,
        )
    return OptionPairRef(underlying="SENSEX", expiry="2026-07-30", strike=77600.0,
                         ce=leg("CE", "1"), pe=leg("PE", "2"))


def _prices(rng):
    return round(rng.uniform(0.05, 900.0), 2), round(rng.uniform(0.05, 900.0), 2)


def test_difference_is_always_the_absolute_gap():
    """The source bot prints |PE - CE|; it stays positive when CE is dearer."""
    rng = random.Random(SEED)
    pair = _pair()
    for _ in range(3000):
        ce, pe = _prices(rng)
        cache = PremiumQuoteCache(pair)
        cache.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=ce, received_ts_ms=1))
        cache.on_option_tick(LegQuote(instrument_id=pair.pe.instrument_id, ltp=pe, received_ts_ms=1))
        view = cache.view("COMPATIBILITY", 1)
        assert view.difference == q2(abs(pe - ce))
        assert view.difference >= 0
        assert view.signed_difference == q2(pe - ce)


def test_cheaper_leg_is_always_the_one_bought():
    rng = random.Random(SEED + 1)
    pair = _pair()
    for _ in range(3000):
        ce, pe = _prices(rng)
        if ce == pe:
            continue
        cache = PremiumQuoteCache(pair)
        cache.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=ce, received_ts_ms=1))
        cache.on_option_tick(LegQuote(instrument_id=pair.pe.instrument_id, ltp=pe, received_ts_ms=1))
        sig = evaluate(cache.view("COMPATIBILITY", 1), CFG)
        assert sig.action == ("BUY_CE" if ce < pe else "BUY_PE")
        # Direction comes from which leg is cheaper, never from a sign: the
        # reported difference is absolute and so carries no direction at all.
        assert sig.difference >= 0
        assert (sig.view.signed_difference > 0) == (ce < pe)


def test_target_is_always_fill_plus_target_points():
    rng = random.Random(SEED + 2)
    for _ in range(3000):
        fill = round(rng.uniform(0.05, 2000.0), 2)
        pts = round(rng.uniform(0.05, 100.0), 2)
        cfg = ATMPremiumImbalanceConfig(target_points=pts)
        assert target_price(fill, cfg) == q2(fill + pts)


def test_exit_price_is_always_below_the_bid_and_on_the_tick_grid():
    rng = random.Random(SEED + 3)
    for _ in range(3000):
        bid = round(rng.uniform(1.0, 2000.0), 2)
        buf = round(rng.uniform(0.0, 5.0), 2)
        cfg = ATMPremiumImbalanceConfig(exit_buffer_points=buf)
        px = exit_order_price(bid, cfg, tick_size=0.05)
        if px is None:
            assert bid - buf <= 0
            continue
        assert px <= bid                       # a sell is never priced above the bid
        assert px <= q2(bid - buf) + 1e-9      # rounding only ever goes down
        assert abs(round(px / 0.05) - px / 0.05) < 1e-6


def test_entry_limit_is_never_above_the_upper_circuit_and_on_the_grid():
    rng = random.Random(SEED + 4)
    for _ in range(3000):
        ask = round(rng.uniform(0.05, 3000.0), 2)
        buf = round(rng.uniform(0.0, 50.0), 2)
        uc = round(rng.uniform(1.0, 3000.0), 2)
        inst = InstrumentRef(
            instrument_id="BSE_FO|1", tradingsymbol="S", option_type="CE",
            strike=77600.0, expiry="2026-07-30", lot_size=20,
            tick_size=0.05, upper_circuit=uc,
        )
        cfg = ATMPremiumImbalanceConfig(entry_buffer_points=buf)
        try:
            priced = price_entry(cfg, inst, best_ask=ask)
        except ValueError:
            continue
        assert priced.limit_price <= uc + 1e-9
        assert priced.limit_price > 0
        assert abs(round(priced.limit_price / 0.05) - priced.limit_price / 0.05) < 1e-6
        assert priced.capped_by_upper_circuit == (priced.raw_price > uc)


def test_tick_alignment_never_moves_a_price_the_wrong_way():
    rng = random.Random(SEED + 5)
    for _ in range(4000):
        px = round(rng.uniform(0.05, 5000.0), 2)
        up = align_to_tick(px, 0.05, mode="up")
        down = align_to_tick(px, 0.05, mode="down")
        assert up >= px - 1e-9
        assert down <= px + 1e-9
        assert up - down < 0.05 + 1e-9


def test_atm_selection_is_always_a_listed_strike_and_minimal_distance():
    rng = random.Random(SEED + 6)
    for _ in range(2000):
        strikes = sorted({round(rng.uniform(70000, 85000), -2) for _ in range(rng.randint(2, 12))})
        spot = round(rng.uniform(70000, 85000), 2)
        chosen = select_atm_strike(spot, strikes)
        assert chosen in strikes
        best = min(abs(s - spot) for s in strikes)
        assert abs(chosen - spot) == pytest.approx(best, abs=1e-9)


def test_duplicate_identical_ticks_never_change_the_view():
    rng = random.Random(SEED + 7)
    pair = _pair()
    for _ in range(500):
        ce, pe = _prices(rng)
        cache = PremiumQuoteCache(pair)
        for _ in range(5):
            cache.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=ce,
                                          received_ts_ms=1, sequence=1))
            cache.on_option_tick(LegQuote(instrument_id=pair.pe.instrument_id, ltp=pe,
                                          received_ts_ms=1, sequence=1))
        v = cache.view("COMPATIBILITY", 1)
        assert (v.ce_price, v.pe_price) == (ce, pe)


def test_stale_quotes_can_only_ever_suppress_a_signal():
    rng = random.Random(SEED + 8)
    pair = _pair()
    for _ in range(1500):
        ce, pe = _prices(rng)
        if ce == pe:
            continue
        age = rng.randint(0, 8000)
        cache = PremiumQuoteCache(pair)
        cache.on_option_tick(LegQuote(instrument_id=pair.ce.instrument_id, ltp=ce, received_ts_ms=0))
        cache.on_option_tick(LegQuote(instrument_id=pair.pe.instrument_id, ltp=pe, received_ts_ms=0))
        sig = evaluate(cache.view("COMPATIBILITY", age), ATMPremiumImbalanceConfig(max_quote_age_ms=2000))
        if age > 2000:
            assert sig.action == "NO_TRADE"
        else:
            assert sig.action == ("BUY_CE" if ce < pe else "BUY_PE")
