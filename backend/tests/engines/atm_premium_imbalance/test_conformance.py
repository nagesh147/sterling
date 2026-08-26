"""Conformance reporting, and the generated validation report.

The report exists so a claim of fidelity is reproducible. These tests guard the
one property that makes it honest: a field the recording never established is
reported UNVERIFIED, not silently omitted and not counted as a pass.
"""
import pytest

from app.engines.atm_premium_imbalance.conformance import (
    MATCH, MISMATCH, UNVERIFIED, build_report, compare, format_report,
    straddle_parity_strike,
)

from .test_golden_trades import (  # reuse the golden harness
    V17_STREAM, ScriptedBroker, drive, make_pair,
)
from app.engines.atm_premium_imbalance import (
    ATMPremiumImbalanceConfig, ATMPremiumImbalanceStrategy, ManualPriceTable,
)


#: Exactly what V17's frames printed. Nothing derived, nothing filled in.
V17_OBSERVED = {
    "strike": 77600.0, "option": "CE", "quantity": 20,
    "entry_order_price": 288.75, "entry": 133.40,
    "trigger": 149.10, "exit_order_price": 148.70, "exit": 156.85,
    "points": 23.45, "pnl": 469.0, "attempts": 1,
    # "target" was never printed -> deliberately absent.
}


def run_v17():
    pair = make_pair(77600.0, "1141595", "1145203", "2026-07-30")
    cfg = ATMPremiumImbalanceConfig(
        enabled=True, entry_price_policy="MANUAL_FILE",
        manual_price_file="strike_prices.txt", quantity=20,
    ).validate()
    s = ATMPremiumImbalanceStrategy(
        cfg=cfg, pair=pair, quantity=20, trade_id="v17",
        manual_table=ManualPriceTable.parse("77600CE 288.75"),
    )
    broker = ScriptedBroker(entry_fill=133.40, exit_fill=156.85)
    drive(s, broker, [("CE", 167.50, 167.0, 167.50), ("PE", 214.85, 214.4, 215.3)] + V17_STREAM)
    return s


def test_v17_replay_is_fully_conformant():
    report = build_report(case="V17 / 2026-07-30", observed=V17_OBSERVED, summary=run_v17().summary())
    assert report["mismatch"] == 0
    assert report["conformant"] is True
    assert report["match"] == 11        # every field the recording established
    assert report["unverified"] == 1    # 'target' was never printed


def test_unestablished_fields_are_unverified_not_passes():
    report = build_report(case="x", observed={"strike": 77600.0}, summary={"strike": 77600.0})
    verdicts = {r["field"]: r["verdict"] for r in report["rows"]}
    assert verdicts["strike"] == MATCH
    assert verdicts["entry"] == UNVERIFIED
    # An unverified field must never be counted toward the match total.
    assert report["match"] == 1
    assert report["unverified"] == len(report["rows"]) - 1


def test_a_mismatch_is_reported_and_fails_conformance():
    report = build_report(case="x", observed={"entry": 133.40}, summary={"entry": 288.75})
    assert report["conformant"] is False
    assert report["mismatch"] == 1
    row = next(r for r in report["rows"] if r["field"] == "entry")
    assert row["verdict"] == MISMATCH
    assert (row["observed"], row["replayed"]) == (133.40, 288.75)


def test_compare_treats_missing_observation_as_unverified():
    assert compare("f", None, 1.0).verdict == UNVERIFIED
    assert compare("f", 1.0, 1.0).verdict == MATCH
    assert compare("f", 1.0, 1.01).verdict == MISMATCH
    assert compare("f", 1.0, 1.01, tolerance=0.05).verdict == MATCH


def test_report_renders_a_markdown_table_with_citations():
    text = format_report(build_report(case="V17", observed=V17_OBSERVED, summary=run_v17().summary()))
    assert "| Field | Observed | Replayed | Verdict | Evidence |" in text
    assert "A231/E6" in text          # entry fill cites its evidence row
    assert "conformant: yes" in text


def test_parity_estimate_is_documented_as_unreliable_at_the_open():
    """V17's own numbers show why parity cannot pick the strike.

    Parity says 77686 from the first post-open tick; the bot printed 77600.
    Both are 'correct' -- the LTPs were independently stale (A231/M6).
    """
    assert straddle_parity_strike(77638.86, 167.50, 214.85) == 77686.21
    # V04, where the quotes were not first-tick stale, lands on a real strike.
    assert straddle_parity_strike(77370.77, 482.05, 620.00) == 77508.72
