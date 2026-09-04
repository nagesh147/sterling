from app.engines.opening_volume_parity import compare_opening_sessions


def _row(session, symbol, *, tier="strong", rvol=5.0, orb="09:16"):
    return {
        "session_date": session,
        "symbol": symbol,
        "direction": "UP",
        "tier": tier,
        "rvol": rvol,
        "signal_time": "09:15",
        "orb_break_time": orb,
        "combo": orb == "09:16",
    }


def test_multi_session_comparison_reports_recall_extras_and_field_mismatches():
    expected = [
        _row("2026-09-02", "AAA"),
        _row("2026-09-03", "BBB", rvol=10.0),
        _row("2026-09-03", "CCC"),
    ]
    actual = [
        _row("2026-09-02", "AAA", rvol=5.03),
        _row("2026-09-03", "BBB", rvol=9.0),
        _row("2026-09-03", "EXTRA"),
    ]

    result = compare_opening_sessions(expected, actual)

    assert result["summary"] == {
        "session_count": 2,
        "expected_count": 3,
        "matched_count": 1,
        "missing_count": 1,
        "extra_count": 1,
        "mismatched_count": 1,
        "recall_pct": 33.33,
        "exact_match": False,
    }
    bbb = next(row for row in result["comparisons"] if row["symbol"] == "BBB")
    assert bbb["mismatches"] == ["rvol"]
