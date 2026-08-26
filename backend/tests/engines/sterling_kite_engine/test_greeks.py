import pytest

from app.services.kite_engine.greeks import black_scholes_greeks, premium_stop_from_move


# ── delta-implied premium stop (shared spot→premium stop translation) ─────────
def test_premium_stop_from_move_call_entry_below():
    # CE (delta +0.5). At entry the trail sits 40 pts BELOW spot → premium ~20 lower
    # → stop 80 (a real protective stop below entry).
    assert premium_stop_from_move(entry_premium=100.0, delta=0.5, spot=25000.0,
                                  trail_level=24960.0) == 80.0


def test_premium_stop_from_move_put_entry_above():
    # PE (delta −0.5, signed). At entry the bear trail sits 40 pts ABOVE spot →
    # premium ~20 lower → stop 80, symmetric with the call case.
    assert premium_stop_from_move(entry_premium=100.0, delta=-0.5, spot=25000.0,
                                  trail_level=25040.0) == 80.0


def test_premium_stop_from_move_call_trails_into_profit():
    # CE: once the ST trail RATCHETS 100 pts ABOVE the entry spot, the stop rises
    # above the entry premium (locks profit) — no re-quote needed.
    assert premium_stop_from_move(entry_premium=100.0, delta=0.5, spot=25000.0,
                                  trail_level=25100.0) == 150.0


def test_premium_stop_from_move_put_trails_into_profit():
    # PE: trail ratchets 100 pts BELOW entry spot → signed delta flips the term
    # positive → stop above entry premium.
    assert premium_stop_from_move(entry_premium=100.0, delta=-0.5, spot=25000.0,
                                  trail_level=24900.0) == 150.0


def test_premium_stop_from_move_floors_at_zero():
    # a move larger than the whole premium can't produce a negative stop.
    assert premium_stop_from_move(entry_premium=10.0, delta=0.9, spot=25000.0,
                                  trail_level=24000.0) == 0.0


def test_premium_stop_from_move_degenerate_entry_returns_zero():
    assert premium_stop_from_move(entry_premium=0.0, delta=0.9, spot=100.0,
                                  trail_level=90.0) == 0.0


def test_atm_call_put_delta_relationship():
    call = black_scholes_greeks(spot=100, strike=100, dte_days=30, iv=0.2, option_type="CE")
    put = black_scholes_greeks(spot=100, strike=100, dte_days=30, iv=0.2, option_type="PE")
    # ATM call delta ~0.5+, put delta ~-0.5; call - put delta ≈ 1 (put-call parity in delta)
    assert 0.45 < call.delta < 0.65
    assert -0.55 < put.delta < -0.35
    assert abs((call.delta - put.delta) - 1.0) < 0.02
    # shared, positive gamma/vega; negative theta (time decay) for a long option
    assert call.gamma > 0 and put.gamma > 0
    assert call.vega > 0 and put.vega > 0
    assert call.theta < 0 and put.theta < 0
    assert abs(call.gamma - put.gamma) < 1e-9  # gamma identical for call/put


def test_deep_itm_call_delta_near_one():
    g = black_scholes_greeks(spot=200, strike=100, dte_days=30, iv=0.2, option_type="CE")
    assert g.delta > 0.95


def test_expired_option_is_intrinsic():
    itm = black_scholes_greeks(spot=110, strike=100, dte_days=0, iv=0.2, option_type="CE")
    otm = black_scholes_greeks(spot=90, strike=100, dte_days=0, iv=0.2, option_type="CE")
    assert itm.delta == 1.0 and otm.delta == 0.0
    assert itm.gamma == 0.0 and itm.vega == 0.0 and itm.theta == 0.0


def test_implied_vol_round_trips():
    from app.services.kite_engine.greeks import bs_price, implied_vol
    px = bs_price(spot=100, strike=100, dte_days=30, iv=0.22, option_type="CE")
    iv = implied_vol(price=px, spot=100, strike=100, dte_days=30, option_type="CE")
    assert abs(iv - 0.22) < 0.005


def test_implied_vol_below_intrinsic_returns_zero():
    from app.services.kite_engine.greeks import implied_vol
    # price below intrinsic (110-100=10) is unsolvable
    assert implied_vol(price=5.0, spot=110, strike=100, dte_days=30, option_type="CE") == 0.0


# ── implied_vol (Newton-Raphson + bisection fallback) ─────────────────────────
from app.services.kite_engine.greeks import implied_vol, bs_price  # noqa: E402


