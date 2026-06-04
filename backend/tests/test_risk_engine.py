"""
RISK ENGINE (Phase 4) — separated, rule-registry risk evaluation.

Additive: the engine evaluates registered rules (fail-closed, first breach
wins) and offers a shadow-comparison helper so it can run log-only against the
existing live_safety / OrderRouter checks before ever becoming authoritative.
"""
from app.engines.risk.engine import RiskEngine, RiskDecision


def test_empty_engine_allows():
    assert RiskEngine().evaluate(context={}).allowed is True


def test_passing_rule_returns_none_allows():
    eng = RiskEngine(rules=[("noop", lambda ctx: None)])
    assert eng.evaluate({}).allowed is True


def test_first_breach_wins_fail_closed():
    calls = []
    eng = RiskEngine(rules=[
        ("ok", lambda ctx: None),
        ("dd", lambda ctx: "max_dd_breach"),
        ("later", lambda ctx: calls.append("reached") or "never"),
    ])
    decision = eng.evaluate({})
    assert decision.allowed is False
    assert decision.code == "max_dd_breach"
    assert calls == []  # short-circuits on first breach


def test_rule_may_return_risk_decision():
    eng = RiskEngine(rules=[("x", lambda ctx: RiskDecision(allowed=False, code="c", reason="r"))])
    d = eng.evaluate({})
    assert d.allowed is False and d.code == "c" and d.reason == "r"


def test_register_adds_rule():
    eng = RiskEngine()
    eng.register("kill", lambda ctx: "kill_switch")
    assert eng.evaluate({}).code == "kill_switch"


def test_shadow_compare_reports_agreement():
    eng = RiskEngine(rules=[("dd", lambda ctx: "breach" if ctx.get("dd") else None)])
    # authoritative allowed=True, engine also allows → agree
    r1 = eng.shadow_compare({"dd": False}, authoritative_allowed=True)
    assert r1["agree"] is True
    # authoritative allowed=True but engine rejects → disagree (flagged for review)
    r2 = eng.shadow_compare({"dd": True}, authoritative_allowed=True)
    assert r2["agree"] is False
    assert r2["engine"].code == "breach"
