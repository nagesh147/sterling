"""
`capital_at_risk_pct` must be the dollar-at-risk as a % of the REAL account NAV,
not a hardcoded $100k. The old formula `max_risk / 100_000 * 100` collapsed the
Risk% column to ~0.00% for any real (small) account: a correct 0.25%-risk scalp on
a $500 book risks ~$1.25, and $1.25/$100k = 0.00125% → rendered "0.00%".

The fix divides by the caller-supplied account equity (legacy $100k fallback when
unknown), so the reported risk matches what was actually configured.
"""
import pytest

from app.api.v1.endpoints.trading import _capital_at_risk_pct


def test_uses_account_equity_not_hardcoded_100k():
    # $500 book, stop $0.25 away, 5 coins → $1.25 at risk = 0.25% of the book.
    max_risk, pct = _capital_at_risk_pct(
        entry_price=79.0, stop_loss=78.75, qty=5.0,
        position_value=79.0 * 5.0, instrument_type="futures",
        account_equity=500.0,
    )
    assert max_risk == pytest.approx(1.25)
    # Real per-trade risk — NOT the old 0.00125% the $100k denominator produced.
    assert pct == pytest.approx(0.25, abs=1e-6)


def test_falls_back_to_100k_when_equity_unknown():
    # Callers that don't supply equity keep the legacy denominator unchanged.
    _, pct = _capital_at_risk_pct(
        entry_price=79.0, stop_loss=78.75, qty=5.0,
        position_value=79.0 * 5.0, instrument_type="futures",
        account_equity=None,
    )
    assert pct == pytest.approx(1.25 / 100_000.0 * 100.0)


def test_no_stop_uses_notional_estimate():
    # Without a stop, risk is estimated from notional (2% futures / 5% options).
    pv = 1000.0
    mr_fut, _ = _capital_at_risk_pct(
        entry_price=79.0, stop_loss=None, qty=5.0,
        position_value=pv, instrument_type="futures", account_equity=500.0,
    )
    mr_opt, _ = _capital_at_risk_pct(
        entry_price=79.0, stop_loss=None, qty=5.0,
        position_value=pv, instrument_type="options", account_equity=500.0,
    )
    assert mr_fut == pytest.approx(pv * 0.02)
    assert mr_opt == pytest.approx(pv * 0.05)


def test_zero_entry_yields_zero_pct():
    _, pct = _capital_at_risk_pct(
        entry_price=0.0, stop_loss=78.75, qty=5.0,
        position_value=0.0, instrument_type="futures", account_equity=500.0,
    )
    assert pct == 0.0
