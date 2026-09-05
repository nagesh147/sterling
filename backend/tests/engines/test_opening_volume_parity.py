from app.engines.opening_volume_parity import compare_opening_sessions


def _row(session, symbol, *, tier="strong", rvol=5.0, orb="09:16"):
    return {
        "session_date": session,
        "symbol": symbol,
        "direction": "UP",
        "tier": tier,
        "rvol": rvol,
        # ORION labels the first ORB event as the visible signal time.
        "signal_time": orb,
        "orb_break_time": orb,
        "combo": True,
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


def test_september_4_orion_cards_accept_late_aligned_combo_times():
    """Freeze the observable SPURT+ ORION cards captured on 2026-09-05.

    This verifies comparison semantics only.  It deliberately does not claim
    independent RVOL reproduction without broker minute bars.
    """

    observed = [
        ("KEI", "DOWN", "explosive", 36.21, "15:02", True),
        ("ANGELONE", "UP", "explosive", 14.24, "09:16", True),
        ("POLYCAB", "DOWN", "explosive", 10.17, "11:13", True),
        ("HAVELLS", "DOWN", "strong", 9.03, "09:22", True),
        ("SWIGGY", "UP", "spurt", 4.40, "09:16", True),
        ("BSE", "UP", "spurt", 3.99, "09:17", True),
        ("HAL", "UP", "spurt", 3.23, "09:19", False),
    ]
    orion_rows = [
        {
            "session_date": "2026-09-04",
            "symbol": symbol,
            "direction": direction,
            "tier": tier,
            "rvol": rvol,
            "signal_time": event_time,
            "orb_break_time": event_time,
            "combo": combo,
        }
        for symbol, direction, tier, rvol, event_time, combo in observed
    ]
    sterling_rows = [
        {
            **row,
            "signal_time": "2026-09-04T09:15:00+05:30",
            "volume_signal_time": "2026-09-04T09:15:00+05:30",
            "actionable_signal_time": f"2026-09-04T{row['orb_break_time']}:00+05:30",
        }
        for row in orion_rows
    ]

    result = compare_opening_sessions(orion_rows, sterling_rows)

    assert result["summary"]["exact_match"] is True
    assert result["summary"]["matched_count"] == 7