def test_implied_vol_round_trips_when_well_conditioned():
    """Price at a known IV, solve it back. Only asserts where the IV is actually
    identifiable from price — i.e. vega is non-trivial. Deep-ITM/OTM low-vol options
    have ~zero vega, so IV is unrecoverable from premium for ANY solver; those are
    excluded (their greeks are IV-insensitive anyway). Guards the Newton solver."""
    import random
    random.seed(11)
    checked = 0
    for _ in range(4000):
        ot = random.choice(["CE", "PE"])
        spot = random.uniform(50, 25000)
        strike = spot * random.uniform(0.8, 1.2)
        dte = random.uniform(1.0, 90)
        iv0 = random.uniform(0.05, 2.5)
        price = bs_price(spot=spot, strike=strike, dte_days=dte, iv=iv0, option_type=ot)
        if price < 0.05:
            continue
        intrinsic = max(0.0, (spot - strike) if ot == "CE" else (strike - spot))
        if price < intrinsic - 1e-6:       # European value below undiscounted intrinsic
            continue                       # → solver returns 0.0 by contract (guarded)
        g = black_scholes_greeks(spot=spot, strike=strike, dte_days=dte, iv=iv0, option_type=ot)
        if g.vega < 0.01 * spot / 100.0:   # IV ill-conditioned here — not recoverable
            continue
        iv = implied_vol(price=price, spot=spot, strike=strike, dte_days=dte, option_type=ot)
        assert abs(iv - iv0) < 1e-3, (ot, spot, strike, dte, iv0, iv, price)
        checked += 1
    assert checked > 1000


def test_implied_vol_rejects_below_intrinsic():
    # price under intrinsic is unsolvable → 0.0 (unchanged contract)
    assert implied_vol(price=0.01, spot=120, strike=100, dte_days=30, option_type="CE") == 0.0
    assert implied_vol(price=0.0, spot=100, strike=100, dte_days=30, option_type="CE") == 0.0


def test_implied_vol_converges_at_high_vol():
    p = bs_price(spot=20000, strike=20000, dte_days=7, iv=1.8, option_type="CE")
    assert abs(implied_vol(price=p, spot=20000, strike=20000, dte_days=7, option_type="CE") - 1.8) < 1e-3


# ── the vol used to translate an underlying move into a premium stop ──────────
class TestEffectiveIV:
    """The GTT trigger and the stop on the board have to be the same number.

    The board backs IV out of the option's premium; the stop translation used a flat
    18%. On a chain printing 40% vol the two disagree about where the trade is
    protected, and the broker's trigger is the one that actually fires.
    """

    def test_solves_the_vol_out_of_the_option_price(self):
        from app.services.kite_engine.greeks import bs_price
        from app.services.kite_engine.service import _effective_iv

        price = bs_price(spot=25_000, strike=25_200, dte_days=7, iv=0.42, option_type="CE")
        got = _effective_iv(price=price, spot=25_000, strike=25_200,
                            dte_days=7, option_type="CE")
        assert got == pytest.approx(0.42, abs=0.01)

    def test_falls_back_when_there_is_no_quote(self):
        from app.services.kite_engine.service import _IV_ASSUMPTION, _effective_iv

        assert _effective_iv(price=0.0, spot=25_000, strike=25_200,
                             dte_days=7, option_type="CE") == _IV_ASSUMPTION

    def test_falls_back_on_a_degenerate_solve(self):
        """A premium below intrinsic is not a tradable price; implied_vol returns 0."""
        from app.services.kite_engine.service import _IV_ASSUMPTION, _effective_iv

        got = _effective_iv(price=1.0, spot=25_000, strike=20_000,
                            dte_days=7, option_type="CE")
        assert got == _IV_ASSUMPTION

    def test_falls_back_on_an_absurd_solve(self):
        """A price near the spot itself solves to a pinned, meaningless vol."""
        from app.services.kite_engine.service import _IV_ASSUMPTION, _effective_iv

        got = _effective_iv(price=24_000.0, spot=25_000, strike=25_200,
                            dte_days=7, option_type="CE")
        assert got == _IV_ASSUMPTION

    def test_an_expired_contract_falls_back(self):
        from app.services.kite_engine.service import _IV_ASSUMPTION, _effective_iv

        assert _effective_iv(price=50.0, spot=25_000, strike=25_200,
                             dte_days=0, option_type="CE") == _IV_ASSUMPTION


