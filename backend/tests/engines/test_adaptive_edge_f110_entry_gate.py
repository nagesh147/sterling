from app.engines.adaptive_edge.f110_entry_gate import EntryDecision, F110Evidence, evaluate_entry


def good() -> F110Evidence:
    return F110Evidence(True, True, 10.0, 5.0, True, True, True)


def test_f110_allows_ce_when_all_source_gates_pass() -> None:
    assert evaluate_entry("CE", good()) is EntryDecision.BUY_CE


def test_f110_allows_pe_when_all_source_gates_pass() -> None:
    assert evaluate_entry("PE", good()) is EntryDecision.BUY_PE


def test_f110_fails_closed_on_non_positive_conservative_ev() -> None:
    e = F110Evidence(True, True, 10.0, 0.0, True, True, True)
    assert evaluate_entry("CE", e) is EntryDecision.NO_TRADE


def test_f110_fails_closed_on_missing_ev() -> None:
    e = F110Evidence(True, True, None, 5.0, True, True, True)
    assert evaluate_entry("CE", e) is EntryDecision.NO_TRADE


def test_f110_fails_closed_on_data_or_execution_gate() -> None:
    assert evaluate_entry("CE", F110Evidence(False, True, 10, 5, True, True, True)) is EntryDecision.NO_TRADE
    assert evaluate_entry("CE", F110Evidence(True, True, 10, 5, False, True, True)) is EntryDecision.NO_TRADE
    assert evaluate_entry("CE", F110Evidence(True, True, 10, 5, True, False, True)) is EntryDecision.NO_TRADE
    assert evaluate_entry("CE", F110Evidence(True, True, 10, 5, True, True, False)) is EntryDecision.NO_TRADE
