"""Crash recovery.

After a restart the strategy's state is gone but a position at the broker is
not. Two things must hold: arming must not open a second position on top of the
first, and adopting must not take charge of the wrong contract.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, InstrumentRef, OptionPairRef,
)
import app.services.atm_premium_imbalance_runner as R

IST = timezone(timedelta(hours=5, minutes=30))


class Pos:
    def __init__(self, symbol, size, entry_price, mark_price=0.0, pnl=0.0):
        self.symbol, self.size = symbol, size
        self.entry_price, self.mark_price, self.unrealized_pnl = entry_price, mark_price, pnl


def _pair(ce="SENSEX26AUG77500CE", pe="SENSEX26AUG77500PE"):
    def leg(ot, sym, token):
        return InstrumentRef(instrument_id=token, tradingsymbol=sym, option_type=ot,
                             strike=77500.0, expiry="2026-08-27", lot_size=20,
                             tick_size=0.05, upper_circuit=3000.0)
    return OptionPairRef(underlying="SENSEX", expiry="2026-08-27", strike=77500.0,
                         ce=leg("CE", ce, "111"), pe=leg("PE", pe, "222"))


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    R.clear()
    monkeypatch.setattr(R, "_is_market_open", lambda: True)
    yield
    R.clear()


@pytest.fixture
def broker(monkeypatch):
    """A Kite account reporting whatever positions the test sets."""
    box = {"positions": []}

    class Client:
        async def get_positions(self):
            return box["positions"]

    class Acct:
        connected = True
        is_paper = False

    from app.services.exchanges.kite import accounts
    monkeypatch.setattr(accounts, "get_active", lambda uid: Acct(), raising=False)

    async def acquire(acct):
        return Client()
    monkeypatch.setattr(accounts, "acquire_client", acquire, raising=False)
    return box


@pytest.fixture
def wired(monkeypatch, broker):
    import app.services.atm_premium_imbalance as svc
    cfg = ATMPremiumImbalanceConfig(enabled=True, sizing_mode="LOTS", lots=1,
                                    max_premium_at_risk_inr=40_000.0).validate()
    monkeypatch.setattr(svc, "get_config", lambda *a, **k: cfg, raising=False)
    box = {"pair": _pair()}

    async def resolve(uid, c):
        return box["pair"]
    monkeypatch.setattr(svc, "resolve_option_pair", resolve, raising=False)

    class TM:
        def __init__(self):
            self.subscribed = []

        async def subscribe(self, uid, tokens, mode="quote", owner=None):
            self.subscribed.append((tokens, owner))
            return {"ok": True}

        async def release(self, uid, tokens, owner):
            return {"ok": True}

    tm = TM()
    import app.services.exchanges.kite as kite_pkg
    monkeypatch.setattr(kite_pkg, "ticker_manager", tm, raising=False)
    return {"cfg": cfg, "pair": box, "tm": tm, "positions": broker}


# ------------------------------------------------------------------- detection

@pytest.mark.asyncio
async def test_a_long_option_with_no_session_is_reported(wired):
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    found = await R.orphan_positions("u1")
    assert len(found) == 1
    assert found[0]["symbol"] == "SENSEX26AUG77500PE"
    assert found[0]["option_type"] == "PE"
    assert found[0]["quantity"] == 20
    assert found[0]["entry_price"] == 268.65


@pytest.mark.asyncio
async def test_a_short_position_is_not_ours_to_adopt(wired):
    """This strategy only ever buys, so a short is somebody else's trade."""
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", -20, 268.65)]
    assert await R.orphan_positions("u1") == []


@pytest.mark.asyncio
async def test_a_flat_position_is_not_a_position(wired):
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 0, 268.65)]
    assert await R.orphan_positions("u1") == []


@pytest.mark.asyncio
async def test_another_underlying_is_ignored(wired):
    wired["positions"]["positions"] = [Pos("NIFTY26AUG24000CE", 50, 100.0)]
    assert await R.orphan_positions("u1") == []


@pytest.mark.asyncio
async def test_a_future_is_not_an_option(wired):
    wired["positions"]["positions"] = [Pos("SENSEX26AUGFUT", 20, 77500.0)]
    assert await R.orphan_positions("u1") == []