# ── the number on screen IS the number placed ────────────────────────────────

class TestTheBoardStopAndThePlacedStopAgree:
    """docs/kite_signal_audit_2026-08-04.md:867 — "the broker stop is not the stop on
    screen". Auto-exec used a flat 18% IV while the board solved IV out of the entry
    premium, so the two translated the same SuperTrend level into different premiums
    and the resting GTT sat somewhere the user had never been shown.

    `_effective_iv` fixed that, and both sides are unit-tested — but nothing tested the
    thing the finding is actually about: that the two paths AGREE. Each is free to
    drift from the other while both stay individually green, which is how the gap
    opened the first time. This pins the equivalence itself.
    """

    #: The audit's own worked example: an AXISBANK bear row, ~30 DTE, 1260 PE at ₹80.
    #: It reported the board showing ₹68.80 against a placed ₹66.52.
    SPOT = 1228.9
    TRAIL = 1250.0
    STRIKE = 1260.0
    ENTRY = 80.0
    DTE_DAYS = 30

    def _row_and_leg(self):
        import time
        from datetime import datetime, timedelta, timezone
        from app.engines.sterling_kite_engine.schemas import (
            AlignmentChip, EngineSignalRow, OptionLeg)
        expiry = (datetime.now(timezone.utc) + timedelta(days=self.DTE_DAYS)).strftime("%Y-%m-%d")
        leg = OptionLeg(moneyness="OTM1", option_type="PE",
                        option_symbol="AXISBANK25SEP1260PE", strike=self.STRIKE,
                        expiry=expiry, lot_size=625, premium_spot=self.ENTRY)
        row = EngineSignalRow(
            underlying="AXISBANK", token=1, exchange="NFO", regime="BEAR",
            alignment=AlignmentChip(fast=-1, mid=-1, slow=-1),
            direction="short", option_type="PE", legs=[leg],
            spot=self.SPOT, underlying_spot=self.SPOT, stop_loss=self.TRAIL,
            score=85.0, timestamp_ms=int(time.time() * 1000))
        return row, leg

    @pytest.mark.asyncio
    async def test_the_two_paths_translate_the_trail_identically(self):
        from app.services.kite_engine.scanner import _stamp_leg_premium_stops
        from app.services.kite_engine.service import _resolve_premium_stop

        row, leg = self._row_and_leg()
        _stamp_leg_premium_stops(row, leg)          # what the board shows
        shown = float(leg.premium_sl)

        class _Quoting:
            async def get_ltp(self, keys):
                return {k: {"last_price": self.ENTRY} for k in keys}
            ENTRY = 80.0

        _entry, placed, _delta = await _resolve_premium_stop(   # what auto-exec arms
            _Quoting(), exch="NFO", symbol=leg.option_symbol, strike=self.STRIKE,
            expiry=leg.expiry, option_type="PE", spot=self.SPOT, trail_level=self.TRAIL)

        assert placed == pytest.approx(shown, rel=0.005), (
            f"the board shows a stop at ₹{shown:.2f} and the broker GTT would be armed "
            f"at ₹{placed:.2f} — the user reasons off one and is protected at the other")

    @pytest.mark.asyncio
    async def test_a_flat_assumption_would_break_the_agreement(self):
        """Guards the guard: with the vol forced back to the flat assumption the two
        diverge, so the test above is measuring something real rather than passing
        because both sides happen to be degenerate."""
        from app.services.kite_engine.greeks import black_scholes_greeks, premium_stop_from_move
        from app.services.kite_engine.scanner import _stamp_leg_premium_stops
        from app.services.kite_engine.service import _IV_ASSUMPTION

        row, leg = self._row_and_leg()
        _stamp_leg_premium_stops(row, leg)
        shown = float(leg.premium_sl)

        flat = black_scholes_greeks(spot=self.SPOT, strike=self.STRIKE,
                                    dte_days=self.DTE_DAYS, iv=_IV_ASSUMPTION,
                                    option_type="PE")
        flat_stop = premium_stop_from_move(entry_premium=self.ENTRY, delta=flat.delta,
                                           spot=self.SPOT, trail_level=self.TRAIL)

        assert flat_stop != pytest.approx(shown, rel=0.005), (
            "the flat-IV stop and the solved-IV stop are indistinguishable here, so the "
            "agreement test above proves nothing — pick a fixture where vol matters")
