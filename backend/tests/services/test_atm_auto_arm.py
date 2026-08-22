"""Arming had to happen by hand at 09:14 every trading morning.

That is not a convenience problem. The mornings a human misses are **not
random** -- they correlate with being busy, away, or asleep after a bad night --
so manual arming biases the very sample the journal is collecting. A biased win
rate is worse than no win rate, because it looks like an answer.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import atm_premium_imbalance_runner as runner

IST = timezone(timedelta(hours=5, minutes=30))


def _ms(y, m, d, hh, mm) -> int:
    return int(datetime(y, m, d, hh, mm, tzinfo=IST).timestamp() * 1000)


# 2026-08-24 is a Monday, 2026-08-23 a Sunday.
MONDAY = (2026, 8, 24)
SUNDAY = (2026, 8, 23)


@pytest.mark.parametrize("hh,mm,expected,why", [
    (8, 50, False, "25 minutes early — outside the lead"),
    (8, 59, False, "one minute before the lead opens"),
    (9,  0, True,  "the lead opens exactly 15 minutes before the bell"),
    (9,  5, True,  "inside the 15-minute pre-open lead"),
    (9, 14, True,  "one minute before the bell"),
    (9, 30, True,  "market open"),
    (16, 0, False, "after the close"),
])
def test_the_arming_window(hh, mm, expected, why):
    assert runner.can_arm_now(_ms(*MONDAY, hh, mm)) is expected, why


def test_arming_is_refused_on_a_non_trading_day():
    """A weekend has no session bounds, so there is nothing to lead into."""
    assert runner.can_arm_now(_ms(*SUNDAY, 9, 5)) is False
    assert runner.can_arm_now(_ms(*SUNDAY, 11, 0)) is False


def test_the_lead_opens_exactly_at_the_boundary():
    from app.services.navigator.calendar import session_bounds_ist
    from datetime import date
    open_dt, _ = session_bounds_ist(date(*MONDAY))
    lead = timedelta(minutes=runner.ARM_LEAD_MINUTES)
    just_inside = int((open_dt - lead).timestamp() * 1000)
    just_outside = just_inside - 60_000
    assert runner.can_arm_now(just_inside) is True
    assert runner.can_arm_now(just_outside) is False


def test_pre_open_arming_cannot_itself_cause_a_trade():
    """The safety property that makes the pre-open lead acceptable.

    Arming resolves the pair and subscribes; entry is gated separately on
    verified market hours. If these two ever collapse into one check, this fails.
    """
    pre_open = _ms(*MONDAY, 9, 5)
    assert runner.can_arm_now(pre_open) is True
    # _is_market_open has no injection point on purpose — it is the live gate.
    # What matters is that it is a *different* function, consulted by on_ticks.
    import inspect
    src = inspect.getsource(runner.on_ticks)
    assert "_is_market_open()" in src, (
        "on_ticks must keep its own market-hours gate; the pre-open arming lead "
        "is only safe because entry is checked independently"
    )


@pytest.mark.asyncio
async def test_auto_arm_does_nothing_outside_the_window(monkeypatch):
    monkeypatch.setattr(runner, "can_arm_now", lambda *a, **k: False)
    called = []
    monkeypatch.setattr(runner, "arm", lambda *a, **k: called.append(a))
    assert await runner.auto_arm_once() == {}
    assert not called


@pytest.mark.asyncio
async def test_auto_arm_does_nothing_when_the_strategy_is_disabled(monkeypatch):
    """Disabled is the default, so the loop must be inert out of the box."""
    monkeypatch.setattr(runner, "can_arm_now", lambda *a, **k: True)
    monkeypatch.setattr(runner, "_kite_user_ids", lambda: ["u1"])
    assert await runner.auto_arm_once() == {}


@pytest.mark.asyncio
async def test_one_broken_account_does_not_stop_the_others(monkeypatch):
    """A single bad account must not cost every other user their morning."""
    from app.engines.atm_premium_imbalance import ATMPremiumImbalanceConfig
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=80).validate()

    monkeypatch.setattr(runner, "can_arm_now", lambda *a, **k: True)
    monkeypatch.setattr(runner, "_kite_user_ids", lambda: ["bad", "good"])
    import app.services.atm_premium_imbalance as store
    monkeypatch.setattr(store, "get_config", lambda: cfg)

    async def fake_arm(uid, c=None):
        if uid == "bad":
            raise RuntimeError("token expired")
        return {"status": "armed", "strike": 24500.0}

    monkeypatch.setattr(runner, "arm", fake_arm)
    monkeypatch.setattr(runner, "_sessions", {})
    out = await runner.auto_arm_once()
    assert out == {"bad": "error", "good": "armed"}


@pytest.mark.asyncio
async def test_an_already_armed_user_is_skipped_without_resolving_the_chain(monkeypatch):
    """Idempotence cheaply: arm() is idempotent too, but it walks the option
    chain to discover that, and this loop runs every 30 seconds."""
    from app.engines.atm_premium_imbalance import ATMPremiumImbalanceConfig
    cfg = ATMPremiumImbalanceConfig(enabled=True, quantity=80).validate()
    monkeypatch.setattr(runner, "can_arm_now", lambda *a, **k: True)
    monkeypatch.setattr(runner, "_kite_user_ids", lambda: ["u1"])
    import app.services.atm_premium_imbalance as store
    monkeypatch.setattr(store, "get_config", lambda: cfg)

    class _S:
        session_date = datetime.now(IST).date()
    monkeypatch.setattr(runner, "_sessions", {"u1": _S()})

    async def boom(*a, **k):
        raise AssertionError("arm() must not be called for an armed user")
    monkeypatch.setattr(runner, "arm", boom)
    assert await runner.auto_arm_once() == {}