@pytest.mark.asyncio
async def test_a_live_session_explains_its_own_position(wired):
    """Nothing is orphaned while the session that opened it is still running."""
    strategy = R.ATMPremiumImbalanceStrategy(
        cfg=wired["cfg"], pair=_pair(), quantity=20, trade_id="live")
    R.register(R.Session(user_id="u1", cfg=wired["cfg"], pair=_pair(), strategy=strategy,
                         session_date=datetime.now(IST).date(),
                         ce_token=111, pe_token=222))
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    assert await R.orphan_positions("u1") == []


@pytest.mark.asyncio
async def test_a_broker_that_will_not_answer_reports_nothing_rather_than_raising(
        wired, monkeypatch):
    """This runs from the arm path; it must not turn a read failure into a crash.

    Reporting nothing is the wrong-but-safe direction here: arm() has its own
    gates, and a raised exception would take the whole arm down.
    """
    from app.services.exchanges.kite import accounts

    async def boom(acct):
        raise RuntimeError("kite down")
    monkeypatch.setattr(accounts, "acquire_client", boom, raising=False)
    assert await R.orphan_positions("u1") == []


# ---------------------------------------------------------------------- arming

@pytest.mark.asyncio
async def test_arming_refuses_while_a_position_is_unaccounted_for(wired):
    """The dangerous case: arming would open a second position on top."""
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    out = await R.arm("u1")
    assert out["status"] == "open_position_unaccounted"
    assert out["positions"][0]["symbol"] == "SENSEX26AUG77500PE"
    assert R.active_session("u1") is None
    assert wired["tm"].subscribed == []          # and nothing was subscribed


@pytest.mark.asyncio
async def test_arming_proceeds_when_the_book_is_flat(wired):
    assert (await R.arm("u1"))["status"] == "armed"


# -------------------------------------------------------------------- adopting

@pytest.mark.asyncio
async def test_adopting_puts_the_stop_and_target_back_to_work(wired):
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    out = await R.adopt("u1", "SENSEX26AUG77500PE")
    assert out["status"] == "adopted"
    s = R.active_session("u1")
    assert s is not None
    assert s.strategy.phase.value == "in_position"
    assert s.strategy.trade.entry_price == 268.65
    assert s.strategy.trade.quantity == 20
    assert s.strategy.trade.target_price == 283.65        # 268.65 + 15
    assert s.strategy.quantity == 20


@pytest.mark.asyncio
async def test_an_adopted_trade_says_it_was_adopted(wired):
    """Its pricing reference and its peak since entry are gone.

    Anything reporting on those has to be able to tell that this trade's history
    is unknown rather than empty.
    """
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    await R.adopt("u1", "SENSEX26AUG77500PE")
    trade = R.active_session("u1").strategy.trade
    assert trade.adopted is True
    assert trade.first_tick_price is None


@pytest.mark.asyncio
async def test_the_trail_resumes_from_the_entry_not_an_invented_peak(wired):
    """The peak since entry is unknowable, so it must not be guessed.

    Seeding it from, say, the current price would place the stop somewhere the
    position never actually reached.
    """
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65,
                                           mark_price=400.0)]
    await R.adopt("u1", "SENSEX26AUG77500PE")
    assert R.active_session("u1").strategy._high_water == 268.65


@pytest.mark.asyncio
async def test_adopting_the_wrong_contract_is_refused(wired):
    """If the ATM has moved, exiting would watch one option to sell another."""
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    wired["pair"]["pair"] = _pair(ce="SENSEX26AUG77900CE", pe="SENSEX26AUG77900PE")
    out = await R.adopt("u1", "SENSEX26AUG77500PE")
    assert out["status"] == "contract_mismatch"
    assert R.active_session("u1") is None


@pytest.mark.asyncio
async def test_adopting_something_that_is_not_there_is_refused(wired):
    out = await R.adopt("u1", "SENSEX26AUG99999PE")
    assert out["status"] == "not_found"
    assert R.active_session("u1") is None


@pytest.mark.asyncio
async def test_adopting_claims_the_legs_so_they_are_released_later(wired):
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    await R.adopt("u1", "SENSEX26AUG77500PE")
    assert wired["tm"].subscribed == [([111, 222], R.TICKER_OWNER)]


@pytest.mark.asyncio
async def test_an_adopted_position_can_still_be_armed_over_once_it_closes(wired):
    """Adoption is not a dead end."""
    wired["positions"]["positions"] = [Pos("SENSEX26AUG77500PE", 20, 268.65)]
    await R.adopt("u1", "SENSEX26AUG77500PE")
    R.active_session("u1").finished = True
    wired["positions"]["positions"] = []
    assert (await R.arm("u1"))["status"] == "armed"
