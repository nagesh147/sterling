from app.services import live_safety


def test_account_daily_pnl_is_authoritative_for_orb_safety(monkeypatch):
    monkeypatch.setattr(
        "app.services.kite_engine.state.daily_realized_pnl",
        lambda uid: -1600.0,
    )
    live_safety.configure_daily_loss(
        live_safety.DailyLossConfig(soft_warn_inr=-1000.0, hard_halt_inr=-1500.0)
    )
    decision = live_safety.assert_safe_to_trade(
        positions=[],
        idempotency_key="orb-test",
        uid="user-1",
        check_daily_loss=True,
    )
    assert decision.allowed is False
    assert decision.code == "daily_loss_halt"
    assert "-1600.00" in decision.reason


def test_account_daily_pnl_is_not_confused_with_empty_position_snapshot(monkeypatch):
    monkeypatch.setattr(
        "app.services.kite_engine.state.daily_realized_pnl",
        lambda uid: -1100.0,
    )
    live_safety.configure_daily_loss(
        live_safety.DailyLossConfig(soft_warn_inr=-1000.0, hard_halt_inr=-1500.0)
    )
    state = live_safety.daily_loss_state([], uid="user-2")
    assert state["pnl_inr"] == -1100.0
    assert state["level"] == "warning"
